"""Genre profiles at passage level, for the books that have been grouped.

On the canon map, the biggest issue might have been that the measurement is on
a chapter level and there are shifts within a chapter, perhaps just a
visualization matter.

It was not a visualization matter. Chapter divisions are 13th-century and verse
divisions 16th-century, so measuring per chapter measures Stephen Langton and
measuring per verse measures Robert Estienne. Neither is authorial, which is
the same objection this project already accepted about the verse being an index
rather than a unit.

The literary unit is the right span, and after the grouping merge there are 701
of them. Job 3 arrives already split:

    job_3_1_2    "Job opens his mouth"           narrative 100
    job_3_3_26   "Job's lament over his birth"   narrative  16

Chapter averaging blends a 12-word frame with a 192-word speech and the seam
disappears. This computes the same vector `genre.py` computes, over passage
spans instead.

**A passage stores its endpoints, not its members** -- by design, since an edge
per member would have doubled the graph and gone stale whenever a seam moved.
So the span has to be expanded from first ref to last before anything is
counted. Measuring `refs` directly reads two verses where the span holds
twenty-four, which is a mistake worth naming because it looks like data.
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from markers import corpus, base                                 # noqa: E402
from bibleont.schema import load_entities                        # noqa: E402
from bibleont.genre import (DIMS, H_JOIN, G_JOIN, H_ASK, G_ASK,  # noqa: E402
                            H_SAY, G_SAY, H_FIG, G_FIG, H_VIS, G_VIS, ATH)

# The graph names books as the corpus does not; STEPBible uses three letters.
BOOK = {"Job": "Job", "Gen": "Gen", "Mark": "Mrk", "Titus": "Tit",
        "Exod": "Exo", "Ps": "Psa", "Prov": "Pro", "Rom": "Rom"}


def index():
    by = collections.defaultdict(list)
    for r in corpus():
        by[r[0]].append(r)
    return by


def expand(refs, by):
    """Every tagged word between a passage's first and last reference."""
    a = re.match(r"([1-3]?[A-Za-z]+) (\d+):(\d+)", refs[0])
    b = re.match(r"([1-3]?[A-Za-z]+) (\d+):(\d+)", refs[-1])
    if not a or not b:
        return []
    bk = BOOK.get(a.group(1), a.group(1))
    c1, v1 = int(a.group(2)), int(a.group(3))
    c2, v2 = int(b.group(2)), int(b.group(3))
    out = []
    for c in range(c1, c2 + 1):
        lo = v1 if c == c1 else 1
        hi = v2 if c == c2 else 200
        for v in range(lo, hi + 1):
            out += by.get(f"{bk}.{c}.{v}", [])
    return out


def profile(rs, by):
    """The same seven dimensions genre.py computes, over an arbitrary span."""
    if not rs:
        return None
    greek = rs[0][4].startswith("G")
    join = G_JOIN if greek else H_JOIN
    ask = G_ASK if greek else H_ASK
    say = G_SAY if greek else H_SAY
    fig = G_FIG if greek else H_FIG
    vis = G_VIS if greek else H_VIS

    n = len(rs)
    verbs = narr = joins = asks = says = figs = viss = persons = 0
    for x in rs:
        lem, morph = base(x[4]), x[5]
        if greek:
            if morph.startswith("V"):
                verbs += 1
                if re.match(r"V-\d?[AI][APM]I", morph):
                    narr += 1
            if re.search(r"-[12][SP]", morph) or morph.startswith(("P-1", "P-2")):
                persons += 1
        else:
            segs = morph.split("/")
            v = next((s for s in segs if s.lstrip("H").startswith("V")), "")
            if v:
                verbs += 1
                if re.match(r"H?V.w", v):
                    narr += 1
            if re.search(r"[12](?:cs|ms|fs|cp|mp|fp)", morph):
                persons += 1
        if lem in join:
            joins += 1
        if lem in ask:
            asks += 1
        if lem in say:
            says += 1
        if lem in fig:
            figs += 1
        if lem in vis:
            viss += 1

    verses = {x[0] for x in rs}
    balanced = 0
    for ref in verses:
        ws = by.get(ref, [])
        idx = [i for i, w in enumerate(ws) if ATH in w[6]]
        if not idx:
            continue
        k = idx[0]
        a2, b2 = k + 1, len(ws) - k - 1
        if a2 and b2 and min(a2, b2) / max(a2, b2) >= 0.55:
            balanced += 1

    def pct(x, of, scale=1.0):
        return max(0, min(100, round(100 * scale * x / max(of, 1))))

    s = {
        "narrative": pct(narr, verbs, 1.6),
        "dialog": pct(says * 6 + persons, n, 1.1),
        "poetry": pct(balanced, len(verses)) if not greek
                  else pct(balanced, len(verses), 0.5),
        "discourse": pct(joins, n, 6.0),
        "rhetorical": pct(asks, n, 12.0),
        "figurative": pct(figs, n, 45.0),
        "vision": pct(viss, n, 55.0),
    }
    if s["narrative"] > 55:
        s["poetry"] = round(s["poetry"] * 0.5)
    return {"words": n, "verses": len(verses),
            "g": [s[d] for d in DIMS]}


def main() -> int:
    by = index()
    ents = load_entities()
    passages = [e for e in ents.values() if e.type == "passage" and e.refs]
    print(f"{len(passages)} passage nodes")

    out = []
    for p in sorted(passages, key=lambda x: x.refs[0]):
        rs = expand(p.refs, by)
        pr = profile(rs, by)
        if not pr:
            continue
        bk = re.match(r"([1-3]?[A-Za-z]+) ", p.refs[0])
        out.append({"id": p.id, "b": bk.group(1) if bk else "?",
                    "from": p.refs[0], "to": p.refs[-1],
                    "name": (p.name or p.id)[:70], **pr})

    (ROOT / "out" / "passage-profiles.json").write_text(
        json.dumps(out, separators=(",", ":")), encoding="utf-8")
    bybook = collections.Counter(o["b"] for o in out)
    print("  profiled:", dict(bybook))
    print(f"  wrote out/passage-profiles.json")

    print(f"\n{'passage':16}{'span':17}{'vv':>4}{'narr':>6}{'poet':>6}{'dial':>6}  name")
    for o in out[:0] or [x for x in out if x["b"] == "Job"][:8]:
        print(f"{o['id']:16}{o['from'] + '-' + o['to'].split(':')[1]:17}"
              f"{o['verses']:>4}{o['g'][0]:>6}{o['g'][2]:>6}{o['g'][1]:>6}"
              f"  {o['name'][:30]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
