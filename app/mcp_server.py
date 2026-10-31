"""MCP stdio and Streamable HTTP server for the UjinFizteha smart home.

The server exposes read tools, scenario management, isolated simulation and a
two-step command flow.  Dangerous device commands are never executed by a
single tool call: :func:`request_device_command` returns a confirmation id and
the agent must call :func:`confirm_device_command` separately.

By default the MCP process connects to an already running control plane over
HTTP (see ``POWER_GUARDIAN_API_URL``), so AI agents see the same live home as
the web UI and Telegram.  ``--local`` runs an isolated in-process home instead.
"""
from __future__ import annotations

import json
from typing import Literal

try:
    from .home_client import HttpHomeClient, ensure_client
    from .api_schema import api_description, openapi_schema, DEMO_PRESETS, VERSION
except ImportError:  # script mode: python app/run.py
    from home_client import HttpHomeClient, ensure_client
    from api_schema import api_description, openapi_schema, DEMO_PRESETS, VERSION

INSTRUCTIONS = """\
You are connected to UjinFizteha, a smart-home control plane with lighting,
climate control, safety sensors, energy metering, household appliances and an intercom.

Read state and events before acting. Explain the reason for every action.
Dangerous commands use a two-step flow: call request_device_command, show the
confirmation summary to the user, and only then call confirm_device_command.
Never guess a confirmation id. Prefer simulate_scenario before changing rules.
Emergency tests and device diagnostics run on isolated emulator instances; they
do not inject faults into the live home. An emergency report includes checkpoints
and can include the full recorded trace for visualizations. run_demo and reset_home
DO change the shared home. Use the template catalog rather than inventing signal IDs.
Ujin credentials are configured on the server and must never be requested as tool input.
"""


def _json(value):
    return json.dumps(value, ensure_ascii=False)


def _load_server_class():
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP as MCPServer
        except ImportError as exc:
            raise ImportError(
                "MCP adapter requires the 'mcp' package: pip install -r requirements-mcp.txt"
            ) from exc
    return MCPServer


