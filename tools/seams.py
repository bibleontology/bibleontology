"""Where a passage divides: our evidence first, BSB where we cannot tell.

2026-09-09, after twelve psalms were marked by hand: the result does not have
to be perfect, as there is not one right answer; getting in the ballpark can be
reasonably good, and if signals are really unclear the default is BSB.

That settles a question the project has been stuck on. Every previous attempt
tried to derive every seam and reported failure whenever it could not -- the
episode scorer speaks on 7 of 42 breaks and stays silent on six chapters in
ten. That rule turns that silence from a failure into a **branch**: derive
what the text marks, defer the rest, and record which is which.

## The evidence, in the order it is trusted

Each is a measurement (made 2026-09-09), not a guess:

    speech closes          2.28x   a quotation ending
    temporal connective    1.78x   'after this', 'in those days'
    anaphora run start     1.25x   a repeated opening lemma beginning
    acrostic run start     1.32x   the alphabet advancing

And one signal that looked promising and is NOT used, recorded so it is not
tried again in ignorance. A **participant chain** change -- MACULA's
`participantref`, 51,755 words this project had never read -- reads perfectly
on Psalm 17, binding verses 10-13 to their antecedent in verse 9 exactly as
the hand reading has it, in a psalm with zero backward connective attachment.
Corpus-wide it fires 3,391 times at 54.9% against a 50.9% base: **1.08x, which
is chance**, and it was 79% of this module's output. It is carried on each row
as `participant_turnover` for a consumer that wants it, and is never a reason
for a seam.

And one signal counted AGAINST a seam, because it says the verse continues:

    backward attachment            a connective pointing back. The hand
                                   reading ((((6-7)-8)-9)-10) for Psalm 92 is
                                   exactly this chain, and reproducing it was
                                   the first time our data yielded a structure
                                   that had been written by hand.

## The fallback, and why it is honest

Where nothing above fires and BSB divides, **BSB's break is taken and labelled
`bsb`**. This is Principle 44's structure/identity line: paragraphing is an
editorial judgement the source does not record, so borrowing it adds
information rather than replacing evidence.

Every row carries `by`, so a consumer can demand derived seams only. **A group
sourced from BSB is BSB's opinion, and this file says so rather than presenting
it as a finding.**

## What it does NOT do

It produces a flat list of seams. The hand notation is a tree --
`((15-(16-17))-18)`, `(4-(5-(6-((7-9)-(10(11-12))))))` -- and it is right that
this is the better shape: what modifies or builds on what. Attachment is
recorded per verse here, but assembling it into a tree is a separate module and
is not attempted in this one.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
HEB = ROOT / "data" / "raw" / "macula" / "hebrew"
DEST = OUT / "seams.jsonl.gz"

W = re.compile(r"<w\s([^>]*?)/?>", re.S)
A = re.compile(r'([\w:.-]+)="([^"]*)"', re.S)
REF = re.compile(r"^([A-Z0-9]{3})\s+(\d+):(\d+)!(\d+)")


def load(name):
    rows = []
    p = OUT / name
    if not p.exists():
        return rows
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                if not any(k.startswith("_") for k in d):
                    rows.append(d)
    return rows


def parts(r):
    p = str(r).split(".")
    if len(p) < 3 or not p[1].isdigit() or not p[2].isdigit():
        return None
    return p[0], int(p[1]), int(p[2])


def chains():
    """Participant chains from MACULA, per Hebrew chapter.

    -> {(book, chapter): {verse: set_of_participant_ids}}
    """
    out = collections.defaultdict(lambda: collections.defaultdict(set))
    files = sorted(HEB.glob("*.xml"))
    for i, p in enumerate(files):
        if i % 250 == 0:
            print(f"  chains {i}/{len(files)} ...", flush=True)
        for m in W.finditer(p.read_text(encoding="utf-8")):
            a = dict(A.findall(m.group(1)))
            r = REF.match(a.get("ref", "") or "")
            if not r:
                continue
            pr = a.get("participantref")
            if not pr:
                continue
            key = (r.group(1), int(r.group(2)))
            v = int(r.group(3))
            for one in pr.split():
                one = one.strip().rstrip(";")
                if one:
                    out[key][v].add(one)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--passage", default="Psa.103")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    sf = {}
    for d in load("sentence-function.jsonl.gz"):
        sf.setdefault(d["ref"], d)
    depth = {d["ref"]: d["depth"] for d in load("speech-depth.jsonl.gz")}
    dev = collections.defaultdict(list)
    for d in load("devices.jsonl.gz"):
        dev[d["ref"]] = d["marks"]
    bsb, agree, heading = set(), {}, {}
    for d in load("structure.jsonl.gz"):
        if "engbsb" in (d.get("by") or []):
            bsb.add(d["ref"])
        agree[d["ref"]] = d.get("agree", 0)
        # A SECTION HEADING OUTRANKS EVERYTHING. 2026-09-09: Proverbs also
        # gets some headings from BSB, which are always deferred to. An
        # editor who wrote a title has committed to a unit, which is a stronger
        # act than leaving a blank line -- and it fixes Proverbs 31, where our
        # acrostic misfired at v3 and v8 while BSB's heading sits at v10,
        # exactly where the alphabet actually starts.
        if d.get("level") == "section" and d.get("title"):
            heading[d["ref"]] = d["title"]

    # VERSE UNIVERSE FROM THE SENTENCE LAYER, NOT THE COLA LAYER. cola.jsonl.gz
    # is built from the Masoretic accents and so is Hebrew-only: keying off it
    # meant this module covered 39 books and no Greek at all, which is why
    # Romans could not be asked for.
    verses = collections.defaultdict(list)
    seen = set()
    for d in load("sentence-function.jsonl.gz"):
        p = parts(d["ref"])
        if p and d["ref"] not in seen:
            seen.add(d["ref"])
            verses[(p[0], p[1])].append(p[2])

    print("reading participant chains from MACULA ...", flush=True)
    ch = chains()
    MAC = {"Gen": "GEN", "Exo": "EXO", "Lev": "LEV", "Num": "NUM", "Deu": "DEU",
           "Jos": "JOS", "Jdg": "JDG", "Rut": "RUT", "1Sa": "1SA", "2Sa": "2SA",
           "1Ki": "1KI", "2Ki": "2KI", "1Ch": "1CH", "2Ch": "2CH", "Ezr": "EZR",
           "Neh": "NEH", "Est": "EST", "Job": "JOB", "Psa": "PSA", "Pro": "PRO",
           "Ecc": "ECC", "Sng": "SNG", "Isa": "ISA", "Jer": "JER", "Lam": "LAM",
           "Ezk": "EZK", "Dan": "DAN", "Hos": "HOS", "Jol": "JOL", "Amo": "AMO",
           "Oba": "OBA", "Jon": "JON", "Mic": "MIC", "Nam": "NAM", "Hab": "HAB",
           "Zep": "ZEP", "Hag": "HAG", "Zec": "ZEC", "Mal": "MAL"}

    # TWO NUMBERINGS, EACH KEPT IN ITS OWN (plan A.14, mended 2026-10-04).
    # The verses walked here are MACULA's (the Hebrew's numbering); the
    # Berean's headings and paragraph breaks are keyed in the Berean's. Looked
    # up by the Hebrew verse, a heading in a renumbered chapter was missed or
    # landed on the wrong verse (BSB Exo 8:1 "The Second Plague: Frogs" is
    # Hebrew 7:26). So each Hebrew verse is turned into the Berean's number
    # (out/versemap.json, Hebrew -> Berean) to ask about headings and breaks,
    # and a row is keyed in the numbering of what it records: a derived seam
    # by the Hebrew verse, a heading or a Berean break by the Berean's -- which
    # is how the server has looked them up since 2026-09-25.
    vm = OUT / "versemap.json"
    moved = (json.loads(vm.read_text(encoding="utf-8")).get("moved") or {}) \
        if vm.exists() else {}
    placed = set()

    rows, tally = [], collections.Counter()
    for (bk, c), vs in sorted(verses.items()):
        vs = sorted(vs)
        cc = ch.get((MAC.get(bk, bk), c), {})
        for i, v in enumerate(vs):
            r = f"{bk}.{c}.{v}"
            e = moved.get(r, r)              # the Berean's number for it
            if i == 0:
                # A CHAPTER'S FIRST VERSE has no verse before it to divide
                # from, so it gets no derived seam -- but it keeps its heading.
                # Skipping it outright lost 1,184 of the Berean's 3,081
                # headings: Matthew 5 opened without "The Sermon on the Mount",
                # 1 Chronicles 13 without "David Fetches the Ark".
                if e in heading:
                    tally["heading"] += 1
                    placed.add(e)
                    rows.append({"ref": e, "by": "heading", "why": [],
                                 "title": heading[e], "agree": agree.get(e, 0),
                                 "attached": False, "participant_turnover": False})
                continue
            pr = f"{bk}.{c}.{vs[i-1]}"
            s = sf.get(r) or {}
            why = []

            d0, d1 = depth.get(pr), depth.get(r)
            if d0 is not None and d1 is not None and d0 > 0 and d1 == 0:
                why.append("speech-close")
            if s.get("relation") == "temporal":
                why.append("temporal")
            for m in dev.get(r, []):
                run = m.get("run") or []
                if m.get("device") not in ("anaphora", "acrostic"):
                    continue
                if len(run) != 2 or run[0] != v or run[1] - run[0] < 1:
                    # A RUN OF ONE MARKS NOTHING. Psalm 145 gives each verse
                    # its own letter, so every verse "starts" an acrostic run
                    # and this fired 20 seams across 21 verses -- a psalm cut
                    # into single lines. Psalm 119's runs are 8 verses long and
                    # behave. Require a run that actually spans.
                    continue
                why.append(m["device"])
            # PARTICIPANT CHANGE IS NOT USED AS EVIDENCE. It read cleanly on
            # Psalm 17, where it binds verses 10-13 to their antecedent in v9
            # exactly as read by hand -- but measured corpus-wide it fires
            # 3,391 times at 54.9% precision against a 50.9% base: 1.08x, which
            # is chance. It was 79% of this module's output and dragged overall
            # precision to 1.13x. Recorded as CONTEXT, never as a reason.
            a0, a1 = cc.get(vs[i - 1], set()), cc.get(v, set())
            turnover = bool(a0 and a1 and not (a0 & a1))

            # evidence AGAINST: this verse attaches back to the previous one
            attached = s.get("direction") == "backward"

            if e in heading and e in placed:
                # two Hebrew verses, one Berean verse: a psalm's title is the
                # Hebrew's verse 1 and inside the Berean's verse 1 (Psalm 3),
                # so its heading is already placed -- once is enough (60 were
                # written twice)
                src, kept = None, False
            elif e in heading:
                src, kept = "heading", True        # outranks everything
            elif why and not attached:
                src, kept = "derived", True
            elif attached:
                src, kept = "attached", False      # explicitly NOT a seam
            elif e in bsb:
                src, kept = "bsb", True
            else:
                src, kept = None, False

            if kept:
                tally[src] += 1
                if src == "heading":
                    placed.add(e)
                rows.append({"ref": r if src == "derived" else e, "by": src,
                             "why": why,
                             "title": heading.get(e) if src == "heading" else None,
                             "agree": agree.get(e, 0),
                             "attached": attached,
                             "participant_turnover": turnover})
            elif attached:
                tally["suppressed-by-attachment"] += 1

    # EVERY HEADING THE BEREAN WROTE IS SHOWN. One whose verse the walk above
    # never reached (a verse with no Hebrew or Greek counterpart) is added as
    # it stands, so no heading can go missing for a reason this file hides.
    for e in sorted(set(heading) - placed):
        tally["heading (verse not walked)"] += 1
        rows.append({"ref": e, "by": "heading", "why": [], "title": heading[e],
                     "agree": agree.get(e, 0), "attached": False,
                     "participant_turnover": False})

    # one row per verse and kind: where two Hebrew verses are one Berean verse
    # (a psalm's title, Hosea 14:10 → 14:9), both can claim the same row
    seen = set()
    rows = [x for x in rows if not ((x["ref"], x["by"]) in seen or seen.add((x["ref"], x["by"])))]

    print(f"\nseams: {len(rows):,}")
    print(f"  BSB section headings  : {tally['heading']:,}"
          f" (+{tally['heading (verse not walked)']:,} at a verse not walked)")
    print(f"  derived from the text : {tally['derived']:,}")
    print(f"  deferred to BSB       : {tally['bsb']:,}")
    print(f"  suppressed (attaches back): {tally['suppressed-by-attachment']:,}")
    print(f"  -> {100*tally['derived']/max(len(rows),1):.1f}% of seams are ours")

    w = collections.Counter(x for r in rows for x in r["why"])
    print(f"  evidence used: {dict(w.most_common())}")

    print(f"\n{a.passage}")
    for r in rows:
        if r["ref"].startswith(a.passage + "."):
            print(f"   v{r['ref'].split('.')[2]:<4} {r['by']:<9} "
                  f"{r['why'] or ''}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_note": "Seams with provenance. by='derived' means the text marks "
                     "it (speech close, temporal connective, participant chain "
                     "break, device run start); by='bsb' means we could not "
                     "tell and took the Berean editor's paragraph break, per "
                     "Doug 2026-09-09: 'if signals are really unclear default "
                     "to BSB'. A verse whose connective attaches it backward "
                     "suppresses a seam even where BSB divides.",
        }, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
