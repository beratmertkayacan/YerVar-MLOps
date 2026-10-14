"""L1 — Bir günün ham turlarını temiz, sorgulanabilir iki tabloya çevirir.

Ham katmanda her 5 dakika ayrı bir JSON dosyası (günde 288 dosya). Model eğitmek,
grafik çizmek ya da Power BI'da rapor açmak için bunların tek tabloya dönüşmesi
gerekiyor. Bu modül bir günü okur, temizler ve iki Parquet dosyası yazar:

    tablo/doluluk/tarih=2026-09-24/doluluk.parquet   ← her 5 dk × her otopark
    tablo/otoparklar/otoparklar.parquet              ← şimdiye kadar görülen her otopark

İki tabloya ayırmak "yıldız şeması" (star schema) denen düzen: değişen ölçümler
(doluluk) bir tabloda, değişmeyen nitelikler (ad, ilçe, konum) ayrı tabloda.
Otopark adı 70.000 satırda tekrar etmez; Power BI da bu düzeni doğrudan anlar.

"tarih=2026-09-24" klasör adı "hive bölümlemesi": DuckDB ve Power BI klasör
adından tarih sütununu kendiliğinden çıkarır ve sadece istenen günleri okur.

Her işlenen gün için bir de özet yazılıyor: tablo/ozet/tarih=.../ozet.parquet.
Özet en son yazılıyor ve "gün tamam" işareti oluyor: doluluk ve özet ikisi de
varsa gün tamamdır.

Çalıştırma:
    python -m yervar.depolama.tablo                           # gece işi (aşağıda)
    python -m yervar.depolama.tablo --tarih 2026-09-24        # belirli bir gün
    python -m yervar.depolama.tablo --baslangic 2026-09-22    # o günden düne kadar

Gece işi (argümansız): dün ve son TAMAMLAMA_GUN içinde ham verisi olup tamam
olmayan günler. En fazla EN_FAZLA_GUN gün ve TABLO_SURE_BUTCESI_SN saniye;
kalanlar sonraki geceye kalır. Bugün bitmediği için hiçbir modda işlenmez,
--tarih bugünü gösterirse iş durur (sadece --bugunu-de-isle ile izin var).

Log kelimeleri (alarm ve sorgular bunları arar):
    GUN_TAMAM      gün yazıldı; satırda özetin bütün alanları var
    GUN_EKSIK      tamlık GUN_EKSIK_ESIGI'nin altında (uyarı, iş başarısız olmaz)
    GUN_HATALI     gün yazılamadı (sebep=...); diğer günlere devam, çıkış kodu 1
    GUN_VERI_YOK   o gün için hiç ham tur yok
    GUN_ERTELENDI  sınıra takılan günler, sonraki geceye kaldı
    GECE_BITTI     gece işi bitti; yapacak iş olmasa bile her gece bir kez

Aynı günü tekrar işlemek güvenli: dosyanın üzerine yazılır (idempotent).
"""

import argparse
import gzip
import json
import re
import tempfile
import time
import zlib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from yervar import ayarlar
from yervar.depolama.ham import BlobDepo, CakismaHatasi, YerelDepo, depo_olustur
from yervar.gunluk import gunluk_al

gunluk = gunluk_al("yervar.depolama.tablo")

DAMGA = re.compile(r"_(\d{8}T\d{6}Z)\.json\.gz$")

# Bir otoparkın gün içinde en az bu kadar farklı değer göstermesi gerekiyor ki
# "canlı" sayılsın. Veri denetiminde donuk otoparklar tek bir değerde, yarı donuk
# olanlar 2-3 değerde takılı kalıyordu; 3'ün üstü gerçek bir sensör demek.
CANLI_ESIK = 3

# Tek tur sıçraması (V-013): önceki ve sonraki tur birbirine yakınken arada tek
# bir tur ikisinden de çok uzaksa bu araç hareketi değil, veri hatası. Neredeyse
# hepsi gece 00:00'da (İstanbul) oluyor. Eşikler kesif/06'daki sorguyla aynı:
# komşular kapasitenin %5'i içinde, sıçrama kapasitenin %30'u (en az 10 araç).
SICRAMA_KOMSU_ORAN = 0.05
SICRAMA_ORAN = 0.3
SICRAMA_EN_AZ = 10

