# kur_01, kur_02, kur_03 ve kur_05'in ortak kullandığı küçük yardımcılar.
# Tek başına çalıştırılmaz, script'lerin başında degiskenler.sh'den sonra
# source edilir:  source "$(dirname "$0")/ortak.sh"

# Etiket kayıt defterinde var mı? (yoksa sessizce başarısız döner)
imaj_var_mi() {
  az acr repository show -n "$KAYIT" --image "yervar:$KOD_SURUMU" -o none 2>/dev/null
}

# İşi kuran script'lerin ön koşulu: etiket üretilmiş ve imaj gönderilmiş olmalı.
# Yoksa iş, kayıt defterinde olmayan bir imajı çekmeye çalışıp her turda düşer.
imaj_hazir_mi() {
  if [ -z "$IMAJ" ]; then
    echo "HATA: IMAJ boş. Script'i repo klasöründen çalıştır."
    exit 1
  fi
  if ! imaj_var_mi; then
    echo "HATA: $IMAJ kayıt defterinde yok. Önce: bash altyapi/kur_02_kayit.sh"
    exit 1
  fi
}

# Bir kimliğe rol verir. Önce bakar, aynı rol aynı kapsamda zaten varsa
# dokunmaz. Atama başarısız olursa script durur. Eskiden her hata
# "rol zaten var" diye yutuluyordu, gerçek bir yetki hatası da gizleniyordu.
#   $1 kimliğin principalId'si   $2 rol adı   $3 kapsam (scope)
#   $4 kimlik türü, verilmezse ServicePrincipal (işler ve yönetilen kimlikler).
#      Kendi kullanıcın için User.
rol_ver() {
  local adet
  adet=$(az role assignment list --assignee-object-id "$1" --role "$2" --scope "$3" \
    --fill-principal-name false --query "length(@)" -o tsv)
  if [ "$adet" != "0" ]; then
    echo "  ($2 zaten var)"
    return
  fi
  az role assignment create --assignee-object-id "$1" \
    --assignee-principal-type "${4:-ServicePrincipal}" \
    --role "$2" --scope "$3" -o none
  echo "  ($2 verildi)"
}
