"""Otopark listesini düzenli aralıklarla çekip ham olarak kaydeder.

Çalıştırma:
    python -m yervar.toplama.toplayici --tek-tur   # bir tur çalışır ve çıkar
    python -m yervar.toplama.toplayici             # sürekli çalışır (yerel kullanım)

Bulutta tek-tur modu kullanılıyor: Azure her 5 dakikada bir bu komutu
başlatıyor, iş bitince konteyner kapanıyor. Sürekli mod sadece yerel test için.

Log satırları alarm ve sorgular için sabit kelimelerle başlıyor:
    TUR_TAMAM        tur yazıldı. "<sayı> otopark kaydedildi" ifadesi sessizlik
                     alarmının aradığı kalıp, değiştirilmemeli.
    KAYNAK_KESINTISI İSPARK'a ulaşılamadı
    KAYNAK_GECERSIZ  İSPARK cevap verdi ama yanıt kullanılamaz
    HATALI_YAZILAMADI geçersiz gövde hatali/ altına yazılamadı
"""

import argparse
import gzip
import signal
import time
from datetime import datetime

import httpx

from yervar import ayarlar
from yervar.depolama.ham import (
    BlobDepo,
    YerelDepo,
    depo_olustur,
    ham_yol,
    hatali_yol,
    simdi_utc,
)
from yervar.gunluk import gunluk_al
from yervar.toplama.istemci import (
    GecersizGovde,
    GecersizYanit,
    KaynakSorunu,
    Tur,
    istemci_olustur,
    park_listesi_getir,
)

gunluk = gunluk_al("yervar.toplama.toplayici")
_calisiyor = True


def _durdur(sinyal: int, _cerceve: object) -> None:
    """Ctrl+C veya SIGTERM gelince döngüyü, içindeki turu bitirdikten sonra durdurur."""
    global _calisiyor
    _calisiyor = False
    gunluk.info("durdurma sinyali alındı (%d), tur bitince çıkılacak", sinyal)


def tur_bilgisi(tur: Tur) -> dict[str, str]:
    """Log satırına ve blob meta verisine giden bilgiler. Anahtarlar Azure meta
    verisine uygun (harf, rakam, alt çizgi), değerler ASCII."""
    return {
        "kayit": str(tur.kayit),
        "deneme": str(tur.deneme),
        "sure_ms": str(tur.sure_ms),
        "yanit_utc": f"{tur.yanit_utc:%Y-%m-%dT%H:%M:%SZ}",
        "surum": ayarlar.KOD_SURUMU,
    }


def hatali_kaydet(depo: YerelDepo | BlobDepo, zaman: datetime, gecersiz: GecersizGovde) -> None:
    """Geçersiz gövdeyi inceleme için hatali/ altına saklar.

    Yazamazsa sadece loglar: asıl sorun (geçersiz yanıt) bunun yüzünden
    kaybolmamalı, iş yine KAYNAK_GECERSIZ ile bitmeli.
    """
    sinir = ayarlar.HATALI_GOVDE_EN_FAZLA_BAYT
    meta = {
        "sebep": gecersiz.sebep,
        "durum_kodu": str(gecersiz.durum_kodu),
        "icerik_turu": gecersiz.icerik_turu,
        "konum": gecersiz.konum,
        "boyut": str(len(gecersiz.govde)),
        "kesildi": "1" if len(gecersiz.govde) > sinir else "0",
        "surum": ayarlar.KOD_SURUMU,
    }
    yol = hatali_yol(zaman, "parklar")
    try:
        depo.yaz_bayt(yol, gzip.compress(gecersiz.govde[:sinir]), meta)
    except Exception:
        gunluk.exception("HATALI_YAZILAMADI: geçersiz gövde saklanamadı (%s)", yol)
        return
    gunluk.info("geçersiz gövde saklandı: %s (%d bayt)", yol, len(gecersiz.govde))


def tek_tur(istemci: httpx.Client, depo: YerelDepo | BlobDepo) -> None:
    """Listeyi bir kez çeker ve kaydeder.

    Kullanılabilir bir tur alınamazsa KaynakSorunu fırlatır. Yolda geçersiz bir
    gövde geldiyse fırlatmadan önce onu hatali/ altına yazar.
    """
    # Dosya adındaki zaman isteğin başladığı an: iş 5 dakikalık takvimle
    # başladığı için tur hep kendi diliminde kalıyor. Yanıtın geldiği an ayrıca
    # yanit_utc olarak saklanıyor.
    zaman = simdi_utc()
    try:
        tur = park_listesi_getir(istemci)
    except KaynakSorunu as hata:
        if hata.gecersiz is not None:
            hatali_kaydet(depo, zaman, hata.gecersiz)
        raise

    yol = ham_yol(zaman, "parklar")
    bilgi = tur_bilgisi(tur)
    depo.yaz(yol, tur.parklar, bilgi)
    alanlar = " ".join(f"{k}={v}" for k, v in bilgi.items())
    gunluk.info("TUR_TAMAM %d otopark kaydedildi %s → %s", tur.kayit, alanlar, yol)


def sorunu_logla(hata: KaynakSorunu) -> None:
    """Sebebi belli kaynak sorunları için uzun hata izi yerine tek, aranabilir satır."""
    if isinstance(hata, GecersizYanit):
        g = hata.gecersiz
        gunluk.error(
            "KAYNAK_GECERSIZ: İSPARK cevap verdi ama yanıt kullanılamaz, bu tur kayıp "
            "(%s) sebep=%s durum=%s surum=%s",
            hata, g.sebep if g else "?", g.durum_kodu if g else "?", ayarlar.KOD_SURUMU,
        )
    else:
        gunluk.error(
            "KAYNAK_KESINTISI: İSPARK'a ulaşılamadı, bu tur kayıp (%s) surum=%s",
            hata, ayarlar.KOD_SURUMU,
        )


def surekli_calis(istemci: httpx.Client, depo: YerelDepo | BlobDepo) -> None:
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
        except KaynakSorunu as hata:
            sorunu_logla(hata)
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

    # ham veri değişmez: aynı adlı bir tur varsa üzerine yazılmaz
    depo = depo_olustur(uzerine_yaz=False)
    mod = "tek-tur" if tek else f"surekli ({ayarlar.TOPLAMA_ARALIGI_SN} sn)"
    gunluk.info("toplayıcı başladı: mod=%s depo=%s surum=%s", mod, ayarlar.DEPO_TURU,
                ayarlar.KOD_SURUMU)
    with istemci_olustur() as istemci:
        if tek:
            try:
                tek_tur(istemci, depo)
            except KaynakSorunu as hata:
                sorunu_logla(hata)
                raise SystemExit(1) from None
        else:
            surekli_calis(istemci, depo)


if __name__ == "__main__":
    main()
