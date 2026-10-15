"""Adım 3 denetimi (a, b): bugünkü kodun sınav setindeki temel çizgisi.

Kod değiştirilmiyor: özellikler, model, olasılık modeli ve bölme yervar/'daki
fonksiyonların kendisi. Yeni olan sadece kıyaslar ve ölçüler:

Kıyaslar (hepsi tahmin anında bilinen bilgiyle):
    simdiki       ufuk sonra da şimdiki gibi
    dun_hizasiz   dün, ŞİMDİKİ saatte ne idiyse (bugünkü egit.py'nin kıyası)
    dun_hizali    dün, HEDEF saatte ne idiyse
    hafta_hizali  geçen hafta, hedef saatte ne idiyse
    karisim       şimdiki + dünün o saatten hedef saate değişimi
Değeri olmayan satırda kıyas şimdiki değere düşüyor (egit.py ile aynı kural);
ne kadar satırın gerçekten değeri olduğu da yazılıyor.

Ölçüler: MAE (doluluk puanı ve araç), beceri = 1 - MAE / MAE_simdiki, günlere
göre bootstrap ile %90 aralık, kırılımlar (saat dilimi, bant, gün, en kötü 10
otopark), "dolu mu" kararı (eşik taraması, Brier, kalibrasyon), model bilgisi
(early stopping, iterasyon, kalibrasyon penceresindeki dolu an sayısı).

Çalıştırma:
    python kesif/13_temel_cizgi.py --anlik 2026-10-15                # 4 ufuk
    python kesif/13_temel_cizgi.py --anlik 2026-10-15 --ufuk 30 60   # bir kısmı
Çıktı: kesif/sonuclar/13_*.csv, MLflow "denetim-2026-10", tahminler
veri/anlik/<ad>/denetim/13_tahminler.parquet (Parça 2'de yeniden çalıştırmadan analiz için).
"""

import argparse
import time

import denetim_ortak as d
import duckdb
import numpy as np
import pandas as pd

from yervar import ayarlar
from yervar.degerlendirme.karne import dolu_mu, kalibrasyon
from yervar.egitim import egit
from yervar.egitim.bolme import gun_katlari
from yervar.egitim.olasilik import dolu_hedefi, olasilik_tahmin_et
from yervar.ozellikler.olustur import ozellik_seti, tablolari_bagla

YONTEMLER = ["simdiki", "dun_hizasiz", "dun_hizali", "hafta_hizali", "karisim", "model"]
ESIKLER = [round(0.1 * i, 1) for i in range(1, 10)]


def kiyaslar(test: pd.DataFrame, tablo: pd.Series, ufuk: int) -> tuple[pd.DataFrame, dict]:
    simdi = test["doluluk_simdi"]
    dun_hedef = d.kaydir(test, tablo, ufuk - 24 * 60)
    hafta_hedef = d.kaydir(test, tablo, ufuk - 7 * 24 * 60)
    karisim = (simdi + (dun_hedef - test["doluluk_dun"])).clip(0, 1)
    k = pd.DataFrame(
        {
            "t_simdiki": simdi,
            "t_dun_hizasiz": test["doluluk_dun"].fillna(simdi),
            "t_dun_hizali": dun_hedef.fillna(simdi),
            "t_hafta_hizali": hafta_hedef.fillna(simdi),
            "t_karisim": karisim.fillna(simdi),
        },
        index=test.index,
    )
    kapsam = {
        "dun_hizasiz": float(test["doluluk_dun"].notna().mean()),
        "dun_hizali": float(dun_hedef.notna().mean()),
        "hafta_hizali": float(hafta_hedef.notna().mean()),
        "karisim": float(karisim.notna().mean()),
    }
    return k, kapsam


def kalibrasyon_dolu_sayisi(egitim: pd.DataFrame) -> tuple[int, int]:
    """olasilik.py'deki ayrımın aynısı: son KALIBRASYON_GUN gün."""
    son_gun = egitim["zaman_utc"].dt.normalize().max()
    kesim = son_gun - pd.Timedelta(days=ayarlar.KALIBRASYON_GUN - 1)
    ayir = egitim[egitim["zaman_utc"] >= kesim]
    return len(ayir), int(dolu_hedefi(ayir).sum())


