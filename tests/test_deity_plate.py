"""The four divine-person cards' shared header (app2/deity_face.py), checked on the fixture alone (2026-10-31).
Written before the code, as its acceptance test; its author may not change it.

    python -X utf8 tests/test_deity_plate.py
"""
import copy
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import deity_face  # noqa: E402
from deity_sketches import SKETCHES  # noqa: E402

CARDS = json.loads((ROOT / "tests" / "fixtures" / "deity_plates.json").read_text(encoding="utf-8"))
fails = []


def faults(c, out, css):
    f = []
    plain = html.unescape(re.sub(r"<[^>]+>", "", out))
    if not out.lstrip().startswith('<header class="deity'):
        f.append(f"{c['id']}: not one <header class=\"deity…\"> fragment")
    m = re.search(r'<h1 class="deity-name"[^>]*>(.*?)</h1>', out, re.S)
    if not m or html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() != c["name"]:
        f.append(f"{c['id']}: no <h1 class=\"deity-name\"> holding the name")
    if SKETCHES[c["sketch"]] not in out:
        f.append(f"{c['id']}: the sketch {c['sketch']} is not carried verbatim")
    if c["text"] not in plain or f'href="/p/{c["go"]}"' not in out or c["ref"] not in plain:
        f.append(f"{c['id']}: the verse is not quoted whole with its linked reference")
    for h in re.findall(r'href="([^"]*)"', out):
        if h != f"/p/{c['go']}":
            f.append(f"{c['id']}: a link the data does not hold: {h}")
    for bad in (r"<script", r"<img\b", r"<image\b", r"<iframe", r"javascript:", r"https?://", r"url\(", r"@import", r"/e/"):
        if re.search(bad, out + css, re.I):
            f.append(f"forbidden: {bad}")
    if re.search(r"<[^>]*\son[a-z]+\s*=", out, re.I):
        f.append("an on…= handler")
    for rule in re.findall(r"([^{}]+)\{", css):
        if not all(s.strip().startswith(".deity") or s.strip().startswith("@") for s in rule.split(",")):
            f.append(f"a CSS rule not scoped under .deity: {rule.strip()[:50]}")
            break
    if re.search(r"#[0-9a-f]{3,8}\b|rgb\(|hsl\(", css, re.I):
        f.append("a fixed color in the CSS: use the app's var(--…) tokens")
    for w in re.findall(r"(?:^|[;{\s])(?:min-)?width\s*:\s*(\d+)px", css):
        if int(w) > 343:
            f.append(f"a width of {w}px (343 at most)")
    if re.search(r"\b(colour|honour|centre|favour|grey)", out + css, re.I):
        f.append("British spelling")
    return f


css = deity_face.CSS
outs = {}
for c in CARDS:
    outs[c["id"]] = deity_face.plate(c)
    fails += faults(c, outs[c["id"]], css)
    if deity_face.plate(copy.deepcopy(c)) != outs[c["id"]]:
        fails.append(f"{c['id']}: not deterministic")
# the four are one family: the same markup with only the data changed
shapes = {re.sub(r">[^<]*<", "><", re.sub(r'(href|aria-label|d|viewBox)="[^"]*"', "", re.sub(r"<svg\b.*?</svg>", "<svg/>", o, flags=re.S)))
          for o in outs.values()}
if len(shapes) != 1:
    fails.append("the four headers differ in structure, not only in their data")
# hostile data stays text
h = dict(CARDS[0], name='God<script>alert(1)</script>', text='x" onmouseover="alert(1)')
o = deity_face.plate(h)
if "<script" in o.lower() or re.search(r"<[^>]*\son[a-z]+\s*=", o, re.I):
    fails.append("planted markup in the data became markup")
# planted faults the check must catch
planted, c0, o0 = 0, CARDS[0], outs[CARDS[0]["id"]]
for what, bad, bcss in [("no name", re.sub(r'<h1 class="deity-name"[^>]*>.*?</h1>', "", o0, flags=re.S), css),
                        ("a card link", o0.replace("</header>", '<a href="/e/god">x</a></header>'), css),
                        ("a fixed color", o0, css + ".deity .x{color:#f00}"),
                        ("the sketch dropped", o0.replace(SKETCHES[c0["sketch"]], ""), css)]:
    planted += 1
    if not faults(c0, bad, bcss):
        fails.append(f"planted: the check did not catch {what}")
for m in fails:
    print("FAIL", m)
print(f"deity plates: {len(CARDS)} cards; planted faults caught: {planted - sum(1 for m in fails if m.startswith('planted'))} "
      f"of {planted}; {len(fails)} failures")
sys.exit(1 if fails else 0)
