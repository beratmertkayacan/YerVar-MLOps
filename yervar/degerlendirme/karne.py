"""L4: geri test sonuçlarının kırılımları ve "dolu mu?" ölçüleri.

Girdi, geri testin bütün günlerini içeren tek tablo: her satırda gerçek değer
(hedef) ve yöntemlerin tahminleri (t_simdiki, t_model).

Kırılımlar: saat, doluluk bandı, gün tipi, otopark.
Karar ölçüleri: hedef DOLU_ESIK ve üstündeyse otopark dolu sayılır.
Dolma anı: şu an dolu değil, ufuk sonra dolu.
"""

import pandas as pd

# Herkes için aynı eşik. Büyük otoparklarda %95 hâlâ çok sayıda boş yer demek;
# uygulama aşamasında boş yer sayısına göre tekrar bakılacak.
DOLU_ESIK = 0.95

BANT_SINIRLARI = [0, 0.5, 0.75, 0.9, 1.01]  # 1.0 son banda girsin diye 1.01
BANT_ADLARI = ["%0-50", "%50-75", "%75-90", "%90-100"]

YONTEMLER = {"simdiki_gibi": "t_simdiki", "model": "t_model"}


def hatalari_ekle(df: pd.DataFrame) -> pd.DataFrame:
    """Mutlak hata (0-100 puan), doluluk bandı ve gün tipi sütunlarını ekler."""
    df = df.copy()
    for ad, sutun in YONTEMLER.items():
        df[f"hata_{ad}"] = 100 * (df["hedef"] - df[sutun]).abs()
    df["bant"] = pd.cut(df["doluluk_simdi"], BANT_SINIRLARI, labels=BANT_ADLARI, right=False)
    df["gun_tipi"] = df["hafta_sonu"].map({1.0: "hafta sonu", 0.0: "hafta içi"})
    return df


def kirilim(df: pd.DataFrame, grup: str) -> pd.DataFrame:
    """Gruba göre ortalama hata. fark > 0 ise model daha iyi."""
    g = df.groupby(grup, observed=True)
    tablo = pd.DataFrame({
        "satir": g.size(),
        "simdiki_gibi": g["hata_simdiki_gibi"].mean(),
        "model": g["hata_model"].mean(),
    })
    tablo["fark"] = tablo["simdiki_gibi"] - tablo["model"]
    return tablo.round(2)


def otopark_kirilimi(df: pd.DataFrame, adlar: pd.Series | None = None) -> pd.DataFrame:
    """Otopark başına hata, en kötüden başlayarak. adlar: park_id -> ad"""
    tablo = kirilim(df, "park_id")
    bilgi = df.groupby("park_id", observed=True)[["ilce", "tip", "kapasite"]].first()
    tablo = tablo.join(bilgi)
    if adlar is not None:
        tablo.insert(0, "ad", [adlar.get(p) for p in tablo.index])
    return tablo.sort_values("model", ascending=False)


def karar_olculeri(df: pd.DataFrame, esik: float = DOLU_ESIK) -> dict:
    """yakalama: gerçek dolu anların yüzde kaçı bilindi.
    isabet: "dolu" denen anların yüzde kaçı doğru çıktı.
    dolma_ani_yakalama: şu an boş yeri olup ufuk sonra dolanların yüzde kaçı bilindi.
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
    # payda 0 ise oran tanımsız; 0 yazmak yanlış anlaşılır
    return round(100 * pay / payda, 1) if payda else None


def sapma(df: pd.DataFrame) -> float:
    """Ortalama (tahmin - gerçek), puan. Artı: fazla dolu tahmin."""
    return round(100 * (df["t_model"] - df["hedef"]).mean(), 2)


def karne_olustur(tahminler: pd.DataFrame, adlar: pd.Series | None = None) -> dict:
    df = hatalari_ekle(tahminler)
    otoparklar = otopark_kirilimi(df, adlar)
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
    """Terminal için kısa özet; tabloların tamamı MLflow'a yazılıyor."""
    t = karne["tablolar"]
    print(f"  {'kırılım':<12} {'şimdiki':>8} {'model':>8} {'fark':>8} {'satır':>8}")
    for tablo in (t["bant"], t["gun_tipi"]):
        for ad, s in tablo.iterrows():
            print(f"  {ad:<12} {s['simdiki_gibi']:>8} {s['model']:>8} {s['fark']:>8} "
                  f"{int(s['satir']):>8}")

    zor = t["saat"].sort_values("model", ascending=False).head(3)
    saatler = ", ".join(f"{int(s):02d}:00 ({h:.2f})" for s, h in zor["model"].items())
    print(f"  en zor saatler: {saatler}")
    print(f"  sapma: {karne['sapma']:+} puan")
    print(f"  modelin yenildiği otopark: "
          f"{karne['modelin_yenildigi_otopark']}/{karne['otopark_sayisi']}")

    k = karne["karar"]
    print(f"  dolu (%{DOLU_ESIK * 100:.0f}+): {k['dolu_an']} an, {k['dolma_ani']} dolma anı")
    for ad in YONTEMLER:
        o = {olcu: "yok" if v is None else f"%{v}" for olcu, v in k[ad].items()}
        print(f"    {ad:<13} yakalama {o['yakalama']}  isabet {o['isabet']}  "
              f"dolma anı {o['dolma_ani_yakalama']}")
