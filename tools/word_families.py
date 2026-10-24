"""Word families: kin words, from the lexicon's own derivation notes (plan 5.10).

2026-10-01: there was no bridge between very similar concepts like content and
contentment (sufficiency/self-sufficiency); a bridge between Phl 4:11, 1 Tim
6:8 and 1 Tim 6:6 was wanted.
Those three verses use αὐτάρκης, αὐτάρκεια and ἀρκέω, and every layer of the
graph matched on the exact lemma, so nothing joined them. The Greek lexicon
the app already reads (Abbott-Smith, via STEPBible's lexicon.json) says where
each word comes from, in a parenthesis after the headword:

    αὐτάρκης   · (αὐτός, ἀρκέω)
    αὐτάρκεια  · (αὐτάρκης, which see)
    ἀρκετός    · (ἀρκέω)

That parenthesis is the only source read here. Nothing is guessed from
spelling.

THE TRAP, MEASURED BEFORE BUILDING (2026-10-01). Followed transitively, 888
words become one family through αὐτός. Restricted to content words and
joined into connected families, they still chain to 429 through compounds.
So a family is the NEAR links, never the connected component:

  - a **source** link: the lexicon derives one word from the other (one step);
  - a **lineage** link, two steps down one line: αὐτάρκεια from αὐτάρκης from
    ἀρκέω -- so αὐτάρκεια and ἀρκέω are kin;
  - a **sibling** link: two words the lexicon derives from the same source
    (ἀρκετός and αὐτάρκης, both from ἀρκέω).

And never the co-parent path: two words are NOT kin because one compound
draws on both (αἰσχροκερδής, "fond of shameful gain", comes from αἰσχρός and
κέρδος; shame and gain are not one family).

Only content words take part: nouns, verbs, adjectives and adverbs. A
pronoun, preposition, article, conjunction or particle is never a link
(αὐτάρκης is not kin to every αὐτ- compound), and a proper name is never in a
family. Hebrew is not built: its lexicon entries carry senses, not
derivation, and a root source has not been chosen.

    python tools/word_families.py            # build out/word-families.json
    python tools/word_families.py --check    # the first checks, from plan 5.10
"""
from __future__ import annotations

import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEX = ROOT / "data" / "raw" / "stepbible" / "lexicon.json"
OUT = ROOT / "out" / "word-families.json"

MAX_DEPTH = 1                                    # derivation steps; see build()
CONTENT = re.compile(r"^G:(N|V|A|ADV)")          # nouns, verbs, adjectives, adverbs
# a Greek word of three letters or more: "(in non-lit. π., ...)" is an
# abbreviation, not a source. And not an ENDING after a hyphen: κάρφος's
# headword reads "κάρφος, -εος (-ους) τό", and "(-ους)" was read as οὖς
# "ear" -- speck from ear (found 2026-10-01 in a random sample).
GREEK = re.compile(r"(?<![-Ͱ-Ͽἀ-῿])[Ͱ-Ͽἀ-῿]{3,}")
PAREN = re.compile(r"\(([^)]*)\)")


def derivation(d: str) -> str | None:
    """The source note: the first parenthesis holding a Greek word, within the
    headword's line or the segment right after it. Abbott-Smith writes it
    either way -- "αὐτάρκης, -ες · (αὐτός, ἀρκέω), [in LXX ..." and
    "βάπτισμα, -τος, τό (βαπτίζω), prop., ..." -- and only there; a later
    parenthesis is a citation or a grammatical note. The headword's own
    segment ends at the first "·"; the next segment is taken only if it
    starts with the parenthesis."""
    parts = (d or "").split("·")
    head = parts[0]
    nxt = parts[1].lstrip() if len(parts) > 1 else ""
    for chunk in (head, nxt if nxt.startswith("(") else ""):
        for m in PAREN.finditer(chunk):
            # A CROSS-REFERENCE IS NOT A SOURCE. 2026-10-01, reading
            # ἀγάπη's card: it put love and unfeeling in the same word
            # family. ἄστοργος reads "(στοργή, family affection, love of
            # kindred, see: ἀγάπη)": the source is στοργή, and ἀγάπη is only
            # where to compare. 261 of 2,693 notes hold a "see", "cf.", "opp."
            # or the like; the source always comes before it ("(αὐτάρκης,
            # which see)"), so the note is cut at the first one.
            src = XREF.split(m.group(1), maxsplit=1)[0]
            if GREEK.search(src):
                return src
    return None


