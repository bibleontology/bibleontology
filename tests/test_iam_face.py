"""The I AM card's face (app2/iam_face.py), checked on the fixture alone: no graph is needed (2026-10-31).
Written before the face, as its acceptance test; the face's author may not change it.

    python -X utf8 tests/test_iam_face.py

What it holds the face to:
  - everything the data holds is shown, and nothing it does not hold: every item's verse, link, speaker and original
    words; no link but to the data's own verses and words; no link to any card (a divine person is never linked)
  - the groups the data marks shown are open on the face, the rest are folded in <details>, each with its count
  - every string is escaped: planted markup in the data never becomes markup
  - the sketch is a plain line drawing of a bush on fire: no text, figure, face, image or script in it
  - phone width, the app's color tokens, American spelling
"""
import copy
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import iam_face  # noqa: E402

DATA = json.loads((ROOT / "tests" / "fixtures" / "iam_card.json").read_text(encoding="utf-8"))
fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


def esc(s):
    return html.escape(s, quote=False)


def faults(data, out, svg, css):
    f = []
    # what a reader sees: tags out, entities read (a face may bold the words inside a verse)
    plain = html.unescape(re.sub(r"<[^>]+>", "", out))
    allowed = {f"/p/{i['go']}" for g in data["groups"] for i in g["items"]}
    allowed |= {f"/p/{i['after']['go']}" for g in data["groups"] for i in g["items"] if i.get("after")}
    allowed |= {f"/p/{data['lede']['go']}", f"/p/{data['sketch']['go']}"}
    for p in data["pairs"]:
        for s in ("a", "b"):
            allowed.add(f"/p/{p[s]['go']}")
            allowed |= {w["addr"] for w in p[s]["words"]}
    for h in re.findall(r'href="([^"]*)"', out):
        if h not in allowed:
            f.append(f"a link the data does not hold: {h}")
    # the lede first, then the groups in the data's order, each once
    lede_at = out.find(f'href="/p/{data["lede"]["go"]}"')
    if lede_at < 0 or data["lede"]["text"] not in plain:
        f.append("the lede verse is not quoted with its link")
    at = lede_at
    for g in data["groups"]:
        tag = "section" if g["shown"] else "details"
        m = re.search(r'<%s\b[^>]*\bdata-group="%s"[^>]*>' % (tag, re.escape(g["id"])), out)
        if not m:
            f.append(f"group {g['id']}: no <{tag} data-group=\"{g['id']}\">")
            continue
        if f'data-count="{len(g["items"])}"' not in m.group(0):
            f.append(f"group {g['id']}: data-count is not {len(g['items'])}")
        if m.start() < at:
            f.append(f"group {g['id']}: out of order (or before the lede)")
        at = m.start()
        if g["title"] not in plain:
            f.append(f"group {g['id']}: its title is not shown")
        for i in g["items"]:
            if f'href="/p/{i["go"]}"' not in out:
                f.append(f"{i['ref']}: no link to /p/{i['go']}")
            if i["text"] not in plain:
                f.append(f"{i['ref']}: the verse is not quoted whole")
            if i["who"] not in plain:
                f.append(f"{i['ref']}: the speaker is not shown")
            if i.get("image") and i["image"] not in plain:
                f.append(f"{i['ref']}: the image is not shown")
            if i.get("after") and i["after"]["text"] not in plain:
                f.append(f"{i['ref']}: the verse after is not quoted")
            for w in i["words"]:
                if w["t"] not in plain:
                    f.append(f"{i['ref']}: the original word {w['t']} is not shown")
    if 'lang="he"' not in out or 'dir="rtl"' not in out or 'lang="grc"' not in out:
        f.append("original words are not marked lang=\"he\" dir=\"rtl\" / lang=\"grc\"")
    for p in data["pairs"]:
        if "data-pair" not in out or p["words"] not in plain:
            f.append("the pair is not shown in an element marked data-pair")
        for s in ("a", "b"):
            if p[s]["text"] not in plain:
                f.append(f"pair: {p[s]['ref']} is not quoted whole")
    # the name plate (round 2, 2026-10-31: the first face opened on the sketch with no name)
    m = re.search(r'<h1 class="iam-name"[^>]*>(.*?)</h1>', out, re.S)
    if not m or html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() != data["name"]:
        f.append("no name plate: <h1 class=\"iam-name\"> holding the card's name")
    elif 0 <= out.find(svg) < m.start():
        f.append("the name plate is not above the sketch")
    # the sketch
    if svg not in out:
        f.append("the face does not carry bush_svg()")
    if data["sketch"]["text"] not in plain:
        f.append("the sketch's verse (Exodus 3:2) is not quoted under it")
    if not re.match(r"\s*<svg\b[^>]*\bviewBox=", svg) or not svg.rstrip().endswith("</svg>"):
        f.append("bush_svg() is not one <svg> with a viewBox")
    if len(re.findall(r"<path\b", svg)) < 8:
        f.append("bush_svg() has fewer than 8 paths (a bush needs branches as well as flames)")
    if re.search(r"<(text|image|use|foreignObject|script|a)\b", svg, re.I):
        f.append("bush_svg() has text, an image, a link or a script in it")
    if re.search(r"face|figure|person|eye|man\b|god|lord", svg, re.I):
        f.append("bush_svg() names a figure")
    if 'role="img"' not in svg or "aria-label=" not in svg:
        f.append("bush_svg() has no role=\"img\" and aria-label")
    if len(svg) > 8000:
        f.append(f"bush_svg() is {len(svg)} characters (8000 at most)")
    # nothing that runs, loads or links out
    for bad in (r"<script", r"<iframe", r"<img\b", r"<image\b", r"<object", r"<embed", r"javascript:", r"https?://",
                r"url\(", r"@import", r"/e/"):
        if re.search(bad, out + css, re.I):
            f.append(f"forbidden in the face or its CSS: {bad}")
    if re.search(r"<[^>]*\son[a-z]+\s*=", out, re.I):
        f.append("an on…= handler in a tag")
    # the CSS: scoped, the app's tokens, phone width
    for rule in re.findall(r"([^{}]+)\{", css):
        if not all(s.strip().startswith(".iam") or s.strip().startswith("@") for s in rule.split(",")):
            f.append(f"a CSS rule not scoped under .iam: {rule.strip()[:60]}")
            break
    if re.search(r"#[0-9a-f]{3,8}\b|rgb\(|hsl\(", css, re.I):
        f.append("a fixed color in the CSS: use the app's var(--…) tokens")
    for w in re.findall(r"(?:^|[;{\s])(?:min-)?width\s*:\s*(\d+)px", css):
        if int(w) > 343:
            f.append(f"a width of {w}px (343 at most: a 375px phone less its gutters)")
    if re.search(r"\b(colour|honour|centre|favour|judgement|grey|behaviour)", out + css, re.I):
        f.append("British spelling")
    if not out.lstrip().startswith('<div class="iam'):
        f.append("the face is not one <div class=\"iam…\"> fragment")
    if len(out) > 120000:
        f.append(f"the face is {len(out)} characters (120000 at most)")
    return f


