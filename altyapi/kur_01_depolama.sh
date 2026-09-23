#!/usr/bin/env bash
# Adım 1 — Kaynak grubu, depolama hesabı, blob kabı ve kendi yetkin.
#
# Script idempotenttir: tekrar çalıştırmak zarar vermez, var olanı bozmaz.
# Bulut kurulumunda bu önemli bir özellik — yarıda kalırsa baştan çalıştırırsın.
#
# Çalıştırma:  bash altyapi/kur_01_depolama.sh

set -euo pipefail                       # hata olursa dur, tanımsız değişkende dur
source "$(dirname "$0")/degiskenler.sh"

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

# Veri düzlemi yetkisi: aboneliğin sahibi olmak blob OKUMAYA yetmez.
# Veriye erişim ayrı bir rolle verilir.
echo "▶ Kendine 'Storage Blob Data Contributor' rolü veriliyor"
DEPOLAMA_ID=$(az storage account show -n "$DEPOLAMA" -g "$KG" --query id -o tsv)
BEN=$(az ad signed-in-user show --query id -o tsv)
az role assignment create --role "Storage Blob Data Contributor" \
  --assignee-object-id "$BEN" --assignee-principal-type User \
  --scope "$DEPOLAMA_ID" -o none 2>/dev/null || echo "  (rol zaten var)"

echo
echo "✓ Bitti. Rolün yayılması 1-5 dakika sürebilir. Sonra sırayla:"
echo
echo "  DEPO_TURU=blob AZURE_DEPOLAMA_HESABI=$DEPOLAMA \\"
echo "    python -m yervar.toplama.toplayici --tek-tur"
echo
echo "  az storage blob list --account-name $DEPOLAMA -c $KAP \\"
echo "    --auth-mode login --query '[].name' -o tsv"
