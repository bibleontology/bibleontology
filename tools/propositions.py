"""Patterns keyed on what is ASSERTED, not on the grammar that asserts it.

2026-09-19: fix this systemically for the whole graph, then re-run the
pipeline to see what impact it has at higher levels.

The fault it fixes, traced the same day. `declares the [X]` is Old Testament
only, and not because the formula is absent from the Greek:

    Hebrew   נְאֻם־יְהוָה   a CONSTRUCT, noun of noun   ->  `declares the [X]`
    Greek    λέγει Κύριος   a CLAUSE, verb + subject    ->  `[S] saying`

One formula, two syntactic shapes, and `tools/clausepatterns.py` keys a
template on its shape — so the Hebrew earns a dedicated pattern at 91% skew and
the Greek dissolves into a generic verb template where it is 4% of instances.
Nothing is missing from the data; the two cannot meet.

## What a proposition is here

A predicate and its participants, with the predicate named in a way both
languages can reach:

    (say, agent=LORD)     נְאֻם־יְהוָה  and  λέγει Κύριος  are the same row

## Two sources, because one is not enough

**Frames** (`out/frames.jsonl.gz`, 92,567 over 92.5% of the corpus) give the
verbal propositions directly — predicate lemma, agent, patient.

**Constructs are the other half, and frames cannot see them.** נְאֻם has ZERO
frames because it is a noun, so a layer built on frames alone would drop the
very formula that prompted this and call the job done. A construct whose head
is an act — `נְאֻם־יְהוָה`, "utterance-of YHWH" — asserts the same proposition
as the clause, so it is read as predicate=head, agent=dependent.

## The cross-language key

MACULA records the Greek the Septuagint used for each Hebrew word, so a Hebrew
predicate is keyed by that Greek rather than by itself. **1,064 of 1,692 Hebrew
predicates (63%) have an LXX form that is also a Greek predicate**, which is
the ceiling on what this can join.

Stemmed, because the column gives inflected forms: `εἶπεν` and `εἰπαν` and
`λέγει` must reach the same row or nothing joins at all.

## What this is NOT

**It does not replace `tools/clausepatterns.py`.** That layer answers "what
phrase does the text repeat", which is a question about form and rightly keyed
on form. This one answers "what does the text assert", and the two disagree
usefully: a formula is a fixed form, a proposition is a recurring claim.

    python tools/propositions.py            # what it joins, and what it costs
    python tools/propositions.py --write
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import sys
import unicodedata

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
DEST = OUT / "propositions.jsonl.gz"

NT = {"Mat", "Mrk", "Luk", "Jhn", "Act", "Rom", "1Co", "2Co", "Gal", "Eph",
      "Php", "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm", "Heb", "Jas",
      "1Pe", "2Pe", "1Jn", "2Jn", "3Jn", "Jud", "Rev"}

MIN_INSTANCES = 5


def norm(w):
    """Fold case, accents and MACULA's chi/xi corruption. See tools/lxxbridge."""
    d = unicodedata.normalize("NFD", w or "")
    d = "".join(c for c in d if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", d).casefold().replace("ξ", "χ")


def stem(g, n=4):
    """Enough of a Greek form to survive inflection, and no more.

    The Septuagint column stores forms rather than lemmas -- εἶπεν, εἰπαν,
    λέγει -- so an exact key joins almost nothing. Four characters is short
    enough to fold a paradigm and long enough that λεγ- and λαμ- stay apart;
    it is the same crude stem `tools/bridge.py` settled on, for the same
    reason.
    """
    s = norm(g)
    return s[:n] if len(s) >= n else s


def strong_key(lemma, strong):
    lang = "h" if any("א" <= c <= "ת" for c in (lemma or "")) else "g"
    num = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", strong or ""))
    return (lang + num) if num else None


def load_bridge():
    """-> {hebrew key: Greek Strong's number}, from MACULA's own column.

    NOT a stem of the Greek word, which was the first attempt and was wrong in
    a way worth recording. Stemming the Septuagint form to four characters
    caught Greek PREVERBS rather than roots, so `κατα` merged שָׁכַן (dwell),
    שָׂרַף (burn) and καταβαίνω (go down), and `προσ` merged פָּנֶה (face),
    קָרַב (draw near) and יָסַף (add). The layer looked productive -- 37% of
    propositions crossing the testaments -- and the merges meant nothing.

    `greekstrong` gives the Greek LEXEME, which is an identity rather than a
    string: נְאֻם is G3004, which is λέγω, which is exactly the verb of
    `λέγει Κύριος`. 3,643 of 5,760 Hebrew lexemes carry one (63%), and that is
    the honest ceiling on what can be joined.
    """
    meta = json.loads((OUT / "lemma-meta.json").read_text(encoding="utf-8"))
    out = {}
    for k, v in meta.items():
        if not k.startswith("h"):
            continue
        for x in (v.get("greekstrong") or [])[:1]:
            n = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", x.get("v") or ""))
            if n:
                out[k] = "g" + n
                break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--top", type=int, default=14)
    a = ap.parse_args()

    bridge = load_bridge()
    print(f"{len(bridge):,} Hebrew lexemes carry a Septuagint form\n")

    # lemma -> strong key, for naming predicates and participants
    lem2key, lem_gloss = {}, {}
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        for w in d.get("words") or []:
            l_, s_ = w.get("l"), w.get("s")
            if l_ and s_ and l_ not in lem2key:
                lem2key[l_] = strong_key(l_, s_)
            if l_ and w.get("g"):
                lem_gloss.setdefault(l_, collections.Counter())[
                    w["g"].strip().lower()] += 1

    def pkey(lemma):
        """The cross-language name of a predicate."""
        k = lem2key.get(lemma)
        if not k:
            return None
        return bridge.get(k) if k.startswith("h") else k

    props = collections.defaultdict(lambda: {
        "n": 0, "refs": [], "books": set(),
        "heb": 0, "grk": 0,
        "agents": collections.Counter(), "names": collections.Counter()})

    def add(key, ref, lemma, agents):
        p = props[key]
        p["n"] += 1
        p["books"].add(ref.split(".")[0])
        if ref.split(".")[0] in NT:
            p["grk"] += 1
        else:
            p["heb"] += 1
        if len(p["refs"]) < 200:
            p["refs"].append(ref)
        p["names"][lemma] += 1
        for ag in agents:
            p["agents"][ag] += 1

    # ---- source 1: frames, the verbal propositions ------------------------
    nf = 0
    for line in gzip.open(OUT / "frames.jsonl.gz", "rt", encoding="utf-8"):
        if line.startswith('{"_'):
            continue
        d = json.loads(line)
        lem = d.get("lemma")
        k = pkey(lem)
        if not k or not d.get("ref"):
            continue
        nf += 1
        ags = []
        for ag in (d.get("agent") or [])[:2]:
            gk = lem2key.get(ag)
            ags.append(pkey(ag) or (gk or ag))
        add(k, d["ref"], lem, ags)
    print(f"{nf:,} propositions from frames")

    # ---- source 2: constructs whose head is an act ------------------------
    #
    # Frames cannot see these: נְאֻם has none, being a noun. A construct like
    # נְאֻם־יְהוָה asserts what a clause asserts, so its head is read as the
    # predicate and its dependent as the agent. Only heads whose lexeme ALSO
    # appears as a framed predicate somewhere count -- that is the test for
    # "this noun names an act", and it is read off the corpus rather than
    # declared.
    framed = {k for k in props}
    nc = 0
    for line in gzip.open(OUT / "patterns.jsonl.gz", "rt", encoding="utf-8"):
        if line.startswith('{"_'):
            continue
        r = json.loads(line)
        t = r.get("template") or ""
        if "[S]" in t or "[X]" not in t or not r.get("lemma"):
            continue
        k = pkey(r["lemma"])
        if not k or k not in framed:
            continue
        for slot, fills in (r.get("slot_refs") or {}).items():
            for filler, refs in fills.items():
                for ref in refs:
                    nc += 1
                    add(k, ref, r["lemma"], [filler])
    print(f"{nc:,} propositions from constructs whose head names an act\n")

    keep = {k: p for k, p in props.items() if p["n"] >= MIN_INSTANCES}
    both = {k: p for k, p in keep.items() if p["heb"] and p["grk"]}
    print(f"{len(keep):,} propositions with {MIN_INSTANCES}+ instances")
    print(f"{len(both):,} ({len(both)/max(len(keep),1):.0%}) occur in BOTH "
          f"testaments\n")

    print("the widest, with how each language says it:")
    for k, p in sorted(both.items(), key=lambda kv: -kv[1]["n"])[:a.top]:
        names = [n for n, _c in p["names"].most_common(3)]
        print(f"   {k:<8} {p['n']:>6}x  {len(p['books']):>2} books  "
              f"OT {p['heb']:>5} / NT {p['grk']:>5}   {', '.join(names)}")

    if not a.write:
        print("\nnothing written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_note": "Propositions: a predicate and its participants, keyed so "
                     "that Hebrew and Greek reach the same row. The predicate "
                     "is named by the Greek the Septuagint used for it, "
                     "stemmed, since that column stores inflected forms. Built "
                     "from frames AND from constructs whose head names an act, "
                     "because frames are verbal and a nominal formula like "
                     "n'um-YHWH has none. This does NOT replace "
                     "out/patterns.jsonl.gz, which answers what phrase the "
                     "text repeats -- a question about form. See "
                     "tools/propositions.py."}) + "\n")
        for k, p in sorted(keep.items(), key=lambda kv: -kv[1]["n"]):
            f.write(json.dumps({
                "key": k, "instances": p["n"],
                "books": sorted(p["books"]),
                "ot": p["heb"], "nt": p["grk"],
                "crosses": bool(p["heb"] and p["grk"]),
                "says": [[n, c] for n, c in p["names"].most_common(6)],
                "agents": [[x, c] for x, c in p["agents"].most_common(8)],
                "refs": p["refs"][:60]}, ensure_ascii=False) + "\n")
    print(f"\n  -> {DEST.relative_to(ROOT)}  {len(keep):,} propositions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
