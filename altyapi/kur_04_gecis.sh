#!/usr/bin/env bash
# Adım 4 — Yerelden buluta geçiş: Mac'te biriken geçmişi Blob'a yükler.
#
# Ön koşul: bulut işi en az bir saattir sorunsuz çalışıyor (bash altyapi/durum.sh).
# Çalıştırma:  bash altyapi/kur_04_gecis.sh

set -euo pipefail
source "$(dirname "$0")/degiskenler.sh"

echo "== Buluttaki son çalıştırmalar =="
az containerapp job execution list -n "$IS" -g "$KG" -o table \
  --query "[:6].{ad: name, durum: properties.status, baslangic: properties.startTime}"

echo
read -r -p "Hepsi Succeeded mı? Yerel geçmiş buluta yüklensin mi? (e/h) " cevap
[ "$cevap" = "e" ] || { echo "İptal edildi."; exit 0; }

# Dosya adları UTC zaman damgalı olduğu için yerel ve bulut dosyaları çakışmaz.
# Geçiş sırasında aynı 5 dakikalık dilimde iki dosya oluşabilir; ham katman
# ekleme-yalnız olduğu için bu sorun değil, tekrarları L1 temizleme adımı ayıklar.
ADET=$(find veri/ham -name '*.json.gz' | wc -l | tr -d ' ')
echo "▶ $ADET yerel dosya yükleniyor"
az storage blob upload-batch --account-name "$DEPOLAMA" -d "$KAP" -s veri/ham \
  --pattern "*.json.gz" --auth-mode login -o none

echo
echo "✓ Yüklendi. Şimdi yerel toplayıcıyı durdur: çalıştığı terminalde Ctrl+C."
echo "  Bundan sonra tek veri kaynağı bulut işi. veri/ klasörü yedek olarak kalabilir."
