import {test,expect} from '@playwright/test';

test.beforeEach(async({page})=>{
  await page.addInitScript(()=>sessionStorage.setItem('guardian-demo-entered','1'));
  await page.goto('/web/#tests');
});

async function seek(page,index) {
  const slider=page.getByRole('slider',{name:'Шаг записи теста',exact:true});
  await slider.focus();await slider.press('Home');
  for(let i=0;i<index;i++)await slider.press('ArrowRight');
}

test('recorded power rises, protection cuts the relay, pause and replay preserve actual readings',async({page})=>{
  const live=[];page.on('request',r=>{if(r.url().includes('/api/commands/'))live.push(r.url());});
  const response=page.waitForResponse(r=>r.url().endsWith('/api/emergency-tests')&&r.request().method()==='POST');
  const card=page.getByRole('article',{name:'Перегрузка розетки',exact:true});
  await card.getByRole('button',{name:'Запустить тест',exact:true}).click();
  const result=(await (await response).json()).results[0];
  const viewer=page.getByRole('region',{name:'Визуализация: Перегрузка розетки',exact:true});
  await expect(viewer).toBeVisible();
  await viewer.getByRole('button',{name:'Пауза воспроизведения'}).click();
  const slider=viewer.getByRole('slider',{name:'Шаг записи теста',exact:true});
  const paused=await slider.inputValue();
  await page.waitForTimeout(500);
  expect(await slider.inputValue()).toBe(paused);
  const trip=result.trace.findIndex(f=>f.readings.some(r=>r.signal==='overload_alarm'&&r.value===1));
  await seek(page,trip);
  await expect(viewer.locator('.playback-main-reading')).toContainText(/2\s?400/);
  await expect(viewer.locator('[data-signal="smart_plug_1.power_w"]')).toContainText('0');
  await expect(viewer.locator('[data-signal="smart_plug_1.power_switch"]')).toContainText('выкл');
  await expect(viewer.locator('.playback-state')).toContainText('тревоге');
  await expect(viewer.getByRole('img',{name:/График/})).toBeVisible();
  const peakPath=await viewer.locator('.trace-line:not(.trace-secondary)').getAttribute('d');
  await viewer.getByRole('button',{name:'Воспроизвести сначала'}).click();
  await expect(viewer.locator('.trace-line:not(.trace-secondary)')).not.toHaveAttribute('d',peakPath);
  await viewer.getByLabel('Скорость воспроизведения',{exact:true}).selectOption('4');
  await expect(card.locator('.test-result-badge')).toContainText('Пройден',{timeout:10000});
  await expect(viewer.locator('.playback-main-reading')).toContainText('900');
  await expect(viewer.locator('.playback-verdict')).toContainText('Проверка пройдена');
  expect(live).toEqual([]);
  await card.getByRole('button',{name:'Посмотреть ход теста'}).click();
  await expect(viewer.getByRole('button',{name:'Пауза воспроизведения'})).toBeVisible();
});

test('gas readings, threshold and siren are visible on a narrow screen',async({page})=>{
  await page.setViewportSize({width:320,height:844});
  const response=page.waitForResponse(r=>r.url().endsWith('/api/emergency-tests')&&r.request().method()==='POST');
  await page.getByRole('article',{name:'Утечка газа',exact:true}).getByRole('button',{name:'Запустить тест',exact:true}).click();
  const result=(await (await response).json()).results[0];
  const viewer=page.getByRole('region',{name:'Визуализация: Утечка газа',exact:true});
  await viewer.getByRole('button',{name:'Пауза воспроизведения'}).click();
  const peak=result.trace.findIndex(f=>f.readings.some(r=>r.signal==='concentration'&&r.value===25));
  await seek(page,peak);
  await expect(viewer.locator('.playback-main-reading')).toContainText('25');
  await expect(viewer.locator('.playback-main-reading')).toContainText('% НКПР');
  await expect(viewer.locator('[data-signal="gas_test.siren"]')).toContainText('Включена');
  await expect(viewer.locator('.trace-threshold')).toContainText('10');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await viewer.getByRole('button',{name:'Перейти к концу записи'}).click();
  await expect(viewer.locator('[data-signal="gas_test.siren"]')).toContainText('Выключена');
});

test('stopping during playback cancels the remaining batch and navigation allows a fresh run',async({page})=>{
  const runs=[];page.on('request',r=>{if(r.url().endsWith('/api/emergency-tests')&&r.method()==='POST')runs.push(r);});
  await page.getByRole('button',{name:'Запустить все тесты'}).click();
  await page.getByRole('button',{name:'Пауза воспроизведения'}).click();
  await page.getByRole('button',{name:'Остановить',exact:true}).click();
  await expect(page.getByText('Проверка остановлена',{exact:true})).toBeVisible();
  await page.waitForTimeout(400);
  expect(runs).toHaveLength(1);
  await page.getByRole('link',{name:'Мой дом',exact:true}).click();
  await page.getByRole('link',{name:'Тесты',exact:true}).click();
  await page.getByRole('article',{name:'Пожар',exact:true}).getByRole('button',{name:'Запустить тест',exact:true}).click();
  await expect(page.getByRole('region',{name:'Визуализация: Пожар',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Перейти к концу записи'}).click();
  await expect(page.getByText('Проверка завершена',{exact:true})).toBeVisible();
});
