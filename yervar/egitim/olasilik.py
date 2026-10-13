"""Ufuk sonunda otoparkın dolu olma olasılığı.

Doluluk modeli tek bir sayı veriyor, örneğin "%93 dolu olacak". Sınıra yakın
tahminlerde dolu deyip demeyeceği belirsiz kalıyor ve dolu anların bir kısmını
kaçırıyor (120 dk'da yakalama %70). Bu model doğrudan "dolu olacak mı"
sorusunu öğreniyor ve 0 ile 1 arasında bir olasılık veriyor.

Dolu tanımı karnedekiyle aynı: degerlendirme/karne.py içindeki dolu_mu().
"""

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from yervar.degerlendirme.karne import dolu_mu


def dolu_hedefi(df: pd.DataFrame) -> pd.Series:
    """Ufuk sonunda dolu ise 1, değilse 0."""
    return dolu_mu(df["hedef"], df["kapasite"]).astype(int)


def olasilik_modeli_kur(
    egitim: pd.DataFrame, sutunlar: list[str], ayarlar: dict
) -> HistGradientBoostingClassifier | None:
    y = dolu_hedefi(egitim)
    # eğitimde hiç dolu an yoksa (ya da hepsi doluysa) öğrenecek bir şey yok
    if y.nunique() < 2:
        return None
    model = HistGradientBoostingClassifier(
        **ayarlar, categorical_features="from_dtype", random_state=0
    )
    return model.fit(egitim[sutunlar], y)


def olasilik_tahmin_et(
    egitim: pd.DataFrame, test: pd.DataFrame, sutunlar: list[str], ayarlar: dict
) -> tuple[HistGradientBoostingClassifier | None, pd.Series]:
    model = olasilik_modeli_kur(egitim, sutunlar, ayarlar)
    if model is None:
        # model kurulamadıysa eğitimdeki dolu oranını herkese veriyoruz
        return None, pd.Series(float(dolu_hedefi(egitim).mean()), index=test.index)
    return model, pd.Series(model.predict_proba(test[sutunlar])[:, 1], index=test.index)
