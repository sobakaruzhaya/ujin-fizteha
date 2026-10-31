import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from devices.fire import FireDetector  # noqa: E402
from devices.fridge import Fridge  # noqa: E402
from devices.intercom import Intercom  # noqa: E402
from devices.kettle import Kettle  # noqa: E402
from devices.leak_hub import LeakHub  # noqa: E402
from devices.leak_sensor import LeakSensor  # noqa: E402
from devices.oven import Oven  # noqa: E402
from devices.smart_tv import SmartTV  # noqa: E402
from devices.stove import Stove  # noqa: E402
from devices.temp_sensor import TempSensor  # noqa: E402


def send(device, name, value):
    """Повторить путь ядра: сначала значение, затем on_command."""
    device.set_value(name, value)
    device.on_command(name, value)
    return device


class TempSensorTest(unittest.TestCase):
    def test_measures_temperature_and_humidity(self):
        sensor = TempSensor(serial="1", start_temp=21.5, start_humidity=50)
        sensor.tick(1)
        self.assertAlmostEqual(sensor.signals["temperature"].value, 21.5, places=1)
        self.assertAlmostEqual(sensor.signals["humidity"].value, 50.0, places=1)

    def test_calibration_is_applied(self):
        sensor = TempSensor(serial="1", start_temp=21.0)
        send(sensor, "calibration", 2)
        sensor.tick(1)
        self.assertAlmostEqual(sensor.signals["temperature"].value, 23.0, places=1)

    def test_battery_drains_and_reports_low(self):
        sensor = TempSensor(serial="1", battery_drain=1.0)
        sensor.set_battery(16)
        sensor.tick(2)
        self.assertEqual(sensor.signals["battery"].value, 14)
        self.assertEqual(sensor.signals["low_battery"].value, 1)

    def test_tamper_and_fault_are_reported(self):
        sensor = TempSensor(serial="1")
        sensor.set_tamper(True)
        sensor.set_fault(True)
        self.assertEqual(sensor.signals["tamper"].value, 1)
        self.assertEqual(sensor.signals["fault"].value, 1)

    def test_target_temperature_is_clamped(self):
        sensor = TempSensor(serial="1")
        send(sensor, "target_temp", 50)
        self.assertEqual(sensor.signals["target_temp"].value, 35)
        send(sensor, "target_temp", -10)
        self.assertEqual(sensor.signals["target_temp"].value, 5)

    def test_report_interval_is_clamped(self):
        sensor = TempSensor(serial="1")
        send(sensor, "report_interval", 5)
        self.assertEqual(sensor.signals["report_interval"].value, 10)
        send(sensor, "report_interval", 99999)
        self.assertEqual(sensor.signals["report_interval"].value, 3600)


class SmartTVTest(unittest.TestCase):
    def test_power_on_consumes_energy(self):
        tv = SmartTV(serial="1")
        send(tv, "power", 1)
        tv.tick(1)
        self.assertGreater(tv.signals["power_w"].value, 0)
        self.assertGreater(tv.signals["energy_kwh"].value, 0)

    def test_volume_clamped_and_mute(self):
        tv = SmartTV(serial="1")
        send(tv, "volume", 150)
        self.assertEqual(tv.signals["volume"].value, 100)
        send(tv, "volume", -5)
        self.assertEqual(tv.signals["volume"].value, 0)
        send(tv, "mute", 1)
        self.assertEqual(tv.signals["mute"].value, 1)

    def test_child_lock_blocks_source_and_app(self):
        tv = SmartTV(serial="1")
        send(tv, "child_lock", 1)
        send(tv, "source", 2)
        send(tv, "app", 2)
        self.assertEqual(tv.signals["source"].value, 0)
        self.assertEqual(tv.signals["app"].value, 0)

    def test_child_lock_limits_volume(self):
        tv = SmartTV(serial="1")
        send(tv, "child_max_volume", 40)
        send(tv, "child_lock", 1)
        send(tv, "volume", 90)
        self.assertEqual(tv.signals["volume"].value, 40)
        send(tv, "child_lock", 0)
        send(tv, "volume", 90)
        self.assertEqual(tv.signals["volume"].value, 90)

    def test_auto_off_turns_tv_off(self):
        tv = SmartTV(serial="1")
        send(tv, "auto_off_seconds", 2)
        send(tv, "power", 1)
        tv.tick(1)
        tv.tick(1)
        self.assertEqual(tv.signals["power"].value, 0)
        self.assertEqual(tv.signals["playback"].value, 0)

    def test_brightness_is_clamped(self):
        tv = SmartTV(serial="1")
        send(tv, "brightness", 0)
        self.assertEqual(tv.signals["brightness"].value, 1)
        send(tv, "brightness", 500)
        self.assertEqual(tv.signals["brightness"].value, 100)

    def test_off_tv_has_no_power(self):
        tv = SmartTV(serial="1")
        tv.tick(1)
        self.assertEqual(tv.signals["power_w"].value, 0.0)


