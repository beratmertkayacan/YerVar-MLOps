import { signal } from '@preact/signals';

export type Rota =
  | { ekran: 'ana' }
  | { ekran: 'liste' }
  | { ekran: 'hakkinda' }
  | { ekran: 'otopark'; id: number }
  | { ekran: 'vitrin' }
  | { ekran: 'bulunamadi' };

export function rotaCoz(hash: string): Rota {
  const yol = hash.replace(/^#/, '') || '/';
  const otopark = /^\/otopark\/(\d+)$/.exec(yol);
  if (otopark) return { ekran: 'otopark', id: Number(otopark[1]) };
  switch (yol) {
    case '/':
      return { ekran: 'ana' };
    case '/liste':
      return { ekran: 'liste' };
    case '/hakkinda':
      return { ekran: 'hakkinda' };
    case '/vitrin':
      return import.meta.env.DEV ? { ekran: 'vitrin' } : { ekran: 'bulunamadi' };
    default:
      return { ekran: 'bulunamadi' };
  }
}

export const otoparkAdresi = (id: number) => `#/otopark/${id}`;

export const rota = signal<Rota>({ ekran: 'ana' });

export function rotayiIzle(): void {
  rota.value = rotaCoz(location.hash);
  addEventListener('hashchange', () => {
    rota.value = rotaCoz(location.hash);
  });
}