def pointers(d: str) -> list[tuple[str, str]]:
    """The lexicon's cross-references, kept as their own kind of link, never
    as descent. On ἀγάπη's card showing ἄστοργος "unfeeling", finding its opposite was
    welcome. So "see: ἀγάπη"
    is recorded as the lexicon pointing there ("compare"), and "opp." as the
    lexicon's own "opposite" -- shown on the word card, labelled so, and not
    used to bridge verses. Read from the same derivation parenthesis only."""
    parts = (d or "").split("·")
    nxt = parts[1].lstrip() if len(parts) > 1 else ""
    out = []
    for chunk in (parts[0], nxt if nxt.startswith("(") else ""):
        for m in PAREN.finditer(chunk):
            body = m.group(1)
            for x in XREF.finditer(body):
                kind = "opposite" if x.group(0).lower().startswith("opp") else "compare"
                rest = XREF.split(body[x.end():], maxsplit=1)[0]
                out += [(w, kind) for w in GREEK.findall(rest)]
            if out:
                return out
    return out


# not "contr.": in Abbott-Smith it means CONTRACTED (a spelling), not
# contrary -- read as "opposite" it made πλόος "voyage" the opposite of
# ἁπλοῦς "sound" (2026-10-01)
XREF = re.compile(r"\b(?:see|cf|v|opp|syn|q\.\s*v)\b\.?:?", re.I)


def plain(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if not unicodedata.combining(c)).lower()


def own_entry(lemma: str, d: str) -> bool:
    """Is this definition about this word? The lexicon file has entries whose
    definition belongs to ANOTHER word -- μόδιος "bucket" carries μοιχαλίς's
    ("an adulteress"), ἀγράμματος carries ἀγραυλέω's -- and taking their
    derivation made "bucket" a child of "adulterer" (found 2026-10-01 in a
    random sample). So the definition must open on a Greek headword close to
    one of the entry's own forms ("γαμίσκω, γαμίζω" lists two). Definitions
    that open in English come from another lexicon whose parentheses are not
    derivations, and are not read either. Measured: 72 of the 2,460 content
    entries with a source fail one of these."""
    import difflib
    first = re.split(r"[\s,·(]+", (d or "").replace("-", "").strip(), maxsplit=1)[0]
    if not GREEK_ANY.search(first):
        return False
    h = plain(first)
    return max(difflib.SequenceMatcher(None, h, plain(f.strip())).ratio()
               for f in lemma.split(",")) >= 0.6


GREEK_ANY = re.compile(r"[Ͱ-Ͽἀ-῿]")


def key(code: str) -> str:
    """G0842 -> g842, the app's sense key."""
    return code[0].lower() + re.sub(r"^0+", "", code[1:])


def build() -> dict:
    raw = json.loads(LEX.read_text(encoding="utf-8"))
    greek = {c: v for c, v in raw.items()
             if c.startswith("G") and isinstance(v, list) and len(v) > 4}
    ok = lambda c: bool(CONTENT.match(greek[c][2] or "")) and not greek[c][0][:1].isupper()  # noqa: E731
    by_lemma = collections.defaultdict(set)
    for c, v in greek.items():
        if ok(c):
            by_lemma[plain(v[0])].add(c)

    parents = collections.defaultdict(set)          # word -> the words it comes from
    ambiguous = misaligned = 0
    akin = set()                                    # words whose note says "akin to"
    pointed = collections.defaultdict(dict)         # word -> {word: compare|opposite}
    for c, v in greek.items():
        if not ok(c):
            continue
        src = derivation(v[4])
        if not src:
            continue
        if not own_entry(v[0], v[4]):
            misaligned += 1
            continue
        if "akin" in src.lower():
            akin.add(c)
        for w in GREEK.findall(src):
            hits = by_lemma.get(plain(w), set()) - {c}
            if len(hits) > 1:
                # one spelling, several entries (homographs): no way to know
                # which is meant, so none is taken
                ambiguous += 1
                continue
            parents[c] |= hits
    # the lexicon's pointers ("see", "cf.", "opp."), from entries whose
    # definition is their own
    for c, v in greek.items():
        if not ok(c) or not own_entry(v[0], v[4]):
            continue
        for w, kind in pointers(v[4]):
            hits = by_lemma.get(plain(w), set()) - {c}
            if len(hits) == 1:
                pointed[c][next(iter(hits))] = kind
    children = collections.defaultdict(set)
    for c, ps in parents.items():
        for p in ps:
            children[p].add(c)

    kin = collections.defaultdict(dict)             # word -> {kin: how}
    def link(a, b, how):
        if a != b and b not in kin[a]:
            kin[a][b] = how
    # ONE LEVEL (MAX_DEPTH). 2026-10-01: set a max depth; if one level
    # does it for the content example, one level suffices. It does: Phil
    # 4:11's αὐτάρκης is one step from both 1 Tim 6:6's αὐτάρκεια and 1 Tim
    # 6:8's ἀρκέω. And the second level was where it went loose -- a random
    # twelve at two levels gave βελτίων "better" ~ ἀρτέμων "foresail" ("both
    # from ὄνος") and ὑποπόδιον "footstool" ~ ὀρθοποδέω "be upright" ("both
    # from πούς"), while every one-step pair read true (θάπτω ~ ταφή, διψάω ~
    # δίψα, ὄνειδος ~ ὀνειδίζω).
    for c, ps in parents.items():
        for p in ps:
            if c in akin:                           # "(akin to γνόφος)": kin, not descent
                link(c, p, "akin to"); link(p, c, "akin to")
                continue
            link(c, p, "from")                      # c comes from p
            link(p, c, "gives")                     # p gives c
            if MAX_DEPTH >= 2:
                for g in parents.get(p, ()):        # lineage: c from p from g
                    link(c, g, "from, through " + greek[p][0])
                    link(g, c, "gives, through " + greek[p][0])
                for s in children[p]:               # siblings through a shared source
                    link(c, s, "both from " + greek[p][0])
    # pointers both ways, and never over a derivation link already there
    for c, ps in pointed.items():
        for p, kind in ps.items():
            link(c, p, kind)
            link(p, c, kind)
    # ONLY THE RELATIONSHIPS ARE WRITTEN: Strong's key to Strong's key, and
    # how. STEPBible asks that their lexicon be distributed from their
    # repository, not ours (app2/server.py, where data/raw is read), so no
    # lemma, gloss or definition of theirs goes into this committed file; the
    # derivations themselves are Abbott-Smith's (1922, public domain), and
    # the app shows each word from the MACULA text it already holds.
    fam = {key(c): [[key(k), how] for k, how in
                    sorted(ks.items(), key=lambda kv: plain(greek[kv[0]][0]))]
           for c, ks in kin.items()}
    sizes = sorted((len(v) for v in fam.values()), reverse=True)
    return {"_about": "plan 5.10: kin words from the lexicon's derivation notes "
                      "(tools/word_families.py)",
            "_stats": {"greek_entries": len(greek), "with_a_source": len(parents),
                       "ambiguous_spellings_skipped": ambiguous,
                       "definitions_not_their_own_skipped": misaligned,
                       "words_with_kin": len(fam),
                       "largest_kin_lists": sizes[:10]},
            "families": fam}