class FridgeTest(unittest.TestCase):
    def test_compressor_cools_the_chamber(self):
        fridge = Fridge(serial="1")
        fridge.set_value("fridge_temp", 8.0)
        fridge.tick(1)
        self.assertEqual(fridge.signals["compressor"].value, 1)
        self.assertLess(fridge.signals["fridge_temp"].value, 8.0)

    def test_long_open_door_raises_alarm(self):
        fridge = Fridge(serial="1")
        fridge.set_door_open(True)
        for _ in range(61):
            fridge.tick(1)
        self.assertEqual(fridge.signals["alarm"].value, 2)

    def test_super_mode_runs_compressor(self):
        fridge = Fridge(serial="1")
        send(fridge, "mode", 2)
        fridge.tick(1)
        self.assertEqual(fridge.signals["compressor"].value, 1)
        self.assertGreater(fridge.signals["power_w"].value, 0)

    def test_child_lock_blocks_mode_change(self):
        fridge = Fridge(serial="1")
        send(fridge, "child_lock", 1)
        send(fridge, "mode", 2)
        self.assertEqual(fridge.signals["mode"].value, 1)

    def test_fault_stops_compressor(self):
        fridge = Fridge(serial="1")
        fridge.set_fault(True)
        fridge.set_value("fridge_temp", 9.0)
        fridge.tick(1)
        self.assertEqual(fridge.signals["compressor"].value, 0)
        self.assertEqual(fridge.signals["power_w"].value, 0.0)

    def test_targets_are_clamped(self):
        fridge = Fridge(serial="1")
        send(fridge, "target_fridge_temp", 20)
        send(fridge, "target_freezer_temp", -50)
        self.assertEqual(fridge.signals["target_fridge_temp"].value, 8)
        self.assertEqual(fridge.signals["target_freezer_temp"].value, -24)


class KettleTest(unittest.TestCase):
    def test_heats_to_target_and_switches_off(self):
        kettle = Kettle(serial="1")
        kettle.set_water_level(80)
        send(kettle, "target_temp", 60)
        send(kettle, "power", 1)
        for _ in range(14):
            kettle.tick(1)
        self.assertEqual(kettle.signals["temperature"].value, 60.0)
        self.assertEqual(kettle.signals["power"].value, 0)
        self.assertEqual(kettle.signals["auto_off"].value, 1)

    def test_dry_boil_blocks_heating(self):
        kettle = Kettle(serial="1")
        kettle.set_water_level(0)
        send(kettle, "power", 1)
        self.assertEqual(kettle.signals["dry_boil"].value, 1)
        self.assertEqual(kettle.signals["power"].value, 0)

    def test_keep_warm_does_not_restart_without_water(self):
        kettle = Kettle(serial="1")
        kettle.set_water_level(0)
        send(kettle, "keep_warm", 1)
        kettle.tick(1)
        self.assertEqual(kettle.signals["power"].value, 0)
        self.assertEqual(kettle.signals["dry_boil"].value, 0)

    def test_keep_warm_restarts_heating(self):
        kettle = Kettle(serial="1")
        kettle.set_water_level(50)
        kettle.set_value("temperature", 70.0)
        send(kettle, "keep_warm", 1)
        kettle.tick(1)
        self.assertEqual(kettle.signals["power"].value, 1)

    def test_mode_sets_target_temperature(self):
        kettle = Kettle(serial="1")
        send(kettle, "mode", 1)
        self.assertEqual(kettle.signals["target_temp"].value, 95.0)
        send(kettle, "mode", 2)
        self.assertEqual(kettle.signals["target_temp"].value, 100.0)

    def test_reset_clears_protection(self):
        kettle = Kettle(serial="1")
        kettle.set_value("dry_boil", 1)
        kettle.set_value("auto_off", 1)
        send(kettle, "reset", 1)
        self.assertEqual(kettle.signals["dry_boil"].value, 0)
        self.assertEqual(kettle.signals["auto_off"].value, 0)


