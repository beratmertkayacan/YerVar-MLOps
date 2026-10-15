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

# Geçersiz yanıtlar ayrı bir önekte tutuluyor (ham/hatali/). Normalde 0 olmalı.
echo
echo "== Bugün saklanan geçersiz yanıt sayısı (hatali/$GUN/) =="
az storage blob list --account-name "$DEPOLAMA" -c "$KAP" --prefix "hatali/$GUN/" \
  --auth-mode login --num-results 1000 --query "length(@)" -o tsv

# Gece işi her günün özetini doluluk dosyasının meta verisine de yazıyor (Adım 2).
# Dosyayı indirmeden okuyoruz. Tamlık %95'in altındaysa o gün GUN_EKSIK.
echo
echo "== Tablo kabındaki son 3 günün özeti =="
SON_GUNLER=$(az storage blob list --account-name "$DEPOLAMA" -c "$TABLO_KAP" --prefix "doluluk/" \
  --auth-mode login --query "[].name" -o tsv | tail -3)
# Meta verisi olmayan alan az'de "None" olarak geliyor; tabloda "-" yazıyoruz.
deger() { if [ -z "$1" ] || [ "$1" = "None" ]; then echo "-"; else echo "$1"; fi; }
printf "%-12s %8s %14s %7s %14s  %s\n" tarih tamlik canli_otopark hatali atlanan_dosya surum
for ad in $SON_GUNLER; do
  # Çift köşeli parantez: tsv tek satır versin. Tek liste her değeri ayrı satıra
  # yazıyordu ve sadece ilk değer (tarih) okunuyordu.
  az storage blob metadata show --account-name "$DEPOLAMA" -c "$TABLO_KAP" -n "$ad" \
    --auth-mode login -o tsv \
    --query "[[tarih, tamlik, canli_otopark, hatali, atlanan_dosya, surum]]" \
    2>/dev/null | {
      IFS=$'\t' read -r tarih tamlik canli hatali atlanan surum || true
      [ "$(deger "$surum")" = "-" ] && surum="(özet yok)"
      printf "%-12s %8s %14s %7s %14s  %s\n" "$(deger "${tarih:-$ad}")" "$(deger "$tamlik")" \
        "$(deger "$canli")" "$(deger "$hatali")" "$(deger "$atlanan")" "$surum"
    }
done
