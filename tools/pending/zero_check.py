"""Mechanical check of the zero-relation answers before any is read by eye.
Usage: zero_check.py  -> writes zero_checked.json (pass / fail with reasons) beside it."""
import json, re, glob, yaml
from pathlib import Path

ROOT = Path(r"<local> Ontology\.claude\worktrees\ubs-lexicon-word-verse-c23765")
S = Path(__file__).parent
cards = {c["id"]: c for c in json.load(open(S / "zero_cand.json", encoding="utf-8"))}
types = yaml.safe_load(open(ROOT / "ontology/schema/relationship_types.yaml", encoding="utf-8"))["types"]
L = lambda v: v if isinstance(v, list) else [v]
kind = {}
for ef in glob.glob(str(ROOT / "ontology/entities/*.jsonl")):
  for ln in open(ef, encoding="utf-8"):
    if ln.strip():
        e = json.loads(ln)
        if "id" in e and e.get("type"): kind.setdefault(e["id"], e.get("type"))
have = set()
for f in glob.glob(str(ROOT / "ontology/relations/*.jsonl")):
    for ln in open(f, encoding="utf-8"):
        if ln.strip():
            r = json.loads(ln); have.add((r.get("src"), r.get("type"), r.get("dst")))
norm = lambda s: re.sub(r"[^a-z0-9 ]", "", re.sub(r"[\u2018\u2019']", "", s.lower())).split()

rows, nones, files = [], [], sorted(glob.glob(str(S / "zero_all/batch-*.answer.txt")))
for f in files:
    t = open(f, encoding="utf-8").read()
    m = re.search(r"^\[.*?^\]", t, re.S | re.M)
    if not m:
        continue
    for it in json.loads(m.group(0)):
        if it.get("none"):
            nones.append(it); continue
        bad, c = [], cards.get(it.get("card"))
        s, d, ty = it.get("src"), it.get("dst"), it.get("type")
        if not c: bad.append("card not in the list")
        if s not in kind: bad.append(f"src {s} unknown")
        if d not in kind: bad.append(f"dst {d} unknown")
        if c and it["card"] not in (s, d): bad.append("card is neither end")
        if ty not in types: bad.append(f"type {ty} unknown")
        elif s in kind and d in kind:
            sp = types[ty]
            if kind[s] not in L(sp.get("src_type")) or kind[d] not in L(sp.get("dst_type")):
                bad.append(f"kinds {kind[s]}->{kind[d]} do not fit {ty}")
        v = None
        if c:
            v = next((x for x in c["verses"] if x["ref"] == it.get("ref")), None)
            if not v: bad.append(f"ref {it.get('ref')} not the card's verse")
        if v:
            q = [w for w in norm(it.get("why", "")) if len(w) > 2]
            vt = set(norm(v["text"]))
            miss = [w for w in q if w not in vt]
            if q and len(miss) > len(q) * 0.25: bad.append(f"quote not in verse ({len(miss)}/{len(q)} words)")
        if (s, ty, d) in have: bad.append("already held")
        rows.append({**it, "verse": v["text"] if v else None, "fail": bad})
ok = [r for r in rows if not r["fail"]]
json.dump({"pass": ok, "fail": [r for r in rows if r["fail"]], "none": nones},
          open(S / "zero_checked.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(len(files), "answer files;", len(rows), "proposals:", len(ok), "pass,", len(rows) - len(ok), "fail;",
      len(nones), "cards with none")
from collections import Counter
print(Counter(b.split(" ")[0] + " " + b.split(" ")[1] for r in rows for b in r["fail"]).most_common())
