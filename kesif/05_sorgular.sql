-- Yervar L1 tablolarını DuckDB ile sorgulamak için örnekler.
--
-- Çalıştırma (proje kökünden, iki adım):
--     duckdb
--     .read kesif/00_baglan_yerel.sql ya da 00_baglan_bulut.sql
--     .read kesif/05_sorgular.sql
-- İlk dosya veriyi nereden okuyacağını, bu dosya ne soracağını belirliyor.
-- Aynı sorgular yerel veride de bulutta da değiştirilmeden çalışır.

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
