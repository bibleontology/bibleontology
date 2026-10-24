"""Re-lay the concept sort onto the entity store. **Run after every merge.**

    python -m bibleont.conceptsort apply [--dry]

The entity store's `concept` type had become a catch-all: a manger, a viper
and bronze sat beside adoption and holiness. 2026-09-28, sorting them:
ideas stay concepts, things become what they are, images become images,
going with the LLM analysis and marking it as such. The decisions are
standing data in `ontology/concept-sort.json` (each with its verdict and the
reason), read by Claude against every record's cited verses; the review list
is `docs/review/CONCEPT-SORT.md`, the design `docs/MEANING-ONTOLOGY.md`.

WHY A COMMAND AND NOT AN EDIT. `merge` rebuilds the entity file from the
staged batches and deletes every relation file, so a sort written once
would vanish at the next merge — silently, which is the pipeline working
correctly (lemma.py says the same of lemma tags). So, like `lemma apply`,
this is derived and re-applied, and merge prints the reminder.

What it does to each decided record:
  - `type` and `attrs.kind` set as decided; the old type kept as
    `attrs.legacy_type`; the decision as `attrs.sorted` = {by, verdict, why}
    — marked as the LLM reading it is;
  - **both**: the record keeps its literal verses, and a new record
    `image_<id>` (type image) takes the figurative ones, joined by
    `drawn_from` — the thing and its image are two nodes (the old graph's
    own relation: "the lion of 1 Peter 5:8 and the lion Daniel was shut in
    with are not one node");
  - **edge** (heart, face, flesh ...): stays a concept, kind
    `extended_sense`.

Idempotent: a second run writes nothing. Untouched rows keep their text
and the file keeps its own line ending (the lemma writer once rewrote all
8,416 rows and buried 322 real changes in the diff).
"""
from __future__ import annotations

import io
import json
import sys

from .paths import ONTOLOGY, RELATIONS_DIR

DECISIONS = ONTOLOGY / "concept-sort.json"
ENTITIES = ONTOLOGY / "entities" / "entities.jsonl"
SOURCE = "concept-sort"                  # the derived relation file's stem
BY = "LLM reading: Claude Opus 5.5, 2026-09-28"


def _decisions() -> dict:
    return json.loads(DECISIONS.read_text(encoding="utf-8"))["decisions"]


def apply(dry: bool = False) -> dict:
    dec = _decisions()
    text = io.open(ENTITIES, encoding="utf-8", newline="").read()
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = [l for l in text.split(eol) if l.strip()]
    rows = [json.loads(l) for l in lines]
    ids = {r["id"] for r in rows}
    out_lines, changed, added, relations = [], 0, 0, []
    for line, r in zip(lines, rows):
        d = dec.get(r["id"])
        attrs = dict(r.get("attrs") or {})
        legacy = attrs.get("legacy_type", r.get("type"))
        if not d or legacy != "concept":
            out_lines.append(line)
            continue
        new = dict(r)
        attrs["legacy_type"] = "concept"
        attrs["sorted"] = {"by": BY, "verdict": d["verdict"], "why": d["why"]}
        if d.get("kind"):
            attrs["kind"] = d["kind"]
        new["type"] = d["type"]
        fig = d.get("figurative_refs") or []
        if fig:
            new["refs"] = [x for x in (r.get("refs") or []) if x not in fig]
        new["attrs"] = attrs
        if json.dumps(new, sort_keys=True) == json.dumps(r, sort_keys=True):
            out_lines.append(line)
        else:
            out_lines.append(json.dumps(new, ensure_ascii=False,
                                        sort_keys=True))
            changed += 1
        if fig:
            iid = f"image_{r['id']}"
            relations.append({
                "certainty": "implied", "dst": r["id"],
                "note": "The same word, and not the same thing: the record "
                        "keeps its literal verses; this image takes the "
                        "verses where the word is used as a picture.",
                "refs": fig, "source": SOURCE, "src": iid,
                "type": "drawn_from"})
            if iid not in ids:
                out_lines.append(json.dumps({
                    "attrs": {"legacy_type": "concept", "sorted": {
                        "by": BY, "verdict": d["verdict"],
                        "why": d["why"] + " — the figurative verses"}},
                    "gender": "unknown", "id": iid,
                    "name": f"{r['name']} (as an image)",
                    "refs": fig, "source": SOURCE, "type": "image"},
                    ensure_ascii=False, sort_keys=True))
                ids.add(iid)
                added += 1
    if not dry:
        if changed or added:
            with io.open(ENTITIES, "w", encoding="utf-8", newline="") as fh:
                fh.write(eol.join(out_lines) + eol)
        RELATIONS_DIR.mkdir(parents=True, exist_ok=True)
        rel = RELATIONS_DIR / f"{SOURCE}.jsonl"
        body = "".join(json.dumps(x, ensure_ascii=False, sort_keys=True) +
                       "\n" for x in sorted(relations,
                                            key=lambda x: x["src"]))
        if not rel.exists() or rel.read_text(encoding="utf-8") != body:
            rel.write_text(body, encoding="utf-8")
    return {"decided": len(dec), "changed": changed, "images_added": added,
            "drawn_from": len(relations)}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] != "apply":
        print(__doc__)
        return 2
    print(apply(dry="--dry" in argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
