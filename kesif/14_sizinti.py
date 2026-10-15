"""Adım 3 denetimi (c): sızıntıların büyüklüğü. Model yok, sadece SQL.

Soru hep aynı: tahmin anında bilinmeyen bir bilgi satırı seçerken ya da bir
sütunu hesaplarken kullanılıyor mu, kullanılıyorsa ne kadar satırı etkiliyor?

    1. canli (S2)   tablo.py canlılığı BÜTÜN günün farklı değer sayısından
                    hesaplıyor. Sabah 08:00'de günün geri kalanı bilinmiyor.
                    Geçmişe bakan iki karşılık (son 3 saat, son 24 saat) ile
                    karşılaştırıyoruz: kaç satırda karar değişiyor, hangi saatte.
    2. sicrama (S2) bir sonraki turla (lead) karar veriyor. O anki tur için
                    tahmin anında bilinemiyor.
    3. hedef seçimi hedef satırı da temiz süzgecinden geçiyor. Şimdi temiz,
                    ufuk sonra temiz değil diye atılan satırlar "geleceğe göre
                    seçilmiş" satırlar.
    4. dün (S1)     doluluk_dun şimdiki saatin dünü; hedef saatin dünü değil.
                    İkisinin MAE farkı.
    5. gece yarısı (S3) takvim şimdiki günün tarihine bağlanıyor. Hedef ertesi
                    güne düşen satırların payı.
    6. canlı dönüşü günlük canli bir günden ötekine kaç kez değişiyor.

Çalıştırma: python kesif/14_sizinti.py --anlik 2026-10-15
Çıktı: kesif/sonuclar/14_*.csv, MLflow "denetim-2026-10" koşusu "sizinti".
"""

import argparse
from datetime import timedelta

import denetim_ortak as d
import duckdb
import pandas as pd

from yervar.depolama.tablo import CANLI_ESIK
from yervar.ozellikler.olustur import tablolari_bagla

TEMIZ = "canli AND gecerli AND acik"


def canlilik_karsilastir(con) -> pd.DataFrame:
    """Günlük canli ile geçmişe bakan canlılık, İstanbul saatine göre."""
    return (
        con.sql(
            f"""
        WITH pencereli AS (
            SELECT zaman_utc, zaman_ist, park_id, canli, gecerli, acik,
                -- sıçramayı ayıklamıyoruz, çünkü sıçrama da geleceğe bakıyor (madde 2)
                count(DISTINCT bos) OVER (PARTITION BY park_id ORDER BY zaman_utc
                    RANGE BETWEEN INTERVAL 175 MINUTE PRECEDING AND CURRENT ROW)
                    > {CANLI_ESIK} AS canli_3saat,
                count(DISTINCT bos) OVER (PARTITION BY park_id ORDER BY zaman_utc
                    RANGE BETWEEN INTERVAL 1435 MINUTE PRECEDING AND CURRENT ROW)
                    > {CANLI_ESIK} AS canli_24saat
            FROM doluluk
            WHERE CAST(zaman_utc AS DATE) BETWEEN $bas AND $bit
        )
        SELECT hour(zaman_ist) AS saat_ist,
            count(*) AS satir,
            count(*) FILTER (canli) AS gunluk_canli,
            count(*) FILTER (canli AND NOT canli_3saat) AS gunluk_evet_3saat_hayir,
            count(*) FILTER (NOT canli AND canli_3saat) AS gunluk_hayir_3saat_evet,
            count(*) FILTER (canli AND NOT canli_24saat) AS gunluk_evet_24saat_hayir,
            count(*) FILTER (NOT canli AND canli_24saat) AS gunluk_hayir_24saat_evet,
            count(*) FILTER (gecerli AND acik AND canli) AS temiz_gunluk,
            count(*) FILTER (gecerli AND acik AND canli_24saat) AS temiz_24saat
        FROM pencereli GROUP BY ALL ORDER BY saat_ist
    """,
            params={"bas": d.EGITIM_BAS, "bit": d.SON_GUN},
        )
        .df()
        .set_index("saat_ist")
    )


def sicrama_payi(con) -> pd.DataFrame:
    return (
        con.sql(
            """
        SELECT tarih, count(*) AS satir,
            count(*) FILTER (sicrama) AS sicrama,
            count(*) FILTER (NOT gecerli) AS gecersiz,
            count(*) FILTER (NOT acik) AS kapali,
            count(*) FILTER (NOT canli) AS canli_degil,
            round(100 * count(*) FILTER (sicrama) / count(*), 3) AS sicrama_yuzde
        FROM doluluk WHERE tarih BETWEEN $bas AND $bit
        GROUP BY ALL ORDER BY tarih
    """,
            params={"bas": d.EGITIM_BAS, "bit": d.SON_GUN},
        )
        .df()
        .set_index("tarih")
    )


