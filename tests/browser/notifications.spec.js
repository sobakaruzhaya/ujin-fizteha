import { test, expect } from '@playwright/test';

test.beforeEach(async ({page,request}) => {
  await request.post('/api/demo/reset',{data:{}});
  await page.addInitScript(()=>sessionStorage.setItem('guardian-demo-entered','1'));
});

test('real alarm transitions and scenario actions notify once, then report recovery',async({page,request})=>{
  const state=await (await request.get('/api/state')).json();
  delete state.notification_protocol; // Exercise compatibility with the legacy signal-only server.
  let events=[{id:'historic-error',type:'error',message:'Old error must not replay'}],polls=0;
  await page.route('**/api/state',r=>{polls++;return r.fulfill({json:state});});
  await page.route('**/api/events',r=>r.fulfill({json:events}));
  await page.goto('/web/#home');
  await expect(page.getByRole('button',{name:'Настроить Умная розетка',exact:true})).toBeVisible();
  const region=page.getByRole('complementary',{name:'Уведомления',exact:true});
  await expect(region).toHaveCount(0);
  state.devices.smart_plug_1.overload_alarm=1;
  state.devices.smart_plug_1.power_switch=0;
  events=[...events,
    {id:'rule-1',type:'scenario_triggered',message:'Сработал сценарий «Защита от перегрузки»'},
    {id:'action-1',type:'command',source:'scenario',device:'smart_plug_1',signal:'power_switch',value:0}];
  await expect(region.getByRole('alert')).toContainText('Перегрузка розетки');
  await expect(region).toContainText('Питание отключено защитой');
  await expect(region).toContainText('Реакция устройств');
  await expect(region).toContainText('Сценарий сработал');
  const before=polls;
  await expect.poll(()=>polls).toBeGreaterThanOrEqual(before+2);
  await expect(region.locator('.notification-error')).toHaveCount(1);
  await expect(region).not.toContainText('Old error');
  const alert=region.getByRole('alert');
  const bounds=await alert.boundingBox();
  expect(bounds.y+bounds.height).toBeLessThanOrEqual(1000);
  await alert.getByRole('button',{name:'Закрыть уведомление'}).click();
  await expect(region.getByRole('alert')).toHaveCount(0);
  state.devices.smart_plug_1.overload_alarm=0;
  await expect(region).toContainText('Устройство вернулось в норму');
});

test('connection failures and recovery do not spam each poll',async({page,request})=>{
  const state=await (await request.get('/api/state')).json();
  let failed=false,polls=0;
  await page.route('**/api/state',r=>{
    polls++;
    return failed?r.fulfill({status:503,json:{error:'offline'}}):r.fulfill({json:state});
  });
  await page.goto('/web/#home');
  await expect(page.getByRole('button',{name:'Настроить Умная розетка',exact:true})).toBeVisible();
  failed=true;
  const region=page.getByRole('complementary',{name:'Уведомления',exact:true});
  await expect(region.getByRole('alert')).toContainText('Нет связи с домом');
  const before=polls;
  await expect.poll(()=>polls).toBeGreaterThanOrEqual(before+2);
  await expect(region.locator('.home-notification')).toHaveCount(1);
  failed=false;
  await expect(region).toContainText('Связь восстановлена');
});

test('command failures remain visible inside native device dialogs and dismiss by keyboard',async({page})=>{
  await page.goto('/web/#home');
  await page.getByRole('button',{name:'Настроить Умная розетка',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Умная розетка',exact:true});
  await page.route('**/api/commands/preview',r=>r.fulfill({status:400,json:{error:'Не удалось изменить лимит'}}));
  const input=dialog.locator('#signal-power_limit_w');
  await input.fill('1800');await input.press('Tab');
  const alert=dialog.getByRole('alert');
  await expect(alert).toContainText('Не удалось изменить лимит');
  await expect(alert).toBeInViewport();
  await alert.focus();await page.keyboard.press('Escape');
  await expect(alert).toHaveCount(0);
  await expect(dialog).toBeVisible();
});

test('test-bench results are labelled, queue fits mobile, and a toast can be swiped away',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/web/#tests');
  const fire=page.getByRole('article',{name:'Пожар',exact:true});
  await fire.getByRole('button',{name:'Запустить тест',exact:true}).click();
  await page.getByLabel('Скорость воспроизведения',{exact:true}).selectOption('4');
  const region=page.getByRole('complementary',{name:'Уведомления',exact:true});
  await expect(region).toContainText('Тестовый стенд');
  await expect(region).toContainText('Пожар: проверка пройдена');
  const toast=region.locator('.swipe-toast__card');
  const box=await toast.boundingBox();
  await page.mouse.move(box.x+box.width/2,box.y+20);
  await page.mouse.down();
  await page.mouse.move(box.x+box.width/2,box.y+90,{steps:8});
  await page.mouse.up();
  await expect(region).toHaveCount(0);
  await page.getByRole('button',{name:'Запустить все тесты'}).click();
  await expect(page.locator('.test-result-badge.passed')).toHaveCount(8,{timeout:30000});
  await expect(region.locator('.home-notification')).toHaveCount(2);
  await expect(region.locator('.notification-pending')).toBeVisible();
  for(const width of [390,320]){
    await page.setViewportSize({width,height:844});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    const bounds=await region.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.x+bounds.width).toBeLessThanOrEqual(width);
    expect(bounds.y+bounds.height).toBeLessThanOrEqual(844);
  }
});
