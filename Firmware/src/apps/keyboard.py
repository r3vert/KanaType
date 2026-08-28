"""USB keyboard mode — KMK, QWERTY (edit kanatype/keymap.py).

Requires the KMK library: copy the kmk/ folder from KMKfw/kmk_firmware
into CIRCUITPY/lib/. Shows an install hint if missing.

MENU key (SW3, under Tab):  tap -> setup overlay,  hold -> back to launcher.

M1..M4 are user-assignable. An assignment is (modifier bits, keytable index)
and becomes a KMK key through kanatype.macros -- no macro MODULE is involved,
because KMK modifier keys are callable: KC.LCTL(KC.C) is Ctrl+C. Assignments
live in profiles in nvm and are written straight into keyboard.keymap, which
KMK re-reads on every press, so a change takes effect on the next keystroke.

The screen reports host presence live: KMK owns the main loop once go() is
called, so the check rides a module hook rather than a loop of our own.
"""
import time

POLL_SECONDS = 0.5   # host presence doesn't change fast; don't burn scan cycles
MENU_HOLD_SECONDS = 0.75   # long enough to be deliberate, short enough to feel
# Printable ASCII, preloaded once. The BDF loader rescans the whole font file
# for any character it has not cached (PLAN.md), and the key picker shows
# arbitrary names - without this, each new letter would stall for ~1 s.
ASCII = "".join(chr(c) for c in range(32, 127))


def _msg(ctx, lines):
    from kanatype import ui

    ctx.display.root_group = ui.screen(lines)
    while not ctx.input.poll():
        time.sleep(0.02)


