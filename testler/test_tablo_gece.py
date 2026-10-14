"""Gece tablo işinin (L1) testleri: dayanıklı okuma, eksik gün, özet, çakışma.

Ağa ve Azure'a çıkmıyoruz: ham ve tablo depoları geçici klasörlerde.
test_tablo.py dönüşümün kendisini sınıyor; bu dosya işin çevresini.
"""

import gzip
import logging
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from yervar import ayarlar
from yervar.depolama import tablo as t
from yervar.depolama.ham import CakismaHatasi, YerelDepo, ham_yol

GUN = date(2026, 9, 24)
GUN2 = date(2026, 9, 25)


def park(park_id: int, bos: int = 50, kapasite: int = 100) -> dict:
    return {
        "parkID": park_id, "parkName": f"Otopark {park_id}", "district": "KADIKÖY",
        "parkType": "AÇIK OTOPARK", "lat": "40.99", "lng": "29.02",
        "capacity": kapasite, "emptyCapacity": bos, "isOpen": 1,
    }


@pytest.fixture(autouse=True)
def bilgi_loglari(caplog):
    # GUN_TAMAM ve GECE_BITTI bilgi düzeyinde; varsayılan yakalama sadece uyarıdan başlıyor.
    caplog.set_level(logging.INFO, logger="yervar")


def zaman(gun: date, sira: int) -> datetime:
    gece = datetime(gun.year, gun.month, gun.day, 0, 0, 30, tzinfo=UTC)
    return gece + timedelta(minutes=5 * sira)


def turlar_yaz(ham: YerelDepo, gun: date, adet: int, parklar=(1, 2), bas: int = 0) -> None:
    for i in range(bas, bas + adet):
        ham.yaz(ham_yol(zaman(gun, i), "parklar"), [park(p, bos=40 + i % 7) for p in parklar])


def hazirla(tmp_path: Path) -> tuple[YerelDepo, YerelDepo]:
    return YerelDepo(tmp_path / "ham", uzerine_yaz=False), YerelDepo(tmp_path / "tablo")


def calistir(monkeypatch, ham, tablo, *argv: str, bugun: date = date(2026, 9, 26)) -> None:
    monkeypatch.setattr(
        t, "depo_olustur", lambda kap=None, **_: ham if kap == ayarlar.AZURE_KAP else tablo
    )
    monkeypatch.setattr(t, "bugun_utc", lambda: bugun)
    monkeypatch.setattr(sys, "argv", ["tablo", *argv])
    t.main()


def var_mi(tablo: YerelDepo, gun: date) -> tuple[bool, bool]:
    return (tablo.kok / t.doluluk_yolu(gun)).exists(), (tablo.kok / t.ozet_yolu(gun)).exists()


# --- 1. dayanıklı okuma -------------------------------------------------------


def bozuk_dosyalar_yaz(ham: YerelDepo, gun: date, bas: int) -> None:
    """Dört farklı biçimde okunamayan dosya, art arda dilimlere."""
    ham.yaz_bayt(ham_yol(zaman(gun, bas), "parklar"), b"gzip degil")
    ham.yaz_bayt(ham_yol(zaman(gun, bas + 1), "parklar"), gzip.compress(b"<html>bakim</html>"))
    ham.yaz(ham_yol(zaman(gun, bas + 2), "parklar"), {"hata": "liste yerine sozluk"})
    ham.yaz(ham_yol(zaman(gun, bas + 3), "parklar"), [{"parkName": "numarasiz"}] * 2)


def test_bozuk_dosyalar_atlanir_gun_yine_yazilir(tmp_path: Path) -> None:
    ham, tablo = hazirla(tmp_path)
    turlar_yaz(ham, GUN, 100)
    bozuk_dosyalar_yaz(ham, GUN, 100)  # 4 / 104 dosya, eşiğin (%5) altında
    # iyi bir turun içinde numarasız bir kayıt ve sayı olmayan bir konum
    kayitlar = [park(1), park(2), {"parkName": "numarasiz"}]
    kayitlar[1]["lat"] = "bilinmiyor"
    ham.yaz(ham_yol(zaman(GUN, 104), "parklar"), kayitlar)

    bilgi = t.gunu_isle(ham, tablo, GUN)

    assert var_mi(tablo, GUN) == (True, True)
    assert bilgi["atlanan_dosya"] == 4
    assert bilgi["atlanan_kayit"] == 3  # numarasız dosyadaki 2 + iyi turdaki 1
    assert bilgi["tur"] == 101
    # konumu bozuk kayıt atlanmadı, sadece konumu boş kaldı
    yol = tablo.kok / t.doluluk_yolu(GUN)
    assert duckdb.sql(f"SELECT count(*) FROM '{yol}'").fetchone()[0] == 202


