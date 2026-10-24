"""About's pictures stay true to the data (2026-10-20: the schema map
mock belongs in the About; the hybrid puts its pictures beside their text).

The About page shows four statements and the standing of each. If the data
moves (a reading releases Gen 3:15, a speaker credit changes), the page would
go on saying something false. So each example is checked against the store, and
a planted change to each must be caught.

  1Sam 16:21 Saul — loved — David      stated: shown, the narrator's (John 3:16
             until 2026-10-20: the Berean prints it inside Jesus's words, D2(a))
  Gen 12:2   God — make — Abraham      described as promised, in God's voice
  Gen 3:15   God — put — enmity        held
  Job 15:6   Job described as ...      Eliphaz's claim

    python tests/test_about_primer.py          (preflight runs it so)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def statements():
    return [json.loads(x) for x in (ROOT / "ontology" / "relations" / "verb-statements.jsonl").read_text(
        encoding="utf-8").splitlines() if x.strip()]


def relations():
    out = []
    for p in sorted((ROOT / "ontology" / "relations").glob("*.jsonl")):
        out += [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return out


def standing(r):
    return "held" if r.get("held") else "described" if r.get("described") else "shown"


def faults(rows, rels, page):
    out = []

    def find(ref, src, dst, label=None):
        return [r for r in rows if ref in r["refs"] and r["src"] == src and r["dst"] == dst
                and (label is None or label in (r.get("label"), r.get("label_plain")))]
    j = find("1Sam 16:21", "saul", "david", "loved")
    if not j or standing(j[0]) != "shown" or j[0].get("claimed_by"):
        out.append("1 Sam 16:21 'Saul loved David' is no longer stated in the narrator's voice")
    # and John 3:16 must not come back as the narrator's (D2(a)): About no
    # longer claims it, and the Berean's marks put it in Jesus's words
    j3 = find("John 3:16", "god", "world", "loved")
    if j3 and standing(j3[0]) == "shown" and not j3[0].get("claimed_by"):
        out.append("John 3:16 is stated in the narrator's voice again, against the Berean's quotation marks")
    g = find("Gen 12:2", "god", "abraham", "make")
    if not g or standing(g[0]) != "described" or g[0].get("modality") != "promised" or g[0].get("claimed_by") != "god":
        out.append("Gen 12:2 'I will make you' is no longer God's promise, described")
    h = find("Gen 3:15", "god", "enmity")
    if not h or standing(h[0]) != "held":
        out.append("Gen 3:15 'put enmity' is no longer held")
    e = [r for r in rels if "Job 15:6" in (r.get("refs") or []) and r.get("src") == "job"
         and r.get("claimed_by") == "eliphaz_the_temanite"]
    if not e:
        out.append("Job 15:6 is no longer Eliphaz's claim about Job")
    for must in ("Saul loved David", "Gen 12:2", "Gen 3:15", "Job 15:6", "וַיֶּאֱהָבֵהוּ", "data-open=\"a-floor\""):
        if must not in page:
            out.append(f"About no longer shows {must!r}")
    return out


def main():
    rows, rels = statements(), relations()
    page = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
    fails = faults(rows, rels, page)
    # PLANTED: each example moved, one at a time, must be caught
    planted = []
    for ref, change in (("1Sam 16:21", {"held": "planted"}), ("Gen 12:2", {"described": None, "modality": "stated"}),
                        ("Gen 3:15", {"held": None}), ("John 3:16", {"held": None, "described": None})):
        moved = [dict(r, **change) if ref in r["refs"] else r for r in rows]
        if not faults(moved, rels, page):
            planted.append(f"planted: {ref} moved and was not caught")
    if not faults(rows, [r for r in rels if "Job 15:6" not in (r.get("refs") or [])], page):
        planted.append("planted: Eliphaz's claim removed and was not caught")
    fails += planted
    print(f"About's pictures: 4 examples against the store, and John 3:16 kept out of the narrator's voice; "
          f"5 planted moves; {len(fails)} failures")
    for f in fails:
        print("FAIL " + f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