OTOPARKLAR_YOL = "otoparklar/otoparklar.parquet"
TARIH = re.compile(r"tarih=(\d{4}-\d{2}-\d{2})/")

# Gün 00:00-24:00 UTC, 5 dakikada bir tur: tam bir günde 288 tur.
GUNDE_TUR = 288
# otoparklar.parquet başka bir çalıştırmayla çakışırsa en fazla bu kadar deneme.
OTOPARKLAR_DENEME = 3
# Atlanan dosyalardan loga en fazla bu kadar ad yazılıyor.
ORNEK_SAYISI = 5

# Testler saati ve günü değiştirebilsin diye ayrı adlarda duruyorlar.
saat = time.monotonic


def bugun_utc() -> date:
    return datetime.now(UTC).date()


class GunHatasi(RuntimeError):
    """Gün yazılmadı. sebep loga sabit bir kelime olarak geçiyor."""

    def __init__(self, sebep: str, ayrinti: str = "") -> None:
        super().__init__(f"{sebep} {ayrinti}".strip())
        self.sebep = sebep
        self.ayrinti = ayrinti


@dataclass
class Okuma:
    """Bir günün okunan satırları ve okurken atlananlar."""

    satirlar: list[dict] = field(default_factory=list)
    dosya: int = 0
    atlanan_dosya: int = 0
    atlanan_kayit: int = 0
    bos_birakilan_deger: int = 0
    sebepler: dict[str, int] = field(default_factory=dict)
    ornekler: list[str] = field(default_factory=list)

    def atla(self, ad: str, sebep: str) -> None:
        self.atlanan_dosya += 1
        self.sebepler[sebep] = self.sebepler.get(sebep, 0) + 1
        if len(self.ornekler) < ORNEK_SAYISI:
            self.ornekler.append(ad)


def _tam_sayi(deger: Any) -> int | None:
    # bool, Python'da int'in alt türü; True'yu 1 diye almak istemiyoruz.
    return deger if isinstance(deger, int) and not isinstance(deger, bool) else None


def _metin(deger: Any) -> str | None:
    return deger if isinstance(deger, str) else None


def _ondalik(deger: Any) -> float | None:
    # API konumu metin olarak veriyor ("41.0246"); sayıya çeviriyoruz.
    try:
        return float(deger) if deger else None
    except (TypeError, ValueError):
        return None


def kayit_satiri(p: Any, zaman: str) -> tuple[dict | None, int]:
    """Tek bir API kaydını tablo satırına çevirir: (satır, boş bırakılan değer sayısı).

    parkID satırın anahtarı; onsuz satır hiçbir otoparka bağlanamıyor, atlanıyor
    (satır None). Diğer alanlar beklenmeyen tipteyse boş bırakılıyor: DuckDB tek
    bir tip uyuşmazlığında bütün günü reddederdi. Kaç değerin böyle boşaltıldığı
    sayılıyor, çünkü gecersiz_satir bunu göstermiyor: boş kapasite ya da boş yer
    "geçersiz" değil "bilinmiyor" sayılıyor, ad ve konum ise hiç bakılmıyor.
    Zaten gelmeyen (None ya da "") değer sayılmıyor, sadece bozuk gelen.
    """
    if not isinstance(p, dict) or _tam_sayi(p.get("parkID")) is None:
        return None, 0
    satir = {
        "zaman": zaman,
        "park_id": p["parkID"],
        "ad": _metin(p.get("parkName")),
        "ilce": _metin(p.get("district")),
        "tip": _metin(p.get("parkType")),
        "lat": _ondalik(p.get("lat")),
        "lng": _ondalik(p.get("lng")),
        "kapasite": _tam_sayi(p.get("capacity")),
        "bos": _tam_sayi(p.get("emptyCapacity")),
        "acik": _tam_sayi(p.get("isOpen")),
    }
    kaynak = {"ad": "parkName", "ilce": "district", "tip": "parkType", "lat": "lat",
              "lng": "lng", "kapasite": "capacity", "bos": "emptyCapacity", "acik": "isOpen"}
    bos = sum(
        1 for sutun, alan in kaynak.items()
        if satir[sutun] is None and p.get(alan) not in (None, "")
    )
    return satir, bos


