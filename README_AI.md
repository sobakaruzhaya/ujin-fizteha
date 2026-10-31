# Power Guardian: web, MCP и Telegram

## Запуск локального control plane

Из корня репозитория:

```bash
python app/run.py
```

Для доступа с телефона или телевизора по локальной сети:

```bash
python app/run.py --host 0.0.0.0 --port 8787
```

Проверка состояния и служебных endpoint:

```bash
curl http://127.0.0.1:8787/api/health
curl http://127.0.0.1:8787/api/config
curl http://127.0.0.1:8787/api/state
curl http://127.0.0.1:8787/api/scenarios
```

Запуск демо перегрузки:

```bash
curl -X POST http://127.0.0.1:8787/api/demo/start
```

## Web frontend

Frontend находится в `app/web/` и раздаётся тем же `app/run.py`. Отдельный frontend-сервер не нужен. Интерфейс использует только HTML, CSS и JavaScript без React/Vue и внешних CDN.

Режимы выбираются URL-параметром:

```text
http://127.0.0.1:8787/web/?mode=phone
http://127.0.0.1:8787/web/?mode=tv
```

- `phone` — портретная раскладка для телефона;
- `tv` — landscape-раскладка с крупными значениями, кнопками, focus-state и навигацией стрелками/Enter.

Оба режима используют один источник состояния: frontend опрашивает `/api/state`, `/api/events` и `/api/scenarios` примерно раз в секунду. Экран показывает состояние соединения, мощность, энергию, лимит, защиту, журнал событий и сценарии.

Кнопки включения, выключения, сброса защиты и изменения лимита используют двухфазный механизм:

```text
POST /api/commands/preview
→ confirmation_id
→ POST /api/commands/<confirmation_id>/confirm
```

Подтверждение действует 60 секунд. После истечения токена frontend просит повторить команду. Кнопки демо (`/api/demo/start` и `/api/demo/reset`) выполняются сразу.

### Доступ с телефона или телевизора

1. Компьютер и устройство должны быть в одной Wi‑Fi-сети.
2. Узнать IP компьютера, например `ip addr` или `hostname -I`.
3. Запустить backend с `--host 0.0.0.0`.
4. Открыть на устройстве:

   ```text
   http://<IP компьютера>:8787/web/?mode=phone
   http://<IP компьютера>:8787/web/?mode=tv
   ```

5. Разрешить входящие подключения к порту `8787` в локальном firewall, если они блокируются.

Android WebView-приложения (Phone APK и TV APK) в этой итерации не реализованы. До их появления те же URL открываются в браузере телефона или телевизора. План Android-обёрток остаётся в `TODO.md`.

## Telegram

Telegram работает через long polling и не требует публичного HTTPS endpoint:

```bash
export TELEGRAM_BOT_TOKEN='...'
export TELEGRAM_ALLOWED_CHAT_IDS='123456789'
python app/run.py --telegram
```

Поддерживаются `/status`, `/events`, `/scenarios`, `/demo` и `/help`. Команды, изменяющие состояние розетки, требуют inline-подтверждения.

## MCP

MCP-адаптер запускается по `stdio` внешним MCP-хостом. Для актуального официального Python SDK нужен отдельный Python 3.11+ environment:

```bash
python3.11 -m venv .venv-mcp
. .venv-mcp/bin/activate
pip install -r requirements-mcp.txt
python app/run.py --mcp
```

MCP предоставляет resources состояния, событий и сценариев, а также tools для чтения, анализа, симуляции и подтверждаемого управления.

## Общая демонстрация

Browser, Telegram и MCP работают через один orchestrator, поэтому изменения состояния синхронны:

```text
Browser phone/tv / Telegram / MCP
                ↓
           Control API
                ↓
           Orchestrator
                ↓
            Smart Plug
```

Сценарий показа:

1. Открыть phone-режим в браузере.
2. Открыть tv-режим во втором окне или на телевизоре.
3. Нажать «Запустить перегрузку».
4. Убедиться, что реле отключилось, а предупреждение появилось во всех каналах.
5. Сбросить защиту или демо и проверить синхронное обновление.

Не передавайте токены через MCP-инструменты. Реальные секреты хранятся только в окружении и не добавляются в git.
