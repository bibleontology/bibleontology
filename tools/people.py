"""People, disambiguated from the text before any external source is consulted.

2026-09-05: disambiguation is still calculated from rules in the text, and
external sources are applied only when there are disputes; in those cases the
aim is to understand how the external source was able to make a judgement the
rules could not see, so as to refine the tools.

And then the other direction: where the rules express a definitive ruling, it
is tested against the external source and, if there is disagreement, the rule
behind the ruling is re-evaluated.

So the loop is:

    1. our rules rule, from the text alone
    2. definitive + agrees with an external witness   -> confirmed
    3. definitive + DISAGREES                         -> re-evaluate the RULE
    4. uncertain + the witness resolves it            -> diagnose what it saw,
                                                         and generalise it
    5. uncertain + the witness is also unsure         -> genuinely uncertain

Case 3 is the valuable one. A confident wrong answer names a broken rule, and
fixing the rule improves every case rather than patching one.

## The rule, and the case that already corrected it

The strongest text-internal signal is the **patronymic**: Hebrew writes
*Zecharyah ben-Berekhyah*, and the father is in the text. That is a fact, not a
judgement — unlike the identification of *which* Zechariah, which is exactly
what an external lexicon supplies as editorial work.

The naive form — same father, same man — makes a definitive and WRONG ruling:

    Zech 1:1   "Zechariah son of Berechiah son of Iddo the prophet"
    Ezra 5:1   "Zechariah son of Iddo the prophet"

Different fathers, so two men. But Zechariah 1:1 gives a three-generation chain:
Iddo is the *grandfather*, and Ezra uses *ben* for "descendant of", which is
ordinary Hebrew. They are one man.

**The correction was in the text, not in an external source.** The longer chain
links them and both carry "the prophet". So the rule became: extract the whole
chain, and two occurrences are compatible when one chain is a SUBSEQUENCE of the
other. No query spent.

## What is deliberately not done

No merging across a disagreement. Where the text does not decide, the
occurrences stay separate and the group is marked `uncertain` with its evidence
— Principle 41: the residue is a revisit list, and small is cheap.

    python tools/people.py                # build, report
    python tools/people.py --name Zechariah
"""
from __future__ import annotations

import collections
import gzip
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from macula import MAC, _ref                                      # noqa: E402

OUT = ROOT / "out"
STEP = ROOT / "data" / "raw" / "stepbible"

TITLE = re.compile(r"^(the )?(prophet|priest|king|scribe|seer|governor|"
                   r"official|servant|son|father|elder)$", re.I)


def person_lemmas():
    """Strong numbers the lexicon classes as a person.

    STEPBible column 5 carries a semantic class: `N:N-M-P` and `N:N-F-P` are
    people, `N:N--L` is a location. This is the one external input used BEFORE
    a dispute, and it is a classification rather than an identification —
    "this word names a person" is much weaker than "this is which person".
    """
    out = set()
    for f in sorted(STEP.glob("TBES*")):
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                c = line.rstrip("\n").split("\t")
                if len(c) > 5 and re.match(r"^[HG]\d{4}", c[0].strip()):
                    if re.search(r"N-[MF]-P$", c[5].strip()):
                        out.add(re.sub(r"[^0-9]", "", c[0].strip()))
    return out


def occurrences(persons):
    """Every occurrence of a proper noun that names a person."""
    rows = []
    for f in sorted(MAC.rglob("*.xml")):
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        ws = list(root.iter("w"))
        for i, w in enumerate(ws):
            t = (w.get("type") or "").lower()
            c = (w.get("class") or "").lower()
            if not (t == "proper" or c == "name"
                    or (w.get("morph") or "").startswith("Np")):
                continue
            num = re.sub(r"[^0-9]", "",
                         w.get("strongnumberx") or w.get("strong") or "")
            if num not in persons:
                continue
            nxt = [(x.get("english") or x.get("gloss") or "").strip()
                   for x in ws[i + 1:i + 8]]
            near_names = {(x.get("english") or x.get("gloss") or "").strip()
                          for x in ws[max(0, i - 25):i + 25]
                          if ((x.get("type") or "").lower() == "proper"
                              or (x.get("class") or "").lower() == "name")}
            me = (w.get("english") or w.get("gloss") or "").strip()
            rows.append({"ref": _ref(w.get("ref") or ""),
                         "name": re.sub("’s$", "", me),
                         "lemma": w.get("lemma"), "strong": num,
                         "chain": _chain(nxt), "title": _title(nxt),
                         "tribe": _tribe(nxt),
                         "context": {n for n in near_names if n and n != me}})
    return rows


