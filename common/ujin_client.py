import os
import httpx
from typing import Dict, Any, List

class UjinSmartHomeClient:
    def __init__(self, api_url: str = None, token: str = None):
        self.api_url = api_url or os.getenv("UJIN_API_URL", "https://api.ujin.tech/v1")
        self.token = token or os.getenv("UJIN_API_TOKEN", "")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    async def get_devices(self) -> List[Dict[str, Any]]:
        """Получение списка всех устройств умного дома."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.api_url}/devices", headers=self.headers)
            response.raise_for_status()
            return response.json().get("devices", [])

    async def set_device_state(self, device_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Изменение состояния конкретного устройства (свет, реле, термостат)."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/devices/{device_id}/state",
                json=state,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
