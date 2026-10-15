import { metin } from '../metin/metinler';
import { rota } from '../uygulama/rota';
import { Arama } from './Arama';
import { Logo } from './Logo';
import { Simge } from './Simge';

const BAGLANTILAR = [
  { adres: '#/', ekran: 'ana', ad: metin.gezinme.harita },
  { adres: '#/liste', ekran: 'liste', ad: metin.gezinme.liste },
  { adres: '#/hakkinda', ekran: 'hakkinda', ad: metin.gezinme.hakkinda },
] as const;

function Baglantilar() {
  const ekran = rota.value.ekran;
  return (
    <ul>
      {BAGLANTILAR.map((b) => (
        <li key={b.adres}>
          <a href={b.adres} aria-current={ekran === b.ekran ? 'page' : undefined}>
            {b.ad}
          </a>
        </li>
      ))}
    </ul>
  );
}

export function UstBaslik() {
  return (
    <div class="ust-baslik">
      <Logo />
      <Arama />
      <nav class="ust-gezinme" aria-label={metin.gezinme.etiket}>
        <Baglantilar />
      </nav>
      <details class="menu">
        <summary aria-label={metin.gezinme.menu}>
          <Simge ad="menu" />
        </summary>
        <nav aria-label={metin.gezinme.etiket}>
          <Baglantilar />
        </nav>
      </details>
    </div>
  );
}