def _chain(after):
    """The patronymic chain: every name in a run of 'son of X son of Y'.

    Taken as a CHAIN rather than a father, because *ben* spans generations —
    Ezra 5:1 calls Zechariah 'son of Iddo' where Zechariah 1:1 makes Iddo the
    grandfather. A rule that compared only the immediate father ruled those two
    men distinct, confidently and wrongly.
    """
    # The chain must begin IMMEDIATELY after the name, or "David ... Saul's"
    # reads as David son of Saul. It ended up with Israel son of Beor -- which
    # is Balaam -- because the scan wandered forward looking for any "son".
    #
    # A possessive is never a patronymic: "Saul’s" is the genitive of a
    # different clause, not this man’s father.
    if not after or not re.fullmatch(r"son( of)?", after[0].strip(), re.I):
        return []
    out, i = [], 0
    while i < len(after) - 1:
        if re.fullmatch(r"son( of)?", after[i], re.I):
            nm = (after[i + 1] or "").strip()
            if (nm and nm[:1].isupper() and not TITLE.match(nm)
                    and "’" not in nm):
                out.append(nm)
                i += 2
                continue
        break
    return out


TRIBES = ("reuben simeon levi judah dan naphtali gad asher issachar zebulun "
          "joseph benjamin ephraim manasseh").split()
GENTILIC = re.compile(r"^(the )?(" + "|".join(
    [x.capitalize() + "ite" for x in TRIBES]
    + ["Levite", "Benjamite", "Ephraimite", "Ephrathite", "Danite",
       "Gadite", "Reubenite", "Simeonite", "Manassite"]) + r")$", re.I)


def _tribe(after):
    """A tribe named right after the person: a gentilic or 'of the tribe of X'."""
    for j, tok in enumerate(after[:5]):
        if GENTILIC.match(tok):
            return re.sub(r"(the |ite$)", "", tok, flags=re.I).lower()
        if re.fullmatch(r"tribe( of)?", tok, re.I) and j + 1 < len(after):
            nm = after[j + 1].strip().lower()
            if nm in TRIBES:
                return nm
    return None


def _title(after):
    """A title in apposition, immediately after the name.

    Scanning three tokens gave David the titles father, king, priest, seer and
    servant -- every title that happened to fall near any of his occurrences.
    An apposition sits next to the name or it is somebody else’s.
    """
    tok = (after[0] if after else "").strip()
    if TITLE.match(tok) and not re.fullmatch(r"(the )?son", tok, re.I):
        return tok.split()[-1].lower()
    return None


def neighbourhood_conflict(a, b):
    """Do these two occurrences sit in disjoint parts of the graph?

    Dependencies and branch placement are the most definitive
    indicators (2026-09-05). Correct, and stronger than the patronymic in principle,
    because it needs no statement of a father — it uses whatever the text does
    say. Mary of Bethany sits beside Lazarus and Martha; the mother of Jesus
    sits beside Joseph and Bethlehem; the neighbourhoods do not touch.

    **But only as grounds to SPLIT.** Many verses name nobody else — Mat 28:1,
    Mrk 15:47, Luk 1:30 — and treating an empty neighbourhood as a difference
    produced 17 Marys from 26 occurrences. That is the same error the
    patronymic rule made before the default was inverted: absence of evidence
    read as evidence of absence.

    So: disjoint AND both non-empty AND not in the same discourse locality.
    Anything less returns None, which means the text has not said.
    """
    ca, cb = a.get("context") or set(), b.get("context") or set()
    if not ca or not cb:
        return None
    if ca & cb:
        return False                      # they share company: same person
    if _near(a, b, span=1):
        return None                       # adjacent text, no conclusion
    return True                           # disjoint company, far apart


def _group_conflict(r, occs):
    """Does this occurrence conflict with the group AS A WHOLE?

    Comparing pairwise with `all()` was wrong: one non-conflicting member
    absorbs everything, and Mary came out as a single person across 48
    occurrences. The group's company is the UNION of its members' contexts, and
    a newcomer conflicts when its own company is disjoint from that union.
    """
    union = set()
    for o in occs:
        union |= (o.get("context") or set())
    mine = r.get("context") or set()
    if not union or not mine:
        return False                      # nothing said either way
    if union & mine:
        return False                      # shared company
    return not any(_near(r, o, span=1) for o in occs)


