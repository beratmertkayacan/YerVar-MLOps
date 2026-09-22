"""İSPARK uç noktalarının gerçekte ne döndürdüğünü gösterir.

Projenin temel sorusu buydu: boş yer bilgisi hangi uçta geliyor?
Sonuç (17.09.2026): liste ucu 247 otoparkı `capacity` ve `emptyCapacity`
alanlarıyla birlikte veriyor. Yani her turda tek istek yeterli.

Script örnek yanıtları kesif/ornek/ altına kaydeder. Listeden sadece ilk
3 kaydı saklıyoruz: amaç şemayı belgelemek, veriyi depoya koymak değil.

Çalıştırma:
    python kesif/01_uc_nokta_dogrula.py
"""

import json
from pathlib import Path

import httpx

TABAN = "https://api.ibb.gov.tr/ispark"
CIKTI = Path(__file__).parent / "ornek"


def kaydet(ad: str, veri: object) -> None:
    CIKTI.mkdir(exist_ok=True)
    (CIKTI / ad).write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


def alanlari_yaz(kayit: dict) -> None:
    for anahtar, deger in kayit.items():
        print(f"  {anahtar:<16} {type(deger).__name__:<6} {str(deger)[:50]}")


def main() -> None:
    with httpx.Client(timeout=25) as istemci:
        liste = istemci.get(f"{TABAN}/Park").raise_for_status().json()
        print(f"\n/Park → {len(liste)} otopark. İlk kaydın alanları:")
        alanlari_yaz(liste[0])
        kaydet("park_listesi.json", liste[:3])

        acik = sum(1 for p in liste if p.get("isOpen") == 1)
        print(f"\nAçık: {acik}, kapalı: {len(liste) - acik}")

        park_id = liste[0]["parkID"]
        detay = istemci.get(f"{TABAN}/ParkDetay", params={"id": park_id}).raise_for_status().json()
        print(f"\n/ParkDetay?id={park_id} → ek alanlar:")
        alanlari_yaz({k: v for k, v in detay[0].items() if k not in liste[0]})
        kaydet("park_detay.json", detay)

    print(f"\nÖrnek yanıtlar kaydedildi: {CIKTI}")


if __name__ == "__main__":
    main()
