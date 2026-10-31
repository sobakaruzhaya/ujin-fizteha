import {test, expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

test.beforeEach(async({page})=>{
  await page.addInitScript(()=>sessionStorage.setItem('guardian-demo-entered','1'));
  await page.goto('/web/#tests');
  await expect(page.getByRole('heading',{name:'Аварийные тесты',exact:true})).toBeVisible();
  await expect(page.locator('.test-device-card')).toHaveCount(8);
});

test('emergencies report sensor reactions, rule execution and export observed values',async({page})=>{
  const liveCommands=[];
  page.on('request',r=>{if(r.url().includes('/api/commands/'))liveCommands.push(r.url());});
  const fire=page.getByRole('article',{name:'Пожар',exact:true});
  await fire.getByRole('button',{name:'Запустить тест',exact:true}).click();
  await page.getByLabel('Скорость воспроизведения',{exact:true}).selectOption('4');
  await expect(fire.locator('.test-result-badge')).toContainText('Пройден');
  await fire.getByText('Реакция датчиков',{exact:true}).click();
  await expect(fire.locator('.test-reaction-stage')).toHaveCount(4);
  await expect(fire.getByRole('heading',{name:/Пожарная тревога и отключение техники/})).toBeVisible();
  await expect(fire.getByText('Сработал сценарий «Отключение техники при пожарной тревоге»',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Запустить все тесты'}).click();
  await expect(page.locator('.test-result-badge.passed')).toHaveCount(8,{timeout:30000});
  await expect(page.getByText('Проверка завершена',{exact:true})).toBeVisible();
  expect(liveCommands).toEqual([]);
  const downloading=page.waitForEvent('download');
  await page.getByRole('button',{name:'Отчёт',exact:true}).click();
  const download=await downloading;
  expect(download.suggestedFilename()).toBe('ujinfizteha-emergency-tests.json');
  const report=JSON.parse(await readFile(await download.path(),'utf8'));
  expect(report.type).toBe('emergency');
  expect(report.results).toHaveLength(8);
  const network=report.results.find(r=>r.id==='network-overload');
  expect(network.timeline[1].readings[0].value).toBe(7200);
  expect(network.timeline[2].readings[0].value).toBe(0);
  await page.getByRole('button',{name:'Ошибки',exact:true}).click();
  await expect(page.getByText('Нет тестов с таким результатом')).toBeVisible();
});

test('gas is an explicit test model, distinct from CO2, and works on mobile',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  const gas=page.getByRole('article',{name:'Утечка газа',exact:true});
  await expect(gas.getByText(/В текущем доме датчика газа нет/)).toBeVisible();
  await gas.getByRole('button',{name:'Запустить тест',exact:true}).click();
  await page.getByLabel('Скорость воспроизведения',{exact:true}).selectOption('4');
  await expect(gas.locator('.test-result-badge')).toContainText('Пройден');
  await gas.getByText('Реакция датчиков',{exact:true}).click();
  await expect(gas.getByText('25 % НКПР',{exact:true})).toBeVisible();
  await gas.getByText('Результаты проверки',{exact:true}).click();
  await expect(gas.getByText('Сброс не скрывает продолжающуюся утечку',{exact:true})).toBeVisible();
  for(const width of [390,320]){
    await page.setViewportSize({width,height:844});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  }
});

test('a failed emergency request can be retried and the queue can be stopped',async({page})=>{
  const card=page.getByRole('article',{name:'Перегрузка розетки',exact:true});
  await page.route('**/api/emergency-tests',r=>r.request().method()==='POST'?r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Стенд недоступен'})}):r.continue());
  await card.getByRole('button',{name:'Запустить тест',exact:true}).click();
  await expect(card.getByRole('alert')).toContainText('Стенд недоступен');
  await page.unroute('**/api/emergency-tests');
  await card.getByRole('button',{name:'Повторить тест',exact:true}).click();
  await page.getByLabel('Скорость воспроизведения',{exact:true}).selectOption('4');
  await expect(card.locator('.test-result-badge')).toContainText('Пройден');
  await page.route('**/api/emergency-tests',async r=>{
    if(r.request().method()==='POST')await new Promise(resolve=>setTimeout(resolve,700));
    await r.continue().catch(()=>{});
  });
  await page.getByRole('button',{name:'Запустить все тесты'}).click();
  await page.getByRole('button',{name:'Остановить',exact:true}).click();
  await expect(page.getByText('Проверка остановлена',{exact:true})).toBeVisible();
});
