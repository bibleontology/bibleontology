"""WHERE THE BEREAN PRINTS SPEECH (the committee's third sitting, D1; ruled
2026-10-20 "all as recommended"): which verses, and which words in them, its
editors set inside quotation marks.

A statement lifted from a clause went out in the narrator's voice whenever the
structure layer had no speaker on record for it, so a character's words were
published as the text's own fact: Job 23:16 "God terrified Job" (Job
speaking), Isa 38:12 (Hezekiah's writing), John 3:16 (inside Jesus's words to
Nicodemus as the Berean marks them, 3:10-21). The Berean's editors have
already decided where speech runs; this reads their marks, as a reason to HOLD
a statement (reversible), never to credit it to anyone.

  berean_quotes() -> ({"John 3:16": "whole" | "part" | None}, {ref: text})
  verb_side(label, texts) -> "inside" | "outside" | "unknown"

A quotation is tracked as open or closed, not counted: the Berean's poetry
reopens a quotation at each stanza without closing the last (Job 23:2 on).
Inner quotations (single marks) are inside the outer one already.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BSB = ROOT / "data" / "bible" / "verses.bsb.jsonl"

# the English past forms the Berean uses where the verb's plain form is not a
# prefix of them (the label is the plain form: "see", "give a drink")
IRREGULAR = {"see": ["saw", "seen", "see"], "give": ["gave", "given", "give"], "go": ["went", "gone", "go"],
             "come": ["came", "come"], "take": ["took", "taken", "take"], "bear": ["bore", "born", "borne", "bear",
             "birth"], "find": ["found", "find"], "send": ["sent", "send"], "say": ["said", "say"],
             "tell": ["told", "tell"], "make": ["made", "make"], "bring": ["brought", "bring"],
             "eat": ["ate", "eaten", "eat"], "know": ["knew", "known", "know"], "hear": ["heard", "hear"],
             "leave": ["left", "leave"], "strike": ["struck", "strike"], "slay": ["slew", "slain", "slay"],
             "rise": ["rose", "risen", "rise"], "speak": ["spoke", "spoken", "speak"], "stand": ["stood", "stand"],
             "sit": ["sat", "sit"], "build": ["built", "build"], "lead": ["led", "lead"], "buy": ["bought", "buy"],
             "sell": ["sold", "sell"], "keep": ["kept", "keep"], "feed": ["fed", "feed"], "flee": ["fled", "flee"],
             "fight": ["fought", "fight"], "hold": ["held", "hold"], "lay": ["laid", "lay"],
             "pay": ["paid", "pay"], "seek": ["sought", "seek"], "teach": ["taught", "teach"],
             "throw": ["threw", "thrown", "throw"], "write": ["wrote", "written", "write"],
             "father": ["fathered", "father"], "beget": ["begot", "begotten", "fathered"],
             "love": ["loved", "love"], "hate": ["hated", "hate"], "die": ["died", "dead", "die"],
             "kill": ["killed", "kill"], "put": ["put"], "set": ["set"], "cut": ["cut"], "hit": ["hit"],
             "fall": ["fell", "fallen", "fall"], "forsake": ["forsook", "forsaken", "forsake"],
             "forget": ["forgot", "forgotten", "forget"], "forgive": ["forgave", "forgiven", "forgive"],
             "meet": ["met", "meet"], "feel": ["felt", "feel"], "begin": ["began", "begun", "begin"],
             "pass": ["passed", "pass"], "clothe": ["clothed", "clothe"], "answer": ["answered", "answer"],
             "bless": ["blessed", "bless"], "lose": ["lost", "lose"], "shoot": ["shot", "shoot"],
             "swear": ["swore", "sworn", "swear"], "tear": ["tore", "torn", "tear"], "wear": ["wore", "worn", "wear"],
             "weep": ["wept", "weep"], "sleep": ["slept", "sleep"], "sweep": ["swept", "sweep"],
             "bind": ["bound", "bind"], "hide": ["hid", "hidden", "hide"], "ride": ["rode", "ridden", "ride"],
             "drink": ["drank", "drunk", "drink"], "sing": ["sang", "sung", "sing"], "spread": ["spread"],
             "shut": ["shut"], "let": ["let"], "become": ["became", "become"], "choose": ["chose", "chosen", "choose"],
             "draw": ["drew", "drawn", "draw"], "drive": ["drove", "driven", "drive"], "grow": ["grew", "grown", "grow"],
             "steal": ["stole", "stolen", "steal"], "break": ["broke", "broken", "break"], "deal": ["dealt", "deal"],
             "dwell": ["dwelt", "dwell"], "lend": ["lent", "lend"], "light": ["lit", "light"]}


def berean_quotes():
    quotes, texts, state, book = {}, {}, False, None
    for line in open(BSB, encoding="utf-8"):
        r = json.loads(line)
        if "b" not in r:
            continue
        if r["b"] != book:
            book, state = r["b"], False
        ins = outs = 0
        for ch in r["t"]:
            if ch == "“":
                state = True
            elif ch == "”":
                state = False
            elif ch.isalpha():
                if state:
                    ins += 1
                else:
                    outs += 1
        ref = f"{r['b']} {r['c']}:{r['v']}"
        quotes[ref] = "whole" if ins and not outs else ("part" if ins else None)
        texts[ref] = (r["t"], state)
    return quotes, texts


def _states(text):
    """Each word of a verse with whether it stands inside a quotation. The
    state the verse opens in is the one the previous verse closed in."""
    t, _end = text if isinstance(text, tuple) else (text, False)
    return t


def verb_side(label, texts, opens=None):
    """Where the verb's English word stands in a partly quoted verse: inside
    the quotation, outside it, or unknown (not found, or found on both sides).
    `texts` are (text, state-at-end) pairs; the state a verse opens in is not
    needed for a part verse (it holds both), so the marks inside it decide."""
    words = (label or "").split()
    if not words:
        return "unknown"
    lemma = words[0].lower()
    forms = IRREGULAR.get(lemma, [lemma])
    stem = lemma[:-1] if lemma.endswith("e") and len(lemma) > 3 else lemma
    if lemma.endswith("y") and len(lemma) > 3:
        stem = lemma[:-1]          # carry -> carri(ed)
    sides, past = set(), set()
    plain = {lemma}
    for text in texts:
        t = text[0] if isinstance(text, tuple) else text
        # the state at the verse's start: open if its first quote mark is a
        # closing one (the quotation runs in from the verse before)
        first = re.search("[“”]", t)
        state = bool(first and first.group() == "”")
        for m in re.finditer(r"[“”]|[A-Za-z']+", t):
            tok = m.group()
            if tok == "“":
                state = True
            elif tok == "”":
                state = False
            else:
                w = tok.lower()
                if w in forms or (len(stem) >= 3 and w.startswith(stem) and len(w) <= len(stem) + 4):
                    side = "inside" if state else "outside"
                    sides.add(side)
                    # a past form ("sent", "approached") is how the narrator
                    # tells it; the plain form in a quotation is a command
                    # ("Send me Uriah"), so where both sides hold the verb,
                    # the past form decides (2 Sam 11:6)
                    if w not in plain and (w.endswith(("ed", "d")) or (w in forms and w != lemma)):
                        past.add(side)
    if len(sides) == 1:
        return sides.pop()
    if len(past) == 1:
        return past.pop()
    return "unknown"
