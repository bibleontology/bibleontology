"""Round 2 of the card layouts (Doug, 2026-11-21): "great layouts but don't throw away the things that are on the
existing cards and make them great: just make sure it fits in the right, consistent, logical location to tell the
story, and removing the redundancy and any meaningless slop". Round 1 read the page copies, which are the server's
text page, not the app's card face: the Navigator button, a hub's sections and the paths to the original-language
cards never reached it.

    python -X utf8 tools/pending/layout_faces.py faces     (from PowerShell: Edge renders empty from Git Bash)
        -> out/layouts/<id>.face.txt: the app's real card face, headings, controls and links, in order
    python -X utf8 tools/pending/layout_faces.py briefs    -> out/layouts/<type>.round2.txt
"""
import html as H
import re
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "pending"))
D = ROOT / "out" / "layouts"


class Face(HTMLParser):
    """the card's text in order, with headings marked, links shown as [text -> where], buttons as (button: text)"""
    SKIP = {"script", "style", "svg", "head", "noscript"}

    def __init__(self):
        super().__init__(); self.out, self.skip, self.a = [], 0, []

    def handle_starttag(self, tag, at):
        at = dict(at)
        if tag in self.SKIP:
            self.skip += 1; return
        if self.skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "summary"):
            self.out.append("\n## " if tag != "summary" else "\n▸ ")
        elif tag in ("p", "li", "div", "section", "br", "tr", "details"):
            self.out.append("\n")
        if tag == "a":
            self.a.append(at.get("href") or at.get("data-go") or at.get("data-ent") or "")
            self.out.append("[")
        if tag == "button":
            self.out.append("(button: ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1; return
        if self.skip:
            return
        if tag == "a" and self.a:
            self.out.append(f" -> {self.a.pop()}]")
        if tag == "button":
            self.out.append(")")

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)


def faces():
    import card_conservation as C
    from layout_pass import TYPES
    prof = tempfile.mkdtemp(prefix="edge-faces-")
    for ty, ids in TYPES.items():
        for cid in ids:
            dom = C.render(cid, prof)
            if not dom or len(dom) < 2000:
                print("EMPTY", cid); continue
            m = re.search(r'<main.*?</main>', dom, re.S) or re.search(r"<body.*?</body>", dom, re.S)
            p = Face(); p.feed(m.group(0))
            t = H.unescape("".join(p.out))
            t = re.sub(r"[ \t]+", " ", t); t = re.sub(r"\n\s*\n+", "\n", t).strip()
            (D / f"{cid}.face.txt").write_text(t, encoding="utf-8")
            print(cid, len(t))


RULES = """ROUND 2. The owner liked the first layouts ("these cards look very good") and set these rules for the second:
1. NOTHING MEANINGFUL IS THROWN AWAY. Below is each card's REAL face as the app renders it today, every section,
   control and link in order. Every item must be placed in the new layout or listed as dropped with a reason, and the
   only allowed reasons are: (a) it repeats something already placed (say where), or (b) it is meaningless slop (say
   why). A rich hub card (many sections) keeps its richness: re-ordered and grouped, not thinned.
2. The "Show in Navigator" button (the graph view) stays, visible on the first screen or directly under it.
3. A PROMINENT path to the original-language word cards (/word/H... and /word/G..., the Hebrew and Greek behind the
   card) on the first screen, wherever the card has them.
4. Consistent: the same kind of thing sits in the same place on every card type (identity, then the answer, then
   the verses, then the connections, then readings, then everything else), adapted to the type, never reinvented.
5. Tell the card's story in a logical order; remove redundancy; keep the first phone screen answering the question
   a visitor came with.
6. WHAT MAKES A CARD DISTINCT IS KEPT. Some cards have a design of their own that fits their content: the Fruit of
   the Spirit card shows the nine in the text's order around one fruit; a hub shows its words grouped as noun, verb
   and adjective with the Hebrew and Greek behind them; an image card has its sketch. The owner: "I don't want to
   throw away the things that make the current cards distinct ... cards like that should be recognized with the
   strengths preserved." Name each such feature on the real faces below and keep it as it is, at the place it
   serves best. The common layout is a frame AROUND a distinct design, never a replacement for it.

Return, at most 1,300 words:
- the sections in order, each with what it holds, default vs behind "more";
- the first phone screen as a plain-text mockup with the real content of the first card, showing the Navigator
  button and the original-language path;
- THE INVENTORY: every heading, control and link group from BOTH real faces below, one line each: "kept → section N",
  "merged into section N (repeat of ...)", or "dropped: slop because ...";
- what changed from your round-1 layout (also below), one line each."""


def outline(t, cap=40000):
    """a long face (Mercy 52k, Faith 99k) cut to fit: every heading and drawer kept, each with its first 3 lines; the
    per-book verse lists collapsed to their headings. Whole if it fits."""
    if len(t) <= cap:
        return t
    out, n = [], 0
    for ln in t.split("\n"):
        if ln.count("(button:") > 3:          # a row of verse chips: one line says it
            out.append(f"  [{ln.count('(button:')} verse chips]"); continue
        if ln.startswith(("## ", "▸ ")) or "(button:" in ln or "Navigator" in ln:
            if re.search(r"· \d+ verses? with its words$", ln):
                n = 99; out.append(ln); continue
            out.append(ln); n = 0
        elif n < 3:
            out.append(ln[:220]); n += 1
    s = "\n".join(out)
    return s if len(s) <= cap else s[:cap] + "\n[... the face continues; every heading above is in order]"


def briefs():
    from layout_pass import TYPES, PRINCIPLES
    for ty, ids in TYPES.items():
        faces_txt = "\n\n".join(f"===== REAL CARD FACE: {cid} =====\n{outline((D / f'{cid}.face.txt').read_text(encoding='utf-8'))}"
                                for cid in ids if (D / f"{cid}.face.txt").exists())
        r1 = re.sub(r"^\{.*?\n\}\n", "", (D / f"{ty}.layout.txt").read_text(encoding="utf-8"), flags=re.S | re.M)
        brief = f"{PRINCIPLES}\nYou are the lead designer for cards of type \"{ty}\".\n\n{RULES}\n\n===== YOUR ROUND-1 LAYOUT =====\n{r1}\n\n{faces_txt}"
        (D / f"{ty}.round2.txt").write_text(brief, encoding="utf-8", newline="\n")
        print(ty, len(brief))


if __name__ == "__main__":
    {"faces": faces, "briefs": briefs}[sys.argv[1]]()
