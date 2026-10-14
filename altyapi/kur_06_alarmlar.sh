#!/usr/bin/env bash
# Adım 6 — İlk alarmlar: veri gelmezse e-posta at.
#
# Dört kural var, hepsi Log Analytics'teki log satırlarını sayıyor:
#
#   alarm-toplayici-sessiz   Son 30 dakikada en az EN_AZ_OTOPARK kayıtlı hiç tur
#                            yazılmadıysa. Sebebi ne olursa olsun veri gelmiyor
#                            demek: iş durdu, imaj bozuldu, yetki gitti, İSPARK çöktü...
#                            Satırdaki sayıya da bakıyoruz: sadece birkaç otoparkla
#                            yazılmış bir tur "veri geliyor" sayılmasın.
#
#   alarm-kaynak-kesintisi   Son 30 dakikada 3'ten fazla KAYNAK_KESINTISI satırı varsa.
#                            İSPARK cevap vermiyor demek (28 Eylül'deki gibi).
#
#   alarm-kaynak-gecersiz    Son 30 dakikada 1'den fazla KAYNAK_GECERSIZ satırı varsa.
#                            İSPARK cevap veriyor ama yanıt kullanılamıyor: biçim
#                            değişmiş, kayıt sayısı düşmüş ya da istek reddediliyor
#                            (4xx). Yanıtın kendisi ham/hatali/ altında duruyor.
#
#   alarm-gece-isi           Son 26 saatte hiç GECE_BITTI yoksa (gece tablo işi
#                            çalışmadı ya da yarıda öldü) VEYA o pencerede bir
#                            GUN_HATALI ya da GUN_VERI_YOK varsa. Saatte bir bakıyor.
#
# İlk üçü toplayıcı (L0) için. İlki her şeyi yakalar ama sebebini söylemez. Diğer ikisi sebebi söyler. Sessizlik
# kesinti ya da geçersiz yanıtla birlikte gelirse sorun İSPARK'ta, tek başına
# gelirse bizde.
#
# Ön koşul: portalda "ag-yervar" adında bir eylem grubu (e-posta adresin içinde).
# Çalıştırma:  bash altyapi/kur_06_alarmlar.sh
# Tekrar çalıştırmak güvenli: kural varsa güncellenir, böylece eşik ya da sorgu
# değiştiğinde script'i yeniden çalıştırmak yetiyor.

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

# Log alarmları sadece bölgesi "Global" olan eylem gruplarıyla çalışıyor.
# Portal varsayılan olarak bir bölge (ör. eastus) seçebiliyor; önceden yakalayalım.
# (tr ile küçük harfe çeviriyoruz: macOS'taki eski bash ${x,,} bilmiyor.)
GRUP_YERI=$(az monitor action-group show -n "$EYLEM_GRUBU" -g "$KG" --query location -o tsv | tr '[:upper:]' '[:lower:]')
[ "$GRUP_YERI" = "global" ] || {
  echo "HATA: '$EYLEM_GRUBU' bölgesi '$GRUP_YERI', 'Global' olmalı. Silip Global olarak yeniden oluştur."
  exit 1
}

# Gece işi alarmı GECE_BITTI satırının yokluğuna bakıyor. Hiç böyle satır yokken
# kurulursa ilk saatte yanlış alarm verir. Önce Log Analytics'te arıyoruz; yoksa
# hiçbir kurala dokunmadan duruyoruz. (Satır, Adım 2 imajıyla gece işi bir kez
# çalışınca oluşuyor: az containerapp job start -n $IS_TABLO -g $KG)
BITTI=$(az monitor log-analytics query -w "$ALAN_KIMLIK" --timespan P2D \
  --analytics-query 'ContainerAppConsoleLogs_CL | where Log_s has "GECE_BITTI" | take 1' \
  --query "length(@)" -o tsv)
if [ "$BITTI" = "0" ]; then
  echo "HATA: son 2 günde hiç GECE_BITTI satırı yok. Önce gece işini bir kez çalıştır:"
  echo "    az containerapp job start -n $IS_TABLO -g $KG"
  exit 1
fi
echo "▶ Loglarda GECE_BITTI var, gece işi alarmı kurulabilir"

