import { mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { gzipSync } from 'node:zlib';

const DIST = 'dist';
const BUTCE_KB = { js: 60, css: 15 };

const kb = (bayt) => Math.round((bayt / 1024) * 10) / 10;
const gz = (yol) => gzipSync(readFileSync(yol), { level: 9 }).length;

const sayfa = readFileSync(join(DIST, 'index.html'), 'utf8');
const ilkYuk = [...sayfa.matchAll(/(?:src|href)="\.\/(assets\/[^"]+\.(js|css))"/g)].map(
  ([, yol, tur]) => ({
    yol,
    tur,
    ham: readFileSync(join(DIST, yol)).length,
    gz: gz(join(DIST, yol)),
  }),
);
const sonradan = readdirSync(join(DIST, 'assets'))
  .map((ad) => `assets/${ad}`)
  .filter((yol) => !ilkYuk.some((d) => d.yol === yol))
  .map((yol) => ({ yol, ham: readFileSync(join(DIST, yol)).length, gz: gz(join(DIST, yol)) }));
const veri = { yol: 'ornek/son.json', ham: readFileSync(join(DIST, 'ornek/son.json')).length };
veri.gz = gz(join(DIST, veri.yol));

const toplam = (tur) => ilkYuk.filter((d) => d.tur === tur).reduce((t, d) => t + d.gz, 0);
const sonuc = {
  dosyalar: ilkYuk,
  sonradan,
  veri,
  js: { gz: toplam('js'), butce: BUTCE_KB.js * 1024 },
  css: { gz: toplam('css'), butce: BUTCE_KB.css * 1024 },
};

const satirlar = [
  ...ilkYuk.map(
    (d) => `  ${d.yol.padEnd(34)} ${String(kb(d.ham)).padStart(7)} KB  gz ${kb(d.gz)} KB`,
  ),
  `  ${veri.yol.padEnd(34)} ${String(kb(veri.ham)).padStart(7)} KB  gz ${kb(veri.gz)} KB`,
  '',
  '  Sonradan yüklenen (harita):',
  ...sonradan.map(
    (d) => `  ${d.yol.padEnd(34)} ${String(kb(d.ham)).padStart(7)} KB  gz ${kb(d.gz)} KB`,
  ),
  '',
  `  İlk JS  gz ${kb(sonuc.js.gz)} KB / bütçe ${BUTCE_KB.js} KB`,
  `  İlk CSS gz ${kb(sonuc.css.gz)} KB / bütçe ${BUTCE_KB.css} KB`,
];
process.stdout.write(`Boyut raporu (ilk yük)\n${satirlar.join('\n')}\n`);

mkdirSync('.galeri', { recursive: true });
writeFileSync('.galeri/boyut.json', JSON.stringify(sonuc, null, 2));

const asanlar = ['js', 'css'].filter((tur) => sonuc[tur].gz > sonuc[tur].butce);
if (asanlar.length > 0) {
  process.stderr.write(`Bütçe aşıldı: ${asanlar.join(', ')}\n`);
  process.exit(1);
}
process.stdout.write('Bütçe: GEÇTİ\n');
