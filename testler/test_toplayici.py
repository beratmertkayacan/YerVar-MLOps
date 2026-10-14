"""Toplayıcı testleri — gerçek API'ye çıkmadan sahte bir sunucuyla."""

import gzip
import re
from datetime import UTC, date
from pathlib import Path

import httpx
import pytest

from yervar import ayarlar
from yervar.depolama.ham import YerelDepo, oku
from yervar.depolama.tablo import gunun_satirlari
from yervar.toplama import istemci as istemci_modulu
from yervar.toplama import toplayici
from yervar.toplama.istemci import GecersizYanit, KaynakHatasi
from yervar.toplama.toplayici import tek_tur


def kayit(park_id: int) -> dict:
    return {"parkID": park_id, "capacity": 100, "emptyCapacity": 23, "isOpen": 1}


# Normal bir yanıt: eşiğin (200) üstünde, bütün kayıtlar tam.
ORNEK = [kayit(i) for i in range(250)]


def json_yanit(veri: object, kod: int = 200):
    return lambda istek: httpx.Response(kod, json=veri, request=istek)


def metin_yanit(metin: str, kod: int = 200):
    return lambda istek: httpx.Response(kod, text=metin, request=istek)


def yonlendirme(istek: httpx.Request) -> httpx.Response:
    # Location başlığında ASCII dışı karakter: sunucular bunu bayt olarak gönderebiliyor
    konum = "https://bakım.ibb.gov.tr/".encode()
    return httpx.Response(302, headers={"Location": konum}, request=istek)


