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


def test_bos_meta_degerleri_atilir() -> None:
    from yervar.depolama.ham import meta_temizle

    assert meta_temizle({"sebep": "az_kayit", "konum": "", "x": None}) == {"sebep": "az_kayit"}
    assert meta_temizle({"konum": ""}) is None
    assert meta_temizle(None) is None


def test_hatali_yol_l1_onekinin_disinda() -> None:
    from yervar.depolama.ham import hatali_yol

    yol = hatali_yol(ORNEK_ZAMAN, "parklar")
    assert yol == "hatali/2026/09/17/14/parklar_20260917T143000Z.govde.gz"
    assert not yol.startswith("2026/")


# --- koşullu yazma: tablo kabındaki ortak dosya (otoparklar) için ------------


def test_yerel_kosullu_yazma_yoksa_olusturur(tmp_path: Path) -> None:
    import hashlib

    depo = YerelDepo(tmp_path)
    assert depo.oku_etiketli("o/o.parquet") == (None, None)
    depo.yaz_kosullu("o/o.parquet", b"bir", None)
    veri, etiket = depo.oku_etiketli("o/o.parquet")
    assert veri == b"bir"
    assert etiket == hashlib.sha256(b"bir").hexdigest()


def test_yerel_yoksa_olustur_baskasi_olusturduysa_reddeder(tmp_path: Path) -> None:
    import pytest

    from yervar.depolama.ham import CakismaHatasi

    depo = YerelDepo(tmp_path)
    depo.yaz_bayt("o.parquet", b"baskasinin")
    with pytest.raises(CakismaHatasi):
        depo.yaz_kosullu("o.parquet", b"benim", None)
    assert depo.oku_bayt("o.parquet") == b"baskasinin"


def test_yerel_okunduktan_sonra_degistiyse_reddeder(tmp_path: Path) -> None:
    import pytest

    from yervar.depolama.ham import CakismaHatasi

    depo = YerelDepo(tmp_path)
    depo.yaz_bayt("o.parquet", b"v1")
    _, etiket = depo.oku_etiketli("o.parquet")
    depo.yaz_bayt("o.parquet", b"v2")  # arada başka bir çalıştırma yazdı
    with pytest.raises(CakismaHatasi):
        depo.yaz_kosullu("o.parquet", b"v3", etiket)
    assert depo.oku_bayt("o.parquet") == b"v2"

    _, yeni = depo.oku_etiketli("o.parquet")
    depo.yaz_kosullu("o.parquet", b"v3", yeni)
    assert depo.oku_bayt("o.parquet") == b"v3"


def test_yerel_etiket_icerige_bakar_boyuta_degil(tmp_path: Path) -> None:
    depo = YerelDepo(tmp_path)
    depo.yaz_bayt("a", b"aaaa")
    depo.yaz_bayt("b", b"bbbb")  # aynı boyut, farklı içerik
    assert depo.oku_etiketli("a")[1] != depo.oku_etiketli("b")[1]


class EtiketliKap:
    """Koşullu yüklemeyi taklit eden kap. Her yazmada ETag değişiyor."""

    url = "https://sahte.blob.core.windows.net/tablo"

    def __init__(self) -> None:
        self.bloblar: dict[str, tuple[bytes, str]] = {}
        self.sayac = 0
        self.cagrilar: list[dict] = []

    def download_blob(self, ad):
        from azure.core.exceptions import ResourceNotFoundError

        if ad not in self.bloblar:
            raise ResourceNotFoundError("BlobNotFound")
        veri, etag = self.bloblar[ad]

        class Indirme:
            class properties:  # noqa: N801  (SDK'daki adın aynısı)
                pass

            def readall(self):
                return veri

        indirme = Indirme()
        indirme.properties.etag = etag
        return indirme

    def upload_blob(self, ad, veri, overwrite, metadata, etag=None, match_condition=None):
        from azure.core.exceptions import ResourceExistsError, ResourceModifiedError

        self.cagrilar.append({"overwrite": overwrite, "etag": etag, "kosul": match_condition})
        if ad in self.bloblar and not overwrite:
            raise ResourceExistsError("BlobAlreadyExists")
        if etag is not None and self.bloblar.get(ad, (None, None))[1] != etag:
            raise ResourceModifiedError("ConditionNotMet")
        self.sayac += 1
        self.bloblar[ad] = (veri, f'"0x{self.sayac}"')

        class Yuklenen:
            url = f"{EtiketliKap.url}/{ad}"

        return Yuklenen()


def test_blob_yoksa_olustur_overwrite_false_ile() -> None:
    import pytest

    from yervar.depolama.ham import CakismaHatasi

    kap = EtiketliKap()
    depo = sahte_blob_depo(kap, uzerine_yaz=True)
    assert depo.oku_etiketli("o.parquet") == (None, None)
    depo.yaz_kosullu("o.parquet", b"ilk", None)
    assert kap.cagrilar[-1]["overwrite"] is False  # If-None-Match: *
    # ikinci çalıştırma da "dosya yok" görmüştü: reddedilmeli
    with pytest.raises(CakismaHatasi):
        depo.yaz_kosullu("o.parquet", b"ikinci", None)
    assert depo.oku_etiketli("o.parquet")[0] == b"ilk"


def test_blob_etag_degistiyse_reddeder() -> None:
    import pytest
    from azure.core import MatchConditions

    from yervar.depolama.ham import CakismaHatasi

    kap = EtiketliKap()
    depo = sahte_blob_depo(kap, uzerine_yaz=True)
    depo.yaz_kosullu("o.parquet", b"v1", None)
    _, etiket = depo.oku_etiketli("o.parquet")
    depo.yaz_kosullu("o.parquet", b"v2", etiket)
    assert kap.cagrilar[-1]["kosul"] == MatchConditions.IfNotModified
    with pytest.raises(CakismaHatasi):
        depo.yaz_kosullu("o.parquet", b"v3", etiket)  # eski etiket
    assert depo.oku_etiketli("o.parquet")[0] == b"v2"
