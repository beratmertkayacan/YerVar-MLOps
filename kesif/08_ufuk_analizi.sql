-- Tahmin ufku analizi: kaç dakika sonrasını tahmin etmek anlamlı?
--
-- Model kurmadan, sadece iki basit tahminle bakıyoruz:
--   simdiki_gibi : "X dk sonra da şimdiki gibi olur"
--   dun_ayni_saat : "X dk sonra dün o saatte ne idiyse o olur"
-- Hata ortalama mutlak fark, doluluk puanı cinsinden (0-100).
-- Bir modelin değeri, bu iki basit tahminin zorlandığı yerde ortaya çıkar.
--
-- Çalıştırma (proje kökünden):
--     duckdb
--     .read kesif/00_baglan_bulut.sql
--     .read kesif/08_ufuk_analizi.sql

CREATE OR REPLACE TEMP VIEW temiz AS
SELECT zaman_utc, zaman_ist, park_id, doluluk FROM doluluk
WHERE canli AND gecerli AND acik AND tarih >= DATE '2026-09-24'; -- referans başlangıç günü

CREATE OR REPLACE TEMP VIEW ufuk_ciftleri AS
SELECT u.dk, t.park_id, t.zaman_ist,
       t.doluluk  AS simdi,
       g.doluluk  AS sonra,
       d.doluluk  AS dun_o_saat
FROM temiz t
CROSS JOIN (SELECT unnest([15, 30, 60, 120, 180, 240]) AS dk) u
JOIN temiz g ON g.park_id = t.park_id AND g.zaman_utc = t.zaman_utc + to_minutes(u.dk)
LEFT JOIN temiz d ON d.park_id = t.park_id AND d.zaman_utc = g.zaman_utc - INTERVAL 1 DAY;


-- 1. Ufuk uzadıkça basit tahminler ne kadar bozuluyor?
-- Karşılaştırma adil olsun diye iki tahmin de aynı satırlarda ölçülüyor.
SELECT dk,
       count(*) AS satir,
       round(100 * avg(abs(sonra - simdi)), 2) AS simdiki_gibi,
       round(100 * avg(abs(sonra - dun_o_saat)), 2) AS dun_ayni_saat
FROM ufuk_ciftleri
WHERE dun_o_saat IS NOT NULL
GROUP BY dk ORDER BY dk;


-- 2. Ne sıklıkla ciddi değişim oluyor? (10 puandan fazla)
-- Ortalama hata küçük olabilir ama önemli olan bu anlar.
SELECT dk,
       round(100 * avg((abs(sonra - simdi) > 0.10)::INT), 1) AS buyuk_degisim_yuzde
FROM ufuk_ciftleri
GROUP BY dk ORDER BY dk;


-- 3. Günün hangi saatinde tahmin zor? (60 dk ufuk, İstanbul saati)
SELECT hour(zaman_ist) AS saat,
       round(100 * avg(abs(sonra - simdi)), 2) AS simdiki_gibi_hata,
       round(100 * avg((abs(sonra - simdi) > 0.10)::INT), 1) AS buyuk_degisim_yuzde
FROM ufuk_ciftleri
WHERE dk = 60
GROUP BY saat ORDER BY saat;


-- 4. Kullanıcı için kritik an: otopark neredeyse doluyken (%85 ve üstü).
-- "Yer bulacak mıyım?" sorusu en çok burada önem taşıyor.
SELECT dk,
       count(*) AS satir,
       round(100 * avg(abs(sonra - simdi)), 2) AS simdiki_gibi,
       round(100 * avg((sonra >= 0.98)::INT), 1) AS tamamen_dolma_yuzde
FROM ufuk_ciftleri
WHERE simdi >= 0.85
GROUP BY dk ORDER BY dk;





