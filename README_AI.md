# Power Guardian — React, React Bits, Telegram и MCP

## Запуск

Нужны Node.js 22.12+ и Python 3.8+. В корне репозитория:

```bash
npm ci
npm run build
python app/run.py
```

Откройте http://127.0.0.1:8787/web/. Python раздаёт собранный React из
`app/web/dist`, дополнительных серверов в production-режиме не требуется.
Без сборки сервер возвращает сообщение с командой `npm run build`.
Для доступа в доверенной локальной сети добавьте `--host 0.0.0.0`.

Для разработки запустите Python на порту 8787 и отдельно `npm run dev`.
Vite проксирует `/api` к Python. React-исходники находятся в `frontend/src`.
Обновление `frontend/src` требует новой сборки для Python-сервера.

## Новый интерфейс

Чёрный фон, три главных раздела: «Мой дом», «Сценарии», «История».
Четыре эмулятора: умная розетка, свет, термостат и вентиляция.
Настройки открываются по изображению устройства. Переключатели используют
двухэтапное подтверждение команд. Фильтры показывают устройства по комнатам.

Сценарии поддерживают создание, редактирование нескольких действий, удаление,
включение и изолированный прогноз на 30 секунд. Правила сохраняются в
`app/data/scenarios.json`; показания и события хранятся в памяти текущего запуска.

Лаборатория находится под кнопкой настроек в шапке: перегрузка, повышение CO₂,
вечерний режим и сброс состояний. Всё работает на эмуляторах.

После перегрузки откройте розетку: установите `Нагрузка = 900`, примените,
сбросьте защиту, затем включите розетку. Защита не сбросится, пока нагрузка
превышает лимит. При необходимости можно сбросить все эмуляторы в лаборатории.

Для телевизора: `/web/?mode=tv`. Поддерживается навигация стрелками и Enter.
APK-обёртки пока не созданы. Авторизация для публичного сервера пока не реализована.

## React Bits и MCP реестра компонентов

В проект добавлены настоящие исходники CountUp, Dither, DarkVeil и SpotlightCard
из официального реестра React Bits. Числа анимирует CountUp; атмосферные canvas-слои
используют Dither и DarkVeil; карточки подсвечивает SpotlightCard.
При `prefers-reduced-motion` фоновые эффекты отключены, числа статичны.
Фото устройств находятся в `frontend/public/images/`, описание генерации — рядом.

Реестр `@react-bits` прописан в `components.json`. MCP-сервер shadcn настроен в
`.mcp.json` для совместимых клиентов и локально в Codex:

```bash
codex mcp add shadcn -- npx -y shadcn@latest mcp
npm run mcp:check
```

После изменения настроек перезапустите Codex, чтобы инструменты загрузились
в новую сессию. `mcp:check` независимо выполняет настоящий stdio handshake,
запрашивает список инструментов и ищет CountUp в React Bits.

Инструкции: https://reactbits.dev/get-started/mcp и https://ui.shadcn.com/docs/mcp.
Лицензия компонентов приложена в `frontend/src/components/reactbits/LICENSE.md`.
Для совместимости сборки используется WASM-версия Rollup, зафиксированная в lockfile.

## Telegram

Бот работает через long polling и общий control plane, поэтому видит те же
устройства, сценарии и события, что web UI. `app/run.py` автоматически читает
`.env` из корня репозитория (реальные переменные окружения имеют приоритет).
Создайте файл и укажите токен с разрешёнными chat id:

```bash
cp .env.example .env
# TELEGRAM_BOT_TOKEN=...
# TELEGRAM_ALLOWED_CHAT_IDS=123456789
chmod 600 .env
python app/run.py --telegram-check   # getMe + тестовое сообщение
python app/run.py --telegram         # backend + бот
```

Или отдельным процессом против уже запущенного backend:

```bash
python app/run.py --telegram --api-url http://127.0.0.1:8787
```

Команды:

- `/status` — состояние всех устройств;
- `/devices` — карточки и inline-управление;
- `/device <id>` — подробные сигналы устройства;
- `/events [n]` — журнал событий;
- `/scenarios` — сценарии с кнопками включения/выключения;
- `/scenario_on <id>` / `/scenario_off <id>` — управление сценарием;
- `/demo [overload|co2|evening]` — лабораторный сценарий;
- `/reset` — сброс эмуляторов;
- `/health` — доступность control plane.

Команды устройств всегда проходят двухфазно: бот сначала показывает summary и
кнопку «Подтвердить», затем вызывает `confirm`. Уведомления об авариях и
срабатываниях сценариев отправляются только в разрешённые чаты. Реальные токены
не добавляйте в git: `.env` исключён `.gitignore`, `.env.example` — только шаблон.

## MCP умного дома

MCP-сервер предоставляет AI-агентам состояние дома, историю, анализ энергии,
сценарии, изолированную симуляцию и подтверждаемое управление. Требуется
Python 3.10+ и зависимости из `requirements-mcp.txt`:

```bash
pip install -r requirements-mcp.txt
```

Рекомендуемый режим — подключение к уже запущенному control plane, чтобы агент
управлял тем же домом, что web UI и Telegram:

```bash
python app/run.py                                   # backend
POWER_GUARDIAN_API_URL=http://127.0.0.1:8787 \
  python app/run.py --mcp                           # MCP over stdio
```

В `.mcp.json` уже добавлен сервер `power-guardian` с этим адресом; MCP-клиент
должен использовать Python, в котором установлен `mcp`. Если backend не запущен,
используйте автономный in-process дом:

```bash
python app/run.py --mcp --local
```

Автономный режим создаёт отдельное состояние и не видит live-события backend —
это явно указано в выводе инструмента `get_health` (`transport: local`).

Инструменты: `get_home_state`, `list_devices`, `get_device_state`,
`get_recent_events`, `get_power_history`, `analyze_energy`, `list_scenarios`,
`create_scenario`, `toggle_scenario`, `delete_scenario`, `simulate_scenario`,
`request_device_command`, `confirm_device_command`, `run_demo`, `reset_home`,
`get_health`. Ресурсы: `home://state`, `home://events`, `home://scenarios`,
`home://devices`.

Опасные команды не выполняются одним вызовом: `request_device_command`
возвращает `confirmation_id`, после чего агент обязан вызвать
`confirm_device_command`. Токен живёт 60 секунд. Для stdio-режима используйте
только stderr для диагностики, чтобы не повредить протокол.

## Проверки

```bash
npm run build
python -m unittest app.tests.test_power_guardian
python -m unittest app.tests.test_home_client app.tests.test_telegram_bot app.tests.test_mcp_server
python -m unittest discover -s task/quattrocold/emulators/tests
npx playwright install chromium
npm run test:e2e
```

Браузерный тест поднимает отдельный runtime без файлового хранилища. Проверяет
изображения, управление, перегрузку и восстановление розетки, создание/симуляцию
правила, комнаты, мобильную компоновку и TV-навигацию.
