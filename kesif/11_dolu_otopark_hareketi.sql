-- Dolu otoparklarda yer açılıyor mu?
--
-- Veriyi 5 dakikada bir alıyoruz ve sadece o anki boş yer sayısını görüyoruz.
-- Arada giren çıkan aracı görmüyoruz. 5 dakikada 3 araç çıkıp 3 araç girerse
-- sayı değişmiyor. Dolu bir otoparkta 2 dakikalığına açılan yeri de kaçırıyoruz.
--
-- Bu dosyada bunu dolaylı olarak ölçüyoruz: otopark doluyken bir sonraki
-- ölçümde boş yer artmış mı, ne sıklıkla artıyor. Sonuçlar
-- belgeler/karar-004-dolu-otopark-hareketi.md dosyasına yazılacak.
--
-- Dolu dediğimiz doluluğun %95 ve üstü olması, karnedeki eşikle aynı.


-- Her ölçümün yanına aynı otoparkın bir sonraki ölçümünü koyuyoruz.
-- ara sütunu iki ölçüm arasındaki süre. Tur kaçmışsa 5 dakikadan uzun olur,
-- o satırları karşılaştırmaya almıyoruz.
CREATE OR REPLACE TEMP VIEW ardisik AS
SELECT park_id, tarih, zaman_ist, kapasite, bos, doluluk,
       lead(bos) OVER w                   AS sonraki_bos,
       lead(zaman_utc) OVER w - zaman_utc AS ara
FROM doluluk
WHERE tarih >= DATE '2026-09-24' AND canli AND gecerli AND acik
WINDOW w AS (PARTITION BY park_id ORDER BY zaman_utc);


-- 1. Genel durum: kaç otopark en az bir kez doluyor, ölçümlerin ne kadarı dolu.
SELECT count(DISTINCT park_id)                                  AS canli_otopark,
       count(DISTINCT park_id) FILTER (WHERE doluluk >= 0.95)   AS en_az_bir_kez_dolan,
       count(*) FILTER (WHERE doluluk >= 0.95)                  AS dolu_olcum,
       round(100 * count(*) FILTER (WHERE doluluk >= 0.95) / count(*), 1) AS dolu_olcum_yuzde
FROM ardisik;


-- 2. Otopark otopark.
--   dolu_yuzde: otoparkın ölçümlerinin yüzde kaçı dolu
--   dolu_iken_yer_acilma: doluyken 5 dk sonra boş yer artmış mı, yüzde kaç
--   dolu_iken_degisim: doluyken 5 dk içinde boş yer ortalama kaç araç oynuyor
-- En az 50 dolu ölçümü olanlar (yaklaşık 4 saat). Daha azında oran güvenilmez.
SELECT a.park_id, o.ad, o.tip, a.kapasite,
       count(*) FILTER (WHERE doluluk >= 0.95)                              AS dolu_olcum,
       round(100 * count(*) FILTER (WHERE doluluk >= 0.95) / count(*), 1)   AS dolu_yuzde,
       round(100 * avg(CASE WHEN sonraki_bos > bos THEN 1 ELSE 0 END)
             FILTER (WHERE doluluk >= 0.95 AND ara = INTERVAL 5 MINUTE), 1) AS dolu_iken_yer_acilma,
       round(avg(abs(sonraki_bos - bos))
             FILTER (WHERE doluluk >= 0.95 AND ara = INTERVAL 5 MINUTE), 2) AS dolu_iken_degisim
FROM ardisik a JOIN otoparklar o USING (park_id)
GROUP BY ALL
HAVING count(*) FILTER (WHERE doluluk >= 0.95) >= 50
ORDER BY dolu_olcum DESC;


-- 3. Dolu ölçümler günün hangi saatlerinde.
SELECT hour(zaman_ist)                                        AS saat,
       count(*) FILTER (WHERE doluluk >= 0.95)                AS dolu_olcum,
       count(DISTINCT park_id) FILTER (WHERE doluluk >= 0.95) AS otopark
FROM ardisik
GROUP BY saat ORDER BY saat;


-- 4. Taslak gruplama. Eşikler sonucu görmeden konuldu, sonuca göre
-- karar dosyasında değişebilir.
--   sik_aciliyor: doluyken ölçümlerin %40'ından fazlasında yer açılıyor
--   ara_sira: %10 ile %40 arası
--   dolu_kaliyor: %10'dan az
WITH park AS (
    SELECT park_id,
           count(*) FILTER (WHERE doluluk >= 0.95) AS dolu_olcum,
           100 * avg(CASE WHEN sonraki_bos > bos THEN 1 ELSE 0 END)
               FILTER (WHERE doluluk >= 0.95 AND ara = INTERVAL 5 MINUTE) AS acilma
    FROM ardisik GROUP BY park_id
    HAVING count(*) FILTER (WHERE doluluk >= 0.95) >= 50
)
SELECT CASE WHEN acilma > 40 THEN 'sik_aciliyor'
            WHEN acilma >= 10 THEN 'ara_sira'
            ELSE 'dolu_kaliyor' END AS grup,
       count(*) AS otopark,
       round(avg(acilma), 1) AS ort_acilma
