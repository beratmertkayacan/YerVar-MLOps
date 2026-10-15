import type { ComponentType } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import { veriDurumu } from '../alan/tazelik';
import { Harita } from '../bilesenler/Harita';
import { Serit } from '../bilesenler/Serit';
import { UstBaslik } from '../bilesenler/UstBaslik';
import { AnaEkran } from '../ekranlar/AnaEkran';
import { BulunamadiEkrani } from '../ekranlar/BulunamadiEkrani';
import { DetayEkrani } from '../ekranlar/DetayEkrani';
import { HakkindaEkrani } from '../ekranlar/HakkindaEkrani';
import { ListeEkrani } from '../ekranlar/ListeEkrani';
import { dakikaFarki, saatYaz } from '../metin/bicim';
import { metin } from '../metin/metinler';
import { cevrimdisi, prototip, yukleme } from '../veri/yukle';
import { simdi } from '../zaman/saat';
import { type Rota, rota } from './rota';

function GelistirmeVitrini() {
  const [Vitrin, setVitrin] = useState<ComponentType | null>(null);
  useEffect(() => {
    import('../ekranlar/Vitrin').then((modul) => setVitrin(() => modul.Vitrin));
  }, []);
  return Vitrin ? <Vitrin /> : null;
}

function Ekran({ rota }: { rota: Rota }) {
  switch (rota.ekran) {
    case 'ana':
      return <AnaEkran />;
    case 'otopark':
      return <DetayEkrani id={rota.id} />;
    case 'liste':
      return <ListeEkrani />;
    case 'hakkinda':
      return <HakkindaEkrani />;
    case 'vitrin':
      return import.meta.env.DEV ? <GelistirmeVitrini /> : <BulunamadiEkrani />;
    case 'bulunamadi':
      return <BulunamadiEkrani />;
  }
}

function sayfaAdi(r: Rota): string | null {
  const veri = yukleme.value;
  switch (r.ekran) {
    case 'liste':
      return metin.liste.baslik;
    case 'hakkinda':
      return metin.hakkinda.baslik;
    case 'bulunamadi':
      return metin.bulunamadi.baslik;
    case 'otopark':
      return veri.tur === 'hazir'
        ? (veri.dosya.otoparklar.find((o) => o.park_id === r.id)?.ad ?? null)
        : null;
    default:
      return null;
  }
}

function Seritler() {
  const durum = yukleme.value;
  if (durum.tur !== 'hazir') return null;
  const veri = veriDurumu(durum.dosya, simdi.value);
  return (
    <div class="seritler">
      {cevrimdisi.value && <Serit tur="uyari">{metin.serit.cevrimdisi}</Serit>}
      {veri === 'gecikmis' && (
        <Serit tur="uyari">
          {metin.serit.gecikmis(dakikaFarki(durum.dosya.veri_utc, simdi.value))}
        </Serit>
      )}
      {veri === 'cok_eski' && (
        <Serit tur="uyari">{metin.serit.suresiDoldu(saatYaz(durum.dosya.veri_utc))}</Serit>
      )}
    </div>
  );
}

export function Uygulama() {
  const gecerli = rota.value;
  const icerik = useRef<HTMLElement>(null);
  const ilkAcilis = useRef(true);
  const haritali = gecerli.ekran === 'ana' || gecerli.ekran === 'otopark';
  const adres = location.hash;
  const sayfa = sayfaAdi(gecerli);

  useEffect(() => {
    document.title = sayfa ? metin.sayfaBasligi(sayfa) : metin.marka.ad;
  }, [sayfa]);

  useEffect(() => {
    document.querySelector('details.menu')?.removeAttribute('open');
    // Ekran değişince odak yeni içeriğe geçer; ekran okuyucu baştan okur.
    if (ilkAcilis.current) {
      ilkAcilis.current = false;
      return;
    }
    icerik.current?.focus();
    scrollTo({ top: 0 });
  }, [adres]);

  return (
    <div class="kabuk" data-ekran={gecerli.ekran}>
      <header class="ust">
        <button type="button" class="icerige-gec" onClick={() => icerik.current?.focus()}>
          {metin.icerigeGec}
        </button>
        <UstBaslik />
        {prototip && <p class="filigran">{metin.filigran}</p>}
        <Seritler />
      </header>
      <div class={haritali ? 'govde govde-haritali' : 'govde'}>
        {haritali && <Harita />}
        <main id="icerik" ref={icerik} tabIndex={-1} class="panel">
          <Ekran rota={gecerli} />
        </main>
      </div>
    </div>
  );
}