# Bir kural oluşturur. Varsa aynı değerlerle günceller.
#   $1 ad   $2 açıklama   $3 koşul   $4 sorgu   $5 önem (0 kritik ... 4 bilgi)
#   $6 sıklık (varsayılan 15m)   $7 pencere (varsayılan 30m)
# Sıklık fiyatı belirliyor: 15 dakika ve daha seyrek en ucuz kademe.
# --auto-mitigate true: kural "durumlu" (stateful). Arıza sürdükçe tekrar tekrar
# e-posta gelmiyor; bir kez "tetiklendi", koşul kalkınca bir kez "çözüldü".
kural_kur() {
  local siklik="${6:-15m}" pencere="${7:-30m}"
  if az monitor scheduled-query show -n "$1" -g "$KG" -o none 2>/dev/null; then
    echo "▶ Kural var, güncelleniyor: $1"
    az monitor scheduled-query update -n "$1" -g "$KG" \
      --description "$2" \
      --condition "$3" \
      --condition-query sorgu="$4" \
      --evaluation-frequency "$siklik" --window-size "$pencere" \
      --severity "$5" --auto-mitigate true \
      --action-groups "$GRUP_ID" \
      -o none
    return
  fi
  echo "▶ Kural oluşturuluyor: $1"
  # Pencere sıklıktan geniş: logların Log Analytics'e düşmesi birkaç dakika sürüyor.
  az monitor scheduled-query create -n "$1" -g "$KG" \
    --scopes "$ALAN_ID" \
    --description "$2" \
    --condition "$3" \
    --condition-query sorgu="$4" \
    --evaluation-frequency "$siklik" --window-size "$pencere" \
    --severity "$5" --auto-mitigate true \
    --action-groups "$GRUP_ID" \
    -o none
}

# Sorgu, "TUR_TAMAM 246 otopark kaydedildi ..." satırından sayıyı çekip
# eşikle karşılaştırıyor. Eşik degiskenler.sh'deki EN_AZ_OTOPARK.
kural_kur alarm-toplayici-sessiz \
  "Son 30 dakikada en az $EN_AZ_OTOPARK otoparklık hiç tur yazılmadı" \
  "count 'sorgu' < 1" \
  "ContainerAppConsoleLogs_CL | where Log_s has \"otopark kaydedildi\" | extend kayit = toint(extract(@\"(\d+) otopark kaydedildi\", 1, Log_s)) | where kayit >= $EN_AZ_OTOPARK" \
  1

kural_kur alarm-kaynak-kesintisi \
  "İSPARK son 30 dakikada 3'ten fazla turda cevap vermedi" \
  "count 'sorgu' > 3" \
  'ContainerAppConsoleLogs_CL | where Log_s has "KAYNAK_KESINTISI"' \
  2

# Eşik 1'den fazla: tek bir geçersiz tur (ör. elle yapılan bir deneme) e-posta
# attırmasın, üst üste gelirse haber versin.
kural_kur alarm-kaynak-gecersiz \
  "İSPARK geçersiz yanıt verdi ya da isteği reddetti (biçim değişikliği, 4xx)" \
  "count 'sorgu' > 1" \
  'ContainerAppConsoleLogs_CL | where Log_s has "KAYNAK_GECERSIZ"' \
  2

# Tek sorgu, tek satır, boyut (dimension) yok: tek zaman serisi, tek ücret.
# Sorun yoksa satır dönmüyor; sorun varsa bir satır (bitti ve sorun sayılarıyla).
# Zaman aralığını kuralın penceresi (26 saat) veriyor, sorguda ago() yok.
# 26 saat: iş her gece 00:30 UTC'de bitiyor, iki çalıştırma arası 24 saat;
# 2 saat pay logların gecikmesi ve uzun süren bir gece için.
kural_kur alarm-gece-isi \
  "Gece tablo işi 26 saattir bitmedi ya da bir günü yazamadı (GUN_HATALI, GUN_VERI_YOK)" \
  "count 'sorgu' > 0" \
  'let bitti = toscalar(ContainerAppConsoleLogs_CL | where Log_s has "GECE_BITTI" | count); let sorun = toscalar(ContainerAppConsoleLogs_CL | where Log_s has "GUN_HATALI" or Log_s has "GUN_VERI_YOK" | count); print gece_bitti = bitti, gun_sorunu = sorun | where gece_bitti == 0 or gun_sorunu > 0' \
  1 1h 26h

echo
echo "✓ Bitti. Kurallar:"
az monitor scheduled-query list -g "$KG" -o table \
  --query "[].{ad:name, acik:enabled, onem:severity, siklik:evaluationFrequency, pencere:windowSize}"
