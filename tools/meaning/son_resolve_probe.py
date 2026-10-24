"""Which NT 'Son' (υἱός, singular) is the Son of God, by the grammar. Measurement first."""
import collections, gzip, json, sys, unicodedata
ROOT = "<local> Ontology/"
sys.path.insert(0, ROOT + "tools/patterns")
from mine import FAM, NTFAM  # noqa


def plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if not unicodedata.combining(c)).lower()


nodes, sons = {}, []
for l in gzip.open(ROOT + "out/structure-nodes.jsonl.gz", "rt", encoding="utf-8"):
    if l.startswith('{"_'):
        continue
    n = json.loads(l)
    if FAM.get(n["id"].split(".")[0], 0) < NTFAM:
        continue
    nodes[n["id"]] = n
    if n.get("word") and plain(n.get("lemma")) == "υιος":
        sons.append(n["id"])
qual = collections.defaultdict(list)
rec = {}
for l in gzip.open(ROOT + "out/mentions.jsonl.gz", "rt", encoding="utf-8"):
    if l.startswith('{"_'):
        continue
    m = json.loads(l)
    rec[m["occurrence"]] = m["record"]
refers = {}
for l in gzip.open(ROOT + "out/structure-edges.jsonl.gz", "rt", encoding="utf-8"):
    if l.startswith('{"_'):
        continue
    e = json.loads(l)
    if e["type"] == "qualifier" and e["src"] in nodes and nodes[e["src"]].get("word"):
        qual[e["src"]].append(e["dst"])
    if e["type"] == "refers_to":
        refers[e["src"]] = e["dst"]
GOD = {"θεος", "υψιστος", "ευλογητος", "πατηρ"}
by_verse = collections.defaultdict(list)
for i, n in nodes.items():
    if n.get("word"):
        by_verse[i.split("#")[0]].append(i)


def words_in(vs):
    return [w for v in vs for w in by_verse.get(v, ())]
why = collections.Counter()
out = []
for sid in sons:
    n = nodes[sid]
    if n.get("number") == "plural":
        why["plural (sons) - not Him"] += 1
        continue
    qs = [nodes.get(q, {}) for q in qual.get(sid, [])]
    ql = {plain(q.get("lemma")) for q in qs}
    verdict = None
    if ql & GOD:
        verdict = "of God"
    elif "ανθρωπος" in ql:
        verdict = "of Man"
    elif "μονογενης" in ql:
        verdict = "only begotten"
    else:
        # a possessive whose referent is God: "His Son", "My Son"
        for q in qs:
            if plain(q.get("lemma")) in ("αυτος", "εγω", "εμος"):
                tgt = refers.get(q["id"])
                r = rec.get(tgt) or rec.get(q["id"])
                if r in ("god", "father", "the_father", "yahweh", "the_lord"):
                    verdict = "His/My Son, God's"
    v = sid.split("#")[0]
    b, c, vv = v.split(".")
    near = [f"{b}.{c}.{int(vv) - k}" for k in (0, 1, 2)]
    if not verdict and ql & {"ιησους", "χριστος"}:
        verdict = "apposition: Jesus / Christ"
    if not verdict:
        for q in qs:
            lem = plain(q.get("lemma"))
            if lem in ("αυτος", "εγω", "εμος", "συ", "σος"):
                # the possessor, resolved like any pronoun: a resolved link if
                # the graph has one, else the nearest God / the Father before
                # it within the verse and the two before
                tgt = refers.get(q["id"])
                r = rec.get(tgt) if tgt else None
                if r is None:
                    for w in sorted((i for i in words_in(near) if i < q["id"] or i.split("#")[0] != v),
                                    reverse=True):
                        if plain(nodes[w].get("lemma")) in ("θεος", "πατηρ"):
                            r = "god"
                            break
                if r in ("god", "father", "the_father", "yahweh", "the_lord"):
                    verdict = f"possessive '{q.get('text')}' -> God"
                break
    if not verdict and not qs and n.get("text", "").lower().startswith(("son", "the son")):
        # the absolute title "the Son", with the Father or God close by
        if any(plain(nodes[w].get("lemma")) in ("πατηρ", "θεος") for w in words_in(near + [f"{b}.{c}.{int(vv) + 1}"])):
            verdict = "absolute 'the Son' beside the Father / God"
    if not verdict and "δαυιδ" in ql and any(rec.get(w) == "jesus" for w in words_in(near)):
        verdict = "Son of David, Jesus in context"
    if verdict:
        why[verdict.split(" '")[0] if verdict.startswith("possessive") else verdict] += 1
        out.append((sid, verdict))
    else:
        why["singular, no mark"] += 1
print(f"{len(sons)} NT υἱός; " + "; ".join(f"{k} {v}" for k, v in why.most_common()))
json.dump(out, open("<local>", "w"))
# unmarked singulars: what they are, a sample by book
um = [s for s in sons if nodes[s].get("number") != "plural" and s not in dict(out)]
bybook = collections.Counter(s.split(".")[0] for s in um)
print("unmarked singular by book:", bybook.most_common(12))
for s in um[::max(1, len(um) // 25)][:25]:
    print("  ", s, nodes[s].get("text"), "| quals:", [nodes.get(q, {}).get("lemma") for q in qual.get(s, [])])
