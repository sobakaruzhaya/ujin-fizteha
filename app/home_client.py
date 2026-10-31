"""Transport-neutral access to the Power Guardian control plane.

The web UI talks to :class:`app.control_api.ControlServer` over HTTP.  Telegram
and MCP use the same small client interface so they observe exactly the same
home state, whether they run in-process or as separate programs. Web and
Telegram controls use apply_command for immediate actions. MCP retains the
request/confirm workflow.
"""
from __future__ import annotations

import json
import copy
from pathlib import Path
from urllib.parse import quote
import urllib.error
import urllib.request


class HomeApiError(RuntimeError):
    """Raised when the control plane rejects a request or is unreachable."""

    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


class LocalHomeClient:
    """In-process adapter around :class:`app.orchestrator.Orchestrator`."""

    def __init__(self, orchestrator, ujin=None):
        self.orchestrator = orchestrator
        self.ujin = ujin

    def state(self):
        return self.orchestrator.state()

    def events(self, limit=50):
        return self.orchestrator.events_since(limit)

    def scenarios(self):
        return self.orchestrator.list_scenarios()

    def declarations(self):
        return self.orchestrator.declarations()

    def device(self, device):
        state = self.state()
        if device not in state['devices']:
            raise HomeApiError(f'Устройство не найдено: {device}', 404)
        return {'id': device, 'metadata': state['metadata'].get(device, {}),
                'state': state['devices'][device], 'declaration': self.declarations().get(device, [])}

    def scenario(self, scenario_id):
        item = next((s for s in self.scenarios() if s['id'] == scenario_id), None)
        if item is None: raise HomeApiError(f'Сценарий не найден: {scenario_id}', 404)
        return item

    def update_scenario(self, scenario_id, scenario):
        with self.orchestrator.lock:
            self.scenario(scenario_id)
            return self.create_scenario({**scenario, 'id': scenario_id})

    def create_from_template(self, template_key, name=None, enabled=True):
        if not isinstance(enabled, bool): raise ValueError('enabled должен быть логическим значением')
        template = next((t for t in self.templates() if t['key'] == template_key), None)
        if template is None: raise HomeApiError(f'Шаблон не найден: {template_key}', 404)
        draft = copy.deepcopy(template['scenario'])
        if name is not None:
            if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
                raise ValueError('Название должно содержать от 1 до 120 символов')
            draft['name'] = name.strip()
        draft['enabled'] = enabled
        with self.orchestrator.lock:
            names = {s['name'] for s in self.scenarios()}
            base, suffix = draft['name'], 2
            while draft['name'] in names:
                ending = f' ({suffix})'
                draft['name'] = base[:120-len(ending)] + ending; suffix += 1
            return self.create_scenario(draft)

    def statistics(self):
        with self.orchestrator.lock:
            state, history = self.state(), self.history(300)
        return energy_statistics(state, history)

    def history(self, limit=300):
        with self.orchestrator.lock:
            return list(self.orchestrator.history[-max(1, int(limit)):])

    def request_command(self, device, signal, value):
        return self.orchestrator.request_command(device, signal, value)

    def apply_command(self, device, signal, value):
        return self.orchestrator.request_command(device, signal, value, require_confirmation=False)

    def templates(self):
        return scenario_templates()

    def test_catalog(self, emergency=True):
        try: from . import emergency_tests, device_tests
        except ImportError: import emergency_tests, device_tests
        return (emergency_tests if emergency else device_tests).catalog(self.orchestrator)

    def run_tests(self, case=None, emergency=True):
        try: from . import emergency_tests, device_tests
        except ImportError: import emergency_tests, device_tests
        return (emergency_tests if emergency else device_tests).run(self.orchestrator, case)

    def ujin_status(self):
        if not self.ujin: raise HomeApiError('Ujin доступен через общий сервер управления')
        return self.ujin.status()

    def ujin_action(self, action, mode='read'):
        if not self.ujin: raise HomeApiError('Ujin доступен через общий сервер управления')
        if action not in ('check', 'start', 'stop'): raise ValueError('Неизвестное действие Ujin')
        if mode not in ('read', 'sync'): raise ValueError('Режим должен быть read или sync')
        if action == 'stop': return self.ujin.stop()
        return self.ujin.start('read' if action == 'check' else mode, once=action == 'check')

    def confirm_command(self, confirmation_id):
        return self.orchestrator.confirm_command(confirmation_id)

    def create_scenario(self, scenario):
        return self.orchestrator.create_scenario(scenario)

    def toggle_scenario(self, scenario_id, enabled=None):
        return self.orchestrator.toggle_scenario(scenario_id, enabled)

    def delete_scenario(self, scenario_id):
        return self.orchestrator.delete_scenario(scenario_id)

    def simulate(self, seconds=10, scenario=None):
        return self.orchestrator.simulate(seconds, scenario)

    def experiment(self, preset):
        return self.orchestrator.experiment(preset)

    def reset(self):
        return self.orchestrator.reset()

    def health(self):
        return {"status": "ok"}


