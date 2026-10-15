import { Simge } from './Simge';

interface Ozellikler {
  ileti: string;
  tur?: 'hata' | 'bilgi';
  eylem?: { etiket: string; yap: () => void };
}

/** Panelde içeriğin yerine geçen durum: hata, uyumsuz sürüm ya da boş veri. */
export function DurumKarti({ ileti, tur = 'hata', eylem }: Ozellikler) {
  return (
    <div class={`durum-karti durum-karti-${tur}`} role={tur === 'hata' ? 'alert' : 'status'}>
      <Simge ad={tur === 'hata' ? 'hata' : 'veri_yok'} />
      <p>{ileti}</p>
      {eylem && (
        <button type="button" class="dugme" onClick={eylem.yap}>
          {eylem.etiket}
        </button>
      )}
    </div>
  );
}