class StoveTest(unittest.TestCase):
    def test_burner_heats_and_uses_power(self):
        stove = Stove(serial="1")
        send(stove, "burner_1", 5)
        stove.tick(1)
        self.assertEqual(stove.signals["burner_1"].value, 5)
        self.assertGreater(stove.signals["power_w"].value, 0)
        self.assertGreater(stove.signals["energy_kwh"].value, 0)

    def test_child_lock_blocks_burners(self):
        stove = Stove(serial="1")
        send(stove, "child_lock", 1)
        send(stove, "burner_2", 4)
        self.assertEqual(stove.signals["burner_2"].value, 0)

    def test_timer_turns_burners_off(self):
        stove = Stove(serial="1")
        send(stove, "burner_1", 5)
        send(stove, "timer", 2)
        stove.tick(1)
        stove.tick(1)
        self.assertEqual(stove.signals["timer"].value, 0)
        self.assertEqual(stove.signals["burner_1"].value, 0)

    def test_boil_dry_turns_burners_off(self):
        stove = Stove(serial="1")
        send(stove, "pot_present", 0)
        send(stove, "burner_1", 3)
        stove.tick(1)
        self.assertEqual(stove.signals["boil_dry"].value, 1)
        self.assertEqual(stove.signals["burner_1"].value, 0)

    def test_overheat_turns_everything_off(self):
        stove = Stove(serial="1")
        for index in range(1, 5):
            send(stove, f"burner_{index}", 9)
        stove.tick(1)
        self.assertEqual(stove.signals["overheat"].value, 1)
        self.assertEqual(stove.signals["power_w"].value, 0.0)

    def test_residual_heat_stays_after_switch_off(self):
        stove = Stove(serial="1")
        send(stove, "burner_1", 5)
        stove.tick(1)
        send(stove, "burner_1", 0)
        stove.tick(1)
        self.assertEqual(stove.signals["residual_heat"].value, 1)


class OvenTest(unittest.TestCase):
    def test_heating_and_preheat(self):
        oven = Oven(serial="1")
        send(oven, "power", 1)
        oven.tick(1)
        self.assertGreater(oven.signals["temperature"].value, 25.0)
        self.assertEqual(oven.signals["preheat"].value, 1)
        self.assertGreater(oven.signals["power_w"].value, 0)

    def test_reaches_target_and_preheat_stops(self):
        oven = Oven(serial="1")
        send(oven, "target_temp", 100)
        send(oven, "power", 1)
        for _ in range(20):
            oven.tick(1)
        self.assertEqual(oven.signals["temperature"].value, 100.0)
        self.assertEqual(oven.signals["preheat"].value, 0)

    def test_open_door_raises_alarm(self):
        oven = Oven(serial="1")
        send(oven, "power", 1)
        oven.set_door_open(True)
        oven.tick(1)
        self.assertEqual(oven.signals["alarm"].value, 1)
        self.assertEqual(oven.signals["power_w"].value, 0.0)

    def test_timer_turns_oven_off(self):
        oven = Oven(serial="1")
        send(oven, "power", 1)
        send(oven, "timer", 2)
        oven.tick(1)
        oven.tick(1)
        self.assertEqual(oven.signals["timer"].value, 0)
        self.assertEqual(oven.signals["power"].value, 0)

    def test_child_lock_blocks_power(self):
        oven = Oven(serial="1")
        send(oven, "child_lock", 1)
        send(oven, "power", 1)
        self.assertEqual(oven.signals["power"].value, 0)

    def test_fault_stops_heating(self):
        oven = Oven(serial="1")
        oven.set_fault(True)
        send(oven, "power", 1)
        oven.tick(1)
        self.assertEqual(oven.signals["power_w"].value, 0.0)
        self.assertEqual(oven.signals["preheat"].value, 0)

    def test_overheat_turns_oven_off(self):
        oven = Oven(serial="1")
        send(oven, "target_temp", 250)
        send(oven, "power", 1)
        for _ in range(46):
            oven.tick(1)
        self.assertEqual(oven.signals["temperature"].value, 250.0)
        send(oven, "target_temp", 50)
        oven.tick(1)
        self.assertEqual(oven.signals["alarm"].value, 2)
        self.assertEqual(oven.signals["power"].value, 0)


