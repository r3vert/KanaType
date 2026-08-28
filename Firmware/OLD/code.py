# SPDX-FileCopyrightText: 2017 Limor Fried for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""CircuitPython I2C Device Address Scan"""
# If you run this and it seems to hang, try manually unlocking
# your I2C bus from the REPL with
#  >>> import board
#  >>> board.I2C().unlock()

import time
import board
import adafruit_ssd1306
import busio as io

# To use default I2C bus (most boards)
#i2c = board.I2C()  # uses board.SCL and board.SDA
i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)

def fill_black():
    oled.fill(0)
    oled.show() 
def fill_white():
    oled.fill(1)
    oled.show() 
# fills display with black pixels clearing it
fill_black()
#Zone for title text
oled.fill_rect(0,0,127,9,True)
#Zone for Kana
#oled.fill_rect(0,14,48,48,True)
#oled.fill_rect(51,14,48,48,True)

oled.text("KanaType", 2, 1, False)

oled.text("HC KC", 58, 1, False)

oled.text("0/320", 95, 1, False)

oled.text("\"Myo\"", 100, 20, True)

oled.text("O", 8, 18, True, size=6)
oled.text("O", 58, 18, True, size=6)


oled.show()