def ufuk_calistir(con, ufuk: int) -> tuple[pd.DataFrame, list[dict]]:
    ham = ozellik_seti(con, d.EGITIM_BAS, d.SON_GUN, d.EGITIM_BAS, ufuk).df()
    tablo = d.deger_tablosu(ham)
    df = egit.veri_hazirla(ham)
    tahminler, bilgiler = [], []
    for gun, egitim, test in gun_katlari(df, ufuk, son_gun=len(d.TEST_GUNLERI)):
        if gun.date() not in d.TEST_GUNLERI:
            raise SystemExit(
                f"beklenmeyen test günü {gun.date()}; anlık görüntü {d.SON_GUN}'de bitmeli"
            )
        bas = time.perf_counter()
        model, sutunlar, t_model = egit.egit_ve_tahmin_et(egitim, test, "fark")
        egitim_sn = time.perf_counter() - bas
        _, olasilik = olasilik_tahmin_et(egitim, test, sutunlar, egit.MODEL_AYARLARI)
        k, kapsam = kiyaslar(test, tablo, ufuk)
        kal_satir, kal_dolu = kalibrasyon_dolu_sayisi(egitim)
        bilgiler.append(
            {
                "ufuk": ufuk,
                "gun": gun.date().isoformat(),
                "egitim_satir": len(egitim),
                "egitim_gun": egitim["zaman_utc"].dt.normalize().nunique(),
                "test_satir": len(test),
                "early_stopping": bool(model.do_early_stopping_),
                "iterasyon": int(model.n_iter_),
                "egitim_sn": round(egitim_sn, 1),
                "atilan_sutun": ",".join(s for s in egit.OZELLIKLER if s not in sutunlar),
                "kalibrasyon_satir": kal_satir,
                "kalibrasyon_dolu": kal_dolu,
                **{f"kapsam_{a}": round(v, 3) for a, v in kapsam.items()},
            }
        )
        t = test[
            ["zaman_utc", "park_id", "kapasite", "saat", "hafta_sonu", "doluluk_simdi", "hedef"]
        ].copy()
        t["park_id"] = t["park_id"].astype(int)
        t = t.join(k).assign(
            t_model=t_model, t_olasilik=olasilik, gun=gun.date().isoformat(), ufuk=ufuk
        )
        tahminler.append(t)
        print(
            f"  ufuk {ufuk:>3} {gun.date()}: model {d.mae(t['hedef'], t['t_model']):.2f} "
            f"şimdiki {d.mae(t['hedef'], t['t_simdiki']):.2f}  "
            f"({egitim_sn:.0f} sn, {model.n_iter_} it)"
        )
    return pd.concat(tahminler), bilgiler


