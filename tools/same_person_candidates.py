"""Candidates for "possibly the same person": one person under two spellings.

2026-10-12, on the navigator centred on David: Shimeah and Shammua are likely
the same person, but they do not get the Rahab treatment; the question was
whether these candidates can be found deterministically in the graph. The
signal: two person records that stand in the SAME relation to the SAME
person (both "son of David", both "brother of David") and whose names reduce
to the same consonants -- the variant spellings of parallel lists (Shammua,
2 Sam 5:14; Shimea, 1 Chr 3:5). Measures only; changes nothing. Each pair is
a candidate for a judgment, then `possibly_same_as` (as Rahab, P-100), never
a merge by rule.

    python tools/same_person_candidates.py      -> out/same-person-candidates.json
"""
import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIN = {"father_of": "child", "mother_of": "child", "sibling_of": "sibling", "half_sibling_of": "sibling",
       "spouse_of": "spouse", "son_of": "parent", "child_of": "parent"}


def skeleton(name):
    """the consonants of a name, as transliterations vary them: vowels and the
    weak letters h, w, y dropped, doubled letters single (Shammua, Shimea,
    Shimeah, Shammah, Shimma -> 'sm')"""
    s = re.sub(r"[^a-z]", "", (name or "").lower())
    s = s.replace("sh", "s").replace("ch", "k").replace("ph", "f").replace("th", "t")
    s = re.sub(r"[aeiouhwy]", "", s)
    return re.sub(r"(.)\1+", r"\1", s)


def main():
    ents = {}
    for p in (ROOT / "ontology" / "entities").glob("*.jsonl"):
        for ln in open(p, encoding="utf-8"):
            if ln.strip():
                e = json.loads(ln)
                ents[e["id"]] = e
    linked = set()                  # pairs already said to be one or possibly one
    by = collections.defaultdict(set)   # (anchor, role) -> person ids
    for p in (ROOT / "ontology" / "relations").glob("*.jsonl"):
        for ln in open(p, encoding="utf-8"):
            if not ln.strip():
                continue
            r = json.loads(ln)
            a, b, t = r.get("src"), r.get("dst"), r.get("type")
            if t in ("possibly_same_as", "same_as", "alias_of"):
                linked.add(frozenset((a, b)))
            if t in ("possibly_same_as", "same_as", "alias_of"):
                continue
            # WIDENED (2026-10-13: the scan was widened): any relation, not
            # only kinship -- two people in the same relation to the same
            # record (members of one group, officers of one king, names in
            # one list), read from either end
            if (ents.get(b) or {}).get("type") == "person" and a in ents:
                by[(a, KIN.get(t, t) + ">")].add(b)
            if (ents.get(a) or {}).get("type") == "person" and b in ents:
                by[(b, KIN.get(t, t) + "<")].add(a)
    out, seen = [], set()
    for (anchor, role), ids in by.items():
        # a small, closed set only: a family, one king's officers, one list.
        # Widened first to every anchor, it found 182 -- Joseph the patriarch
        # and Joseph of Nazareth both "traveled to Egypt"; a place or a large
        # group gathers namesakes from a thousand years apart
        if len(ids) > 40 or (ents.get(anchor) or {}).get("type") == "place":
            continue
        ids = sorted(ids)
        for i, x in enumerate(ids):
            for y in ids[i + 1:]:
                pair = frozenset((x, y))
                if pair in seen or pair in linked:
                    continue
                kx, ky = skeleton(ents[x].get("name")), skeleton(ents[y].get("name"))
                # named side by side in one verse, they are two (Medan and
                # Midian, Gen 25:2; Ishvi and Ishvah, 1 Chr 7:30) -- the first
                # run's four false candidates all shared a verse
                if set(ents[x].get("refs") or []) & set(ents[y].get("refs") or []):
                    continue
                if len(kx) >= 2 and kx == ky:
                    seen.add(pair)
                    same = (ents[x].get("name") or "").lower() == (ents[y].get("name") or "").lower()
                    out.append({"kind": "duplicate record" if same else "variant spelling",
                                "anchor": anchor, "anchor_name": ents[anchor].get("name"), "role": role,
                                "a": x, "a_name": ents[x].get("name"), "a_refs": (ents[x].get("refs") or [])[:3],
                                "b": y, "b_name": ents[y].get("name"), "b_refs": (ents[y].get("refs") or [])[:3],
                                "skeleton": kx})
    out.sort(key=lambda c: (c["kind"], c["anchor_name"] or "", c["role"]))
    (ROOT / "out" / "same-person-candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                              encoding="utf-8")
    print(f"{len(out)} candidate pairs (same relation to the same person, same consonants)")
    for c in out[:40]:
        print(f"  [{c['kind']}] {c['role']} of {c['anchor_name']}: {c['a_name']} {c['a_refs'][:2]}  ~  {c['b_name']} {c['b_refs'][:2]}")


if __name__ == "__main__":
    main()
