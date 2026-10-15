"""Adım 3 denetim betiklerinin (kesif/12-16) ortak parçaları.

Denetim bulutta değil, Mac'e bir kez indirilen dondurulmuş bir anlık görüntü
(snapshot) üzerinde çalışıyor: veri/anlik/<ad>/tablo/ altında doluluk, otoparklar
ve özet. Böylece aynı betik yarın da aynı sayıları verir; bulutta her gece bir gün
eklenmesi sonucu değiştirmez.

Bu dosya yervar/ altındaki kodu DEĞİŞTİRMİYOR, sadece içe aktarıyor. Ayarları
(veri kökü, depo türü) çalışma anında anlık görüntüye çeviriyor.
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
# "python kesif/xx.py" ile çalışınca arama yolunda proje kökü yok (bkz. 03_blob_oku.py)
sys.path.insert(0, str(KOK))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from yervar import ayarlar  # noqa: E402

SONUC = KOK / "kesif" / "sonuclar"
VARSAYILAN_ANLIK = "2026-10-15"

# Sınav seti. Eğitim VERI_BASLANGIC'ten (24 Eylül) başlıyor: 22-23 Eylül Mac
# dönemi, boşluklu ve GUN_EKSIK. Test son 7 tam gün: 9 Ekim Cuma - 15 Ekim
# Perşembe, haftanın her günü bir kez, hepsinin tamlığı %99'un üstünde.
EGITIM_BAS = date(2026, 9, 24)
TEST_GUNLERI = [date(2026, 10, 9) + timedelta(days=i) for i in range(7)]
SON_GUN = TEST_GUNLERI[-1]
UFUKLAR = [15, 30, 60, 120]
RASTGELE = 0

# Saat dilimleri (İstanbul saati)
DILIMLER = [
    (0, 6, "gece_00_06"),
    (7, 10, "sabah_07_10"),
    (11, 15, "ogle_11_15"),
    (16, 19, "aksam_16_19"),
    (20, 23, "gece_20_23"),
]
BANTLAR = [0, 0.5, 0.75, 0.85, 0.95, 1.01]
BANT_ADLARI = ["%0-50", "%50-75", "%75-85", "%85-95", "%95-100"]


def anlik_klasoru(ad: str) -> Path:
    return KOK / "veri" / "anlik" / ad


def anlik_kur(ad: str) -> Path:
    """Ayarları anlık görüntüye çevirir. Buluta hiç gidilmez."""
    klasor = anlik_klasoru(ad)
    if not (klasor / "tablo" / "doluluk").exists():
        raise SystemExit(
            f"Anlık görüntü yok: {klasor}/tablo/doluluk. Önce indirme komutunu çalıştır."
        )
    ayarlar.DEPO_TURU = "yerel"
    ayarlar.VERI_KOK = klasor
    ayarlar.TABLO_KAP = "tablo"
    return klasor


def anlik_kimligi(ad: str) -> str:
    dosya = anlik_klasoru(ad) / "parmak_izi.json"
    if not dosya.exists():
        raise SystemExit(f"{dosya} yok. Önce: python kesif/12_anlik_goruntu.py --anlik {ad}")
    return json.loads(dosya.read_text())["kimlik"]


def mlflow_hazirla(deney: str = "denetim-2026-10"):
    """Denetim koşularını ayrı bir deneye yazar. Kayıt yeri her zamanki yerel
    veritabanı (veri/mlflow.db); anlık görüntünün içine değil."""
    import mlflow

    mlflow.set_tracking_uri(ayarlar.MLFLOW_ADRES)
    if mlflow.get_experiment_by_name(deney) is None:
        yer = (KOK / "veri" / "mlflow_artifacts").resolve().as_uri()
        mlflow.create_experiment(deney, artifact_location=yer)
    mlflow.set_experiment(deney)
    return mlflow


def etiketler(ad: str, betik: str) -> dict:
    from yervar.egitim.egit import git_bilgisi

    return {**git_bilgisi(), "anlik": anlik_kimligi(ad), "betik": betik, "katman": "denetim"}


def deger_tablosu(ham: pd.DataFrame) -> pd.Series:
    """(park_id, zaman_utc) anahtarlı doluluk. Herhangi bir anın değerini bulmak için."""
    t = ham[["park_id", "zaman_utc", "doluluk_simdi"]].copy()
    t["park_id"] = t["park_id"].astype(int)
    return t.set_index(["park_id", "zaman_utc"])["doluluk_simdi"]


def kaydir(df: pd.DataFrame, tablo: pd.Series, dakika: int) -> pd.Series:
    """Aynı otoparkın, satırın zamanından `dakika` sonraki değeri (eksiyse önceki)."""
    anahtar = pd.MultiIndex.from_arrays(
        [
            df["park_id"].astype(int).to_numpy(),
            (df["zaman_utc"] + pd.Timedelta(minutes=dakika)).to_numpy(),
        ]
    )
    return pd.Series(tablo.reindex(anahtar).to_numpy(), index=df.index)


def dilim(saat: pd.Series) -> pd.Series:
    sonuc = pd.Series("?", index=saat.index, dtype=object)
    for bas, bit, ad in DILIMLER:
        sonuc[saat.between(bas, bit)] = ad
    return sonuc


def mae(gercek: pd.Series, tahmin: pd.Series) -> float:
    return float(100 * (gercek - tahmin).abs().mean())


def gun_bootstrap(gunluk: pd.DataFrame, yontemler: list[str], tekrar: int = 2000) -> dict:
    """Günleri yeniden örnekleyip MAE ve beceri için %90 güven aralığı.

    gunluk: her test günü için satır sayısı (`n`) ve her yöntemin mutlak hata
    toplamı (`top_<yontem>`). Günler bütün olarak örnekleniyor, çünkü aynı günün
    satırları birbirine bağımlı; satır satır örneklemek aralığı yapay daraltır.
    """
    rng = np.random.default_rng(RASTGELE)
    n = gunluk["n"].to_numpy()
    toplar = {y: gunluk[f"top_{y}"].to_numpy() for y in yontemler}
    secim = rng.integers(0, len(gunluk), size=(tekrar, len(gunluk)))
    paydalar = n[secim].sum(axis=1)
    sonuc = {}
    maeler = {y: 100 * toplar[y][secim].sum(axis=1) / paydalar for y in yontemler}
    for y in yontemler:
        sonuc[y] = (float(np.percentile(maeler[y], 5)), float(np.percentile(maeler[y], 95)))
        if y != "simdiki":
            beceri = 1 - maeler[y] / maeler["simdiki"]
            sonuc[f"beceri_{y}"] = (
                float(np.percentile(beceri, 5)),
                float(np.percentile(beceri, 95)),
            )
    return sonuc


def kaydet(df: pd.DataFrame, ad: str) -> Path:
    SONUC.mkdir(parents=True, exist_ok=True)
    yol = SONUC / ad
    df.to_csv(yol, index=True)
    return yol
