#!/usr/bin/env bash
# Adım 3 — Kimlikler, Container Apps ortamı ve 5 dakikada bir çalışan iş.
#
# Kimlik tasarımı (Microsoft'un Container Apps güvenlik önerisi):
#   id-yervar-acr  kullanıcı atamalı, SADECE imaj çekme (AcrPull)
#   işin kendisi   sistem atamalı, SADECE ham kabına yazma
# Birbirinden ayrı iki kimlik: biri sızarsa diğerinin yetkisi gitmez.
# Sistem atamalı kimlik işle doğar, işle ölür; unutulmuş yetki kalmaz.
#
# İşin yazma yetkisi eskiden bütün depolama hesabına verilmişti, yani tablo
# kabına da yazabiliyordu. Artık sadece ham kabına veriliyor. Eski hesap
# düzeyindeki yetki bu script'le kendiliğinden silinmiyor; kap yetkisi
# yayıldıktan ve işin onunla yazabildiği görüldükten sonra elle kaldırılıyor:
#   bash altyapi/kur_03_is.sh --hesap-yetkisini-kaldir
#
# Çalıştırma:  bash altyapi/kur_03_is.sh
# Ön koşul: imaj kayıt defterinde olmalı (bash altyapi/kur_02_kayit.sh).
# Script idempotent: tekrar çalıştırmak güvenli.

set -euo pipefail
source "$(dirname "$0")/degiskenler.sh"
source "$(dirname "$0")/ortak.sh"

ROL="Storage Blob Data Contributor"

