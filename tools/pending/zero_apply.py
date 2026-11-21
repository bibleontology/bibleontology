"""Apply Claude's verdicts to the checked proposals; write the proposed relations and Doug's sheet.
Usage: zero_apply.py [--seen]   (--seen records every current proposal as read; otherwise unread ones are printed)"""
import json, sys
from pathlib import Path
from collections import defaultdict
S = Path(__file__).parent
sys.path.insert(0, str(S))
import zero_verdicts as V

ROOT = Path(r"<local> Ontology\.claude\worktrees\ubs-lexicon-word-verse-c23765")
d = json.load(open(S / "zero_checked.json", encoding="utf-8"))
cards = {c["id"]: c for c in json.load(open(S / "zero_cand.json", encoding="utf-8"))}
seen_f = S / "zero_seen.json"
seen = set(map(tuple, json.load(open(seen_f)))) if seen_f.exists() else set()
key = lambda r: (r["src"], r["type"], r["dst"], r.get("ref"))
if "--seen" in sys.argv:
    json.dump(sorted(set(key(r) for r in d["pass"]) | seen), open(seen_f, "w")); print("recorded", len(d["pass"])); sys.exit()
unread = [r for r in d["pass"] if key(r) not in seen]
for r in unread:
    print("UNREAD |", r["src"], r["type"], r["dst"], "|", r["ref"], "|", r["verse"][:220])

import yaml
SYM = {t for t, v in yaml.safe_load(open(ROOT / "ontology/schema/relationship_types.yaml", encoding="utf-8"))["types"].items()
       if v.get("symmetric")}
out, dropped = {}, []
def put(src, ty, dst, refs, note, card, verse):
    if ty in SYM and dst < src:
        src, dst = dst, src
    k = (src, ty, dst)
    if k in out:
        out[k]["refs"] = sorted(set(out[k]["refs"]) | set(refs)); return
    out[k] = {"src": src, "type": ty, "dst": dst, "refs": refs, "note": note, "card": card, "verse": verse}

for r in d["pass"]:
    t = (r["src"], r["type"], r["dst"])
    if t in V.DROP: dropped.append((r, V.DROP[t])); continue
    if t in V.DROP_DUP: continue
    if r["type"] == "named_with" and r["src"] in V.REPLACE_NAMED_WITH_AMONG and r["dst"] in V.REPLACE_NAMED_WITH_AMONG:
        continue
    if t in V.FIX:
        for (s, ty, ds) in V.FIX[t]:
            put(s, ty, ds, [r["ref"]], r["why"], r["card"], r["verse"])
        continue
    if r["type"] == "asserted_by" and r["dst"] in V.SPEAKER:
        put(r["src"], "asserted_by", V.SPEAKER[r["dst"]], [r["ref"]], r["why"], r["card"], r["verse"]); continue
    put(r["src"], r["type"], r["dst"], [r["ref"]], r["why"], r["card"], r["verse"])
for a in V.ADD:
    put(a["src"], a["type"], a["dst"], a["refs"], a["note"], a["dst"], "Gen 22:20-23")
# Itinerary stops DeepSeek could not wire because the Israelites were not offered as a candidate (Claude, by rule,
# each read): only a verse saying they camped AT / IN THE MOUNTAINS OF the card's own name; 'near', 'opposite' and
# 'set out from' are not a camp there. 'They' is the Israelites: 'These are the journeys of the Israelites' (Num 33:1).
import re
for cid, name, ref, text in json.load(open(S / "zero_camps.json", encoding="utf-8")):
    if re.search(r"camped (at|in the mountains of) " + re.escape(name) + r"\b", text):
        put("children_of_israel", "camped_at", cid, [ref], text, cid, text)
put("ezra", "camped_at", "river_of_ahava", ["Ezra 8:15"], "'I assembled these exiles at the canal that flows to Ahava, and we camped there three days'",
    "river_of_ahava", "Now I assembled these exiles at the canal that flows to Ahava, and we camped there three days.")

for r in out.values():
    if r["type"] == "asserted_by":
        op = V.OPENER.get((r["dst"], r["refs"][0].rsplit(":", 1)[0]))
        if op and op not in r["refs"]:
            r["refs"] = [op] + r["refs"]
    r["refs"] = r["refs"] + [x for x in V.EXTRA_REFS.get((r["src"], r["type"], r["dst"]), []) if x not in r["refs"]]
rels = list(out.values())
json.dump({"relations": rels, "release": [list(x) for x in V.RELEASE], "dropped": [{"src": r["src"], "type": r["type"], "dst": r["dst"], "ref": r["ref"], "why": w}
           for r, w in dropped]}, open(S / "zero_final.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
covered = {c for c in cards if any(c in (x["src"], x["dst"]) for x in rels)} | {s for _, _, s in V.RELEASE if s in cards}

if "--write" in sys.argv:   # only on Doug's ruling: the new file, and the 14 releases edited in place
    with open(ROOT / "ontology/relations/zero-relation-pass.jsonl", "w", encoding="utf-8", newline="\n") as o:
        for r in sorted(rels, key=lambda r: (r["src"], r["type"], r["dst"])):
            o.write(json.dumps({"certainty": "explicit", "dst": r["dst"], "note": r["note"], "refs": r["refs"],
                                "source": "zero-relation-pass-20261119", "src": r["src"], "type": r["type"]},
                               ensure_ascii=False, sort_keys=True) + "\n")
    p = ROOT / "ontology/relations/gen-1-25.jsonl"
    raw = open(p, "rb").read().decode("utf-8"); nl = "\r\n" if "\r\n" in raw else "\n"
    want, done, lines = set(V.RELEASE), 0, []
    for ln in raw.split(nl):
        if ln.strip():
            r = json.loads(ln)
            if (r["src"], r["type"], r["dst"]) in want and r.get("held", "").startswith("inside quoted speech"):
                del r["held"]; r["refs"] = r["refs"] + [V.RELEASE_REF]; r["note"] = V.RELEASE_NOTE; done += 1
                ln = json.dumps(r, ensure_ascii=False, sort_keys=True)
        lines.append(ln)
    assert done == len(want), (done, len(want))
    open(p, "wb").write(nl.join(lines).encode("utf-8"))
    print("wrote", len(rels), "and released", done)
print(len(rels), "relations;", len(dropped), "dropped;", len(unread), "unread;", len(covered), "of", len(cards), "cards reached")
