#!/usr/bin/env bash
# Sistemin anlık durumu: iş ayakta mı, son çalıştırmalar ne oldu, veri geliyor mu.
# Çalıştırma:  bash altyapi/durum.sh

set -euo pipefail
source "$(dirname "$0")/degiskenler.sh"

echo "== İş =="
az containerapp job show -n "$IS" -g "$KG" -o table --query "{
  durum: properties.provisioningState,
  zamanlama: properties.configuration.scheduleTriggerConfig.cronExpression,
  imaj: properties.template.containers[0].image }"

echo
echo "== Son çalıştırmalar =="
az containerapp job execution list -n "$IS" -g "$KG" -o table --query "[:6].{
  ad: name, durum: properties.status, baslangic: properties.startTime }"

echo
GUN=$(date -u +%Y/%m/%d)
echo "== Bugün ($GUN) buluta yazılan blob sayısı =="
az storage blob list --account-name "$DEPOLAMA" -c "$KAP" --prefix "$GUN/" \
  --auth-mode login --num-results 1000 --query "length(@)" -o tsv
