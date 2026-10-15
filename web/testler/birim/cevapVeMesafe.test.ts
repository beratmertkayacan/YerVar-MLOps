import { describe, expect, it } from 'vitest';
import { cevapBul } from '../../src/alan/cevap';
import { egilimBul } from '../../src/alan/egilim';
import { kusUcusuMetre, yurumeDakika } from '../../src/alan/mesafe';
import { mesafeYaz } from '../../src/metin/bicim';
import { tahminDosyasiOku } from '../../src/veri/oku';
import { ornekKopya } from './ornek';

const sonuc = tahminDosyasiOku(ornekKopya());
if (sonuc.tur !== 'tamam') throw new Error('örnek okunamadı');
const { otoparklar, ufuklar } = sonuc.dosya;
const bul = (id: number) => {
  const o = otoparklar.find((x) => x.park_id === id);
  if (!o) throw new Error(`${id} yok`);
  return o;
};
const otuz = ufuklar.find((u) => u.ufuk_dk === 30) ?? null;

describe('otopark cevabı', () => {
  it('taze model otoparkta seçili ufkun bandını ve aralığını verir', () => {
    expect(cevapBul(bul(1034), otuz)).toMatchObject({
      tur: 'tahmin',
      bant: 'belirsiz',
      alt: 7,
      ust: 30,
    });
  });

  it('"Şimdi" seçiliyken son ölçümü verir', () => {
    expect(cevapBul(bul(1034), null)).toMatchObject({ tur: 'olcum', bos: 41 });
  });

  it('basit tahminde olasılık ve bant yoktur', () => {
    expect(cevapBul(bul(1093), otuz)).toMatchObject({ tur: 'basit', bos: 47 });
  });

  it('eski veride tahmin göstermez, son ölçümü verir', () => {
    expect(cevapBul(bul(1089), otuz)).toMatchObject({ tur: 'eski', bos: 37 });
  });

  it('veri yok ve gösterilmeyende sayı yoktur', () => {
    expect(cevapBul(bul(1112), otuz)).toEqual({ tur: 'veri_yok' });
    expect(cevapBul(bul(1146), otuz)).toEqual({ tur: 'gosterme' });
  });
});

describe('eğilim', () => {
  it('boş yer ufuk boyunca belirgin azalıyorsa "azalıyor" der', () => {
    expect(egilimBul(bul(1034).tahminler)).toBe('azaliyor');
  });

  it('küçük oynamada eğilim söylemez', () => {
    expect(egilimBul(bul(1052).tahminler)).toBeNull();
  });
});

describe('mesafe', () => {
  it('kuş uçuşu mesafeyi metre olarak hesaplar', () => {
    const m = kusUcusuMetre({ lat: 41.0422, lng: 29.0067 }, { lat: 41.06722, lng: 28.99459 });
    expect(m).toBeGreaterThan(2_900);
    expect(m).toBeLessThan(3_000);
  });

  it('yürüme süresini 80 m/dk ile yukarı yuvarlar', () => {
    expect(yurumeDakika(81)).toBe(2);
    expect(yurumeDakika(10)).toBe(1);
  });

  it('mesafeyi kısa ve uzun biçimde yazar', () => {
    expect(mesafeYaz(648)).toBe('650 m');
    expect(mesafeYaz(2_437)).toBe('2,4 km');
    expect(mesafeYaz(13_000)).toBe('13 km');
  });
});
