-- Yervar L1 tablolarını DuckDB ile sorgulamak için örnekler.
--
-- Çalıştırma (proje kökünden):
--     duckdb                      -> etkileşimli kabuk açılır
--     .read kesif/05_sorgular.sql -> bu dosyadaki her şeyi çalıştırır
--
-- Veriyi nereden okuyacağını aşağıdaki iki görünümden (VIEW) biri belirliyor.
-- Görünüm, kaydedilmiş bir sorgudur: veri kopyalanmaz, her seferinde kaynaktan okunur.


--A) Yerel veri: veri/tablo/ altından oku 
CREATE OR REPLACE VIEW doluluk AS
    SELECT * FROM read_parquet('veri/tablo/doluluk/**/*.parquet', hive_partitioning = true);
CREATE OR REPLACE VIEW otoparklar AS
    SELECT * FROM 'veri/tablo/otoparklar/otoparklar.parquet';


--B) Bulut verisi: Azure'daki "tablo" kabından oku 
-- Önce terminalde `az login` yapılmış olmalı. Parola ya da anahtar yok:
-- DuckDB, az CLI oturumunu kullanıyor (CHAIN 'cli'). A'yı kullanmak için
-- aşağıdaki satırların başına -- koy, B'yi kullanmak için baştaki --'ları kaldır.
--
-- CREATE OR REPLACE SECRET yervar (
--     TYPE azure, PROVIDER credential_chain, CHAIN 'cli', ACCOUNT_NAME 'styervarbmk01'
-- );
-- CREATE OR REPLACE VIEW doluluk AS
--     SELECT * FROM read_parquet('az://tablo/doluluk/**/*.parquet', hive_partitioning = true);
-- CREATE OR REPLACE VIEW otoparklar AS
--     SELECT * FROM 'az://tablo/otoparklar/otoparklar.parquet';


-- 1. Tabloda neler var? Sütun adları ve tipleri.
DESCRIBE doluluk;

-- 2. Gün gün özet: kaç tur geldi (288 = tam gün), kaç otopark canlı?
SELECT tarih,
       count(DISTINCT zaman_utc)                    AS tur,
       round(count(DISTINCT zaman_utc) / 2.88, 1)   AS tamlik_yuzde,
       count(DISTINCT park_id) FILTER (canli)       AS canli_otopark,
       count(DISTINCT park_id) FILTER (NOT canli)   AS donuk_otopark
FROM doluluk GROUP BY tarih ORDER BY tarih;

-- 3. Tek bir otoparkın gün içi seyri (İstanbul saatiyle, saatlik ortalama).
--    Örnek olarak en büyük canlı otoparkı seçiyor. Kendi seçtiğin park_id'yi
--    yazmak için alt sorguyu bir sayıyla değiştir (ör. park_id = 3068).
SELECT hour(zaman_ist) AS saat, round(avg(doluluk) * 100) AS ort_doluluk_yuzde
FROM doluluk
WHERE park_id = (SELECT park_id FROM doluluk WHERE canli ORDER BY kapasite DESC LIMIT 1)
  AND canli AND gecerli
GROUP BY saat ORDER BY saat;

-- 4. Şu an en dolu 10 otopark (son turda, sadece canlı olanlar).
SELECT o.ad, o.ilce, d.kapasite, d.bos, round(d.doluluk * 100) AS doluluk_yuzde
FROM doluluk d JOIN otoparklar o USING (park_id)
WHERE d.zaman_utc = (SELECT max(zaman_utc) FROM doluluk) AND d.canli AND d.gecerli
ORDER BY d.doluluk DESC LIMIT 10;

-- 5. İlçe bazında ortalama doluluk.
SELECT o.ilce, count(DISTINCT park_id) AS otopark, round(avg(d.doluluk) * 100) AS ort_doluluk_yuzde
FROM doluluk d JOIN otoparklar o USING (park_id)
WHERE d.canli AND d.gecerli
GROUP BY o.ilce ORDER BY ort_doluluk_yuzde DESC;

-- 6. Bir tablonun sonucunu CSV'ye aktarmak (Excel'de açmak için):
-- COPY (SELECT * FROM otoparklar) TO 'veri/otoparklar.csv' (HEADER);