# ISO biçimli bir zamandan (2026-10-14T10:05:03+00:00) bu yana geçen dakika.
# Azure zamanları UTC veriyor. macOS'taki date komutu Linux'takinden farklı
# çalıştığı için hesabı python3'e yaptırıyoruz.
gecen_dakika() {
  python3 -c 'import sys, datetime as d
t = d.datetime.strptime(sys.argv[1][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=d.timezone.utc)
print(int((d.datetime.now(d.timezone.utc) - t).total_seconds() // 60))' "$1"
}

# Bugün ham kaba yazılan son turun zamanı (yoksa boş).
son_tur() {
  az storage blob list --account-name "$DEPOLAMA" -c "$KAP" \
    --prefix "$(date -u +%Y/%m/%d/)" --auth-mode login --num-results 1000 \
    --query "max_by([], &properties.lastModified).properties.lastModified" -o tsv
}

# Hesap düzeyindeki eski yetkiyi güvenli şekilde kaldırır. Adımlar:
#   a) kap yetkisi en az 30 dakikalık mı (yetkilerin yayılması zaman alıyor)
#   b) iş şu an çalışıyor mu (son 10 dakikada tur var mı)
#   c) onay
#   d) kaldır
#   e) 20 dakika boyunca yeni tur gelecek mi diye bak, gelmezse geri vermeyi öner
hesap_yetkisini_kaldir() {
  local is_asil depolama_id kap_kapsami adet olusma yas son fark kaldirma cevap i
  is_asil=$(az containerapp job show -n "$IS" -g "$KG" --query identity.principalId -o tsv)
  depolama_id=$(az storage account show -n "$DEPOLAMA" -g "$KG" --query id -o tsv)
  kap_kapsami="$depolama_id/blobServices/default/containers/$KAP"

  adet=$(az role assignment list --assignee-object-id "$is_asil" --role "$ROL" \
    --scope "$depolama_id" --fill-principal-name false --query "length(@)" -o tsv)
  if [ "$adet" = "0" ]; then
    echo "Hesap düzeyinde yetki zaten yok, yapılacak bir şey kalmadı."
    return
  fi

  # a)
  olusma=$(az role assignment list --assignee-object-id "$is_asil" --role "$ROL" \
    --scope "$kap_kapsami" --fill-principal-name false --query "[0].createdOn" -o tsv)
  if [ -z "$olusma" ]; then
    echo "HATA: ham kabında yetki yok. Önce bu script'i bayraksız çalıştır."
    exit 1
  fi
  yas=$(gecen_dakika "$olusma")
  if [ "$yas" -lt 30 ]; then
    echo "Kap yetkisi $yas dakika önce verildi. En az 30 dakika olunca tekrar dene."
    exit 1
  fi
  echo "▶ Kap yetkisi $yas dakikalık"

  # b)
  son=$(son_tur)
  if [ -z "$son" ]; then
    echo "HATA: bugün hiç tur yazılmamış. Önce işin çalıştığından emin ol (bash altyapi/durum.sh)."
    exit 1
  fi
  fark=$(gecen_dakika "$son")
  if [ "$fark" -gt 10 ]; then
    echo "HATA: son tur $fark dakika önce yazılmış. İş şu an sağlıklı görünmüyor, yetkiye dokunmuyorum."
    exit 1
  fi
  echo "▶ Son tur $fark dakika önce yazıldı"

  # c)
  read -r -p "Hesap düzeyindeki yazma yetkisi kaldırılsın mı? (e/h) " cevap
  if [ "$cevap" != "e" ]; then
    echo "İptal edildi."
    return
  fi

  # d)
  kaldirma=$(date -u +%Y-%m-%dT%H:%M:%S)
  az role assignment delete --assignee-object-id "$is_asil" --role "$ROL" --scope "$depolama_id"
  echo "▶ Kaldırıldı ($kaldirma UTC). Yeni tur bekleniyor, en fazla 20 dakika."

  # e) Zaman damgaları aynı biçimde olduğu için metin olarak karşılaştırılabiliyor.
  for i in $(seq 1 20); do
    sleep 60
    son=$(son_tur)
    if [ -n "$son" ] && [[ "${son:0:19}" > "$kaldirma" ]]; then
      echo "✓ Yetki kaldırıldıktan sonra yeni tur yazıldı: $son"
      echo "  Kesin sonuç için 1 saat sonra bir de: bash altyapi/durum.sh"
      return
    fi
    echo "  $i. dakika, henüz yeni tur yok"
  done

  echo "UYARI: 20 dakikadır yeni tur yok. Kap yetkisi çalışmıyor olabilir."
  read -r -p "Hesap düzeyindeki yetki geri verilsin mi? (e/h) " cevap
  if [ "$cevap" = "e" ]; then
    rol_ver "$is_asil" "$ROL" "$depolama_id"
  fi
}

if [ "${1:-}" = "--hesap-yetkisini-kaldir" ]; then
  hesap_yetkisini_kaldir
  exit 0
fi

imaj_hazir_mi

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
rol_ver "$ACR_KIMLIK_ASIL" AcrPull "$KAYIT_ID"

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
# Süre sınırı 240 sn: tur aralığı 5 dk, bir sonraki tur başlamadan biter.
# Azure'un yeniden deneme hakkı 0: denemeleri kod içinde, süre bütçesiyle
# yapıyoruz (TUR_SURE_BUTCESI_SN). Azure'un yeniden denemesi aynı süre
# sınırını paylaşıyordu ve 30 Eylül'de tam bu yüzden bir tur başarısız sayıldı.
#
# Ortam değişkenleri iki dalda da veriliyor: iş eskiden kurulduysa yeni
# eklenen bir ayar (EN_AZ_OTOPARK gibi) güncellemede de yerine gitsin.
# KOD_SURUMU burada yok, imajın içine derlenirken yazılıyor (Dockerfile).
AYARLAR=(DEPO_TURU=blob AZURE_DEPOLAMA_HESABI="$DEPOLAMA" AZURE_KAP="$KAP"
         EN_AZ_OTOPARK="$EN_AZ_OTOPARK")
if az containerapp job show -n "$IS" -g "$KG" -o none 2>/dev/null; then
  echo "▶ İş zaten var, imaj ve ayarlar güncelleniyor: $IMAJ"
  az containerapp job update -n "$IS" -g "$KG" --image "$IMAJ" \
    --replica-timeout 240 --replica-retry-limit 0 \
    --set-env-vars "${AYARLAR[@]}" -o none
else
  echo "▶ Zamanlanmış iş oluşturuluyor: $IS"
  az containerapp job create -n "$IS" -g "$KG" --environment "$ORTAM" \
    --trigger-type Schedule --cron-expression "*/5 * * * *" \
    --replica-timeout 240 --replica-retry-limit 0 \
    --parallelism 1 --replica-completion-count 1 \
    --cpu 0.25 --memory 0.5Gi \
    --image "$IMAJ" \
    --registry-server "$KAYIT.azurecr.io" --registry-identity "$ACR_KIMLIK_ID" \
    --mi-user-assigned "$ACR_KIMLIK_ID" --mi-system-assigned \
    --env-vars "${AYARLAR[@]}" \
    -o none
fi

# az containerapp, "--replica-retry-limit 0" değerini "verilmemiş" sayıp
# göndermiyor (0'ı boş sanıyor). Değeri genel kaynak komutuyla ayrıca yazıyoruz,
# sonra kontrol ediyoruz. 9 Ekim'de bu yüzden bulutta 1 kalmıştı.
az resource update -g "$KG" -n "$IS" --resource-type Microsoft.App/jobs \
  --set properties.configuration.replicaRetryLimit=0 -o none
DENEME=$(az containerapp job show -n "$IS" -g "$KG" \
  --query properties.configuration.replicaRetryLimit -o tsv)
[ "$DENEME" = "0" ] || { echo "HATA: yeniden deneme hakkı 0 değil ($DENEME)"; exit 1; }

# --- 4. İşin kendi kimliğine veri yetkisi -------------------------------------
# Sistem atamalı kimlik ancak iş oluştuktan sonra var olur; yetki bu yüzden sonra.
# Kapsam sadece ham kabı: iş tablo kabına yazamaz, hesabın geri kalanını göremez.
echo "▶ İşin kimliğine '$KAP' kabına yazma yetkisi"
IS_ASIL=$(az containerapp job show -n "$IS" -g "$KG" --query identity.principalId -o tsv)
rol_ver "$IS_ASIL" "$ROL" "$DEPOLAMA_ID/blobServices/default/containers/$KAP"

echo
echo " Bitti. Rollerin yayılması için ~5 dakika bekle, sonra elle bir kez başlat:"
echo "    az containerapp job start -n $IS -g $KG"
echo "  Durumu izle:"
echo "    az containerapp job execution list -n $IS -g $KG -o table \\"
echo "      --query \"[].{ad:name, durum:properties.status, baslangic:properties.startTime}\""
echo "  Eski hesap düzeyindeki yetkiyi en az 30 dakika sonra kaldır:"
echo "    bash altyapi/kur_03_is.sh --hesap-yetkisini-kaldir"
