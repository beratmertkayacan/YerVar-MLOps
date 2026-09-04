"""
ISPARK uc noktalarinin ne dondurdugunu ogrenir.
Hicbir alan adi varsaymaz - ham yaniti kaydeder ve alanlari listeler.
"""
from __future__ import annotations
import json, pathlib, sys
import httpx

TABAN = "https://api.ibb.gov.tr/ispark"
CIKTI = pathlib.Path(__file__).parent / "ornek"
CIKTI.mkdir(parents=True, exist_ok=True)


def baslik(m: str) -> None:
    print("\n" + "=" * 64 + f"\n{m}\n" + "=" * 64)


def alanlari_goster(kayit: dict, girinti: str = "  ") -> None:
    for anahtar, deger in kayit.items():
        print(f"{girinti}{anahtar:<30} {type(deger).__name__:<8} {str(deger)[:50]}")


def kaydet(ad: str, veri) -> None:
    (CIKTI / ad).write_text(
        json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    with httpx.Client(timeout=20.0, headers={"User-Agent": "yervar-kesif/0.1"}) as c:

        baslik("1) GET /Park — otopark listesi")
        y = c.get(f"{TABAN}/Park")
        print("HTTP", y.status_code, "|", y.headers.get("content-type"))
        y.raise_for_status()
        liste = y.json()
        kaydet("park_listesi.json", liste)
        print("Tip:", type(liste).__name__, "| Kayit sayisi:", len(liste))

        ilk = liste[0] if isinstance(liste, list) and liste else None
        if not isinstance(ilk, dict):
            sys.exit("Beklenmeyen yapi — kesif/ornek/park_listesi.json dosyasina bak.")
        print("\nIlk kaydin alanlari:")
        alanlari_goster(ilk)

        adaylar = [a for a in ilk if "id" in a.lower()]
        print("\nKimlik alani adaylari:", adaylar)
        if not adaylar:
            sys.exit("Kimlik alani bulunamadi.")
        park_id = ilk[adaylar[0]]

        baslik(f"2) GET /ParkDetay?id={park_id}")
        y2 = c.get(f"{TABAN}/ParkDetay", params={"id": park_id})
        print("HTTP", y2.status_code)
        y2.raise_for_status()
        detay = y2.json()
        kaydet("park_detay.json", detay)
        kayit = detay[0] if isinstance(detay, list) and detay else detay
        print("\nDetay alanlari:")
        alanlari_goster(kayit)

        baslik("3) KRITIK SORU — doluluk alani var mi?")
        for ipucu in ("bos", "empty", "free", "kapasite", "capacity", "doluluk", "occup"):
            bulunan = [a for a in kayit if ipucu in a.lower()]
            if bulunan:
                print(f"  '{ipucu}' iceren alanlar: {bulunan}")

        print("\nOrnek yanitlar: kesif/ornek/ altina yazildi.")


if __name__ == "__main__":
    main()