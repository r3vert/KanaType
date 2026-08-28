# KanaType — Project Handoff

Context document for anyone (human or AI) joining this project cold. Everything below has been
verified against the actual KiCad files, datasheets, and vendor documentation unless marked
otherwise. Last updated: 2026-08-11.

## What this is

KanaType is a custom **61-switch kana (Japanese) typing keyboard** that doubles as a general-purpose
**CircuitPython app platform** — the long-term vision is a multi-app pocket device (kana practice,
typing trainer, offline Obsidian vault editor, I2C debug tool, quick-note capture) with a boot menu,
selected on a 128×64 OLED. USB keyboard mode is just one of the apps.

- **EDA:** KiCad 10.0 project (`KanaType.kicad_sch` / `KanaType.kicad_pcb`), 2-layer, 1.6 mm board,
  roughly 85 × 57 mm. A 3D-printed enclosure exists (see `3D Printing/`).
- **Assembly:** JLCPCB PCBA. Production files in `production/` (`bom.csv`, `positions.csv` are the
  JLC-format files; J1 and U1 are hand-installed).
- **Firmware target:** CircuitPython + **KMK** (chosen over QMK deliberately — Python-native,
  pluggable scanners, and the whole app-platform concept depends on CircuitPython).

## Hardware

### Controller: Adafruit Feather RP2040 (socketed, U1)

All 21 header GPIOs are consumed — **zero spare pins**. I2C (STEMMA QT + J1) is the only expansion path.

| Feather pin | GPIO | Net | Role |
|---|---|---|---|
| TX | 0 | COL1 | column input |
| RX | 1 | COL2 | column input |
| SDA | 2 | SDA | I2C1 → J1 + STEMMA QT |
| SCL | 3 | SCL | I2C1 → J1 + STEMMA QT |
| D4 | 6 | CMD | modifier input |
| D5 | 7 | ROW7 | row drive |
| D6 | 8 | ROW6 | row drive |
| D9 | 9 | ROW5 | row drive |
| D10 | 10 | ROW4 | row drive |
| D11 | 11 | ROW3 | row drive |
| D12 | 12 | ROW2 | row drive |
| **D13** | **13** | **ROW1** | row drive — **onboard red LED on this pin** (see scan polarity) |
| SCK | 18 | COL5 | column input |
| MOSI | 19 | COL4 | column input |
| MISO | 20 | COL3 | column input |
| D24 | 24 | COL7 | column input |
| D25 | 25 | COL6 | column input |
| A0 | 26 | ROW9 | modifier mini-row (held LOW in firmware) |
| A1 | 27 | SHIFT | modifier input |
| A2 | 28 | CTRL | modifier input |
| A3 | 29 | COL8 | column input (also wake-key target) |
| RESET | — | RESET | RESET1 button to GND |
| VBUS / EN / VBAT | — | unconnected | EN power switch was considered but NOT added |

### Key matrix

- **56 keys** in a full 7×8 matrix (ROW1–7 × COL1–8), plus **3 off-matrix modifiers**
  (SHIFT1, CTRL1, CTRL2 = nets SHIFT/CTRL/CMD, each switching to ROW9). Modifiers are
  ghost-immune by construction.
