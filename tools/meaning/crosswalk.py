"""The entity store's types onto the proposed meaning ontology — and a test
of how good those types are, by two methods that never saw them.

2026-09-28: the existing types were not bad, so that progress is not to be
lost. So every record of ontology/entities/entities.jsonl
lands somewhere, its type and kind kept verbatim (bom:legacyType,
bom:legacyKind), and the claim "not bad" is measured rather than assumed:

  1. THE CROSSWALK: each type to its layer and class; counts.
  2. AGAINST WORDNET: records that carry a Hebrew/Greek lemma (attrs.lemma)
     are placed by tools/meaning/categorize.py through their glosses. Does
     the category agree with the class the type maps to?
  3. AGAINST THE STRUCTURE: a person SPEAKS (a name that is the subject of
     a verb of saying); a place is gone TO, FROM or dwelt IN (a name after
     אֶל, מִן, בְּ, εἰς, ἐκ, ἐν, ἀπό). For names the store types person or
     place, how often does the structure's evidence agree?

    python tools/meaning/crosswalk.py
"""
import collections
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "builder"))
from source import norm  # noqa: E402

CROSSWALK = {
    # type        layer                       class
    "person":      ("3 referent",  "PersonalBeing"),
    "being":       ("3 referent",  "PersonalBeing (+ predications)"),
    "place":       ("3 referent",  "Place"),
    "group":       ("3 referent",  "Group"),
    "creature":    ("3 referent",  "Animal"),
    "object":      ("3 referent",  "Artifact"),
    "event":       ("3 referent",  "Event"),
    "observance":  ("3 referent",  "Event (observance)"),
    "covenant":    ("3 referent",  "Communication (covenant)"),
    "concept":     ("2 sense",     "Concept"),
    "title":       ("2 sense",     "Title"),
    "image":       ("4 figure",    "Image"),
    "assessment":  ("3 referent",  "Predication"),
    "text":        ("4 figure",    "Saying (+ told world)"),
    "passage":     ("structure",   "a section (kinds.json)"),
    "pattern":     ("patterns",    "a pattern (Step 6)"),
}
# the class a WordNet top category means, per crosswalked type
EXPECT = {"person": {"PersonalBeing"}, "being": {"PersonalBeing"},
          "place": {"Place", "NaturalObject"}, "group": {"Group"},
          "creature": {"Animal"}, "object": {"Artifact", "NaturalObject",
                                             "Substance", "Food", "BodyPart",
                                             "Plant", "Animal", "Possession"},
          "event": {"Event", "Act", "State"},
          "observance": {"Event", "Act", "Time"}}
# "to Moses" (אֶל) is who is SPOKEN TO, the commonest clause in the Torah:
# a place is gone to, come from, dwelt in — by a verb of motion or dwelling
LOCATIVE = {"אל", "מן", "ב", "ל", "εις", "εκ", "εν", "απο", "προς"}
SPEECH = {"אמר", "דבר", "ענה", "קרא", "צוה", "λεγω", "λαλεω", "αποκρινομαι",
          "φημι"}
MOTION = {"הלך", "בוא", "יצא", "עלה", "ירד", "שוב", "ישב", "נסע", "עבר",
          "ברח", "גלה", "שלח", "חנה", "ερχομαι", "πορευομαι", "εξερχομαι",
          "εισερχομαι", "απερχομαι", "αναβαινω", "καταβαινω", "κατοικεω",
          "υποστρεφω", "πεμπω"}


