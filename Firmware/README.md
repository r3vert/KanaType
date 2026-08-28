# KanaType Firmware

See `PLAN.md` for the full plan; `../HANDOFF.md` for hardware truth.

## Layout

- `src/` — mirrors the CIRCUITPY drive root. Deploy with `tools/deploy.ps1`.
- `tools/` — desktop-side helpers (deploy, mockup round-trip).
- `mockups/` — UI mockups (`.txt` / `.pbm` pixel-exact, `.png` for viewing).
- `OLD/` — original framebuf UI mockup dump; reference only, never deployed.

## Device prerequisites (once)

1. CircuitPython **10.2.1** (already on the Feather — see `OLD/boot_out.txt`).
2. From the Adafruit **10.x bundle**, copy into `CIRCUITPY/lib/`:
   - `adafruit_displayio_ssd1306.mpy`
   - `adafruit_display_text/`
   - `adafruit_bitmap_font/`
3. Fonts: see `src/fonts/README.md` (optional — ASCII fallback works without).

## Dev loop

Run the pre-deploy checks first, then deploy:

```powershell
python tools\preflight.py
```

It compiles everything, then verifies font roles, prompt-font styles, keymap
coverage, deck counts, icon bounds, the nvm settings round-trip, menu entries,
and (when the device is mounted) stale files left behind on it. Exits non-zero
on anything that has broken this project before.

Deploy scripts NEVER delete, so a file removed from `src/` lingers on the
device until you remove it by hand — preflight names those files for you.

First deploy after a big change? Work through `BRINGUP.md`.


```powershell
.\tools\deploy.ps1     # copies src/ to CIRCUITPY; device auto-reloads
```

Open the serial console (Mu, `screen`, or PuTTY on the board's COM port).
Until the boards arrive, the console **is** the keyboard:

| Serial key | Acts as |
|---|---|
| letters / digits | themselves |
| arrows or `j`/`k` | menu navigation |
| Enter | select / confirm |
| `?` | hint (practice) |
| `` ` `` or Ctrl-Q | exit-to-menu (future SHIFT+CTRL+CMD hold) |
| `~` | WAKE key |

## Mockup round-trip

Draw UI ideas as pixel grids and share them losslessly (see PLAN.md):

```powershell
python tools\mockup.py new mockups\myscreen.txt        # blank 128x64 grid
python tools\mockup.py convert mockups\myscreen.txt mockups\myscreen.png 6
python tools\mockup.py demo mockups                    # regenerate the sample
```

`.txt` grids (`#`/`.`) are pixel-exact and diff-able; `.pbm` (GIMP "ASCII" export)
round-trips through image editors; `.png` is for eyeballs.