def ag_hatasi(istek: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("bağlantı kurulamadı", request=istek)


def sahte_istemci(cevaplar: list) -> httpx.Client:
    """Sırayla cevap veren sahte HTTP istemcisi.

    Her eleman ya bir durum kodu (200 ise ORNEK döner) ya da istek alıp yanıt
    üreten bir fonksiyon.
    """
    sira = iter(cevaplar)

    def cevapla(istek: httpx.Request) -> httpx.Response:
        cevap = next(sira)
        if isinstance(cevap, int):
            return httpx.Response(cevap, json=ORNEK if cevap == 200 else {}, request=istek)
        return cevap(istek)

    return httpx.Client(transport=httpx.MockTransport(cevapla))


@pytest.fixture(autouse=True)
def beklemeyi_kapat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Testlerde tekrar deneme beklemelerini atla."""
    monkeypatch.setattr(istemci_modulu.time, "sleep", lambda _: None)


def ana_programi_calistir(monkeypatch, istemci: httpx.Client, depo) -> int:
    """toplayici.main'i --tek-tur ile çalıştırır, çıkış kodunu döndürür (0: sorunsuz)."""
    monkeypatch.setattr(toplayici, "istemci_olustur", lambda: istemci)
    monkeypatch.setattr(toplayici, "depo_olustur", lambda **_: depo)
    monkeypatch.setattr("sys.argv", ["toplayici", "--tek-tur"])
    try:
        toplayici.main()
    except SystemExit as cikis:
        return cikis.code
    return 0


# --- istemci: başarılı tur -----------------------------------------------------

def test_tek_tur_dosya_yazar(tmp_path: Path) -> None:
    tek_tur(sahte_istemci([200]), YerelDepo(tmp_path))
    dosyalar = list(tmp_path.rglob("*.json.gz"))
    assert len(dosyalar) == 1
    assert oku(dosyalar[0]) == ORNEK


def test_basarili_tur_bilgisi() -> None:
    tur = istemci_modulu.park_listesi_getir(sahte_istemci([200]))
    assert (tur.kayit, tur.deneme) == (250, 1)
    assert tur.sure_ms >= 0
    assert tur.yanit_utc.tzinfo == UTC


def test_5xx_sonrasi_tekrar_dener() -> None:
    tur = istemci_modulu.park_listesi_getir(sahte_istemci([503, 200]))
    assert tur.parklar == ORNEK
    assert tur.deneme == 2


def test_4xx_tekrar_denenmez() -> None:
    with pytest.raises(httpx.HTTPStatusError):
        istemci_modulu.park_listesi_getir(sahte_istemci([404, 200]))


def test_tum_denemeler_biterse_kaynak_hatasi_verir() -> None:
    with pytest.raises(KaynakHatasi):
        istemci_modulu.park_listesi_getir(sahte_istemci([503] * ayarlar.DENEME_SAYISI))


def test_sure_butcesi_bitince_denemeyi_keser() -> None:
    # Bütçe 0: ilk hatadan sonra beklemeye vakit yok. 200 hiç istenmemeli.
    with pytest.raises(KaynakHatasi, match="1 deneme"):
        istemci_modulu.park_listesi_getir(sahte_istemci([503, 200]), butce_sn=0)


# --- istemci: yanıt doğrulama ------------------------------------------------

def eksik(alan: str, deger: object = "sil") -> list[dict]:
    """Bütün kayıtlarda bir alanı bozulmuş liste."""
    kayitlar = [kayit(i) for i in range(250)]
    for k in kayitlar:
        if deger == "sil":
            del k[alan]
        else:
            k[alan] = deger
    return kayitlar


@pytest.mark.parametrize(("cevap", "sebep"), [
    (json_yanit([]), "az_kayit"),
    (json_yanit({"hata": "bakım"}), "liste_degil"),
    (metin_yanit("<html>Bakımdayız</html>"), "json_degil"),
    (json_yanit(ORNEK[:199]), "az_kayit"),
    (json_yanit(eksik("emptyCapacity")), "alan_eksik"),
    (json_yanit(eksik("isOpen")), "alan_eksik"),
    (json_yanit(eksik("capacity", None)), "alan_eksik"),
    (json_yanit(eksik("capacity", "100")), "alan_eksik"),
    (json_yanit(eksik("isOpen", True)), "alan_eksik"),
    (yonlendirme, "yonlendirme"),
])
def test_gecersiz_yanit(cevap, sebep: str) -> None:
    with pytest.raises(GecersizYanit) as hata:
        istemci_modulu.park_listesi_getir(sahte_istemci([cevap]), butce_sn=0)
    assert hata.value.gecersiz.sebep == sebep


def test_birkac_kayitta_alan_eksik_olsa_da_gecerli() -> None:
    kayitlar = [kayit(i) for i in range(250)]
    for k in kayitlar[:3]:
        del k["isOpen"]
    tur = istemci_modulu.park_listesi_getir(sahte_istemci([json_yanit(kayitlar)]))
    assert tur.kayit == 250


def test_yonlendirme_konumu_ascii() -> None:
    with pytest.raises(GecersizYanit) as hata:
        istemci_modulu.park_listesi_getir(sahte_istemci([yonlendirme]), butce_sn=0)
    assert hata.value.gecersiz.konum.isascii()
    assert hata.value.gecersiz.konum.startswith("https://bak")
    assert "konum=" in str(hata.value)


def test_yonlendirme_sonrasi_tekrar_denenir() -> None:
    tur = istemci_modulu.park_listesi_getir(sahte_istemci([yonlendirme, 200]))
    assert tur.deneme == 2


def test_gecersiz_yanit_butce_icinde_tekrar_denenir() -> None:
    tur = istemci_modulu.park_listesi_getir(sahte_istemci([json_yanit({}), 200]))
    assert tur.deneme == 2


def test_hep_gecersizse_gecersiz_yanit_verir() -> None:
    cevaplar = [json_yanit([])] * ayarlar.DENEME_SAYISI
    with pytest.raises(GecersizYanit, match=f"{ayarlar.DENEME_SAYISI} deneme"):
        istemci_modulu.park_listesi_getir(sahte_istemci(cevaplar))


def test_son_deneme_ag_hatasiysa_onceki_gecersiz_govde_tasinir(monkeypatch) -> None:
    monkeypatch.setattr(ayarlar, "DENEME_SAYISI", 2)
    with pytest.raises(KaynakHatasi) as hata:
        istemci_modulu.park_listesi_getir(sahte_istemci([metin_yanit("bakım"), ag_hatasi]))
    assert hata.value.gecersiz.govde == b"bak\xc4\xb1m"


# --- toplayıcı: loglar, çıkış kodu, hatali/ -----------------------------------

def test_basari_satiri_alarm_kalibiyla_eslesir(tmp_path, caplog) -> None:
    caplog.set_level("INFO")
    tek_tur(sahte_istemci([200]), YerelDepo(tmp_path))

    satir = next(r.getMessage() for r in caplog.records if "TUR_TAMAM" in r.getMessage())
    # kur_06'daki sessizlik alarmı bu kalıpla sayıyı ayıklıyor
    assert re.search(r"(\d+) otopark kaydedildi", satir).group(1) == "250"
    for alan in ("kayit=250", "deneme=1", "sure_ms=", "yanit_utc=", "surum="):
        assert alan in satir


def test_kaynak_kesintisi_tek_satir_log_ve_cikis_kodu(tmp_path, monkeypatch, caplog) -> None:
    def cokmus_kaynak(_istemci):
        raise KaynakHatasi("5 deneme başarısız: HTTP 503")

    monkeypatch.setattr(toplayici, "park_listesi_getir", cokmus_kaynak)
    kod = ana_programi_calistir(monkeypatch, sahte_istemci([]), YerelDepo(tmp_path))
    assert kod == 1
    assert "KAYNAK_KESINTISI" in caplog.text
    assert "surum=" in caplog.text


def test_gecersiz_yanit_saklanir_loglanir_ve_cikis_1(tmp_path, monkeypatch, caplog) -> None:
    caplog.set_level("INFO")
    cevaplar = [metin_yanit("<html>Bakımdayız</html>")] * ayarlar.DENEME_SAYISI
    depo = YerelDepo(tmp_path, uzerine_yaz=False)

    kod = ana_programi_calistir(monkeypatch, sahte_istemci(cevaplar), depo)

    assert kod == 1
    assert "KAYNAK_GECERSIZ" in caplog.text
    assert "sebep=json_degil" in caplog.text
    assert "otopark kaydedildi" not in caplog.text
    hatalilar = list((tmp_path / "hatali").rglob("*.govde.gz"))
    assert len(hatalilar) == 1
    assert gzip.decompress(hatalilar[0].read_bytes()).decode() == "<html>Bakımdayız</html>"
    assert list(tmp_path.rglob("*.json.gz")) == []


def test_hatali_govde_boyut_siniri(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ayarlar, "HATALI_GOVDE_EN_FAZLA_BAYT", 10)
    cevaplar = [metin_yanit("x" * 50)] * ayarlar.DENEME_SAYISI
    ana_programi_calistir(monkeypatch, sahte_istemci(cevaplar), YerelDepo(tmp_path))
    dosya = next((tmp_path / "hatali").rglob("*.govde.gz"))
    assert gzip.decompress(dosya.read_bytes()) == b"x" * 10


def test_hatali_yazilamazsa_asil_sebep_kaybolmaz(tmp_path, monkeypatch, caplog) -> None:
    class BozukDepo(YerelDepo):
        def yaz_bayt(self, goreli_yol, veri, meta=None):
            raise OSError("disk dolu")

    cevaplar = [json_yanit([])] * ayarlar.DENEME_SAYISI
    kod = ana_programi_calistir(monkeypatch, sahte_istemci(cevaplar), BozukDepo(tmp_path))

    assert kod == 1
    assert "HATALI_YAZILAMADI" in caplog.text
    assert "KAYNAK_GECERSIZ" in caplog.text


def test_hatali_dosyalar_l1_okumasina_karismaz(tmp_path, monkeypatch) -> None:
    depo = YerelDepo(tmp_path, uzerine_yaz=False)
    # önce geçersiz bir tur, sonra geçerli bir tur, aynı gün
    with pytest.raises(GecersizYanit):
        tek_tur(sahte_istemci([json_yanit({"hata": 1})] * ayarlar.DENEME_SAYISI), depo)
    tek_tur(sahte_istemci([200]), depo)

    assert len(list((tmp_path / "hatali").rglob("*"))) > 0
    bugun = next(tmp_path.rglob("*.json.gz")).relative_to(tmp_path).parts[:3]
    satirlar = gunun_satirlari(depo, date(*map(int, bugun)))
    assert len(satirlar) == 250


def test_surekli_mod_gecersiz_yanitta_durmaz(tmp_path, monkeypatch, caplog) -> None:
    monkeypatch.setattr(toplayici, "_calisiyor", True)
    monkeypatch.setattr(ayarlar, "TOPLAMA_ARALIGI_SN", 0)
    cagri = []

    def sahte_tur(_istemci, _depo):
        cagri.append(1)
        if len(cagri) == 1:
            raise GecersizYanit("1 deneme başarısız", None)
        toplayici._calisiyor = False  # ikinci turdan sonra dur

    monkeypatch.setattr(toplayici, "tek_tur", sahte_tur)
    toplayici.surekli_calis(sahte_istemci([]), YerelDepo(tmp_path))

    assert len(cagri) == 2
    assert "KAYNAK_GECERSIZ" in caplog.text


def test_ham_meta_verisi_ascii_ve_tanimlayici(tmp_path) -> None:
    yazilan = {}

    class KayitliDepo(YerelDepo):
        def yaz(self, goreli_yol, icerik, meta=None):
            yazilan.update(meta)
            return super().yaz(goreli_yol, icerik, meta)

    tek_tur(sahte_istemci([200]), KayitliDepo(tmp_path))
    assert set(yazilan) == {"kayit", "deneme", "sure_ms", "yanit_utc", "surum"}
    assert all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k) for k in yazilan)
    assert all(isinstance(v, str) and v.isascii() for v in yazilan.values())
