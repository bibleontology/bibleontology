"""Write ontology/concept-sort.json from the reading (concept_verdicts.py).

The reading is the one place a verdict is changed; this turns it into the
standing decisions `python -m bibleont.conceptsort apply` lays onto the
entity store after every merge.

    python tools/meaning/export_concept_sort.py
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from concept_verdicts import V  # noqa: E402

KIND = {"Artifact": "artifact", "Plant": "plant", "Food": "food",
        "Substance": "substance", "NaturalObject": "natural_object",
        "BodyPart": "body_part", "Possession": "possession"}
GROUP = {"company": "company", "two_bands": "company", "gods_host": "company",
         "fathers_house": "household", "posterity": "people",
         "all_mankind": "people", "humankind": "people"}
# the verses where a "both" record is used as a picture (the rest stay with
# the thing)
BOTH_FIG = {"brass": ["Job 6:12"], "bearing_fruit": ["Ps 1:3", "Ps 92:14"],
            "clothes": ["Job 9:31"], "covering": ["Job 22:14"],
            "ox": ["Job 6:5", "Job 40:15"]}


def decision(i, v, why):
    d = {"verdict": v, "why": why}
    kind, _, cls = v.partition(":")
    if kind in ("thing", "both"):
        d["type"] = "creature" if cls == "Animal" else \
            "place" if cls == "Place" else "object"
        if cls in KIND:
            d["kind"] = KIND[cls]
        if kind == "both":
            d["figurative_refs"] = BOTH_FIG[i]
    elif kind == "image":
        d["type"] = "image"
    elif kind == "edge":
        d["type"], d["kind"] = "concept", "extended_sense"
    elif v == "other:group":
        d["type"], d["kind"] = "group", GROUP[i]
    elif v == "other:place":
        d["type"], d["kind"] = "place", "sacred_site"
    elif v == "other:time":
        d["type"], d["kind"] = "concept", "time"
    else:
        d["type"] = "concept"
    return d


def main():
    out = {i: decision(i, v, why) for i, (v, why) in sorted(V.items())}
    doc = {
        "_what": "Standing decisions: the entity store's `concept` records "
                 "re-sorted (docs/MEANING-ONTOLOGY.md; review list "
                 "docs/review/CONCEPT-SORT.md). Applied after every merge by "
                 "`python -m bibleont.conceptsort apply`. Written by "
                 "tools/meaning/export_concept_sort.py from "
                 "tools/meaning/concept_verdicts.py — change a verdict THERE.",
        "_by": "LLM reading: Claude Opus 5.5, 2026-09-28 — every record read "
               "against its cited verses (BSB, and the Hebrew where they "
               "differ). Doug, 2026-09-28: 'I would go with the llm analysis "
               "and mark it as such.'",
        "_rules": [
            "The record keeps its old type as attrs.legacy_type and the "
            "decision as attrs.sorted (by, verdict, why).",
            "both: the thing keeps its literal verses; an image record "
            "image_<id> (the existing one, where the store has it) takes the "
            "figurative ones, joined by drawn_from — the thing and its image "
            "are two nodes.",
            "edge: a word whose ordinary biblical sense is inner or abstract "
            "(heart, face, flesh): stays a concept, kind extended_sense — the "
            "meaning schema's extendedFrom.",
            "idea: stays a concept; recorded so the decision is visible."],
        "decisions": out}
    (ROOT / "ontology" / "concept-sort.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print(collections.Counter(
        d["type"] + ("/" + d["kind"] if "kind" in d else "")
        for d in out.values()).most_common())


if __name__ == "__main__":
    main()
