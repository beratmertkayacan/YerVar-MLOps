"""
Tek merkezi günlük (logging) yapılandırması.
Neden print değil: print nereye, ne zaman, ne kadar önemli olduğunu söylemez.
Cloud'da çalışan iş için günlük satır tek farkındalık: zaman, seviye, modül adı olmadan sorunu geriye dönük çözemeyiz
"""


from __future__ import annotations

import logging
import sys

from yervar.ayarlar import AYARLAR

_BICIM = "%(asctime)s | %(levelname)-7s | %(name)-28s | %(message)s"
_ZAMAN_BICIMI = "%Y-%m-%dT%H:%M:%S%z"

_yapilandirildi = False


def _yapilandir() -> None:
    """Kök günlükçü bir kez yapılandır"""
    global _yapilandirildi
    if _yapilandirildi:
        return

    isleyici = logging.StreamHandler(stream=sys.stdout)
    isleyici.setFormatter(logging.Formatter(_BICIM, datefmt=_ZAMAN_BICIMI))

    kok = logging.getLogger()
    kok.setLevel(AYARLAR.log_seviyesi)
    kok.handlers.clear()
    kok.addHandler(isleyici)

    #httpx her isteği info seviyesinde basar, 5 dakika gibi rutin işte gürültü sorunu, kendi satırlarımız görünür kılınsın diye susturuldu
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    _yapilandirildi = True


def gunluk_al(ad: str) -> logging.Logger:
    """Verilen ad için yapılandırılmış bir günlükçü döndürür"""
    _yapilandir()
    return logging.getLogger(ad)