def test_atlanan_orani_asilinca_gun_yarim_yazilmaz(tmp_path: Path) -> None:
    ham, tablo = hazirla(tmp_path)
    turlar_yaz(ham, GUN, 10)
    ham.yaz_bayt(ham_yol(zaman(GUN, 10), "parklar"), b"bozuk")  # 1 / 11, yaklaşık %9

    with pytest.raises(t.GunHatasi) as hata:
        t.gunu_isle(ham, tablo, GUN)

    assert hata.value.sebep == "atlanan_dosya_orani"
    assert var_mi(tablo, GUN) == (False, False)
    assert not (tablo.kok / t.OTOPARKLAR_YOL).exists()


def test_hatali_gun_digerlerini_durdurmaz_cikis_kodu_1(tmp_path, monkeypatch, caplog) -> None:
    ham, tablo = hazirla(tmp_path)
    turlar_yaz(ham, GUN, 10)
    ham.yaz_bayt(ham_yol(zaman(GUN, 10), "parklar"), b"bozuk")
    turlar_yaz(ham, GUN2, 10)

    with pytest.raises(SystemExit) as cikis:
        calistir(monkeypatch, ham, tablo, "--baslangic", "2026-09-24")

    assert cikis.value.code == 1
    assert "GUN_HATALI tarih=2026-09-24 sebep=atlanan_dosya_orani" in caplog.text
    assert var_mi(tablo, GUN) == (False, False)
    assert var_mi(tablo, GUN2) == (True, True)


def test_okuma_hatasi_atlanmaz_gun_hatali_olur(tmp_path, monkeypatch, caplog) -> None:
    class KopanDepo(YerelDepo):
        def oku_bayt(self, goreli_yol: str) -> bytes:
            if goreli_yol.endswith("T001030Z.json.gz"):
                raise ConnectionError("ağ koptu")
            return super().oku_bayt(goreli_yol)

    ham = KopanDepo(tmp_path / "ham")
    tablo = YerelDepo(tmp_path / "tablo")
    turlar_yaz(ham, GUN, 30)

    with pytest.raises(SystemExit) as cikis:
        calistir(monkeypatch, ham, tablo, "--tarih", "2026-09-24")

    assert cikis.value.code == 1
    assert "GUN_HATALI tarih=2026-09-24 sebep=okuma_yazma_hatasi ConnectionError" in caplog.text
    assert var_mi(tablo, GUN) == (False, False)


# --- 2. eksik günler ve bugün ---------------------------------------------------


def test_eksik_gunler_secilir(tmp_path, monkeypatch) -> None:
    ham, tablo = hazirla(tmp_path)
    bugun = date(2026, 10, 14)
    for gun in range(8, 15):  # 8-14 Ekim ham var, 7 Ekim yok
        turlar_yaz(ham, date(2026, 10, gun), 1)
    # 11 Ekim tamam (doluluk + özet); 12 Ekim'in sadece doluluğu var, tamam sayılmaz
    for yol in (t.doluluk_yolu(date(2026, 10, 11)), t.ozet_yolu(date(2026, 10, 11)),
                t.doluluk_yolu(date(2026, 10, 12))):
        tablo.yaz_bayt(yol, b"x")
    monkeypatch.setattr(ayarlar, "EN_FAZLA_GUN", 3)

    gunler, ertelenen = t.islenecek_gunler(ham, tablo, bugun)

    assert gunler == [date(2026, 10, 13), date(2026, 10, 8), date(2026, 10, 9)]
    assert ertelenen == [date(2026, 10, 10), date(2026, 10, 12)]
    assert bugun not in gunler + ertelenen
    assert date(2026, 10, 11) not in gunler + ertelenen  # tamam olan tekrar işlenmiyor
    assert date(2026, 10, 7) not in gunler + ertelenen  # ham verisi olmayan aday değil


def test_bugun_islenmez_bayrakla_islenir(tmp_path, monkeypatch) -> None:
    ham, tablo = hazirla(tmp_path)
    bugun = date(2026, 9, 24)
    turlar_yaz(ham, bugun, 3)

    with pytest.raises(SystemExit) as cikis:
        calistir(monkeypatch, ham, tablo, "--tarih", "2026-09-24", bugun=bugun)
    assert cikis.value.code == 2  # argparse hatası
    assert var_mi(tablo, bugun) == (False, False)

    calistir(monkeypatch, ham, tablo, "--tarih", "2026-09-24", "--bugunu-de-isle", bugun=bugun)
    assert var_mi(tablo, bugun) == (True, True)


