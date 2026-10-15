import { listeGelsin } from './ornekVeri';
import { expect, test } from './temel';

test('ana ekran haritayı ve önerilen otoparkları gösterir', async ({ page }) => {
  await page.goto('./#/');
  await expect(
    page.getByRole('heading', { level: 1, name: 'İstanbul otoparkları' }),
  ).toBeAttached();
  await expect(page.locator('main a.satir')).toHaveCount(8);
  await expect(page.locator('.harita[data-durum="hazir"]')).toBeVisible();
  await expect(page.locator('.isaret')).toHaveCount(12);
  await expect(page).toHaveTitle('YerVar');
});

test('haritada işarete dokununca önizleme çıkar, "Durumu gör" durum sayfasını açar', async ({
  page,
}) => {
  await page.goto('./#/');
  await expect(page.locator('.harita[data-durum="hazir"]')).toBeVisible();
  await page.locator('.isaret.ton-belirsiz').click();
  const onizleme = page.locator('.on-izleme');
  await expect(onizleme).toContainText('Mecidiyeköy Katlı Otoparkı');
  await expect(onizleme).toContainText('Belirsiz');
  await onizleme.getByRole('link', { name: 'Durumu gör' }).click();
  await expect(
    page.getByRole('heading', { level: 1, name: 'Mecidiyeköy Katlı Otoparkı' }),
  ).toBeVisible();
});

test('durum sayfası bandı, aralığı, sonraki iki saati ve eğilimi gösterir', async ({ page }) => {
  await page.goto('./#/otopark/1034');
  await expect(page.locator('.cevap-bant')).toHaveText('Belirsiz');
  await expect(page.locator('.cevap-sayi')).toContainText('7–30');
  await expect(page.locator('.cevap-sayi')).toContainText('saat 08:35 için');
  await expect(page.locator('.zaman-seridi li')).toHaveCount(4);
  await expect(page.getByText('Doluyor: boş yer azalıyor.')).toBeVisible();
  await expect(page.getByRole('link', { name: /Haritalarda aç/ })).toHaveAttribute(
    'href',
    /query=41\.06722,28\.99459$/,
  );
  await expect(page).toHaveTitle('Mecidiyeköy Katlı Otoparkı · YerVar');
});

test('bilinmeyen otopark numarasında bunu söyler', async ({ page }) => {
  await page.goto('./#/otopark/9999');
  await expect(
    page.getByRole('heading', { level: 1, name: 'Bu numarayla bir otopark yok.' }),
  ).toBeVisible();
});

test('liste gösterilebilen bütün otoparkları sayar', async ({ page }) => {
  await page.goto('./#/liste');
  await expect(page.getByRole('heading', { level: 1, name: 'Liste' })).toBeVisible();
  await listeGelsin(page);
  await expect(page.locator('.otopark-listesi').first().locator('a.satir')).toHaveCount(9);
  await expect(page.getByText('Veri yok (3)')).toBeVisible();
  await expect(page.getByText('görünmeyen 2 otopark gösterilmiyor')).toBeVisible();
});

test('"Nasıl çalışır?" sayfası atıfı, harita gizliliğini ve veri yaşını anlatır', async ({
  page,
}) => {
  await page.goto('./#/hakkinda');
  await expect(page.getByRole('heading', { level: 1, name: 'Nasıl çalışır?' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Veri yaşı' })).toBeVisible();
  await expect(page.getByText('baktığın bölge o sunucuya iletilir')).toBeVisible();
  await expect(page.getByText('İSPARK ile resmî bağlantısı yoktur').first()).toBeVisible();
});

test('bilinmeyen adreste "sayfa bulunamadı" der ve ana sayfaya döndürür', async ({ page }) => {
  await page.goto('./#/yok');
  await expect(page.getByRole('heading', { level: 1, name: 'Sayfa bulunamadı' })).toBeVisible();
  await page.getByRole('link', { name: 'Ana sayfaya dön' }).click();
  await expect(page.locator('main a.satir').first()).toBeVisible();
});

test('tarayıcının geri ve ileri düğmeleri ekranlar arasında gezer', async ({ page }) => {
  await page.goto('./#/');
  await page.locator('main a.satir').first().click();
  await expect(page.locator('.detay-baslik')).toBeVisible();
  await page.locator('.ust-gezinme').getByRole('link', { name: 'Liste' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Liste' })).toBeVisible();
  await page.goBack();
  await expect(page.locator('.detay-baslik')).toBeVisible();
  await page.goBack();
  await expect(page.locator('main a.satir').first()).toBeVisible();
  await page.goForward();
  await expect(page.locator('.detay-baslik')).toBeVisible();
});

test('her ekranda alt bilgi ve prototip filigranı görünür', async ({ page }) => {
  for (const adres of ['./#/', './#/liste', './#/hakkinda', './#/otopark/1021', './#/yok']) {
    await page.goto(adres);
    await expect(page.locator('.alt-bilgi')).toContainText('İBB Açık Veri Portalı');
    await expect(page.getByText('Prototip · sahte veri')).toBeVisible();
  }
});

for (const saatDilimi of ['America/New_York', 'Asia/Tokyo']) {
  test.describe(`cihaz saat dilimi ${saatDilimi}`, () => {
    test.use({ timezoneId: saatDilimi });

    test('saatler yine İstanbul saatiyle yazılır', async ({ page }) => {
      await page.goto('./#/');
      await expect(page.locator('.veri-cipi')).toContainText('Veri 08:05');
      await expect(page.locator('.varis-secenek').nth(2)).toContainText('08:35');
    });
  });
}
