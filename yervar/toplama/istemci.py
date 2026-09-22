"""ISPARK web servisi istemcisi.

Tek sorumlulugu: istegi yapmak, gecici hatalarda yeniden denemek, ham yaniti
oldugu gibi dondurmek. Yaniti yorumlamaz, alan adi bilmez - bilerek. Sema
dogrulandiginda bile bu dosya degismeyecek; yorumlama isi L1'e ait.
"""

from __future__ import annotations

import time
from types import TracebackType
from typing import Any

import httpx

from yervar.ayarlar import AYARLAR
from yervar.gunluk import gunluk_al

_gunluk = gunluk_al(__name__)


class IsparkHatasi(RuntimeError):
    """Tum denemeler tukendikten sonra firlatilir."""


class IsparkIstemcisi:
    """ISPARK uc noktalarina istek atan istemci.

    Baglam yoneticisi olarak kullanilir; boylece TCP baglantilari tekrar kullanilir
    ve her istekte yeniden el sikismaya gerek kalmaz:

        with IsparkIstemcisi() as istemci:
            liste = istemci.park_listesi()
    """

    def __init__(
        self,
        taban_url: str | None = None,
        zaman_asimi_sn: float | None = None,
        deneme_sayisi: int | None = None,
        ilk_bekleme_sn: float | None = None,
    ) -> None:
        self.taban_url = (taban_url or AYARLAR.ispark_taban_url).rstrip("/")
        self.zaman_asimi_sn = zaman_asimi_sn or AYARLAR.istek_zaman_asimi_sn
        self.deneme_sayisi = deneme_sayisi or AYARLAR.deneme_sayisi
        self.ilk_bekleme_sn = ilk_bekleme_sn or AYARLAR.ilk_bekleme_sn

        self._istemci = httpx.Client(
            timeout=self.zaman_asimi_sn,
            headers={
                "User-Agent": AYARLAR.kullanici_ajani,
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

    def __enter__(self) -> IsparkIstemcisi:
        return self

    def __exit__(
        self,
        tur: type[BaseException] | None,
        deger: BaseException | None,
        iz: TracebackType | None,
    ) -> None:
        self.kapat()

    def kapat(self) -> None:
        """Alttaki HTTP istemcisini kapatir."""
        self._istemci.close()

    # --- ic yardimci -----------------------------------------------------

    def _getir(self, yol: str, parametreler: dict[str, Any] | None = None) -> Any:
        """Tek bir GET istegi yapar, gecici hatalarda ustel bekleyerek tekrar dener.

        Hangi hatada tekrar denenir, hangisinde denenmez - bu ayrim onemli:

        * Ag hatasi, zaman asimi, 5xx  -> sunucunun gecici sorunu, TEKRAR DENE.
        * 4xx (400, 404, 429 haric)    -> istegimiz yanlis, tekrar denemek ayni
          yanlisi tekrarlamaktir. Hemen birak.
        * 429 (cok fazla istek)        -> sunucu "yavasla" diyor, bekleyip dene.

        Bekleme suresi her denemede ikiye katlanir (2s, 4s, 8s). Buna ustel geri
        cekilme denir; sunucu zorlaniyorsa uzerine gitmek yerine geri cekiliriz.
        """
        adres = f"{self.taban_url}/{yol.lstrip('/')}"
        bekleme = self.ilk_bekleme_sn
        son_hata: Exception | None = None

        for deneme in range(1, self.deneme_sayisi + 1):
            try:
                yanit = self._istemci.get(adres, params=parametreler)

                if yanit.status_code >= 500 or yanit.status_code == 429:
                    raise httpx.HTTPStatusError(
                        f"sunucu {yanit.status_code} dondurdu",
                        request=yanit.request,
                        response=yanit,
                    )

                yanit.raise_for_status()
                return yanit.json()

            except httpx.HTTPStatusError as hata:
                kod = hata.response.status_code
                if kod < 500 and kod != 429:
                    # Bizim hatamiz; tekrar denemek anlamsiz.
                    raise IsparkHatasi(f"{adres} -> HTTP {kod}") from hata
                son_hata = hata

            except (httpx.RequestError, ValueError) as hata:
                # RequestError: ag/zaman asimi. ValueError: JSON cozulemedi.
                son_hata = hata

            if deneme < self.deneme_sayisi:
                _gunluk.warning(
                    "istek basarisiz (%d/%d): %s -> %s | %.1f sn sonra tekrar",
                    deneme,
                    self.deneme_sayisi,
                    adres,
                    son_hata,
                    bekleme,
                )
                time.sleep(bekleme)
                bekleme *= 2

        raise IsparkHatasi(
            f"{adres} icin {self.deneme_sayisi} deneme tukendi: {son_hata}"
        )

    # --- uc noktalar -----------------------------------------------------

    def park_listesi(self) -> Any:
        """Tum otoparklarin listesini ham olarak dondurur."""
        return self._getir("Park")

    def park_detay(self, park_kimligi: str) -> Any:
        """Tek bir otoparkin anlik detayini ham olarak dondurur."""
        return self._getir("ParkDetay", {"id": park_kimligi})
