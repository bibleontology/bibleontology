"""Where the text speaks in images: category clash in "X is Y", and "like".

2026-09-28: a literal word can carry a symbolic meaning — "sword"
and "the sword of the Spirit", "light" and the light of life. Plan 4.2 is
the same thing from the structure side: "the LORD is not in the category
'shepherd'". This finds the places the TEXT'S FORM makes an image, without
deciding what any image means (docs/MEANING-ONTOLOGY.md, part 5):

1. CATEGORY CLASH in a copular clause (a subject and a predicate, `s` and
   `p`: "the LORD [is] my shepherd", "your word is a lamp", ἐγώ εἰμι ὁ
   ἄρτος). The two are placed in WordNet through their English glosses
   (PRINCIPLES 44a: overlay, derived via English, every gloss kept) and
   compared: where they meet only high in the hierarchy (their lowest
   common hypernym at depth <= CLASH_DEPTH) and in different lexicographer
   files, they are not the same kind of thing, and one is said to be the
   other. Then:
       image         the predicate is concrete (an artifact, animal, plant,
                     natural object, phenomenon, food, substance, body
                     part, place): "the LORD is my rock"
       quality       the predicate is abstract: "God is love" — said of
                     him, not pictured; not an image
       same kind     no clash: "David was king", "Abraham was old"
       unplaced      a side has no WordNet place (a name we cannot type, a
                     word WordNet lacks)
2. SIMILE BY MARKER: a participant through כְּ / ὡς / ὥσπερ ("like a tree
   planted", Psa 1:3). The marker decides; no hierarchy is consulted.

A subject that is a pronoun or a verb's implicit subject is followed
through `refers_to` (the structure's, and the BSB readings layer).

It finds WHERE an image is used and what the image is (its vehicle). It
does not say what the image means: that is a reading (part 6 of the
recommendation), and symbolic relations do not chain (PRINCIPLES 17).

    python tools/meaning/figures.py            # report and samples
    python tools/meaning/figures.py --write    # out/meaning-figures.jsonl.gz
    python tools/meaning/figures.py --verse Psa.23.1
"""
import argparse
import collections
import gzip
import json
import random
import sys
from pathlib import Path

from nltk.corpus import wordnet as wn

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "builder"))
from source import norm  # noqa: E402

CLASH_DEPTH = 5
CONCRETE = {"noun.artifact", "noun.animal", "noun.plant", "noun.object",
            "noun.phenomenon", "noun.food", "noun.substance", "noun.body",
            "noun.location"}
# an image can be a KIND OF PERSON too: shepherd, king, father, warrior
# ("the LORD is my shepherd"); only attributes, feelings, states and the
# like are said as qualities ("God is love")
PICTURABLE = CONCRETE | {"noun.person", "noun.group"}
SIMILE = {"כ", "ως", "ωσπερ", "ωσει"}
# names the WordNet map cannot place, typed by what the entity store says
# (a person, a place, a people); the divine names by the word "God"
TYPE_SYNSET = {"person": "person.n.01", "place": "location.n.01",
               "group": "people.n.01", "being": "spiritual_being.n.01",
               "creature": "animal.n.01"}
DIVINE = {"יהוה", "אלהים", "אל", "אלוה", "θεος", "יה"}


def rows(p):
    for line in gzip.open(p, "rt", encoding="utf-8"):
        yield json.loads(line)


def wordnet_places():
    """(lang, lemma) -> {gloss: its two commonest synsets}, in order of how
    often MACULA glosses the lemma so; keyed by the POINTED lemma, and by
    the normalised one as a fallback (unpointed, אֵלֶּה 'these' and אָלָה
    'curse' are one key — the first run called "these are the generations"
    a clash with a curse)."""
    out = {}
    for r in rows(OUT / "wordnet-map.jsonl.gz"):
        if not r.get("lemma") or r.get("pos") != "noun":
            continue
        by_via = collections.defaultdict(list)
        for m in r.get("map") or []:
            by_via[m["via"]].append(m)
        vias = sorted(by_via, key=lambda v: -(by_via[v][0].get("n") or 0))
        g = {v: [m["synset"] for m in sorted(
            by_via[v], key=lambda m: -(m.get("count") or 0))[:2]]
            for v in vias}
        out[(r["lang"], "=" + r["lemma"])] = g
        out.setdefault((r["lang"], norm(r["lemma"])), {}).update(g)
    return out


