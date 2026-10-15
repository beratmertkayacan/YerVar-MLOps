import { test } from './temel';

// Lighthouse'un mobil "yavaş 4G" ön ayarı: 150 ms gidiş-dönüş, 1,6 Mbit/sn indirme, 750 kbit/sn yükleme,
// 4 kat işlemci yavaşlatma. Tarayıcı ağ emülasyonu istek düzeyinde çalıştığı için Lighthouse aynı
// düzeltme çarpanlarını uygular: gecikme × 3,75, bant genişliği × 0,9.
// Kaynak: https://github.com/GoogleChrome/lighthouse/blob/main/docs/throttling.md
const GECIKME_MS = 150 * 3.75;
const INDIRME_BAYT_SN = (1.6 * 1024 * 0.9 * 1024) / 8;
const YUKLEME_BAYT_SN = (750 * 0.9 * 1024) / 8;
const ISLEMCI_YAVASLATMA = 4;
const OLCUM_SAYISI = 5;
const BUTCE_MS = 2_500;

test('ilk anlamlı içerik (LCP) ölçümü, yavaş 4G', async ({ browser }, bilgi) => {
  test.setTimeout(120_000);
  const sureler: number[] = [];
  const ogeler: string[] = [];
  for (let sira = 0; sira < OLCUM_SAYISI; sira++) {
    const baglam = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await baglam.newPage();
    const cdp = await baglam.newCDPSession(page);
    await cdp.send('Network.enable');
    await cdp.send('Network.emulateNetworkConditions', {
      offline: false,
      latency: GECIKME_MS,
      downloadThroughput: INDIRME_BAYT_SN,
      uploadThroughput: YUKLEME_BAYT_SN,
    });
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: ISLEMCI_YAVASLATMA });
    await page.goto('./#/');
    await page.locator('main a.satir').first().waitFor({ timeout: 30_000 });
    await page.waitForTimeout(1_000);
    const lcp = await page.evaluate(
      () =>
        new Promise<{ sure: number; oge: string }>((bitti) => {
          new PerformanceObserver((liste) => {
            const son = liste.getEntries().at(-1) as PerformanceEntry & { element?: Element };
            const oge = son?.element;
            bitti({
              sure: son?.startTime ?? -1,
              oge: oge ? `${oge.tagName.toLowerCase()}.${oge.className}` : '?',
            });
          }).observe({ type: 'largest-contentful-paint', buffered: true });
        }),
    );
    sureler.push(lcp.sure);
    ogeler.push(lcp.oge);
    await baglam.close();
  }
  const sirali = [...sureler].sort((a, b) => a - b);
  const ortanca = sirali[Math.floor(sirali.length / 2)] ?? -1;
  const ozet = `LCP ortanca ${Math.round(ortanca)} ms (bütçe ${BUTCE_MS} ms) · ölçümler ${sureler
    .map(Math.round)
    .join(', ')} · öğe ${[...new Set(ogeler)].join(', ')}`;
  bilgi.annotations.push({ type: 'olcum', description: ozet });
});