- **No per-key diodes** → 2-key rollover; 3 keys forming a matrix rectangle can phantom a 4th.
  KMK has **no built-in anti-ghosting** (unlike QMK's `MATRIX_HAS_GHOST`), so phantoms would type.
  Deemed acceptable for sequential kana typing; diodes are the headline item for a possible v3.
- **Switch: YIYUAN YTS810SJK** (LCSC C2910644, 4.2×3.2 mm SMD tactile, clone of C&K PTS810).
  **Critical part knowledge:** internal terminal pairs are **{1,2} and {3,4}** (top edge / bottom
  edge) per both YIYUAN's and C&K's datasheets. The LCSC/EasyEDA schematic symbol draws the pairing
  diagonally ({1,4}/{2,3}) — **the symbol is wrong**. All switches are wired pad 2 → row-side net,
  pad 4 → column-side net (pads 1/3 unconnected), which is correct under either interpretation.
  An early board revision had pad 3 also tied to the row, which shorted every key permanently —
  fixed before fabrication. Verify new switch batches with a multimeter: continuity 1↔2 and 3↔4,
  none across 2↔3 unpressed.

### E9 provisioning and the scan-polarity commitment (IMPORTANT)

Eight **8.2 kΩ pull-downs (R1–R8) sit on COL1–COL8** to ground. They exist to (a) neutralize the
D13 LED problem and (b) pre-harden the board for a future RP2350 swap (erratum RP2350-E9 breaks
internal pull-downs; mitigation is external ≤8.2 kΩ, per the RP2350 datasheet errata).

**Consequence: this board must be scanned ACTIVE-HIGH, forever.** Firmware must use
`columns_to_anodes=False` (rows driven high one at a time, columns read with pull-downs).
Default active-low firmware (internal pull-ups on columns) loses against the 8.2 k pull-downs and
reads **every key as permanently pressed**. This is noted on the silkscreen.

Why active-high in the first place: the Feather's red LED hangs on GPIO13 = ROW1
(pin → resistor → LED → GND). With pull-up/active-low scanning, a held ROW1 key sags its column
to ~1.5–1.8 V (the RP2040's undefined zone) → flaky phantoms. With active-high scanning all idle
nets rest at 0 V where the LED cannot conduct. The LED faintly blinks during ROW1 scans (harmless).

### Other on-board circuits (all netlist-verified)

- **RESET1**: tactile switch, RESET pin ↔ GND. Double-tap = UF2 bootloader (Adafruit bootloader).
- **WAKE1**: tactile switch, 3.3 V → R11 (1 kΩ series) → switch → COL8. Enables true wake from
  CircuitPython deep sleep via `alarm.pin.PinAlarm(COL8, value=True)` — pressed level ≈ 2.94 V
  against the 8.2 k pull-down; the 1 k caps fault current at 3.3 mA. Firmware can also treat it
  as a "power key" (signature: COL8 high with no row driven).
- **R9, R10**: 8.2 kΩ I2C pull-ups, SDA/SCL → 3.3 V. Bus is self-sufficient without any module's
  onboard pull-ups; parallel stacking with module pull-ups is fine (keep combined > ~1 kΩ).
- **C1**: 10 µF X5R 0805 bulk cap across 3.3 V/GND, 5.7 mm from J1 (OLED transient reservoir;
  sized via C ≥ I·Δt/ΔV: 30 mA × 30 µs / 100 mV ≈ 9 µF, rounded up for MLCC DC-bias derating).
- **GND pour** on both layers, stitched with ~68 vias. After any routing edit: **refill zones
  (`B`) and SAVE before trusting DRC** — an unfilled pour looks like dozens of dangling vias.

### Display: 128×64 SSD1306 OLED

Plugs into **J1** (pin order GND, 3.3V, SCL, SDA — matches common 4-pin modules; check module
silkscreen for swapped VCC/GND clones). I2C address 0x3C, bus shared with the Feather's STEMMA QT
connector (same GPIO2/3 = I2C1). Text budget with default font: **8 lines × 21 chars**.
Power: ~5–10 mA typical UI, ~20 mA all-white, ~10 µA with `display.sleep()`.
Kana glyphs need `adafruit_bitmap_font` + a BDF with the kana range (Misaki, k8x12) — `terminalio`
is ASCII-only.

### Power / battery

- **350 mAh LiPo** on the Feather's JST; charger is on the Feather (200 mA, CHG LED).
- Estimates: ~30–40 mA active (9–11 h), ~15–20 mA idle w/ display blanked (~1 day),
  ~1.5–2.5 mA CircuitPython deep sleep (~1 week), EN grounded ≈ off (months).
  Linear regulator → battery-hours = mAh ÷ mA. Derate pack ~10%.
- **No RTC battery domain on RP2040** — the on-chip RTC keeps time only while powered and boots
  ignorant. Plan: homelab sync sets the clock at every plug-in (see sync design); flag timestamps
  as unknown after full power loss. Whether the RTC survives deep sleep is untested.
- EN slide switch (hard off) was recommended but **not implemented** — candidate for v2.

### RP2350 upgrade path

The Feather RP2350 is near drop-in (header-compatible; D24/D25/A0–A3 present; D13 LED still exists;
QT still shared with SDA/SCL; 8 MB flash; **HSTX FPC connector on the underside** — check socket
standoff clearance). Gains: 520 KB RAM (2×), much better deep sleep, faster M33 cores. The column
pull-downs already satisfy the E9 erratum for active-high scanning. `board.*` pin names port
unchanged; raw GPIO numbers all shift (D13 = GPIO7 there), but nothing in the plan uses raw numbers.

## Firmware architecture (planned, partially designed)

### Keyboard mode: KMK

```python
keyboard.matrix = [
    MatrixScanner(
        row_pins=(board.D13, board.D12, board.D11, board.D10, board.D9, board.D6, board.D5),  # ROW1..7
        column_pins=(board.TX, board.RX, board.MISO, board.MOSI, board.SCK, board.D25, board.D24, board.A3),
        columns_to_anodes=False,   # MANDATORY: active-high, matches hardware pull-downs
    ),
    KeysScanner(pins=(board.A1, board.A2, board.D4), value_when_pressed=False),  # SHIFT, CTRL, CMD
]
# plus: board.A0 (ROW9) held as output LOW so modifiers read as ground-switched keys
```

Keymap coords: 56 matrix positions row-major, then the 3 modifier keys.
CircuitPython's `keypad` scans in the background and queues events (idle rows returned to inputs —
diodeless-safe by construction). KMK Display extension handles the OLED in keyboard mode
(`off_time`/`dim_time` for power).

### App platform: boot-menu launcher (Architecture A)

`code.py` = launcher: init display, show menu, read one key via raw `keypad`, deinit, then import
and run ONE app. Switch apps via `supervisor.reload()`. KMK loads only inside the keyboard app.

- **RAM is the constraint** (~200 KB heap; fonts are the big consumer) → lazy-import one app at a
  time. Flash is abundant (8 MB total, ~6 MB free on CIRCUITPY for apps/fonts/vault files).
- Shared library planned: `kanatype/hw.py` (display + matrix factories), `kanatype/keymap.py`
  (coord → kana/latin tables — single source of truth for KMK keymap AND practice apps),
  `kanatype/ui.py` (menu, fonts).
- **Filesystem ownership rule:** host owns CIRCUITPY by default (safe for sync + keyboard use);
  hold a designated key at power-on → `boot.py` does `storage.remount("/", readonly=False)` +
  `storage.disable_usb_drive()` for edit/note modes. Never both writers at once (FAT corruption).
- Planned apps: **USB keyboard** (KMK) · **kana practice** · **typing trainer** ·
  **vault editor** · **I2C debug tool** (scan/hexdump/driver views; can type results to host via
  `adafruit_hid`) · **quick-note** · **IR remote** (drives a separate RP2040 IR device over I2C,
  that device running `i2ctarget` as a smart peripheral — I2C carries messages, never IR timing).

### Quick-note mode (low-power capture)

Nap mode default: `display.sleep()` + underclock (`microcontroller.cpu.frequency = 48 MHz`) +
lazy poll; `keypad` keeps scanning in background so the **first keystroke is never lost**
(~8–12 mA). After ~4 s idle: append buffer to notes file, `flush` + `os.sync()`, blank display.
Optional deep-sleep tier after long idle (~1.5–2.5 mA): wake via WAKE1 (PinAlarm on COL8) or
RESET1; `nvm` flag routes boot straight back into quick-note. USB connection suppresses sleep
(CircuitPython behavior) — quick-note is a battery mode by design.

### Obsidian vault editor + homelab sync

- Device stores a curated subset of the vault (markdown only, no attachments) on CIRCUITPY.
- Editor: 128×64 = 8×21 text window. Streaming design for limited RAM: byte-offset header outline
  (`#`-scan in binary mode → jump list), ring buffer of recent line offsets for scroll-back,
  wrap-on-render. Editing tiers: whole-file load (<~24 KB), header-section splice via temp file +
  `os.rename` (power-loss safe), append mode. No autosave per keystroke (flash has no wear leveling).
- **Sync = udev + systemd on a headless Linux homelab.** udev matches `ID_FS_LABEL=="CIRCUITPY"` /
  vendor `239a`, pulls a templated oneshot service: mount → sync → `sync` → unmount, with `flock`.
  **Never trust device FAT timestamps** (no RTC) — use a 3-way merge against a stored manifest of
  SHA-256s from last sync; both-changed = Obsidian-style conflict copy; deletions go to a trash dir.
  Vault dir on the homelab is a Syncthing replica (versioning on) → propagates everywhere.
  Script writes `.sync/status.json` (+ current time, which the device uses to set its RTC) as the
  last act; editor shows sync status at launch.

## Production / JLCPCB

**BOM (`production/bom.csv`, JLC format, J1 excluded by convention):**

| Qty | Part | LCSC | Notes |
|---|---|---|---|
| 61 | YTS810SJK tactile switch | C2910644 | 56 keys + 3 modifiers + RESET1 + WAKE1 |
| 10 | 8.2 kΩ 0805 1% | C17828 | R1–R8 column pull-downs, R9/R10 I2C pull-ups |
| 1 | 1 kΩ 0805 1% | C17513 | R11 wake series |
| 1 | 10 µF 0805 X5R 25 V | C15850 | C1, JLC Basic part |
| 1 | Feather RP2040 | — | hand-installed in socket |

- `positions.csv` format: `Designator,Mid X,Mid Y,Rotation,Layer`, Y negated (KiCad pos convention),
  rotations normalized 0–360, J1 excluded, 74 rows. Switch rotations match a previously working
  assembly run — do not "fix" them.
- A converter script regenerates both files from a KiCad `.pos` export (handles the `10_uF`
  value-mangling KiCad does in pos files).
- Board status at handoff: **DRC 0 errors / 0 unconnected / 0 schematic-parity issues**; remaining
  warnings are cosmetic silkscreen items + a harmless J1 library-mismatch note.
- Order-time checklist: regenerate gerbers from current board · confirm the four C-numbers are
  Basic parts with stock · check switch orientation in the 3D preview · multimeter new switches
  (1↔2 and 3↔4 continuity, none 2↔3).

## Key roles that differ from the silkscreen (READ THIS FIRST)

Four keys no longer do what a plain QWERTY reading of the board suggests. The
authoritative file is `Firmware/src/kanatype/keymap.py`; render the board with:

    python Firmware/tools/keychart.py all

| Physical key | Silkscreen | Now does | Cost |
|---|---|---|---|
| under Tab (SW3, scan 1,3) | none | **MENU**: tap = setup overlay, hold 0.75 s = launcher | lost `` ` `` / `~`, the board's only grave |
| right of space (SW4, scan 1,4) | none | **LAYER** toggle (M5-M8 + F1-F12) | lost `]`, the board's only bracket |
| M1..M3 (SW13/23/33) | M1 M2 M3 | user-assignable macros | M1 defaults to `-`, the board's only hyphen |
| M4 (SW43, scan 5,6) | **none — board erratum** | fourth macro key | was wired as a spacebar position |

Notes for a fresh session:

* **M4 has no silkscreen legend.** The PCB prints M1/M2/M3 and nothing for
  SW43. Add it in v2. Until then the on-screen assignment list is the only
  place M4 is identified.
* **M2/M3/M4 used to type a space** — the original keymap treated all four as
  spacebar positions, contradicting the silkscreen. Only SW57 carries the SPACE
  legend and only SW57 sends space now.
* The number row is silkscreened `1..0` with **no shifted legend**, which is
  why the keyboard app's base screen prints `!@#$%^&*()` under the digits.
