# Azure kaynak adları ve abonelik. Her yeni terminalde:
#   source altyapi/degiskenler.sh
# Sır içermez; kaynak adları ve abonelik kimliği gizli bilgi değildir.

# Doğru aboneliğe geç. Bu satır olmadan yanlış abonelikte kaynak açma riski var.
export ABONELIK=f07a2594-dfeb-44f2-a24d-6268c1780f31
az account set --subscription "$ABONELIK" 2>/dev/null || true

export KG=rg-yervar # kaynak grubu
export KONUM=westeurope # bölge
export SONEK=bmk01 # küresel olarak benzersiz olması gereken adlar için

export DEPOLAMA=styervar$SONEK # depolama hesabı (3-24 karakter, küçük harf ve rakam)
export KAP=ham # ham turların kabı (L0 yazar)
export TABLO_KAP=tablo # günlük tabloların kabı (L1 yazar)
export KAYIT=acryervar$SONEK # konteyner kayıt defteri
export KIMLIK_ACR=id-yervar-acr # imaj çekme kimliği (sadece AcrPull)
export ORTAM=cae-yervar  # Container Apps ortamı
export IS=job-yervar-toplayici  # 5 dakikada bir: toplama (L0)
export IS_TABLO=job-yervar-tablo  # her gece: dünün tablosu (L1)

# Tek imaj, iki iş: toplayıcı ve tablo işi aynı imajı farklı komutla çalıştırıyor.
# 0.3 ile imajın adı yervar-toplayici'dan yervar'a geçti, çünkü artık sadece
# toplayıcı değil. Eski sürümler kayıt defterinde eski adla duruyor.
export SURUM=0.3
export IMAJ=$KAYIT.azurecr.io/yervar:$SURUM

# -Python uygulamasının okuduğu isimler 
# Yukarıdaki kısa adlar az komutları için. Uygulama ise .env'deki adları okuyor.
# Aynı değeri iki isimle taşımak yerine burada eşliyoruz: tek doğru kaynak kalıyor.
export AZURE_DEPOLAMA_HESABI=$DEPOLAMA
export AZURE_KAP=$KAP
# DEPO_TURU bilerek ayarlanmıyor: varsayılan "yerel" kalsın, buluta yazmak
# istediğinde komutun başına DEPO_TURU=blob yazarsın. Böylece yanlışlıkla
# buluta yazmak mümkün olmuyor.
