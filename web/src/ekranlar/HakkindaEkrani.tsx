import { veriDurumu } from '../alan/tazelik';
import { AltBilgi } from '../bilesenler/AltBilgi';
import { VeriBekleyen } from '../bilesenler/VeriBekleyen';
import { VeriCipi } from '../bilesenler/VeriCipi';
import { metin } from '../metin/metinler';
import { sebepMetni } from '../metin/sebep';
import { simdi } from '../zaman/saat';

export function HakkindaEkrani() {
  const simdiMs = simdi.value;
  return (
    <div class="sayfa metin-sayfasi">
      <h1>{metin.hakkinda.baslik}</h1>
      <p>{metin.hakkinda.nasil}</p>
      <VeriBekleyen iskelet={null}>
        {(dosya) => {
          const gosterilmeyen = dosya.otoparklar.filter((o) => o.kapsam === 'gosterme');
          return (
            <>
              <section aria-labelledby="veri-yasi">
                <h2 id="veri-yasi">{metin.hakkinda.veriYasiBaslik}</h2>
                <VeriCipi
                  veriUtc={dosya.veri_utc}
                  durum={veriDurumu(dosya, simdiMs)}
                  simdiMs={simdiMs}
                />
                <p>{metin.hakkinda.veriYasi(dosya.tazelik_esigi_dk)}</p>
              </section>
              {gosterilmeyen.length > 0 && (
                <section aria-labelledby="gosterilmeyen">
                  <h2 id="gosterilmeyen">{metin.hakkinda.gosterilmeyenBaslik}</h2>
                  <p>{metin.kapsam.gosterilmeyenler(gosterilmeyen.length)}</p>
                  <ul class="duz-liste">
                    {gosterilmeyen.map((o) => (
                      <li key={o.park_id}>
                        <b>{o.ad}</b>: {sebepMetni(o.kapsam_sebebi)}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          );
        }}
      </VeriBekleyen>
      <section aria-labelledby="gizlilik">
        <h2 id="gizlilik">{metin.hakkinda.gizlilikBaslik}</h2>
        <p>{metin.hakkinda.gizlilik}</p>
        <p>{metin.hakkinda.harita}</p>
        <p>{metin.hakkinda.analitikYok}</p>
      </section>
      <AltBilgi />
    </div>
  );
}
