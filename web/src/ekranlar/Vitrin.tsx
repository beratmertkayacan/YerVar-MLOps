import type { ComponentChildren } from 'preact';
import { useEffect } from 'preact/hooks';
import { listeOlustur } from '../alan/liste';
import { ufukSec } from '../alan/ufuk';
import { cevapGorunumu } from '../bilesenler/cevapGorunumu';
import { DurumKarti } from '../bilesenler/DurumKarti';
import { IskeletListesi, OtoparkListesi } from '../bilesenler/OtoparkListesi';
import { Serit } from '../bilesenler/Serit';
import { Simge } from '../bilesenler/Simge';
import { VeriBekleyen } from '../bilesenler/VeriBekleyen';
import { VeriCipi } from '../bilesenler/VeriCipi';
import { saatYaz } from '../metin/bicim';
import { metin } from '../metin/metinler';
import { vitrinMetni } from '../metin/vitrinMetni';
import type { TahminDosyasi } from '../veri/sozlesme';
import { simdi } from '../zaman/saat';

const RENKLER = [
  'zemin',
  'yuzey',
  'yuzey-alt',
  'metin',
  'metin-ikincil',
  'kenar',
  'kenar-guclu',
  'marka',
  'marka-acik',
  'bant-yer',
  'bant-yer-metin',
  'bant-belirsiz',
  'bant-dolu',
  'bant-dolu-metin',
  'notr',
  'veri-yok',
  'uyari',
  'uyari-zemin',
  'hata',
  'hata-zemin',
];
const YAZI_OLCEGI = [12, 14, 16, 20, 24, 32];
const DAKIKA_MS = 60_000;
const hicbirSeyYapma = () => undefined;

function Bolum({ baslik, children }: { baslik: string; children: ComponentChildren }) {
  return (
    <section class="vitrin-bolum">
      <h2>{baslik}</h2>
      {children}
    </section>
  );
}

function Icerik({ dosya }: { dosya: TahminDosyasi }) {
  const simdiMs = simdi.value;
  const otuz = ufukSec(dosya.ufuklar, simdiMs, 30);
  const ikiSaat = ufukSec(dosya.ufuklar, simdiMs, 120);
  const otuzListe = listeOlustur(dosya.otoparklar, otuz, 'olasilik', null);
  const ikiSaatListe = listeOlustur(dosya.otoparklar, ikiSaat, 'olasilik', null);
  const simdiListe = listeOlustur(dosya.otoparklar, null, 'olasilik', null);
  const dakikaOnce = (dk: number) => new Date(simdiMs - dk * DAKIKA_MS).toISOString();
  return (
    <>
      <Bolum baslik={vitrinMetni.renkler}>
        <ul class="renk-listesi">
          {RENKLER.map((ad) => (
            <li key={ad}>
              <span class="renk-ornegi" style={{ background: `var(--renk-${ad})` }} />
              <code>--renk-{ad}</code>
            </li>
          ))}
        </ul>
      </Bolum>
      <Bolum baslik={vitrinMetni.yazi}>
        {YAZI_OLCEGI.map((boy) => (
          <p key={boy} style={{ fontSize: `var(--yazi-${boy})`, lineHeight: 1.2 }}>
            {boy} · {vitrinMetni.yaziOrnegi}
          </p>
        ))}
      </Bolum>
      <Bolum baslik={vitrinMetni.satirlar}>
        <div class="vitrin-izgara">
          <OtoparkListesi satirlar={otuzListe.siradakiler} simdiMs={simdiMs} />
          <div class="otopark-listesi">
            <OtoparkListesi satirlar={ikiSaatListe.siradakiler.slice(0, 4)} simdiMs={simdiMs} />
            <OtoparkListesi satirlar={simdiListe.siradakiler.slice(0, 2)} simdiMs={simdiMs} />
            <OtoparkListesi satirlar={otuzListe.veriYok.slice(0, 1)} simdiMs={simdiMs} />
            <IskeletListesi adet={1} />
          </div>
        </div>
      </Bolum>
      <Bolum baslik={vitrinMetni.isaretler}>
        <div class="isaret-ornekleri">
          {[...otuzListe.siradakiler, ...otuzListe.veriYok].map((s) => {
            const g = cevapGorunumu(s.cevap, simdiMs);
            return (
              <span key={s.otopark.park_id} class={`isaret ton-${g.ton}`}>
                <Simge ad={g.simge} />
              </span>
            );
          })}
          <span class="isaret secili">
            <Simge ad="belirsiz" />
          </span>
          <span class="konum-noktasi" />
        </div>
      </Bolum>
      <Bolum baslik={vitrinMetni.durumlar}>
        <VeriCipi veriUtc={dakikaOnce(3)} durum="guncel" simdiMs={simdiMs} />
        <VeriCipi veriUtc={dakikaOnce(25)} durum="gecikmis" simdiMs={simdiMs} />
        <VeriCipi veriUtc={dakikaOnce(185)} durum="cok_eski" simdiMs={simdiMs} />
        <Serit tur="uyari">{metin.serit.gecikmis(25)}</Serit>
        <Serit tur="uyari">{metin.serit.suresiDoldu(saatYaz(dosya.veri_utc))}</Serit>
        <Serit tur="uyari">{metin.serit.cevrimdisi}</Serit>
        <DurumKarti
          ileti={metin.hata.ulasilamiyor}
          eylem={{ etiket: metin.hata.tekrarDene, yap: hicbirSeyYapma }}
        />
        <DurumKarti
          ileti={metin.hata.yeniSurum}
          eylem={{ etiket: metin.hata.yenile, yap: hicbirSeyYapma }}
        />
        <DurumKarti tur="bilgi" ileti={metin.hata.bosVeri} />
      </Bolum>
    </>
  );
}

/** Yalnızca geliştirmede açılan bileşen ve jeton sayfası. */
export function Vitrin() {
  useEffect(() => {
    document.title = metin.sayfaBasligi(vitrinMetni.baslik);
  }, []);
  return (
    <div class="vitrin">
      <h1>{vitrinMetni.baslik}</h1>
      <VeriBekleyen iskelet={<IskeletListesi adet={3} />}>
        {(dosya) => <Icerik dosya={dosya} />}
      </VeriBekleyen>
    </div>
  );
}
