"""İlk model akışının testleri. Modelin iyi olup olmadığını değil, akışın
doğru kurulduğunu kontrol ediyoruz."""

import math

import pandas as pd

from yervar.egitim.egit import OZELLIKLER, bilgili_sutunlar, bir_ufuk, bol, veri_hazirla


def sahte_set(gun_sayisi: int = 2, park_sayisi: int = 3) -> pd.DataFrame:
    """Özellik seti biçiminde, gün içinde dalgalanan sahte veri."""
    zamanlar = pd.date_range("2026-09-24", periods=288 * gun_sayisi, freq="5min")
    satirlar = []
    for p in range(park_sayisi):
        for z in zamanlar:
            deger = 0.5 + 0.3 * math.sin(2 * math.pi * z.hour / 24)
            satir = {s: 0.0 for s in OZELLIKLER}
            satir.update({
                "zaman_utc": z, "park_id": p, "ilce": "KADIKÖY", "tip": "AÇIK OTOPARK",
                "saat": z.hour, "gunun_dakikasi": z.hour * 60 + z.minute,
                "doluluk_simdi": deger, "hedef": deger,
            })
            satirlar.append(satir)
    return pd.DataFrame(satirlar)


def test_egitim_ve_test_arasinda_ufuk_kadar_bosluk_var() -> None:
    df = veri_hazirla(sahte_set())
    egitim, test = bol(df, ufuk_dk=60)

    son_hedef = egitim["zaman_utc"].max() + pd.Timedelta(minutes=60)
    assert son_hedef < test["zaman_utc"].min()


def test_test_son_gun() -> None:
    df = veri_hazirla(sahte_set(gun_sayisi=3))
    _, test = bol(df, ufuk_dk=30)
    assert test["zaman_utc"].dt.date.nunique() == 1
    assert test["zaman_utc"].dt.day.iloc[0] == 26


def test_akis_uctan_uca_calisir() -> None:
    sonuc = bir_ufuk(sahte_set(), ufuk_dk=30, onem=False)
    assert set(sonuc["hatalar"]) == {"simdiki_gibi", "dun_ayni_saat", "model"}
    assert sonuc["test"] > 0


def test_bos_ve_sabit_sutunlar_atilir() -> None:
    df = veri_hazirla(sahte_set())
    df["doluluk_dun"] = float("nan")   # ilk gün: dün yok
    sutunlar = bilgili_sutunlar(df)
    assert "doluluk_dun" not in sutunlar     # hep boş
    assert "resmi_tatil" not in sutunlar     # hep 0
    assert "doluluk_simdi" in sutunlar