class HttpHomeClient:
    """JSON client for a running Power Guardian HTTP control plane."""

    def __init__(self, base_url, timeout=10):
        self.base_url = str(base_url).rstrip("/")
        self.timeout = timeout

    def _request(self, method, path, payload=None):
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=data,
                                         headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                message = json.loads(raw).get("error", raw)
            except (ValueError, AttributeError):
                message = raw or exc.reason
            raise HomeApiError(str(message), status=exc.code) from exc
        except urllib.error.URLError as exc:
            raise HomeApiError(f"control plane unavailable: {exc.reason}", status=0) from exc
        try:
            return json.loads(body or "null")
        except ValueError as exc:
            raise HomeApiError("control plane returned invalid JSON", status=0) from exc

    def state(self):
        return self._request("GET", "/api/state")

    def events(self, limit=50):
        return self._request("GET", f"/api/events?limit={max(1, min(int(limit), 200))}")

    def scenarios(self):
        return self._request("GET", "/api/scenarios")

    def declarations(self):
        return self._request("GET", "/api/devices")

    def device(self, device):
        return self._request('GET', '/api/devices/' + quote(device, safe=''))

    def scenario(self, scenario_id):
        return self._request('GET', '/api/scenarios/' + quote(scenario_id, safe=''))

    def update_scenario(self, scenario_id, scenario):
        return self._request('PUT', '/api/scenarios/' + quote(scenario_id, safe=''), scenario)

    def create_from_template(self, template_key, name=None, enabled=True):
        body = {'enabled': enabled}
        if name is not None: body['name'] = name
        return self._request('POST', '/api/scenario-templates/' + quote(template_key, safe='') + '/apply', body)

    def statistics(self):
        return self._request('GET', '/api/statistics')

    def history(self, limit=300):
        return self._request("GET", f"/api/history?limit={max(1, int(limit))}")

    def request_command(self, device, signal, value):
        return self._request("POST", "/api/commands/preview",
                             {"device": device, "signal": signal, "value": value})

    def apply_command(self, device, signal, value):
        return self._request('POST', '/api/commands/preview',
                             {'device': device, 'signal': signal, 'value': value, 'require_confirmation': False})

    def templates(self):
        return self._request('GET', '/api/scenario-templates')

    def test_catalog(self, emergency=True):
        return self._request('GET', '/api/emergency-tests' if emergency else '/api/device-tests')

    def run_tests(self, case=None, emergency=True):
        return self._request('POST', '/api/emergency-tests' if emergency else '/api/device-tests',
                             {'case' if emergency else 'device': case})

    def ujin_status(self):
        return self._request('GET', '/api/integrations/ujin')

    def ujin_action(self, action, mode='read'):
        return self._request('POST', '/api/integrations/ujin', {'action': action, 'mode': mode})

    def confirm_command(self, confirmation_id):
        return self._request("POST", f"/api/commands/{quote(confirmation_id, safe='')}/confirm")

    def create_scenario(self, scenario):
        return self._request("POST", "/api/scenarios", scenario)

    def toggle_scenario(self, scenario_id, enabled=None):
        payload = {} if enabled is None else {"enabled": enabled}
        return self._request("POST", f"/api/scenarios/{quote(scenario_id, safe='')}/toggle", payload)

    def delete_scenario(self, scenario_id):
        return self._request("DELETE", f"/api/scenarios/{quote(scenario_id, safe='')}")

    def simulate(self, seconds=10, scenario=None):
        return self._request("POST", "/api/simulations",
                             {"seconds": seconds, "scenario": scenario})

    def experiment(self, preset):
        return self._request("POST", "/api/demo/start", {"preset": preset})

    def reset(self):
        return self._request("POST", "/api/demo/reset")

    def health(self):
        return self._request("GET", "/api/health")


def ensure_client(target):
    """Accept a client, an Orchestrator, or an object with an ``orchestrator``."""
    if isinstance(target, (LocalHomeClient, HttpHomeClient)):
        return target
    if hasattr(target, "orchestrator"):
        return LocalHomeClient(target.orchestrator, getattr(target, 'ujin', None))
    if hasattr(target, "state") and hasattr(target, "request_command"):
        return LocalHomeClient(target)
    raise TypeError("expected a HomeClient or an Orchestrator")


def scenario_templates():
    path = Path(__file__).resolve().parent.parent / 'frontend/src/components/scenarioTemplates.json'
    return json.loads(path.read_text(encoding='utf-8'))


def energy_statistics(state, history):
    devices = [{'id': key, 'name': state['metadata'].get(key, {}).get('name', key),
                'power_w': round(float(values.get('power_w', 0) or 0), 2),
                'energy_kwh': round(float(values.get('energy_kwh', 0) or 0), 6)}
               for key, values in state['devices'].items() if 'power_w' in values or 'energy_kwh' in values]
    devices.sort(key=lambda item: item['power_w'], reverse=True)
    return {'total_power_w': round(sum(d['power_w'] for d in devices), 2),
            'total_energy_kwh': round(sum(d['energy_kwh'] for d in devices), 6),
            'active_scenarios': state['summary']['active_scenarios'], 'devices': devices,
            'top_consumer': devices[0] if devices else None,
            'peak_power_w': max((h['power_w'] for h in history), default=state['summary']['power_w']),
            'history_samples': len(history)}
