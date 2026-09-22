"""Toplayıcı testleri — gerçek API'ye çıkmadan sahte bir sunucuyla."""

from pathlib import Path

import httpx
import pytest

from yervar.depolama.ham import YerelDepo, oku
from yervar.toplama import istemci as istemci_modulu
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


def test_tum_denemeler_biterse_hata_verir() -> None:
    with pytest.raises(RuntimeError):
        istemci_modulu.park_listesi_getir(sahte_istemci([503, 503, 503]))
