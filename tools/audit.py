"""Score the deterministic floor against the old graph, which is held frozen.

2026-09-04, on finding the two structures are entirely separate: that is
perfect, because the old is kept as an audit against building up the new.

That is a design decision, not an accident, and it is a strong one. The old
graph is **not** technical debt waiting to be migrated. It is a labelled test
set, and its whole value is that it was produced **independently** -- by a
different process, months ago, in English, with none of this floor in view.
Nobody built it to be an answer key, which is exactly why it works as one.

## The rule that keeps it worth anything

**The old graph must stop moving.** Extending it into new books is fine.
*Editing it to agree with the floor is contamination*, and the failure is
silent: the audit keeps returning a number and the number quietly stops meaning
anything. There is no mechanical check for this -- a contaminated label looks
exactly like a correct one -- so it is a discipline, recorded here because
discipline that lives in a conversation did not survive the conversation.

## What is actually separate today

Nothing in `src/` or `app/` reads anything this floor produces; the only
importer of `tuples`, `quotes` or `acts` is another tool. 320 of 8,416 entities
carry a `lemma` attribute, and that is the only stored link in either
direction. The graph lives in `ontology/` and is committed and validated; the
floor lives in `out/` and is regenerated free.

## The two measurements

**Grounding** asks how much of the old graph the floor can even see: for each
entity, is there a tagged original word in one of its own cited verses carrying
its name? That is the ceiling for any name-matched rebase.

**Prediction** asks whether the floor's grammar recovers a decision the old
graph made. 48 words exist as both an `image` node and a literal node, which
controls for vocabulary; words typed only one way are held out, and the rule is
never fit on them.

    python tools/audit.py            # both measurements
    python tools/audit.py --json     # writes out/audit.json
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
from markers import corpus, base                                  # noqa: E402
from acts import eng                                              # noqa: E402
from tuples import _seg                                           # noqa: E402
from bibleont.schema import load_entities, load_relations         # noqa: E402

LITERAL = {"object", "animal", "plant", "substance", "artifact", "thing",
           "creature"}
SIMILE = {"H3644", "G5613", "G5618", "G5616", "H1819"}
STOPW = {"the", "a", "an", "of", "and", "to", "in", "is", "his", "her"}


def _verses():
    by = collections.defaultdict(list)
    for r in corpus():
        by[eng(r[0])].append(r)
    return by


def _norm(n):
    return re.sub(r"^(the|a|an) ", "", (n or "").strip().lower())


def _refs_by_entity(rels):
    where = collections.defaultdict(set)
    for r in rels:
        for i in (r.src, r.dst):
            for ref in (r.refs or []):
                where[i].add(ref)
    return where


def find_word(by, ref, name):
    """The tagged word in this verse whose gloss carries the name, if any."""
    ts = [t for t in re.findall(r"[a-z]+", (name or "").lower())
          if t not in STOPW and len(t) > 2]
    for w in by.get(ref, []):
        g = (w[3] or "").lower()
        for t in ts:
            stem = t[:-1] if t.endswith("s") and len(t) > 4 else t
            if re.search(rf"\b{re.escape(stem)}", g):
                return w
    return None


def feats(by, w, ref):
    """Everything readable from this ONE word's own tag.

    Scoped to the word, never to the verse. Hebrew *ke-* is a prefix and is a
    property of the word it marks; asking whether the VERSE holds a simile
    particle scored 58% against a 46% base rate and was measuring nothing.
    """
    m = w[5] or ""
    segs = [s.lstrip("H") for s in m.split("/")]
    g = (w[3] or "").strip().lower()
    greek = w[4].startswith("G")
    ws = by.get(ref, [])
    i = ws.index(w) if w in ws else -1
    prev = ws[i - 1] if i > 0 else None
    return {
        "simile": (bool(re.match(r"^(like|as)/", g))
                   or (greek and prev is not None
                       and base(prev[4]) in SIMILE)),
        "definite": any(s.startswith("Td") for s in segs) or m.startswith("T-"),
        "possessed": bool(re.search(r"Sp[123]", m)),
    }


def predict(f):
    """image / literal / None. Abstaining is a valid answer and is counted."""
    if f["simile"]:
        return "image"
    if f["definite"] or f["possessed"]:
        return "literal"
    return None


# ------------------------------------------------------------ grounding

def grounding(by, ents, where):
    out = {}
    for x in ents.values():
        key = getattr(x, "id", None) or x.name
        refs = {r for r in where.get(key, ()) if r in by}
        c = out.setdefault(x.type, collections.Counter())
        if not refs:
            c["no-ref"] += 1
            continue
        lem = (x.attrs or {}).get("lemma")
        if lem and any(base(w[4]) == base(lem)
                       for r in refs for w in by.get(r, [])):
            c["lemma"] += 1
        elif any(find_word(by, r, x.name) for r in refs):
            c["gloss"] += 1
        else:
            c["none"] += 1
    return out


# ----------------------------------------------------------- prediction

def label_sets(by, ents, where):
    img, lit = collections.defaultdict(list), collections.defaultdict(list)
    for x in ents.values():
        if x.type == "image":
            img[_norm(x.name)].append(x)
        elif x.type in LITERAL:
            lit[_norm(x.name)].append(x)
    both = set(img) & set(lit)

    def collect(names, store, label):
        out = []
        for nm in names:
            for x in store[nm]:
                for ref in where.get(getattr(x, "id", None) or x.name, ()):
                    if ref not in by:
                        continue
                    w = find_word(by, ref, nm)
                    if w is not None:
                        out.append((nm, ref, w, label))
        return out

    def dedupe(rs):
        seen = collections.defaultdict(set)
        for nm, ref, w, lab in rs:
            seen[(nm, ref)].add(lab)
        return [r for r in rs if len(seen[(r[0], r[1])]) == 1]

    train = dedupe(collect(both, img, "image") + collect(both, lit, "literal"))
    held = dedupe(collect(set(img) - both, img, "image")
                  + collect(set(lit) - both, lit, "literal"))
    return train, held, len(both)


def score(by, rs):
    c = collections.Counter(l for *_, l in rs)
    maj = max(c.values()) if c else 0
    fired = ok = 0
    for nm, ref, w, lab in rs:
        p = predict(feats(by, w, ref))
        if p is None:
            continue
        fired += 1
        ok += (p == lab)
    return {"n": len(rs), "image": c["image"], "literal": c["literal"],
            "majority": 100 * maj // max(len(rs), 1),
            "fires": fired, "coverage": 100 * fired // max(len(rs), 1),
            "correct": ok, "accuracy": 100 * ok // max(fired, 1)}


def edge_agreement(limit_books=None):
    """Does the floor reproduce what the old graph asserted?

    A correctness measure was asked for before more tuning, rightly:
    three times in one day a coverage number looked fine and hid
    wrongness. But correctness needs an answer key, and for edges there is no
    gold standard -- except the old graph, which asserted 15,023 relations
    independently, in English, months earlier, with none of this in view.

    **What this measures and what it does not.** For every old-graph relation
    carrying a verse reference, it asks whether the floor's edges for that
    verse connect the same two things. That is RECALL against an independent
    witness. It is not precision: the floor emits 126,418 edges against the
    graph's 15,023, and the excess is mostly real structure the old pass never
    looked for rather than error. A low score here means the floor missed
    something the graph found; it does not mean the extra edges are wrong.

    Three levels, because they fail for different reasons:

        both nodes present   the floor saw both things in that verse at all
        connected            an edge joins them, in either direction
        same direction       src and dst agree

    A drop from the first to the second is a missing relation. A drop from the
    second to the third is a direction error, which is a different bug.

    ## First run, and what the number actually means

        relations scored           14,476
        both nodes present            760    5%
        connected by an edge          358    2%
        same direction                324    2%

    **2% is real and it is measuring the wrong thing for most of these
    relations.** Sampling the misses says why: the old graph's relations are
    largely INFERENCES, not clause-level facts. `abraham father_of ishmael` is
    derived from "she bore him Ishmael"; `adam father_of seth` from "Adam
    begat a son and called his name Seth". The floor emits what the clause
    says; the graph recorded what the passage means. Agreement between them
    needs an inference layer that does not exist, so a low score here is a
    statement about the gap between the layers rather than about the floor's
    accuracy.

    That is worth knowing before anyone reads 2% as a quality score. But the
    sampling also found two defects that ARE the floor's, and neither was
    visible in any coverage number:

    **No identity resolution.** Genesis 16:15 gives the floor `abram` where
    the graph says `abraham`. Same person, two node ids, and nothing joins
    them. That is step 9 of the pass sequence -- identity, deduplication,
    typing -- confirmed missing by measurement rather than by assumption.

    **Multi-object coordination collapses.** Genesis 25:2 lists six sons, each
    with its own object marker, and the floor emits one node. It also emits a
    garbage `to -> to` edge where a preposition became both the relation and
    its own target.
    """
    import xml.etree.ElementTree as ET
    sys.path.insert(0, str(ROOT / "tools"))
    from macula import MAC, _words, _ref, BOOK                    # noqa: E402
    from graphnodes import resolve, SKIP_WORDS                    # noqa: E402

    ents = load_entities()
    rels = load_relations()

    def as_id(name):
        t = re.sub(r"[^A-Za-z0-9 ]", " ", (name or ""))
        parts = [p for p in t.split() if p.lower() not in SKIP_WORDS]
        if not parts:
            return None
        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])

    # the floor, per verse, for the books the old graph actually covers
    want = set()
    for r in rels:
        for ref in (r.refs or []):
            m = re.match(r"^([1-3]?[A-Za-z]+) (\d+):(\d+)$", ref)
            if m:
                want.add(ref)
    floor = {}
    byref = collections.OrderedDict()
    for f in sorted(MAC.rglob("*.xml")):
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        nested = {id(c) for t in root.iter("wg") if t.get("class") == "cl"
                  for c in t.iter("wg")
                  if c is not t and c.get("class") == "cl"}
        for c in root.iter("wg"):
            if c.get("class") != "cl" or id(c) in nested:
                continue
            ws = _words(c)
            if not ws:
                continue
            k = _ref(ws[0].get("ref") or "")
            if k:
                byref.setdefault(k, []).append(c)
    carry = prev = None
    for k, cls in byref.items():
        bk = k.split(".")[0]
        if bk != prev:
            carry = None
        prev = bk
        try:
            g = resolve(cls, carry=carry)
            carry = g.get("carry")
        except Exception:                                         # noqa: BLE001
            continue
        floor[k] = g

    # The old graph writes "1Chr 27:33"; the floor keys on "1Ch.27.33".
    # acts.BOOK is the table that maps between them, and inverting the MACULA
    # table instead scored zero of 15,022 relations while looking like a
    # coverage problem.
    from acts import BOOK as ENGBOOK                              # noqa: E402
    INV = {v: k for k, v in ENGBOOK.items()}

    def eng_key(ref):
        m = re.match(r"^([1-3]?[A-Za-z]+) (\d+):(\d+)$", ref or "")
        if not m:
            return None
        b = INV.get(m.group(1))
        return f"{b}.{int(m.group(2))}.{int(m.group(3))}" if b else None

    tot = both = conn = same = norefs = 0
    for r in rels:
        s = ents.get(r.src)
        d = ents.get(r.dst)
        sid, did = as_id(s.name if s else r.src), as_id(d.name if d else r.dst)
        if not sid or not did:
            continue
        hit_both = hit_conn = hit_same = False
        seen_verse = False
        for ref in (r.refs or []):
            k = eng_key(ref)
            g = floor.get(k) if k else None
            if not g:
                continue
            seen_verse = True
            ns = set(g["nodes"])
            if sid in ns and did in ns:
                hit_both = True
            for e in g["edges"]:
                a, b = e.get("src"), e.get("dst")
                b = b if isinstance(b, str) else None
                if {a, b} == {sid, did}:
                    hit_conn = True
                    if a == sid and b == did:
                        hit_same = True
        if not seen_verse:
            norefs += 1
            continue
        tot += 1
        both += hit_both
        conn += hit_conn
        same += hit_same
    return {"scored": tot, "both": both, "connected": conn, "directed": same,
            "no_floor_for_verse": norefs}


def main() -> int:
    by = _verses()
    ents = load_entities()
    rels = load_relations()
    where = _refs_by_entity(rels)

    print("THE OLD GRAPH IS THE ANSWER KEY. It must not be edited to agree")
    print("with the floor -- a contaminated label looks exactly like a good one.")
    print()
    g = grounding(by, ents, where)
    print("GROUNDING -- can the floor see this node in its own cited verses?")
    print(f"{'type':13}{'total':>7}{'lemma':>7}{'gloss':>7}{'none':>7}"
          f"{'no ref':>8}{'grounded':>10}")
    T = L = G = 0
    for t in sorted(g, key=lambda t: -sum(g[t].values())):
        c = g[t]
        tot = sum(c.values())
        ok = c["lemma"] + c["gloss"]
        T, L, G = T + tot, L + c["lemma"], G + ok
        print(f"  {t:11}{tot:>7}{c['lemma']:>7}{c['gloss']:>7}{c['none']:>7}"
              f"{c['no-ref']:>8}{100*ok//max(tot,1):>9}%")
    print(f"  {'ALL':11}{T:>7}{L:>7}{G-L:>7}{'':>7}{'':>8}{100*G//max(T,1):>9}%")
    print(f"\n  {100*G//max(T,1)}% is the CEILING for a name-matched rebase;")
    print(f"  {100*L//max(T,1)}% is its floor -- only {L} land on a lemma rather")
    print("  than on an English gloss, which can match for the wrong reason.")

    train, held, nboth = label_sets(by, ents, where)
    print()
    print(f"PREDICTION -- {nboth} words the old graph typed BOTH ways")
    st, sh = score(by, train), score(by, held)
    print(f"{'':12}{'n':>6}{'majority':>10}{'coverage':>10}{'accuracy':>10}"
          f"{'lift':>7}")
    for nm, s in (("train", st), ("held out", sh)):
        print(f"  {nm:10}{s['n']:>6}{s['majority']:>9}%{s['coverage']:>9}%"
              f"{s['accuracy']:>9}%{s['accuracy']-s['majority']:>+7}")
    print()
    print("  Held out = words the graph typed only ONE way. The rule is never")
    print("  fit on them, so a rule that merely learned which words are")
    print("  image-ish scores at the majority baseline there.")

    if "--edges" in sys.argv:
        e = edge_agreement()
        print()
        print("EDGE AGREEMENT — does the floor reproduce what the old graph")
        print("asserted? Recall against an independent witness, not precision.")
        n = max(e["scored"], 1)
        print(f"  relations scored           {e['scored']:>7,}")
        print(f"  both nodes present         {e['both']:>7,}   "
              f"{100*e['both']//n}%")
        print(f"  connected by an edge       {e['connected']:>7,}   "
              f"{100*e['connected']//n}%")
        print(f"  same direction             {e['directed']:>7,}   "
              f"{100*e['directed']//n}%")
        print(f"  no floor for that verse    {e['no_floor_for_verse']:>7,}")
        print()
        print("  A drop from 'both present' to 'connected' is a missing")
        print("  relation; a drop from 'connected' to 'same direction' is a")
        print("  direction error. They are different bugs.")

    if "--json" in sys.argv:
        p = ROOT / "out" / "audit.json"
        p.write_text(json.dumps(
            {"grounding": {k: dict(v) for k, v in g.items()},
             "grounded_pct": 100 * G // max(T, 1),
             "lemma_pct": 100 * L // max(T, 1),
             "both_way_words": nboth, "train": st, "held_out": sh},
            indent=2), encoding="utf-8")
        print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
