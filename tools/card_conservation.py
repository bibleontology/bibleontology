"""Conservation of what cards show (P-2026-11-18-8; Doug, 2026-11-19: "card organization can be fairly mechanical but
we just need to be certain that we are not removing completely meaningful information that belongs on any of the
card types", and "rationalization might also mean adding to the graph").

    python -X utf8 tools/card_conservation.py snapshot event        # render every event card, record its facts
    python -X utf8 tools/card_conservation.py check event           # render again, compare with the snapshot

A card's facts are what its rendered page carries, drawers included: every card it links (`data-ent`, `/e/` links)
and every verse or passage it points to (`data-go`). The page is rendered by Edge, headless, with a throwaway profile
(Doug's yes, 2026-11-19), against the local server on port 8002, so the facts are what a reader's browser builds and
not what the API happens to return.

**Run it from PowerShell, not Git Bash.** From Git Bash, Edge exits in 0.1 s with exit code 0 and an empty page, with
the output going to a pipe or to a file alike (2026-11-19); the same call from PowerShell renders in about 1 s. An
empty render is counted as a failed card, never as a card with no facts.

`check` fails on any fact that was on a card and is gone, unless docs/review/card-conservation/removals.json lists
it (each entry with its reason and ruling). Facts that are new are reported, not failed.

Each fact in the snapshot also says whether a relation backs it: a linked card the card has a relation with, or a
verse one of its relations cites. The unbacked ones are the graph's to-do list: what the card shows that the graph
does not yet say (graph backs the card).
"""
import os
import json
import re
import subprocess
import sys
import tempfile
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "review" / "card-conservation"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE = "http://localhost:8002/e/"
sys.path.insert(0, str(ROOT / "app2"))

ENT = re.compile(r'data-ent="([^"]+)"|href="/e/([^"#?]+)"')
GO = re.compile(r'data-go="([^"]+)"')


def norm_ref(r):
    """'Luk.8.22', 'Luke 8:22', 'Luke.8.22' -> 'luke 8:22' (books by their first three letters, as the site varies)"""
    m = re.match(r"\s*([1-3]?\s?[A-Za-z]+)[\s.]+(\d+)[.:](\d+)", r)
    return f"{m.group(1).replace(' ', '').lower()[:4]} {m.group(2)}:{m.group(3)}" if m else r.strip().lower()


def render(eid, profile):
    p = subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                        "--disable-extensions", f"--user-data-dir={profile}", "--window-size=375,812",
                        "--virtual-time-budget=15000", "--dump-dom", BASE + eid],
                       capture_output=True, timeout=120)
    return p.stdout.decode("utf-8", "replace")


TOKEN = re.compile(r'<h[23][^>]*>(.*?)</h[23]>|data-ent="([^"]+)"|href="/e/([^"#?]+)"|data-go="([^"]+)"', re.S)


def facts(html, eid):
    """{card: [sections]}, {verse: [sections]}: each fact with the headings it sits under, in page order. A heading is
    the nearest <h2>/<h3> before it ("Before and after it, in the canon's order" is navigation; "Who did what" is not)."""
    ents, gos, here = {}, {}, "(top)"
    for m in TOKEN.finditer(html):
        h, a, b, g = m.groups()
        if h is not None:
            here = re.sub(r"<[^>]+>|\s+", " ", h).strip()[:80] or here
        elif a or b:
            if (a or b) != eid:
                ents.setdefault(a or b, set()).add(here)
        elif g:
            gos.setdefault(norm_ref(g), set()).add(here)
    return ents, gos


CONTROL_WORD = re.compile(r'data-key="([HGhg]\d+[A-Za-z]?)"')


def controls(html):
    """what a reader uses besides links (Doug, 2026-11-21, round 2 of the card layouts: "make sure that we are not
    losing the navigator button", "a prominent path to the original language cards", "the fruit of the spirit card
    has a unique design ... strengths preserved"): the Navigator button, each Hebrew/Greek word card it opens, a
    sketch"""
    c = set()
    if 'data-navgo="' in html:
        c.add("navigator button")
    c |= {f"word card {k.upper()}" for k in CONTROL_WORD.findall(html)}
    if re.search(r'<use[^>]+href="#sk-', html):
        c.add("sketch")
    return c


