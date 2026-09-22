"""ISPARK uc noktalarinin gercekte ne dondurdugunu ogrenir.

Projenin tum varsayimi tek bir soruya bagli: doluluk (bos yer) bilgisi geliyor mu,
ve geliyorsa LISTE ucunda mi yoksa sadece DETAY ucunda mi? Cevap toplama modunu,
gunluk istek sayisini ve dolayisiyla mimariyi belirliyor.

Bu script hicbir alan adi varsaymaz. Ham yaniti diske kaydeder, alanlari listeler
ve doluluga benzeyen alanlari isaretler.

Calistirma:
    python kesif/01_uc_nokta_dogrula.py
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import httpx

TABAN = "https://api.ibb.gov.tr/ispark"
CIKTI = pathlib.Path(__file__).parent / "ornek"
CIKTI.mkdir(parents=True, exist_ok=True)

# Bu kelimelerden birini iceren alan adi, doluluk bilgisi adayidir.
DOLULUK_IPUCLARI = (
    "bos", "empty", "free", "available", "musait",
    "kapasite", "capacity", "doluluk", "occup", "dolu",
)


def baslik(metin: str) -> None:
    print("\n" + "=" * 68)
    print(metin)
    print("=" * 68)


def alanlari_goster(kayit: dict[str, Any], girinti: str = "  ") -> None:
    """Bir kaydin tum alanlarini adi, tipi ve ornek degeriyle yazar."""
    for anahtar, deger in kayit.items():
        ornek = str(deger).replace("\n", " ")[:46]
        print(f"{girinti}{anahtar:<28} {type(deger).__name__:<8} {ornek}")


def doluluk_adaylari(kayit: dict[str, Any]) -> list[str]:
    """Doluluk bilgisi tasiyabilecek alan adlarini dondurur."""
    bulunan: list[str] = []
    for anahtar in kayit:
        kucuk = anahtar.lower()
        if any(ipucu in kucuk for ipucu in DOLULUK_IPUCLARI):
            bulunan.append(anahtar)
    return bulunan


def ilk_kayit(veri: Any) -> dict[str, Any] | None:
    """Liste ya da tek nesne olsun, ilk sozluk kaydi cikarir."""
    if isinstance(veri, list) and veri and isinstance(veri[0], dict):
        return veri[0]
    if isinstance(veri, dict):
        return veri
    return None


def kaydet(ad: str, veri: Any) -> pathlib.Path:
    yol = CIKTI / ad
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    return yol


def main() -> int:
    with httpx.Client(
        timeout=25.0,
        headers={"User-Agent": "yervar/0.1 (ogrenme projesi)", "Accept": "application/json"},
        follow_redirects=True,
    ) as istemci:

        # ------------------------------------------------------------------
        baslik("1) GET /Park  -  otopark listesi")
        try:
            yanit = istemci.get(f"{TABAN}/Park")
        except httpx.RequestError as hata:
            print(f"BAGLANTI HATASI: {hata}")
            print("Ag baglantisini ve adresi kontrol et.")
            return 1

        print(f"HTTP {yanit.status_code} | {yanit.headers.get('content-type')}")
        print(f"Yanit boyutu: {len(yanit.content) / 1024:.1f} KB")

        if yanit.status_code != 200:
            print("Beklenen 200 alinamadi. Ham govde:")
            print(yanit.text[:600])
            return 1

        try:
            liste = yanit.json()
        except ValueError:
            print("Yanit JSON degil. Ham govde:")
            print(yanit.text[:600])
            return 1

        yol = kaydet("park_listesi.json", liste)
        adet = len(liste) if isinstance(liste, list) else 1
        print(f"Tip: {type(liste).__name__} | Kayit sayisi: {adet}")
        print(f"Kaydedildi: {yol}")

        ornek = ilk_kayit(liste)
        if ornek is None:
            print("Beklenmeyen yapi; kaydedilen dosyaya bak.")
            return 1

        print("\nIlk kaydin alanlari:")
        alanlari_goster(ornek)

        liste_doluluk = doluluk_adaylari(ornek)
        print(f"\nListede doluluk adayi alanlar: {liste_doluluk or 'YOK'}")

        # ------------------------------------------------------------------
        kimlik_adaylari = [a for a in ornek if "id" in a.lower()]
        print(f"Kimlik alani adaylari: {kimlik_adaylari or 'YOK'}")
        if not kimlik_adaylari:
            print("Kimlik alani bulunamadi; detay ucu denenemiyor.")
            return 1

        kimlik_alani = kimlik_adaylari[0]
        park_kimligi = ornek[kimlik_alani]

        baslik(f"2) GET /ParkDetay?id={park_kimligi}  ({kimlik_alani} alanindan)")
        try:
            yanit2 = istemci.get(f"{TABAN}/ParkDetay", params={"id": park_kimligi})
        except httpx.RequestError as hata:
            print(f"BAGLANTI HATASI: {hata}")
            return 1

        print(f"HTTP {yanit2.status_code} | {len(yanit2.content)} bayt")
        if yanit2.status_code != 200:
            print(yanit2.text[:600])
            return 1

        try:
            detay = yanit2.json()
        except ValueError:
            print("Detay yaniti JSON degil:")
            print(yanit2.text[:600])
            return 1

        yol2 = kaydet("park_detay.json", detay)
        print(f"Kaydedildi: {yol2}")

        detay_kayit = ilk_kayit(detay)
        if detay_kayit is None:
            print("Detay yaniti beklenmeyen yapida.")
            return 1

        print("\nDetay alanlari:")
        alanlari_goster(detay_kayit)

        detay_doluluk = doluluk_adaylari(detay_kayit)
        print(f"\nDetayda doluluk adayi alanlar: {detay_doluluk or 'YOK'}")

        # ------------------------------------------------------------------
        baslik("3) KARAR")
        if liste_doluluk:
            gunluk_istek = 288
            print("Doluluk bilgisi LISTE ucunda var.")
            print("  -> TOPLAMA_MODU=liste")
            print(f"  -> Gunluk istek: ~{gunluk_istek} (5 dakikada bir, tek istek)")
            print("  -> Kapsam: tum otoparklar")
        elif detay_doluluk:
            print("Doluluk bilgisi SADECE DETAY ucunda var.")
            print("  -> TOPLAMA_MODU=detay")
            print(f"  -> Her tur icin otopark sayisi kadar istek gerekir ({adet} otopark).")
            print(f"  -> Tum otoparklar icin gunluk ~{adet * 288:,} istek - fazla agresif.")
            print("  -> Kapsami canli ve degisken otoparklarla sinirla (60-100 adet).")
            print("  -> Sonraki adim: kesif/02_canlilik_taramasi.py")
        else:
            print("Hicbir ucta doluluk alani bulunamadi.")
            print("  -> Kaydedilen JSON dosyalarini ELDE incele; alan adi")
            print("     ipucu listemizde olmayan bir sey olabilir.")
            print("  -> Bulunamazsa proje kapsamini cevirmek gerekir (bkz. risk notu).")

        print(f"\nOrnek yanitlar: {CIKTI}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
