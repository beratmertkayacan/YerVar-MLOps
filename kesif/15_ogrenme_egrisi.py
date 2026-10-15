"""Adım 3 denetimi (d): daha çok gün daha iyi model demek mi?

Aynı 7 test günü (9-15 Ekim), aynı model, sadece eğitim penceresi değişiyor:
    kayan_7, kayan_10, kayan_14   test gününden önceki son N gün
    genisleyen                    test gününden önceki bütün günler (bugünkü kod)
Ufuk embargosu bolme.py ile aynı: eğitim satırının hedefi test gününe taşmıyor.

İki şey okunacak:
    1. Pencereler arasında fark var mı (kayan iyi çıkarsa eski günler zarar veriyor).
    2. genisleyen'de test günü ilerledikçe (15 günden 21 güne eğitim) hata düşüyor mu.
       Düşüyorsa veri biriktikçe model kendiliğinden iyileşecek demek.

Süre sınırı: --en-fazla-dk (varsayılan 60). Sınır dolunca o ana kadarki sonuçlar
yazılıp çıkılıyor. Varsayılan ufuklar 30 ve 60 (iş tanımındaki sınır).

Çalıştırma: python kesif/15_ogrenme_egrisi.py --anlik 2026-10-15
Çıktı: kesif/sonuclar/15_*.csv, MLflow "denetim-2026-10" koşusu "ogrenme-egrisi".
"""

import argparse
import time

import denetim_ortak as d
import duckdb
import pandas as pd

from yervar.egitim import egit
from yervar.egitim.bolme import gun_katlari
from yervar.ozellikler.olustur import ozellik_seti, tablolari_bagla

PENCERELER = {"kayan_7": 7, "kayan_10": 10, "kayan_14": 14, "genisleyen": None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anlik", default=d.VARSAYILAN_ANLIK)
    ap.add_argument("--ufuk", type=int, nargs="+", default=[30, 60])
    ap.add_argument("--en-fazla-dk", type=float, default=60)
    arg = ap.parse_args()
    d.anlik_kur(arg.anlik)
    etiket = d.etiketler(arg.anlik, "15_ogrenme_egrisi.py")
    con = duckdb.connect()
    tablolari_bagla(con)

    bas = time.perf_counter()
    satirlar, yarim = [], False
    for ufuk in arg.ufuk:
        df = egit.veri_hazirla(ozellik_seti(con, d.EGITIM_BAS, d.SON_GUN, d.EGITIM_BAS, ufuk).df())
        for gun, egitim_hepsi, test in gun_katlari(df, ufuk, son_gun=len(d.TEST_GUNLERI)):
            simdiki = d.mae(test["hedef"], test["doluluk_simdi"])
            for ad, n in PENCERELER.items():
                if (time.perf_counter() - bas) / 60 > arg.en_fazla_dk:
                    yarim = True
                    break
                egitim = egitim_hepsi
                if n:
                    egitim = egitim_hepsi[egitim_hepsi["zaman_utc"] >= gun - pd.Timedelta(days=n)]
                t0 = time.perf_counter()
                _, _, tahmin = egit.egit_ve_tahmin_et(egitim, test, "fark")
                model = d.mae(test["hedef"], tahmin)
                satirlar.append(
                    {
                        "ufuk": ufuk,
                        "gun": gun.date().isoformat(),
                        "pencere": ad,
                        "egitim_gun": egitim["zaman_utc"].dt.normalize().nunique(),
                        "egitim_satir": len(egitim),
                        "mae_model": round(model, 3),
                        "mae_simdiki": round(simdiki, 3),
                        "beceri": round(1 - model / simdiki, 4),
                        "sn": round(time.perf_counter() - t0, 1),
                    }
                )
                print(
                    f"  ufuk {ufuk:>3} {gun.date()} {ad:<11} {satirlar[-1]['egitim_gun']:>2} gün "
                    f"MAE {model:.2f} (şimdiki {simdiki:.2f})"
                )
            if yarim:
                break
        if yarim:
            print(f"süre sınırı ({arg.en_fazla_dk} dk) doldu, yarım sonuç yazılıyor")
            break

    ham = pd.DataFrame(satirlar).set_index(["ufuk", "gun", "pencere"])
    ozet = (
        ham.groupby(["ufuk", "pencere"])
        .agg(
            gun=("mae_model", "size"),
            mae_model=("mae_model", "mean"),
            mae_simdiki=("mae_simdiki", "mean"),
            beceri_ort=("beceri", "mean"),
            egitim_gun_ort=("egitim_gun", "mean"),
            sn_ort=("sn", "mean"),
        )
        .round(4)
    )
    # genisleyen'in egimi: eğitim günü 1 artınca beceri ne kadar değişiyor (en küçük kareler)
    egim = {}
    for ufuk, g in ham.reset_index().query("pencere == 'genisleyen'").groupby("ufuk"):
        if len(g) >= 3:
            x, y = g["egitim_gun"], g["beceri"]
            egim[ufuk] = float(
                ((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum()
            )
    ozet["genisleyen_beceri_egimi_gun_basina"] = [
        round(egim.get(u), 5) if p == "genisleyen" and u in egim else None for u, p in ozet.index
    ]
    yollar = [d.kaydet(ham, "15_ogrenme_egrisi.csv"), d.kaydet(ozet, "15_ozet.csv")]

    mlflow = d.mlflow_hazirla()
    with mlflow.start_run(run_name="ogrenme-egrisi"):
        mlflow.set_tags({**etiket, "asama": "ogrenme-egrisi", "yarim": str(yarim)})
        for (u, p), s in ozet.iterrows():
            mlflow.log_metric(f"beceri_{p}_{u}dk", float(s["beceri_ort"]))
        for yol in yollar:
            mlflow.log_artifact(str(yol))

    pd.set_option("display.width", 200)
    print("\n" + ozet.to_string())
    print(
        f"\ntoplam {(time.perf_counter() - bas) / 60:.1f} dk  anlık: {etiket['anlik']}  "
        f"commit: {etiket['git_commit']}"
    )


if __name__ == "__main__":
    main()
