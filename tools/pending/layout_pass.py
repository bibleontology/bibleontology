"""DeepSeek proposes card layouts for the card types without a ruled one (Doug, 2026-11-20: "In think mode, could
DeepSeek propose card layouts for the other types? With some simple design principles and maybe its own specialized
personas, I am hoping it can get close.").

    python -X utf8 tools/pending/layout_pass.py build    -> out/layouts/<type>.<persona>.txt and <type>.reconcile.txt
    bash tools/pending/layout_run.sh                     sends them, think mode, resumable (personas first, then reconcile)

Each type gets two real cards as the live site prints them (from the built copies, out/pages/site/e/), four persona
readings, then one reconciling call that sees the four and returns the proposal. Proposals only: nothing is built
from them without Doug's look.
"""
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "out" / "pages" / "site" / "e"
OUT = ROOT / "out" / "layouts"
TYPES = {
    "person": ["ruth", "barnabas"],
    "place": ["bethel", "capernaum"],
    "concept": ["mercy", "faith"],
    "group": ["pharisees", "levites"],
    "object": ["ark_of_the_covenant", "altar"],
    "image": ["image_lamp", "image_temple"],
    "saying": ["fruit_of_the_spirit", "gen_22_7_abraham_response"],
    "message": ["msg_be_holy", "msg_abide_in_me"],
}
PERSONAS = {
    "visitor": "someone who arrived from a web search with one plain question about this person, place or idea, "
               "reading on a phone, who will leave within ten seconds if the first screen does not answer it",
    "teacher": "a Bible-study leader preparing next week's lesson, who wants the key passages, how they connect, and "
               "something worth discussing, without having to dig",
    "scholar": "a careful reader who checks claims: wants to see exactly which verse supports each statement, what is "
               "the text's own statement and what is a reading, and where the evidence is thin",
    "designer": "a mobile UI designer who has to fit all of this on a 375-pixel-wide screen with clear hierarchy, "
                "few levels, nothing repeated, and an obvious next step",
}
PRINCIPLES = """The site is a free Bible explorer built on a knowledge graph of the Berean Standard Bible: people,
places, ideas, sayings and events, each with relations to others, and every relation cites the verse that states it.
Design principles for every card:
1. Answer first. The first phone screen says what this is and the one or two things most readers came for.
2. Nothing twice. Each fact appears once, in the one section where it belongs; no section repeats another.
3. Every fact is tied to its verse, one tap away.
4. Keep much, show little. Strongest items by default; the rest behind a clear "more" that always opens.
5. The graph stays visible. The reader should sense it is moving through connections, not reading an article.
6. The text's own statements are kept apart from readings (interpretations), which are marked as such.
7. No doctrinal position: describe what the text says and who reads it how, never which reading is right.
8. Never hide a thin card; give it its verses and an obvious way on.
"""


class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.out, self.skip = [], 0

    def handle_starttag(self, tag, a):
        if tag in ("script", "style", "head", "nav", "footer"):
            self.skip += 1
        elif tag in ("h1", "h2", "h3", "h4"):
            self.out.append("\n## ")
        elif tag in ("p", "li", "div", "section", "br", "tr"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head", "nav", "footer") and self.skip:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)


def card_text(cid):
    f = SITE / f"{cid}.html"
    if not f.exists():
        return None
    p = Text(); p.feed(f.read_text(encoding="utf-8"))
    t = html.unescape("".join(p.out))
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t).strip()
    return t[:9000]


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for ty, ids in TYPES.items():
        cards = [(c, card_text(c)) for c in ids]
        cards = [(c, t) for c, t in cards if t]
        shown = "\n\n".join(f"===== CARD: {c} (as the live page prints it, text only) =====\n{t}" for c, t in cards)
        for pk, pv in PERSONAS.items():
            brief = f"""{PRINCIPLES}
You are {pv}.

Below are two real cards of the type "{ty}" as they print today (text only; the layout is lost, the order is kept).

{shown}

From your point of view, for ANY card of type "{ty}" (not just these two):
1. What questions does this kind of card have to answer for you, in order of importance?
2. What on today's cards serves you, what is in your way, what is said twice, and what is missing?
3. Propose the card's layout: the sections in order, what each holds, what shows by default and what sits behind
   "more". Mark the first phone screen. Use the real content above to show it.
Be concrete and brief: headings and short lines, no general essay. At most 700 words."""
            (OUT / f"{ty}.{pk}.txt").write_text(brief, encoding="utf-8", newline="\n"); n += 1
        (OUT / f"{ty}.cards.txt").write_text(shown, encoding="utf-8", newline="\n")
    print(n, "persona briefs ->", OUT.relative_to(ROOT))


def reconcile(ty):
    parts = [f"===== {pk.upper()} =====\n" + (OUT / f"{ty}.{pk}.answer.txt").read_text(encoding="utf-8")
             for pk in PERSONAS]
    shown = (OUT / f"{ty}.cards.txt").read_text(encoding="utf-8")
    return f"""{PRINCIPLES}
You are the lead designer. Four reviewers each proposed a layout for cards of type "{ty}". Their proposals, then the
two real cards they looked at:

{chr(10).join(parts)}

{shown}

Produce ONE layout for every card of type "{ty}":
- the sections in order, each with what it holds, what shows by default, what sits behind "more";
- the first phone screen marked, drawn as a plain-text mockup using the real content of the first card;
- where the reviewers disagreed, what you chose and why, in one line each;
- what today's cards hold that this layout drops or moves, so nothing meaningful is lost (list every item);
- anything the layout needs that the cards do not hold today (data the graph would have to add).
At most 1,000 words."""


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build()
    elif sys.argv[1] == "reconcile":
        print(reconcile(sys.argv[2]))
