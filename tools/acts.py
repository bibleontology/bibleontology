"""Claims, assertions and commands -- typed from mood, which is a closed class.

2026-09-04: claims, assertions and commands were asked for as the types, following
the E1 ruling on Genesis 1: "let there be light" is a speech node that is a
command and not a claim; "there was light" is the effect of the command; the
command event is fundamental to domain-driven design and is captured as a core
pattern.

That ruling had stood as a requirement with nothing implementing it. This implements it, and it costs nothing, because **mood is
grammatical**. An imperative is a command whoever reads it; the tagged text
states the mood and no model is asked to decide anything.

## Two axes, and conflating them is the mistake

    ACT     what the clause DOES        assertion / command / question / wish
    STATUS  how it is PUT FORWARD       asserted / attributed / entertained /
                                        denied

Genesis 1:3 needs both to come out right. `yehi` is a command; `wayehi` is an
assertion; the first is spoken by God inside a quotation and the second is the
narrator's. Same verb root, same verse, opposite records.

The status axis is what keeps the graph honest. A conditional's protasis, a
rhetorical question, a quoted objection and a denial all look like claims and
none of them are being claimed. 22% of the corpus's finite verbs sit under a
negation and 12% inside a condition or a question; a graph that records those
as assertions is asserting the opposite of the text in a quarter of its rows.

## Scoping, which is where the first two attempts went wrong

**Verse-level scoping does not work.** Marking every verb in a verse
interrogative because the verse contains *mah* made Genesis 2:19 a question --
*mah* there is "whatever the man called". Marking every verb denied because the
verse contains *lo* does the same thing to any verse with two clauses.

Both particles bind to the verb that FOLLOWS them, in both languages. So the
scope is the **pre-field**: the words between the previous finite verb and this
one. That is exact rather than a window, and it is a property of the text
rather than a number chosen to make the output look reasonable.

Interrogatives are read from the tag, not guessed from lemmas: Hebrew marks the
interrogative particle as its own segment class `Ti`, and Greek keeps
interrogative `G5101` distinct from indefinite `G5100`.

## What Greek subjunctive is not

The first run called Acts 2:21 a wish -- "everyone who calls on the name of the
Lord will be saved". It is a relative clause. The Greek subjunctive is
overwhelmingly subordinate (after *hina*, *ean*, *hos an*) and is a speech act
of its own only when hortatory (1st plural, "let us") or prohibitive (*me* with
a 2nd-person aorist). Subordinate subjunctives open no clause here at all.

    python tools/acts.py              # counts, examples, and the defects
    python tools/acts.py --json       # writes out/acts.jsonl
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
from markers import corpus, base                                  # noqa: E402
from quotes import spans                                          # noqa: E402
from tuples import _seg                                           # noqa: E402
from bibleont.decompose import _load                              # noqa: E402

# Closed classes, by lemma number so STEPBible's disambiguating suffixes do not
# have to be enumerated. Every one of these does exactly one job.
NEG = {"H3808", "H0408", "H0369", "H1115", "G3756", "G3361", "G3364"}
COND = {"H0518", "H3863", "G1487", "G1437"}
SUBORD = {"G2443", "G3704", "G1437", "G3752", "G302", "G1487"}
MH = {"G3361", "G3364"}

BOOK = {"Gen": "Gen", "Exo": "Exod", "Lev": "Lev", "Num": "Num", "Deu": "Deut",
        "Jos": "Josh", "Jdg": "Judg", "Rut": "Ruth", "1Sa": "1Sam",
        "2Sa": "2Sam", "1Ki": "1Kgs", "2Ki": "2Kgs", "1Ch": "1Chr",
        "2Ch": "2Chr", "Ezr": "Ezra", "Neh": "Neh", "Est": "Esth",
        "Job": "Job", "Psa": "Ps", "Pro": "Prov", "Ecc": "Eccl",
        "Sng": "Song", "Isa": "Isa", "Jer": "Jer", "Lam": "Lam",
        "Ezk": "Ezek", "Dan": "Dan", "Hos": "Hos", "Jol": "Joel",
        "Amo": "Amos", "Oba": "Obad", "Jon": "Jonah", "Mic": "Mic",
        "Nam": "Nah", "Hab": "Hab", "Zep": "Zeph", "Hag": "Hag",
        "Zec": "Zech", "Mal": "Mal", "Mat": "Matt", "Mrk": "Mark",
        "Luk": "Luke", "Jhn": "John", "Act": "Acts", "Rom": "Rom",
        "1Co": "1Cor", "2Co": "2Cor", "Gal": "Gal", "Eph": "Eph",
        "Php": "Phil", "Col": "Col", "1Th": "1Thess", "2Th": "2Thess",
        "1Ti": "1Tim", "2Ti": "2Tim", "Tit": "Titus", "Phm": "Phlm",
        "Heb": "Heb", "Jas": "Jas", "1Pe": "1Pet", "2Pe": "2Pet",
        "1Jn": "1John", "2Jn": "2John", "3Jn": "3John", "Jud": "Jude",
        "Rev": "Rev"}
REF = re.compile(r"^([1-3]?[A-Za-z]+) (\d+):(\d+)$")

# Books that address a reader directly rather than narrating. An imperative
# outside a quotation is a missed speech span in a narrative book and is
# perfectly normal here, so the detector has to know the difference.
ADDRESS = {"Ps", "Prov", "Eccl", "Song", "Rom", "1Cor", "2Cor", "Gal", "Eph",
           "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim", "Titus", "Phlm",
           "Heb", "Jas", "1Pet", "2Pet", "1John", "2John", "3John", "Jude",
           "Deut", "Lev"}


def eng(ref: str) -> str:
    b, c, v = ref.split(".")
    return f"{BOOK.get(b, b)} {c}:{v}"


def interrogative(w) -> bool:
    """From the tag. Hebrew segment class Ti; Greek G5101, not G5100."""
    if w[4].startswith("G"):
        return base(w[4]) == "G5101"
    return any(s.lstrip("H").startswith("Ti") for s in (w[5] or "").split("/"))


def _mood(w):
    """(kind, person-number) for a finite verb, or None if it opens no clause.

    Participles and infinitives are structures inside a clause rather than
    clauses of their own, so they get no speech act.
    """
    m = w[5] or ""
    if w[4].startswith("G"):
        mm = re.match(r"V-\d?\w\w(\w)", m)
        if not mm or mm.group(1) in ("P", "N"):
            return None
        return mm.group(1), m[-2:]
    v = _seg(m, "V")
    if not v or len(v) < 3 or v[2] in "arcs":
        return None
    return v[2], ""


def act_of(w, pre) -> str | None:
    """The speech act a finite verb opens, given the words before it.

    `pre` is the pre-field -- everything between the previous finite verb and
    this one -- which is where both languages put the negation, the condition
    and the interrogative that bind to this verb.
    """
    mp = _mood(w)
    if not mp:
        return None
    mood, person = mp
    lems = {base(x[4]) for x in pre}
    if w[4].startswith("G"):
        if mood == "M":
            return "command"
        if mood == "O":
            return "wish"
        if mood == "S":
            if person == "1P" and not (lems & SUBORD):
                return "command"                    # hortatory, "let us"
            if (lems & MH) and person[:1] == "2":
                return "command"                    # prohibition
            return None                             # subordinate
    elif mood in "vjh":
        return "command"
    if any(interrogative(x) for x in pre) or interrogative(w):
        return "question"
    return "assertion"


def status_of(w, pre, quoted) -> str:
    """How the clause is put forward, from the same pre-field."""
    lems = {base(x[4]) for x in pre}
    if lems & NEG:
        return "denied"
    if lems & COND:
        return "entertained"
    if any(interrogative(x) for x in pre):
        return "entertained"
    return "attributed" if quoted else "asserted"


def quoted_verses() -> set:
    """Every verse sitting inside a quotation span."""
    out = set()
    for s in spans():
        a, b = REF.match(s["from"]), REF.match(s["to"])
        if not a or not b or a.group(1) != b.group(1):
            continue
        if a.group(2) != b.group(2):
            continue
        for v in range(int(a.group(3)), int(b.group(3)) + 1):
            out.add(f"{a.group(1)} {a.group(2)}:{v}")
    return out


def analyse():
    """One record per finite verb: its act, its status, and where it is."""
    inside = quoted_verses()
    rows = corpus()
    by = collections.OrderedDict()
    for r in rows:
        by.setdefault(r[0], []).append(r)

    out = []
    for ref, ws in by.items():
        e = eng(ref)
        quoted = e in inside
        verbs = [i for i, w in enumerate(ws) if _mood(w)]
        prev = 0
        for i in verbs:
            pre = ws[prev:i]
            a = act_of(ws[i], pre)
            prev = i + 1
            if not a:
                continue
            out.append({"ref": e, "book": e.rsplit(" ", 1)[0].rsplit(" ", 1)[0]
                        if " " in e else e,
                        "gloss": ws[i][3].strip(), "lemma": ws[i][4],
                        "act": a,
                        "status": ("attributed" if a == "command" and quoted
                                   else status_of(ws[i], pre, quoted)),
                        "quoted": quoted})
    return out


def main() -> int:
    recs = analyse()
    bsb = _load("verses.bsb.jsonl")
    acts = collections.Counter((r["quoted"], r["act"]) for r in recs)
    status = collections.Counter(r["status"] for r in recs)

    print(f"finite verbs typed: {len(recs):,}")
    print()
    print("SPEECH ACT from mood -- closed class, no model, no judgement")
    print(f"{'':14}{'quoted speech':>16}{'narration':>13}")
    for a in ("assertion", "command", "question", "wish"):
        print(f"  {a:12}{acts[(True, a)]:>16,}{acts[(False, a)]:>13,}")
    print()
    print("ASSERTION STATUS -- scoped to the pre-field, not the verse")
    for k in ("asserted", "attributed", "entertained", "denied"):
        print(f"  {k:14}{status[k]:>9,}   {100*status[k]//max(len(recs),1)}%")

    print()
    print("worked examples:")
    seen = set()
    for r in recs:
        k = (r["act"], r["status"])
        if k in seen or r["ref"] not in bsb:
            continue
        seen.add(k)
        print(f"  {r['act']:10} {r['status']:12} {r['ref']:11} "
              f"{r['gloss'][:16]:18} {bsb[r['ref']][:66]}")

    print()
    miss = collections.Counter(r["book"] for r in recs
                               if r["act"] == "command" and not r["quoted"]
                               and r["book"] not in ADDRESS)
    print(f"commands in narration, outside an addressed book: "
          f"{sum(miss.values()):,}")
    print("  A narrator does not give orders, so each of these is speech the")
    print("  quotation marks failed to enclose.")
    print("   ", dict(miss.most_common(10)))

    if "--json" in sys.argv:
        p = ROOT / "out" / "acts.jsonl"
        with p.open("w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"\nwrote {p}  ({len(recs):,} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
