"""L4: Modelin karnesi. Hata nerede, ne zaman, hangi otoparkta?

Tek bir ortalama hata çok şey saklıyor. 1,0 puanlık ortalama, gece boş duran
yüz otoparkta 0 hata ile sabah dolan on otoparkta 10 hatanın ortalaması
olabilir. Kullanıcı ise tam o sabah saatini soruyor. Bu yüzden hatayı
parçalara ayırıyoruz (kırılım):

    saat           -> hangi saatler zor?
    doluluk bandı  -> boşken mi doluyken mi yanılıyor?
    gün tipi       -> hafta sonu farklı mı?
    otopark        -> model hangi otoparklarda basit tahmine bile yeniliyor?

Bir de kullanıcının asıl sorusunu ölçüyoruz: "gittiğimde yer olacak mı?"
Bu artık bir sayı tahmini değil, evet/hayır kararı. Doluluk DOLU_ESIK'in
üstündeyse otoparkı "dolu" sayıyoruz ve modelin bunu ne kadar yakaladığına
bakıyoruz. En değerli an "dolma anı": şu an yer var, ufuk sonra dolu.
"Şimdiki gibi kalır" tahmini bu anları tanım gereği hiç yakalayamaz;
modelin gerçek katkısı burada görünür.

Girdi: geri testin bütün günlerinden gelen tek tablo. Her satırda gerçek
değer (hedef) ve her yöntemin tahmini (t_simdiki, t_model) var.
"""

import pandas as pd

# %95 dolu otoparkı "dolu" sayıyoruz. Varsayım: küçük otoparkta bu 2-3 yer,
# 4000'lik otoparkta 200 yer demek. Uygulama aşamasında boş yer sayısına göre
# yeniden düşünülecek, şimdilik herkes için aynı ölçü.
DOLU_ESIK = 0.95

# Doluluk bantları. Son bandın üst sınırı 1'in biraz üstünde ki 1,0 da girsin.
BANT_SINIRLARI = [0, 0.5, 0.75, 0.9, 1.01]
BANT_ADLARI = ["%0-50", "%50-75", "%75-90", "%90-100"]

# Karnede karşılaştırdığımız iki yöntem: basit tahmin ve model.
YONTEMLER = {"simdiki_gibi": "t_simdiki", "model": "t_model"}


def hatalari_ekle(df: pd.DataFrame) -> pd.DataFrame:
    """Her satıra her yöntemin mutlak hatasını (doluluk puanı, 0-100) ekler."""
    df = df.copy()
    for ad, sutun in YONTEMLER.items():
        df[f"hata_{ad}"] = 100 * (df["hedef"] - df[sutun]).abs()
    df["bant"] = pd.cut(df["doluluk_simdi"], BANT_SINIRLARI, labels=BANT_ADLARI, right=False)
    df["gun_tipi"] = df["hafta_sonu"].map({1.0: "hafta sonu", 0.0: "hafta içi"})
    return df


def kirilim(df: pd.DataFrame, grup: str) -> pd.DataFrame:
    """Bir sütuna göre gruplayıp her yöntemin ortalama hatasını verir.

    fark: basit tahminin hatası eksi modelin hatası. Pozitifse model iyi,
    negatifse model o grupta "şimdiki gibi"ye yeniliyor.
    """
    g = df.groupby(grup, observed=True)
    tablo = pd.DataFrame({
        "satir": g.size(),
        "simdiki_gibi": g["hata_simdiki_gibi"].mean(),
        "model": g["hata_model"].mean(),
    })
    tablo["fark"] = tablo["simdiki_gibi"] - tablo["model"]
    return tablo.round(2)


def otopark_kirilimi(df: pd.DataFrame) -> pd.DataFrame:
    """Otopark başına hata, en kötüden başlayarak."""
    tablo = kirilim(df, "park_id")
    bilgi = df.groupby("park_id", observed=True)[["ilce", "tip", "kapasite"]].first()
    return tablo.join(bilgi).sort_values("model", ascending=False)


