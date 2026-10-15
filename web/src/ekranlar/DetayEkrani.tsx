import { type Cevap, cevapBul } from '../alan/cevap';
import { egilimBul } from '../alan/egilim';
import { kusUcusuMetre, yurumeDakika } from '../alan/mesafe';
import { siklikCumlesi } from '../alan/siklik';
import { veriDurumu } from '../alan/tazelik';
import { AltBilgi } from '../bilesenler/AltBilgi';
import { cevapGorunumu } from '../bilesenler/cevapGorunumu';
import { Simge } from '../bilesenler/Simge';
import { VarisSecici } from '../bilesenler/VarisSecici';
import { VeriBekleyen } from '../bilesenler/VeriBekleyen';
import { VeriCipi } from '../bilesenler/VeriCipi';
import { ilceYaz, mesafeYaz, saatYaz, sayiYaz, yasYaz } from '../metin/bicim';
import { metin } from '../metin/metinler';
import { sebepMetni } from '../metin/sebep';
import { etkinVaris, konum } from '../uygulama/durum';
import type { Otopark, TahminDosyasi } from '../veri/sozlesme';
import { simdi } from '../zaman/saat';

const kucukHarfli = (s: string) => {
  const kucuk = s.toLocaleLowerCase('tr-TR');
  return kucuk.charAt(0).toLocaleUpperCase('tr-TR') + kucuk.slice(1);
};

function haritalarAdresi(otopark: Otopark): string {
  // Dış haritaya yalnızca otoparkın koordinatı gider; kullanıcının konumu eklenmez.
  return `https://www.google.com/maps/search/?api=1&query=${otopark.lat},${otopark.lng}`;
}

function AnaCevap({
  cevap,
  otopark,
  dosya,
}: {
  cevap: Cevap;
  otopark: Otopark;
  dosya: TahminDosyasi;
}) {
  const simdiMs = simdi.value;
  switch (cevap.tur) {
    case 'tahmin': {
      const siklik = cevap.bant
        ? siklikCumlesi(cevap.bant, dosya.esikler, dosya.model.bant_kalibrasyonu)
        : null;
      return (
        <>
          {cevap.bant && (
            <p class={`cevap-bant ton-${cevap.bant}`}>
              <Simge ad={cevap.bant} />
              {metin.bant[cevap.bant].kisa}
            </p>
          )}
          {cevap.bant && <p class="cevap-cumle">{metin.bant[cevap.bant].cumle}</p>}
          <p class="cevap-sayi">
            {cevap.alt !== null && cevap.ust !== null ? (
              <b>{metin.aralikKisa(sayiYaz(cevap.alt), sayiYaz(cevap.ust))}</b>
            ) : (
              <b>~{sayiYaz(cevap.bos)}</b>
            )}{' '}
            <span>
              {metin.bosYer} · {metin.saatIcin(saatYaz(cevap.hedefUtc))}
            </span>
          </p>
          {siklik && <p class="cevap-cumle">{siklik}</p>}
          <details class="aciklama">
            <summary>{metin.doluNe.soru}</summary>
            <p>{metin.doluNe.cevap}</p>
          </details>
        </>
      );
    }
    case 'basit':
      return (
        <>
          <p class="cevap-bant ton-basit">
            <Simge ad="basit" />
            {metin.basit.kisa}
          </p>
          <p class="cevap-sayi">
            <b>≈{sayiYaz(cevap.bos)}</b>{' '}
            <span>
              {metin.bosYer} · {metin.saatIcin(saatYaz(cevap.hedefUtc))}
            </span>
          </p>
          <p class="cevap-cumle">{metin.basit.aciklama}</p>
          <p class="cevap-cumle">{sebepMetni(otopark.kapsam_sebebi)}</p>
        </>
      );
    case 'olcum':
      return (
        <>
          <p class="cevap-bant ton-olcum">
            <Simge ad="olcum" />
            {metin.varis.simdiAciklama}
          </p>
          <p class="cevap-sayi">
            <b>{sayiYaz(cevap.bos)}</b>{' '}
            <span>
              {metin.bosYer} · {metin.olcum.saatinde(saatYaz(cevap.zamanUtc))}
            </span>
          </p>
        </>
      );
    case 'eski':
      return (
        <p class="cevap-bant ton-olcum">
          <Simge ad="saat" />
          {metin.olcum.eski(
            saatYaz(cevap.zamanUtc),
            yasYaz(cevap.zamanUtc, simdiMs),
            sayiYaz(cevap.bos),
          )}
        </p>
      );
    case 'veri_yok':
      return (
        <>
          <p class="cevap-bant ton-veri_yok">
            <Simge ad="veri_yok" />
            {metin.kapsam.veriYok}
          </p>
          <p class="cevap-cumle">{metin.kapsam.veriYokAciklama}</p>
          <p class="cevap-cumle">{sebepMetni(otopark.kapsam_sebebi)}</p>
        </>
      );
    case 'gosterme':
      return <p class="cevap-cumle">{sebepMetni(otopark.kapsam_sebebi)}</p>;
  }
}

