# 🚀 Edge-AI Haptic Control Node

> **Zero-touch AI gesture control meets physical hardware verification.**

## 🎯 The Problem
In modern high-tech workspaces, medical clean-rooms, and public terminals, users rely heavily on touchless software or simple AI. However, these systems suffer from a **digital-physical disconnect**:
1. **Lack of Security:** Software-only AI can be fooled by remote hijackers or spoofed images.
2. **Lack of Feedback:** Screen popups for posture or alerts are easily ignored and interrupt workflow.
3. **Hygiene Risks:** Shared physical controls (keyboards/buttons/latches) spread contaminants. 

## 💡 The Solution
The **Edge-AI Haptic Control Node** bridges laptop computer vision with physical edge hardware. It requires **Multi-Factor Physical Presence**—meaning it uses AI to read your gestures, but won't execute physical commands (like unlocking a servo latch) unless the onboard ultrasonic sensor verifies a human is actually sitting at the desk.

Instead of annoying screen popups, the system provides **ambient physical feedback** using OLED telemetry and RGB indicators for a truly zero-touch, secure environment.

## ✨ Features
* **AI Computer Vision:** Real-time hand tracking and gesture recognition via laptop webcam.
* **Multi-Factor Presence Verification:** Ultrasonic sensors ensure the user is physically present before accepting AI commands.
* **Zero-Touch Actuation:** Physical servo motors and latches trigger based on mid-air gestures.
* **Live Hardware Dashboard:** Real-time system telemetry and AI confidence scores stream to an external OLED display.
* **Ambient Alerts:** RGB visual feedback for system status and gesture confirmation.

## 🛠️ Tech Stack
**Hardware:**
* Raspberry Pi Pico
* 52Pi Sensor Kit (Ultrasonic Distance Sensor, OLED Display, Servo Motor, RGB Ring, MPU6050)
* Laptop (Webcam & Processing)

**Software:**
* **Laptop:** Python, OpenCV, MediaPipe, PySerial
* **Microcontroller:** MicroPython

## ⚙️ How It Works (Architecture)
1. **The Brain (Laptop):** A Python script uses OpenCV and MediaPipe to track user gestures in real-time.
2. **The Bridge (Serial):** The laptop sends lightweight encoded commands (e.g., `UNLOCK`, `UPDATE_OLED`) over USB Serial to the Pico.
3. **The Edge (Pico):** The Pico runs a MicroPython loop. It reads local sensor data (Ultrasonic) to verify presence, updates the OLED/RGB displays, and triggers the
