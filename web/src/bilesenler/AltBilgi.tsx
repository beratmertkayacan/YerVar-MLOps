import { metin } from '../metin/metinler';
import { rota } from '../uygulama/rota';

export function AltBilgi() {
  return (
    <footer class="alt-bilgi">
      <p>{metin.altBilgi}</p>
      {rota.value.ekran !== 'hakkinda' && (
        <a class="baglanti" href="#/hakkinda">
          {metin.gezinme.hakkinda}
        </a>
      )}
    </footer>
  );
}
