"""L3: modeli birden çok günde sınar, sonucu MLflow'a kaydeder.

Akış (her ufuk için):
    özellik seti → her gün sırayla test günü olur (geri test)
                 → her günde model ve iki basit tahmin yarışır
                 → ortalamalar + son model MLflow'a yazılır

Model: scikit-learn HistGradientBoostingRegressor. Karar ağaçlarını üst üste
ekleyen bir yöntem (gradient boosting). Boş değerlerle ve kategorilerle
kendisi baş ediyor, ek kurulum istemiyor.

Rakipler (referans tahminler):
  - simdiki_gibi : X dk sonra da şimdiki gibi olur
  - dun_ayni_saat: X dk sonra dün o saatte ne idiyse o olur

Çalıştırma:
    DEPO_TURU=blob python -m yervar.egitim.egit --ufuk 15 30 60 120
Sonuçları görmek:
    mlflow ui --backend-store-uri sqlite:///veri/mlflow.db
"""

import argparse
import subprocess
from datetime import UTC, date, datetime, timedelta

import duckdb
import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

from yervar import ayarlar
from yervar.egitim.bolme import gun_katlari
from yervar.gunluk import gunluk_al
from yervar.ozellikler.olustur import ozellik_seti, tablolari_bagla

gunluk = gunluk_al("yervar.egitim.egit")

DENEY_ADI = "yervar-doluluk"
KATEGORIK = ["park_id", "ilce", "tip"]
SAYISAL = [
    "saat", "gunun_dakikasi", "haftanin_gunu", "hafta_sonu",
    "resmi_tatil", "arife", "idari_izin", "okul_tatili",
    "kapasite", "doluluk_simdi", "doluluk_5dk_once", "doluluk_15dk_once",
    "doluluk_30dk_once", "doluluk_60dk_once", "degisim_30dk", "ort_son_1saat",
    "doluluk_dun", "doluluk_gecen_hafta",
]
OZELLIKLER = KATEGORIK + SAYISAL
MODEL_AYARLARI = {"max_iter": 300, "learning_rate": 0.05}
YONTEMLER = ("simdiki_gibi", "dun_ayni_saat", "model")

# MLflow modeli pickle yerine skops biçiminde saklıyor. Pickle dosyası açılırken
# içindeki herhangi bir kodu çalıştırabilir, skops sadece izin verilen tipleri
# yükler. Modelimizin içinde bulunan ve güvendiğimiz tipler bunlar.
GUVENILEN_TIPLER = [
    "functools.partial",
    "sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor",
    "sklearn.utils.validation.check_array",
]
OLCULER = ("genel", "sabah_07_10", "neredeyse_dolu")


# --- veri ---------------------------------------------------------------------

def veri_hazirla(ozellik_df: pd.DataFrame) -> pd.DataFrame:
    """Hedefi olan satırları alır, tipleri modele uygun hale getirir."""
    df = ozellik_df[ozellik_df["hedef"].notna()].copy()
    # Kategorileri bölmeden ÖNCE ayarlıyoruz ki eğitim ve testte aynı olsun.
    for s in KATEGORIK:
        df[s] = df[s].astype("category")
    for s in SAYISAL:
        df[s] = df[s].astype(float)
    return df


def bilgili_sutunlar(egitim: pd.DataFrame) -> list[str]:
    """Eğitimde en az iki farklı değeri olan sütunlar.

    Hep boş ya da hep aynı olan bir sütundan model bir şey öğrenemez. Ayrıca
    scikit-learn'ün yeni sürümleri böyle sütunlarda hata veriyor. Örnek: veri
    24 Eylül'de başladığı için ilk günün "dün" sütunu tamamen boş.
    """
    return [s for s in OZELLIKLER if egitim[s].nunique(dropna=True) > 1]


# --- ölçme --------------------------------------------------------------------

def hata(gercek: pd.Series, tahmin: pd.Series) -> float:
    """Ortalama mutlak hata, doluluk puanı olarak (0-100)."""
    return round(100 * (gercek - tahmin).abs().mean(), 2)


