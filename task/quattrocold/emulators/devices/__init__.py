"""Набор эмуляторов устройств."""
from .leak_sensor import LeakSensor
from .barrier import Barrier
from .thermostat import Thermostat
from .elevator import Elevator
from .leak_hub import LeakHub
from .counter import Counter
from .ventilation import Ventilation
from .fire import FireDetector
from .light import Light
from .smart_plug import SmartPlug
from .temp_sensor import TempSensor
from .smart_tv import SmartTV
from .fridge import Fridge
from .kettle import Kettle
from .stove import Stove
from .oven import Oven
from .intercom import Intercom

REGISTRY = {
    "leak": LeakSensor,
    "barrier": Barrier,
    "thermostat": Thermostat,
    "elevator": Elevator,
    "hub": LeakHub,
    "counter": Counter,
    "ventilation": Ventilation,
    "fire": FireDetector,
    "light": Light,
    "smart_plug": SmartPlug,
    "temp_sensor": TempSensor,
    "smart_tv": SmartTV,
    "fridge": Fridge,
    "kettle": Kettle,
    "stove": Stove,
    "oven": Oven,
    "intercom": Intercom,
}
