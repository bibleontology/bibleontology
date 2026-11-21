"""Write one DeepSeek brief per batch of five zero-relation cards: the verses, the candidate cards, the relation
types the published vocabulary allows between their kinds. Public material only (the Berean text, card names, the
/ns/relation definitions). Usage: zero_brief.py zero_cand.json outdir [ids...]"""
import json, sys, yaml
from pathlib import Path

ROOT = Path(r"<local> Ontology\.claude\worktrees\ubs-lexicon-word-verse-c23765")
cards = json.load(open(sys.argv[1], encoding="utf-8"))
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
only = set(sys.argv[3:])
types = yaml.safe_load(open(ROOT / "ontology/schema/relationship_types.yaml", encoding="utf-8"))["types"]
defs = json.load(open(ROOT / "ontology/schema/relation_definitions.json", encoding="utf-8"))["types"]
SKIP = {"speaks_of", "in_theme", "instance_of", "spoken_in", "states"}
as_list = lambda v: v if isinstance(v, list) else [v]


def allowed(a, b):
    got = []
    for t, s in types.items():
        if t in SKIP or t not in defs:
            continue
        if a in as_list(s.get("src_type")) and b in as_list(s.get("dst_type")):
            got.append(t)
        elif b in as_list(s.get("src_type")) and a in as_list(s.get("dst_type")):
            got.append(t)
    return got


pick = [c for c in cards if c["candidates"] and (not only or c["id"] in only)]
HEAD = """You are reading Bible verses (the Berean Standard Bible) to find relations a verse STATES between named things.

For each CARD below you get: its verses, and CANDIDATES (other records named or cited in those verses). For each card,
list every relation that one of its verses states plainly between the card and a candidate, using ONLY a relation
type from the TYPES list (each with its definition). Rules:
- The verse must say it. Not implied by the wider story, not by tradition, not by what is generally known.
- Direction matters: "src" does the relation to "dst" as the type's definition reads. Use the ids given.
- A card may get none: then say so, with the words that show why.
- At most 4 relations per card; prefer the ones that say what the card IS or DOES in the verse.
- "why" quotes the exact words of the CARD'S verse that state it. Verses marked (before) are context only: use them
  to see who "the king", "he" or "him" is, never as the evidence.

Return ONLY a JSON array, one object per relation: {"card": id, "src": id, "type": type, "dst": id, "ref": "Book 1:2",
"why": "quoted words"}; and for a card with none: {"card": id, "none": true, "why": "..."}.
"""
batches = [pick[i:i + 5] for i in range(0, len(pick), 5)]
for n, b in enumerate(batches):
    parts, tys = [], set()
    for c in b:
        cand = "\n".join(f"    - {x['id']} ({x['type']}): {x['name']}" for x in c["candidates"])
        vs = "\n".join("".join(f"    (before) {x['ref']}: {x['text']}\n" for x in v.get("before") or [])
                       + f"    {v['ref']}: {v['text']}" for v in c["verses"])
        parts.append(f"CARD {c['id']} ({c['type']}): {c['name']}\n  verses:\n{vs}\n  candidates:\n{cand}")
        for x in c["candidates"]:
            tys |= set(allowed(c["type"], x["type"]))
    tl = "\n".join(f"- {t}: {defs[t]['definition'].split('. ')[0][:220]} (reads: src {types[t].get('label', t)} dst; "
                   f"src {'/'.join(as_list(types[t].get('src_type')))}, dst {'/'.join(as_list(types[t].get('dst_type')))})"
                   for t in sorted(tys))
    (out / f"batch-{n:03d}.txt").write_text(HEAD + "\nTYPES:\n" + tl + "\n\n" + "\n\n".join(parts) + "\n", encoding="utf-8")
print(len(pick), "cards in", len(batches), "batches;", sum(1 for c in cards if not c["candidates"]), "cards with no candidates")
