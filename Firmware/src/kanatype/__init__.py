"""KanaType shared platform library.

Apps import ONLY from this package + stdlib/CircuitPython core.
Apps never import each other.
"""

VERSION = "0.1.0-M0"


class Ctx:
    """Handed to every app's run(ctx). The app's whole world."""

    def __init__(self, display, inp, usb, writable):
        self.display = display    # displayio Display (128x64)
        self.input = inp          # driver with .poll() -> list[KeyEvent]
        self.usb = usb            # True if a USB host enumerated us
        self.writable = writable  # True if boot.py granted a write session
