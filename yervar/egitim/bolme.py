"""Zamana göre eğitim/test bölme.

Rastgele bölmüyoruz: zaman serisinde gelecekten öğrenip geçmişi tahmin etmek
hile olur. Her test günü için eğitim o günden önceki bütün günler oluyor
(genişleyen pencere). Böylece model gerçekte olacağı gibi sınanıyor: dünü
bilerek bugünü tahmin ediyor.

Eğitimin son satırlarının hedefi test gününe düşmesin diye arada ufuk kadar
boşluk bırakıyoruz. Yoksa model test gününden bir parçayı eğitimde görmüş olur.
"""

import pandas as pd


def gun_katlari(
    df: pd.DataFrame, ufuk_dk: int, en_az_egitim_gun: int = 1, son_gun: int | None = None
) -> list[tuple[pd.Timestamp, pd.DataFrame, pd.DataFrame]]:
    """Her test günü için (gün, eğitim, test) üçlüsü döndürür.

    en_az_egitim_gun: ilk test gününden önce en az kaç günlük eğitim olsun
    son_gun: sadece son N günü test et (veri büyüyünce süreyi sınırlamak için)
    """
    gunler = sorted(df["zaman_utc"].dt.normalize().unique())
    test_gunleri = gunler[en_az_egitim_gun:]
    if son_gun:
        test_gunleri = test_gunleri[-son_gun:]

    katlar = []
    for gun in test_gunleri:
        gun = pd.Timestamp(gun)
        egitim = df[df["zaman_utc"] + pd.Timedelta(minutes=ufuk_dk) < gun]
        test = df[(df["zaman_utc"] >= gun) & (df["zaman_utc"] < gun + pd.Timedelta(days=1))]
        katlar.append((gun, egitim, test))
    return katlar
