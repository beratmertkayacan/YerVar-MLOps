-- Gerçek verideki case'leri bulan sorgular.
-- Bulunan her vaka belgeler/veri-bulgulari.md dosyasına kanıtıyla yazıldı.

-- Çalıştırma (proje kökünden, iki adım):
--     duckdb
--     .read kesif/00_baglan_yerel.sql ya da 00_baglan_bulut.sql
--     .read kesif/06_vaka_sorgulari.sql
-- İlk dosya veriyi nereden okuyacağını, bu dosya ne soracağını belirliyor.
-- Aynı sorgular yerel veride de bulutta da değiştirilmeden çalışır.

-- V-001 / V-002: Donuk otoparklar, türe göre.
-- "hep_dolu": boş yer hiç değişmeden 0. Uygulamada "yer yok" diye görünür ama aslında sensör yok. "ara_sabit": 0 olmayan bir sayıda takılı kalmış.
WITH ozet AS (
    SELECT park_id, count(DISTINCT bos) AS farkli, min(bos) AS en_az
    FROM doluluk GROUP BY park_id
)
SELECT o.tip,
       count(*)                                          AS otopark,
       count(*) FILTER (farkli = 1 AND en_az = 0)        AS hep_dolu,
       count(*) FILTER (farkli = 1 AND en_az > 0)        AS ara_sabit,
       count(*) FILTER (farkli BETWEEN 2 AND 3)          AS yari_donuk,
       count(*) FILTER (farkli > 3)                      AS canli
FROM ozet JOIN otoparklar o USING (park_id)
GROUP BY o.tip ORDER BY otopark DESC;


-- V-003: Otoparklar gece kapanıyor mu? İstanbul saatine göre kapalı otopark sayısı.
SELECT hour(zaman_ist) AS ist_saat,
       count(DISTINCT park_id) FILTER (NOT acik) AS kapali_otopark
FROM doluluk GROUP BY ist_saat ORDER BY ist_saat;


-- V-004 ve V-005 için ortak adım: her satırı bir önceki turla karşılaştır.
-- Sadece art arda iki tur (arada tam 5 dk) karşılaştırılıyor. Yoksa 3 saatlik
-- bir boşluğun iki ucu "5 dakikada dev sıçrama" gibi görünür.
CREATE OR REPLACE TEMP VIEW farklar AS
SELECT park_id, zaman_utc, zaman_ist, kapasite, bos,
       bos - lag(bos) OVER w AS fark,
       zaman_utc - lag(zaman_utc) OVER w AS ara
FROM doluluk
WINDOW w AS (PARTITION BY park_id ORDER BY zaman_utc);


-- V-004: Aşırı oynak (zikzak yapan) otoparklar.
-- Her 5 dakikada yön değiştiren büyük sıçramalar gerçek araç hareketi değil;
-- iki sayaç sırayla veri gönderiyor olabilir. Yön değişimi sayısına bakıyoruz.
WITH
yonler AS (
    SELECT park_id, kapasite, fark,
           sign(fark) <> sign(lag(fark) OVER (PARTITION BY park_id ORDER BY zaman_utc))
               AS yon_degisti
    FROM farklar
    WHERE ara = INTERVAL 5 MINUTE
      -- Büyük sıçrama: kapasitenin %10'u, ama en az 10 araç. Alt sınır olmazsa
      -- 20 araçlık küçük bir otoparkta 2 aracın girip çıkması da "titreme" sayılıyor.
      AND abs(fark) >= greatest(0.1 * kapasite, 10)
)
SELECT y.park_id, o.ad, y.kapasite, count(*) AS buyuk_sicrama,
       count(*) FILTER (yon_degisti) AS yon_degisimi
FROM yonler y JOIN otoparklar o USING (park_id)
GROUP BY ALL HAVING count(*) FILTER (yon_degisti) >= 5
ORDER BY yon_degisimi DESC LIMIT 10;


-- V-005: Sayaç sıfırlanması: 5 dakikada kapasitenin %30'undan fazla sıçrama.
SELECT f.park_id, o.ad, f.zaman_ist, f.kapasite, f.bos - f.fark AS once, f.bos AS sonra
FROM farklar f JOIN otoparklar o USING (park_id)
WHERE f.ara = INTERVAL 5 MINUTE AND abs(f.fark) > 0.3 * f.kapasite
ORDER BY abs(f.fark) DESC LIMIT 10;


-- V-006: Toplama boşlukları: art arda iki tur arasında 5 dakikadan uzun ara.
WITH turlar AS (SELECT DISTINCT zaman_utc FROM doluluk),
aralar AS (
    SELECT zaman_utc, zaman_utc - lag(zaman_utc) OVER (ORDER BY zaman_utc) AS ara FROM turlar
)
SELECT zaman_utc + INTERVAL 3 HOUR AS ist_zaman, ara
FROM aralar WHERE ara > INTERVAL 5 MINUTE ORDER BY ara DESC;


-- Kontrol: kural dışı değerler (boş < 0, boş > kapasite, kapasite 0). Sıfır çıkması beklenir.
SELECT count(*) FILTER (NOT gecerli) AS gecersiz_satir,
       count(*) FILTER (kapasite = 0) AS kapasitesi_sifir
FROM doluluk;
