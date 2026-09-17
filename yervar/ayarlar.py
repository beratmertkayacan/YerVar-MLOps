
""" 
Projenin Tüm ayarları. Diğer dosyalarda sabit değer yok, ayarlar ilk olarak ortam değişkenlerinden okunur, yoksa buradaki sabitten.
Aynı kod yerelde, testte, cloud'da farklı değerlerle çalışır; kodu değiştirmeden davranışı değiştirebiliriz.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# .env dosyası varsa ortam değişkenlerine yükler, yoksa sessiz geç
load_dotenv()

# ayarlar.py proje kökü
PROJE_KOKU: Path = Path(__file__).resolve().parent.parent


def _metin(anahtar: str, varsayilan: str) -> str:
    """Ortam değişkenini metin olarak okur"""
    return os.getenv(anahtar, varsayilan)


def _tam_sayi(anahtar: str, varsayilan: int) -> int:
    """Ortam değişkenini tam sayı okur, bozuksa varsayılan döndür"""
    ham = os.getenv(anahtar)
    if ham is None:
        return varsayilan
    try:
        return int(ham)
    except ValueError:
        return varsayilan


def _ondalik(anahtar: str, varsayilan: float) -> float:
    """Ortam değişkenini ondalık sayı olarak okur, bozuksa varsayılan"""
    ham = os.getenv(anahtar)
    if ham is None:
        return varsayilan
    try:
        return float(ham)
    except ValueError:
        return varsayilan


def _kimlik_listesi(anahtar: str) -> tuple[str, ...]:
    """Virgüllü otopark kimliklerini okur, boş ise boş döndür"""
    ham = os.getenv(anahtar, "").strip()
    if not ham:
        return ()
    return tuple(parca.strip() for parca in ham.split(",") if parca.strip())


@dataclass(frozen=True)
class Ayarlar:
    """Çalışma zamanı ayarları. frozen = True: çalışırken değiştirilemez"""

    ispark_taban_url: str
    kullanici_ajani: str

    toplama_araligi_sn: int
    istek_zaman_asimi_sn: float
    deneme_sayisi: int
    ilk_bekleme_sn: float

    # "liste" -> tek istekle tüm otoparkları çek(ucuz, tercih edilen)
    # "detay" -> her otopark için ayrı istek(pahalı, listede doluluk yoksa)
    toplama_modu: str
    detay_park_kimlikleri: tuple[str, ...]
    detay_istek_arasi_sn: float

    veri_kok: Path
    log_seviyesi: str

    @property
    def ham_kok(self) -> Path:
        """Dokunulmamış API yanıtlarının yazıldığı kök dizini"""
        return self.veri_kok / "ham"


def _ayarlari_olustur() -> Ayarlar:
    """Ortam değişkenlerinden tek bir Ayarlar nesnesi üretir"""
    veri_kok_ham = _metin("VERI_KOK", "veri")
    veri_kok = Path(veri_kok_ham)
    if not veri_kok.is_absolute():
        veri_kok = PROJE_KOKU / veri_kok

    return Ayarlar(
        ispark_taban_url=_metin("ISPARK_TABAN_URL", "https://api.ibb.gov.tr/ispark"),
        kullanici_ajani=_metin("KULLANICI_AJANI", "yervar/0.1 (ogrenme projesi)"),
        toplama_araligi_sn=_tam_sayi("TOPLAMA_ARALIGI_SN", 300),
        istek_zaman_asimi_sn=_ondalik("ISTEK_ZAMAN_ASIMI_SN", 20.0),
        deneme_sayisi=_tam_sayi("DENEME_SAYISI", 3),
        ilk_bekleme_sn=_ondalik("ILK_BEKLEME_SN", 2.0),
        toplama_modu=_metin("TOPLAMA_MODU", "liste").lower(),
        detay_park_kimlikleri=_kimlik_listesi("DETAY_PARK_KIMLIKLERI"),
        detay_istek_arasi_sn=_ondalik("DETAY_ISTEK_ARASI_SN", 0.2),
        veri_kok=veri_kok,
        log_seviyesi=_metin("LOG_SEVIYESI", "INFO").upper(),
    )

# Tüm proje bu tek nesneyi içeri aktarır
AYARLAR: Ayarlar = _ayarlari_olustur()
