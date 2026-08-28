# Bring-up checklist — first deploy after the 2026-08 changes

This deploy is unusually large: fonts were replaced, the practice screen was
reflowed, two apps are new, and several screens changed how they refresh. Work
top to bottom; each task says what "good" looks like and what to do if it isn't.

Tick boxes as you go. If something fails, note *what you saw* — that is what
makes it fixable.

---

## STATUS (updated live)

Deployed 3x; device at `L:` with **6.0 MB free**; KMK confirmed in `lib/`.
**Tasks 1-3b are DONE.** Next action is **task 4** (keyboard + macros on
hardware) — the app was rewritten on 2026-08-28 and has never run on the board
in this form.

Deployed again after 3b with three changes: the drill-font preload, and fixes
for two AttributeError crashes that would have killed **Practice** and **Clock**
on entry (`layout.DRILL_SCORE_X` and `layout.DRILL_ECHO_Y`, both renamed away in
the 2026-08 reflow). Preflight now resolves every `layout.*` reference against
the real module, so that class of bug fails before a deploy instead of on
hardware.
Nothing is committed to git yet — task 10 matters.

If the drive goes read-only again (it has, repeatedly), run in an **elevated**
PowerShell. `deploy.ps1` now probes writability first and prints this command
itself — before the fix it printed "Deployed" while copying nothing, because
robocopy exits 2 (not >= 8) on a write-protected target:

```powershell
Get-Volume | Where-Object FileSystemLabel -eq CIRCUITPY | Get-Partition | ForEach-Object { Set-Disk -Number $_.DiskNumber -IsReadOnly $false }
```

## 1. Delete the stale fonts  ✅ DONE

The deploy scripts are non-destructive on purpose (`robocopy /E`, `rsync`
without `--delete`) so device-side `lib/` installs are never clobbered. The
downside: fonts removed from the repo stay on the device forever.

- [x] Plug in the device, confirm CIRCUITPY mounts
- [x] Delete from `CIRCUITPY/fonts/`:
  - `k8x12.bdf` (845 KB) — replaced by `k8x12_kana.bdf`
  - `misaki_gothic.bdf` (764 KB) — role retired
  - `LICENSE-misaki.txt` (optional tidiness)
- [x] Confirm ~1.6 MB of free space came back

**Good:** `fonts/` holds only the files that are in `Firmware/src/fonts/`.

---

## 2. Preflight, then deploy  ✅ DONE

- [x] `python Firmware/tools/preflight.py` → **PREFLIGHT PASSED**
      (with the device plugged in it also flags any stale font it still finds)
- [x] `.\Firmware\tools\deploy.ps1`   (Windows)
      or `./Firmware/tools/deploy.sh`  (macOS/Linux)
- [x] Device auto-reloads

**If preflight fails:** stop. It only reports problems that have actually
broken this project before; deploying past it wastes a debugging cycle.

---

## 3. Boot and launcher  ✅ DONE (all 4 confirmed)

- [x] Panel goes straight from black to the menu — **no REPL / "Ctrl-D" text**
- [x] Title reads `KanaType`, six entries: Keyboard, Practice, Quick note,
      Vault, Clock, Sleep
- [x] Top-right shows a **tilde** briefly, then a **lightning bolt** (USB)
- [x] Arrow keys / `j`,`k` scroll the menu; it feels immediate, not laggy
- [x] Cursor starts on **Keyboard** (because USB is present)

**Then test the polling fix:**

- [x] Sit at the menu, unplug USB → icon changes to **battery** within ~1 s
- [x] Plug back in → icon returns to **bolt**, and the cursor does **not** jump

**If the icon never changes:** the poll isn't running — capture whether it was
stuck on bolt or battery.

---

## 3b. Boot timing measurement  ✅ DONE

    before:  display 180ms  input 271ms  menu 4648ms
    after:   display 180ms  input 270ms  menu  827ms
             [font 64  glyphs 595  labels 95  icons 19  paint 51]

The line reprints every 3 s while the menu is idle, since PuTTY can only attach
after boot. Toggle is `DEBUG_BOOT_TIMING` at the top of `src/code.py`; set it
`False` when you no longer want the noise. Repeats carry `(uptime Ns)`.

**Cause was not font size or `.mpy`** - the BDF loader has no glyph index, so
every uncached character rescans the whole `.bdf` from byte 0, and the menu
build did ~6 of them. `ui.preload()` now does one pass up front: 5.5x faster.
Full write-up and the per-font scan costs are in `PLAN.md`.

