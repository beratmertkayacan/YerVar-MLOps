export interface Konum {
  lat: number;
  lng: number;
}

const DUNYA_YARICAPI_M = 6_371_000;
const YURUME_M_DK = 80;

/** İki nokta arasındaki kuş uçuşu mesafe (metre), haversine formülüyle. */
export function kusUcusuMetre(a: Konum, b: Konum): number {
  const radyan = (derece: number) => (derece * Math.PI) / 180;
  const dLat = radyan(b.lat - a.lat);
  const dLng = radyan(b.lng - a.lng);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(radyan(a.lat)) * Math.cos(radyan(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * DUNYA_YARICAPI_M * Math.asin(Math.sqrt(h));
}

export function yurumeDakika(metre: number): number {
  return Math.max(1, Math.ceil(metre / YURUME_M_DK));
}
