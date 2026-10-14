"""Ham API yanıtlarını DEĞİŞTİRMEDEN saklar.

Kurallar:
1. Gelen yanıta dokunulmaz. Temizleme ve dönüştürme sonraki katmanın işi.
   Şemayı yanlış anladığımızı sonradan fark edersek, ham veri sayesinde
   geçmişi baştan işleyebiliriz.
2. Her tur ayrı bir dosyaya yazılır; dosya adı UTC zaman damgalıdır.
3. Dosyalar gzip ile sıkıştırılır. Ölçülen: tek bir liste yanıtı ~56 KB,
   sıkıştırınca ~8 KB. Günde 288 turla aylık ~480 MB yerine ~70 MB.
4. Ham kapta var olan bir dosyanın üzerine yazılmaz. Aynı ad tekrar yazılmak
   istenirse uyarı loglanır ve var olan dosya korunur.

İki depo var ve ikisi de aynı dört metoda sahip (yaz, yaz_bayt, listele,
oku_bayt): YerelDepo diske, BlobDepo Azure'a yazar. Kodun geri kalanı hangisiyle
konuştuğunu bilmez; depo_olustur() ayara bakıp doğru olanı verir. L1 (tablo.py)
aynı sınıfları hem ham veriyi okumak hem tabloyu yazmak için kullanıyor. Tablo
kabında üzerine yazma açık, çünkü bir gün tekrar işlenebilmeli.

Geçersiz yanıtlar "hatali/" önekiyle aynı ham kaba yazılır. L1 sadece
"YYYY/MM/DD/" önekini okuduğu için bu dosyalar ona karışmaz.
"""

import gzip
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from yervar import ayarlar
from yervar.gunluk import gunluk_al

gunluk = gunluk_al(__name__)


def simdi_utc() -> datetime:
    """Şu anki zamanı UTC olarak döndürür.

    Projedeki tek zaman kaynağı budur. Yerel saatle kayıt yapılırsa yaz saati
    geçişinde bir saat ya tekrarlanır ya kaybolur ve bu veri onarılamaz.
    """
    return datetime.now(UTC)


def ham_yol(zaman: datetime, etiket: str) -> str:
    """Bir turun göreli dosya yolu: 2026/09/17/14/parklar_20260917T143000Z.json.gz

    Saat bazlı klasörler, tek bir klasörde on binlerce dosya birikmesini önler
    ve "sadece dünü oku" gibi sorguları ucuzlatır.
    """
    return f"{zaman:%Y/%m/%d/%H}/{etiket}_{zaman:%Y%m%dT%H%M%SZ}.json.gz"


def hatali_yol(zaman: datetime, etiket: str) -> str:
    """Geçersiz bir yanıtın yolu: hatali/2026/10/14/09/parklar_20261014T090000Z.govde.gz

    Uzantı .json.gz değil, çünkü gövde JSON olmayabilir (bakım sayfası gibi).
    """
    return f"hatali/{zaman:%Y/%m/%d/%H}/{etiket}_{zaman:%Y%m%dT%H%M%SZ}.govde.gz"


def meta_temizle(meta: dict[str, Any] | None) -> dict[str, str] | None:
    """Blob meta verisi sadece ASCII kabul ediyor. Değerleri metne çevirip
    ASCII dışı karakterleri ? yapıyoruz ve uzunluğu sınırlıyoruz."""
    if not meta:
        return None
    return {k: str(v).encode("ascii", "replace").decode("ascii")[:256] for k, v in meta.items()}


def _sikistir(icerik: Any) -> bytes:
    """İçeriği Türkçe karakterleri koruyarak JSON'a çevirip gzip ile sıkıştırır."""
    return gzip.compress(json.dumps(icerik, ensure_ascii=False).encode("utf-8"))


class YerelDepo:
    """Dosyaları yerel diske yazar ve okur (geliştirme ortamı).

    uzerine_yaz=False ise var olan dosyaya dokunulmaz (ham kap).
    Meta veri yerelde tutulmuyor, verilirse yok sayılıyor.
    """

    def __init__(self, kok: Path, uzerine_yaz: bool = True) -> None:
        self.kok = kok
        self.uzerine_yaz = uzerine_yaz

    def yaz(self, goreli_yol: str, icerik: Any, meta: dict[str, Any] | None = None) -> str:
        """İçeriği JSON'a çevirip sıkıştırarak yazar."""
        return self.yaz_bayt(goreli_yol, _sikistir(icerik), meta)

    def yaz_bayt(self, goreli_yol: str, veri: bytes, meta: dict[str, Any] | None = None) -> str:
        """Hazır baytları atomik olarak yazar.

        Atomik yazma: önce .tmp dosyasına yazılır, sonra tek adımda asıl adına
        taşınır. Yazma sırasında süreç kesilirse geride yarım bir dosya kalmaz.
        """
        hedef = self.kok / goreli_yol
        if not self.uzerine_yaz and hedef.exists():
            gunluk.warning("dosya zaten var, üzerine yazılmadı: %s", goreli_yol)
            return str(hedef)
        hedef.parent.mkdir(parents=True, exist_ok=True)

        gecici = hedef.with_name(hedef.name + ".tmp")
        gecici.write_bytes(veri)
        os.replace(gecici, hedef)
        return str(hedef)

    def listele(self, onek: str) -> list[str]:
        """Önekle başlayan dosyaların göreli yollarını sıralı döndürür."""
        klasor = self.kok / onek
        if not klasor.exists():
            return []
        return sorted(
            p.relative_to(self.kok).as_posix()
            for p in klasor.rglob("*")
            if p.is_file() and not p.name.endswith(".tmp")
        )

    def oku_bayt(self, goreli_yol: str) -> bytes:
        return (self.kok / goreli_yol).read_bytes()


