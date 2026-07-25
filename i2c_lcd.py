"""
I2C LCD1602 driver for MicroPython/Raspberry Pi Pico
Compatible with PCF8574 I2C backpack
"""

from machine import I2C
import time


class I2cLcd:
    """Driver for I2C LCD1602 display with PCF8574 backpack"""

    # LCD commands
    LCD_CLEARDISPLAY = 0x01
    LCD_RETURNHOME = 0x02
    LCD_ENTRYMODESET = 0x04
    LCD_DISPLAYCONTROL = 0x08
    LCD_CURSORSHIFT = 0x10
    LCD_FUNCTIONSET = 0x20
    LCD_SETCGRAMADDR = 0x40
    LCD_SETDDRAMADDR = 0x80

    # Flags for display entry mode
    LCD_ENTRYRIGHT = 0x00
    LCD_ENTRYLEFT = 0x02
    LCD_ENTRYSHIFTINCREMENT = 0x01
    LCD_ENTRYSHIFTDECREMENT = 0x00

    # Flags for display on/off control
    LCD_DISPLAYON = 0x04
    LCD_DISPLAYOFF = 0x00
    LCD_CURSORON = 0x02
    LCD_CURSOROFF = 0x00
    LCD_BLINKON = 0x01
    LCD_BLINKOFF = 0x00

    # Flags for display/cursor shift
    LCD_DISPLAYMOVE = 0x08
    LCD_CURSORMOVE = 0x00
    LCD_MOVERIGHT = 0x04
    LCD_MOVELEFT = 0x00

    # Flags for function set
    LCD_8BITMODE = 0x10
    LCD_4BITMODE = 0x00
    LCD_2LINE = 0x08
    LCD_1LINE = 0x00
    LCD_5x10DOTS = 0x04
    LCD_5x8DOTS = 0x00

    # Flags for backlight control
    LCD_BACKLIGHT = 0x08
    LCD_NOBACKLIGHT = 0x00

    EN = 0b00000100  # Enable bit
    RW = 0b00000010  # Read/Write bit
    RS = 0b00000001  # Register select bit

    def __init__(self, i2c, addr, rows=2, cols=16):
        self.i2c = i2c
        self.addr = addr
        self.rows = rows
        self.cols = cols
        self._backlightval = self.LCD_BACKLIGHT
        self._displayfunction = self.LCD_4BITMODE | self.LCD_2LINE | self.LCD_5x8DOTS
        self._displaycontrol = self.LCD_DISPLAYON | self.LCD_CURSOROFF | self.LCD_BLINKOFF
        self._displaymode = self.LCD_ENTRYLEFT | self.LCD_ENTRYSHIFTDECREMENT

        time.sleep_ms(50)  # Wait for LCD to power up
        self._write(0x00)
        time.sleep_ms(1000)

        # Initialize display
        self._write(0x03)
        self._write(0x03)
        self._write(0x03)
        self._write(0x02)

        self._command(self.LCD_FUNCTIONSET | self._displayfunction)
        time.sleep_ms(5)
        self._command(self.LCD_FUNCTIONSET | self._displayfunction)
        time.sleep_ms(5)
        self._command(self.LCD_FUNCTIONSET | self._displayfunction)
        time.sleep_ms(5)

        self._command(self.LCD_DISPLAYCONTROL | self._displaycontrol)
        self.clear()
        self._command(self.LCD_ENTRYMODESET | self._displaymode)

        self._command(self.LCD_DISPLAYCONTROL | self._displaycontrol)
        self.home()

    def _write(self, value):
        """Write raw byte to I2C"""
        self.i2c.writeto(self.addr, bytes([value | self._backlightval]))

    def _strobe(self, data):
        """Clock enable bit"""
        self._write(data | self.EN)
        time.sleep_us(1)
        self._write(data & ~self.EN)
        time.sleep_us(50)

    def _write4bits(self, value):
        """Write 4 bits to LCD"""
        self._write(value)
        self._strobe(value)

    def _command(self, cmd):
        """Send command to LCD"""
        self._write4bits(cmd & 0xF0)
        self._write4bits((cmd << 4) & 0xF0)

    def _data(self, data):
        """Send data to LCD"""
        self._write4bits(data | self.RS)
        self._write4bits((data << 4) | self.RS)

    def clear(self):
        """Clear display and return cursor to home"""
        self._command(self.LCD_CLEARDISPLAY)
        time.sleep_ms(2)

    def home(self):
        """Return cursor to home position"""
        self._command(self.LCD_RETURNHOME)
        time.sleep_ms(2)

    def move_to(self, col, row):
        """Move cursor to position (col, row)"""
        if row >= self.rows:
            row = self.rows - 1
        self._command(self.LCD_SETDDRAMADDR | (col + 0x40 * row))

    def putstr(self, string):
        """Write string to LCD at current cursor position"""
        for char in string:
            if char == '\n':
                self.move_to(0, 1)
            else:
                self._data(ord(char))

    def backlight(self, state):
        """Turn backlight on/off"""
        if state:
            self._backlightval = self.LCD_BACKLIGHT
        else:
            self._backlightval = self.LCD_NOBACKLIGHT
        self._write(0)

    def display(self, state):
        """Turn display on/off"""
        if state:
            self._displaycontrol |= self.LCD_DISPLAYON
        else:
            self._displaycontrol &= ~self.LCD_DISPLAYON
        self._command(self.LCD_DISPLAYCONTROL | self._displaycontrol)

    def cursor(self, state):
        """Turn cursor on/off"""
        if state:
            self._displaycontrol |= self.LCD_CURSORON
        else:
            self._displaycontrol &= ~self.LCD_CURSORON
        self._command(self.LCD_DISPLAYCONTROL | self._displaycontrol)

    def blink(self, state):
        """Turn cursor blink on/off"""
        if state:
            self._displaycontrol |= self.LCD_BLINKON
        else:
            self._displaycontrol &= ~self.LCD_BLINKOFF
        self._command(self.LCD_DISPLAYCONTROL | self._displaycontrol)
