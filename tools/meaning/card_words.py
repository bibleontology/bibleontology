"""A card's words against its own verses (plan 4.7a).

2026-09-30, approving P-69. A card's anchors (its Hebrew and Greek
words) are found from its English title through MACULA's glosses
(tools/meaning/concept_anchors.py). Some titles came from an older
translation and never matched the Hebrew under them: "scales" cites Job
41:15, where the Hebrew is מָגֵן "shields"; "clay" cites Job 4:19, חֹמֶר.
Such a card is anchored by its title alone, and its "Where the text speaks
of it" lists another word's verses, or none.

This finds them, deterministically: a card none of whose cited verses holds
any of its anchored words. For each, the words IN its cited verses whose
own MACULA gloss renders the card's name are offered as its word -- found
in the verse, not guessed from the title.

    python tools/meaning/card_words.py
        -> out/card-words.json
        -> docs/review/CARD-WORDS.md
"""
import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "themes"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
from concept_anchors import STOP, stem  # noqa: E402

TYPES = ("concept", "title", "observance", "object", "image")
# a multi-word name's little words never name the thing: "those who provoke
# God" offered אֲשֶׁר 'who', "its stump" offered 'its'
FUNC = set("who whom whose which what that this these those its it he she they them we "
           "you one ones all not no nor any some every each there here".split())


def lemmas():
    sys.path.insert(0, str(ROOT / "tools" / "builder"))
    import source as S
    out = {}
    for lang in ("hebrew", "greek"):
        for p in S.files(lang):
            _r, ws = S.load(p, lang)
            for w in ws.values():
                st = "".join(ch for ch in (w.get("strongnumberx") or w.get("strong") or "")
                             if ch.isdigit())
                if st:
                    out.setdefault(("g" if lang == "greek" else "h") + str(int(st)),
                                   w.get("lemma"))
    return out


def verses(ref):
    """'Job 41:15' / 'Matt 5:3–12' -> BSB ids."""
    m = re.fullmatch(r"([1-3]?[A-Za-z]+) (\d+):(\d+)(?:–(\d+))?", ref)
    if not m:
        return []
    b, c, v1, v2 = m.group(1), m.group(2), int(m.group(3)), int(m.group(4) or m.group(3))
    return [f"{b}.{c}.{v}" for v in range(v1, v2 + 1)]


