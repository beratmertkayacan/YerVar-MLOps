"""
Ham API yanıtları doğrudan saklanır (2 kural)

1- Doğrudan yazılır: ad düzeltme, tip dönüşümü, filtreleme yok. Ayrıştırma L1'in temizleme adımı işi
Şemanın yanlış anlaşıldığı 3 ay sonra çıkarsa, ham veri duruyorsa geçmişi baştan işleriz.
Dokunulursa veri gelmez!

2- Her tür kendi dosyasına yazılsın, adı UTC zamanı damgalı şekilde

Depoalama arayüzü(Hamdepo) soyut bu adımda. Diskten sonra Azure Blob vs yazılacak, toplayıcı kodu değişmeden
sadece kendisine verilen depo nesnesi değiştirilecek
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol


class HamDepo(Protocol):
    """Ham yanıtları saklayan deponun kuralları"""

    def yaz(self, goreli_yol: str, icerik: Any) -> str:
        """İçeri verilen yola JSON olarak yaz, nihai konuma döndür"""
        ...


def simdi_utc() -> datetime:
    """Şuanki zamanı UTC döndür 
    Proje boyunca tek zaman kaynağı bu, yerel saat, yaz saati vs veri onarımı gerekebilir bozar.
    Diske yazılan her şey UTC 
    """
    return datetime.now(UTC)


def zaman_damgasi(zaman: datetime) -> str:
    """Dosya adında kullanılacak sıkıştırılmış UTC damgası: 20260917T143000Z"""
    return zaman.strftime("%Y%m%dT%H%M%SZ")


def ham_yol(zaman: datetime, etiket: str) -> str:
    """Bir türün yazılacağı göreli yolu üretir

    Örnek: 2026/09/17/14/parklar_20260917T143000Z.json

    Klasörlerin yıl/ay/gün/saat olarak bölünmesi bilerek: dosya sistemi ve bölümlü okuma mimarisi
    yavaşlayabilir diğer türlü.
    Saat bazlı bölümleme işi ucuzlatır ve planlı yapar
    """
    return (
        f"{zaman:%Y}/{zaman:%m}/{zaman:%d}/{zaman:%H}/"
        f"{etiket}_{zaman_damgasi(zaman)}.json"
    )


class YerelDepo:
    """Ham yanıtları yerel diske yazar (aşama1)"""

    def __init__(self, kok: Path) -> None:
        self.kok = kok

    def yaz(self, goreli_yol: str, icerik: Any) -> str:
        """İçeriği diske yaz, tüm yolu döndür
        Önce geçici dosyaya yaz, nihai ada taşı.
        Yazma sürcinde kill olursa .json değil .tmp kalır okuyunca bozuk dosya görülmez
        """
        hedef = self.kok / goreli_yol
        hedef.parent.mkdir(parents=True, exist_ok=True)

        gecici = hedef.with_suffix(hedef.suffix + ".tmp")
        metin = json.dumps(icerik, ensure_ascii=False, separators=(",", ":"))
        gecici.write_text(metin, encoding="utf-8")
        os.replace(gecici, hedef)

        return str(hedef)


class BellekDepo:
    """Testler için diske yazmayan örnek depo"""

    def __init__(self) -> None:
        self.kayitlar: dict[str, Any] = {}

    def yaz(self, goreli_yol: str, icerik: Any) -> str:
        self.kayitlar[goreli_yol] = icerik
        return goreli_yol
