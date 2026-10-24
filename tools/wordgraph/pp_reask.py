"""FAMILY-ONLY ANSWERS WHOSE REASON NAMES A TYPE (plan 2.13; approved as
P-2026-10-18-9). Leviticus 11:32's "any of them" was named only the family
between_things while the judge's own reason said "partitive": the answer did
not commit to what it said. These are LISTED for a re-ask, never changed: the
reason is the judge's words, not its answer.

    python tools/wordgraph/pp_reask.py   -> out/wordgraph/reask-family-only.json, a count
"""
import collections
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "out" / "wordgraph" / "prep-phrases-judged-2.jsonl.gz"
DST = ROOT / "out" / "wordgraph" / "reask-family-only.json"


def main():
    pr = json.loads((ROOT / "ontology" / "schema" / "prep_relations.json").read_text(encoding="utf-8"))
    types = {t: f for f, v in pr["families"].items() for t in v["types"]}
    out, by = [], collections.Counter()
    with gzip.open(SRC, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            d = json.loads(line)
            for p in d["pp"]:
                if p.get("level") != "family":
                    continue
                why = (p.get("by") or "").lower()
                # a type of the SAME family, named as a word in the reason
                named = [t for t, fam in types.items() if fam == p["relation"]
                         and re.search(r"\b" + re.escape(t.replace("_", " ")) + r"\b", why.replace("_", " "))]
                # what it is made of, said before the type existed (Matthew 3:4:
                # "material of the garment, 'of camel's hair'")
                if p["relation"] == "between_things" and not named and re.search(r"\b(made of|material)\b", why):
                    named = ["composed_of"]
                if named:
                    out.append({"id": p["id"], "verse": d["ref"], "family": p["relation"], "reason_names": named,
                                "why": p.get("by")})
                    by[(p["relation"], named[0])] += 1
    DST.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} family-only answers whose reason names a type -> {DST.relative_to(ROOT)}")
    print(dict(by.most_common(12)))


if __name__ == "__main__":
    main()
