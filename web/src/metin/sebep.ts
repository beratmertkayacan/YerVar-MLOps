import { metin } from './metinler';

const sebepler: Record<string, string> = metin.kapsam.sebep;

/** Kapsam sebebinin açıklaması; tanınmayan ya da boş kodda genel metne düşer. */
export function sebepMetni(kod: string | null): string {
  if (kod === null || !Object.hasOwn(sebepler, kod)) return metin.kapsam.sebepBilinmiyor;
  return sebepler[kod] ?? metin.kapsam.sebepBilinmiyor;
}
