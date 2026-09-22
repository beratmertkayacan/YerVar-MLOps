"""İSPARK web servisine istek atan katman.

Tek işi: isteği yapmak ve geçici hatalarda tekrar denemek. Yanıtı yorumlamaz.

Hangi hatada tekrar deneriz?
- Ağ hatası, zaman aşımı, 5xx  → sunucunun geçici sorunu, bekle ve tekrar dene
- 4xx                          → isteğimiz yanlış, tekrar denemek anlamsız
Bekleme süresi her denemede ikiye katlanır (2 → 4 → 8 sn): üstel geri çekilme.
"""

import time
from typing import Any

import httpx

from yervar import ayarlar
from yervar.gunluk import gunluk_al

gunluk = gunluk_al(__name__)


def istemci_olustur() -> httpx.Client:
    """Tekrar kullanılabilir bir HTTP istemcisi oluşturur.

    Aynı istemciyi turlar boyunca kullanmak, bağlantının her seferinde
    yeniden kurulmasını önler.
    """
    return httpx.Client(
        timeout=ayarlar.ISTEK_ZAMAN_ASIMI_SN,
        headers={"User-Agent": ayarlar.KULLANICI_AJANI},
    )


def park_listesi_getir(istemci: httpx.Client) -> list[dict[str, Any]]:
    """Tüm otoparkların anlık durumunu döndürür.

    Liste ucu kapasite ve boş yer bilgisini içeriyor (kesif/ornek'e bakın),
    bu yüzden her tur için tek bir istek yeterli.
    """
    adres = f"{ayarlar.ISPARK_TABAN_URL}/Park"
    bekleme = 2.0
    hata = ""

    for deneme in range(1, ayarlar.DENEME_SAYISI + 1):
        try:
            yanit = istemci.get(adres)
            if yanit.status_code < 500:
                yanit.raise_for_status()  # 4xx ise burada hata fırlatır, tekrar denenmez
                return yanit.json()
            hata = f"HTTP {yanit.status_code}"
        except httpx.TransportError as e:  # bağlantı hatası, zaman aşımı
            hata = str(e)

        if deneme < ayarlar.DENEME_SAYISI:
            gunluk.warning("deneme %d başarısız (%s), %.0f sn sonra tekrar", deneme, hata, bekleme)
            time.sleep(bekleme)
            bekleme *= 2

    raise RuntimeError(f"{ayarlar.DENEME_SAYISI} deneme başarısız: {hata}")
