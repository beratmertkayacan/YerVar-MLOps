import { Simge } from './Simge';

export function Serit({ tur, children }: { tur: 'uyari' | 'hata'; children: string }) {
  return (
    <p class={`serit serit-${tur}`} role="status">
      <Simge ad={tur} />
      <span>{children}</span>
    </p>
  );
}
