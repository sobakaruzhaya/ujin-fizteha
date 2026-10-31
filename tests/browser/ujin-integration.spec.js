import {test,expect} from '@playwright/test';

test.beforeEach(async({page})=>{
  await page.addInitScript(()=>sessionStorage.setItem('guardian-demo-entered','1'));
});

const sample=()=>({configured:true,state:'connected',mode:'read',running:false,message:'Учётная запись employee подключена. Устройства прочитаны.',panel_url:'https://signal-panel.duckdns.org',last_check:1793426400,published:3,commands_applied:0,devices:[{
  family:'light',local_id:'light_1',name:'Основной свет',model:'model_from_packet',publish_class:'example',serial_hint:'…123456',panel_signals:3,api_signals:1,writable_signals:0,verified:0,state:'read_only',signals:[{name:'example_lamp',value:'0.001',management:'r'}]
}]});

test('settings lead to Ujin status, limits are visible and no credentials are requested in the browser',async({page})=>{
  await page.route('**/api/integrations/ujin',r=>r.fulfill({json:sample()}));
  await page.goto('/web/#home');
  await page.getByRole('button',{name:'Настройки и эксперименты',exact:true}).click();
  await page.getByRole('button',{name:'Подключение Ujin',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Подключение Ujin',exact:true})).toBeVisible();
  const card=page.getByRole('article',{name:'Основной свет',exact:true});
  await expect(card.getByText('Команды недоступны',{exact:true})).toBeVisible();
  await expect(card).toContainText('Платформа пока не открыла управляющие сигналы');
  await card.locator('summary').click();
  await expect(card).toContainText('example_lamp');
  await expect(page.locator('input[type=password]')).toHaveCount(0);
  expect(await page.getByRole('link',{name:'Панель сигналов',exact:true}).getAttribute('href')).toBe('https://signal-panel.duckdns.org');
});

test('start and stop use the backend, failures stay reviewable and mobile fits',async({page})=>{
  let state=sample();const actions=[];
  await page.route('**/api/integrations/ujin',async r=>{
    if(r.request().method()==='POST'){
      const body=r.request().postDataJSON();actions.push(body);
      if(body.action==='start')state={...state,running:true,mode:body.mode,state:'connecting'};
      else state={...state,running:false,mode:'off',state:'stopped'};
    }
    await r.fulfill({json:state});
  });
  await page.goto('/web/#integrations');
  await page.getByRole('button',{name:'Запустить обмен',exact:true}).click();
  expect(actions[0]).toEqual({action:'start',mode:'sync'});
  await expect(page.getByRole('button',{name:'Запустить обмен',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Остановить',exact:true}).click();
  expect(actions[1].action).toBe('stop');
  await page.unroute('**/api/integrations/ujin');
  await page.route('**/api/integrations/ujin',r=>r.request().method()==='POST'?r.fulfill({status:400,json:{error:'Ujin отклонил подключение'}}):r.fulfill({json:state}));
  await page.getByRole('button',{name:'Наблюдать',exact:true}).click();
  await expect(page.locator('.ujin-error[role=alert]')).toContainText('Ujin отклонил подключение');
  for(const width of [390,320]){
    await page.setViewportSize({width,height:844});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  }
});
