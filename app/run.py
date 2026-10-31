"""Run the Power Guardian control plane, Telegram bot or MCP server."""
from __future__ import annotations

import argparse
import os
import sys
import time
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
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
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
    main()
