import type { Cevap } from '../alan/cevap';
import { saatYaz, sayiYaz, yasYaz } from '../metin/bicim';
import { metin } from '../metin/metinler';
import type { SimgeAdi } from './Simge';

export interface CevapGorunumu {
  simge: SimgeAdi;
  /** Bandın ya da durumun kısa adı; rengini `ton` belirler. */
  etiket: string;
  ton: SimgeAdi;
  sayi: string;
  sayiAlt: string;
}

/** Bir cevabın satırda ve harita işaretinde nasıl görüneceği: simge, kısa etiket, ana sayı. */
export function cevapGorunumu(cevap: Cevap, simdiMs: number): CevapGorunumu {
  switch (cevap.tur) {
    case 'tahmin': {
      const sayi =
        cevap.alt !== null && cevap.ust !== null
          ? metin.aralikKisa(sayiYaz(cevap.alt), sayiYaz(cevap.ust))
          : `~${sayiYaz(cevap.bos)}`;
      const ton = cevap.bant ?? 'olcum';
      const etiket = cevap.bant ? metin.bant[cevap.bant].kisa : '';
      return { simge: ton, etiket, ton, sayi, sayiAlt: metin.bosYer };
    }
    case 'basit':
      return {
        simge: 'basit',
        etiket: metin.basit.kisa,
        ton: 'basit',
        sayi: `≈${sayiYaz(cevap.bos)}`,
        sayiAlt: metin.bosYer,
      };
    case 'olcum':
      return {
        simge: 'olcum',
        etiket: metin.olcum.kisa,
        ton: 'olcum',
        sayi: sayiYaz(cevap.bos),
        sayiAlt: metin.bosYer,
      };
    case 'eski':
      return {
        simge: 'saat',
        etiket: metin.olcum.ne(saatYaz(cevap.zamanUtc), yasYaz(cevap.zamanUtc, simdiMs)),
        ton: 'olcum',
        sayi: sayiYaz(cevap.bos),
        sayiAlt: metin.bosYer,
      };
    case 'veri_yok':
    case 'gosterme':
      return {
        simge: 'veri_yok',
        etiket: metin.kapsam.veriYok,
        ton: 'veri_yok',
        sayi: '—',
        sayiAlt: '',
      };
  }
}
