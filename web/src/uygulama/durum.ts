import { signal } from '@preact/signals';
import type { Konum } from '../alan/mesafe';
import { VARIS_SECENEKLERI, VARSAYILAN_VARIS_DK, varisUfku } from '../alan/ufuk';
import type { Ufuk } from '../veri/sozlesme';

const VARIS_ANAHTARI = 'yervar.varis';

function kayitliVaris(): number {
  try {
    const kayit = localStorage.getItem(VARIS_ANAHTARI);
    const deger = Number(kayit);
    return kayit !== null && (VARIS_SECENEKLERI as readonly number[]).includes(deger)
      ? deger
      : VARSAYILAN_VARIS_DK;
  } catch {
    return VARSAYILAN_VARIS_DK;
  }
}

/** Seçili varış (dk). Cihazda yalnızca bu tercih saklanır. */
export const varisDk = signal(kayitliVaris());

export function varisSec(dk: number): void {
  varisDk.value = dk;
  try {
    localStorage.setItem(VARIS_ANAHTARI, String(dk));
  } catch {
    // Gizli pencerede depolama kapalı olabilir; tercih yalnızca bu oturumda kalır.
  }
}

export type KonumDurumu = 'yok' | 'bekliyor' | 'reddedildi' | 'var';

// Konum yalnızca bellekte tutulur; URL'ye ve cihaz deposuna yazılmaz.
export const konum = signal<Konum | null>(null);
export const konumDurumu = signal<KonumDurumu>('yok');

export function konumIste(): void {
  if (!('geolocation' in navigator)) {
    konumDurumu.value = 'reddedildi';
    return;
  }
  konumDurumu.value = 'bekliyor';
  navigator.geolocation.getCurrentPosition(
    (sonuc) => {
      konum.value = { lat: sonuc.coords.latitude, lng: sonuc.coords.longitude };
      konumDurumu.value = 'var';
    },
    () => {
      konumDurumu.value = 'reddedildi';
    },
    { timeout: 10_000, maximumAge: 60_000 },
  );
}

/** Kullanıcı daha önce izin verdiyse konumu sormadan alır; izin yoksa hiçbir şey sormaz. */
export async function izinVarsaKonumuAl(): Promise<void> {
  try {
    const izin = await navigator.permissions?.query({ name: 'geolocation' });
    if (izin?.state === 'granted') konumIste();
  } catch {
    // Permissions API olmayan tarayıcıda konum yalnızca düğmeyle istenir.
  }
}

/** Haritada seçili otopark (önizleme kartı için). */
export const seciliOtopark = signal<number | null>(null);

/** Seçili varışın gerçekte kullanılan hâli: ufku geçmişte kaldıysa "Şimdi"ye düşer. */
export function etkinVaris(ufuklar: Ufuk[], simdiMs: number): { dk: number; ufuk: Ufuk | null } {
  const ufuk = varisUfku(ufuklar, simdiMs, varisDk.value);
  return ufuk ? { dk: varisDk.value, ufuk } : { dk: 0, ufuk: null };
}