def gunu_oku(depo: YerelDepo | BlobDepo, gun: date) -> Okuma:
    """Bir günün ham turlarını okur; okunamayan dosyayı ve kaydı atlayıp sayar.

    Zaman, API'den değil dosya adından alınıyor: liste ucu güncelleme zamanı
    vermiyor, bizim toplama anımız tek güvenilir kaynak.

    Atlanan dosya: bozuk gzip, JSON değil, liste değil, içinde hiç geçerli kayıt
    yok. Atlanmayan: dosyaya ulaşılamaması (ağ, yetki). O bir okuma hatası;
    günü eksik yazmak yerine hata veriyoruz, gün ertesi gece tamamlanıyor.
    """
    okuma = Okuma()
    for ad in depo.listele(f"{gun:%Y/%m/%d}/"):
        eslesme = DAMGA.search(ad)
        if not eslesme:
            continue
        okuma.dosya += 1
        zaman = datetime.strptime(eslesme.group(1), "%Y%m%dT%H%M%SZ")
        veri = depo.oku_bayt(ad)  # ağ ya da yetki hatası burada fırlar, yakalamıyoruz
        try:
            kayitlar = json.loads(gzip.decompress(veri))
        except (OSError, EOFError, zlib.error, ValueError):
            okuma.atla(ad, "okunamadi")
            continue
        if not isinstance(kayitlar, list):
            okuma.atla(ad, "liste_degil")
            continue
        onceki = len(okuma.satirlar)
        for p in kayitlar:
            satir, bos = kayit_satiri(p, zaman.strftime("%Y-%m-%d %H:%M:%S"))
            if satir is None:
                okuma.atlanan_kayit += 1
            else:
                okuma.satirlar.append(satir)
                okuma.bos_birakilan_deger += bos
        if len(okuma.satirlar) == onceki:
            okuma.atla(ad, "gecerli_kayit_yok")
    return okuma


def gunun_satirlari(depo: YerelDepo | BlobDepo, gun: date) -> list[dict]:
    """Bir günün okunabilen bütün satırları (keşif ve testler için)."""
    return gunu_oku(depo, gun).satirlar


