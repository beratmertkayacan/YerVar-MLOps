#!/usr/bin/env bash
# Adım 6 — İlk alarmlar: veri gelmezse e-posta at.
#
# İki kural var, ikisi de Log Analytics'teki log satırlarını sayıyor:
#
#   alarm-toplayici-sessiz   Son 30 dakikada hiç "otopark kaydedildi" satırı yoksa.
#                            Sebebi ne olursa olsun veri gelmiyor demek: iş durdu,
#                            imaj bozuldu, yetki gitti, İSPARK çöktü...
#
#   alarm-kaynak-kesintisi   Son 30 dakikada 3'ten fazla KAYNAK_KESINTISI satırı varsa.
#                            İSPARK cevap vermiyor demek (28 Eylül'deki gibi).
#
# İlki her şeyi yakalar ama sebebini söylemez. İkincisi sebebi söyler. İkisi
# birlikte gelirse sorun İSPARK'ta, sadece ilki gelirse bizde.
#
# Ön koşul: portalda "ag-yervar" adında bir eylem grubu (e-posta adresin içinde).
# Çalıştırma:  bash altyapi/kur_06_alarmlar.sh
# Tekrar çalıştırmak güvenli: var olan kurala dokunmaz.

set -euo pipefail
source "$(dirname "$0")/degiskenler.sh"

# Alarmlar ve eylem grupları Microsoft.Insights servisine ait. Abonelikte bu
# servis kayıtlı değilse hiçbiri oluşturulamıyor (10 Ekim'de portalda bu hatayı
# aldık). Kayıt abonelik başına bir kez yapılır, tekrar çalıştırmak zararsız.
echo "▶ Kaynak sağlayıcısı kaydediliyor: Microsoft.Insights (1-2 dakika sürebilir)"
az provider register -n Microsoft.Insights --wait -o none

# Log Analytics çalışma alanını bul. Ortam bize sadece kimliğini (customerId)
# veriyor, kural ise tam adresini (resource id) istiyor.
ALAN_KIMLIK=$(az containerapp env show -n "$ORTAM" -g "$KG" \
  --query properties.appLogsConfiguration.logAnalyticsConfiguration.customerId -o tsv)
ALAN_ID=$(az monitor log-analytics workspace list \
  --query "[?customerId=='$ALAN_KIMLIK'].id | [0]" -o tsv)
[ -n "$ALAN_ID" ] || { echo "HATA: çalışma alanı bulunamadı"; exit 1; }
echo "▶ Çalışma alanı: $ALAN_ID"

GRUP_ID=$(az monitor action-group show -n "$EYLEM_GRUBU" -g "$KG" --query id -o tsv 2>/dev/null) || {
  echo "HATA: '$EYLEM_GRUBU' eylem grubu yok. Önce portalda oluştur."; exit 1;
}

# Bir kural oluşturur. Varsa dokunmaz.
#   $1 ad   $2 açıklama   $3 koşul   $4 sorgu   $5 önem (0 kritik ... 4 bilgi)
kural_kur() {
  if az monitor scheduled-query show -n "$1" -g "$KG" -o none 2>/dev/null; then
    echo "▶ Kural zaten var: $1"
    return
  fi
  echo "▶ Kural oluşturuluyor: $1"
  # Her 15 dakikada bir son 30 dakikaya bakar. Logların Log Analytics'e
  # düşmesi birkaç dakika sürüyor, bu yüzden pencereyi geniş tuttuk.
  az monitor scheduled-query create -n "$1" -g "$KG" \
    --scopes "$ALAN_ID" \
    --description "$2" \
    --condition "$3" \
    --condition-query sorgu="$4" \
    --evaluation-frequency 15m --window-size 30m \
    --severity "$5" \
    --action-groups "$GRUP_ID" \
    -o none
}

kural_kur alarm-toplayici-sessiz \
  "Son 30 dakikada hiç otopark verisi yazılmadı" \
  "count 'sorgu' < 1" \
  'ContainerAppConsoleLogs_CL | where Log_s has "otopark kaydedildi"' \
  1

kural_kur alarm-kaynak-kesintisi \
  "İSPARK son 30 dakikada 3'ten fazla turda cevap vermedi" \
  "count 'sorgu' > 3" \
  'ContainerAppConsoleLogs_CL | where Log_s has "KAYNAK_KESINTISI"' \
  2

echo
echo "✓ Bitti. Kurallar:"
az monitor scheduled-query list -g "$KG" -o table \
  --query "[].{ad:name, acik:enabled, onem:severity, siklik:evaluationFrequency}"
