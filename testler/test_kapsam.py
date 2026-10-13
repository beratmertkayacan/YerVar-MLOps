"""Kapsam kuralının testleri."""

from datetime import date, timedelta

import duckdb
import pandas as pd

from yervar.degerlendirme.kapsam import kapsam_belirle, saglik_hesapla

BIT = date(2026, 10, 8)


def baglan(gunler: dict[int, list[bool]]) -> duckdb.DuckDBPyConnection:
    """gunler: park_id ve her gün için canlı mı listesi (son eleman BIT günü)."""
    con = duckdb.connect()
    con.execute("CREATE TABLE doluluk (tarih DATE, park_id INTEGER, canli BOOLEAN)")
    for park, canlilar in gunler.items():
        for i, canli in enumerate(canlilar):
            gun = BIT - timedelta(days=len(canlilar) - 1 - i)
            con.execute("INSERT INTO doluluk VALUES (?, ?, ?)", [gun, park, canli])
    con.execute("""
        CREATE TABLE otoparklar AS
        SELECT DISTINCT park_id, 'Otopark' AS ad, 'AÇIK OTOPARK' AS tip FROM doluluk
    """)
    return con


def test_saglik_siniflari() -> None:
    con = baglan({
        1: [True] * 7,                          # her gün canlı
        2: [True, True, True, False, False, False, True],   # 7 günün 4'ü
        3: [False] * 7,                         # hiç canlı değil
        4: [True] * 6,                          # son gün yok (bir gün önce bitiyor)
    })
    # 4 numaranın günlerini bir gün geri kaydır: son günü BIT'ten önce
    con.execute("UPDATE doluluk SET tarih = tarih - INTERVAL 1 DAY WHERE park_id = 4")

    df = saglik_hesapla(con, BIT - timedelta(days=6), BIT).set_index("park_id")

    assert df["saglik"].to_dict() == {
        1: "saglikli", 2: "kismen", 3: "donuk", 4: "liste_disi",
    }


def test_kapsam_karne_ile_birlesir() -> None:
    saglik = pd.DataFrame({
        "park_id": [1, 2, 3, 4, 5],
        "saglik": ["saglikli", "saglikli", "kismen", "donuk", "saglikli"],
    })
    # karnede park_id indeks, kategori tipinde geliyor
    karne = pd.DataFrame(
        {"fark": [0.5, -0.2, 0.8]},
        index=pd.CategoricalIndex([1, 2, 3], name="park_id"),
    )

    kapsam = kapsam_belirle(saglik, karne)["kapsam"].to_dict()

    assert kapsam == {
        1: "model",      # sağlıklı, model iyi
        2: "basit",      # sağlıklı ama model kaybediyor
        3: "basit",      # kısmen canlı, model iyi olsa da
        4: "veri_yok",
        5: "basit",      # karnede yok, model hiç denenmedi
    }
