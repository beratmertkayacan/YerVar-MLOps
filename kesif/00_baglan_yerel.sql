-- Bağlantı: bilgisayarındaki L1 tablolarını (veri/tablo/) okur.
--
-- Veri kopyalanmıyor. "doluluk" ve "otoparklar" adında iki görünüm (VIEW) tanımlanıyor. 
--Görünüm kaydedilmiş bir sorgudur: her kullanıldığında dosyaları yeniden okur. 05 ve 06 numaralı dosyalar sadece bu iki adı kullanıyor.
--
-- Yerel tablolar ancak `python -m yervar.depolama.tablo --tarih ...` ile
-- ürettiğin günleri içerir.

CREATE OR REPLACE VIEW doluluk AS
    SELECT * FROM read_parquet('veri/tablo/doluluk/**/*.parquet', hive_partitioning = true);
CREATE OR REPLACE VIEW otoparklar AS
    SELECT * FROM 'veri/tablo/otoparklar/otoparklar.parquet';
-- Günlük özet (Adım 2): her işlenen gün için tek satır; tamlık, canlı otopark,
-- atlanan dosya, hatali sayısı, kod sürümü. Tarih klasör adından geliyor.
-- Henüz hiç özet yoksa bu satır "No files found" der; diğer görünümler etkilenmez.
CREATE OR REPLACE VIEW ozet AS
    SELECT * FROM read_parquet('veri/tablo/ozet/**/*.parquet', hive_partitioning = true);

-- Hangi günler var?
SELECT tarih, count(DISTINCT zaman_utc) AS tur, count(*) AS satir
FROM doluluk GROUP BY tarih ORDER BY tarih;


--Output:
--┌────────────┬───────┬───────┐
--│   tarih    │  tur  │ satir │
--│    date    │ int64 │ int64 │
--├────────────┼───────┼───────┤
--│ 2026-09-23 │    56 │ 13776 │
--└────────────┴───────┴───────┘