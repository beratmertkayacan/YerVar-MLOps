"""İSPARK web servisine istek atan katman.

Tek işi: isteği yapmak ve geçici hatalarda tekrar denemek. Yanıtı yorumlamaz.

Hangi hatada tekrar deneriz?
- Ağ hatası, zaman aşımı, 5xx  → sunucunun geçici sorunu, bekle ve tekrar dene
- 4xx                          → isteğimiz yanlış, tekrar denemek anlamsız
Bekleme süresi her denemede ikiye katlanır (2 → 4 → 8 → 16 sn): üstel geri çekilme.

Denemeler bir süre bütçesiyle sınırlı. Bütçe biterse ya da denemeler tükenirse
KaynakHatasi fırlatılıyor. Bu, "İSPARK cevap vermedi" demek; bizim kodda bir
hata olmadığını log'da ayırt edebilmek için ayrı bir hata tipi.
"""

import time
from typing import Any

import httpx

from yervar import ayarlar
from yervar.gunluk import gunluk_al

gunluk = gunluk_al(__name__)


class KaynakHatasi(RuntimeError):
    """İSPARK'a ulaşılamadı (5xx ya da bağlantı hatası). Bu tur kayıp."""


def istemci_olustur() -> httpx.Client:
    """Tekrar kullanılabilir bir HTTP istemcisi oluşturur.

    Aynı istemciyi turlar boyunca kullanmak, bağlantının her seferinde
    yeniden kurulmasını önler.
    """
    return httpx.Client(
        timeout=ayarlar.ISTEK_ZAMAN_ASIMI_SN,
        headers={"User-Agent": ayarlar.KULLANICI_AJANI},
    )


def park_listesi_getir(
    istemci: httpx.Client, butce_sn: float | None = None
) -> list[dict[str, Any]]:
    """Tüm otoparkların anlık durumunu döndürür.

    Liste ucu kapasite ve boş yer bilgisini içeriyor (kesif/ornek'e bakın),
    bu yüzden her tur için tek bir istek yeterli.

    butce_sn: denemelere ayrılan toplam süre. Verilmezse TUR_SURE_BUTCESI_SN.
    """
    adres = f"{ayarlar.ISPARK_TABAN_URL}/Park"
    butce = ayarlar.TUR_SURE_BUTCESI_SN if butce_sn is None else butce_sn
    bitis = time.monotonic() + butce
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

        son_deneme = deneme == ayarlar.DENEME_SAYISI
        butce_bitiyor = time.monotonic() + bekleme >= bitis
        if son_deneme or butce_bitiyor:
            break
        gunluk.warning("deneme %d başarısız (%s), %.0f sn sonra tekrar", deneme, hata, bekleme)
        time.sleep(bekleme)
        bekleme *= 2

    raise KaynakHatasi(f"{deneme} deneme başarısız: {hata}")