def hedef_secimi(con, ufuk: int) -> dict:
    """Şimdi temiz satırların hedefi neden yok? Test günlerinde."""
    satir = (
        con.sql(
            f"""
        SELECT
            count(*) AS simdi_temiz,
            count(*) FILTER (h.park_id IS NULL) AS hedef_turu_yok,
            count(*) FILTER (h.park_id IS NOT NULL AND NOT (h.canli AND h.gecerli AND h.acik))
                AS hedef_temiz_degil,
            count(*) FILTER (h.park_id IS NOT NULL AND NOT h.canli) AS hedef_canli_degil,
            count(*) FILTER (h.park_id IS NOT NULL AND NOT h.gecerli) AS hedef_gecersiz,
            count(*) FILTER (h.park_id IS NOT NULL AND h.sicrama) AS hedef_sicrama,
            count(*) FILTER (h.park_id IS NOT NULL AND NOT h.acik) AS hedef_kapali,
            count(*) FILTER (
                CAST(t.zaman_ist AS DATE) <> CAST(t.zaman_ist + INTERVAL {ufuk} MINUTE AS DATE))
                AS hedef_ertesi_gun_ist
        FROM doluluk t
        LEFT JOIN doluluk h
            ON h.park_id = t.park_id AND h.zaman_utc = t.zaman_utc + INTERVAL {ufuk} MINUTE
        WHERE t.canli AND t.gecerli AND t.acik AND t.tarih BETWEEN $ilk AND $bit
    """,
            params={"ilk": d.TEST_GUNLERI[0], "bit": d.SON_GUN},
        )
        .df()
        .iloc[0]
        .to_dict()
    )
    return {"ufuk": ufuk, **{k: int(v) for k, v in satir.items()}}


def dun_farki(con, ufuk: int) -> dict:
    """Hizasız (şimdiki saatin dünü) ile hizalı (hedef saatin dünü) dün, test günlerinde.

    İkisi de tahmin anında bilinen bilgi. Sadece ikisinin de değeri olan
    satırlarda karşılaştırıyoruz, böylece fark yalnızca hizadan geliyor.
    """
    satir = (
        con.sql(
            f"""
        WITH temiz AS (
            SELECT park_id, zaman_utc, doluluk FROM doluluk
            WHERE {TEMIZ} AND tarih BETWEEN $okuma AND $okuma_bit
        ),
        anlar AS (
            -- birleştirme anahtarlarını önce sütun yapıyoruz (düz eşitlik)
            SELECT park_id, doluluk,
                zaman_utc + INTERVAL {ufuk} MINUTE                  AS z_hedef,
                zaman_utc - INTERVAL 1 DAY                          AS z_dun,
                zaman_utc + INTERVAL {ufuk} MINUTE - INTERVAL 1 DAY AS z_dun_hedef
            FROM temiz WHERE CAST(zaman_utc AS DATE) BETWEEN $ilk AND $bit
        )
        -- LEFT JOIN ve FILTER bilerek: iç birleştirmede DuckDB sırayı değiştirip önce
        -- h, d0, dh'yi yalnız park_id ile birbirine bağlıyor (otopark başına çarpım).
        SELECT count(*) FILTER (hepsi) AS satir,
            100 * avg(abs(h.doluluk - t.doluluk)) FILTER (hepsi) AS mae_simdiki,
            100 * avg(abs(h.doluluk - d0.doluluk)) FILTER (hepsi) AS mae_dun_hizasiz,
            100 * avg(abs(h.doluluk - dh.doluluk)) FILTER (hepsi) AS mae_dun_hizali
        FROM anlar t
        LEFT JOIN temiz h  ON h.park_id = t.park_id  AND h.zaman_utc = t.z_hedef
        LEFT JOIN temiz d0 ON d0.park_id = t.park_id AND d0.zaman_utc = t.z_dun
        LEFT JOIN temiz dh ON dh.park_id = t.park_id AND dh.zaman_utc = t.z_dun_hedef,
        LATERAL (SELECT h.doluluk IS NOT NULL AND d0.doluluk IS NOT NULL
                        AND dh.doluluk IS NOT NULL AS hepsi)
    """,
            params={
                "okuma": d.TEST_GUNLERI[0] - timedelta(days=2),
                "okuma_bit": d.SON_GUN + timedelta(days=1),
                "ilk": d.TEST_GUNLERI[0],
                "bit": d.SON_GUN,
            },
        )
        .df()
        .iloc[0]
        .to_dict()
    )
    satir = {k: round(float(v), 3) for k, v in satir.items()}
    satir["satir"] = int(satir["satir"])
    satir["hiza_kazanci_puan"] = round(satir["mae_dun_hizasiz"] - satir["mae_dun_hizali"], 3)
    return {"ufuk": ufuk, **satir}


