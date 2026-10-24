"""What the passages of one stamp have in common, mined from their structure.

2026-09-29, on the Explore Events type pages: something more is needed to
reveal the characteristics of each list of events, mined out for each list. The
lists may not share a common structure, but they all have node structures now
to mine.

A stamp (a parable, a healing, an oracle against the nations ...) sits on a
set of BSB sections. For each stamp, five facets are counted by PRESENCE in
each of its sections — not raw frequency, so one long section cannot carry a
feature — and set against how many of ALL sections carry the same thing:

    actions   the verbs of the section's clauses
    doers     who acts: the records the clauses' subjects resolve to
    things    what is acted on: the objects' words
    places    the places mentioned
    concepts  the anchored concepts of the section's words

A feature is kept when at least a fifth of the stamp's sections (and two)
carry it and it is at least 1.5x as common there as across all sections;
ranked by share x log(lift), with example verses. It says what the text of
these passages does together, not what they mean.

    python tools/event_profiles.py     -> out/event-profiles.json
"""
from __future__ import annotations

import collections
import gzip
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
OSIS = ("Gen Exod Lev Num Deut Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr 2Chr Ezra Neh Esth Job Ps Prov "
        "Eccl Song Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal Matt Mark "
        "Luke John Acts Rom 1Cor 2Cor Gal Eph Phil Col 1Thess 2Thess 1Tim 2Tim Titus Phlm Heb Jas 1Pet "
        "2Pet 1John 2John 3John Jude Rev").split()
USFM = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA "
        "JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO "
        "GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV").split()
MAC = ("Gen Exo Lev Num Deu Jos Jdg Rut 1Sa 2Sa 1Ki 2Ki 1Ch 2Ch Ezr Neh Est Job Psa Pro Ecc Sng Isa "
       "Jer Lam Ezk Dan Hos Jol Amo Oba Jon Mic Nam Hab Zep Hag Zec Mal Mat Mrk Luk Jhn Act Rom 1Co 2Co "
       "Gal Eph Php Col 1Th 2Th 1Ti 2Ti Tit Phm Heb Jas 1Pe 2Pe 1Jn 2Jn 3Jn Jud Rev").split()
CODE, TOMAC = dict(zip(OSIS, USFM)), dict(zip(OSIS, MAC))
MIN_SHARE, MIN_LIFT, TOP, EXAMPLES = 0.15, 1.5, 10, 3
# verbs and words that are everywhere and say nothing about a kind of passage
LIGHT = {"say", "said", "be", "is", "was", "were", "have", "has", "had", "do", "did", "go", "went",
         "come", "came", "make", "made", "give", "gave", "take", "took", "see", "saw", "speak", "spoke",
         "answer", "answered", "let", "will"}