def ozet_tablolari(t: pd.DataFrame) -> dict[str, pd.DataFrame]:
    hata = {y: (t["hedef"] - t[f"t_{y}"]).abs() for y in YONTEMLER}
    sonuc = {}

    satirlar = []
    for ufuk, g in t.groupby("ufuk"):
        gunluk = g.groupby("gun").apply(
            lambda x: pd.Series(
                {"n": len(x), **{f"top_{y}": hata[y][x.index].sum() for y in YONTEMLER}}
            ),
            include_groups=False,
        )
        ga = d.gun_bootstrap(gunluk, YONTEMLER)
        mae_simdi = 100 * hata["simdiki"][g.index].mean()
        for y in YONTEMLER:
            m = 100 * hata[y][g.index].mean()
            gun_mae = 100 * gunluk[f"top_{y}"] / gunluk["n"]
            gun_simdi = 100 * gunluk["top_simdiki"] / gunluk["n"]
            satirlar.append(
                {
                    "ufuk": ufuk,
                    "yontem": y,
                    "mae_puan": round(m, 3),
                    "mae_arac": round(float((hata[y][g.index] * g["kapasite"]).mean()), 2),
                    "beceri": round(1 - m / mae_simdi, 4) if y != "simdiki" else 0.0,
                    "mae_alt90": round(ga[y][0], 3),
                    "mae_ust90": round(ga[y][1], 3),
                    "beceri_alt90": round(ga[f"beceri_{y}"][0], 4) if y != "simdiki" else None,
                    "beceri_ust90": round(ga[f"beceri_{y}"][1], 4) if y != "simdiki" else None,
                    "simdikiyi_yendigi_gun": int((gun_mae < gun_simdi).sum())
                    if y != "simdiki"
                    else None,
                    "gun_sayisi": len(gunluk),
                    "gunluk_mae_std": round(float(gun_mae.std()), 3),
                }
            )
    sonuc["13_ozet.csv"] = pd.DataFrame(satirlar).set_index(["ufuk", "yontem"])

    t = t.assign(
        dilim=d.dilim(t["saat"]),
        bant=pd.cut(t["doluluk_simdi"], d.BANTLAR, labels=d.BANT_ADLARI, right=False),
        hedef_85=np.where(t["hedef"] >= 0.85, "hedef>=85", "hedef<85"),
    )
    for grup, ad in [
        ("gun", "13_gun.csv"),
        ("dilim", "13_dilim.csv"),
        ("bant", "13_bant.csv"),
        ("hedef_85", "13_hedef85.csv"),
    ]:
        tablo = t.groupby(["ufuk", grup], observed=True).apply(
            lambda x: pd.Series(
                {"satir": len(x), **{y: 100 * hata[y][x.index].mean() for y in YONTEMLER}}
            ),
            include_groups=False,
        )
        tablo["beceri_model"] = 1 - tablo["model"] / tablo["simdiki"]
        sonuc[ad] = tablo.round(3)

    otopark = t.groupby(["ufuk", "park_id"]).apply(
        lambda x: pd.Series(
            {
                "satir": len(x),
                "kapasite": x["kapasite"].iloc[0],
                "simdiki": 100 * hata["simdiki"][x.index].mean(),
                "model": 100 * hata["model"][x.index].mean(),
                "model_arac": float((hata["model"][x.index] * x["kapasite"]).mean()),
            }
        ),
        include_groups=False,
    )
    otopark["beceri"] = 1 - otopark["model"] / otopark["simdiki"]
    sonuc["13_otopark_en_kotu.csv"] = (
        otopark.reset_index()
        .sort_values(["ufuk", "model"], ascending=[True, False])
        .groupby("ufuk")
        .head(10)
        .set_index(["ufuk", "park_id"])
        .round(3)
    )
    return sonuc


def karar_tablolari(t: pd.DataFrame) -> dict[str, pd.DataFrame]:
    satirlar, kal = [], []
    for ufuk, g in t.groupby("ufuk"):
        gercek = dolu_mu(g["hedef"], g["kapasite"])
        kararlar = {
            "simdiki": dolu_mu(g["t_simdiki"], g["kapasite"]),
            "model_regresyon": dolu_mu(g["t_model"], g["kapasite"]),
            **{f"olasilik>={e}": g["t_olasilik"] >= e for e in ESIKLER},
        }
        for ad, dedi in kararlar.items():
            dp = int((dedi & gercek).sum())
            yp = int((dedi & ~gercek).sum())  # "dolu" dedik, yer vardı
            yn = int((~dedi & gercek).sum())  # "yer var" dedik, doluydu: kullanıcıyı boşa gönderir
            yakalama = dp / (dp + yn) if dp + yn else np.nan
            isabet = dp / (dp + yp) if dp + yp else np.nan
            satirlar.append(
                {
                    "ufuk": ufuk,
                    "karar": ad,
                    "dolu_an": int(gercek.sum()),
                    "dogru_dolu": dp,
                    "yanlis_dolu": yp,
                    "yanlis_yer_var": yn,
                    "yakalama": yakalama,
                    "isabet": isabet,
                    "f1": 2 * yakalama * isabet / (yakalama + isabet)
                    if yakalama + isabet
                    else np.nan,
                    "yer_var_dedigimizde_dolu_orani": yn / int((~dedi).sum())
                    if (~dedi).sum()
                    else np.nan,
                }
            )
        brier_o = float(((g["t_olasilik"] - gercek.astype(float)) ** 2).mean())
        brier_s = float(
            (
                (dolu_mu(g["t_simdiki"], g["kapasite"]).astype(float) - gercek.astype(float)) ** 2
            ).mean()
        )
        satirlar.append({"ufuk": ufuk, "karar": "brier", "olasilik": brier_o, "simdiki": brier_s})
        kal.append(kalibrasyon(g).assign(ufuk=ufuk))
    karar = pd.DataFrame(satirlar)
    return {
        "13_karar.csv": karar.set_index(["ufuk", "karar"]).round(4),
        "13_maliyet.csv": maliyet_tablosu(karar),
        "13_kalibrasyon.csv": pd.concat(kal).reset_index().set_index(["ufuk", "t_olasilik"]),
    }


