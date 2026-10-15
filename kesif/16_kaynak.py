"""Adım 3 denetimi (e): kaynak ölçümü ve ücretsiz kota hesabı (Adım 8 için).

İki alt komut:

    olc    Anlık görüntü üzerinde gece eğitimi ve canlı tahmin ne kadar sürüyor,
           ne kadar bellek istiyor, model kaç bayt. Bugünkü kodun fonksiyonları
           ile, son güne kadar bütün veriyle (canlıda gece yapılacak eğitim gibi).
    isler  Azure'dan indirilen iş çalıştırma listeleri (JSON) ve log özetlerinden
           toplayıcı ile gece işinin süresini "açılış" ve "iş" olarak ayırır,
           sonra Container Apps ücretsiz kotasına göre aylık hesap yapar.

Açılış: çalıştırmanın başlaması ile kodun ilk log satırı arası (imaj çekme,
kapsayıcı başlatma, Python'un açılması). İş: ilk log ile son log arası.
Gece işinde ölçüldü: bütün çalıştırma 37 sn, kod 7,8 sn, yani yaklaşık 29 sn
açılış. Her AYRI iş bu açılışı her seferinde yeniden ödüyor; Adım 8'de "tahmini
ayrı bir iş yapalım" kararının bedeli tam burada görünüyor.

Ücretsiz kota (Container Apps tüketim planı, abonelik başına aylık):
180.000 vCPU-saniye ve 360.000 GiB-saniye. Fatura replikanın çalıştığı süre
için; açılışın da faturaya girdiğini varsayıyoruz (ihtiyatlı tarafta kalmak için).

Çalıştırma:
    OMP_NUM_THREADS=1 python kesif/16_kaynak.py olc --anlik 2026-10-15
    python kesif/16_kaynak.py isler --klasor veri/anlik/2026-10-15/isler
OMP_NUM_THREADS=1: model eğitimi Mac'te bütün çekirdekleri kullanıyor; bulutta
iş 0.25-1 vCPU alıyor. Tek çekirdekle ölçmek buluta daha yakın bir süre veriyor.
"""

import argparse
import json
import pickle
import platform
import resource
import time
from pathlib import Path

import denetim_ortak as d
import duckdb
import pandas as pd

from yervar.egitim import egit
from yervar.egitim.olasilik import olasilik_modeli_kur
from yervar.ozellikler.olustur import ozellik_seti, tablolari_bagla

KOTA_VCPU_SN = 180_000
KOTA_GIB_SN = 360_000
AY_GUN = 30


def en_yuksek_bellek_mib() -> float:
    tepe = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS bayt, Linux kilobayt veriyor
    return tepe / 2**20 if platform.system() == "Darwin" else tepe / 2**10


def olc(arg) -> None:
    d.anlik_kur(arg.anlik)
    etiket = d.etiketler(arg.anlik, "16_kaynak.py olc")
    con = duckdb.connect()
    tablolari_bagla(con)
    satirlar = []

    def yaz(adim: str, sn: float, **ek) -> None:
        satirlar.append(
            {
                "adim": adim,
                "sn": round(sn, 2),
                "tepe_bellek_mib": round(en_yuksek_bellek_mib()),
                **ek,
            }
        )
        print(f"  {adim:<34} {sn:7.2f} sn  tepe {satirlar[-1]['tepe_bellek_mib']} MiB  {ek or ''}")

    toplam = time.perf_counter()
    modeller = {}
    for ufuk in d.UFUKLAR:
        t0 = time.perf_counter()
        ham = ozellik_seti(con, d.EGITIM_BAS, d.SON_GUN, d.EGITIM_BAS, ufuk).df()
        yaz(f"ozellik_tum_gunler_{ufuk}dk", time.perf_counter() - t0, satir=len(ham))
        df = egit.veri_hazirla(ham)

        t0 = time.perf_counter()
        sutunlar = egit.bilgili_sutunlar(df)
        reg = egit.model_kur().fit(df[sutunlar], egit.ogrenme_hedefi(df, "fark"))
        yaz(
            f"egitim_regresyon_{ufuk}dk",
            time.perf_counter() - t0,
            satir=len(df),
            iterasyon=int(reg.n_iter_),
        )

        t0 = time.perf_counter()
        sinif, s_sutunlar = olasilik_modeli_kur(df, sutunlar, egit.MODEL_AYARLARI)
        yaz(f"egitim_olasilik_{ufuk}dk", time.perf_counter() - t0)
        modeller[ufuk] = (reg, sutunlar, sinif, s_sutunlar)
        boyut = len(pickle.dumps(reg)) + (len(pickle.dumps(sinif)) if sinif is not None else 0)
        satirlar[-1]["model_bayt"] = boyut
        del ham, df

    # Canlı tahmin: son günün özellikleri (7 gün geriye okuyarak), sonra sadece
    # son turun satırları için 4 ufuk. Canlıda veri blobdan okunacak; ağ süresi burada yok.
    t0 = time.perf_counter()
    canli = egit.veri_hazirla(
        ozellik_seti(con, d.SON_GUN, d.SON_GUN, d.EGITIM_BAS, 30).df().assign(hedef=0.0)
    )
    tur = canli[canli["zaman_utc"] == canli["zaman_utc"].max()]
    yaz("ozellik_tek_gun", time.perf_counter() - t0, satir=len(canli), son_tur_otopark=len(tur))
    t0 = time.perf_counter()
    for reg, sutunlar, sinif, s_sutunlar in modeller.values():
        reg.predict(tur[sutunlar])
        if sinif is not None:
            sinif.predict_proba(tur[s_sutunlar])
    yaz("tahmin_tek_tur_4_ufuk", time.perf_counter() - t0, otopark=len(tur))
    yaz(
        "toplam",
        time.perf_counter() - toplam,
        model_bayt_toplam=sum(s.get("model_bayt", 0) for s in satirlar),
    )

    tablo = pd.DataFrame(satirlar).set_index("adim")
    yol = d.kaydet(tablo, "16_olcum.csv")
    mlflow = d.mlflow_hazirla()
    with mlflow.start_run(run_name="kaynak-olcumu"):
        mlflow.set_tags(
            {
                **etiket,
                "asama": "kaynak",
                "omp_num_threads": arg.omp,
                "makine": platform.machine(),
                "python": platform.python_version(),
            }
        )
        for adim, s in tablo.iterrows():
            mlflow.log_metric(f"sn_{adim}", float(s["sn"]))
        mlflow.log_metric("tepe_bellek_mib", float(tablo["tepe_bellek_mib"].max()))
        mlflow.log_artifact(str(yol))
    print(f"\nanlık: {etiket['anlik']}  commit: {etiket['git_commit']}  sonuç: {yol}")