def ids_of(kind):
    import server as S
    d = S.load()
    return d, sorted(k for k, e in d["ents"].items() if e.get("type") == kind and not e.get("alias_of"))


def run(kind, workers=4):
    d, ids = ids_of(kind)
    tmp = Path(tempfile.mkdtemp(prefix="edge-cons-"))
    profiles = [tmp / f"p{i}" for i in range(workers)]

    def one(ix):
        i, eid = ix
        for _ in range(3):  # 6 of 524 came back empty with four renders at once (2026-11-19); each rendered alone
            html = render(eid, profiles[i % workers])
            if "<body" in html:
                break
        return eid, ((*facts(html, eid), controls(html)) if "<body" in html else None), len(html)

    try:
        with ThreadPoolExecutor(workers) as ex:
            got = list(ex.map(one, enumerate(ids)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    rels = d["rels"]
    out = {}
    for eid, f, n in got:
        if f is None:
            out[eid] = {"error": f"no page ({n} bytes)"}
            continue
        ents, gos, ctl = f
        linked = {r["other"] for r in rels.get(eid, [])}
        cited = {norm_ref(x) for r in rels.get(eid, []) for x in (r.get("refs") or [])}
        out[eid] = {"cards": {e: {"backed": e in linked, "in": sorted(s)} for e, s in sorted(ents.items())},
                    "verses": {g: {"backed": g in cited, "in": sorted(s)} for g, s in sorted(gos.items())},
                    "controls": {c: {"backed": True, "in": []} for c in sorted(ctl)}}
    return out


def snapshot(kind):
    out = run(kind)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{kind}-snapshot.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    ok = [v for v in out.values() if "error" not in v]
    nc = sum(len(v["cards"]) for v in ok); nv = sum(len(v["verses"]) for v in ok)
    uc = sum(1 for v in ok for b in v["cards"].values() if not b["backed"])
    uv = sum(1 for v in ok for b in v["verses"].values() if not b["backed"])
    print(f"{kind}: {len(ok)} cards rendered ({len(out) - len(ok)} failed); {nc} card links ({uc} with no relation), "
          f"{nv} verse targets ({uv} cited by no relation of the card) -> {p.relative_to(ROOT)}")


def removals():
    rem_p = OUT / "removals.json"
    rem = json.loads(rem_p.read_text(encoding="utf-8")) if rem_p.exists() else {"removals": []}
    return {(r["card"], r["fact"]) for r in rem["removals"]}


def compare(base, now, allowed):
    """(lost, new): every fact of `base` missing from `now` outside `allowed` ((card, fact), card "*" for any)"""
    lost, new = [], 0
    for eid, b in base.items():
        n = now.get(eid)
        if "error" in b:
            continue
        if n is None or "error" in n:
            lost.append(f"{eid}: the card no longer renders"); continue
        for sect in ("cards", "verses", "controls"):    # a snapshot taken before 2026-11-21 has no controls
            for fact in b.get(sect, {}):
                if fact not in n.get(sect, {}) and (eid, fact) not in allowed and ("*", fact) not in allowed:
                    lost.append(f"{eid}: {sect[:-1]} {fact} was shown and is gone")
            new += len(set(n.get(sect, {})) - set(b.get(sect, {})))
    return lost, new


def check(kind):
    base = json.loads((OUT / f"{kind}-snapshot.json").read_text(encoding="utf-8"))
    lost, new = compare(base, run(kind, workers=int(os.environ.get("CONS_WORKERS", "4"))), removals())
    # every loss, not only the 60 printed (2026-11-21: 140 cards "no longer render" and the rest could not be named)
    (ROOT / "out" / f"{kind}-check-lost.json").write_text(json.dumps(lost, ensure_ascii=False, indent=0), encoding="utf-8")
    for x in lost[:60]:
        print("LOST", x)
    print(f"{kind} conservation: {len(base)} cards; {len(lost)} facts lost outside the removals list; {new} new facts")
    return 1 if lost else 0


if __name__ == "__main__":
    cmd, kind = sys.argv[1], sys.argv[2]
    sys.exit({"snapshot": lambda: snapshot(kind) or 0, "check": lambda: check(kind)}[cmd]())
