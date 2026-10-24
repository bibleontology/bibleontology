"""One record per theme, carrying every piece of evidence for it.

2026-09-15: the join is fundamental, against the release gate set the same day:
ask for the 50 most prominent themes in the Bible, based on evidence, and get a
defensible list.

Five independent axes of evidence existed by that afternoon and **none of them
were joined**, so answering "why is holiness on this list?" meant assembling
four tools' output by hand. This does the assembly and writes it down.

    stamps        a model's reading of a section        broad, unverifiable
    families      the original-language word is there   checkable, narrow
    summaries     the author saying "here is the whole" 16 verses
    types         the author asserting an OT<->NT link  12 verses
    lexicon       frequency and spread, bottom-up       13,857 lemmas

## Why rank by axes first and size second

**Prominence here means weight of evidence, not volume.** A theme three
independent methods name is better attested than one a single model stamped
often, however often it stamped it. So the sort is: number of axes, then spread
across the 66 books, then share of the corpus.

That ordering is the whole defensibility claim and it fits in a sentence, which
is the test it has to pass. The alternative -- one blended score -- hides which
evidence is doing the work, and this project has already been burned by a
blended score: five ranking measures built on 2026-09-14 kept disagreeing
because each was the right question for a different family of pattern.

## What is judgement here, and it is marked

`RELATED` below maps stamp ids to word families. Nothing computes it. `blood`
and `sacrifice` clearly belong together; `faith` and `promise_faithfulness`
clearly do NOT, because the stamp is God's faithfulness to his promise and the
family is human trust -- and treating them as one would be the
`character_roles` error again, a nearby id standing in for a missing one. Each
mapping carries `same`, `overlaps` or `none`, and `overlaps` means a reader
should check rather than trust.

## What this does not claim

A theme's presence here is not a claim that the text teaches it, only that
stated evidence supports it and the evidence is shown. The recall floors are
carried through unchanged: `grace` misses all seven passages agreed to teach
it, and that number appears in its record rather than in a footnote.

    python tools/themeregister.py
    python tools/themeregister.py --why holiness
    python tools/themeregister.py --write
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import sys
import unicodedata

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools"))

# How much support an axis needs before it counts toward a theme's rank. An
# axis resting on a handful of sections cannot be told from chance, and a rank
# that counts it reads as stronger evidence than it is. The typology axis (7
# sections) falls below this and is recorded as a note instead.
MIN_AXIS = 12

# How far above chance a stamp/family pair must land before it counts as
# corroboration. 1.5x is the same order of floor the summary and typology axes
# use (1.2x), set higher because this axis is applied to a hand-made mapping.
MIN_CORROB_LIFT = 1.5

NT = {"Matt", "Mark", "Luke", "John", "Acts", "Rom", "1Cor", "2Cor", "Gal",
      "Eph", "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim", "Titus",
      "Phlm", "Heb", "Jas", "1Pet", "2Pet", "1John", "2John", "3John",
      "Jude", "Rev"}

# HAND JUDGEMENT. stamp id -> (family id, how close). Nothing computes this.
#
# `none` entries are the informative ones: they are stamps with no lexical
# confirmation available, which is not a defect in either layer but a fact
# about what each can see. `overlaps` means the two name related but
# non-identical things and a reader should check before relying on the pair.
RELATED = {
    "sacrifice": ("blood", "overlaps"),
    "mercy_restoration": ("grace", "overlaps"),
    "judgment": ("wrath", "overlaps"),
    "priesthood": ("holiness", "overlaps"),
    "temple_presence": ("holiness", "overlaps"),
    "law_wisdom": ("fear_of_the_lord", "overlaps"),
    "people_of_god": ("adoption", "overlaps"),
}

# Deliberately NOT mapped, with the reason, because the near-miss is the trap:
#   faith      <- promise_faithfulness is GOD's faithfulness to his promise;
#                 the family is human trust. Different claims, one English word.
#   justice    <- stranger_sojourner is a character role, not the demand.
#                 Mic 6:8 is not a passage about a sojourner.
REFUSED = {
    "faith": "promise_faithfulness is God's faithfulness, not human trust",
    "justice": "stranger_sojourner is a role, not the ethical demand",
}


def nfc(s):
    return unicodedata.normalize("NFC", s)


def vkey(r):
    b, c, v = r.split(".")
    return (b, int(c), int(v))


def load_stamps():
    """-> ({id: {section refs}}, {id: category}, [all section refs])"""
    by = collections.defaultdict(set)
    cat = {}
    allrefs = set()
    for line in (OUT / "stamps-leveled.jsonl").read_text(
            encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        allrefs.add(d["ref"])
        if d.get("category") == "themes":
            by[d["id"]].add(d["ref"])
            cat[d["id"]] = d["category"]
    return by, cat, sorted(allrefs, key=vkey)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--why", help="one theme, all its evidence")
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    import wordfamily as wf
    from themespine import DECLARED

    stamps, _cat, allrefs = load_stamps()
    il = wf.load_interlinear()
    of = wf.container(allrefs)
    fams = {f["id"]: f for f in wf.load_families()}
    wf.validate(fams.values(), {l for ls in il.values() for l in ls})

    # Declared-summary sections, for the stamp side of the summary axis.
    decl_secs = {of(r) for r in DECLARED if of(r)}

    recs = {}

    def rec(tid, name):
        return recs.setdefault(tid, {
            "id": tid, "name": name, "axes": [], "books": set(),
            "sections": set(), "verses": 0, "notes": [], "limits": []})

    # ---- axis 1: theme stamps -------------------------------------------
    for sid, refs in stamps.items():
        r = rec(sid, sid.replace("_", " "))
        r["axes"].append("stamp")
        r["sections"] |= refs
        r["books"] |= {x.split(".")[0] for x in refs}
        r["stamp_sections"] = len(refs)
        # summary axis for a stamp: does it sit on the sections holding the
        # text's own summaries, more than its NT rate would predict?
        onsum = len(refs & decl_secs)
        ntrate = len([x for x in refs if x.split(".")[0] in NT]) / max(
            len([x for x in allrefs if x.split(".")[0] in NT]), 1)
        if onsum >= 3 and onsum / len(decl_secs) > ntrate * 1.2:
            r["axes"].append("summary")
            r["notes"].append(
                f"on {onsum}/{len(decl_secs)} sections holding the text's own "
                f"summaries, above its {100*ntrate:.0f}% NT rate")

    # ---- axis 2: word families ------------------------------------------
    for fid, f in fams.items():
        lem = {nfc(x) for x in set(f["greek"]) | set(f["hebrew"])}
        pairs = [tuple(nfc(x) for x in p) for p in f.get("pairs", [])]

        def sees(ls):
            return bool(ls & lem) or any(x in ls and y in ls for x, y in pairs)

        verses = {ref for ref, ls in il.items() if sees(ls)}
        secs = {s for s in (of(x) for x in verses) if s}
        r = rec(fid, f["name"])
        r["axes"].append("family")
        r["verses"] = len(verses)
        r["sections"] |= secs
        r["books"] |= {x.split(".")[0] for x in verses}
        r["family_verses"] = len(verses)

        enacted = f.get("enacted", [])
        miss = [x for x in enacted if not sees(il.get(x, set()))]
        if enacted:
            r["recall"] = f"{len(enacted)-len(miss)}/{len(enacted)}"
            if miss:
                r["limits"].append(
                    f"lemmas miss {len(miss)} of {len(enacted)} passages "
                    f"agreed to teach it: {', '.join(miss[:4])}")
        for k in ("_rejected_rule", "_rejected_lemma"):
            if f.get(k):
                r["limits"].append("a member was tried and dropped; see "
                                   "ontology/word-families.json")
        # summary axis for a family: do its words appear in the verses where
        # the text summarises itself? Parallel to the stamp test and stronger,
        # because it is the words rather than a section overlap.
        insum = [x for x in DECLARED if sees(il.get(x, set()))]
        if len(insum) >= 2:
            r["axes"].append("summary")
            r["notes"].append(
                f"its words appear in {len(insum)} of the {len(DECLARED)} "
                f"verses where the text summarises itself: "
                f"{', '.join(sorted(insum)[:4])}")

    # ---- axis 3: the two layers corroborating each other -----------------
    #
    # CONTAINMENT, NOT JACCARD. The first version scored these pairs with
    # Jaccard and got 0.21-0.28, which was written up as "overlap, not
    # agreement" -- and that conclusion was an artefact of the metric.
    # Jaccard punishes unequal set sizes: `mercy_restoration` holds 1,668
    # sections and `grace` 440, so even if EVERY grace section sat inside it,
    # Jaccard could not exceed 0.26. It was measuring the size difference.
    #
    # The question a corroboration axis actually asks is "what share of the
    # narrower layer does the broader one confirm", which is the overlap
    # coefficient, |A n B| / min(|A|,|B|). Grace scores 0.84 on it: 84% of the
    # sections where the grace WORDS appear are also stamped
    # `mercy_restoration`, by a model that never saw the lemma list. That is
    # corroboration, and Jaccard hid it.
    for sid, (fid, how) in RELATED.items():
        if sid in recs and fid in recs and how != "none":
            ss, fs = recs[sid]["sections"], recs[fid]["sections"]
            if ss and fs:
                both = len(ss & fs)
                small, big = sorted((ss, fs), key=len)
                ov = both / len(small)
                chance = len(big) / len(allrefs)
                lift = ov / chance if chance else 0.0
                # AND LIFT OVER CHANCE, not a flat containment floor. A flat
                # floor rewards pairing against a huge set and punishes a
                # precise pairing against a small one, which is backwards:
                #   adoption / people_of_god   0.84 containment, 1.18x chance
                #   blood / sacrifice          0.34 containment, 3.15x chance
                # people_of_god covers 71% of the corpus, so 0.84 of anything
                # falls inside it for nothing; `sacrifice` covers 11%, so a
                # third of the blood verses landing there is real. Lift is the
                # test the summary and typology axes already use, and using it
                # here too is consistency rather than a new idea.
                note = (f"{sid} (stamp) and {fid} (lemmas) {how}: {both} "
                        f"sections in common, {ov:.0%} of the narrower layer, "
                        f"{lift:.2f}x its {chance:.0%} base rate -- `{how}` is "
                        f"a hand judgement, not computed")
                for t in (sid, fid):
                    if lift >= MIN_CORROB_LIFT:
                        recs[t]["axes"].append("corroborated")
                    else:
                        recs[t]["limits"].append(
                            f"weak corroboration with "
                            f"{fid if t == sid else sid}: {lift:.2f}x chance, "
                            f"below {MIN_CORROB_LIFT} -- {ov:.0%} containment "
                            f"but the partner covers {chance:.0%} of the "
                            f"corpus anyway")
                    recs[t]["notes"].append(note)
    for fid, why in REFUSED.items():
        if fid in recs:
            recs[fid]["limits"].append(f"no stamp deliberately: {why}")

    # ---- axis 4: declared types -----------------------------------------
    #
    # DERIVED, not assigned. The first version of this block handed the axis to
    # redemption_in_christ, sacrifice and new_creation because they sounded
    # like typology, which is precisely the move this project keeps catching
    # itself in -- a plausible label standing in for a measurement. The 12
    # verified verses land in sections that carry whatever they carry, and
    # those stamps are the evidence.
    p = OUT / "declared-types.jsonl"
    if p.exists():
        tverses = [json.loads(line)["ref"]
                   for line in p.read_text(encoding="utf-8").splitlines()
                   if line.strip() and not line.startswith('{"_')]
        tsecs = {of(r) for r in tverses if of(r)}
        for sid, refs in stamps.items():
            on = len(refs & tsecs)
            base = len(refs) / len(allrefs)
            if on >= 3 and on / max(len(tsecs), 1) > base * 1.2:
                # AN AXIS NEEDS ENOUGH SUPPORT TO BEAT CHANCE, and this one
                # does not: the 12 verified typology verses fall in just 7
                # sections. At n=7 a theme carried by half the corpus clears
                # "3 or more" by luck, and counting it promoted eight themes by
                # a full axis -- including the top three. So it is recorded and
                # not counted. The rule is general, not a patch for this axis.
                if len(tsecs) >= MIN_AXIS:
                    recs[sid]["axes"].append("typology")
                recs[sid]["notes"].append(
                    f"on {on}/{len(tsecs)} sections holding a verse where the "
                    f"NT names an OT<->NT type, above its "
                    f"{100*base:.0f}% corpus rate -- NOT counted as an axis, "
                    f"only {len(tsecs)} sections support it "
                    f"(tools/declaredtypes.py)")

    # ---- axis 5: the lexical audit --------------------------------------
    for fid in ("holiness", "wrath", "fear_of_the_lord", "blood"):
        if fid in recs:
            recs[fid]["axes"].append("lexicon")
            recs[fid]["notes"].append(
                "found bottom-up by tools/lexcoverage.py going word by word, "
                "not from anyone's list; has no id in the 264-stamp vocabulary")

    for r in recs.values():
        r["axes"] = sorted(set(r["axes"]))

    ranked = sorted(recs.values(),
                    key=lambda r: (-len(r["axes"]), -len(r["books"]),
                                   -len(r["sections"])))

    if a.why:
        r = recs.get(a.why)
        if not r:
            raise SystemExit(f"no theme {a.why!r}; have: "
                             + ", ".join(sorted(recs)))
        print(f"{r['name']}  ({r['id']})\n")
        print(f"  evidence axes  {len(r['axes'])}: {', '.join(r['axes'])}")
        print(f"  spread         {len(r['books'])}/66 books")
        print(f"  sections       {len(r['sections'])} of {len(allrefs)}")
        if r.get("family_verses"):
            print(f"  verses         {r['family_verses']} by lemma")
        if r.get("stamp_sections"):
            print(f"  stamped        {r['stamp_sections']} sections")
        if r.get("recall"):
            print(f"  recall         {r['recall']} on its agreed passages")
        for n in r["notes"]:
            print(f"  + {n}")
        for l in r["limits"]:
            print(f"  ! {l}")
        return 0

    print(f"{len(ranked)} themes with stated evidence, "
          f"ranked by axes then spread\n")
    print(f"  {'#':>2} {'axes':>4}  {'books':>5} {'sects':>5}  "
          f"{'theme':<24} evidence")
    for i, r in enumerate(ranked[:a.top], 1):
        flag = " !" if r["limits"] else ""
        print(f"  {i:>2} {len(r['axes']):>4}  {len(r['books']):>5} "
              f"{len(r['sections']):>5}  {r['name'][:23]:<24} "
              f"{','.join(r['axes'])}{flag}")
    print(f"\n  ! = has a stated limit; see --why <id>")
    print(f"  {sum(1 for r in ranked if len(r['axes']) >= 3)} themes rest on "
          f"3+ independent axes, "
          f"{sum(1 for r in ranked if len(r['axes']) == 1)} on only one")
    # THE AXES ARE NOT EQUALLY STRONG and the table cannot show that, so it is
    # said here. Counting axes treats 3,078 stamped sections and 11 typology
    # sections as one tick each. They are not one tick each.
    print(f"\n  axis strength -- they are NOT equal, and the count above "
          f"treats them as equal:")
    print(f"    stamp        {len(allrefs):,} sections read by a model     "
          f"broad, unverifiable")
    print(f"    family       {len(fams)} lemma sets over {len(il):,} verses "
          f"   checkable, narrow recall")
    print(f"    corroborated a hand-mapped stamp/family pair      "
          f"`overlaps` is judgement")
    print(f"    summary      {len(DECLARED)} verses                          "
          f"    thin")
    nts = len(tsecs) if p.exists() else 0
    print(f"    typology     {nts} sections                          "
          f"    below MIN_AXIS={MIN_AXIS}: recorded, NOT counted")

    if a.write:
        p = OUT / "theme-register.jsonl"
        with p.open("w", encoding="utf-8") as f:
            f.write(json.dumps({
                "_note": "One record per theme with every axis of evidence for "
                         "it. Ranked by NUMBER OF INDEPENDENT AXES, then "
                         "spread, then size -- not by a blended score, so it "
                         "stays visible which evidence is doing the work. "
                         "`limits` carries each theme's known weaknesses "
                         "unchanged. See tools/themeregister.py."}) + "\n")
            for r in ranked:
                d = dict(r)
                d["books"] = sorted(r["books"])
                d["sections"] = len(r["sections"])
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        print(f"\n  -> {p.relative_to(ROOT)}  {len(ranked)} themes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