def degerlendir(test: pd.DataFrame, tahminler: dict[str, pd.Series]) -> dict:
    """Her tahmini üç açıdan ölçer: genel, sabah dolma saatleri, neredeyse dolu."""
    sabah = test["saat"].between(7, 10)
    dolu = test["doluluk_simdi"] >= 0.85
    sonuc = {}
    for ad, tahmin in tahminler.items():
        sonuc[ad] = {
            "genel": hata(test["hedef"], tahmin),
            "sabah_07_10": hata(test["hedef"][sabah], tahmin[sabah]),
            "neredeyse_dolu": hata(test["hedef"][dolu], tahmin[dolu]),
        }
    return sonuc


# --- model --------------------------------------------------------------------

def model_kur() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        **MODEL_AYARLARI, categorical_features="from_dtype", random_state=0
    )


def egit_ve_tahmin_et(egitim: pd.DataFrame, test: pd.DataFrame):
    """Eğitimde işe yarayan sütunlarla modeli kurar, testi tahmin eder."""
    sutunlar = bilgili_sutunlar(egitim)
    model = model_kur()
    model.fit(egitim[sutunlar], egitim["hedef"])
    tahmin = pd.Series(model.predict(test[sutunlar]), index=test.index).clip(0, 1)
    return model, sutunlar, tahmin


def geri_test(df: pd.DataFrame, ufuk_dk: int, son_gun: int | None) -> list[dict]:
    """Her test günü için modeli eğitip üç yöntemi ölçer."""
    katlar = []
    for gun, egitim, test in gun_katlari(df, ufuk_dk, son_gun=son_gun):
        model, sutunlar, tahmin = egit_ve_tahmin_et(egitim, test)
        tahminler = {
            "simdiki_gibi": test["doluluk_simdi"],
            # dün değeri yoksa şimdikini kullan, yoksa satırı ölçemeyiz
            "dun_ayni_saat": test["doluluk_dun"].fillna(test["doluluk_simdi"]),
            "model": tahmin,
        }
        katlar.append({
            "gun": gun.date().isoformat(),
            "egitim": len(egitim),
            "test": len(test),
            "atilan": [s for s in OZELLIKLER if s not in sutunlar],
            "hatalar": degerlendir(test, tahminler),
            "_model": model, "_sutunlar": sutunlar, "_test": test,
        })
        gunluk.info("ufuk %d dk, test %s: model %.2f, şimdiki gibi %.2f",
                    ufuk_dk, gun.date(), katlar[-1]["hatalar"]["model"]["genel"],
                    katlar[-1]["hatalar"]["simdiki_gibi"]["genel"])
    return katlar


def ortalama(katlar: list[dict]) -> dict:
    """Günlerin ortalama hatası: {yontem: {olcu: deger}}"""
    return {
        y: {o: round(sum(k["hatalar"][y][o] for k in katlar) / len(katlar), 2) for o in OLCULER}
        for y in YONTEMLER
    }


def sutun_onemi(kat: dict) -> list[tuple[str, float]]:
    """Bir sütunu karıştırınca hata ne kadar artıyor? Çok artıyorsa model
    o sütuna dayanıyor. Hız için testten örnek alıyoruz."""
    test = kat["_test"]
    ornek = test.sample(min(3000, len(test)), random_state=0)
    o = permutation_importance(
        kat["_model"], ornek[kat["_sutunlar"]], ornek["hedef"],
        scoring="neg_mean_absolute_error", n_repeats=3, random_state=0,
    )
    sira = sorted(zip(kat["_sutunlar"], o.importances_mean, strict=True), key=lambda x: -x[1])
    return [(ad, round(100 * d, 2)) for ad, d in sira[:8]]


# --- kayıt --------------------------------------------------------------------

def git_bilgisi() -> dict:
    """Hangi kodla çalıştık? Commit'lenmemiş değişiklik varsa sonuç tam
    tekrarlanamaz, bunu da not ediyoruz."""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
        kirli = subprocess.run(["git", "status", "--porcelain", "--", "yervar"],
                               capture_output=True, text=True, check=True).stdout.strip()
        return {"git_commit": commit, "git_temiz": str(not kirli)}
    except (OSError, subprocess.CalledProcessError):
        return {"git_commit": "bilinmiyor", "git_temiz": "bilinmiyor"}


def deneyi_hazirla() -> None:
    """MLflow'a nereye yazacağını söyler. Varsayılan: veri/ altında yerel dosya."""
    mlflow.set_tracking_uri(ayarlar.MLFLOW_ADRES)
    if mlflow.get_experiment_by_name(DENEY_ADI) is None:
        yer = (ayarlar.VERI_KOK / "mlflow_artifacts").resolve().as_uri()
        mlflow.create_experiment(DENEY_ADI, artifact_location=yer)
    mlflow.set_experiment(DENEY_ADI)


