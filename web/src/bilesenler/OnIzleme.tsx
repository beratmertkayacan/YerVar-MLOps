import { cevapBul } from '../alan/cevap';
import { saatYaz } from '../metin/bicim';
import { metin } from '../metin/metinler';
import { etkinVaris } from '../uygulama/durum';
import type { Otopark, TahminDosyasi } from '../veri/sozlesme';
import { cevapGorunumu } from './cevapGorunumu';
import { Simge } from './Simge';

interface Ozellikler {
  otopark: Otopark;
  dosya: TahminDosyasi;
  simdiMs: number;
  adres: string;
  kapat: () => void;
}

/** Haritada seçilen otoparkın kısa özeti; ayrıntı durum sayfasında. */
export function OnIzleme({ otopark, dosya, simdiMs, adres, kapat }: Ozellikler) {
  const { ufuk } = etkinVaris(dosya.ufuklar, simdiMs);
  const gorunum = cevapGorunumu(cevapBul(otopark, ufuk), simdiMs);
  const parcalar = [
    gorunum.sayi !== '—' ? `${gorunum.sayi} ${gorunum.sayiAlt}` : null,
    ufuk ? metin.hedefSaat(saatYaz(ufuk.hedef_utc)) : null,
  ].filter((p) => p !== null);
  return (
    <section class="on-izleme" aria-label={otopark.ad}>
      <Simge ad={gorunum.simge} />
      <div class="on-izleme-metin">
        <b>{otopark.ad}</b>
        <span>
          {gorunum.etiket && <b class={`ton-${gorunum.ton}`}>{gorunum.etiket}</b>}
          {parcalar.length > 0 && ` · ${parcalar.join(' · ')}`}
        </span>
      </div>
      <button type="button" class="kapat" aria-label={metin.harita.kapat} onClick={kapat}>
        ×
      </button>
      <a class="dugme" href={adres}>
        {metin.detay.durumuGor}
      </a>
    </section>
  );
}