# Dönüşümün tamamı tek SQL'de. Adımlar yukarıdan aşağı okunur.
DOLULUK_SQL = f"""
WITH dilimli AS (
    -- 1. Her turu 5 dakikalık dilime yuvarla: 12:05:48 → 12:05:00.
    --    Böylece farklı saniyelerde çekilen turlar aynı zaman ızgarasına oturur.
    SELECT time_bucket(INTERVAL 5 MINUTE, zaman) AS zaman_utc, *
    FROM ham
),
tekil AS (
    -- 2. Aynı dilimde aynı otopark iki kez varsa (ör. yerelden buluta geçiş
    --    sırasında iki toplayıcı çalıştı) en son çekileni tut.
    SELECT * FROM dilimli
    QUALIFY row_number() OVER (PARTITION BY zaman_utc, park_id ORDER BY zaman DESC) = 1
),
komsulu AS (
    -- 3. Her satırın yanına aynı otoparkın bir önceki ve bir sonraki turunu koy.
    --    ara_once / ara_sonra: komşu tur gerçekten 5 dk uzakta mı? Arada tur
    --    kaçmışsa karşılaştırma anlamsız, o zaman sıçrama demiyoruz.
    --    İstanbul 00:00 = UTC 21:00, yani gün ortası; komşular aynı günde.
    SELECT *,
        lag(bos)  OVER w                   AS onceki,
        lead(bos) OVER w                   AS sonraki,
        zaman_utc - lag(zaman_utc) OVER w  AS ara_once,
        lead(zaman_utc) OVER w - zaman_utc AS ara_sonra
    FROM tekil
    WINDOW w AS (PARTITION BY park_id ORDER BY zaman_utc)
),
isaretli AS (
    -- 4. Tek tur sıçraması (V-013). Günün ilk ve son turunun bir komşusu yok,
    --    karşılaştırma NULL çıkıyor; coalesce ile onları "sıçrama değil" sayıyoruz.
    SELECT *,
        coalesce(
            ara_once = INTERVAL 5 MINUTE AND ara_sonra = INTERVAL 5 MINUTE
            AND abs(onceki - sonraki) <= {SICRAMA_KOMSU_ORAN} * kapasite
            AND abs(bos - onceki) >= greatest({SICRAMA_ORAN} * kapasite, {SICRAMA_EN_AZ}),
            false) AS sicrama
    FROM komsulu
),
canlilik AS (
    -- 5. Otoparkın gün içinde kaç farklı değer gösterdiği. Hiç değişmeyen bir
    --    sayı sensörden değil, sabit bir varsayılandan geliyordur. Sıçramaları
    --    saymıyoruz: donuk bir otopark gece yarısı hatası yüzünden canlı görünmesin.
    SELECT park_id, count(DISTINCT bos) FILTER (NOT sicrama) AS farkli_deger
    FROM isaretli GROUP BY park_id
)
SELECT
    t.zaman_utc,
    -- İstanbul 2016'dan beri yıl boyu UTC+3; yaz saati yok, sabit fark güvenli.
    t.zaman_utc + INTERVAL 3 HOUR                        AS zaman_ist,
    t.park_id,
    t.kapasite,
    t.bos,
    CASE WHEN t.kapasite > 0
         THEN round((t.kapasite - t.bos) / t.kapasite, 4) END AS doluluk,
    t.acik = 1                                           AS acik,
    c.farkli_deger > {CANLI_ESIK}                        AS canli,
    t.sicrama,
    -- Satırı silmiyoruz, işaretliyoruz: neyin neden dışlandığı görünür kalsın.
    (t.bos BETWEEN 0 AND t.kapasite) AND NOT t.sicrama   AS gecerli
FROM isaretli t JOIN canlilik c USING (park_id)
ORDER BY t.zaman_utc, t.park_id
"""

# Otopark listesi zamanla değişiyor (V-012): İSPARK bazı otoparkları listeden
# çıkarıyor, yenilerini ekliyor. Eskiden tablo her gün sadece o günün listesiyle
# yazılıyordu, çıkan otoparkın adı ilçesi kayboluyordu. Artık eski tabloyla
# bugünün listesi birleşiyor: çıkan otopark kalıyor, son_gorulme'de donuyor.
ESKI_OTOPARKLAR = """
CREATE TABLE eski (park_id INTEGER, ad VARCHAR, ilce VARCHAR, tip VARCHAR,
                   lat DOUBLE, lng DOUBLE, ilk_gorulme TIMESTAMP, son_gorulme TIMESTAMP)
"""

OTOPARKLAR_SQL = """
WITH bugun AS (
    -- Bugün görülen her otoparkın en son bilgisi (ad, ilçe, tip, konum).
    SELECT
        park_id,
        arg_max(ad, zaman)   AS ad,
        arg_max(ilce, zaman) AS ilce,
        arg_max(tip, zaman)  AS tip,
        arg_max(lat, zaman)  AS lat,
        arg_max(lng, zaman)  AS lng,
        min(zaman)           AS ilk_gorulme,
        max(zaman)           AS son_gorulme
    FROM ham GROUP BY park_id
),
hepsi AS (
    SELECT * FROM bugun
    UNION ALL BY NAME
    SELECT * FROM eski
)
-- Bilgiyi en son görüldüğü satırdan alıyoruz. Eski bir günü yeniden işlesek
-- bile daha yeni bir ad ya da konum geri gitmiyor.
SELECT
    park_id,
    arg_max(ad, son_gorulme)   AS ad,
    arg_max(ilce, son_gorulme) AS ilce,
    arg_max(tip, son_gorulme)  AS tip,
    arg_max(lat, son_gorulme)  AS lat,
    arg_max(lng, son_gorulme)  AS lng,
    min(ilk_gorulme)           AS ilk_gorulme,
    max(son_gorulme)           AS son_gorulme
FROM hepsi GROUP BY park_id ORDER BY park_id
"""

