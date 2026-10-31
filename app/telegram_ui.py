"""Button menus and conversations for Telegram, shared control-plane operations."""
import copy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
import secrets
import time
try:
    from .telegram_scenarios import ScenarioWizard
    from .telegram_media import ASSETS, TEMPLATES, device_photo, test_photo
except ImportError:
    from telegram_scenarios import ScenarioWizard
    from telegram_media import ASSETS, TEMPLATES, device_photo, test_photo

COMMANDS = [('start','Главное меню'),('devices','Устройства и настройки'),('newscenario','Создать сценарий'),
    ('scenarios','Управление сценариями'),('templates','Шаблоны сценариев'),('tests','Аварийные тесты'),
    ('diagnostics','Диагностика устройств'),('stats','Статистика'),('events','История событий'),
    ('ujin','Подключение Ujin'),('notifications','Уведомления'),('cancel','Отменить ввод'),('help','Помощь')]
DEMOS = {'overload':'Перегрузка розетки','co2':'Высокий CO₂','evening':'Вечер','comfort':'Обогрев',
         'leak':'Протечка','fire':'Пожар','intercom':'Домофон','kitchen':'Кухня'}


@dataclass
class Context:
    chat: str
    user: str
    message_id: int | None = None
    media: bool = False
    @property
    def actor(self): return (self.chat, self.user)


