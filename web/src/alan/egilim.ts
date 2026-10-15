import type { Tahmin } from '../veri/sozlesme';

export type Egilim = 'azaliyor' | 'artiyor' | null;

/**
 * İlk ve son ufuk arasındaki boş yer değişimi belirginse yönünü söyler. "Belirgin": en az 5 araç ve
 * ilk ufuktaki boş yerin en az dörtte biri; küçük oynamalar için uyarı göstermeyiz.
 */
export function egilimBul(tahminler: Tahmin[] | null): Egilim {
  if (!tahminler || tahminler.length < 2) return null;
  const sirali = [...tahminler].sort((a, b) => a.ufuk_dk - b.ufuk_dk);
  const ilk = sirali[0];
  const son = sirali[sirali.length - 1];
  if (!ilk || !son) return null;
  const fark = son.bos_yer - ilk.bos_yer;
  const esik = Math.max(5, ilk.bos_yer * 0.25);
  if (fark <= -esik) return 'azaliyor';
  if (fark >= esik) return 'artiyor';
  return null;
}