HAM_SUTUNLAR = {
    "zaman": "TIMESTAMP", "park_id": "INTEGER", "ad": "VARCHAR", "ilce": "VARCHAR",
    "tip": "VARCHAR", "lat": "DOUBLE", "lng": "DOUBLE", "kapasite": "INTEGER",
    "bos": "INTEGER", "acik": "INTEGER",
}


def tabloya_cevir(satirlar: list[dict], klasor: Path, eski_otoparklar: Path | None = None) -> dict:
    """Satırları DuckDB'ye yükler, iki Parquet dosyası yazar ve özet döndürür.

    eski_otoparklar: şimdiye kadar biriken otopark tablosu (yoksa None).
    Saf dönüşüm: depoya dokunmaz, sadece verilen klasöre yazar. Test edilebilir.
    """
    # Satırları satır satır INSERT etmek yavaş; tek bir JSON dosyasına yazıp
    # DuckDB'ye tek seferde okutmak saniyeler içinde bitiyor.
    kaynak = klasor / "ham.ndjson"
    with kaynak.open("w", encoding="utf-8") as f:
        for s in satirlar:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    con = duckdb.connect()
    con.execute(f"CREATE TABLE ham AS SELECT * FROM read_json('{kaynak}', columns={HAM_SUTUNLAR})")

    con.execute(ESKI_OTOPARKLAR)
    if eski_otoparklar:
        tanim = con.execute(f"DESCRIBE SELECT * FROM '{eski_otoparklar}'").fetchall()
        sutunlar = {satir[0] for satir in tanim}
        # 0.5 öncesi tabloda ilk_gorulme yok. Onu yok sayıyoruz: zaten bütün günleri
        # baştan yeniden işleyince tablo doğru hâliyle kuruluyor.
        if "ilk_gorulme" in sutunlar:
            con.execute(f"INSERT INTO eski BY NAME SELECT * FROM '{eski_otoparklar}'")
    # zstd: Parquet'in en iyi sıkıştırmalarından biri; okurken de hızlı.
    bicim = "(FORMAT parquet, COMPRESSION zstd)"
    con.execute(f"COPY ({DOLULUK_SQL}) TO '{klasor / 'doluluk.parquet'}' {bicim}")
    con.execute(f"COPY ({OTOPARKLAR_SQL}) TO '{klasor / 'otoparklar.parquet'}' {bicim}")

    tur, satir, canli, gecersiz, sicrama = con.execute(f"""
        SELECT count(DISTINCT zaman_utc), count(*), count(DISTINCT park_id) FILTER (canli),
               count(*) FILTER (NOT gecerli), count(*) FILTER (sicrama)
        FROM '{klasor / 'doluluk.parquet'}'
    """).fetchone()
    # Tur başına otopark sayısı: listeden otopark düşerse ya da bir tur yarım
    # gelirse en az değeri bunu gösteriyor.
    en_az, en_cok = con.execute(f"""
        SELECT min(n), max(n) FROM (
            SELECT count(*) AS n FROM '{klasor / 'doluluk.parquet'}' GROUP BY zaman_utc)
    """).fetchone()
    con.close()
    return {"tur": tur, "satir": satir, "canli_otopark": canli,
            "gecersiz_satir": gecersiz, "sicrama": sicrama,
            "tur_basina_en_az": en_az, "tur_basina_en_cok": en_cok}


