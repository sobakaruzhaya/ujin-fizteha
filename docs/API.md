# UjinFizteha: REST API и MCP

Веб-интерфейс, Telegram и MCP работают с одним HTTP-сервером и одним состоянием
дома. Изолированные тесты создают отдельные экземпляры эмуляторов.

## Запуск в Windows

```powershell
# Терминал 1: REST API и веб-приложение
./.venv-mcp/Scripts/python.exe -m app.run --local

# Терминал 2: MCP Streamable HTTP, подключённый к этому же дому
./.venv-mcp/Scripts/python.exe -m app.run --mcp-http --api-url http://127.0.0.1:8787
```

- REST API: <http://127.0.0.1:8787/api>
- Интерактивная документация: <http://127.0.0.1:8787/api/docs>
- OpenAPI 3.1: <http://127.0.0.1:8787/api/openapi.json>
- MCP Streamable HTTP: <http://127.0.0.1:8788/mcp>

Документация работает локально, без внешних скриптов и CDN. Она позволяет искать
методы, вводить путь и тело запроса, выполнять запросы и просматривать JSON-ответ.
Схему можно импортировать в Postman, Insomnia или Swagger.

Для установки MCP-зависимостей нужен Python 3.11+:

```powershell
python -m venv .venv-mcp
./.venv-mcp/Scripts/python.exe -m pip install -r requirements-mcp.txt
```

Параметры HTTP MCP: `--mcp-host 127.0.0.1 --mcp-port 8788`.
REST: `--host 127.0.0.1 --port 8787`.

## REST-методы

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/api`, `/api/health`, `/api/config` | Описание, доступность, конфигурация |
| GET | `/api/state` | Все состояния, метаданные, сводка |
| GET | `/api/devices` | Декларации сигналов, режимы и диапазоны |
| GET | `/api/devices/{device}` | Одно устройство: состояние и декларация |
| GET | `/api/statistics` | Потребление, энергия, пик, основные потребители |
| GET | `/api/history?limit=300` | История мощности и CO₂ |
| GET | `/api/events?limit=50` | Журнал, до 200 событий |
| POST | `/api/commands` | Немедленная команда, как в веб-версии |
| POST | `/api/commands/preview` | Команда с подтверждением либо `require_confirmation=false` |
| POST | `/api/commands/{confirmation_id}/confirm` | Выполнение подтверждённой команды |
| GET, POST | `/api/scenarios` | Список / создание сценария |
| GET, PUT, DELETE | `/api/scenarios/{scenario_id}` | Чтение / изменение / удаление |
| POST | `/api/scenarios/{scenario_id}/toggle` | `{"enabled":false}`; `{}` инвертирует состояние |
| GET | `/api/scenario-templates` | Восемь готовых шаблонов |
| POST | `/api/scenario-templates/{template_key}/apply` | Создать сценарий из шаблона |
| POST | `/api/simulations` | Изолированная симуляция, 1–120 секунд |
| GET, POST | `/api/emergency-tests` | Каталог / аварийные тесты |
| GET, POST | `/api/device-tests` | Каталог / диагностика устройств |
| POST | `/api/demo/start` | Эксперимент в общем доме |
| POST | `/api/demo/reset` | Сброс эмуляторов с сохранением сценариев |
| GET, POST | `/api/integrations/ujin` | Состояние / управление интеграцией |

Тела POST/PUT — JSON-объекты. Ошибки имеют форму `{"error":"описание"}`.
При создании сценария возвращается 201; при запуске/проверке Ujin — 202.
Новые методы чтения/обновления по ID возвращают 404 для отсутствующего объекта;
некорректные параметры — 400. Общий максимальный размер JSON-запроса — 1 МиБ.

### Примеры PowerShell

```powershell
# Прочитать устройство
Invoke-RestMethod http://127.0.0.1:8787/api/devices/light_1

# Установить яркость сразу
Invoke-RestMethod http://127.0.0.1:8787/api/commands -Method Post `
  -ContentType application/json `
  -Body '{"device":"light_1","signal":"brightness","value":45}'

# Создать выключенный сценарий из шаблона
Invoke-RestMethod http://127.0.0.1:8787/api/scenario-templates/cinema/apply `
  -Method Post -ContentType application/json -Body '{"enabled":false}'

