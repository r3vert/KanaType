"""Kana data — single source of truth for the practice decks.

Row granularity mirrors DJT Kana: basic rows, dakuten rows, digraph combos,
each in hiragana and katakana. Categories: H (hira incl. dakuten),
HC (hira combos), K, KC.
"""

SAMPLE = "あいう アイウ"

# --- rows: (category, row_id, [(kana, canonical_romaji), ...]) --------------
ROWS = [
    ("H", "a", [("あ", "a"), ("い", "i"), ("う", "u"), ("え", "e"), ("お", "o")]),
    ("H", "k", [("か", "ka"), ("き", "ki"), ("く", "ku"), ("け", "ke"), ("こ", "ko")]),
    ("H", "s", [("さ", "sa"), ("し", "shi"), ("す", "su"), ("せ", "se"), ("そ", "so")]),
    ("H", "t", [("た", "ta"), ("ち", "chi"), ("つ", "tsu"), ("て", "te"), ("と", "to")]),
    ("H", "n", [("な", "na"), ("に", "ni"), ("ぬ", "nu"), ("ね", "ne"), ("の", "no")]),
    ("H", "h", [("は", "ha"), ("ひ", "hi"), ("ふ", "fu"), ("へ", "he"), ("ほ", "ho")]),
    ("H", "m", [("ま", "ma"), ("み", "mi"), ("む", "mu"), ("め", "me"), ("も", "mo")]),
    ("H", "y", [("や", "ya"), ("ゆ", "yu"), ("よ", "yo")]),
    ("H", "r", [("ら", "ra"), ("り", "ri"), ("る", "ru"), ("れ", "re"), ("ろ", "ro")]),
    ("H", "w", [("わ", "wa"), ("を", "wo")]),
    ("H", "nn", [("ん", "n")]),
    ("H", "g", [("が", "ga"), ("ぎ", "gi"), ("ぐ", "gu"), ("げ", "ge"), ("ご", "go")]),
    ("H", "z", [("ざ", "za"), ("じ", "ji"), ("ず", "zu"), ("ぜ", "ze"), ("ぞ", "zo")]),
    ("H", "d", [("だ", "da"), ("ぢ", "ji"), ("づ", "zu"), ("で", "de"), ("ど", "do")]),
    ("H", "b", [("ば", "ba"), ("び", "bi"), ("ぶ", "bu"), ("べ", "be"), ("ぼ", "bo")]),
    ("H", "p", [("ぱ", "pa"), ("ぴ", "pi"), ("ぷ", "pu"), ("ぺ", "pe"), ("ぽ", "po")]),
    ("HC", "ky", [("きゃ", "kya"), ("きゅ", "kyu"), ("きょ", "kyo")]),
    ("HC", "sh", [("しゃ", "sha"), ("しゅ", "shu"), ("しょ", "sho")]),
    ("HC", "ch", [("ちゃ", "cha"), ("ちゅ", "chu"), ("ちょ", "cho")]),
    ("HC", "ny", [("にゃ", "nya"), ("にゅ", "nyu"), ("にょ", "nyo")]),
    ("HC", "hy", [("ひゃ", "hya"), ("ひゅ", "hyu"), ("ひょ", "hyo")]),
    ("HC", "my", [("みゃ", "mya"), ("みゅ", "myu"), ("みょ", "myo")]),
    ("HC", "ry", [("りゃ", "rya"), ("りゅ", "ryu"), ("りょ", "ryo")]),
    ("HC", "gy", [("ぎゃ", "gya"), ("ぎゅ", "gyu"), ("ぎょ", "gyo")]),
    ("HC", "j", [("じゃ", "ja"), ("じゅ", "ju"), ("じょ", "jo")]),
    ("HC", "dj", [("ぢゃ", "ja"), ("ぢゅ", "ju"), ("ぢょ", "jo")]),
    ("HC", "by", [("びゃ", "bya"), ("びゅ", "byu"), ("びょ", "byo")]),
    ("HC", "py", [("ぴゃ", "pya"), ("ぴゅ", "pyu"), ("ぴょ", "pyo")]),
    ("K", "a", [("ア", "a"), ("イ", "i"), ("ウ", "u"), ("エ", "e"), ("オ", "o")]),
    ("K", "k", [("カ", "ka"), ("キ", "ki"), ("ク", "ku"), ("ケ", "ke"), ("コ", "ko")]),
    ("K", "s", [("サ", "sa"), ("シ", "shi"), ("ス", "su"), ("セ", "se"), ("ソ", "so")]),
    ("K", "t", [("タ", "ta"), ("チ", "chi"), ("ツ", "tsu"), ("テ", "te"), ("ト", "to")]),
    ("K", "n", [("ナ", "na"), ("ニ", "ni"), ("ヌ", "nu"), ("ネ", "ne"), ("ノ", "no")]),
    ("K", "h", [("ハ", "ha"), ("ヒ", "hi"), ("フ", "fu"), ("ヘ", "he"), ("ホ", "ho")]),
    ("K", "m", [("マ", "ma"), ("ミ", "mi"), ("ム", "mu"), ("メ", "me"), ("モ", "mo")]),
    ("K", "y", [("ヤ", "ya"), ("ユ", "yu"), ("ヨ", "yo")]),
    ("K", "r", [("ラ", "ra"), ("リ", "ri"), ("ル", "ru"), ("レ", "re"), ("ロ", "ro")]),
    ("K", "w", [("ワ", "wa"), ("ヲ", "wo")]),
    ("K", "nn", [("ン", "n")]),
    ("K", "g", [("ガ", "ga"), ("ギ", "gi"), ("グ", "gu"), ("ゲ", "ge"), ("ゴ", "go")]),
    ("K", "z", [("ザ", "za"), ("ジ", "ji"), ("ズ", "zu"), ("ゼ", "ze"), ("ゾ", "zo")]),
    ("K", "d", [("ダ", "da"), ("ヂ", "ji"), ("ヅ", "zu"), ("デ", "de"), ("ド", "do")]),
    ("K", "b", [("バ", "ba"), ("ビ", "bi"), ("ブ", "bu"), ("ベ", "be"), ("ボ", "bo")]),
    ("K", "p", [("パ", "pa"), ("ピ", "pi"), ("プ", "pu"), ("ペ", "pe"), ("ポ", "po")]),
    ("KC", "ky", [("キャ", "kya"), ("キュ", "kyu"), ("キョ", "kyo")]),
    ("KC", "sh", [("シャ", "sha"), ("シュ", "shu"), ("ショ", "sho")]),
    ("KC", "ch", [("チャ", "cha"), ("チュ", "chu"), ("チョ", "cho")]),
    ("KC", "ny", [("ニャ", "nya"), ("ニュ", "nyu"), ("ニョ", "nyo")]),
    ("KC", "hy", [("ヒャ", "hya"), ("ヒュ", "hyu"), ("ヒョ", "hyo")]),
    ("KC", "my", [("ミャ", "mya"), ("ミュ", "myu"), ("ミョ", "myo")]),
    ("KC", "ry", [("リャ", "rya"), ("リュ", "ryu"), ("リョ", "ryo")]),
    ("KC", "gy", [("ギャ", "gya"), ("ギュ", "gyu"), ("ギョ", "gyo")]),
    ("KC", "j", [("ジャ", "ja"), ("ジュ", "ju"), ("ジョ", "jo")]),
    ("KC", "dj", [("ヂャ", "ja"), ("ヂュ", "ju"), ("ヂョ", "jo")]),
    ("KC", "by", [("ビャ", "bya"), ("ビュ", "byu"), ("ビョ", "byo")]),
    ("KC", "py", [("ピャ", "pya"), ("ピュ", "pyu"), ("ピョ", "pyo")]),
]

# Accepted alternative romanizations (DJT 'replacements' equivalent; global,
# so e.g. 'di' is accepted for either ji-kana — same leniency as the site).
VARIANTS = {
    "shi": ("si",),
    "chi": ("ti",),
    "tsu": ("tu",),
    "fu": ("hu",),
    "ji": ("zi", "di"),
    "zu": ("du",),
    "wo": ("o",),
    "n": ("nn",),
    "sha": ("sya",), "shu": ("syu",), "sho": ("syo",),
    "cha": ("tya", "cya"), "chu": ("tyu", "cyu"), "cho": ("tyo", "cyo"),
    "ja": ("jya", "zya", "dya"), "ju": ("jyu", "zyu", "dyu"), "jo": ("jyo", "zyo", "dyo"),
}


def answers(canonical):
    """All accepted romaji spellings for a canonical reading."""
    return (canonical,) + VARIANTS.get(canonical, ())


def build_deck(categories):
    """[(kana, canonical), ...] for the enabled category ids (H/K/HC/KC)."""
    deck = []
    for cat, _row, entries in ROWS:
        if cat in categories:
            deck.extend(entries)
    return deck
