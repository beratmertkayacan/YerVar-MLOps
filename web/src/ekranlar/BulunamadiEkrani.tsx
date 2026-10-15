import { AltBilgi } from '../bilesenler/AltBilgi';
import { metin } from '../metin/metinler';

export function BulunamadiEkrani() {
  return (
    <div class="sayfa metin-sayfasi">
      <h1>{metin.bulunamadi.baslik}</h1>
      <p>{metin.bulunamadi.aciklama}</p>
      <a class="dugme" href="#/">
        {metin.bulunamadi.donus}
      </a>
      <AltBilgi />
    </div>
  );
}
