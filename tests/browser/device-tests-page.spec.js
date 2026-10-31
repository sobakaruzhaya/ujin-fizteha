import {test,expect} from '@playwright/test';

test.beforeEach(async({page})=>{
  await page.addInitScript(()=>sessionStorage.setItem('guardian-demo-entered','1'));
  await page.goto('/web/#tests');
  await page.getByRole('button',{name:'Диагностика устройств',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Тесты устройств',exact:true})).toBeVisible();
  await expect(page.locator('.test-device-card')).toHaveCount(15);
});

test('individual and full diagnostics show real checks and export a report',async({page})=>{
  const commandRequests=[];
  page.on('request',r=>{if(r.url().includes('/api/commands/'))commandRequests.push(r.url());});
  const kettle=page.getByRole('article',{name:'Чайник',exact:true});
  await kettle.getByRole('button',{name:'Запустить тест',exact:true}).click();
  await expect(kettle.locator('.test-result-badge')).toContainText('Пройден');
  await kettle.locator('summary').click();
  await expect(kettle.getByText('Защита обнаруживает сухой ход',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Запустить все тесты'}).click();
  await expect(page.locator('.test-result-badge.passed')).toHaveCount(15);
  await expect(page.getByText('Проверка завершена',{exact:true})).toBeVisible();
  expect(commandRequests).toEqual([]);
  await page.getByRole('button',{name:'Ошибки',exact:true}).click();
  await expect(page.getByText('Нет устройств с таким результатом')).toBeVisible();
  await page.getByRole('button',{name:'Все',exact:true}).click();
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('button',{name:'Отчёт',exact:true}).click();
  expect((await downloadPromise).suggestedFilename()).toBe('ujinfizteha-device-tests.json');
  await page.getByRole('button',{name:'Сбросить результаты'}).click();
  await expect(page.locator('.test-result-badge.passed')).toHaveCount(0);
  await expect(page.locator('.test-result-badge.idle')).toHaveCount(15);
});

test('failed requests can be retried and a batch can be stopped',async({page})=>{
  const card=page.getByRole('article',{name:'Умная розетка',exact:true});
  await page.route('**/api/device-tests',r=>r.request().method()==='POST'?r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Сервис проверки недоступен'})}):r.continue());
  await card.getByRole('button',{name:'Запустить тест',exact:true}).click();
  await expect(card.getByRole('alert')).toContainText('Сервис проверки недоступен');
  await page.unroute('**/api/device-tests');
  await card.getByRole('button',{name:'Повторить тест',exact:true}).click();
  await expect(card.locator('.test-result-badge')).toContainText('Пройден');
  await page.route('**/api/device-tests',async r=>{
    if(r.request().method()==='POST')await new Promise(resolve=>setTimeout(resolve,700));
    await r.continue().catch(()=>{});
  });
  await page.getByRole('button',{name:'Запустить все тесты'}).click();
  await page.getByRole('button',{name:'Остановить',exact:true}).click();
  await expect(page.getByText('Проверка остановлена',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Запустить все тесты'})).toBeEnabled();
});

test('navigation, mobile layout and keyboard access work',async({page})=>{
  for(const width of [390,320]){
    await page.setViewportSize({width,height:844});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    const aligned=await page.locator('.pill-nav__track').evaluate(track=>{
      const links=[...track.querySelectorAll('.pill-nav__item')];
      const labels=[...track.querySelectorAll('.pill-nav__ink-item')];
      return links.every((link,i)=>Math.abs(link.getBoundingClientRect().x-labels[i].getBoundingClientRect().x)<1&&Math.abs(link.offsetWidth-labels[i].offsetWidth)<1);
    });
    expect(aligned).toBe(true);
  }
  await page.getByRole('link',{name:'Мой дом',exact:true}).click();
  await page.getByRole('link',{name:'Тесты',exact:true}).click();
  await page.getByRole('button',{name:'Диагностика устройств',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Тесты устройств',exact:true})).toBeVisible();
  const run=page.getByRole('button',{name:'Запустить все тесты'});
  await run.focus();await page.keyboard.press('Enter');
  await expect(page.locator('.test-result-badge.passed')).toHaveCount(15);
});