class TelegramUI:
    def __init__(self, bot):
        self.bot = bot;self.client = bot.client;self.wizard = ScenarioWizard(bot)

    def button(self, ctx, text, route, *args, revision=None):
        now = time.time()
        for key, value in list(self.bot.actions.items()):
            if value['expires'] < now: self.bot.actions.pop(key, None)
        while len(self.bot.actions) >= 4000: self.bot.actions.pop(next(iter(self.bot.actions)))
        key = secrets.token_hex(6)
        self.bot.actions[key] = {'actor':ctx.actor,'expires':now+1800,'route':route,'args':args,'revision':revision}
        return {'text':str(text)[:90],'callback_data':'b:'+key}

    def render(self, ctx, text, rows=None, photo=None):
        if photo is not None or ctx.media:
            if self.bot.photos.render(ctx, text, rows, photo): return
            return self.bot._send(ctx.chat, text, rows)
        if ctx.message_id and len(str(text).encode('utf-16-le'))//2 <= 3500:
            payload = {'chat_id':ctx.chat,'message_id':ctx.message_id,'text':text,'reply_markup':json.dumps({'inline_keyboard':rows or []},ensure_ascii=False)}
            try: return self.bot._api('editMessageText',payload)
            except RuntimeError: pass
        return self.bot._send(ctx.chat,text,rows)

    def back(self, ctx): return [self.button(ctx,'🏠 Главное меню','home')]

    def home(self, ctx):
        self.bot.sessions.pop(ctx.actor,None)
        rows = [[self.button(ctx,label,route) for label,route in pair] for pair in [
            [('🔌 Устройства','devices'),('📊 Статистика','stats')], [('🧩 Сценарии','scenarios'),('✨ Шаблоны','templates')],
            [('🧪 Аварийные тесты','tests'),('🔎 Диагностика','diagnostics')], [('📋 История','events'),('🔗 Ujin','ujin')],
            [('🔔 Уведомления','notifications'),('🧫 Лаборатория','demo')]]]
        self.render(ctx,'🏠 UjinFizteha\nУстройства, сценарии, тесты и Ujin — тот же дом, что в веб-версии.\n\nВыберите раздел. /help — команды; /cancel — отменить ввод.',rows,photo=ASSETS/'home.jpg')

    def devices(self,ctx):
        state = self.client.state()
        rows = [[self.button(ctx,m['name']+' · '+m['room'],'device',key)] for key,m in state['metadata'].items() if key in state['devices']]
        self.render(ctx,'🔌 Выберите устройство',rows+[self.back(ctx)],photo=ASSETS/'home.jpg')

    def device(self,ctx,device):
        declarations = self.client.declarations()
        if device not in declarations: raise ValueError('Устройство не найдено')
        rows = [[self.button(ctx,'⚙️ '+s['title'],'field',device,s['name'])] for s in declarations[device] if s['management']!='r']
        rows.extend([[self.button(ctx,'🔄 Обновить','device',device)],[self.button(ctx,'◀️ Устройства','devices')]])
        self.render(ctx,self.bot._device_text(device),rows,photo=device_photo(device))

    @staticmethod
    def validate(signal,value):
        if not isinstance(value,(int,float)) or not math.isfinite(value): raise ValueError('Введите конечное число')
        if signal.get('min') is not None and value<signal['min'] or signal.get('max') is not None and value>signal['max']:
            raise ValueError(f"Значение должно быть в диапазоне {signal.get('min','—')} … {signal.get('max','—')}")
        if signal.get('layout') and str(int(value) if value==int(value) else value) not in {str(k) for k in signal['layout']}: raise ValueError('Выберите допустимый режим кнопкой')
        if signal['control']=='button' and value!=1: raise ValueError('Кнопка принимает значение 1')

    def field(self,ctx,device,name):
        signal = next((s for s in self.client.declarations().get(device,[]) if s['name']==name and s['management']!='r'),None)
        if not signal: raise ValueError('Действие недоступно')
        if signal['control']=='button': return self.apply(ctx,device,name,1)
        if signal.get('layout'):
            self.render(ctx,signal['title']+': выберите значение',[[self.button(ctx,str(label),'apply',device,name,float(value))] for value,label in signal['layout'].items()]+[[self.button(ctx,'◀️ К устройству','device',device)]])
        else:
            self.bot.sessions[ctx.actor]={'kind':'value','device':device,'signal':name}
            self.render(ctx,f"{signal['title']}\nВведите число: {signal.get('min','—')} … {signal.get('max','—')} {signal.get('measure','')}\n/cancel — отменить")

    def apply(self,ctx,device,name,value):
        signal=next((s for s in self.client.declarations().get(device,[]) if s['name']==name and s['management']!='r'),None)
        if not signal: raise ValueError('Сигнал недоступен для управления')
        self.validate(signal,value);self.client.apply_command(device,name,value);self.bot.sessions.pop(ctx.actor,None)
        self.render(ctx,'✅ Команда выполнена\n'+self.bot._device_text(device),[[self.button(ctx,'⚙️ Настройки устройства','device',device)],self.back(ctx)],photo=device_photo(device))

    def scenario_photo(self,item):
        when=item.get('when',{})
        for template in self.client.templates():
            condition=template['scenario']['when']
            if all(when.get(k)==condition.get(k) for k in ('device','signal','operator')):
                return TEMPLATES/(template['key']+'.jpg')
        return device_photo(when.get('device'))

    def scenario_text(self,item):
        state,decl=self.client.state(),self.client.declarations()
        def describe(a):
            signal=next((s for s in decl.get(a['device'],[]) if s['name']==a['signal']),{})
            value=self.bot._layout_value(decl.get(a['device'],[]),a['signal'],a['value'])
            return f"{state['metadata'].get(a['device'],{}).get('name',a['device'])} · {signal.get('title',a['signal'])} {a.get('operator','→')} {value} {signal.get('measure','')}".strip()
        lines=[item.get('name') or 'Без названия','✅ Активен' if item.get('enabled',True) else '⏸ Выключен']
        if item.get('when'): lines.append('\nЕсли: '+describe(item['when']))
        lines.extend(f"Тогда {i+1}: {describe(a)}" for i,a in enumerate(item.get('do',[])))
        return '\n'.join(lines)

    def scenarios(self,ctx):
        items=self.client.scenarios()
        rows=[[self.button(ctx,('✅ ' if s['enabled'] else '⏸ ')+s['name'],'scenario',s['id'])] for s in items]
        rows.extend([[self.button(ctx,'➕ Новый сценарий','newscenario'),self.button(ctx,'✨ Шаблоны','templates')],self.back(ctx)])
        self.render(ctx,f'🧩 Сценарии: {len(items)}',rows,photo=ASSETS/'home.jpg')

    def scenario(self,ctx,key):
        item=next((s for s in self.client.scenarios() if s['id']==key),None)
        if not item: raise ValueError('Сценарий не найден')
        rows=[[self.button(ctx,'⏸ Выключить' if item['enabled'] else '✅ Включить','toggle',key,not item['enabled'])],
            [self.button(ctx,'✏️ Изменить','edit',key),self.button(ctx,'🗑 Удалить','delete',key)],
            [self.button(ctx,'🧪 Проверить на 30 секунд','simulate',key)],[self.button(ctx,'◀️ Сценарии','scenarios')]]
        self.render(ctx,self.scenario_text(item),rows,photo=self.scenario_photo(item))

    def events(self,ctx,kind='all',limit=20):
        events=[e for e in self.client.events(200) if e['type']!='log' and not e.get('notification_handled') and
                (kind=='all' or e['type']==kind or kind=='alarm' and e.get('category')=='safety' or
                 kind=='command' and e.get('category')=='commands')]
        zone=timezone(timedelta(hours=5))
        lines=['📋 История событий']+[datetime.fromtimestamp(e.get('time',time.time()),zone).strftime('%H:%M:%S')+' — '+str(e.get('message') or e['type']) for e in events[-limit:]]
        rows=[[self.button(ctx,label,'events',value)] for label,value in [('Все события','all'),('Безопасность','alarm'),('Сценарии','scenario_triggered'),('Команды','command')]]
        self.render(ctx,'\n'.join(lines),rows+[self.back(ctx)],photo=ASSETS/'home.jpg')

    def stats(self,ctx):
        state=self.client.state();summary=state['summary'];history=self.client.history(300)
        lines=['📊 Статистика дома',f"Потребление: {self.bot._number(summary['power_w'])} Вт",f"Энергия за сеанс: {self.bot._number(summary['energy_kwh'])} кВт·ч",f"Активных сценариев: {summary['active_scenarios']}",'']
        lines.extend(f"{state['metadata'][key]['name']}: {self.bot._number(v['power_w'])} Вт" for key,v in sorted(state['devices'].items(),key=lambda p:p[1].get('power_w',0),reverse=True) if 'power_w' in v)
        if history: lines.append(f"Пик за последние {len(history)} отсчётов: {max(h['power_w'] for h in history)} Вт")
        self.render(ctx,'\n'.join(lines),[[self.button(ctx,'🔄 Обновить','stats')],self.back(ctx)],photo=ASSETS/'counter.jpg')

    def tests(self,ctx,emergency=True):
        data=self.client.test_catalog(emergency);items=data['tests' if emergency else 'devices']
        rows=[[self.button(ctx,'▶️ Запустить все тесты','test_run',emergency,None)]]
        rows.extend([[self.button(ctx,c['name'],'test_info',emergency,c['id'])] for c in items])
        self.render(ctx,'🧪 Аварийные тесты' if emergency else '🔎 Диагностика устройств',rows+[self.back(ctx)],photo=ASSETS/'home.jpg')

    def test_run(self,ctx,emergency,case):
        report=self.client.run_tests(case,emergency);self.bot.reports[ctx.actor]=report
        lines=['🧪 Изолированный стенд: состояние дома не изменено.',f"Пройдено: {report['summary']['passed']} / {report['summary']['total']}"]
        rows=[]
        for i,result in enumerate(report['results']):
            label=('✅ ' if result['status']=='passed' else '❌ ')+result['name'];lines.append(label)
            rows.append([self.button(ctx,label,'test_result',report['id'],i)])
        rows.extend([[self.button(ctx,'📎 Скачать JSON-отчёт','report',report['id'])],self.back(ctx)])
        self.render(ctx,'\n'.join(lines),rows,photo=test_photo(case,emergency))

    def test_result(self,ctx,key,index):
        report=self.bot.reports.get(ctx.actor)
        if not report or report['id']!=key: raise ValueError('Отчёт устарел. Запустите тест заново.')
        result=report['results'][index];lines=['🧪 Тестовый стенд: '+result['name'],'']
        for check in result['checks']:
            lines.append(('✅ ' if check['passed'] else '❌ ')+check['title'])
            lines.append(check.get('error') or f"Ожидание: {check.get('comparison','==')} {check.get('expected')} · Получено: {check.get('actual')} {check.get('measure','')}")
        for stage in result.get('timeline',[]):
            lines.append(f"\n{stage['title']} · {stage['seconds']} с")
            lines.extend(f"{r['source']} · {r['title']}: {r.get('label') or r['value']} {r.get('measure','')}" for r in stage['readings'])
        self.render(ctx,'\n'.join(lines),[[self.button(ctx,'📎 JSON-отчёт','report',key)],self.back(ctx)],photo=test_photo(result.get('id') or result.get('device'),report.get('type')!='device-diagnostics' and 'timeline' in result))

    def ujin(self,ctx):
        status=self.client.ujin_status()
        lines=['🔗 Ujin',status['message'],f"Режим: {status['mode']}",f"Подтверждено показаний: {status['published']} · команд выполнено: {status['commands_applied']}"]
        lines.extend(f"{d['name']}: {d['state']} · сигналов для команд: {d['writable_signals']}" for d in status['devices'])
        rows=[[self.button(ctx,'🔄 Обновить','ujin')]]
        if status['configured']:
            if status['running']: rows.append([self.button(ctx,'⏹ Остановить обмен','ujin_action','stop','read')])
            else: rows.extend([[self.button(ctx,'Проверить подключение','ujin_action','check','read')],[self.button(ctx,'Наблюдать','ujin_action','start','read'),self.button(ctx,'Запустить обмен','ujin_action','start','sync')]])
        rows.extend([[{'text':'Панель сигналов','url':status['panel_url']}],self.back(ctx)])
        self.render(ctx,'\n'.join(lines),rows,photo=ASSETS/'hub.jpg')

    def dispatch(self,ctx,route,*args):
        if route not in ('wizard','newscenario','edit','template'): self.bot.sessions.pop(ctx.actor,None)
        if route=='home': self.home(ctx)
        elif route=='devices': self.devices(ctx)
        elif route=='device': self.device(ctx,*args)
        elif route=='field': self.field(ctx,*args)
        elif route=='apply': self.apply(ctx,*args)
        elif route=='status': self.render(ctx,self.bot._status_text(),[self.back(ctx)],photo=ASSETS/'home.jpg')
        elif route=='stats': self.stats(ctx)
        elif route=='events': self.events(ctx,*args)
        elif route=='scenarios': self.scenarios(ctx)
        elif route=='scenario': self.scenario(ctx,*args)
        elif route=='newscenario': self.wizard.begin(ctx)
        elif route=='wizard': self.wizard.action(ctx,*args)
        elif route=='edit':
            item=next(s for s in self.client.scenarios() if s['id']==args[0]);self.wizard.begin(ctx,item,photo=self.scenario_photo(item))
        elif route=='toggle': self.client.toggle_scenario(*args);self.scenario(ctx,args[0])
        elif route=='delete': self.render(ctx,'Удалить сценарий?',[[self.button(ctx,'🗑 Да, удалить','delete_yes',args[0])],[self.button(ctx,'Отмена','scenario',args[0])]])
        elif route=='delete_yes': self.client.delete_scenario(args[0]);self.scenarios(ctx)
        elif route=='simulate':
            item=next(s for s in self.client.scenarios() if s['id']==args[0]);result=self.client.simulate(30,item)
            self.render(ctx,f"🧪 {sum(e['type']=='scenario_triggered' for e in result['events'])} срабатываний за 30 секунд. Состояние дома не изменилось.",[[self.button(ctx,'◀️ К сценарию','scenario',args[0])]])
        elif route=='templates': self.render(ctx,'✨ Шаблоны: выбор открывает черновик.',[[self.button(ctx,t['scenario']['name'],'template',t['key'])] for t in self.client.templates()]+[self.back(ctx)],photo=ASSETS/'home.jpg')
        elif route=='template':
            template=next(t for t in self.client.templates() if t['key']==args[0])
            item=copy.deepcopy(template['scenario']);base=item['name'];names={s['name'] for s in self.client.scenarios()};i=2
            while item['name'] in names: item['name']=f'{base} ({i})';i+=1
            key=template['key']
            photo=TEMPLATES/f'{key}.jpg' if Path(key).name==key else ASSETS/'home.jpg'
            self.wizard.begin(ctx,item,photo=photo)
        elif route in ('tests','diagnostics'): self.tests(ctx,route=='tests')
        elif route=='test_info':
            emergency,case=args;data=self.client.test_catalog(emergency)
            item=next(c for c in data['tests' if emergency else 'devices'] if c['id']==case)
            self.render(ctx,f"🧪 {item['name']}\n{item['description']}\n{item.get('expected','')}\n{item.get('note','')}\n\nИзолированный стенд: дом не меняется.",[[self.button(ctx,'▶️ Запустить тест','test_run',emergency,case)],self.back(ctx)],photo=test_photo(case,emergency))
        elif route=='test_run': self.test_run(ctx,*args)
        elif route=='test_result': self.test_result(ctx,*args)
        elif route=='report':
            report=self.bot.reports.get(ctx.actor)
            if not report or report['id']!=args[0]: raise ValueError('Отчёт устарел')
            self.bot._api('sendDocument',{'chat_id':ctx.chat,'caption':'UjinFizteha · отчёт изолированных тестов','document':('ujinfizteha-tests.json',json.dumps(report,ensure_ascii=False,indent=2).encode())})
        elif route=='ujin': self.ujin(ctx)
        elif route=='ujin_action': self.client.ujin_action(*args);self.ujin(ctx)
        elif route=='notifications':
            enabled=ctx.chat in self.bot.subscribers
            self.render(ctx,'🔔 Уведомления '+('включены' if enabled else 'выключены'),[[self.button(ctx,'Выключить' if enabled else 'Включить','subscribe',not enabled)],self.back(ctx)])
        elif route=='subscribe':
            with self.bot.state_lock:
                if args[0]: self.bot.subscribers.add(ctx.chat)
                else: self.bot.subscribers.discard(ctx.chat)
                self.bot.save_state()
            self.dispatch(ctx,'notifications')
        elif route=='demo': self.render(ctx,'🧫 Эксперименты меняют виртуальные устройства; при активном обмене показания отправляются в Ujin.',[[self.button(ctx,title,'experiment',preset)] for preset,title in DEMOS.items()]+[[self.button(ctx,'♻️ Сбросить эмуляторы','reset')],self.back(ctx)],photo=ASSETS/'home.jpg')
        elif route=='experiment': self.client.experiment(args[0]);self.render(ctx,'🧫 Эксперимент запущен\n'+self.bot._status_text(),[self.back(ctx)],photo=ASSETS/'home.jpg')
        elif route=='reset': self.render(ctx,'Сбросить состояния устройств? Сценарии сохранятся.',[[self.button(ctx,'♻️ Сбросить','reset_yes')],self.back(ctx)])
        elif route=='reset_yes': self.client.reset();self.render(ctx,'♻️ Устройства сброшены. Сценарии сохранены.',[self.back(ctx)])
        else: raise ValueError('Неизвестное действие. /start — меню')

    def natural(self,ctx,text):
        text=text.lower().strip().rstrip('.!')
        m=re.fullmatch(r'(включи|включить|выключи|выключить|отключи|отключить) (свет|розетку|вентиляцию|термостат|телевизор|чайник|духовку)',text)
        if m:
            device,signal,on={'свет':('light_1','lamp',1),'розетку':('smart_plug_1','power_switch',1),'вентиляцию':('ventilation_1','mode',1),'термостат':('thermostat_1','mode',3),'телевизор':('tv_1','power',1),'чайник':('kettle_1','power',1),'духовку':('oven_1','power',1)}[m[2]]
            self.apply(ctx,device,signal,on if m[1].startswith('включ') else 0);return True
        for pattern,device,signal in [(r'яркость(?: света)?\s+(\d+(?:[.,]\d+)?)\s*%?','light_1','brightness'),(r'температур[ау](?: термостата)?\s+(\d+(?:[.,]\d+)?)','thermostat_1','target_temp'),(r'скорость(?: вентиляции)?\s+(\d+)','ventilation_1','fan_speed')]:
            m=re.fullmatch(pattern,text)
            if m: self.apply(ctx,device,signal,float(m[1].replace(',','.')));return True
        return False

    def message(self,ctx,text):
        if text.startswith('/'):
            command,_,rest=text.partition(' ');command=command.split('@')[0].lower();rest=rest.strip()
            self.bot.sessions.pop(ctx.actor,None)
            if command=='/start':
                with self.bot.state_lock: self.bot.subscribers.add(ctx.chat);self.bot.save_state()
                self.home(ctx)
            elif command in ('/cancel','/menu'): self.home(ctx)
            elif command=='/help': self.render(ctx,'🏠 UjinFizteha\n'+'\n'.join('/'+c+' — '+d for c,d in COMMANDS)+'\n\nМожно написать: «включи свет», «яркость 45%», «скорость вентиляции 3».\n/set light_1 brightness 45 — точная команда.\nКоманды устройств выполняются сразу, как в веб-версии.',[self.back(ctx)])
            elif command=='/device': self.device(ctx,rest) if rest else self.devices(ctx)
            elif command=='/set':
                args=rest.split()
                if len(args)!=3: raise ValueError('Формат: /set light_1 brightness 45')
                self.apply(ctx,args[0],args[1],float(args[2].replace(',','.')))
            elif command in ('/scenario_on','/scenario_off'): self.client.toggle_scenario(rest,command=='/scenario_on');self.scenarios(ctx)
            elif command=='/events': self.events(ctx,limit=min(30,max(1,int(rest))) if rest else 20)
            elif command=='/demo': self.dispatch(ctx,'experiment',rest) if rest in DEMOS else self.dispatch(ctx,'demo')
            elif command=='/reset': self.dispatch(ctx,'reset')
            elif command=='/health': self.render(ctx,'✅ Control plane: '+str(self.client.health()['status']))
            elif command=='/id': self.render(ctx,'chat_id: '+ctx.chat)
            elif command[1:] in ('status','devices','stats','scenarios','newscenario','templates','tests','diagnostics','ujin','notifications'): self.dispatch(ctx,command[1:])
            else: self.render(ctx,'Неизвестная команда. /help', [self.back(ctx)])
        else:
            session=self.bot.sessions.get(ctx.actor)
            if session and session['kind']=='scenario': self.wizard.text(ctx,text)
            elif session and session['kind']=='value': self.apply(ctx,session['device'],session['signal'],float(text.replace(',','.')))
            elif not self.natural(ctx,text): self.render(ctx,'Выберите действие в меню или напишите, например: «включи свет».',[self.back(ctx)])

    def callback(self,ctx,data):
        item=self.bot.actions.get(data[2:])
        if not item or item['actor']!=ctx.actor or item['expires']<time.time(): raise ValueError('Меню устарело или принадлежит другому пользователю. /start — открыть своё меню')
        if item['revision'] and self.bot.sessions.get(ctx.actor,{}).get('revision')!=item['revision']: raise ValueError('Этот шаг черновика уже изменён. /newscenario — начать заново')
        if item['route'] in ('apply','delete_yes','reset_yes','experiment','ujin_action','wizard'): self.bot.actions.pop(data[2:],None)
        self.dispatch(ctx,item['route'],*item['args'])
