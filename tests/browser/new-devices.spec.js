import {test,expect} from '@playwright/test';

test('all 15 devices render, new controls save, intercom actions execute',async({page,request})=>{
  await request.post('/api/demo/reset',{data:{}});
  await page.addInitScript(()=>sessionStorage.setItem('guardian-demo-entered','1'));
  await page.goto('/web/#home');
  const state=(await (await request.get('/api/state')).json());
  expect(Object.keys(state.devices)).toHaveLength(15);
  await expect(page.locator('.product-image img')).toHaveCount(15);
  for(const img of await page.locator('.product-image img').all())expect(await img.evaluate(e=>e.complete&&e.naturalWidth>0)).toBe(true);
  for(const name of Object.values(state.metadata).map(m=>m.name)){
    await page.getByRole('button',{name:'Настроить '+name,exact:true}).click();
    const dialog=page.getByRole('dialog',{name,exact:true});
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button',{name:'Закрыть',exact:true}).click();
  }
  const kettle=page.locator('.device-card').filter({has:page.getByRole('button',{name:'Настроить Чайник',exact:true})});
  await kettle.getByRole('switch').click();
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).devices.kettle_1.power).toBe(1);
  const sensor=page.locator('.device-card').filter({has:page.getByRole('button',{name:'Настроить Датчик температуры',exact:true})});
  await expect(sensor.getByRole('switch')).toHaveCount(0);
  await page.getByRole('button',{name:'Настроить Умный телевизор',exact:true}).click();
  let dialog=page.getByRole('dialog',{name:'Умный телевизор',exact:true});
  await dialog.locator('#signal-volume').fill('27');await dialog.locator('#signal-volume').press('Tab');
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).devices.tv_1.volume).toBe(27);
  await dialog.getByRole('button',{name:'Закрыть',exact:true}).click();
  await request.post('/api/demo/start',{data:{preset:'intercom'}});
  await page.getByRole('button',{name:'Настроить Домофон',exact:true}).click();
  dialog=page.getByRole('dialog',{name:'Домофон',exact:true});
  await dialog.getByRole('button',{name:'Открыть дверь',exact:true}).click();
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).devices.intercom_1.door_open).toBe(1);
  await dialog.getByRole('button',{name:'Закрыть',exact:true}).click();
  await page.getByRole('radio',{name:'Ванная',exact:true}).click();
  await expect(page.locator('.product-image')).toHaveCount(2);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
