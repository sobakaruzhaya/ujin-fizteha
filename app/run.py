"""Run the Power Guardian control plane, Telegram bot or MCP server."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from .control_api import ControlServer
    from .home_client import HttpHomeClient, LocalHomeClient
    from .orchestrator import Orchestrator
    from .telegram_bot import TelegramBot
except ImportError:  # script mode: python app/run.py
    from control_api import ControlServer
    from home_client import HttpHomeClient, LocalHomeClient
    from orchestrator import Orchestrator
    from telegram_bot import TelegramBot


def load_dotenv(path=None):
    """Load KEY=VALUE pairs from .env without overriding the real environment."""
    path = Path(path or os.environ.get(
        "POWER_GUARDIAN_ENV", Path(__file__).resolve().parent.parent / ".env"))
    if not path.is_file():
        return {}
    loaded = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


def telegram_api(token, method, payload=None, timeout=20):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(payload or {}).encode("utf-8")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data),
                                    timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8"))
        except ValueError:
            return {"ok": False, "description": f"Telegram HTTP {exc.code}"}
    except (urllib.error.URLError, OSError) as exc:
        return {"ok": False, "description": f"network error: {exc}"}


def telegram_check():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    raw = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "")
    chats = [item.strip() for item in raw.split(",") if item.strip()]
    if not token or not chats:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_CHAT_IDS in .env",
              file=sys.stderr)
        return 2
    me = telegram_api(token, "getMe")
    if not me.get("ok"):
        print(f"Telegram getMe failed: {me.get('description')}", file=sys.stderr)
        return 1
    bot = me["result"]
    print(f"Bot: @{bot.get('username')} ({bot.get('id')})")
    sent = telegram_api(token, "sendMessage", {
        "chat_id": chats[0],
        "text": "✅ Power Guardian подключён. Отправьте /start.",
    })
    if not sent.get("ok"):
        print(f"Telegram sendMessage failed: {sent.get('description')}",
              file=sys.stderr)
        return 1
    print(f"Test message sent to chat {chats[0]}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Power Guardian smart home")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--mcp", action="store_true",
                        help="serve MCP over stdio (local home unless --api-url is set)")
    parser.add_argument("--telegram", action="store_true",
                        help="start the Telegram long-polling bot")
    parser.add_argument("--api-url", default=None,
                        help="connect to a running control plane instead of starting a local home "
                             "(default: $POWER_GUARDIAN_API_URL)")
    parser.add_argument("--local", action="store_true",
                        help="ignore POWER_GUARDIAN_API_URL and use an in-process home")
    parser.add_argument("--telegram-check", action="store_true",
                        help="validate the bot token and send one test message")
    return parser


def main(argv=None):
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.telegram_check:
        return telegram_check()
    api_url = None if args.local else (args.api_url or os.environ.get("POWER_GUARDIAN_API_URL"))
    if api_url and not (args.mcp or args.telegram):
        parser.error("--api-url requires --mcp or --telegram")

    orchestrator = None
    server = None
    bot = None
    try:
        if api_url:
            client = HttpHomeClient(api_url)
        else:
            orchestrator = Orchestrator(
                storage_path=Path(__file__).parent / "data" / "scenarios.json")
            orchestrator.start()
            client = LocalHomeClient(orchestrator)

        if args.telegram:
            bot = TelegramBot(client)
            if bot.enabled:
                bot.start()
            else:
                print("Telegram bot disabled: set TELEGRAM_BOT_TOKEN and "
                      "TELEGRAM_ALLOWED_CHAT_IDS", file=sys.stderr, flush=True)

        if args.mcp:
            try:
                from .mcp_server import run_stdio
            except ImportError:
                from mcp_server import run_stdio
            return run_stdio(client)

        if api_url:
            # Telegram-only remote mode: keep the poller alive.
            while True:
                time.sleep(1)

        server = ControlServer(orchestrator, args.host, args.port)
        server.start()
        print(f"Power Guardian API: http://{args.host}:{server.port}", flush=True)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if bot is not None:
            bot.stop()
        if server is not None:
            server.stop()
        if orchestrator is not None:
            orchestrator.stop()


if __name__ == "__main__":
    sys.exit(main())
