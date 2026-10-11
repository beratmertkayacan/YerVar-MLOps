"""Eğitim akışının testleri. Modelin iyi olup olmadığını değil, akışın
doğru kurulduğunu kontrol ediyoruz."""

import math

import mlflow
import pandas as pd

from yervar import ayarlar
from yervar.degerlendirme.karne import karne_olustur
from yervar.egitim import egit
from yervar.egitim.bolme import gun_katlari
from yervar.egitim.egit import (
    OZELLIKLER,
    bilgili_sutunlar,
    geri_test,
    ogrenme_hedefi,
    tahmine_cevir,
    veri_hazirla,
)


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


def test_her_gun_sirayla_test_edilir() -> None:
    df = veri_hazirla(sahte_set(gun_sayisi=4))
    katlar = gun_katlari(df, ufuk_dk=30)
    assert [k[0].day for k in katlar] == [25, 26, 27]


def test_egitim_ve_test_arasinda_ufuk_kadar_bosluk_var() -> None:
    df = veri_hazirla(sahte_set(gun_sayisi=3))
    for _gun, egitim, test in gun_katlari(df, ufuk_dk=60):
        son_hedef = egitim["zaman_utc"].max() + pd.Timedelta(minutes=60)
        assert son_hedef < test["zaman_utc"].min()
        assert test["zaman_utc"].dt.normalize().nunique() == 1


def test_son_gun_siniri() -> None:
    df = veri_hazirla(sahte_set(gun_sayisi=5))
    assert len(gun_katlari(df, ufuk_dk=30, son_gun=2)) == 2


def test_bos_ve_sabit_sutunlar_atilir() -> None:
    df = veri_hazirla(sahte_set())
    df["doluluk_dun"] = float("nan")   # ilk gün: dün yok
    sutunlar = bilgili_sutunlar(df)
    assert "doluluk_dun" not in sutunlar     # hep boş
    assert "resmi_tatil" not in sutunlar     # hep 0
    assert "doluluk_simdi" in sutunlar


def test_geri_test_ve_kayit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ayarlar, "MLFLOW_ADRES", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.setattr(ayarlar, "VERI_KOK", tmp_path)

    df = veri_hazirla(sahte_set(gun_sayisi=3))
    katlar = geri_test(df, ufuk_dk=30, son_gun=None)
    assert len(katlar) == 2
    assert set(katlar[0]["hatalar"]) == {"simdiki_gibi", "dun_ayni_saat", "model"}

    karne = karne_olustur(pd.concat(k["_tahmin"] for k in katlar))
    assert len(karne["tablolar"]["saat"]) == 24

    egit.deneyi_hazirla()
    egit.kaydet(30, df, katlar, onem=None, karne=karne)
    kosular = mlflow.search_runs(experiment_names=[egit.DENEY_ADI])
    assert len(kosular) == 1
    assert "metrics.model_genel" in kosular.columns
    assert "metrics.model_sapma" in kosular.columns


def test_fark_hedefi_geri_cevrilince_dolulugu_verir() -> None:
    df = pd.DataFrame({"doluluk_simdi": [0.5, 0.9], "hedef": [0.7, 0.95]})
    fark = ogrenme_hedefi(df, "fark")
    assert fark.round(2).tolist() == [0.2, 0.05]
    assert tahmine_cevir(fark, df, "fark").round(2).tolist() == [0.7, 0.95]
    # Doluluk 1'i geçemez: 0.9 + 0.3 → 1.0
    assert tahmine_cevir(pd.Series([0.3, 0.3]), df, "fark").tolist() == [0.8, 1.0]


def test_fark_modeli_degismeyen_seriyi_aynen_tahmin_eder() -> None:
    # Sahte veride hedef = şimdiki, değişim hep 0. Fark modeli 0 öğrenir,
    # tahmin şimdiki değerin kendisi olur, hata sıfır.
    df = veri_hazirla(sahte_set(gun_sayisi=3))
    katlar = geri_test(df, ufuk_dk=30, son_gun=None, hedef_turu="fark")
    assert katlar[-1]["hatalar"]["model"]["genel"] == 0.0
