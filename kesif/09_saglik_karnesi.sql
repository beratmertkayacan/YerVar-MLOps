-- Otopark sağlık karnesi ve SQL dersleri.
--
-- Bu dosya iki işi birden yapıyor:
--   1. Her otoparkın ne kadar güvenilir veri verdiğini ölçüyor (karne).
--   2. SQL'i adım adım öğretiyor: her "Ders" bir önceki derse bir şey ekliyor.
--
-- Çalıştırma (proje kökünden):
--     duckdb
--     .read kesif/00_baglan_bulut.sql
--     .read kesif/09_saglik_karnesi.sql
--
-- Öğrenmek için daha iyisi: dosyayı açıp sorguları tek tek kopyalayıp
-- DuckDB kabuğuna yapıştırmak. Her dersin sonunda "Kendin dene" var.
--
-- Referans gün: sadece 24 Eylül ve sonrasına bakıyoruz (öncesi Mac dönemi).


-- ═══════════════════════════════════════════════════════════════════════════
-- Ders 1: Satırlara bakmak (SELECT, WHERE, ORDER BY, LIMIT)
-- ═══════════════════════════════════════════════════════════════════════════
-- SELECT  hangi sütunlar
-- FROM    hangi tablo
-- WHERE   hangi satırlar (filtre)
-- ORDER BY sıralama, DESC büyükten küçüğe
-- LIMIT   ilk kaç satır
--
-- Bir otoparkın son 12 turu (1 saat):
SELECT zaman_ist, kapasite, bos, doluluk, canli, acik
FROM doluluk
WHERE park_id = 2175
ORDER BY zaman_utc DESC
LIMIT 12;

-- Kendin dene: park_id'yi değiştir. Bir otoparkın adını bulmak için:
--   SELECT park_id, ad, ilce FROM otoparklar WHERE ad ILIKE '%kadıköy%';


-- ═══════════════════════════════════════════════════════════════════════════
-- Ders 2: Özetlemek (GROUP BY, count, avg, min, max)
-- ═══════════════════════════════════════════════════════════════════════════
-- GROUP BY satırları gruplara ayırır, her gruptan tek satır çıkar.
-- count(*) satır sayısı, count(DISTINCT x) farklı x sayısı.
--
-- Gün gün: kaç otopark, kaç tur, ortalama doluluk?
SELECT tarih,
       count(DISTINCT park_id)          AS otopark,
       count(DISTINCT zaman_utc)        AS tur,
       round(avg(doluluk) * 100, 1)     AS ort_doluluk_yuzde
FROM doluluk
WHERE tarih >= DATE '2026-09-24'
GROUP BY tarih
ORDER BY tarih;

-- Kendin dene: GROUP BY'ı hour(zaman_ist) yap, günün saatine göre özet çıkar.


-- ═══════════════════════════════════════════════════════════════════════════
-- Ders 3: Koşullu saymak (FILTER, CASE)
-- ═══════════════════════════════════════════════════════════════════════════
-- count(*) FILTER (WHERE koşul) sadece koşulu tutan satırları sayar.
-- Aynı işi CASE ile de yapabilirsin: sum(CASE WHEN koşul THEN 1 ELSE 0 END)
--
-- Model hangi satırlarla eğitildi? Eğitime sadece canlı + geçerli + açık
-- satırlar giriyor (yervar/ozellikler/olustur.py, "temiz" adımı).
-- Kalanlar neden dışarıda?
SELECT count(*)                                              AS toplam,
       count(*) FILTER (WHERE canli AND gecerli AND acik)    AS egitime_giren,
       count(*) FILTER (WHERE NOT canli)                     AS donuk_sensor,
       count(*) FILTER (WHERE canli AND NOT acik)            AS kapali_saat,
       count(*) FILTER (WHERE canli AND acik AND NOT gecerli) AS gecersiz_deger,
       round(100 * count(*) FILTER (WHERE canli AND gecerli AND acik) / count(*), 1)
                                                             AS giren_yuzde
FROM doluluk
WHERE tarih >= DATE '2026-09-24';

