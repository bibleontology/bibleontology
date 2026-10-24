"""What the text says of a person or thing: its profile, counted (plan 4.7).

2026-09-28, after the probe showed "suffer, die, be raised, be handed
over, be crucified" among what most distinguishes Jesus as doer: this is
what the graph should surface in theory. For every record with enough
occurrences, three lists, each by LIFT over its testament and each with
example verses, so a reader can check every line:

    does        the verbs of clauses it is the doer of (active voice)
    undergoes   the verbs of clauses it is the one acted on in: its passive
                clauses ("was crucified"), and clauses with it as object
    companions  the anchored concepts found in its verses

A person is ONE node under several names. The mentions layer ties names and
resolved pronouns to records; titles need the text's marks, because the
title's word is ordinary (the sons of Zebedee were not God's
sons). TITLES says, per record, which words count and on what marks.

    python tools/meaning/profiles.py      -> out/profiles.jsonl.gz
"""
import collections
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "builder"))
sys.path.insert(0, str(ROOT / "tools" / "patterns"))
from source import norm  # noqa: E402
from mine import FAM, NTFAM  # noqa: E402

MIN_OCC = 20           # a record needs this many occurrences for a profile
MIN_N = 3              # a line needs this many clauses or verses
TOP = 12               # lines kept per list
EXAMPLES = 3
# A TITLE'S WORD IS ORDINARY; its instances need the text's marks. Per
# record: lemma -> the marks one of which must be in the same verse (Strong's
# numbers, Greek), or None when the word alone is enough.
TITLES = {
    "jesus": {
        "χριστος": None,                       # Christ
        "αρνιον": {"g2316", "g2362"},          # the Lamb: with God or the throne
        "υιος": {"g2316", "g3962", "g3439",   # the Son: God, the Father,
                 "g444"},                      # only begotten, Son of Man
    },
}


def rows(p):
    for line in gzip.open(p, "rt", encoding="utf-8"):
        if line.startswith('{"_'):
            continue
        yield json.loads(line)


def main():
    nodes = {}
    for n in rows(OUT / "structure-nodes.jsonl.gz"):
        if n.get("clause") or n.get("word") or n.get("implicit"):
            nodes[n["id"]] = n
    role_of = collections.defaultdict(list)       # filler -> (clause, role)
    for e in rows(OUT / "structure-edges.jsonl.gz"):
        if e.get("clause_role") and "#ct" in e["src"] and \
                e["type"] in ("s", "o", "o2", "io", "pp"):
            role_of[e["dst"]].append((e["src"].replace("#ct", "#cl"),
                                      e["type"]))
    # every occurrence of every record: the mentions layer, plus titles
    occ = collections.defaultdict(set)
    for m in rows(OUT / "mentions.jsonl.gz"):
        occ[m["record"]].add(m["occurrence"])
    verse_strongs = collections.defaultdict(set)
    words_by_lemma = collections.defaultdict(list)
    for nid, n in nodes.items():
        if n.get("word") and n.get("lemma"):
            d = "".join(ch for ch in n.get("strong") or "" if ch.isdigit())
            if d:
                verse_strongs[nid.split("#")[0]].add(
                    ("g" if n["lang"] == "greek" else "h") + str(int(d)))
            words_by_lemma[norm(n["lemma"])].append(nid)
    titled = collections.Counter()
    for rec, rules in TITLES.items():
        for lem, marks in rules.items():
            for nid in words_by_lemma.get(lem, ()):
                v = nid.split("#")[0]
                if FAM.get(v.split(".")[0], 0) < NTFAM:
                    continue
                if marks is None or verse_strongs[v] & marks:
                    occ[rec].add(nid)
                    titled[rec] += 1
    # concepts per verse, by anchor
    anch = collections.defaultdict(set)
    cname = {}
    for r in rows(OUT / "concept-anchors.jsonl.gz"):
        if r["kind"] != "word":
            continue
        cname[r["id"]] = r["name"]
        for p in r["parts"]:
            for k, _n, s in p["anchors"]:
                if s >= 0.15:
                    anch[k].add(r["id"])
    verse_c = {v: {c for k in ks for c in anch.get(k, ())}
               for v, ks in verse_strongs.items()}

    def testament(v):
        return "NT" if FAM.get(v.split(".")[0], 0) >= NTFAM else "OT"
    # baselines per testament: verbs by voice-role, concepts by verse
    base_do, base_under = collections.Counter(), collections.Counter()
    base_c = collections.Counter()
    n_cl = collections.Counter()
    n_v = collections.Counter()
    for cid, c in nodes.items():
        if c.get("clause") and c.get("verb_lemma"):
            t = testament(cid)
            n_cl[t] += 1
            base_do[(t, norm(c["verb_lemma"]))] += 1
    for v, cs in verse_c.items():
        t = testament(v)
        n_v[t] += 1
        for c in cs:
            base_c[(t, c)] += 1
    passive = lambda c: (c.get("verb_voice") or "").startswith("pass")  # noqa
    gloss = {}
    for n in nodes.values():
        if n.get("word") and n.get("verb") and n.get("lemma"):
            gloss.setdefault(norm(n["lemma"]),
                             (n.get("text") or "").split(" ")[-1])
    out = []
    for rec, ids in occ.items():
        if len(ids) < MIN_OCC:
            continue
        do, under = collections.Counter(), collections.Counter()
        ex = collections.defaultdict(list)
        verses = set()
        tcount = collections.Counter()
        for nid in ids:
            v = nid.split("#")[0]
            verses.add(v)
            tcount[testament(v)] += 1
            for cid, role in role_of.get(nid, ()):
                c = nodes.get(cid) or {}
                if not c.get("verb_lemma"):
                    continue
                lem = norm(c["verb_lemma"])
                key = (testament(cid), lem)
                bucket = do if role == "s" and not passive(c) else under
                bucket[key] += 1
                if len(ex[(bucket is do, lem)]) < EXAMPLES:
                    ex[(bucket is do, lem)].append(v)
        comp = collections.Counter()
        cex = collections.defaultdict(list)
        for v in verses:
            for c in verse_c.get(v, ()):
                comp[(testament(v), c)] += 1
                if len(cex[c]) < EXAMPLES:
                    cex[c].append(v)

        def lifted(cnt, base, denom, total, name, exk):
            tot_t = collections.Counter()
            for (t, _x), k in cnt.items():
                tot_t[t] += k
            res = collections.defaultdict(lambda: [0, 0.0])
            for (t, x), k in cnt.items():
                if not base[(t, x)] or not tot_t[t]:
                    continue
                lf = (k / tot_t[t]) / (base[(t, x)] / denom[t])
                res[x][0] += k
                res[x][1] = max(res[x][1], lf)
            lines = [{"what": name(x), "n": k, "lift": round(lf, 1),
                      "examples": exk(x)}
                     for x, (k, lf) in res.items() if k >= MIN_N]
            return sorted(lines, key=lambda r: -r["lift"])[:TOP]
        out.append({
            "record": rec, "occurrences": len(ids), "titled": titled[rec],
            "testaments": dict(tcount),
            "does": lifted(do, base_do, n_cl, None, lambda x: gloss.get(x, x),
                           lambda x: ex[(True, x)]),
            "undergoes": lifted(under, base_do, n_cl, None,
                                lambda x: gloss.get(x, x),
                                lambda x: ex[(False, x)]),
            "companions": lifted(comp, base_c, n_v, None,
                                 lambda x: cname.get(x, x), lambda x: cex[x])})
    with gzip.open(OUT / "profiles.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(out):,} profiles; titles resolved: {dict(titled)}")


if __name__ == "__main__":
    main()
