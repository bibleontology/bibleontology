"""Which "Son" is Jesus: every NT υἱός resolved like a pronoun, with its reason.

2026-09-28: it is very important that the Son be tagged as the proper Son of
God and not a generic son node; and is Son a relationship with God to be
resolved, kind of like a pronoun? Yes: son is
a RELATIONAL noun with two ends to resolve, the referent (who) and the
relatum (son of whom). The mentions layer linked no υἱός at all.

The foundation is the grammar (the structure's qualifier edges and the
resolved pronouns); where it cannot reach, the old graph's sourced relations
are laid over it, credited (established and sourced
relationships/nodes in the old graph are treated as overlays in the new graph
if the graph is unable to surface them). The Trinity is NOT modelled either way
(a standing decision): "Son" + "of God" links the occurrence to Jesus and names the
title; nothing merges Jesus with God or the Father.

Rules, each measured 2026-09-28 by reading every hit:
    of God / Most High / Father   qualifier edge to θεός, ὕψιστος, πατήρ
    of Man                        qualifier edge to ἄνθρωπος
    only begotten                 qualifier edge to μονογενής
    apposition                    qualifier Ἰησοῦς / Χριστός        7 of 7
    possessive                    His / My / Your Son, the possessor God:
                                  its resolved referent, else θεός within the
                                  verse and the two before, unless a person
                                  is NAMED in the verse (Jas 2:21) 14 of 14
    absolute "the Son"            no qualifier, "the Father" / God within a
                                  verse either side, no family list in the
                                  verse                            29 of 32
    Son of David                  Jesus in context, not Joseph     11 of 11
    old graph overlay             the_son_of_god / the_son_of_man records
                                  and relations citing the verse

    python tools/meaning/son_titles.py     -> out/son-titles.jsonl
"""
from __future__ import annotations

import collections
import gzip
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "patterns"))
from mine import FAM, NTFAM  # noqa: E402

GOD = {"θεος", "υψιστος", "ευλογητος", "πατηρ"}
KIN = {"μητηρ", "θυγατηρ", "αδελφος", "αδελφη", "νυμφη", "πενθερα", "τεκνον"}
POSS = {"αυτος", "εγω", "εμος", "συ", "σος"}
TITLES = {"the_son_of_god", "the_son_of_man"}
OSIS = {"Matt": "Mat", "Mark": "Mrk", "Luke": "Luk", "John": "Jhn", "Acts": "Act",
        "Rom": "Rom", "1Cor": "1Co", "2Cor": "2Co", "Gal": "Gal", "Eph": "Eph",
        "Phil": "Php", "Col": "Col", "1Thess": "1Th", "2Thess": "2Th", "1Tim": "1Ti",
        "2Tim": "2Ti", "Titus": "Tit", "Phlm": "Phm", "Heb": "Heb", "Jas": "Jas",
        "1Pet": "1Pe", "2Pet": "2Pe", "1John": "1Jn", "2John": "2Jn", "3John": "3Jn",
        "Jude": "Jud", "Rev": "Rev"}


def plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if not unicodedata.combining(c)).lower()


