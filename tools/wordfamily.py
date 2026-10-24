"""Themes the stamps cannot name, reached by their original-language words.

2026-09-15: grace, faith, and love might be fast-tracked by
their original language words (Agape) and word families -- the three themes
`ontology/major-themes.json` marks `no_vocabulary`, and three of the most
agreed themes in Christianity. `tools/giftresponse.py` already had to fall back
to Greek lemmas for grace because the taxonomy cannot say the word.

## Why this is worth having next to the stamps

A word family is the INVERSE of a stamp, and that is the whole argument for it:

    stamp          a model's reading      broad recall, unverifiable
    word family    the word is there      narrow recall, anyone can check

The project's release gate: ask for the 50 most
prominent themes in the Bible based on evidence and get a defensible list. A theme resting only on a stamp rests on
one leg. A theme that a stamp finds AND a lemma family confirms rests on two
independent ones, and the second is checkable with a concordance.

## The recall problem, measured rather than admitted

The note: grace is trickier because it is often demonstrated without the word,
mercy being closely related. Exactly so, and it is the governing limit:
Luke 15 is the clearest teaching of grace in the Gospels and has no χάρις in
it; Genesis 22 is the New Testament's own example of faith (Heb 11:17) and has
no אָמַן.

So each family carries an `enacted` list -- passages broadly agreed to teach
the theme -- and this tool reports how many of them the lemmas MISS. Nothing is
asserted about which passages lack the word; the tool checks, which is the only
form in which that claim is worth anything.

## חֶסֶד belongs to three families and stays in all three

It is glossed "steadfast love" 130 times here and "kindness" 37. Hebrew does
not cut grace, love and faithfulness where English does, and forcing it into
one family would impose a distinction the text refuses. Shared lemmas are
reported, not resolved.

    python tools/wordfamily.py
    python tools/wordfamily.py --family grace --lemmas
    python tools/wordfamily.py --vs-stamps
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import sys
import unicodedata

# These tools print Hebrew and Greek. Windows consoles default to cp1252, which
# raises UnicodeEncodeError partway through a run -- after the useful output,
# so it reads as a crash rather than a console limitation.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
REG = ROOT / "ontology" / "word-families.json"
STAMPS = OUT / "stamps-leveled.jsonl"

NT = {"Matt", "Mark", "Luke", "John", "Acts", "Rom", "1Cor", "2Cor", "Gal",
      "Eph", "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim", "Titus",
      "Phlm", "Heb", "Jas", "1Pet", "2Pet", "1John", "2John", "3John",
      "Jude", "Rev"}

# The interlinear spells books differently from the stamp layer. This bit the
# app on 2026-09-14 (phrases.jsonl.gz keyed "JHN.1.1" against a title-case
# lookup, and every link silently missed), so the mapping is explicit and any
# code it does not cover is left alone rather than guessed at.
IL2STAMP = {"Mat": "Matt", "Mrk": "Mark", "Luk": "Luke", "Jhn": "John",
            "Act": "Acts", "1Co": "1Cor", "2Co": "2Cor", "Php": "Phil",
            "1Th": "1Thess", "2Th": "2Thess", "1Ti": "1Tim", "2Ti": "2Tim",
            "1Pe": "1Pet", "2Pe": "2Pet", "1Jn": "1John", "2Jn": "2John",
            "3Jn": "3John", "Tit": "Titus", "Phm": "Phlm", "Jud": "Jude",
            "Sng": "Song", "Psa": "Ps", "Jos": "Josh", "Jdg": "Judg",
            "1Sa": "1Sam", "2Sa": "2Sam", "1Ki": "1Kgs", "2Ki": "2Kgs",
            "1Ch": "1Chr", "2Ch": "2Chr", "Ezr": "Ezra", "Neh": "Neh",
            "Est": "Esth", "Pro": "Prov", "Ecc": "Eccl", "Isa": "Isa",
            "Jer": "Jer", "Lam": "Lam", "Ezk": "Ezek", "Dan": "Dan",
            "Hos": "Hos", "Jol": "Joel", "Amo": "Amos", "Oba": "Obad",
            "Jon": "Jonah", "Mic": "Mic", "Nam": "Nah", "Hab": "Hab",
            "Zep": "Zeph", "Hag": "Hag", "Zec": "Zech", "Mal": "Mal",
            "Gen": "Gen", "Exo": "Exod", "Lev": "Lev", "Num": "Num",
            "Deu": "Deut", "Rut": "Ruth", "Job": "Job", "Rom": "Rom",
            "Gal": "Gal", "Eph": "Eph", "Col": "Col", "Heb": "Heb",
            "Jas": "Jas", "Rev": "Rev"}


def norm(ref):
    b, c, v = ref.split(".")
    return f"{IL2STAMP.get(b, b)}.{int(c)}.{int(v)}"


def nfc(s):
    """Hebrew niqqud composes two ways and they are not the same string.

    Five lemmas written into ontology/word-families.json by hand looked
    identical to the corpus's and matched nothing -- מִשְׁפָּט (422 verses),
    צַדִּיק (206), שָׁפַט (202), יָשָׁר (119), בָּטַח (118). 1,067 occurrences
    invisible, and the tool reported it as a RECALL FLOOR finding: "the lemmas
    miss Mic 6:8", a verse whose second word is מִשְׁפָּט.

    That is the failure this project keeps meeting -- a silent lookup miss
    dressed as a measurement -- so both sides are composed here AND
    `validate()` refuses to run a family containing a lemma that matches
    nothing.
    """
    return unicodedata.normalize("NFC", s)


def validate(fams, seen):
    """A lemma that matches zero verses is an error in the register, never a
    fact about the corpus. Loud, and fatal."""
    bad = []
    for f in fams:
        for side in ("greek", "hebrew"):
            for l in f.get(side, {}):
                if nfc(l) not in seen:
                    bad.append(f"{f['id']}.{side}: {l!r}")
    if bad:
        raise SystemExit("register lemmas matching NOTHING in the corpus "
                         "(fix ontology/word-families.json):\n  "
                         + "\n  ".join(bad))


def load_families():
    d = json.loads(REG.read_text(encoding="utf-8"))
    return d["families"]


def load_interlinear():
    """-> {normalised ref: {lemmas}}"""
    out = {}
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if not d.get("ref"):
            continue
        out[norm(d["ref"])] = {nfc(w["l"]) for w in d["words"] if w.get("l")}
    return out


def load_sections():
    """-> ([section refs sorted], {ref: title}, {ref: {theme ids}})"""
    title, themes = {}, collections.defaultdict(set)
    for line in STAMPS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        title[d["ref"]] = d.get("title", "")
        if d.get("category") == "themes":
            themes[d["ref"]].add(d["id"])
    return sorted(title, key=vkey), title, themes


def vkey(r):
    b, c, v = r.split(".")
    return (b, int(c), int(v))


def container(secrefs):
    byb = collections.defaultdict(list)
    for r in secrefs:
        byb[r.split(".")[0]].append(vkey(r))
    for b in byb:
        byb[b].sort()
    def of(ref):
        b, c, v = vkey(ref)
        best = None
        for cand in byb.get(b, ()):
            if cand[1:] <= (c, v):
                best = cand
            else:
                break
        return ".".join(str(x) for x in best) if best else None
    return of


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--family")
    ap.add_argument("--lemmas", action="store_true",
                    help="per-lemma counts, so a bad member is visible")
    ap.add_argument("--vs-stamps", action="store_true",
                    help="what the family finds that the themes lane does not")
    a = ap.parse_args()

    fams = load_families()
    if a.family:
        fams = [f for f in fams if f["id"] == a.family]
        if not fams:
            raise SystemExit(f"no family {a.family!r}")

    il = load_interlinear()
    validate(fams, {l for ls in il.values() for l in ls})
    secrefs, title, themes = load_sections()
    of = container(secrefs)

    for f in fams:
        lem = {nfc(x) for x in set(f["greek"]) | set(f["hebrew"])}
        # A `pairs` family is one whose words are individually too common to
        # mean anything -- see the adoption entry. Both lemmas in one verse.
        pairs = [tuple(nfc(x) for x in p) for p in f.get("pairs", [])]
        verses = {r for r, ls in il.items()
                  if (ls & lem) or any(a in ls and b in ls for a, b in pairs)}
        secs = {s for s in (of(r) for r in verses) if s}
        books = {r.split(".")[0] for r in verses}
        nt = sum(1 for r in verses if r.split(".")[0] in NT)

        print(f"== {f['name']} ({f['id']})")
        print(f"   {len(verses):,} verses, {len(secs):,} of {len(secrefs):,} "
              f"sections ({100*len(secs)/len(secrefs):.0f}%), "
              f"{len(books)}/66 books")
        print(f"   {nt:,} NT verses, {len(verses)-nt:,} OT")

        # The recall floor. These are passages agreed to teach the theme; the
        # tool reports which ones the lemmas cannot see, rather than the
        # docstring asserting it.
        def sees(r):
            ls = il.get(r, set())
            return bool(ls & lem) or any(a in ls and b in ls for a, b in pairs)

        miss = [r for r in f.get("enacted", []) if not sees(r)]
        hit = [r for r in f.get("enacted", []) if sees(r)]
        gone = [r for r in f.get("enacted", []) if r not in il]
        if gone:
            # A ref the interlinear does not hold is a typo in the register,
            # not a miss. Counting it as a miss would inflate the recall floor.
            raise SystemExit(f"{f['id']}: refs not in the interlinear at all "
                             f"(register typo): {', '.join(gone)}")
        n = len(f.get("enacted", []))
        if n:
            print(f"   RECALL FLOOR: the lemmas miss {len(miss)}/{n} passages "
                  f"agreed to teach this")
            if miss:
                print(f"      missed  {', '.join(miss)}")
            if hit:
                print(f"      found   {', '.join(hit)}")
        for s in f.get("shares", []):
            print(f"   shares: {s}")

        if a.lemmas:
            print("   per lemma:")
            for l in sorted(lem, key=lambda x: -sum(
                    1 for ls in il.values() if x in ls)):
                c = sum(1 for ls in il.values() if l in ls)
                print(f"      {l:<14} {c:>5} verses")

        if a.vs_stamps:
            # Which theme stamps sit on the sections this family selects. A
            # family whose sections carry no distinctive theme is finding
            # something the stamps genuinely cannot say.
            hits = collections.Counter()
            for s in secs:
                hits.update(themes.get(s, ()))
            base = collections.Counter()
            for s in secrefs:
                base.update(themes.get(s, ()))
            print("   themes on the sections this family selects "
                  "(x = vs corpus):")
            for t, c in hits.most_common(6):
                share, bshare = c / len(secs), base[t] / len(secrefs)
                print(f"      {100*share:5.1f}%  {t:<22} x{share/bshare:4.2f}")
            bare = [s for s in secs if not themes.get(s)]
            print(f"      {len(bare)} selected sections carry no theme stamp "
                  f"at all")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
