"""Запуск Power Guardian: dashboard/control API, Telegram или MCP."""
from __future__ import annotations

import argparse
import threading
import time

from control_api import ControlServer
from orchestrator import Orchestrator
from telegram_bot import TelegramBot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--mcp", action="store_true")
    parser.add_argument("--telegram", action="store_true")
    args = parser.parse_args()

    orchestrator = Orchestrator()
    orchestrator.start()
    if args.mcp:
        from mcp_server import run_stdio
        return run_stdio(orchestrator)
    server = ControlServer(orchestrator, args.host, args.port)
    server.start()
    if args.telegram:
        TelegramBot(orchestrator).start()
    print(f"Power Guardian API: http://{args.host}:{server.port}", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        orchestrator.stop()
        server.stop()


if __name__ == "__main__":
    main()

