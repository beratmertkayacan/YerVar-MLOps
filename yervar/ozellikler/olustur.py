"""L2: L1 tablolarından modelin kullanacağı özellik setini üretir.

Her satır "şu an, şu otopark" demek. Sütunlar ikiye ayrılıyor:
  - özellikler: o an elimizde olan bilgiler (saat, gün, son değerler...)
  - hedef: TAHMIN_UFKU_DK dakika sonraki doluluk

Kural: hiçbir özellik o andan sonraki veriyi kullanamaz. Kullanırsa model
eğitimde çok iyi görünür ama canlıda o bilgi olmadığı için çöker (sızıntı).

Geçmiş değerleri satır sırasıyla değil zamanla buluyoruz: "5 dk önce" gerçekten
5 dk önceki kayıt demek. O kayıt yoksa (toplama boşluğu) değer boş kalıyor,
10 dk önceki değer onun yerine geçmiyor. V-006'daki hatayı burada tekrarlamıyoruz.

Çalıştırma:
    python -m yervar.ozellikler.olustur --baslangic 2026-09-24
    DEPO_TURU=blob python -m yervar.ozellikler.olustur --baslangic 2026-09-24
Çıktı: veri/ozellikler/ozellik_seti.parquet
"""

import argparse
from datetime import UTC, date, datetime, timedelta

import duckdb

from yervar import ayarlar
from yervar.gunluk import gunluk_al
from yervar.ozellikler.takvim import takvimi_yukle

gunluk = gunluk_al("yervar.ozellikler.olustur")

# Geçmişe en uzak bakan özellik "geçen hafta aynı saat". Başlangıçtan 7 gün
# öncesini de okumamız gerekiyor, yoksa ilk haftanın bu sütunu hep boş kalır.
GERIYE_BAKIS_GUN = 7


def tablolari_bagla(con: duckdb.DuckDBPyConnection) -> None:
    """doluluk ve otoparklar görünümlerini yerel diske ya da Azure'a bağlar.

    kesif/00_baglan_*.sql dosyalarının Python karşılığı.
    """
    if ayarlar.DEPO_TURU == "blob":
        # Yerelde az login oturumu, bulutta işin yönetilen kimliği kullanılıyor.
        con.execute(f"""
            CREATE OR REPLACE SECRET yervar (
                TYPE azure, PROVIDER credential_chain,
                CHAIN 'cli;managed_identity', ACCOUNT_NAME '{ayarlar.AZURE_DEPOLAMA_HESABI}'
            )
        """)
        kok = f"az://{ayarlar.TABLO_KAP}"
    else:
        kok = (ayarlar.VERI_KOK / ayarlar.TABLO_KAP).as_posix()

    con.execute(f"""
        CREATE OR REPLACE VIEW doluluk AS
        SELECT * FROM read_parquet('{kok}/doluluk/**/*.parquet', hive_partitioning = true)
    """)
    con.execute(f"""
        CREATE OR REPLACE VIEW otoparklar AS
        SELECT * FROM '{kok}/otoparklar/otoparklar.parquet'
    """)


