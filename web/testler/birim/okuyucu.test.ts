import { describe, expect, it } from 'vitest';
import { anaSurum, tahminDosyasiOku } from '../../src/veri/oku';
import { ornekKopya } from './ornek';

function oku(ham: unknown) {
  const sonuc = tahminDosyasiOku(ham);
  if (sonuc.tur !== 'tamam') throw new Error(`okunamadı: ${sonuc.tur}`);
  return sonuc.dosya;
}

describe('tahmin dosyası okuyucu', () => {
  it('örnek dosyadaki 14 otoparkı okur', () => {
    expect(oku(ornekKopya()).otoparklar).toHaveLength(14);
  });

  it('bilinmeyen alanları yok sayar ve çıktıya taşımaz', () => {
    const ham = ornekKopya();
    ham.yeni_ust_alan = 'x';
    (ham.otoparklar[0] as Record<string, unknown>).yeni_alan = 42;
    const dosya = oku(ham);
    expect(dosya).not.toHaveProperty('yeni_ust_alan');
    expect(dosya.otoparklar[0]).not.toHaveProperty('yeni_alan');
  });

  it('tanınmayan kapsam sebebini olduğu gibi tutar', () => {
    const ham = ornekKopya();
    (ham.otoparklar[7] as Record<string, unknown>).kapsam_sebebi = 'yeni_bir_sebep';
    expect(oku(ham).otoparklar[7]?.kapsam_sebebi).toBe('yeni_bir_sebep');
  });

  it('tanınmayan bant kodu taşıyan otoparkı veri yok gibi gösterir', () => {
    const ham = ornekKopya();
    const ilk = ham.otoparklar[0];
    if (ilk?.tahminler?.[0]) (ilk.tahminler[0] as { bant: string }).bant = 'cok_dolu';
    const otopark = oku(ham).otoparklar[0];
    expect(otopark?.kapsam).toBe('veri_yok');
    expect(otopark?.tahminler).toBeNull();
  });

  it('tanınmayan kapsam değerini veri yok sayar', () => {
    const ham = ornekKopya();
    (ham.otoparklar[0] as { kapsam: string }).kapsam = 'yeni_kapsam';
    expect(oku(ham).otoparklar[0]?.kapsam).toBe('veri_yok');
  });

  it('eksik isteğe bağlı alanı boş sayar', () => {
    const ham = ornekKopya();
    delete (ham as Record<string, unknown>).aralik_duzeyi;
    expect(oku(ham).aralik_duzeyi).toBeNull();
  });

  it('bozuk tek bir otoparkı atlar, dosyanın kalanını okur', () => {
    const ham = ornekKopya();
    (ham.otoparklar[0] as Record<string, unknown>).park_id = 'bir';
    expect(oku(ham).otoparklar).toHaveLength(13);
  });

  it('zorunlu üst alan eksikse dosyayı bozuk sayar', () => {
    const ham = ornekKopya();
    delete (ham as Record<string, unknown>).veri_utc;
    expect(tahminDosyasiOku(ham).tur).toBe('bozuk');
  });

  it('nesne olmayan içeriği bozuk sayar', () => {
    expect(tahminDosyasiOku('metin').tur).toBe('bozuk');
    expect(tahminDosyasiOku(null).tur).toBe('bozuk');
  });
});

describe('şema sürümü', () => {
  it('ana sürümü okur', () => {
    expect(anaSurum('0.1.1')).toBe(0);
    expect(anaSurum('1.0.0')).toBe(1);
    expect(anaSurum('12.3.4-taslak')).toBe(12);
  });

  it('sürüm biçimi tanınmazsa ana sürüm yoktur', () => {
    expect(anaSurum('sürüm bir')).toBeNull();
    expect(anaSurum('1.0')).toBeNull();
  });

  it('ana sürümü 0 olmayan dosyayı uyumsuz sayar', () => {
    const ham = ornekKopya();
    ham.sema_surumu = '1.0.0';
    expect(tahminDosyasiOku(ham)).toEqual({ tur: 'uyumsuz', surum: '1.0.0' });
  });

  it('ara ve yama sürümü farklı olsa da okur', () => {
    const ham = ornekKopya();
    ham.sema_surumu = '0.7.3';
    expect(tahminDosyasiOku(ham).tur).toBe('tamam');
  });

  it('sürüm biçimi bozuksa dosyayı bozuk sayar', () => {
    const ham = ornekKopya();
    ham.sema_surumu = 'yeni';
    expect(tahminDosyasiOku(ham).tur).toBe('bozuk');
  });
});
