"""Ham depolama katmanının testleri."""

import gzip
from datetime import UTC, datetime
from pathlib import Path

from yervar.depolama.ham import YerelDepo, ham_yol, oku, simdi_utc

ORNEK_ZAMAN = datetime(2026, 9, 17, 14, 30, 0, tzinfo=UTC)


def test_yol_saat_bazli_klasorlenir() -> None:
    yol = ham_yol(ORNEK_ZAMAN, "parklar")
    assert yol == "2026/09/17/14/parklar_20260917T143000Z.json.gz"


def test_zaman_utc_ve_zaman_dilimli() -> None:
    assert simdi_utc().tzinfo == UTC


def test_yazilan_veri_aynen_okunur(tmp_path: Path) -> None:
    icerik = [{"parkID": 3068, "parkName": "15 Temmuz Şehitler Meydanı", "emptyCapacity": 379}]
    yol = YerelDepo(tmp_path).yaz(ham_yol(ORNEK_ZAMAN, "parklar"), icerik)
    assert oku(yol) == icerik


def test_gecici_dosya_kalmaz(tmp_path: Path) -> None:
    YerelDepo(tmp_path).yaz(ham_yol(ORNEK_ZAMAN, "parklar"), {"a": 1})
    assert list(tmp_path.rglob("*.tmp")) == []


def test_turkce_karakterler_korunur(tmp_path: Path) -> None:
    yol = YerelDepo(tmp_path).yaz("x.json.gz", {"ilce": "ÜMRANİYE", "ad": "Şişli"})
    with gzip.open(yol, "rt", encoding="utf-8") as dosya:
        metin = dosya.read()
    assert "ÜMRANİYE" in metin and "\\u" not in metin


def test_varsayilan_depo_yereldir(monkeypatch) -> None:
    from yervar import ayarlar
    from yervar.depolama.ham import depo_olustur

    monkeypatch.setattr(ayarlar, "DEPO_TURU", "yerel")
    assert isinstance(depo_olustur(), YerelDepo)


def test_blob_icin_hesap_adi_zorunlu(monkeypatch) -> None:
    import pytest

    from yervar import ayarlar
    from yervar.depolama.ham import depo_olustur

    monkeypatch.setattr(ayarlar, "DEPO_TURU", "blob")
    monkeypatch.setattr(ayarlar, "AZURE_DEPOLAMA_HESABI", "")
    with pytest.raises(ValueError):
        depo_olustur()


# --- üzerine yazma ve meta veri ---------------------------------------------

def test_ham_kapta_ikinci_yazim_uzerine_yazmaz(tmp_path: Path, caplog) -> None:
    depo = YerelDepo(tmp_path, uzerine_yaz=False)
    yol = ham_yol(ORNEK_ZAMAN, "parklar")
    depo.yaz(yol, {"ilk": 1})
    depo.yaz(yol, {"ikinci": 2})
    assert oku(tmp_path / yol) == {"ilk": 1}
    assert "üzerine yazılmadı" in caplog.text


def test_tablo_kabinda_uzerine_yazilir(tmp_path: Path) -> None:
    depo = YerelDepo(tmp_path)  # varsayılan: üzerine yaz (tablo.py böyle kullanıyor)
    depo.yaz("x.json.gz", {"ilk": 1})
    depo.yaz("x.json.gz", {"ikinci": 2})
    assert oku(tmp_path / "x.json.gz") == {"ikinci": 2}


def test_depo_olustur_kaba_gore_karar_verir(monkeypatch, tmp_path: Path) -> None:
    from yervar import ayarlar
    from yervar.depolama.ham import depo_olustur

    monkeypatch.setattr(ayarlar, "DEPO_TURU", "yerel")
    monkeypatch.setattr(ayarlar, "VERI_KOK", tmp_path)
    assert depo_olustur().uzerine_yaz is False
    assert depo_olustur(ayarlar.AZURE_KAP).uzerine_yaz is False
    assert depo_olustur(ayarlar.TABLO_KAP).uzerine_yaz is True
    assert depo_olustur(ayarlar.TABLO_KAP, uzerine_yaz=False).uzerine_yaz is False


class SahteKap:
    """BlobDepo'nun kullandığı kap istemcisinin taklidi. Azure'a çıkmaz."""

    url = "https://sahte.blob.core.windows.net/ham"

    def __init__(self, var_olan: set[str] | None = None) -> None:
        self.var_olan = var_olan or set()
        self.cagrilar: list[dict] = []

    def upload_blob(self, ad, veri, overwrite, metadata):
        from azure.core.exceptions import ResourceExistsError

        self.cagrilar.append({"ad": ad, "overwrite": overwrite, "metadata": metadata})
        if ad in self.var_olan and not overwrite:
            raise ResourceExistsError("BlobAlreadyExists")
        self.var_olan.add(ad)

        class Yuklenen:
            url = f"{SahteKap.url}/{ad}"

        return Yuklenen()


def sahte_blob_depo(kap: SahteKap, uzerine_yaz: bool):
    from yervar.depolama.ham import BlobDepo

    depo = BlobDepo.__new__(BlobDepo)  # __init__ Azure'a bağlanırdı, atlıyoruz
    depo.kap = kap
    depo.uzerine_yaz = uzerine_yaz
    return depo


def test_blob_zaten_varsa_hata_vermez(caplog) -> None:
    kap = SahteKap(var_olan={"a.json.gz"})
    adres = sahte_blob_depo(kap, uzerine_yaz=False).yaz_bayt("a.json.gz", b"x")
    assert adres.endswith("/a.json.gz")
    assert kap.cagrilar[0]["overwrite"] is False
    assert "üzerine yazılmadı" in caplog.text


def test_blob_tablo_kabinda_uzerine_yazar() -> None:
    kap = SahteKap(var_olan={"t.parquet"})
    sahte_blob_depo(kap, uzerine_yaz=True).yaz_bayt("t.parquet", b"x")
    assert kap.cagrilar[0]["overwrite"] is True


def test_blob_meta_verisi_ascii() -> None:
    kap = SahteKap()
    sahte_blob_depo(kap, uzerine_yaz=False).yaz("a.json.gz", [], {"ilce": "ÜMRANİYE", "kayit": 247})
    assert kap.cagrilar[0]["metadata"] == {"ilce": "?MRAN?YE", "kayit": "247"}


def test_hatali_yol_l1_onekinin_disinda() -> None:
    from yervar.depolama.ham import hatali_yol

    yol = hatali_yol(ORNEK_ZAMAN, "parklar")
    assert yol == "hatali/2026/09/17/14/parklar_20260917T143000Z.govde.gz"
    assert not yol.startswith("2026/")
