import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('guardian-demo-entered', '1'));
  await page.goto('/web/#scenarios');
  await page.getByRole('button', { name: 'Шаблоны', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Шаблоны сценариев', exact: true })).toBeFocused();
  await expect(page.locator('.scenario-template')).toHaveCount(8);
});

test('templates filter, open a populated draft and cancel without saving', async ({ page, request }) => {
  const before = await (await request.get('/api/scenarios')).json();
  const filter = page.getByRole('group', { name: 'Категории шаблонов' });
  await filter.getByRole('button', { name: 'Безопасность', exact: true }).click();
  await expect(page.locator('.scenario-template')).toHaveCount(3);
  const card = page.getByRole('article', { name: 'Защита от перегрузки', exact: true });
  const use = card.getByRole('button', { name: 'Использовать шаблон' });
  await use.click();
  const sheet = page.getByRole('dialog', { name: 'Новый сценарий', exact: true });
  await expect(sheet.getByLabel('Название сценария')).toHaveValue('Защита от перегрузки (2)');
  await expect(sheet.getByRole('spinbutton', { name: 'Значение условия' })).toHaveAttribute('aria-valuenow', '2000');
  await expect(sheet.locator('.builder-action-list .builder-card')).toHaveCount(1);
  await expect(sheet.getByRole('button', { name: 'Выключить', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await sheet.getByRole('button', { name: 'Отмена', exact: true }).click();
  await expect(sheet).not.toBeVisible();
  await expect(use).toBeFocused();
  expect(await (await request.get('/api/scenarios')).json()).toEqual(before);
});

test('a template can be edited, saved, executed and survives reload', async ({ page, request }) => {
  await request.post('/api/demo/reset', { data: {} });
  let saved;
  try {
    await page.getByRole('article', { name: 'Киновечер', exact: true }).getByRole('button', { name: 'Использовать шаблон' }).click();
    const sheet = page.getByRole('dialog', { name: 'Новый сценарий', exact: true });
    await sheet.getByLabel('Название сценария').fill('Template cinema integration');
    const brightness = sheet.locator('.builder-action-list .builder-card').first().getByRole('spinbutton', { name: 'Значение действия' });
    await brightness.fill('35');
    await brightness.press('Tab');
    await sheet.getByRole('button', { name: 'Создать сценарий', exact: true }).click();
    await expect(sheet).not.toBeVisible();
    saved = (await (await request.get('/api/scenarios')).json()).find(s => s.name === 'Template cinema integration');
    expect(saved.when).toEqual({ device: 'tv_1', signal: 'power', operator: '==', value: 1 });
    expect(saved.do).toEqual([{ device: 'light_1', signal: 'brightness', value: 35 }, { device: 'light_1', signal: 'lamp', value: 1 }]);
    await request.post('/api/commands/preview', { data: { device: 'tv_1', signal: 'power', value: 1, require_confirmation: false } });
    await expect.poll(async () => (await (await request.get('/api/state')).json()).devices.light_1.brightness).toBe(35);
    expect((await (await request.get('/api/state')).json()).devices.light_1.lamp).toBe(1);
    await page.reload();
    expect((await (await request.get('/api/scenarios')).json()).some(s => s.id === saved.id)).toBe(true);
    await page.getByRole('button', { name: 'Шаблоны', exact: true }).click();
    await page.getByRole('article', { name: 'Киновечер', exact: true }).getByRole('button', { name: 'Использовать шаблон' }).click();
    await expect(page.getByLabel('Название сценария')).toHaveValue('Киновечер');
  } finally {
    if (saved) await request.delete(`/api/scenarios/${saved.id}`);
    await request.post('/api/demo/reset', { data: {} });
  }
});

test('mobile templates fit the screen and unavailable devices disable matching templates', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.route('**/api/devices', async route => {
    const response = await route.fetch();
    const data = await response.json();
    delete data.tv_1;
    await route.fulfill({ response, json: data });
  });
  await page.reload();
  const cinema = page.getByRole('article', { name: 'Киновечер', exact: true });
  await expect(cinema.getByRole('button', { name: 'Использовать шаблон' })).toBeDisabled();
  await expect(cinema.getByText('Нужные устройства недоступны')).toBeVisible();
  await expect(page.getByRole('article', { name: 'Свежий воздух', exact: true }).getByRole('button', { name: 'Использовать шаблон' })).toBeEnabled();
});
