"""Toplayıcı testleri — gerçek API'ye çıkmadan sahte bir sunucuyla."""

from pathlib import Path

import httpx
import pytest

from yervar import ayarlar
from yervar.depolama.ham import YerelDepo, oku
from yervar.toplama import istemci as istemci_modulu
from yervar.toplama import toplayici
from yervar.toplama.istemci import KaynakHatasi
from yervar.toplama.toplayici import tek_tur

ORNEK = [{"parkID": 1, "capacity": 100, "emptyCapacity": 23}]


def sahte_istemci(durum_kodlari: list[int]) -> httpx.Client:
    """Sırayla verilen durum kodlarını döndüren sahte HTTP istemcisi."""
    kodlar = iter(durum_kodlari)

    def cevapla(istek: httpx.Request) -> httpx.Response:
        kod = next(kodlar)
        return httpx.Response(kod, json=ORNEK if kod == 200 else {}, request=istek)

    return httpx.Client(transport=httpx.MockTransport(cevapla))


@pytest.fixture(autouse=True)
def beklemeyi_kapat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Testlerde tekrar deneme beklemelerini atla."""
    monkeypatch.setattr(istemci_modulu.time, "sleep", lambda _: None)


def test_tek_tur_dosya_yazar(tmp_path: Path) -> None:
    tek_tur(sahte_istemci([200]), YerelDepo(tmp_path))
    dosyalar = list(tmp_path.rglob("*.json.gz"))
    assert len(dosyalar) == 1
    assert oku(dosyalar[0]) == ORNEK


def test_5xx_sonrasi_tekrar_dener() -> None:
    sonuc = istemci_modulu.park_listesi_getir(sahte_istemci([503, 200]))
    assert sonuc == ORNEK


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


def test_kaynak_kesintisi_tek_satir_log_ve_cikis_kodu(tmp_path, monkeypatch, caplog) -> None:
    def cokmus_kaynak(_istemci):
        raise KaynakHatasi("5 deneme başarısız: HTTP 503")

    monkeypatch.setattr(toplayici, "park_listesi_getir", cokmus_kaynak)
    monkeypatch.setattr(toplayici, "depo_olustur", lambda: YerelDepo(tmp_path))
    monkeypatch.setattr("sys.argv", ["toplayici", "--tek-tur"])

    with pytest.raises(SystemExit) as cikis:
        toplayici.main()
    assert cikis.value.code == 1
    assert "KAYNAK_KESINTISI" in caplog.text
