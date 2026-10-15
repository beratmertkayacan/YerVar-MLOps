import type { Bant, Otopark, Ufuk } from '../veri/sozlesme';

/** Bir otoparkın seçili varış için ekranda gösterilecek cevabı. */
export type Cevap =
  | {
      tur: 'tahmin';
      bant: Bant | null;
      bos: number;
      alt: number | null;
      ust: number | null;
      doluOlasiligi: number | null;
      hedefUtc: string;
    }
  | { tur: 'basit'; bos: number; hedefUtc: string }
  | { tur: 'olcum'; bos: number; zamanUtc: string }
  | { tur: 'eski'; bos: number; zamanUtc: string }
  | { tur: 'veri_yok' }
  | { tur: 'gosterme' };

/**
 * `ufuk` boşsa "Şimdi" seçilidir ve son ölçüm gösterilir. Tahmin yalnızca taze otoparkta ve seçili ufukta
 * tahmin varsa gösterilir; yoksa son ölçüm "güncel tahmin yok" diye yazılır.
 */
export function cevapBul(otopark: Otopark, ufuk: Ufuk | null): Cevap {
  if (otopark.kapsam === 'gosterme') return { tur: 'gosterme' };
  if (otopark.kapsam === 'veri_yok') return { tur: 'veri_yok' };
  const olcum = otopark.son_olcum;
  if (!olcum) return { tur: 'veri_yok' };
  if (ufuk === null) return { tur: 'olcum', bos: olcum.bos_yer, zamanUtc: olcum.zaman_utc };
  const tahmin =
    otopark.tazelik === 'taze'
      ? otopark.tahminler?.find((t) => t.ufuk_dk === ufuk.ufuk_dk)
      : undefined;
  if (!tahmin) return { tur: 'eski', bos: olcum.bos_yer, zamanUtc: olcum.zaman_utc };
  if (otopark.kapsam === 'basit') {
    return { tur: 'basit', bos: tahmin.bos_yer, hedefUtc: ufuk.hedef_utc };
  }
  return {
    tur: 'tahmin',
    bant: tahmin.bant,
    bos: tahmin.bos_yer,
    alt: tahmin.bos_yer_alt,
    ust: tahmin.bos_yer_ust,
    doluOlasiligi: tahmin.dolu_olasiligi,
    hedefUtc: ufuk.hedef_utc,
  };
}
