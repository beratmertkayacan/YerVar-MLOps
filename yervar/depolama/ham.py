"""Ham API yanıtlarını DEĞİŞTİRMEDEN saklar.

Kurallar:
1. Gelen yanıta dokunulmaz. Temizleme ve dönüştürme sonraki katmanın işi.
   Şemayı yanlış anladığımızı sonradan fark edersek, ham veri sayesinde
   geçmişi baştan işleyebiliriz.
2. Her tur ayrı bir dosyaya yazılır; dosya adı UTC zaman damgalıdır.
3. Dosyalar gzip ile sıkıştırılır. Ölçülen: tek bir liste yanıtı ~56 KB,
   sıkıştırınca ~8 KB. Günde 288 turla aylık ~480 MB yerine ~70 MB.

İki depo var ve ikisinin de aynı yaz() metodu var: YerelDepo diske,
BlobDepo Azure'a yazar. Toplayıcı hangisiyle konuştuğunu bilmez;
depo_olustur() ayara bakıp doğru olanı verir.
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
    """Ham yanıtları yerel diske yazar (geliştirme ortamı)."""

    def __init__(self, kok: Path) -> None:
        self.kok = kok

    def yaz(self, goreli_yol: str, icerik: Any) -> str:
        """İçeriği sıkıştırıp atomik olarak yazar.

        Atomik yazma: önce .tmp dosyasına yazılır, sonra tek adımda asıl adına
        taşınır. Yazma sırasında süreç kesilirse geride yarım bir dosya kalmaz.
        """
        hedef = self.kok / goreli_yol
        hedef.parent.mkdir(parents=True, exist_ok=True)

        gecici = hedef.with_name(hedef.name + ".tmp")
        gecici.write_bytes(_sikistir(icerik))
        os.replace(gecici, hedef)
        return str(hedef)


class BlobDepo:
    """Ham yanıtları Azure Blob Storage'a yazar (bulut ortamı).

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
        """İçeriği sıkıştırıp blob olarak yükler, blob adresini döndürür."""
        blob = self.kap.upload_blob(goreli_yol, _sikistir(icerik), overwrite=True)
        return blob.url


def depo_olustur() -> YerelDepo | BlobDepo:
    """DEPO_TURU ayarına göre doğru depoyu döndürür."""
    if ayarlar.DEPO_TURU == "blob":
        if not ayarlar.AZURE_DEPOLAMA_HESABI:
            raise ValueError("DEPO_TURU=blob için AZURE_DEPOLAMA_HESABI ayarlanmalı")
        return BlobDepo(ayarlar.AZURE_DEPOLAMA_HESABI, ayarlar.AZURE_KAP)
    if ayarlar.DEPO_TURU == "yerel":
        return YerelDepo(ayarlar.HAM_KOK)
    raise ValueError(f"bilinmeyen DEPO_TURU: {ayarlar.DEPO_TURU!r} (yerel veya blob olmalı)")


def oku(yol: str | Path) -> Any:
    """Sıkıştırılmış bir ham dosyayı okur."""
    with gzip.open(yol, "rt", encoding="utf-8") as dosya:
        return json.load(dosya)
