"""L3 ilk deneme: basit bir model kurup iki basit tahminle yarıştırmak.

Amaç iyi bir model değil, akışı uçtan uca görmek:
    özellik seti -> eğitim/test bölme -> model -> karşılaştırma

Model: scikit-learn HistGradientBoostingRegressor. Karar ağaçlarını üst üste
ekleyen bir yöntem (gradient boosting). Seçme sebeplerimiz:
  - boş değerlerle kendisi baş ediyor (dün sütunu bazen boş)
  - ilçe, tip, park_id gibi kategorileri doğrudan alıyor
  - hızlı, ek kurulum istemiyor

Rakipler (referans tahminler):
  - simdiki_gibi : X dk sonra da şimdiki gibi olur
  - dun_ayni_saat: X dk sonra dün o saatte ne idiyse o olur

Model bunları geçemiyorsa işe yaramıyor demektir.

Çalıştırma:
    DEPO_TURU=blob python -m yervar.egitim.egit --ufuk 15 30 60 120
"""

import argparse
from datetime import UTC, date, datetime, timedelta

import duckdb
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

from yervar import ayarlar
from yervar.gunluk import gunluk_al
from yervar.ozellikler.olustur import ozellik_seti, tablolari_bagla

gunluk = gunluk_al("yervar.egitim.egit")

KATEGORIK = ["park_id", "ilce", "tip"]
SAYISAL = [
    "saat", "gunun_dakikasi", "haftanin_gunu", "hafta_sonu",
    "resmi_tatil", "arife", "idari_izin", "okul_tatili",
    "kapasite", "doluluk_simdi", "doluluk_5dk_once", "doluluk_15dk_once",
    "doluluk_30dk_once", "doluluk_60dk_once", "degisim_30dk", "ort_son_1saat",
    "doluluk_dun", "doluluk_gecen_hafta",
]
OZELLIKLER = KATEGORIK + SAYISAL


def veri_hazirla(ozellik_df: pd.DataFrame) -> pd.DataFrame:
    """Hedefi olan satırları alır, tipleri modele uygun hale getirir."""
    df = ozellik_df[ozellik_df["hedef"].notna()].copy()
    # Kategorileri bölmeden ÖNCE ayarlıyoruz ki eğitim ve testte aynı olsun.
    for s in KATEGORIK:
        df[s] = df[s].astype("category")
    for s in SAYISAL:
        df[s] = df[s].astype(float)
    return df


