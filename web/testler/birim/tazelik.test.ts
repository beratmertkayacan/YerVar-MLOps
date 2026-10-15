import { describe, expect, it } from 'vitest';
import { veriDurumu } from '../../src/alan/tazelik';

const DK = 60_000;
const VERI = Date.parse('2026-10-16T05:05:00Z');
const dosya = {
  veri_utc: '2026-10-16T05:05:00Z',
  tazelik_esigi_dk: 15,
  ufuklar: [
    { ufuk_dk: 15, hedef_utc: '2026-10-16T05:20:00Z', gun_tipi_kod: 'is_gunu' },
    { ufuk_dk: 120, hedef_utc: '2026-10-16T07:05:00Z', gun_tipi_kod: 'is_gunu' },
  ],
};

describe('veri durumu', () => {
  it('eşiğe kadar günceldir, eşik dahil', () => {
    expect(veriDurumu(dosya, VERI + 3 * DK)).toBe('guncel');
    expect(veriDurumu(dosya, VERI + 15 * DK)).toBe('guncel');
  });

  it('eşiği bir an geçince gecikmiştir', () => {
    expect(veriDurumu(dosya, VERI + 15 * DK + 1)).toBe('gecikmis');
  });

  it('eşiği dosyadan okur', () => {
    expect(veriDurumu({ ...dosya, tazelik_esigi_dk: 30 }, VERI + 20 * DK)).toBe('guncel');
  });

  it('son ufkun hedef saatinde hâlâ gecikmiştir', () => {
    expect(veriDurumu(dosya, VERI + 120 * DK)).toBe('gecikmis');
  });

  it('bütün ufukların hedef saati geçince çok eskidir', () => {
    expect(veriDurumu(dosya, VERI + 120 * DK + 1)).toBe('cok_eski');
  });

  it('ufuk listesi boşsa çok eskidir', () => {
    expect(veriDurumu({ ...dosya, ufuklar: [] }, VERI)).toBe('cok_eski');
  });
});
