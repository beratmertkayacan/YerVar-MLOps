import { metin } from '../metin/metinler';
import type { Bant, BantKalibrasyonu, Esikler } from '../veri/sozlesme';

/**
 * Bandın gözlenen dolu oranını "10 tahminden kaç" sayısına çevirir. Yarım her zaman yukarı gider;
 * Python'un `round` fonksiyonu 2,5'i 2'ye indirdiği için sunucuyla aynı kural burada yazılıdır.
 */
export function onTahmindeKac(gercekDoluOrani: number): number {
  return Math.min(10, Math.max(0, Math.floor(gercekDoluOrani * 10 + 0.5)));
}

/** Sıklık cümlesi yalnızca eşikler kesinleşmişken ve o bandın kalibrasyon satırı varken yazılır. */
export function siklikCumlesi(
  bant: Bant,
  esikler: Esikler,
  kalibrasyon: BantKalibrasyonu[] | null,
): string | null {
  if (esikler.bant_esikleri_gecici) return null;
  const satir = kalibrasyon?.find((k) => k.bant === bant);
  if (!satir) return null;
  const ad = metin.bant[bant].kisa;
  const n = onTahmindeKac(satir.gercek_dolu_orani);
  if (n === 0) return metin.siklik.neredeyseHic(ad);
  if (n === 10) return metin.siklik.neredeyseHepsi(ad);
  return metin.siklik.yaklasik(ad, n);
}
