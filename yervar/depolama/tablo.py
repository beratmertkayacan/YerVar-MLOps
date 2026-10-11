"""L1 — Bir günün ham turlarını temiz, sorgulanabilir iki tabloya çevirir.

Ham katmanda her 5 dakika ayrı bir JSON dosyası (günde 288 dosya). Model eğitmek,
grafik çizmek ya da Power BI'da rapor açmak için bunların tek tabloya dönüşmesi
gerekiyor. Bu modül bir günü okur, temizler ve iki Parquet dosyası yazar:

    tablo/doluluk/tarih=2026-09-24/doluluk.parquet   ← her 5 dk × her otopark
    tablo/otoparklar/otoparklar.parquet              ← şimdiye kadar görülen her otopark

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

# Tek tur sıçraması (V-013): önceki ve sonraki tur birbirine yakınken arada tek
# bir tur ikisinden de çok uzaksa bu araç hareketi değil, veri hatası. Neredeyse
# hepsi gece 00:00'da (İstanbul) oluyor. Eşikler kesif/06'daki sorguyla aynı:
# komşular kapasitenin %5'i içinde, sıçrama kapasitenin %30'u (en az 10 araç).
SICRAMA_KOMSU_ORAN = 0.05
SICRAMA_ORAN = 0.3
SICRAMA_EN_AZ = 10

OTOPARKLAR_YOL = "otoparklar/otoparklar.parquet"


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
komsulu AS (
    -- 3. Her satırın yanına aynı otoparkın bir önceki ve bir sonraki turunu koy.
    --    ara_once / ara_sonra: komşu tur gerçekten 5 dk uzakta mı? Arada tur
    --    kaçmışsa karşılaştırma anlamsız, o zaman sıçrama demiyoruz.
    --    İstanbul 00:00 = UTC 21:00, yani gün ortası; komşular aynı günde.
    SELECT *,
        lag(bos)  OVER w                   AS onceki,
        lead(bos) OVER w                   AS sonraki,
        zaman_utc - lag(zaman_utc) OVER w  AS ara_once,
        lead(zaman_utc) OVER w - zaman_utc AS ara_sonra
    FROM tekil
    WINDOW w AS (PARTITION BY park_id ORDER BY zaman_utc)
),
isaretli AS (
    -- 4. Tek tur sıçraması (V-013). Günün ilk ve son turunun bir komşusu yok,
    --    karşılaştırma NULL çıkıyor; coalesce ile onları "sıçrama değil" sayıyoruz.
    SELECT *,
        coalesce(
            ara_once = INTERVAL 5 MINUTE AND ara_sonra = INTERVAL 5 MINUTE
            AND abs(onceki - sonraki) <= {SICRAMA_KOMSU_ORAN} * kapasite
            AND abs(bos - onceki) >= greatest({SICRAMA_ORAN} * kapasite, {SICRAMA_EN_AZ}),
            false) AS sicrama
    FROM komsulu
),
canlilik AS (
    -- 5. Otoparkın gün içinde kaç farklı değer gösterdiği. Hiç değişmeyen bir
    --    sayı sensörden değil, sabit bir varsayılandan geliyordur. Sıçramaları
    --    saymıyoruz: donuk bir otopark gece yarısı hatası yüzünden canlı görünmesin.
    SELECT park_id, count(DISTINCT bos) FILTER (NOT sicrama) AS farkli_deger
    FROM isaretli GROUP BY park_id
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
    t.sicrama,
    -- Satırı silmiyoruz, işaretliyoruz: neyin neden dışlandığı görünür kalsın.
    (t.bos BETWEEN 0 AND t.kapasite) AND NOT t.sicrama   AS gecerli
FROM isaretli t JOIN canlilik c USING (park_id)
ORDER BY t.zaman_utc, t.park_id
"""

# Otopark listesi zamanla değişiyor (V-012): İSPARK bazı otoparkları listeden
# çıkarıyor, yenilerini ekliyor. Eskiden tablo her gün sadece o günün listesiyle
# yazılıyordu, çıkan otoparkın adı ilçesi kayboluyordu. Artık eski tabloyla
# bugünün listesi birleşiyor: çıkan otopark kalıyor, son_gorulme'de donuyor.
ESKI_OTOPARKLAR = """
CREATE TABLE eski (park_id INTEGER, ad VARCHAR, ilce VARCHAR, tip VARCHAR,
                   lat DOUBLE, lng DOUBLE, ilk_gorulme TIMESTAMP, son_gorulme TIMESTAMP)
"""

