"""Toplanan verinin sağlığını denetler: akış kesintisiz mi, kayıtlar tam mı,
değerler geçerli mi, sensörler canlı mı, gün içi örüntü makul mü?

Çalıştırma:
    source altyapi/degiskenler.sh
    python kesif/04_veri_kalitesi.py # buluttaki son 24 saat
    python kesif/04_veri_kalitesi.py --saat 48 # son 48 saat
    python kesif/04_veri_kalitesi.py --yerel # Mac'teki veri/ham klasörü
    python kesif/04_veri_kalitesi.py --kaynak # + İSPARK'ın kendi güncelleme zamanı

Üç ayrı soruyu cevaplar:
  1. Boru hattımız doğru mu çalışıyor? -> süreklilik, tamlık
  2. API kendi içinde tutarlı mı? -> geçerlilik
  3. API gerçeği yansıtıyor mu? -> canlılık, gün içi örüntü, kaynak tazeliği
"""

import argparse
import collections
import gzip
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ISTANBUL = timezone(timedelta(hours=3))
DAMGA = re.compile(r"_(\d{8}T\d{6}Z)\.json\.gz$")


def damga(ad: str) -> datetime:
    """Dosya adındaki UTC zaman damgasını okur."""
    return datetime.strptime(DAMGA.search(ad).group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


# --- Veri okuma ---------------------------------------------------------------

def yerelden_oku(saat: int) -> list[tuple[datetime, list]]:
    dosyalar = sorted(Path("veri/ham").rglob("*.json.gz"), key=lambda p: damga(p.name))
    if not dosyalar:
        raise SystemExit("veri/ham altında dosya yok.")
    son = damga(dosyalar[-1].name)
    secilen = [p for p in dosyalar if damga(p.name) > son - timedelta(hours=saat)]
    return [(damga(p.name), json.loads(gzip.decompress(p.read_bytes()))) for p in secilen]


def buluttan_oku(saat: int) -> list[tuple[datetime, list]]:
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import ContainerClient

    hesap = os.getenv("AZURE_DEPOLAMA_HESABI")
    if not hesap:
        raise SystemExit("AZURE_DEPOLAMA_HESABI yok. Önce: source altyapi/degiskenler.sh")
    kap = ContainerClient(f"https://{hesap}.blob.core.windows.net",
                          os.getenv("AZURE_KAP", "ham"), credential=DefaultAzureCredential())

    # Sadece ilgili günlerin klasörlerini listele: tüm kabı taramaktan çok daha ucuz.
    simdi = datetime.now(timezone.utc)
    gunler = {(simdi - timedelta(hours=h)).strftime("%Y/%m/%d/") for h in range(0, saat + 24, 24)}
    adlar = sorted(
        (b.name for g in gunler for b in kap.list_blobs(name_starts_with=g)),
        key=damga,
    )
    if not adlar:
        raise SystemExit("Bu aralıkta blob yok.")
    son = damga(adlar[-1])
    adlar = [a for a in adlar if damga(a) > son - timedelta(hours=saat)]

    print(f"{len(adlar)} blob indiriliyor", end="", flush=True)
    turlar = []
    for i, ad in enumerate(adlar):
        turlar.append((damga(ad), json.loads(gzip.decompress(kap.download_blob(ad).readall()))))
        if i % 25 == 0:
            print(".", end="", flush=True)
    print()
    return turlar


# --- Denetimler ---------------------------------------------------------------

def baslik(no: int, metin: str) -> None:
    print(f"\n[{no}] {metin}")


def denetle(turlar: list[tuple[datetime, list]]) -> list[int]:
    zamanlar = [z for z, _ in turlar]
    print(f"Tur: {len(turlar)}   {zamanlar[0].astimezone(ISTANBUL):%d.%m %H:%M} → "
          f"{zamanlar[-1].astimezone(ISTANBUL):%d.%m %H:%M} (İstanbul)")

    # 1. Süreklilik: 5 dakikalık aralıkta 7 dakikadan uzun boşluk bir tur kaçtı demektir.
    baslik(1, "Süreklilik — kaçan tur var mı?")
    beklenen = int((zamanlar[-1] - zamanlar[0]).total_seconds() / 300) + 1
    bosluklar = [(a, b) for a, b in zip(zamanlar, zamanlar[1:]) if b - a > timedelta(minutes=7)]
    print(f"    beklenen ~{beklenen} tur, gelen {len(turlar)}  (%{len(turlar) / beklenen * 100:.0f})")
    for a, b in bosluklar[:5]:
        print(f"    boşluk: {a.astimezone(ISTANBUL):%d.%m %H:%M} → "
              f"{b.astimezone(ISTANBUL):%H:%M}  ({(b - a).total_seconds() / 60:.0f} dk)")

    # 2. Tamlık: her turda aynı otoparklar gelmeli.
    baslik(2, "Tamlık — her turda tüm otoparklar geliyor mu?")
    adetler = [len(t) for _, t in turlar]
    kume = [{p["parkID"] for p in t} for _, t in turlar]
    print(f"    tur başına otopark: en az {min(adetler)}, en çok {max(adetler)}")
    print(f"    her turda olan: {len(set.intersection(*kume))}, "
          f"en az bir kez görülen: {len(set.union(*kume))}")

    # 3. Geçerlilik: boş yer 0 ile kapasite arasında olmalı.
    baslik(3, "Geçerlilik — değerler mantıklı aralıkta mı?")
    hatalar = collections.Counter()
    for _, t in turlar:
        for p in t:
            k, b = p.get("capacity"), p.get("emptyCapacity")
            if k is None or b is None:
                hatalar["eksik alan"] += 1
            elif b < 0:
                hatalar["negatif boş yer"] += 1
            elif b > k:
                hatalar["boş yer > kapasite"] += 1
    print(f"    {dict(hatalar) if hatalar else 'sorun yok'}")

    # 4. Canlılık: hiç değişmeyen bir sayı sensörden değil, sabit bir varsayılandan geliyordur.
    baslik(4, "Canlılık — hangi otoparklar gerçekten ölçülüyor?")
    seri = collections.defaultdict(list)
    bilgi = {}
    for _, t in turlar:
        for p in t:
            seri[p["parkID"]].append(p.get("emptyCapacity"))
            bilgi[p["parkID"]] = (p.get("parkName", ""), p.get("parkType", ""))
    donuk = [k for k, v in seri.items() if len(set(v)) == 1]
    canli = [k for k, v in seri.items() if len(set(v)) > 3]
    print(f"    canlı (>3 farklı değer): {len(canli)}   donuk (hiç değişmeyen): {len(donuk)}   "
          f"arada: {len(seri) - len(canli) - len(donuk)}")
    for tip in sorted({b[1] for b in bilgi.values()}):
        toplam = sum(1 for k in seri if bilgi[k][1] == tip)
        d = sum(1 for k in donuk if bilgi[k][1] == tip)
        print(f"      {tip:<16} {d:>3} / {toplam:<3} donuk")

    # 5. Makullük: sadece CANLI otoparklarla, İstanbul saatine göre ortalama doluluk.
    baslik(5, "Gün içi örüntü — canlı otoparklarda doluluk % (İstanbul saati)")
    canli_kume = set(canli)
    saatlik = collections.defaultdict(list)
    for z, t in turlar:
        k = sum(p["capacity"] for p in t if p["parkID"] in canli_kume)
        b = sum(p["emptyCapacity"] for p in t if p["parkID"] in canli_kume)
        if k:
            saatlik[z.astimezone(ISTANBUL).hour].append((k - b) / k * 100)
    for h in sorted(saatlik):
        ort = sum(saatlik[h]) / len(saatlik[h])
        print(f"    {h:02d}:00  {ort:5.1f}  {'█' * int(ort / 2)}")

    return canli, donuk, bilgi


def kaynak_tazeligi(canli: list[int], donuk: list[int], bilgi: dict) -> None:
    """İSPARK'ın kendi güncelleme zamanına bakar: liste ucunda yok, detay ucunda var."""
    import httpx

    baslik(6, "Kaynak tazeliği — İSPARK bu otoparkı en son ne zaman güncellemiş?")
    simdi = datetime.now(ISTANBUL)
    with httpx.Client(timeout=20) as istemci:
        for etiket, liste in (("canlı", canli[:3]), ("donuk", donuk[:3])):
            for k in liste:
                d = istemci.get("https://api.ibb.gov.tr/ispark/ParkDetay", params={"id": k}).json()[0]
                g = datetime.strptime(d["updateDate"], "%d.%m.%Y %H:%M:%S").replace(tzinfo=ISTANBUL)
                yas = (simdi - g).total_seconds() / 3600
                print(f"    {etiket:<6} {k:>5} {bilgi[k][0][:32]:<32} son güncelleme: "
                      f"{g:%d.%m %H:%M}  ({yas:,.1f} saat önce)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Veri kalitesi denetimi")
    ap.add_argument("--saat", type=int, default=24, help="kaç saatlik veriye bakılsın")
    ap.add_argument("--yerel", action="store_true", help="bulut yerine veri/ham klasörünü oku")
    ap.add_argument("--kaynak", action="store_true", help="İSPARK güncelleme zamanını da kontrol et")
    arg = ap.parse_args()

    turlar = yerelden_oku(arg.saat) if arg.yerel else buluttan_oku(arg.saat)
    canli, donuk, bilgi = denetle(turlar)
    if arg.kaynak:
        kaynak_tazeligi(canli, donuk, bilgi)


if __name__ == "__main__":
    main()
