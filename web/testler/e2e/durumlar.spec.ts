import { listeGelsin, ornegiDegistir, VERI_ADRESI } from './ornekVeri';
import { expect, test } from './temel';

test('yüklenirken iskelet ve ileti görünür, 3 saniye sonra ileti değişir', async ({ page }) => {
  await page.clock.install();
  await page.route(VERI_ADRESI, () => {});
  await page.goto('./#/');
  await expect(page.locator('.satir-iskelet')).toHaveCount(8);
  await expect(page.getByText('Tahminler yükleniyor…')).toBeVisible();
  await page.clock.runFor(3_100);
  await expect(page.getByText('Sunucu uyanıyor, birkaç saniye sürebilir.')).toBeVisible();
});

test('sunucu hata verirse ileti ve "Tekrar dene" çıkar; tekrar deneyince veri gelir', async ({
  page,
}) => {
  await page.route(VERI_ADRESI, (route) => route.fulfill({ status: 500 }));
  await page.goto('./#/');
  await expect(page.getByText('Tahminlere şu an ulaşılamıyor.')).toBeVisible();
  await page.unroute(VERI_ADRESI);
  await page.getByRole('button', { name: 'Tekrar dene' }).click();
  await listeGelsin(page);
});

test('çözülemeyen dosyada hata iletisi çıkar', async ({ page }) => {
  await page.route(VERI_ADRESI, (route) =>
    route.fulfill({ body: '{"bozuk', contentType: 'application/json' }),
  );
  await page.goto('./#/');
  await expect(page.getByText('Tahminlere şu an ulaşılamıyor.')).toBeVisible();
});

test('tanınmayan ana şema sürümünde "Yenile" ister', async ({ page }) => {
  await ornegiDegistir(page, (veri) => {
    veri.sema_surumu = '1.0.0';
  });
  await page.goto('./#/');
  await expect(page.getByText('Uygulamanın yeni sürümü var.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Yenile' })).toBeVisible();
});

test('otopark listesi boşsa bunu söyler, boş liste göstermez', async ({ page }) => {
  await ornegiDegistir(page, (veri) => {
    veri.otoparklar = [];
  });
  await page.goto('./#/liste');
  await expect(page.getByText('Şu an gösterilecek otopark yok.')).toBeVisible();
  await expect(page.locator('a.satir')).toHaveCount(0);
});

test('veri çipi güncel veride yaşı yazar', async ({ page }) => {
  await page.goto('./#/');
  await expect(page.locator('.veri-cipi')).toHaveText('Veri 08:05 · 1 dk önce');
  await expect(page.locator('.veri-cipi')).toHaveClass(/veri-cipi-guncel/);
  await expect(page.locator('.serit')).toHaveCount(0);
});

test('eşik aşılınca çip gecikmiş görünür ve şerit çıkar', async ({ page }) => {
  await page.clock.install();
  await page.goto('./#/');
  await listeGelsin(page);
  await page.clock.fastForward('20:00');
  await expect(page.locator('.veri-cipi')).toHaveClass(/veri-cipi-gecikmis/);
  await expect(page.getByText(/Veriler 2\d dk önce güncellendi/)).toBeVisible();
});

test('bütün ufuklar geçince tahmin yerine son ölçüm gösterilir ve yalnız "Şimdi" seçilebilir', async ({
  page,
}) => {
  await page.clock.install();
  await page.goto('./#/');
  await listeGelsin(page);
  await page.clock.fastForward('03:00:00');
  await expect(page.locator('.veri-cipi')).toHaveClass(/veri-cipi-cok_eski/);
  await expect(page.getByText('Tahminlerin süresi doldu. Son ölçüm saat 08:05.')).toBeVisible();
  await expect(page.getByRole('radio', { name: /30 dk/ })).toBeDisabled();
  await expect(page.getByRole('radio', { name: /Şimdi/ })).toBeChecked();
  await expect(page.locator('main a.satir').first()).toContainText('Son ölçüm');
});

test('bağlantı kopunca çevrimdışı şeridi çıkar', async ({ page, context }) => {
  await page.goto('./#/');
  await listeGelsin(page);
  await context.setOffline(true);
  await expect(
    page.getByText('Çevrimdışısın; son kaydedilen tahminler gösteriliyor.'),
  ).toBeVisible();
  await context.setOffline(false);
  await expect(page.locator('.serit')).toHaveCount(0);
});

test('satırda bant metni, simgesi ve aralığı birlikte durur', async ({ page }) => {
  await page.goto('./#/liste');
  await listeGelsin(page);
  const belirsiz = page.locator('a.satir', { hasText: 'Mecidiyeköy' });
  await expect(belirsiz).toContainText('Belirsiz');
  await expect(belirsiz.locator('svg.simge-belirsiz')).toHaveCount(1);
  await expect(belirsiz).toContainText('7–30');
  await expect(belirsiz).toContainText('Şişli');
  const basit = page.locator('a.satir', { hasText: 'Sarıyer' });
  await expect(basit).toContainText('Basit tahmin');
  await expect(basit).toContainText('≈47');
  const eski = page.locator('a.satir', { hasText: 'Eminönü' });
  await expect(eski).toContainText('Son ölçüm 07:20');
});

test('harita yüklenemezse bunu söyler, liste çalışmaya devam eder', async ({ page }) => {
  await page.unroute('https://tiles.openfreemap.org/**');
  await page.route('https://tiles.openfreemap.org/**', (istek) => istek.abort());
  await page.goto('./#/');
  await expect(page.getByText('Harita yüklenemedi. Listeden devam edebilirsin.')).toBeVisible();
  await listeGelsin(page);
});