def canli_donusu(con) -> pd.DataFrame:
    return (
        con.sql(
            """
        WITH gunluk AS (
            SELECT park_id, tarih, bool_or(canli) AS canli FROM doluluk
            WHERE tarih BETWEEN $bas AND $bit GROUP BY ALL
        ),
        sirali AS (
            SELECT *, lag(canli) OVER (PARTITION BY park_id ORDER BY tarih) AS dunku FROM gunluk
        )
        SELECT park_id,
            count(*) AS gun, count(*) FILTER (canli) AS canli_gun,
            count(*) FILTER (canli <> dunku) AS donus
        FROM sirali GROUP BY ALL HAVING count(*) FILTER (canli) < count(*)
        ORDER BY donus DESC, park_id
    """,
            params={"bas": d.EGITIM_BAS, "bit": d.SON_GUN},
        )
        .df()
        .set_index("park_id")
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anlik", default=d.VARSAYILAN_ANLIK)
    arg = ap.parse_args()
    d.anlik_kur(arg.anlik)
    etiket = d.etiketler(arg.anlik, "14_sizinti.py")
    con = duckdb.connect()
    tablolari_bagla(con)

    canlilik = canlilik_karsilastir(con)
    sicrama = sicrama_payi(con)
    secim = pd.DataFrame([hedef_secimi(con, u) for u in d.UFUKLAR]).set_index("ufuk")
    dun = pd.DataFrame([dun_farki(con, u) for u in d.UFUKLAR]).set_index("ufuk")
    donus = canli_donusu(con)

    secim["etkilenen_yuzde"] = (100 * secim["hedef_temiz_degil"] / secim["simdi_temiz"]).round(3)
    secim["ertesi_gun_yuzde"] = (100 * secim["hedef_ertesi_gun_ist"] / secim["simdi_temiz"]).round(
        3
    )
    toplam = canlilik.sum()
    ozet = {
        "canli_3saat_farkli_yuzde": round(
            100
            * (toplam["gunluk_evet_3saat_hayir"] + toplam["gunluk_hayir_3saat_evet"])
            / toplam["satir"],
            3,
        ),
        "canli_24saat_farkli_yuzde": round(
            100
            * (toplam["gunluk_evet_24saat_hayir"] + toplam["gunluk_hayir_24saat_evet"])
            / toplam["satir"],
            3,
        ),
        "temiz_fark_24saat_yuzde": round(
            100 * (toplam["temiz_24saat"] - toplam["temiz_gunluk"]) / toplam["temiz_gunluk"], 3
        ),
        "sicrama_yuzde": round(100 * sicrama["sicrama"].sum() / sicrama["satir"].sum(), 3),
        "donen_otopark": len(donus[donus["donus"] > 0]),
    }

    yollar = [
        d.kaydet(canlilik, "14_canlilik_saat.csv"),
        d.kaydet(sicrama, "14_sicrama_gun.csv"),
        d.kaydet(secim, "14_hedef_secimi.csv"),
        d.kaydet(dun, "14_dun_hizasi.csv"),
        d.kaydet(donus, "14_canli_donusu.csv"),
        d.kaydet(pd.Series(ozet, name="deger").to_frame(), "14_ozet.csv"),
    ]

    mlflow = d.mlflow_hazirla()
    with mlflow.start_run(run_name="sizinti"):
        mlflow.set_tags({**etiket, "asama": "sizinti"})
        mlflow.log_metrics(ozet)
        for u in d.UFUKLAR:
            mlflow.log_metric(f"hedef_secimi_yuzde_{u}dk", float(secim.loc[u, "etkilenen_yuzde"]))
            mlflow.log_metric(f"hiza_kazanci_{u}dk", float(dun.loc[u, "hiza_kazanci_puan"]))
        for yol in yollar:
            mlflow.log_artifact(str(yol))

    pd.set_option("display.width", 200)
    print("ÖZET", ozet)
    print("\nHEDEF SEÇİMİ (test günleri)\n" + secim.to_string())
    print("\nDÜN HİZASI (test günleri, ikisi de dolu satırlar)\n" + dun.to_string())
    print("\nCANLILIK SAATE GÖRE (ilk 8 saat)\n" + canlilik.head(8).to_string())
    print(f"\nanlık: {etiket['anlik']}  commit: {etiket['git_commit']}")


if __name__ == "__main__":
    main()
