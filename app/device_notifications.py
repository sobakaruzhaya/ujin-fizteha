"""Semantic device transitions shared by web, Telegram, API and MCP.

Measurements are not notifications. Only changes of operating state, settings,
threshold crossings, faults and recoveries enter the event journal.
"""
import copy


POWER_SIGNALS = {'smart_plug': 'power_switch', 'light': 'lamp', 'smart_tv': 'power',
                 'oven': 'power', 'counter': 'load_relay', 'thermostat': 'mode',
                 'ventilation': 'mode', 'fridge': 'mode'}
ALERTS = {
    'overload_alarm': ('Перегрузка розетки', 'Превышен лимит мощности. Питание отключено защитой.', 'error'),
    'anomaly': ('Аномалия питания', 'Обнаружена аномалия питания.', 'error'),
    'leak': ('Обнаружена протечка', 'Датчик обнаружил воду.', 'error'),
    'dry_boil': ('Чайник без воды', 'Защита сухого хода заблокировала нагрев.', 'error'),
    'overheat': ('Перегрев плиты', 'Конфорки отключены встроенной защитой.', 'error'),
    'boil_dry': ('Сухой нагрев плиты', 'Посуда не обнаружена. Нагрев прекращён.', 'warning'),
    'fault': ('Сбой датчика', 'Устройство сообщает о неисправности.', 'error'),
    'low_battery': ('Низкий заряд датчика', 'Замените или зарядите батарею.', 'warning'),
    'tamper': ('Вскрытие корпуса', 'Сработал датчик вскрытия.', 'warning'),
    'descale': ('Требуется очистка чайника', 'Очистите чайник от накипи.', 'warning'),
}


def display(signal, value):
    label = (signal.layout or {}).get(value)
    if label is not None:
        return str(label)
    number = f'{value:g}' if isinstance(value, (int, float)) else str(value)
    return number + (f' {signal.measure}' if signal.measure else '')


