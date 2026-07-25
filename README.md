# Multipurpose Security System

## Developers

Palash Agrawal, Shreeansh Bharadwaj, Valan Sebastian

## Overview

This project is a home-security prototype built around a Raspberry Pi Pico. It is designed for situations where you want to monitor a house, room, or entryway while you are away.

The system combines multiple checks before raising an alert:

- human detection from an external device running OpenCV
- ultrasonic motion/proximity sensing
- visual status on an LCD
- ambient temperature on a 4-digit display
- buzzer and LED alarm output

When a person is detected and motion is confirmed, the Pico activates the alarm and flashes the LEDs.

## How It Works

OpenCV runs on a laptop, Raspberry Pi, or other host device connected to a camera. When the host detects a human, it drives a Pico input pin high. The Pico then checks an ultrasonic sensor to confirm motion or proximity.

If both checks indicate a possible intrusion, the Pico:

- sounds the buzzer
- flashes the status LED
- shows the alarm state on the LCD
- keeps the alert active for a timed period

The 4-digit display shows the ambient temperature using the Pico's internal temperature sensor.

## Firmware

The MicroPython firmware is in [`main.py`](./main.py).

Default pins used by the firmware:

- `GP15` - external human-detection trigger input
- `GP2` - ultrasonic `TRIG`
- `GP3` - ultrasonic `ECHO`
- `GP16` - buzzer
- `GP25` - status LED
- `GP14` - arm/disarm button
- `GP4` - TM1637 clock
- `GP5` - TM1637 data
- `GP0` / `GP1` - I2C LCD

## Optional Libraries

The firmware works even if the display libraries are missing, but it will use them automatically if they are installed on the Pico:

- `tm1637` for the 4-digit display
- `i2c_lcd` for the I2C LCD

## Notes

- OpenCV does not run on the Pico itself. It must run on the host device.
- The ultrasonic sensor is used as a second check, not as the only detector.
- The internal temperature sensor is an approximation, which is fine for a classroom demo or prototype.

## Project Summary

This system is a multipurpose security prototype that combines camera-based detection, motion sensing, temperature display, and active alerts into one compact Pico-based setup.

## Web Dashboard

A Svelte-based security dashboard lives in [`web/`](./web). It includes:

- live webcam preview
- face-based human detection when the browser supports it
- motion gating and alarm state
- LCD-style status output
- temperature and alert panels
- anime.js animations for the security theme

To run it locally:

```bash
cd web
npm install
npm run dev
```

The camera view works best on `localhost` or another secure context.
