import { describe, expect, it } from 'vitest';
import { metin } from '../../src/metin/metinler';
import { sebepMetni } from '../../src/metin/sebep';

const IZ = '⟦x⟧';

function hepsiniTopla(deger: unknown, cikti: string[] = []): string[] {
  if (typeof deger === 'string') cikti.push(deger);
  else if (typeof deger === 'function') cikti.push(String(deger(IZ, IZ, IZ)));
  else if (deger && typeof deger === 'object') {
    for (const alt of Object.values(deger)) hepsiniTopla(alt, cikti);
  }
  return cikti;
}

const butunMetinler = hepsiniTopla(metin);

describe('mikro metinler', () => {
  it('bir yer tutucunun hemen ardına ek getirmez', () => {
    const ekli = butunMetinler.filter((m) => m.includes(`${IZ}'`) || m.includes(`${IZ}’`));
    expect(ekli).toEqual([]);
  });

  it('kaçınılacak sözcükleri kullanmaz', () => {
    const yasakli = /kesin|%100|yapay zek|garanti(?! değil)/i;
    expect(butunMetinler.filter((m) => yasakli.test(m))).toEqual([]);
  });

  it('ana metinlerde yüzde işareti yoktur', () => {
    const { doluNe: _tanim, ...anaMetinler } = metin;
    expect(hepsiniTopla(anaMetinler).filter((m) => m.includes('%'))).toEqual([]);
  });
});

describe('kapsam sebebi', () => {
  it('bilinen kodun açıklamasını verir', () => {
    expect(sebepMetni('liste_disi')).toBe(metin.kapsam.sebep.liste_disi);
  });

  it('tanınmayan ya da boş kodda genel metne düşer', () => {
    expect(sebepMetni('yeni_bir_sebep')).toBe(metin.kapsam.sebepBilinmiyor);
    expect(sebepMetni('toString')).toBe(metin.kapsam.sebepBilinmiyor);
    expect(sebepMetni(null)).toBe(metin.kapsam.sebepBilinmiyor);
  });
});