OZET_SUTUNLAR = {
    "tur": "INTEGER", "tamlik": "DOUBLE", "satir": "INTEGER", "canli_otopark": "INTEGER",
    "gecersiz_satir": "INTEGER", "sicrama": "INTEGER", "tur_basina_en_az": "INTEGER",
    "tur_basina_en_cok": "INTEGER", "atlanan_dosya": "INTEGER", "atlanan_kayit": "INTEGER",
    "bos_birakilan_deger": "INTEGER", "hatali": "INTEGER", "sure_sn": "DOUBLE",
    "surum": "VARCHAR", "islenme_utc": "TIMESTAMP",
}


def doluluk_yolu(gun: date) -> str:
    return f"doluluk/tarih={gun:%Y-%m-%d}/doluluk.parquet"


def ozet_yolu(gun: date) -> str:
    return f"ozet/tarih={gun:%Y-%m-%d}/ozet.parquet"


def ozet_yaz(bilgi: dict, yol: Path) -> None:
    """Günün özetini tek satırlık bir Parquet dosyasına yazar.

    Tarih sütunu dosyada yok, klasör adında (tarih=...): doluluk tablosundaki
    gibi hive bölümlemesiyle okunuyor.
    """
    con = duckdb.connect()
    con.execute(f"CREATE TABLE ozet ({', '.join(f'{k} {t}' for k, t in OZET_SUTUNLAR.items())})")
    con.execute(
        f"INSERT INTO ozet VALUES ({', '.join('?' for _ in OZET_SUTUNLAR)})",
        [bilgi[k] for k in OZET_SUTUNLAR],
    )
    con.execute(f"COPY ozet TO '{yol}' (FORMAT parquet)")
    con.close()


def alanlar(bilgi: dict) -> str:
    """Log satırı için: anahtar=değer anahtar=değer ..."""
    return " ".join(f"{k}={v}" for k, v in bilgi.items() if k != "islenme_utc")


