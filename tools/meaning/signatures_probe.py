"""An idea, tested: concepts with similar role signatures (subject, object,
verb, prepositional phrase) are related. Deterministic, corpus-wide, on the
concept anchors and the structure's clause roles. PPMI + cosine."""
import collections, gzip, json, math, sys
ROOT = "<local> Ontology/"
ROLES = {"s", "o", "o2", "io", "pp", "p"}
anch, cname = collections.defaultdict(set), {}
for l in gzip.open(ROOT + "out/concept-anchors.jsonl.gz", "rt", encoding="utf-8"):
    if l.startswith('{"_'):
        continue
    r = json.loads(l)
    if r["kind"] != "word":
        continue
    cname[r["id"]] = r["name"]
    for p in r["parts"]:
        for k, _n, s in p["anchors"]:
            if s >= 0.15:
                anch[k].add(r["id"])
key = {}                        # word id -> strong key
for l in gzip.open(ROOT + "out/structure-nodes.jsonl.gz", "rt", encoding="utf-8"):
    if l.startswith('{"_') or '"word": true' not in l:
        continue
    n = json.loads(l)
    d = "".join(ch for ch in (n.get("strong") or "") if ch.isdigit())
    if d:
        key[n["id"]] = ("g" if n["lang"] == "greek" else "h") + str(int(d))
clause = collections.defaultdict(lambda: {"v": None, "roles": []})
for l in gzip.open(ROOT + "out/structure-edges.jsonl.gz", "rt", encoding="utf-8"):
    if l.startswith('{"_') or '"clause_role": true' not in l:
        continue
    e = json.loads(l)
    if "#ct" not in e["src"]:
        continue
    k = key.get(e["dst"])
    if not k:
        continue
    if e["type"] == "v":
        clause[e["src"]]["v"] = k
    elif e["type"] in ROLES:
        clause[e["src"]]["roles"].append((e["type"], k))
# a filler is its concept(s) where anchored, else its lexeme key
def fill(k):
    cs = anch.get(k)
    return sorted(cs) if cs else [k]
feat = collections.defaultdict(collections.Counter)      # concept -> feature counts
for c in clause.values():
    for role, k in c["roles"]:
        for con in anch.get(k, ()):
            if c["v"]:
                feat[con][(role, "verb", c["v"])] += 1
            for r2, k2 in c["roles"]:
                if k2 == k:
                    continue
                for f2 in fill(k2):
                    feat[con][(role, "with " + r2, f2)] += 1
# PPMI
fc = collections.Counter()
for cnt in feat.values():
    fc.update(cnt)
tot = sum(fc.values())
ctot = {c: sum(v.values()) for c, v in feat.items()}
vec = {}
for c, cnt in feat.items():
    if ctot[c] < 30:
        continue
    v = {}
    for f, n in cnt.items():
        if fc[f] < 3:
            continue
        pmi = math.log(n * tot / (ctot[c] * fc[f]))
        if pmi > 0:
            v[f] = pmi
    norm = math.sqrt(sum(x * x for x in v.values())) or 1
    vec[c] = {f: x / norm for f, x in v.items()}
by_name = collections.defaultdict(list)
for c in vec:
    by_name[cname[c]].append(c)


def near(c, k=10):
    a = vec[c]
    out = []
    for o, b in vec.items():
        if o == c or cname[o] == cname[c]:
            continue
        s = sum(x * b.get(f, 0) for f, x in a.items())
        out.append((s, o))
    return sorted(out, reverse=True)[:k]


print(f"{len(vec)} concepts with signatures")
for probe in sys.argv[1:] or ["love", "mercy", "grace", "faith", "sin", "salvation", "righteousness", "anger", "life", "peace"]:
    for c in by_name.get(probe, [])[:2]:
        print(f"\n{probe} ({c}, {ctot[c]} role-features):")
        print("   " + ", ".join(f"{cname[o]} {s:.2f}" for s, o in near(c)))
