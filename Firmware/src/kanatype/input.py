"""Input abstraction.

Apps consume KeyEvent objects from ctx.input.poll(). Logical key codes are
lowercase strings ("a".."z", "0".."9") plus the named codes below.

PARITY RULE (see PLAN.md risk #4): every driver — SerialInput today, the
matrix driver in M3 — must emit exactly these codes. Apps never see GPIOs,
scancodes, or serial bytes.

Serial stand-in mapping (dev rig, until boards arrive):
    letters/digits -> themselves        arrows       -> up/down/left/right
    Enter          -> enter             Space        -> space
    Backspace/Del  -> backspace         ?            -> hint
    ` or Ctrl-Q    -> exit (= the future SHIFT+CTRL+CMD hold combo)
    ~              -> wake (= the future WAKE key)
"""
import sys

import supervisor

ENTER = "enter"
SPACE = "space"
BACKSPACE = "backspace"
UP = "up"
DOWN = "down"
LEFT = "left"
RIGHT = "right"
HINT = "hint"
EXIT = "exit"
WAKE = "wake"
LAYER = "layer"   # the macro-layer toggle, right of the spacebar

_ARROWS = {"\x1b[A": UP, "\x1b[B": DOWN, "\x1b[C": RIGHT, "\x1b[D": LEFT}


class KeyEvent:
    def __init__(self, code, pressed=True):
        self.code = code
        self.pressed = pressed  # SerialInput only emits presses


class SerialInput:
    """Reads the USB-CDC console; stands in for the matrix until M3."""

    def __init__(self):
        self._esc = ""

    def poll(self):
        events = []
        while supervisor.runtime.serial_bytes_available:
            code = self._map(sys.stdin.read(1))
            if code:
                events.append(KeyEvent(code))
        return events

    def _map(self, ch):
        if self._esc:
            self._esc += ch
            if self._esc in ("\x1b[", "\x1bO"):
                return None  # sequence still incomplete
            seq, self._esc = self._esc, ""
            return _ARROWS.get(seq)
        if ch == "\x1b":
            self._esc = ch
            return None
        if ch in ("\r", "\n"):
            return ENTER
        if ch == " ":
            return SPACE
        if ch in ("\x7f", "\x08"):
            return BACKSPACE
        if ch in ("`", "\x11"):
            return EXIT
        if ch == "~":
            return WAKE
        if ch == "?":
            return HINT
        if "a" <= ch <= "z" or "0" <= ch <= "9":
            return ch
        if "A" <= ch <= "Z":
            return ch.lower()
        return None


class MatrixInput:
    """The real board: 7x8 matrix + 3 hardware modifiers (M3).

    ACTIVE-HIGH scanning is mandatory (columns_to_anodes=False) — the PCB has
    8.2k pull-downs on every column. Emits presses only (parity with
    SerialInput); the sole synthetic event is EXIT when all three modifiers
    are held together. Call deinit() before KMK takes over the same pins.
    """

    def __init__(self):
        import board
        import digitalio
        import keypad

        from kanatype import keymap

        self._row9 = digitalio.DigitalInOut(getattr(board, keymap.ROW9_PIN_NAME))
        self._row9.switch_to_output(value=False)  # modifiers read as gnd-switched
        rows = tuple(getattr(board, n) for n in keymap.ROW_PIN_NAMES)
        cols = tuple(getattr(board, n) for n in keymap.COL_PIN_NAMES)
        self._matrix = keypad.KeyMatrix(rows, cols, columns_to_anodes=False)
        self._mods = keypad.Keys(
            tuple(getattr(board, n) for n in keymap.MOD_PIN_NAMES),
            value_when_pressed=False, pull=True,
        )
        codes = keymap.matrix_app_codes()
        self._by_num = [codes.get((r + 1, c + 1))
                        for r in range(7) for c in range(8)]
        self._held_mods = [False, False, False]
        self._exit_sent = False

    def poll(self):
        events = []
        ev = self._matrix.events.get()
        while ev:
            if ev.pressed:
                code = self._by_num[ev.key_number]
                if code:
                    events.append(KeyEvent(code))
            ev = self._matrix.events.get()
        mev = self._mods.events.get()
        while mev:
            self._held_mods[mev.key_number] = mev.pressed
            if all(self._held_mods) and not self._exit_sent:
                events.append(KeyEvent(EXIT))
                self._exit_sent = True
            elif not all(self._held_mods):
                self._exit_sent = False
            mev = self._mods.events.get()
        return events

    def deinit(self):
        self._matrix.deinit()
        self._mods.deinit()
        self._row9.deinit()


class CombinedInput:
    """Polls several drivers as one (matrix + serial console during dev)."""

    def __init__(self, drivers):
        self.drivers = drivers

    def poll(self):
        events = []
        for d in self.drivers:
            events.extend(d.poll())
        return events

    def deinit(self):
        for d in self.drivers:
            if hasattr(d, "deinit"):
                d.deinit()


def get_input():
    """Matrix + serial together when the board responds; serial-only otherwise
    (bare Feather, or pins claimed by something else)."""
    drivers = []
    try:
        drivers.append(MatrixInput())
    except Exception:
        pass
    drivers.append(SerialInput())
    return CombinedInput(drivers)
