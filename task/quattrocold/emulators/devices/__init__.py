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
}
