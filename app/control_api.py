"""Локальный HTTP control plane, dashboard и статический web frontend."""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse, unquote
try:
    from .device_tests import catalog as test_catalog, run as run_device_tests
    from .emergency_tests import catalog as emergency_catalog, run as run_emergency_tests
    from .ujin_integration import UjinIntegration
    from .home_client import scenario_templates, LocalHomeClient, HomeApiError
    from .api_schema import openapi_schema, api_description, VERSION
except ImportError:  # python app/run.py
    from device_tests import catalog as test_catalog, run as run_device_tests
    from emergency_tests import catalog as emergency_catalog, run as run_emergency_tests
    from ujin_integration import UjinIntegration
    from home_client import scenario_templates, LocalHomeClient, HomeApiError
    from api_schema import openapi_schema, api_description, VERSION

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
    def __init__(self, orchestrator, host="127.0.0.1", port=8787, ujin=None):
        self.orchestrator = orchestrator
        self.ujin = ujin or UjinIntegration(orchestrator)
        self.client = LocalHomeClient(orchestrator, self.ujin)
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
                if size < 0 or size > 1024 * 1024:
                    raise ValueError('Размер JSON-запроса превышает 1 МБ')
                value = json.loads((self.rfile.read(size) or b"{}").decode())
                if not isinstance(value, dict): raise ValueError('Ожидается JSON-объект')
                return value

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
                    "app": "UjinFizteha",
                    "version": VERSION,
                    "device_id": "smart_plug_1",
                    "poll_interval_ms": 1000,
                    "confirmation_ttl_seconds": 60,
                    "modes": ["phone", "tv"],
                    "demo": {"overload_load_w": 2400, "default_load_w": 900},
                })

            @staticmethod
            def query_limit(query, default, maximum=1000):
                try:
                    value = int(query.get("limit", [default])[0])
                except (TypeError, ValueError):
                    return default
                return max(1, min(value, maximum))

            def do_GET(self):
                parsed = urlparse(self.path)
                path = unquote(parsed.path)
                query = parse_qs(parsed.query)
                if path in ('/api', '/api/'):
                    return self.send_json(api_description())
                if path == '/api/openapi.json':
                    return self.send_json(openapi_schema())
                if path in ('/api/docs', '/api/docs/'):
                    with open(os.path.join(os.path.dirname(__file__), 'api_docs.html'), 'rb') as source:
                        return self.send_body(source.read(), 'text/html; charset=utf-8')
                if path == '/api/statistics':
                    return self.send_json(owner.client.statistics())
                if (path.startswith('/api/devices/') or path.startswith('/api/scenarios/')) and len(path.split('/')) == 4:
                    key = path.split('/')[3]
                    try:
                        return self.send_json(owner.client.device(key) if path.startswith('/api/devices/') else owner.client.scenario(key))
                    except HomeApiError as exc:
                        return self.send_json({'error': str(exc)}, exc.status or 400)
                if path == "/api/state":
                    return self.send_json(owner.orchestrator.state())
                if path == "/api/devices":
                    return self.send_json(owner.orchestrator.declarations())
                if path == '/api/device-tests':
                    return self.send_json(test_catalog(owner.orchestrator))
                if path == '/api/emergency-tests':
                    return self.send_json(emergency_catalog(owner.orchestrator))
                if path == '/api/integrations/ujin':
                    return self.send_json(owner.ujin.status())
                if path == '/api/scenario-templates':
                    return self.send_json(scenario_templates())
                if path == "/api/events":
                    limit = self.query_limit(query, 50, 200)
                    return self.send_json(owner.orchestrator.events_since(limit))
                if path == "/api/scenarios":
                    return self.send_json(owner.orchestrator.list_scenarios())
                if path == "/api/history":
                    limit = self.query_limit(query, 300, 1000)
                    with owner.orchestrator.lock:
                        return self.send_json(list(owner.orchestrator.history[-limit:]))
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
                return self.do_GET()

            def do_POST(self):
                path = unquote(urlparse(self.path).path)
                try:
                    body = self.read_json()
                    if path == '/api/commands':
                        return self.send_json(owner.client.apply_command(body['device'], body['signal'], body.get('value')))
                    if path.startswith('/api/scenario-templates/') and path.endswith('/apply') and len(path.split('/')) == 5:
                        return self.send_json(owner.client.create_from_template(path.split('/')[3], body.get('name'), body.get('enabled', True)), 201)
                    if path == '/api/integrations/ujin':
                        if not isinstance(body, dict):
                            raise ValueError('Ожидается действие интеграции Ujin')
                        action = body.get('action')
                        if action == 'check':
                            return self.send_json(owner.ujin.start('read', once=True), 202)
                        if action == 'start':
                            return self.send_json(owner.ujin.start(body.get('mode', 'read')), 202)
                        if action == 'stop':
                            return self.send_json(owner.ujin.stop())
                        raise ValueError('Неизвестное действие интеграции Ujin')
                    if path == '/api/emergency-tests':
                        if not isinstance(body, dict):
                            raise ValueError('Ожидается объект с параметрами аварийного теста')
                        return self.send_json(run_emergency_tests(owner.orchestrator, body.get('case')))
                    if path == '/api/device-tests':
                        if not isinstance(body, dict):
                            raise ValueError('Ожидается объект с параметрами проверки')
                        return self.send_json(run_device_tests(owner.orchestrator, body.get('device')))
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
                except HomeApiError as exc:
                    return self.send_json({'error': str(exc)}, exc.status or 400)
                except (KeyError, PermissionError, ValueError, TypeError) as exc:
                    return self.send_json({"error": str(exc)}, 400)
                except Exception as exc:
                    return self.send_json({"error": str(exc)}, 500)

            def log_message(self, fmt, *args):
                return

            def do_PUT(self):
                path = unquote(urlparse(self.path).path)
                if not path.startswith('/api/scenarios/') or len(path.split('/')) != 4:
                    return self.send_json({'error': 'not_found'}, 404)
                try:
                    return self.send_json(owner.client.update_scenario(path.split('/')[3], self.read_json()))
                except HomeApiError as exc:
                    return self.send_json({'error': str(exc)}, exc.status or 400)
                except (KeyError, PermissionError, ValueError, TypeError) as exc:
                    return self.send_json({'error': str(exc)}, 400)

            def do_DELETE(self):
                path = unquote(urlparse(self.path).path)
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
        self.ujin.stop()
        self.httpd.shutdown()
        self.httpd.server_close()
