"""L1 — Bir günün ham turlarını temiz, sorgulanabilir iki tabloya çevirir.

Ham katmanda her 5 dakika ayrı bir JSON dosyası (günde 288 dosya). Model eğitmek,
grafik çizmek ya da Power BI'da rapor açmak için bunların tek tabloya dönüşmesi
gerekiyor. Bu modül bir günü okur, temizler ve iki Parquet dosyası yazar:

    tablo/doluluk/tarih=2026-09-24/doluluk.parquet   ← her 5 dk × her otopark
    tablo/otoparklar/otoparklar.parquet              ← her otoparkın sabit bilgileri

İki tabloya ayırmak "yıldız şeması" (star schema) denen düzen: değişen ölçümler
(doluluk) bir tabloda, değişmeyen nitelikler (ad, ilçe, konum) ayrı tabloda.
Otopark adı 70.000 satırda tekrar etmez; Power BI da bu düzeni doğrudan anlar.

"tarih=2026-09-24" klasör adı "hive bölümlemesi": DuckDB ve Power BI klasör
adından tarih sütununu kendiliğinden çıkarır ve sadece istenen günleri okur.

Çalıştırma:
    python -m yervar.depolama.tablo                           # dün (UTC)
    python -m yervar.depolama.tablo --tarih 2026-09-24        # belirli bir gün
    python -m yervar.depolama.tablo --baslangic 2026-09-22    # o günden düne kadar

Aynı günü tekrar işlemek güvenli: dosyanın üzerine yazılır (idempotent).
"""

import argparse
import gzip
import json
import re
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb

from yervar import ayarlar
from yervar.depolama.ham import BlobDepo, YerelDepo, depo_olustur
from yervar.gunluk import gunluk_al

gunluk = gunluk_al("yervar.depolama.tablo")

DAMGA = re.compile(r"_(\d{8}T\d{6}Z)\.json\.gz$")

# Bir otoparkın gün içinde en az bu kadar farklı değer göstermesi gerekiyor ki
# "canlı" sayılsın. Veri denetiminde donuk otoparklar tek bir değerde, yarı donuk
# olanlar 2-3 değerde takılı kalıyordu; 3'ün üstü gerçek bir sensör demek.
CANLI_ESIK = 3


def gunun_satirlari(depo: YerelDepo | BlobDepo, gun: date) -> list[dict]:
    """Bir günün tüm ham turlarını okuyup düz satır listesine çevirir.

    Zaman, API'den değil dosya adından alınıyor: liste ucu güncelleme zamanı
    vermiyor, bizim toplama anımız tek güvenilir kaynak.
    """
    satirlar = []
    for ad in depo.listele(f"{gun:%Y/%m/%d}/"):
        eslesme = DAMGA.search(ad)
        if not eslesme:
            continue
        zaman = datetime.strptime(eslesme.group(1), "%Y%m%dT%H%M%SZ")
        for p in json.loads(gzip.decompress(depo.oku_bayt(ad))):
            satirlar.append({
                "zaman": zaman.strftime("%Y-%m-%d %H:%M:%S"),
                "park_id": p["parkID"],
                "ad": p.get("parkName"),
                "ilce": p.get("district"),
                "tip": p.get("parkType"),
                # API konumu metin olarak veriyor ("41.0246"); sayıya çeviriyoruz.
                "lat": float(p["lat"]) if p.get("lat") else None,
                "lng": float(p["lng"]) if p.get("lng") else None,
                "kapasite": p.get("capacity"),
                "bos": p.get("emptyCapacity"),
                "acik": p.get("isOpen"),
            })
    return satirlar


# Dönüşümün tamamı tek SQL'de. Adımlar yukarıdan aşağı okunur.
DOLULUK_SQL = f"""
WITH dilimli AS (
    -- 1. Her turu 5 dakikalık dilime yuvarla: 12:05:48 → 12:05:00.
    --    Böylece farklı saniyelerde çekilen turlar aynı zaman ızgarasına oturur.
    SELECT time_bucket(INTERVAL 5 MINUTE, zaman) AS zaman_utc, *
    FROM ham
),
tekil AS (
    -- 2. Aynı dilimde aynı otopark iki kez varsa (ör. yerelden buluta geçiş
    --    sırasında iki toplayıcı çalıştı) en son çekileni tut.
    SELECT * FROM dilimli
    QUALIFY row_number() OVER (PARTITION BY zaman_utc, park_id ORDER BY zaman DESC) = 1
),
canlilik AS (
    -- 3. Otoparkın gün içinde kaç farklı değer gösterdiği. Hiç değişmeyen bir
    --    sayı sensörden değil, sabit bir varsayılandan geliyordur.
    SELECT park_id, count(DISTINCT bos) AS farkli_deger
    FROM tekil GROUP BY park_id
)
SELECT
    t.zaman_utc,
    -- İstanbul 2016'dan beri yıl boyu UTC+3; yaz saati yok, sabit fark güvenli.
    t.zaman_utc + INTERVAL 3 HOUR                        AS zaman_ist,
    t.park_id,
    t.kapasite,
    t.bos,
    CASE WHEN t.kapasite > 0
         THEN round((t.kapasite - t.bos) / t.kapasite, 4) END AS doluluk,
    t.acik = 1                                           AS acik,
    c.farkli_deger > {CANLI_ESIK}                        AS canli,
    -- Satırı silmiyoruz, işaretliyoruz: neyin neden dışlandığı görünür kalsın.
    (t.bos BETWEEN 0 AND t.kapasite)                     AS gecerli
FROM tekil t JOIN canlilik c USING (park_id)
ORDER BY t.zaman_utc, t.park_id
"""

