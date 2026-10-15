import type {
  Bant,
  BantKalibrasyonu,
  Kapsam,
  Otopark,
  Tahmin,
  TahminDosyasi,
  Tazelik,
} from './sozlesme';

export type OkumaSonucu =
  | { tur: 'tamam'; dosya: TahminDosyasi }
  | { tur: 'uyumsuz'; surum: string }
  | { tur: 'bozuk' };

const DESTEKLENEN_ANA_SURUM = 0;
const BANTLAR: readonly string[] = ['yer_var_olasi', 'belirsiz', 'dolu_olasi'];
const KAPSAMLAR: readonly string[] = ['model', 'basit', 'veri_yok', 'gosterme'];

class BozukAlan extends Error {}
class BilinmeyenBant extends Error {}

type Ham = Record<string, unknown>;

function nesne(x: unknown): Ham {
  if (typeof x === 'object' && x !== null && !Array.isArray(x)) return x as Ham;
  throw new BozukAlan();
}

function dizi(x: unknown): unknown[] {
  if (Array.isArray(x)) return x;
  throw new BozukAlan();
}

function metin(x: unknown): string {
  if (typeof x === 'string') return x;
  throw new BozukAlan();
}

function sayi(x: unknown): number {
  if (typeof x === 'number' && Number.isFinite(x)) return x;
  throw new BozukAlan();
}

function mantik(x: unknown): boolean {
  if (typeof x === 'boolean') return x;
  throw new BozukAlan();
}

// Eksik alan ile null aynı sayılır; yeni bir üretici alanı hiç yazmayabilir.
function bosOlabilir<T>(x: unknown, oku: (x: unknown) => T): T | null {
  return x === null || x === undefined ? null : oku(x);
}

export function anaSurum(surum: string): number | null {
  const eslesme = /^(\d+)\.\d+\.\d+/.exec(surum);
  return eslesme ? Number(eslesme[1]) : null;
}

function bantOku(x: unknown): Bant | null {
  if (x === null || x === undefined) return null;
  if (typeof x === 'string' && BANTLAR.includes(x)) return x as Bant;
  throw new BilinmeyenBant();
}

function tahminOku(x: unknown): Tahmin {
  const t = nesne(x);
  return {
    ufuk_dk: sayi(t.ufuk_dk),
    bos_yer: sayi(t.bos_yer),
    bos_yer_alt: bosOlabilir(t.bos_yer_alt, sayi),
    bos_yer_ust: bosOlabilir(t.bos_yer_ust, sayi),
    dolu_olasiligi: bosOlabilir(t.dolu_olasiligi, sayi),
    bant: bantOku(t.bant),
  };
}

function otoparkOku(x: unknown): Otopark {
  const o = nesne(x);
  const kapsamHam = metin(o.kapsam);
  const otopark: Otopark = {
    park_id: sayi(o.park_id),
    ad: metin(o.ad),
    ilce: bosOlabilir(o.ilce, metin),
    lat: sayi(o.lat),
    lng: sayi(o.lng),
    kapasite: bosOlabilir(o.kapasite, sayi),
    tip: bosOlabilir(o.tip, metin),
    calisma_saatleri: bosOlabilir(o.calisma_saatleri, metin),
    kapsam: KAPSAMLAR.includes(kapsamHam) ? (kapsamHam as Kapsam) : 'veri_yok',
    kapsam_sebebi: KAPSAMLAR.includes(kapsamHam) ? bosOlabilir(o.kapsam_sebebi, metin) : null,
    // Tanınmayan tazelik değeri "eski" sayılır: emin olmadığımız tahmini göstermeyiz.
    tazelik: bosOlabilir(o.tazelik, (t) => (metin(t) === 'taze' ? 'taze' : 'eski') as Tazelik),
    son_olcum: bosOlabilir(o.son_olcum, (s) => {
      const so = nesne(s);
      return {
        zaman_utc: metin(so.zaman_utc),
        bos_yer: sayi(so.bos_yer),
        acik: mantik(so.acik),
        dolu: mantik(so.dolu),
      };
    }),
    tahminler: null,
  };
  try {
    otopark.tahminler = bosOlabilir(o.tahminler, (t) => dizi(t).map(tahminOku));
  } catch (hata) {
    if (!(hata instanceof BilinmeyenBant)) throw hata;
    return { ...otopark, kapsam: 'veri_yok', kapsam_sebebi: null, tahminler: null };
  }
  return otopark;
}

