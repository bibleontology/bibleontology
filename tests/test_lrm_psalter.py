"""The Psalter in /ns/biblio (tools/lrm_psalter.py; plan 8.1g step 3, 2026-11-06), checked whole.

  1. THE SHAPES: the whole Psalter conforms to the published shapes (/ns/biblio's and the claims'), pyshacl,
     inference off.
  2. THE COUNTS: 151 Works (the Psalter and 150 psalms), 302 Expressions plus the Psalter's two, 151 creation
     events, 150 entries in five books (I 1-41, II 42-72, III 73-89, IV 90-106, V 107-150), each psalm placed once,
     at its own number, in the right book.
  3. THE VERSES: every Hebrew and English verse of the Psalter is its own text's segment; every Hebrew verse is
     aligned to one English verse of the same psalm, or two where the English splits it (Hebrew 13:6 is English
     13:5-6), and every English verse to at least one.
  4. THE HEADINGS: a name the graph holds once is the narrator's, explicit; one it holds more than once (Asaph,
     Heman, Ethan) is the editors', conjectured; who composed a psalm is always the editors', disputed; no claim
     names Korah for "the sons of Korah"; no reading is ever a plain triple.

Each check is proved by a planted fault. Run: python -X utf8 tests/test_lrm_psalter.py"""
import collections
import sys
from pathlib import Path

import pyshacl
import rdflib

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import lrm_pilot  # noqa: E402
import lrm_psalter as P  # noqa: E402

import gzip  # noqa: E402

PUBLISHED = "".join(l for l in gzip.open(P.PUBLISHED, "rt", encoding="utf-8") if not l.startswith("#"))
if (ROOT / "out" / "structure-nodes.jsonl.gz").exists():
    triples, stats, fx = P.build()
    TEXT = lrm_pilot.to_ntriples(triples)
    # the published copy is the build (the release's file, not a stale one)
    assert PUBLISHED == TEXT, "out/export/psalter.nt.gz is not what tools/lrm_psalter.py builds: rerun it"
else:   # the public copy carries the published file, not the structure it is built from (2026-11-11, the gate)
    fx, TEXT = P.fixture(), PUBLISHED
    stats = {"hebrew_verses": 2527, "english_verses": 2461, "claims": 180}
    print("the structure is not in this copy: the published out/export/psalter.nt.gz is checked")
NS = fx["ns"]
B = fx["base"]
SITE = P.SITE


def T(term):
    p, _, local = term.partition(":")
    return "<" + NS[p] + local + ">"


TYPE = "<" + NS["rdf"] + "type>"
shapes = rdflib.Graph().parse(ROOT / "ontology" / "biblio" / "shapes.ttl", format="turtle")
shapes.parse(ROOT / "ontology" / "claim" / "shapes.ttl", format="turtle")


def lines_of(text):
    return [tuple(l[:-2].split(" ", 2)) for l in text.split("\n") if l]