class DeviceNotificationObserver:
    def __init__(self, home):
        self.reset(home)

    def reset(self, home):
        self.previous = {key: home._device_state(device) for key, device in home.devices.items()}
        self.conditions = {}
        self.completed_targets = {}
        for key, values in self.previous.items():
            self.conditions[key] = self._alerts(home.metadata[key]['family'], values, {})

    @staticmethod
    def _alerts(family, values, previous):
        rows = {name: (value, name, *ALERTS[name]) for name, value in values.items() if name in ALERTS}
        if 'alarm' in values:
            title = {'fire': 'Пожарная тревога', 'gas': 'Утечка газа', 'fridge': 'Тревога холодильника',
                     'oven': 'Предупреждение духовки'}.get(family, 'Тревога устройства')
            message = {'fire': 'Пожарный датчик сообщает о задымлении.', 'gas': 'Превышен порог концентрации газа.',
                       'fridge': 'Проверьте температуру и состояние двери.',
                       'oven': 'Проверьте дверь и состояние нагрева.'}.get(family, 'Устройство сообщает о тревоге.')
            rows['alarm'] = (values['alarm'], 'alarm', title, message, 'error' if family in ('fire', 'gas') else 'warning')
        if 'online' in values:
            rows['offline'] = (values['online'] == 0, 'online', 'Нет связи с устройством',
                               'Устройство перестало выходить на связь.', 'error')
        if 'battery' in values and 'low_battery' not in values:
            rows['low_battery'] = (values['battery'] <= 20, 'battery', 'Низкий заряд датчика',
                                   'Замените или зарядите батарею.', 'warning')
        if family == 'hub':
            missing = max(0, values['sensors_total'] - values['sensors_online'])
            rows['offline-sensors'] = (missing, 'sensors_online', 'Нет связи с датчиком протечки',
                f"На связи {values['sensors_online']} из {values['sensors_total']} датчиков.", 'warning')
        for key, signal, high, low, title, unit in [
            ('high-co2', 'co2', 1000, 900, 'Высокий уровень CO₂', 'ppm'),
            ('high-power', 'power_w', 6000, 5500, 'Перегрузка электросети', 'Вт'),
        ]:
            if signal not in values or (key == 'high-power' and family != 'counter'):
                continue
            was_high = bool(previous.get(key, (False,))[0])
            active = values[signal] > high or (was_high and values[signal] > low)
            rows[key] = (active, signal, title, f"Измерено {values[signal]:g} {unit}.", 'warning')
        return rows

    def observe(self, home, device_id=None, source='device', command=None):
        for key in ([device_id] if device_id else list(home.devices)):
            device, meta = home.devices[key], home.metadata[key]
            current = home._device_state(device)
            before = self.previous.get(key)
            if before is None:
                self.previous[key] = current
                self.conditions[key] = self._alerts(meta['family'], current, {})
                continue
            family, name = meta['family'], meta['name']
            emitted = False

            def emit(title, message, signal, kind='info', event_type='device_notification', watch_key=None, category='commands'):
                nonlocal emitted
                emitted = True
                home.add_event(event_type, device=key, signal=signal, value=current.get(signal),
                    previous_value=before.get(signal), source=source, title=title,
                    kind=kind, message=f'{name}: {message}', notification=True,
                    watch_key=f'{key}:{watch_key or signal}', category=category)

            old_alerts = self.conditions.get(key, {})
            new_alerts = self._alerts(family, current, old_alerts)
            for watch_key, (value, signal, title, message, kind) in new_alerts.items():
                old_value = old_alerts.get(watch_key, (0,))[0]
                if value == old_value:
                    continue
                if value:
                    if signal == 'alarm' and device.signals[signal].layout:
                        message += f' Причина: {display(device.signals[signal], current[signal])}.'
                    if family == 'hub' and signal == 'leak':
                        message += ' Сирена включена.' if current.get('siren') else ' Звук сирены отключён.'
                    if family == 'thermostat' and signal == 'fault' and not current.get('output'):
                        message += ' Нагрев остановлен.'
                    emit(title, message, signal, kind, 'alarm', watch_key, 'safety')
                elif old_value:
                    emit('Устройство вернулось в норму', f'«{title}» — состояние восстановлено.',
                         signal, 'success', 'device_recovered', watch_key, 'safety')
            self.conditions[key] = new_alerts

            power_signal = POWER_SIGNALS.get(family)
            if power_signal and before.get(power_signal) != current[power_signal]:
                value = current[power_signal]
                if family in ('thermostat', 'ventilation', 'fridge'):
                    details = f'Режим: {display(device.signals[power_signal], value)}.'
                    if family == 'ventilation':
                        details += f" Скорость вентиляции: {current['fan_speed']} / 6."
                    emit('Режим устройства изменён', details, power_signal)
                else:
                    auto_stop = source == 'device' and not value and not any(r[0] for r in new_alerts.values())
                    if auto_stop and (before.get('timer', 0) > 0 and current.get('timer') == 0
                                      or before.get('offline_timeout', 0) > 0 or before.get('auto_off_seconds', 0) > 0):
                        emit('Сработал таймер', 'Работа завершена, питание отключено автоматически.', power_signal, 'success', 'device_finished')
                    else:
                        emit('Устройство включено' if value else 'Устройство выключено',
                             'Питание включено.' if value else 'Питание отключено.', power_signal)
            if family == 'stove':
                burners = [n for n in current if n.startswith('burner_')]
                old_on, new_on = any(before[n] for n in burners), any(current[n] for n in burners)
                if old_on != new_on:
                    finished = not new_on and before['timer'] > 0 and current['timer'] == 0 and source == 'device'
                    changed_burner = next(n for n in burners if before[n] != current[n])
                    emit('Приготовление завершено' if finished else 'Плита включена' if new_on else 'Плита выключена',
                         'Таймер завершён, конфорки выключены.' if finished else 'Конфорки включены.' if new_on else 'Конфорки выключены.',
                         changed_burner, 'success' if finished else 'info', 'device_finished' if finished else 'device_notification')

            for signal in ('door_open', 'call_state', 'failed_attempts', 'siren'):
                if signal not in current or current[signal] == before[signal]:
                    continue
                if signal == 'door_open':
                    emit('Дверь открыта' if current[signal] else 'Дверь закрыта',
                         'Дверь открыта.' if current[signal] else 'Дверь закрыта.', signal)
                elif signal == 'call_state':
                    title = {0: 'Вызов завершён', 1: 'Звонок в дверь', 2: 'Разговор начат'}.get(current[signal], 'Состояние вызова изменено')
                    emit(title, f'{title}.', signal)
                elif signal == 'failed_attempts' and current[signal] > before[signal]:
                    emit('Дверь не открыта', 'Открытие двери отклонено: проверьте вызов и защиту от вскрытия.', signal, 'warning', category='safety')
                elif signal == 'siren' and current.get('leak') == before.get('leak'):
                    emit('Сирена включена' if current[signal] else 'Сирена выключена',
                         'Сирена включена.' if current[signal] else 'Сирена выключена.', signal, category='safety')

            if family == 'oven' and before['preheat'] and not current['preheat'] and current['power'] and not current['alarm'] and current['temperature'] >= current['target_temp']:
                emit('Духовка прогрета', f"Достигнута температура {current['temperature']:g} °C.", 'preheat', 'success', 'device_finished')
            if family == 'thermostat':
                target_key = (current['mode'], current['target_temp'])
                if (before['mode'], before['target_temp']) != target_key:
                    self.completed_targets.pop(key, None)
                if before['output'] and not current['output'] and current['mode'] and not current['fault'] and abs(current['temperature'] - current['target_temp']) <= 0.5 and self.completed_targets.get(key) != target_key:
                    emit('Температура достигнута', f"В комнате {current['temperature']:g} °C, цель {current['target_temp']:g} °C.", 'output', 'success', 'device_finished')
                    self.completed_targets[key] = target_key

            if command and not emitted and not (family == 'kettle' and command[0] == 'power'):
                signal, requested = command
                spec, value = device.signals[signal], current[signal]
                if spec.control == 'button':
                    emit('Команда устройству обработана', f'{spec.title}: запрос обработан.', signal)
                elif value != requested:
                    emit('Изменение не применено', f'{spec.title}: запрошено {display(spec, requested)}, фактически {display(spec, value)}. Проверьте ограничения и защиту.', signal, 'warning')
                elif value != before[signal]:
                    emit('Настройки устройства изменены', f'{spec.title}: {display(spec, value)}.', signal)
            self.previous[key] = copy.deepcopy(current)
