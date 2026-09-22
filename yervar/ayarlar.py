"""Projenin tüm ayarları tek bir yerde.

Her değer önce ortam değişkeninden (.env) okunur; yoksa buradaki varsayılan
kullanılır. Böylece aynı kod yerelde ve bulutta farklı ayarlarla çalışır.
Hatalı bir değer (ör. sayı yerine yazı) program başlarken hemen hata verir —
bu bilinçli: yanlış ayarla sessizce çalışmaktansa hiç başlamamak daha iyi.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJE_KOKU = Path(__file__).resolve().parent.parent

# İSPARK web servisi
ISPARK_TABAN_URL = os.getenv("ISPARK_TABAN_URL", "https://api.ibb.gov.tr/ispark")
KULLANICI_AJANI = os.getenv("KULLANICI_AJANI", "yervar/0.1")

# Toplama
TOPLAMA_ARALIGI_SN = int(os.getenv("TOPLAMA_ARALIGI_SN", "300"))
ISTEK_ZAMAN_ASIMI_SN = float(os.getenv("ISTEK_ZAMAN_ASIMI_SN", "20"))
DENEME_SAYISI = int(os.getenv("DENEME_SAYISI", "3"))

# Depolama — göreli yol verilirse proje köküne göre çözülür
VERI_KOK = PROJE_KOKU / os.getenv("VERI_KOK", "veri")
HAM_KOK = VERI_KOK / "ham"

# Günlük
LOG_SEVIYESI = os.getenv("LOG_SEVIYESI", "INFO").upper()
