import { VERI_ADRESI } from './ornekVeri';
import { expect, test } from './temel';

for (const boyut of [
  { width: 390, height: 844 },
  { width: 1280, height: 800 },
]) {
  test(`veri gelince düzen kaymaz: ${boyut.width}`, async ({ page }) => {
    await page.setViewportSize(boyut);
    await page.route(VERI_ADRESI, async (route) => {
      await new Promise((bitti) => setTimeout(bitti, 800));
      await route.continue();
    });
    await page.goto('./#/');
    await page.locator('main a.satir').first().waitFor();
    await page.waitForTimeout(500);
    const kayma = await page.evaluate(
      () =>
        new Promise<number>((bitti) => {
          new PerformanceObserver((liste) => {
            const toplam = liste
              .getEntries()
              .reduce((t, kayit) => t + (kayit as unknown as { value: number }).value, 0);
            bitti(toplam);
          }).observe({ type: 'layout-shift', buffered: true });
          setTimeout(() => bitti(0), 200);
        }),
    );
    expect(kayma).toBe(0);
  });
}
