"""Doug's sheet for the zero-relation pass, from zero_final.json. Usage: zero_sheet.py out.md"""
import json, sys, glob, os, yaml
from pathlib import Path
from collections import defaultdict
S = Path(__file__).parent
ROOT = Path(r"<local> Ontology\.claude\worktrees\ubs-lexicon-word-verse-c23765")
sys.path.insert(0, str(S))
import zero_verdicts as V
f = json.load(open(S / "zero_final.json", encoding="utf-8"))
chk = json.load(open(S / "zero_checked.json", encoding="utf-8"))
cards = {c["id"]: c for c in json.load(open(S / "zero_cand.json", encoding="utf-8"))}
types = yaml.safe_load(open(ROOT / "ontology/schema/relationship_types.yaml", encoding="utf-8"))["types"]
name = {}
for ef in glob.glob(str(ROOT / "ontology/entities/*.jsonl")):
    for ln in open(ef, encoding="utf-8"):
        if ln.strip():
            e = json.loads(ln)
            if "id" in e: name.setdefault(e["id"], e.get("name") or e["id"])
DIVINE = {"god", "jesus", "holy_spirit", "the_father", "seven_spirits_of_god", "angel_of_the_lord"}
lab = lambda t: (types[t].get("label") or t).replace("_", " ")
N = lambda i: name.get(i, i)

proposed = {(r["src"], r["type"], r["dst"]) for r in chk["pass"]}
def how(r):
    t = (r["src"], r["type"], r["dst"])
    if r["type"] == "camped_at" and r["src"] in ("children_of_israel", "ezra") and t not in proposed:
        return "added"
    if r["src"] in ("nahor_son_of_terah", "milcah") and t not in proposed:
        return "added"
    return "kept" if t in proposed else "changed"

groups = defaultdict(list)
for r in f["relations"]:
    groups["divine" if {r["src"], r["dst"]} & DIVINE else how(r)].append(r)
line = lambda r: (f"- **{N(r['src'])}** {lab(r['type'])} **{N(r['dst'])}** ({', '.join(r['refs'])}): "
                  f"\"{(r.get('note') or '').strip()[:200]}\"")
rel_ = f.get("release", [])
reached = {c for c in cards if any(c in (x["src"], x["dst"]) for x in f["relations"])} | {s for _, _, s in rel_ if s in cards}
md = [f"# Cards with no relation: the proposed relations (P-2026-11-18-5)", "",
      f"Built 2026-11-19. Of **{len(cards)}** cards with no relation, these **{len(f['relations'])}** new relations and "
      f"**{len(rel_)}** released ones reach **{len(reached)}**. Each new one was proposed by DeepSeek from the card's own verse (blind, the published relation "
      "definitions as the only types), checked mechanically (ids, kinds, direction, the verse is the card's, the quote "
      "is in it, not already held), then read by Claude against the verse. Recommendation: **add all, as listed**; "
      "override by number or name.", "",
      "How to rule: \"as recommended\", or name what to leave out.", ""]
for g, title in [("kept", "Kept as DeepSeek proposed"), ("changed", "Changed by Claude on reading (the corrected form)"),
                 ("added", "Added by Claude by rule (each read): the itinerary camps"),
                 ("divine", "Touching God, Jesus, the seven spirits or the angel of the LORD (relations only; no record merged or renamed)")]:
    md += [f"## {title} ({len(groups[g])})", ""] + [line(r) for r in sorted(groups[g], key=lambda r: (r["refs"][0], r["src"]))] + [""]
    if g == "added":
        md += ["They camped at each stop of Num 33 (and Num 21:10-11): \"They set out from X and camped at Y\". \"They\" is the "
               "Israelites: \"These are the journeys of the Israelites\" (Num 33:1). DeepSeek could not wire these because the "
               "Israelites were not among its candidates. Only \"camped at\" or \"in the mountains of\" the card's own name was "
               "counted; \"near Migdol\" and \"opposite Baal-zephon\" were not.", ""]
md += [f"## Released: already recorded, held as quoted speech ({len(rel_)})", "",
       "Nahor's and Milcah's sons were recorded from Gen 22:20-22 and held, because those verses are an unnamed report to "
       "Abraham (\"Abraham was told, ...\"). Gen 22:23 is the narrator's, outside the quotation marks: \"Milcah bore these "
       "eight sons to Abraham's brother Nahor.\" Releasing them cites that verse. Kemuel as Aram's father is said only "
       "inside the report (v21) and stays held.", ""] + \
      [f"- **{N(p)}** {lab(t)} **{N(s)}** (Gen 22:23)" for p, t, s in rel_] + [""]
md += [f"## Dropped on reading ({len(f['dropped'])})", ""] + \
      [f"- {N(x['src'])} {lab(x['type'])} {N(x['dst'])} ({x['ref']}): {x['why']}" for x in f["dropped"]] + [""]
md += ["## Still with no relation", "",
       f"{len(cards) - len(reached)} cards. Their panels keep showing what their verses name. Most common reasons in "
       "DeepSeek's \"none\": a border-list point (Joshua's boundary verses state a route, not a relation), a general "
       "word card (\"go\", \"keep\", \"lest\"), or a fact with no type yet (near, between, visiting, owning).", ""]
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(md))
print({g: len(v) for g, v in groups.items()}, len(reached), "reached")
