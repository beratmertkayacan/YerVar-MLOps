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

# Depolama
# DEPO_TURU: "yerel" → diske yazar (geliştirme), "blob" → Azure Blob Storage'a yazar (bulut)
DEPO_TURU = os.getenv("DEPO_TURU", "yerel")

# Yerel depo — göreli yol verilirse proje köküne göre çözülür
VERI_KOK = PROJE_KOKU / os.getenv("VERI_KOK", "veri")
HAM_KOK = VERI_KOK / "ham"

# Azure Blob depo — parola yok; kimlik, bulutta yönetilen kimlikten (managed identity), yerelde `az login` oturumundan otomatik alınır.
AZURE_DEPOLAMA_HESABI = os.getenv("AZURE_DEPOLAMA_HESABI", "")
AZURE_KAP = os.getenv("AZURE_KAP", "ham")        # ham turlar (L0 yazar)
TABLO_KAP = os.getenv("TABLO_KAP", "tablo")      # günlük tablolar (L1 yazar)

# Özellikler (L2)
# Kaç dakika sonrasını tahmin ediyoruz. Sürücü otoparka ortalama bu kadar
# sürede varıyor varsayımı. 5'in katı olmalı, çünkü veri 5 dakikalık.
TAHMIN_UFKU_DK = int(os.getenv("TAHMIN_UFKU_DK", "30"))

# Günlük
LOG_SEVIYESI = os.getenv("LOG_SEVIYESI", "INFO").upper()