class BlobDepo:
    """Dosyaları Azure Blob Storage'a yazar ve okur (bulut ortamı).

    Blob yüklemesi kendiliğinden atomiktir: dosya ya tamamen yüklenir ya hiç
    görünmez. Bu yüzden .tmp hilesine gerek yok.

    uzerine_yaz=False ise var olan blob'a dokunulmaz (ham kap).
    """

    def __init__(self, hesap: str, kap: str, uzerine_yaz: bool = True) -> None:
        self.uzerine_yaz = uzerine_yaz
        # Azure kütüphaneleri sadece burada yükleniyor: yerel geliştirmede ve
        # testlerde Azure'a hiç ihtiyaç duymuyoruz.
        try:
            from azure.identity import DefaultAzureCredential
            from azure.storage.blob import BlobServiceClient
        except ImportError as hata:
            # Hata mesajı ne yapılacağını söylemeli, sadece neyin eksik olduğunu değil.
            raise RuntimeError(
                "Azure kütüphaneleri kurulu değil. Şunu çalıştır:\n"
                "    pip install -r gereksinimler.txt"
            ) from hata

        # DefaultAzureCredential parolasız kimlik doğrulama yapar. Sırayla
        # dener: bulutta yönetilen kimlik, yerelde `az login` oturumu.
        servis = BlobServiceClient(
            account_url=f"https://{hesap}.blob.core.windows.net",
            credential=DefaultAzureCredential(),
        )
        self.kap = servis.get_container_client(kap)

    def yaz(self, goreli_yol: str, icerik: Any, meta: dict[str, Any] | None = None) -> str:
        """İçeriği JSON'a çevirip sıkıştırarak yükler."""
        return self.yaz_bayt(goreli_yol, _sikistir(icerik), meta)

    def yaz_bayt(self, goreli_yol: str, veri: bytes, meta: dict[str, Any] | None = None) -> str:
        """Hazır baytları blob olarak yükler, blob adresini döndürür.

        meta: blob'un yanında saklanan kısa bilgiler (tur bilgisi, sürüm).
        Anahtarlar harf, rakam ve alt çizgiden oluşmalı.
        """
        from azure.core.exceptions import ResourceExistsError

        try:
            yuklenen = self.kap.upload_blob(
                goreli_yol, veri, overwrite=self.uzerine_yaz, metadata=meta_temizle(meta)
            )
        except ResourceExistsError:
            # aynı turu tekrar yazmaya çalışmak hata değil, var olan korunuyor
            gunluk.warning("blob zaten var, üzerine yazılmadı: %s", goreli_yol)
            return f"{self.kap.url}/{goreli_yol}"
        return yuklenen.url

    def listele(self, onek: str) -> list[str]:
        """Önekle başlayan blob adlarını sıralı döndürür.

        Önek, klasör gibi davranır: "2026/09/24/" sadece o günü listeler.
        Tüm kabı taramaktan çok daha hızlı ve ucuz.
        """
        return sorted(b.name for b in self.kap.list_blobs(name_starts_with=onek))

    def oku_bayt(self, goreli_yol: str) -> bytes:
        return self.kap.download_blob(goreli_yol).readall()


def depo_olustur(
    kap: str | None = None, uzerine_yaz: bool | None = None
) -> YerelDepo | BlobDepo:
    """DEPO_TURU ayarına göre doğru depoyu döndürür.

    kap: hangi bölme — "ham" (varsayılan) ya da "tablo". Yerelde veri/<kap>/
    klasörüne, bulutta aynı adlı blob kabına karşılık gelir.
    uzerine_yaz: verilmezse ham kapta kapalı, diğer kaplarda açık.
    """
    kap = kap or ayarlar.AZURE_KAP
    if uzerine_yaz is None:
        uzerine_yaz = kap != ayarlar.AZURE_KAP
    if ayarlar.DEPO_TURU == "blob":
        if not ayarlar.AZURE_DEPOLAMA_HESABI:
            raise ValueError("DEPO_TURU=blob için AZURE_DEPOLAMA_HESABI ayarlanmalı")
        return BlobDepo(ayarlar.AZURE_DEPOLAMA_HESABI, kap, uzerine_yaz)
    if ayarlar.DEPO_TURU == "yerel":
        return YerelDepo(ayarlar.VERI_KOK / kap, uzerine_yaz)
    raise ValueError(f"bilinmeyen DEPO_TURU: {ayarlar.DEPO_TURU!r} (yerel veya blob olmalı)")


def oku(yol: str | Path) -> Any:
    """Sıkıştırılmış bir ham dosyayı okur."""
    with gzip.open(yol, "rt", encoding="utf-8") as dosya:
        return json.load(dosya)