-- Output: 
-- Outputa göre tahmin ufku kararı için analizler: 
--Zor saatler 07-10 ve 22-00. Sabah 8'de 60 dakika içinde büyük değişim olasılığı %27. Gece 03'te %1.
--%85 dolu otoparkların yaklaşık yarısı 15-60 dakika içinde tamamen doluyor. Kullanıcı için en önemli bölge burası.
--İki basit tahmin 60 ile 120 dakika arasında yer değiştiriyor. Kısa ufukta "şimdiki durum" kazanıyor, uzun ufukta "dün bu saat" kazanıyor.
-- Bir model ikisini birlikte kullanabildiği için en çok 60-180 dakika arasında fark yaratmalı.




--┌───────┬───────┬──────────────┬───────────────┐
--│  dk   │ satir │ simdiki_gibi │ dun_ayni_saat │
--│ int32 │ int64 │    double    │    double     │
--├───────┼───────┼──────────────┼───────────────┤
--│    15 │ 25279 │         1.33 │          5.31 │
--│    30 │ 25090 │         2.21 │          5.32 │
--│    60 │ 24810 │          3.8 │          5.35 │
--│   120 │ 24054 │         6.58 │          5.38 │
--│   180 │ 23300 │         8.89 │          5.36 │
--│   240 │ 22544 │        10.82 │          5.31 │
--└───────┴───────┴──────────────┴───────────────┘
--┌───────┬─────────────────────┐
--│  dk   │ buyuk_degisim_yuzde │
--│ int32 │       double        │
--├───────┼─────────────────────┤
--│    15 │                 1.1 │
--│    30 │                 3.8 │
--│    60 │                10.2 │
--│   120 │                19.9 │
--│   180 │                27.6 │
--│   240 │                33.9 │
--└───────┴─────────────────────┘
--┌───────┬───────────────────┬─────────────────────┐
--│ saat  │ simdiki_gibi_hata │ buyuk_degisim_yuzde │
--│ int64 │      double       │       double        │
--├───────┼───────────────────┼─────────────────────┤
--│     0 │              6.57 │                14.6 │
--│     1 │              1.74 │                 4.0 │
--│     2 │               0.8 │                 1.7 │
--│     3 │              0.51 │                 0.8 │
--│     4 │              0.42 │                 1.0 │
--│     5 │              0.66 │                 0.6 │
--│     6 │               2.8 │                 6.4 │
--│     7 │               5.1 │                13.3 │
--│     8 │              7.43 │                27.1 │
--│     9 │              6.69 │                24.2 │
--│    10 │              4.41 │                12.4 │
--│    11 │              3.59 │                 9.4 │
--│    12 │              2.97 │                 6.4 │
--│    13 │              2.22 │                 3.3 │
--│    14 │              2.39 │                 4.3 │
--│    15 │               3.1 │                 7.4 │
--│    16 │              3.67 │                 9.3 │
--│    17 │              4.07 │                10.7 │
--│    18 │              4.06 │                 9.7 │
--│    19 │              3.43 │                 9.2 │
--│    20 │               2.9 │                 5.5 │
--│    21 │               3.3 │                 8.4 │
--│    22 │               5.2 │                16.4 │
--│    23 │              9.34 │                19.6 │
--└───────┴───────────────────┴─────────────────────┘
--  24 rows                               3 columns
--┌───────┬───────┬──────────────┬─────────────────────┐
--│  dk   │ satir │ simdiki_gibi │ tamamen_dolma_yuzde │
--│ int32 │ int64 │    double    │       double        │
--├───────┼───────┼──────────────┼─────────────────────┤
--│    15 │  9531 │         1.27 │                48.4 │
--│    30 │  9471 │         1.83 │                48.1 │
--│    60 │  9356 │         2.96 │                47.0 │
--│   120 │  9029 │         5.38 │                44.4 │
--│   180 │  8619 │         7.62 │                42.2 │
--│   240 │  8208 │         9.93 │                39.7 │
--└───────┴───────┴──────────────┴─────────────────────┘