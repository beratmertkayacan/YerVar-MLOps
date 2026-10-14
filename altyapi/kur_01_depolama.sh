#!/usr/bin/env bash
# Adım 1 — Kaynak grubu, depolama hesabı, blob kabı ve kendi yetkin.
#
# Script idempotenttir: tekrar çalıştırmak zarar vermez, var olanı bozmaz.
# Bulut kurulumunda bu önemli bir özellik — yarıda kalırsa baştan çalıştırırsın.
#
# Çalıştırma:  bash altyapi/kur_01_depolama.sh

set -euo pipefail                       # hata olursa dur, tanımsız değişkende dur
source "$(dirname "$0")/degiskenler.sh"
source "$(dirname "$0")/ortak.sh"

echo "▶ Abonelik: $(az account show --query name -o tsv)"

# Kaynak grubu: projenin tüm kaynaklarını tutan klasör.
echo "▶ Kaynak grubu oluşturuluyor: $KG ($KONUM)"
az group create -n "$KG" -l "$KONUM" -o none

# Depolama hesabı: ham verinin bulutta duracağı yer.
#   Standard_LRS  → en ucuz dayanıklılık seviyesi, veri tek bölgede 3 kopya
#   StorageV2     → güncel nesil, blob ve diğer türleri destekler
#   TLS1_2        → eski, zayıf şifreleme sürümlerini kapatır
#   public-access → blob'ların anonim olarak okunmasını kapatır
echo "▶ Depolama hesabı oluşturuluyor: $DEPOLAMA"
az storage account create -n "$DEPOLAMA" -g "$KG" -l "$KONUM" \
  --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 \
  --allow-blob-public-access false -o none

# Blob kabı: klasör benzeri bölme. "container-rm" yönetim düzleminden çalışır,
# bu yüzden henüz veri yetkin olmadan da kabı oluşturabilirsin.
echo "▶ Blob kabı oluşturuluyor: $KAP"
az storage container-rm create --storage-account "$DEPOLAMA" -g "$KG" -n "$KAP" -o none \
  || echo "  (kap zaten var)"

# Silmeye karşı koruma. Ham veri geri gelmeyen bir veri: İSPARK geçmiş
# sunmuyor, kaybolan tur sonsuza kadar kaybolur.
#   silinen blob ve kap 14 gün boyunca geri getirilebilir (soft delete)
#   versioning açık: bir blob değişirse ya da silinirse eski hali sürüm
#   olarak kalır. Ham kapta üzerine yazma kodda zaten kapalı, orada sürüm
#   pek oluşmuyor. Sürümler daha çok tablo kabında birikiyor, çünkü tablo
#   işi aynı günü yeniden çalıştırınca dosyanın üzerine yazıyor.
echo "▶ Silme koruması ve sürümleme açılıyor"
az storage account blob-service-properties update \
  --account-name "$DEPOLAMA" -g "$KG" \
  --enable-delete-retention true --delete-retention-days 14 \
  --enable-container-delete-retention true --container-delete-retention-days 14 \
  --enable-versioning true -o none

# Sürümler sonsuza kadar birikmesin: tablo kabındaki eski sürümler 30 gün
# sonra siliniyor. Kural sadece "tablo/" önekine bakıyor; ham kaba ve
# ham/hatali/ altına bilerek kural yok, oradaki hiçbir şey kendiliğinden silinmiyor.
echo "▶ Yaşam döngüsü kuralı yükleniyor: yasam_dongusu.json"
az storage account management-policy create \
  --account-name "$DEPOLAMA" -g "$KG" \
  --policy @"$(dirname "$0")/yasam_dongusu.json" -o none

# Veri düzlemi yetkisi: aboneliğin sahibi olmak blob OKUMAYA yetmez.
# Veriye erişim ayrı bir rolle verilir.
echo "▶ Kendine 'Storage Blob Data Contributor' rolü veriliyor"
DEPOLAMA_ID=$(az storage account show -n "$DEPOLAMA" -g "$KG" --query id -o tsv)
BEN=$(az ad signed-in-user show --query id -o tsv)
rol_ver "$BEN" "Storage Blob Data Contributor" "$DEPOLAMA_ID" User

echo
echo "✓ Bitti. Rolün yayılması 1-5 dakika sürebilir. Sonra sırayla:"
echo
echo "  DEPO_TURU=blob AZURE_DEPOLAMA_HESABI=$DEPOLAMA \\"
echo "    python -m yervar.toplama.toplayici --tek-tur"
echo
echo "  az storage blob list --account-name $DEPOLAMA -c $KAP \\"
echo "    --auth-mode login --query '[].name' -o tsv"
