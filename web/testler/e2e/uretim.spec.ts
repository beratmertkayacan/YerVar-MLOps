import { expect, test } from './temel';

test('üretim paketinde geliştirme parametreleri yok', async ({ request }) => {
  const sayfa = await (await request.get('./')).text();
  const betikler = [...sayfa.matchAll(/src="\.?\/?(assets\/[^"]+\.js)"/g)].map((e) => e[1]);
  expect(betikler.length).toBeGreaterThan(0);
  for (const betik of betikler) {
    const kod = await (await request.get(`./${betik}`)).text();
    expect(kod).not.toContain('URLSearchParams');
    expect(kod).not.toContain('cerceve');
  }
});

test('üretimde ?saat yok sayılır', async ({ page }) => {
  await page.goto('./?saat=2026-10-16T09:00:00Z#/');
  await expect(page.locator('.veri-cipi')).toHaveText('Veri 08:05 · 1 dk önce');
});

test('üretimde vitrin açılmaz', async ({ page }) => {
  await page.goto('./#/vitrin');
  await expect(page.getByRole('heading', { level: 1, name: 'Sayfa bulunamadı' })).toBeVisible();
});
