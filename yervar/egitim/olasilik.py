"""Ufuk sonunda otoparkın dolu olma olasılığı.

Doluluk modeli tek bir sayı veriyor, örneğin "%93 dolu olacak". Sınıra yakın
tahminlerde dolu deyip demeyeceği belirsiz kalıyor ve dolu anların bir kısmını
kaçırıyor (120 dk'da yakalama %70). Bu model doğrudan "dolu olacak mı"
sorusunu öğreniyor ve 0 ile 1 arasında bir olasılık veriyor.

Kalibrasyon: ilk denemede model orta olasılıklarda çekingen çıktı. %40-50
dediği anların aslında %60'ı doluydu. Bu yüzden eğitim verisinin son
KALIBRASYON_GUN günü ayrılıyor. Model önceki günlerle eğitiliyor, sonra son
günlerde verdiği olasılıklar gerçekleşenlere göre düzeltiliyor (isotonic).

Dolu tanımı karnedekiyle aynı: degerlendirme/karne.py içindeki dolu_mu().
"""

import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator

from yervar import ayarlar
from yervar.degerlendirme.karne import dolu_mu


def dolu_hedefi(df: pd.DataFrame) -> pd.Series:
    """Ufuk sonunda dolu ise 1, değilse 0."""
    return dolu_mu(df["hedef"], df["kapasite"]).astype(int)


def dolu_sutunlar(df: pd.DataFrame, sutunlar: list[str]) -> list[str]:
    """Bu veride en az iki farklı değeri olan sütunlar.

    Kalibrasyon için son günleri ayırınca kalan kısımda bazı sütunlar tamamen
    boş kalabiliyor. Örnek: veri 24 Eylül'de başlıyor, "geçen hafta" sütunu
    ancak 1 Ekim'den sonra dolu. Boş sütunla model kurulamıyor.
    """
    return [s for s in sutunlar if df[s].nunique(dropna=True) > 1]


def siniflandirici(egitim: pd.DataFrame, sutunlar: list[str], model_ayarlari: dict):
    model = HistGradientBoostingClassifier(
        **model_ayarlari, categorical_features="from_dtype", random_state=0
    )
    return model.fit(egitim[sutunlar], dolu_hedefi(egitim))


def olasilik_modeli_kur(egitim: pd.DataFrame, sutunlar: list[str], model_ayarlari: dict):
    """Kalibre edilmiş olasılık modeli ve kullandığı sütunlar. Kurulamazsa (None, []).

    Kalibrasyon için yeterli gün yoksa ya da ayrılan kısımda hem dolu hem boş
    an yoksa kalibrasyonsuz model dönüyor.
    """
    if dolu_hedefi(egitim).nunique() < 2:
        # eğitimde hiç dolu an yoksa (ya da hepsi doluysa) öğrenecek bir şey yok
        return None, []

    son_gun = egitim["zaman_utc"].dt.normalize().max()
    kesim = son_gun - pd.Timedelta(days=ayarlar.KALIBRASYON_GUN - 1)
    ogren = egitim[egitim["zaman_utc"] < kesim]
    ayir = egitim[egitim["zaman_utc"] >= kesim]
    if ogren.empty or dolu_hedefi(ogren).nunique() < 2 or dolu_hedefi(ayir).nunique() < 2:
        sutunlar = dolu_sutunlar(egitim, sutunlar)
        return siniflandirici(egitim, sutunlar, model_ayarlari), sutunlar

    sutunlar = dolu_sutunlar(ogren, sutunlar)
    model = siniflandirici(ogren, sutunlar, model_ayarlari)
    # FrozenEstimator: modeli tekrar eğitme, sadece çıktısını düzelt
    kalibre = CalibratedClassifierCV(FrozenEstimator(model), method="isotonic")
    return kalibre.fit(ayir[sutunlar], dolu_hedefi(ayir)), sutunlar


def olasilik_tahmin_et(
    egitim: pd.DataFrame, test: pd.DataFrame, sutunlar: list[str], model_ayarlari: dict
):
    model, sutunlar = olasilik_modeli_kur(egitim, sutunlar, model_ayarlari)
    if model is None:
        # model kurulamadıysa eğitimdeki dolu oranını herkese veriyoruz
        return None, pd.Series(float(dolu_hedefi(egitim).mean()), index=test.index)
    return model, pd.Series(model.predict_proba(test[sutunlar])[:, 1], index=test.index)
