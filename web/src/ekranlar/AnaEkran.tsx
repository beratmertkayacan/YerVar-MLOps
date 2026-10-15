import { useState } from 'preact/hooks';
import { listeOlustur } from '../alan/liste';
import { veriDurumu } from '../alan/tazelik';
import { AltBilgi } from '../bilesenler/AltBilgi';
import { IskeletListesi, OtoparkListesi } from '../bilesenler/OtoparkListesi';
import { Simge } from '../bilesenler/Simge';
import { VarisSecici } from '../bilesenler/VarisSecici';
import { VeriBekleyen, YuklemeIletisi } from '../bilesenler/VeriBekleyen';
import { VeriCipi } from '../bilesenler/VeriCipi';
import { metin } from '../metin/metinler';
import { etkinVaris, konum, konumDurumu, konumIste } from '../uygulama/durum';
import type { TahminDosyasi } from '../veri/sozlesme';
import { simdi } from '../zaman/saat';

const GOSTERILEN = 8;
type Sekme = 'onerilen' | 'yakinimda';

function KonumIstegi() {
  const reddedildi = konumDurumu.value === 'reddedildi';
  return (
    <div class="bilgi-kutusu">
      <p>{reddedildi ? metin.konum.reddedildi : metin.konum.yok}</p>
      {!reddedildi && (
        <button type="button" class="dugme" onClick={konumIste}>
          <Simge ad="konum" />
          {konumDurumu.value === 'bekliyor' ? metin.konum.bekleniyor : metin.konum.kullan}
        </button>
      )}
    </div>
  );
}

function Panel({ dosya }: { dosya: TahminDosyasi }) {
  const [sekme, setSekme] = useState<Sekme>('onerilen');
  const simdiMs = simdi.value;
  const varis = etkinVaris(dosya.ufuklar, simdiMs);
  const liste = listeOlustur(
    dosya.otoparklar,
    varis.ufuk,
    sekme === 'yakinimda' ? 'yakinlik' : 'onerilen',
    konum.value,
  );
  const konumGerekli = sekme === 'yakinimda' && !konum.value;
  return (
    <>
      <VeriCipi veriUtc={dosya.veri_utc} durum={veriDurumu(dosya, simdiMs)} simdiMs={simdiMs} />
      <VarisSecici dosya={dosya} simdiMs={simdiMs} etkinDk={varis.dk} />
      <fieldset class="sekmeler">
        <legend class="gorsel-gizli">{metin.ana.sekmeler}</legend>
        {(['onerilen', 'yakinimda'] as const).map((s) => (
          <button key={s} type="button" aria-pressed={sekme === s} onClick={() => setSekme(s)}>
            {s === 'onerilen' ? metin.ana.onerilen : metin.ana.yakinimda}
          </button>
        ))}
      </fieldset>
      {konumGerekli ? (
        <KonumIstegi />
      ) : (
        <>
          {liste.yaricap?.genisledi && <p class="ipucu">{metin.konum.genisledi}</p>}
          {liste.siradakiler.length === 0 && liste.yaricap && (
            <p class="bilgi-kutusu">{metin.konum.sonucYok}</p>
          )}
          <OtoparkListesi satirlar={liste.siradakiler.slice(0, GOSTERILEN)} simdiMs={simdiMs} />
          <a class="dugme dugme-ikincil" href="#/liste">
            {metin.ana.tumu}
          </a>
        </>
      )}
    </>
  );
}

// Yüklenirken her parçanın yerini aynı yükseklikte tutar: veri gelince düzen kaymaz.
function PanelIskeleti() {
  return (
    <>
      <p class="yukleme-iletisi" role="status">
        <YuklemeIletisi />
      </p>
      <div class="iskelet-blok iskelet-varis" aria-hidden="true" />
      <div class="iskelet-blok iskelet-sekmeler" aria-hidden="true" />
      <IskeletListesi adet={GOSTERILEN} />
      <div class="iskelet-blok iskelet-dugme" aria-hidden="true" />
    </>
  );
}

export function AnaEkran() {
  return (
    <div class="panel-icerik">
      <h1 class="gorsel-gizli">{metin.ana.baslik}</h1>
      <VeriBekleyen iskelet={<PanelIskeleti />}>{(dosya) => <Panel dosya={dosya} />}</VeriBekleyen>
      <AltBilgi />
    </div>
  );
}
