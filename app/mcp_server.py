"""MCP stdio adapter. Требует Python 3.11+ и пакет mcp."""
from __future__ import annotations

import json


def run_stdio(orchestrator):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit("MCP adapter requires: pip install -r requirements-mcp.txt") from exc

    server = FastMCP("Power Guardian")

    @server.resource("home://state")
    def home_state() -> str:
        return json.dumps(orchestrator.state(), ensure_ascii=False)

    @server.resource("home://events")
    def home_events() -> str:
        return json.dumps(orchestrator.events_since(), ensure_ascii=False)

    @server.resource("home://scenarios")
    def home_scenarios() -> str:
        return json.dumps(orchestrator.list_scenarios(), ensure_ascii=False)

    @server.tool()
    def get_home_state() -> dict:
        """Read current state of the smart home."""
        return orchestrator.state()

    @server.tool()
    def get_recent_events(limit: int = 20) -> list:
        """Read recent Power Guardian events."""
        return orchestrator.events_since(limit)

    @server.tool()
    def list_scenarios() -> list:
        """List configured automation scenarios."""
        return orchestrator.list_scenarios()

    @server.tool()
    def analyze_energy() -> dict:
        """Summarize current smart plug energy usage."""
        state = orchestrator.state()["devices"]["smart_plug_1"]
        return {"power_w": state["power_w"], "energy_kwh": state["energy_kwh"],
                "limit_w": state["power_limit_w"], "protected": bool(state["overload_alarm"])}

    @server.tool()
    def simulate_scenario(seconds: int = 10) -> dict:
        """Simulate rules without persisting device state."""
        return orchestrator.simulate(seconds)

    @server.tool()
    def request_device_command(device: str, signal: str, value: float) -> dict:
        """Request a device command. Dangerous commands return a confirmation id."""
        return orchestrator.request_command(device, signal, value)

    @server.tool()
    def confirm_device_command(confirmation_id: str) -> dict:
        """Confirm a previously requested dangerous device command."""
        return orchestrator.confirm_command(confirmation_id)

    @server.tool()
    def toggle_scenario(scenario_id: str, enabled: bool) -> dict:
        """Enable or disable a scenario."""
        return orchestrator.toggle_scenario(scenario_id, enabled)

    server.run(transport="stdio")

