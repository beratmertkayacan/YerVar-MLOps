import { describe, expect, it } from 'vitest';
import { vitrinMetni } from '../../src/metin/vitrinMetni';

describe('ekran kodu', () => {
  it('vitrin metinlerinde de yer tutucu ardına ek ya da yüzde yoktur', () => {
    const metinler = Object.values(vitrinMetni);
    expect(metinler.filter((m) => /[%'’]/.test(m))).toEqual([]);
  });

  const kaynaklar = import.meta.glob<string>(
    ['../../src/ekranlar/*.tsx', '../../src/bilesenler/*.tsx', '../../src/uygulama/*.tsx'],
    { query: '?raw', import: 'default', eager: true },
  );

  it('kullanıcıya görünen Türkçe metni kendisi yazmaz', () => {
    const turkceHarf = /[çğıöşüÇĞİÖŞÜ]/;
    const bulgular = Object.entries(kaynaklar).flatMap(([dosya, icerik]) =>
      icerik
        .split('\n')
        .filter((satir) => !/^(\/\/|\/\*|\*)/.test(satir.trim()) && turkceHarf.test(satir))
        .map((satir) => `${dosya}: ${satir.trim()}`),
    );
    expect(bulgular).toEqual([]);
  });
});
