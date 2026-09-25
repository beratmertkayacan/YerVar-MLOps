"""L1 tablo dönüşümünün testleri.

Gerçek API'ye ya da Azure'a gitmiyoruz: sahte ham turları geçici bir klasöre
yazıp dönüşümü onun üzerinde çalıştırıyoruz.
"""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb

from yervar.depolama.ham import YerelDepo, ham_yol
from yervar.depolama.tablo import gunu_isle

GUN = date(2026, 9, 24)


def park(park_id: int, bos: int, kapasite: int = 100) -> dict:
    """API'nin döndürdüğü biçimde tek bir otopark kaydı."""
    return {
        "parkID": park_id, "parkName": f"Otopark {park_id}", "district": "KADIKÖY",
        "parkType": "AÇIK OTOPARK", "lat": "40.99", "lng": "29.02",
        "capacity": kapasite, "emptyCapacity": bos, "isOpen": 1,
    }


def tur_yaz(depo: YerelDepo, zaman: datetime, parklar: list[dict]) -> None:
    depo.yaz(ham_yol(zaman, "parklar"), parklar)


def doluluk_oku(tablo_kok: Path) -> list[tuple]:
    yol = tablo_kok / f"doluluk/tarih={GUN}/doluluk.parquet"
    return duckdb.sql(
        f"SELECT park_id, zaman_utc, bos, doluluk, canli, gecerli FROM '{yol}' "
        "ORDER BY park_id, zaman_utc"
    ).fetchall()


def hazirla(tmp_path: Path) -> tuple[YerelDepo, YerelDepo]:
    return YerelDepo(tmp_path / "ham"), YerelDepo(tmp_path / "tablo")


def test_ayni_dilimdeki_cift_tur_teklenir(tmp_path: Path) -> None:
    ham, tablo = hazirla(tmp_path)
    t = datetime(2026, 9, 24, 12, 5, 10, tzinfo=UTC)
    tur_yaz(ham, t, [park(1, 50)])
    # 30 sn sonra ikinci toplayıcı aynı dilime yazmış: sadece sonuncusu kalmalı.
    tur_yaz(ham, t + timedelta(seconds=30), [park(1, 48)])

    gunu_isle(ham, tablo, GUN)

    satirlar = doluluk_oku(tmp_path / "tablo")
    assert len(satirlar) == 1
    assert satirlar[0][1] == datetime(2026, 9, 24, 12, 5)  # 5 dk'ya yuvarlandı
    assert satirlar[0][2] == 48


def test_doluluk_orani_hesaplanir(tmp_path: Path) -> None:
    ham, tablo = hazirla(tmp_path)
    tur_yaz(ham, datetime(2026, 9, 24, 8, 0, tzinfo=UTC), [park(1, bos=25, kapasite=100)])

    gunu_isle(ham, tablo, GUN)

    assert doluluk_oku(tmp_path / "tablo")[0][3] == 0.75


def test_donuk_otopark_canli_sayilmaz(tmp_path: Path) -> None:
    ham, tablo = hazirla(tmp_path)
    for i in range(10):
        zaman = datetime(2026, 9, 24, 9, 0, tzinfo=UTC) + timedelta(minutes=5 * i)
        # 1 numara her turda farklı değer veriyor, 2 numara hep 30'da takılı.
        tur_yaz(ham, zaman, [park(1, 40 + i), park(2, 30)])

    gunu_isle(ham, tablo, GUN)

    canlilik = {s[0]: s[4] for s in doluluk_oku(tmp_path / "tablo")}
    assert canlilik == {1: True, 2: False}


def test_imkansiz_deger_isaretlenir_silinmez(tmp_path: Path) -> None:
    ham, tablo = hazirla(tmp_path)
    # Boş yer kapasiteden fazla olamaz; satır kalmalı ama gecerli=False olmalı.
    tur_yaz(ham, datetime(2026, 9, 24, 10, 0, tzinfo=UTC), [park(1, 120), park(2, 10)])

    gunu_isle(ham, tablo, GUN)

    gecerlilik = {s[0]: s[5] for s in doluluk_oku(tmp_path / "tablo")}
    assert gecerlilik == {1: False, 2: True}


def test_otoparklar_tablosu_yazilir(tmp_path: Path) -> None:
    ham, tablo = hazirla(tmp_path)
    tur_yaz(ham, datetime(2026, 9, 24, 10, 0, tzinfo=UTC), [park(1, 5), park(2, 10)])

    gunu_isle(ham, tablo, GUN)

    yol = tmp_path / "tablo/otoparklar/otoparklar.parquet"
    ad, ilce, lat = duckdb.sql(f"SELECT ad, ilce, lat FROM '{yol}' WHERE park_id = 1").fetchone()
    assert (ad, ilce, lat) == ("Otopark 1", "KADIKÖY", 40.99)


def test_baska_gunun_turlari_karismaz(tmp_path: Path) -> None:
    ham, tablo = hazirla(tmp_path)
    tur_yaz(ham, datetime(2026, 9, 24, 23, 55, tzinfo=UTC), [park(1, 5)])
    tur_yaz(ham, datetime(2026, 9, 25, 0, 0, tzinfo=UTC), [park(1, 6)])

    gunu_isle(ham, tablo, GUN)

    assert len(doluluk_oku(tmp_path / "tablo")) == 1


def test_veri_olmayan_gun_dosya_yazmaz(tmp_path: Path) -> None:
    ham, tablo = hazirla(tmp_path)

    gunu_isle(ham, tablo, GUN)

    assert not (tmp_path / "tablo").exists()
