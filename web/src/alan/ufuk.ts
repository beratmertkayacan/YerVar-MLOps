import type { Ufuk } from '../veri/sozlesme';

export const VARSAYILAN_VARIS_DK = 30;

/** Seçilen varış anına hedef saati en yakın, henüz geçmemiş ufku döner; ara değer uydurmaz. */
export function ufukSec(ufuklar: Ufuk[], simdiMs: number, varisDk: number): Ufuk | null {
  const varisMs = simdiMs + varisDk * 60_000;
  let secilen: Ufuk | null = null;
  let enKucukFark = Number.POSITIVE_INFINITY;
  for (const ufuk of ufuklar) {
    const hedefMs = Date.parse(ufuk.hedef_utc);
    if (hedefMs < simdiMs) continue;
    const fark = Math.abs(hedefMs - varisMs);
    if (fark < enKucukFark) {
      secilen = ufuk;
      enKucukFark = fark;
    }
  }
  return secilen;
}

/** Varış seçicideki seçenekler (dk); 0 = "Şimdi", yani son ölçüm. */
export const VARIS_SECENEKLERI = [0, 15, 30, 60, 120] as const;

export function varisUfku(ufuklar: Ufuk[], simdiMs: number, varisDk: number): Ufuk | null {
  return varisDk === 0 ? null : ufukSec(ufuklar, simdiMs, varisDk);
}