def zaman(s: str | None) -> pd.Timestamp | None:
    return pd.Timestamp(s).tz_convert("UTC") if s else None


def calismalar(dosya: Path, loglar: Path) -> pd.DataFrame:
    """az containerapp job execution list çıktısı ile log özetinden çalıştırma başına süreler."""
    satirlar = []
    for c in json.loads(dosya.read_text()):
        p = c.get("properties", c)
        satirlar.append(
            {
                "ad": c["name"],
                "durum": p.get("status"),
                "bas": zaman(p.get("startTime")),
                "bit": zaman(p.get("endTime")),
            }
        )
    cal = pd.DataFrame(satirlar)
    log = pd.DataFrame(json.loads(loglar.read_text()))
    log["ilk"] = log["ilk"].map(zaman)
    log["son"] = log["son"].map(zaman)
    # replika adı çalıştırma adıyla başlıyor: çalıştırma job-...-abc12, replika job-...-abc12-xyz9k
    eslesen = []
    for _, r in cal.iterrows():
        k = log[log["grup"].str.startswith(r["ad"] + "-") | (log["grup"] == r["ad"])]
        eslesen.append(k.iloc[0] if len(k) else pd.Series({"ilk": None, "son": None, "satir": 0}))
    cal = pd.concat(
        [cal, pd.DataFrame(eslesen).reset_index(drop=True)[["ilk", "son", "satir"]]], axis=1
    )
    cal["toplam_sn"] = (cal["bit"] - cal["bas"]).dt.total_seconds()
    cal["acilis_sn"] = (cal["ilk"] - cal["bas"]).dt.total_seconds()
    cal["is_sn"] = (cal["son"] - cal["ilk"]).dt.total_seconds()
    cal["kapanis_sn"] = (cal["bit"] - cal["son"]).dt.total_seconds()
    return cal


def aylik(ad: str, kez_ayda: float, sn: float, cpu: float, gib: float) -> dict:
    vcpu, gibsn = kez_ayda * sn * cpu, kez_ayda * sn * gib
    return {
        "is": ad,
        "kez_ayda": round(kez_ayda),
        "sn_kez": round(sn, 1),
        "vcpu": cpu,
        "gib": gib,
        "vcpu_sn_ay": round(vcpu),
        "gib_sn_ay": round(gibsn),
        "vcpu_kota_yuzde": round(100 * vcpu / KOTA_VCPU_SN, 1),
        "gib_kota_yuzde": round(100 * gibsn / KOTA_GIB_SN, 1),
    }


