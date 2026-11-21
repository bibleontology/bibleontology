"""For each card with no relations: its verses (Berean text), the cards cited at the same verses, and the hub that
lists it, as evidence for a judged question: which relations does the verse state?"""
import sys, json, collections
sys.path.insert(0, "app2")
import server as S
d = S.load()
rows = [r for r in json.load(open(sys.argv[1], encoding="utf-8")) if r["type"] != "passage"]
at = S._cards_at()
MIX = S._mention_ix()
hubs = collections.defaultdict(list)
try:
    for h in S._aggregate_hubs().values() if hasattr(S, "_aggregate_hubs") else []:
        pass
except Exception:
    pass
out, stat = [], collections.Counter()
for r in rows:
    e = d["ents"][r["id"]]
    vs, cands = [], {}
    for ref in (e.get("refs") or [])[:4]:
        r1 = ref.split("-")[0].split("–")[0].strip()
        k, text = S._verse_text(d, S._macula_ref(d, r1))
        if not text: continue
        # the three verses before it, so "the king" (1 Kgs 1:15) and "him" (Acts 17:18) can be read as the text names them
        ctx = []
        m3 = S._macula_ref(d, r1).split(".")
        if len(m3) == 3:
            for back in (3, 2, 1):
                vn = int(m3[2]) - back
                if vn < 1: continue
                kk, tt = S._verse_text(d, f"{m3[0]}.{m3[1]}.{vn}")
                if tt:
                    ctx.append({"ref": f"{r1.rsplit(':', 1)[0]}:{vn}", "text": tt})
                    for n in S.verse_names(d, S._site_key(d, f"{m3[0]}.{m3[1]}.{vn}"), tt, {r["id"]}):
                        if n.get("id"):
                            oe = d["ents"].get(n["id"]) or {}
                            cands.setdefault(n["id"], {"id": n["id"], "name": oe.get("name"), "type": oe.get("type"),
                                                       "relations": len(d["rels"].get(n["id"], [])), "at": "nearby"})
        vs.append({"ref": r1, "text": text, "before": ctx})
        site = S._site_key(d, S._macula_ref(d, r1))
        bcv = tuple(site.split(".")); bcv = (bcv[0], int(bcv[1]), int(bcv[2])) if len(bcv) == 3 else None
        site_k = f"{bcv[0]}.{bcv[1]}.{bcv[2]}" if bcv else None
        named = [n.get("id") for n in (S.verse_names(d, site_k, text, {r["id"]}) if site_k else []) if n.get("id")]
        mac = S._macula_ref(d, r1).split(".")
        ment = []
        if len(mac) == 3:
            try:
                ment = [m for m, _n in MIX[mac[0]][(int(mac[1]), int(mac[2]))].most_common(8)]
            except (KeyError, ValueError):
                ment = []
        for oid in list(at.get(bcv, []) if bcv else []) + named + ment:
            oe = d["ents"].get(oid) or {}
            if oid == r["id"] or oe.get("alias_of") or oe.get("type") in ("passage",) or oid in S.OB_DIVINE and False:
                continue
            cands.setdefault(oid, {"id": oid, "name": oe.get("name"), "type": oe.get("type"),
                                   "relations": len(d["rels"].get(oid, [])), "at": r1})
    cl = sorted(cands.values(), key=lambda c: -c["relations"])[:12]
    stat["with candidates" if cl else "no candidates"] += 1
    out.append({"id": r["id"], "name": r["name"], "type": r["type"], "desc": e.get("desc"), "verses": vs,
                "candidates": cl})
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(dict(stat), "verses missing:", sum(1 for o in out if not o["verses"]))
c = [o for o in out if o["id"] in ("abishag", "epicureans", "abarim", "table_of_the_presence")]
for o in c: print(o["id"], [x["name"] for x in o["candidates"]][:8])
