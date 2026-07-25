# Multipurpose Security System
# Developers

Palash Agrawal, Shreeansh Bharadwaj, Valan Sebastian

# Project Overview

Imagine that you have to leave your house for a long period of time (for example, 1-2 weeks) for a vacation or some event. Mabye one thing that you are worried about is the security of your home, that someone might break in. So, what if you did not have to worry about that, and instead you had a system that protects your home? Our project uses a thermal camera to detect unwanted human prescense. Not only will it sound an alarm and flash LEDs, it can also send a text message to your phone letting you know of the detection. The system also includes multiple other layers of detection including motion sensing.

# How it works
We used a raspberry pi pico and connected to it a 4-digit display, an ultrasonic sensor, and an LCD display. The pi will connect to a laptop camera and extract multiple frames from the feed. For each frame, the code uses OpenCV to detect humans, and the ultrasonic sensor detects fast movement. If both of these are detected, it triggers an alarm. The LCD display shows how far the person is and whether the alarm is on or off. The 4-digit display shows the temperature of the environment it is in. These parts help create a multipurpose security system.

# Wiring GPIO values
buzzer = 16
trig = 17
echo = 27
out = 21
dio = 14
clk = 15
data = 28
sda = 0
scl = 1
