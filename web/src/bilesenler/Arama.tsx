import { useState } from 'preact/hooks';
import { ilceYaz } from '../metin/bicim';
import { metin } from '../metin/metinler';
import { konumDurumu, konumIste } from '../uygulama/durum';
import { otoparkAdresi } from '../uygulama/rota';
import type { Otopark } from '../veri/sozlesme';
import { yukleme } from '../veri/yukle';
import { Simge } from './Simge';

const EN_COK_SONUC = 6;
const kucuk = (s: string) => s.toLocaleLowerCase('tr-TR');

export function aramaSonuclari(otoparklar: Otopark[], sorgu: string): Otopark[] {
  const aranan = kucuk(sorgu.trim());
  if (!aranan) return [];
  return otoparklar
    .filter((o) => o.kapsam !== 'gosterme')
    .filter((o) => kucuk(o.ad).includes(aranan) || kucuk(o.ilce ?? '').includes(aranan))
    .slice(0, EN_COK_SONUC);
}

/** Yerel arama: dosyadaki ad ve ilçe üzerinde, harici servis yok. Açılır liste klavyeyle gezilir. */
export function Arama() {
  const [sorgu, setSorgu] = useState('');
  const [etkin, setEtkin] = useState(-1);
  const durum = yukleme.value;
  const sonuclar = durum.tur === 'hazir' ? aramaSonuclari(durum.dosya.otoparklar, sorgu) : [];
  const acik = sorgu.trim().length > 0;

  function git(otopark: Otopark) {
    location.hash = otoparkAdresi(otopark.park_id);
    setSorgu('');
    setEtkin(-1);
  }

  function tus(olay: KeyboardEvent) {
    if (olay.key === 'ArrowDown') {
      olay.preventDefault();
      setEtkin((etkin + 1) % Math.max(1, sonuclar.length));
    } else if (olay.key === 'ArrowUp') {
      olay.preventDefault();
      setEtkin(etkin <= 0 ? sonuclar.length - 1 : etkin - 1);
    } else if (olay.key === 'Enter') {
      const secilen = sonuclar[Math.max(0, etkin)];
      if (secilen) git(secilen);
    } else if (olay.key === 'Escape') {
      setSorgu('');
    }
  }

  return (
    <div class="arama">
      <div class="arama-kutu">
        <Simge ad="ara" />
        <input
          type="search"
          role="combobox"
          aria-label={metin.arama.etiket}
          aria-expanded={acik}
          aria-controls="arama-sonuclari"
          aria-autocomplete="list"
          aria-activedescendant={etkin >= 0 ? `arama-${etkin}` : undefined}
          placeholder={metin.arama.yerTutucu}
          value={sorgu}
          onInput={(olay) => {
            setSorgu(olay.currentTarget.value);
            setEtkin(-1);
          }}
          onKeyDown={tus}
        />
        <button
          type="button"
          class="konum-dugmesi"
          onClick={konumIste}
          aria-pressed={konumDurumu.value === 'var'}
        >
          <Simge ad="konum" />
          {konumDurumu.value === 'bekliyor' ? (
            <span>{metin.konum.bekleniyor}</span>
          ) : (
            <>
              <span class="yalniz-genis">{metin.konum.kullan}</span>
              <span class="yalniz-dar">{metin.konum.kisa}</span>
            </>
          )}
        </button>
      </div>
      {acik && (
        <div
          id="arama-sonuclari"
          class="arama-sonuclari"
          role="listbox"
          aria-label={metin.arama.etiket}
        >
          {sonuclar.length === 0 && <p class="arama-bos">{metin.arama.sonucYok}</p>}
          {sonuclar.map((otopark, sira) => (
            <div
              key={otopark.park_id}
              id={`arama-${sira}`}
              role="option"
              tabIndex={-1}
              aria-selected={sira === etkin}
              onMouseDown={(olay) => {
                olay.preventDefault();
                git(otopark);
              }}
            >
              <span>{otopark.ad}</span>
              {otopark.ilce && <small>{ilceYaz(otopark.ilce)}</small>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
