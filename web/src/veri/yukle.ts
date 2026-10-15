import { signal } from '@preact/signals';
import { saatiDosyayaGoreAyarla } from '../zaman/saat';
import { tahminDosyasiOku } from './oku';
import type { TahminDosyasi } from './sozlesme';

export type Yukleme =
  | { tur: 'yukleniyor' }
  | { tur: 'hazir'; dosya: TahminDosyasi }
  | { tur: 'hata' }
  | { tur: 'uyumsuz' };

const ZAMAN_ASIMI_MS = 15_000;
const disAdres = import.meta.env.VITE_VERI_URL;

/** Veri adresi verilmediyse uygulama örnek dosyayla, prototip olarak çalışır. */
export const prototip = !disAdres;
const veriAdresi = disAdres || `${import.meta.env.BASE_URL}ornek/son.json`;

export const yukleme = signal<Yukleme>({ tur: 'yukleniyor' });
export const cevrimdisi = signal(!navigator.onLine);

export async function veriyiYukle(): Promise<void> {
  yukleme.value = { tur: 'yukleniyor' };
  const iptal = new AbortController();
  const zamanAsimi = setTimeout(() => iptal.abort(), ZAMAN_ASIMI_MS);
  try {
    const yanit = await fetch(veriAdresi, { cache: 'no-cache', signal: iptal.signal });
    if (!yanit.ok) {
      yukleme.value = { tur: 'hata' };
      return;
    }
    const sonuc = tahminDosyasiOku(await yanit.json());
    if (sonuc.tur === 'tamam') {
      saatiDosyayaGoreAyarla(sonuc.dosya.uretim_utc, prototip);
      yukleme.value = { tur: 'hazir', dosya: sonuc.dosya };
    } else {
      yukleme.value = { tur: sonuc.tur === 'uyumsuz' ? 'uyumsuz' : 'hata' };
    }
  } catch {
    yukleme.value = { tur: 'hata' };
  } finally {
    clearTimeout(zamanAsimi);
  }
}

export function baglantiyiIzle(): void {
  addEventListener('online', () => {
    cevrimdisi.value = false;
  });
  addEventListener('offline', () => {
    cevrimdisi.value = true;
  });
}
