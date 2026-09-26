#!/usr/bin/env bash
# Sistemin anlık durumu: iş ayakta mı, son çalıştırmalar ne oldu, veri geliyor mu.
# Çalıştırma:  bash altyapi/durum.sh

set -euo pipefail
source "$(dirname "$0")/degiskenler.sh"

for ad in "$IS" "$IS_TABLO"; do
  echo "== İş: $ad =="
  az containerapp job show -n "$ad" -g "$KG" -o table --query "{
    durum: properties.provisioningState,
    zamanlama: properties.configuration.scheduleTriggerConfig.cronExpression,
    imaj: properties.template.containers[0].image }" 2>/dev/null || echo "  (iş yok)"
  echo "-- son çalıştırmalar"
  az containerapp job execution list -n "$ad" -g "$KG" -o table --query "[:4].{
    ad: name, durum: properties.status, baslangic: properties.startTime }" 2>/dev/null || true
  echo
done

GUN=$(date -u +%Y/%m/%d)
echo "== Bugün ($GUN) buluta yazılan blob sayısı =="
az storage blob list --account-name "$DEPOLAMA" -c "$KAP" --prefix "$GUN/" \
  --auth-mode login --num-results 1000 --query "length(@)" -o tsv

echo
echo "== Tablo kabındaki son 3 gün =="
az storage blob list --account-name "$DEPOLAMA" -c "$TABLO_KAP" --prefix "doluluk/" \
  --auth-mode login --query "[].name" -o tsv 2>/dev/null | tail -3 || echo "  (tablo kabı yok)"