def main():
    import messages
    C = messages.corpus()
    words, mac = C.words, C.mac
    anchors = {r["id"]: r for r in map(json.loads, gzip.open(
        ROOT / "out" / "concept-anchors.jsonl.gz", "rt", encoding="utf-8"))}
    lem = lemmas()
    rows = []
    tally = collections.Counter()
    for ln in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        e = json.loads(ln)
        if e["type"] not in TYPES or not e.get("refs"):
            continue
        a = anchors.get(e["id"])
        keys = {k for p in (a or {}).get("parts", []) for k, *_ in p["anchors"]} | \
            {v["key"] for v in (a or {}).get("from_verses", [])}
        vs = [v for r in e["refs"] for v in verses(r)]
        held = {v: [w for w in words.get(mac(v), [])] for v in vs}
        found = sorted({k for ws in held.values() for _p, k, *_ in ws if k in keys})
        if found:
            tally["its own verses hold its word"] += 1
            continue
        # the name's own words, stemmed as the anchors stem them
        names = [e["name"]] + (e.get("aka") or [])
        stems = {stem(x) for nm in names for x in re.findall(r"[A-Za-z]+", nm)
                 if x.lower() not in STOP | FUNC and len(x) > 2}
        offer = collections.OrderedDict()
        for v, ws in held.items():
            # the verse's own language only: Acts 10:38 offered Hebrew keys
            langs = collections.Counter(k[0] for _p, k, *_ in ws)
            lang = langs.most_common(1)[0][0] if langs else None
            for _p, k, _mood, _per, _stem, gloss in ws:
                if k[0] != lang:
                    continue
                g = {stem(x) for x in re.findall(r"[A-Za-z]+", gloss or "")
                     if x.lower() not in STOP}
                if g & stems and not ({x.lower() for x in re.findall(r"[A-Za-z]+", gloss or "")}
                                      <= FUNC | STOP):
                    offer.setdefault(k, {"key": k, "lemma": lem.get(k), "gloss": gloss,
                                         "verses": []})
                    offer[k]["verses"].append(v)
        kind = ("no anchors" if not keys else "anchors absent from its verses")
        tally[kind + (": its verses offer a word" if offer else ": nothing offered")] += 1
        rows.append({"id": e["id"], "type": e["type"], "name": e["name"], "refs": e["refs"],
                     "anchors": sorted(keys), "kind": kind, "offer": list(offer.values()),
                     "desc": (e.get("desc") or "")[:300],
                     "anchor_words": [[k, lem.get(k)] for k in sorted(keys)],
                     "verse_text": {v: C.shown(v) for v in vs},
                     "verse_words": {v: [[k, lem.get(k), g] for _p, k, _m, _pe, _s, g in ws]
                                     for v, ws in held.items()}})
    (ROOT / "out" / "card-words.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# A card's words against its own verses (plan 4.7a)", "",
             "Made by `tools/meaning/card_words.py`. A card none of whose cited verses "
             "holds any of its anchored words is anchored by its English title alone. "
             "Offered: words in its cited verses whose own gloss renders the card's name.",
             "", "| | cards |", "|---|---|"]
    lines += [f"| {k} | {v:,} |" for k, v in sorted(tally.items())]
    lines += ["", "| card | type | cites | anchored to | offered from its verses |",
              "|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["kind"], r["id"])):
        off = "; ".join(f"{o['key']} '{o['gloss']}' ({', '.join(o['verses'][:2])})"
                        for o in r["offer"]) or "—"
        lines.append(f"| {r['name']} (`{r['id']}`) | {r['type']} | {', '.join(r['refs'][:3])} | "
                     f"{', '.join(r['anchors'][:4]) or '—'} | {off} |")
    (ROOT / "docs" / "review" / "CARD-WORDS.md").write_text("\n".join(lines) + "\n",
                                                           encoding="utf-8")
    print(dict(tally))


READER = "Claude Sonnet 5.5, two blind passes, 2026-09-30"
READER3 = "Claude Sonnet 5.5, two of three blind passes, 2026-09-30"


def merge(da, db, dt=None):
    """The judged words -> ontology/card-words.jsonl. A word both passes
    picked is the card's; a word one picked goes to the third pass, whose
    verdict decides (on the anchor senses: the third pass's reasoning is
    solid). A key not in the card's own verses is refused, whoever gave it."""
    import glob

    def load(d, p):
        out = {}
        for f in sorted(glob.glob(str(Path(d) / f"{p}_*.json"))):
            if re.fullmatch(rf"{p}_\d\d\.json", Path(f).name):
                for x in json.load(open(f, encoding="utf-8")):
                    out[x["card"]] = x
        return out
    items = {x["card"]: x for f in sorted(glob.glob(str(Path(da) / "batch_*.json")))
             for x in json.load(open(f, encoding="utf-8"))}
    A, B = load(da, "A"), load(db, "B")
    T = load(dt, "T") if dt else {}
    missing = [c for c in items if c not in A or c not in B]
    if missing:
        raise SystemExit(f"{len(missing)} cards lack a pass: {missing[:5]}")
    rows, disputed, tally = [], [], collections.Counter()
    for c, it in items.items():
        inverse = {k: (v, lm, g) for v, vv in it["verses"].items() for k, lm, g in vv["words"]}
        sa = {k for k in A[c]["words"] if k in inverse}
        sb = {k for k in B[c]["words"] if k in inverse}
        tally["refused (not in the verse)"] += len(set(A[c]["words"]) - sa) + \
            len(set(B[c]["words"]) - sb)
        if sa != sb:
            disputed.append(c)
        for k in sorted(sa | sb):
            if k in sa and k in sb:
                reader = READER
            elif c in T:
                if k not in T[c]["words"]:
                    tally["one pass only, third said no"] += 1
                    continue
                reader = READER3
            else:
                tally["one pass only, awaiting the third"] += 1
                continue
            v, lm, g = inverse[k]
            rows.append({"card": c, "key": k, "lemma": lm, "gloss": g, "verse": v,
                         "reader": reader, "why": A[c].get("why") or ""})
            tally[reader] += 1
        if not (sa | sb):
            tally["cards with no word, both passes"] += 1
    with open(ROOT / "ontology" / "card-words.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(rows, key=lambda r: (r["card"], r["key"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(items)} cards; disputed {len(disputed)}; {dict(tally)}")
    return disputed


if __name__ == "__main__":
    if sys.argv[1:2] == ["merge"]:
        merge(*sys.argv[2:5])
    else:
        main()