def check(data: dict) -> int:
    """Plan 5.10's first checks."""
    fam = data["families"]
    kin = lambda a: {k for k, _how in fam.get(a, [])}  # noqa: E731
    # at one level, 1 Tim 6:6 and 6:8 meet THROUGH Phil 4:11's word, not
    # directly; the siblings below are the second level's errors, kept as
    # checks so a deeper setting cannot quietly bring them back
    want = [("g842", "g841", True, "αὐτάρκης ~ αὐτάρκεια (Phil 4:11 ~ 1 Tim 6:6)"),
            ("g842", "g714", True, "αὐτάρκης ~ ἀρκέω (Phil 4:11 ~ 1 Tim 6:8)"),
            ("g714", "g713", True, "ἀρκέω ~ ἀρκετός"),
            ("g907", "g908", True, "βαπτίζω ~ βάπτισμα"),
            ("g714", "g843", False, "ἀρκέω is not kin to αὐτοκατάκριτος"),
            ("g957", "g736", False, "βελτίων 'better' is not kin to ἀρτέμων 'foresail'"),
            ("g5286", "g3716", False, "ὑποπόδιον 'footstool' is not kin to ὀρθοποδέω"),
            ("g2595", "g3775", False, "κάρφος 'speck' is not from οὖς 'ear' (an ending, -ους)"),
            ("g3426", "g3432", False, "μόδιος 'bucket' is not from μοιχός (another word's definition)"),
            ("g2217", "g1105", True, "ζόφος ~ γνόφος, 'akin to' in the lexicon"),
    ]
    # ἄστοργος and ἀγάπη: linked, but as the lexicon's pointer, never as descent
    how = dict(fam.get("g794", [])).get("g26")
    print(f"  {'ok ' if how == 'compare' else 'BAD'} ἄστοργος ~ ἀγάπη as 'compare', not descent (got {how!r})")
    bad = int(how != "compare")
    for a, b, should, what in want:
        got = b in kin(a)
        print(f"  {'ok ' if got == should else 'BAD'} {what}")
        bad += got != should
    return bad


def main():
    data = build()
    s = data["_stats"]
    print(f"{s['greek_entries']:,} Greek entries; {s['with_a_source']:,} name a source word; "
          f"{s['ambiguous_spellings_skipped']} homograph sources skipped; "
          f"{s['words_with_kin']:,} words with kin; largest kin lists {s['largest_kin_lists']}")
    if "--check" in sys.argv:
        sys.exit(1 if check(data) else 0)
    OUT.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