def bol(df: pd.DataFrame, ufuk_dk: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Son gün test, öncesi eğitim.

    Rastgele bölmüyoruz: zaman serisinde gelecekten öğrenip geçmişi tahmin
    etmek hile olur. Eğitimin son satırlarının hedefi test gününe düşmesin diye
    arada ufuk kadar boşluk bırakıyoruz.
    """
    test_bas = df["zaman_utc"].max().normalize()
    egitim = df[df["zaman_utc"] + pd.Timedelta(minutes=ufuk_dk) < test_bas]
    test = df[df["zaman_utc"] >= test_bas]
    return egitim, test


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


def bilgili_sutunlar(egitim: pd.DataFrame) -> list[str]:
    """Eğitimde en az iki farklı değeri olan sütunlar.

    Hep boş ya da hep aynı olan bir sütundan model bir şey öğrenemez. Ayrıca
    scikit-learn'ün yeni sürümleri böyle sütunlarda hata veriyor. Örnek: veri
    24 Eylül'de başladığı için ilk günün "dün" sütunu tamamen boş.
    """
    return [s for s in OZELLIKLER if egitim[s].nunique(dropna=True) > 1]


def model_kur() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=300,
        learning_rate=0.05,
        categorical_features="from_dtype",
        random_state=0,
    )


def bir_ufuk(ozellik_df: pd.DataFrame, ufuk_dk: int, onem: bool) -> dict:
    df = veri_hazirla(ozellik_df)
    egitim, test = bol(df, ufuk_dk)
    gunluk.info("ufuk %d dk: eğitim %d satır, test %d satır", ufuk_dk, len(egitim), len(test))

    sutunlar = bilgili_sutunlar(egitim)
    atilan = [s for s in OZELLIKLER if s not in sutunlar]
    if atilan:
        gunluk.info("eğitimde bilgi taşımadığı için atılan sütunlar: %s", ", ".join(atilan))

    model = model_kur()
    model.fit(egitim[sutunlar], egitim["hedef"])
    tahmin = pd.Series(model.predict(test[sutunlar]), index=test.index).clip(0, 1)

    tahminler = {
        "simdiki_gibi": test["doluluk_simdi"],
        # dün değeri yoksa şimdikini kullan, yoksa satırı ölçemeyiz
        "dun_ayni_saat": test["doluluk_dun"].fillna(test["doluluk_simdi"]),
        "model": tahmin,
    }
    sonuc = {"ufuk": ufuk_dk, "egitim": len(egitim), "test": len(test),
             "atilan": atilan, "hatalar": degerlendir(test, tahminler)}

    if onem:
        # Bir sütunu karıştırınca hata ne kadar artıyor? Çok artıyorsa model
        # o sütuna dayanıyor. Hız için testten örnek alıyoruz.
        ornek = test.sample(min(3000, len(test)), random_state=0)
        o = permutation_importance(
            model, ornek[sutunlar], ornek["hedef"],
            scoring="neg_mean_absolute_error", n_repeats=3, random_state=0,
        )
        sira = sorted(zip(sutunlar, o.importances_mean, strict=True), key=lambda x: -x[1])
        sonuc["onem"] = [(ad, round(100 * d, 2)) for ad, d in sira[:8]]
    return sonuc


def yazdir(sonuclar: list[dict]) -> None:
    print("\nHata (doluluk puanı, düşük iyi). Test: son gün.\n")
    print(f"{'ufuk':>5} {'test':>7} | {'ölçü':<15} {'şimdiki':>8} {'dün':>8} {'model':>8}")
    print("-" * 60)
    for s in sonuclar:
        h = s["hatalar"]
        for olcu in ("genel", "sabah_07_10", "neredeyse_dolu"):
            print(f"{s['ufuk']:>5} {s['test']:>7} | {olcu:<15} "
                  f"{h['simdiki_gibi'][olcu]:>8} {h['dun_ayni_saat'][olcu]:>8} "
                  f"{h['model'][olcu]:>8}")
        print("-" * 60)
    for s in sonuclar:
        if "onem" in s:
            print(f"\nUfuk {s['ufuk']} dk, modelin en çok dayandığı sütunlar "
                  "(karıştırınca hatanın artışı, puan):")
            for ad, d in s["onem"]:
                print(f"  {ad:<22} {d:>6}")


def main() -> None:
    ap = argparse.ArgumentParser(description="İlk model denemesi (L3)")
    ap.add_argument("--ufuk", type=int, nargs="+", default=[ayarlar.TAHMIN_UFKU_DK])
    ap.add_argument("--baslangic", type=date.fromisoformat,
                    default=date.fromisoformat(ayarlar.VERI_BASLANGIC))
    ap.add_argument("--bitis", type=date.fromisoformat, help="varsayılan: dün (UTC)")
    ap.add_argument("--onem", action="store_true", help="sütun önemlerini de hesapla")
    arg = ap.parse_args()
    bit = arg.bitis or datetime.now(UTC).date() - timedelta(days=1)

    con = duckdb.connect()
    tablolari_bagla(con)
    sonuclar = []
    for ufuk in arg.ufuk:
        ozellik_df = ozellik_seti(con, arg.baslangic, bit, arg.baslangic, ufuk).df()
        sonuclar.append(bir_ufuk(ozellik_df, ufuk, arg.onem))
    yazdir(sonuclar)


if __name__ == "__main__":
    main()
