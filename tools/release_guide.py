"""A SIDE-BY-SIDE GUIDE for a release (2026-10-25). Doug: "provide the page for me with a guide with what changes as
I want to do side by sides with the current deployed site as you prepare".

For every card whose rulings changed since the commit the live site runs, it asks both servers how many verses the
card lists (the live site and the local one) and writes a page with the two links side by side, biggest changes
first. Read-only on both: GET /api/entity-verses only.

    python tools/release_guide.py LIVE_COMMIT [--local http://localhost:8012] [--live https://bibleontology.org]
      -> docs/review/release-<date>/GUIDE.md
"""
import collections
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
arg = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
LOCAL, LIVE = arg("--local", "http://localhost:8012"), arg("--live", "https://bibleontology.org")
DATE = time.strftime("%Y-%m-%d")
OUT = ROOT / "docs" / "review" / f"release-{DATE}" / "GUIDE.md"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def address(card):
    """the card's public address: /e/<id> answers 301 to it when a card has one (Doug, 2026-10-25, on the guide's
    first row: image_two_houses opens as house_matt_7_24, and the page read as a different card)"""
    try:
        urllib.request.build_opener(_NoRedirect).open(f"{LOCAL}/e/{card}", timeout=60)
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location") or ""
        if e.code in (301, 302) and "/e/" in loc:
            return loc.split("/e/", 1)[1]
    except Exception:
        pass
    return card


def total(base, card):
    try:
        req = urllib.request.Request(f"{base}/api/entity-verses?id={card}", headers={"User-Agent": "release-guide"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r).get("total")
    except Exception as e:
        return f"error: {str(e)[:40]}"


def main(live_commit):
    old = subprocess.run(["git", "show", f"{live_commit}:ontology/card-repairs.jsonl"], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8").stdout
    now = (ROOT / "ontology" / "card-repairs.jsonl").read_text(encoding="utf-8")
    rows = lambda s: {(r["card"], r["key"], r["action"], tuple(r.get("verses") or ()))
                      for r in (json.loads(l) for l in s.splitlines() if l.strip())}
    changed = sorted({c for c, *_ in rows(old) ^ rows(now)})
    ents = {}
    for ln in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        if ln.strip():
            e = json.loads(ln)
            ents[e["id"]] = e
    out = []
    for c in changed:
        a, b = total(LIVE, c), total(LOCAL, c)
        out.append({"card": c, "name": (ents.get(c) or {}).get("name") or c, "type": (ents.get(c) or {}).get("type"),
                    "live": a, "local": b, "at": address(c)})
        time.sleep(0.2)
    num = lambda x: x if isinstance(x, int) else 0
    out.sort(key=lambda r: -abs(num(r["live"]) - num(r["local"])))
    kinds = collections.Counter("emptied" if num(r["local"]) == 0 else "was empty" if num(r["live"]) == 0
                                else "narrowed" if num(r["local"]) < num(r["live"]) else
                                "widened" if num(r["local"]) > num(r["live"]) else "same count" for r in out)
    L = [f"# Release side by side — {DATE}", "",
         f"Live runs `{live_commit}`; local is this checkout. **{len(out)} cards** have different rulings: "
         + ", ".join(f"{n} {k}" for k, n in kinds.most_common()) + ".", "",
         "**How to look:** open the live and local links side by side, and scroll to **Where the text speaks of "
         "it**: that section is what changed, and its count is the one in the table. The top of a card (its "
         "description and the verses it quotes) is the same on both. On an image card, the local list should hold "
         "the verses where the text uses the figure, with the plain uses of the word gone. A card that was empty "
         "should now show the verses its own description cites. Anything that looks wrong, say the card's name and "
         "I stop.", "",
         "**Where to start:** the first twenty rows are the biggest changes.", "",
         "| # | card | live | local | side by side |", "|---|---|---|---|---|"]
    for n, r in enumerate(out, 1):
        L.append(f"| {n} | {r['name']} (`{r['card']}`) | {r['live']} | {r['local']} | "
                 f"[live]({LIVE}/e/{r['at']}) · [local]({LOCAL}/e/{r['at']}) |")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{len(out)} cards: {dict(kinds)} -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
