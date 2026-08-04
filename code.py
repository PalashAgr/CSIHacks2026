import time
import board
import analogio
import digitalio
import usb_hid
from adafruit_hid.mouse import Mouse

# Initialize CircuitPython's native USB Mouse driver
mouse = Mouse(usb_hid.devices)

# Setup Analog Inputs based on your hardware pins
x_axis = analogio.AnalogIn(board.GP26)  # VRX connected to GP26
y_axis = analogio.AnalogIn(board.GP27)  # VRY connected to GP27

# Setup Digital Input for the Joystick button click
select_button = digitalio.DigitalInOut(board.GP16)
select_button.direction = digitalio.Direction.INPUT
select_button.pull = digitalio.Pull.UP

# Establish baseline resting values at startup
CENTER_X = x_axis.value
CENTER_Y = y_axis.value

# Configuration thresholds
DEADZONE = 3000   # Window around center to prevent cursor drift
MAX_SPEED = 12    # Tracking speed

def map_value(value, old_min, old_max, new_min, new_max):
    """Rescales raw analog range values to pixel speed range."""
    return int(new_min + ((value - old_min) * (new_max - new_min) / (old_max - old_min)))

# Track the previous button state to avoid spamming commands
last_button_state = True 

while True:
    # Read current joystick values
    raw_x = x_axis.value
    raw_y = y_axis.value

    # Calculate offset from resting center
    delta_x = raw_x - CENTER_X
    delta_y = raw_y - CENTER_Y

    move_x = 0
    move_y = 0

    # Process X movement (Left / Right) on GP26
    if abs(delta_x) > DEADZONE:
        if delta_x > 0:
            move_x = map_value(raw_x, CENTER_X + DEADZONE, 65535, 0, MAX_SPEED)
        else:
            move_x = map_value(raw_x, 0, CENTER_X - DEADZONE, -MAX_SPEED, 0)

    # Process Y movement (Up / Down) on GP27
    if abs(delta_y) > DEADZONE:
        if delta_y > 0:
            move_y = map_value(raw_y, CENTER_Y + DEADZONE, 65535, 0, MAX_SPEED)
        else:
            move_y = map_value(raw_y, 0, CENTER_Y - DEADZONE, -MAX_SPEED, 0)

    # Move cursor ONLY if inputs are outside the deadzone
    if move_x != 0 or move_y != 0:
        mouse.move(x=move_x, y=move_y)

    # Read current button state
    current_button_state = select_button.value

    # ONLY trigger actions if the button state actually CHANGED
    if current_button_state != last_button_state:
        if not current_button_state:  # Button pressed down (reads False)
            mouse.press(Mouse.LEFT_BUTTON)
        else:                         # Button released (reads True)
            mouse.release_all()
        
        last_button_state = current_button_state

    # Clean delay to slow down USB transmissions and ease power ripples
    time.sleep(0.015)
