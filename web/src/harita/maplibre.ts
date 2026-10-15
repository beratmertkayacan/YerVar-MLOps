import { Map as HaritaMotoru, Marker, setWorkerUrl } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import isciAdresi from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

// Vite, kütüphanenin işçi dosyasını kendiliğinden bulamıyor; adresi açıkça veriyoruz.
setWorkerUrl(isciAdresi);

const STIL = 'https://tiles.openfreemap.org/styles/positron';
const ISTANBUL: [[number, number], [number, number]] = [
  [28.6, 40.8],
  [29.45, 41.25],
];

export type Harita = HaritaMotoru;

export function haritaOlustur(kap: HTMLElement, hazir: () => void, hata: () => void): Harita {
  const harita = new HaritaMotoru({
    container: kap,
    style: STIL,
    bounds: ISTANBUL,
    fitBoundsOptions: { padding: 24 },
    attributionControl: { compact: true },
    dragRotate: false,
    pitchWithRotate: false,
  });
  harita.touchZoomRotate.disableRotation();
  let yuklendi = false;
  harita.once('load', () => {
    yuklendi = true;
    // Altlığın kendi otopark simgeleri bizim işaretlerimizle karışmasın.
    for (const katman of harita.getStyle().layers ?? []) {
      if (katman.type === 'symbol' && /park/i.test(katman.id)) {
        harita.setLayoutProperty(katman.id, 'visibility', 'none');
      }
    }
    hazir();
  });
  harita.on('error', () => {
    if (!yuklendi) hata();
  });
  return harita;
}

export function isaretEkle(harita: Harita, lng: number, lat: number, eleman: HTMLElement): Marker {
  return new Marker({ element: eleman }).setLngLat([lng, lat]).addTo(harita);
}