def main():
    E = [json.loads(l) for l in open(ROOT / "ontology" / "entities" /
                                    "entities.jsonl", encoding="utf-8")]
    # ---- 1. the crosswalk
    by = collections.Counter(e.get("type") for e in E)
    print(f"THE CROSSWALK: {len(E):,} records, every one placed; type and "
          f"kind kept verbatim")
    for t, n in by.most_common():
        layer, cls = CROSSWALK.get(t, ("?", "UNPLACED"))
        print(f"  {t:11} {n:>5,}  ->  layer {layer:11} {cls}")
    unplaced = sum(n for t, n in by.items() if t not in CROSSWALK)
    print(f"  unplaced: {unplaced}")

    # ---- 2. against WordNet, where a record carries its lemma. The store's
    # "lemma" is a STEPBible Strong's code (H8441); joined to the word
    # graph's lexemes by number, then to their categories.
    cat = {}
    for line in gzip.open(OUT / "meaning-categories.jsonl.gz", "rt",
                          encoding="utf-8"):
        r = json.loads(line)
        if r.get("lemma") and r.get("verdict") in ("decided", "leaning"):
            cat[(r["lang"][0].upper(), norm(r["lemma"]))] = r["class"]
    by_strong = collections.defaultdict(list)
    for line in gzip.open(OUT / "word-lexemes.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if d.get("kind") == "lexeme" and d["strong"]["value"]:
            lang = d["lang"]["value"]
            s = "".join(ch for ch in str(d["strong"]["value"]) if ch.isdigit())
            by_strong[("H" if lang in "HA" else "G", s.lstrip("0"))].append(
                (("H" if lang in "HA" else "G"), norm(d["lemma"]["value"])))
    ABSTRACT = {"Feeling", "Cognition", "Communication", "Attribute",
                "Quantity", "Possession", "Relation", "Shape", "Motive",
                "State", "Act", "Event", "Time", "Abstraction"}
    agree = collections.Counter()
    miss = collections.defaultdict(list)
    for e in E:
        code = (e.get("attrs") or {}).get("lemma") or ""
        t = e.get("type")
        if not code or t not in ("concept", "image"):
            continue
        digits = "".join(ch for ch in code[1:] if ch.isdigit()).lstrip("0")
        cs = {cat.get(k) for k in by_strong.get((code[:1], digits), [])} - {None}
        if not cs:
            agree[(t, "no category")] += 1
            continue
        ok = bool(cs - ABSTRACT) if t == "image" else bool(cs & ABSTRACT)
        agree[(t, ok)] += 1
        if not ok:
            miss[t].append((e["name"], sorted(cs)))
    print("\nAGAINST WORDNET (records that carry a Strong's code; the category "
          "is reached through glosses, independently of the store). An IMAGE "
          "should be something one can picture; a CONCEPT an abstraction:")
    for t in ("image", "concept"):
        n = agree[(t, True)] + agree[(t, False)]
        if n:
            print(f"  {t:8} agree {agree[(t, True)]:>3} of {n:>3} "
                  f"({agree[(t, True)] / n:.0%})  (no category "
                  f"{agree[(t, 'no category')]})  differ, e.g. {miss[t][:5]}")

    # ---- 3. against the structure, for person and place names
    names = collections.defaultdict(set)
    for e in E:
        if e.get("type") in ("person", "place"):
            names[(e.get("name") or "").strip().lower()].add(e["type"])
    names = {k: next(iter(v)) for k, v in names.items() if len(v) == 1}
    nodes = {}
    for line in gzip.open(OUT / "structure-nodes.jsonl.gz", "rt",
                          encoding="utf-8"):
        n = json.loads(line)
        if n.get("word") and n.get("proper"):
            nodes[n["id"]] = n
        elif n.get("clause"):
            nodes[n["id"]] = n
    ev = collections.defaultdict(collections.Counter)
    for line in gzip.open(OUT / "structure-edges.jsonl.gz", "rt",
                          encoding="utf-8"):
        e = json.loads(line)
        d = nodes.get(e.get("dst"))
        if not d or not d.get("word"):
            continue
        name = (d.get("text") or "").strip().lower()
        if name not in names:
            continue
        cl = nodes.get(e["src"].replace("#ct", "#cl")) or {}
        verb = norm(cl.get("verb_lemma") or "")
        if e["type"] == "s" and verb in SPEECH:
            ev[name]["speaks"] += 1
        elif e["type"] in ("pp", "io") and verb in SPEECH:
            ev[name]["speaks"] += 1          # spoken to: a person
        elif e["type"] == "pp" and verb in MOTION and \
                norm(e.get("prep") or "") in LOCATIVE:
            ev[name]["gone to / from / in"] += 1
    tally = collections.Counter()
    wrong = collections.defaultdict(list)
    for name, c in ev.items():
        sp, lo = c["speaks"], c["gone to / from / in"]
        if sp == lo:
            continue
        says = "person" if sp > lo else "place"
        t = names[name]
        tally[(t, says == t)] += 1
        if says != t:
            wrong[t].append((name, sp, lo))
    print("\nAGAINST THE STRUCTURE (names the store types person or place, "
          "where the structure leans one way):")
    for t in ("person", "place"):
        n = tally[(t, True)] + tally[(t, False)]
        if n:
            print(f"  {t:7} agree {tally[(t, True)]:>4} of {n:>4} "
                  f"({tally[(t, True)] / n:.0%});  structure says otherwise, "
                  f"e.g. {sorted(wrong[t], key=lambda x: -(x[1] + x[2]))[:6]}")


if __name__ == "__main__":
    main()