OTOPARKLAR_SQL = """
WITH bugun AS (
    -- Bugün görülen her otoparkın en son bilgisi (ad, ilçe, tip, konum).
    SELECT
        park_id,
        arg_max(ad, zaman)   AS ad,
        arg_max(ilce, zaman) AS ilce,
        arg_max(tip, zaman)  AS tip,
        arg_max(lat, zaman)  AS lat,
        arg_max(lng, zaman)  AS lng,
        min(zaman)           AS ilk_gorulme,
        max(zaman)           AS son_gorulme
    FROM ham GROUP BY park_id
),
hepsi AS (
    SELECT * FROM bugun
    UNION ALL BY NAME
    SELECT * FROM eski
)
-- Bilgiyi en son görüldüğü satırdan alıyoruz. Eski bir günü yeniden işlesek
-- bile daha yeni bir ad ya da konum geri gitmiyor.
SELECT
    park_id,
    arg_max(ad, son_gorulme)   AS ad,
    arg_max(ilce, son_gorulme) AS ilce,
    arg_max(tip, son_gorulme)  AS tip,
    arg_max(lat, son_gorulme)  AS lat,
    arg_max(lng, son_gorulme)  AS lng,
    min(ilk_gorulme)           AS ilk_gorulme,
    max(son_gorulme)           AS son_gorulme
FROM hepsi GROUP BY park_id ORDER BY park_id
"""

HAM_SUTUNLAR = {
    "zaman": "TIMESTAMP", "park_id": "INTEGER", "ad": "VARCHAR", "ilce": "VARCHAR",
    "tip": "VARCHAR", "lat": "DOUBLE", "lng": "DOUBLE", "kapasite": "INTEGER",
    "bos": "INTEGER", "acik": "INTEGER",
}


def tabloya_cevir(satirlar: list[dict], klasor: Path, eski_otoparklar: Path | None = None) -> dict:
    """Satırları DuckDB'ye yükler, iki Parquet dosyası yazar ve özet döndürür.

    eski_otoparklar: şimdiye kadar biriken otopark tablosu (yoksa None).
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

    con.execute(ESKI_OTOPARKLAR)
    if eski_otoparklar:
        tanim = con.execute(f"DESCRIBE SELECT * FROM '{eski_otoparklar}'").fetchall()
        sutunlar = {satir[0] for satir in tanim}
        # 0.5 öncesi tabloda ilk_gorulme yok. Onu yok sayıyoruz: zaten bütün günleri
        # baştan yeniden işleyince tablo doğru hâliyle kuruluyor.
        if "ilk_gorulme" in sutunlar:
            con.execute(f"INSERT INTO eski BY NAME SELECT * FROM '{eski_otoparklar}'")
    # zstd: Parquet'in en iyi sıkıştırmalarından biri; okurken de hızlı.
    bicim = "(FORMAT parquet, COMPRESSION zstd)"
    con.execute(f"COPY ({DOLULUK_SQL}) TO '{klasor / 'doluluk.parquet'}' {bicim}")
    con.execute(f"COPY ({OTOPARKLAR_SQL}) TO '{klasor / 'otoparklar.parquet'}' {bicim}")

    tur, satir, canli, gecersiz, sicrama = con.execute(f"""
        SELECT count(DISTINCT zaman_utc), count(*), count(DISTINCT park_id) FILTER (canli),
               count(*) FILTER (NOT gecerli), count(*) FILTER (sicrama)
        FROM '{klasor / 'doluluk.parquet'}'
    """).fetchone()
    con.close()
    return {"tur": tur, "satir": satir, "canli_otopark": canli,
            "gecersiz_satir": gecersiz, "sicrama": sicrama}


def gunu_isle(ham: YerelDepo | BlobDepo, tablo: YerelDepo | BlobDepo, gun: date) -> None:
    """Bir günü okur, dönüştürür ve tablo deposuna yazar."""
    satirlar = gunun_satirlari(ham, gun)
    if not satirlar:
        gunluk.warning("%s: ham veri yok, atlandı", gun)
        return

    with tempfile.TemporaryDirectory() as gecici:
        klasor = Path(gecici)
        # Biriken otopark tablosu varsa indiriyoruz, bugünün listesiyle birleşecek.
        eski = None
        if OTOPARKLAR_YOL in tablo.listele("otoparklar/"):
            eski = klasor / "eski_otoparklar.parquet"
            eski.write_bytes(tablo.oku_bayt(OTOPARKLAR_YOL))
        ozet = tabloya_cevir(satirlar, klasor, eski)

        yol = f"doluluk/tarih={gun:%Y-%m-%d}/doluluk.parquet"
        tablo.yaz_bayt(yol, (klasor / "doluluk.parquet").read_bytes())
        tablo.yaz_bayt(OTOPARKLAR_YOL, (klasor / "otoparklar.parquet").read_bytes())

    tamlik = ozet["tur"] / 288 * 100
    gunluk.info(
        "%s: %d tur (%%%.0f), %d satır, %d canlı otopark, %d geçersiz satır (%d sıçrama) → %s",
        gun, ozet["tur"], tamlik, ozet["satir"], ozet["canli_otopark"],
        ozet["gecersiz_satir"], ozet["sicrama"], yol,
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