out = iam_face.render(DATA)
svg = iam_face.bush_svg()
css = iam_face.CSS
for x in faults(DATA, out, svg, css):
    check(False, x)
check(out == iam_face.render(copy.deepcopy(DATA)), "render is not deterministic")

# ---- planted faults: the check must catch each, and the face must survive the hostile data
planted = 0
d2 = copy.deepcopy(DATA)
d2["groups"][2]["items"][0]["text"] = 'It is I. <script>alert(1)</script>'
d2["groups"][2]["items"][1]["who"] = 'Jesus" onmouseover="alert(1)'
d2["groups"][3]["items"][0]["image"] = "<img src=x onerror=alert(1)>"
o2 = iam_face.render(d2)
check("<script" not in o2.lower() and "<img" not in o2.lower() and not re.search(r"<[^>]*\son[a-z]+\s*=", o2, re.I),
      "planted markup in the data became markup")
check(not faults(d2, o2, svg, css), "the hostile data's face fails the check: " + "; ".join(faults(d2, o2, svg, css))[:300])
for what, bad in [
    ("a dropped item", out.replace(f'href="/p/{DATA["groups"][2]["items"][5]["go"]}"', 'href="#"')),
    ("an invented link", out.replace("</div>", '<a href="/p/Gen.1.1">x</a></div>', 1)),
    ("a link to a card", out.replace("</div>", '<a href="/e/god">God</a></div>', 1)),
    ("a shown group folded", out.replace('<section', '<details', 1)),
    ("no name plate", re.sub(r'<h1 class="iam-name"[^>]*>.*?</h1>', "", out, flags=re.S)),
]:
    planted += 1
    check(bool(faults(DATA, bad, svg, css)), f"planted: the check did not catch {what}")
for what, s in [("text in the sketch", svg.replace("</svg>", "<text>x</text></svg>")),
                ("a figure in the sketch", svg.replace("<path", '<path class="figure"', 1))]:
    planted += 1
    check(bool(faults(DATA, out.replace(svg, s), s, css)), f"planted: the check did not catch {what}")
planted += 1
check(bool(faults(DATA, out, svg, css + ".iam .x{color:#f00}")), "planted: the check did not catch a fixed color")

for m in fails:
    print("FAIL", m)
print(f"I AM face: {sum(len(g['items']) for g in DATA['groups'])} items in {len(DATA['groups'])} groups, "
      f"{len(out)} characters; planted faults caught: {planted - sum(1 for m in fails if m.startswith('planted'))} of {planted}; "
      f"{len(fails)} failures")
sys.exit(1 if fails else 0)
