import { render } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import { cevapBul } from '../alan/cevap';
import type { Harita as HaritaMotoru } from '../harita/maplibre';
import { metin } from '../metin/metinler';
import { etkinVaris, konum, seciliOtopark } from '../uygulama/durum';
import { otoparkAdresi, rota } from '../uygulama/rota';
import { yukleme } from '../veri/yukle';
import { simdi } from '../zaman/saat';
import { cevapGorunumu } from './cevapGorunumu';
import { OnIzleme } from './OnIzleme';
import { Simge } from './Simge';

type HaritaModulu = typeof import('../harita/maplibre');
type Isaret = ReturnType<HaritaModulu['isaretEkle']>;

/**
 * Harita sonradan yüklenen ayrı bir parçadır; o gelene kadar yer tutucu çizim görünür.
 * İşaretler süs değil, kısayoldur: ekran okuyucu ve klavye için asıl yol listedir.
 */
export function Harita() {
  const kap = useRef<HTMLDivElement>(null);
  const motor = useRef<{ harita: HaritaMotoru; modul: HaritaModulu } | null>(null);
  const isaretler = useRef(new Map<number, { isaret: Isaret; eleman: HTMLElement }>());
  const konumIsareti = useRef<Isaret | null>(null);
  const [durum, setDurum] = useState<'yukleniyor' | 'hazir' | 'hata'>('yukleniyor');

  useEffect(() => {
    let iptal = false;
    import('../harita/maplibre')
      .then((modul) => {
        if (iptal || !kap.current) return;
        const harita = modul.haritaOlustur(
          kap.current,
          () => setDurum('hazir'),
          () => setDurum('hata'),
        );
        harita.on('click', () => {
          seciliOtopark.value = null;
        });
        motor.current = { harita, modul };
      })
      .catch(() => setDurum('hata'));
    return () => {
      iptal = true;
      motor.current?.harita.remove();
      motor.current = null;
      isaretler.current.clear();
    };
  }, []);

  const veri = yukleme.value;
  const simdiMs = simdi.value;
  const secili = seciliOtopark.value;
  const gecerliRota = rota.value;

  useEffect(() => {
    const m = motor.current;
    if (!m || durum !== 'hazir' || veri.tur !== 'hazir') return;
    const { ufuk } = etkinVaris(veri.dosya.ufuklar, simdiMs);
    const gorulen = new Set<number>();
    for (const otopark of veri.dosya.otoparklar) {
      if (otopark.kapsam === 'gosterme') continue;
      gorulen.add(otopark.park_id);
      let kayit = isaretler.current.get(otopark.park_id);
      if (!kayit) {
        const eleman = document.createElement('button');
        eleman.type = 'button';
        eleman.tabIndex = -1;
        eleman.setAttribute('aria-hidden', 'true');
        eleman.addEventListener('click', (olay) => {
          olay.stopPropagation();
          seciliOtopark.value = otopark.park_id;
        });
        kayit = { eleman, isaret: m.modul.isaretEkle(m.harita, otopark.lng, otopark.lat, eleman) };
        isaretler.current.set(otopark.park_id, kayit);
      }
      const gorunum = cevapGorunumu(cevapBul(otopark, ufuk), simdiMs);
      kayit.eleman.className = `isaret ton-${gorunum.ton}${
        otopark.park_id === secili ? ' secili' : ''
      }${otopark.tazelik === 'eski' ? ' soluk' : ''}`;
      render(<Simge ad={gorunum.simge} />, kayit.eleman);
    }
    for (const [id, kayit] of isaretler.current) {
      if (!gorulen.has(id)) {
        kayit.isaret.remove();
        isaretler.current.delete(id);
      }
    }
  }, [durum, veri, simdiMs, secili]);

  useEffect(() => {
    const m = motor.current;
    if (!m || durum !== 'hazir' || veri.tur !== 'hazir') return;
    if (gecerliRota.ekran === 'otopark') {
      const otopark = veri.dosya.otoparklar.find((o) => o.park_id === gecerliRota.id);
      if (otopark) {
        seciliOtopark.value = otopark.park_id;
        m.harita.easeTo({ center: [otopark.lng, otopark.lat], zoom: 14 });
      }
    } else if (konum.value) {
      m.harita.easeTo({ center: [konum.value.lng, konum.value.lat], zoom: 13 });
    }
    if (konum.value) {
      konumIsareti.current?.remove();
      const nokta = document.createElement('div');
      nokta.className = 'konum-noktasi';
      konumIsareti.current = m.modul.isaretEkle(m.harita, konum.value.lng, konum.value.lat, nokta);
    }
  }, [durum, veri, gecerliRota, konum.value]);

  const seciliOtoparkVerisi =
    veri.tur === 'hazir' && secili !== null && gecerliRota.ekran === 'ana'
      ? veri.dosya.otoparklar.find((o) => o.park_id === secili)
      : undefined;

  return (
    <section class="harita" aria-label={metin.harita.etiket} data-durum={durum}>
      <div class="harita-kap" ref={kap} />
      {durum !== 'hazir' && (
        <div class="harita-yer-tutucu" aria-hidden={durum === 'yukleniyor'}>
          <svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
            <path d="M0 170C60 150 110 190 170 175S280 120 410 140" />
            <path d="M120 0C140 60 120 120 150 170S170 260 160 310" />
            <path d="M0 70C80 90 160 60 240 80S340 40 410 60" />
            <path d="M250 0C240 70 280 140 270 200S300 280 290 310" />
          </svg>
          <p>{durum === 'hata' ? metin.harita.yuklenemedi : metin.harita.yukleniyor}</p>
        </div>
      )}
      {seciliOtoparkVerisi && veri.tur === 'hazir' && (
        <OnIzleme
          otopark={seciliOtoparkVerisi}
          dosya={veri.dosya}
          simdiMs={simdiMs}
          adres={otoparkAdresi(seciliOtoparkVerisi.park_id)}
          kapat={() => {
            seciliOtopark.value = null;
          }}
        />
      )}
    </section>
  );
}
