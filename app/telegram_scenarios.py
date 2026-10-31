"""Per-user scenario drafts for the Telegram interface."""
import copy
import math
import uuid


class ScenarioWizard:
    def __init__(self, bot): self.bot = bot

    def begin(self, ctx, item=None, photo=None):
        draft = copy.deepcopy(item or {'name': '', 'enabled': True, 'do': []})
        self.bot.sessions[ctx.actor] = {'kind': 'scenario', 'draft': draft, 'revision': uuid.uuid4().hex, 'step': 'name', 'photo': photo}
        if item: return self.review(ctx)
        self.bot.render(ctx, '🧩 Новый сценарий\nВведите название.\n/cancel — отменить')

    def current(self, ctx):
        session = self.bot.sessions.get(ctx.actor, {})
        if session.get('kind') != 'scenario': raise ValueError('Черновик устарел. Начните создание сценария заново.')
        return session

    def button(self, ctx, title, action, *args):
        return self.bot.button(ctx, title, 'wizard', action, *args, revision=self.current(ctx)['revision'])

    def touch(self, session): session['revision'] = uuid.uuid4().hex

    def devices(self, ctx, action=False):
        session = self.current(ctx)
        session['step'] = 'action_device' if action else 'when_device'
        state, declarations = self.bot.client.state(), self.bot.client.declarations()
        rows = []
        for device, metadata in state['metadata'].items():
            if any(s['management'] != ('r' if action else 'w') and s['name'] != 'fw' for s in declarations.get(device, [])):
                rows.append([self.button(ctx, metadata['name'], 'device', device)])
        rows.append([self.button(ctx, '◀️ К черновику', 'review')])
        self.bot.render(ctx, 'Тогда: выберите устройство для действия' if action else 'Если: выберите устройство для условия', rows)

    def signals(self, ctx, device, action):
        session = self.current(ctx);session['step'] = 'action_signal' if action else 'when_signal'
        session['selected_device'] = device
        signals = self.bot.client.declarations().get(device, [])
        rows = [[self.button(ctx, s['title'], 'signal', s['name'])] for s in signals if s['name'] != 'fw' and s['management'] != ('r' if action else 'w')]
        self.bot.render(ctx, 'Выберите действие' if action else 'Выберите показатель', rows)

    def value(self, ctx, action):
        session = self.current(ctx);session['step'] = 'action_value' if action else 'when_value'
        signal = next(s for s in self.bot.client.declarations()[session['selected_device']] if s['name'] == session['selected_signal'])
        if action and signal['control'] == 'button': return self.accept_value(ctx, 1)
        rows = []
        for value, title in (signal.get('layout') or {}).items():
            rows.append([self.button(ctx, str(title), 'value', float(value))])
        limits = ''
        if action:
            limits = f"\nДиапазон: {signal.get('min', '—')} … {signal.get('max', '—')} {signal.get('measure', '')}"
        self.bot.render(ctx, f"{signal['title']}: выберите значение или введите число{limits}", rows)

    def accept_value(self, ctx, value):
        session = self.current(ctx)
        if not math.isfinite(value): raise ValueError('Введите конечное число')
        entry = {'device': session['selected_device'], 'signal': session['selected_signal'], 'value': value}
        if session['step'] == 'when_value':
            self.touch(session)
            entry['operator'] = session['operator'];session['draft']['when'] = entry
            if not session['draft']['do']: return self.devices(ctx, True)
        else:
            signal = next(s for s in self.bot.client.declarations()[entry['device']] if s['name'] == entry['signal'])
            self.bot.validate_value(signal, value)
            self.touch(session)
            index = session.pop('editing_action', None)
            if index is None: session['draft']['do'].append(entry)
            else: session['draft']['do'][index] = entry
        return self.review(ctx)

    def text(self, ctx, text):
        session = self.current(ctx)
        if session['step'] == 'name':
            if not text.strip() or len(text.strip()) > 120: raise ValueError('Название должно содержать от 1 до 120 символов')
            session['draft']['name'] = text.strip();self.touch(session)
            if 'when' in session['draft']: self.review(ctx)
            else: self.devices(ctx)
        elif session['step'] in ('when_value', 'action_value'):
            try: value = float(text.replace(',', '.'))
            except ValueError: raise ValueError('Введите число, например 22.5') from None
            self.accept_value(ctx, value)
        else: self.bot.render(ctx, 'Выберите вариант кнопкой. /cancel — отменить')

    def review(self, ctx):
        session = self.current(ctx);session['step'] = 'review';draft = session['draft']
        if draft.get('when'): session['photo'] = self.bot.scenario_photo(draft)
        rows = [[self.button(ctx, '✏️ Название', 'name'), self.button(ctx, 'Если: изменить условие', 'when')],
                [self.button(ctx, '➕ Добавить действие', 'add')],
                [self.button(ctx, '✅ Активировать после сохранения' if draft.get('enabled', True) else '⏸ Сохранить выключенным', 'enabled')]]
        for i in range(len(draft['do'])):
            rows.append([self.button(ctx, f'✏️ Действие {i+1}', 'edit_action', i), self.button(ctx, f'🗑 Действие {i+1}', 'remove_action', i)])
        if draft.get('name') and draft.get('when') and draft.get('do'):
            rows.append([self.button(ctx, '🧪 Проверить на 30 секунд', 'test')])
            rows.append([self.button(ctx, '💾 Сохранить сценарий', 'save')])
        rows.append([self.button(ctx, 'Отмена', 'cancel')])
        self.bot.render(ctx, '📝 Черновик сценария\n' + self.bot.scenario_text(draft), rows, photo=session.get('photo'))

    def action(self, ctx, action, *args):
        session = self.current(ctx)
        step = session['step'];self.touch(session)
        if action == 'device' and step in ('when_device', 'action_device'):
            self.signals(ctx, args[0], step == 'action_device')
        elif action == 'signal' and step in ('when_signal', 'action_signal'):
            session['selected_signal'] = args[0]
            if step == 'action_signal': self.value(ctx, True)
            else:
                session['step'] = 'operator'
                self.bot.render(ctx, 'Выберите условие сравнения', [[self.button(ctx, label, 'operator', op)] for op, label in [('>', 'Больше'), ('<', 'Меньше'), ('==', 'Равно'), ('>=', 'Не меньше'), ('<=', 'Не больше'), ('!=', 'Не равно')]])
        elif action == 'operator' and step == 'operator':
            session['operator'] = args[0];self.value(ctx, False)
        elif action == 'value' and step in ('when_value', 'action_value'): self.accept_value(ctx, args[0])
        elif action == 'review': self.review(ctx)
        elif action == 'when': self.devices(ctx)
        elif action == 'name': session['step'] = 'name';self.bot.render(ctx, 'Введите новое название сценария')
        elif action == 'enabled': session['draft']['enabled'] = not session['draft'].get('enabled', True);self.review(ctx)
        elif action == 'add': session.pop('editing_action', None);self.devices(ctx, True)
        elif action == 'edit_action': session['editing_action'] = int(args[0]);self.devices(ctx, True)
        elif action == 'remove_action':
            del session['draft']['do'][int(args[0])];self.review(ctx)
        elif action == 'test':
            result = self.bot.client.simulate(30, session['draft'])
            count = sum(e['type'] == 'scenario_triggered' for e in result['events'])
            self.bot.send(ctx.chat, f'🧪 Проверка завершена: {count} срабатываний за 30 секунд. Состояние дома не изменилось.')
            self.review(ctx)
        elif action == 'save':
            saved = self.bot.client.create_scenario(session['draft'])
            self.bot.sessions.pop(ctx.actor, None)
            self.bot.render(ctx, f"✅ Сценарий «{saved['name']}» сохранён. Он доступен и в веб-версии.", [[self.bot.button(ctx, '🧩 Сценарии', 'scenarios')]],photo=session.get('photo'))
        elif action == 'cancel': self.bot.sessions.pop(ctx.actor, None);self.bot.home(ctx)
        else: raise ValueError('Этот шаг устарел. Откройте черновик заново.')