def source_classes():
    """MACULA id -> word class, both languages (the floor: a predicate
    phrase holding a preposition is a location or a relation, not an
    identity)."""
    import source as SRC
    cls = {}
    for lang in ("hebrew", "greek"):
        for path in SRC.files(lang):
            _, ws = SRC.load(path, lang)
            cls.update((i, w.get("class")) for i, w in ws.items())
    return cls


def senses(glosses, text):
    """The synsets for THIS occurrence: its own English gloss first (MACULA
    glosses Psa 23:1's רֹעִי "shepherd"; the lemma's commonest gloss, after
    the pointing is stripped, is רֵעַ "friend"), then the lemma's two
    commonest glosses."""
    words = [w for w in (text or "").lower().replace(".", " ").split()
             if w.isalpha()]
    own = next((glosses[w] for w in reversed(words) if w in glosses), [])
    rest = [s for v in list(glosses)[:2] for s in glosses[v]]
    return own + [s for s in rest if s not in own]


def entity_types():
    """English name -> entity type, for names with one type only."""
    t = collections.defaultdict(set)
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl",
                     encoding="utf-8"):
        e = json.loads(line)
        if e.get("type") in TYPE_SYNSET:
            t[(e.get("name") or "").lower()].add(e["type"])
    return {k: next(iter(v)) for k, v in t.items() if len(v) == 1}


