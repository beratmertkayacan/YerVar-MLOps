# Temel imaj: Python 3.13'ün küçültülmüş (slim) Debian sürümü.
# Sürümü sabitliyoruz: "latest" kullansaydık imaj bir gün habersizce değişirdi.
FROM python:3.13-slim

# Loglar tampona alınmadan anında yazılsın (yoksa `docker logs` gecikmeli görünür),
# .pyc dosyaları üretilmesin.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Uygulamayı çalıştıracak root olmayan kullanıcı. Kod kopyalanmadan önce
# oluşturuluyor, çünkü aşağıdaki COPY --chown bu kullanıcıya ihtiyaç duyuyor.
RUN useradd --create-home yervar

WORKDIR /uygulama

# Önce sadece bağımlılık listesi kopyalanır ve kurulur. Docker her satırı
# önbelleğe aldığı için, kod değiştiğinde bu adım tekrar çalışmaz.
COPY gereksinimler.txt .
RUN pip install --no-cache-dir -r gereksinimler.txt

# Kodu kopyalarken sahibini yervar kullanıcısı yapıyoruz. --chown olmadan
# dosyalar root'a ait olur ve bilgisayardaki izinler kısıtlıysa (ör. 600)
# yervar kullanıcısı onları okuyamaz. Böylece imaj, derlendiği makinenin
# dosya izinlerinden bağımsız çalışır.
COPY --chown=yervar:yervar yervar/ ./yervar/
RUN mkdir veri && chown yervar:yervar veri

# Konteyner root yetkisiyle çalışmasın: bir açık olursa etkisi sınırlı kalır.
USER yervar

# Varsayılan: tek tur çalış ve çık. Bulutta zamanlayıcı bunu her 5 dakikada
# bir başlatacak. Sürekli mod için komut `docker run` sırasında değiştirilir.
CMD ["python", "-m", "yervar.toplama.toplayici", "--tek-tur"]