def faults(text, shacl=True):
    f = []
    trs = lines_of(text)
    S = set(trs)
    by_p = collections.defaultdict(list)
    for s, p, o in trs:
        by_p[p].append((s, o))
    # ---- 2. counts and the arrangement
    works = {s for s, o in by_p[TYPE] if o == T("lrmoo:F1_Work")}
    if len(works) != 151:
        f.append(f"{len(works)} Works, not 151")
    exprs = {s for s, o in by_p[TYPE] if o == T("lrmoo:F2_Expression")}
    if len(exprs) != 302:
        f.append(f"{len(exprs)} Expressions, not 302")
    created = collections.Counter(o for s, o in by_p[T("lrmoo:R16_created")])
    if set(created) != works or any(n != 1 for n in created.values()):
        f.append("not exactly one creation event per Work")
    if any(p == T("lrmoo:R67_has_part") for s, p, o in trs):
        f.append("R67 has part: the Psalter incorporates its psalms (R75), it does not have them as parts")
    member = dict(by_p[T("biblio:member")])
    pos = dict(by_p[T("biblio:position")])
    sec = dict(by_p[T("biblio:inSection")])
    placed = collections.Counter(member.values())
    for c in range(1, 151):
        w = f"<{B}work/psalm-{c}>"
        if placed[w] != 1:
            f.append(f"Psalm {c} placed {placed[w]} times")
    book = {n.lower(): (a, b) for n, a, b in P.BOOKS}
    for e, w in member.items():
        c = int(w.rsplit("-", 1)[1][:-1])
        if pos.get(e) != f'"{c}"^^<{NS["xsd"]}integer>':
            f.append(f"Psalm {c} is not at position {c}")
        a, b = book[sec[e].rsplit("book-", 1)[1][:-1]]
        if not a <= c <= b:
            f.append(f"Psalm {c} filed in the wrong book")
    # ---- 3. the verses
    seg_of = dict(by_p[T("biblio:segmentOf")])
    al = collections.defaultdict(list)
    for e, h in by_p[T("biblio:alignedWith")]:
        al[h].append(e)
    heb = [s for s in seg_of if "/seg/hebrew/" in s]
    eng = [s for s in seg_of if s.startswith(f"<{SITE}/p/")]
    if len(heb) != stats["hebrew_verses"] or len(eng) != stats["english_verses"]:
        f.append(f"{len(heb)} Hebrew and {len(eng)} English segments")
    for h in heb:
        c = h.split("Ps.")[1].split(".")[0]
        if not al[h]:
            f.append(f"{h} aligned to no English verse")
        elif any(e.split("Ps.")[1].split(".")[0] != c for e in al[h]):
            f.append(f"{h} aligned into another psalm: {al[h]}")
        elif len(al[h]) > 2:
            f.append(f"{h} aligned to {len(al[h])} English verses")
    aligned_eng = {e for es in al.values() for e in es}
    for e in eng:
        if e not in aligned_eng:
            f.append(f"{e} has no Hebrew verse aligned to it")
    # ---- 4. the headings
    claims = collections.defaultdict(dict)
    for s, p, o in trs:
        if s.startswith(f"<{B}claim/"):
            claims[s][p] = o
    once = {f"<{SITE}/e/{r}>" for r, one in P.NAMED.values() if one}
    for cid, c in claims.items():
        rel, obj = c.get(T("claim:relation")), c.get(T("claim:object"))
        cert, voice = c.get(T("claim:certainty")), c.get(T("claim:voice"))
        if rel == T("biblio:composedBy") and (cert != T("claim:disputed") or voice != f"<{P.EDITORS}>"):
            f.append(f"{cid}: who composed a psalm is not the editors' disputed reading")
        if rel == T("biblio:superscriptionNames"):
            want = (T("claim:explicit"), f"<{P.NARRATOR}>") if obj in once else (T("claim:conjectured"), f"<{P.EDITORS}>")
            if (cert, voice) != want:
                f.append(f"{cid}: the certainty or voice does not follow how many people the graph holds by that name")
        if obj and "korah" in obj:
            f.append(f"{cid}: names a Korah for 'the sons of Korah'")
        if (c.get(T("claim:subject")), rel, obj) in S:
            f.append(f"{cid}: its reading is stated as a plain triple")
    if len(claims) != stats["claims"]:
        f.append(f"{len(claims)} claims, not {stats['claims']}")
    # ---- 1. the shapes
    if shacl:
        g = rdflib.Graph().parse(data=text, format="nt")
        ok, _g, report = pyshacl.validate(g, shacl_graph=shapes, inference="none", advanced=True)
        if not ok:
            f.append("does not conform to the published shapes: " + report[:1500])
    return f


fails = faults(TEXT)
print(f"the Psalter: {TEXT.count(chr(10)):,} triples; {stats}")

L = TEXT.split("\n")


def without(bit):
    hit = [l for l in L if bit in l]
    assert hit, f"plant: {bit!r} matches nothing"
    return "\n".join(l for l in L if bit not in l) + "\n"


def plus(line):
    return TEXT + line + "\n"


w23, psalter = f"<{B}work/psalm-23>", f"<{B}work/psalter>"
PLANTS = [
    ("R67 between the Psalter and a psalm", plus(f"{psalter} {T('lrmoo:R67_has_part')} {w23} ."), False),
    ("a psalm with no creation event", without(f"<{B}event/psalm-23-creation>"), True),
    ("a psalm in the wrong book", without(f"<{B}arr/psalter-mt/entry-23> {T('biblio:inSection')}")
     + f"<{B}arr/psalter-mt/entry-23> {T('biblio:inSection')} <{B}arr/psalter-mt/book-v> .\n", False),
    ("a Hebrew verse aligned into another psalm",
     without(f"<{SITE}/p/Ps.54.1> {T('biblio:alignedWith')} <{B}seg/hebrew/Ps.54.2>")
     + f"<{SITE}/p/Ps.53.6> {T('biblio:alignedWith')} <{B}seg/hebrew/Ps.54.2> .\n", False),
    ("authorship stated as a plain triple", plus(f"{w23} {T('biblio:composedBy')} <{SITE}/e/david> ."), False),
    ("Asaph's identification given as the narrator's",
     without(f"<{B}claim/psalm-73-superscription> {T('claim:voice')}")
     + f"<{B}claim/psalm-73-superscription> {T('claim:voice')} <{P.NARRATOR}> .\n", False),
    ("an English verse with nothing aligned to it",
     "\n".join(l for l in L if f"<{SITE}/p/Ps.23.6> {T('biblio:alignedWith')}" not in l) + "\n", False),
]
caught = 0
for what, text, shacl in PLANTS:
    if text == TEXT:
        fails.append(f"planted: {what}: the plant changed nothing")
    elif faults(text, shacl=shacl):
        caught += 1
    else:
        fails.append(f"planted: {what} was not caught")
for m in fails:
    print("FAIL", m)
print(f"planted faults caught: {caught} of {len(PLANTS)}; {len(fails)} failures")
sys.exit(1 if fails else 0)
