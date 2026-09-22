"""Otopark listesini düzenli aralıklarla çekip ham olarak kaydeder.

Çalıştırma:
    python -m yervar.toplama.toplayici --tek-tur   # bir tur çalışır ve çıkar
    python -m yervar.toplama.toplayici             # sürekli çalışır (yerel kullanım)

Bulutta tek-tur modu kullanılacak: Azure her 5 dakikada bir bu komutu
başlatacak, iş bitince konteyner kapanacak. Sürekli mod sadece yerel test için.
"""

import argparse
import signal
import time

import httpx

from yervar import ayarlar
from yervar.depolama.ham import YerelDepo, ham_yol, simdi_utc
from yervar.gunluk import gunluk_al
from yervar.toplama.istemci import istemci_olustur, park_listesi_getir

gunluk = gunluk_al(__name__)
_calisiyor = True


def _durdur(sinyal: int, _cerceve: object) -> None:
    """Ctrl+C veya SIGTERM gelince döngüyü, içindeki turu bitirdikten sonra durdurur."""
    global _calisiyor
    _calisiyor = False
    gunluk.info("durdurma sinyali alındı (%d), tur bitince çıkılacak", sinyal)


def tek_tur(istemci: httpx.Client, depo: YerelDepo) -> None:
    """Listeyi bir kez çeker ve kaydeder."""
    zaman = simdi_utc()
    parklar = park_listesi_getir(istemci)
    yol = depo.yaz(ham_yol(zaman, "parklar"), parklar)
    gunluk.info("%d otopark kaydedildi → %s", len(parklar), yol.name)


def surekli_calis(istemci: httpx.Client, depo: YerelDepo) -> None:
    """Turları durdurulana kadar sabit aralıkla tekrarlar.

    Toplayıcı hata yüzünden asla durmaz: kaynakta geçmiş arşiv olmadığı için
    kaçırılan her tur geri gelmez. Hata kaydedilir, bir sonraki tur denenir.
    """
    signal.signal(signal.SIGINT, _durdur)
    signal.signal(signal.SIGTERM, _durdur)

    sonraki = time.monotonic()
    while _calisiyor:
        try:
            tek_tur(istemci, depo)
        except Exception:
            gunluk.exception("tur başarısız, bir sonraki turda tekrar denenecek")

        # Kaymasız zamanlama: sonraki turun zamanı, bu turun ne kadar
        # sürdüğünden bağımsız hesaplanır. sleep(300) kullansaydık her tur
        # birkaç saniye kayar, gün sonunda 07:00, 07:05... düzeni bozulurdu.
        sonraki = max(sonraki + ayarlar.TOPLAMA_ARALIGI_SN, time.monotonic())
        while _calisiyor and time.monotonic() < sonraki:
            time.sleep(1)


def main() -> None:
    ayristirici = argparse.ArgumentParser(description="İSPARK ham veri toplayıcısı")
    ayristirici.add_argument("--tek-tur", action="store_true", help="bir tur çalış ve çık")
    tek = ayristirici.parse_args().tek_tur

    depo = YerelDepo(ayarlar.HAM_KOK)
    with istemci_olustur() as istemci:
        if tek:
            tek_tur(istemci, depo)
        else:
            aralik, hedef = ayarlar.TOPLAMA_ARALIGI_SN, ayarlar.HAM_KOK
            gunluk.info("toplayıcı başladı: her %d sn → %s", aralik, hedef)
            surekli_calis(istemci, depo)


if __name__ == "__main__":
    main()
