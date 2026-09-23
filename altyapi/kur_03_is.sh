#!/usr/bin/env bash
# Adım 3 — Kimlikler, Container Apps ortamı ve 5 dakikada bir çalışan iş.
#
# Kimlik tasarımı (Microsoft'un Container Apps güvenlik önerisi):
#   id-yervar-acr  kullanıcı atamalı  → SADECE imaj çekme (AcrPull)
#   işin kendisi   sistem atamalı     → SADECE blob yazma
# Birbirinden ayrı iki kimlik: biri sızarsa diğerinin yetkisi gitmez.
# Sistem atamalı kimlik işle doğar, işle ölür; unutulmuş yetki kalmaz.
#
# Çalıştırma:  bash altyapi/kur_03_is.sh
# Script idempotent: tekrar çalıştırmak güvenli.

set -euo pipefail
source "$(dirname "$0")/degiskenler.sh"

echo "▶ Kaynak sağlayıcıları kaydediliyor (abonelik başına bir kez)"
for p in Microsoft.App Microsoft.OperationalInsights Microsoft.ManagedIdentity; do
  az provider register -n "$p" --wait -o none
done

DEPOLAMA_ID=$(az storage account show -n "$DEPOLAMA" -g "$KG" --query id -o tsv)
KAYIT_ID=$(az acr show -n "$KAYIT" -g "$KG" --query id -o tsv)

# --- 1. İmaj çekme kimliği ---------------------------------------------------
echo "▶ İmaj çekme kimliği: $KIMLIK_ACR"
az identity create -n "$KIMLIK_ACR" -g "$KG" -l "$KONUM" -o none
ACR_KIMLIK_ID=$(az identity show -n "$KIMLIK_ACR" -g "$KG" --query id -o tsv)
ACR_KIMLIK_ASIL=$(az identity show -n "$KIMLIK_ACR" -g "$KG" --query principalId -o tsv)

az role assignment create --assignee-object-id "$ACR_KIMLIK_ASIL" \
  --assignee-principal-type ServicePrincipal \
  --role AcrPull --scope "$KAYIT_ID" -o none 2>/dev/null || echo "  (AcrPull zaten var)"

# --- 2. Ortam ----------------------------------------------------------------
# Ortam, işlerin ve uygulamaların yaşadığı sınır: ortak ağ ve ortak log alanı.
# İlk oluşturmada bir Log Analytics çalışma alanı da otomatik açılır.
if az containerapp env show -n "$ORTAM" -g "$KG" -o none 2>/dev/null; then
  echo "▶ Ortam zaten var: $ORTAM"
else
  echo "▶ Container Apps ortamı oluşturuluyor: $ORTAM (3-5 dakika)"
  az containerapp env create -n "$ORTAM" -g "$KG" -l "$KONUM" -o none
fi

# --- 3. İş -------------------------------------------------------------------
if az containerapp job show -n "$IS" -g "$KG" -o none 2>/dev/null; then
  echo "▶ İş zaten var, imaj güncelleniyor: $IMAJ"
  az containerapp job update -n "$IS" -g "$KG" --image "$IMAJ" -o none
else
  echo "▶ Zamanlanmış iş oluşturuluyor: $IS"
  az containerapp job create -n "$IS" -g "$KG" --environment "$ORTAM" \
    --trigger-type Schedule --cron-expression "*/5 * * * *" \
    --replica-timeout 120 --replica-retry-limit 1 \
    --parallelism 1 --replica-completion-count 1 \
    --cpu 0.25 --memory 0.5Gi \
    --image "$IMAJ" \
    --registry-server "$KAYIT.azurecr.io" --registry-identity "$ACR_KIMLIK_ID" \
    --mi-user-assigned "$ACR_KIMLIK_ID" --mi-system-assigned \
    --env-vars DEPO_TURU=blob AZURE_DEPOLAMA_HESABI="$DEPOLAMA" AZURE_KAP="$KAP" \
    -o none
fi

# --- 4. İşin kendi kimliğine veri yetkisi -------------------------------------
# Sistem atamalı kimlik ancak iş oluştuktan sonra var olur; yetki bu yüzden sonra.
echo "▶ İşin kimliğine blob yazma yetkisi"
IS_ASIL=$(az containerapp job show -n "$IS" -g "$KG" --query identity.principalId -o tsv)
az role assignment create --assignee-object-id "$IS_ASIL" \
  --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Contributor" --scope "$DEPOLAMA_ID" -o none 2>/dev/null \
  || echo "  (rol zaten var)"

echo
echo "✓ Bitti. Rollerin yayılması için ~5 dakika bekle, sonra elle bir kez başlat:"
echo "    az containerapp job start -n $IS -g $KG"
echo "  Durumu izle:"
echo "    az containerapp job execution list -n $IS -g $KG -o table \\"
echo "      --query \"[].{ad:name, durum:properties.status, baslangic:properties.startTime}\""