def ozellik_sql(ufuk_dk: int) -> str:
    return f"""
WITH temiz AS (
    -- Sadece güvenilir satırlar: sensör canlı, değer mantıklı, otopark açık.
    -- (veri bulguları V-001, V-002, V-003)
    SELECT zaman_utc, zaman_ist, park_id, kapasite, doluluk
    FROM doluluk
    WHERE tarih BETWEEN $okuma_bas AND $okuma_bit
      AND canli AND gecerli AND acik
),
ortalamali AS (
    -- Son 1 saatin ortalaması. RANGE zamana göre pencere açıyor:
    -- arada eksik tur varsa pencere yine 1 saat, satır sayısı azalıyor sadece.
    SELECT *,
        avg(doluluk) OVER (
            PARTITION BY park_id ORDER BY zaman_utc
            RANGE BETWEEN INTERVAL 55 MINUTE PRECEDING AND CURRENT ROW
        ) AS ort_son_1saat
    FROM temiz
)
SELECT
    t.zaman_utc,
    t.park_id,

    -- takvim
    hour(t.zaman_ist)                               AS saat,
    hour(t.zaman_ist) * 60 + minute(t.zaman_ist)    AS gunun_dakikasi,
    isodow(t.zaman_ist)                             AS haftanin_gunu,   -- 1 pzt ... 7 paz
    isodow(t.zaman_ist) >= 6                        AS hafta_sonu,
    coalesce(NOT k.yarim_gun, false)                AS resmi_tatil,
    coalesce(k.yarim_gun, false)                    AS arife,

    -- otoparkın sabit bilgileri
    o.ilce,
    o.tip,
    t.kapasite,

    -- şimdiki ve geçmiş değerler
    t.doluluk                                       AS doluluk_simdi,
    g5.doluluk                                      AS doluluk_5dk_once,
    g15.doluluk                                     AS doluluk_15dk_once,
    g30.doluluk                                     AS doluluk_30dk_once,
    g60.doluluk                                     AS doluluk_60dk_once,
    t.doluluk - g30.doluluk                         AS degisim_30dk,
    t.ort_son_1saat,
    d1.doluluk                                      AS doluluk_dun,
    d7.doluluk                                      AS doluluk_gecen_hafta,

    -- hedef: {ufuk_dk} dk sonraki doluluk. Canlıda bu sütun olmayacak.
    h.doluluk                                       AS hedef
FROM ortalamali t
JOIN otoparklar o USING (park_id)
LEFT JOIN takvim k ON k.tarih = CAST(t.zaman_ist AS DATE)
LEFT JOIN temiz g5  ON g5.park_id  = t.park_id AND g5.zaman_utc  = t.zaman_utc - INTERVAL 5 MINUTE
LEFT JOIN temiz g15 ON g15.park_id = t.park_id AND g15.zaman_utc = t.zaman_utc - INTERVAL 15 MINUTE
LEFT JOIN temiz g30 ON g30.park_id = t.park_id AND g30.zaman_utc = t.zaman_utc - INTERVAL 30 MINUTE
LEFT JOIN temiz g60 ON g60.park_id = t.park_id AND g60.zaman_utc = t.zaman_utc - INTERVAL 60 MINUTE
LEFT JOIN temiz d1  ON d1.park_id  = t.park_id AND d1.zaman_utc  = t.zaman_utc - INTERVAL 1 DAY
LEFT JOIN temiz d7  ON d7.park_id  = t.park_id AND d7.zaman_utc  = t.zaman_utc - INTERVAL 7 DAY
LEFT JOIN temiz h   ON h.park_id   = t.park_id
                    AND h.zaman_utc   = t.zaman_utc + INTERVAL {ufuk_dk} MINUTE
WHERE CAST(t.zaman_utc AS DATE) BETWEEN $bas AND $bit
ORDER BY t.zaman_utc, t.park_id
"""


def ozellik_seti(con: duckdb.DuckDBPyConnection, bas: date, bit: date) -> duckdb.DuckDBPyRelation:
    """bas ile bit (dahil) arasındaki günler için özellik satırlarını döndürür.

    con içinde doluluk ve otoparklar tabloları hazır olmalı. Hedefi boş olan
    satırlar da dönüyor: eğitimde atılacaklar ama canlıda tahmin tam o satırlar
    için yapılacak.
    """
    takvimi_yukle(con, bas - timedelta(days=GERIYE_BAKIS_GUN), bit)
    parametreler = {
        "bas": bas,
        "bit": bit,
        "okuma_bas": bas - timedelta(days=GERIYE_BAKIS_GUN),
        "okuma_bit": bit + timedelta(days=1),  # gece yarısına yakın satırların hedefi ertesi günde
    }
    return con.sql(ozellik_sql(ayarlar.TAHMIN_UFKU_DK), params=parametreler)


def main() -> None:
    ap = argparse.ArgumentParser(description="L1 tablolarından özellik seti üret (L2)")
    ap.add_argument("--baslangic", type=date.fromisoformat, required=True)
    ap.add_argument("--bitis", type=date.fromisoformat, help="varsayılan: dün (UTC)")
    arg = ap.parse_args()
    bit = arg.bitis or datetime.now(UTC).date() - timedelta(days=1)

    con = duckdb.connect()
    tablolari_bagla(con)
    ozellikler = ozellik_seti(con, arg.baslangic, bit)

    hedef_klasor = ayarlar.VERI_KOK / "ozellikler"
    hedef_klasor.mkdir(parents=True, exist_ok=True)
    dosya = hedef_klasor / "ozellik_seti.parquet"
    ozellikler.write_parquet(str(dosya), compression="zstd")

    satir, park, hedefli = con.sql(f"""
        SELECT count(*), count(DISTINCT park_id), count(hedef)
        FROM '{dosya}'
    """).fetchone()
    gunluk.info(
        "%s → %s: %d satır, %d otopark, %d satırın hedefi var → %s",
        arg.baslangic, bit, satir, park, hedefli, dosya,
    )


if __name__ == "__main__":
    main()