def karar_olculeri(df: pd.DataFrame, esik: float = DOLU_ESIK) -> dict:
    """"Dolu mu?" sorusunda yöntemlerin başarısı.

    yakalama : gerçekten dolu olan anların yüzde kaçında "dolu" dedi
    isabet   : "dolu" dediği anların yüzde kaçı gerçekten dolu çıktı
    dolma_ani: şu an dolu değil, ufuk sonra dolu. Kaç tane var, kaçını bildi.
    """
    gercek = df["hedef"] >= esik
    dolma_ani = (df["doluluk_simdi"] < esik) & gercek
    sonuc = {"dolu_an": int(gercek.sum()), "dolma_ani": int(dolma_ani.sum())}
    for ad, sutun in YONTEMLER.items():
        dedi = df[sutun] >= esik
        bildi = dedi & gercek
        sonuc[ad] = {
            "yakalama": _yuzde(bildi.sum(), gercek.sum()),
            "isabet": _yuzde(bildi.sum(), dedi.sum()),
            "dolma_ani_yakalama": _yuzde((dedi & dolma_ani).sum(), dolma_ani.sum()),
        }
    return sonuc


def _yuzde(pay: int, payda: int) -> float | None:
    # Hiç olay yoksa oran tanımsız; 0 yazmak "hiç bilemedi" gibi yanıltır.
    return round(100 * pay / payda, 1) if payda else None


def sapma(df: pd.DataFrame) -> float:
    """Model ortalamada fazla mı tahmin ediyor az mı? (puan, + ise fazla)

    Mutlak hata yönü gizler. Sapma sıfırdan uzaksa model sistematik olarak
    bir tarafa kayıyor demek; bu, hatadan daha kolay düzeltilir.
    """
    return round(100 * (df["t_model"] - df["hedef"]).mean(), 2)


def karne_olustur(tahminler: pd.DataFrame) -> dict:
    """Bütün karneyi tek sözlükte toplar: tablolar ve tek sayılık özetler."""
    df = hatalari_ekle(tahminler)
    otoparklar = otopark_kirilimi(df)
    return {
        "tablolar": {
            "saat": kirilim(df, "saat"),
            "bant": kirilim(df, "bant"),
            "gun_tipi": kirilim(df, "gun_tipi"),
            "otopark": otoparklar,
        },
        "karar": karar_olculeri(df),
        "sapma": sapma(df),
        "modelin_yenildigi_otopark": int((otoparklar["fark"] < 0).sum()),
        "otopark_sayisi": len(otoparklar),
    }


def karne_yazdir(karne: dict) -> None:
    """Terminale kısa özet. Tabloların tamamı MLflow'da."""
    t = karne["tablolar"]
    print(f"  {'kırılım':<12} {'şimdiki':>8} {'model':>8} {'fark':>8} {'satır':>8}")
    for tablo in (t["bant"], t["gun_tipi"]):
        for ad, s in tablo.iterrows():
            print(f"  {ad:<12} {s['simdiki_gibi']:>8} {s['model']:>8} {s['fark']:>8} "
                  f"{int(s['satir']):>8}")

    zor = t["saat"].sort_values("model", ascending=False).head(3)
    saatler = ", ".join(f"{int(s):02d}:00 ({h:.2f})" for s, h in zor["model"].items())
    print(f"  model için en zor saatler: {saatler}")
    print(f"  sapma: {karne['sapma']:+} puan (+ ise model fazla dolu sanıyor)")
    print(f"  modelin basit tahmine yenildiği otopark: "
          f"{karne['modelin_yenildigi_otopark']}/{karne['otopark_sayisi']}")

    k = karne["karar"]
    print(f"  'dolu mu?' (%{DOLU_ESIK * 100:.0f}+): {k['dolu_an']} dolu an, "
          f"{k['dolma_ani']} dolma anı")
    for ad in YONTEMLER:
        o = {olcu: "yok" if v is None else f"%{v}" for olcu, v in k[ad].items()}
        print(f"    {ad:<13} yakalama {o['yakalama']}  isabet {o['isabet']}  "
              f"dolma anı yakalama {o['dolma_ani_yakalama']}")
