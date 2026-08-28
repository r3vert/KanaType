"""Hardware init. The single source of truth apps use for the display.

Pin-level truth for the finished board lives in HANDOFF.md; the matrix
pins land here in M3 as one PINS table shared by input.py and keyboard app.
"""
import board
import displayio

from kanatype.layout import WIDTH, HEIGHT  # single source of truth

OLED_ADDR = 0x3C

_display = None


def display():
    """Init (once) and return the 128x64 SSD1306 on I2C1 (J1 / STEMMA QT)."""
    global _display
    if _display is None:
        import i2cdisplaybus
        import adafruit_displayio_ssd1306

        import busio

        displayio.release_displays()
        # Same bus as STEMMA_I2C/J1, but explicitly at 400 kHz — the SSD1306
        # supports it and display updates are 4x faster than the 100 kHz default.
        i2c = busio.I2C(board.SCL, board.SDA, frequency=400_000)
        bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=OLED_ADDR)
        _display = adafruit_displayio_ssd1306.SSD1306(bus, width=WIDTH, height=HEIGHT)
        # A fresh display defaults to showing CircuitPython's serial console —
        # blank it immediately so boot text never reaches the panel.
        _display.root_group = displayio.Group()
    return _display