def gunu_isle(ham: YerelDepo | BlobDepo, tablo: YerelDepo | BlobDepo, gun: date) -> dict | None:
    """Bir günü okur, dönüştürür ve tablo deposuna yazar. Günün özetini döndürür.

    Ham veri hiç yoksa None. Gün yazılamazsa GunHatasi.
    Yazma sırası: otoparklar, doluluk, en son özet. Özet "gün tamam" işareti;
    arada bir şey yarıda kalırsa özet olmaz, gece işi o günü yeniden işler.
    """
    bas = saat()
    okuma = gunu_oku(ham, gun)
    if okuma.dosya == 0:
        gunluk.warning("GUN_VERI_YOK tarih=%s", gun)
        return None
    if okuma.atlanan_dosya:
        gunluk.warning(
            "atlanan dosya tarih=%s sayi=%d/%d sebepler=%s ornek=%s", gun,
            okuma.atlanan_dosya, okuma.dosya, okuma.sebepler, ",".join(okuma.ornekler),
        )
    oran = okuma.atlanan_dosya / okuma.dosya
    if not okuma.satirlar or oran > ayarlar.ATLANAN_DOSYA_ORANI_EN_FAZLA:
        raise GunHatasi(
            "atlanan_dosya_orani",
            f"atlanan={okuma.atlanan_dosya}/{okuma.dosya} ornek={','.join(okuma.ornekler)}",
        )

    with tempfile.TemporaryDirectory() as gecici:
        klasor = Path(gecici)
        # otoparklar.parquet bütün günlerin ortak dosyası. İki çalıştırma aynı
        # anda yazarsa (gece işi ve elle başlatılan) biri diğerinin eklediğini
        # ezebilir. Bu yüzden koşullu yazıyoruz: dosya okuduğumuzdan beri
        # değiştiyse yazma reddediliyor; yeniden okuyup yeniden birleştiriyoruz.
        # Bu doğru çünkü OTOPARKLAR_SQL birleştirmesi sıradan bağımsız ve tekrar
        # güvenli: min(ilk_gorulme), max(son_gorulme) ve son_gorulme'ye göre
        # arg_max. Hangi gün önce gelirse gelsin, aynı gün iki kez gelse bile
        # sonuç aynı.
        for deneme in range(1, OTOPARKLAR_DENEME + 1):
            eski_veri, etiket = tablo.oku_etiketli(OTOPARKLAR_YOL)
            eski = None
            if eski_veri is not None:
                eski = klasor / "eski_otoparklar.parquet"
                eski.write_bytes(eski_veri)
            ozet = tabloya_cevir(okuma.satirlar, klasor, eski)
            try:
                tablo.yaz_kosullu(
                    OTOPARKLAR_YOL, (klasor / "otoparklar.parquet").read_bytes(), etiket
                )
                break
            except CakismaHatasi:
                gunluk.warning(
                    "otoparklar başka bir çalıştırmayla çakıştı, yeniden birleştiriliyor "
                    "(tarih=%s deneme=%d)", gun, deneme,
                )
        else:
            raise GunHatasi("otoparklar_cakisma", f"{OTOPARKLAR_DENEME} deneme")

        bilgi = {
            "tarih": f"{gun:%Y-%m-%d}",
            "tur": ozet["tur"],
            "tamlik": round(ozet["tur"] / GUNDE_TUR * 100, 1),
            "satir": ozet["satir"],
            "canli_otopark": ozet["canli_otopark"],
            "gecersiz_satir": ozet["gecersiz_satir"],
            "sicrama": ozet["sicrama"],
            "tur_basina_en_az": ozet["tur_basina_en_az"],
            "tur_basina_en_cok": ozet["tur_basina_en_cok"],
            "atlanan_dosya": okuma.atlanan_dosya,
            "atlanan_kayit": okuma.atlanan_kayit,
            "bos_birakilan_deger": okuma.bos_birakilan_deger,
            # Toplayıcının o gün sakladığı geçersiz yanıtlar (Adım 1).
            "hatali": len(ham.listele(f"hatali/{gun:%Y/%m/%d}/")),
            "sure_sn": round(saat() - bas, 1),
            "surum": ayarlar.KOD_SURUMU,
            "islenme_utc": datetime.now(UTC).replace(tzinfo=None, microsecond=0),
        }
        # Meta veri blob'un yanında duruyor: dosyayı açmadan günün özeti görülüyor
        # (durum.sh böyle okuyor). Yerel depo meta veriyi yok sayıyor.
        meta = {k: str(v) for k, v in bilgi.items()}
        tablo.yaz_bayt(doluluk_yolu(gun), (klasor / "doluluk.parquet").read_bytes(), meta)
        ozet_yaz(bilgi, klasor / "ozet.parquet")
        tablo.yaz_bayt(ozet_yolu(gun), (klasor / "ozet.parquet").read_bytes())

    gunluk.info("GUN_TAMAM %s", alanlar(bilgi))
    if bilgi["tamlik"] < ayarlar.GUN_EKSIK_ESIGI:
        gunluk.warning(
            "GUN_EKSIK tarih=%s tamlik=%s esik=%s", gun, bilgi["tamlik"], ayarlar.GUN_EKSIK_ESIGI
        )
    return bilgi


def tamam_gunler(tablo: YerelDepo | BlobDepo) -> set[date]:
    """Hem doluluk hem özet dosyası olan günler."""

    def gunler(kok: str, dosya: str) -> set[date]:
        return {
            date.fromisoformat(eslesme.group(1))
            for ad in tablo.listele(f"{kok}/")
            if ad.endswith(f"/{dosya}") and (eslesme := TARIH.search(ad))
        }

    return gunler("doluluk", "doluluk.parquet") & gunler("ozet", "ozet.parquet")


