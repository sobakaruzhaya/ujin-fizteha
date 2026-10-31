"""Transport-neutral access to the Power Guardian control plane.

The web UI talks to :class:`app.control_api.ControlServer` over HTTP.  Telegram
and MCP use the same small client interface so they observe exactly the same
home state and obey the same confirmation policy, whether they run in-process
or as separate programs.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class HomeApiError(RuntimeError):
    """Raised when the control plane rejects a request or is unreachable."""

    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


class LocalHomeClient:
    """In-process adapter around :class:`app.orchestrator.Orchestrator`."""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def state(self):
        return self.orchestrator.state()

    def events(self, limit=50):
        return self.orchestrator.events_since(limit)

    def scenarios(self):
        return self.orchestrator.list_scenarios()

    def declarations(self):
        return self.orchestrator.declarations()

    def history(self, limit=300):
        with self.orchestrator.lock:
            return list(self.orchestrator.history[-max(1, int(limit)):])

    def request_command(self, device, signal, value):
        return self.orchestrator.request_command(device, signal, value)

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

    def history(self, limit=300):
        return self._request("GET", f"/api/history?limit={max(1, int(limit))}")

    def request_command(self, device, signal, value):
        return self._request("POST", "/api/commands/preview",
                             {"device": device, "signal": signal, "value": value})

    def confirm_command(self, confirmation_id):
        return self._request("POST", f"/api/commands/{confirmation_id}/confirm")

    def create_scenario(self, scenario):
        return self._request("POST", "/api/scenarios", scenario)

    def toggle_scenario(self, scenario_id, enabled=None):
        payload = {} if enabled is None else {"enabled": enabled}
        return self._request("POST", f"/api/scenarios/{scenario_id}/toggle", payload)

    def delete_scenario(self, scenario_id):
        return self._request("DELETE", f"/api/scenarios/{scenario_id}")

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
        return LocalHomeClient(target.orchestrator)
    if hasattr(target, "state") and hasattr(target, "request_command"):
        return LocalHomeClient(target)
    raise TypeError("expected a HomeClient or an Orchestrator")
