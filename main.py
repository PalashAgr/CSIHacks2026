from machine import ADC, I2C, Pin, PWM, time_pulse_us
import time

"""
Pico security firmware for the final hardware build in the photo.

Primary hardware:
- PIR motion sensor for human presence
- HC-SR04 ultrasonic sensor for proximity / motion confirmation
- I2C 16x2 LCD for distance and alarm state
- buzzer and status LED for the alarm
- arm/disarm button

Optional hardware:
- TM1637 4-digit display for temperature

If your wiring differs, change the pin constants at the top.
"""


# -----------------------------
# Pin mapping
# -----------------------------
PIR_PIN = 15
HUMAN_TRIGGER_PIN = PIR_PIN  # Alias kept for compatibility with earlier code

ULTRASONIC_TRIG_PIN = 2
ULTRASONIC_ECHO_PIN = 3

BUZZER_PIN = 16
STATUS_LED_PIN = 25
ARM_BUTTON_PIN = 14

I2C_SDA_PIN = 0
I2C_SCL_PIN = 1
LCD_ROWS = 2
LCD_COLS = 16
LCD_ADDR_CANDIDATES = (0x27, 0x3F)

TM1637_CLK_PIN = 4
TM1637_DIO_PIN = 5


# -----------------------------
# Tuning
# -----------------------------
ALARM_DURATION_MS = 30_000
FLASH_INTERVAL_MS = 140
DISPLAY_UPDATE_MS = 250
TEMP_UPDATE_MS = 1_000
DEBOUNCE_MS = 50

PIR_ACTIVE_HIGH = True
BUTTON_ACTIVE_LOW = True

DISTANCE_NEAR_CM = 120.0
DISTANCE_DELTA_CM = 15.0
PIR_HOLD_MS = 1_250

BEEP_FREQ = 2_100
BEEP_DUTY = 32_768


# -----------------------------
# Optional libraries
# -----------------------------
try:
    import tm1637  # type: ignore
except ImportError:
    tm1637 = None

try:
    from i2c_lcd import I2cLcd  # type: ignore
except ImportError:
    I2cLcd = None


# -----------------------------
# Hardware setup
# -----------------------------
pir_in = Pin(PIR_PIN, Pin.IN, Pin.PULL_DOWN)
button_in = Pin(ARM_BUTTON_PIN, Pin.IN, Pin.PULL_UP)

status_led = Pin(STATUS_LED_PIN, Pin.OUT)
buzzer = PWM(Pin(BUZZER_PIN))
buzzer.duty_u16(0)

ultrasonic_trig = Pin(ULTRASONIC_TRIG_PIN, Pin.OUT)
ultrasonic_echo = Pin(ULTRASONIC_ECHO_PIN, Pin.IN)
ultrasonic_trig.value(0)

temp_sensor = ADC(4)

tm_display = None
if tm1637 is not None:
    try:
        tm_display = tm1637.TM1637(Pin(TM1637_CLK_PIN), Pin(TM1637_DIO_PIN))
    except Exception as exc:
        print("TM1637 init failed:", exc)
        tm_display = None

lcd = None
if I2C is not None and I2cLcd is not None:
    try:
        i2c = I2C(0, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=400_000)
        detected = None
        try:
            scan = i2c.scan()
            for candidate in LCD_ADDR_CANDIDATES:
                if candidate in scan:
                    detected = candidate
                    break
            if detected is None and scan:
                detected = scan[0]
        except Exception:
            detected = LCD_ADDR_CANDIDATES[0]

        if detected is not None:
            lcd = I2cLcd(i2c, detected, LCD_ROWS, LCD_COLS)
    except Exception as exc:
        print("LCD init failed:", exc)
        lcd = None


# -----------------------------
# Helpers
# -----------------------------
def buzzer_on():
    buzzer.freq(BEEP_FREQ)
    buzzer.duty_u16(BEEP_DUTY)


def buzzer_off():
    buzzer.duty_u16(0)


def led_on():
    status_led.value(1)


def led_off():
    status_led.value(0)


def outputs_off():
    buzzer_off()
    led_off()


def is_pir_triggered():
    value = pir_in.value()
    return value == 1 if PIR_ACTIVE_HIGH else value == 0


def is_button_pressed():
    value = button_in.value()
    return value == 0 if BUTTON_ACTIVE_LOW else value == 1


def read_distance_cm():
    try:
        ultrasonic_trig.value(0)
        time.sleep_us(2)
        ultrasonic_trig.value(1)
        time.sleep_us(10)
        ultrasonic_trig.value(0)

        pulse = time_pulse_us(ultrasonic_echo, 1, 30_000)
        if pulse < 0:
            return None
        return pulse / 58.0
    except Exception:
        return None


def read_temperature_c():
    reading = temp_sensor.read_u16() * (3.3 / 65535)
    return 27 - (reading - 0.706) / 0.001721