* MENU, LAYER and M1..M4 all send `KC.NO` in the static keymap. The macro keys
  are filled in at runtime from the active profile; `preflight.py` allows `NO`
  at exactly those six positions and fails anywhere else.

## Known gotchas (learned the hard way)

1. **LCSC/EasyEDA symbols can lie about switch internals** — always check the manufacturer's
   circuit diagram (this bit us: symbol said diagonal pairing, datasheet says edge pairing).
2. **Refill zones + save before running CLI DRC** — `kicad-cli` judges the file on disk; an
   unfilled pour = phantom "dangling via" storms. (`B` = fill, `Ctrl+B` = UNfill — easy to confuse.)
3. **Off-grid schematic placement** creates invisible 0.02 mm connection gaps — netlist-verify,
   don't trust eyes. Align to grid.
4. **This board is active-high-scan only** (column pull-downs). Wrong polarity = all keys pressed.
5. ERC baseline noise: the switch symbol uses "Unspecified" pin types → ~240 warnings that are
   all benign; don't chase them. Seven 0.1 mm orphan wire crumbs sit at the schematic's left edge
   (cosmetic leftovers from the pad-3 rewiring).
6. **CIRCUITPY goes read-only often**, and robocopy hides it: on a write-protected
   target it logs `ERROR 19` per directory but exits **2**, below the usual >= 8
   failure threshold, so a deploy can report success having copied nothing.
   `deploy.ps1` now probes writability first. Fix with an elevated
   `Set-Disk -IsReadOnly $false` (exact command in `Firmware/BRINGUP.md`).
7. **`adafruit_bitmap_font`'s BDF loader has no glyph index** — every uncached
   character re-scans the whole `.bdf` from byte 0. That was a 4.6 s boot and
   would have been ~3 s per first-seen kana in the drill. Preload glyphs in one
   pass (`ui.preload`); see `Firmware/PLAN.md`.
8. KiCad's `.pos` export rewrites values ("10 μF" → `10_uF`) — the converter script normalizes.
