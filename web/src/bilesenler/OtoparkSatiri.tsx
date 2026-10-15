import type { Satir } from '../alan/liste';
import { ilceYaz, mesafeYaz } from '../metin/bicim';
import { metin } from '../metin/metinler';
import { otoparkAdresi } from '../uygulama/rota';
import { cevapGorunumu } from './cevapGorunumu';
import { Simge } from './Simge';

export function OtoparkSatiri({ satir, simdiMs }: { satir: Satir; simdiMs: number }) {
  const { otopark, cevap, mesafeM } = satir;
  const gorunum = cevapGorunumu(cevap, simdiMs);
  const ayrintilar = [
    otopark.ilce ? ilceYaz(otopark.ilce) : null,
    mesafeM !== null ? metin.konum.kisaMesafe(mesafeYaz(mesafeM)) : null,
  ].filter((parca) => parca !== null);
  return (
    <a class="satir" href={otoparkAdresi(otopark.park_id)} data-durum={cevap.tur}>
      <Simge ad={gorunum.simge} />
      <span class="satir-ad">{otopark.ad}</span>
      <span class="satir-alt">
        {gorunum.etiket && <b class={`ton-${gorunum.ton}`}>{gorunum.etiket}</b>}
        {ayrintilar.length > 0 && <span>{ayrintilar.join(' · ')}</span>}
      </span>
      <span class="satir-sayi">
        <b>{gorunum.sayi}</b>
        <small>{gorunum.sayiAlt}</small>
      </span>
    </a>
  );
}

export function SatirIskeleti() {
  return (
    <div class="satir satir-iskelet" aria-hidden="true">
      <span class="iskelet-daire" />
      <span class="iskelet-cizgi iskelet-uzun" />
      <span class="iskelet-cizgi iskelet-kisa" />
      <span class="iskelet-sayi" />
    </div>
  );
}
