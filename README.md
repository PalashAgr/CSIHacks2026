# Multipurpose Security System

## Developers

Palash Agrawal, Shreeansh Bharadwaj, Valan Sebastian

# Project Overview

This project is a local home-security prototype built around a Raspberry Pi Pico, a laptop webcam, and a browser dashboard.

The system uses:

- `PIR` motion sensing for human presence
- `HC-SR04` ultrasonic sensing for distance confirmation
- `DHT11` for room temperature and humidity
- `LCD1602` for distance and alarm status
- `TM1637` 4-digit display for temperature
- OpenCV on the laptop for tracking and identity matching
- a people database to decide whether a visitor is known or unknown
- a buzzer and LED alarm for unknown or suspicious activity

## How It Works

The Pico handles the physical sensors and displays:

- The LCD shows the nearest distance on the top line.
- The second LCD line shows whether the alarm is `ON` or `OFF`.
- The TM1637 display shows the room temperature.
- The DHT11 temperature and humidity readings are averaged before they are sent to the dashboard.

The laptop runs `bridge.py`:

- reads Pico sensor data over USB serial
- uses OpenCV to track the person in the laptop camera
- compares the detected person against the local people database
- enables the buzzer only when the visitor is outside the saved database
- serves the synced dashboard locally on `http://127.0.0.1:8000`

# Functionality of each component

LCD1602 Display: Top line should display the distance to the nearest human unrecognized by OpenCV, while the bottom line shows the alarm status (On/Off).

TM1637 4-digit display: Shows the surrounding temperature in Celsius (may include a tilt switch to choose C or F).

Ultrasonic Sensor (HC-SR04): Sends out high-frequency ultrasound waves to determine distance to the nearest obstacle and assists in detecting fast movement.

PIR Motion Sensor: Senses changes in infrared background and converts them into electronic impulses to detect presence.

DHT11 Temperature/Humidity Sensor: Uses a resistive element and internal microcontroller to calculate temperature and humidity; updates roughly once per second.

# Wiring GPIO values

- buzzer = 16
- trig = 17
- echo = 27
- out = 21
- dio = 14
- clk = 15
- data = 28
- sda = 0
- scl = 1

## Files

- [`main.py`](./main.py) - MicroPython firmware for the Pico
- [`bridge.py`](./bridge.py) - local OpenCV + serial bridge and HTTP server
- [`web/`](./web) - Svelte dashboard source
- [`requirements.txt`](./requirements.txt) - Python packages for the bridge

## People Database

Create a folder named `people_db/` in the repo root.

For each known person, add a subfolder with their name and several face images:

```text
people_db/
  Alice/
    1.jpg
    2.jpg
  Bob/
    1.jpg
    2.jpg
```

The bridge trains the local OpenCV face recognizer from those images.

## Running Locally

1. Flash `main.py` to the Pico.
2. Install the Python bridge dependencies:

```bash
pip install -r requirements.txt
```

3. Build the web dashboard:

```bash
cd web
npm install
npm run build
```

4. Start the bridge server from the repo root:

```bash
python bridge.py
```

5. Open the dashboard at:

```text
http://127.0.0.1:8000
```

## Notes

- OpenCV runs on the laptop, not on the Pico.
- The dashboard is local only and stays on `127.0.0.1`.
- The buzzer is driven only when the tracked person is unknown or when the Pico raises a local alarm.
- If the face recognizer is unavailable, the bridge still tracks the camera feed and will treat visitors as unknown.
