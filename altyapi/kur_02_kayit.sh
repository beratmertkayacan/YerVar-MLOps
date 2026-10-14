#!/usr/bin/env bash
# Adım 2 — Konteyner kayıt defteri oluştur ve imajı buluta gönder.
#
# İmaj etiketi sürüm ve commit'ten oluşuyor (degiskenler.sh), ör. 0.6-890478c.
# Bu yüzden derlemeden önce iki şeye bakılıyor:
#   imaja giren dosyalarda commit'lenmemiş değişiklik olmamalı, yoksa etiket
#   imajın içindeki kodu doğru göstermez
#   aynı etiket kayıt defterinde varsa tekrar derlenmez (--zorla ile derlenir)
#
# Çalıştırma: bash altyapi/kur_02_kayit.sh [--zorla]
# Ön koşul: Docker Desktop açık olmalı (docker info çalışmalı)

set -euo pipefail
source "$(dirname "$0")/degiskenler.sh"
source "$(dirname "$0")/ortak.sh"

ZORLA=0
if [ "${1:-}" = "--zorla" ]; then
  ZORLA=1
fi

if [ -z "$IMAJ" ]; then
  echo "HATA: IMAJ boş. Script'i repo klasöründen çalıştır."
  exit 1
fi

KIRLI=$(git -C "$KOK" status --porcelain --untracked-files=all -- "${YOLLAR[@]}")
if [ -n "$KIRLI" ]; then
  echo "HATA: imaja giren dosyalarda commit'lenmemiş değişiklik var:"
  echo "$KIRLI"
  echo "Etiket son commit'i gösterdiği için önce commit'le."
  exit 1
fi

# Commit GitHub'a gönderilmemişse imaj, kimsenin göremediği bir kodu gösterir.
# Durdurmuyoruz, sadece uyarıyoruz. (origin/main bilgisi son git fetch'e göre.)
if ! git -C "$KOK" merge-base --is-ancestor "$KOMIT" origin/main 2>/dev/null; then
  echo "UYARI: $KOMIT origin/main'de görünmüyor. Push ettin mi? (git fetch ile tazele)"
fi

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

if imaj_var_mi && [ "$ZORLA" = "0" ]; then
  echo "▶ $IMAJ zaten kayıt defterinde, derleme atlandı (yeniden derlemek için --zorla)"
  exit 0
fi

# Docker'ın kayıt defterine giriş yapması. Parola yok: az oturumundan token alır.
echo "▶ Docker, kayıt defterine bağlanıyor"
az acr login -n "$KAYIT"

# --platform linux/amd64 ZORUNLU: Mac arm64 üretir, Azure amd64 çalıştırır.
#   Bu bayrak olmadan imaj yüklenir ama iş "exec format error" ile çöker.
# --provenance=false: buildx varsayılan olarak imajın yanına bir "attestation"
#   katmanı ekleyip çok mimarili bir manifest listesi üretiyor. Bazı çalışma
#   ortamları bu listeyi çözemiyor. Tek mimarili sade bir imaj daha güvenli.
# --build-arg KOD_SURUMU: etiket imajın içine de yazılıyor, loglarda surum=
#   alanı bu değeri gösteriyor.
echo "▶ İmaj derleniyor ve gönderiliyor: $IMAJ"
docker buildx build --platform linux/amd64 --provenance=false \
  --build-arg KOD_SURUMU="$KOD_SURUMU" -t "$IMAJ" --push "$KOK"

echo
echo "✓ Kayıt defterindeki etiketler:"
az acr repository show-tags -n "$KAYIT" --repository yervar -o table