def kaydet(ufuk_dk: int, df: pd.DataFrame, katlar: list[dict], onem) -> None:
    ort = ortalama(katlar)
    with mlflow.start_run(run_name=f"ufuk-{ufuk_dk}dk"):
        mlflow.set_tags({**git_bilgisi(), "katman": "L3"})
        mlflow.log_params({
            "ufuk_dk": ufuk_dk,
            "model": "HistGradientBoostingRegressor",
            **MODEL_AYARLARI,
            "veri_ilk": str(df["zaman_utc"].min().date()),
            "veri_son": str(df["zaman_utc"].max().date()),
            "test_gun_sayisi": len(katlar),
            "satir": len(df),
        })
        for y in YONTEMLER:
            for o in OLCULER:
                mlflow.log_metric(f"{y}_{o}", ort[y][o])
        kazanilan = sum(k["hatalar"]["model"]["genel"] < k["hatalar"]["simdiki_gibi"]["genel"]
                        for k in katlar)
        mlflow.log_metric("modelin_kazandigi_gun", kazanilan)

        mlflow.log_dict(
            {"katlar": [{k: v for k, v in kat.items() if not k.startswith("_")} for kat in katlar],
             "sutun_onemi": onem},
            "geri_test.json",
        )
        # Canlıda kullanılacak model: bütün veriyle eğitiliyor.
        sutunlar = bilgili_sutunlar(df)
        son_model = model_kur().fit(df[sutunlar], df["hedef"])
        mlflow.sklearn.log_model(son_model, name="model", skops_trusted_types=GUVENILEN_TIPLER)
        mlflow.log_dict({"sutunlar": sutunlar}, "sutunlar.json")


def yazdir(ufuk_dk: int, katlar: list[dict]) -> None:
    ort = ortalama(katlar)
    kazanilan = sum(k["hatalar"]["model"]["genel"] < k["hatalar"]["simdiki_gibi"]["genel"]
                    for k in katlar)
    print(f"\nUfuk {ufuk_dk} dk, {len(katlar)} test günü ortalaması "
          f"(model {kazanilan}/{len(katlar)} günde 'şimdiki gibi'yi geçti)")
    print(f"  {'ölçü':<15} {'şimdiki':>8} {'dün':>8} {'model':>8}")
    for o in OLCULER:
        print(f"  {o:<15} {ort['simdiki_gibi'][o]:>8} {ort['dun_ayni_saat'][o]:>8} "
              f"{ort['model'][o]:>8}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Geri test ve MLflow kaydı (L3)")
    ap.add_argument("--ufuk", type=int, nargs="+", default=[ayarlar.TAHMIN_UFKU_DK])
    ap.add_argument("--baslangic", type=date.fromisoformat,
                    default=date.fromisoformat(ayarlar.VERI_BASLANGIC))
    ap.add_argument("--bitis", type=date.fromisoformat, help="varsayılan: dün (UTC)")
    ap.add_argument("--son-gun", type=int, default=7, help="en fazla kaç gün test edilsin")
    ap.add_argument("--onem", action="store_true", help="sütun önemlerini de hesapla")
    arg = ap.parse_args()
    bit = arg.bitis or datetime.now(UTC).date() - timedelta(days=1)

    con = duckdb.connect()
    tablolari_bagla(con)
    deneyi_hazirla()

    for ufuk in arg.ufuk:
        df = veri_hazirla(ozellik_seti(con, arg.baslangic, bit, arg.baslangic, ufuk).df())
        katlar = geri_test(df, ufuk, arg.son_gun)
        onem = sutun_onemi(katlar[-1]) if arg.onem else None
        yazdir(ufuk, katlar)
        if onem:
            print("  modelin en çok dayandığı sütunlar (son test günü):")
            for ad, d in onem:
                print(f"    {ad:<22} {d:>6}")
        kaydet(ufuk, df, katlar, onem)

    print(f"\nKayıt: {ayarlar.MLFLOW_ADRES}")
    print("Görmek için: mlflow ui --backend-store-uri " + ayarlar.MLFLOW_ADRES)


if __name__ == "__main__":
    main()
