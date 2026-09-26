#!/usr/bin/env bash
# Adım 2 — Konteyner kayıt defteri oluştur ve imajı buluta gönder.
#
# Çalıştırma: bash altyapi/kur_02_kayit.sh
# Ön koşul: Docker Desktop açık olmalı (docker info çalışmalı)

set -euo pipefail
source "$(dirname "$0")/degiskenler.sh"

docker info >/dev/null 2>&1 || {
  echo "Docker çalışmıyor. Önce: open -a Docker"; exit 1;
}

# Kayıt defteri: imajların bulut deposu. Basic en küçük katman, 10 GB dahil.
if az acr show -n "$KAYIT" -g "$KG" -o none 2>/dev/null; then
  echo "▶ Kayıt defteri zaten var: $KAYIT"
else
  echo "▶ Kayıt defteri oluşturuluyor: $KAYIT"
  az acr create -n "$KAYIT" -g "$KG" -l "$KONUM" --sku Basic -o none
fi

# Docker'ın kayıt defterine giriş yapması. Parola yok: az oturumundan token alır.
echo "▶ Docker, kayıt defterine bağlanıyor"
az acr login -n "$KAYIT"

# --platform linux/amd64 ZORUNLU: Mac arm64 üretir, Azure amd64 çalıştırır.
#   Bu bayrak olmadan imaj yüklenir ama iş "exec format error" ile çöker.
# --provenance=false: buildx varsayılan olarak imajın yanına bir "attestation"
#   katmanı ekleyip çok mimarili bir manifest listesi üretiyor. Bazı çalışma
#   ortamları bu listeyi çözemiyor. Tek mimarili sade bir imaj daha güvenli.
echo "▶ İmaj derleniyor ve gönderiliyor: $IMAJ"
docker buildx build --platform linux/amd64 --provenance=false -t "$IMAJ" --push .

echo
echo "✓ Kayıt defterindeki etiketler:"
az acr repository show-tags -n "$KAYIT" --repository yervar -o table
