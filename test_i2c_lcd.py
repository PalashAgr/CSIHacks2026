import importlib
import sys
import types


def load_i2c_lcd_module():
    machine_module = types.ModuleType("machine")

    class FakeI2C:
        pass

    machine_module.I2C = FakeI2C
    sys.modules["machine"] = machine_module
    sys.modules.pop("i2c_lcd", None)
    return importlib.import_module("i2c_lcd")


def test_write_clamps_values_to_byte_range():
    lcd_module = load_i2c_lcd_module()

    class FakeI2C:
        def __init__(self):
            self.calls = []

        def writeto(self, addr, data):
            self.calls.append((addr, data))

    fake_i2c = FakeI2C()
    lcd = object.__new__(lcd_module.I2cLcd)
    lcd.i2c = fake_i2c
    lcd.addr = 0x27
    lcd._backlightval = 0x08

    lcd._write(0x100)

    assert fake_i2c.calls[-1][1] == b"\x08"