def run(ctx):
    try:
        from kmk.keys import KC
        from kmk.kmk_keyboard import KMKKeyboard
        from kmk.modules import Module
        from kmk.scanners.keypad import KeysScanner, MatrixScanner
    except ImportError:
        _msg(ctx, ["KEYBOARD", "KMK not installed", "kmk/ -> lib/", "Any key: menu"])
        return

    import board
    import digitalio
    import displayio
    import supervisor

    from apps import kbdui
    from kanatype import keymap, macros, settings, ui

    # Our input driver owns the matrix pins — release them for KMK.
    if hasattr(ctx.input, "deinit"):
        ctx.input.deinit()

    row9 = digitalio.DigitalInOut(getattr(board, keymap.ROW9_PIN_NAME))
    row9.switch_to_output(value=False)

    ui.preload(ASCII, "menu")
    ui.preload(ASCII, "jp")

    # --- saved macros --------------------------------------------------------
    stored = settings.load_macros()
    if stored is None:
        state = {"active": 0, "profiles": macros.blank_profiles(), "layer": 0}
        settings.save_macros(state["active"], state["profiles"])
    else:
        state = {"active": stored[0], "profiles": stored[1], "layer": 0}
    # The layer is deliberately NOT persisted: it is a mode you are holding in
    # your head, and coming back to a keyboard that silently types F-keys
    # would be baffling. Every entry into the app starts on the base layer.

    # --- KMK -----------------------------------------------------------------
    keyboard = KMKKeyboard()
    keyboard.matrix = [
        MatrixScanner(
            row_pins=tuple(getattr(board, n) for n in keymap.ROW_PIN_NAMES),
            column_pins=tuple(getattr(board, n) for n in keymap.COL_PIN_NAMES),
            columns_to_anodes=False,  # MANDATORY: PCB has column pull-downs
        ),
        KeysScanner(
            pins=tuple(getattr(board, n) for n in keymap.MOD_PIN_NAMES),
            value_when_pressed=False,
        ),
    ]
    keyboard.keymap = [
        [getattr(KC, n) for n in keymap.kmk_matrix_names()]
        + [getattr(KC, n) for n in keymap.MOD_KMK_NAMES]
    ]

    menu_index = keymap.menu_matrix_index()
    layer_index = keymap.layer_matrix_index()
    macro_indices = keymap.macro_matrix_indices()
    base_names = keymap.kmk_matrix_names()
    layer2 = keymap.layer2_overrides()   # {flat index: KMK name}
    # matrix coordinate -> app code, so the overlay reads logical keys only
    code_by_index = {(r - 1) * 8 + (c - 1): code
                     for (r, c), code in keymap.matrix_app_codes().items()}
    # the three off-matrix modifiers land after the 56 matrix positions
    mod_name_by_index = {56 + i: n for i, n in enumerate(keymap.MOD_KMK_NAMES)}

    def apply_macros():
        """Write the active profile and the layer overrides into the live KMK
        keymap. KMK resolves keymap[layer][idx] on every press, so this takes
        effect on the next keystroke with no reload.

        One KMK layer is used, not two: we are already intercepting every key
        for the overlay, so swapping ~16 entries here is simpler than adding
        the Layers module and keeping its state in step with the screen."""
        keys = state["profiles"][state["active"]]["keys"]
        layer = state["layer"]
        for i, idx in enumerate(macro_indices):
            slot = macros.slot(layer, i)
            keyboard.keymap[0][idx] = macros.to_kc(KC, keys[slot][0],
                                                   keys[slot][1])
        for idx, name in layer2.items():
            keyboard.keymap[0][idx] = getattr(
                KC, name if layer else base_names[idx])

    connected = [supervisor.runtime.usb_connected]

    def show_base():
        with ui.frame():
            ctx.display.root_group = kbdui.base_group(
                connected[0], state["profiles"][state["active"]]["keys"],
                state["layer"])

    def on_change():
        apply_macros()
        if setup.mode == kbdui.OFF:
            show_base()

    def on_save():
        settings.save_macros(state["active"], state["profiles"])

    setup = kbdui.Setup(ctx.display, state, on_change, on_save)
    apply_macros()
    show_base()

    class Companion(Module):
        """MENU tap/hold, the setup overlay's input, and the host-presence
        readout — all on one set of KMK hooks."""

        def __init__(self):
            self._next_poll = 0.0
            self._menu_since = None
            self._held = set()

        def during_bootup(self, kb):
            pass

        def before_matrix_scan(self, kb):
            if (self._menu_since is not None
                    and time.monotonic() - self._menu_since >= MENU_HOLD_SECONDS):
                displayio.release_displays()   # no console flash during reboot
                supervisor.reload()
            now = time.monotonic()
            if now < self._next_poll:
                return
            self._next_poll = now + POLL_SECONDS
            live = supervisor.runtime.usb_connected
            if live != connected[0]:
                connected[0] = live
                if setup.mode == kbdui.OFF:
                    show_base()

        def after_matrix_scan(self, kb):
            pass

        def process_key(self, kb, key, is_pressed, int_coord):
            # Modifiers: track them even while the overlay is open, so the
            # picker can bake whatever is held into the assignment.
            name = mod_name_by_index.get(int_coord)
            if name is not None:
                if is_pressed:
                    self._held.add(name)
                else:
                    self._held.discard(name)
                setup.set_mods(macros.mods_from_kmk(self._held))
                return None if setup.mode != kbdui.OFF else key

            # Returning None breaks KMK's module chain before HID, so the
            # overlay gets the whole keyboard without dropping the USB link.
            if setup.mode != kbdui.OFF:
                if is_pressed:
                    code = code_by_index.get(int_coord)
                    if code:
                        setup.handle(code)
                return None

            if int_coord == layer_index:
                # A toggle, not a hold: flip on press and ignore the release.
                if is_pressed:
                    state["layer"] = 1 - state["layer"]
                    apply_macros()
                    show_base()
                return None

            if int_coord == menu_index:
                if is_pressed:
                    # Only the START is recorded here; the hold deadline is
                    # checked in before_matrix_scan, because process_key runs
                    # on a state CHANGE only — a key merely staying down never
                    # calls it again.
                    self._menu_since = time.monotonic()
                else:
                    started = self._menu_since
                    self._menu_since = None
                    if started is not None:
                        if time.monotonic() - started < MENU_HOLD_SECONDS:
                            setup.open()
                return None

            return key

        def before_hid_send(self, kb):
            pass

        def after_hid_send(self, kb):
            pass

        def on_powersave_enable(self, kb):
            pass

        def on_powersave_disable(self, kb):
            pass

        def deinit(self, kb):
            pass

    keyboard.modules.append(Companion())
    keyboard.go()  # never returns; the MENU hold reloads out
