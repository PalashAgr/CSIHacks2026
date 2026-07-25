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
