"""The drill loop — DJT Kana mechanics on our event queue.

Deck: Fisher-Yates shuffle, draw from front, no immediate repeats, reshuffle
when exhausted. Wrong answer: re-insert the missed kana at queue positions 3
and 13 (DJT's spaced re-drill). Score: correct-first-try / total-answered.

Screen (geometry in layout.DRILL_*): enabled types stacked down the left,
score as a vertical fraction on the right, typed romaji in a 3-slot box
beneath it, and the whole middle band for the prompt glyph.

Miss feedback: the correct reading appears under the prompt and your wrong
input stays in the box, so you can see both at once. It clears on the next
prompt. The reading NEVER appears in the answer box -- that box shows what you
typed and nothing else, so the two can never be confused.

Correction Type (config):
  Bypass  - a miss reveals the answer; Space/Enter moves on.
  Correct - a miss reveals the answer and you must clear the wrong input and
            type the right one, as the DJT Kana site drills it. Space/Enter
            do NOT skip; the exit key still leaves.
"""
import gc
import random
import time

# Serial-only RAM trace. With PCF the prompt font loads glyphs as they are
# first shown, and the library's glyph cache never evicts -- so free RAM walks
# DOWN as the deck is worked through, and levels off once every kana has been
# seen. That curve is what sizes the eviction floor a 48px prompt needs
# (PLAN.md backlog 3), and it cannot be read from a single number at start.
# Set False when the measurement is done.
DEBUG_RAM = True
RAM_EVERY = 10          # answers between prints

import displayio
from adafruit_display_text import label

from kanatype import input as kt_input
from kanatype import kana as kdata
from kanatype import layout, ui


def _shuffled(items):
    out = list(items)
    for i in range(len(out) - 1, 0, -1):
        j = random.randrange(i + 1)
        out[i], out[j] = out[j], out[i]
    return out


class Screen:
    def __init__(self, cats, font_role, prompt_chars=""):
        self.frame = ui.frame()   # shared: nests with the Menu widget's frames
        if ui.try_font(font_role) is None:
            for fallback in layout.PROMPT_FONTS:      # first installed wins
                if ui.try_font(fallback) is not None:
                    font_role = fallback
                    break
        self.font_role = font_role
        self.adv, self.scale, kana_y = layout.DRILL_PROMPT_STYLES[font_role]

        # The PROMPT font is deliberately NOT preloaded. Under BDF it had to be
        # -- that loader keeps no glyph index, so the first appearance of each
        # kana cost a full rescan of the file (~3.1 s for notosansjp40), which
        # meant paying for every glyph in the deck up front behind a splash.
        # PCF seeks straight to each glyph, so they load in ~ms when first
        # shown and a short session never pays for kana it did not display.
        # (Caveat in PLAN.md: the library's glyph cache never evicts, so a LONG
        # session still converges on the whole deck being resident.)
        #
        # The jp font IS preloaded: it is the score, the answer box and the
        # reveal line, a fixed ~45 ASCII glyphs that every drill shows anyway,
        # and batching them keeps allocation out of the keystroke path.
        ui.preload("".join(cats) + "0123456789abcdefghijklmnopqrstuvwxyz"
                   + layout.DRILL_ANSWER_BLANK, "jp")
        gc.collect()
        print("drill: font %s, deck can show %d kana, %d B free"
              % (font_role, len(set(prompt_chars)), gc.mem_free()))

        uif = ui.font("jp")
        self.group = displayio.Group()

        # left column: enabled types, one per line
        for i, cat in enumerate(cats):
            self.group.append(label.Label(
                uif, text=cat, color=0xFFFFFF,
                x=layout.DRILL_TYPES_X,
                y=layout.DRILL_TYPES_Y0 + i * layout.DRILL_TYPES_PITCH))

        # right column: score as a fraction
        # x is a placeholder: score() right-aligns both on every update.
        self._correct = label.Label(uif, text="", color=0xFFFFFF,
                                    x=layout.DRILL_SCORE_RIGHT, y=layout.DRILL_SCORE_Y)
        self._total = label.Label(uif, text="", color=0xFFFFFF,
                                  x=layout.DRILL_SCORE_RIGHT, y=layout.DRILL_TOTAL_Y)
        self.group.append(self._correct)
        self.group.append(self._total)
        self.group.append(ui.filled_box(*layout.DRILL_SCORE_RULE))

        # right column: typed-answer box
        self.group.append(ui.outline_box(*layout.DRILL_ANSWER_BOX))
        self._answer = label.Label(uif, text="", color=0xFFFFFF,
                                   x=layout.DRILL_ANSWER_X, y=layout.DRILL_ANSWER_Y)
        self.group.append(self._answer)

        # centre: the prompt glyph
        self._kana = label.Label(ui.font(font_role), text="", color=0xFFFFFF,
                                 x=0, y=kana_y, scale=self.scale)
        self.group.append(self._kana)

        # under it: the correct reading, shown only after a miss
        self._miss = label.Label(uif, text="", color=0xFFFFFF,
                                 x=0, y=layout.DRILL_MISS_Y)
        self.group.append(self._miss)

    def score(self, correct, answered):
        # right-aligned inside the 8px-per-digit column
        with self.frame:
            c, t = str(correct), str(answered)
            self._correct.text = c
            self._correct.x = layout.DRILL_SCORE_RIGHT - len(c) * layout.JP_CHAR_W
            self._total.text = t
            self._total.x = layout.DRILL_SCORE_RIGHT - len(t) * layout.JP_CHAR_W

    def kana(self, text):
        """Text and position change together — a torn frame here is what makes
        a 2-kana prompt appear one glyph at a time."""
        with self.frame:
            self._kana.text = text
            width = self.adv * self.scale * len(text)
            self._kana.x = layout.DRILL_PROMPT_CENTER_X - width // 2

    def reveal(self, reading):
        """Show the correct reading after a miss; "" clears it."""
        with self.frame:
            self._miss.text = reading
            width = len(reading) * layout.JP_CHAR_W
            self._miss.x = layout.DRILL_PROMPT_CENTER_X - width // 2

    def answer(self, buf):
        with self.frame:
            slots = layout.DRILL_ANSWER_SLOTS
            self._answer.text = (buf[:slots]
                                 + layout.DRILL_ANSWER_BLANK * (slots - len(buf[:slots])))


