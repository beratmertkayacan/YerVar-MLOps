import { defineConfig, devices } from '@playwright/test';

const ADRES = 'http://localhost:4173/';

// Uçtan uca testler üretim derlemesi üzerinde koşar: kullanıcının alacağı paket sınanır.
export default defineConfig({
  testDir: 'testler/e2e',
  fullyParallel: true,
  reporter: [['list'], ['json', { outputFile: '.galeri/e2e.json' }]],
  use: {
    baseURL: ADRES,
    locale: 'tr-TR',
    timezoneId: 'Europe/Istanbul',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run derle && npx vite preview --port 4173 --strictPort',
    url: ADRES,
  },
});