def _tribe_conflict(r, occs):
    """Two people named to different tribes are different people.

    Assigning tribes to the people is another way to disambiguate
    (2026-09-05). Yes, and it is text-internal: Hebrew says *ha-Levi*,
    *ben-Yemini*, *ha-Efrati*, or "of the tribe of X". A gentilic is a fact
    about the word, not an identification of the man.
    """
    mine = r.get("tribe")
    if not mine:
        return False
    theirs = {o.get("tribe") for o in occs if o.get("tribe")}
    return bool(theirs) and mine not in theirs


def compatible(a, b):
    """Can these two occurrences be the same person, on the text alone?

    Compatible when one patronymic chain is a subsequence of the other — which
    is what makes 'son of Berechiah son of Iddo' and 'son of Iddo' one man
    rather than two. Two chains that share no ancestor and both state one are
    incompatible; a chain against no chain decides nothing.
    """
    ca, cb = a["chain"], b["chain"]
    if not ca or not cb:
        return None                       # the text does not say
    if _subseq(ca, cb) or _subseq(cb, ca):
        return True
    return False


def _subseq(short, long):
    it = iter(long)
    return all(x in it for x in short)


def _same_book(a, b):
    return a["ref"].split(".")[0] == b["ref"].split(".")[0]


def _near(a, b, span=2):
    """Same book, and within `span` chapters — discourse continuity.

    The first version had no locality rule and treated "the text does not say"
    as "not the same person", which split Zechariah into 47. Luke 1:5, 1:12,
    1:13, 1:18, 1:21, 1:59 and 1:67 are one man in one continuous scene and the
    text never repeats his patronymic, because it does not need to.

    This is the same discourse-continuity principle the elision pass already
    uses to carry a subject across verses, applied to names: a name repeated
    nearby is the same referent **unless something says otherwise**, and the
    patronymic is what says otherwise.
    """
    ba, ca, _ = a["ref"].split(".")
    bb, cb, _ = b["ref"].split(".")
    return ba == bb and abs(int(ca) - int(cb)) <= span


def group(rows):
    """Partition occurrences of one name into people, from the text alone.

    Three outcomes per pair, and the middle one is the whole design:

        chains incompatible   different people, definitively
        chains compatible     the same person, definitively
        no chain either side  undecided by patronymic — fall back to locality,
                              and mark the group uncertain if nothing else
                              ever pins it
    """
    # THE DEFAULT IS ONE PERSON. Splitting requires evidence, exactly as
    # merging does.
    #
    # The first version defaulted to separate and merged on evidence, falling
    # back to locality when the text said nothing. Measured against the old
    # graph across 815 shared names: **69% over-split, 1% under.** David
    # appears across Samuel, Kings, Chronicles and the Psalms and came out as
    # 69 men, because a two-chapter window splits him at every gap.
    #
    # A name carries no evidence of plurality until the text supplies an
    # incompatible patronymic. Most names never do, and most names are one
    # person — so the burden of proof belongs on the split.
    # A bare occurrence must not join a NAMED group while other named groups
    # exist for the same name. That is a coin-flip dressed as a decision:
    # three attested Zechariahs and an unmarked one means the text has not
    # said which, and the honest node is a disjunction over all three.
    #
    # Competition is what creates the disjunction. David has 1,099 references
    # and no competing patronymic anywhere, so merging them is not a guess --
    # nobody else is called David. The rule is therefore about rivals, not
    # about missing evidence.
    named_chains = [r["chain"] for r in rows if r["chain"]]
    contested = len({tuple(c) for c in named_chains}) > 1

    people, unresolved = [], 0
    for r in rows:
        placed = False
        if contested and not r["chain"]:
            # Unresolved only when the rivals are LOCALLY PLAUSIBLE. Joshua
            # son of Nun and Joshua son of Jehozadak never share a book, so a
            # bare Joshua in the book of Joshua is not genuinely ambiguous --
            # and calling it so put 65% of all nodes in the uncertain
            # category, which trips Principle 41's own falsifier: a residue
            # that large is hiding a method that does not work.
            rivals = [p for p in people if p.get("named")
                      and any(_same_book(r, o) for o in p["occurrences"])]
            if len(rivals) == 1:
                rivals[0]["occurrences"].append(r)
                continue
            if len(rivals) > 1:
                people.append({"occurrences": [r], "bare": True})
                continue
            # no locally plausible rival: fall through to ordinary grouping
        for p in people:
            votes = [compatible(r, o) for o in p["occurrences"]]
            if any(v is False for v in votes):
                continue                       # patronymics separate them
            # NEIGHBOURHOOD SPLITTING IS OFF. It might be premature, as that
            # part of the graph was not yet built out. Measured: adding it
            # took agreement with the old graph from
            # 68% DOWN to 54%, over-splits from 15% to 37%. The signal
            # intended is graph position; what is available today is raw
            # token proximity, which is a much weaker proxy and splits on
            # coincidence. `_group_conflict` is kept, unused, for when the
            # person-to-person relations exist to make it real.
            if _tribe_conflict(r, p["occurrences"]):
                continue                       # named to different tribes
            p["occurrences"].append(r)
            placed = True
            break
        if not placed:
            people.append({"occurrences": [r], "named": bool(r["chain"])})
    for p in people:
        chains = [o["chain"] for o in p["occurrences"] if o["chain"]]
        titles = {o["title"] for o in p["occurrences"] if o["title"]}
        p["chain"] = max(chains, key=len) if chains else []
        p["titles"] = sorted(titles)
        p["certain"] = bool(chains)
        if not chains:
            unresolved += 1
    return people, unresolved


