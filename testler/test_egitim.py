"""Eğitim akışının testleri. Modelin iyi olup olmadığını değil, akışın
doğru kurulduğunu kontrol ediyoruz."""

import math

import mlflow
import pandas as pd

from yervar import ayarlar
from yervar.egitim import egit
from yervar.egitim.bolme import gun_katlari
from yervar.egitim.egit import OZELLIKLER, bilgili_sutunlar, geri_test, veri_hazirla


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

    egit.deneyi_hazirla()
    egit.kaydet(30, df, katlar, onem=None)
    kosular = mlflow.search_runs(experiment_names=[egit.DENEY_ADI])
    assert len(kosular) == 1
    assert "metrics.model_genel" in kosular.columns