def run(ctx, opts):
    cats = [c for c in ("H", "K", "HC", "KC") if opts[c]]
    deck = kdata.build_deck(cats)
    deck_glyphs = len({c for k, _r in deck for c in k})
    # No "Loading..." splash any more: it existed to cover the multi-second
    # glyph preload, and PCF removed the preload.
    scr = Screen(cats, opts["font"], "".join(k for k, _ in deck))
    ctx.display.root_group = scr.group

    queue = _shuffled(deck)
    correct = 0
    answered = 0
    cur = None      # (kana, canonical)
    buf = ""
    wrong = False   # awaiting Space/Enter after a miss

    def next_prompt():
        nonlocal queue, cur, buf, wrong
        if not queue:
            queue = _shuffled(deck)
        i = 1 if (cur and len(queue) > 1 and queue[0][0] == cur[0]) else 0
        cur = queue.pop(i)
        buf = ""
        wrong = False
        with scr.frame:            # prompt + cleared answer box in one frame
            scr.kana(cur[0])
            scr.answer("")
            scr.reveal("")         # drop the previous miss's reading

    def miss():
        nonlocal answered, wrong
        answered += 1
        wrong = True          # buf stays on screen as the only feedback
        trace_ram()
        queue.insert(min(3, len(queue)), cur)
        queue.insert(min(13, len(queue)), cur)
        with scr.frame:
            scr.score(correct, answered)
            scr.reveal(kdata.reveal(cur[1]))   # the point of a miss

    def trace_ram():
        if not (DEBUG_RAM and answered % RAM_EVERY == 0):
            return
        # gc.collect() FIRST. mem_free() on its own reports the free heap
        # including garbage that has not been collected yet, which is a
        # sawtooth: the first version of this trace printed 46/57/59/52/55/50
        # KB over 60 answers and showed the allocator, not the glyph cache.
        gc.collect()
        # Resident glyph COUNT is the direct measurement and needs no
        # inference. GlyphCache._glyphs is private, hence defensive: this is a
        # bring-up readout, not a feature.
        try:
            cached = len(ui.font(scr.font_role)._glyphs)
        except Exception:
            cached = -1
        print("drill: %d answered, %d/%d prompt glyphs, %d B free"
              % (answered, cached, deck_glyphs, gc.mem_free()))

    def hit():
        nonlocal correct, answered
        correct += 1
        answered += 1
        with scr.frame:            # score bump + next prompt land together
            scr.score(correct, answered)
            next_prompt()
        trace_ram()

    with scr.frame:                # first paint arrives complete
        scr.score(0, 0)
        next_prompt()

    while True:
        for ev in ctx.input.poll():
            code = ev.code
            if code == kt_input.EXIT:
                return
            if wrong:
                if not opts.get("correct"):
                    if code in (kt_input.SPACE, kt_input.ENTER):
                        next_prompt()
                    continue
                # Correct mode: the only way out is typing it properly. buf is
                # capped at the box width, so a wrong answer that already fills
                # it forces a backspace before anything else can be entered.
                if code == kt_input.BACKSPACE:
                    buf = buf[:-1]
                    scr.answer(buf)
                elif len(code) == 1 and "a" <= code <= "z":
                    if len(buf) < layout.DRILL_ANSWER_SLOTS:
                        buf += code
                        scr.answer(buf)
                    if buf in kdata.answers(cur[1]):
                        next_prompt()       # corrected; already scored a miss
                continue
            if code == kt_input.HINT:
                # same place a miss shows it -- the answer box is for your
                # own typing only
                scr.reveal(kdata.reveal(cur[1]))
            elif code == kt_input.BACKSPACE:
                buf = buf[:-1]
                scr.answer(buf)
            elif code == kt_input.ENTER and not opts["instant"]:
                if buf:
                    if buf in kdata.answers(cur[1]):
                        hit()
                    else:
                        miss()
            elif len(code) == 1 and "a" <= code <= "z":
                if len(buf) < layout.DRILL_ANSWER_SLOTS:
                    buf += code
                    scr.answer(buf)
                if opts["instant"]:
                    ans = kdata.answers(cur[1])
                    if buf in ans:
                        hit()
                    elif not any(a.startswith(buf) for a in ans):
                        miss()
        time.sleep(0.02)
