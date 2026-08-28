# KanaType Firmware — Unified Plan (v1)

High-level plan agreed 2026-08-11 after decision interview. Companion to `../HANDOFF.md`
(hardware truth lives there — pin map, scan polarity, part numbers). This document is the
software source of truth.

## Decisions locked (from the interview)

| Decision | Choice |
|---|---|
| App roster | **Keyboard, Practice (kana drill; typing test later), Quick-note, Vault editor + sync.** Bench tools (I2C debug, IR remote) cut from scope. |
| Display stack | **displayio** everywhere. The framebuf mockup in `OLD/` gets ported, then `OLD/` is reference-only. |
| Japanese text | **On-device only.** Bundle two BDF fonts: Misaki 8 px (dense text, full JIS incl. kanji, scale×2 for big prompts) and k8x12 (legible menus/prompts). Apps pick per purpose. |
| USB keyboard mode | **Plain Latin/QWERTY for v1.** No kana/romaji HID semantics; maybe alt languages later. |
| Boot flow | **Context-smart:** USB host → 2 s menu splash → keyboard mode; battery → quick-note; hold WAKE at power-on → write-enabled session (boot.py remount). Exit-to-menu combo available in every app. |
| Practice drill | Modeled on **DJT Kana** (https://djtguide.neocities.org/kana/ — mechanics reverse-engineered from its `djtkana.js`; no license/attribution in source, we reimplement from scratch in Python). Config menu = per-row checkboxes (basic rows, dakuten rows, digraph combos, × hiragana/katakana) → large kana shown → **user types romaji answer**. Full algorithm in the Practice spec below. |
| Quick-note power | **Nap mode only in v1** (display sleep + underclock + lazy poll, ~8–12 mA). Deep sleep + WAKE1 PinAlarm + nvm re-entry = later milestone. |
| Vault editor v1 | **Browser + append**: file list → header-outline jump → streaming reader → append-to-note. In-place editing deferred. |
| Dev rig (next ~2 weeks) | Bare Feather RP2040 + OLED on STEMMA QT. **Input abstraction with a SerialInput driver** stands in for the matrix; MatrixInput drops in when boards arrive. |
| Build order | M0 platform → M1 practice → M2 quick-note + vault reader → M3 keyboard (boards arrive) → M4 sync + append + deep sleep. |

## Architecture

### Repo layout

```
Firmware/
  OLD/                    # original framebuf mockup — reference only, never deployed
  src/                    # mirrors the CIRCUITPY drive root exactly
    boot.py               # filesystem ownership + (later) nvm wake routing
    code.py               # launcher: context detect, menu, dispatch one app
    settings.toml
    apps/
      keyboard.py         # KMK config (M3)
      practice/
        __init__.py       # app entry: run(ctx)
        config.py         # category/filter menu (H, K, HC, KC, rows/vowels)
        drill.py          # prompt loop, scoring, miss re-queue
        decks.py          # generated from kanatype/kana.py tables
      quicknote.py
      vault/
        __init__.py       # file list + outline + reader (+ append)
        reader.py         # streaming scroll engine (byte offsets, ring buffer)
    kanatype/             # shared platform library — apps import ONLY from here + stdlib
      hw.py               # display init (displayio, 128x64, addr 0x3C), i2c singleton,
                          # pin constants imported from one PINS table
      input.py            # event queue abstraction + drivers (see below)
      ui.py               # menu widget, status bar, text helpers, font loader/cache
      power.py            # nap helpers: display sleep/wake, cpu underclock, idle timer
      storage.py          # write-session detection, safe append (flush+os.sync), nvm keys
      kana.py             # kana ↔ romaji tables: hiragana, katakana, combined (kya…),
                          #   grouped by row/vowel for the filter menu — single source of truth
    fonts/
      misaki_gothic.bdf   # 8px, full JIS
      k8x12.bdf           # 12px
    lib/                  # Adafruit bundle: displayio_ssd1306, display_text, bitmap_font, KMK (M3)
  tools/
    sync/                 # homelab deliverable (M4): udev rule, systemd unit, vault_sync.py
  PLAN.md                 # this file
```

Deployment = copy `src/` contents to CIRCUITPY (a `tools/deploy.ps1` robocopy one-liner is
worth writing on day one).

### The app contract

Each app is a module exposing `run(ctx)` where `ctx` carries: `display`, `input` (event queue),
`fonts`, `writable` (bool from boot.py decision), and `exit_to_menu()` (raises a control
exception the launcher catches → `supervisor.reload()`). Launcher imports **one** app lazily —
the RAM discipline the whole platform depends on. Apps never import each other; sharing goes
through `kanatype/`.

**Global input reservations** (honored by every app):
- Hold all three modifiers (SHIFT+CTRL+CMD, dedicated GPIOs — cheap to poll anywhere) ≈1 s → exit to launcher.
- WAKE key = power semantics only (wake / sleep toggle), never text input.

### Input abstraction (`kanatype/input.py`)

One event model: `KeyEvent(code, pressed)` where `code` is a logical key id from the layout
table (not a GPIO). Drivers:
- **SerialInput** (M0): reads the USB-CDC console — each typed char maps to a logical key;
  a few escape sequences simulate modifiers/WAKE. Makes every app runnable on the bare Feather today.
- **MatrixInput** (M3): wraps `keypad.KeyMatrix` with `columns_to_anodes=False`
  (**mandatory** — hardware pull-downs; see HANDOFF) + `keypad.Keys` for the three modifiers
  (ROW9 held low), + WAKE detection (COL8-high-with-no-row signature).
- Keyboard app is the exception: KMK owns scanning there; the abstraction is for the other apps.

### boot.py responsibilities (kept minimal in v1)

1. Detect hold-WAKE-at-power-on → `storage.remount("/", readonly=False)` +
   `storage.disable_usb_drive()`; record decision for `ctx.writable`.
2. (M4) Read nvm flag → deep-sleep wake routing.
Everything else stays in code.py — boot.py bugs brick the drive access, so it stays tiny.

### Launcher (code.py)

1. Init display + input (serial driver until M3).
2. Context: wait ~1.5 s for USB enumeration → if host present, splash menu with 2 s timeout
   defaulting to keyboard app; if battery, default to quick-note; any key during splash → full menu.
3. Menu: vertical list (k8x12), wraps, shows battery-relevant hints; dispatch via lazy import.
4. On app exit: `supervisor.reload()` (clean heap every time — no leak bookkeeping).

## App specs (high level)

### Practice (M1) — flagship
- **Config screen**: toggle H / K / HC / KC, then row/vowel group filters (the standard
  practice-site checkboxes, adapted to 8 lines — paged checklist). Selection persists
  (settings.toml or a small json when writable; defaults otherwise).
- **Drill screen** (port of the OLD mockup, displayio): title bar (mode + score n/total),
  large kana centered (Misaki scale×2 or ×3; two panes when drilling H+K together),
  typed-romaji echo area, correct/incorrect feedback flash, miss re-queue.
- **Deck**: built from `kana.py` filtered by config (DJT's row granularity: basic rows あ/か/さ…,
  ん, dakuten rows が/ざ/だ/ば/ぱ, digraph combos きゃ/しゃ/…, mirrored for katakana).
- **Algorithm (from DJT Kana source — adopt as-is, it's proven):**
  - Fisher-Yates shuffle the active pool into a deck; draw from the front; skip a draw that
    would immediately repeat the current kana; reshuffle when exhausted.
  - **Validation mode is a setting** with two options: *instant* (DJT-style on-keystroke —
    typed prefix checked live, full match advances immediately) and *confirm* (type then
    press Enter to submit — more deliberate, tolerates typo correction). Both share the same
    romaji variant table (`shi`/`si`, `chi`/`ti`, `tsu`/`tu`, `fu`/`hu`, `ji`/`zi`…) in
    `kana.py`; instant is the default.
  - **Wrong keystroke** → show `kana = reading` correction (inverted text stands in for the
    site's red), require Space/Enter to advance, and **re-insert the missed kana at deck
    positions 3 and 13** (DJT's spaced re-drill — cheap and effective).
  - **Score**: `correct-first-try / total-answered` (the mockup's "0/320" counter semantics).
  - Hint: a designated key reveals the reading (device equivalent of the site's hover).
  - Site features cut on-device: audio (no speaker) and stroke-order GIFs (possible future
    OLED animation; out of scope).
- **Font variety** (device version of the site's 16-typeface display): bundle **3–5
  kana-subset display fonts** for the big prompt glyph; practice setting `font: fixed /
  random-per-prompt / cycle` (random is the pedagogical win — kana recognition across
  typefaces). Storage math (why no compression is needed):
  - The variety fonts are **subset to kana only** (~200 glyphs: hiragana + katakana +
    digraph smalls), unlike the two full-JIS UI fonts. A kana-subset BDF ≈ 40–60 KB as
    plain text; converted to **PCF** (binary, supported by `adafruit_bitmap_font`
    alongside BDF) ≈ 15–30 KB. Five fonts ≈ well under 300 KB against ~6 MB free flash —
    compression would save nothing that matters, and CircuitPython can't feed compressed
    fonts to the font loader anyway. Subsetting IS the compression.
  - RAM: glyphs lazy-load into a cache as rendered — one variety font in play at a time
    (~30–60 KB worst case fully cached), dropped on font switch + `gc.collect()`.
  - Candidate free bitmap families with kana coverage at prompt sizes: Shinonome
    (12/14/16 px, **gothic AND mincho** — real stylistic contrast), JF-Dot collection,
    k8x12, PixelMplus (via TTF→BDF conversion), plus Misaki scaled ×2 as a freebie.
    Rendering check on the 128×64 panel decides the final roster.
  - Pipeline task (M1): `tools/fonts/` script — subset BDF to kana codepoints → `bdftopcf`
    → verify glyph coverage; document each font's license file alongside.
- Runs entirely on serial input until M3 — same logical key codes.

### Quick-note (M2, nap-only)
- Requires `ctx.writable`; if read-only, shows "hold WAKE at power-on to enable" and exits.
- Loop: blank display via `power.nap()` (display.sleep + 48 MHz) → first event wakes screen,
  echo buffer (k8x12) → 4 s idle → append to `/notes/quick-YYYYMMDD.md` (or `quick.md` when
  clock unset) with `---` separator, flush + `os.sync()`, "saved ✓", back to nap.
- Timestamps: from RTC if it looks set (sync sets it in M4); else `[time unknown]` marker.

### Vault (M2 reader, M4 append)
- File list from `/vault/` (curated subset synced later; hand-copied test files until then).
- Per-file: header outline (streaming `#`-scan with byte offsets, code-fence aware) → jump;
  reader with 8-line Misaki window, ring-buffer scroll-back, wrap-on-render;
  strip `**`/`*`/backticks on the visible window only.
- M4 adds: append-to-note (reuses quick-note's editor widget) and the homelab sync
  (`tools/sync/`: udev match on CIRCUITPY label → systemd oneshot → mount → SHA-256 manifest
  3-way merge, conflict copies, trash-not-delete → Syncthing propagates; writes
  `.sync/status.json` + current time as final act).

### Keyboard (M3, boards in hand)
- KMK, QWERTY keymap, config exactly as specified in HANDOFF.md (active-high MatrixScanner +
  KeysScanner modifiers + ROW9 low). KMK Display extension: layer name + status line.
- Exit combo handled by a tiny custom module (modifier-hold detection → supervisor.reload()).
- Keymap layers minimal in v1: base QWERTY + one symbols/function layer.

## Milestones

| # | When | Deliverable | Exit criteria |
|---|---|---|---|
| M0 | now, week 1 | Platform: repo layout, deploy script, hw/input/ui/power modules, fonts loading, launcher + menu on serial input | Menu navigable on bare Feather; a stub app opens and exits cleanly; kana renders in both fonts |
| M1 | week 1–2 | Practice app | Full drill loop on serial input: config → drill → score; OLD mockup visually reproduced in displayio |
| M2 | week 2 | Quick-note (nap) + vault reader | Note survives power pull after "saved ✓"; scroll a real 100 KB markdown file with kanji smoothly |
| M3 | boards arrive | MatrixInput + KMK keyboard app + WAKE/RESET verification | Types on a real PC; practice app driven by physical keys; MENU-key hold works everywhere |
| M4 | after M3 | Homelab sync + vault append + deep-sleep tier | Plug-in sync round-trip with conflict test; WAKE1 wakes from deep sleep into quick-note |

**Landed out-of-band (2026-08):** M0, M1, M3 complete. Plus two unplanned
apps: **Sleep** (manual deep sleep from the menu, WAKE-button wake — the M4
deep-sleep tier arrived early because the battery is glued in) and **Clock**
(view/set RTC — the instrument for the RTC-across-deep-sleep test, open item
#3). Keymap is board-verified; console-on-OLED at boot suppressed.

Also out-of-band, **M-key macros + profiles + a second layer** (section below).
That was not on any milestone; it turns the keyboard app from a fixed keymap
into something configurable on the device.

**Caveat on "complete":** M1 and M3 are complete as *code*, and both have been
deployed, but the practice drill has not been run on hardware since the
2026-08 reflow and the keyboard app has never been run on hardware at all in
its current form. Two AttributeError crashes (`layout.DRILL_SCORE_X`,
`layout.DRILL_ECHO_Y`) were found by preflight on 2026-08-27 and would have
killed Practice and Clock on entry, which is a fair measure of how much of
this is still unverified. `BRINGUP.md` is the checklist.

### Backlog (post-M2, unscheduled)

- **On-device REPL app** ("PyPad"): eval/exec in a persistent namespace,
  custom print injected into the namespace, 8x21 scrollback view, history.
  Namespace pre-seeded with board/ctx/gc/shared-I2C — which quietly restores
  the useful half of the cut bench-tools scope (i2c.scan(), register pokes,
  mem stats) for free. Known limits: no Ctrl-C (runaway exec = RESET button;
  optional watchdog), line wrap on 21-char lines.
  **Prerequisite shared with the M4 vault editor:** a shift layer in
  MatrixInput + punctuation app-codes in keymap.py ( ) . , = : ' " [ ] —
  build it once, both features consume it. The real CircuitPython REPL
  cannot be used on-device (REPL and code.py are mutually exclusive; REPL
  stdin is hardwired to the console) — this app is the practical substitute.

## Font set (2026-08 decision)

On-device JP fonts are down to four, ~221 KB total (was ~1.6 MB):
`notosansjp40.bdf` (Noto rasterized natively at 40px — the drill prompt),
`unifont_jp16_kana.bdf` + `_bold` (16px prompt alternatives), and
`k8x12_kana.bdf` (12px small UI text). Built with `tools/ttf2bdf.py` and
`tools/subset_font.py`; both documented in `src/fonts/README.md`.

**Kanji were dropped** — the full-JIS k8x12 and Misaki are gone, and the "small"
font role with them. **M2's vault reader must regenerate a kanji-capable font
before it can display real notes** (recipes in the fonts README). Also: k8x12's
real metrics are 4px halfwidth / 8px fullwidth — an earlier 8/12 assumption had
silently broken every right-alignment on the drill screen.

## Boot-time work (2026-08)

The black screen before the menu was attacked three ways: the menu font (the
first font loaded on every boot) was subset from 1356 glyphs / 169 KB to
95 / 12 KB; the splash bitmap is painted *before* font loading and matrix init,
since OnDiskBitmap streams from flash with no parse; and the splash text is
baked into that bitmap by `tools/make_splash.py` so it needs no font at all
(`ui.loading()` was removed - its labels would double-print over the baked
text). `code.py` prints `boot: display Xms input Yms menu Zms` to serial, repeated
every 3 s while the menu is idle (`DEBUG_BOOT_TIMING`) because PuTTY can only
attach after the device has booted.

### MEASURED 2026-08-27, and the real cause

    before:  display 180ms  input 271ms  menu 4648ms
    after:   display 180ms  input 270ms  menu  827ms
             [font 64  glyphs 595  labels 95  icons 19  paint 51]

Neither `.mpy` nor font size was the problem. **`adafruit_bitmap_font`'s BDF
loader keeps no glyph index**: `load_glyphs()` does `file.seek(0)` and reads the
whole `.bdf` line by line for any code point not already cached (verified in the
library source). Both `Label(...)` and every `label.text = ...` call it, so
building the 6-item menu cost ~6 full scans of the file - title, cursor, then
`Keyboard`/`Practice`/`Quick note`/`Vault` each dragging in new letters.

`ui.preload(chars, role)` now loads every glyph a screen can show in ONE pass
before any Label exists. That alone took `menu` from 4648 ms to 827 ms (5.5x);
`labels` fell from ~4 s to 95 ms. The libraries were already `.mpy`, and our own
modules import before the timer starts, so **`.mpy` is not the lever BRINGUP
assumed** - it would only shave the pre-`main()` import, which is unmeasured.

Scan cost is linear in FILE LINES, measured at ~0.29 ms/line (595 ms / 2022
lines). Predicted cost of one full scan per font:

| font | bytes | lines | one scan |
|---|---|---|---|
| `ter-u14b_ascii` (menu) | 12 KB | 2022 | 0.59 s (measured) |
| `k8x12_kana` (jp) | 29 KB | 4165 | ~1.2 s |
| `unifont_jp16_kana` (Font 2/3) | 45 KB | 6609 | ~1.9 s |
| `notosansjp40` (Font 1, default) | 97 KB | 10556 | ~3.1 s |

### Consequence for the practice app (preload DONE, PCF is the follow-up)

`drill.py` sets `self._kana.text` per prompt, so the FIRST appearance of each
kana triggers a full scan of the prompt font - ~3.1 s each with the default
40px Noto, against ~75 distinct hiragana in the deck. Score and answer labels
do the same against the jp font (~1.2 s each) until warm. Two fixes:

* **DONE - preload at drill start.** `Screen.__init__` now calls
  `ui.preload()` once per font before building any Label, covered by the baked
  "Loading..." splash: one ~3.1 s pass over the prompt font plus ~1.2 s over the
  jp font, then never again for that session. Measured glyph counts and the RAM
  they cost (~320 B per 40px glyph):

  | enabled | deck | distinct glyphs | prompt-font RAM |
  |---|---|---|---|
  | H (default) | 71 | 71 | ~22 KB |
  | H + HC | 107 | 74 | ~23 KB |
  | all four | 214 | 148 | ~46 KB |

  `drill.py` prints `drill: font X, N prompt glyphs, M B free` to serial on
  entry, which is the number open item #2 asks for. 46 KB with all four scripts
  is the case to watch.

* **FOLLOW-UP (chosen 2026-08-27, after bring-up) - ship PCF instead of BDF.**
  The PCF loader reads an encoding table at init
  and *seeks* straight to each glyph (`file.seek(indices_offset + 2 * idx)`), so
  no scan ever happens and RAM stays proportional to glyphs actually used. Also
  takes boot's `glyphs 595` to near zero, and removes the drill-start wait and
  its RAM spike entirely (glyphs load on demand in ~ms). Needs a
  `tools/bdf2pcf.py` (no
  pure-Python converter exists - the Adafruit one I expected is not real; X.org
  `bdftopcf` is a C tool that is awkward on Windows). Keep BDFs in the repo as
  source for `tools/render.py`, ship PCFs to the device. Verify by reparsing the
  PCF and comparing every glyph bitmap against the BDF it came from.

### Two crash bugs this uncovered (both fixed 2026-08-27)

Reading `drill.py` for the preload turned up `layout.DRILL_SCORE_X`, renamed to
`DRILL_SCORE_RIGHT` during the 2026-08 reflow - `render.py` was updated, the
firmware was not. `Screen.__init__` would have raised AttributeError the moment
Start was pressed, so the practice app could never have reached the drill
screen. `apps/clock.py` had the same disease: `layout.DRILL_ECHO_Y`, a constant
the reflow deleted, now `SCREEN_HINT_Y`.

Both compile clean and only fail when that screen is built, which is why three
deploys never caught them. `tools/preflight.py` now walks every module's **ast**
and resolves each `layout.`/`icons.`/`keymap.`/`kana.` attribute load against
the real module (85 references today). An ast walk rather than a text scan
because docstrings mention `layout.DRILL_*` in prose; verified against a
deliberately reintroduced bug, which it catches while ignoring the same name
inside a docstring.

## M-key macros and profiles (2026-08-28)

The bottom row carries four user-assignable keys. The silkscreen prints M1/M2/M3
and, as a board erratum, nothing for M4 -- so the on-screen assignment list is
the only place M4 is identified. All four were wired as extra spacebar
positions in the original keymap, which contradicted the silkscreen; they typed
a space until this landed.

**No macro module is involved.** KMK modifier keys are callable
(`ModifierKey.__call__` returns a `ModifiedKey`), so `KC.LCTL(KC.C)` *is*
Ctrl+C, and it nests for Ctrl+Shift+V. `kmk.modules.macros` exists for
multi-step sequences and text snippets and is deliberately NOT used: KMK's own
docs recommend custom keys for simple combos, and it costs scan time.

An assignment is two bytes: **modifier bits + an index into
`keytable.NAMES`**. That is what makes four profiles fit in nvm, and it maps
straight onto `macros.to_kc()`.

### Where the keycode list comes from

KMK has no enumerable list of its keys. `KC.<NAME>` walks `KEY_GENERATORS`, and
each `maybe_make_*` function matches the name against a table that is a LOCAL
variable inside the function body -- nothing importable. So
`tools/gen_keytable.py` parses the INSTALLED `lib/kmk/keys.py` with `ast`,
looking for assignments whose value is a tuple of `(code, (name, alias, ...))`
pairs. That one shape covers ascii, F-keys, nav, numpad and the shifted
symbols; letters and digits come from the module-level `ALL_ALPHAS` /
`ALL_NUMBER_ALIASES`. Result: **131 keycodes**, every one guaranteed to resolve
via `getattr(KC, name)` on this device.

Regenerate after a KMK upgrade:

    python Firmware/tools/gen_keytable.py

`keytable.HASH` is stored beside the saved macros. A regenerated table
invalidates them rather than letting stored indices decode to the wrong keys.

### The second layer

The unlabelled key right of the spacebar (SW4, scan 1,4 -- previously `RBRC`,
the board's only "]") is a TOGGLE, not a hold. Pressed, it swaps:

* M1..M4 -> M5..M8, each with its own assignment
* the number row -> F1..F10, and Q/W -> F11/F12
* the panel's `!@#$%^&*()` legend -> `-> F1-F10`, and the M list -> M5..M8

`keymap.LAYER2_KMK` is keyed by KMK NAME, not coordinate, so rearranging
`LAYOUT` moves the F-keys with the right keys. Only ONE KMK layer is used and
~16 keymap entries are swapped by hand: the app already intercepts every key
for the overlay, so adding the `Layers` module would mean keeping its state in
step with the screen for no gain. The layer is **not persisted** -- returning
to a keyboard that silently types F-keys would be baffling.

### The setup overlay

Tap MENU inside the keyboard app. It runs INSIDE the KMK loop rather than
reloading into a separate app: a module whose `process_key` returns None breaks
the chain before HID (`kmk_keyboard.pre_process_key`), so the overlay owns the
whole keyboard while open and the USB link is never dropped.

Screens: setup list (M-keys + active profile), key picker, profile list,
rename. The picker is **type-to-filter** rather than a category tree -- the
device is a keyboard, so the fastest search is already under your fingers -- and
whatever modifiers you hold when you press Enter get baked into the assignment.

Unassigned is the sentinel `0xFF`, never index 0: index 0 is the letter A, and
a slot that quietly types "a" is worse than one that is visibly empty.

nvm went KT05 -> KT06 for eight slots per profile. Full ASCII is preloaded for
both fonts at app start, because the picker shows arbitrary key names and the
BDF loader would otherwise stall ~1 s per newly-seen character.

Still open: multi-key sequences and text snippets (that is where
`kmk.modules.macros` earns its place), and naming profiles beyond 8 characters.

## Open items / risks

1. ~~**Practice-site reference link**~~ — RESOLVED: DJT Kana
   (https://djtguide.neocities.org/kana/); its mechanics are reimplemented in
   `drill.py` (shuffled deck, on-keystroke validation, re-queue at 3 and 13).
2. **KMK + launcher RAM headroom** — measure `gc.mem_free()` in keyboard app early in M3;
   if tight, keyboard app skips font loading entirely.
3. ~~**RTC-across-deep-sleep**~~ — RESOLVED 2026-08-28, negatively: the RTC
   does **not** survive. Set the time in Clock, run Sleep, wake with WAKE1, and
   the clock comes back unset. Cause is structural, not a bug: CircuitPython's
   deep sleep "shuts down power to nearly all of the microcontroller including
   the CPU and RAM" and restarts code.py from the top, and the Feather RP2040
   has no battery-backed RTC domain — the battery keeps the rail up but the
   RTC's clock stops and the chip resets on wake. No firmware change fixes it.

   **Fallback shipped:** `sleepmode.py` stamps the wall clock into nvm before
   sleeping and `code.py` restores it on the way up, flagged **approximate**
   because the time spent asleep is unknowable. The Clock app shows
   `approx (slept)` until the time is set by hand. Quick-note (M2) must treat
   any approximate timestamp as `[time unknown]` rather than presenting it as
   fact. The stamp lives after the MAGIC-guarded blob under its own marker
   byte, so adding it did NOT reset anyone's macros or practice settings.

   Two options if the clock needs to stay genuinely right, neither built:
   * **Periodic re-stamp:** add a `TimeAlarm` alongside the `PinAlarm` so the
     device wakes every N minutes, advances the stored time and sleeps again.
     Cheap — 4 wakes/hour at ~2 s and ~20 mA is ~0.04 mAh/h against ~2 mA of
     sleep current — but it needs boot to recognise a timer wake and go
     straight back down without painting the launcher.
   * **External RTC:** a DS3231 or PCF8523 on the existing I2C bus with its own
     coin cell. Solves it properly and permanently; costs a part and a v2 board.
4. **Serial↔matrix parity** — logical key codes must be identical across drivers or M3 becomes
   a rewrite; locked by defining the layout table in `kana.py`/`hw.py` from day one (M0).
5. CircuitPython **10.2.1** confirmed on the Feather (`OLD/boot_out.txt`); pin the Adafruit
   bundle version to match and record both in `src/settings.toml` comments.
