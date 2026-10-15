import type { ComponentChildren } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { metin } from '../metin/metinler';
import type { TahminDosyasi } from '../veri/sozlesme';
import { veriyiYukle, yukleme } from '../veri/yukle';
import { DurumKarti } from './DurumKarti';

const UZUN_YUKLEME_MS = 3_000;

export function YuklemeIletisi() {
  const [uzun, setUzun] = useState(false);
  useEffect(() => {
    const zamanlayici = setTimeout(() => setUzun(true), UZUN_YUKLEME_MS);
    return () => clearTimeout(zamanlayici);
  }, []);
  return <span>{uzun ? metin.yukleme.uzun : metin.yukleme.suruyor}</span>;
}

interface Ozellikler {
  iskelet: ComponentChildren;
  children: (dosya: TahminDosyasi) => ComponentChildren;
}

/** Veri hazır değilken iskeleti ya da durum kartını, hazırken içeriği gösterir. */
export function VeriBekleyen({ iskelet, children }: Ozellikler) {
  const durum = yukleme.value;
  switch (durum.tur) {
    case 'yukleniyor':
      return <>{iskelet}</>;
    case 'hata':
      return (
        <DurumKarti
          ileti={metin.hata.ulasilamiyor}
          eylem={{ etiket: metin.hata.tekrarDene, yap: veriyiYukle }}
        />
      );
    case 'uyumsuz':
      return (
        <DurumKarti
          ileti={metin.hata.yeniSurum}
          eylem={{ etiket: metin.hata.yenile, yap: () => location.reload() }}
        />
      );
    case 'hazir':
      if (durum.dosya.otoparklar.length === 0)
        return <DurumKarti tur="bilgi" ileti={metin.hata.bosVeri} />;
      return <>{children(durum.dosya)}</>;
  }
}