def clash(a, b):
    """(clashes?, deepest meeting depth, the pair) over the candidate
    senses: the same kind if ANY pair meets deeper than CLASH_DEPTH.

    Not by lexicographer file: WordNet files God under noun.person, so
    "same file" called "the LORD is my shepherd" the same kind of thing.
    Where they MEET is the test: god.n.01 and shepherd.n.01 meet only at
    entity.n.01."""
    best = (-1, None)
    for x in a:
        for y in b:
            sx, sy = wn.synset(x), wn.synset(y)
            d = max((h.max_depth() for h in sx.lowest_common_hypernyms(sy)),
                    default=0)
            if d > best[0]:
                best = (d, (x, y))
    return best[0] <= CLASH_DEPTH, best[0], best[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--verse")
    a = ap.parse_args()
    places = wordnet_places()
    etype = entity_types()
    nodes = {}
    for n in rows(OUT / "structure-nodes.jsonl.gz"):
        if n.get("word") or n.get("implicit") or n.get("composite"):
            nodes[n["id"]] = n
    wclass = source_classes()
    roles = collections.defaultdict(dict)
    p_ids = {}
    refers = {}
    simile_pp = []
    member_of = collections.defaultdict(list)
    headings = set()                 # "a psalm of David" is not "X is Y"
    for e in rows(OUT / "structure-edges.jsonl.gz"):
        if e["type"] == "member":
            member_of[e["src"]].append(e)
        if e["type"] == "frame" and "#writing" in e["src"]:
            headings.add(e["dst"])
        if e.get("clause_role") and e["type"] in ("s", "p"):
            roles[e["src"]][e["type"]] = e["dst"]
            if e["type"] == "p":
                p_ids[e["src"]] = e.get("src_ids") or []
        elif e["type"] == "refers_to":
            refers.setdefault(e["src"], e["dst"])
        if e.get("clause_role") and e["type"] == "pp" and \
                norm(e.get("prep") or "") in SIMILE:
            simile_pp.append(e)
    for e in rows(OUT / "structure-readings.jsonl.gz"):
        refers.setdefault(e["src"], e["dst"])

    def resolve(nid):
        seen = 0
        while nid in refers and seen < 4:
            nid, seen = refers[nid], seen + 1
        return nid

    def place(nid):
        """The synsets a node stands in, and how they were found."""
        n = nodes.get(nid) or {}
        lang = n.get("lang")
        lem = norm(n.get("lemma") or "")
        if lem in DIVINE:
            return ["god.n.01"], "a divine name"
        exact = (lang, "=" + (n.get("lemma") or ""))
        if exact in places and not n.get("proper"):
            return senses(places[exact], n.get("text")), "its glosses"
        if (lang, lem) in places and not n.get("proper"):
            return senses(places[(lang, lem)], n.get("text")), "its glosses"
        t = etype.get((n.get("text") or "").strip().lower())
        if t:
            return [TYPE_SYNSET[t]], f"a {t} in the entity store"
        if (lang, lem) in places:
            return senses(places[(lang, lem)], n.get("text")), "its glosses"
        return [], None

    out = []
    stats = collections.Counter()
    for ct, r in roles.items():
        if "s" not in r or "p" not in r or \
                ct.replace("#ct", "#cl") in headings:
            continue
        if a.verse and not ct.startswith(a.verse + "#"):
            continue
        s, p = resolve(r["s"]), r["p"]
        ss, how_s = place(s)
        ps, how_p = place(p)
        lang = (nodes.get(p) or {}).get("lang") or "?"
        rec = {"ct": ct, "ref": ct.split("#")[0], "lang": lang,
               "subject": (nodes.get(s) or {}).get("text"),
               "predicate": (nodes.get(p) or {}).get("text"),
               "subject_via": how_s, "predicate_via": how_p}
        nominal = {"noun", "pron"}
        if any(wclass.get(i) == "prep" for i in p_ids.get(ct, [])):
            # "two rings [are] on its side": where, not what
            rec["verdict"] = "prepositional"
        elif (nodes.get(p) or {}).get("class") != "noun" or \
                (nodes.get(s) or {}).get("class", "noun") not in nominal:
            # "her appearance [was] ugly", "these [are] the generations":
            # an adjective or a pointing word, not a naming
            rec["verdict"] = "not two nouns"
        elif not ss or not ps:
            rec["verdict"] = "unplaced"
        else:
            c, depth, pair = clash(ss, ps)
            rec.update(meet_depth=depth, pair=pair)
            if not c:
                rec["verdict"] = "same kind"
            else:
                # the predicate's USUAL sense (commonest gloss, commonest
                # sense) says whether it is a thing one can picture
                lex = wn.synset(ps[0]).lexname()
                rec["verdict"] = "image" if lex in PICTURABLE else "quality"
                rec["vehicle_class"] = lex
        stats[(lang, rec["verdict"])] += 1
        out.append(rec)
    for e in simile_pp:
        if a.verse and e["ref"] != a.verse:
            continue
        v = nodes.get(e["dst"]) or {}
        ps, how = place(e["dst"])
        if not ps and v.get("composite"):
            # "like a lion and a lioness": the first member's place
            first = next((x["dst"] for x in member_of.get(e["dst"], [])), None)
            ps, how = place(first) if first else ([], None)
        lex = wn.synset(ps[0]).lexname() if ps else None
        # כְּ and ὡς also mean "according to", "about", "when": "like the
        # word" is mostly ACCORDING TO the word. A simile only where what it
        # is likened to can be pictured.
        verdict = "simile" if lex in CONCRETE or lex == "noun.animal" \
            else "comparison"
        rec = {"ct": e["src"], "ref": e["ref"], "lang": e["lang"],
               "verdict": verdict, "marker": e.get("prep"),
               "vehicle": v.get("text"), "vehicle_class": lex}
        stats[(e["lang"], verdict)] += 1
        out.append(rec)

    print("COPULAR CLAUSES ('X is Y') AND SIMILES, by what the form shows:")
    for lang in ("hebrew", "greek"):
        tot = sum(v for (l, _), v in stats.items() if l == lang)
        print(f"  {lang}: " + ", ".join(
            f"{k} {stats[(lang, k)]:,}" for k in
            ("same kind", "image", "quality", "unplaced", "prepositional",
             "not two nouns", "simile", "comparison")))
    rng = random.Random(4)
    for verdict in ("image", "quality", "same kind", "simile"):
        pool = [r for r in out if r["verdict"] == verdict]
        print(f"\n{verdict.upper()} — sample:")
        for r in rng.sample(pool, min(12, len(pool))) if not a.verse else pool:
            if verdict == "simile":
                print(f"  {r['ref']:10} like {r['vehicle']}  "
                      f"({r['vehicle_class']})")
            else:
                print(f"  {r['ref']:10} {r['subject']} | {r['predicate']}  "
                      f"{r.get('pair')} meet@{r.get('meet_depth')}")
    if a.write and not a.verse:
        with gzip.open(OUT / "meaning-figures.jsonl.gz", "wt",
                       encoding="utf-8") as f:
            for r in out:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"\nwrote {len(out):,} rows to out/meaning-figures.jsonl.gz")


if __name__ == "__main__":
    main()
