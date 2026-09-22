"""Ham API yanıtlarını DEĞİŞTİRMEDEN saklar.

Kurallar:
1. Gelen yanıta dokunulmaz. Temizleme ve dönüştürme sonraki katmanın işi.
   Şemayı yanlış anladığımızı sonradan fark edersek, ham veri sayesinde
   geçmişi baştan işleyebiliriz.
2. Her tur ayrı bir dosyaya yazılır; dosya adı UTC zaman damgalıdır.
3. Dosyalar gzip ile sıkıştırılır. Ölçülen: tek bir liste yanıtı ~56 KB,
   sıkıştırınca ~8 KB. Günde 288 turla aylık ~480 MB yerine ~70 MB.

Hafta 2'de aynı yaz() metoduna sahip bir BlobDepo yazacağız; toplayıcının
kodu değişmeyecek, sadece ona verilen depo nesnesi değişecek.
"""

import gzip
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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


class YerelDepo:
    """Ham yanıtları yerel diske yazar."""

    def __init__(self, kok: Path) -> None:
        self.kok = kok

    def yaz(self, goreli_yol: str, icerik: Any) -> Path:
        """İçeriği sıkıştırıp atomik olarak yazar.

        Atomik yazma: önce .tmp dosyasına yazılır, sonra tek adımda asıl adına
        taşınır. Yazma sırasında süreç kesilirse geride yarım bir dosya kalmaz.
        """
        hedef = self.kok / goreli_yol
        hedef.parent.mkdir(parents=True, exist_ok=True)

        gecici = hedef.with_name(hedef.name + ".tmp")
        with gzip.open(gecici, "wt", encoding="utf-8") as dosya:
            json.dump(icerik, dosya, ensure_ascii=False)
        os.replace(gecici, hedef)

        return hedef


def oku(yol: Path) -> Any:
    """Sıkıştırılmış bir ham dosyayı okur."""
    with gzip.open(yol, "rt", encoding="utf-8") as dosya:
        return json.load(dosya)
