import type { VeriDurumu } from '../alan/tazelik';
import { saatYaz, yasYaz } from '../metin/bicim';
import { metin } from '../metin/metinler';
import { Simge } from './Simge';

interface Ozellikler {
  veriUtc: string;
  durum: VeriDurumu;
  simdiMs: number;
}

export function VeriCipi({ veriUtc, durum, simdiMs }: Ozellikler) {
  return (
    <p class={`veri-cipi veri-cipi-${durum}`}>
      {durum === 'gecikmis' && <Simge ad="saat" />}
      {durum === 'cok_eski' && <Simge ad="uyari" />}
      <span>{metin.veriCipi(saatYaz(veriUtc), yasYaz(veriUtc, simdiMs))}</span>
    </p>
  );
}
