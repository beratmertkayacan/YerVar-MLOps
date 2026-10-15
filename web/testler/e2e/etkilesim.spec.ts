import { listeGelsin } from './ornekVeri';
import { expect, test } from './temel';

test('arama otopark ve semt adında Türkçe harfle arar, Enter durum sayfasını açar', async ({
  page,
}) => {
  await page.goto('./#/');
  await listeGelsin(page);
  const kutu = page.getByRole('combobox', { name: 'Otopark ya da semt ara' });
  await kutu.fill('KADIKÖY');
  await expect(page.getByRole('option')).toHaveCount(1);
  await expect(page.getByRole('option')).toContainText('Kadıköy Rıhtım Katlı Otoparkı');
  await kutu.press('ArrowDown');
  await kutu.press('Enter');
  await expect(
    page.getByRole('heading', { level: 1, name: 'Kadıköy Rıhtım Katlı Otoparkı' }),
  ).toBeVisible();
});

test('aramada sonuç yoksa bunu söyler', async ({ page }) => {
  await page.goto('./#/');
  await listeGelsin(page);
  await page.getByRole('combobox').fill('zzz');
  await expect(page.getByText('Bu aramaya uyan otopark yok.')).toBeVisible();
});

test('varış değişince bantlar o saate göre değişir; "Şimdi" son ölçümü gösterir', async ({
  page,
}) => {
  await page.goto('./#/liste');
  await listeGelsin(page);
  const mecidiyekoy = page.locator('a.satir', { hasText: 'Mecidiyeköy' });
  await expect(mecidiyekoy).toContainText('Belirsiz');
  await page.getByRole('radio', { name: /2 sa/ }).check({ force: true });
  await expect(mecidiyekoy).toContainText('Dolu olası');
  await page.getByRole('radio', { name: /Şimdi/ }).check({ force: true });
  await expect(mecidiyekoy).toContainText('Son ölçüm');
  await expect(mecidiyekoy).toContainText('41');
});

test('varış tercihi sayfa yenilense de hatırlanır', async ({ page }) => {
  await page.goto('./#/');
  await listeGelsin(page);
  await page.getByRole('radio', { name: /1 sa/ }).check({ force: true });
  await page.reload();
  await listeGelsin(page);
  await expect(page.getByRole('radio', { name: /1 sa/ })).toBeChecked();
});

test('konum yokken "Yakınımda" izin ister, konum gelince mesafeye göre sıralar', async ({
  page,
  context,
}) => {
  await page.goto('./#/');
  await listeGelsin(page);
  await page.getByRole('button', { name: 'Yakınımda' }).click();
  await expect(page.getByText('Yakındaki otoparkları görmek için konum izni ver')).toBeVisible();
  await context.grantPermissions(['geolocation']);
  await context.setGeolocation({ latitude: 41.0422, longitude: 29.0067 });
  await page.locator('main').getByRole('button', { name: 'Konumumu kullan' }).click();
  const ilk = page.locator('main a.satir').first();
  await expect(ilk).toContainText('Beşiktaş Barbaros');
  await expect(ilk).toContainText('kuş uçuşu');
});

test("konum izni daha önce verildiyse sormadan kullanılır ve URL'ye yazılmaz", async ({
  page,
  context,
}) => {
  await context.grantPermissions(['geolocation']);
  await context.setGeolocation({ latitude: 41.0422, longitude: 29.0067 });
  await page.goto('./#/liste');
  await listeGelsin(page);
  await expect(page.getByRole('radio', { name: 'Yakınlık' })).toBeEnabled();
  expect(page.url()).not.toContain('41.04');
});

test('telefonda menü açılır ve sayfaya götürür', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('./#/');
  await page.getByLabel('Menü').click();
  await page.locator('.menu').getByRole('link', { name: 'Nasıl çalışır?' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Nasıl çalışır?' })).toBeVisible();
  await expect(page.locator('.menu')).not.toHaveAttribute('open');
});
