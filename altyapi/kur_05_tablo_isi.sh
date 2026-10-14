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
# tablo.py dünü ve son 7 günde eksik kalanları işliyor (Adım 2).
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
source "$(dirname "$0")/ortak.sh"

imaj_hazir_mi

DEPOLAMA_ID=$(az storage account show -n "$DEPOLAMA" -g "$KG" --query id -o tsv)
ACR_KIMLIK_ID=$(az identity show -n "$KIMLIK_ACR" -g "$KG" --query id -o tsv)

#  1. Tablo kabı 
echo "▶ Blob kabı: $TABLO_KAP"
az storage container-rm create --storage-account "$DEPOLAMA" -g "$KG" -n "$TABLO_KAP" \
  -o none 2>/dev/null || echo "  (kap zaten var)"

#  2. İş 
# Süre sınırı 1800 sn: kod 1200 sn'den sonra yeni bir güne başlamıyor
# (TABLO_SURE_BUTCESI_SN), başlamış günü bitirmek için 600 sn pay kalıyor.
# Bir gün buluttan yaklaşık 20 sn sürüyor; normal gece 1-2 dakika.
# Azure'un yeniden denemesi 0: kaçan gün ertesi gece kendiliğinden işleniyor,
# Azure'un denemesi ise bütün günleri baştan alıp süreyi ikiye katlıyordu.
#
# Ayarlar iki dalda da veriliyor (kur_03'teki gibi): iş eskiden kurulduysa yeni
# ayarlar güncellemede de yerine gitsin. Değerler ayarlar.py'deki
# varsayılanlarla aynı; bulutta birini değiştirmek için burayı değiştir.
# KOD_SURUMU burada yok, imajın içine derlenirken yazılıyor (Dockerfile).
AYARLAR=(DEPO_TURU=blob AZURE_DEPOLAMA_HESABI="$DEPOLAMA" AZURE_KAP="$KAP"
         TABLO_KAP="$TABLO_KAP"
         ATLANAN_DOSYA_ORANI_EN_FAZLA=0.05 TAMAMLAMA_GUN=7 EN_FAZLA_GUN=4
         TABLO_SURE_BUTCESI_SN=1200 GUN_EKSIK_ESIGI=95)
if az containerapp job show -n "$IS_TABLO" -g "$KG" -o none 2>/dev/null; then
  echo "▶ İş zaten var, imaj ve ayarlar güncelleniyor: $IMAJ"
  az containerapp job update -n "$IS_TABLO" -g "$KG" --image "$IMAJ" \
    --replica-timeout 1800 --replica-retry-limit 0 \
    --set-env-vars "${AYARLAR[@]}" -o none
else
  echo "▶ Gece işi oluşturuluyor: $IS_TABLO"
  # Kaynaklar: günlük yaklaşık 70 bin satır, DuckDB ile 1-2 saniyelik iş. 0.5 CPU / 1 GB bol bol yeter. İş dakikalar içinde bitiyor, ücret sadece çalıştığı süre için.
  az containerapp job create -n "$IS_TABLO" -g "$KG" --environment "$ORTAM" \
    --trigger-type Schedule --cron-expression "30 0 * * *" \
    --replica-timeout 1800 --replica-retry-limit 0 \
    --parallelism 1 --replica-completion-count 1 \
    --cpu 0.5 --memory 1Gi \
    --image "$IMAJ" --args "yervar.depolama.tablo" \
    --registry-server "$KAYIT.azurecr.io" --registry-identity "$ACR_KIMLIK_ID" \
    --mi-user-assigned "$ACR_KIMLIK_ID" --mi-system-assigned \
    --env-vars "${AYARLAR[@]}" \
    -o none
fi

# az containerapp, "--replica-retry-limit 0" değerini "verilmemiş" sayıp
# göndermiyor (kur_03'te 9 Ekim'de yaşandı). Değeri genel kaynak komutuyla
# ayrıca yazıyoruz, sonra ikisini de geri okuyup kontrol ediyoruz.
az resource update -g "$KG" -n "$IS_TABLO" --resource-type Microsoft.App/jobs \
  --set properties.configuration.replicaRetryLimit=0 -o none
DENEME=$(az containerapp job show -n "$IS_TABLO" -g "$KG" \
  --query properties.configuration.replicaRetryLimit -o tsv)
SURE=$(az containerapp job show -n "$IS_TABLO" -g "$KG" \
  --query properties.configuration.replicaTimeout -o tsv)
[ "$DENEME" = "0" ] || { echo "HATA: yeniden deneme hakkı 0 değil ($DENEME)"; exit 1; }
[ "$SURE" = "1800" ] || { echo "HATA: süre sınırı 1800 değil ($SURE)"; exit 1; }
echo "  (süre sınırı $SURE sn, yeniden deneme $DENEME)"

#  3. Kap düzeyinde yetkiler 
# Kapsam (scope) bir kaynağın adresi. Hesap yerine kabın adresini verince yetki sadece o kapla sınırlı kalıyor.
IS_ASIL=$(az containerapp job show -n "$IS_TABLO" -g "$KG" --query identity.principalId -o tsv)

echo "▶ '$KAP' kabına okuma yetkisi"
rol_ver "$IS_ASIL" "Storage Blob Data Reader" "$DEPOLAMA_ID/blobServices/default/containers/$KAP"

echo "▶ '$TABLO_KAP' kabına yazma yetkisi"
rol_ver "$IS_ASIL" "Storage Blob Data Contributor" "$DEPOLAMA_ID/blobServices/default/containers/$TABLO_KAP"

echo
echo "✓ Bitti. Rollerin yayılması için ~5 dakika bekle, sonra gece beklemeden bir kez elle çalıştır:"
echo "    az containerapp job start -n $IS_TABLO -g $KG"
echo "  Durumu izle:"
echo "    bash altyapi/durum.sh"