def test_gece_isi_kalp_atisi_yapacak_is_olmasa_bile(tmp_path, monkeypatch, caplog) -> None:
    ham, tablo = hazirla(tmp_path)  # hiç veri yok

    calistir(monkeypatch, ham, tablo, bugun=date(2026, 9, 26))

    assert "GUN_VERI_YOK tarih=2026-09-25" in caplog.text
    assert "GECE_BITTI islenen=0 ertelenen=0 hatali=0 eksik=0 veri_yok=1" in caplog.text


def test_sure_butcesi_dolunca_yeni_gune_baslanmaz(tmp_path, monkeypatch, caplog) -> None:
    ham, tablo = hazirla(tmp_path)
    for gun in (11, 12, 13):
        turlar_yaz(ham, date(2026, 10, gun), 2)
    monkeypatch.setattr(ayarlar, "TABLO_SURE_BUTCESI_SN", -1)  # ilk günden sonra doldu

    calistir(monkeypatch, ham, tablo, bugun=date(2026, 10, 14))

    assert var_mi(tablo, date(2026, 10, 13)) == (True, True)  # dün her zaman ilk
    assert var_mi(tablo, date(2026, 10, 11)) == (False, False)
    assert "GUN_ERTELENDI sebep=sure_butcesi gunler=2026-10-11,2026-10-12" in caplog.text
    assert "GECE_BITTI islenen=1 ertelenen=2" in caplog.text


def test_elle_verilen_gunlere_sinir_uygulanmaz(tmp_path, monkeypatch) -> None:
    ham, tablo = hazirla(tmp_path)
    for gun in (22, 23, 24, 25):
        turlar_yaz(ham, date(2026, 9, gun), 2)
    monkeypatch.setattr(ayarlar, "EN_FAZLA_GUN", 1)
    monkeypatch.setattr(ayarlar, "TABLO_SURE_BUTCESI_SN", -1)

    calistir(monkeypatch, ham, tablo, "--baslangic", "2026-09-22", bugun=date(2026, 9, 26))

    assert all(var_mi(tablo, date(2026, 9, g)) == (True, True) for g in (22, 23, 24, 25))


# --- 3. günlük özet -------------------------------------------------------------


class MetaKaydeden(YerelDepo):
    """Yerel depo meta veriyi yok sayıyor; test için yanına kaydediyoruz."""

    def __init__(self, kok: Path) -> None:
        super().__init__(kok)
        self.metalar: dict[str, dict] = {}

    def yaz_bayt(self, goreli_yol, veri, meta=None):
        if meta is not None:
            self.metalar[goreli_yol] = meta
        return super().yaz_bayt(goreli_yol, veri, meta)


def test_gun_tamam_satiri_meta_ve_ozet(tmp_path, monkeypatch, caplog) -> None:
    ham = YerelDepo(tmp_path / "ham", uzerine_yaz=False)
    tablo = MetaKaydeden(tmp_path / "tablo")
    turlar_yaz(ham, GUN, 12, parklar=(1, 2, 3))
    turlar_yaz(ham, GUN, 1, parklar=(1, 2), bas=12)  # yarım gelen bir tur
    for i in range(2):  # toplayıcının sakladığı iki geçersiz yanıt
        ham.yaz_bayt(f"hatali/2026/09/24/0{i}/parklar_x{i}.govde.gz", b"x")
    monkeypatch.setattr(ayarlar, "KOD_SURUMU", "0.7-abc1234")

    bilgi = t.gunu_isle(ham, tablo, GUN)

    beklenen = {"tarih": "2026-09-24", "tur": 13, "satir": 38, "tur_basina_en_az": 2,
                "tur_basina_en_cok": 3, "atlanan_dosya": 0, "atlanan_kayit": 0,
                "hatali": 2, "surum": "0.7-abc1234"}
    assert {k: bilgi[k] for k in beklenen} == beklenen
    assert bilgi["tamlik"] == round(13 / 288 * 100, 1)

    satir = next(r.getMessage() for r in caplog.records if r.getMessage().startswith("GUN_TAMAM"))
    for anahtar in ("tarih", "tur", "tamlik", "satir", "canli_otopark", "gecersiz_satir",
                    "sicrama", "tur_basina_en_az", "tur_basina_en_cok", "atlanan_dosya",
                    "atlanan_kayit", "hatali", "sure_sn", "surum"):
        assert f" {anahtar}=" in satir
    assert "hatali=2" in satir and "surum=0.7-abc1234" in satir

    meta = tablo.metalar[t.doluluk_yolu(GUN)]
    assert meta["tamlik"] == str(bilgi["tamlik"]) and meta["hatali"] == "2"
    assert all(isinstance(v, str) and v for v in meta.values())

    ozet = duckdb.sql(
        f"SELECT * FROM read_parquet('{tablo.kok}/ozet/**/*.parquet', hive_partitioning = true)"
    )
    satirlar = ozet.fetchall()
    sutunlar = ozet.columns
    assert len(satirlar) == 1
    kayit = dict(zip(sutunlar, satirlar[0], strict=True))
    assert kayit["tarih"] == GUN
    assert kayit["tur"] == 13 and kayit["hatali"] == 2 and kayit["surum"] == "0.7-abc1234"


