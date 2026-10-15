import type { Page } from '@playwright/test';

export const VERI_ADRESI = '**/ornek/son.json';

type Veri = Record<string, unknown>;

/** Örnek dosyayı tarayıcıya giderken değiştirir; diskteki dosyaya dokunmaz. */
export async function ornegiDegistir(page: Page, degistir: (veri: Veri) => void): Promise<void> {
  await page.route(VERI_ADRESI, async (route) => {
    const yanit = await route.fetch();
    const veri = (await yanit.json()) as Veri;
    degistir(veri);
    await route.fulfill({ response: yanit, json: veri });
  });
}

export async function listeGelsin(page: Page): Promise<void> {
  await page.locator('a.satir').first().waitFor();
}
