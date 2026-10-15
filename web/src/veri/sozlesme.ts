export type Bant = 'yer_var_olasi' | 'belirsiz' | 'dolu_olasi';
export type Kapsam = 'model' | 'basit' | 'veri_yok' | 'gosterme';
export type Tazelik = 'taze' | 'eski';

export interface GunTipi {
  tarih_yerel: string;
  kod: string;
  ad: string | null;
  yarim_gun_baslangic_yerel: string | null;
  model_taniyor: boolean;
}

export interface Ufuk {
  ufuk_dk: number;
  hedef_utc: string;
  gun_tipi_kod: string;
}

export interface Esikler {
  dolu_oran: number;
  dolu_en_fazla_arac: number;
  dolu_olasilik_esigi: number;
  bant_alt: number | null;
  bant_ust: number | null;
  bant_esikleri_gecici: boolean;
}

export interface KarneSatiri {
  ufuk_dk: number;
  mae_arac: number;
  beceri: number;
  brier: number | null;
}

export interface BantKalibrasyonu {
  bant: Bant;
  ort_olasilik: number;
  gercek_dolu_orani: number;
  ornek_sayisi: number;
}

export interface Model {
  surum: string;
  olasilik_surum: string | null;
  kod_surumu: string;
  egitim_bitis_tarihi: string;
  karne: KarneSatiri[] | null;
  bant_kalibrasyonu: BantKalibrasyonu[] | null;
}

export interface VeriSagligi {
  tarih: string;
  tur: number;
  tamlik: number;
  canli_otopark: number;
}

export interface KapsamSayilari {
  model: number;
  basit: number;
  veri_yok: number;
  gosterme: number;
  toplam: number;
}

export interface SonOlcum {
  zaman_utc: string;
  bos_yer: number;
  acik: boolean;
  dolu: boolean;
}

export interface Tahmin {
  ufuk_dk: number;
  bos_yer: number;
  bos_yer_alt: number | null;
  bos_yer_ust: number | null;
  dolu_olasiligi: number | null;
  bant: Bant | null;
}

export interface Otopark {
  park_id: number;
  ad: string;
  ilce: string | null;
  lat: number;
  lng: number;
  kapasite: number | null;
  tip: string | null;
  calisma_saatleri: string | null;
  kapsam: Kapsam;
  kapsam_sebebi: string | null;
  tazelik: Tazelik | null;
  son_olcum: SonOlcum | null;
  tahminler: Tahmin[] | null;
}

/** Tahmin dosyası (`son.json`), şema 0.1.x. */
export interface TahminDosyasi {
  sema_surumu: string;
  uretim_utc: string;
  veri_utc: string;
  saat_dilimi: string;
  tazelik_esigi_dk: number;
  gun_tipi: GunTipi;
  ufuklar: Ufuk[];
  esikler: Esikler;
  aralik_duzeyi: number | null;
  model: Model;
  veri_sagligi: VeriSagligi | null;
  kapsam_sayilari: KapsamSayilari;
  otoparklar: Otopark[];
}
