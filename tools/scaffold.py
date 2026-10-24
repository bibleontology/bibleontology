"""Climb Romans: BSB sections as the floor, merged upward by shared pattern.

2026-09-12: the formula was optimized for psalms, and it makes sense to keep
the version-voting method for books with headings and paragraph structures.
Go bottom up, always matching the most similar contiguous nodes until the top
is reached, plugging in patterns with each grouping as it rises.

So the floor is the translators' 47 section headings, not our grammar. Above it,
adjacent nodes merge by shared signal until one node remains, and **every merge
records the signals that justified it** -- the pattern being plugged in at that
level.

Similarity is IDF-weighted Jaccard over Greek content lemmas. Jaccard rather
than raw overlap because a node grows as it merges, and raw overlap would make
the biggest node look similar to everything.

The acceptance test was chosen before running: Romans' best-known macro-structure
is 1-8 doctrine, **9-11 Israel**, 12-16 application. A merge order that recovers
9-11 as a unit has found the one thing every reader of Romans agrees on. It
does: `1:1-8:39`, `9:1-11:32` and `14:1-16:16` are all real nodes.

## The output that matters is RESISTANCE, not the tree

2026-09-12, correcting the framing: according to the algorithm The Day is Near
should be the hold out, because it is a node that really stands on its own. Read
as scaffolding for patterns, this grouping is quite good.

That is right, and the first reading of this output was wrong. The tree's TOP is
poor -- it splits 1-13 against 14-16, because the greetings carry the most
distinctive vocabulary in the letter while chapters 1-8 and 9-11 argue in shared
theological terms. That looked like a defect ("it ranks distinctiveness above
significance"). **For scaffolding it is not a defect at all**: a node that is
internally coherent and externally distinct is exactly what a pattern can attach
to without bleeding across a seam.

And read that way, **how long a section resists merging is a self-containment
detector**, and it finds what commentators already flag:

    HELD OUT LONGEST                    JOINED EARLIEST
    13:11  The Day Is Near              6:1   Dead to Sin, Alive to God
    16:25  Doxology                     5:12  Death in Adam, Life in Christ
    13:8   Love Fulfills the Law        6:15  The Wages of Sin
    16:21  Greetings, Fellow Workers    7:13  Struggling with Sin
    16:17  Avoid Divisions              7:7   God's Law Is Holy
    8:35   More than Conquerors         7:1   Release from the Law
    11:33  A Hymn of Praise             8:18  Future Glory
    12:1   Living Sacrifices            8:12  Heirs with Christ

The Doxology is the most textually detachable passage in Romans -- manuscripts
place it after 14:23 or 15:33. "Avoid Divisions" is the classic abrupt intrusion
into the greetings. "A Hymn of Praise" seals chapters 9-11. "More than
Conquerors" is the peroration of chapter 8. "Living Sacrifices" is the hinge.
None of that was supplied; all of it is lemma overlap and merge order.

The earliest-joined are **Romans 5-8 entire** -- the one long stretch where the
argument runs unbroken, which is why they fuse first.

    python tools/scaffold.py            # climb, and rank by resistance
"""
import xml.etree.ElementTree as ET
import re, json, gzip, math, collections, pathlib

STOP = {"ὁ", "καί", "δέ", "ἐν", "εἰς", "αὐτός", "γάρ", "οὐ", "τίς", "ὅς", "εἰμί",
        "ἐγώ", "σύ", "ἡμεῖς", "ὑμεῖς", "οὗτος", "ἀλλά", "ἐκ", "ἐπί", "πρός",
        "διά", "κατά", "μή", "τε", "ἵνα", "ὅτι", "ὡς", "ἤ", "ἐάν", "περί",
        "ἀπό", "ὑπό", "πᾶς", "γίνομαι", "ἔχω", "λέγω", "μέν", "οὖν", "ἄν"}


