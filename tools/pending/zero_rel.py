"""Every card with no relations: kind, whether it is listed (has a page offered), and clues to why."""
import sys, json, collections, re
sys.path.insert(0, "app2")
import server as S
d = S.load()
srcfile = {}
import glob
for f in glob.glob("ontology/entities/*.jsonl"):
    for l in open(f, encoding="utf-8"):
        try: r = json.loads(l)
        except ValueError: continue
        if r.get("id"): srcfile[r["id"]] = f.split("\\")[-1].split("/")[-1]
rows = []
for k, e in d["ents"].items():
    if e.get("alias_of") or d["rels"].get(k): continue
    t = e.get("type")
    rows.append({"id": k, "name": e.get("name"), "type": t, "file": srcfile.get(k, "?"),
                 "refs": (e.get("refs") or [])[:3], "nrefs": len(e.get("refs") or []),
                 "desc": (e.get("desc") or "")[:100], "attrs": sorted((e.get("attrs") or {}).keys())[:6]})
c = collections.Counter(r["type"] for r in rows)
print("cards with no relations:", len(rows), dict(c.most_common()))
print("by source file:", collections.Counter(r["file"] for r in rows).most_common(12))
print("with own cited verses:", sum(1 for r in rows if r["nrefs"]), "without:", sum(1 for r in rows if not r["nrefs"]))
json.dump(rows, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
