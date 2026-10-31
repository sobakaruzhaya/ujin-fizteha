import { test, expect } from '@playwright/test';

test('remote kettle commands show heating, automatic completion and manual stop', async ({ page, request }) => {
  await request.post('/api/demo/reset', { data: {} });
  await page.addInitScript(() => sessionStorage.setItem('guardian-demo-entered', '1'));
  await page.goto('/web/#home');
  const kettle = page.locator('.device-card').filter({ has: page.getByRole('button', { name: 'Настроить Чайник', exact: true }) });
  await expect(kettle.locator('.device-room')).toContainText('Выключен');
  const command = (signal, value) => request.post('/api/commands', { data: { device: 'kettle_1', signal, value } });
  await command('target_temp', 40);
  // Remote clients use the same confirmed command path as MCP.
  const preview = await (await request.post('/api/commands/preview', { data: { device: 'kettle_1', signal: 'power', value: 1 } })).json();
  await request.post(`/api/commands/${preview.confirmation_id}/confirm`, { data: {} });
  await expect(kettle.getByRole('switch')).toHaveAttribute('aria-checked', 'true');
  await expect(kettle.locator('.device-room')).toContainText('Включён · нагрев до 40 °C');
  await expect(kettle.locator('.device-room')).toContainText('Вода нагрета · автоотключение', { timeout: 16000 });
  await expect(kettle.getByRole('switch')).toHaveAttribute('aria-checked', 'false');
  await expect(page.getByRole('complementary', { name: 'Уведомления', exact: true })).toContainText('Вода нагрета');
  await command('target_temp', 80);
  await command('power', 1);
  await expect(kettle.locator('.device-room')).toContainText('Включён · нагрев до 80 °C');
  await command('power', 0);
  await expect(kettle.locator('.device-room')).toContainText('Выключен');
});
