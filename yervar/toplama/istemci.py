"""İSPARK web servisine istek atan katman.

İşi: isteği yapmak, yanıtın kullanılabilir bir tur olup olmadığına bakmak ve
geçici sorunlarda tekrar denemek.

Hangi durumda tekrar deneriz?
- Ağ hatası, zaman aşımı, 5xx, 408, 429  → geçici sorun, bekle ve tekrar dene
- Geçersiz yanıt  → 2xx ama JSON değil, liste değil, çok az kayıt ya da
                    kayıtların çoğunda zorunlu alan yok
- 3xx             → bakım sayfasına yönlendirme olabilir; takip etmiyoruz,
                    geçersiz yanıt sayıp tekrar deniyoruz
- Diğer 4xx       → isteğimiz reddedildi, tekrar denemek anlamsız. Geçersiz
                    yanıt olarak saklanıyor (sebep istemci_hatasi)
Bekleme süresi her denemede ikiye katlanır (2, 4, 8, 16 sn): üstel geri çekilme.
Sunucu Retry-After ile saniye verirse o kadar bekliyoruz; bütçeye sığmıyorsa
denemeyi bırakıyoruz.

Denemeler bir süre bütçesiyle sınırlı. Hiçbir deneme kullanılabilir tur
vermezse son denemenin türüne göre iki hatadan biri fırlıyor:
- KaynakHatasi : İSPARK'a ulaşılamadı. Log kelimesi KAYNAK_KESINTISI.
- GecersizYanit: ulaşıldı ama yanıt kullanılamaz. Log kelimesi KAYNAK_GECERSIZ.
İkisi de KaynakSorunu'ndan geliyor. Önceki bir denemede geçersiz gövde geldiyse,
son deneme ağ hatası olsa bile o gövde hatada taşınıyor ki saklanabilsin.
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from yervar import ayarlar
from yervar.depolama.ham import simdi_utc
from yervar.gunluk import gunluk_al

gunluk = gunluk_al(__name__)

# Bir kaydın "tam" sayılması için bu alanlar var olmalı ve tam sayı olmalı.
# lat/lng metin geldiği için burada yok.
ZORUNLU_ALANLAR = ("parkID", "capacity", "emptyCapacity", "isOpen")


@dataclass
class GecersizGovde:
    """Geçersiz bir yanıtın saklanacak bilgileri.

    sebep: json_degil, liste_degil, az_kayit, alan_eksik ya da yonlendirme
    """

    govde: bytes
    sebep: str
    durum_kodu: int
    icerik_turu: str
    konum: str = ""  # yönlendirmede Location başlığı


class KaynakSorunu(RuntimeError):
    """İSPARK'tan kullanılabilir bir tur alınamadı. Bu tur kayıp."""

    def __init__(self, mesaj: str, gecersiz: GecersizGovde | None = None) -> None:
        super().__init__(mesaj)
        self.gecersiz = gecersiz


class KaynakHatasi(KaynakSorunu):
    """İSPARK'a ulaşılamadı (5xx ya da bağlantı hatası)."""


class GecersizYanit(KaynakSorunu):
    """İSPARK cevap verdi ama yanıt bir tur olarak kullanılamaz."""


@dataclass
class Tur:
    """Başarılı bir turun verisi ve nasıl alındığı."""

    parklar: list[dict[str, Any]]
    deneme: int
    sure_ms: int
    yanit_utc: datetime

    @property
    def kayit(self) -> int:
        return len(self.parklar)


def istemci_olustur() -> httpx.Client:
    """Tekrar kullanılabilir bir HTTP istemcisi oluşturur.

    Aynı istemciyi turlar boyunca kullanmak, bağlantının her seferinde
    yeniden kurulmasını önler. Yönlendirmeler takip edilmiyor (httpx varsayılanı).
    """
    return httpx.Client(
        timeout=ayarlar.ISTEK_ZAMAN_ASIMI_SN,
        headers={"User-Agent": ayarlar.KULLANICI_AJANI},
    )


def _kayit_tam_mi(kayit: Any) -> bool:
    if not isinstance(kayit, dict):
        return False
    # bool da Python'da int sayılıyor; True/False gelirse tam sayı kabul etmiyoruz
    return all(
        isinstance(kayit.get(alan), int) and not isinstance(kayit.get(alan), bool)
        for alan in ZORUNLU_ALANLAR
    )


