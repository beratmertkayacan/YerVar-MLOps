import { describe, expect, it } from 'vitest';
import { rotaCoz } from '../../src/uygulama/rota';

describe('rota', () => {
  it('bilinen adresleri çözer', () => {
    expect(rotaCoz('')).toEqual({ ekran: 'ana' });
    expect(rotaCoz('#/')).toEqual({ ekran: 'ana' });
    expect(rotaCoz('#/liste')).toEqual({ ekran: 'liste' });
    expect(rotaCoz('#/hakkinda')).toEqual({ ekran: 'hakkinda' });
  });

  it('otopark adresinden numarayı okur', () => {
    expect(rotaCoz('#/otopark/1021')).toEqual({ ekran: 'otopark', id: 1021 });
  });

  it('bilinmeyen adreste "bulunamadı" der', () => {
    expect(rotaCoz('#/otopark/abc')).toEqual({ ekran: 'bulunamadi' });
    expect(rotaCoz('#/yok')).toEqual({ ekran: 'bulunamadi' });
  });
});
