import type { Satir } from '../alan/liste';
import { OtoparkSatiri, SatirIskeleti } from './OtoparkSatiri';

export function OtoparkListesi({ satirlar, simdiMs }: { satirlar: Satir[]; simdiMs: number }) {
  return (
    <ul class="otopark-listesi">
      {satirlar.map((satir) => (
        <li key={satir.otopark.park_id}>
          <OtoparkSatiri satir={satir} simdiMs={simdiMs} />
        </li>
      ))}
    </ul>
  );
}

export function IskeletListesi({ adet }: { adet: number }) {
  return (
    <ul class="otopark-listesi" aria-hidden="true">
      {Array.from({ length: adet }, (_, sira) => (
        <li key={sira}>
          <SatirIskeleti />
        </li>
      ))}
    </ul>
  );
}
