"""L2 özellik setinin testleri.

L1 tablolarını elle, bellekte kuruyoruz. Her test tek bir kuralı kontrol ediyor.
En önemlisi sızıntı testi: gelecekteki bir değeri değiştirince özellikler
değişmemeli, sadece hedef değişmeli.
"""

from datetime import date, datetime, timedelta

import duckdb

from yervar.ozellikler.olustur import ozellik_seti
from yervar.ozellikler.takvim import ozel_donemler, takvim_satirlari, tatil_gunleri

BAS = datetime(2026, 9, 24, 6, 0)  # UTC, İstanbul 09:00


def kur(kayitlar: list[tuple], otopark_bilgisi: bool = True) -> duckdb.DuckDBPyConnection:
    """Bellekte doluluk ve otoparklar tablosu kurar.

    kayitlar: (zaman_utc, park_id, doluluk) ya da (..., canli, acik)
    """
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE doluluk (
            tarih DATE, zaman_utc TIMESTAMP, zaman_ist TIMESTAMP, park_id INTEGER,
            kapasite INTEGER, bos INTEGER, doluluk DOUBLE,
            acik BOOLEAN, canli BOOLEAN, gecerli BOOLEAN
        )
    """)
    for k in kayitlar:
        zaman, park, oran = k[:3]
        canli = k[3] if len(k) > 3 else True
        acik = k[4] if len(k) > 4 else True
        con.execute(
            "INSERT INTO doluluk VALUES (?, ?, ?, ?, 100, ?, ?, ?, ?, true)",
            [zaman.date(), zaman, zaman + timedelta(hours=3), park,
             round(100 * (1 - oran)), oran, acik, canli],
        )
    con.execute("""
        CREATE TABLE otoparklar AS
        SELECT DISTINCT park_id, 'KADIKÖY' AS ilce, 'AÇIK OTOPARK' AS tip FROM doluluk
    """)
    return con


def seri(park: int, degerler: list[float], bas: datetime = BAS) -> list[tuple]:
    """5 dakika arayla bir otoparkın değerleri."""
    return [(bas + timedelta(minutes=5 * i), park, d) for i, d in enumerate(degerler)]


def satir(con, zaman: datetime, park: int = 1) -> dict:
    gun = zaman.date()
    rel = ozellik_seti(con, gun, gun).filter(f"zaman_utc = '{zaman}' AND park_id = {park}")
    sutunlar = rel.columns
    return dict(zip(sutunlar, rel.fetchone(), strict=True))


def test_hedef_30dk_sonraki_deger() -> None:
    con = kur(seri(1, [round(0.1 * i, 1) for i in range(10)]))
    s = satir(con, BAS)
    assert s["hedef"] == 0.6  # 6. adım = 30 dk sonra


def test_gecmis_deger_zamana_gore_bulunur() -> None:
    # 5 dk önceki tur eksik. Özellik boş kalmalı, 10 dk önceki değer kullanılmamalı.
    kayitlar = seri(1, [0.1, 0.2, 0.3])
    del kayitlar[1]
    con = kur(kayitlar)
    s = satir(con, BAS + timedelta(minutes=10))
    assert s["doluluk_5dk_once"] is None


def test_gelecek_ozellikleri_etkilemez() -> None:
    degerler = [0.5] * 12
    a = satir(kur(seri(1, degerler)), BAS + timedelta(minutes=25))

    degerler[8] = 0.99   # 15 dk sonrası
    degerler[11] = 0.99  # 30 dk sonrası, yani hedef
    b = satir(kur(seri(1, degerler)), BAS + timedelta(minutes=25))

    assert a.pop("hedef") != b.pop("hedef")
    assert a == b


def test_donuk_ve_kapali_satirlar_atilir() -> None:
    kayitlar = [
        (BAS, 1, 0.5),
        (BAS, 2, 0.5, False, True),   # canlı değil
        (BAS, 3, 0.5, True, False),   # kapalı
    ]
    con = kur(kayitlar)
    parklar = {r[0] for r in ozellik_seti(con, BAS.date(), BAS.date()).select("park_id").fetchall()}
    assert parklar == {1}


def test_tatil_ve_arife_isaretlenir() -> None:
    arife = datetime(2026, 10, 28, 11, 0)   # İstanbul 14:00
    bayram = datetime(2026, 10, 29, 11, 0)
    con = kur([(arife, 1, 0.5), (bayram, 1, 0.5)])

    assert satir(con, arife)["arife"] is True
    assert satir(con, arife)["resmi_tatil"] is False
    assert satir(con, bayram)["resmi_tatil"] is True


def test_hafta_sonu() -> None:
    cumartesi = datetime(2026, 9, 26, 9, 0)
    con = kur([(cumartesi, 1, 0.5)])
    s = satir(con, cumartesi)
    assert s["hafta_sonu"] is True
    assert s["haftanin_gunu"] == 6


def test_dun_ayni_saat() -> None:
    dun = BAS - timedelta(days=1)
    con = kur([(dun, 1, 0.3), (BAS, 1, 0.8)])
    assert satir(con, BAS)["doluluk_dun"] == 0.3


def test_tatil_listesinde_2026_bayramlari_var() -> None:
    gunler = {s["tarih"]: s["yarim_gun"] for s in tatil_gunleri([2026])}
    assert gunler[date(2026, 3, 20)] is False  # Ramazan Bayramı
    assert gunler[date(2026, 5, 26)] is True   # Kurban Bayramı arifesi


def test_ozel_donemler_takvime_islenir() -> None:
    donemler = [
        {"baslangic": date(2026, 11, 16), "bitis": date(2026, 11, 20),
         "tur": "okul_tatili", "ad": "ara tatil"},
        {"baslangic": date(2026, 10, 30), "bitis": date(2026, 10, 30),
         "tur": "idari_izin", "ad": "deneme"},
    ]
    satirlar = takvim_satirlari(date(2026, 10, 28), date(2026, 11, 21), donemler)
    gunler = {s["tarih"]: s for s in satirlar}
    assert gunler[date(2026, 11, 18)]["okul_tatili"] is True
    assert gunler[date(2026, 11, 21)]["okul_tatili"] is False
    assert gunler[date(2026, 10, 30)]["idari_izin"] is True
    assert gunler[date(2026, 10, 29)]["resmi_tatil"] is True
    assert gunler[date(2026, 10, 28)]["arife"] is True


def test_ozel_donemler_dosyasi_okunur() -> None:
    turler = {d["tur"] for d in ozel_donemler()}
    assert turler <= {"idari_izin", "okul_tatili"}
