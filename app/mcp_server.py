"""MCP stdio server for the Power Guardian smart home.

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

try:
    from .home_client import HttpHomeClient, ensure_client
except ImportError:  # script mode: python app/run.py
    from home_client import HttpHomeClient, ensure_client

INSTRUCTIONS = """\
You are connected to Power Guardian, a smart-home control plane built around a
smart plug with overload protection, lighting, a thermostat and ventilation.

Read state and events before acting. Explain the reason for every action.
Dangerous commands use a two-step flow: call request_device_command, show the
confirmation summary to the user, and only then call confirm_device_command.
Never guess a confirmation id. Prefer simulate_scenario before changing rules.
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


def build_server(client, name="Power Guardian"):
    """Register all tools and resources.  Kept separate from ``run_stdio`` for tests."""
    client = ensure_client(client)
    MCPServer = _load_server_class()
    server = MCPServer(name, instructions=INSTRUCTIONS)

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
        state = client.state()
        if device not in state.get("devices", {}):
            raise ValueError(f"Unknown device: {device}")
        return {
            "id": device,
            "metadata": state.get("metadata", {}).get(device, {}),
            "state": state["devices"][device],
            "declaration": client.declarations().get(device, []),
        }

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
        state = client.state()
        devices = []
        total_power = 0.0
        total_energy = 0.0
        for device_id, values in state.get("devices", {}).items():
            power = float(values.get("power_w", 0) or 0)
            energy = float(values.get("energy_kwh", 0) or 0)
            if "power_w" not in values and "energy_kwh" not in values:
                continue
            total_power += power
            total_energy += energy
            devices.append({
                "id": device_id,
                "name": state.get("metadata", {}).get(device_id, {}).get("name", device_id),
                "power_w": round(power, 2),
                "energy_kwh": round(energy, 6),
            })
        devices.sort(key=lambda item: item["power_w"], reverse=True)
        return {
            "total_power_w": round(total_power, 2),
            "total_energy_kwh": round(total_energy, 6),
            "devices": devices,
            "top_consumer": devices[0] if devices else None,
        }

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
        """Run a lab preset: overload, co2 or evening."""
        if preset not in {"overload", "co2", "evening"}:
            raise ValueError("preset must be overload, co2 or evening")
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
