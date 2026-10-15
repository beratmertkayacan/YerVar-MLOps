import { VARIS_SECENEKLERI, varisUfku } from '../alan/ufuk';
import { saatYaz } from '../metin/bicim';
import { metin } from '../metin/metinler';
import { varisDk, varisSec } from '../uygulama/durum';
import type { TahminDosyasi } from '../veri/sozlesme';

interface Ozellikler {
  dosya: TahminDosyasi;
  simdiMs: number;
  /** Seçili seçenek geçmişte kaldıysa gerçekte kullanılan varış (dk). */
  etkinDk: number;
}

/** Varış seçici: bir radyo grubu, klavyeyle oklarla gezilir. Hedef saati geçmiş seçenek seçilemez. */
export function VarisSecici({ dosya, simdiMs, etkinDk }: Ozellikler) {
  return (
    <fieldset class="varis">
      <legend class="gorsel-gizli">{metin.varis.baslik}</legend>
      {VARIS_SECENEKLERI.map((dk) => {
        const ufuk = varisUfku(dosya.ufuklar, simdiMs, dk);
        const gecerli = dk === 0 || ufuk !== null;
        const saat = dk === 0 ? saatYaz(dosya.veri_utc) : ufuk ? saatYaz(ufuk.hedef_utc) : '—';
        return (
          <label key={dk} class="varis-secenek">
            <input
              type="radio"
              name="varis"
              value={dk}
              checked={etkinDk === dk}
              disabled={!gecerli}
              onChange={() => varisSec(dk)}
            />
            <span>{dk === 0 ? metin.varis.simdi : metin.varis.secenek(dk)}</span>
            <small>{saat}</small>
          </label>
        );
      })}
      {varisDk.value === 0 && <p class="varis-not">{metin.varis.simdiAciklama}</p>}
    </fieldset>
  );
}
