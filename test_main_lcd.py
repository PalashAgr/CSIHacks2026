import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class FakePin:
    IN = "IN"
    OUT = "OUT"
    PULL_DOWN = "PULL_DOWN"
    PULL_UP = "PULL_UP"

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def value(self, *args, **kwargs):
        return 0


class FakePWM:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def duty_u16(self, *args, **kwargs):
        return None

    def freq(self, *args, **kwargs):
        return None


class FakeI2C:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def scan(self):
        return []

    def writeto(self, *args, **kwargs):
        return None


class FakeDHT11:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def measure(self):
        return None

    def temperature(self):
        return 0.0

    def humidity(self):
        return 0.0


class FailingLCD:
    def __init__(self):
        self.clear_calls = 0

    def clear(self):
        self.clear_calls += 1
        raise RuntimeError("lcd broken")

    def move_to(self, *args, **kwargs):
        return None

    def putstr(self, *args, **kwargs):
        return None


def load_main_module():
    machine_module = types.ModuleType("machine")
    machine_module.I2C = FakeI2C
    machine_module.Pin = FakePin
    machine_module.PWM = FakePWM
    machine_module.time_pulse_us = lambda *args, **kwargs: 0
    sys.modules["machine"] = machine_module

    dht_module = types.ModuleType("dht")
    dht_module.DHT11 = FakeDHT11
    sys.modules["dht"] = dht_module

    select_module = types.ModuleType("select")
    select_module.poll = lambda: None
    select_module.POLLIN = 0
    sys.modules["select"] = select_module

    sys.modules.pop("main", None)

    spec = importlib.util.spec_from_file_location("main", ROOT / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_update_lcd_disables_itself_after_failure():
    main = load_main_module()
    failing_lcd = FailingLCD()
    main.lcd = failing_lcd
    main.last_lcd = ("", "")

    main.update_lcd("HELLO", "WORLD")
    main.update_lcd("HELLO", "WORLD")

    assert failing_lcd.clear_calls == 1
    assert main.lcd is None