OTOPARKLAR_SQL = """
-- Her otopark için günün en son görülen bilgileri (ad, ilçe, tip, konum).
SELECT
    park_id,
    arg_max(ad, zaman)   AS ad,
    arg_max(ilce, zaman) AS ilce,
    arg_max(tip, zaman)  AS tip,
    arg_max(lat, zaman)  AS lat,
    arg_max(lng, zaman)  AS lng,
    max(zaman)           AS son_gorulme
FROM ham GROUP BY park_id ORDER BY park_id
"""

HAM_SUTUNLAR = {
    "zaman": "TIMESTAMP", "park_id": "INTEGER", "ad": "VARCHAR", "ilce": "VARCHAR",
    "tip": "VARCHAR", "lat": "DOUBLE", "lng": "DOUBLE", "kapasite": "INTEGER",
    "bos": "INTEGER", "acik": "INTEGER",
}


def tabloya_cevir(satirlar: list[dict], klasor: Path) -> dict:
    """Satırları DuckDB'ye yükler, iki Parquet dosyası yazar ve özet döndürür.

    Saf dönüşüm: depoya dokunmaz, sadece verilen klasöre yazar. Test edilebilir.
    """
    # Satırları satır satır INSERT etmek yavaş; tek bir JSON dosyasına yazıp
    # DuckDB'ye tek seferde okutmak saniyeler içinde bitiyor.
    kaynak = klasor / "ham.ndjson"
    with kaynak.open("w", encoding="utf-8") as f:
        for s in satirlar:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    con = duckdb.connect()
    con.execute(f"CREATE TABLE ham AS SELECT * FROM read_json('{kaynak}', columns={HAM_SUTUNLAR})")
    # zstd: Parquet'in en iyi sıkıştırmalarından biri; okurken de hızlı.
    bicim = "(FORMAT parquet, COMPRESSION zstd)"
    con.execute(f"COPY ({DOLULUK_SQL}) TO '{klasor / 'doluluk.parquet'}' {bicim}")
    con.execute(f"COPY ({OTOPARKLAR_SQL}) TO '{klasor / 'otoparklar.parquet'}' {bicim}")

    tur, satir, canli, gecersiz = con.execute(f"""
        SELECT count(DISTINCT zaman_utc), count(*), count(DISTINCT park_id) FILTER (canli),
               count(*) FILTER (NOT gecerli)
        FROM '{klasor / 'doluluk.parquet'}'
    """).fetchone()
    con.close()
    return {"tur": tur, "satir": satir, "canli_otopark": canli, "gecersiz_satir": gecersiz}


def gunu_isle(ham: YerelDepo | BlobDepo, tablo: YerelDepo | BlobDepo, gun: date) -> None:
    """Bir günü okur, dönüştürür ve tablo deposuna yazar."""
    satirlar = gunun_satirlari(ham, gun)
    if not satirlar:
        gunluk.warning("%s: ham veri yok, atlandı", gun)
        return

    with tempfile.TemporaryDirectory() as gecici:
        klasor = Path(gecici)
        ozet = tabloya_cevir(satirlar, klasor)

        yol = f"doluluk/tarih={gun:%Y-%m-%d}/doluluk.parquet"
        tablo.yaz_bayt(yol, (klasor / "doluluk.parquet").read_bytes())
        # Otopark bilgileri tek dosya: her işlenen gün en güncel hâliyle üzerine yazar.
        otoparklar = (klasor / "otoparklar.parquet").read_bytes()
        tablo.yaz_bayt("otoparklar/otoparklar.parquet", otoparklar)

    tamlik = ozet["tur"] / 288 * 100
    gunluk.info(
        "%s: %d tur (%%%.0f), %d satır, %d canlı otopark, %d geçersiz satır → %s",
        gun, ozet["tur"], tamlik, ozet["satir"], ozet["canli_otopark"],
        ozet["gecersiz_satir"], yol,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Ham turları günlük tabloya çevir (L1)")
    ap.add_argument("--tarih", type=date.fromisoformat, help="tek bir gün (YYYY-AA-GG)")
    ap.add_argument("--baslangic", type=date.fromisoformat, help="bu günden düne kadar hepsi")
    arg = ap.parse_args()

    dun = datetime.now(UTC).date() - timedelta(days=1)
    if arg.baslangic:
        gunler = [arg.baslangic + timedelta(days=i) for i in range((dun - arg.baslangic).days + 1)]
    else:
        gunler = [arg.tarih or dun]

    ham = depo_olustur(ayarlar.AZURE_KAP)
    tablo = depo_olustur(ayarlar.TABLO_KAP)
    for gun in gunler:
        gunu_isle(ham, tablo, gun)


if __name__ == "__main__":
    main()
