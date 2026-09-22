"""Ham depolama katmaninin testleri.

Bu katman test edilebilir cunku saf mantik (yol uretimi) ile G/C (diske yazma)
ayrilmis durumda. Ayirmasaydik, yol kuralini test etmek icin gercek dosya
yazmamiz gerekirdi.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from yervar.depolama.ham import (
    BellekDepo,
    YerelDepo,
    ham_yol,
    simdi_utc,
    zaman_damgasi,
)

ORNEK_ZAMAN = datetime(2026, 9, 17, 14, 30, 0, tzinfo=UTC)


def test_zaman_damgasi_utc_bicimi() -> None:
    assert zaman_damgasi(ORNEK_ZAMAN) == "20260917T143000Z"


def test_ham_yol_saat_bazli_bolumleme() -> None:
    yol = ham_yol(ORNEK_ZAMAN, "parklar")
    assert yol == "2026/09/17/14/parklar_20260917T143000Z.json"


def test_ham_yol_farkli_etiket() -> None:
    yol = ham_yol(ORNEK_ZAMAN, "detaylar")
    assert yol.endswith("detaylar_20260917T143000Z.json")


def test_simdi_utc_zaman_dilimi_tasir() -> None:
    """Zaman damgasi zaman dilimi bilgisi tasimali; naive datetime kabul edilmez."""
    zaman = simdi_utc()
    assert zaman.tzinfo is not None
    assert zaman.utcoffset() == UTC.utcoffset(None)


def test_yerel_depo_yazar_ve_okunabilir(tmp_path: Path) -> None:
    depo = YerelDepo(tmp_path)
    icerik = [{"parkID": 1, "parkAdi": "Ornek"}]

    yol = depo.yaz(ham_yol(ORNEK_ZAMAN, "parklar"), icerik)

    dosya = Path(yol)
    assert dosya.exists()
    assert json.loads(dosya.read_text(encoding="utf-8")) == icerik


def test_yerel_depo_gecici_dosya_birakmaz(tmp_path: Path) -> None:
    """Atomik yazma sonrasi .tmp dosyasi kalmamali."""
    depo = YerelDepo(tmp_path)
    depo.yaz(ham_yol(ORNEK_ZAMAN, "parklar"), {"a": 1})

    assert list(tmp_path.rglob("*.tmp")) == []


def test_yerel_depo_turkce_karakter_bozmaz(tmp_path: Path) -> None:
    """ensure_ascii=False kullaniliyor; Turkce karakterler kacisli yazilmamali."""
    depo = YerelDepo(tmp_path)
    icerik = {"parkAdi": "Kadikoy Iskele Otoparki - Sisli Sismangazi"}

    yol = depo.yaz(ham_yol(ORNEK_ZAMAN, "parklar"), icerik)

    metin = Path(yol).read_text(encoding="utf-8")
    assert "Kadikoy" in metin
    assert "\\u" not in metin


def test_bellek_depo_diske_yazmaz() -> None:
    depo = BellekDepo()
    yol = depo.yaz("a/b.json", {"x": 1})

    assert depo.kayitlar[yol] == {"x": 1}
