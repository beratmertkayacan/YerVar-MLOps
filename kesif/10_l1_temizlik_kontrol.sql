-- L1 temizliği (0.5) sonrası kontrol: V-013 ve V-012 gerçekten düzeldi mi?
--
-- Bütün günler yeniden işlendikten SONRA çalıştır:
--     duckdb
--     .read kesif/00_baglan_bulut.sql
--     .read kesif/10_l1_temizlik_kontrol.sql
--
-- Her sorgunun altında ne görmeyi beklediğimiz yazıyor. Beklenenden farklı
-- bir şey çıkarsa çıktıyı olduğu gibi gönder.


-- Kontrol 1: Yeni sütun her günde var mı?
-- Eski (0.4) tabloda sicrama sütunu yoktu. Bir gün yeniden işlenmemişse
-- burada o gün 0 satırla ya da hata ile görünür.
-- Beklenen: 22 Eylül'den düne kadar her gün, sicrama sütunu dolu.
SELECT tarih,
       count(*)                       AS satir,
       count(*) FILTER (sicrama)      AS sicrama,
       count(*) FILTER (NOT gecerli)  AS gecersiz
FROM doluluk GROUP BY tarih ORDER BY tarih;


-- Kontrol 2: Sıçramalar hangi saatte? (V-013)
-- Beklenen: neredeyse hepsi İstanbul 00:00'da, diğer saatler tek haneli.
-- 9 Ekim analizinde 133 canlı otoparkın 106'sı her gece sıçrıyordu.
SELECT hour(zaman_ist)              AS ist_saat,
       count(*)                     AS sicrama,
       count(DISTINCT park_id)      AS otopark,
       count(DISTINCT tarih)        AS gun
FROM doluluk
WHERE sicrama AND tarih >= DATE '2026-09-24'
GROUP BY ist_saat ORDER BY sicrama DESC LIMIT 5;


-- Kontrol 3: Yenikapı gece yarısı, önce ve sonra yan yana.
-- Beklenen: 00:00 satırında bos çok küçük, sicrama = true, gecerli = false.
-- Komşu satırlar (23:55, 00:05) normal ve gecerli = true.
SELECT zaman_ist, bos, sicrama, gecerli
FROM doluluk
WHERE park_id = (SELECT park_id FROM otoparklar WHERE ad ILIKE '%yenikapı spor%' LIMIT 1)
  AND zaman_ist BETWEEN TIMESTAMP '2026-10-09 23:50' AND TIMESTAMP '2026-10-10 00:10'
ORDER BY zaman_ist;


-- Kontrol 4: Sıçramayı saymayınca canlı otopark sayısı değişti mi?
-- Önceden gece yarısı hatası, 3 değerde takılı bir otoparka 4. değer
-- ekleyip onu "canlı" gösterebiliyordu. Beklenen: günlük sayı biraz düşük
-- ya da aynı (önceki analizde günde 110-116 arası).
SELECT tarih, count(DISTINCT park_id) FILTER (canli) AS canli_otopark
FROM doluluk WHERE tarih >= DATE '2026-09-24'
GROUP BY tarih ORDER BY tarih;


-- Kontrol 5: Otopark tablosu birikiyor mu? (V-012)
-- Beklenen: toplam 254 civarı (eskiden sadece son günün 243-247'si vardı),
-- ilk_gorulme sütunu dolu.
SELECT count(*)                  AS otopark,
       min(ilk_gorulme)          AS en_eski,
       max(son_gorulme)          AS en_yeni
FROM otoparklar;


-- Kontrol 6: Listeden çıkan otoparklar.
-- Son görülmesi en yeni günden 1 günden eski olanlar. Beklenen: 8 civarı,
-- aralarında 1508 (Yeşilköy Halk Pazarı, V-004) ve 904, 2719, 2271, 119, 2243.
SELECT park_id, ad, ilce, tip,
       CAST(ilk_gorulme AS DATE) AS ilk,
       CAST(son_gorulme AS DATE) AS son
FROM otoparklar
WHERE son_gorulme < (SELECT max(son_gorulme) FROM otoparklar) - INTERVAL 1 DAY
ORDER BY son_gorulme;


-- Kontrol 7: Sonradan eklenen otoparklar.
-- İlk görülmesi 24 Eylül'den sonra olanlar. Bunların geçmiş verisi kısa;
-- model için "yeni otopark" sorunu (soğuk başlangıç) burada başlıyor.
SELECT park_id, ad, ilce, tip, CAST(ilk_gorulme AS DATE) AS ilk
FROM otoparklar
WHERE ilk_gorulme >= TIMESTAMP '2026-09-25'
ORDER BY ilk_gorulme;