class IntercomTest(unittest.TestCase):
    def test_ring_and_answer(self):
        intercom = Intercom(serial="1")
        intercom.ring()
        self.assertEqual(intercom.signals["call_state"].value, 1)
        self.assertEqual(intercom.signals["last_call"].value, 1)
        send(intercom, "answer", 1)
        self.assertEqual(intercom.signals["call_state"].value, 2)
        self.assertEqual(intercom.signals["answer"].value, 0)

    def test_unlock_requires_active_call(self):
        intercom = Intercom(serial="1")
        send(intercom, "unlock", 1)
        self.assertEqual(intercom.signals["door_open"].value, 0)
        self.assertEqual(intercom.signals["failed_attempts"].value, 1)
        intercom.ring()
        send(intercom, "unlock", 1)
        self.assertEqual(intercom.signals["door_open"].value, 1)

    def test_hangup_ends_call(self):
        intercom = Intercom(serial="1")
        intercom.ring()
        send(intercom, "answer", 1)
        send(intercom, "hangup", 1)
        self.assertEqual(intercom.signals["call_state"].value, 0)
        self.assertEqual(intercom.signals["hangup"].value, 0)

    def test_auto_hangup(self):
        intercom = Intercom(serial="1")
        send(intercom, "auto_hangup_seconds", 5)
        intercom.ring()
        intercom.tick(5)
        self.assertEqual(intercom.signals["call_state"].value, 0)

    def test_tamper_blocks_unlock(self):
        intercom = Intercom(serial="1")
        intercom.ring()
        intercom.set_tamper(True)
        send(intercom, "unlock", 1)
        self.assertEqual(intercom.signals["door_open"].value, 0)
        self.assertEqual(intercom.signals["failed_attempts"].value, 1)

    def test_door_closes_after_unlock(self):
        intercom = Intercom(serial="1")
        intercom.ring()
        send(intercom, "unlock", 1)
        intercom.tick(3)
        self.assertEqual(intercom.signals["door_open"].value, 0)


class FireSafetyTest(unittest.TestCase):
    def test_battery_drains_and_low_battery(self):
        fire = FireDetector(serial="1", battery_drain=1.0)
        fire.set_battery(16)
        fire.tick(2)
        self.assertEqual(fire.signals["battery"].value, 14)
        self.assertEqual(fire.signals["low_battery"].value, 1)

    def test_tamper_triggers_alarm(self):
        fire = FireDetector(serial="1")
        fire.set_tamper(True)
        fire.tick(1)
        self.assertEqual(fire.signals["alarm"].value, 1)
        self.assertEqual(fire.signals["duty"].value, 0)

    def test_alarm_is_latched_until_reset(self):
        fire = FireDetector(serial="1", threshold=50)
        fire.set_smoke(80)
        fire.tick(1)
        fire.set_smoke(0)
        fire.tick(1)
        self.assertEqual(fire.signals["alarm"].value, 1)
        send(fire, "reset_alarm", 1)
        fire.tick(1)
        self.assertEqual(fire.signals["alarm"].value, 0)

    def test_threshold_is_clamped(self):
        fire = FireDetector(serial="1")
        send(fire, "threshold", 1)
        self.assertEqual(fire.signals["threshold"].value, 10)
        send(fire, "threshold", 500)
        self.assertEqual(fire.signals["threshold"].value, 95)

    def test_fault_triggers_alarm(self):
        fire = FireDetector(serial="1")
        fire.set_fault(True)
        fire.tick(1)
        self.assertEqual(fire.signals["alarm"].value, 1)


class LeakSafetyTest(unittest.TestCase):
    def test_low_battery_and_last_seen(self):
        sensor = LeakSensor(serial="1", battery_drain=1.0)
        sensor.set_battery(16)
        sensor.step(1)
        sensor.step(1)
        self.assertEqual(sensor.signals["battery"].value, 14)
        self.assertEqual(sensor.signals["low_battery"].value, 1)
        self.assertEqual(sensor.signals["last_seen"].value, 2)

    def test_tamper_is_reported(self):
        sensor = LeakSensor(serial="1")
        sensor.set_tamper(True)
        sensor.tick(1)
        self.assertEqual(sensor.signals["tamper"].value, 1)


class LeakHubSafetyTest(unittest.TestCase):
    def test_low_battery_is_aggregated(self):
        hub = LeakHub(serial="1")
        hub.sensor(2).battery = 10
        hub.tick(1)
        self.assertEqual(hub.signals["battery"].value, 10)
        self.assertEqual(hub.signals["low_battery"].value, 1)


if __name__ == "__main__":
    unittest.main()