function ZamanSeridi({
  otopark,
  dosya,
  seciliDk,
}: {
  otopark: Otopark;
  dosya: TahminDosyasi;
  seciliDk: number;
}) {
  const simdiMs = simdi.value;
  const gelecek = dosya.ufuklar.filter((u) => Date.parse(u.hedef_utc) >= simdiMs);
  if (otopark.tazelik !== 'taze' || !otopark.tahminler || gelecek.length === 0) return null;
  return (
    <section aria-labelledby="zaman-seridi">
      <h2 id="zaman-seridi" class="ara-baslik">
        {metin.detay.zamanSeridi}
      </h2>
      <ol class="zaman-seridi">
        {gelecek.map((ufuk) => {
          const gorunum = cevapGorunumu(cevapBul(otopark, ufuk), simdiMs);
          return (
            <li key={ufuk.ufuk_dk} aria-current={ufuk.ufuk_dk === seciliDk ? 'true' : undefined}>
              <Simge ad={gorunum.simge} />
              <b>{gorunum.sayi}</b>
              <small>{saatYaz(ufuk.hedef_utc)}</small>
              <span class="gorsel-gizli">{gorunum.etiket}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function Detay({ dosya, id }: { dosya: TahminDosyasi; id: number }) {
  const simdiMs = simdi.value;
  const otopark = dosya.otoparklar.find((o) => o.park_id === id);
  if (!otopark) return <h1 class="detay-baslik">{metin.detay.bulunamadi}</h1>;
  const varis = etkinVaris(dosya.ufuklar, simdiMs);
  const cevap = cevapBul(otopark, varis.ufuk);
  const egilim = otopark.tazelik === 'taze' ? egilimBul(otopark.tahminler) : null;
  const mesafe = konum.value ? kusUcusuMetre(konum.value, otopark) : null;
  const yedekOne =
    cevap.tur === 'tahmin' &&
    cevap.doluOlasiligi !== null &&
    cevap.doluOlasiligi >= dosya.esikler.dolu_olasilik_esigi;
  const meta = [
    otopark.ilce ? ilceYaz(otopark.ilce) : null,
    otopark.tip ? kucukHarfli(otopark.tip) : null,
    otopark.kapasite ? metin.detay.kapasite(sayiYaz(otopark.kapasite)) : null,
    otopark.calisma_saatleri,
  ].filter((p) => p);
  return (
    <>
      <div>
        <h1 class="detay-baslik">{otopark.ad}</h1>
        <p class="detay-meta">{meta.join(' · ')}</p>
        {mesafe !== null && (
          <p class="detay-meta">{metin.konum.mesafe(mesafeYaz(mesafe), yurumeDakika(mesafe))}</p>
        )}
      </div>
      {otopark.kapsam !== 'gosterme' && otopark.kapsam !== 'veri_yok' && (
        <VarisSecici dosya={dosya} simdiMs={simdiMs} etkinDk={varis.dk} />
      )}
      <div class="cevap-kutusu">
        <AnaCevap cevap={cevap} otopark={otopark} dosya={dosya} />
      </div>
      <ZamanSeridi otopark={otopark} dosya={dosya} seciliDk={varis.dk} />
      {egilim && (
        <p class={`egilim egilim-${egilim}`}>
          {egilim === 'azaliyor' ? metin.egilim.azaliyor : metin.egilim.artiyor}
        </p>
      )}
      {otopark.son_olcum && otopark.kapasite !== null && (
        <p class="detay-olcum">
          {metin.olcum.satir(
            saatYaz(otopark.son_olcum.zaman_utc),
            sayiYaz(otopark.son_olcum.bos_yer),
            sayiYaz(otopark.kapasite),
          )}
        </p>
      )}
      <VeriCipi veriUtc={dosya.veri_utc} durum={veriDurumu(dosya, simdiMs)} simdiMs={simdiMs} />
      <div class="eylemler">
        <a class={yedekOne ? 'dugme' : 'dugme dugme-ikincil'} href="#/liste">
          {metin.detay.yedekler}
        </a>
        <a
          class="dugme dugme-ikincil"
          href={haritalarAdresi(otopark)}
          target="_blank"
          rel="noopener noreferrer"
        >
          {metin.detay.haritalardaAc}
          <Simge ad="disari" />
        </a>
      </div>
    </>
  );
}

export function DetayEkrani({ id }: { id: number }) {
  return (
    <div class="panel-icerik detay">
      <a class="geri" href="#/">
        <Simge ad="geri" />
        {metin.detay.geri}
      </a>
      <VeriBekleyen iskelet={null}>{(dosya) => <Detay dosya={dosya} id={id} />}</VeriBekleyen>
      <AltBilgi />
    </div>
  );
}