def sections():
    out = []
    with gzip.open("out/structure.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            b, c, v = d["ref"].split(".")
            if b == "Rom" and d.get("level") == "section" \
               and "engbsb" in (d.get("by") or []):
                out.append({"c": int(c), "v": int(v), "title": d.get("title"),
                            "agree": d.get("agree")})
    out.sort(key=lambda x: (x["c"], x["v"]))
    return out


def greek_lemmas():
    """-> {(chapter, verse): [lemma...]} for Romans."""
    root = ET.parse("data/raw/macula/greek/06-romans.xml").getroot()
    per = collections.defaultdict(list)
    for w in root.iter("w"):
        m = re.search(r"ROM (\d+):(\d+)", w.get("ref") or "")
        if not m:
            continue
        per[(int(m.group(1)), int(m.group(2)))].append(w.get("lemma"))
    return per


def build():
    secs = sections()
    per = greek_lemmas()
    allv = sorted(per)
    # assign every verse to the section it falls in
    bounds = [(s["c"], s["v"]) for s in secs]
    leaves = []
    for i, s in enumerate(secs):
        lo = (s["c"], s["v"])
        hi = bounds[i + 1] if i + 1 < len(bounds) else (99, 99)
        vs = [k for k in allv if lo <= k < hi]
        lem = [l for k in vs for l in per[k] if l and l not in STOP]
        leaves.append({"lo": lo, "hi": vs[-1] if vs else lo, "title": s["title"],
                       "agree": s["agree"], "sig": set(lem), "n": len(vs),
                       "kids": [], "depth": 0, "why": []})
    # IDF over the 47 sections
    df = collections.Counter()
    for n in leaves:
        for l in n["sig"]:
            df[l] += 1
    N = len(leaves)

    def w(l):
        return math.log(N / max(df.get(l, 1), 1))

    def sim(a, b):
        inter = a["sig"] & b["sig"]
        union = a["sig"] | b["sig"]
        if not union:
            return 0, []
        num = sum(w(l) for l in inter)
        den = sum(w(l) for l in union)
        top = sorted(inter, key=lambda l: -w(l))[:6]
        return (num / den if den else 0), top

    nodes = leaves[:]
    merges = []
    while len(nodes) > 1:
        best, bi, btop = -1, None, []
        for i in range(len(nodes) - 1):
            s, top = sim(nodes[i], nodes[i + 1])
            if s > best:
                best, bi, btop = s, i, top
        a, b = nodes[bi], nodes[bi + 1]
        new = {"lo": a["lo"], "hi": b["hi"],
               "title": None, "agree": None,
               "sig": a["sig"] | b["sig"], "n": a["n"] + b["n"],
               "kids": [a, b], "depth": 0, "why": btop, "score": best}
        merges.append({"span": (a["lo"], b["hi"]), "score": round(best, 4),
                       "why": btop,
                       "left": a.get("title") or f'{a["lo"][0]}:{a["lo"][1]}',
                       "right": b.get("title") or f'{b["lo"][0]}:{b["lo"][1]}'})
        nodes = nodes[:bi] + [new] + nodes[bi + 2:]
    root = nodes[0]

    def setdepth(n, d=0):
        n["depth"] = d
        for k in n["kids"]:
            setdepth(k, d + 1)
    setdepth(root)
    return root, merges, leaves


def flatten(n, out=None):
    if out is None:
        out = []
    out.append({"lo": n["lo"], "hi": n["hi"], "depth": n["depth"],
                "title": n["title"], "why": n["why"],
                "score": n.get("score")})
    for k in n["kids"]:
        flatten(k, out)
    return out


if __name__ == "__main__":
    root, merges, leaves = build()
    spans = flatten(root)
    json.dump({"spans": spans,
               "leaves": [{"lo": l["lo"], "hi": l["hi"], "title": l["title"],
                           "agree": l["agree"], "n": l["n"]} for l in leaves],
               "merges": merges},
              open("out/romans-climb.json", "w", encoding="utf-8"),
              ensure_ascii=False)
    print(f"47 sections -> {len(merges)} merges\n")
    print("LAST 8 MERGES (the top of the tree)\n")
    for m in merges[-8:]:
        (c1, v1), (c2, v2) = m["span"]
        print(f"  {c1}:{v1}-{c2}:{v2:<4} score {m['score']:.3f}  "
              f"{' '.join(m['why'][:5])}")
    print("\nFIRST 8 MERGES (tightest pairs, the bottom)\n")
    for m in merges[:8]:
        (c1, v1), (c2, v2) = m["span"]
        print(f"  {c1}:{v1}-{c2}:{v2:<4} score {m['score']:.3f}  "
              f"{' '.join(m['why'][:5])}")


def resistance(leaves, spans):
    """How long each section resisted merging. Shallow parent = held out longest.

    This is the module's most useful output and was not what it was built for.
    See the header: the 2026-09-12 reframing of the tree as *scaffolding* is
    what exposed it.
    """
    def lo(x): return (x["lo"][0], x["lo"][1])
    def hi(x): return (x["hi"][0], x["hi"][1])
    out = []
    for L in leaves:
        anc = [s for s in spans if lo(s) <= lo(L) and hi(s) >= hi(L)
               and not (lo(s) == lo(L) and hi(s) == hi(L))]
        if not anc:
            continue
        out.append((max(s["depth"] for s in anc), L["lo"], L["title"]))
    out.sort()
    return out
