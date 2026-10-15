"""Adım 3 denetimi: indirilen anlık görüntünün parmak izi.

Anlık görüntü (snapshot): tablo kabının belli bir sabahki hâlinin Mac'e indirilmiş
kopyası. Denetimin bütün ölçümleri bunun üzerinde yapılıyor. Parmak izi, aynı
görüntüyle çalışıldığını sonradan kanıtlamak için: her dosyanın sha256 özeti,
gün başına satır / tur / otopark sayısı ve özetteki tamlık. Bütün dosya
özetlerinden tek bir kimlik çıkıyor; MLflow koşularına etiket olarak yazılıyor.

Çalıştırma:
    python kesif/12_anlik_goruntu.py --anlik 2026-10-15
Çıktı: veri/anlik/<ad>/parmak_izi.json ve kesif/sonuclar/12_parmak_izi.csv
"""

import argparse
import hashlib
import json

import denetim_ortak as d
import duckdb
import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anlik", default=d.VARSAYILAN_ANLIK)
    arg = ap.parse_args()
    klasor = d.anlik_klasoru(arg.anlik)
    tablo = klasor / "tablo"

    dosyalar = sorted(p for p in tablo.rglob("*.parquet"))
    if not dosyalar:
        raise SystemExit(f"{tablo} altında parquet yok")
    ozetler = {
        p.relative_to(tablo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in dosyalar
    }
    kimlik = hashlib.sha256(json.dumps(ozetler, sort_keys=True).encode()).hexdigest()[:12]

    con = duckdb.connect()
    gunler = (
        con.sql(f"""
        SELECT tarih, count(*) AS satir, count(DISTINCT zaman_utc) AS tur,
               count(DISTINCT park_id) AS otopark,
               count(DISTINCT park_id) FILTER (canli) AS canli_otopark,
               count(*) FILTER (canli AND gecerli AND acik) AS temiz_satir
        FROM read_parquet('{tablo}/doluluk/**/*.parquet', hive_partitioning = true)
        GROUP BY tarih ORDER BY tarih
    """)
        .df()
        .set_index("tarih")
    )
    ozet = (
        con.sql(f"""
        SELECT tarih, tamlik, surum
        FROM read_parquet('{tablo}/ozet/**/*.parquet', hive_partitioning = true)
    """)
        .df()
        .set_index("tarih")
    )
    gunler = gunler.join(ozet, how="left")
    otopark_say = con.sql(
        f"SELECT count(*) FROM '{tablo}/otoparklar/otoparklar.parquet'"
    ).fetchone()[0]

    uyarilar = []
    if gunler["tamlik"].isna().any():
        uyarilar.append(
            f"özeti olmayan gün: {list(gunler.index[gunler['tamlik'].isna()].astype(str))}"
        )
    son = pd.Timestamp(gunler.index.max()).date().isoformat()
    if son != arg.anlik:
        uyarilar.append(f"son gün {son}, beklenen {arg.anlik}")
    eksik = [pd.Timestamp(g).date().isoformat() for g in gunler.index[gunler["tamlik"] < 95]]

    bilgi = {
        "ad": arg.anlik,
        "kimlik": f"{arg.anlik}-{kimlik}",
        "gun_sayisi": len(gunler),
        "ilk_gun": pd.Timestamp(gunler.index.min()).date().isoformat(),
        "son_gun": son,
        "toplam_satir": int(gunler["satir"].sum()),
        "otoparklar_satir": int(otopark_say),
        "gun_eksik": eksik,
        "dosya_sayisi": len(dosyalar),
        "dosyalar": ozetler,
        "uyarilar": uyarilar,
    }
    (klasor / "parmak_izi.json").write_text(json.dumps(bilgi, indent=2, ensure_ascii=False))
    d.kaydet(gunler, "12_parmak_izi.csv")

    print(gunler.to_string())
    print(
        f"\nkimlik: {bilgi['kimlik']}  gün: {bilgi['gun_sayisi']}  dosya: {len(dosyalar)}"
        f"  satır: {bilgi['toplam_satir']}  otoparklar tablosu: {otopark_say}"
    )
    print(f"GUN_EKSIK (<%95): {eksik}")
    for u in uyarilar:
        print(f"UYARI: {u}")


if __name__ == "__main__":
    main()
