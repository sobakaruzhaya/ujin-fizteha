"""OpenAPI contract for the shared UjinFizteha HTTP control plane."""
from __future__ import annotations

VERSION = '2.1.0'
DEMO_PRESETS = ('overload', 'co2', 'evening', 'comfort', 'leak', 'fire', 'intercom', 'kitchen')


def ref(name):
    return {'$ref': f'#/components/schemas/{name}'}


def openapi_schema():
    schemas = {
        'Error': {'type': 'object', 'required': ['error'], 'properties': {'error': {'type': 'string'}}},
        'Command': {'type': 'object', 'required': ['device', 'signal', 'value'], 'properties': {
            'device': {'type': 'string'}, 'signal': {'type': 'string'}, 'value': {'type': 'number'}}},
        'CommandPreview': {'allOf': [ref('Command'), {'type': 'object', 'properties': {
            'require_confirmation': {'type': 'boolean', 'default': True}}}]},
        'CommandResult': {'type': 'object', 'properties': {
            'status': {'type': 'string', 'enum': ['applied', 'confirmation_required']},
            'confirmation_id': {'type': 'string'}, 'summary': {'type': 'string'}}},
        'Condition': {'type': 'object', 'required': ['device', 'signal', 'operator', 'value'], 'properties': {
            'device': {'type': 'string'}, 'signal': {'type': 'string'},
            'operator': {'type': 'string', 'enum': ['>', '<', '==', '!=', '>=', '<=']}, 'value': {'type': 'number'}}},
        'Scenario': {'type': 'object', 'required': ['name', 'when', 'do'], 'properties': {
            'id': {'type': 'string'}, 'name': {'type': 'string', 'minLength': 1, 'maxLength': 120},
            'enabled': {'type': 'boolean', 'default': True}, 'when': ref('Condition'),
            'do': {'type': 'array', 'minItems': 1, 'items': ref('Command')}}},
        'Reading': {'type': 'object', 'required': ['device', 'signal', 'value'], 'properties': {
            'device': {'type': 'string'}, 'signal': {'type': 'string'}, 'source': {'type': 'string'},
            'title': {'type': 'string'}, 'value': {'type': 'number'}, 'label': {'type': ['string', 'null']},
            'measure': {'type': 'string'}, 'discrete': {'type': 'boolean'}}},
        'TraceFrame': {'type': 'object', 'properties': {
            'seconds': {'type': 'number'}, 'title': {'type': 'string'},
            'event': {'type': ['string', 'null']}, 'checkpoint': {'type': 'boolean'},
            'readings': {'type': 'array', 'items': ref('Reading')}}},
        'TestResult': {'type': 'object', 'properties': {
            'id': {'type': 'string'}, 'device': {'type': 'string'}, 'name': {'type': 'string'},
            'status': {'type': 'string', 'enum': ['passed', 'failed', 'unsupported']},
            'checks': {'type': 'array', 'items': {'type': 'object'}},
            'trace': {'type': 'array', 'description': 'Recorded emulator samples; no interpolated values.', 'items': ref('TraceFrame')},
            'timeline': {'type': 'array', 'items': {'type': 'object'}},
            'visualization': {'type': 'object', 'description': 'Primary/secondary signal identifiers and plot threshold.'},
            'events': {'type': 'array', 'items': {'type': 'object'}},
            'simulated_seconds': {'type': 'number'}, 'duration_ms': {'type': 'number'}}},
        'TestReport': {'type': 'object', 'required': ['id', 'mode', 'results', 'summary'], 'properties': {
            'id': {'type': 'string'}, 'mode': {'const': 'isolated'}, 'finished_at': {'type': 'number'},
            'results': {'type': 'array', 'items': ref('TestResult')},
            'summary': {'type': 'object', 'properties': {k: {'type': 'integer'} for k in ('total', 'passed', 'failed')}}}},
    }
    paths = {}

    def route(path, method, operation, title, tag, response=None, body=None, example=None, status=200, description=None):
        item = {'operationId': operation, 'summary': title, 'tags': [tag], 'responses': {
            str(status): {'description': 'Успешный ответ', 'content': {'application/json': {'schema': response or {'type': 'object'}}}},
            '400': {'description': 'Неверные параметры', 'content': {'application/json': {'schema': ref('Error')}}},
            '404': {'description': 'Объект не найден', 'content': {'application/json': {'schema': ref('Error')}}},
        }}
        if description: item['description'] = description
        if body:
            media = {'schema': body}
            if example is not None: media['example'] = example
            item['requestBody'] = {'required': True, 'content': {'application/json': media}}
        parts = [part[1:-1] for part in path.split('/') if part.startswith('{') and part.endswith('}')]
        if parts: item['parameters'] = [{'name': part, 'in': 'path', 'required': True, 'schema': {'type': 'string'}} for part in parts]
        paths.setdefault(path, {})[method] = item
        return item

    any_object = {'type': 'object'}
    any_array = {'type': 'array', 'items': any_object}
    route('/api', 'get', 'describe_api', 'Описание сервиса и ссылки', 'Сервис')
    route('/api/health', 'get', 'get_health', 'Доступность сервера', 'Сервис')
    route('/api/config', 'get', 'get_config', 'Параметры приложения', 'Сервис')
    route('/api/openapi.json', 'get', 'get_openapi', 'OpenAPI-схема', 'Сервис')
    route('/api/state', 'get', 'get_home_state', 'Состояние всего дома', 'Устройства')
    route('/api/devices', 'get', 'get_device_declarations', 'Декларации сигналов всех устройств', 'Устройства')
    route('/api/devices/{device}', 'get', 'get_device', 'Состояние и сигналы устройства', 'Устройства')
    route('/api/statistics', 'get', 'get_statistics', 'Потребление, энергия и пиковая мощность', 'Статистика')
    for path, operation, title, maximum, default in [
        ('/api/events', 'get_events', 'Журнал событий', 200, 50),
        ('/api/history', 'get_history', 'История мощности и CO₂', 1000, 300),
    ]:
        item = route(path, 'get', operation, title, 'Статистика', any_array)
        item['parameters'] = [{'in': 'query', 'name': 'limit', 'schema': {'type': 'integer', 'minimum': 1, 'maximum': maximum, 'default': default}}]
    command_example = {'device': 'light_1', 'signal': 'brightness', 'value': 45}
    route('/api/commands', 'post', 'apply_command', 'Выполнить команду сразу', 'Управление', ref('CommandResult'), ref('Command'), command_example,
          description='То же немедленное управление, что в веб-версии и Telegram. Допустимые сигналы и диапазоны: GET /api/devices.')
    route('/api/commands/preview', 'post', 'request_command', 'Запросить команду с подтверждением', 'Управление', ref('CommandResult'), ref('CommandPreview'),
          {**command_example, 'require_confirmation': True}, description='Опасные команды возвращают confirmation_id. require_confirmation=false выполняет команду сразу.')
    route('/api/commands/{confirmation_id}/confirm', 'post', 'confirm_command', 'Подтвердить запрошенную команду', 'Управление', ref('CommandResult'), any_object, {},
          description='Подтверждение живёт 60 секунд и используется один раз.')
    scenario_example = {'name': 'Свет при включении ТВ', 'enabled': True,
        'when': {'device': 'tv_1', 'signal': 'power', 'operator': '==', 'value': 1},
        'do': [{'device': 'light_1', 'signal': 'lamp', 'value': 1}]}
    route('/api/scenarios', 'get', 'list_scenarios', 'Все сценарии', 'Сценарии', {'type': 'array', 'items': ref('Scenario')})
    route('/api/scenarios', 'post', 'create_scenario', 'Создать сценарий', 'Сценарии', ref('Scenario'), ref('Scenario'), scenario_example, 201)
    route('/api/scenarios/{scenario_id}', 'get', 'get_scenario', 'Прочитать сценарий', 'Сценарии', ref('Scenario'))
    route('/api/scenarios/{scenario_id}', 'put', 'update_scenario', 'Изменить сценарий', 'Сценарии', ref('Scenario'), ref('Scenario'), scenario_example)
    route('/api/scenarios/{scenario_id}', 'delete', 'delete_scenario', 'Удалить сценарий', 'Сценарии')
    route('/api/scenarios/{scenario_id}/toggle', 'post', 'toggle_scenario', 'Включить или выключить сценарий', 'Сценарии', ref('Scenario'),
          {'type': 'object', 'properties': {'enabled': {'type': 'boolean'}}}, {'enabled': False})
    route('/api/scenario-templates', 'get', 'list_scenario_templates', 'Восемь шаблонов сценариев', 'Сценарии', any_array)
    route('/api/scenario-templates/{template_key}/apply', 'post', 'apply_scenario_template', 'Создать сценарий из шаблона', 'Сценарии', ref('Scenario'),
          {'type': 'object', 'properties': {'name': {'type': 'string'}, 'enabled': {'type': 'boolean', 'default': True}}}, {'enabled': True}, 201)
    route('/api/simulations', 'post', 'simulate_scenario', 'Изолированная симуляция сценария', 'Сценарии', any_object,
          {'type': 'object', 'properties': {'seconds': {'type': 'integer', 'minimum': 1, 'maximum': 120, 'default': 10}, 'scenario': ref('Scenario')}}, {'seconds': 10})
    for path, operation, title, field, example in [
        ('/api/emergency-tests', 'emergency_tests', 'Аварийные тесты с записью показаний', 'case', 'socket-overload'),
        ('/api/device-tests', 'device_tests', 'Диагностика устройств', 'device', 'light_1'),
    ]:
        route(path, 'get', f'list_{operation}', f'Каталог: {title.lower()}', 'Тесты')
        route(path, 'post', f'run_{operation}', title, 'Тесты', ref('TestReport'),
              {'type': 'object', 'properties': {field: {'type': ['string', 'null']}}}, {field: example},
              description='Пустой объект запускает весь набор. Изолированный стенд не изменяет устройства, историю и сохранённые правила дома.')
    route('/api/demo/start', 'post', 'run_demo', 'Запустить лабораторный эксперимент', 'Лаборатория', any_object,
          {'type': 'object', 'properties': {'preset': {'type': 'string', 'enum': list(DEMO_PRESETS), 'default': 'overload'}}}, {'preset': 'overload'},
          description='Изменяет состояния виртуальных устройств общего дома; это не изолированный тест.')
    route('/api/demo/reset', 'post', 'reset_home', 'Сбросить эмуляторы, сохранив сценарии', 'Лаборатория', any_object, any_object, {})
    route('/api/integrations/ujin', 'get', 'get_ujin_status', 'Состояние интеграции Ujin', 'Ujin')
    route('/api/integrations/ujin', 'post', 'manage_ujin', 'Проверить, запустить или остановить обмен', 'Ujin', any_object,
          {'type': 'object', 'required': ['action'], 'properties': {
              'action': {'type': 'string', 'enum': ['check', 'start', 'stop']},
              'mode': {'type': 'string', 'enum': ['read', 'sync'], 'default': 'read'}}}, {'action': 'check'},
          description='check и start возвращают 202, stop — 200. Доступы берутся из локальной конфигурации сервера.')
    paths['/api/integrations/ujin']['post']['responses']['202'] = paths['/api/integrations/ujin']['post']['responses']['200'].copy()
    return {'openapi': '3.1.0', 'info': {'title': 'UjinFizteha API', 'version': VERSION,
        'description': 'Общий дом для веб-интерфейса, Telegram и MCP. Временная шкала тестов содержит реальные отсчёты эмуляторов.'},
        'servers': [{'url': '/'}], 'paths': paths, 'components': {'schemas': schemas}}


def api_description():
    return {'name': 'UjinFizteha', 'version': VERSION, 'links': {
        'docs': '/api/docs', 'openapi': '/api/openapi.json', 'health': '/api/health', 'web': '/web/'},
        'features': ['devices', 'commands', 'scenarios', 'templates', 'statistics', 'emergency-tests',
                     'device-tests', 'test-traces', 'simulation', 'ujin'],
        'mcp': {'transport': ['stdio', 'streamable-http'], 'default_local_url': 'http://127.0.0.1:8788/mcp'}}