def islenecek_gunler(
    ham: YerelDepo | BlobDepo, tablo: YerelDepo | BlobDepo, bugun: date
) -> tuple[list[date], list[date]]:
    """Gece işinin günleri: (bu gece işlenecekler, sonraki geceye kalanlar).

    Dün her zaman işleniyor; tekrar işlemek güvenli. Son TAMAMLAMA_GUN içinde
    ham verisi olup tamam olmayan günler de ekleniyor, eskiden yeniye: pencereden
    ilk düşecek olan önce. Bugün hiç yok, çünkü bitmedi.
    """
    dun = bugun - timedelta(days=1)
    tamam = tamam_gunler(tablo)
    eksikler = []
    for geri in range(ayarlar.TAMAMLAMA_GUN, 1, -1):
        gun = bugun - timedelta(days=geri)
        if gun not in tamam and ham.listele(f"{gun:%Y/%m/%d}/"):
            eksikler.append(gun)
    gunler = [dun, *eksikler]
    sinir = max(ayarlar.EN_FAZLA_GUN, 1)
    return gunler[:sinir], gunler[sinir:]


def main() -> None:
    ap = argparse.ArgumentParser(description="Ham turları günlük tabloya çevir (L1)")
    ap.add_argument("--tarih", type=date.fromisoformat, help="tek bir gün (YYYY-AA-GG)")
    ap.add_argument("--baslangic", type=date.fromisoformat, help="bu günden düne kadar hepsi")
    ap.add_argument("--bugunu-de-isle", action="store_true",
                    help="--tarih bugünü gösterse bile işle (yarım gün; sadece deneme için)")
    arg = ap.parse_args()

    bugun = bugun_utc()
    dun = bugun - timedelta(days=1)
    if arg.tarih and arg.tarih >= bugun and not arg.bugunu_de_isle:
        ap.error(f"{arg.tarih} henüz bitmedi (bugün UTC {bugun}). "
                 "Yine de işlemek için --bugunu-de-isle")

    bas = saat()
    ham = depo_olustur(ayarlar.AZURE_KAP)
    tablo = depo_olustur(ayarlar.TABLO_KAP)
    gece = not (arg.tarih or arg.baslangic)
    ertelenen: list[date] = []
    if arg.tarih:
        gunler = [arg.tarih]
    elif arg.baslangic:
        gunler = [arg.baslangic + timedelta(days=i) for i in range((dun - arg.baslangic).days + 1)]
    else:
        gunler, ertelenen = islenecek_gunler(ham, tablo, bugun)
        if ertelenen:
            gunluk.info("GUN_ERTELENDI sebep=en_fazla_gun gunler=%s",
                        ",".join(map(str, ertelenen)))

    islenen = hatali = eksik = veri_yok = 0
    for sira, gun in enumerate(gunler):
        # Süre bütçesi sadece gece işinde: elle verilen günlerin hepsi işleniyor.
        if gece and sira > 0 and saat() - bas > ayarlar.TABLO_SURE_BUTCESI_SN:
            kalan = gunler[sira:]
            ertelenen = kalan + ertelenen
            gunluk.info("GUN_ERTELENDI sebep=sure_butcesi gunler=%s", ",".join(map(str, kalan)))
            break
        try:
            bilgi = gunu_isle(ham, tablo, gun)
        except GunHatasi as h:
            hatali += 1
            gunluk.error("GUN_HATALI tarih=%s sebep=%s %s", gun, h.sebep, h.ayrinti)
            continue
        except Exception as h:
            # Ağ ya da yetki hatası: gün atlanmıyor, yarım da yazılmıyor. Diğer
            # günlere devam; gece işi bu günü sonraki gece yeniden dener.
            hatali += 1
            gunluk.exception("GUN_HATALI tarih=%s sebep=okuma_yazma_hatasi %s",
                             gun, type(h).__name__)
            continue
        if bilgi is None:
            veri_yok += 1
        else:
            islenen += 1
            eksik += bilgi["tamlik"] < ayarlar.GUN_EKSIK_ESIGI

    if gece:
        # Kalp atışı: iş çalıştı ve bitti. Alarm bu satırın yokluğuna bakıyor.
        gunluk.info(
            "GECE_BITTI islenen=%d ertelenen=%d hatali=%d eksik=%d veri_yok=%d "
            "sure_sn=%.1f surum=%s",
            islenen, len(ertelenen), hatali, eksik, veri_yok, saat() - bas, ayarlar.KOD_SURUMU,
        )
    if hatali:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
