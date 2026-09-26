"""Resmi tatiller ve arifeler.

Tatil listesini elle yazmıyoruz, `holidays` kütüphanesinden alıyoruz. Dini
bayramlar her yıl kayıyor, elle tutulan liste bir gün mutlaka eskir.

Arife günleri yarım gün tatil (13:00'ten sonra). Kütüphane bunları "half_day"
kategorisinde veriyor, biz de ayrı bir sütun olarak tutuyoruz.
"""

from datetime import date

import holidays


def tatil_gunleri(yillar: list[int]) -> list[dict]:
    """Verilen yıllardaki tatil günlerini döndürür.

    Her satır: {"tarih": date, "ad": str, "yarim_gun": bool}
    """
    tam = holidays.Turkey(years=yillar)
    hepsi = holidays.Turkey(years=yillar, categories=("public", "half_day"))

    satirlar = []
    for gun, ad in sorted(hepsi.items()):
        satirlar.append({"tarih": gun, "ad": ad, "yarim_gun": gun not in tam})
    return satirlar


def takvimi_yukle(con, baslangic: date, bitis: date) -> None:
    """Tatil tablosunu DuckDB bağlantısına `takvim` adıyla ekler."""
    yillar = list(range(baslangic.year, bitis.year + 1))
    con.execute("CREATE OR REPLACE TABLE takvim (tarih DATE, ad VARCHAR, yarim_gun BOOLEAN)")
    for s in tatil_gunleri(yillar):
        con.execute("INSERT INTO takvim VALUES (?, ?, ?)", [s["tarih"], s["ad"], s["yarim_gun"]])
