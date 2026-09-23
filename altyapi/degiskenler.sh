# Azure kaynak adları ve abonelik. Her yeni terminalde:
#   source altyapi/degiskenler.sh
# Sır içermez; kaynak adları ve abonelik kimliği gizli bilgi değildir.

# Doğru aboneliğe geç. Bu satır olmadan yanlış abonelikte kaynak açma riski var.
export ABONELIK=f07a2594-dfeb-44f2-a24d-6268c1780f31
az account set --subscription "$ABONELIK" 2>/dev/null || true

export KG=rg-yervar                 # kaynak grubu
export KONUM=westeurope             # bölge
export SONEK=bmk01                  # küresel olarak benzersiz olması gereken adlar için

export DEPOLAMA=styervar$SONEK      # depolama hesabı (3-24 karakter, küçük harf ve rakam)
export KAP=ham                      # blob kabı
export KAYIT=acryervar$SONEK        # konteyner kayıt defteri
export KIMLIK=id-yervar             # yönetilen kimlik
export ORTAM=cae-yervar             # Container Apps ortamı
export IS=job-yervar-toplayici      # zamanlanmış iş

export SURUM=0.2
export IMAJ=$KAYIT.azurecr.io/yervar-toplayici:$SURUM

# --- Python uygulamasının okuduğu isimler ---
# Yukarıdaki kısa adlar az komutları için. Uygulama ise .env'deki adları okuyor.
# Aynı değeri iki isimle taşımak yerine burada eşliyoruz: tek doğru kaynak kalıyor.
export AZURE_DEPOLAMA_HESABI=$DEPOLAMA
export AZURE_KAP=$KAP
# DEPO_TURU bilerek ayarlanmıyor: varsayılan "yerel" kalsın, buluta yazmak
# istediğinde komutun başına DEPO_TURU=blob yazarsın. Böylece yanlışlıkla
# buluta yazmak mümkün olmuyor.
