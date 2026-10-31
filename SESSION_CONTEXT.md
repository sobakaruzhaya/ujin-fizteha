# Контекст сессии Power Guardian

Этот файл — handoff для продолжения работы над проектом на другом устройстве или в новой сессии ChatGPT/Codex.

## Последнее обновление: домашние эмуляторы и мультиустройственный UI

В ветке `emulators` добавлены рабочие эмуляторы умного телевизора, датчика
температуры/влажности, холодильника, чайника, плиты, духовки и домофона.
Пожарный датчик и датчики протечки получили низкий заряд, `last_seen`, тампер и
сброс тревоги. `Orchestrator` теперь держит 15 домашних устройств, отдаёт их в
`/api/state` и `/api/devices`, маршрутизирует команды по `device_id` и умеет
показывать новые устройства в web UI. В лабораторию добавлены пресеты
«тепло по датчику», «протечка», «пожар», «звонок в дверь» и «кухня».
Проверки: 110 офлайн-тестов эмуляторов, 23 теста Power Guardian, `py_compile`,
dry-run всех семейств и `npm run build`. Live-прогоны на стенде в этой сессии
не выполнялись: нужны сеть и доступы из `task/quattrocold/доступы.json`.

## Предыдущая переделка: центр умного дома

Состояние на конец сессии: React-сборка работает через Python `/web/`; MCP
shadcn зарегистрирован в локальном Codex и `.mcp.json`, проверен поиском
CountUp. Прошли сборка, 75 Python-тестов и браузерный тест управления,
сценариев, восстановления после перегрузки, мобильного и TV-режимов.
Файлы доступа, зависимости, локальные сценарии и сборка исключены из Git.
На другом устройстве выполните `npm ci && npm run build`, затем `python app/run.py`.
Для активации нового MCP-сервера перезапустите Codex. Подробности в `README_AI.md`.

Актуальная версия frontend теперь на React + Vite, в `frontend/src`. Старые
vanilla-файлы `app/web/index.html`, `style.css`, `app.js` удалены. Собирайте
`npm ci && npm run build`: Python раздаёт `app/web/dist` на `/web/`.
По последнему запросу пользователя фон чёрный, главный экран упрощён до карточек
сгенерированных фото устройств; используются React Bits CountUp, Dither,
DarkVeil, SpotlightCard. Основные вкладки — дом, сценарии, история. Эксперименты
и сброс находятся в настройках. Сценарии и backend сохранены.

React Bits registry подключён через shadcn MCP: `components.json`, `.mcp.json`,
локальный `codex mcp add shadcn`. Handshake и поиск проверяются `npm run mcp:check`.
Для загрузки MCP-инструментов в Codex нужен перезапуск клиента.
Изображения находятся в `frontend/public/images`, сгенерированы встроенным image_gen.
Браузерные тесты — `npm run test:e2e`. Актуальные команды — в `README_AI.md`.

По запросу пользователя веб-приложение переработано в центр умного дома с
устройствами и сценариями. Светлый интерфейс содержит обзор, устройства,
сценарии, события, лабораторию и подключения. Backend объединяет Smart Plug,
Light, Thermostat и Ventilation. Добавлены межустройственные правила,
валидация команд, CRUD сценариев, сохранение правил в `app/data/scenarios.json`,
график мощности, лабораторные пресеты и изолированная симуляция.

В последней визуальной итерации применён skill `frontend-design` из
`https://github.com/anthropics/skills` через `npx skills use`. Центральный элемент
обзора — интерактивная схема квартиры с живыми показаниями. Полный браузерный
прогон проверяет команды, создание/предпросмотр правил, перегрузку, phone и TV.

Разделы ниже описывают историю проекта; актуальная инструкция — `README_AI.md`.
APK ещё нет. MCP по-прежнему запускает отдельный runtime; это явно указано
в интерфейсе подключений.

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
