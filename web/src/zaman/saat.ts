import { signal } from '@preact/signals';

const YENILEME_MS = 15_000;

let fark = 0;
let zamanlayici: ReturnType<typeof setInterval> | undefined;

/** Uygulamanın "şimdi"si (ms). Saatle ilgili her hesap buradan okur. */
export const simdi = signal(Date.now());

function guncelle(): void {
  simdi.value = Date.now() + fark;
}

function kur(baslangicMs: number): void {
  fark = baslangicMs - Date.now();
  guncelle();
}

export function saatiCalistir(): void {
  if (zamanlayici !== undefined) return;
  guncelle();
  zamanlayici = setInterval(guncelle, YENILEME_MS);
}

/**
 * Prototipte örnek dosya geçmiş bir güne ait; saat o dosyanın üretim anından başlayıp ilerler.
 * Geliştirmede `?saat=ISO` başka bir anı denemeyi sağlar.
 */
export function saatiDosyayaGoreAyarla(uretimUtc: string, prototip: boolean): void {
  if (import.meta.env.DEV) {
    const istenen = new URLSearchParams(location.search).get('saat');
    const ms = istenen ? Date.parse(istenen) : Number.NaN;
    if (!Number.isNaN(ms)) {
      kur(ms);
      return;
    }
  }
  if (prototip) kur(Date.parse(uretimUtc));
}
