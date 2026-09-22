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
