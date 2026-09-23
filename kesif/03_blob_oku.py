"""Buluttaki ham veriyi satır satır gösterir.

Blob'lar gzip'lenmiş JSON olduğu için portalda çift tıklayıp okunamıyor.
Bu script en son blob'u indirir, açar ve tablo halinde yazar.

Çalıştırma:
    python kesif/03_blob_oku.py            # en son blob, ilk 15 otopark
    python kesif/03_blob_oku.py --adet 50  # ilk 50 otopark
    python kesif/03_blob_oku.py --liste    # sadece blob'ları listele
"""

import argparse
import gzip
import json

from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient

from yervar import ayarlar


def kap_baglan() -> ContainerClient:
    """Blob kabına, parolasız kimlikle bağlanır."""
    if not ayarlar.AZURE_DEPOLAMA_HESABI:
        raise SystemExit("AZURE_DEPOLAMA_HESABI ayarlanmamış. Önce: source altyapi/degiskenler.sh")
    return ContainerClient(
        account_url=f"https://{ayarlar.AZURE_DEPOLAMA_HESABI}.blob.core.windows.net",
        container_name=ayarlar.AZURE_KAP,
        credential=DefaultAzureCredential(),
    )


def main() -> None:
    ayristirici = argparse.ArgumentParser(description="Buluttaki ham veriyi göster")
    ayristirici.add_argument("--adet", type=int, default=15, help="kaç otopark gösterilsin")
    ayristirici.add_argument("--liste", action="store_true", help="sadece blob adlarını yaz")
    arg = ayristirici.parse_args()

    kap = kap_baglan()

    # Blob adları zaman damgalı olduğu için alfabetik sıralama = zaman sırası.
    # UTC ve sabit genişlikli biçim seçmemizin bir faydası da bu.
    bloblar = sorted(b.name for b in kap.list_blobs())
    if not bloblar:
        raise SystemExit("Kapta hiç blob yok.")

    if arg.liste:
        for ad in bloblar:
            print(ad)
        print(f"\nToplam {len(bloblar)} blob")
        return

    son = bloblar[-1]
    ham = kap.download_blob(son).readall()
    parklar = json.loads(gzip.decompress(ham).decode("utf-8"))

    print(f"Blob   : {son}")
    print(f"Boyut  : {len(ham) / 1024:.1f} KB sıkıştırılmış")
    print(f"Kayıt  : {len(parklar)} otopark\n")

    print(f"{'ID':>6}  {'İLÇE':<14} {'OTOPARK':<34} {'KAP':>6} {'BOŞ':>6} {'DOLU%':>6}")
    print("-" * 78)
    for p in parklar[: arg.adet]:
        kapasite = p.get("capacity") or 0
        bos = p.get("emptyCapacity") or 0
        oran = (kapasite - bos) / kapasite * 100 if kapasite else 0
        print(
            f"{p.get('parkID', ''):>6}  {p.get('district', '')[:14]:<14} "
            f"{p.get('parkName', '')[:34]:<34} {kapasite:>6} {bos:>6} {oran:>5.0f}%"
        )

    toplam_kap = sum(p.get("capacity") or 0 for p in parklar)
    toplam_bos = sum(p.get("emptyCapacity") or 0 for p in parklar)
    print("-" * 78)
    print(f"İstanbul geneli: {toplam_kap:,} kapasite, {toplam_bos:,} boş, "
          f"%{(toplam_kap - toplam_bos) / toplam_kap * 100:.0f} dolu")


if __name__ == "__main__":
    main()
