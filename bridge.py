from __future__ import annotations

import json
import mimetypes
import os
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
import time
from urllib.parse import urlparse

import cv2
import numpy as np
import serial


ROOT = Path(__file__).resolve().parent
WEB_DIST = ROOT / "web" / "dist"
PEOPLE_DB = ROOT / "people_db"

HOST = "127.0.0.1"
PORT = int(os.environ.get("BRIDGE_PORT", "8000"))
PICO_PORT = os.environ.get("PICO_PORT", "COM4")
PICO_BAUD = int(os.environ.get("PICO_BAUD", "115200"))

ALARM_UNKNOWN_THRESHOLD = 3
FACE_RECOGNITION_THRESHOLD = 75.0
TARGET_FPS = 15

def find_cascade_path(filename: str):
    candidates = []
    if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
        candidates.append(Path(cv2.data.haarcascades) / filename)

    cv2_root = Path(cv2.__file__).resolve().parent
    candidates.extend(
        [
            cv2_root / "data" / filename,
            cv2_root / filename,
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    for match in cv2_root.rglob(filename):
        return str(match)

    return None


CASCADE_PATH = find_cascade_path("haarcascade_frontalface_default.xml")
try:
    FACE_CASCADE = cv2.CascadeClassifier(CASCADE_PATH) if CASCADE_PATH else None
except Exception:
    FACE_CASCADE = None

try:
    HOG = cv2.HOGDescriptor()
    HOG.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
except Exception:
    HOG = None


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def to_plain_python(value):
    if isinstance(value, dict):
        return {str(k): to_plain_python(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain_python(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [to_plain_python(item) for item in value.tolist()]
    if isinstance(value, Path):
        return str(value)
    return value


def safe_average(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def clamp(value, lower, upper):
    return max(lower, min(upper, value))


def ensure_people_db():
    PEOPLE_DB.mkdir(exist_ok=True)


def save_person_image(person_name, image_bytes, root=None):
    base_root = Path(root) if root is not None else PEOPLE_DB
    base_root.mkdir(exist_ok=True, parents=True)
    person_dir = base_root / person_name.replace("/", "_").strip()
    person_dir.mkdir(exist_ok=True, parents=True)
    target = person_dir / f"{int(time.time() * 1000)}.jpg"
    target.write_bytes(image_bytes)
    return target


def load_database():
    ensure_people_db()
    people = []
    samples = []
    labels = []
    label_names = {}

    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()  # type: ignore[attr-defined]
    except Exception:
        recognizer = None

    label_id = 0
    for person_dir in sorted(PEOPLE_DB.iterdir()):
        if not person_dir.is_dir():
            continue

        person_samples = []
        for image_path in sorted(person_dir.glob("*")):
            if image_path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            image = cv2.imread(str(image_path))
            if image is None or FACE_CASCADE is None:
                continue
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = FACE_CASCADE.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))
            if len(faces) == 0:
                continue
            x, y, w, h = max(faces, key=lambda box: box[2] * box[3])
            face = gray[y : y + h, x : x + w]
            face = cv2.resize(face, (200, 200))
            samples.append(face)
            labels.append(label_id)
            person_samples.append(str(image_path.name))

        if person_samples:
            people.append(
                {
                    "name": person_dir.name,
                    "sample_count": len(person_samples),
                    "sample_files": person_samples,
                    "label_id": label_id,
                }
            )
            label_names[label_id] = person_dir.name
            label_id += 1

    if recognizer is not None and samples:
        recognizer.train(samples, np.array(labels, dtype=np.int32))

    return recognizer, label_names, people


class AppState:
    def __init__(self):
        self.lock = Lock()
        self.data = {
            "server": {"connected": True, "time": utc_now()},
            "pico": {
                "connected": False,
                "armed": False,
                "alarm": False,
                "alarm_reason": "idle",
                "distance_cm": None,
                "temperature_c": None,
                "humidity": None,
                "display_unit": "C",
                "last_seen": None,
            },
            "vision": {
                "connected": False,
                "person_name": "No person",
                "known": False,
                "confidence": None,
                "bbox": None,
                "center": None,
                "tracked": False,
                "unknown_streak": 0,
                "camera_index": 0,
            },
            "environment": {
                "room_temperature_c": None,
                "room_humidity": None,
                "temperature_samples": 0,
            },
            "database": {"count": 0, "people": [], "recognition": False},
            "alarm": {"active": False, "reason": "idle", "source": "none"},
            "frame_version": 0,
            "frame_ts": None,
            "logs": [],
        }
        self.frame_jpeg = None
        self.last_sent_alarm = None
        self.serial = None
        self.last_serial_try = 0.0
        self.temp_window = deque(maxlen=5)
        self.humidity_window = deque(maxlen=5)
        self.recognizer = None
        self.label_names = {}
        self.people = []

    def update(self, section, **kwargs):
        with self.lock:
            self.data[section].update({k: to_plain_python(v) for k, v in kwargs.items()})
            if section != "server":
                self.data["server"]["time"] = utc_now()

    def append_log(self, message, tone="info"):
        entry = {"time": utc_now(), "tone": tone, "message": message}
        with self.lock:
            self.data["logs"] = [entry, *self.data["logs"]][:10]

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(to_plain_python(self.data)))

    def set_frame(self, frame_bytes):
        with self.lock:
            self.frame_jpeg = frame_bytes
            self.data["frame_version"] += 1
            self.data["frame_ts"] = utc_now()

    def get_frame(self):
        with self.lock:
            return self.frame_jpeg

    def connect_serial(self):
        if self.serial is not None:
            return self.serial
        if time.time() - self.last_serial_try < 2:
            return None
        self.last_serial_try = time.time()
        try:
            self.serial = serial.Serial(PICO_PORT, PICO_BAUD, timeout=0.1)
            self.append_log(f"Connected to Pico on {PICO_PORT}", "success")
            self.update("pico", connected=True)
            return self.serial
        except Exception as exc:
            self.update("pico", connected=False)
            self.append_log(f"Pico serial unavailable: {exc}", "warn")
            self.serial = None
            return None

    def write_serial(self, line):
        ser = self.connect_serial()
        if ser is None:
            return
        try:
            ser.write((line.strip() + "\n").encode("utf-8"))
        except Exception as exc:
            self.append_log(f"Serial write failed: {exc}", "warn")
            try:
                ser.close()
            except Exception:
                pass
            self.serial = None
            self.update("pico", connected=False)


STATE = AppState()


def maybe_track_tracker():
    tracker_factory = None
    for name in ("TrackerCSRT_create", "TrackerKCF_create", "TrackerMIL_create"):
        tracker_factory = getattr(cv2, name, None)
        if tracker_factory is not None:
            return tracker_factory
    legacy = getattr(getattr(cv2, "legacy", None), "TrackerCSRT_create", None)
    if legacy is not None:
        return legacy
    legacy = getattr(getattr(cv2, "legacy", None), "TrackerKCF_create", None)
    if legacy is not None:
        return legacy
    legacy = getattr(getattr(cv2, "legacy", None), "TrackerMIL_create", None)
    if legacy is not None:
        return legacy
    return None


TRACKER_FACTORY = maybe_track_tracker()


def train_database():
    recognizer, label_names, people = load_database()
    STATE.recognizer = recognizer
    STATE.label_names = label_names
    STATE.people = people
    STATE.update("database", count=len(people), people=people, recognition=recognizer is not None)


def recognize_face(face_gray):
    if STATE.recognizer is None or not STATE.label_names:
        return None, None
    try:
        label_id, confidence = STATE.recognizer.predict(face_gray)
        name = STATE.label_names.get(label_id)
        return name, float(confidence)
    except Exception:
        return None, None


def detect_person(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = []
    if FACE_CASCADE is not None and not FACE_CASCADE.empty():
        faces = FACE_CASCADE.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))

    if len(faces) == 0 and HOG is not None:
        rects, _ = HOG.detectMultiScale(frame, winStride=(8, 8), padding=(8, 8), scale=1.03)
        faces = rects

    if len(faces) == 0:
        return None, None, None, None

    x, y, w, h = max(faces, key=lambda box: box[2] * box[3])
    crop_gray = gray[y : y + h, x : x + w]
    face_name, face_confidence = None, None
    if crop_gray.size > 0:
        faces_in_crop = []
        if FACE_CASCADE is not None and not FACE_CASCADE.empty():
            faces_in_crop = FACE_CASCADE.detectMultiScale(crop_gray, 1.1, 4, minSize=(40, 40))
        if len(faces_in_crop) > 0:
            fx, fy, fw, fh = max(faces_in_crop, key=lambda box: box[2] * box[3])
            face = crop_gray[fy : fy + fh, fx : fx + fw]
            face = cv2.resize(face, (200, 200))
            face_name, face_confidence = recognize_face(face)
        elif STATE.recognizer is not None:
            face = cv2.resize(crop_gray, (200, 200))
            face_name, face_confidence = recognize_face(face)

    if face_name is None:
        face_name = "Unknown"

    return (x, y, w, h), face_name, face_confidence, crop_gray


def open_tracker(frame, bbox):
    if TRACKER_FACTORY is None:
        return None
    try:
        tracker = TRACKER_FACTORY()
        tracker.init(frame, tuple(bbox))
        return tracker
    except Exception:
        return None


def open_camera(index=0):
    candidate_indexes = [index, 0, 1, 2, 3]
    backends = []
    if hasattr(cv2, "CAP_DSHOW"):
        backends.append((cv2.CAP_DSHOW, "dshow"))
    if hasattr(cv2, "CAP_MSMF"):
        backends.append((cv2.CAP_MSMF, "msmf"))
    backends.append((cv2.CAP_ANY, "any"))

    for backend, backend_name in backends:
        for candidate in candidate_indexes:
            try:
                capture = cv2.VideoCapture(candidate, backend)
            except Exception:
                continue
            if capture is None or not capture.isOpened():
                continue
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            capture.set(cv2.CAP_PROP_FPS, TARGET_FPS)
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ok, frame = capture.read()
            if ok and frame is not None:
                return capture, candidate, backend_name
            capture.release()

    return None, None, None


def camera_loop():
    capture, camera_index, camera_backend = open_camera(int(os.environ.get("CAMERA_INDEX", "0")))
    if capture is None:
        STATE.append_log("Camera unavailable", "warn")
        STATE.update("vision", connected=False, camera_index=None, camera_backend=None)
        return

    STATE.update("vision", connected=True, camera_index=camera_index, camera_backend=camera_backend)
    STATE.append_log(f"OpenCV camera connected on index {camera_index} via {camera_backend}", "success")

    tracker = None
    tracker_bbox = None
    unknown_streak = 0
    last_alarm = False
    frame_index = 0
    last_good_person = "Unknown"
    last_confidence = None

    while True:
        ok, frame = capture.read()
        if not ok or frame is None:
            capture.release()
            capture, camera_index, camera_backend = open_camera(camera_index + 1 if camera_index is not None else 0)
            if capture is None:
                STATE.append_log("Camera stream lost", "warn")
                STATE.update("vision", connected=False, camera_index=None, camera_backend=None)
                time.sleep(0.5)
                continue
            STATE.update("vision", connected=True, camera_index=camera_index, camera_backend=camera_backend)
            continue

        frame_index += 1
        display = frame.copy()

        bbox = None
        person_name = "No person"
        confidence = None
        known = False
        tracked = False

        if tracker is not None:
            ok_track, tracked_box = tracker.update(frame)
            if ok_track:
                x, y, w, h = [int(v) for v in tracked_box]
                bbox = (x, y, w, h)
                tracked = True
            else:
                tracker = None

        if bbox is None:
            bbox, person_name, confidence, _ = detect_person(frame)
            if bbox is not None:
                tracker = open_tracker(frame, bbox)
                tracked = tracker is not None
        else:
            x, y, w, h = bbox
            gray = cv2.cvtColor(frame[y : y + h, x : x + w], cv2.COLOR_BGR2GRAY)
            if gray.size > 0:
                faces = FACE_CASCADE.detectMultiScale(gray, 1.1, 4, minSize=(40, 40)) if FACE_CASCADE is not None and not FACE_CASCADE.empty() else []
                if len(faces) > 0:
                    fx, fy, fw, fh = max(faces, key=lambda box: box[2] * box[3])
                    face = gray[fy : fy + fh, fx : fx + fw]
                    face = cv2.resize(face, (200, 200))
                    person_name, confidence = recognize_face(face)
                elif STATE.recognizer is not None:
                    face = cv2.resize(gray, (200, 200))
                    person_name, confidence = recognize_face(face)
                else:
                    person_name = "Unknown"

        if person_name not in (None, "Unknown", "No person"):
            known = confidence is not None and confidence < FACE_RECOGNITION_THRESHOLD
            if known:
                last_good_person = person_name
                last_confidence = confidence

        if bbox is not None:
            x, y, w, h = bbox
            color = (0, 220, 0) if known else (0, 0, 255)
            cv2.rectangle(display, (x, y), (x + w, y + h), color, 2)
            label = f"{person_name}"
            if confidence is not None:
                label += f" {confidence:.1f}"
            cv2.putText(display, label, (x, max(24, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2)

        if bbox is not None and not known:
            unknown_streak += 1
        elif known or bbox is None:
            unknown_streak = 0

        alarm_active = unknown_streak >= ALARM_UNKNOWN_THRESHOLD
        if alarm_active != last_alarm:
            STATE.write_serial("ALARM_ON" if alarm_active else "ALARM_OFF")
            STATE.append_log(
                "Unknown person detected" if alarm_active else "Known person cleared",
                "danger" if alarm_active else "success",
            )
            last_alarm = alarm_active

        if bbox is not None:
            x, y, w, h = bbox
            center = (int(x + w / 2), int(y + h / 2))
        else:
            center = None

        pico = STATE.snapshot()["pico"]
        temp_c = pico.get("temperature_c")
        humidity = pico.get("humidity")
        if temp_c is not None:
            STATE.temp_window.append(float(temp_c))
        if humidity is not None:
            STATE.humidity_window.append(float(humidity))

        avg_temp = safe_average(list(STATE.temp_window))
        avg_humidity = safe_average(list(STATE.humidity_window))
        if avg_temp is not None or avg_humidity is not None:
            STATE.update(
                "environment",
                room_temperature_c=avg_temp,
                room_humidity=avg_humidity,
                temperature_samples=len(STATE.temp_window),
            )

        STATE.update(
            "vision",
            person_name=last_good_person if known else person_name,
            known=known,
            confidence=confidence,
            bbox=bbox,
            center=center,
            tracked=tracked or bbox is not None,
            unknown_streak=unknown_streak,
        )

        STATE.update(
            "alarm",
            active=alarm_active,
            reason="outside database" if alarm_active else "idle",
            source="opencv"
        )

        STATE.update(
            "pico",
            alarm=alarm_active or bool(pico.get("alarm")),
            alarm_reason="outside database" if alarm_active else pico.get("alarm_reason", "idle"),
            last_seen=utc_now(),
        )

        if bbox is not None:
            cv2.putText(
                display,
                f"Alarm: {'ON' if alarm_active else 'OFF'}",
                (16, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255) if alarm_active else (80, 255, 160),
                2,
            )
            cv2.putText(
                display,
                f"Temp avg: {avg_temp:.1f}C" if avg_temp is not None else "Temp avg: --",
                (16, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
            )

        success, jpg = cv2.imencode(".jpg", display, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if success:
            STATE.set_frame(jpg.tobytes())

        STATE.update(
            "server",
            connected=True,
            time=utc_now(),
        )

        time.sleep(max(0.0, 1.0 / TARGET_FPS))


class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self._send_json(STATE.snapshot())
            return
        if parsed.path == "/api/frame.jpg":
            frame = STATE.get_frame()
            if frame is None:
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                return
            self._send_bytes(frame, "image/jpeg")
            return
        if parsed.path == "/api/people":
            self._send_json({"people": STATE.people, "recognition": STATE.recognizer is not None})
            return

        path = parsed.path
        if path == "/":
            path = "/index.html"
        target = (WEB_DIST / path.lstrip("/")).resolve()
        if not str(target).startswith(str(WEB_DIST.resolve())) or not target.exists() or target.is_dir():
            target = (WEB_DIST / "index.html").resolve()
        if not target.exists():
            self.send_error(404, "Build the web app first with `cd web && npm run build`.")
            return

        mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self._send_bytes(data, mime)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/alarm":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                payload = json.loads(body)
            except Exception:
                payload = {}
            enabled = bool(payload.get("enabled", False))
            STATE.write_serial("ALARM_ON" if enabled else "ALARM_OFF")
            self._send_json({"ok": True, "enabled": enabled})
            return
        if parsed.path == "/api/people/add":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            if not body:
                self._send_json({"ok": False, "error": "empty body"}, 400)
                return
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                self._send_json({"ok": False, "error": "invalid json"}, 400)
                return

            person_name = str(payload.get("name", "")).strip()
            image_b64 = payload.get("image")
            if not person_name or not image_b64:
                self._send_json({"ok": False, "error": "missing name or image"}, 400)
                return

            try:
                import base64
                image_bytes = base64.b64decode(image_b64.split(",", 1)[-1])
            except Exception:
                self._send_json({"ok": False, "error": "invalid image data"}, 400)
                return

            saved_path = save_person_image(person_name, image_bytes)
            train_database()
            self._send_json({"ok": True, "path": str(saved_path)})
            return
        self.send_error(404)


def main():
    train_database()

    serial_thread = Thread(target=serial_loop, daemon=True)
    serial_thread.start()

    camera_thread = Thread(target=camera_loop, daemon=True)
    camera_thread.start()

    server = ThreadingHTTPServer((HOST, PORT), RequestHandler)
    STATE.append_log(f"Dashboard serving on http://{HOST}:{PORT}", "success")
    print(f"Dashboard serving on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def serial_loop():
    while True:
        ser = STATE.connect_serial()
        if ser is None:
            time.sleep(2)
            continue

        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            if line.startswith("{"):
                try:
                    payload = json.loads(line)
                except Exception:
                    continue

                STATE.update(
                    "pico",
                    connected=True,
                    armed=bool(payload.get("armed", False)),
                    alarm=bool(payload.get("alarm", False)),
                    remote_alarm=bool(payload.get("remote_alarm", False)),
                    alarm_reason=payload.get("alarm_reason", "idle"),
                    distance_cm=payload.get("distance_cm"),
                    temperature_c=payload.get("temperature_c"),
                    humidity=payload.get("humidity"),
                    display_unit=payload.get("display_unit", "C"),
                    last_seen=utc_now(),
                )
                continue

            STATE.append_log(line, "info")
            if "system armed" in line.lower():
                STATE.update("pico", armed=True)
            elif "system disarmed" in line.lower():
                STATE.update("pico", armed=False, alarm=False)
        except Exception as exc:
            STATE.append_log(f"Serial error: {exc}", "warn")
            try:
                ser.close()
            except Exception:
                pass
            STATE.serial = None
            STATE.update("pico", connected=False)
            time.sleep(1)


if __name__ == "__main__":
    main()