function kalibrasyonOku(x: unknown): BantKalibrasyonu[] {
  const satirlar: BantKalibrasyonu[] = [];
  for (const ham of dizi(x)) {
    const k = nesne(ham);
    if (typeof k.bant !== 'string' || !BANTLAR.includes(k.bant)) continue;
    satirlar.push({
      bant: k.bant as Bant,
      ort_olasilik: sayi(k.ort_olasilik),
      gercek_dolu_orani: sayi(k.gercek_dolu_orani),
      ornek_sayisi: sayi(k.ornek_sayisi),
    });
  }
  return satirlar;
}

function dosyaOku(k: Ham, surum: string): TahminDosyasi {
  const gun = nesne(k.gun_tipi);
  const esik = nesne(k.esikler);
  const model = nesne(k.model);
  const kapsam = nesne(k.kapsam_sayilari);
  const otoparklar: Otopark[] = [];
  for (const ham of dizi(k.otoparklar)) {
    try {
      otoparklar.push(otoparkOku(ham));
    } catch (hata) {
      // Tek bir bozuk kayıt bütün dosyayı düşürmesin.
      if (!(hata instanceof BozukAlan)) throw hata;
    }
  }
  return {
    sema_surumu: surum,
    uretim_utc: metin(k.uretim_utc),
    veri_utc: metin(k.veri_utc),
    saat_dilimi: metin(k.saat_dilimi),
    tazelik_esigi_dk: sayi(k.tazelik_esigi_dk),
    gun_tipi: {
      tarih_yerel: metin(gun.tarih_yerel),
      kod: metin(gun.kod),
      ad: bosOlabilir(gun.ad, metin),
      yarim_gun_baslangic_yerel: bosOlabilir(gun.yarim_gun_baslangic_yerel, metin),
      model_taniyor: mantik(gun.model_taniyor),
    },
    ufuklar: dizi(k.ufuklar).map((u) => {
      const uf = nesne(u);
      return {
        ufuk_dk: sayi(uf.ufuk_dk),
        hedef_utc: metin(uf.hedef_utc),
        gun_tipi_kod: metin(uf.gun_tipi_kod),
      };
    }),
    esikler: {
      dolu_oran: sayi(esik.dolu_oran),
      dolu_en_fazla_arac: sayi(esik.dolu_en_fazla_arac),
      dolu_olasilik_esigi: sayi(esik.dolu_olasilik_esigi),
      bant_alt: bosOlabilir(esik.bant_alt, sayi),
      bant_ust: bosOlabilir(esik.bant_ust, sayi),
      bant_esikleri_gecici: mantik(esik.bant_esikleri_gecici),
    },
    aralik_duzeyi: bosOlabilir(k.aralik_duzeyi, sayi),
    model: {
      surum: metin(model.surum),
      olasilik_surum: bosOlabilir(model.olasilik_surum, metin),
      kod_surumu: metin(model.kod_surumu),
      egitim_bitis_tarihi: metin(model.egitim_bitis_tarihi),
      karne: bosOlabilir(model.karne, (x) =>
        dizi(x).map((s) => {
          const ks = nesne(s);
          return {
            ufuk_dk: sayi(ks.ufuk_dk),
            mae_arac: sayi(ks.mae_arac),
            beceri: sayi(ks.beceri),
            brier: bosOlabilir(ks.brier, sayi),
          };
        }),
      ),
      bant_kalibrasyonu: bosOlabilir(model.bant_kalibrasyonu, kalibrasyonOku),
    },
    veri_sagligi: bosOlabilir(k.veri_sagligi, (x) => {
      const v = nesne(x);
      return {
        tarih: metin(v.tarih),
        tur: sayi(v.tur),
        tamlik: sayi(v.tamlik),
        canli_otopark: sayi(v.canli_otopark),
      };
    }),
    kapsam_sayilari: {
      model: sayi(kapsam.model),
      basit: sayi(kapsam.basit),
      veri_yok: sayi(kapsam.veri_yok),
      gosterme: sayi(kapsam.gosterme),
      toplam: sayi(kapsam.toplam),
    },
    otoparklar,
  };
}

/**
 * Tahmin dosyasını hoşgörüyle okur: bilinmeyen alanları yok sayar, tanınmayan bant kodunu taşıyan
 * otoparkı "veri yok" gibi gösterir. Ana sürümü desteklenmeyen dosyada `uyumsuz` döner.
 */
export function tahminDosyasiOku(ham: unknown): OkumaSonucu {
  try {
    const kok = nesne(ham);
    const surum = metin(kok.sema_surumu);
    const ana = anaSurum(surum);
    if (ana === null) return { tur: 'bozuk' };
    if (ana !== DESTEKLENEN_ANA_SURUM) return { tur: 'uyumsuz', surum };
    return { tur: 'tamam', dosya: dosyaOku(kok, surum) };
  } catch (hata) {
    if (hata instanceof BozukAlan || hata instanceof BilinmeyenBant) return { tur: 'bozuk' };
    throw hata;
  }
}
