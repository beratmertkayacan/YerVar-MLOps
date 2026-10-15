import { describe, expect, it } from 'vitest';
import { onTahmindeKac, siklikCumlesi } from '../../src/alan/siklik';

const kesinEsikler = {
  dolu_oran: 0.05,
  dolu_en_fazla_arac: 10,
  dolu_olasilik_esigi: 0.5,
  bant_alt: 0.2,
  bant_ust: 0.6,
  bant_esikleri_gecici: false,
};
const kalibrasyon = (oran: number) => [
  { bant: 'belirsiz' as const, ort_olasilik: 0.37, gercek_dolu_orani: oran, ornek_sayisi: 5320 },
];

describe('10 tahminde kaç', () => {
  it.each([
    [0.04, 0],
    [0.05, 1],
    [0.25, 3],
    [0.96, 10],
  ])('%s oranı %s olur (yarım yukarı)', (oran, beklenen) => {
    expect(onTahmindeKac(oran)).toBe(beklenen);
  });

  it('0 ile 10 dışına çıkmaz', () => {
    expect(onTahmindeKac(-0.2)).toBe(0);
    expect(onTahmindeKac(1.4)).toBe(10);
  });
});

describe('sıklık cümlesi', () => {
  it('bütün otoparklar için tek kalibrasyon olduğunu söyler', () => {
    expect(siklikCumlesi('belirsiz', kesinEsikler, kalibrasyon(0.4))).toBe(
      'Geçmişte tüm otoparklar için "Belirsiz" dediğimiz her 10 tahminden yaklaşık 4 tanesinde otopark dolu çıktı.',
    );
  });

  it('n = 0 ve n = 10 için ayrı cümle kurar', () => {
    expect(siklikCumlesi('belirsiz', kesinEsikler, kalibrasyon(0.02))).toContain('neredeyse hiç');
    expect(siklikCumlesi('belirsiz', kesinEsikler, kalibrasyon(0.97))).toContain(
      'neredeyse hepsinde',
    );
  });

  it('eşikler geçiciyken yazılmaz', () => {
    const geciciEsikler = { ...kesinEsikler, bant_esikleri_gecici: true };
    expect(siklikCumlesi('belirsiz', geciciEsikler, kalibrasyon(0.4))).toBeNull();
  });

  it('bandın kalibrasyon satırı yoksa yazılmaz', () => {
    expect(siklikCumlesi('dolu_olasi', kesinEsikler, kalibrasyon(0.4))).toBeNull();
    expect(siklikCumlesi('belirsiz', kesinEsikler, null)).toBeNull();
  });
});