def maliyet_tablosu(karar: pd.DataFrame) -> pd.DataFrame:
    """Hangi eşik daha az zarar veriyor?

    "Yer var" deyip kullanıcıyı dolu otoparka göndermek (yanlis_yer_var), "dolu"
    deyip boş otoparktan uzak tutmaktan (yanlis_dolu) daha pahalı. Oranı (k)
    bilmiyoruz, birkaç değer deniyoruz. Olasılık kalibre ise kuramsal en iyi
    eşik 1 / (1 + k); ölçülen en iyi eşik buna yakınsa kalibrasyon işe yarıyor.
    """
    satirlar = []
    esikli = karar[karar["karar"].str.startswith("olasilik>=")].copy()
    esikli["esik"] = esikli["karar"].str.removeprefix("olasilik>=").astype(float)
    for ufuk, g in esikli.groupby("ufuk"):
        for k in [1, 2, 3, 5]:
            maliyet = g["yanlis_dolu"] + k * g["yanlis_yer_var"]
            en_iyi = g.loc[maliyet.idxmin()]
            satirlar.append(
                {
                    "ufuk": ufuk,
                    "k": k,
                    "kuramsal_esik": round(1 / (1 + k), 3),
                    "olculen_en_iyi_esik": en_iyi["esik"],
                    "maliyet": int(maliyet.min()),
                    "yakalama": round(en_iyi["yakalama"], 4),
                    "isabet": round(en_iyi["isabet"], 4),
                    "maliyet_esik_0_5": int(maliyet[g["esik"] == 0.5].iloc[0]),
                }
            )
    return pd.DataFrame(satirlar).set_index(["ufuk", "k"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anlik", default=d.VARSAYILAN_ANLIK)
    ap.add_argument("--ufuk", type=int, nargs="+", default=d.UFUKLAR)
    arg = ap.parse_args()
    klasor = d.anlik_kur(arg.anlik)
    etiket = d.etiketler(arg.anlik, "13_temel_cizgi.py")

    con = duckdb.connect()
    tablolari_bagla(con)

    hepsi, bilgiler = [], []
    for ufuk in arg.ufuk:
        t, b = ufuk_calistir(con, ufuk)
        hepsi.append(t)
        bilgiler += b
    t = pd.concat(hepsi, ignore_index=True)
    (klasor / "denetim").mkdir(exist_ok=True)
    t.to_parquet(klasor / "denetim" / "13_tahminler.parquet")

    tablolar = {
        **ozet_tablolari(t),
        **karar_tablolari(t),
        "13_model_bilgisi.csv": pd.DataFrame(bilgiler).set_index(["ufuk", "gun"]),
    }
    yollar = [d.kaydet(tb, ad) for ad, tb in tablolar.items()]

    mlflow = d.mlflow_hazirla()
    ozet = tablolar["13_ozet.csv"]
    for ufuk in arg.ufuk:
        with mlflow.start_run(run_name=f"temel-{ufuk}dk"):
            mlflow.set_tags({**etiket, "asama": "temel-cizgi"})
            mlflow.log_params(
                {
                    "ufuk_dk": ufuk,
                    "test_ilk": str(d.TEST_GUNLERI[0]),
                    "test_son": str(d.SON_GUN),
                    "egitim_bas": str(d.EGITIM_BAS),
                    **egit.MODEL_AYARLARI,
                }
            )
            for y in YONTEMLER:
                s = ozet.loc[(ufuk, y)]
                mlflow.log_metric(f"mae_{y}", s["mae_puan"])
                if y != "simdiki":
                    mlflow.log_metric(f"beceri_{y}", s["beceri"])
            for yol in yollar:
                mlflow.log_artifact(str(yol))

    pd.set_option("display.width", 200)
    print(
        "\n"
        + ozet[
            [
                "mae_puan",
                "mae_arac",
                "beceri",
                "beceri_alt90",
                "beceri_ust90",
                "simdikiyi_yendigi_gun",
            ]
        ].to_string()
    )
    print(f"\nanlık: {etiket['anlik']}  commit: {etiket['git_commit']}  sonuçlar: {d.SONUC}")


if __name__ == "__main__":
    main()
