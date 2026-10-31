import asyncio
from mcp.server.fastmcp import FastMCP
from common.ujin_client import UjinSmartHomeClient

mcp = FastMCP("Ujin Smart Home Manager")
ujin = UjinSmartHomeClient()

@mcp.tool()
async def list_devices() -> str:
    """Получить полный список устройств умного дома и их текущий статус."""
    try:
        devices = await ujin.get_devices()
        result = []
        for dev in devices:
            result.append(f"ID: {dev['id']} | Name: {dev['name']} | Status: {dev.get('status', 'unknown')}")
        return "\n".join(result) if result else "Устройства не найдены."
    except Exception as e:
        return f"Ошибка при получении списка устройств: {str(e)}"

@mcp.tool()
async def control_device(device_id: str, power: bool) -> str:
    """
    Управление питанием устройства (включить/выключить).
    :param device_id: Идентификатор устройства
    :param power: True для включения, False для выключения
    """
    try:
        state = {"power": power}
        res = await ujin.set_device_state(device_id, state)
        action = "включено" if power else "выключено"
        return f"Устройство {device_id} успешно {action}."
    except Exception as e:
        return f"Ошибка управления устройством {device_id}: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
