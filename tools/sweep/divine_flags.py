"""THE DIVINE FLAGS, GROUPED FOR A RULING (plan 1.34: "Anything touching God, the
Father, Jesus or the Holy Spirit is held for a hand ruling"; 2026-10-17: the sheet, item
3 of the list chosen).

Every choice the two sweep passes flagged divine (a referent, or a speech's
speaker or addressee), with the word it names, sorted into patterns:
  speaker's own "I"     a first person inside a speech whose speaker is that
                        same divine person, named in the same speech
  addressed "you"       a second person inside a speech or prayer addressed to
                        that divine person
  "he" after the name   a third person after the name, in the same passage
  speaker / addressee   a speech's sender or addressee
and the identity-bearing ones apart: where the word chosen and the word in the
text differ in kind (a "Lord" read as Jesus or as God, "the angel of the LORD"
read as the LORD, a "Spirit" read as the Holy Spirit). Those are never ruled
as a pattern (memory: divine persons by hand).

    python tools/sweep/divine_flags.py   -> out/sweep/divine-flags.json, counts
"""
import collections
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIRST = ROOT / "out" / "sweep" / "runs" / "sweep-1"
MERGED = ROOT / "out" / "sweep" / "runs" / "resolve-1" / "merged"


def nodes_index():
    ix = {}
    with gzip.open(ROOT / "out" / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("word") or d.get("composite") or d.get("voice"):
                ix[d["id"]] = {"text": d.get("text"), "lemma": d.get("lemma"), "strong": d.get("strong")}
    return ix


def labels(c, ref, ix):
    """A choice's words: an id, a list of them (several together), or a
    generic entity the second pass made ({"new": ...})."""
    if isinstance(c, list):
        return [x for y in c for x in labels(y, ref, ix)]
    if isinstance(c, dict):
        return [c.get("new") or "?"]
    full = c if "#" in str(c) else f"{ref}#{c}"
    return [(ix.get(full) or {}).get("text") or str(c)]


def person(morph):
    m = (morph or "").split("/")[0]
    return {"first": "1", "second": "2", "third": "3"}.get(m, "?")


def main():
    ix = nodes_index()
    rows = []
    for p in sorted(FIRST.glob("*.json")):
        if not re.match(r"^[1-3]?[A-Z][a-z]{1,2}\.\d+\.\d+\.json$", p.name):
            continue
        ref = p.stem
        src = MERGED / p.name if (MERGED / p.name).exists() else p
        a = json.loads(src.read_text(encoding="utf-8"))
        for r in a.get("referents") or []:
            if not r.get("divine"):
                continue
            ch = r.get("choice")
            labs = labels(ch, ref, ix)
            rows.append({"ref": ref, "kind": "referent", "slot": r.get("slot"), "choice": ch, "names": labs,
                         "confidence": r.get("confidence"), "why": r.get("why"), "by": r.get("resolved_by") or "first pass"})
        for g in a.get("groups") or []:
            if g.get("divine") and g.get("kind") == "turn":
                for m in g.get("members") or []:
                    if m.get("role") in ("sender", "addressee"):
                        # a speaker may be a list from the second pass (several together)
                        names = labels(m["node"], ref, ix)
                        rows.append({"ref": ref, "kind": m["role"], "choice": m["node"], "names": names,
                                     "confidence": g.get("confidence"), "why": g.get("why"), "by": "first pass"})
    c = collections.Counter((r["kind"], " + ".join(r["names"])) for r in rows)
    print(f"{len(rows):,} divine-flagged decisions in {len({r['ref'] for r in rows}):,} verses")
    for k, v in c.most_common(25):
        print(f"  {v:6,}  {k[0]:10s} {k[1]}")
    (ROOT / "out" / "sweep" / "divine-flags.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
