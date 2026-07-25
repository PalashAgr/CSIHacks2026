# Multipurpose Security System

## Developers

Palash Agrawal, Shreeansh Bharadwaj, Valan Sebastian

# Project Overview/Pitch

Imagine that you have to leave your house for a long period of time (for example, 1-2 weeks) for a vacation or some event. Mabye one thing that you are worried about is the security of your home, that someone might break in. So, what if you did not have to worry about that, and instead you had a system that protects your home? Our project uses a thermal camera to detect unwanted human prescense. Not only will it sound an alarm and flash LEDs, it can also send a text message to your phone letting you know of the detection. The system also includes multiple other layers of detection including motion sensing.

# How the system works
We used a raspberry pi pico and connected to it a 4-digit display, an ultrasonic sensor, and an LCD display. The pi will connect to a laptop camera and extract multiple frames from the feed. For each frame, the code uses OpenCV to detect humans, and the ultrasonic sensor detects fast movement. If both of these are detected, it triggers an alarm. The LCD display shows how far the person is and whether the alarm is on or off. The 4-digit display shows the temperature of the environment it is in. These parts help create a multipurpose security system.

# Functionality of each component
LCD1602 Display: Top line should display the distance to the nearest human unrecognized by OpenCv, while the bottom line shows the alarm status (On/off).
TM1637 4-digit display: Shows the surrounding temperature in celsius (Might include a tilt switch to choose either C or F). 
Ultrasonic Sensor: Similar to bats, it sends out high frequency ultrasound waves (between 23 and 40 Hz) to determine the distance between it and the nearest obstacle. 
PIR Motion Sensor: Senses the changes in infrared background and converts into electronic impulses. 
DHT11 Temperature Humidity Sensor Module: By using NTC thermistor (resistive to humid change) and a built-in microcontroller, it calculates both immediate temperature and humidity in the surroundings. It updates once per second. 

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