# Изолированный тест с полной записью показаний
$report = Invoke-RestMethod http://127.0.0.1:8787/api/emergency-tests `
  -Method Post -ContentType application/json -Body '{"case":"socket-overload"}'
$report.results[0].trace
```

Ключи шаблонов: `overload`, `leak`, `fire`, `fresh-air`, `warm-room`, `cool-room`,
`cinema`, `doorbell`. Можно передать `name` и `enabled`. Коллизии названий получают
суффикс `(2)`, `(3)` и т. д.; существующие сценарии не перезаписываются.

Ключи аварийных тестов: `socket-overload`, `network-overload`, `fire`, `gas-leak`,
`water-leak`, `high-co2`, `dry-kettle`, `sensor-fault`. `{}` запускает весь набор.
Диагностика принимает `{"device":"light_1"}` или `{}` для всех устройств.

В аварийном отчёте `trace` содержит реальные отсчёты эмуляторов по шагам;
`timeline[].frame` связывает контрольные этапы с записью, а `visualization`
задаёт основной/дополнительный сигнал и порог графика. Веб-проигрыватель использует
эти же данные. Концентрация газа — % НКПР, CO₂ — ppm.

Эксперименты `overload`, `co2`, `evening`, `comfort`, `leak`, `fire`, `intercom`,
`kitchen` изменяют общий дом. Аварийные тесты и симуляция изолированы.

## MCP

Файл `mcp.http.example.json` содержит конфигурацию HTTP-клиента:

```json
{"mcpServers":{"ujinfizteha":{"type":"http","url":"http://127.0.0.1:8788/mcp"}}}
```

Для клиентов со stdio в `.mcp.json` настроен `power-guardian`. Он использует
`.venv-mcp/Scripts/python.exe` и общий API. Эквивалентный запуск:

```powershell
./.venv-mcp/Scripts/python.exe -m app.run --mcp --api-url http://127.0.0.1:8787
```

Без `--api-url` оба MCP-транспорта по умолчанию используют API на 8787.
`--local` явно выбирает отдельный in-process дом; его `get_health` возвращает
`transport: local`. Управление Ujin доступно через общий HTTP backend.

### 27 инструментов

| Группа | Инструменты |
| --- | --- |
| Дом | `get_home_state`, `list_devices`, `get_device_state`, `get_health` |
| История и энергия | `get_recent_events`, `get_power_history`, `analyze_energy` |
| Сценарии | `list_scenarios`, `get_scenario`, `create_scenario`, `update_scenario`, `toggle_scenario`, `delete_scenario`, `simulate_scenario` |
| Шаблоны | `list_scenario_templates`, `create_scenario_from_template` |
| Управление | `request_device_command`, `confirm_device_command` |
| Тесты | `list_emergency_tests`, `run_emergency_tests`, `list_device_diagnostics`, `run_device_diagnostics` |
| Ujin | `get_ujin_status`, `manage_ujin_integration` |
| Лаборатория | `run_demo`, `reset_home` |
| API | `describe_api` |

В MCP сохранён существующий двухэтапный протокол опасных команд: первый вызов
возвращает `confirmation_id`, второй выполняет команду. Подтверждение одноразовое,
живёт 60 секунд. REST `/api/commands` выполняет команды сразу.

`run_emergency_tests(case_id="socket-overload", include_trace=true)` возвращает
полную запись для графиков. По умолчанию `trace` опущен для компактного ответа;
проверки, контрольные этапы и события возвращаются всегда.

### Ресурсы

`home://state`, `home://events`, `home://scenarios`, `home://devices`,
`home://scenario-templates`, `home://tests/emergency`, `home://tests/devices`,
`home://integrations/ujin`, `home://api`.

Входные данные Ujin и токен Telegram остаются в локальной конфигурации, вне API
и git. Для Ujin используются уже настроенные `UJIN_CREDENTIALS_FILE`,
`UJIN_BINDINGS_FILE` и `UJIN_PANEL_URL`.

### Проверки

```powershell
./.venv-mcp/Scripts/python.exe -m unittest app.tests.test_public_api `
  app.tests.test_mcp_server app.tests.test_mcp_http
```

HTTP-тест выполняет настоящее MCP-подключение к изолированному общему API,
проверяет обнаружение инструментов, команды, шаблоны, ресурсы и запись аварий.