def rows(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith('{"_'):
                yield json.loads(line)


def overlay_verses():
    """Verses where the old graph's sourced records and relations say the
    Son of God or the Son of Man is meant."""
    def mref(r):
        m = re.match(r"(\w+) (\d+):(\d+)", r or "")
        return f"{OSIS.get(m.group(1), m.group(1))}.{m.group(2)}.{m.group(3)}" if m else None
    cover = collections.defaultdict(set)
    for line in (ROOT / "ontology" / "entities" / "entities.jsonl").open(encoding="utf-8"):
        d = json.loads(line)
        if d["id"] in TITLES:
            for r in d.get("refs") or []:
                if mref(r):
                    cover[mref(r)].add(d["id"])
    for f in (ROOT / "ontology" / "relations").glob("*.jsonl"):
        for line in f.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("dst") in TITLES and r.get("src") == "jesus":
                for x in r.get("refs") or []:
                    if mref(x):
                        cover[mref(x)].add(r["dst"])
    return cover


def main():
    nodes, sons = {}, []
    for n in rows(OUT / "structure-nodes.jsonl.gz"):
        if FAM.get(n["id"].split(".")[0], 0) < NTFAM:
            continue
        nodes[n["id"]] = n
        if n.get("word") and plain(n.get("lemma")) == "υιος":
            sons.append(n["id"])
    rec = {m["occurrence"]: m["record"] for m in rows(OUT / "mentions.jsonl.gz")}
    qual, refers = collections.defaultdict(list), {}
    for e in rows(OUT / "structure-edges.jsonl.gz"):
        if e["type"] == "qualifier" and e["src"] in nodes:
            qual[e["src"]].append(e["dst"])
        elif e["type"] == "refers_to":
            refers[e["src"]] = e["dst"]
    by_verse = collections.defaultdict(list)
    for i, n in nodes.items():
        if n.get("word"):
            by_verse[i.split("#")[0]].append(i)
    words = lambda vs: [w for v in vs for w in by_verse.get(v, ())]  # noqa: E731
    lem = lambda w: plain(nodes[w].get("lemma"))                      # noqa: E731
    cover = overlay_verses()
    out, tally = [], collections.Counter()
    for sid in sons:
        n = nodes[sid]
        if n.get("number") == "plural":
            continue
        v = sid.split("#")[0]
        b, c, vv = v.split(".")
        near = [f"{b}.{c}.{int(vv) - k}" for k in (0, 1, 2)]
        qs = [nodes[q] for q in qual.get(sid, []) if q in nodes]
        ql = {plain(q.get("lemma")) for q in qs}
        via, title, relatum = None, None, None
        if ql & GOD:
            via, title, relatum = "of God", "the_son_of_god", "god"
        elif "ανθρωπος" in ql:
            via, title = "of Man", "the_son_of_man"
        elif "μονογενης" in ql:
            via, title, relatum = "only begotten", "the_son_of_god", "god"
        elif ql & {"ιησους", "χριστος"}:
            via = "apposition: Jesus / Christ"
        else:
            for q in qs:
                if plain(q.get("lemma")) in POSS:
                    r = rec.get(refers.get(q["id"])) if refers.get(q["id"]) else None
                    named = {rec.get(w) for w in words([v])
                             if (nodes[w].get("lemma") or "x")[:1].isupper()
                             and lem(w) not in ("θεος", "ιησους", "χριστος")} - {None, "god", "jesus"}
                    if r is None and not named and any(lem(w) == "θεος" for w in words(near)):
                        r = "god"
                    if r in ("god", "father", "the_father", "yahweh"):
                        via, title, relatum = f"possessive '{q.get('text')}' -> God", "the_son_of_god", "god"
                    break
            # "His Son" with no possessive in the Greek is the absolute title:
            # John 3:17 is ἀπέστειλεν ὁ θεὸς τὸν υἱόν — the English adds "His"
            if not via and not qs and (n.get("text") or "").lower().startswith(("son", "the son", "his son")):
                here = {lem(w) for w in words([v])}
                if not here & KIN and any(lem(w) in ("πατηρ", "θεος")
                                          for w in words(near + [f"{b}.{c}.{int(vv) + 1}"])):
                    via, title, relatum = "absolute 'the Son' beside the Father / God", "the_son_of_god", "the_father"
            if not via and "δαυιδ" in ql and any(rec.get(w) == "jesus" for w in words(near)) \
                    and not any(lem(w) == "ιωσηφ" for w in words([v])):
                via, relatum = "Son of David, Jesus in context", "david"
        source = "grammar"
        if not via and v in cover:
            via, title, source = "old graph overlay", sorted(cover[v])[0], "old graph (overlay)"
        if not via:
            continue
        tally[via.split(" '")[0]] += 1
        out.append({"occurrence": sid, "record": "jesus", "title": title,
                    "relatum": relatum, "via": via, "source": source,
                    "overlay_agrees": source == "grammar" and v in cover})
    with (OUT / "son-titles.jsonl").open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"_note": "NT υἱός resolved to Jesus, each with its reason "
                             "(tools/meaning/son_titles.py). The title is named, never merged "
                             "with God or the Father (ROADMAP: the Trinity is not modelled "
                             "either way). Measured precision on the read rules 61 of 64; "
                             "known misses: Luke 11:11, 15:21, Rev 21:7 (absolute rule)."}) + "\n")
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(out)} of {sum(1 for s in sons if nodes[s].get('number') != 'plural')} "
          f"singular υἱός linked to Jesus: " + ", ".join(f"{k} {n}" for k, n in tally.most_common()))


if __name__ == "__main__":
    main()
