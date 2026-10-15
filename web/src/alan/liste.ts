import type { Otopark, Ufuk } from '../veri/sozlesme';
import { type Cevap, cevapBul } from './cevap';
import { type Konum, kusUcusuMetre } from './mesafe';

export type Siralama = 'onerilen' | 'yakinlik' | 'olasilik';

export interface Satir {
  otopark: Otopark;
  cevap: Cevap;
  mesafeM: number | null;
}

export interface Liste {
  siradakiler: Satir[];
  veriYok: Satir[];
  gosterilmeyen: Otopark[];
  /** Önerilen sırası konuma göre süzüldüyse: 1 km'de 3'ten az otopark varsa 2 km'ye genişler. */
  yaricap: { metre: number; genisledi: boolean } | null;
}

const YARICAP_M = 1_000;
const GENIS_YARICAP_M = 2_000;
const EN_AZ_OTOPARK = 3;
const adSirasi = new Intl.Collator('tr-TR');

function grup(cevap: Cevap): number {
  if (cevap.tur === 'tahmin' && cevap.doluOlasiligi !== null) return 0;
  if (cevap.tur === 'basit') return 1;
  if (cevap.tur === 'olcum') return 0;
  return 2;
}

// "Şimdi" seçiliyken olasılık yok; son ölçümde boş yer oranı yüksek olan önce gelir.
function olasilikAnahtari(satir: Satir): number {
  const { cevap, otopark } = satir;
  if (cevap.tur === 'tahmin') return cevap.doluOlasiligi ?? 1;
  if (cevap.tur === 'olcum') return 1 - cevap.bos / Math.max(1, otopark.kapasite ?? 1);
  return 1;
}

function olasilikSirasi(a: Satir, b: Satir): number {
  return (
    grup(a.cevap) - grup(b.cevap) ||
    olasilikAnahtari(a) - olasilikAnahtari(b) ||
    (a.mesafeM ?? 0) - (b.mesafeM ?? 0) ||
    adSirasi.compare(a.otopark.ad, b.otopark.ad)
  );
}

const mesafeSirasi = (a: Satir, b: Satir) => (a.mesafeM ?? 0) - (b.mesafeM ?? 0);

/**
 * Otoparkları seçili varışa göre dizer. Gösterilmeyenler listeye girmez, "veri yok" olanlar ayrı döner.
 * Önerilen: konum varsa yarıçap içindekiler olasılık sırasıyla; konum yoksa bütün şehir olasılık sırasıyla.
 */
export function listeOlustur(
  otoparklar: Otopark[],
  ufuk: Ufuk | null,
  siralama: Siralama,
  konum: Konum | null,
): Liste {
  const satirlar = otoparklar
    .filter((o) => o.kapsam !== 'gosterme')
    .map((otopark) => ({
      otopark,
      cevap: cevapBul(otopark, ufuk),
      mesafeM: konum ? kusUcusuMetre(konum, otopark) : null,
    }));
  const verili = satirlar.filter((s) => s.cevap.tur !== 'veri_yok');
  const veriYok = satirlar.filter((s) => s.cevap.tur === 'veri_yok');
  const gosterilmeyen = otoparklar.filter((o) => o.kapsam === 'gosterme');
  if (konum) veriYok.sort(mesafeSirasi);

  if (siralama === 'yakinlik' && konum) {
    return { siradakiler: verili.sort(mesafeSirasi), veriYok, gosterilmeyen, yaricap: null };
  }
  if (siralama === 'onerilen' && konum) {
    const icinde = (metre: number) => verili.filter((s) => (s.mesafeM ?? 0) <= metre);
    const dar = icinde(YARICAP_M);
    const genisledi = dar.length < EN_AZ_OTOPARK;
    const secilen = genisledi ? icinde(GENIS_YARICAP_M) : dar;
    return {
      siradakiler: secilen.sort(olasilikSirasi),
      veriYok,
      gosterilmeyen,
      yaricap: { metre: genisledi ? GENIS_YARICAP_M : YARICAP_M, genisledi },
    };
  }
  return { siradakiler: verili.sort(olasilikSirasi), veriYok, gosterilmeyen, yaricap: null };
}
