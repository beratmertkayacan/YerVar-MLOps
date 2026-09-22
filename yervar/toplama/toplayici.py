"""Belirli araliklarla ISPARK verisini ceken ve ham olarak saklayan is.

Calistirma:
    python -m yervar.toplama.toplayici           # sonsuz dongu
    python -m yervar.toplama.toplayici --tek-tur # tek tur, cikar

Iki calisma modu vardir:

* liste  - tek istekle tum otoparklari ceker. Ucuz ve tercih edilen yol.
* detay  - her otopark icin ayri istek atar. Sadece liste ucunda doluluk alani
           YOKSA gerekir; o zaman da sinirli sayida otoparkla calisilir.

Hangi modun gerektigini kesif/01_uc_nokta_dogrula.py cikitisi soyler.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from types import FrameType
from typing import Any

from yervar.ayarlar import AYARLAR
from yervar.depolama.ham import HamDepo, YerelDepo, ham_yol, simdi_utc
from yervar.gunluk import gunluk_al
from yervar.toplama.istemci import IsparkHatasi, IsparkIstemcisi

_gunluk = gunluk_al(__name__)

# SIGTERM/SIGINT geldiginde donguyu temiz kapatmak icin bayrak.
_durdur = False


def _durdurma_isareti(imza: int, cerceve: FrameType | None) -> None:
    """Kapatma sinyalini yakalar; tur ortasinda kesmek yerine turu bitirtir.

    Bulutta konteyner yeniden baslatilirken once SIGTERM gelir. Bunu yakalamazsak
    surec yazma isleminin ortasinda olur. Yakalarsak, icinde bulundugu turu
    tamamlar ve oyle cikar.
    """
    global _durdur
    _durdur = True
    _gunluk.info("kapatma sinyali alindi (%s); bu tur bitince cikilacak", imza)


def tek_tur(istemci: IsparkIstemcisi, depo: HamDepo) -> list[str]:
    """Bir toplama turu yapar ve yazilan dosyalarin yollarini dondurur."""
    zaman = simdi_utc()
    yazilanlar: list[str] = []

    if AYARLAR.toplama_modu == "liste":
        icerik: Any = istemci.park_listesi()
        yol = depo.yaz(ham_yol(zaman, "parklar"), icerik)
        yazilanlar.append(yol)
        adet = len(icerik) if isinstance(icerik, list) else 1
        _gunluk.info("liste alindi: %d kayit -> %s", adet, yol)

    elif AYARLAR.toplama_modu == "detay":
        kimlikler = AYARLAR.detay_park_kimlikleri
        if not kimlikler:
            raise RuntimeError(
                "TOPLAMA_MODU=detay secildi ama DETAY_PARK_KIMLIKLERI bos. "
                "Once kesif scriptiyle canli otoparklari belirle."
            )

        detaylar: dict[str, Any] = {}
        basarisiz = 0
        for kimlik in kimlikler:
            try:
                detaylar[kimlik] = istemci.park_detay(kimlik)
            except IsparkHatasi as hata:
                # Tek otoparkin hatasi turu bitirmez; eksigi kaydedip devam et.
                basarisiz += 1
                _gunluk.warning("detay alinamadi: id=%s (%s)", kimlik, hata)
            time.sleep(AYARLAR.detay_istek_arasi_sn)

        yol = depo.yaz(ham_yol(zaman, "detaylar"), detaylar)
        yazilanlar.append(yol)
        _gunluk.info(
            "detay alindi: %d basarili, %d basarisiz -> %s",
            len(detaylar),
            basarisiz,
            yol,
        )

    else:
        raise RuntimeError(
            f"bilinmeyen TOPLAMA_MODU: {AYARLAR.toplama_modu!r} "
            "(beklenen: 'liste' veya 'detay')"
        )

    return yazilanlar


def sonsuz_dongu(depo: HamDepo | None = None) -> None:
    """Toplayiciyi surekli calistirir.

    Zamanlama kaymayi onleyecek sekilde kurulmustur. Naif yaklasim her turun
    sonunda sleep(300) demektir; ama tur 12 saniye surerse gercek aralik 312
    saniye olur ve gun sonunda zaman damgalari 07:00, 07:05, 07:10 degil
    kaymis degerler olur. Bunun yerine turlarin olmasi gereken anlarini
    baslangictan itibaren hesaplayip aradaki farki uyuyoruz.
    """
    depo = depo or YerelDepo(AYARLAR.ham_kok)
    aralik = AYARLAR.toplama_araligi_sn

    signal.signal(signal.SIGINT, _durdurma_isareti)
    signal.signal(signal.SIGTERM, _durdurma_isareti)

    _gunluk.info(
        "toplayici basladi | mod=%s | aralik=%ds | hedef=%s",
        AYARLAR.toplama_modu,
        aralik,
        AYARLAR.ham_kok,
    )

    baslangic = time.monotonic()
    tur_no = 0

    with IsparkIstemcisi() as istemci:
        while not _durdur:
            basladi = time.monotonic()
            try:
                tek_tur(istemci, depo)
            except Exception as hata:  # noqa: BLE001
                # Toplayici ASLA olmez. Bir tur kaybetmek, tum akisi kaybetmekten
                # iyidir; arsiv olmadigi icin duran her dakika geri gelmiyor.
                _gunluk.error("tur basarisiz: %s", hata, exc_info=True)

            tur_no += 1
            hedef = baslangic + tur_no * aralik
            uyku = hedef - time.monotonic()

            if uyku < 0:
                # Tur araliktan uzun surdu: bir sonraki hedefe atla, birikme olmasin.
                atlanan = int(-uyku // aralik) + 1
                _gunluk.warning(
                    "tur %.1f sn surdu, aralik %d sn - %d tur atlaniyor",
                    time.monotonic() - basladi,
                    aralik,
                    atlanan,
                )
                tur_no += atlanan
                uyku = baslangic + tur_no * aralik - time.monotonic()

            # Uykuyu parcalara bolerek kapatma sinyaline hizli cevap veriyoruz.
            son = time.monotonic() + max(uyku, 0)
            while not _durdur and time.monotonic() < son:
                time.sleep(min(1.0, son - time.monotonic()))

    _gunluk.info("toplayici durdu | toplam tur: %d", tur_no)


def main() -> int:
    """Komut satiri girisi."""
    ayristirici = argparse.ArgumentParser(description="ISPARK ham veri toplayicisi")
    ayristirici.add_argument(
        "--tek-tur",
        action="store_true",
        help="tek bir tur calistir ve cik (test ve hata ayiklama icin)",
    )
    argumanlar = ayristirici.parse_args()

    if argumanlar.tek_tur:
        depo = YerelDepo(AYARLAR.ham_kok)
        with IsparkIstemcisi() as istemci:
            yazilanlar = tek_tur(istemci, depo)
        for yol in yazilanlar:
            print(yol)
        return 0

    sonsuz_dongu()
    return 0


if __name__ == "__main__":
    sys.exit(main())