def rows(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith('{"_'):
                yield json.loads(line)


def sections():
    """BSB section start -> its verses, in MACULA numbering."""
    secs = {}
    for osis in OSIS:
        f = next((ROOT / "data" / "raw" / "usfm" / "engbsb").glob(f"*{CODE[osis]}engbsb.usfm"))
        ch, cur, pend = 0, None, False
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\\c (\d+)", line)
            if m:
                ch = int(m.group(1))
            if line.startswith("\\s1"):
                pend = True
            for v in re.findall(r"\\v (\d+)", line):
                if pend or cur is None:
                    cur, pend = f"{osis}.{ch}.{v}", False
                    secs[cur] = []
                secs[cur].append(f"{TOMAC[osis]}.{ch}.{v}")
    return secs


def main():
    secs = sections()
    sec_of = {v: s for s, vs in secs.items() for v in vs}
    ents = {}
    for line in (ROOT / "ontology" / "entities" / "entities.jsonl").open(encoding="utf-8"):
        e = json.loads(line)
        ents[e["id"]] = (e["name"], e["type"])
    mention = {m["occurrence"]: m["record"] for m in rows(OUT / "mentions.jsonl.gz")}
    anch, cname = collections.defaultdict(set), {}
    for r in rows(OUT / "concept-anchors.jsonl.gz"):
        if r["kind"] != "word":
            continue
        cname[r["id"]] = r["name"]
        for p in r["parts"]:
            for k, _n, s in p["anchors"]:
                if s >= 0.15:
                    anch[k].add(r["id"])
    words, phrase_w = {}, {}
    feats = collections.defaultdict(lambda: collections.defaultdict(set))   # section -> facet -> {key}
    where = collections.defaultdict(list)          # (section, facet, key) -> verses
    label = collections.defaultdict(collections.Counter)
    clause_verb = {}
    for n in rows(OUT / "structure-nodes.jsonl.gz"):
        v = n["id"].split("#")[0]
        s = sec_of.get(v)
        if not s:
            continue
        if n.get("word"):
            words[n["id"]] = n
            d = "".join(ch for ch in (n.get("strong") or "") if ch.isdigit())
            if d:
                for c in anch.get(("g" if n.get("lang") == "greek" else "h") + str(int(d)), ()):
                    feats[s]["concepts"].add(c)
                    where[(s, "concepts", c)].append(v)
            r = mention.get(n["id"])
            if r and ents.get(r, ("", ""))[1] == "place":
                feats[s]["places"].add(r)
                where[(s, "places", r)].append(v)
        elif n.get("clause") and n.get("verb_lemma"):
            clause_verb[n["id"]] = (n["verb_lemma"], v)
        elif n.get("w"):
            # a phrase: an object often points here, not at a word (the first
            # pass found no "things" at all for healing or the crucifixion)
            phrase_w[n["id"]] = [f"{v}#w{i}" for i in n["w"]]
    # the verb's English: the gloss of the clause's verb word, most common
    for e in rows(OUT / "structure-edges.jsonl.gz"):
        if not e.get("clause_role") or "#ct" not in e["src"]:
            continue
        cid = e["src"].replace("#ct", "#cl")
        if cid not in clause_verb:
            continue
        lem, v = clause_verb[cid]
        s = sec_of.get(v)
        w = words.get(e["dst"], {})
        if e["type"] == "v":
            g = (w.get("text") or "").lower()
            label[("actions", lem)][g] += 1
            if g not in LIGHT:
                feats[s]["actions"].add(lem)
                where[(s, "actions", lem)].append(v)
        elif e["type"] == "s":
            r = mention.get(e["dst"])
            if r and r in ents:
                feats[s]["doers"].add(r)
                where[(s, "doers", r)].append(v)
        elif e["type"] in ("o", "o2"):
            # the object's head word: the word itself, or the first noun of
            # the phrase it points to
            cands = [w] if w.get("lemma") else [words.get(x, {}) for x in phrase_w.get(e["dst"], [])]
            head = next((x for x in cands if x.get("lemma") and x.get("class") == "noun"), None) \
                or next((x for x in cands if x.get("lemma")
                         and x.get("class") not in ("pron", "art", "det", "prep", "cj")), None)
            if head:
                g = (head.get("text") or "").lower()
                if g and g not in LIGHT:
                    feats[s]["things"].add(head["lemma"])
                    label[("things", head["lemma"])][g] += 1
                    where[(s, "things", head["lemma"])].append(v)
    nsec = len(secs)
    # THE BASELINE IS THE SAME BOOKS. Against the whole canon, healing's
    # "actions" came out as "saying, having seen, having gone out" — gospel
    # storytelling, not healing, because most healings are in the gospels.
    # A feature's expected share in a stamp is the mean, over the stamp's
    # sections, of how common it is in that section's own book.
    book_n = collections.Counter(s.split(".")[0] for s in secs)
    book_has = collections.Counter((s.split(".")[0], f, k)
                                   for s in feats for f, ks in feats[s].items() for k in ks)

    def name(facet, k):
        if facet in ("doers", "places"):
            return ents.get(k, (k, ""))[0]
        if facet == "concepts":
            return cname.get(k, k)
        return (label[(facet, k)].most_common(1) or [(k, 0)])[0][0] or k
    stamp_secs = collections.defaultdict(set)
    for line in (OUT / "stamps-leveled.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r["ref"] in secs:
                stamp_secs[r["id"]].add(r["ref"])
    out = {}
    for sid, ss in stamp_secs.items():
        n = len(ss)
        if n < 3:
            continue
        prof = {}
        for facet in ("actions", "doers", "things", "places", "concepts"):
            got = collections.Counter(k for s in ss for k in feats[s].get(facet, ()))
            lines, seen_names = [], set()
            for k, c in got.items():
                if c < max(2, MIN_SHARE * n):
                    continue
                expected = sum(book_has[(s.split(".")[0], facet, k)] / book_n[s.split(".")[0]]
                               for s in ss) / n
                if expected <= 0:
                    continue
                lift = (c / n) / expected
                if lift < MIN_LIFT:
                    continue
                ex = []
                for s in sorted(ss):
                    for v in where.get((s, facet, k), [])[:1]:
                        ex.append(v)
                    if len(ex) >= EXAMPLES:
                        break
                lines.append({"key": k, "what": name(facet, k), "sections": c,
                              "share": round(c / n, 2), "lift": round(lift, 1), "examples": ex,
                              # the sections carrying it: the page groups and
                              # filters the instances by these (there may
                              # be better ways to organize than by book)
                              "in": sorted(s for s in ss if k in feats[s].get(facet, ()))})
            lines.sort(key=lambda x: -(x["share"] * math.log(x["lift"])))
            kept, seen_sets = [], set()
            for x in lines:
                # one line per NAME ("the ground" x3) and per SET of sections
                # ("eyes", "eye", "the eyes of the Lord" are one finding)
                nm = re.sub(r"^the ", "", x["what"].lower())
                key = tuple(x["in"])
                if nm in seen_names or key in seen_sets:
                    continue
                seen_names.add(nm)
                seen_sets.add(key)
                kept.append(x)
            prof[facet] = kept[:TOP]
        # HOW THEY DIVIDE AMONG THEMSELVES — no baseline: the commonest values
        # of the facets that organise a list (who acts, where, on what), each
        # with its sections. There may be better ways to organize than
        # by book, based on the mining. Jesus is not DISTINCTIVE of healings
        # against the gospels, and he is still how most of them group.
        groups = {}
        for facet in ("doers", "places", "things"):
            got = collections.Counter(k for s in ss for k in feats[s].get(facet, ()))
            gl = [{"key": k, "what": name(facet, k), "sections": c,
                   "in": sorted(s for s in ss if k in feats[s].get(facet, ()))}
                  for k, c in got.most_common(12) if c >= 3]
            if gl:
                groups[facet] = gl
        out[sid] = {"sections": n, "profile": prof, "groups": groups}
    (OUT / "event-profiles.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"{len(out)} stamps profiled over {nsec:,} sections")
    for sid in ("healing", "parable_of_the_kingdom", "sacrifice_ev", "exile_ev", "crucifixion"):
        p = out.get(sid)
        if p:
            print(f"\n{sid} ({p['sections']} sections)")
            for f, ls in p["profile"].items():
                print(f"  {f:9s} " + ", ".join(f"{x['what']} {x['share']:.0%}/{x['lift']}x" for x in ls[:6]))
            for f, gl in p.get("groups", {}).items():
                print(f"  by {f:6s} " + ", ".join(f"{g['what']} {g['sections']}" for g in gl[:8]))


if __name__ == "__main__":
    main()