FROM park GROUP BY grup ORDER BY grup;



--Output:
--┌───────────────┬─────────────────────┬────────────┬──────────────────┐
--│ canli_otopark │ en_az_bir_kez_dolan │ dolu_olcum │ dolu_olcum_yuzde │
--│     int64     │        int64        │   int64    │      double      │
--├───────────────┼─────────────────────┼────────────┼──────────────────┤
--│           130 │                  80 │      65335 │             13.4 │
--└───────────────┴─────────────────────┴────────────┴──────────────────┘
--┌─────────┬─────────────────────────┬────────────────┬───┬────────────┬──────────────────────┬───────────────────┐
--│ park_id │           ad            │      tip       │ … │ dolu_yuzde │ dolu_iken_yer_acilma │ dolu_iken_degisim │
--│  int32  │         varchar         │    varchar     │ … │   double   │        double        │      double       │
--├─────────┼─────────────────────────┼────────────────┼───┼────────────┼──────────────────────┼───────────────────┤
--│    1912 │ Alibeyköy Cep Otogarı … │ AÇIK OTOPARK   │ … │      100.0 │                 39.7 │              3.73 │
--│    3036 │ Bağcılar Devlet Hastan… │ KAPALI OTOPARK │ … │       79.9 │                 21.5 │              1.07 │
--│    2822 │ Esenler Menderes Parkı… │ KAPALI OTOPARK │ … │       59.9 │                  7.0 │              0.29 │
--│    3082 │ Rumeli Hisarı Sahil Yo… │ AÇIK OTOPARK   │ … │       46.9 │                 10.5 │              0.18 │
--│    2855 │ Şemsipaşa Açık Otoparkı │ AÇIK OTOPARK   │ … │       46.8 │                  7.6 │              0.24 │
--│    3152 │ Mimar Sinan Zemin Altı… │ KAPALI OTOPARK │ … │       67.2 │                  4.9 │              0.72 │
--│    1655 │ Kadıköy Metro Açık Oto… │ AÇIK OTOPARK   │ … │       66.3 │                 14.7 │              0.34 │
--│    2237 │ Dragos Sosyal Tesisleri │ AÇIK OTOPARK   │ … │       43.0 │                  4.6 │              0.17 │
--│    2053 │ Bayrampaşa Muratpaşa Y… │ KAPALI OTOPARK │ … │       99.4 │                  5.4 │              0.16 │
--│    2468 │ Bebek Açık              │ AÇIK OTOPARK   │ … │       99.6 │                  0.1 │               0.0 │
--│    2994 │ Kirazlı Metro Durağı P… │ AÇIK OTOPARK   │ … │       60.9 │                  9.5 │              0.23 │
--│    1475 │ Fatih Katlı Otoparkı    │ KAPALI OTOPARK │ … │       51.1 │                  6.7 │               0.2 │
--│    2960 │ Büyükçekmece Metrobüs … │ KAPALI OTOPARK │ … │       50.6 │                  6.4 │              0.31 │
--│    1447 │ Kadıköy İski Açık Otop… │ AÇIK OTOPARK   │ … │       50.5 │                 13.3 │              0.41 │
--│    2439 │ Şirinevler Meydan Zemi… │ KAPALI OTOPARK │ … │       32.1 │                 19.2 │              1.13 │
--│    1525 │ Hacıosman Metro Yer Al… │ KAPALI OTOPARK │ … │       56.3 │                  2.4 │              0.33 │
--│    3011 │ Esenler Menderes Metro… │ AÇIK OTOPARK   │ … │       88.3 │                  2.9 │              0.06 │
--│    1859 │ Maçka Katlı Otoparkı    │ KAPALI OTOPARK │ … │       60.1 │                  4.8 │              0.49 │
--│    2948 │ Suadiye Sahil Açık Oto… │ AÇIK OTOPARK   │ … │       26.2 │                 14.4 │              0.59 │
--│    1298 │ Çengelköy Açık Otoparkı │ AÇIK OTOPARK   │ … │       40.8 │                  2.2 │              0.34 │
--│      ·  │       ·                 │      ·         │ … │          · │                   ·  │                ·  │
--│      ·  │       ·                 │      ·         │ … │          · │                   ·  │                ·  │
--│      ·  │       ·                 │      ·         │ … │          · │                   ·  │                ·  │
--│    1461 │ Güneş Plajı 2           │ AÇIK OTOPARK   │ … │        5.1 │                 13.6 │              0.56 │
--│    1456 │ Bostancı Sahil-Cep Açı… │ AÇIK OTOPARK   │ … │        3.8 │                  6.5 │              0.41 │
--│    1550 │ Kartal Sahil Açık Otop… │ AÇIK OTOPARK   │ … │        3.8 │                  7.2 │              0.26 │
--│    1303 │ Seyrantepe Katlı (Aren… │ KAPALI OTOPARK │ … │       12.0 │                  2.2 │             41.79 │
--│    1376 │ Mercan Açık             │ AÇIK OTOPARK   │ … │        4.0 │                 48.9 │              1.21 │
--│    1455 │ Bostancı Açık           │ AÇIK OTOPARK   │ … │        3.4 │                 36.4 │              1.38 │
--│    3303 │ Esenyurt Adile Naşit B… │ KAPALI OTOPARK │ … │        2.3 │                  0.0 │               0.0 │
--│    2920 │ Yeşilce Zemin Altı Kat… │ KAPALI OTOPARK │ … │        2.3 │                 24.8 │             11.68 │
--│    2787 │ Cevizli Açık Otoparkı   │ AÇIK OTOPARK   │ … │        6.8 │                 28.0 │              1.17 │
--│    3235 │ Haliç Sosyal Tesisleri… │ AÇIK OTOPARK   │ … │        3.1 │                  8.5 │              0.21 │
--│    2799 │ Sultanbeyli Emir Cadde… │ KAPALI OTOPARK │ … │        3.5 │                  4.5 │              0.19 │
--│    3201 │ Altınboynuz Sosyal Tes… │ AÇIK OTOPARK   │ … │       30.7 │                  1.8 │              1.21 │
--│    2898 │ Ümraniye Okan Sokak Ze… │ KAPALI OTOPARK │ … │        1.8 │                 26.5 │              5.15 │
--│    1653 │ Deniz Feneri Otoparkı   │ AÇIK OTOPARK   │ … │        2.5 │                 21.6 │              0.91 │
--│    2345 │ Üsküdar Uzunçayır PD A… │ AÇIK OTOPARK   │ … │        2.9 │                 22.6 │              0.47 │
--│    3412 │ 5. Levent Gaziosmanpaş… │ AÇIK OTOPARK   │ … │        3.6 │                 14.9 │              3.68 │
--│    2449 │ Kozyatağı Sebze-Meyve … │ AÇIK OTOPARK   │ … │       25.7 │                  1.4 │             20.53 │
--│    2905 │ Çeliktepe Açık Otoparkı │ AÇIK OTOPARK   │ … │        1.3 │                 41.1 │             10.44 │
--│    1423 │ Güneş Plajı 1           │ AÇIK OTOPARK   │ … │        1.7 │                 48.4 │              2.55 │
--│    2808 │ Kadıköy Yeni Salı Paza… │ KAPALI OTOPARK │ … │        0.9 │                 45.1 │              4.82 │
--└─────────┴─────────────────────────┴────────────────┴───┴────────────┴──────────────────────┴───────────────────┘
--  66 rows (40 shown)                     use .last to show entire result                     8 columns (6 shown)
--┌───────┬────────────┬─────────┐
--│ saat  │ dolu_olcum │ otopark │
--│ int64 │   int64    │  int64  │
--├───────┼────────────┼─────────┤
--│     0 │       1203 │      30 │
--│     1 │       1064 │      18 │
--│     2 │       1140 │      17 │
--│     3 │       1195 │      17 │
--│     4 │       1167 │      17 │
--│     5 │       1166 │      17 │
--│     6 │       1090 │      17 │
--│     7 │       1079 │      19 │
--│     8 │       2015 │      38 │
--│     9 │       2505 │      45 │
--│    10 │       3207 │      50 │
--│    11 │       3862 │      54 │
--│    12 │       4156 │      55 │
--│    13 │       4492 │      54 │
--│    14 │       4739 │      58 │
--│    15 │       4676 │      60 │
--│    16 │       4344 │      55 │
--│    17 │       3952 │      53 │
--│    18 │       3630 │      54 │
--│    19 │       3384 │      44 │
--│    20 │       3341 │      43 │
--│    21 │       3264 │      43 │
--│    22 │       2635 │      36 │
--│    23 │       2029 │      31 │
--└───────┴────────────┴─────────┘
--  24 rows            3 columns
--┌──────────────┬─────────┬────────────┐
--│     grup     │ otopark │ ort_acilma │
--│   varchar    │  int64  │   double   │
--├──────────────┼─────────┼────────────┤
--│ ara_sira     │      27 │       19.5 │
--│ dolu_kaliyor │      35 │        5.0 │
--│ sik_aciliyor │       4 │       45.9 │
--└──────────────┴─────────┴────────────┘