def main() -> int:
    persons = person_lemmas()
    rows = occurrences(persons)
    byname = collections.defaultdict(list)
    for r in rows:
        byname[r["name"].lower()].append(r)

    if "--name" in sys.argv:
        want = sys.argv[sys.argv.index("--name") + 1].lower()
        people, _ = group(byname.get(want, []))
        print(f"{want}: {len(byname.get(want, []))} occurrences -> "
              f"{len(people)} people\n")
        for p in people:
            mark = "" if p["certain"] else "   [uncertain: no patronymic]"
            print(f"  chain={p['chain']}  titles={p['titles']}{mark}")
            print(f"     {[o['ref'] for o in p['occurrences']][:8]}")
        return 0

    allp, stats = [], collections.Counter()
    for name, rs in byname.items():
        people, unres = group(rs)
        stats["occurrences"] += len(rs)
        stats["people"] += len(people)
        stats["uncertain"] += sum(1 for p in people if not p["certain"])
        if len(people) > 1:
            stats["names_split"] += 1
        # An UNRESOLVED node: this occurrence names one of these people and
        # the text does not say which.
        #
        # A type of node that is unresolved and holds a list of
        # possibilities, which will not stay that way.
        #
        # Better than a confidence flag, because a flag says only that we are
        # unsure while a candidate list says WHAT the alternatives are — which
        # is what makes it revisitable. And better than forcing a choice,
        # because edges can attach to the unresolved node: "someone named
        # Zechariah prophesied in Jerusalem" is true whichever man it was, so
        # downstream structure is not blocked on a decision nobody can make
        # yet. Resolution is then one edit rather than an un-merge and a
        # re-split.
        if len(people) > 1:
            bare = [p for p in people if p.get("bare")]
            named = [p for p in people if p["chain"]]
            for p in bare:
                p["candidates"] = [" ".join(["son of"] + q["chain"])
                                   for q in named] or None
        for p in people:
            allp.append({"name": rs[0]["name"], "chain": p["chain"],
                         "unresolved": bool(p.get("candidates")),
                         "candidates": p.get("candidates"),
                         "titles": p["titles"], "certain": p["certain"],
                         "refs": [o["ref"] for o in p["occurrences"]],
                         "strong": sorted({o["strong"]
                                           for o in p["occurrences"]})})
    path = OUT / "people.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for p in sorted(allp, key=lambda x: (-len(x["refs"]), x["name"])):
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")

    print("PEOPLE, from the text alone — no external identification used")
    print(f"  person-name occurrences   {stats['occurrences']:>7,}")
    print(f"  distinct names            {len(byname):>7,}")
    print(f"  people after grouping     {stats['people']:>7,}")
    print(f"  names split into several  {stats['names_split']:>7,}")
    print(f"  groups with NO patronymic {stats['uncertain']:>7,}   "
          f"{100*stats['uncertain']//max(stats['people'],1)}% — the text does "
          f"not say")
    print(f"\n  wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
