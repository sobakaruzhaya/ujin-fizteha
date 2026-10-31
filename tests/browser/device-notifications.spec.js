import { test, expect } from '@playwright/test';

test('all fifteen devices show their own server notification without kettle-specific titles', async ({ page, request }) => {
  await request.post('/api/demo/reset', { data: {} });
  await request.post('/api/commands', { data: { device: 'thermostat_1', signal: 'mode', value: 0 } });
  await page.addInitScript(() => sessionStorage.setItem('guardian-demo-entered', '1'));
  await page.goto('/web/#home');
  await expect(page.getByRole('button', { name: 'Настроить Чайник', exact: true })).toBeVisible();
  const { metadata } = await (await request.get('/api/state')).json();
  const actions = [
    ['smart_plug_1', 'power_switch', 1], ['light_1', 'lamp', 1], ['thermostat_1', 'mode', 1],
    ['ventilation_1', 'mode', 0], ['temp_sensor_1', 'calibration', 1], ['leak_1', 'self_test', 1],
    ['hub_1', 'mute', 1], ['fire_1', 'threshold', 65], ['counter_1', 'load_relay', 0],
    ['tv_1', 'power', 1], ['fridge_1', 'mode', 2], ['kettle_1', 'power', 1],
    ['stove_1', 'burner_1', 2], ['oven_1', 'power', 1], ['intercom_1', 'volume', 40],
  ];
  for (const [device, signal, value] of actions) {
    const response = await request.post('/api/commands', { data: { device, signal, value } });
    expect(response.ok()).toBeTruthy();
    const notice = page.locator('.home-notification').filter({ hasText: metadata[device].name });
    await expect(notice).toHaveCount(1);
    if (device !== 'kettle_1') await expect(notice).not.toContainText('Чайник включён');
    // Closing a toast keeps subsequent messages visible even on a small screen.
    for (const close of await page.getByRole('button', { name: 'Закрыть уведомление', exact: true }).all()) {
      await close.click();
    }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await request.post('/api/commands', { data: { device: 'light_1', signal: 'lamp', value: 0 } });
  const notice = page.locator('.home-notification').filter({ hasText: 'Основной свет' });
  await expect(notice).toBeVisible();
  const box = await notice.boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(390);
});

test('a short alarm and recovery between polls are shown once from the event journal', async ({ page, request }) => {
  await page.addInitScript(() => sessionStorage.setItem('guardian-demo-entered', '1'));
  const state = await (await request.get('/api/state')).json();
  state.notification_protocol = 1;
  state.devices.fire_1.alarm = 0;
  let events = [];
  await page.route('**/api/state', route => route.fulfill({ json: state }));
  await page.route('**/api/events', route => route.fulfill({ json: events }));
  await page.goto('/web/#home');
  await expect(page.getByRole('button', { name: 'Настроить Пожарный датчик', exact: true })).toBeVisible();
  events = [
    { id: 'fire-start', type: 'alarm', device: 'fire_1', signal: 'alarm', notification: true, kind: 'error', title: 'Пожарная тревога', category: 'safety', message: 'Пожарный датчик: обнаружен дым.' },
    { id: 'fire-end', type: 'device_recovered', device: 'fire_1', signal: 'alarm', notification: true, kind: 'success', title: 'Устройство вернулось в норму', category: 'safety', message: 'Пожарный датчик: состояние восстановлено.' },
  ];
  const region = page.getByRole('complementary', { name: 'Уведомления', exact: true });
  await expect(region).toContainText('Пожарная тревога');
  await expect(region).toContainText('состояние восстановлено');
  await expect(region.locator('.notification-error')).toHaveCount(1);
  await expect(region.locator('.notification-success')).toHaveCount(1);
  await page.getByRole('link', { name: 'История', exact: true }).first().click();
  await page.getByRole('button', { name: 'Безопасность', exact: true }).click();
  await expect(page.locator('.activity-list')).toContainText('обнаружен дым');
  await expect(page.locator('.activity-list')).toContainText('состояние восстановлено');
});
