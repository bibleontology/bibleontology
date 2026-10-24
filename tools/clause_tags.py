"""What each clause speaks of: stamps and concepts placed on clauses by a model.

2026-09-28, after the section stamps were pinned to clauses: have Flash take a
second pass at the clause level and assign a strength for every clause that is
matched, the strength corresponding to the confidence (a low 33% and a medium
67% of a high), comparing node by node; and these tags could be added to the
structure expansions in the reader, as they apply 1:1.

Reads the pass-2 answers (one per section: every clause that carries a kept
stamp or an anchored concept, with high / medium / low) and writes one row
per (clause, tag). A READING, credited to its reader; never merged into a
computed layer. The pilot covers 20 sections (2026-09-28).

    python tools/clause_tags.py [answers_dir]   -> out/clause-tags.jsonl.gz

Gzipped since the corpus run (2026-09-29: stored gzipped): 74 MB
as plain text, over GitHub's 50 MB warning.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
WEIGHT = {"high": 1.0, "medium": 0.67, "low": 0.33}      # 2026-09-28
# pass 2b — the owner's form (each pass-1 assertion as made, beside the graph's
# roles) — came out cleaner on the probe verses than pass 2, so it is the
# one shown (2026-09-28)
PATTERN = "p2bout_*.txt"
READER = "DeepSeek Flash (pass 2b, unreviewed)"


def answer(path: Path) -> dict:
    """The answer's JSON, however it is laid out; a missing one is an error
    (a pretty-printed answer was once skipped silently)."""
    t = path.read_text(encoding="utf-8")
    m = re.search(r'\{\s*"section"', t)
    if not m:
        raise SystemExit(f"no answer in {path}")
    # exactly one object from where it starts: an answer may carry a note
    # after it, with braces of its own
    return json.JSONDecoder().raw_decode(t[m.start():])[0]


def main(src: Path) -> None:
    rows, bad, orphans = [], 0, 0
    # the corpus run (tools/stamp_corpus.py) writes one <section>.json per
    # section; the pilot wrote p2bout_*.txt answers — both hold the answer
    pattern = PATTERN if list(src.glob(PATTERN)) else "*.json"
    global READER
    if pattern == "*.json":
        READER = "DeepSeek Flash (corpus run, pass 2b, unreviewed)"
    for f in sorted(src.glob(pattern)):
        j = answer(f)
        for t in j.get("tags", []):
            # Flash's slips, 2026-09-28: a tag named "id" instead of "tag"
            # (Exodus 12, 31 of them) is kept; a clause entry that escaped
            # its tag's list (10 in 6 sections) has no tag and is counted
            raw = t.get("tag") or (t.get("id") if "clauses" in t else None)
            if not raw:
                orphans += 1
                continue
            # a model sometimes names a tag by its whole brief line
            name = re.sub(r"^(stamp|concept):\s*", "", raw).split(" (")[0].strip()
            cs = t.get("clauses", [])
            if not isinstance(cs, list):        # "clauses": true (corpus run, 29 Sep)
                bad += 1
                continue
            for c in cs:
                if not isinstance(c, dict):     # a bare id has no strength: counted, not kept
                    bad += 1
                    continue
                s, cid = c.get("strength"), c.get("id", "")
                if s not in WEIGHT or "#cl" not in cid:
                    bad += 1
                    continue
                rows.append({"clause": cid, "tag": name,
                             "kind": t.get("kind") or "stamp", "strength": s,
                             "weight": WEIGHT[s], "reader": READER,
                             "section": j.get("section")})
    # the clause's own words (its gloss in the original's order), so a tag's
    # page can show what each pinned clause says without another lookup
    want = {r["clause"] for r in rows}
    text = {}
    import gzip
    with gzip.open(OUT / "structure-nodes.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            if '"clause": true' not in line:
                continue
            n = json.loads(line)
            if n["id"] in want:
                text[n["id"]] = n.get("text") or ""
    for r in rows:
        r["text"] = text.get(r["clause"], "")
    with gzip.open(OUT / "clause-tags.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({"_note": "Stamps and concepts a model placed on "
                             "clauses, with strength = confidence (high 1, "
                             "medium 0.67, low 0.33). A reading, shown as one. "
                             "Built by tools/clause_tags.py.",
                             "_reader": READER}) + "\n")
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows):,} clause tags from {len(list(src.glob(pattern)))} "
          f"sections; {bad} entries without a valid strength or clause id; "
          f"{orphans} clause entries outside any tag, dropped")
    p1 = src.parent / "p1"
    if pattern == "*.json" and p1.exists():
        section_tags(p1)


def section_tags(p1: Path) -> None:
    """The section stamps pass 1 did NOT pin to a clause, kept at the
    section's level. 2026-09-29: the section tags are not thrown away just
    because they did not hit nodes; in some cases they apply better to
    sections. Pass 1 judged each September section stamp: pinned to
    clauses (those are the clause tags), GENERAL — the section's drift, no
    clause in particular — or WRONG for the section, with a reason. General
    ones (and those given no clause) are kept as section tags; wrong ones are
    kept as DISPUTED — the September reading said yes, Flash said no — so
    the disagreement stays on record instead of vanishing."""
    out, tally = [], {"general": 0, "disputed": 0}
    for f in sorted(p1.glob("*.json")):
        j = json.loads(f.read_text(encoding="utf-8"))
        for p in j.get("pins", []):
            if not isinstance(p, dict) or not p.get("stamp"):
                continue
            if p.get("wrong"):
                status = "disputed"
            elif p.get("general") or not p.get("clauses"):
                status = "general"
            else:
                continue
            tally[status] += 1
            out.append({"section": j.get("section"), "tag": p["stamp"], "status": status,
                        "confidence": p.get("confidence"), "reason": p.get("reason") or "",
                        "reader": "DeepSeek Flash (corpus run, pass 1, unreviewed)"})
    with (OUT / "section-tags.jsonl").open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"_note": "September section stamps that pass 1 of the corpus run "
                             "did not pin to a clause: 'general' (the section's drift) or "
                             "'disputed' (Flash judged it wrong for the section, with its "
                             "reason). Built by tools/clause_tags.py."}) + "\n")
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"section tags: {tally['general']:,} general, {tally['disputed']:,} disputed")


if __name__ == "__main__":
    # the corpus run's answers when they exist, else the pilot's
    corpus = OUT / "clause-stamping" / "p2b"
    main(Path(sys.argv[1]) if len(sys.argv) > 1
         else corpus if corpus.exists() and any(corpus.glob("*.json")) else OUT / "pin-pilot")
