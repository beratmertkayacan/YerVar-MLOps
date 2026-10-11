"""Karne hesaplarının testleri, elle hesaplanabilen küçük örneklerle."""

import pandas as pd

from yervar.degerlendirme.karne import karar_olculeri, karne_olustur, sapma


def satir(simdi: float, hedef: float, model: float, park: int = 1, saat: int = 8) -> dict:
    return {
        "zaman_utc": pd.Timestamp("2026-10-01 05:00"), "park_id": park, "ilce": "KADIKÖY",
        "tip": "AÇIK OTOPARK", "kapasite": 100, "saat": saat, "hafta_sonu": 0.0,
        "doluluk_simdi": simdi, "hedef": hedef, "t_simdiki": simdi, "t_dun": simdi,
        "t_model": model,
    }


def test_dolma_anini_sadece_model_yakalayabilir() -> None:
    # Şu an %80, ufuk sonra %97: dolma anı. Model %96 demiş, bilmiş.
    df = pd.DataFrame([satir(0.80, 0.97, 0.96), satir(0.50, 0.50, 0.50)])

    k = karar_olculeri(df)

    assert k["dolma_ani"] == 1
    assert k["simdiki_gibi"]["dolma_ani_yakalama"] == 0.0   # tanım gereği hiç bilemez
    assert k["model"]["dolma_ani_yakalama"] == 100.0


def test_yanlis_alarm_isabeti_dusurur() -> None:
    # Model iki kez "dolu" dedi, biri doğru çıktı: isabet %50, yakalama %100.
    df = pd.DataFrame([satir(0.90, 0.97, 0.96), satir(0.90, 0.80, 0.96)])

    k = karar_olculeri(df)

    assert (k["model"]["yakalama"], k["model"]["isabet"]) == (100.0, 50.0)


def test_hic_dolu_yoksa_oran_tanimsiz() -> None:
    df = pd.DataFrame([satir(0.3, 0.4, 0.4)])

    assert karar_olculeri(df)["model"]["yakalama"] is None


def test_sapma_yonu_gosterir() -> None:
    # Model her satırda 10 puan fazla diyor.
    df = pd.DataFrame([satir(0.5, 0.5, 0.6), satir(0.3, 0.3, 0.4)])

    assert sapma(df) == 10.0


def test_modelin_yenildigi_otopark_sayilir() -> None:
    df = pd.DataFrame([
        satir(0.5, 0.5, 0.6, park=1),   # basit tahmin tam bildi, model 10 puan kaçırdı
        satir(0.5, 0.7, 0.7, park=2),   # model tam bildi
    ])

    karne = karne_olustur(df, adlar=pd.Series({1: "Birinci", 2: "İkinci"}))

    assert karne["modelin_yenildigi_otopark"] == 1
    otoparklar = karne["tablolar"]["otopark"]
    assert otoparklar.index[0] == 1   # en kötü otopark en üstte
    assert otoparklar["ad"].tolist() == ["Birinci", "İkinci"]
