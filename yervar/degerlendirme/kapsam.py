"""Hangi otoparkta model, hangisinde basit tahmin gösterilecek.

Otoparkın veri sağlığı son KAPSAM_GUN günden, modelin o otoparktaki başarısı
geri testin karnesinden geliyor. Dört sonuç var:

    model     : veri sağlıklı ve model basit tahminden kötü değil
    basit     : veri yarı yarıya canlı ya da model bu otoparkta kaybediyor
    veri_yok  : sensör donuk, tahmin vermiyoruz
    gosterme  : otopark son gün listede yok
"""

from datetime import date

import duckdb
import pandas as pd

from yervar import ayarlar

KAPSAMLAR = ("model", "basit", "veri_yok", "gosterme")

SAGLIK_SQL = """
SELECT d.park_id, o.ad, o.tip,
       count(DISTINCT d.tarih)                         AS gun,
       count(DISTINCT d.tarih) FILTER (WHERE d.canli)  AS canli_gun,
       max(d.tarih)                                    AS son_gun
FROM doluluk d JOIN otoparklar o USING (park_id)
WHERE d.tarih BETWEEN $bas AND $bit
GROUP BY ALL
"""


def saglik_hesapla(con: duckdb.DuckDBPyConnection, bas: date, bit: date) -> pd.DataFrame:
    """bas ile bit arasında her otoparkın kaç gün göründüğü, kaç gün canlı olduğu."""
    df = con.sql(SAGLIK_SQL, params={"bas": bas, "bit": bit}).df()
    oran = df["canli_gun"] / df["gun"]
    df["saglik"] = "saglikli"
    df.loc[oran < ayarlar.SAGLIKLI_CANLI_ORAN, "saglik"] = "kismen"
    df.loc[df["canli_gun"] == 0, "saglik"] = "donuk"
    # son günü listede olmayan otopark kapanmış ya da numarası değişmiş olabilir (V-014)
    df.loc[pd.to_datetime(df["son_gun"]).dt.date < bit, "saglik"] = "liste_disi"
    return df


def kapsam_belirle(saglik: pd.DataFrame, otopark_karnesi: pd.DataFrame) -> pd.DataFrame:
    """Her otopark için ne gösterileceği. otopark_karnesi: karnedeki otopark tablosu."""
    # karnede park_id kategori tipinde indeks, birleştirmek için sayıya çeviriyoruz
    fark = otopark_karnesi["fark"].rename(index=int)
    df = saglik.copy()
    df["model_farki"] = df["park_id"].map(fark)

    df["kapsam"] = "basit"
    # geri testte hiç görünmeyen otoparkta modeli denemedik, basit tahmin kalıyor
    df.loc[(df["saglik"] == "saglikli") & (df["model_farki"] >= 0), "kapsam"] = "model"
    df.loc[df["saglik"] == "donuk", "kapsam"] = "veri_yok"
    df.loc[df["saglik"] == "liste_disi", "kapsam"] = "gosterme"
    return df.sort_values(["kapsam", "park_id"]).set_index("park_id")


def kapsam_yazdir(kapsam: pd.DataFrame) -> None:
    sayilar = kapsam["kapsam"].value_counts()
    metin = ", ".join(f"{ad} {sayilar.get(ad, 0)}" for ad in KAPSAMLAR)
    print(f"  kapsam: {metin}")
