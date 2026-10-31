"""Локальный HTTP control plane, dashboard и статический web frontend."""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

WEB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "web", "dist"))
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
}


class ControlServer:
    def __init__(self, orchestrator, host="127.0.0.1", port=8787):
        self.orchestrator = orchestrator
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def send_body(self, body, content_type, status=200, extra_headers=None):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                for name, value in (extra_headers or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            def send_json(self, value, status=200):
                body = json.dumps(value, ensure_ascii=False).encode()
                self.send_body(body, "application/json; charset=utf-8", status)

            def send_redirect(self, location):
                self.send_body(b"", "text/plain; charset=utf-8", 302,
                               {"Location": location})

            def read_json(self):
                size = int(self.headers.get("Content-Length", 0))
                return json.loads((self.rfile.read(size) or b"{}").decode())

            @staticmethod
            def web_path(path):
                """Return an absolute path inside app/web or None.

                Path traversal outside the web root is rejected before any
                filesystem access, so URLs cannot read arbitrary files.
                """
                if path in ("/web", "/web/"):
                    relative = "index.html"
                elif path.startswith("/web/"):
                    relative = path[len("/web/"):]
                else:
                    return None
                relative = relative.strip("/")
                if not relative:
                    relative = "index.html"
                candidate = os.path.realpath(os.path.join(WEB_DIR, relative))
                try:
                    if os.path.commonpath([WEB_DIR, candidate]) != WEB_DIR:
                        return None
                except ValueError:
                    return None
                if not os.path.isfile(candidate):
                    return None
                return candidate

            def send_static(self, path):
                if path in ('/web', '/web/') and not os.path.isfile(os.path.join(WEB_DIR, 'index.html')):
                    return self.send_json({'error': 'Frontend not built. Run npm ci && npm run build in the repository root.'}, 503)
                candidate = self.web_path(path)
                if candidate is None:
                    return self.send_json({"error": "not_found"}, 404)
                extension = os.path.splitext(candidate)[1].lower()
                content_type = CONTENT_TYPES.get(extension, "application/octet-stream")
                with open(candidate, "rb") as source:
                    body = source.read()
                return self.send_body(body, content_type, extra_headers={"Cache-Control": "no-store"})

            def send_config(self):
                return self.send_json({
                    "app": "Power Guardian",
                    "version": "1.0.0",
                    "device_id": "smart_plug_1",
                    "poll_interval_ms": 1000,
                    "confirmation_ttl_seconds": 60,
                    "modes": ["phone", "tv"],
                    "demo": {"overload_load_w": 2400, "default_load_w": 900},
                })

            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/api/state":
                    return self.send_json(owner.orchestrator.state())
                if path == "/api/devices":
                    return self.send_json(owner.orchestrator.declarations())
                if path == "/api/events":
                    return self.send_json(owner.orchestrator.events_since())
                if path == "/api/scenarios":
                    return self.send_json(owner.orchestrator.list_scenarios())
                if path == "/api/history":
                    with owner.orchestrator.lock:
                        return self.send_json(list(owner.orchestrator.history))
                if path == "/api/health":
                    return self.send_json({"status": "ok"})
                if path == "/api/config":
                    return self.send_config()
                if path == "/":
                    return self.send_redirect("/web/?mode=phone")
                if path == "/web" or path.startswith("/web/"):
                    return self.send_static(path)
                return self.send_json({"error": "not_found"}, 404)

            def do_HEAD(self):
                path = urlparse(self.path).path
                if path == "/web" or path.startswith("/web/"):
                    return self.send_static(path)
                if path in ("/api/state", "/api/events", "/api/scenarios",
                            "/api/health", "/api/config", "/api/devices"):
                    return self.send_json({})
                return self.send_json({"error": "not_found"}, 404)

            def do_POST(self):
                path = urlparse(self.path).path
                try:
                    body = self.read_json()
                    if path == "/api/scenarios":
                        return self.send_json(owner.orchestrator.create_scenario(body), 201)
                    if path.startswith("/api/scenarios/") and path.endswith("/toggle"):
                        scenario_id = path.split("/")[3]
                        return self.send_json(owner.orchestrator.toggle_scenario(scenario_id, body.get("enabled")))
                    if path == "/api/commands/preview":
                        require_confirmation = body.get("require_confirmation", True)
                        if not isinstance(require_confirmation, bool):
                            raise ValueError("require_confirmation должен быть логическим значением")
                        return self.send_json(owner.orchestrator.request_command(
                            body["device"], body["signal"], body.get("value"), require_confirmation,
                        ))
                    if path.startswith("/api/commands/") and path.endswith("/confirm"):
                        token = path.split("/")[3]
                        return self.send_json(owner.orchestrator.confirm_command(token))
                    if path == "/api/simulations":
                        return self.send_json(owner.orchestrator.simulate(body.get("seconds", 10), body.get("scenario")))
                    if path == "/api/demo/reset":
                        return self.send_json(owner.orchestrator.reset())
                    if path == "/api/demo/start":
                        return self.send_json(owner.orchestrator.experiment(body.get("preset", "overload")))
                    return self.send_json({"error": "not_found"}, 404)
                except (KeyError, PermissionError, ValueError) as exc:
                    return self.send_json({"error": str(exc)}, 400)
                except Exception as exc:
                    return self.send_json({"error": str(exc)}, 500)

            def log_message(self, fmt, *args):
                return

            def do_DELETE(self):
                path = urlparse(self.path).path
                try:
                    if path.startswith('/api/scenarios/') and len(path.split('/')) == 4:
                        return self.send_json(owner.orchestrator.delete_scenario(path.split('/')[3]))
                    return self.send_json({'error': 'not_found'}, 404)
                except ValueError as exc:
                    return self.send_json({'error': str(exc)}, 400)

        self.httpd = ThreadingHTTPServer((host, port), Handler)
        self.port = self.httpd.server_address[1]

    def serve_forever(self):
        self.httpd.serve_forever()

    def start(self):
        import threading
        thread = threading.Thread(target=self.serve_forever, daemon=True)
        thread.start()
        return thread

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
