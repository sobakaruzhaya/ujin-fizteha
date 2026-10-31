# Контекст сессии Power Guardian

Этот файл — handoff для продолжения работы над проектом на другом устройстве или в новой сессии ChatGPT/Codex.

## Как продолжить

1. Открыть репозиторий `ujin-fizteha`.
2. Прочитать этот файл.
3. Затем открыть `TODO.md`.
4. Перед реализацией проверить `git status` и текущую структуру `app/`.
5. Продолжать работу с первого незакрытого пункта TODO.

## Проект

Название: **Power Guardian**.

Идея: умная розетка на базе Ujin OS, которая измеряет потребление, обнаруживает перегрузку или аномалию, автоматически отключает нагрузку и объясняет пользователю причину действия.

Основной demo-flow:

```text
Smart Plug измеряет мощность
→ обнаруживает перегрузку
→ отключает реле
→ создаёт событие
→ показывает объяснение
→ отправляет уведомление
```

## Контекст хакатона

В `task/quattrocold` находится предоставленный пакет хакатона Ujin:

- Python-эмуляторы устройств;
- локальная HTTP-панель;
- Ujin API client;
- HTTP/polling/WebSocket-контракты;
- генератор новых устройств;
- сценарии `если → то`;
- офлайн-тесты.

Исходный пакет рассчитан на Python 3.8+ и по умолчанию работает в dry-run.

## Уже добавлено в репозиторий

### Smart Plug

Файл:

`task/quattrocold/emulators/devices/smart_plug.py`

Сигналы:

- `power_switch` — реле;
- `power_w` — текущая мощность;
- `energy_kwh` — накопленная энергия;
- `voltage` — напряжение;
- `current_a` — ток;
- `load_w` — моделируемая нагрузка;
- `power_limit_w` — лимит мощности;
- `auto_off_seconds` — таймер выключения;
- `overload_alarm` — авария перегрузки;
- `anomaly` — аномалия;
- `reset_protection` — сброс защиты.

Семейство зарегистрировано в `devices.REGISTRY` и запускается так:

```bash
cd task/quattrocold/emulators
python main.py smart_plug --port 8099
```

После превышения лимита розетка отключается и блокирует повторное включение до сброса защиты.

### Control plane

Каталог: `app/`

- `app/orchestrator.py` — единый владелец состояния, сценариев, событий и confirmation flow;
- `app/control_api.py` — локальный HTTP API, статика и раздача web frontend;
- `app/web/` — общий frontend для режимов `phone` и `tv`;
- `app/telegram_bot.py` — Telegram Bot API через long polling;
- `app/mcp_server.py` — MCP stdio adapter;
- `app/run.py` — запуск приложения;
- `app/tests/test_power_guardian.py` — тесты Smart Plug, orchestrator и API.

Запуск:

```bash
python app/run.py
```

API:

```text
http://127.0.0.1:8787/api/state
http://127.0.0.1:8787/api/events
http://127.0.0.1:8787/api/scenarios
http://127.0.0.1:8787/api/health
http://127.0.0.1:8787/api/config
```

Запуск демо перегрузки:

```bash
curl -X POST http://127.0.0.1:8787/api/demo/start
```

### Web frontend

Файлы:

- `app/web/index.html`;
- `app/web/style.css`;
- `app/web/app.js`.

Frontend работает без React/Vue и внешнего CDN, опрашивает `/api/state`, `/api/events`, `/api/scenarios` примерно раз в секунду и показывает состояние соединения. Опасные команды проходят через `/api/commands/preview` и `/api/commands/<id>/confirm`.

URL:

```text
http://127.0.0.1:8787/web/?mode=phone
http://127.0.0.1:8787/web/?mode=tv
```

Для доступа по LAN:

```bash
python app/run.py --host 0.0.0.0 --port 8787
```

### Telegram

Переменные окружения:

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_ALLOWED_CHAT_IDS="123456789"
python app/run.py --telegram
```

Есть команды `/status`, `/events`, `/scenarios`, `/demo`, `/help`, inline-подтверждения команд и уведомления об аварийных событиях.

### MCP

Файл: `app/mcp_server.py`.

Используется официальный Python MCP SDK, запускаемый через `stdio`. Для SDK нужен отдельный Python 3.11+ environment:

```bash
python3.11 -m venv .venv-mcp
. .venv-mcp/bin/activate
pip install -r requirements-mcp.txt
python app/run.py --mcp
```

MCP предоставляет чтение состояния, событий и сценариев, анализ энергии, симуляцию и подтверждаемое управление.

### Документы

- `KILLER_FEATURES.md` — полная концепция Power Guardian, AI, Telegram и web-каналов;
- `README_AI.md` — запуск web/Telegram/MCP и доступ по LAN;
- `TODO.md` — план следующих этапов, включая Android WebView;
- `requirements-mcp.txt` — MCP dependency;
- `.env.example` — шаблон Telegram environment variables.

## Следующая задача

Задачи 1–3 и backend/frontend-часть задачи 6 из `TODO.md` выполнены:

1. Web frontend в `app/web/`.
2. Режимы `phone` и `tv`.
3. Раздача `/web/` из `app/control_api.py`.
4. API `/api/health` и `/api/config`.
5. Управление через preview/confirmation API.
6. Тесты backend и frontend smoke-проверки.

Отложено по решению пользователя:

- Android WebView Phone APK;
- Android TV APK;
- `ANDROID_BUILD.md` и Android-часть демонстрации;
- прошивка физической розетки.

До появления APK режимы `phone` и `tv` открываются в браузере телефона или телевизора:

```text
http://<IP компьютера>:8787/web/?mode=phone
http://<IP компьютера>:8787/web/?mode=tv
```

## Принятые решения

- Главный killer feature — Power Guardian.
- Основной демо-объект — Smart Plug.
- ИИ подключается через MCP для внешних AI-агентов.
- Telegram используется для уведомлений и управления.
- Опасные команды требуют подтверждения.
- Dashboard, Telegram и MCP работают через общий orchestrator.
- WebView APK использует один web frontend для телефона и TV.
- Внешний Ujin-стенд не должен быть обязательным для демо.
- Не прошивать неизвестную физическую Wi‑Fi-розетку без определения модели и протокола.

## Проверки

Последний известный результат:

- 58 существующих тестов эмуляторов проходят;
- 17 тестов Power Guardian проходят, включая статику `/web/`, `/api/health`, `/api/config`, path traversal, двухфазное подтверждение и frontend smoke-проверки;
- Python-файлы компилируются;
- HTTP-тесты запускаются с разрешением на локальные sockets.

После изменений обязательно запускать:

```bash
python -m unittest discover -s tests
```

из `task/quattrocold/emulators`, а также:

```bash
python -m unittest app.tests.test_power_guardian
python -m py_compile app/*.py app/tests/*.py
```

## Важные ограничения

- Не коммитить реальные Telegram/Ujin/MCP токены.
- Не использовать `git reset --hard`.
- Сохранять существующие тесты и dry-run режим.
- Не давать AI прямой доступ к устройствам без control plane.
- Для опасных команд сохранять двухфазное подтверждение.
- Для Android MVP допустим cleartext HTTP только в локальной Wi‑Fi-сети.
