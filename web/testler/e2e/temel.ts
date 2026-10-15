import { test as temel } from '@playwright/test';

export { expect } from '@playwright/test';

// Testler dış harita sunucusuna gitmez: stil yerine yalnızca zemin rengi olan yerel bir stil verilir.
const YEREL_STIL = {
  version: 8,
  sources: {},
  layers: [{ id: 'zemin', type: 'background', paint: { 'background-color': '#ebece6' } }],
};

export const test = temel.extend<{ yerelHarita: undefined }>({
  yerelHarita: [
    async ({ page }, kullan) => {
      await page.route('https://tiles.openfreemap.org/**', (istek) =>
        istek.request().url().includes('/styles/')
          ? istek.fulfill({ json: YEREL_STIL })
          : istek.abort(),
      );
      await kullan(undefined);
    },
    { auto: true },
  ],
});
