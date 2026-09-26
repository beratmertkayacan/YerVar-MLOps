"""Gün gün takvim bilgisi: resmi tatil, arife, idari izin, okul tatili.

İki kaynaktan geliyor:
  - holidays kütüphanesi: resmi tatiller ve arifeler. Dini bayramlar her yıl
    kaydığı için bunları elle yazmıyoruz.
  - ozel_donemler.csv: kütüphanenin bilmediği şeyler. İdari izinler ve okul
    tatilleri. Elle tutuluyor, açıklandıkça ekleniyor (bkz. V-009).

Arife günleri yarım gün tatil (13:00'ten sonra). Kütüphane bunları
"half_day" kategorisinde veriyor.
"""

import csv
from datetime import date, timedelta
from pathlib import Path

import holidays

OZEL_DONEMLER = Path(__file__).with_name("ozel_donemler.csv")


def tatil_gunleri(yillar: list[int]) -> list[dict]:
    """Resmi tatiller ve arifeler. Her satır: {"tarih", "ad", "yarim_gun"}"""
    tam = holidays.Turkey(years=yillar)
    hepsi = holidays.Turkey(years=yillar, categories=("public", "half_day"))
    return [
        {"tarih": gun, "ad": ad, "yarim_gun": gun not in tam}
        for gun, ad in sorted(hepsi.items())
    ]


def ozel_donemler(dosya: Path = OZEL_DONEMLER) -> list[dict]:
    """CSV'deki dönemleri okur. # ile başlayan satırlar açıklama."""
    with dosya.open(encoding="utf-8") as f:
        satirlar = [s for s in f if s.strip() and not s.startswith("#")]
    donemler = []
    for s in csv.DictReader(satirlar):
        donemler.append({
            "baslangic": date.fromisoformat(s["baslangic"]),
            "bitis": date.fromisoformat(s["bitis"]),
            "tur": s["tur"],
            "ad": s["ad"],
        })
    return donemler


def takvim_satirlari(bas: date, bit: date, donemler: list[dict] | None = None) -> list[dict]:
    """bas ile bit arasındaki her gün için bir satır, dört işaretle."""
    if donemler is None:
        donemler = ozel_donemler()
    tatiller = {t["tarih"]: t for t in tatil_gunleri(list(range(bas.year, bit.year + 1)))}

    satirlar = []
    gun = bas
    while gun <= bit:
        tatil = tatiller.get(gun)
        turler = {d["tur"] for d in donemler if d["baslangic"] <= gun <= d["bitis"]}
        satirlar.append({
            "tarih": gun,
            "resmi_tatil": tatil is not None and not tatil["yarim_gun"],
            "arife": tatil is not None and tatil["yarim_gun"],
            "idari_izin": "idari_izin" in turler,
            "okul_tatili": "okul_tatili" in turler,
        })
        gun += timedelta(days=1)
    return satirlar


def takvimi_yukle(con, bas: date, bit: date, donemler: list[dict] | None = None) -> None:
    """Takvimi DuckDB bağlantısına `takvim` tablosu olarak ekler."""
    con.execute("""
        CREATE OR REPLACE TABLE takvim (
            tarih DATE, resmi_tatil BOOLEAN, arife BOOLEAN,
            idari_izin BOOLEAN, okul_tatili BOOLEAN
        )
    """)
    for s in takvim_satirlari(bas, bit, donemler):
        con.execute(
            "INSERT INTO takvim VALUES (?, ?, ?, ?, ?)",
            [s["tarih"], s["resmi_tatil"], s["arife"], s["idari_izin"], s["okul_tatili"]],
        )