def gecersizlik_sebebi(veri: Any) -> str | None:
    """Çözülmüş JSON bir tur olarak kullanılabilir mi? Değilse sebep kodu döner.

    Tek tük bozuk kayıt turu reddettirmez, onları L1 işaretliyor.
    """
    if not isinstance(veri, list):
        return "liste_degil"
    if len(veri) < ayarlar.EN_AZ_OTOPARK:
        return "az_kayit"
    tam = sum(1 for kayit in veri if _kayit_tam_mi(kayit))
    if tam < ayarlar.ZORUNLU_ALAN_ORANI * len(veri):
        return "alan_eksik"
    return None


def _gecersiz(yanit: httpx.Response, sebep: str) -> GecersizGovde:
    konum = yanit.headers.get("location", "")
    return GecersizGovde(
        govde=yanit.content,
        sebep=sebep,
        durum_kodu=yanit.status_code,
        icerik_turu=yanit.headers.get("content-type", ""),
        konum=konum.encode("ascii", "replace").decode("ascii")[:200],
    )


def _retry_after(yanit: httpx.Response) -> float | None:
    """Retry-After başlığı saniye ise onu döndürür. Tarih biçimini ve
    anlaşılmayan değerleri yok sayıyoruz, o zaman normal bekleme kullanılır."""
    deger = yanit.headers.get("retry-after", "").strip()
    return float(deger) if deger.isdigit() else None


def park_listesi_getir(istemci: httpx.Client, butce_sn: float | None = None) -> Tur:
    """Tüm otoparkların anlık durumunu bir tur olarak döndürür.

    Liste ucu kapasite ve boş yer bilgisini içeriyor (kesif/ornek'e bakın),
    bu yüzden her tur için tek bir istek yeterli.

    butce_sn: denemelere ayrılan toplam süre. Verilmezse TUR_SURE_BUTCESI_SN.
    """
    adres = f"{ayarlar.ISPARK_TABAN_URL}/Park"
    butce = ayarlar.TUR_SURE_BUTCESI_SN if butce_sn is None else butce_sn
    baslangic = time.monotonic()
    bitis = baslangic + butce
    bekleme = 2.0
    hata = ""
    son_gecersiz: GecersizGovde | None = None
    son_deneme_gecersiz = False

    for deneme in range(1, ayarlar.DENEME_SAYISI + 1):
        son_deneme_gecersiz = False
        bu_bekleme = bekleme
        try:
            yanit = istemci.get(adres)
        except httpx.RequestError as e:
            # bağlantı hatası, zaman aşımı, bozuk sıkıştırılmış yanıt...
            hata = str(e) or type(e).__name__
        else:
            kod = yanit.status_code
            if kod >= 500 or kod in (408, 429):
                hata = f"HTTP {kod}"
                bu_bekleme = _retry_after(yanit) or bekleme
            elif kod >= 400:
                # isteğimiz reddedildi, tekrar denemiyoruz ama gövdeyi saklıyoruz
                raise GecersizYanit(
                    f"{deneme} deneme başarısız: HTTP {kod} istemci hatası",
                    _gecersiz(yanit, "istemci_hatasi"),
                )
            elif kod >= 300:
                son_gecersiz = _gecersiz(yanit, "yonlendirme")
                son_deneme_gecersiz = True
            else:
                try:
                    veri = yanit.json()
                except ValueError:
                    sebep = "json_degil"
                else:
                    sebep = gecersizlik_sebebi(veri)
                if sebep is None:
                    sure_ms = int((time.monotonic() - baslangic) * 1000)
                    return Tur(veri, deneme, sure_ms, simdi_utc())
                son_gecersiz = _gecersiz(yanit, sebep)
                son_deneme_gecersiz = True

            if son_deneme_gecersiz:
                hata = f"geçersiz yanıt: {son_gecersiz.sebep} (HTTP {kod})"
                if son_gecersiz.konum:
                    hata += f" konum={son_gecersiz.konum}"

        son_deneme = deneme == ayarlar.DENEME_SAYISI
        butce_bitiyor = time.monotonic() + bu_bekleme >= bitis
        if son_deneme or butce_bitiyor:
            break
        gunluk.warning("deneme %d başarısız (%s), %.0f sn sonra tekrar", deneme, hata, bu_bekleme)
        time.sleep(bu_bekleme)
        bekleme *= 2

    mesaj = f"{deneme} deneme başarısız: {hata}"
    if son_deneme_gecersiz:
        raise GecersizYanit(mesaj, son_gecersiz)
    raise KaynakHatasi(mesaj, son_gecersiz)