Boot is now ~1.3 s to an interactive menu, with the splash on screen from
180 ms, so the black screen is no longer the problem. The remaining 595 ms is
one honest pass over the BDF - see the PCF option in PLAN.md.

The same rescan hit the drill prompt at ~3.1 s per first-seen kana; `drill.py`
now preloads each font in one pass at start instead. PCF is the logged
follow-up that removes scanning altogether (PLAN.md).

## 4. Keyboard app + macro system  <-- NEXT ACTION

The whole app was rewritten on 2026-08-28 and has never run on hardware in this
form. Work it in order; the later checks assume the earlier ones passed.

### 4a. Base typing

- [ ] Open Keyboard. Screen shows `KEYBOARD`, a bolt icon, `1234567890` over
      `!@#$%^&*()` on the left, `M1..M4` with assignments on the right, and
      `tap: setup` / `hold: exit` bottom-left
- [ ] Type in a text editor — letters match the printed keys
- [ ] `Shift`+letter capitalises; `Ctrl`+C/V copy-paste; `Alt` behaves
- [ ] Spacebar (SW57, the key with the SPACE legend) types a space
- [ ] Arrow keys move the caret in the right directions
- [ ] **M1 types `-`** (the board's only hyphen), M2 `Ctrl+C`, M3 `Ctrl+V`,
      M4 `Ctrl+Shift+V` — M4 is the UNLABELLED key between M3 and the spacebar
- [ ] The key right of the spacebar no longer types `]`

### 4b. MENU tap vs hold

- [ ] Tap MENU (under Tab) → setup overlay, titled `SETUP M1-M4`
- [ ] **While the overlay is open, typing does NOT reach the PC.** Watch the
      editor: every key should be swallowed. This is the `process_key`
      return-None path and it has only been verified against KMK's source
- [ ] USB stays connected the whole time (no device-disconnect chime)
- [ ] MENU again closes the overlay, back to the base screen
- [ ] Hold MENU ~0.75 s → launcher, no console flash. **If 0.75 s feels wrong
      in the hand, say so** — `MENU_HOLD_SECONDS` in `apps/keyboard.py`

### 4c. Assigning a key

- [ ] In setup, Enter on `M1` → `SET M1`, `find: _`, list of keycodes
- [ ] Type `f13` → the list narrows to `F13`. **It should be instant**; a
      pause of ~1 s per letter means the ASCII preload did not work
- [ ] Enter → back to the list, `M1  F13`
- [ ] Close the overlay and press M1 → the PC receives F13
- [ ] Assign again, this time **holding the CMD key while pressing Enter** →
      the filter line shows `+Ctrl` and the assignment reads `Ctrl+...`
- [ ] Backspace on an M row clears it to `-`; that key then types nothing

### 4d. The layer toggle

- [ ] Press the key right of the spacebar → the M list becomes `M5..M8`, the
      second legend row becomes `-> F1-F10`
- [ ] Number row now sends **F1..F10**; **Q sends F11, W sends F12**
- [ ] M5..M8 are independently assignable, and **assigning one must not change
      M1..M4** (the slot indexing is the risky part)
- [ ] Press it again → back to digits and M1..M4
- [ ] Press it inside the setup overlay → the title flips between
      `SETUP M1-M4` and `SETUP M5-M8`
- [ ] Leave the app and come back → **starts on the base layer** (deliberate)

### 4e. Profiles and persistence

- [ ] Setup → `Profile` row → Enter → profile list, `*` marks the active one
- [ ] Select profile 2, assign something to M1, switch back to profile 1 →
      profile 1's assignments are intact
- [ ] `Rename` → type a name (8 chars max) → Enter → the name shows in the list
- [ ] **Hold MENU to the launcher, re-enter Keyboard → every assignment,
      profile and name survived** (this is the nvm round-trip)

### 4f. Host presence

- [ ] Unplug USB, keep the battery on → the bolt icon becomes a battery within
      ~1 s; plug back in → bolt returns

**If a key types the wrong character:** note the physical key and what it typed.
One-line fix in `kanatype/keymap.py`, then re-run preflight.

**Expect a one-time reset:** nvm went KT05 -> KT06, so macro assignments AND
practice settings start at defaults on this deploy.

---

## 5. Practice app — not yet seen on hardware

Everything below is render-verified only, so this is the section most likely to
surprise.

- [ ] Open Practice → config menu appears
- [ ] Toggle categories with Enter; `[x]` / `[ ]` update instantly
- [ ] **Font** row opens a submenu listing Font 1–4, each previewing あ at its
      real drill size on the right — Font 1 (Noto 40px) should look clearly
      the best
- [ ] Pick Font 1, Back, then Start
- [ ] **Start shows the "Loading..." splash for ~4 s**, then the drill. That is
      the one-time glyph preload (~3.1 s prompt font + ~1.2 s jp font); it
      should NOT reappear on later prompts or on re-entry in the same session
- [ ] Serial prints `drill: font noto, 71 prompt glyphs, N B free` — note N,
      it answers PLAN open item #2. Enable all four scripts and check it again
      (~148 glyphs, ~46 KB more)
- [ ] Drill screen: types stacked down the **left**, score as a **fraction**
      top-right, **3-slot box** below it, big kana centred
- [ ] **Multi-kana prompts (きゃ etc.) appear all at once**, never one glyph
      then the other — this was the tearing fix
- [ ] Type a correct answer → advances instantly, score increments
- [ ] Type a wrong letter → your input stays in the box; Space/Enter advances
- [ ] `/` reveals the reading in the box
- [ ] Exit combo → back to config; again → back to the menu

**Persistence:**

- [ ] Change categories/mode/font, exit to the menu, re-enter Practice →
      **your settings are still there**
- [ ] "Reset to defaults" → Hiragana only, Instant, Font 1, status says
      `Defaults restored`

---

## 6. Clock — set the time

- [ ] Open Clock → live date/time, seconds ticking
- [ ] Expect **`RTC UNSET!`** on a cold boot (year reads pre-2024)
- [ ] Enter → edit mode, dashes underline the active field
- [ ] LEFT/RIGHT move between year/month/day/hour/minute; UP/DOWN change values
- [ ] Enter commits → warning clears, seconds tick from :00
- [ ] Leave and re-enter Clock → time still correct

---

## 7. Sleep + wake

- [ ] From the menu, choose **Sleep** → "WAKE button wakes me up", screen off
- [ ] Press any *ordinary* key → **nothing happens** (this is intended)
- [ ] Press **WAKE** → device wakes and returns to the menu

**Note:** while USB is connected CircuitPython refuses true deep sleep, so this
is screen-off only. For the real power test, run it on battery, unplugged.

---

## 8. Check the RTC survived sleep  ← the open experiment

This answers PLAN.md open item #3 and decides whether quick-note timestamps can
ever be trusted.

- [ ] Set the clock (task 6) and note the real time
- [ ] **Unplug USB** so deep sleep is actually allowed
- [ ] Menu → Sleep
- [ ] Wait a known interval (10 minutes is plenty)
- [ ] Press WAKE, open Clock, compare against your phone

| Result | Meaning | Action |
|---|---|---|
| Time is correct | RTC survives deep sleep | quick-note gets real timestamps; record it in PLAN.md |
| `RTC UNSET!` or frozen at sleep time | clock resets/pauses | M2 falls back to sync-time anchoring + `[time unknown]` |

- [ ] Record the outcome in `Firmware/PLAN.md` open item #3

---

## 9. Battery-only pass

- [ ] Unplug and power from the LiPo alone
- [ ] Boot → menu shows the **battery** icon, cursor starts on **Quick note**
- [ ] Practice still runs on battery
- [ ] Keyboard app shows `No device connected`

---

## 10. Wrap up

- [ ] Note anything that looked wrong, with the screen and the key involved
- [ ] `git add -A && git commit` — this is a big, working checkpoint and
      nothing has been committed for a long time
- [ ] If moving to the Mac: push, clone there, `chmod +x Firmware/tools/deploy.sh`

---

## Optional cleanups (no functional effect)

- `ter-u14b.bdf` (169 KB, kept only as the subset source) and `ter-u16b.bdf`
  (177 KB, unused spare) sit on the device doing nothing at runtime: 346 KB of
  flash. Both are one-file downloads to restore. Boot time is unaffected.
- A stale `__pycache__/` folder from an earlier compile pass is on the device.
  Harmless; CircuitPython ignores it.

## Known-incomplete (not bugs)

- **Quick note** and **Vault** are still stubs ("Not built yet") — M2 work.
- **Nothing renders kanji any more.** The vault reader will need a
  kanji-capable font regenerated first (recipes in `src/fonts/README.md`).
- **Practice settings reset once** on this deploy — the nvm format version
  changed, so the old blob is deliberately rejected rather than misread.