def build_server(client, name="UjinFizteha"):
    """Register all tools and resources.  Kept separate from ``run_stdio`` for tests."""
    client = ensure_client(client)
    MCPServer = _load_server_class()
    server = MCPServer(name, instructions=INSTRUCTIONS, version=VERSION)

    # ------------------------------------------------------------- resources
    @server.resource("home://state")
    def home_state_resource() -> str:
        """Current state of every device in the home."""
        return _json(client.state())

    @server.resource("home://events")
    def home_events_resource() -> str:
        """Recent events from the shared event journal."""
        return _json(client.events(50))

    @server.resource("home://scenarios")
    def home_scenarios_resource() -> str:
        """Configured if-then automation scenarios."""
        return _json(client.scenarios())

    @server.resource("home://devices")
    def home_devices_resource() -> str:
        """Ujin signal declarations for all devices."""
        return _json(client.declarations())

    @server.resource('home://scenario-templates')
    def home_templates_resource() -> str:
        """Eight canonical automation templates shared with web and Telegram."""
        return _json(client.templates())

    @server.resource('home://tests/emergency')
    def emergency_tests_resource() -> str:
        """Available isolated fault-injection tests and their expected reactions."""
        return _json(client.test_catalog())

    @server.resource('home://tests/devices')
    def device_tests_resource() -> str:
        """Diagnostic capabilities of all emulator devices."""
        return _json(client.test_catalog(False))

    @server.resource('home://integrations/ujin')
    def ujin_resource() -> str:
        """Ujin integration state; no credentials are returned."""
        return _json(client.ujin_status())

    @server.resource('home://api')
    def api_schema_resource() -> str:
        """OpenAPI schema for the shared REST API."""
        return _json(openapi_schema())

    # ----------------------------------------------------------------- tools
    @server.tool()
    def get_home_state() -> dict:
        """Read current state, metadata and summary for every smart-home device."""
        return client.state()

    @server.tool()
    def list_devices() -> list:
        """List devices with their room, current state and Ujin declarations."""
        state = client.state()
        declarations = client.declarations()
        metadata = state.get("metadata", {})
        result = []
        for device_id, values in state.get("devices", {}).items():
            meta = metadata.get(device_id, {})
            result.append({
                "id": device_id,
                "name": meta.get("name", device_id),
                "room": meta.get("room", ""),
                "family": meta.get("family", ""),
                "state": values,
                "declaration": declarations.get(device_id, []),
            })
        return result

    @server.tool()
    def get_device_state(device: str) -> dict:
        """Read the current state of one device by id (for example smart_plug_1)."""
        return client.device(device)

    @server.tool()
    def get_recent_events(limit: int = 20) -> list:
        """Read recent events from the shared journal (newest last)."""
        return client.events(limit)

    @server.tool()
    def get_power_history(limit: int = 60) -> list:
        """Read recent power and CO2 samples collected by the orchestrator."""
        return client.history(limit)

    @server.tool()
    def analyze_energy() -> dict:
        """Summarize current consumption and lifetime energy per device."""
        return client.statistics()

    @server.tool()
    def list_scenarios() -> list:
        """List automation scenarios with their enabled state and rules."""
        return client.scenarios()

    @server.tool()
    def create_scenario(scenario: dict) -> dict:
        """Create or replace an if-then scenario.

        Expected shape: {"name": str, "enabled": bool, "when": {"device",
        "signal", "operator", "value"}, "do": [{"device", "signal", "value"}]}.
        """
        return client.create_scenario(scenario)

    @server.tool()
    def get_scenario(scenario_id: str) -> dict:
        """Read a saved automation scenario by id."""
        return client.scenario(scenario_id)

    @server.tool()
    def update_scenario(scenario_id: str, scenario: dict) -> dict:
        """Replace an existing scenario's name, condition, actions and enabled state."""
        return client.update_scenario(scenario_id, scenario)

    @server.tool()
    def list_scenario_templates() -> list:
        """List the eight templates, their signal IDs and actions. Does not save anything."""
        return client.templates()

    @server.tool()
    def create_scenario_from_template(template_key: str, name: str | None = None, enabled: bool = True) -> dict:
        """Save a new scenario from a catalog template. Existing names receive a unique suffix."""
        return client.create_from_template(template_key, name, enabled)

    @server.tool()
    def list_emergency_tests() -> dict:
        """List overload, fire, gas, water, CO2, dry-kettle and sensor-fault tests."""
        return client.test_catalog()

    @server.tool()
    def run_emergency_tests(case_id: str | None = None, include_trace: bool = False) -> dict:
        """Run one fault-injection test or all eight on an ISOLATED stand.

        Return observed sensor reactions, checks, checkpoints and rule events.
        include_trace=true includes every recorded reading for plots/playback.
        These tests never change devices, timers, events or scenarios in the live home.
        """
        report = client.run_tests(case_id)
        if not include_trace:
            for result in report['results']: result.pop('trace', None)
        return report

    @server.tool()
    def list_device_diagnostics() -> dict:
        """Read the isolated diagnostic catalog for all 15 devices."""
        return client.test_catalog(False)

    @server.tool()
    def run_device_diagnostics(device: str | None = None) -> dict:
        """Run isolated diagnostics for one device or every available emulator."""
        return client.run_tests(device, False)

    @server.tool()
    def get_ujin_status() -> dict:
        """Read Ujin connectivity, mapped devices and exchange counters; no secrets."""
        return client.ujin_status()

    @server.tool()
    def manage_ujin_integration(action: Literal['check', 'start', 'stop'], mode: Literal['read', 'sync'] = 'read') -> dict:
        """Check connectivity, start read/sync exchange, or stop the Ujin integration.

        sync publishes readings and consumes cloud commands. Credentials stay on the server.
        """
        return client.ujin_action(action, mode)

    @server.tool()
    def describe_api() -> dict:
        """Discover REST API documentation, schema and service capabilities."""
        result = api_description()
        if isinstance(client, HttpHomeClient): result['base_url'] = client.base_url
        return result

    @server.tool()
    def toggle_scenario(scenario_id: str, enabled: bool | None = None) -> dict:
        """Enable or disable a scenario; omit enabled to flip it."""
        return client.toggle_scenario(scenario_id, enabled)

    @server.tool()
    def delete_scenario(scenario_id: str) -> dict:
        """Delete a scenario by id."""
        return client.delete_scenario(scenario_id)

    @server.tool()
    def simulate_scenario(seconds: int = 10, scenario: dict | None = None) -> dict:
        """Run an isolated simulation without touching live state, timers or events."""
        return client.simulate(seconds, scenario)

    @server.tool()
    def request_device_command(device: str, signal: str, value: float) -> dict:
        """Request a device command.

        Dangerous commands are not applied: the result contains
        status=confirmation_required and a confirmation_id for the second step.
        """
        return client.request_command(device, signal, value)

    @server.tool()
    def confirm_device_command(confirmation_id: str) -> dict:
        """Confirm a previously requested device command (tokens expire in 60 s)."""
        return client.confirm_command(confirmation_id)

    @server.tool()
    def run_demo(preset: str = "overload") -> dict:
        """Change the LIVE emulator home with a lab preset: overload, co2, evening, comfort, leak, fire, intercom or kitchen."""
        if preset not in DEMO_PRESETS:
            raise ValueError('preset must be one of: ' + ', '.join(DEMO_PRESETS))
        return client.experiment(preset)

    @server.tool()
    def reset_home() -> dict:
        """Reset emulator state while keeping saved scenarios."""
        return client.reset()

    @server.tool()
    def get_health() -> dict:
        """Check that the connected control plane is reachable."""
        result = client.health()
        result = dict(result)
        result["transport"] = "http" if isinstance(client, HttpHomeClient) else "local"
        return result

    return server


def run_stdio(client):
    """Build the server and serve MCP over stdio until the client disconnects."""
    server = build_server(client)
    server.run(transport="stdio")


def run_http(client, host='127.0.0.1', port=8788):
    """Serve the same MCP tools over the official Streamable HTTP transport."""
    server = build_server(client)
    server.run(transport='streamable-http', host=host, port=port,
               streamable_http_path='/mcp', json_response=True, stateless_http=True)
