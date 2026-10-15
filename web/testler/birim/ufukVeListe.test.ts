import { describe, expect, it } from 'vitest';
import { listeOlustur } from '../../src/alan/liste';
import { ufukSec, varisUfku } from '../../src/alan/ufuk';
import { tahminDosyasiOku } from '../../src/veri/oku';
import { ornekKopya } from './ornek';

const DK = 60_000;
const ufuklar = [15, 30, 60, 120].map((dk) => ({
  ufuk_dk: dk,
  hedef_utc: new Date(Date.parse('2026-10-16T05:05:00Z') + dk * DK).toISOString(),
  gun_tipi_kod: 'is_gunu',
}));
const URETIM = Date.parse('2026-10-16T05:06:38Z');

describe('ufuk seçimi', () => {
  it('varış anına hedef saati en yakın ufku seçer', () => {
    expect(ufukSec(ufuklar, URETIM, 30)?.ufuk_dk).toBe(30);
    expect(ufukSec(ufuklar, URETIM, 50)?.ufuk_dk).toBe(60);
  });

  it('hedef saati geçmiş ufku seçmez', () => {
    expect(ufukSec(ufuklar, URETIM + 40 * DK, 0)?.ufuk_dk).toBe(60);
  });

  it('bütün ufuklar geçtiyse ufuk yoktur', () => {
    expect(ufukSec(ufuklar, URETIM + 3 * 60 * DK, 30)).toBeNull();
  });

  it('"Şimdi" seçiliyken ufuk yoktur, son ölçüm gösterilir', () => {
    expect(varisUfku(ufuklar, URETIM, 0)).toBeNull();
  });
});

describe('liste', () => {
  const sonuc = tahminDosyasiOku(ornekKopya());
  if (sonuc.tur !== 'tamam') throw new Error('örnek okunamadı');
  const { otoparklar } = sonuc.dosya;
  const otuz = ufukSec(sonuc.dosya.ufuklar, URETIM, 30);
  const kimlikler = (l: ReturnType<typeof listeOlustur>) =>
    l.siradakiler.map((s) => s.otopark.park_id);

  it('taze model tahminlerini dolu olasılığı artan sırada öne koyar', () => {
    const liste = listeOlustur(otoparklar, otuz, 'olasilik', null);
    expect(kimlikler(liste).slice(0, 3)).toEqual([1068, 1052, 1021]);
  });

  it('basit tahminleri modellerden sonra, eski veriyi en sona koyar', () => {
    const liste = listeOlustur(otoparklar, otuz, 'olasilik', null);
    expect(liste.siradakiler.map((s) => s.cevap.tur)).toEqual([
      'tahmin',
      'tahmin',
      'tahmin',
      'tahmin',
      'tahmin',
      'tahmin',
      'basit',
      'basit',
      'eski',
    ]);
  });

  it('veri yok ve gösterilmeyenleri ayrı döner', () => {
    const liste = listeOlustur(otoparklar, otuz, 'onerilen', null);
    expect(liste.veriYok).toHaveLength(3);
    expect(liste.gosterilmeyen).toHaveLength(2);
  });

  it('"Şimdi" seçiliyken son ölçümde boş yer oranı yüksek olanı öne koyar', () => {
    const liste = listeOlustur(otoparklar, null, 'olasilik', null);
    expect(liste.siradakiler.every((s) => s.cevap.tur === 'olcum')).toBe(true);
    expect(kimlikler(liste)[0]).toBe(1101);
  });

  it('konum varken yakınlık sırası mesafeye göredir', () => {
    const besiktas = { lat: 41.0422, lng: 29.0067 };
    const liste = listeOlustur(otoparklar, otuz, 'yakinlik', besiktas);
    expect(kimlikler(liste)[0]).toBe(1047);
    const mesafeler = liste.siradakiler.map((s) => s.mesafeM ?? 0);
    expect(mesafeler).toEqual([...mesafeler].sort((a, b) => a - b));
  });

  it('önerilen, konumun 1 km çevresinde 3 otoparktan azı varsa 2 km’ye genişler', () => {
    const besiktas = { lat: 41.0422, lng: 29.0067 };
    const liste = listeOlustur(otoparklar, otuz, 'onerilen', besiktas);
    expect(liste.yaricap?.genisledi).toBe(true);
    expect(liste.siradakiler.every((s) => (s.mesafeM ?? 0) <= 2000)).toBe(true);
  });
});
