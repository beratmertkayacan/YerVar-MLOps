import AxeBuilder from '@axe-core/playwright';
import { listeGelsin } from './ornekVeri';
import { expect, test } from './temel';

const ROTALAR = [
  { adres: './#/', baslik: 'İstanbul otoparkları' },
  { adres: './#/liste', baslik: 'Liste' },
  { adres: './#/otopark/1034', baslik: 'Mecidiyeköy Katlı Otoparkı' },
  { adres: './#/hakkinda', baslik: 'Nasıl çalışır?' },
  { adres: './#/yok', baslik: 'Sayfa bulunamadı' },
];
const GENISLIKLER = [
  { width: 390, height: 844 },
  { width: 1280, height: 800 },
];

for (const boyut of GENISLIKLER) {
  for (const { adres, baslik } of ROTALAR) {
    test(`axe ihlali yok: ${adres} · ${boyut.width}`, async ({ page }) => {
      await page.setViewportSize(boyut);
      await page.goto(adres);
      await expect(page.getByRole('heading', { level: 1, name: baslik })).toBeAttached();
      await page.waitForLoadState('networkidle');
      const sonuc = await new AxeBuilder({ page }).analyze();
      expect(sonuc.violations).toEqual([]);
    });
  }
}

for (const adres of ['./#/', './#/liste', './#/otopark/1034']) {
  test(`dokunma alanları en az 48 × 48 px: ${adres}`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(adres);
    await page.waitForLoadState('networkidle');
    // Harita işaretleri ve harita atıf düğmesi klavye ve ekran okuyucu yolunda değil; asıl yol liste.
    const kucukler = await page.evaluate(() =>
      [...document.querySelectorAll('a, button, summary, .secici-secenek, .varis-secenek')]
        .filter((el) => !el.closest('.maplibregl-map'))
        .map((el) => ({
          ad: el.textContent?.trim() || el.className,
          kutu: el.getBoundingClientRect(),
        }))
        .filter(({ kutu }) => kutu.width > 0 && kutu.height > 0)
        .filter(({ kutu }) => kutu.width < 48 || kutu.height < 48)
        .map(({ ad, kutu }) => `${ad}: ${Math.round(kutu.width)}×${Math.round(kutu.height)}`),
    );
    expect(kucukler).toEqual([]);
  });
}

test('ilk Tab "İçeriğe geç" düğmesini görünür kılar', async ({ page }) => {
  await page.goto('./#/');
  await page.keyboard.press('Tab');
  const dugme = page.getByRole('button', { name: 'İçeriğe geç' });
  await expect(dugme).toBeFocused();
  await expect(dugme).toBeInViewport();
});

for (const adres of ['./#/', './#/liste', './#/otopark/1034', './#/hakkinda']) {
  test(`klavyeyle odaklanan her öğede görünür odak halkası var: ${adres}`, async ({ page }) => {
    await page.goto(adres);
    await page.waitForLoadState('networkidle');
    const halkasizlar: string[] = [];
    for (let adim = 0; adim < 20; adim++) {
      await page.keyboard.press('Tab');
      const odak = await page.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) return null;
        const halkaSahibi = el.matches('input[type="radio"]')
          ? el.closest('label')
          : el.matches('.arama input')
            ? el.closest('.arama-kutu')
            : el;
        const stil = getComputedStyle(halkaSahibi ?? el);
        return {
          ad: el.textContent?.trim() || el.getAttribute('aria-label') || el.tagName,
          halka: stil.outlineStyle !== 'none' && Number.parseFloat(stil.outlineWidth) >= 2,
        };
      });
      if (odak && !odak.halka) halkasizlar.push(odak.ad);
    }
    expect(halkasizlar).toEqual([]);
  });
}

test('varış seçicisi oklarla gezilir', async ({ page }) => {
  await page.goto('./#/');
  await listeGelsin(page);
  await page.getByRole('radio', { name: /30 dk/ }).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('radio', { name: /1 sa/ })).toBeChecked();
});

test('ekran değişince odak ana içeriğe geçer', async ({ page }) => {
  await page.goto('./#/');
  await listeGelsin(page);
  await page.locator('main a.satir').first().click();
  await expect(page.locator('main')).toBeFocused();
});
