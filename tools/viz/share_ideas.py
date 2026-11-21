"""THE HEAT MAP'S SHARE IMAGE (Doug, 2026-11-15: "I want to start promoting the new visuals on my own sub, but it needs
to be compelling enough to cause a click"; "I also like that if I want to read a book that discusses joy - it points
to Philippians"). A portrait image, 1200 x 1500, for a Reddit post: a strip of the heat map, a few ideas across all
66 books, each idea's most concentrated book marked and numbered, and the reading guide those marks make.

Drawn only from out/viz/ideas.json (tools/viz/build.py ideas), so every number on it is the view's own; nothing is
added. Rendered to PNG by the installed Edge or Chrome, headless; nothing is installed.

    python tools/viz/share_ideas.py        -> out/viz/share-ideas.html and out/viz/share-ideas.png
"""
import html
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "viz"
# the reading guide: each idea and the book the map says to start with (its most concentrated book with 10 or more
# verses, so a short letter's two verses never leads). Light and darkness share one mark: both peak in Job.
PICKS = ["joy", "redemption", "wisdom", "light", "darkness", "love"]
MIN_VERSES = 10
# LOVE IN BOTH TESTAMENTS (Doug, 2026-11-15: "Song of Solomon is a romantic love but 1 John is about God's agape love"):
# the map marks both: the Hebrew words peak in the Song, the Greek agape in 1 John (7.9x, 30 verses)
# WISDOM IN TWO BOOKS (Doug, the same day: "I would mention Ecclesiastes and Proverbs as they are both very high"):
# Proverbs 5.8x on 106 verses beside Ecclesiastes 8.9x on 43; one row and one number for both (JOIN)
ALSO = {"love": ["1John"], "wisdom": ["Prov"]}
JOIN = {"wisdom"}
WHAT = {("love", "Song of Solomon"): "romantic love", ("love", "1 John"): "agapē love"}
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]


