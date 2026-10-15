import type { TahminDosyasi } from '../veri/sozlesme';

export type VeriDurumu = 'guncel' | 'gecikmis' | 'cok_eski';

/**
 * Dosyanın yaşını eşikle karşılaştırır. Bütün ufukların hedef saati geçtiyse dosya çok eskidir;
 * değilse yaş eşiği aştığında gecikmiştir. Eşik dosyadan okunur.
 */
export function veriDurumu(
  dosya: Pick<TahminDosyasi, 'veri_utc' | 'tazelik_esigi_dk' | 'ufuklar'>,
  simdiMs: number,
): VeriDurumu {
  const gelecekUfukVar = dosya.ufuklar.some((u) => Date.parse(u.hedef_utc) >= simdiMs);
  if (!gelecekUfukVar) return 'cok_eski';
  const yasMs = simdiMs - Date.parse(dosya.veri_utc);
  return yasMs > dosya.tazelik_esigi_dk * 60_000 ? 'gecikmis' : 'guncel';
}
