"""The drill loop — DJT Kana mechanics on our event queue.

Deck: Fisher-Yates shuffle, draw from front, no immediate repeats, reshuffle
when exhausted. Wrong answer: re-insert the missed kana at queue positions 3
and 13 (DJT's spaced re-drill). Score: correct-first-try / total-answered.

Screen (geometry in layout.DRILL_*): enabled types stacked down the left,
score as a vertical fraction on the right, typed romaji in a 3-slot box
beneath it, and the whole middle band for the prompt glyph.

Miss feedback is deliberately minimal for now — no correction text; your
wrong input simply stays visible in the box until you press Space/Enter.
(Reworking this is a TODO; that's where a flash/invert would go.)
"""
import gc
import random
import time

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

        # ONE pass over each .bdf, up front. The BDF loader keeps no glyph
        # index, so any character it has not cached costs a full rescan of the
        # file -- ~3.1 s for notosansjp40 -- and without this that happens on
        # the FIRST appearance of every kana, mid-drill. (PLAN.md, boot-time
        # work.) load_glyphs skips what it already holds, so re-entering the
        # drill in the same session is free.
        ui.preload(prompt_chars, font_role)
        ui.preload("".join(cats) + "0123456789abcdefghijklmnopqrstuvwxyz"
                   + layout.DRILL_ANSWER_BLANK, "jp")
        # 40px glyph bitmaps are the biggest RAM item in the app (~320 B each,
        # so ~46 KB with all four scripts enabled). Serial only -- this is the
        # number PLAN open item #2 wants.
        gc.collect()
        print("drill: font %s, %d prompt glyphs, %d B free"
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

    def answer(self, buf):
        with self.frame:
            slots = layout.DRILL_ANSWER_SLOTS
            self._answer.text = (buf[:slots]
                                 + layout.DRILL_ANSWER_BLANK * (slots - len(buf[:slots])))


def run(ctx, opts):
    cats = [c for c in ("H", "K", "HC", "KC") if opts[c]]
    deck = kdata.build_deck(cats)
    # Screen() parses every glyph the deck can show, which takes a few seconds
    # with the 40px font; the splash already has "Loading..." baked in.
    ctx.display.root_group = ui.splash_art()
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

    def miss():
        nonlocal answered, wrong
        answered += 1
        wrong = True          # buf stays on screen as the only feedback
        queue.insert(min(3, len(queue)), cur)
        queue.insert(min(13, len(queue)), cur)
        with scr.frame:
            scr.score(correct, answered)

    def hit():
        nonlocal correct, answered
        correct += 1
        answered += 1
        with scr.frame:            # score bump + next prompt land together
            scr.score(correct, answered)
            next_prompt()

    with scr.frame:                # first paint arrives complete
        scr.score(0, 0)
        next_prompt()

    while True:
        for ev in ctx.input.poll():
            code = ev.code
            if code == kt_input.EXIT:
                return
            if wrong:
                if code in (kt_input.SPACE, kt_input.ENTER):
                    next_prompt()
                continue
            if code == kt_input.HINT:
                scr.answer(cur[1])          # reveal in the box, unscored
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
