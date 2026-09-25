-- Bağlantı: Azure'daki "tablo" kabını, dosyaları indirmeden okur.
--
-- Amaç: Bulutta üretilen L1 tablolarını kendi bilgisayarımızdan sorgulamak.
-- Bulut her gün yeni tablo yazıyor. Yerel kopya ise sadece elle ürettiğimiz
-- günleri içerir. Bulut verisini görmenin, doğrulamanın ve vaka sorgularını
-- tam günler üzerinde çalıştırmanın yolu bu dosya.
--
-- Nasıl çalışıyor:
-- 1. SECRET, DuckDB'ye Azure'a nasıl giriş yapacağını söyler. Parola ya da
--    anahtar yok: terminalde açık olan `az login` oturumu kullanılıyor
--    (CHAIN 'cli'). Oturum kapalıysa önce terminalde `az login`.
-- 2. Görünümler, yerel dosyadakilerle aynı adı taşıyor (doluluk, otoparklar).
--    Sadece adres farklı: veri/tablo/... yerine az://tablo/...
--    Bu yüzden 05 ve 06 numaralı sorgular hiç değişmeden bulutta da çalışır.
-- 3. DuckDB sadece sorgunun ihtiyaç duyduğu dosyaları ve sütunları okur.
--    Tek bir günü sormak bütün kabı indirmek demek değil.


CREATE OR REPLACE SECRET yervar (
    TYPE azure, PROVIDER credential_chain, CHAIN 'cli', ACCOUNT_NAME 'styervarbmk01'
);

CREATE OR REPLACE VIEW doluluk AS
    SELECT * FROM read_parquet('az://tablo/doluluk/**/*.parquet', hive_partitioning = true);
CREATE OR REPLACE VIEW otoparklar AS
    SELECT * FROM 'az://tablo/otoparklar/otoparklar.parquet';

-- Kontrol 1: Kapta hangi dosyalar var? Her gün için bir doluluk dosyası ve tek bir otoparklar dosyası görmeliyiz.
SELECT file FROM glob('az://tablo/**/*.parquet') ORDER BY file;

-- Kontrol 2: Her gün için tur sayısı ve tamlık. Tam bir gün 288 turdur.
-- Buluta geçişten sonraki günler %100'e yakın olmalı. Mac dönemi (22-23 Eylül) boşluklar yüzünden düşük çıkar (V-006).
SELECT tarih,
       count(DISTINCT zaman_utc)                  AS tur,
       round(count(DISTINCT zaman_utc) / 2.88, 1) AS tamlik_yuzde,
       count(DISTINCT park_id) FILTER (canli)     AS canli_otopark
FROM doluluk GROUP BY tarih ORDER BY tarih;


--Output:
--┌─────────────────────────────────────────────────────┐
--│                        file                         │
--│                       varchar                       │
--├─────────────────────────────────────────────────────┤
--│ az://tablo/doluluk/tarih=2026-09-22/doluluk.parquet │
--│ az://tablo/doluluk/tarih=2026-09-23/doluluk.parquet │
--│ az://tablo/doluluk/tarih=2026-09-24/doluluk.parquet │
--│ az://tablo/otoparklar/otoparklar.parquet            │

--┌────────────┬───────┬──────────────┬───────────────┐
--│   tarih    │  tur  │ tamlik_yuzde │ canli_otopark │
--│    date    │ int64 │    double    │     int64     │
--├────────────┼───────┼──────────────┼───────────────┤
--│ 2026-09-22 │    40 │         13.9 │           109 │
--│ 2026-09-23 │   196 │         68.1 │           114 │
--│ 2026-09-24 │   286 │         99.3 │           114 │
--└────────────┴───────┴──────────────┴───────────────┘