import ornek from '../../public/ornek/son.json';

/** Her test kendi kopyasını değiştirir; örnek dosya paylaşılmaz. */
export function ornekKopya(): Record<string, unknown> & typeof ornek {
  return structuredClone(ornek);
}