def update_tm1637_temperature(temp_c):
    if tm_display is None:
        return

    value = int(round(temp_c))
    try:
        tm_display.number(value)
    except Exception:
        try:
            tm_display.show(str(value).rjust(4)[:4])
        except Exception:
            pass


last_lcd = ("", "")


def update_lcd(line1, line2):
    global last_lcd

    if lcd is None:
        return

    text1 = line1[:LCD_COLS].ljust(LCD_COLS)
    text2 = line2[:LCD_COLS].ljust(LCD_COLS)

    if last_lcd == (text1, text2):
        return

    try:
        lcd.clear()
        lcd.move_to(0, 0)
        lcd.putstr(text1)
        lcd.move_to(0, 1)
        lcd.putstr(text2)
        last_lcd = (text1, text2)
    except Exception as exc:
        print("LCD update failed:", exc)


def format_distance(distance_cm):
    if distance_cm is None:
        return "DIST --- CM"
    return "DIST {:5.1f}CM".format(distance_cm)


def set_armed(value):
    global armed, alarm_active, led_state, alarm_until

    armed = value
    if not armed:
        alarm_active = False
        led_state = False
        alarm_until = 0
        outputs_off()
        print("System disarmed")
    else:
        print("System armed")


def start_alarm(reason, distance_cm, temp_c):
    global alarm_active, alarm_until

    alarm_active = True
    alarm_until = time.ticks_add(time.ticks_ms(), ALARM_DURATION_MS)
    print("ALARM:", reason)
    if distance_cm is not None:
        print("Distance: {:.1f} cm".format(distance_cm))
    if temp_c is not None:
        print("Temperature: {:.1f} C".format(temp_c))


# -----------------------------
# State
# -----------------------------
armed = True
alarm_active = False
alarm_until = 0
led_state = False

pir_latched_until = 0
last_distance_cm = None
last_temperature_c = None

last_button_raw = is_button_pressed()
last_button_change = time.ticks_ms()
button_latched = False

last_flash = 0
last_display_update = 0
last_temp_update = 0


print("Pico security system booted")
print("Hardware profile: PIR + ultrasonic + LCD")
outputs_off()
update_lcd("SYSTEM ARMED", "PIR + SONAR READY")


while True:
    now = time.ticks_ms()

    # Button debounce for arm/disarm.
    button_raw = is_button_pressed()
    if button_raw != last_button_raw:
        last_button_raw = button_raw
        last_button_change = now
        button_latched = False
    elif button_raw and not button_latched and time.ticks_diff(now, last_button_change) >= DEBOUNCE_MS:
        set_armed(not armed)
        button_latched = True
        last_lcd = ("", "")

    # Read sensors.
    pir_now = is_pir_triggered()
    if pir_now:
        pir_latched_until = time.ticks_add(now, PIR_HOLD_MS)
    pir_recent = time.ticks_diff(pir_latched_until, now) > 0

    distance_cm = read_distance_cm()
    sonar_motion = False
    if distance_cm is not None:
        if distance_cm <= DISTANCE_NEAR_CM:
            sonar_motion = True
        if last_distance_cm is not None and abs(distance_cm - last_distance_cm) >= DISTANCE_DELTA_CM:
            sonar_motion = True
        last_distance_cm = distance_cm

    if time.ticks_diff(now, last_temp_update) >= TEMP_UPDATE_MS:
        last_temp_update = now
        last_temperature_c = read_temperature_c()
        update_tm1637_temperature(last_temperature_c)

    # Trigger policy: PIR presence plus ultrasonic confirmation.
    intrusion_confirmed = pir_recent and sonar_motion
    if armed and intrusion_confirmed:
        if not alarm_active:
            start_alarm("pir + ultrasonic", distance_cm, last_temperature_c)
        alarm_active = True
        alarm_until = time.ticks_add(now, ALARM_DURATION_MS)

    # Alarm outputs.
    if armed and alarm_active:
        if time.ticks_diff(alarm_until, now) > 0:
            if time.ticks_diff(now, last_flash) >= FLASH_INTERVAL_MS:
                last_flash = now
                led_state = not led_state
                status_led.value(1 if led_state else 0)
                if led_state:
                    buzzer_on()
                else:
                    buzzer_off()
        else:
            print("Alarm finished")
            alarm_active = False
            led_state = False
            outputs_off()
    else:
        outputs_off()

    # LCD status.
    if time.ticks_diff(now, last_display_update) >= DISPLAY_UPDATE_MS:
        last_display_update = now

        line1 = format_distance(distance_cm)
        if not armed:
            line2 = "SYSTEM DISARMED"
        elif alarm_active:
            line2 = "ALARM ACTIVE"
        elif pir_recent:
            line2 = "MOTION DETECTED"
        else:
            line2 = "SYSTEM ARMED"

        update_lcd(line1, line2)

    time.sleep_ms(20)
