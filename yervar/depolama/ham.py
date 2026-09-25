"""Ham API yanıtlarını DEĞİŞTİRMEDEN saklar.

Kurallar:
1. Gelen yanıta dokunulmaz. Temizleme ve dönüştürme sonraki katmanın işi.
   Şemayı yanlış anladığımızı sonradan fark edersek, ham veri sayesinde
   geçmişi baştan işleyebiliriz.
2. Her tur ayrı bir dosyaya yazılır; dosya adı UTC zaman damgalıdır.
3. Dosyalar gzip ile sıkıştırılır. Ölçülen: tek bir liste yanıtı ~56 KB,
   sıkıştırınca ~8 KB. Günde 288 turla aylık ~480 MB yerine ~70 MB.

İki depo var ve ikisi de aynı dört metoda sahip (yaz, yaz_bayt, listele,
oku_bayt): YerelDepo diske, BlobDepo Azure'a yazar. Kodun geri kalanı hangisiyle
konuştuğunu bilmez; depo_olustur() ayara bakıp doğru olanı verir. L1 (tablo.py)
aynı sınıfları hem ham veriyi okumak hem tabloyu yazmak için kullanıyor.
"""

import gzip
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from yervar import ayarlar


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


def _sikistir(icerik: Any) -> bytes:
    """İçeriği Türkçe karakterleri koruyarak JSON'a çevirip gzip ile sıkıştırır."""
    return gzip.compress(json.dumps(icerik, ensure_ascii=False).encode("utf-8"))


class YerelDepo:
    """Dosyaları yerel diske yazar ve okur (geliştirme ortamı)."""

    def __init__(self, kok: Path) -> None:
        self.kok = kok

    def yaz(self, goreli_yol: str, icerik: Any) -> str:
        """İçeriği JSON'a çevirip sıkıştırarak yazar."""
        return self.yaz_bayt(goreli_yol, _sikistir(icerik))

    def yaz_bayt(self, goreli_yol: str, veri: bytes) -> str:
        """Hazır baytları atomik olarak yazar.

        Atomik yazma: önce .tmp dosyasına yazılır, sonra tek adımda asıl adına
        taşınır. Yazma sırasında süreç kesilirse geride yarım bir dosya kalmaz.
        """
        hedef = self.kok / goreli_yol
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
    """

    def __init__(self, hesap: str, kap: str) -> None:
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

    def yaz(self, goreli_yol: str, icerik: Any) -> str:
        """İçeriği JSON'a çevirip sıkıştırarak yükler."""
        return self.yaz_bayt(goreli_yol, _sikistir(icerik))

    def yaz_bayt(self, goreli_yol: str, veri: bytes) -> str:
        """Hazır baytları blob olarak yükler, blob adresini döndürür."""
        return self.kap.upload_blob(goreli_yol, veri, overwrite=True).url

    def listele(self, onek: str) -> list[str]:
        """Önekle başlayan blob adlarını sıralı döndürür.

        Önek, klasör gibi davranır: "2026/09/24/" sadece o günü listeler.
        Tüm kabı taramaktan çok daha hızlı ve ucuz.
        """
        return sorted(b.name for b in self.kap.list_blobs(name_starts_with=onek))

    def oku_bayt(self, goreli_yol: str) -> bytes:
        return self.kap.download_blob(goreli_yol).readall()


def depo_olustur(kap: str | None = None) -> YerelDepo | BlobDepo:
    """DEPO_TURU ayarına göre doğru depoyu döndürür.

    kap: hangi bölme — "ham" (varsayılan) ya da "tablo". Yerelde veri/<kap>/
    klasörüne, bulutta aynı adlı blob kabına karşılık gelir.
    """
    kap = kap or ayarlar.AZURE_KAP
    if ayarlar.DEPO_TURU == "blob":
        if not ayarlar.AZURE_DEPOLAMA_HESABI:
            raise ValueError("DEPO_TURU=blob için AZURE_DEPOLAMA_HESABI ayarlanmalı")
        return BlobDepo(ayarlar.AZURE_DEPOLAMA_HESABI, kap)
    if ayarlar.DEPO_TURU == "yerel":
        return YerelDepo(ayarlar.VERI_KOK / kap)
    raise ValueError(f"bilinmeyen DEPO_TURU: {ayarlar.DEPO_TURU!r} (yerel veya blob olmalı)")


def oku(yol: str | Path) -> Any:
    """Sıkıştırılmış bir ham dosyayı okur."""
    with gzip.open(yol, "rt", encoding="utf-8") as dosya:
        return json.load(dosya)
