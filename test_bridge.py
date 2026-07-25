import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bridge", ROOT / "bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def test_to_plain_python_handles_numpy_scalars_and_arrays():
    import numpy as np

    value = {"scalar": np.int32(7), "array": np.array([1, 2, 3])}
    plain = bridge.to_plain_python(value)

    assert plain["scalar"] == 7
    assert plain["array"] == [1, 2, 3]


def test_snapshot_serializes_state_without_error():
    import numpy as np

    state = bridge.AppState()
    state.update("vision", confidence=np.float32(0.75), bbox=(1, 2, 3, 4))
    snapshot = state.snapshot()

    assert snapshot["vision"]["confidence"] == 0.75
    assert snapshot["vision"]["bbox"] == [1, 2, 3, 4]


def test_save_person_image_writes_file(tmp_path):
    image_bytes = b"fake-image-bytes"
    saved_path = bridge.save_person_image("Alice", image_bytes, root=tmp_path)

    assert saved_path.exists()
    assert saved_path.parent.name == "Alice"
    assert saved_path.read_bytes() == image_bytes


def test_detect_serial_ports_prefers_discovered_ports(monkeypatch):
    class DummyListPorts:
        def __init__(self, ports):
            self._ports = ports

        def comports(self):
            return [type("Port", (), {"device": port})() for port in self._ports]

    monkeypatch.setattr(bridge, "PICO_PORT", "COM4")
    monkeypatch.setattr(bridge, "list_ports", DummyListPorts(["COM5"]))

    ports = bridge.detect_serial_ports()

    assert ports[0] == "COM5"
    assert "COM4" not in ports[:1]


def test_classify_serial_message_ignores_repl_noise():
    assert bridge.classify_serial_message(">>>") == "repl_prompt"
    assert bridge.classify_serial_message("NameError: name 'ALARM_ON' isn't defined") == "repl_error"
    assert bridge.classify_serial_message('{"armed": true}') == "payload"
