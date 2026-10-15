import { useState } from 'preact/hooks';
import { listeOlustur, type Siralama } from '../alan/liste';
import { AltBilgi } from '../bilesenler/AltBilgi';
import { IskeletListesi, OtoparkListesi } from '../bilesenler/OtoparkListesi';
import { VarisSecici } from '../bilesenler/VarisSecici';
import { VeriBekleyen } from '../bilesenler/VeriBekleyen';
import { metin } from '../metin/metinler';
import { etkinVaris, konum } from '../uygulama/durum';
import type { TahminDosyasi } from '../veri/sozlesme';
import { simdi } from '../zaman/saat';

const SECENEKLER: Siralama[] = ['onerilen', 'yakinlik', 'olasilik'];

function Liste({ dosya }: { dosya: TahminDosyasi }) {
  const [siralama, setSiralama] = useState<Siralama>('onerilen');
  const simdiMs = simdi.value;
  const varis = etkinVaris(dosya.ufuklar, simdiMs);
  const liste = listeOlustur(dosya.otoparklar, varis.ufuk, siralama, konum.value);
  return (
    <>
      <VarisSecici dosya={dosya} simdiMs={simdiMs} etkinDk={varis.dk} />
      <fieldset class="secici" aria-describedby={konum.value ? undefined : 'yakinlik-ipucu'}>
        <legend>{metin.liste.siralama}</legend>
        <div class="secici-secenekler">
          {SECENEKLER.map((secenek) => (
            <label key={secenek} class="secici-secenek">
              <input
                type="radio"
                name="siralama"
                value={secenek}
                checked={siralama === secenek}
                disabled={secenek === 'yakinlik' && !konum.value}
                onChange={() => setSiralama(secenek)}
              />
              <span>{metin.liste.secenek[secenek]}</span>
            </label>
          ))}
        </div>
        {!konum.value && (
          <p id="yakinlik-ipucu" class="ipucu">
            {metin.liste.yakinlikPasif}
          </p>
        )}
      </fieldset>
      {liste.yaricap?.genisledi && <p class="ipucu">{metin.konum.genisledi}</p>}
      <OtoparkListesi satirlar={liste.siradakiler} simdiMs={simdiMs} />
      {liste.veriYok.length > 0 && (
        <details class="akordeon">
          <summary>{metin.kapsam.veriYokGrubu(liste.veriYok.length)}</summary>
          <OtoparkListesi satirlar={liste.veriYok} simdiMs={simdiMs} />
        </details>
      )}
      {liste.gosterilmeyen.length > 0 && (
        <p class="ipucu">
          {metin.kapsam.gosterilmeyenler(liste.gosterilmeyen.length)}{' '}
          <a class="baglanti" href="#/hakkinda">
            {metin.kapsam.neden}
          </a>
        </p>
      )}
    </>
  );
}

export function ListeEkrani() {
  return (
    <div class="sayfa">
      <h1>{metin.liste.baslik}</h1>
      <VeriBekleyen iskelet={<IskeletListesi adet={8} />}>
        {(dosya) => <Liste dosya={dosya} />}
      </VeriBekleyen>
      <AltBilgi />
    </div>
  );
}
