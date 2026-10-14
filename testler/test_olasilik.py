"""Dolu olma olasılığı modelinin ve ölçülerinin testleri."""

import mlflow
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV

from testler.test_egitim import sahte_set
from yervar import ayarlar
from yervar.degerlendirme.karne import kalibrasyon, karne_olustur, olasilik_olculeri
from yervar.egitim import egit
from yervar.egitim.egit import geri_test, veri_hazirla
from yervar.egitim.olasilik import dolu_hedefi, olasilik_modeli_kur, olasilik_tahmin_et


def dolulu_set() -> pd.DataFrame:
    """Öğlen 12-14 arası %97 dolu olan, kapasitesi 100 olan sahte veri."""
    df = sahte_set(gun_sayisi=3)
    df["kapasite"] = 100.0
    ogle = df["saat"].between(12, 14)
    df.loc[ogle, ["doluluk_simdi", "hedef"]] = 0.97
    return df


def test_dolu_hedefi() -> None:
    df = pd.DataFrame({"hedef": [0.97, 0.5], "kapasite": [100, 100]})
    assert dolu_hedefi(df).tolist() == [1, 0]


def test_hic_dolu_yoksa_sabit_olasilik() -> None:
    df = pd.DataFrame({"hedef": [0.3, 0.4], "kapasite": [100, 100], "saat": [1.0, 2.0]})
    model, olasilik = olasilik_tahmin_et(df, df, ["saat"], {"max_iter": 10})
    assert model is None
    assert olasilik.tolist() == [0.0, 0.0]


def test_brier_elle_hesaplanir() -> None:
    # gerçek: dolu, boş. olasılık 0.8 ve 0.2. Brier = (0.2² + 0.2²) / 2 = 0.04
    # şimdiki gibi: ikisi de şu an boş, olasılık 0 ve 0. Brier = (1 + 0) / 2 = 0.5
    df = pd.DataFrame({
        "hedef": [0.97, 0.5], "doluluk_simdi": [0.5, 0.5],
        "kapasite": [100, 100], "t_olasilik": [0.8, 0.2],
    })
    assert olasilik_olculeri(df) == {"brier_simdiki_gibi": 0.5, "brier_olasilik": 0.04}


def test_kalibrasyon_dilimleri() -> None:
    df = pd.DataFrame({
        "hedef": [0.97, 0.97, 0.5, 0.5], "kapasite": [100] * 4,
        "t_olasilik": [0.75, 0.72, 0.71, 0.05],
    })
    tablo = kalibrasyon(df)
    # 0.7-0.8 diliminde 3 satır, 2'si dolu
    satir = tablo.iloc[-1]
    assert (satir["satir"], satir["gercek_oran"]) == (3, 0.667)


def test_olasilik_geri_testte_ve_kayitta(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ayarlar, "MLFLOW_ADRES", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.setattr(ayarlar, "VERI_KOK", tmp_path)

    df = veri_hazirla(dolulu_set())
    katlar = geri_test(df, ufuk_dk=30, son_gun=None)
    karne = karne_olustur(pd.concat(k["_tahmin"] for k in katlar))
    assert "olasilik" in karne["karar"]
    assert karne["olasilik"]["brier_olasilik"] <= karne["olasilik"]["brier_simdiki_gibi"]

    egit.deneyi_hazirla()
    egit.kaydet(30, df, katlar, onem=None, karne=karne)
    kosu = mlflow.search_runs(experiment_names=[egit.DENEY_ADI]).iloc[0]
    assert "metrics.brier_olasilik" in kosu.index
    # MLflow 3'te modeller koşunun dosyalarında değil, ayrı "logged model" olarak duruyor
    modeller = mlflow.search_logged_models(
        experiment_ids=[kosu.experiment_id], output_format="list"
    )
    assert {m.name for m in modeller} == {"model", "model_olasilik"}


def test_yeterli_gun_varsa_kalibre_edilir(monkeypatch) -> None:
    monkeypatch.setattr(ayarlar, "KALIBRASYON_GUN", 1)
    df = veri_hazirla(dolulu_set())
    sutunlar = ["saat", "doluluk_simdi"]

    # 3 gün: ilk 2 günle eğitim, son günle kalibrasyon
    model, _ = olasilik_modeli_kur(df, sutunlar, {"max_iter": 20})
    assert isinstance(model, CalibratedClassifierCV)


def test_gun_yetmezse_kalibrasyonsuz(monkeypatch) -> None:
    monkeypatch.setattr(ayarlar, "KALIBRASYON_GUN", 5)
    df = veri_hazirla(dolulu_set())

    # 3 günlük veride 5 gün ayrılamaz, düz model dönüyor
    model, _ = olasilik_modeli_kur(df, ["saat", "doluluk_simdi"], {"max_iter": 20})
    assert not isinstance(model, CalibratedClassifierCV)


def test_ilk_gunlerde_bos_sutun_atilir(monkeypatch) -> None:
    # Gerçekte yaşanan hata: "geçen hafta" sütunu ilk günlerde tamamen boş.
    # Kalibrasyon için son gün ayrılınca kalan kısımda bu sütunla model kurulamıyordu.
    monkeypatch.setattr(ayarlar, "KALIBRASYON_GUN", 1)
    df = veri_hazirla(dolulu_set())
    son_gun = df["zaman_utc"].dt.normalize().max()
    df["doluluk_gecen_hafta"] = float("nan")
    df.loc[df["zaman_utc"] >= son_gun, "doluluk_gecen_hafta"] = df["doluluk_simdi"]

    model, sutunlar = olasilik_modeli_kur(
        df, ["saat", "doluluk_simdi", "doluluk_gecen_hafta"], {"max_iter": 20}
    )

    assert isinstance(model, CalibratedClassifierCV)
    assert sutunlar == ["saat", "doluluk_simdi"]
