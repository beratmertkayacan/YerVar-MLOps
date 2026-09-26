#!/usr/bin/env bash
# Adım 5 — L1 tablo işi: her gece bir önceki günü tabloya çevirir.
#
# Toplayıcıyla AYNI imajı kullanıyor, sadece çalıştırdığı modül farklı:
#   toplayıcı  -> python -m yervar.toplama.toplayici --tek-tur   (imajın varsayılanı)
#   tablo işi  -> python -m yervar.depolama.tablo                (--args ile)
# Tek imaj demek tek sürüm demek: iki iş hep aynı kodla çalışır.
#
# Zamanlama: her gün 00:30 UTC (İstanbul 03:30). Gün 00:00 UTC'de bitiyor,
# son tur 23:55'te geliyor; 30 dakika pay bırakıyoruz. Argüman verilmeyince
# tablo.py zaten "dün (UTC)" günü işliyor.
#
# Yetki (en az yetki ilkesi): bu işin kimliği bütün depolama hesabına değil,
# sadece ihtiyaç duyduğu kaplara yetkili:
#   ham -> Storage Blob Data Reader       (sadece okur, ham veriyi bozamaz)
#   tablo -> Storage Blob Data Contributor  (tabloları yazar)
#
# Ön koşul: imaj kayıt defterinde olmalı (bash altyapi/kur_02_kayit.sh).
# Çalıştırma:  bash altyapi/kur_05_tablo_isi.sh
# Script idempotent: tekrar çalıştırmak güvenli.

set -euo pipefail
source "$(dirname "$0")/degiskenler.sh"

DEPOLAMA_ID=$(az storage account show -n "$DEPOLAMA" -g "$KG" --query id -o tsv)
ACR_KIMLIK_ID=$(az identity show -n "$KIMLIK_ACR" -g "$KG" --query id -o tsv)

#  1. Tablo kabı 
echo "▶ Blob kabı: $TABLO_KAP"
az storage container-rm create --storage-account "$DEPOLAMA" -g "$KG" -n "$TABLO_KAP" \
  -o none 2>/dev/null || echo "  (kap zaten var)"

#  2. İş 
if az containerapp job show -n "$IS_TABLO" -g "$KG" -o none 2>/dev/null; then
  echo "▶ İş zaten var, imaj güncelleniyor: $IMAJ"
  az containerapp job update -n "$IS_TABLO" -g "$KG" --image "$IMAJ" -o none
else
  echo "▶ Gece işi oluşturuluyor: $IS_TABLO"
  # Kaynaklar: günlük yaklaşık 70 bin satır, DuckDB ile 1-2 saniyelik iş. 0.5 CPU / 1 GB bol bol yeter. İş dakikalar içinde bitiyor, ücret sadece çalıştığı süre için.
  # replica-timeout 600: 10 dakikada bitmezse bir şey ters gitmiş demektir.
  az containerapp job create -n "$IS_TABLO" -g "$KG" --environment "$ORTAM" \
    --trigger-type Schedule --cron-expression "30 0 * * *" \
    --replica-timeout 600 --replica-retry-limit 1 \
    --parallelism 1 --replica-completion-count 1 \
    --cpu 0.5 --memory 1Gi \
    --image "$IMAJ" --args "yervar.depolama.tablo" \
    --registry-server "$KAYIT.azurecr.io" --registry-identity "$ACR_KIMLIK_ID" \
    --mi-user-assigned "$ACR_KIMLIK_ID" --mi-system-assigned \
    --env-vars DEPO_TURU=blob AZURE_DEPOLAMA_HESABI="$DEPOLAMA" \
               AZURE_KAP="$KAP" TABLO_KAP="$TABLO_KAP" \
    -o none
fi

#  3. Kap düzeyinde yetkiler 
# Kapsam (scope) bir kaynağın adresi. Hesap yerine kabın adresini verince yetki sadece o kapla sınırlı kalıyor.
IS_ASIL=$(az containerapp job show -n "$IS_TABLO" -g "$KG" --query identity.principalId -o tsv)

echo "▶ '$KAP' kabına okuma yetkisi"
az role assignment create --assignee-object-id "$IS_ASIL" \
  --assignee-principal-type ServicePrincipal --role "Storage Blob Data Reader" \
  --scope "$DEPOLAMA_ID/blobServices/default/containers/$KAP" -o none 2>/dev/null \
  || echo "  (rol zaten var)"

echo "▶ '$TABLO_KAP' kabına yazma yetkisi"
az role assignment create --assignee-object-id "$IS_ASIL" \
  --assignee-principal-type ServicePrincipal --role "Storage Blob Data Contributor" \
  --scope "$DEPOLAMA_ID/blobServices/default/containers/$TABLO_KAP" -o none 2>/dev/null \
  || echo "  (rol zaten var)"

echo
echo "✓ Bitti. Rollerin yayılması için ~5 dakika bekle, sonra gece beklemeden bir kez elle çalıştır:"
echo "    az containerapp job start -n $IS_TABLO -g $KG"
echo "  Durumu izle:"
echo "    bash altyapi/durum.sh"