-- Kendin dene: sonuna GROUP BY tarih ekle (ve SELECT'e tarih), gün gün gör.


-- ═══════════════════════════════════════════════════════════════════════════
-- Ders 4: Önceki satıra bakmak (pencere fonksiyonları: LAG, LEAD)
-- ═══════════════════════════════════════════════════════════════════════════
-- GROUP BY satırları birleştirir. Pencere fonksiyonu ise her satırı korur,
-- yanına komşu satırlardan bilgi ekler.
--   lag(bos)  OVER (PARTITION BY park_id ORDER BY zaman_utc)  → bir önceki tur
--   lead(bos) OVER (...)                                       → bir sonraki tur
-- PARTITION BY: her otopark kendi içinde sıralanır, otoparklar karışmaz.
--
-- Yenikapı'da gece yarısı: önceki, şimdiki, sonraki tur yan yana.
SELECT zaman_ist,
       lag(bos)  OVER w AS onceki,
       bos,
       lead(bos) OVER w AS sonraki
FROM doluluk
WHERE park_id = 2175 AND tarih >= DATE '2026-09-28'
WINDOW w AS (PARTITION BY park_id ORDER BY zaman_utc)
QUALIFY hour(zaman_ist) = 0 AND minute(zaman_ist) <= 10
ORDER BY zaman_ist;

-- QUALIFY: pencere fonksiyonu hesaplandıktan SONRA filtreler. WHERE ile
-- yapsaydık önce satırlar atılır, lag() yanlış komşuya bakardı.
-- Kendin dene: QUALIFY satırını silip farkı gör.


-- ═══════════════════════════════════════════════════════════════════════════
-- Ders 5: Adım adım düşünmek (WITH, yani CTE)
-- ═══════════════════════════════════════════════════════════════════════════
-- Uzun sorguyu parçalara bölmek için: WITH ad AS (sorgu), ad2 AS (...) SELECT ...
-- Her parça bir öncekini tablo gibi kullanabilir. Okuması ve hata ayıklaması kolay.
--
-- Karne: her otopark için tek satır. Bu sorgu bir görünüm (VIEW) olarak
-- kaydediliyor, sonraki derslerde tekrar kullanacağız.
CREATE OR REPLACE TEMP VIEW karne AS
WITH
son_gun AS (
    -- Tablodaki en son gün. Bu günde görünmeyen otopark listeden çıkmış.
    SELECT max(tarih) AS gun FROM doluluk
),
komsulu AS (
    -- Her tura önceki ve sonraki turu ekle (Ders 4)
    SELECT park_id, tarih, zaman_ist, zaman_utc, kapasite, bos, canli,
           lag(bos)  OVER w AS onceki,
           lead(bos) OVER w AS sonraki,
           zaman_utc - lag(zaman_utc) OVER w AS ara
    FROM doluluk
    WHERE tarih >= DATE '2026-09-24'
    WINDOW w AS (PARTITION BY park_id ORDER BY zaman_utc)
),
isaretli AS (
    -- Her tur için iki soru:
    --   tek_tur_sicrama: önceki ve sonraki birbirine yakın, bu tur ikisinden de çok farklı
    --   buyuk_sicrama:   5 dakikada kapasitenin %10'u ve en az 10 araç değişim
    SELECT *,
        abs(onceki - sonraki) <= 0.05 * kapasite
            AND abs(bos - onceki) >= greatest(0.3 * kapasite, 10)   AS tek_tur_sicrama,
        ara = INTERVAL 5 MINUTE
            AND abs(bos - onceki) >= greatest(0.1 * kapasite, 10)   AS buyuk_sicrama
    FROM komsulu
),
yonler AS (
    -- Büyük sıçramalar arasında yön değişimi: bir artıyor, sonra azalıyor...
    -- Gerçek otopark böyle zikzak yapmaz, iki sayaç çakışması gibi duruyor (V-004).
    SELECT park_id,
           sign(bos - onceki) <> lag(sign(bos - onceki))
               OVER (PARTITION BY park_id ORDER BY zaman_utc) AS yon_degisti
    FROM isaretli
    WHERE buyuk_sicrama
),
yon_ozeti AS (
    SELECT park_id, count(*) FILTER (WHERE yon_degisti) AS yon_degisimi
    FROM yonler GROUP BY park_id
),
park_ozeti AS (
    -- Her otopark için tek satır (Ders 2 ve 3)
    SELECT park_id,
           count(DISTINCT tarih)                                        AS gun,
           count(DISTINCT tarih) FILTER (WHERE canli)                   AS canli_gun,
           max(tarih)                                                   AS son_tarih,
           count(*) FILTER (WHERE tek_tur_sicrama AND hour(zaman_ist) = 0) AS gece_yarisi_sicrama,
           count(*) FILTER (WHERE tek_tur_sicrama AND hour(zaman_ist) > 0) AS diger_sicrama,
           round(count(*) FILTER (WHERE buyuk_sicrama)
                 / count(DISTINCT tarih), 1)                           AS gunluk_buyuk_sicrama
    FROM isaretli
    GROUP BY park_id
)
SELECT p.*,
       round(coalesce(y.yon_degisimi, 0) / p.gun, 1) AS gunluk_yon_degisimi,
       o.ad, o.ilce, o.tip,
       -- Ders 6: sınıflandırma. CASE ilk tutan koşulda durur, sıra önemli.
       CASE
           WHEN p.son_tarih < (SELECT gun FROM son_gun)  THEN '5_listeden_cikti'
           WHEN p.canli_gun = 0                          THEN '4_donuk'
           WHEN p.canli_gun < p.gun                      THEN '3_kismen_canli'
           -- Eşikler ilk tahmin: günde 2'den fazla zikzak ya da gece yarısı
           -- dışında tek tur sıçraması. Veriye bakıp ayarlanabilir.
           WHEN p.diger_sicrama > 0
             OR coalesce(y.yon_degisimi, 0) / p.gun > 2  THEN '2_canli_ama_gurultulu'
           ELSE                                               '1_saglikli'
       END AS saglik
FROM park_ozeti p
LEFT JOIN yon_ozeti y USING (park_id)
LEFT JOIN otoparklar o USING (park_id);

-- LEFT JOIN: karnedeki her otopark kalır, otoparklar tablosunda karşılığı
-- yoksa ad/ilçe boş gelir. Düz JOIN olsaydı listeden çıkan otoparklar
-- sessizce kaybolurdu (V-012'de tam bunu yaşadık: 246 yerine 243 saydık).


-- ═══════════════════════════════════════════════════════════════════════════
-- Ders 6: Karnenin özeti
-- ═══════════════════════════════════════════════════════════════════════════
-- Kaç otopark hangi sınıfta? Türe göre?
SELECT saglik,
       count(*)                                        AS otopark,
       count(*) FILTER (WHERE tip = 'AÇIK OTOPARK')    AS acik,
       count(*) FILTER (WHERE tip = 'KAPALI OTOPARK')  AS kapali,
       count(*) FILTER (WHERE tip = 'YOL ÜSTÜ')        AS yol_ustu
FROM karne
GROUP BY saglik
ORDER BY saglik;

-- Gece yarısı sıçraması yaşayan otopark sayısı (V-013):
SELECT count(*) FILTER (WHERE gece_yarisi_sicrama > 0) AS gece_yarisi_sicramali,
       count(*) FILTER (WHERE canli_gun > 0)           AS canli_olan
FROM karne;

-- Gürültülü ve kısmen canlı otoparklar, en kötüden başlayarak:
SELECT park_id, ad, ilce, tip, gun, canli_gun,
       diger_sicrama, gunluk_yon_degisimi, saglik
FROM karne
WHERE saglik IN ('2_canli_ama_gurultulu', '3_kismen_canli')
ORDER BY gunluk_yon_degisimi DESC
LIMIT 15;

-- Karneyi CSV olarak kaydet (Excel'de ya da ileride Power BI'da açmak için):
COPY (SELECT * FROM karne ORDER BY saglik, park_id) TO 'veri/otopark_karnesi.csv' (HEADER);


-- ═══════════════════════════════════════════════════════════════════════════
-- Ders 7: Birleştirip desen aramak (JOIN + GROUP BY)
-- ═══════════════════════════════════════════════════════════════════════════
-- Sadece sağlıklı otoparklarda, günün saatine göre ortalama doluluk.
-- Hafta içi ve hafta sonu yan yana. isodow: 1 Pazartesi ... 7 Pazar.
SELECT hour(d.zaman_ist)                                                     AS saat,
       round(100 * avg(d.doluluk) FILTER (WHERE isodow(d.zaman_ist) <= 5))    AS hafta_ici,
       round(100 * avg(d.doluluk) FILTER (WHERE isodow(d.zaman_ist) >= 6))    AS hafta_sonu
FROM doluluk d
JOIN karne k USING (park_id)
WHERE k.saglik = '1_saglikli' AND d.tarih >= DATE '2026-09-24' AND d.acik AND d.gecerli
GROUP BY saat
ORDER BY saat;


-- ═══════════════════════════════════════════════════════════════════════════
-- Ders 8: Her grubun en iyisini seçmek (QUALIFY + row_number)
-- ═══════════════════════════════════════════════════════════════════════════
-- Her ilçenin en dolu sağlıklı otoparkı (hafta içi 08-18 ortalaması):
WITH ort AS (
    SELECT k.ilce, k.ad, round(100 * avg(d.doluluk)) AS ort_doluluk
    FROM doluluk d JOIN karne k USING (park_id)
    WHERE k.saglik = '1_saglikli' AND d.acik AND d.gecerli
      AND isodow(d.zaman_ist) <= 5 AND hour(d.zaman_ist) BETWEEN 8 AND 18
      AND d.tarih >= DATE '2026-09-24'
    GROUP BY k.ilce, k.ad
)
SELECT * FROM ort
QUALIFY row_number() OVER (PARTITION BY ilce ORDER BY ort_doluluk DESC) = 1
ORDER BY ort_doluluk DESC
LIMIT 15;

-- Kendin dene: "= 1" yerine "<= 3" yaz, her ilçenin ilk 3'ünü gör.
