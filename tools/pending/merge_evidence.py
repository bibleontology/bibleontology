"""Option C (Doug, 2026-11-18): the same-word sets whose shown names are the same or a plural apart. For each card
merged into another, both records' evidence: name, other names, description, verses (Berean), words, relations."""
import sys, json, collections
sys.path.insert(0, "app2")
import server as S
d = S.load()
cards = json.load(open("ontology/concept-lead-words.json", encoding="utf-8"))["cards"]
def sing(n):
    n = n.lower().strip()
    for a, b in (("ies", "y"), ("men", "man"), ("es", ""), ("s", "")):
        if n.endswith(a) and len(n) > len(a) + 2: return n[:-len(a)] + b
    return n
lead = collections.defaultdict(list)
for k, ws in cards.items():
    if k in d["ents"] and not d["ents"][k].get("alias_of"): lead[ws[0]].append(k)
def rec(k):
    e = d["ents"][k]
    vs = []
    for r in (e.get("refs") or [])[:4]:
        r1 = r.split("-")[0].split("–")[0].strip()
        ref, t = S._verse_text(d, S._macula_ref(d, r1))
        if t: vs.append({"ref": r1, "text": t})
    rl = []
    for r in d["rels"].get(k, [])[:8]:
        o = d["ents"].get(r["other"]) or {}
        rl.append({"type": r["type"], "dir": r["dir"], "other": o.get("name") or r["other"], "refs": (r.get("refs") or [])[:2]})
    return {"id": k, "name": e.get("name"), "aka": e.get("aka") or [], "desc": (e.get("desc") or "")[:300],
            "verses": vs, "words": cards.get(k, [])[:4], "relations": rl, "n_relations": len(d["rels"].get(k, []))}
pairs = []
for w, ks in lead.items():
    if w == "h639":            # anger and wrath: kept apart (Doug, 2026-10-04)
        continue
    by = collections.defaultdict(list)
    for k in ks: by[sing(d["ents"][k]["name"])].append(k)
    for s_, g in by.items():
        if len(g) < 2: continue
        g.sort(key=lambda k: (-len(d["rels"].get(k, [])), len(d["ents"][k]["name"])))
        keep = g[0]
        for other in g[1:]:
            pairs.append({"word": w, "keep": rec(keep), "merge": rec(other)})
json.dump(pairs, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(pairs), "pairs")
for p in pairs: print(" ", p["word"], p["merge"]["id"], "->", p["keep"]["id"], p["merge"]["n_relations"], p["keep"]["n_relations"])