def main():
    d = json.loads((OUT / "ideas.json").read_text(encoding="utf-8"))
    books = d["books"]
    rows = {r["name"]: r for r in d["rows"]}
    W, H = 1200, 1500
    left, cw, ch, top = 215, 14.4, 52, 360
    marks, guide = [], []
    for i, name in enumerate(PICKS):
        r = rows[name]
        best = max(((c["lift"], code) for code, c in r["cells"].items() if c["n"] >= MIN_VERSES), default=None)
        if best:
            bk = next(b for b in books if b["code"] == best[1])
            marks.append((i, books.index(bk), name, bk["name"], best[0], r["cells"][best[1]]["n"]))
        for code in ALSO.get(name, []):
            c = r["cells"].get(code)
            bk = next((b for b in books if b["code"] == code), None)
            if c and bk:
                marks.append((i, books.index(bk), name, bk["name"], c["lift"], c["n"]))
    cells, labels = [], []
    for i, name in enumerate(PICKS):
        y = top + i * ch
        labels.append(f'<text x="{left - 14}" y="{y + ch / 2 + 7}" text-anchor="end" class="row">{html.escape(name)}</text>')
        for j, b in enumerate(books):
            c = rows[name]["cells"].get(b["code"])
            op = 0.05 if not c else (0.08 + 0.92 * max(0.0, min(1.0, math.log2(max(c["lift"], 0.5)) / 3.0))
                                     if c["lift"] > 1 else 0.10)
            col = "#b8237a" if b["nt"] else "#1f5fbf"
            cells.append(f'<rect x="{left + j * cw + .5}" y="{y + .5}" width="{cw - 1}" height="{ch - 2}" rx="2" '
                         f'fill="{col}" fill-opacity="{op:.2f}"/>')
    nt_x = left + next(j for j, b in enumerate(books) if b["nt"]) * cw
    # the numbered marks: a ring round the cell and its number above the strip, shared by light and darkness
    seen, ring, guide_rows, n = {}, [], [], 0
    for i, j, name, book, lift, nv in marks:
        key = name if name in JOIN else book        # an idea in JOIN is one row however many books it names
        if key not in seen:
            n += 1
            seen[key] = n
            guide_rows.append([n, [name], [book], [lift], nv])
        else:
            g = next(g for g in guide_rows if g[0] == seen[key])
            if name not in g[1]:
                g[1].append(name)
            if book not in g[2]:
                g[2].append(book)
            g[3].append(lift)
        x, y = left + j * cw, top + i * ch
        ring.append(f'<rect x="{x - 2}" y="{y - 2}" width="{cw + 3}" height="{ch + 2}" rx="4" fill="none" '
                    f'stroke="#1d1b17" stroke-width="3"/>')
        if name in JOIN:
            # one number over the joined cells (Proverbs and Ecclesiastes are neighbors: two numbers collided)
            mine = [m for m in marks if m[2] == name]
            if mine[0][1] != j:
                continue
            x = left + sum(m[1] for m in mine) / len(mine) * cw
        if not any(m[3] == book and m[0] < i for m in marks):      # one number per book (Job holds two rows)
            ring.append(f'<circle cx="{x + cw / 2}" cy="{y - 18}" r="15" fill="#1d1b17"/>'
                        f'<text x="{x + cw / 2}" y="{y - 12}" text-anchor="middle" class="num">{seen[key]}</text>')
    book_ticks = []
    for code in ("Gen", "Ruth", "Job", "Matt", "Phil", "Rev"):   # the guide names the rest
        j = next((k for k, b in enumerate(books) if b["code"] == code), None)
        if j is not None:
            x = left + j * cw + cw / 2
            book_ticks.append(f'<text x="{x}" y="{top + len(PICKS) * ch + 26}" text-anchor="end" class="tick" '
                              f'transform="rotate(-50 {x} {top + len(PICKS) * ch + 26})">{html.escape(books[j]["name"])}</text>')
    gy = top + len(PICKS) * ch + 205
    guide = []
    for k, (num, names, book, lifts, nv) in enumerate(guide_rows):
        y = gy + k * 84
        what = " and ".join(WHAT.get((nm, book[0]), nm) for nm in names)
        # half up, as a reader rounds (7.85 is 7.9, not the float's 7.8)
        times = " and ".join(f"{math.floor(l * 10 + 0.5) / 10:.1f}\u00d7".replace(".0\u00d7", "\u00d7") for l in lifts)
        guide.append(f'<circle cx="{left - 40}" cy="{y - 10}" r="17" fill="#1d1b17"/><text x="{left - 40}" y="{y - 3}" '
                     f'text-anchor="middle" class="num">{num}</text>'
                     f'<text x="{left}" y="{y}" class="q">Want to read about {html.escape(what)}?</text>'
                     f'<text x="{left}" y="{y + 36}" class="a">Start with {html.escape(" and ".join(book))}</text>'
                     f'<text x="{W - 60}" y="{y + 36}" text-anchor="end" class="m">'
                     f'{times} its usual share</text>')
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<style>
text{{font-family:Georgia,'Times New Roman',serif;fill:#1d1b17}}
.k{{font:600 20px system-ui,sans-serif;letter-spacing:.14em;fill:#6b645a}}
.h{{font-size:58px;font-weight:700}} .s{{font-size:27px;fill:#6b645a}}
.row{{font-size:27px;font-weight:600}} .tick{{font:17px system-ui,sans-serif;fill:#6b645a}}
.num{{font:700 18px system-ui,sans-serif;fill:#fbf8f2}} .q{{font-size:31px}} .a{{font-size:31px;font-weight:700}}
.m{{font:22px system-ui,sans-serif;fill:#6b645a}} .f{{font:22px system-ui,sans-serif;fill:#6b645a}}
.leg{{font:19px system-ui,sans-serif;fill:#6b645a}}
</style>
<rect width="{W}" height="{H}" fill="#fbf8f2"/>
<text x="60" y="92" class="k">BIBLE ONTOLOGY \u00b7 FROM THE HEBREW AND GREEK</text>
<text x="60" y="166" class="h">Where does each big idea</text>
<text x="60" y="232" class="h">live in the Bible?</text>
<text x="60" y="288" class="s">A reading guide drawn from the text itself: each idea’s own words, book by book</text>
{''.join(cells)}
<line x1="{nt_x - .5}" y1="{top - 6}" x2="{nt_x - .5}" y2="{top + len(PICKS) * ch + 4}" stroke="#1d1b17" stroke-width="1.5"/>
{''.join(labels)}{''.join(ring)}{''.join(book_ticks)}
<rect x="{left}" y="{top + len(PICKS) * ch + 122}" width="22" height="8" rx="2" fill="#1f5fbf"/>
<text x="{left + 30}" y="{top + len(PICKS) * ch + 130}" class="leg">Old Testament</text>
<rect x="{left + 190}" y="{top + len(PICKS) * ch + 122}" width="22" height="8" rx="2" fill="#b8237a"/>
<text x="{left + 220}" y="{top + len(PICKS) * ch + 130}" class="leg">New Testament \u00b7 darker: the book gives the idea more of its attention</text>
{''.join(guide)}
<text x="60" y="{H - 92}" class="f">39 ideas across all 66 books, counted from each idea's own Hebrew and Greek words.</text>
<text x="60" y="{H - 58}" class="f">Explore every cell and its verses: bibleontology.org/visual/ideas</text>
</svg>"""
    page = (f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:#fbf8f2}}'
            f'</style></head><body>{svg}</body></html>')
    (OUT / "share-ideas.html").write_text(page, encoding="utf-8")
    (OUT / "share-ideas.svg").write_text(svg, encoding="utf-8")
    exe = next((b for b in BROWSERS if Path(b).exists()), None)
    if not exe:
        sys.exit("no Edge or Chrome to render the PNG; the HTML is at " + str(OUT / "share-ideas.html"))
    png = OUT / "share-ideas.png"
    prof = OUT / ".share-browser-profile"             # its own throwaway profile: a running browser is never touched
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}",
                    f"--user-data-dir={prof}",
                    f"--screenshot={png}", (OUT / "share-ideas.html").as_uri()], check=False, timeout=120,
                   capture_output=True)
    print("guide:", [(g[0], g[1], g[2], [round(x, 1) for x in g[3]], g[4]) for g in guide_rows])
    print("->", png if png.exists() else "(no PNG written)")


if __name__ == "__main__":
    main()