def isler(arg) -> None:
    k = Path(arg.klasor)
    top = calismalar(k / "toplayici_calismalar.json", k / "toplayici_loglar.json")
    gece = calismalar(k / "tablo_calismalar.json", k / "tablo_loglar.json")
    d.kaydet(top.set_index("ad"), "16_toplayici_calismalar.csv")
    d.kaydet(gece.set_index("ad"), "16_tablo_calismalar.csv")

    def ozet(c: pd.DataFrame, ad: str) -> dict:
        b = c[c["durum"] == "Succeeded"]
        return {
            "is": ad,
            "calisma": len(c),
            "basarili": len(b),
            **{
                f"{s}_{f}": round(float(getattr(b[s], f)()), 1)
                for s in ["toplam_sn", "acilis_sn", "is_sn", "kapanis_sn"]
                for f in ["median", "max"]
            },
        }

    ozetler = pd.DataFrame([ozet(top, "toplayici"), ozet(gece, "tablo")]).set_index("is")
    d.kaydet(ozetler, "16_is_sureleri.csv")

    acilis = float(pd.concat([top["acilis_sn"], gece["acilis_sn"]]).median())
    top_sn = float(ozetler.loc["toplayici", "toplam_sn_median"])
    gece_sn = float(ozetler.loc["tablo", "toplam_sn_median"])
    olcum = (
        pd.read_csv(d.SONUC / "16_olcum.csv", index_col="adim")
        if (d.SONUC / "16_olcum.csv").exists()
        else None
    )
    tahmin_sn = egitim_sn = None
    if olcum is not None:
        tahmin_sn = float(
            olcum.loc["ozellik_tek_gun", "sn"] + olcum.loc["tahmin_tek_tur_4_ufuk", "sn"]
        )
        egitim_sn = float(
            olcum.loc[
                [i for i in olcum.index if i.startswith(("ozellik_tum", "egitim_"))], "sn"
            ].sum()
        )
    # Mac'te tek çekirdekle ölçüldü; 0.5 vCPU iki kat yavaş varsayılıyor
    yavas = 1 / arg.tahmin_cpu

    tur_ayda = AY_GUN * 24 * 12
    satirlar = [
        aylik("toplayici (bugün)", tur_ayda, top_sn, 0.25, 0.5),
        aylik("tablo (bugün)", AY_GUN, gece_sn, 0.5, 1.0),
    ]
    if tahmin_sn is not None:
        satirlar += [
            aylik(
                "A: tahmin toplayıcının içinde, 5 dk",
                tur_ayda,
                top_sn + tahmin_sn / 0.25,
                0.25,
                0.5,
            ),
            aylik(
                "B: ayrı tahmin işi, 5 dk",
                tur_ayda,
                acilis + tahmin_sn * yavas,
                arg.tahmin_cpu,
                arg.tahmin_gib,
            ),
            aylik(
                "C: ayrı tahmin işi, 15 dk",
                tur_ayda / 3,
                acilis + tahmin_sn * yavas,
                arg.tahmin_cpu,
                arg.tahmin_gib,
            ),
            aylik(
                "gece eğitimi, günde 1",
                AY_GUN,
                acilis + egitim_sn / arg.egitim_cpu,
                arg.egitim_cpu,
                arg.egitim_gib,
            ),
        ]
    hesap = pd.DataFrame(satirlar).set_index("is")
    d.kaydet(hesap, "16_kota_hesabi.csv")

    # Tasarımın bütün ayı: her tasarımda tablo ve gece eğitimi de var; A'da tahmin
    # toplayıcının içinde olduğu için toplayıcı ayrıca sayılmıyor.
    tasarim = None
    if tahmin_sn is not None:
        ortak = ["tablo (bugün)", "gece eğitimi, günde 1"]
        parcalar = {
            "A": ["A: tahmin toplayıcının içinde, 5 dk"],
            "B": ["toplayici (bugün)", "B: ayrı tahmin işi, 5 dk"],
            "C": ["toplayici (bugün)", "C: ayrı tahmin işi, 15 dk"],
        }
        tasarim = pd.DataFrame(
            {
                t: hesap.loc[
                    p + ortak, ["vcpu_sn_ay", "gib_sn_ay", "vcpu_kota_yuzde", "gib_kota_yuzde"]
                ].sum()
                for t, p in parcalar.items()
            }
        ).T
        tasarim.index.name = "tasarim"
        d.kaydet(tasarim, "16_tasarim_kota.csv")

    pd.set_option("display.width", 220)
    print(ozetler.to_string())
    print(
        f"\nortanca açılış: {acilis:.1f} sn  tek tur tahmin (Mac, 1 çekirdek): "
        f"{tahmin_sn and round(tahmin_sn, 2)} sn  "
        f"gece eğitimi: {egitim_sn and round(egitim_sn, 1)} sn"
    )
    print("\n" + hesap.to_string())
    if tasarim is not None:
        print(
            "\nTASARIM BAŞINA AYLIK TOPLAM (kota yüzdesi 100'ü geçerse ücret başlar)\n"
            + tasarim.to_string()
        )
    print(
        "\nnot: A satırında toplayıcının 0.5 GiB'ı yeter mi, "
        "16_olcum.csv'deki tepe bellek ile karşılaştır."
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    alt = ap.add_subparsers(dest="komut", required=True)
    o = alt.add_parser("olc")
    o.add_argument("--anlik", default=d.VARSAYILAN_ANLIK)
    i = alt.add_parser("isler")
    i.add_argument("--klasor", required=True)
    i.add_argument("--tahmin-cpu", type=float, default=0.5)
    i.add_argument("--tahmin-gib", type=float, default=1.0)
    i.add_argument("--egitim-cpu", type=float, default=1.0)
    i.add_argument("--egitim-gib", type=float, default=2.0)
    arg = ap.parse_args()
    if arg.komut == "olc":
        import os

        arg.omp = os.environ.get("OMP_NUM_THREADS", "yok")
        olc(arg)
    else:
        isler(arg)


if __name__ == "__main__":
    main()