def test_gun_eksik_uyarisi_isi_dusurmez(tmp_path, monkeypatch, caplog) -> None:
    ham, tablo = hazirla(tmp_path)
    turlar_yaz(ham, GUN2, 20)  # %6,9 tamlık

    calistir(monkeypatch, ham, tablo, bugun=date(2026, 9, 26))

    assert "GUN_EKSIK tarih=2026-09-25 tamlik=6.9 esik=95" in caplog.text
    assert "GECE_BITTI islenen=1 ertelenen=0 hatali=0 eksik=1" in caplog.text
    assert var_mi(tablo, GUN2) == (True, True)

    caplog.clear()
    monkeypatch.setattr(ayarlar, "GUN_EKSIK_ESIGI", 5)
    t.gunu_isle(ham, tablo, GUN2)
    assert "GUN_EKSIK" not in caplog.text


# --- 4. otoparklar.parquet çakışması --------------------------------------------


def otoparklar(tablo: YerelDepo) -> list[tuple]:
    yol = tablo.kok / t.OTOPARKLAR_YOL
    return duckdb.sql(f"SELECT * FROM '{yol}' ORDER BY park_id").fetchall()


def test_birlestirme_sira_bagimsiz(tmp_path: Path) -> None:
    ham = YerelDepo(tmp_path / "ham", uzerine_yaz=False)
    turlar_yaz(ham, GUN, 3, parklar=(1, 2))
    turlar_yaz(ham, GUN2, 3, parklar=(2, 3))
    ileri, geri = YerelDepo(tmp_path / "ileri"), YerelDepo(tmp_path / "geri")

    for gun in (GUN, GUN2):
        t.gunu_isle(ham, ileri, gun)
    for gun in (GUN2, GUN, GUN2):  # ters sıra, üstüne bir gün iki kez
        t.gunu_isle(ham, geri, gun)

    assert otoparklar(ileri) == otoparklar(geri)
    assert [s[0] for s in otoparklar(ileri)] == [1, 2, 3]


def test_cakismada_yeniden_okunup_birlestirilir(tmp_path: Path) -> None:
    ham = YerelDepo(tmp_path / "ham", uzerine_yaz=False)
    turlar_yaz(ham, GUN, 3, parklar=(1,))
    turlar_yaz(ham, GUN2, 3, parklar=(99,))
    # "öteki çalıştırmanın" yazacağı dosyayı önceden hazırla
    oteki = YerelDepo(tmp_path / "oteki")
    t.gunu_isle(ham, oteki, GUN2)
    oteki_bayt = oteki.oku_bayt(t.OTOPARKLAR_YOL)

    class ArayaGiren(YerelDepo):
        """Okuma ile yazma arasında başka bir çalıştırma dosyayı değiştiriyor."""

        araya_girdi = False

        def yaz_kosullu(self, goreli_yol, veri, etiket, meta=None):
            if not self.araya_girdi:
                self.araya_girdi = True
                self.yaz_bayt(goreli_yol, oteki_bayt)
            return super().yaz_kosullu(goreli_yol, veri, etiket, meta)

    tablo = ArayaGiren(tmp_path / "tablo")
    t.gunu_isle(ham, tablo, GUN)

    assert [s[0] for s in otoparklar(tablo)] == [1, 99]  # iki çalıştırmanın eklediği de var
    assert var_mi(tablo, GUN) == (True, True)


def test_uc_cakismadan_sonra_gun_hatali(tmp_path: Path) -> None:
    ham = YerelDepo(tmp_path / "ham", uzerine_yaz=False)
    turlar_yaz(ham, GUN, 3)

    class HepCakisan(YerelDepo):
        def yaz_kosullu(self, goreli_yol, veri, etiket, meta=None):
            raise CakismaHatasi(goreli_yol)

    tablo = HepCakisan(tmp_path / "tablo")
    with pytest.raises(t.GunHatasi) as hata:
        t.gunu_isle(ham, tablo, GUN)

    assert hata.value.sebep == "otoparklar_cakisma"
    assert var_mi(tablo, GUN) == (False, False)  # gün yarım yazılmadı
