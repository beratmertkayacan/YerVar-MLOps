"""Tek merkezî günlük (logging) ayarı.

print yerine bunu kullanıyoruz: her satır zamanı, önem seviyesini ve hangi
modülden geldiğini yazar. Bulutta çalışan bir işi izlemenin tek yolu budur.
"""

import logging
import sys

from yervar import ayarlar

logging.basicConfig(
    level=ayarlar.LOG_SEVIYESI,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    stream=sys.stdout,
)

# httpx her isteği ayrı satırda basıyor; kendi kayıtlarımızı boğmasın.
logging.getLogger("httpx").setLevel(logging.WARNING)


def gunluk_al(ad: str) -> logging.Logger:
    """Modüle özel bir günlükçü döndürür. Kullanım: gunluk_al(__name__)"""
    return logging.getLogger(ad)
