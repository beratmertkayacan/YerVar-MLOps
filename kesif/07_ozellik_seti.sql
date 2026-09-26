-- Özellik setine (L2) ilk bakış.
--
-- Önce seti üret:
--     DEPO_TURU=blob python -m yervar.ozellikler.olustur --baslangic 2026-09-24
-- Sonra proje kökünden:
--     duckdb
--     .read kesif/07_ozellik_seti.sql

CREATE OR REPLACE VIEW oz AS SELECT * FROM 'veri/ozellikler/ozellik_seti.parquet';

-- 1. Ne kadar veri var?
SELECT min(zaman_utc) AS ilk, max(zaman_utc) AS son,
       count(*) AS satir, count(DISTINCT park_id) AS otopark,
       count(hedef) AS hedefi_olan
FROM oz;

-- 2. Hangi sütunlar ne kadar dolu?
-- Dün ve geçen hafta sütunları veri biriktikçe dolacak. Geçen hafta için en
-- az 8 günlük veri lazım.
SELECT round(100 * count(doluluk_5dk_once) / count(*), 1) AS g5_yuzde,
       round(100 * count(doluluk_60dk_once) / count(*), 1) AS g60_yuzde,
       round(100 * count(doluluk_dun) / count(*), 1) AS dun_yuzde,
       round(100 * count(doluluk_gecen_hafta) / count(*), 1) AS gecen_hafta_yuzde,
       round(100 * count(hedef) / count(*), 1) AS hedef_yuzde
FROM oz;

-- 3. Basit tahminler ne kadar tutuyor? (L3'ün ön izlemesi)
-- Model kurmadan önce "30 dk sonra da şimdiki gibi olur" demenin hatası ne?
-- Model bunu geçemiyorsa işe yaramıyor demektir.
-- Hata = ortalama mutlak fark, doluluk puanı olarak (0-100).
SELECT round(100 * avg(abs(hedef - doluluk_simdi)), 2) AS simdiki_gibi,
       round(100 * avg(abs(hedef - ort_son_1saat)), 2) AS son_1saat_ort,
       round(100 * avg(abs(hedef - doluluk_dun)), 2)   AS dun_ayni_saat
FROM oz
WHERE hedef IS NOT NULL AND doluluk_dun IS NOT NULL;

-- 4. Hangi özellik hedefle birlikte hareket ediyor? (korelasyon, -1 ile 1 arası)
SELECT round(corr(hedef, doluluk_simdi), 3) AS simdi,
       round(corr(hedef, doluluk_60dk_once), 3) AS g60,
       round(corr(hedef, doluluk_dun), 3) AS dun,
       round(corr(hedef, degisim_30dk), 3) AS degisim,
       round(corr(hedef, saat), 3) AS saat
FROM oz WHERE hedef IS NOT NULL;

-- 5. Günün saatine göre ortalama doluluk: hafta içi ve hafta sonu.
SELECT saat,
       round(100 * avg(doluluk_simdi) FILTER (NOT hafta_sonu)) AS hafta_ici,
       round(100 * avg(doluluk_simdi) FILTER (hafta_sonu)) AS hafta_sonu
FROM oz GROUP BY saat ORDER BY saat;




--Output: 26 eylül 16.32 çalıştırması

--┌─────────────────────┬─────────────────────┬───────┬─────────┬─────────────┐
--│         ilk         │         son         │ satir │ otopark │ hedefi_olan │
--│      timestamp      │      timestamp      │ int64 │  int64  │    int64    │
--├─────────────────────┼─────────────────────┼───────┼─────────┼─────────────┤
--│ 2026-09-24 00:00:00 │ 2026-09-25 23:55:00 │ 52901 │     118 │       51438 │
--└─────────────────────┴─────────────────────┴───────┴─────────┴─────────────┘
--┌──────────┬───────────┬───────────┬───────────────────┬─────────────┐
--│ g5_yuzde │ g60_yuzde │ dun_yuzde │ gecen_hafta_yuzde │ hedef_yuzde │
--│  double  │  double   │  double   │      double       │   double    │
--├──────────┼───────────┼───────────┼───────────────────┼─────────────┤
--│     99.1 │      96.5 │      84.5 │               0.0 │        97.2 │
--└──────────┴───────────┴───────────┴───────────────────┴─────────────┘
--┌──────────────┬───────────────┬───────────────┐
--│ simdiki_gibi │ son_1saat_ort │ dun_ayni_saat │
--│    double    │    double     │    double     │
--├──────────────┼───────────────┼───────────────┤
--│         2.22 │          3.56 │          6.05 │
--└──────────────┴───────────────┴───────────────┘
--┌────────┬────────┬────────┬─────────┬────────┐
--│ simdi  │  g60   │  dun   │ degisim │  saat  │
--│ double │ double │ double │ double  │ double │
--├────────┼────────┼────────┼─────────┼────────┤
--│  0.984 │  0.941 │  0.936 │   0.095 │  0.093 │
--└────────┴────────┴────────┴─────────┴────────┘
--┌───────┬───────────┬────────────┐
--│ saat  │ hafta_ici │ hafta_sonu │
--│ int64 │  double   │   double   │
--├───────┼───────────┼────────────┤
--│     0 │      50.0 │       52.0 │
--│     1 │      45.0 │       47.0 │
--│     2 │      44.0 │       45.0 │
--│     3 │      43.0 │       NULL │
--│     4 │      42.0 │       NULL │
--│     5 │      42.0 │       NULL │
--│     6 │      41.0 │       NULL │
--│     7 │      39.0 │       NULL │
--│     8 │      40.0 │       NULL │
--│     9 │      46.0 │       NULL │
--│    10 │      52.0 │       NULL │
--│    11 │      55.0 │       NULL │
--│    12 │      57.0 │       NULL │
--│    13 │      58.0 │       NULL │
--│    14 │      58.0 │       NULL │
--│    15 │      57.0 │       NULL │
--│    16 │      55.0 │       NULL │
--│    17 │      53.0 │       NULL │
--│    18 │      51.0 │       NULL │
--│    19 │      52.0 │       NULL │
--│    20 │      52.0 │       NULL │
--│    21 │      52.0 │       NULL │
--│    22 │      52.0 │       NULL │
--│    23 │      48.0 │       NULL │
--└───────┴───────────┴────────────┘