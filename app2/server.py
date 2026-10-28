"""Explorer for the structural graph — the reading surface IS the app.

2026-09-05, on the existing explorer: it had good auto-zoom and slider
capabilities, a nice tree structure and filtering, but was taking on complexity
and losing its elegance, and the reader modal felt second class.

That last clause is the design brief. Here the text is the primary surface and
everything else is secondary to it. Nothing about the graph appears until the
reader asks a question of the passage in front of them.

## What is deliberately different

**One density lever, not a wall of filters.** Plain / Marked / Structured. It
changes how much is shown, never what is reachable — every card is one tap away
in all three. Filters accumulate into complexity; a single lever cannot.

**Everything is a unit, and every unit is the same card.** A passage, a person, a
word sense, a pattern. That is what lets someone start from a passage and someone
else start from a topic without the app being two apps.

**A card stack, not panels.** Tapping pushes, back pops. It is the phone's own
idiom, so it needs no explaining, and it supports an arbitrarily deep dive
without a "research mode".

**Built for where the graph is going.** The unit endpoint takes a REF and returns
nodes plus edges; it does not know whether that ref names a verse, a sentence, a
speech or a scroll. When grouping above the sentence lands, it is a new query
against the same contract and not a rewrite.

    python app2/server.py            # port 8001

MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0.
"""
from __future__ import annotations

import collections
import gzip
from html import escape as _esc, unescape as html_unescape
import json
import math
import os
import re
import unicodedata
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, quote, unquote, urlencode, urlparse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
STATIC = Path(__file__).resolve().parent / "static"
# the library (the invite gate, bibleont.invites, among it) lives in src/
sys.path.insert(0, str(ROOT / "src"))

# THE HEBREW LEXICON ENTRY. STEP Bible publishes both brief lexicons under
# CC BY 4.0 (their repository's own terms, which the site credits), but the
# Hebrew file's field notes add that its "Meaning" column is based on the
# Online Bible's abridged Brown-Driver-Briggs, (c) Larry Pierce, and that
# "permission should be gained from Online Bible before these definitions are
# applied in any project". The Greek (Abbott-Smith, 1922) carries no such
# note. Found 2026-10-26 while showing the entries whole; the owner decides.
# False withholds the Hebrew entries from every card and page, nothing else.
# Off until the owner rules (2026-10-26): the cautious default while the
# permission the note asks for has not been sought.
HEBREW_DEFINITIONS_SHOWN = False

# THE WORKING PAGES: drawn from tools/ for building the graph, never for
# readers. /plan is the owner's plan; the others reload Python modules on every
# request (/suite measured 472 s of CPU for one GET, /tree 22 s). They exist
# only when the server is started with --dev (the local launch config does;
# the systemd unit does not) and are 404 otherwise. First keyed on the gate
# being on -- which would have brought them back at the public switch, when
# the gate goes off (the security review, 2026-10-01; docs/LAUNCH.md).
WORKING_PAGES = {"/suite", "/ontology", "/plan", "/passage", "/tree"}
DEV = "--dev" in sys.argv
# a query longer than this is refused before anything reads it (no route needs
# more; the review found a regex whose cost grows with a long echoed input)
MAX_QUERY = 1024
# the cookie that keeps a browser out of the activity counts (Handler._uncounted)
UNCOUNTED = "bo_uncounted"


class BadQuery(ValueError):
    """A malformed query -- "c=abc", a book that is not one: the reader's
    mistake, answered 400. Anything else that raises inside a route is the
    server's, answered 500 and logged (plan A.24). Until 2026-10-02 every
    ValueError, KeyError, IndexError and TypeError was a 400, and a shadowed
    variable in search answered "bad request" to "heaven" for most of a day
    with no traceback anywhere."""


def qint(q, key, default):
    """An integer query parameter, or BadQuery."""
    s = (q.get(key) or [str(default)])[0] or str(default)
    try:
        return int(s)
    except ValueError:
        raise BadQuery(key) from None


def qbook(d, q, default="Gen"):
    """A book code from the query that the text has, or BadQuery."""
    b = (q.get("b") or [default])[0]
    if b not in d["chapters"]:
        raise BadQuery("b")
    return b


def qchapter(d, q, b):
    """A chapter the book has, or BadQuery. 2026-10-21, before the source went
    public (the security seat, finding 3): /api/structure?c=99999 went through
    the 12-entry chapter cache and evicted real chapters for nothing."""
    c = qint(q, "c", 1)
    if c not in d["chapters"].get(b, ()):
        raise BadQuery("c")
    return c

# The reading text and the structural graph abbreviate books differently, which
# has silently returned zero twice in this project. The map is explicit and
# `_selfcheck` refuses to serve if it stops lining up.
TO_MACULA = {
    "Gen": "Gen", "Exod": "Exo", "Lev": "Lev", "Num": "Num", "Deut": "Deu",
    "Josh": "Jos", "Judg": "Jdg", "Ruth": "Rut", "1Sam": "1Sa", "2Sam": "2Sa",
    "1Kgs": "1Ki", "2Kgs": "2Ki", "1Chr": "1Ch", "2Chr": "2Ch", "Ezra": "Ezr",
    "Neh": "Neh", "Esth": "Est", "Job": "Job", "Ps": "Psa", "Prov": "Pro",
    "Eccl": "Ecc", "Song": "Sng", "Isa": "Isa", "Jer": "Jer", "Lam": "Lam",
    "Ezek": "Ezk", "Dan": "Dan", "Hos": "Hos", "Joel": "Jol", "Amos": "Amo",
    "Obad": "Oba", "Jonah": "Jon", "Mic": "Mic", "Nah": "Nam", "Hab": "Hab",
    "Zeph": "Zep", "Hag": "Hag", "Zech": "Zec", "Mal": "Mal",
    "Matt": "Mat", "Mark": "Mrk", "Luke": "Luk", "John": "Jhn", "Acts": "Act",
    "Rom": "Rom", "1Cor": "1Co", "2Cor": "2Co", "Gal": "Gal", "Eph": "Eph",
    "Phil": "Php", "Col": "Col", "1Thess": "1Th", "2Thess": "2Th",
    "1Tim": "1Ti", "2Tim": "2Ti", "Titus": "Tit", "Phlm": "Phm", "Heb": "Heb",
    "Jas": "Jas", "1Pet": "1Pe", "2Pet": "2Pe", "1John": "1Jn", "2John": "2Jn",
    "3John": "3Jn", "Jude": "Jud", "Rev": "Rev",
}
# The reverse map, for reading MACULA-keyed layers back into our book codes.
FROM_MACULA = {v: k for k, v in TO_MACULA.items()}
TITLE = {
    "Gen": "Genesis", "Exod": "Exodus", "Lev": "Leviticus", "Num": "Numbers",
    "Deut": "Deuteronomy", "Josh": "Joshua", "Judg": "Judges", "Ruth": "Ruth",
    "1Sam": "1 Samuel", "2Sam": "2 Samuel", "1Kgs": "1 Kings",
    "2Kgs": "2 Kings", "1Chr": "1 Chronicles", "2Chr": "2 Chronicles",
    "Ezra": "Ezra", "Neh": "Nehemiah", "Esth": "Esther", "Job": "Job",
    "Ps": "Psalms", "Prov": "Proverbs", "Eccl": "Ecclesiastes",
    "Song": "Song of Solomon", "Isa": "Isaiah", "Jer": "Jeremiah",
    "Lam": "Lamentations", "Ezek": "Ezekiel", "Dan": "Daniel", "Hos": "Hosea",
    "Joel": "Joel", "Amos": "Amos", "Obad": "Obadiah", "Jonah": "Jonah",
    "Mic": "Micah", "Nah": "Nahum", "Hab": "Habakkuk", "Zeph": "Zephaniah",
    "Hag": "Haggai", "Zech": "Zechariah", "Mal": "Malachi", "Matt": "Matthew",
    "Mark": "Mark", "Luke": "Luke", "John": "John", "Acts": "Acts",
    "Rom": "Romans", "1Cor": "1 Corinthians", "2Cor": "2 Corinthians",
    "Gal": "Galatians", "Eph": "Ephesians", "Phil": "Philippians",
    "Col": "Colossians", "1Thess": "1 Thessalonians",
    "2Thess": "2 Thessalonians", "1Tim": "1 Timothy", "2Tim": "2 Timothy",
    "Titus": "Titus", "Phlm": "Philemon", "Heb": "Hebrews", "Jas": "James",
    "1Pet": "1 Peter", "2Pet": "2 Peter", "1John": "1 John", "2John": "2 John",
    "3John": "3 John", "Jude": "Jude", "Rev": "Revelation",
}
ORDER = list(TITLE)
MACULA_BACK = {v: k for k, v in TO_MACULA.items()}

# Canon position per book, derived from TO_MACULA's own order so the two can
# never disagree. Used to sort pattern instance lists -- see _vkey.
_CANON = {b: i for i, b in enumerate(TO_MACULA)}

# Display title -> book code, so a citation written "Genesis 18:21" resolves as
# readily as "Gen.18.21". Built from TITLE rather than listed again.
TITLE_BACK = {v: k for k, v in TITLE.items()}

# Edge types that record where words sit rather than what is claimed. The audit
# behind this is not a preference: 75% of the legacy graph turned out to be this
# shape, so hiding it by default is an editorial position the measurement earns.
STRUCTURAL = {"member", "references", "apposition", "possessed_by"}

# Hebrew and Aramaic read right to left; the strip has to say so or the words
# appear in reverse and quietly misteach anyone reading along.
HEBREW_BOOKS = {TO_MACULA[b] for b in list(TO_MACULA)[:39]}

# Features whose partner is a function word say nothing about meaning -- they
# are an artefact of the edge vocabulary, and `subjof:to` rendered as "is what
# tos" on the card, which is worse than saying nothing.
NOISE_PARTNERS = {"to", "from", "for", "with", "in", "on", "at", "of", "and",
                  "the", "a", "as", "by", "be", "is", "was", "not", "all",
                  "which", "that", "this", "it", "him", "them", "you", "adjunct"}

_data: dict | None = None
_lock = threading.Lock()


# The base text is the KJV, which spells in British English. Readers type
# American. 2026-09-12, after a search for "Armor of God" found nothing
# (the issue was spelling: "the whole armour of God"):
#
# The overlay had it all along -- entity `the_whole_armour_of_god`, plus
# `armour` and `breastplate` and a whole relations file. *"whole armour"* found
# it and *"armor of god"* returned nothing, so a reader who spells the American
# way concludes the graph is empty where it is in fact thorough. That is the
# exact failure this project names: it looks authoritative where it is empty,
# and here it looked empty where it was full.
#
# Folded at the normaliser rather than patched per field, so every index built
# through `_slug` and `_wordkey` gets it at once.
#
# **An explicit list, not morphology.** The first version used blanket rules --
# `our -> or` and `ise -> ize` -- and they were measurably wrong on this corpus:
# `ours` became `ors`, and `praise`, `wise`, `rise`, `promise` and `paradise`
# all became nonsense. `praise` alone is everywhere in the Psalms. A rule broad
# enough to catch `baptise` is broad enough to break the commonest word in the
# book, so the pairs are written out.
_SPELL = {
    "armour": "armor", "armourbearer": "armorbearer", "honour": "honor",
    "honourable": "honorable", "saviour": "savior", "labour": "labor",
    "labourer": "labourer", "favour": "favor", "favoured": "favored",
    "neighbour": "neighbor", "neighbours": "neighbors", "colour": "color",
    "valour": "valor", "vigour": "vigor", "clamour": "clamor",
    "odour": "odor", "succour": "succor", "rigour": "rigor",
    "behaviour": "behavior", "endeavour": "endeavor", "splendour": "splendor",
    "judgement": "judgment", "judgements": "judgments",
    "counsellor": "counselor", "counsellors": "counselors",
    "travelled": "traveled", "worshipped": "worshiped",
    "marvellous": "marvelous", "grey": "gray", "plough": "plow",
    "centre": "center", "sceptre": "scepter", "theatre": "theater",
    "baptise": "baptize", "baptised": "baptized", "baptising": "baptizing",
    "realise": "realize", "recognise": "recognize",
}
_SPELL_RE = re.compile(r"\b(" + "|".join(sorted(_SPELL, key=len, reverse=True))
                       + r")\b")


def _fold(s):
    """One spelling for both sides of the Atlantic. Applied to index AND query."""
    return _SPELL_RE.sub(lambda m: _SPELL[m.group(1)], (s or "").lower())


def _slug(s):
    return re.sub(r"[^a-z0-9]", "", _fold(s))


def _wordkey(s):
    """A name as spaced lowercase words, so a match can respect word starts.

    `_slug` throws the spaces away, which is why searching *holy ghost* returned
    nothing: the entity is "the Holy Ghost", and "theholyghost" does not start
    with "holyghost". Keeping the spaces lets a search match the second word of
    a name without matching the middle of the first one.
    """
    return " ".join(re.findall(r"[a-z0-9]+", _fold(s)))


# A name is routinely introduced by an article that nobody types.
LEADING = ("the ", "a ", "an ")

# The KJV's vocabulary is not the reader's. Found 2026-09 typing *holy spirit*
# and *holy ghost* and getting nothing for either -- the first because the KJV
# says Ghost throughout, the second because of the article above.
#
# This is a translation fact, not an interpretation: these are the same word in
# the Greek, rendered differently by the KJV than by any modern version. Kept
# deliberately short and one-directional -- reader's word on the left, the
# corpus's word on the right -- because a synonym list is where a search quietly
# starts making claims the graph does not.
KJV_SAYS = {
    "holy spirit": "holy ghost",
    "love": "charity",
    "food": "meat",
    "conduct": "conversation",
    "living": "quick",
    "sea monster": "whale",
}


def load() -> dict:
    global _data
    with _lock:
        if _data is not None:
            return _data
        # BSB IS THE READING TEXT. Decided 2026-09-08: the BSB is the default
        # translation for relations, unless the reader can be given the choice;
        # this is not about English from 1700. And there is now a second, harder reason: the KJV file on disk
        # has lost the divine name — LORD appears 6 times against Lord 7,719,
        # because the small caps did not survive its conversion, so YHWH and
        # Adonai are one string in it. BSB keeps them apart (6,490 / 1,106).
        #
        # The KJV file is still loaded, as the fallback for any verse BSB does
        # not carry, and because verse NUMBERING is shared across all five
        # translations on disk — 0 differing verse sets over 1,189 chapters.
        print("  loading verses …", flush=True)
        verses, chapters = {}, collections.defaultdict(set)
        # Both are read and the SECOND overwrites the first, so the text a
        # reader actually sees is the last one loaded. `/api/about` used to
        # assert "King James Version (1769)" from a hardcoded string while the
        # screen showed BSB -- a false statement on the one page whose job is
        # to be true. It is now recorded here, where the fact is, rather than
        # written down somewhere that can drift away from it.
        translation = None
        NAMED = {"verses.jsonl": "King James Version (1769)",
                 "verses.bsb.jsonl": "Berean Standard Bible"}
        for name in ("verses.jsonl", "verses.bsb.jsonl"):
            p = ROOT / "data" / "bible" / name
            if not p.exists():
                continue
            translation = NAMED.get(name, name)
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                d = json.loads(line)
                if "b" not in d:
                    continue
                verses[(d["b"], d["c"], d["v"])] = d["t"]
                chapters[d["b"]].add(d["c"])

        print("  loading structure …", flush=True)
        # ONE COPY (2026-10-01, docs/LAUNCH.md): nodes and edges are read
        # through tools/structure.py's chapter blocks, not held here as
        # 1.4 million dicts beside them. Same answers: see NodesView.
        S = _structure()
        S.store()
        nodes, byref = NodesView(S), ByRefView(S)

        print("  loading senses …", flush=True)
        profiles = {}
        p = OUT / "sense-profiles.jsonl.gz"
        if p.exists():
            for line in gzip.open(p, "rt", encoding="utf-8"):
                d = json.loads(line)
                if d.get("key"):
                    profiles[d["key"]] = d

        contrasts = collections.defaultdict(list)
        p = OUT / "contrast-pairs.jsonl.gz"
        if p.exists():
            for line in gzip.open(p, "rt", encoding="utf-8"):
                d = json.loads(line)
                if d.get("a"):
                    contrasts[d["a"]].append(d)
                    contrasts[d["b"]].append(d)

        print("  loading original-language strip …", flush=True)
        orig = {}
        # The word-group tree. Both halves of the two-column reader need it:
        # nested boxes on the right, and the maximal non-predicating phrases
        # that the left column hyperlinks. See tools/phrases.py.
        # `ptree`, not `phrases`: a module-level phrases() already exists for
        # word senses, and a local of the same name shadows it for anyone
        # reading load() later.
        print("  loading phrase trees …", flush=True)
        # HELD COMPRESSED, PARSED WHEN ITS CHAPTER OPENS (2026-10-01,
        # docs/LAUNCH.md): every verse's tree parsed at start was the bulk of
        # a 688 MB step, and only api_chapter reads them, a chapter at a time.
        # Each verse's line is kept zlib-compressed and read by _ptree().
        import zlib
        ptree = {}
        pf = OUT / "phrases.jsonl.gz"
        if pf.exists():
            for line in gzip.open(pf, "rt", encoding="utf-8"):
                m = re.search(r'"ref":\s*"([^"]+)"', line)
                if m:
                    # phrases.jsonl.gz keys on MACULA's own uppercase codes
                    # ("JHN.1.1") and the app uses title case ("Jhn.1.1"), so
                    # the lookup silently missed every verse.
                    ptree[m.group(1).upper()] = zlib.compress(line.encode("utf-8"))

        # Higher-level patterns, and which sections carry them. A section is
        # just the outermost BOX (2026-09-14: boxes are nested and
        # sections are a big box) -- so its chips hang on the same structure
        # as any inner box's will once phrase-level mining exists.
        # How rare each stamp is, corpus-wide. A chip is worth showing when
        # the thing it names is UNCOMMON -- `armor_of_god` in 18 sections of
        # 3,078 is a pattern a reader recognises; `people_of_god` in 2,000 is
        # not. 2026-09-15, on the co-occurrence chips: promising, but not
        # matching expectations. They did not: the chips were statistical PAIRS,
        # and what a reader pictures -- Armor of God, chiasm, the exodus arc -- are
        # NAMED things the stamps already carry.
        print("  ranking stamps by rarity …", flush=True)
        stamp_df = collections.Counter()
        stamp_by_sec = collections.defaultdict(list)
        stamp_secs = collections.defaultdict(list)
        sectitle = {}
        sl = OUT / "stamps-leveled.jsonl"
        # ONCE PER SECTION AND TAG. The file holds 3,210 repeated (section,
        # tag) rows, so a tag's page listed sections twice -- messianic
        # prophecy 374 rows of 334 (M-D12, the 2026-10-02 evaluation) -- and
        # every count built on them was inflated the same way
        seen_st = set()
        # and the readings a review found wrong (ontology/stamp-verdicts.jsonl)
        dropped_st = {(r["ref"], r["id"]) for r in _rows(ROOT / "ontology" / "stamp-verdicts.jsonl")
                      if r.get("verdict") == "drop"}
        if sl.exists():
            for line in sl.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                if (r["ref"], r["id"]) in seen_st or (r["ref"], r["id"]) in dropped_st:
                    continue
                # THE THEME STAMPS ARE RETIRED (2026-10-08): the existing tags
                # were not trusted, and "Retire from view" was chosen. The
                # themes now tag the text from their own tables (_theme_tags);
                # these 17,291 stamps named 21 themes of the September
                # taxonomy, five of which are not themes now. Kept on disk.
                if r.get("category") == "themes":
                    continue
                seen_st.add((r["ref"], r["id"]))
                stamp_df[r["id"]] += 1
                stamp_by_sec[r["ref"]].append(r)
                # Reverse index: which sections carry a given stamp. A chip is
                # only worth clicking if it can answer "where else", and
                # /api/pattern could not answer it -- it resolved ids against
                # `hpat` alone, so every `stamp:` chip came back {found:False}.
                stamp_secs[r["id"]].append(r["ref"])
                # `sectitle` was read at the instance list of the higher-pattern
                # branch and never built anywhere, so every instance there has
                # shown an empty title. The stamp rows carry it.
                if r.get("title"):
                    sectitle.setdefault(r["ref"], r["title"])

        print("  loading patterns (graph) …", flush=True)
        hpat, hpat_by_sec = {}, collections.defaultdict(list)
        hpat_inst = collections.defaultdict(list)
        pn = OUT / "pattern-nodes.jsonl.gz"
        if pn.exists():
            for line in gzip.open(pn, "rt", encoding="utf-8"):
                r = json.loads(line)
                if r.get("id"):
                    hpat[r["id"]] = r
            pe = OUT / "pattern-edges.jsonl.gz"
            if pe.exists():
                for line in gzip.open(pe, "rt", encoding="utf-8"):
                    r = json.loads(line)
                    if r.get("type") == "instance_of" and r.get("src", "").startswith("sec:"):
                        hpat_by_sec[r["src"][4:]].append(
                            {"id": r["dst"], "fill": r.get("fill")})
                        # and the other way: a pattern needs its instances, or
                        # "where else does this happen" has no answer
                        hpat_inst[r["dst"]].append(
                            {"ref": r["src"][4:], "fill": r.get("fill")})

        p = OUT / "interlinear.jsonl.gz"
        if p.exists():
            for line in gzip.open(p, "rt", encoding="utf-8"):
                d = json.loads(line)
                if d.get("ref"):
                    orig[d["ref"]] = d["words"]

        # Definitions and transliteration. The full lexicon lives under
        # data/raw/, which is gitignored because STEPBible asks that their
        # dataset be distributed from their repository rather than ours; the
        # committed extract holds only the codes the legacy graph needed. Read
        # from disk, never redistributed -- the same standing as MACULA's XML.
        print("  loading lexicon …", flush=True)
        lex = {}
        # THE ENTRY WHOLE, from STEP's own files where this machine holds them
        # (the live server fetches them: tools/fetch_lexicon.py), else from the
        # built lexicon.json, else from the committed extract. The built file
        # was cut at 340 characters (2026-10-26: "1a5b)" ended the entry of
        # אהב) and kept the last row of each number, which headed God
        # "(Gibeath)-elohim"; src/bibleont/lemma.py now reads the main row,
        # whole, with no KJV rendering in it. The two older sources get the same
        # cut for the renderings, so none can come in by a stale file.
        from bibleont import lemma as _lemma
        sources = []
        try:
            sources.append(_lemma.tbes_entries())
        except OSError:
            pass
        for cand in (ROOT / "data" / "raw" / "stepbible" / "lexicon.json",
                     ROOT / "ontology" / "lexicon.json"):
            if cand.exists():
                sources.append(json.loads(cand.read_text(encoding="utf-8")))
        for raw in sources:
            if not raw:
                continue
            # a number STEP holds only as letter variants (H6213a, H6213b)
            # gets their entries together, each under its own sense
            for code, v in list(raw.items()) + list(_lemma.variant_entries(raw).items()):
                if not isinstance(v, list) or len(v) < 4:
                    continue
                k = code[0].lower() + re.sub(r"^0+", "", code[1:])
                defn = _lemma.scrub_translation(v[4] if len(v) > 4 else "")
                lex.setdefault(k, {"word": v[0], "translit": v[1],
                                   "pos": v[2],
                                   # the word's main sense, never a
                                   # participle's ("to love", not "friend")
                                   "gloss": _lemma.headline_gloss(v[3]),
                                   "gloss_full": v[3],
                                   "definition": "" if (
                                       k[0] == "h" and not HEBREW_DEFINITIONS_SHOWN)
                                   else defn})
            break

        # Strong's key -> the verses it occurs in, so a word can be shown IN A
        # PHRASE rather than only as a list of properties.
        # (from the chapter blocks' word rows, in the node file's order -- the
        # order the dict of every node was walked in; a node without a
        # Strong's number has no sense key, so the rows omit nothing used)
        occ = collections.defaultdict(list)
        words_rows = S.words()
        si = sys.intern
        for lang, strong, ref, text, _lemma in words_rows:
            k = sense_key(lang, strong)
            if k and text:
                occ[k].append((si(ref) if ref else ref, text))

        mp = OUT / "lemma-meta.json"
        lmeta = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}

        # HOW THE TEXT ON SCREEN RENDERS EACH WORD, which is not the same as
        # how MACULA glosses it. A reader met "the prophecy of one who hears" at
        # Numbers 24:4 while the card said "declares" and the interlinear said
        # "oracle" -- three Englishes, one word, nothing connecting them.
        bwp = OUT / "bsb-words.json"
        bsbw = (json.loads(bwp.read_text(encoding="utf-8")).get("words") or {}
                ) if bwp.exists() else {}

        # The same word in the Bible's other languages. Greek is an ALIGNMENT
        # from MACULA's Septuagint column; Aramaic is a COGNATE observed in the
        # Aramaic passages themselves. Different kinds of claim, kept apart.
        # The Berean editors' own tagging of their English, so a pattern can
        # mark the translation as well as the original without guessing which
        # word renders which. See tools/bsbalign.py for what it is and is not.
        align = {}
        ap_ = OUT / "bsb-align.jsonl.gz"
        if ap_.exists():
            for line in gzip.open(ap_, "rt", encoding="utf-8"):
                r = json.loads(line)
                if r.get("ref"):
                    align[r["ref"]] = r

        # THE TWO SOURCES DO NOT NUMBER THE VERSES THE SAME WAY. 2026-09-21,
        # reading what the app printed under Exodus 8:6, the BSB verse bore no
        # visible relation to it. MACULA's
        # Exo.8.6 is "there is no one like the LORD our God"; the Berean text
        # carries that at 8:10, because Hebrew Exodus 8 runs four verses ahead
        # of the English. 142 chapters differ, 983 verses move. Anything that
        # takes a graph reference and asks the Berean text for "that verse"
        # has to come through here. See tools/versify.py.
        vmap = {}
        vp = OUT / "versemap.json"
        if vp.exists():
            vmap = (json.loads(vp.read_text(encoding="utf-8"))
                    .get("moved") or {})

        eqp = OUT / "word-equivalents.json"
        eqs = json.loads(eqp.read_text(encoding="utf-8")) if eqp.exists() else {}

        print("  loading sentences …", flush=True)
        sents, sent_by_verse = {}, {}
        sp = OUT / "sentences.jsonl.gz"
        if sp.exists():
            for line in gzip.open(sp, "rt", encoding="utf-8"):
                r = json.loads(line)
                if r.get("id"):
                    sents[r["id"]] = r
        svp = OUT / "sentences-by-verse.json"
        if svp.exists():
            sent_by_verse = json.loads(svp.read_text(encoding="utf-8"))

        # Where a chapter divides, over the whole canon: 8,694 seams across all
        # 66 books, each carrying WHO SAID SO. `derived` means the text marks it
        # (a quotation closing, a temporal connective, an anaphora or acrostic
        # run beginning); `heading` is a Berean section title, which was ruled
        # always to outrank our own reading; `bsb` is its paragraph break taken
        # because our signals were unclear -- the rule of 2026-09-09: if
        # signals are really unclear, default to the BSB. Showing the provenance is
        # the point: a reader can see which divisions the text earned and which
        # were borrowed.
        # ATTACHMENT: which verse builds on which. `direction: backward` means
        # this verse's connective points at what precedes it, and chaining
        # those is what reproduced the hand-drawn ((((6-7)-8)-9)-10) for Psalm 92
        # exactly. It is the relation the design has described all along --
        # "what modifies or builds on what" -- and until now nothing read it.
        print("  loading attachment …", flush=True)
        attach = {}
        ap_ = OUT / "sentence-function.jsonl.gz"
        if ap_.exists():
            for line in gzip.open(ap_, "rt", encoding="utf-8"):
                r = json.loads(line)
                ref = r.get("ref")
                if ref and ref not in attach and not any(
                        k.startswith("_") for k in r):
                    attach[ref] = {"dir": r.get("direction"),
                                   "rel": r.get("relation"),
                                   "sub": r.get("subtype")}

        print("  loading seams …", flush=True)
        # THE SEAMS FILE MIXES TWO NUMBERINGS, found 2026-09-25: the Berean's
        # headings and paragraph breaks (by 'heading' / 'bsb') are keyed in the
        # BERean numbering — "The Third Plague: Gnats" under Exo.8.16 — while
        # the seams derived from the Hebrew (by 'derived') are keyed in
        # MACULA's — Exo.8.12's speech-close is where BSB 8:16 begins. Held in
        # one dict they could overwrite each other, and any one lookup was
        # wrong for one kind: looked up by the Hebrew verse, every heading in
        # a renumbered chapter landed late. Kept apart, and each looked up by
        # its own numbering.
        seams, seams_heb = {}, {}
        sm = OUT / "seams.jsonl.gz"
        if sm.exists():
            for line in gzip.open(sm, "rt", encoding="utf-8"):
                r = json.loads(line)
                if r.get("ref") and not any(k.startswith("_") for k in r):
                    by = r.get("by")
                    (seams_heb if by == "derived" else seams)[r["ref"]] = r

        # Where each BSB section starts, per book. The reader loads whole
        # sections rather than whole chapters, because 36% of sections run
        # past their chapter's end and a chapter-bounded reader cuts them.
        print("  loading section starts …", flush=True)
        secstart = collections.defaultdict(list)
        st = OUT / "structure.jsonl.gz"
        if st.exists():
            for line in gzip.open(st, "rt", encoding="utf-8"):
                if not line.strip():
                    continue
                r = json.loads(line)
                if any(k.startswith("_") for k in r):
                    continue
                if r.get("level") != "section" or "engbsb" not in (r.get("by") or []):
                    continue
                mb, mc, mv = r["ref"].split(".")
                secstart[FROM_MACULA.get(mb, mb)].append((int(mc), int(mv)))
        for k in secstart:
            secstart[k].sort()

        # The legacy graph's relations: 15,023 of them, reasoned out verse by
        # verse and typed against a 116-type taxonomy. The structural graph
        # says what a sentence does; this says what a PERSON is to another
        # person across the whole corpus, and an entity card is poor without it.
        print("  loading legacy relations …", flush=True)
        rels = collections.defaultdict(list)
        import glob as _glob
        for f in sorted(_glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl"))):
            for line in Path(f).read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                # `held`: a statement inside speech whose speaker cannot be said
                # (plan 2.19), or whose verb's form does not say it happened.
                # Never shown, so never shown as the narrator's or as a fact.
                # `described`: a command, promise, prediction or wish (plan
                # 2.19a): exported as described, but not drawn as a link on the
                # cards, which would read as a fact, until the cards can say
                # "commanded" or "promised"
                if r.get("held") or r.get("described"):
                    continue
                # `claimed_by`: the relation is a speaker's claim, not the
                # narrator's (P-71: Abraham's fear "they will kill me", Gen
                # 12:12, was shown as "was killed by the Egyptians")
                # `map`: the edge comes from the major-theme map, a reading
                # drawn over the text, and a card says so (the 2026-10-02
                # evaluation: "Christ as Fulfillment of the Law" sat on
                # Jesus's card as if it were the graph's own fact)
                tmap = r.get("source") == "copilot-theme-map"
                # `pairs`: a story echo's words set side by side, later then
                # earlier, so the card shows them ("the fact that it was 40
                # days vs 40 years needs to be obvious", 2026-10-03)
                pairs = {"pairs": r["pairs"]} if r.get("pairs") else {}
                # `reading`: who holds a link the text does not state (Rahab of
                # Matt 1:5 and of Jericho, plan 5.12); the card says so
                if r.get("reading"):
                    pairs["reading"] = r["reading"]
                # A STATEMENT carries its own verb as its label (plan 2.19:
                # "loved", John 3:16), and the other end its inverse ("loved
                # by"); a type's one label cannot say what each verb says
                own = ({"label_out": r["label"], "label_in": r.get("inverse_label")}
                       if r.get("type") == "states" and r.get("label") else {})
                pairs = {**pairs, **own}
                rels[r["src"]].append({"dir": "out", "type": r["type"],
                                       "other": r["dst"], "refs": r.get("refs", []),
                                       "note": r.get("note"),
                                       "certainty": r.get("certainty"),
                                       "claimed_by": r.get("claimed_by"), "map": tmap, **pairs})
                rels[r["dst"]].append({"dir": "in", "type": r["type"],
                                       "other": r["src"], "refs": r.get("refs", []),
                                       "note": r.get("note"),
                                       "certainty": r.get("certainty"),
                                       "claimed_by": r.get("claimed_by"), "map": tmap, **pairs})

        # the taxonomy, so relations group under headings a reader recognises
        cats = {}
        sch = ROOT / "ontology" / "schema" / "relationship_types.yaml"
        if sch.exists():
            try:
                import yaml
                y = yaml.safe_load(sch.read_text(encoding="utf-8"))
                catlabel = {k: (v or {}).get("label", k)
                            for k, v in (y.get("categories") or {}).items()}
                for name, spec in (y.get("types") or {}).items():
                    if isinstance(spec, dict):
                        cats[name] = {
                            "category": spec.get("category") or "other",
                            "label": spec.get("label") or name,
                            "inverse": spec.get("inverse") or name,
                            # the label when the target is not an image
                            # (draws_on; _rel_label)
                            "plain_label": spec.get("plain_label"),
                            "plain_inverse": spec.get("plain_inverse"),
                            # a category with no label falls back to its own
                            # key, which arrived lowercase next to properly
                            # titled ones -- tidy it rather than ship the seam
                            "catlabel": (catlabel.get(spec.get("category"))
                                         or (spec.get("category") or "other")
                                         .replace("_", " ").capitalize()),
                            # the Knowledge Graph Navigator's tie strength
                            # (api_graph): how much of a relationship the
                            # type accounts for, and whether it has a
                            # direction to draw
                            "weight": spec.get("weight"),
                            "symmetric": bool(spec.get("symmetric")),
                        }
            except Exception as exc:                             # noqa: BLE001
                # Said out loud: a silent fallback here filed every relation
                # on every card under "Other" and nothing noticed.
                print(f"  relation categories not loaded: {exc!r}", flush=True)
                cats = {}

        # The name -> Strong's map, so a PERSON carries the original-language
        # word behind their name. Losing this was a real regression against the
        # legacy app: a person is a Hebrew or Greek word before an English one.
        namemap = {}
        nmp = OUT / "name-strongs.json"
        if nmp.exists():
            namemap = (json.loads(nmp.read_text(encoding="utf-8"))
                       .get("map") or {})

        print("  loading patterns …", flush=True)
        patterns, pat_by_ref = {}, {}
        pp = OUT / "patterns.jsonl.gz"
        if pp.exists():
            for line in gzip.open(pp, "rt", encoding="utf-8"):
                r = json.loads(line)
                if r.get("key"):
                    patterns[r["key"]] = r
        pr = OUT / "patterns-by-ref.json"
        if pr.exists():
            pat_by_ref = json.loads(pr.read_text(encoding="utf-8"))
        mined = _load_mined()
        print("  loading echoes …", flush=True)
        echoes = _load_echoes()
        aligned = _load_aligned()

        print("  loading entities …", flush=True)
        ents, byname, renamed = {}, collections.defaultdict(list), {}
        # EVERY FILE in the entities directory, as bibleont.schema.load_entities
        # reads it: the major-theme nodes (2026-09-29) live in theme-map.jsonl
        # beside the shared store, so the store is never rewritten to add them
        for f in sorted((ROOT / "ontology" / "entities").glob("*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                d = json.loads(line)
                ents[d["id"]] = d
                byname[_slug(d["name"])].append(d["id"])
                # An id renamed out of the KJV's wording (A.22, 2026-10-02)
                # keeps its old one, so a link shared before still lands.
                if d.get("id_kjv"):
                    renamed[d["id_kjv"]] = d["id"]
                # renamed twice (the KJV-phrase addresses, 2026-10-21): every
                # earlier address still lands
                for old in d.get("former_ids_kjv") or []:
                    renamed.setdefault(old, d["id"])
                # and a record merged into this one (the duplicate merges,
                # 2026-10-02) opens this one
                for old in d.get("merged_from") or []:
                    renamed.setdefault(old, d["id"])

        # Precomputed once so a word card is a lookup and a dot product, never
        # a model call. This is what keeps a deep dive free to serve.
        print("  indexing senses …", flush=True)
        vecs, norms, lemmas = {}, {}, {}
        for k, p in profiles.items():
            v = {f["feature"]: f["weight"] for f in p.get("top", [])}
            vecs[k] = v
            norms[k] = (sum(x * x for x in v.values()) ** 0.5) or 1.0
        # how often each lemma stands under a number, its own uses (no letter
        # code) apart: the card is headed by the commonest (headwords())
        own_n, all_n = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
        for lang, strong, _ref, _text, lemma in words_rows:
            k = sense_key(lang, strong)
            if k and lemma and k not in lemmas:
                lemmas[k] = lemma
            if k and lemma:
                all_n[k][lemma] += 1
                if not strong[-1:].isalpha():
                    own_n[k][lemma] += 1
        del words_rows
        common = {k: (own_n.get(k) or c).most_common(1)[0][0] for k, c in all_n.items()}
        del own_n, all_n
        heads = headwords(common, lemmas, lex)

        # What this word DOES, and what it is a kind of doing. Both layers were
        # built 2026-09-07 and neither was reachable by a reader: 26,018
        # narrative events read off the wayyiqtol and the aorist indicative, and
        # 113 verb classes clustered from context plus MACULA's gloss.
        #
        # They are keyed by the ORIGINAL lemma form and the app is keyed by
        # Strong's, so the join goes through the node layer -- the same bridge
        # `lemmas` just built, inverted. Three separate joins failed silently
        # today for want of exactly this, so it is written once and shared.
        print("  loading events …", flush=True)
        key_of_lemma = {v: k for k, v in lemmas.items()}
        events = collections.defaultdict(list)
        # The TRUE total, kept separately. The index below is keyed by Strong's
        # and the bridge from the original lemma loses 9% -- 23,653 of 26,018 --
        # so reporting the index size on the About page would have put a
        # silently low number on the one page whose job is to be trustworthy.
        events_total = 0
        ev_path = OUT / "events.jsonl.gz"
        if ev_path.exists():
            for line in gzip.open(ev_path, "rt", encoding="utf-8"):
                if not line.strip():
                    continue
                e = json.loads(line)
                if any(x.startswith("_") for x in e):
                    continue
                events_total += 1
                k = key_of_lemma.get(e.get("lemma"))
                if k:
                    events[k].append(e)

        vclass, classes = {}, {}
        vc_path = OUT / "verb-classes.json"
        if vc_path.exists():
            raw = json.loads(vc_path.read_text(encoding="utf-8"))
            for c in raw.get("clusters", []):
                classes[c["id"]] = c
                for lem in c["verbs"]:
                    k = key_of_lemma.get(lem)
                    if k:
                        vclass[k] = c["id"]

        # Entities that answer to the same name. `jesus` is a PERSON with 419
        # relations and `jesus_christ` is a BEING with 7, and each lists the
        # other in its `aka` -- a distinction the graph makes and never shows.
        # Indexed once so a card can say "also recorded separately as", without
        # merging anything: read the corpus without harmonising it.
        # ONE EVENT, RECORDED TWICE (2026-10-04: searching "temptation"
        # found two "temptation in the wilderness" cards before "Jesus'
        # temptation"; consolidation and aliases were asked for). ontology/aliases.jsonl names an older record that is an
        # event-layer event recorded again. At load, and only here: its name
        # becomes the event's "also called", its links show on the event's
        # card, links to it point to the event, and its own card and address
        # send the reader on (card_page, 301). The record itself is untouched,
        # so deleting the line undoes it.
        alias_of = {}
        for a in _rows(ROOT / "ontology" / "aliases.jsonl"):
            old, new = a.get("id"), a.get("alias_of")
            if old in ents and new in ents and old != new:
                alias_of[old] = new
        for old, new in alias_of.items():
            ents[old] = {**ents[old], "alias_of": new}
            # its name and its own other names become the survivor's "also
            # called" (Aeneas: the merged record alone held the Berean's
            # spelling, as an aka -- 2026-10-04)
            have = {_slug(x) for x in [ents[new]["name"]] + list(ents[new].get("aka") or [])}
            more = [x for x in [ents[old]["name"]] + list(ents[old].get("aka") or [])
                    if x and _slug(x) not in have and not have.add(_slug(x))]
            if more:
                ents[new] = {**ents[new], "aka": list(ents[new].get("aka") or []) + more}
            # and its verses (2026-10-14, the consolidation review: "a merge
            # keeps the record named, carries the other's names and verses"):
            # the Luke 4:33 telling of the man with an unclean spirit was on
            # the record merged away
            refs = list(ents[new].get("refs") or [])
            extra = [r for r in (ents[old].get("refs") or []) if r not in refs]
            if extra:
                ents[new] = {**ents[new], "refs": refs + extra}
            # its hidden old-translation name stays searchable, never shown
            # ("charity" finds love; A.22 keeps KJV words out of sight)
            if ents[old].get("name_kjv"):
                ents[new] = {**ents[new], "aka_kjv": list(ents[new].get("aka_kjv") or [])
                             + [ents[old]["name_kjv"]]}
            rels[new].extend(dict(r) for r in rels.get(old, []) if r["other"] != new)
        if alias_of:
            for lst in rels.values():
                for r in lst:
                    if r["other"] in alias_of:
                        r["other"] = alias_of[r["other"]]
            # two duplicates that linked to each other would leave the
            # survivor linked to itself: those links go
            for owner in {v for v in alias_of.values()}:
                rels[owner] = [r for r in rels.get(owner, []) if r["other"] != owner]
        # A RENAMED THEME IS FOUND BY ITS NEW NAME (plan 7.6b): the shown name
        # is rewritten at the door (_theme_renames), so search must know it
        # too -- "prophets and prophecy" found nothing until this
        for _tid, _n in (_theme_homes().get("names") or {}).items():
            _te = ents.get("theme_" + _tid)
            if _te is not None:
                _te["aka"] = list(_te.get("aka") or []) + [_n["name"]]
        alias_ix = collections.defaultdict(set)
        for _e in ents.values():
            if _e.get("alias_of"):
                continue
            for nm in [_e["name"]] + list(_e.get("aka") or []):
                if nm:
                    alias_ix[_slug(nm)].add(_e["id"])

        # Gloss -> the words the text actually uses. `namemap` only resolves
        # proper names, so it says nothing about "God" -- and a dropdown of ten
        # rows all reading "God" is a list of unlabelled doors. One row was
        # elohim and the next eloh, so the Hebrew is shown in the dropdown.
        # Commonest use first, so the
        # word offered is the one the reader is most likely to have met.
        gloss_ix = collections.defaultdict(list)
        for k, p in profiles.items():
            g = _slug(p.get("gloss"))
            if g:
                gloss_ix[g].append((-(p.get("observations") or 0), k))
        for g in gloss_ix:
            gloss_ix[g].sort()

        # ---- the derived layers, keyed by MACULA ref
        #
        # 2026-09-12: the app was no longer delivering the whole message.
        # It was loading ten layers. Everything derived this
        # year -- who speaks, what is compared to what, what stands as an image
        # for what, family relations, places, and which verbs are NEGATED --
        # existed on disk and was invisible here. A reader cannot be shown a
        # graph the reader's own app does not read.
        #
        # Each is attached to the verse, because that is where a reader meets
        # it. Nothing is merged: every entry says which layer it came from, so
        # a wrong one can be traced to its tool rather than to "the app".
        print("  loading the derived layers …", flush=True)
        layers = collections.defaultdict(dict)

        def _lay(name, key, fn):
            p = OUT / name
            if not p.exists():
                return 0
            n = 0
            try:
                for line in gzip.open(p, "rt", encoding="utf-8"):
                    if not line.strip():
                        continue
                    r = json.loads(line)
                    if not isinstance(r, dict) or any(
                            k.startswith("_") for k in r):
                        continue
                    ref = r.get("ref")
                    if not ref:
                        continue
                    val = fn(r)
                    if val:
                        layers[ref].setdefault(key, []).append(val)
                        n += 1
            except (OSError, json.JSONDecodeError):
                return n
            return n

        counts = {
            "speakers": _lay("speakers.jsonl.gz", "speaks", lambda r: (
                {"who": r.get("speaker"), "act": r.get("act"),
                 "divine": r.get("divine"), "by": r.get("by")}
                if r.get("speaker") else None)),
            "comparisons": _lay("comparisons.jsonl.gz", "compare", lambda r: (
                {"vehicle": r.get("vehicle") or [], "tenor": r.get("tenor") or [],
                 "particle": r.get("particle"), "shape": r.get("shape")}
                if r.get("vehicle") else None)),
            "metaphor": _lay("metaphor.jsonl.gz", "image", lambda r: (
                {"vehicle": r.get("vehicle") or [], "tenor": r.get("tenor") or [],
                 "reads": r.get("reads")} if r.get("vehicle") else None)),
            "kinship": _lay("kinship.jsonl.gz", "kin", lambda r: (
                {"a": r.get("a"), "rel": r.get("rel"), "b": r.get("b"),
                 "by": r.get("by")} if r.get("rel") else None)),
            "places": _lay("places.jsonl.gz", "place", lambda r: (
                [p.get("label") if isinstance(p, dict) else p
                 for p in (r.get("places") or [])] or None)),
        }
        # polarity and stance are per VERB, so they are summarised per verse:
        # a reader wants "this verse denies something", not a list of frames
        neg = collections.Counter()
        stance = collections.defaultdict(collections.Counter)
        p = OUT / "frames.jsonl.gz"
        if p.exists():
            try:
                for line in gzip.open(p, "rt", encoding="utf-8"):
                    if not line.strip():
                        continue
                    r = json.loads(line)
                    if not isinstance(r, dict) or any(
                            k.startswith("_") for k in r):
                        continue
                    ref = r.get("ref")
                    if not ref:
                        continue
                    if r.get("polarity") == "negative":
                        neg[ref] += 1
                    if r.get("stance"):
                        stance[ref][r["stance"]] += 1
            except (OSError, json.JSONDecodeError):
                pass
        for ref, k in neg.items():
            layers[ref]["negated"] = k
        for ref, c in stance.items():
            layers[ref]["stance"] = c.most_common(1)[0][0]
        counts["frames"] = len(neg) + len(stance)
        print("    " + "  ".join(f"{k} {v:,}" for k, v in counts.items()),
              flush=True)

        _data = {"layers": layers, "translation": translation,
                 "verses": verses, "alias_ix": alias_ix, "chapters": chapters, "nodes": nodes,
                 "byref": byref, "profiles": profiles, "contrasts": contrasts,
                 "ents": ents, "byname": byname, "renamed": renamed,
                 "vecs": vecs, "norms": norms,
                 "gloss_ix": gloss_ix,
                 "lemmas": lemmas, "heads": heads, "orig": orig,
                 "ptree": ptree, "hpat": hpat, "hpat_by_sec": hpat_by_sec,
                 "hpat_inst": hpat_inst,
                 "secstart": secstart,
                 "stamp_df": stamp_df, "stamp_by_sec": stamp_by_sec,
                 "stamp_secs": stamp_secs, "sectitle": sectitle,
                 # The pattern layers built as separate tools, surfaced
                 # together by /api/patternsets. Each is small; a missing one
                 # simply drops its category rather than failing the load.
                 # Lemma -> its commonest English gloss. The ladder chains are
                 # sequences of LEMMAS, and a reader who does not read Hebrew
                 # sees eight opaque tokens (2026-09-16: ladder chains are confusing
                 # to a reader who does not speak the language).
                 "lemgloss": _lemma_gloss(orig),
                 # Precomputed by tools/hubrank.py; empty if never run, which
                 # drops the People list back to verse counts rather than
                 # failing.
                 "hubscore": _hubscores(),
                 "taxdetail": _taxonomy_detail(),
                 "nodepat": _rows(OUT / "nodepat.jsonl.gz"),
                 "gradatio": _rows(OUT / "gradatio.jsonl.gz"),
                 "declared_types": _rows(OUT / "declared-types.jsonl"),
                 "theme_register": _rows(OUT / "theme-register.jsonl"),
                 "patterns": patterns, "pat_by_ref": pat_by_ref,
                 "mined": mined, "echoes": echoes, "aligned": aligned,
                 "event_refs": _load_event_refs(),
                 "lex": lex, "occ": occ, "lmeta": lmeta, "bsbw": bsbw,
                 "aramaic": eqs.get("aramaic") or {},
                 "gforms": eqs.get("greek_forms") or {},
                 "hebfor": eqs.get("hebrew_for") or {},
                 "loans": eqs.get("loanwords") or {},
                 "aramkeys": eqs.get("aramaic_lexemes") or {},
                 "align": align, "vmap": vmap,
                 "events": events, "vclass": vclass, "classes": classes,
                 "events_total": events_total,
                 "sents": sents, "sent_by_verse": sent_by_verse,
                 "seams": seams, "seams_heb": seams_heb, "attach": attach,
                 "rels": rels, "cats": cats, "namemap": namemap,
                 "pat_by_tmpl": {r["template"]: r for r in patterns.values()}}
        _selfcheck(_data)
        return _data


def _selfcheck(d):
    """Refuse to serve a silent zero. Two book vocabularies meet here."""
    hits = sum(1 for b in list(d["chapters"])[:20]
               if f"{TO_MACULA.get(b, b)}.1.1" in d["byref"])
    print(f"  self-check: {hits}/20 sampled books line up with the structure",
          flush=True)
    if hits < 10:
        raise SystemExit("book map is wrong; refusing to serve")


# ------------------------------------------------------------------ helpers

def _load_verse_map():
    """English chapter -> the shift to MACULA's numbering, from versemap.py.

    **The Hebrew and English Bibles number verses differently in 93 chapters**,
    and this function is the one place a KJV verse becomes a MACULA reference,
    so it was silently attaching the structure of the wrong verse in the
    reader's view -- Psalm 3:1's diagram drawn beside Psalm 3:2's text.

    The ruling: verses are an indexing convention and should not affect
    grouping or relationships, except as sourcing documentation, where the
    English numbering should be used because readers go by the verse numbers
    in the modern translations. That makes this the whole fix: the internal joins are
    MACULA-to-MACULA and were never wrong, and the citation a reader sees stays
    in English numbering.

    **English, not the King James's.** All five translations on disk share
    identical versification -- 0 differing verse sets in 1,189 chapters -- so
    nothing here privileges the KJV and nothing here changes when the default
    display translation does.
    """
    p = OUT / "verse-map.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("offsets", {})


_VERSE_SHIFT = _load_verse_map()


def macula_ref(b, c, v):
    return f"{TO_MACULA.get(b, b)}.{c}.{v + _VERSE_SHIFT.get(f'{b}.{c}', 0)}"


def _load_eng_to_heb():
    """English verse -> the Hebrew (MACULA) verse holding the same words, per
    VERSE — out/versemap.json maps MACULA -> English, including verses that
    move between chapters (BSB Exodus 8:1-4 = Hebrew 7:26-29), which the
    per-chapter shift above cannot express. Used only to NAME the Hebrew verse
    on the original-language panel (2026-09-25: the BSB verse references are
    the primary and the Hebrew is visible only if the original language is
    expanded)."""
    try:
        moved = json.loads((OUT / "versemap.json").read_text(
            encoding="utf-8")).get("moved") or {}
    except (OSError, ValueError):
        return {}
    return {e: m for m, e in moved.items()}


_ENG_TO_HEB = _load_eng_to_heb()


def hebrew_ref(b, c, v):
    eng = f"{TO_MACULA.get(b, b)}.{c}.{v}"
    return _ENG_TO_HEB.get(eng, eng)


def marks_for(d, b, c, v, text):
    """Words in the reading text that lead somewhere.

    Matched against the glosses MACULA gives the very same verse, so the link
    from an English word to a lemma is local evidence rather than a global
    dictionary. It is approximate -- the KJV and MACULA word choices differ --
    and approximate is honest here: an unmarked word is not a claim that
    nothing is known about it.
    """
    ref = macula_ref(b, c, v)
    out = {}
    for e in d["byref"].get(ref, []):
        for side in ("src", "dst"):
            nid = e.get(side)
            if not isinstance(nid, str):
                continue
            n = d["nodes"].get(nid)
            if not n or not n.get("text") or n.get("composite"):
                continue
            w = _slug(n["text"])
            if len(w) < 3:
                continue
            out.setdefault(w, {"word": n["text"], "strong": n.get("strong"),
                               "lang": n.get("lang"), "lemma": n.get("lemma"),
                               "proper": n.get("proper")})
    found = []
    for m in re.finditer(r"[A-Za-z][A-Za-z'-]*", text):
        w = _slug(m.group(0))
        hit = out.get(w)
        if not hit:
            # KJV plurals and verb forms drift from the gloss; one step of
            # tolerance catches most of it without inventing matches
            hit = out.get(w.rstrip("s")) or out.get(w + "s")
        if hit:
            found.append({"start": m.start(), "end": m.end(), **hit})
    return found


def _taxonomy_detail():
    """-> {stamp id: whatever the taxonomy records about it}.

    2026-09-16: the list looked right, but drilling in showed only a bunch of
    verse references, never the list.

    The members were there the whole time. `ontology/interest-taxonomy.json`
    records, for `fruit_of_the_spirit`, its passage (Gal 5), its shape
    ("Spirit > transformation > character") and its nine members -- and the
    stamp card showed none of it, because it was built for stamps in general
    and a stamp is normally just a label. A collection is not: the members ARE
    the thing, and a card that lists where the fruit of the Spirit is mentioned
    without ever naming love, joy and peace has withheld the answer.

    Read across every category rather than just `aggregates`, since parables
    and dreams carry structure of their own.
    """
    p = ROOT / "ontology" / "interest-taxonomy.json"
    if not p.exists():
        return {}
    try:
        tax = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    out = {}

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("id"), str):
                extra = {k: v for k, v in node.items()
                         if k not in ("id",) and not k.startswith("_")}
                if extra:
                    out.setdefault(node["id"], extra)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(tax)
    return out


_AGG = None


def _agg_hubs():
    """-> ontology/aggregate-hubs.json: the declared lists (A.34), each with
    its card, its members and the passage's own verbs.

    2026-10-07: an aggregate is a type of concept and two cards were confusing
    -- so a list is ONE card. Its graph
    card carries the members and moves, and the collection card a section's
    chip used to open (stamp:armor_of_god, built from the taxonomy's ids:
    "armor of god", "sword of the spirit") sends the reader there instead."""
    global _AGG
    if _AGG is None:
        p = ROOT / "ontology" / "aggregate-hubs.json"
        try:
            hubs = {k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items()
                    if not k.startswith("_")}
        except (ValueError, OSError):
            hubs = {}
        _AGG = {"hubs": hubs, "by_card": {h["card"]: k for k, h in hubs.items() if h.get("card")}}
    return _AGG


def hub_for(d, eid):
    """The list a card is the hub of: each member with its card (where the
    graph holds it as the same thing) or else its verse, each move with its
    verse, and the sections tagged with the list."""
    aid = _agg_hubs()["by_card"].get(eid)
    if not aid:
        return None
    h = _agg_hubs()["hubs"][aid]
    ents = d["ents"]
    tagged = list(dict.fromkeys(d.get("stamp_secs", {}).get(aid) or []))
    return {"id": aid, "passage": h.get("passage"), "note": h.get("note"),
            # a heading a list needs instead of the plain ones ("Isaiah 11:2, set
            # beside them"), and no count where traditions count differently
            "members_heading": h.get("members_heading"), "moves_heading": h.get("moves_heading"),
            "uncounted": bool(h.get("uncounted")),
            "members": [{"label": m["label"], "ref": m["ref"],
                         **({"card": m["card"], "name": ents[m["card"]]["name"]}
                            if m.get("card") in ents else {})}
                        for m in h.get("members") or []],
            "moves": [{"words": m["words"], "ref": m["ref"]} for m in h.get("moves") or []],
            "tagged": [{"ref": r, "title": d.get("sectitle", {}).get(r, "")}
                       for r in sorted(tagged, key=_vkey)]}


def _hubscores():
    """-> {entity id: hub score} from out/hubs.json, or {} if absent."""
    p = OUT / "hubs.json"
    if not p.exists():
        return {}
    try:
        rows = json.loads(p.read_text(encoding="utf-8")).get("hubs") or []
    except (ValueError, OSError):
        return {}
    return {r["id"]: r.get("score", 0) for r in rows if r.get("id")}


def _person_verses(d):
    """-> {lowercased name: verses that name appears in}.

    Cached on the loaded data, since it is a full pass over the cross-reference
    layer and the Explore page asks for it on every build.
    """
    got = d.get("_pverses")
    if got is not None:
        return got
    # KEYED ON STRONG'S NUMBER, NOT THE NAME. Both sides carry one -- the
    # entity records as `strong: ["2424"]`, the cross-reference layer as
    # `strong: "H121"` -- and an id join is the only one that survives the
    # spellings. Matching on names put Jesus 23rd with no count at all,
    # because the xref layer writes him "of Jesus", and dropped Paul from the
    # list entirely because it writes him "Paulus".
    #
    # Names are kept as a fallback, since a person the xref layer names but
    # does not number should still be found.
    tally = collections.Counter()
    p = OUT / "people-xref.jsonl.gz"
    if p.exists():
        for line in gzip.open(p, "rt", encoding="utf-8"):
            row = json.loads(line)
            if "ref" not in row:
                continue
            for person in row.get("people") or []:
                s = re.sub(r"^0+", "", re.sub(r"[^0-9]", "",
                                              person.get("strong") or ""))
                if s:
                    tally["#" + s] += 1
                nm = (person.get("name") or "").strip().lower()
                if nm:
                    tally[re.sub(r"^of ", "", nm)] += 1
    d["_pverses"] = tally
    return tally


def _person_count(verses_in, e):
    """How many verses this person is in, by id first and name second."""
    for s in (e.get("strong") or []):
        s = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", str(s)))
        if s and "#" + s in verses_in:
            return verses_in["#" + s]
    return verses_in.get((e.get("name") or "").strip().lower())


def _lemma_gloss(orig):
    """-> {lemma or surface form: commonest gloss}.

    BOTH KEYS, because the two layers that need this store different things.
    The ladder chains are sequences of LEMMAS; the node structures' slot
    fillers are SURFACE FORMS. Indexing lemmas alone glossed χάρις — which
    happens to be both — and left ὑμῖν and ἀπὸ bare, which is precisely what
    a reader hit: the Greek for slot 0 and 1 could not be read.

    Surface forms are added second and do not overwrite a lemma entry, so a
    word that is its own lemma keeps the dictionary reading rather than one
    verse's contextual gloss.

    The commonest gloss rather than the first: a word reads differently by
    context, and the majority is what makes a bare list legible.
    """
    lem = collections.defaultdict(collections.Counter)
    sur = collections.defaultdict(collections.Counter)
    for words in orig.values():
        for w in words:
            g = (w.get("g") or "").strip()
            if not g:
                continue
            if w.get("l"):
                lem[w["l"]][g] += 1
            if w.get("t"):
                sur[w["t"].strip(",.;·")][g] += 1
    out = {t: c.most_common(1)[0][0] for t, c in sur.items()}
    out.update({l: c.most_common(1)[0][0] for l, c in lem.items()})
    return out


MINED_TOP = 3000          # the explorer lists' reach, besides indexed rows


def _load_mined():
    """The pattern miner's findings (tools/patterns/mine.py), for the reader.

    2026-09-28: patterns should show up in the search results and in the
    node descriptions -- what are the most interesting patterns a node
    participates in? So three files: every node's best patterns (the index), the rows
    those and the explorer's lists name, and their instances with the
    Strong's numbers of the words that put each one there. Formulas and
    quotations/parallel accounts are not a node's patterns and are not
    loaded. Absent files give an empty layer, not a failed load.
    """
    out = {"rows": {}, "index": {}, "inst": {}, "top": []}
    pi = OUT / "pattern-index.jsonl.gz"
    if not pi.exists():
        return out
    print("  loading mined patterns …", flush=True)
    for r in _rows(pi):
        out["index"][r["node"]] = r["patterns"]
    want = {p["id"] for ps in out["index"].values() for p in ps}
    pc = OUT / "pattern-candidates.jsonl.gz"
    for line in (gzip.open(pc, "rt", encoding="utf-8") if pc.exists()
                 else ()):
        r = json.loads(line)
        if r["kind"].startswith(("formula", "reference")):
            continue
        if len(out["top"]) < MINED_TOP:
            out["top"].append(r["id"])
        elif r["id"] not in want:
            continue
        out["rows"][r["id"]] = r
    for r in _rows(OUT / "pattern-instances.jsonl.gz"):
        if r["id"] in out["rows"]:
            out["inst"][r["id"]] = r["instances"]
    return out


# Measured by hand, 8 NT verses per rank band (tools/patterns/echoes.py,
# 2026-09-28, regraded after the bridge fixes): how often an NT->OT link at
# that score is a real quotation or echo. OT->OT links are NOT measured and
# are never given these names.
ECHO_BANDS = [(14.5, "strong", "about 5 in 8 real"),
              (12.4, "likely", "about 4 in 8 real"),
              (10.7, "possible", "about 2-3 in 8 real"),
              (0.0, "faint", "about 1 in 8 real")]


def _cv(ref):
    b, c, v = ref.split(".")
    return b, int(c), int(v)


def _load_event_refs():
    """What a passage refers to, as a reader reads it — CREDITED READINGS,
    never computed. 2026-09-28: not every verse has to map, though what every
    line in Phil 2:5-11 references is obvious to a reader; and they are
    shown, credited. A reading names any verse of
    the event it means; the event is found here, from out/gospel-events
    (events are rebuilt, verses are not). Returns the readings and the
    events, each event as its tellings' spans."""
    events = []
    for r in _rows(OUT / "gospel-events.jsonl.gz"):
        spans = [(_cv(t["start"]), _cv(t["end"])) for t in r["tellings"]]
        events.append({"id": r["id"], "title": r["title"],
                       "tellings": r["tellings"], "spans": spans})
    # CONFIRMED READINGS ONLY. 2026-09-29: John 1:1-5 each appeared
    # "referred to by" Phil 2:6 -- a draft reading, pinned to the
    # event of John 1:1 and so shown on every verse of it; drafts need care. Drafts stay
    # in the file as a record; the reader shows what a person has confirmed.
    readings = [r for r in _rows(ROOT / "ontology" / "event-references.jsonl")
                if r.get("confirmed_by")]
    return {"readings": readings, "events": events}


def event_at(d, ref):
    """The gospel event whose tellings hold a verse, or None.

    Was `event_of`, and a second `event_of(d, eid)` written a day later
    (the event card) replaced it, since Python keeps the last definition of
    a name: from 2026-09-29 every call here looked a VERSE up as an event id,
    found nothing, and a reading referring to an event was shown only at
    its exact verse, never at the other verses that tell the event (found
    2026-10-03)."""
    try:
        b, c, v = _cv(ref)
    except ValueError:
        return None
    for e in (d.get("event_refs") or {}).get("events", ()):
        for (b1, c1, v1), (_b2, c2, v2) in e["spans"]:
            if b1 == b and (c1, v1) <= (c, v) <= (c2, v2):
                return e
    return None


def _event_brief(d, e):
    return {"title": e["title"],
            "tellings": [{"book": t["book"], "start": bsb_ref(d, t["start"]),
                          "end": bsb_ref(d, t["end"])} for t in e["tellings"]]}


def event_refs_for(d, ref):
    """This verse's readings both ways: what it refers to, and the readings
    that refer to it — to its verse, or to the event it is told in. The
    later echoes, read from the original reference, matter as much as the
    reference points seen when reading the echoes later."""
    refers, referred = [], []
    here = event_at(d, ref)
    for r in (d.get("event_refs") or {}).get("readings", ()):
        credit = {"words": r.get("words"), "kind": r.get("kind"),
                  "note": r.get("note"), "reader": r.get("reader"),
                  "status": r.get("status"),
                  "confirmed_by": r.get("confirmed_by")}
        if r["from"] == ref:
            for t in r["to"]:
                eref, text = _verse_text(d, t)
                e = event_at(d, t)
                refers.append(dict(credit, eref=eref, text=text,
                                   event=_event_brief(d, e) if e else None))
        hits = [t for t in r["to"] if t == ref or
                (here is not None and event_at(d, t) is here)]
        if hits:
            eref, text = _verse_text(d, r["from"])
            referred.append(dict(credit, eref=eref, text=text,
                                 event=here["title"] if here else None))
    return refers, referred


SAYING = {}               # verse -> its saying's first telling (canon order)
SAYING_FAMILY = {}        # first telling -> every verse that tells it
FORMULA_SIZE = 12         # a family larger than this is a stock formula


def _load_echoes():
    """Quotations, echoes and parallel accounts, by verse, both ways.
    2026-09-28: a reader of Isa 8:14 wants to know about all the
    later references -- so an OT verse lists the later verses that take it
    up as surely as an NT verse lists its sources."""
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in _rows(OUT / "echoes.jsonl.gz"):
        a, b, k = r["from"], r["to"], r["kind"]
        sh = r.get("shared_en") or r.get("shared") or []
        if k == "NT->OT":
            out[a]["earlier"].append((b, r["score"], sh))
            out[b]["later"].append((a, r["score"], sh))
        elif k == "OT->OT":
            out[a]["elsewhere"].append((b, r["score"], sh))
            out[b]["elsewhere"].append((a, r["score"], sh))
            if r.get("source"):
                # the same saying told again, and where it is first told
                for x in (a, b):
                    SAYING[x] = r["source"]
                    SAYING_FAMILY.setdefault(r["source"], set()).add(x)
        elif k == "parallel":
            out[a]["parallel"].append((b, r["score"], sh))
            out[b]["parallel"].append((a, r["score"], sh))
    return out


def _load_aligned(precomputed=True):
    """Verse -> verses that say the same thing, by structure and meaning.

    PRECOMPUTED WHEN IT CAN BE (2026-10-01, docs/LAUNCH.md): rolling 303,447
    clause pairs up at every start held 1.1 GB of a 4.8 GB server. The same
    roll-up, run once by tools/patterns/aligned_verses.py and kept to the
    pairs and fields the panel reads, is loaded instead when it is newer than
    its inputs; `--check` there compares api_echoes both ways."""
    dest = OUT / "aligned-verses.jsonl.gz"
    if precomputed and dest.exists():
        with gzip.open(dest, "rt", encoding="utf-8") as f:
            head = json.loads(f.readline() or "{}")
        # by its inputs' fingerprints, not file times: a git checkout gives
        # every file a fresh, arbitrary time
        if head.get("_inputs") == aligned_inputs():
            # each verse's pairs kept compressed, unpacked when that verse's
            # panel asks (133k pairs as dicts were 256 MB)
            out = CompressedMap()
            with gzip.open(dest, "rt", encoding="utf-8") as f:
                f.readline()
                for line in f:
                    m = re.match(r'\{"v":"([^"]+)","pairs":', line)
                    if m:
                        out.put(m.group(1), line[m.end():-2] if line.endswith("}\n") else line[m.end():-1])
            return out
        print("  aligned-verses.jsonl.gz was built from other inputs: rolling up at "
              "start (run tools/patterns/aligned_verses.py)", flush=True)
    return _load_aligned_full()


def _structure():
    """tools/structure.py, imported once: the clause structure's one copy."""
    global _STRUCTURE
    if _STRUCTURE is None:
        import importlib
        tdir = str(ROOT / "tools")
        if tdir not in sys.path:
            sys.path.insert(0, tdir)
        _STRUCTURE = importlib.import_module("structure")
    return _STRUCTURE


class NodesView:
    """d["nodes"], read from the chapter blocks: the same nine fields, the
    same coercions, the same answers as the dict of 707k nodes it replaces.
    What needed every node at once reads the blocks' summary instead
    (structure.summary()); values() is refused so a new caller cannot
    quietly unpack the whole corpus."""
    def __init__(self, S):
        self.S = S
        sm = S.summary()
        self._n, self._away = sm["nodes"], sm["ids_away"]

    def _key(self, nid):
        return self._away.get(nid) or nid.split("#")[0].rsplit(".", 1)[0]

    @staticmethod
    def _project(d):
        return {"id": d["id"], "ref": d.get("ref"), "local": d.get("local"),
                "text": d.get("text"), "lemma": d.get("lemma"), "strong": d.get("strong"),
                "proper": bool(d.get("proper")), "lang": d.get("lang"),
                "composite": bool(d.get("composite"))}

    def get(self, nid, default=None):
        if not isinstance(nid, str):
            return default
        raw = self.S.chapter(self._key(nid))[0].get(nid)
        return self._project(raw) if raw is not None else default

    def __getitem__(self, nid):
        r = self.get(nid)
        if r is None:
            raise KeyError(nid)
        return r

    def __contains__(self, nid):
        return self.get(nid) is not None

    def __len__(self):
        return self._n

    def values(self):
        raise NotImplementedError("read structure.summary(), not every node")


class ByRefView:
    """d["byref"], read from the chapter blocks: a verse's edges in file
    order, the structure graph's own (not the BSB readings), as before."""
    def __init__(self, S):
        self.S = S

    def get(self, ref, default=None):
        if not isinstance(ref, str) or "." not in ref:
            return default
        es = [e for e in self.S.chapter(ref.rsplit(".", 1)[0])[1] if e.get("ref") == ref]
        return es or default

    def __contains__(self, ref):
        return bool(self.get(ref))

    def __len__(self):
        # verses with edges, as len() of the old dict counted them (the
        # start-up banner; missed by the equivalence run, which never calls
        # main() -- found on starting the server, 2026-10-01)
        return self.S.summary()["edge_refs"]


class CompressedMap(dict):
    """key -> JSON value, held zlib-compressed and parsed on each read. A dict
    to everything that reads it (get, [], items, values, in, len); what it
    saves is that a value nobody asks for is never a Python object.
    (2026-10-01, docs/LAUNCH.md: the representation, not the content.)"""
    def put(self, key, json_text):
        import zlib
        super().__setitem__(key, zlib.compress(json_text.encode("utf-8")))

    def _unpack(self, z):
        import zlib
        return json.loads(zlib.decompress(z))

    def __getitem__(self, key):
        return self._unpack(super().__getitem__(key))

    def get(self, key, default=None):
        z = super().get(key)
        return default if z is None else self._unpack(z)

    def items(self):
        for k, z in super().items():
            yield k, self._unpack(z)

    def values(self):
        for z in super().values():
            yield self._unpack(z)


def aligned_inputs():
    """{file: md5} of what the aligned roll-up reads; about 40 ms."""
    import hashlib
    return {n: hashlib.md5((OUT / n).read_bytes()).hexdigest()
            for n in ("aligned.jsonl.gz", "trim.jsonl.gz", "clause-tags.jsonl.gz")
            if (OUT / n).exists()}


def _load_aligned_full():
    """Verse -> verses that say the same thing, by structure and meaning
    (tools/patterns/aligned.py), rolled up from clause pairs by COVERAGE.

    2026-09-28, on John 3:16's list: 2 of the 4 primary were poor
    matches -- 1 Chr 25:5 ("God had given Heman fourteen sons") matched ONE
    of John 3:16's five clauses. A verse says the same thing when it
    matches more of the verse: each of this verse's clauses counts once,
    at its best pair into the other verse; the verse's score is their sum;
    `clauses` says how many matched and `of` how many could. A contrast in
    any clause makes the pair a contrast."""
    per = collections.defaultdict(lambda: collections.defaultdict(dict))
    alignable = collections.defaultdict(set)
    tags = _clause_tags()
    # THE CHECKLIST (tools/patterns/trim.py, plan 6.14). 2026-09-29:
    # anything that does not completely pass is demoted to the other possible
    # connections section, and others that scored low originally
    # and/or fail the trimming pass badly are removed. A removed clause pair is not
    # read at all; a demoted one carries its reason.
    trim = {}
    if (OUT / "trim.jsonl.gz").exists():
        trim = {(t["from"], t["to"]): t for t in _rows(OUT / "trim.jsonl.gz")}
    for r in _rows(OUT / "aligned.jsonl.gz"):
        a, b = r["from"].split("#")[0], r["to"].split("#")[0]
        alignable[a].add(r["from"])
        t = trim.get((r["from"], r["to"]))
        if t and t["verdict"] == "remove":
            continue
        if t and t["verdict"] == "demote":
            r = dict(r, trim=t["fails"])
        # THE STAMPS LIFT A MATCH TOWARD THE BAR. 2026-09-28: raise
        # the bar a little and let the stamps raise the score to
        # reach the bar. Structure alone cannot tell a true match from a
        # false one — of the pilot's judged pairs, "none" scored 10.1-15.4
        # against "same" 10.3-17.1 (John 3:16 / 1 Chr 25:5 "gave ... sons"
        # at 15.4). Each tag BOTH clauses carry adds STAMP_LIFT x the two
        # strengths (high 1, medium .67, low .33: the chosen weights).
        # STAMPS ONLY. With the whole corpus tagged (29 Sep), concept tags
        # lifted Ps 23:6 "dwell in the house" to 20 against Deut 21:13's
        # captive woman "in your house": the run pins a concept where its
        # word stands ("house", "home", "household"), so sharing one repeats
        # the word match that made the pair. A stamp is a reading.
        ta = {t["tag"]: t["weight"] for t in tags.get(r["from"], ()) if t.get("kind") == "stamp"}
        tb = {t["tag"]: t["weight"] for t in tags.get(r["to"], ()) if t.get("kind") == "stamp"}
        shared = set(ta) & set(tb)
        if shared:
            r = dict(r, structure=r["score"],
                     score=round(r["score"] + STAMP_LIFT * sum(ta[t] * tb[t] for t in shared), 2),
                     # ties by name: set order changes with every process
                     # (hash randomisation), so "king, kingdom" was
                     # "kingdom, king" on the next start (found 2026-10-01
                     # proving the precomputed matches equal)
                     stamps=sorted(shared, key=lambda t: (-ta[t] * tb[t], t)))
        prev = per[a][b].get(r["from"])
        # a contrast is the more telling finding and wins a tie: "God loved
        # the world" meets both "if anyone loves the world" and "do not love
        # the world" (1 John 2:15) at one score
        if not prev or r["score"] > prev["score"] or (
                r["score"] == prev["score"] and r.get("tier") == "contrast"):
            per[a][b][r["from"]] = r
    out = collections.defaultdict(dict)
    for a, targets in per.items():
        for b, byc in targets.items():
            rs = sorted(byc.values(), key=lambda r: -r["score"])
            top = rs[0]
            tiers = {r.get("tier") for r in rs}
            agg = dict(top)
            agg["score"] = round(sum(r["score"] for r in rs[:3]), 2)
            agg["clauses"] = len([r for r in rs if r.get("tier") != "similar"])
            agg["of"] = len(alignable[a])
            agg["tier"] = "contrast" if "contrast" in tiers else top.get("tier")
            # held back only when every clause that matched was: one clause
            # that passes the checklist carries the verse
            fails = [f for r in rs if r.get("tier") != "similar" for f in r.get("trim", ())]
            if all(r.get("trim") for r in rs if r.get("tier") != "similar") and fails:
                agg["trim"] = sorted(set(fails))
            else:
                agg.pop("trim", None)
            if agg["tier"] == "contrast":
                c = next(r for r in rs if r.get("tier") == "contrast")
                agg.update({k: c[k] for k in ("verb", "obj", "force", "neg")
                            if k in c})
            out[a][b] = agg
    return out


def connected(d):
    """Every verse whose connections panel would show anything, shown or
    potential — built once. 2026-09-28: the connections chip is not
    shown if there are no connections. The same filters as
    api_echoes and mined_for, so the chip and the panel cannot disagree."""
    s = d.get("_connected")
    if s is not None:
        return s
    s = set()
    for ref, got in d["echoes"].items():
        for kind in ("earlier", "later"):
            if any(sc >= ECHO_BANDS[1][0] for _o, sc, _sh in got.get(kind, [])):
                s.add(ref)
        if any(sc >= OT_STRONG for _o, sc, _sh in got.get("elsewhere", [])):
            s.add(ref)
        if got.get("parallel"):
            s.add(ref)
    pj = _pair_judgments()
    for ref, al in (d.get("aligned") or {}).items():
        if pj:
            # once pairs are judged, only a pair read as the same earns the chip
            if any(r["score"] >= ALIGN_MIN and r.get("tier") == "same" and
                   (pj.get(tuple(sorted((ref, o)))) or {}).get("verdict") == "same"
                   for o, r in al.items()):
                s.add(ref)
        elif any(r["score"] >= ALIGN_MIN and r.get("tier") == "same" and not r.get("trim")
                 for r in al.values()):
            s.add(ref)
    # patterns alone do not earn the chip: they are folded in the panel,
    # and nearly every verse has one (all 31 of Proverbs 4)
    # a READING earns it both ways: the verse that refers, and every verse
    # of the event it refers to (the crucifixion shows "referred to by")
    spans = []
    for r in (d.get("event_refs") or {}).get("readings", ()):
        s.add(r["from"])
        for t in r["to"]:
            s.add(t)
            e = event_at(d, t)
            if e is not None:
                spans += e["spans"]
    if spans:
        books = {b for (b, _c, _v), _e in spans}
        for key in d.get("verses", {}):
            b = TO_MACULA.get(key[0], key[0])
            if b not in books:
                continue
            cv = (key[1], key[2])
            if any(b == b1 and (c1, v1) <= cv <= (c2, v2)
                   for (b1, c1, v1), (_b, c2, v2) in spans):
                s.add(f"{b}.{key[1]}.{key[2]}")
    # the editors' notes earn it too: a parallel note for every verse of its
    # section, a quotation footnote for its verse (and the verse it quotes)
    fwd, back = _declared_refs(d)
    s.update(fwd)
    s.update(back)
    # a verse a theme's table sets out has something to show (2026-10-08;
    # before, every verse the theme map's outline cited)
    for (b, c, v) in _theme_tags():
        s.add(_macula_ref(d, f"{b}.{c}.{v}"))
    # what two verses share (plan 6.17): both verses of every judged link --
    # Rev 17:7's only connection is the ten-horns node (2026-10-04)
    for r in _rows(ROOT / "ontology" / "allusions.jsonl"):
        s.add(_macula_ref(d, r["nt"]))
        s.add(_macula_ref(d, r["ot"]))
    # and every verse carrying a step of a story told again (plan 6.18)
    for r in _rows(ROOT / "ontology" / "told-again.jsonl"):
        for pair in r["beats"]:
            for ref, _w in pair:
                s.add(_macula_ref(d, ref))
    # and both verses of every shown reference from the letters (plan 6.21)
    for refs in _letter_refs().values():
        for r in refs:
            s.add(_macula_ref(d, r["letter"][0]))
            s.add(_macula_ref(d, re.sub(r"\s*[-–]\s*\d+$", "", r["account_verse"])))
    # and both verses of every shown link from Revelation (plan 6.22)
    show_all = os.environ.get("BIBLEONT_SHOW_UNREVIEWED") == "1"
    for r in _rows(ROOT / "ontology" / "revelation-links.jsonl"):
        if r.get("reviewed_by_owner") or show_all:
            s.add(_macula_ref(d, r["rev"][0]))
            s.add(_macula_ref(d, r["other"][0]))
    # and of every shown link between the history books (plan 6.23)
    for r in _rows(ROOT / "ontology" / "history-links.jsonl"):
        if r.get("reviewed_by_owner") or show_all:
            s.add(_macula_ref(d, r["later"][0]))
            s.add(_macula_ref(d, r["earlier"][0]))
    xi, qi = _xref_index(d), _quote_index(d)
    for key in d.get("verses", {}):
        r = f"{TO_MACULA.get(key[0], key[0])}.{key[1]}.{key[2]}"
        if r in qi or (xi and _section_start_of(d, r) in xi):
            s.add(r)
    d["_connected"] = s
    return s


def api_echoes(d, q):
    """A verse's links to other verses, graded. 2026-09-28: Dig Deeper is
    backed off; the threshold is tightened even for the shown list because
    noise hurts credibility. So: shown, only what
    measured strong (echoes 14.5+, about 5 in 8) and what says the same
    thing by structure with the same words; under "dig deeper", likely
    echoes and structural matches through similar words; nothing weaker
    at all."""
    ref = _macula_ref(d, (q.get("ref") or [""])[0])
    got = d["echoes"].get(ref) or {}
    out = {"ref": ref}
    al = []
    for other, r in sorted((d.get("aligned") or {}).get(ref, {}).items(),
                           key=lambda x: -x[1]["score"]):
        if r["score"] < ALIGN_MIN:
            continue
        # a match through only-similar words must at least line up in
        # force (Prov 4:13's "discipline ~ feet" did not)
        if r.get("tier") not in ("same", "contrast") and \
                r["force"][0] != r["force"][1]:
            continue           # (a contrast differs in force by nature)
        eref, text = _verse_text(d, other)
        # COVERAGE: the same thing means more of this verse — two of its
        # clauses, or half of a short one (John 3:16 has five: one shared
        # clause, "God gave Heman sons", is not the same thing)
        n, of = r.get("clauses", 1), max(r.get("of", 1), 1)
        covered = n >= 2 or n / of >= 0.5
        tier = r.get("tier")
        how = _aligned_how(r)
        if tier == "same" and not covered:
            how += f" · one clause of {of}"
        if r.get("trim"):
            how += " · held back: " + "; ".join(r["trim"])
        # THE JUDGMENT DECIDES "says the same thing". 2026-09-29:
        # less is more on the verse to verse connections. Structure only
        # proposes: a pair Flash judged "no" is not shown at all; "partly"
        # goes under other potential matches as the same theme; only "same"
        # is shown, with its reason, credited. Unjudged pairs wait below.
        judged = None
        if tier == "same" and _pair_judgments():
            judged = _pair_judgments().get(tuple(sorted((ref, other))))
            if judged and judged["verdict"] == "no":
                continue
            if judged:
                if judged["verdict"] == "same":      # the reading was of both verses whole
                    how = how.replace(f" · one clause of {of}", "")
                how += (" · read as saying the same" if judged["verdict"] == "same"
                        else " · on the same theme") + \
                       (f": {judged['reason']}" if judged.get("reason") else "") + \
                       " (DeepSeek Flash, unreviewed)"
        held = bool(r.get("trim")) or (
            tier == "same" and bool(_pair_judgments()) and not (judged and judged["verdict"] == "same"))
        al.append({"ref": other, "eref": eref, "text": text,
                   "score": r["score"],
                   "judged": bool(judged and judged["verdict"] == "same"),
                   # a pair judged the same is shown whatever share of the
                   # verse it covers: the reading was of the two verses whole
                   "deeper": False if (judged and judged["verdict"] == "same") else held or not (
                       tier == "contrast" or (tier == "same" and covered)),
                   "tier": tier, "doer": r.get("doer"), "how": how})
    # a pair READ as the same is shown whatever its score (up to SHOW_MAX):
    # the score's knee cut John 3:16's 3:36, 5:24, 6:47 and 20:31, all read
    # as the same promise, because 6:40 scored higher on structure
    judged = sorted([x for x in al if x.get("judged")], key=lambda x: -x["score"])
    for i, x in enumerate(judged):
        x["deeper"] = i >= SHOW_MAX
    same = judged + knee([x for x in al if not x["deeper"] and x["tier"] == "same"
                          and not x.get("judged")],
                         fill_ok=lambda x: x.get("doer") != "unconfirmed")
    same += knee([x for x in al if not x["deeper"] and x["tier"] == "contrast"])
    out["aligned"] = (same + [x for x in al if x["deeper"]])[:30]
    parallel_refs = {o for o, _s, _sh in got.get("parallel", [])}
    for kind in ("earlier", "later", "parallel", "elsewhere"):
        seen, items = set(), []
        for other, score, sh in sorted(got.get(kind, []), key=lambda x: -x[1]):
            if other in seen:
                continue
            seen.add(other)
            band, note = next((n, t) for lo, n, t in ECHO_BANDS if score >= lo)
            if kind == "elsewhere":
                # OT <-> OT on Hebrew lexemes, graded by its own hand check
                # (7-8 of 8 real down to 12.7); a retelling is listed as a
                # parallel account, not again here
                if score < OT_STRONG or other in parallel_refs:
                    continue
                band, note = "strong", "about 7 in 8 real"
            elif kind != "parallel" and band in ("possible", "faint"):
                continue           # too weak to show at all
            eref = bsb_ref(d, other)
            try:
                b, c, v = eref.split(".")
                text = d["verses"].get((MACULA_BACK.get(b, b), int(c), int(v)))
            except (ValueError, TypeError):
                text = ""
            items.append({"ref": other, "eref": eref, "text": text or "",
                          "score": score, "band": band, "band_note": note,
                          "shared": sh[:8],
                          "deeper": kind != "parallel" and band != "strong"})
        shown = knee([x for x in items if not x["deeper"]])
        out[kind] = shown + [x for x in items if x["deeper"]]
    out["thread"] = echo_thread(d, ref)
    out["refers_to"], out["referred_by"] = event_refs_for(d, ref)
    out["editors"] = editor_notes(d, ref)
    # words one verse takes up from another, judged (a reading). Where the
    # editors already link the two, the verse is not repeated: the
    # explanation joins their note instead, still credited as a reading. A
    # shared image stays either way -- it names what both use, which the
    # editors' note does not
    # The editors often note a range (Heb 8:8 -> Jer 31:26-40), so a link
    # joins the note whose span holds its verse, not only one that starts there
    def _note_for(r):
        k = _vkey_macula(r)
        for e in out["editors"]:
            lo = _vkey_macula(e["ref"])
            hi = _vkey_macula(e["eend"]) if e.get("eend") else lo
            if lo <= k <= hi:
                return e
        return None
    al = allusions_for(d, ref)
    kept = []
    for x in al["words"]:
        e = _note_for(x["ref"])
        if e is None:
            kept.append(x)
        elif x.get("explanation"):
            e.setdefault("explanations", []).append(
                {"ref": x["eref"], "explanation": x["explanation"], "reader": x["reader"]})
    al["words"] = kept
    out["allusions"] = al
    out["themes"] = themes_for(d, ref)
    out["kin"] = kin_verses(d, ref)          # plan 5.10, the word family
    # what the verse DECLARES it points to, as Flash read it: shown with
    # the readings, credited to the model and marked unreviewed
    fwd, back = _declared_refs(d)
    reader = "DeepSeek Flash"
    for x in fwd.get(ref, ()):
        eref, text = _verse_text(d, x["to"])
        out["refers_to"].append({
            "words": x["trigger"], "kind": "cites", "note": x["reason"], "reader": reader,
            "status": "unreviewed" + (", its own suggestion" if x["suggested"] else ""),
            "confirmed_by": None, "eref": eref, "text": text, "event": None})
    for x in back.get(ref, ()):
        eref, text = _verse_text(d, x["frm"])
        out["referred_by"].append({
            "words": x["trigger"], "kind": "cited by", "note": x["reason"], "reader": reader,
            "status": "unreviewed", "confirmed_by": None, "eref": eref, "text": text,
            "event": None})
    # THE SAYING: 2026-09-28, of Ps 103:8 and Exod 34:6 -- too strong
    # to be coincidence; Exo 34:6 is identifiable as the
    # originating instance, so that is the direction of the pointer
    src = SAYING.get(ref)
    if src:
        fam = sorted(SAYING_FAMILY.get(src, ()) - {ref},
                     key=lambda x: (_MCANON.get(x.split(".")[0], 99),
                                    [int(n) for n in x.split(".")[1:]]))
        eref, text = _verse_text(d, src)
        out["saying"] = {
            "source": src, "eref": eref, "text": text, "here": src == ref,
            "formula": len(fam) + 1 > FORMULA_SIZE,
            "by": "canon order — the family's earliest telling",
            "family": [{"ref": x, "eref": bsb_ref(d, x)} for x in fam]}
    return out


KNEE = 0.75               # shown: within this share of the best score
SHOW_MAX, SHOW_MIN = 12, 5


def knee(items, key="score", fill_ok=lambda x: True):
    """2026-09-28: up to 10 or even more is fine if the matches are very
    strong, as with compassionate and gracious; it is at a steep drop-off
    that the list is trimmed, around 5. Shown: every item within
    KNEE of the best, up to SHOW_MAX, and at least SHOW_MIN when there are
    that many; the rest is marked for the expansion."""
    xs = sorted(items, key=lambda x: -x[key])
    if not xs:
        return xs
    best = xs[0][key]
    for i, x in enumerate(xs):
        below = x[key] < KNEE * best
        # the minimum fills only with what may be promoted: an unconfirmed
        # doer is not (Num 21:29 filled John 3:16's fifth place)
        if i >= SHOW_MAX or (below and (i >= SHOW_MIN or not fill_ok(x))):
            x["deeper"] = True
    return xs


THREAD_MIN = 14.5         # strong NT<->OT links only
OT_THREAD = 19.5          # strong OT<->OT links (the 7-in-8 band floor)
# structural matches weaker than this are not shown. Raised 8.0 -> 10.0 on
# 2026-09-28 (the bar raised a little): it removes the 8-9 band where
# John 3:4 met Deut 31:16 on "entered ~ came, womb ~ midst", and keeps the six
# true "love the LORD your God" matches of Deut 6:5 at 10.3. It goes to
# STAMP_BAR once the corpus is stamped (plan 6.13), when the lift below can
# carry good matches over it and the false ones — which score as high on
# structure alone — stay under.
ALIGN_MIN = 10.0
STAMP_BAR = 12.0
STAMP_LIFT = 0.2 * STAMP_BAR   # each shared high tag: 20% of the bar


def _aligned_how(r):
    """What lines up, in words: "command · keep ≈ guard · heart"."""
    f = r["force"][0] if r["force"][0] == r["force"][1] == "directive" \
        else None
    vb = [x.replace(" (unstated)", "") for x in r["verb"][:2]]
    v = vb[0] if vb[0] == vb[1] else f"{vb[0]} ≈ {vb[1]}"
    if r.get("tier") == "contrast":
        ng = r.get("neg") or [False, False]
        v = (f"not {vb[0]}" if ng[0] else vb[0]) + " / " + \
            (f"not {vb[1]}" if ng[1] else vb[1])
    o = r["obj"][0] if r["obj"][0] == r["obj"][1] else \
        f"{r['obj'][0]} ≈ {r['obj'][1]}"
    # a match the stamps lifted says so, and by which tags
    st = ("both speak of " + ", ".join(s.replace("_", " ").removesuffix(" ev")
                                       for s in r["stamps"][:3])) if r.get("stamps") else None
    return " · ".join(x for x in ({"directive": "both commands"}.get(f, f),
                                  v, o, st) if x)
THREAD_HOPS = 2
THREAD_MAX = 40
THREAD_KINDS = ("earlier", "later", "parallel", "elsewhere")
OT_STRONG = 12.7          # OT <-> OT echoes: 7-8 of 8 real at and above


def echo_thread(d, ref):
    """Every verse joined to this one within two steps by a strong or likely
    link, in canon order. 2026-09-28: the later echoes, read from
    the original reference, matter as much as the reference points seen
    when reading the echoes later, as do all the points in the middle.
    Isa 8:14 and Rom 9:33 are two points; the thread
    is Ps 118:22, Isa 8:14, Isa 28:16, the gospels, Rom 9:33, 1 Pet 2:6-8."""
    seen, weakest, frontier = {ref: 0}, {ref: None}, [ref]
    # THE THEME MUST CARRY. What each verse shares with the one that reached
    # it; a verse two steps away is kept only if what it shares with the
    # middle verse overlaps what the middle verse shares with the start.
    # Strong at each step does not stop drift — A->B on one set of words,
    # B->C on another, and C has nothing to do with A. 2026-09-28, of
    # Absalom's mule (2 Sam 18:9) in Ps 103:8's thread: it had to be filtered
    # out — it shares none of compassion, grace, anger, loving devotion.
    theme = {ref: None}
    for hop in range(1, THREAD_HOPS + 1):
        nxt = []
        for v in frontier:
            for kind, xs in (d["echoes"].get(v) or {}).items():
                if kind not in THREAD_KINDS:
                    continue
                # STRONG LINKS ONLY, each kind on its own scale.
                # 2026-09-28, of Ps 103:8's thread reaching Ruth 2:20 and
                # Absalom's mule by "likely" links two steps away: the
                # strong links are the ones to make prominent
                floor = OT_THREAD if kind == "elsewhere" else THREAD_MIN
                for other, score, sh in xs:
                    if score < floor or other in seen or \
                            len(seen) >= THREAD_MAX:
                        continue
                    words = {str(x).lower() for x in sh}
                    carried = theme[v]
                    if carried is not None and kind != "parallel" and \
                            not (words & carried):
                        continue
                    seen[other] = hop
                    theme[other] = words if carried is None else \
                        (words & carried) or carried
                    w = weakest.get(v)
                    weakest[other] = score if w is None else min(w, score)
                    nxt.append(other)
        frontier = nxt
    if len(seen) < 3:
        return []
    order = lambda r: (_MCANON.get(r.split(".")[0], 99),  # noqa: E731
                       [int(n) for n in r.split(".")[1:] if n.isdigit()])
    out = []
    for r in sorted(seen, key=order):
        eref = bsb_ref(d, r)
        try:
            b, c, v = eref.split(".")
            text = d["verses"].get((MACULA_BACK.get(b, b), int(c), int(v)))
        except (ValueError, TypeError):
            text = ""
        w = weakest.get(r)
        out.append({"ref": r, "eref": eref, "text": text or "",
                    "here": r == ref, "step": seen[r],
                    # the weakest link on the way here names its band
                    "band": None if w is None else "strong"})
    return out


def mined_tier(r):
    """For the interested reader, or for the one who wants to dig.
    2026-09-28: filter for the average interested reader, but allow a deeper
    drill-in to the more questionable matches. A finding is `sure` unless one of these says why it is not;
    the reasons travel with it, so digging shows WHY a match is weaker."""
    why = []
    if r.get("accounts", 0) < 3:
        why.append(f"only {r.get('accounts', 0)} independent accounts")
    if "~{" in (r.get("pattern") or ""):
        why.append("matched through a similar word, not the same word")
    return ("sure" if not why else "deeper"), why


_HUBS: dict = {}


def concept_hub(eid):
    """A concept hub built by tools/concepts/hub_build.py (out/concept-hubs/
    <id>.json), from its spec (ontology/concept-hubs/<id>.json). Shown on the
    live site only when the spec says "shown": true -- set on approval,
    as a theme's outline is -- and in the preview (BIBLEONT_SHOW_UNREVIEWED)
    before then. 2026-10-09: concepts like love are almost as important as
    themes; the graph is the distinguishing factor, and love is a bridge to
    God and to the commandments."""
    if eid not in _HUBS:
        built = OUT / "concept-hubs" / f"{eid}.json"
        spec = ROOT / "ontology" / "concept-hubs" / f"{eid}.json"
        hub = None
        if built.exists() and spec.exists():
            shown = json.loads(spec.read_text(encoding="utf-8")).get("shown")
            if shown or os.environ.get("BIBLEONT_SHOW_UNREVIEWED") == "1":
                hub = json.loads(built.read_text(encoding="utf-8"))
        _HUBS[eid] = hub
    return _HUBS[eid]


_GLOSS_IX = None
_FACES: dict = {}
_GSTOP = {"with", "from", "that", "this", "they", "them", "their", "there", "have", "will", "which", "your",
          "were", "been", "into", "upon", "what", "when", "shall", "make", "made", "give", "take", "come",
          "said", "says", "unto", "also", "then", "than", "very", "more", "most", "some", "such", "being"}


def _gstem(t):
    """a gloss word's stem, crudely: love, loved, loving, loves -> lov"""
    for suf in ("ings", "ing", "edly", "ed", "es", "s", "ly"):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            t = t[: -len(suf)]
            break
    return t[:-1] if t.endswith("e") and len(t) > 3 else t


def _gtokens(g):
    return {_gstem(t) for t in re.findall(r"[a-z]+", (g or "").lower()) if len(t) >= 4 and t not in _GSTOP}


def _gloss_ix(d):
    """every gloss stem -> {word key: (verses glossed so, verses in all)},
    built once: the words the English renders the same way"""
    global _GLOSS_IX
    if _GLOSS_IX is None:
        ix = {}
        for k, occ in d["occ"].items():
            per, every = {}, set()
            for ref, g in occ:
                every.add(ref)
                for t in _gtokens(g):
                    per.setdefault(t, set()).add(ref)
            for t, rs in per.items():
                ix.setdefault(t, {})[k] = (len(rs), len(every))
        _GLOSS_IX = ix
    return _GLOSS_IX


_VNAMES = None


def verse_names(d, ref, text, skip=()):
    """THE NAMES IN A QUOTED VERSE, LINKED (2026-10-13, on Moses's role
    card: more linking on cards within the text -- built in the preview). Only a person,
    place or group the mention layer has already resolved in THIS verse
    (out/mentions.jsonl.gz, from the original language), found in the
    Berean's wording of that verse by its name or another name it carries;
    never a pronoun (no name to find), never a name two resolved records
    share. (`cited` mentions count: in this layer they are name WORDS --
    "Jethro" at Exod 3:1 w6 -- resolved by the record citing the verse.)
    `ref` in either numbering; returns [{id, name, at}] with `at` the words
    as the verse has them, first occurrence only."""
    global _VNAMES
    if _VNAMES is None:
        ix = collections.defaultdict(set)
        p = OUT / "mentions.jsonl.gz"
        if p.exists():
            for line in gzip.open(p, "rt", encoding="utf-8"):
                r = json.loads(line)
                if "occurrence" in r:
                    ix[r["occurrence"].split("#")[0]].add(r["record"])
        _VNAMES = ix
    if not text:
        return []
    found = {}                                    # surface -> set(record)
    for rid in _VNAMES.get(_macula_ref(d, ref), ()):
        # a record merged into another (ontology/aliases.jsonl) is that one:
        # two records of one person would otherwise read as a shared name
        rid = (d["ents"].get(rid) or {}).get("alias_of") or rid
        o = d["ents"].get(rid) or {}
        if rid in skip or o.get("type") not in ("person", "place", "group"):
            continue
        for nm in [o.get("name")] + list(o.get("aka") or []):
            # a proper name only: "the field" or "a messenger" would catch
            # ordinary words
            if not nm or not nm[0].isupper() or len(nm) < 3:
                continue
            m = re.search(r"(?<![\w'’])" + re.escape(nm) + r"(?![\w])", text)
            if m:
                found.setdefault(m.group(0), set()).add(rid)
    return [{"id": next(iter(ids)), "name": d["ents"][next(iter(ids))]["name"], "at": at}
            for at, ids in found.items() if len(ids) == 1]


def text_face(d, eid, e):
    """A TEXT CARD'S FACE (2026-10-12, after Bing's first click-throughs
    landed on two of them: the information was good, but these were sparse
    nodes that could be presented more cleanly to show what they
    accomplish). What a reader arriving at a saying wants first: its words,
    who said them (once -- the graph records a speaker as asserted_by, told
    and claimed_by, three ways), what it is part of, what it speaks of.

    THE SAME FACE FOR PASSAGES AND VERDICTS (2026-10-13, items 1-4
    done together): a passage card opened on "Said in Israel receives the law told
    in Exodus, Deuteronomy Deuteronomy 9:9-11, a telling of an event" and
    never quoted its verses; a verdict ("your own lips testify against you")
    quoted itself alone. A passage records its first and last verse, so its
    verses are the run between them; a verdict's speaker is the claim's
    (`claimed_by` on the relation that says whom it is said of)."""
    quote, more = [], 0
    if e["type"] == "passage" and len(e.get("refs") or []) == 2:
        # the run from the first verse to the last, in the Berean's order
        ends = [_verse_text(d, _macula_ref(d, r))[0].split(".") for r in e["refs"]]
        if all(len(x) == 3 for x in ends) and ends[0][0] == ends[1][0]:
            b = ends[0][0]
            keys = d.get("_book_keys", {}).get(b)
            if keys is None:
                keys = sorted(k for k in d["verses"] if k[0] == MACULA_BACK.get(b, b))
                d.setdefault("_book_keys", {})[b] = keys
            lo, hi = (int(ends[0][1]), int(ends[0][2])), (int(ends[1][1]), int(ends[1][2]))
            run = [k for k in keys if lo <= (k[1], k[2]) <= hi]
            for k in run[:8]:
                quote.append({"eref": f"{b}.{k[1]}.{k[2]}", "id": f"{k[0]}.{k[1]}.{k[2]}",
                              "ref": f"{k[0]} {k[1]}:{k[2]}", "text": d["verses"][k]})
            more = max(0, len(run) - 8)
    for r in ([] if quote else (e.get("refs") or [])[:12]):
        mr = re.match(r"^(.*?\d+):(\d+)-(\d+)$", r.strip())
        for p in ([f"{mr.group(1)}:{n}" for n in range(int(mr.group(2)), int(mr.group(3)) + 1)] if mr else [r])[:8]:
            try:
                eref, text = _verse_text(d, _macula_ref(d, p))
            except Exception:
                continue
            if text and eref not in {q["eref"] for q in quote}:
                b, c, v = eref.split(".")
                quote.append({"eref": eref, "id": f"{MACULA_BACK.get(b, b)}.{c}.{v}", "ref": p, "text": text})
    for x in quote:
        x["names"] = verse_names(d, x["id"], x["text"], {eid})
    speakers, part_of, speaks_of, said_of, tells, instance_of, seen = [], [], [], [], [], [], set()

    def add(lst, tag, item):
        if (tag, item["id"]) not in seen:
            seen.add((tag, item["id"]))
            lst.append(item)
    for r in d["rels"].get(eid, []):
        o = d["ents"].get(r["other"]) or {}
        item = {"id": r["other"], "name": o.get("name") or r["other"]}
        t, dr = r["type"], r["dir"]
        if (t == "asserted_by" and dr == "out") or (t == "told" and dr == "in") or (t == "claimed_by" and dr == "out"):
            add(speakers, "s", item)
        elif t == "contains" and dr == "in":
            add(part_of, "p", item)
        elif t == "part_of" and dr == "out" and o.get("type") != "event":
            add(part_of, "p", item)
        elif t in ("recounts", "part_of") and dr == "out" and o.get("type") == "event":
            add(tells, "t", item)
        elif t == "instance_of" and dr == "out":
            add(instance_of, "i", item)
        elif t == "speaks_of" and dr == "out":
            add(speaks_of, "c", item)
        elif t in ("described_as", "assessed_as") and dr == "in":
            add(said_of, "o", item)
            if r.get("claimed_by"):
                cb = d["ents"].get(r["claimed_by"]) or {}
                add(speakers, "s", {"id": r["claimed_by"], "name": cb.get("name") or r["claimed_by"]})
    ak = (e.get("attrs") or {}).get("kind")
    kind = {"role_row": "role", "role_cell": "role", "template_stage": "stage of a story",
            "telling": "telling"}.get(ak) if e["type"] == "passage" else None
    kind = kind or {"passage": "passage", "assessment": "verdict"}.get(e["type"]) or ak or "saying"
    # WHO IT IS ABOUT, where the record names them (a role pattern's row and
    # cells: "Moses (Role pattern: Shepherd)" had no way back to Moses --
    # 2026-10-13: it should be easier to link back)
    figures = [{"id": f, "name": (d["ents"].get(f) or {}).get("name") or f}
               for f in (e.get("attrs") or {}).get("figure") or [] if f in d["ents"]]
    return {"kind": kind, "quote": quote, "more": more, "figures": figures,
            "speakers": speakers, "part_of": part_of, "speaks_of": speaks_of,
            "said_of": said_of, "tells": tells, "instance_of": instance_of}


def person_face(d, eid, e):
    """WHO THIS IS, for a person the graph has no description of (2026-10-13:
    997 of 1,667 people opened straight into the
    graph -- the daughter of Jairus with no line saying whose daughter she
    is). From what the card already holds, each part with its verse: the
    record's own disambiguation, or else its kinship; and the first verses
    that name them, quoted."""
    if (e.get("desc") or "").strip():
        return None
    kin = person_kin(d, eid, e)
    quote = []
    for r in (e.get("refs") or [])[:2]:
        try:
            eref, text = _verse_text(d, _macula_ref(d, re.split(r"[-–]", r)[0]))
        except Exception:
            continue
        if text:
            b, c, v = eref.split(".")
            quote.append({"id": f"{MACULA_BACK.get(b, b)}.{c}.{v}", "ref": r, "text": text,
                          "names": verse_names(d, f"{MACULA_BACK.get(b, b)}.{c}.{v}", text, {eid})})
    who = _who(e)
    if not (who or kin or quote):
        return None
    return {"who": who, "kin": [] if who else kin[:5], "quote": quote}


def person_kin(d, eid, e):
    """A person's family, as the face says it: each relation once, parents
    first, then children, spouses, siblings. The card-sections review
    (2026-10-13): Google's knowledge panel and Wikipedia's infobox both put
    parents, children and spouse at the top of a person, because those are
    the questions asked of a person -- and David's Kinship section sat five
    phone screens down, closed."""
    g = e.get("gender")
    kin, seen = [], set()
    for r in d["rels"].get(eid, []):
        o = d["ents"].get(r["other"]) or {}
        t, dr = r["type"], r["dir"]
        if t in ("father_of", "mother_of") and dr == "in":
            word = {"m": "son of", "f": "daughter of"}.get(g, "child of")
        elif t in ("son_of", "child_of") and dr == "out":
            word = {"m": "son of", "f": "daughter of"}.get(g, "child of")
        elif t == "spouse_of":
            word = {"m": "husband of", "f": "wife of"}.get(g, "spouse of")
        elif t in ("sibling_of", "half_sibling_of"):
            word = {"m": "brother of", "f": "sister of"}.get(g, "sibling of")
        elif t in ("father_of", "mother_of") and dr == "out":
            word = {"father_of": "father of", "mother_of": "mother of"}[t]
        else:
            continue
        if (word, r["other"]) in seen:
            continue
        seen.add((word, r["other"]))
        kin.append({"rel": word, "id": r["other"], "name": o.get("name") or r["other"]})
    order = ["son of", "daughter of", "child of", "father of", "mother of",
             "wife of", "husband of", "spouse of", "brother of", "sister of", "sibling of"]
    kin.sort(key=lambda k: order.index(k["rel"]))
    return kin


def concept_face(d, eid, e, words):
    """THE HUB'S TOP HALF BY RULE, for a concept card without a hub (plan
    7.6g; 2026-10-09: every concept card gets the hub's layout and look
    by rule). Two things the card did not have:

    - its key verses quoted ("In the texts' own words"), from the card's own
      references, as the hubs quote theirs;
    - the other words the English renders as this card's words do ("Other
      words translated the same way"), named apart with their verses -- the
      rule love's hub was given by hand (when it is clearly a
      different word the user should be informed). The English is the card's
      name and its words' own glosses; a word counts where that rendering is
      its usual one (10 verses, or a quarter of its uses), not a stray."""
    if eid in _FACES:
        return _FACES[eid]
    own = []
    # a people's card quotes more of its verses: the review of "the Jews" put
    # the text's plain statements first, the conflict after (2026-10-10)
    # eight, for any card: the review of "slaves" set the hard verses beside
    # the releases and protections, which four could not hold (2026-10-10)
    for r in (e.get("refs") or [])[:8]:
        # a range ("Matt 23:2-3", "John 11:47-48") is quoted whole; the parser
        # takes single verses, and ranges fell out unseen (2026-10-10)
        mr = re.match(r"^(.*?\d+):(\d+)-(\d+)$", r.strip())
        parts = [f"{mr.group(1)}:{n}" for n in range(int(mr.group(2)), int(mr.group(3)) + 1)] if mr else [r]
        try:
            got = [_verse_text(d, _macula_ref(d, p)) for p in parts[:4]]
        except Exception:
            continue
        eref = got[0][0] if got else ""
        text = " ".join(t for _e, t in got if t)
        if text:
            b, c, v = eref.split(".")
            # the names each verse of the range resolves, found in the whole
            names = {}
            for ge, gt in got:
                for n in verse_names(d, ge, gt, {eid}):
                    names.setdefault(n["at"], n)
            own.append({"id": f"{MACULA_BACK.get(b, b)}.{c}.{v}", "ref": r, "text": text,
                        "names": list(names.values())})
    want = _gtokens(e.get("name"))
    for w in words:
        want |= _gtokens(re.split(r"[:;,(]", w.get("gloss") or "")[0])
    mine = {w["key"] for w in words}
    # THE SAME WORD IN ANOTHER FORM IS NOT ANOTHER WORD (2026-10-09, on
    # righteousness: if righteous is the adjective form of the same word, it
    # does not need the same treatment): one derivation step from the
    # card's words, by the links trusted to bridge verses (KIN_BRIDGES), is
    # its family -- ἐλεέω beside ἔλεος -- shown with the words, never as
    # "other words". Two steps was tried: it reached λανθάνω "be hidden" from
    # truth and φρήν "thinking" from humility, through etymology and
    # compounds (2026-10-09)
    fam = {k.lower() for f in mine for k, how in _families().get(f.lower(), []) if how in KIN_BRIDGES}
    # the lexicon's links miss some (ταπεινόω beside ταπεινοφροσύνη, ἀληθεύω
    # beside ἀλήθεια), so for Greek the spelling too: a word holding the
    # first four letters of a card word, accents aside. Not for Hebrew, where
    # three-letter roots meet by chance (עָנָה "humble", עָנָה "answer")
    def bare(x):
        return "".join(ch for ch in unicodedata.normalize("NFD", x or "") if not unicodedata.combining(ch)).lower()
    stems = {bare(w.get("lemma"))[:4] for w in words if (w.get("key") or "").startswith("g") and len(bare(w.get("lemma"))) >= 5}
    fam -= {k.lower() for k in mine}
    vo = _verses_of(d)
    family = []
    for k in fam:
        n = len(vo.get(k, ()))
        if n:
            lemma, gloss = _word_label(d, k)
            family.append({"key": k, "lemma": lemma, "gloss": gloss, "uses": n})
    family.sort(key=lambda x: -x["uses"])
    ix = _gloss_ix(d)
    cand = {}
    for t in want:
        for k, (n, tot) in ix.get(t, {}).items():
            if k in mine or k.lower() in fam:
                continue
            if k.startswith("g") and any(s in bare(d["lemmas"].get(k)) for s in stems):
                fam.add(k.lower())
                lemma, gloss = _word_label(d, k)
                family.append({"key": k, "lemma": lemma, "gloss": gloss, "uses": len(vo.get(k, ()))})
                continue
            m = cand.get(k, (0, tot))
            cand[k] = (max(m[0], n), tot)
    others = []
    # a card that names its own words was chosen by hand; the gloss rule,
    # word by word, would set "chief" (אַלּוּף, the chiefs of Edom) beside "the
    # chief priests" and "son" beside "the sons of Israel"
    for k, (n, tot) in ([] if e.get("words") else sorted(cand.items(), key=lambda x: -x[1][0])):
        if n < 10 and n < 0.25 * tot:
            continue
        rows, _n = occurrences(d, k, cap=10 ** 6)
        refs = []
        for r in rows:
            if _gtokens(r.get("gloss")) & want:
                b, c, v = bsb_ref(d, r["ref"]).split(".")
                vid = f"{MACULA_BACK.get(b, b)}.{c}.{v}"
                if vid not in refs:
                    refs.append(vid)
        if not refs:
            continue
        lx = d["lex"].get(k) or {}
        meta = d["lmeta"].get(k) or {}
        others.append({"key": k, "lemma": d["lemmas"].get(k) or lx.get("word"),
                       "translit": lx.get("translit") or _first(meta, "transliteration"),
                       "gloss": lx.get("gloss") or (d["profiles"].get(k) or {}).get("gloss"),
                       "lang": "Hebrew" if k.startswith("h") else "Greek", "n": len(refs), "verses": refs[:40]})
        if len(others) >= 12:
            break
    # a card with no words of its own (a people: "the Jews") shows the words
    # its English renders as its words -- they are its words, not "others"
    if not words and others:
        # counted as every word card counts: all its verses (Ἰουδαῖος 185, the
        # note's figure), not only those rendered as the card's name (157)
        for o in others:
            o["uses"] = len(vo.get(o["key"].lower(), ())) or len(vo.get(o["key"], ())) or o["n"]
        _FACES[eid] = {"own_words": own, "others": [], "family": [], "words": others}
        return _FACES[eid]
    _FACES[eid] = {"own_words": own, "others": others, "family": family[:8]}
    return _FACES[eid]


_VMARKS = None


def verse_marks(b, c, v):
    """WHAT THE PAGE SAYS AT THE VERSE BESIDE THE BEREAN'S WORDS (2026-10-08).
    Two kinds, both shown with the verse wherever it is shown, never
    changing its words:

    - "ms": the Berean's own footnotes on the manuscripts (out/manuscript-
      notes.json, tools/manuscript_notes.py). Of Mark 16:16 in a theme
      outline (2026-10): mark it site-wide -- the longer ending of Mark and John
      7:53-8:11 carry the Berean's note that the earliest manuscripts lack
      them, on every verse.
    - "find": where the original reads otherwise at a word that matters
      (ontology/translation-findings.json), marked at the word. The rule: keep
      the Berean's words, but make the note clearly marked, with an
      asterisk or equivalent right in the verse, for consistency in
      using a translation while communicating our findings.

    None when the verse has neither, so most replies carry nothing extra."""
    global _VMARKS
    if _VMARKS is None:
        _VMARKS = {}
        p = OUT / "manuscript-notes.json"
        if p.exists():
            for k, notes in json.loads(p.read_text(encoding="utf-8"))["notes"].items():
                _VMARKS.setdefault(k, {})["ms"] = notes
        p = ROOT / "ontology" / "translation-findings.json"
        if p.exists():
            for f in json.loads(p.read_text(encoding="utf-8"))["findings"]:
                _VMARKS.setdefault(f["ref"], {}).setdefault("find", []).append(
                    {k: f[k] for k in ("word", "lemma", "gloss", "note")})
    return _VMARKS.get(f"{b}.{c}.{v}")


def _verse_text(d, ref):
    eref = bsb_ref(d, ref)
    try:
        b, c, v = eref.split(".")
        return eref, d["verses"].get((MACULA_BACK.get(b, b), int(c), int(v))) or ""
    except (ValueError, TypeError):
        return eref, ""


def mined_examples(d, pid, n=6, skip=None):
    """The strongest showing of a finding in a few verses, text included.
    2026-09-28: the strong examples of each pattern are shown directly
    on the pattern page, since it was too hard to navigate to them. One verse per book, both testaments where it has both,
    canon order; `skip` leaves out the verse the reader came from."""
    inst = [x["ref"] for x in d["mined"]["inst"].get(pid, [])
            if x["ref"] != skip]
    by_t = {"OT": [], "NT": []}
    seen = set()
    for r in sorted(inst, key=lambda x: (_MCANON.get(x.split(".")[0], 99),
                                         [int(k) for k in x.split(".")[1:]])):
        b = r.split(".")[0]
        if b in seen:
            continue
        seen.add(b)
        by_t["NT" if _MCANON.get(b, 0) >= 39 else "OT"].append(r)
    half = max(1, n // 2)
    pick = by_t["OT"][:half] + by_t["NT"][:half]
    pick += [r for r in by_t["OT"] + by_t["NT"] if r not in pick][:n - len(pick)]
    pick.sort(key=lambda x: (_MCANON.get(x.split(".")[0], 99),
                             [int(k) for k in x.split(".")[1:]]))
    out = []
    for r in pick[:n]:
        eref, text = _verse_text(d, r)
        out.append({"ref": r, "eref": eref, "text": text})
    return out


def _mined_brief(d, pid, via=None, skip=None, examples=0):
    r = d["mined"]["rows"].get(pid)
    if not r:
        return None
    tier, why = mined_tier(r)
    out = {"key": "m:" + pid, "template": r["pattern"], "kind": r["kind"],
           "instances": r["accounts"], "tier": tier, "why": why,
           "testaments": r["testaments"], "books": r["books"],
           "via": via, "score": r["score"]}
    if examples:
        out["examples"] = mined_examples(d, pid, examples, skip)
    return out


def _homographs(d):
    """Word keys that share their letters (vowels and accents aside) with
    another word of the same language: נַעַר "boy" and נֹעַר "youth"."""
    got = d.get("_homographs")
    if got is None:
        import unicodedata
        by = collections.defaultdict(set)
        for k, lem in d["lemmas"].items():
            s = "".join(ch for ch in unicodedata.normalize("NFD", lem or "")
                        if unicodedata.category(ch)[0] == "L").lower()
            if s:
                by[(k[:1], s)].add(k)
        got = d["_homographs"] = {k for ks in by.values() if len(ks) > 1 for k in ks}
    return got


def mined_for(d, node, examples=2):
    """A node's patterns, sure ones first, each with its tier, in the
    index's own order (interest for this node, not the list score, which
    carries frequency), each with a few example verses to read in place."""
    skip = node[6:] if node.startswith("verse:") else None
    # A WORD'S PATTERN HAS THE WORD IN IT. The miner names a word by its
    # consonants and then gives the pattern to every Strong's number spelled
    # so, so נֹעַר "youth" listed the patterns of נַעַר "boy" (2026-10-03). Through "its word", a pattern is this word's only where the
    # word stands in one of the pattern's instances; through a similar word
    # it never does, and is left alone. ONLY FOR A HOMOGRAPH: applied to
    # every word, the test dropped 10,247 of 18,850 links, because a part
    # matched by meaning ("≈heard") lets an instance use another word for it
    # -- those are the word's patterns too. The bug is two words one spelling
    mine_vs = _verses_of(d).get(node[6:], set()) \
        if node.startswith("sense:") and node[6:] in _homographs(d) else None
    out = []
    for p in d["mined"]["index"].get(node, []):
        if mine_vs is not None and str(p.get("via") or "").startswith("its word") and not any(
                x["ref"] in mine_vs for x in d["mined"]["inst"].get(p["id"], [])):
            continue
        b = _mined_brief(d, p["id"], p.get("via"), skip, examples)
        if b:
            b["score"] = p["score"]
            out.append(b)
    out.sort(key=lambda b: (b["tier"] != "sure", -b["score"]))
    return out


def _rows(path):
    """Every record in a jsonl(.gz), skipping the provenance header.

    Returns [] when the file is absent: these layers are built by separate
    tools and a reader should lose one category rather than the whole app.
    """
    if not path.exists():
        return []
    op = gzip.open if path.suffix == ".gz" else open
    out = []
    with op(path, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith('{"_'):
                continue
            d = json.loads(line)
            if not any(k.startswith("_") for k in d):
                out.append(d)
    return out


def sense_key(lang, strong):
    s = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", strong or ""))
    return ((lang or "")[:1] + s) if s else None


def _letters(s):
    """A word's letters alone: accents, breathings and points gone, final sigma medial."""
    s = unicodedata.normalize("NFD", s or "")
    return "".join(ch for ch in s if unicodedata.category(ch)[0] == "L").lower().replace("ς", "σ")


def _translit_head(word):
    """The transliteration of a headword this file chose itself, in STEP's convention
    beside it (υ as u): tools/interlinear.py's scheme, which strips breathings, with
    the rough one put back (ἱερόν hieron, ῥαφίς rhaphis)."""
    if str(ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(ROOT / "tools"))
    from interlinear import translit_greek
    first = word.split(",")[0].strip()
    t = translit_greek(first).replace("y", "u")
    if "̔" in unicodedata.normalize("NFD", first[:2]):
        t = ("rh" + t[1:]) if t[:1] == "r" else ("h" + t)
    return t[:1].upper() + t[1:] if first[:1].isupper() else t


def headwords(common, lemmas, lex):
    """Which form heads a word card, and the other form listed beside it (2026-10-27).

    A card is a Strong's number and was headed by the FIRST lemma MACULA gives
    any of its uses, which is not always the word: G689 (Aram) was headed ἀδμίν
    from one stray use, G5179 (type) τυπικώς; 13 Greek cards and 202 Hebrew ones.
    `common` is the commonest lemma under the number, its own uses first (a
    Hebrew letter code, 2050c "his", is MACULA's pronoun suffix or particle
    filed under the number, and the card key drops the letter): H1886 is headed
    Dothan again, not the suffix ה.

    And MACULA files several Greek numbers under one dictionary form: G2411 (the
    temple, 71 uses) and G2413 (sacred, 3) are both ἱερός, so the temple's card
    showed the adjective while its Strong's entry is the noun ἱερόν (found by a
    reader, 2026-10-27). Where the lemma is shared by another number it cannot
    tell the cards apart, and the number's own form (STEP's headword) leads:
    ἱερόν, μόνον, πρῶτον, φαγεῖν, Ἱερουσαλήμ. Elsewhere MACULA's lemma keeps
    the lead, since Strong's prints active forms the New Testament never uses
    (ἀποκρίνω for ἀποκρίνομαι), and where the letters differ the other form is
    listed. Hebrew gets the commonest lemma only: until its suffixes are parted
    from the words they are filed under, STEP's headword and the card's uses
    name different words (tools/audit_headwords.py counts them).

    {key: {"lemma", "translit" (only when STEP's form leads), "also": {"form", "source", "with"}}}
    """
    owners = collections.defaultdict(list)
    for k, lem in common.items():
        if k[:1] == "g":
            owners[unicodedata.normalize("NFC", lem)].append(k)
    out = {}
    for k, lem in common.items():
        if lem != lemmas.get(k):
            # the transliteration goes with the lead: the uses' own was the
            # stray's ("ha" under Dothan), so STEP's where its headword is this
            # word, generated for Greek, and none rather than another word's
            lx = lex.get(k) or {}
            out[k] = {"lemma": lem, "translit": (
                _translit_head(lem) if k[:1] == "g"
                else lx.get("translit") if _letters(lx.get("word") or "") == _letters(lem) else "")}
        step = " ".join(((lex.get(k) or {}).get("word") or "").split())
        if k[:1] != "g" or not step:
            continue
        step = ", ".join(dict.fromkeys(x.strip() for x in re.split(r"[=,]", step) if x.strip()))
        mac = unicodedata.normalize("NFC", lem)
        if mac == unicodedata.normalize("NFC", step):
            continue
        shared = [o for o in owners[mac] if o != k]
        if shared:
            out[k] = {"lemma": step, "translit": _translit_head(step),
                      "also": {"form": lem, "source": "macula", "with": shared}}
        elif _letters(mac) != _letters(step):
            # MACULA Greek carries no transliteration, so the card's was STEP's,
            # of STEP's form ("apokrinō" under ἀποκρίνομαι): made from the lead
            out.setdefault(k, {}).update(translit=_translit_head(lem),
                                         also={"form": step, "source": "strongs"})
    return out


def _head(d, key, lemma, translit):
    """(lemma, translit, also) as a card shows them: headwords() over MACULA's."""
    h = (d.get("heads") or {}).get(key) or {}
    return (h.get("lemma") or lemma, h["translit"] if "translit" in h else translit, h.get("also"))


# ---------------------------------------------------------------- endpoints

def api_books(d, q):
    """Books, plus BOTH spellings of each, because citations arrive in two.

    The structural graph cites `Gen.1.1` and the legacy entities cite
    `1Chr 27:33`. A card links to a passage either way, so the client is handed
    the reverse map rather than left to guess at it.
    """
    return {"books": [{"id": b, "title": TITLE.get(b, b),
                       "macula": TO_MACULA.get(b, b),
                       "chapters": max(d["chapters"][b])}
                      for b in ORDER if d["chapters"].get(b)]}


def _ptree(d, ref):
    """A verse's word-group tree, unpacked from its compressed line (load())."""
    import zlib
    z = d["ptree"].get(ref.upper())
    return json.loads(zlib.decompress(z)) if z else {}


def api_chapter(d, q):
    b = qbook(d, q)
    c = qchapter(d, q, b)
    rows = []
    # Chapter-bounded, deliberately. 36% of BSB sections run past their
    # chapter's end, and the first fix was to extend the load to whole
    # sections -- no heroics: boxes may span two tabs,
    # with the bottom or top borderless and some kind of continuation
    # indicator. A box drawn open at the edge says the same thing and costs
    # no payload: Genesis's phrase trees alone are 4.5 MB.
    span = [(b, c, n) for n in
            sorted(n for (bb, cc, n) in d["verses"] if bb == b and cc == c)]
    for (_b, vc, v) in span:
        text = d["verses"][(b, vc, v)]
        # WHICH HEBREW VERSE. The per-chapter shift (macula_ref) cannot say
        # that BSB Exodus 8:1-4 are Hebrew 7:26-29 — it produced "Exo.8.-3",
        # and those verses had no original at all. The per-verse map fixes 90
        # verses the shift got wrong; it has gaps at 7 the shift gets right
        # (Lev 6:24-25, Isa 9:21, Jer 9:26, Dan 4:35-37). So: the map, and the
        # shift only where the map's verse has no original and the shift's
        # does. Measured 2026-09-25 over all 31,102 verses: verses with no
        # original 152 -> 62.
        shifted, mapped = macula_ref(b, vc, v), hebrew_ref(b, vc, v)
        ref = mapped if (mapped in d["orig"] or shifted not in d["orig"]) \
            else shifted
        # and the BERean's own headings are keyed in the Berean numbering:
        # looked up by the Hebrew verse, "The Third Plague: Gnats" (BSB 8:16)
        # appeared above 8:20
        eng = f"{TO_MACULA.get(b, b)}.{vc}.{v}"
        # The original-language strip travels with the verse. It is the whole
        # of what "show me the mapping" needs: the words in THEIR order, each
        # with the gloss it carries. Hebrew puts the verb first and English
        # does not, and seeing that is most of what looking at the original
        # gives a reader who does not read it.
        starts = [d["sents"][i] for i in d["sent_by_verse"].get(ref, [])
                  if i in d["sents"] and d["sents"][i]["ref"] == ref]
        cont = [i for i in d["sent_by_verse"].get(ref, [])
                if i in d["sents"] and d["sents"][i]["ref"] != ref]
        sm = d.get("seams", {}).get(eng) or \
            d.get("seams_heb", {}).get(ref)
        at = d.get("attach", {}).get(ref) or {}
        rows.append({"v": v, "c": vc, "ref": ref, "text": text,
                     # the Berean's manuscript note and our findings at
                     # the word (verse_marks)
                     "vmarks": verse_marks(b, vc, v),
                     # the Hebrew verse, by the per-verse map, for the
                     # original panel's header only
                     "heb": ref,
                     # whether the connections chip has anything behind it
                     "conn": ref in connected(d),
                     "attach": ({"rel": at.get("rel"), "sub": at.get("sub")}
                                if at.get("dir") == "backward" else None),
                     "seam": ({"by": sm["by"], "why": sm.get("why") or [],
                               "title": sm.get("title"),
                               "agree": sm.get("agree", 0)} if sm else None),
                     # a sentence STARTING here owns the structure; a verse that
                     # merely continues one shows a marker instead, so the same
                     # diagram is not drawn three times
                     "sentences": [{"id": s["id"], "verses": s["verses"],
                                    "spans": s["spans"], "words": s["words"]}
                                   for s in starts],
                     "continues": cont,
                     "marks": marks_for(d, b, vc, v, text),
                     # what the derived layers say about this verse; empty for
                     # a verse no layer reached, which is itself informative
                     "layers": d.get("layers", {}).get(ref) or None,
                     "orig": [w for w in d["orig"].get(ref, [])
                              if w.get("t") or w.get("g")],
                     "rtl": TO_MACULA.get(b, b) in HEBREW_BOOKS,
                     # the word-group tree: nested boxes on the right, and the
                     # maximal non-predicating phrases the left column links
                     "tree": (pt := _ptree(d, ref)).get("trees"),
                     "links": pt.get("links"),
                     "structured": bool(d["byref"].get(ref))})
    # Does a section cross either edge of this chapter? The renderer draws
    # those boxes open -- borderless at the edge, with a continuation mark --
    # rather than pretending the unit ends where the chapter does.
    starts = d.get("secstart", {}).get(b, [])
    opens_before = bool(starts and span
                        and (c, span[0][2]) not in starts
                        and any(s < (c, span[0][2]) for s in starts))
    runs_past = bool(starts and span
                     and not any(s[0] == c + 1 and s[1] == 1 for s in starts)
                     and any(s > (c, span[-1][2]) for s in starts))
    return {"book": b, "title": TITLE.get(b, b), "chapter": c,
            "continues": {"before": opens_before, "after": runs_past},
            "theme_spans": theme_spans(b, c, [v for (_b, _c, v) in span]),
            # the story patterns whose stages fall in this chapter (plan A.9)
            "story_spans": story_spans(b, c),
            # the divine messages spoken in it, verse by verse
            "messages_at": messages_at(b, c),
            # and the speech acts the text names in it (A.18)
            "acts_at": acts_at(b, c),
            # NO STAMP CHIPS ON THE READING SCREEN. 2026-09-28: it was
            # hard to understand what all the verses behind a chip had to do with
            # it, and many did not make sense; the chips were removed from the
            # general reader screen and made clickable on
            # the clause level. They were the 14 September SECTION stamps
            # (devices, reversals, parables ...), never pinned to a clause; a
            # stamp now appears only on the clauses it is pinned to, in the
            # structure view, and opens its own page (api_tag).
            "chapters": max(d["chapters"].get(b, {1})), "verses": rows}


def api_unit(d, q):
    """Nodes and edges for one unit.

    Takes a REF and nothing else. It does not know whether that names a verse,
    a sentence or -- when grouping above the sentence lands -- a speech or a
    scroll, which is what keeps the viewer level-agnostic.
    """
    ref = (q.get("ref") or [""])[0]
    # A sentence id looks like `Gen.1.1#1`. The endpoint takes a ref and does
    # not care what kind of unit it names -- which is the whole point of the
    # contract, and why the sentence layer is a new query and not a rewrite.
    sent = d["sents"].get(ref)
    if sent:
        edges = [e for v in sent["verses"] for e in d["byref"].get(v, [])]
    else:
        edges = d["byref"].get(ref, [])
    ids = set()
    for e in edges:
        for side in ("src", "dst"):
            if isinstance(e.get(side), str):
                ids.add(e[side])
        rel = e.get("dst_relation") or {}
        for side in ("src", "dst"):
            if isinstance(rel.get(side), str):
                ids.add(rel[side])
    # Patterns keyed by TEMPLATE, so the diagram can mark the specific event
    # that instantiates one rather than listing them loosely beneath the verse.
    # Only those clearing the surprise gate: a verb with objects is not a
    # pattern and marking it as one is noise.
    here = {}
    for e in edges:
        verb = _slug(e.get("verb") or e.get("type"))
        if not verb:
            continue
        if e.get("scopes_over"):
            tm = f"[S] {verb} {_slug(e.get('type'))} [X]"
        elif isinstance(e.get("dst"), str):
            tm = f"[S] {verb} [O]"
        else:
            tm = f"[S] {verb}"
        r = d["pat_by_tmpl"].get(tm)
        if r and r.get("distinctive"):
            here[tm] = {"key": r["key"], "kind": r["kind"],
                        "instances": r["instances"], "lift": r["lift"],
                        "top": r["top_filler"]}
    return {"ref": ref, "patterns": here,
            "sentence": ({"id": sent["id"], "verses": sent["verses"],
                          "words": sent["words"]} if sent else None),
            "nodes": [d["nodes"][i] for i in ids if i in d["nodes"]],
            "edges": [{k: v for k, v in e.items() if k != "lang"}
                      for e in edges],
            "structural": sorted(STRUCTURAL)}


def api_sense(d, q):
    """The word card, with the patterns the word takes part in (2026-09-28:
    what are the most interesting patterns it participates
    in?). The card itself is _api_sense, which has several return paths."""
    out = _api_sense(d, q)
    if out.get("found") and out.get("key"):
        out["mined"] = mined_for(d, f"sense:{out['key'].lower()}")
        out["family"] = family_of(d, out["key"].lower())      # plan 5.10
        out["concepts"] = concepts_of_word(d, out["key"].lower())
        out["note"] = word_notes().get(out["key"].lower())
        _word_card_extras(d, out)
    return out


# STEP's two brief lexicons, credited in the licence's words (CC BY 4.0, "Credit
# it to 'STEP Bible' linked to www.STEPBible.org") with the work each is
# based on, as their own field notes name it.
LEXICON_EDITED = ("Edited here: the renderings of the King James (Authorised) Version "
                  "and STEP's pointers to its own other entries are left out.")
LEXICON_CREDIT = {
    "hebrew": "STEP Bible's Translators Brief lexicon (Tyndale House, Cambridge), "
              "CC BY 4.0, based on the abridged Brown-Driver-Briggs of the Online "
              "Bible (© Larry Pierce). " + LEXICON_EDITED,
    "greek": "STEP Bible's Translators Brief lexicon (Tyndale House, Cambridge), "
             "CC BY 4.0, based on Abbott-Smith's Manual Greek Lexicon of the New "
             "Testament (1922). " + LEXICON_EDITED,
}


def renderings_of(d, key, per=150):
    """How the Berean renders the word, summed: each English the text puts for
    it with how many times, commonest first, and the verses of each in
    canonical order. Counted over every use the occurrence index holds (not
    over verses: a verse with the word twice counts twice), so the counts sum
    to `total` by construction; `total` is stated beside the card's own count
    of uses (observations), because the index is sparser than the interlinear
    for particles and a few verbs, and the card says so rather than rounding.

    2026-10-26: no card added the renderings up. The rows carried them
    (אהב: love 87, loved 39, loves 37, lovers 16, friends 6 ...) and a reader
    had to count.
    """
    lang = "hebrew" if (key or "").startswith("h") else "greek"
    n, shapes = collections.Counter(), collections.defaultdict(collections.Counter)
    refs, seen = collections.defaultdict(list), collections.defaultdict(set)
    for ref, g in d["occ"].get(key, []):
        g = (g or "").strip()
        if not g:
            continue
        low = g.lower()
        n[low] += 1
        shapes[low][g] += 1
        ref = _where(d, key, ref, lang)
        if ref not in seen[low]:
            seen[low].add(ref)
            refs[low].append(ref)
    rows = []
    for low in sorted(n, key=lambda x: (-n[x], x)):
        sh = shapes[low]
        # a name keeps its capital ("Beor"); "silent" is not "Silent"
        shown = low if sh.get(low, 0) * 2 >= sum(sh.values()) else sh.most_common(1)[0][0]
        rs = sorted(refs[low], key=_vkey_macula)
        rows.append({"gloss": shown, "n": n[low], "verses": len(rs), "refs": rs[:per]})
    return {"rows": rows, "total": sum(n.values()), "per": per}


_WORD_REGISTER = None


def _register(d):
    """ontology/word-families.json, resolved to word keys: the words the site
    has grouped by hand under a theme (love, grace, faith ...), each lemma
    matched to the key the interlinear gives it. {key: [family ids]} and
    {family id: (name, [keys])}. A lemma that stands for more than one key
    (homographs) is taken as the key holding at least four in five of its
    uses; otherwise it is left out, never guessed."""
    global _WORD_REGISTER
    if _WORD_REGISTER is not None:
        return _WORD_REGISTER
    p = ROOT / "ontology" / "word-families.json"
    fams = json.loads(p.read_text(encoding="utf-8")).get("families") or [] if p.exists() else []
    ix = collections.defaultdict(collections.Counter)
    for ref, ws in (d.get("orig") or {}).items():
        side = "g" if ref.split(".")[0] in _NT_BOOKS else "h"
        for w in ws or ():
            s, lem = re.sub(r"\D", "", str(w.get("s") or "")), w.get("l")
            if s and lem:
                ix[(side, unicodedata.normalize("NFC", lem))][side + str(int(s))] += 1
    by_key, by_fam = collections.defaultdict(list), {}
    for f in fams:
        members = []
        for side, field in (("g", "greek"), ("h", "hebrew")):
            for lem in (f.get(field) or {}):
                c = ix.get((side, unicodedata.normalize("NFC", lem))) or {}
                # the register counts a lemma's uses (אַהֲבָה 35); MACULA tags
                # three of them under another number (h157), so the word is
                # the number that holds the great majority, or none
                top = max(c, key=c.get) if c else None
                if top and c[top] >= 0.8 * sum(c.values()):
                    members.append(top)
        by_fam[f["id"]] = (f["name"], members)
        for k in members:
            by_key[k].append(f["id"])
    _WORD_REGISTER = (by_key, by_fam)
    return _WORD_REGISTER


def grouped_with(d, key):
    """The site's own groupings that hold this word: for each, the other words
    in it. A grouping made by hand to find passages by their words, not a
    claim that the words share a root (the register says so itself)."""
    by_key, by_fam = _register(d)
    out = []
    for fid in by_key.get(key, ()):
        name, members = by_fam[fid]
        rows = []
        for k in members:
            if k == key:
                continue
            lemma, gloss = _word_label(d, k)
            rows.append({"key": k, "lemma": lemma, "gloss": gloss,
                         "uses": len(_verses_of(d).get(k, ()))})
        rows.sort(key=lambda r: (-r["uses"], r["key"]))
        out.append({"id": fid, "name": name, "members": rows})
    return out


def _word_card_extras(d, out):
    """What every word card carries whichever path built it (_api_sense has
    four, and the verb path built no verse list, no Septuagint row and no
    lexicon entry): the lexicon entry whole with its credit, the Berean's
    renderings summed, the word's groupings, and its verses in canonical
    order."""
    key = out["key"].lower()
    lx = d["lex"].get(key) or {}
    if not out.get("definition"):
        out["definition"] = lx.get("definition") or None
    if not out.get("short"):
        out["short"] = lx.get("gloss") or None
    out["definition_credit"] = (LEXICON_CREDIT["hebrew" if key[:1] == "h" else "greek"]
                                if out["definition"] else None)
    if "occurrences" not in out:
        out["occurrences"] = _occ_payload(d, key)
    if "equiv" not in out:
        out["equiv"] = _equivalents(d, key)
    if not out.get("lxx"):
        out["lxx"] = lxx_of(d, key)
    out["renderings"] = renderings_of(d, key)
    out["grouped"] = grouped_with(d, key)


_WORD_NOTES = None


def word_notes():
    """A word page's note in the site's voice, where how a word is used needs
    saying before its verses (ontology/word-notes.json; first: the words for
    "Jew", from the review of the card "the Jews", 2026-10-10). Each note is
    reviewed as all site-voice prose is."""
    global _WORD_NOTES
    if _WORD_NOTES is None:
        p = ROOT / "ontology" / "word-notes.json"
        raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        _WORD_NOTES = {k.lower(): v for k, v in raw.items() if not k.startswith("_")}
    return _WORD_NOTES


_WORD_CONCEPTS = None


def concepts_of_word(d, key):
    """THE BRIDGE FROM A WORD TO ITS CONCEPT (2026-10-09: a
    natural bridge from the language card to the concept card, as the concept
    card is far richer; of love, this is the love hub). The concept
    cards that list this word among "the words the text uses for this", by
    the same two rules the concept card uses (api_entity): a concept named as
    the word is glossed ("love" for ἀγάπη), and a concept whose own verses
    hold the word (_anchors). Named matches first."""
    global _WORD_CONCEPTS
    if _WORD_CONCEPTS is None:
        by_name = collections.defaultdict(list)
        for eid, e in d["ents"].items():
            if e.get("type") == "concept" and not str(eid).startswith("theme_"):
                for nm in [e.get("name")] + list(e.get("aka") or []):
                    if _slug(nm):
                        by_name[_slug(nm)].append(eid)
        ix = collections.defaultdict(list)
        for k, prof in d["profiles"].items():
            # "to love" is love, as on the concept card
            for eid in by_name.get(_slug(re.sub(r"^to\s+", "", prof.get("gloss") or "")), ()):
                if eid not in ix[k]:
                    ix[k].append(eid)
        vs = _verses_of(d)
        for eid, anchors in _anchors().items():
            e = d["ents"].get(eid) or {}
            if e.get("type") != "concept" or str(eid).startswith("theme_") or not e.get("refs"):
                continue
            own = {_macula_ref(d, r) for r in e["refs"]}
            for k, _s in anchors:
                if vs.get(k, set()) & own and eid not in ix[k]:
                    ix[k].append(eid)
        _WORD_CONCEPTS = ix
    return [{"id": eid, "name": d["ents"][eid].get("name") or eid}
            for eid in _WORD_CONCEPTS.get(key, [])[:4] if eid in d["ents"]]


def _api_sense(d, q):
    """The card for a word: what the text does with it, with citations."""
    key = (q.get("key") or [""])[0]
    if not key and q.get("strong"):
        key = sense_key((q.get("lang") or ["hebrew"])[0], q["strong"][0])
    prof = d["profiles"].get(key)
    if not prof:
        # A verb has no sense profile -- `tools/senses.py` profiled NOMINAL
        # lemmas, so every event verb in the corpus fell through here and
        # returned `found: False`. It is not missing: it has 26,018 events and
        # a verb class, and those are the whole card for a verb.
        return _verb_card(d, key)
    # The surface must never show the machinery's vocabulary. `ofhead:israel`
    # on `god` is the phrase "God of Israel"; say that, not the feature name.
    word = (prof.get("gloss") or "").lower()
    feats = []
    for f in prof["top"][:14]:
        tag, _, rest = f["feature"].partition(":")
        # the feature names carry underscores ("possessed_by"): printed as
        # "possessed_bys" on the page of אֵד (2026-10-26); never the machinery's
        rest = rest.replace("_", " ")
        if tag == "coord":
            says, quote = "stands beside", rest
        elif tag == "objof":
            says, quote = "is what someone", rest
        elif tag == "subjof":
            # ONLY A BARE VERB TAKES THE -S. This appended it unconditionally,
            # which is right for "cast" -> "is what casts" and wrong for
            # everything else: "having" -> "is what havings", and any partner
            # that is already a phrase -- "will inherit" -> "will inherits".
            # 2026-09-15, listing what the card printed: "havings · 2×".
            one = " " not in rest.strip()
            # AND NOT A PAST FORM: "issued" + "s" was printed "issueds" (3x, on
            # the page of the Aramaic טְעֵם, 2026-10-26). A word ending -ed is
            # left as it is, but for the bases that end so ("feed" -> "feeds").
            past = rest.endswith("ed") and rest not in (
                "need", "feed", "bleed", "heed", "seed", "speed", "plead", "breed",
                "weed", "exceed", "proceed", "succeed", "shed")
            quote = (rest + "s") if (one and not past and not rest.endswith(("s", "ing")))\
                else rest
            says = "is what"
        elif tag == "ofhead":
            # DO NOT INVENT THE CONNECTOR. This read `f"{word} of {rest}"`, so
            # every construct on the word card was rendered with "of" whatever
            # what the text does. 2026-09-19, drilling into `declares the [X]`:
            # "declares of lord" on the card against "declares the LORD" in
            # the verse and in the pattern list.
            #
            # `tools/clausepatterns.py` already learned this and reads the
            # connector off the Berean text, but it can only verify 7 of 920
            # construct templates — and ALL SEVEN turn out not to be "of".
            # So "of" is wrong often and demonstrably, and the honest move is
            # to stop asserting it rather than guess a replacement.
            says, quote = "in the phrase", _construct(d, word, rest)
        elif tag == "ofdep":
            says, quote = "in the phrase", _construct(d, rest, word)
        elif tag == "simile":
            says, quote = "is used as an image", ""
        else:
            says, quote = tag, rest
        if rest.strip().lower() in NOISE_PARTNERS:
            continue
        feats.append({"kind": tag, "says": says, "with": quote,
                      "quoted": tag in ("ofhead", "ofdep"),
                      "count": f["count"], "weight": f["weight"],
                      "refs": f["refs"]})
    lx = d["lex"].get(key, {})
    lemma, translit, also = _head(d, key, d["lemmas"].get(key) or lx.get("word"),
                                  top_of(d, key, "transliteration") or lx.get("translit"))
    return {"key": key, "found": True, "gloss": prof.get("gloss"),
            "observations": _uses(d, key),
            "lemma": lemma, "lemma_also": also,
            "strong": key[1:],
            "lang": _lang_of(d, key),
            "translit": translit,
            "grammar": grammar_of(d, key),
            "lxx": lxx_of(d, key),
            "loan": (d.get("loans") or {}).get(key) or None,
            # Node-shaped, so the card can show them the way the reader shows
            # any word: original, phonetic, English, and clickable.
            "equiv": _equivalents(d, key),
            "pos": lx.get("pos"),
            "short": lx.get("gloss"), "definition": lx.get("definition"),
            # Refs only; the verse arrives from /api/sense-verse on click.
            "occurrences": _occ_payload(d, key),
            "features": feats,
            "neighbours": neighbours(d, key),
            "acts": acts_of(d, key),
            "verb_class": class_of(d, key),
            "contrasts": [c for c in d["contrasts"].get(word, [])][:8]}


def _consonants(w):
    """A Hebrew or Aramaic word's consonants alone (pointing stripped, final
    forms folded), as tools/equivalents.py compares them."""
    n = "".join(c for c in unicodedata.normalize("NFD", w or "") if not unicodedata.combining(c))
    return re.sub(r"[^א-ת]", "", n.translate(str.maketrans("ךםןףץ", "כמנפצ")))


def _equivalents(d, key):
    """The same word in the Bible's other languages, as word nodes.

    2026-09-19: on the word page, the Greek chips carry the original,
    the phonetic and the English label, clickable for each word offered;
    Aramaic may be included if applicable, only if there is an equivalent
    usage in the Bible.

    **The two are different kinds of claim and are labelled as such.** `greek`
    is an ALIGNMENT: MACULA records the word the Septuagint used for this one,
    so it is a translator's decision preserved in the data. `aramaic` is a
    COGNATE: the Bible's Aramaic passages use a word with the same consonants,
    which is a fact about the spelling and not a translation of anything.
    Presenting them identically would make the weaker one look like the
    stronger.

    Aramaic comes only from the passages that ARE Aramaic, by
    constraint, so every word offered is one a reader can go and find.
    """
    if not key.startswith("h"):
        # THE BRIDGE READS BOTH WAYS. 2026-09-19: the Greek card
        # should reference the Hebrew just as the Hebrew references the
        # Greek. The Septuagint column is stored per Hebrew lexeme, so a
        # Hebrew card could answer "what Greek stands here" while a Greek card
        # answered nothing -- one alignment, legible from one end only.
        return {"greek": [], "aramaic": None,
                "hebrew": (d.get("hebfor") or {}).get(key) or []}
    forms = d.get("gforms") or {}
    # MATCH WITHOUT THE ACCENTS. The Septuagint column and the Greek New
    # Testament spell the same form differently often enough that an exact
    # lookup found nothing for λέγει or φησὶν, and the chips rendered with no
    # transliteration and no gloss — the two things asked for.
    fold = d.get("_gfold")
    if fold is None:
        fold = {}
        for k, v in forms.items():
            n = unicodedata.normalize("NFD", k)
            n = "".join(c for c in n if not unicodedata.combining(c)).lower()
            fold.setdefault(n, v)
        d["_gfold"] = fold

    def look(w):
        n = unicodedata.normalize("NFD", (w or "").strip(",.;·:"))
        n = "".join(c for c in n if not unicodedata.combining(c)).lower()
        return forms.get(w) or fold.get(n) or {}

    greek = []
    for x in lxx_of(d, key):
        w = x["word"]
        f = look(w)
        greek.append({"t": w, "x": f.get("x"), "g": f.get("g"),
                      "key": f.get("key") or x.get("key"), "n": x["n"]})
    a = (d.get("aramaic") or {}).get(key)
    # THE CLAIM IS "THE SAME CONSONANTS", so it is checked here. out/word-
    # equivalents.json keys a cognate by Strong's number, and one stray tag
    # (MACULA's lemma יהב under 157 at Hosea 4:18) gave אהב "love" the Aramaic
    # יהב "give", 28 uses, on its card and page (2026-10-26). A cognate whose
    # consonants are not the word's own is not shown.
    own = d["lemmas"].get(key) or (d["lex"].get(key) or {}).get("word")
    if a and own and _consonants(own) != _consonants(a.get("lemma")):
        a = None
    aram = None
    if a:
        aram = {"t": a.get("lemma"), "x": a.get("x"), "g": a.get("g"),
                "n": a.get("n"),
                # No sense card for an Aramaic lexeme: the profiles were built
                # over Hebrew and Greek. Offering a click that opens nothing
                # would be worse than offering none.
                "key": None}
    return {"greek": greek, "aramaic": aram, "hebrew": []}


def _construct(d, head, dep):
    """A construct phrase, WITHOUT inventing the word that joins it.

    This read `f"{head} of {dep}"`, so every construct on the word card was
    rendered with "of" whatever the text does. 2026-09-19, drilling into
    `declares the [X]`: the card said *"declares of lord"* while the verse and
    the pattern list both say "declares the LORD".

    "of" is wrong often and demonstrably. `tools/clausepatterns.py` reads the
    connector off the Berean text and can verify only 7 of 920 construct
    templates -- and ALL SEVEN turn out not to be "of".

    So the two words are shown as a pair, which claims the relation without
    claiming an English word the verse may not contain. The pattern list still
    shows the measured connector for the templates where it was verified,
    because there it was measured against those very instances.
    """
    # KEYING THE CONNECTOR ON THE HEAD WAS ALSO WRONG, and was tried first.
    # Borrowing the pattern layer's verified "the" gave `declares the lord`,
    # which is right, and `declares the balaam`, which is not: Numbers 24:3
    # reads "the oracle OF Balaam". One Hebrew construct, and the Berean text
    # joins it differently depending on how it renders the head — so the
    # connector belongs to the rendering, not to the word, and no table keyed
    # on the head can be correct for every dependent.
    #
    # This is the same fault one level down as the card naming a word by one
    # gloss, so it gets the same answer: do not assert English the verse may
    # not contain. The two words are shown as a pair. The pattern list still
    # carries the measured connector for the templates where it was verified,
    # because there it was measured against those instances.
    return f"{head} — {dep}"


def _lang_of(d, key):
    """Hebrew, Aramaic or Greek -- and Aramaic was never being said.

    2026-09-19, searching for "father": the first and third entries
    looked the same. They were not. The first is Hebrew אָב and the third is
    Aramaic אַב, and both said "Hebrew", so a page listing them looked like it
    was repeating itself instead of showing two languages.

    A lexeme is called Aramaic only when the Bible uses it ONLY in the Aramaic
    passages; a word the two languages share stays Hebrew, since claiming it
    for Aramaic would be the same mistake facing the other way.
    """
    if not key.startswith("h"):
        return "Greek"
    return "Aramaic" if key in (d.get("aramkeys") or {}) else "Hebrew"


def _uses(d, key):
    """How many times the word occurs in the text -- what "N uses" on a card
    says. It showed the sense profile's observations instead: the word's
    uses in the roles the profiler reads, so ἔρχομαι "come", 599 times in the
    text, read "55 uses", and 6,017 of 6,242 profiled words showed a number
    their own occurrence list contradicted (2026-10-03, on the monster
    Rahab: 10 uses, 6 verses). The profile's count stays the profile's.

    The occurrence index matches the interlinear for every content word
    (ἔρχομαι 635 and 635) but undercounts particles and prefixes (אֶל 4 of
    5,514), so the larger of the two is taken."""
    got = d.get("_inter_n")
    if got is None:
        got = collections.Counter()
        for ref, ws in (d.get("orig") or {}).items():
            g = ref.split(".")[0] in _NT_BOOKS
            for w in ws or ():
                s = re.sub(r"\D", "", str(w.get("s") or ""))
                if s:
                    got[("g" if g else "h") + str(int(s))] += 1
        d["_inter_n"] = got
    return max(len(d["occ"].get(key, ())), got.get(key, 0)) \
        or (d["profiles"].get(key) or {}).get("observations") or 0


_NT_BOOKS = set("Mat Mrk Luk Jhn Act Rom 1Co 2Co Gal Eph Php Col 1Th 2Th 1Ti 2Ti Tit Phm "
                "Heb Jas 1Pe 2Pe 1Jn 2Jn 3Jn Jud Rev".split())


def _text_gloss(d, key):
    """The word's commonest English in MACULA's own glosses, for a heading
    with nothing better. The lexicon's gloss is not on the live site (STEP's
    terms, docs/OPERATIONS.md), so a verb or a rare word showed its Hebrew and
    no English at all -- 2026-10-03, on אָלַם (no "speechless") and
    נֹעַר (no "youth")."""
    # counted without case, shown in the text's own (a name keeps its
    # capital: "Beor", not "beor"; "silent" is not "Silent" at a sentence head)
    c, form = collections.Counter(), collections.defaultdict(collections.Counter)
    for _r, t in d["occ"].get(key, ()):
        t = (t or "").strip()
        if t:
            c[t.lower()] += 1
            form[t.lower()][t] += 1
    if not c:
        return None
    best = c.most_common(1)[0][0]
    shapes = form[best]
    lower = shapes.get(best, 0)
    return best if lower * 2 >= sum(shapes.values()) else shapes.most_common(1)[0][0]


def _bare_card(d, key):
    """A card for a word with no profile, no acts and no verb class.

    2026-09-19, having gone looking for ἀββά: clicking on it from Romans
    in the reader did not resolve Abba.

    It did not, and nothing did: a word the sense layer never profiled returned
    `found: False`, and the client returns silently on that, so the click died
    without a sound. ἀββά has three occurrences, which is well under any
    profiling floor — but **every word in the text is in the text**, and a
    reader who clicks one is owed at least what it is and where it occurs.

    So this is the floor of the card stack rather than a special case for
    loanwords: lemma, transliteration, gloss, occurrences. Rare words are
    exactly the ones a reader is most likely to click and least likely to
    already know.
    """
    occ = _occ_payload(d, key)
    lex = d["lex"].get(key) or {}
    lemma = d["lemmas"].get(key) or lex.get("word")
    if not (occ.get("total") or lemma):
        return {"key": key, "found": False}
    loan = (d.get("loans") or {}).get(key) or {}
    lemma, translit, also = _head(d, key, lemma or loan.get("lemma"),
                                  top_of(d, key, "transliteration") or loan.get("x"))
    return {"key": key, "found": True, "kind": "bare",
            "gloss": loan.get("gloss") or lex.get("gloss") or _text_gloss(d, key),
            # The occurrence index is built for profiled words and is sparser
            # than the text: it found ἀββά once where the interlinear has it
            # three times. For an unprofiled word the interlinear IS the count,
            # so take whichever is larger rather than under-reporting a word
            # this card exists to describe.
            "observations": max(occ.get("total") or 0, loan.get("n") or 0)
            or None,
            "lemma": lemma, "lemma_also": also,
            "strong": key[1:],
            "lang": _lang_of(d, key),
            "translit": translit,
            "short": lex.get("gloss"), "definition": lex.get("definition"),
            "loan": loan or None,
            "equiv": _equivalents(d, key),
            "occurrences": occ,
            "features": [], "neighbours": [], "grammar": [], "lxx": [],
            "acts": None, "verb_class": None, "contrasts": []}


def _verb_card(d, key):
    """The card for a word the sense layer never profiled.

    Built from what a verb actually has: the events it is, the agents that
    perform it, and the class of verbs it behaves like. No sense profile, no
    feature list, and the card says which by carrying `kind: verb`.
    """
    acts = acts_of(d, key)
    cls = class_of(d, key)
    if not (acts or cls):
        return _bare_card(d, key)
    lex = d["lex"].get(key) or {}
    gloss = None
    if acts and acts["examples"]:
        gloss = acts["examples"][0].get("gloss")
    lemma, translit, also = _head(d, key, d["lemmas"].get(key) or lex.get("word"),
                                  _first(d["lmeta"].get(key) or {}, "transliteration")
                                  or lex.get("translit"))
    return {"key": key, "found": True, "kind": "verb",
            "gloss": gloss or lex.get("gloss") or _text_gloss(d, key),
            "lemma": lemma, "lemma_also": also,
            "strong": key[1:],
            "lang": "Hebrew" if key[:1] == "h" else "Greek",
            "translit": translit,
            "grammar": grammar_of(d, key),
            "acts": acts, "verb_class": cls,
            "observations": _uses(d, key) or (acts or {}).get("count"),
            "features": [], "phrases": [], "neighbours": [], "contrasts": []}


# committed, gzipped (tools/wordgraph/export_wordpage.py writes it)
WORDSPACE = OUT / "wordpage-data.json.gz"


def _wordspace(d):
    """The word page's data, indexed by the word card's key (h2617, g1656).
    Loaded once, on first use. Built by tools/wordgraph/export_wordpage.py;
    absent means the card simply shows none of its sections."""
    if "_wordspace" in d:
        return d["_wordspace"]
    ws = {"by": {}, "labels": {}, "books": []}
    if WORDSPACE.exists():
        with gzip.open(WORDSPACE, "rt", encoding="utf-8") as f:
            raw = json.load(f)
        ws["books"], ws["labels"] = raw["books"], raw["labels"]
        for w in raw["words"]:
            k = _ws_key(w["id"], w.get("strong"))
            # one card per key: the commonest lexeme carrying that number
            if k and (k not in ws["by"] or w["count"] > ws["by"][k]["count"]):
                ws["by"][k] = w
    d["_wordspace"] = ws
    return ws


def _ws_key(lid, strong):
    """lex:H:2617:חסד -> h2617; lex:G:1656:ἔλεος -> g1656 (Aramaic is h)."""
    lang = (lid.split(":") + ["", ""])[1]
    return sense_key("greek" if lang == "G" else "hebrew", strong)


def api_wordspace(d, q):
    """WHERE A WORD SITS, for the word card: its neighbours by each tested
    kind of evidence, its links across the languages, what the structure
    graph says of it, how it is spoken and where it occurs.

    2026-09-27: it can enhance the word tabs in the main app without taking
    away from what is there, adding value and insight. So this adds sections
    to the card and changes none. The measures were tested before the
    sections were built on them (2026-09)."""
    ws = _wordspace(d)
    if not ws["by"]:
        # the data file was not built on this machine: say so, so the card
        # leaves its sections out instead of calling every word "too rare"
        return {"found": False, "absent": True}
    key = (q.get("key") or [""])[0]
    w = ws["by"].get(key)
    if not w:
        return {"found": False}

    def node(lid, score=None):
        lab = ws["labels"].get(lid) or ["", "", 0]
        k = _ws_key(lid, lid.split(":")[2])
        out = {"id": lid, "lemma": lab[0], "gloss": lab[1], "count": lab[2],
               "lang": lid.split(":")[1],
               # clickable when that word has a card here
               "key": k if k in ws["by"] else None}
        if score is not None:
            out["score"] = score
        return out

    return {
        "found": True, "id": w["id"], "lemma": w["lemma"], "gloss": w["gloss"],
        "lang": w["lang"], "count": w["count"],
        "near": {ev: [node(m, s) for m, s in lst]
                 for ev, lst in w["near"].items()},
        "portrait": {rel: [dict(node(p), n=n) for p, n in lst]
                     for rel, lst in w["portrait"].items()},
        "force": w["force"], "sept": w["sept"], "bsb": w["bsb"],
        "books": w["books"], "book_names": ws["books"],
    }


_STMT_COUNTS = None


def _statement_counts():
    """The verb statements by standing, from ontology/relations/verb-statements.jsonl."""
    global _STMT_COUNTS
    if _STMT_COUNTS is None:
        c = collections.Counter()
        for r in _rows(ROOT / "ontology" / "relations" / "verb-statements.jsonl"):
            c["held" if r.get("held") else "described" if r.get("described") else "shown"] += 1
        _STMT_COUNTS = dict(c)
    return _STMT_COUNTS


def _readings_counts(d):
    tags = _clause_tags()
    readers = collections.Counter(t.get("reader") for v in tags.values() for t in v)
    refs = (d.get("event_refs") or {}).get("readings", [])
    return {"tagged_clauses": len(tags),
            "tags": sum(len(v) for v in tags.values()),
            "tag_books": len({c.split(".")[0] for c in tags}),
            "tag_reader": readers.most_common(1)[0][0] if readers else None,
            "event_refs": len(refs),
            "event_refs_confirmed": sum(1 for r in refs if r.get("confirmed_by"))}


def api_about(d, _q):
    """What this holds, how it was made, and where it is thin — computed live.

    A standing rule for the legacy app's version of this
    page calls it *"the project's claim about its own trustworthiness. A
    tool whose stated limits are out of date is worse than one that states
    none, since a reader who checks the caveats and finds them stale has no
    reason to believe the citations either."*

    **The new experience had no such page at all**, which is worse than a stale
    one. Every number here is counted from the loaded data rather than written
    down, so the prose can be wrong but the figures cannot drift.

    The shape it has to describe is this project's central distinction: a
    **computed floor** read off the grammar, and a **reasoned overlay** where
    people did the reading. They are not a draft and its replacement, and an
    About page that blurred them would misrepresent the whole thing.
    """
    ents = d["ents"]
    by_type = collections.Counter(e.get("type") for e in ents.values())
    rel_types = collections.Counter(r["type"] for v in d["rels"].values()
                                    for r in v)
    noted = sum(1 for v in d["rels"].values() for r in v if (r.get("note") or "").strip())
    rel_total = sum(len(v) for v in d["rels"].values())
    ev = d["events"]
    verse_marks("", 0, 0)            # load the marks (About counts them)
    return {
        "translation": d.get("translation") or "unknown",
        "ms_verses": sum(1 for m in _VMARKS.values() if m.get("ms")),
        "findings": sum(len(m.get("find", [])) for m in _VMARKS.values()),
        # the concept hubs this site shows, by name (About says how they are built)
        # the traditions' own words (ontology/traditions/): counted from the shown question cards, None until one is shown
        "traditions": _tradition_counts(),
        "concept_hubs": sorted((d["ents"].get(p.stem) or {}).get("name") or p.stem
                               for p in (ROOT / "ontology" / "concept-hubs").glob("*.json")
                               if concept_hub(p.stem)),
        "verses": len(d["verses"]),
        "floor": {
            "sentences": len(d.get("sents") or []),
            "words_with_lemma": _structure().summary()["with_lemma"],
            "nodes": len(d["nodes"]),
            "events": d.get("events_total") or sum(len(v) for v in ev.values()),
            "event_verbs": len(ev),
            "verb_classes": len(d["classes"]),
            "patterns": len(d["patterns"]),
            "senses": len(d["profiles"]),
        },
        "overlay": {
            "entities": len(ents),
            "by_type": by_type.most_common(),
            "relations": rel_total // 2,
            "relation_types": len(rel_types),
            "with_a_note": noted // 2,
        },
        # THE VERB STATEMENTS by standing (About's primer, 2026-10-20): shown
        # (stated outright), described (a promise, prediction or command,
        # never stated) and held (not yet readable), counted from the store
        "statements": _statement_counts(),
        # THE SCHEMA MAP (/ns/map, from 1.2.0): About links to it only once
        # the release has written it, so the link is never a 404
        "schema_map": (OUT / "ns" / "map.html").exists(),
        # READINGS, shown as readings (2026-09-28): a model's clause tags
        # (Flash, a pilot of sections), and credited readings of what a
        # passage refers to — counted, so the About page cannot drift
        "readings": _readings_counts(d),
        # the word card's "How it connects to other words" (api_wordspace)
        "word_space": _word_space_counts(d),
        # STEPBible was not credited here although the word families read
        # their lexicon and CC BY asks for credit (noticed 2026-10-01). It
        # then said "Lexicon entries: STEPBible's", which the live site never
        # shows: the lexicon file is not on the server (their terms,
        # docs/OPERATIONS.md), so no "Lexicon entry" section appears there and
        # the word headings come from MACULA (2026-10-03). Credit what is used
        # MACULA's own attribution, word for word, and its copyright holder
        # (2026-10-06: "Clear Bible" alone sent a thank-you to the wrong people)
        "source": "MACULA Hebrew Linguistic Datasets, available at "
                  "https://github.com/Clear-Bible/macula-hebrew/, and MACULA Greek "
                  "Linguistic Datasets, available at "
                  "https://github.com/Clear-Bible/macula-greek/ — © Biblica, Inc., "
                  "CC BY 4.0: the words, their grammar and their English glosses "
                  "(the Berean Interlinear's and Andi Wu's Cherith glosses, "
                  "which MACULA includes). Word families from the "
                  "derivations in Abbott-Smith's Manual Greek Lexicon of the New "
                  "Testament (1922), as given in STEPBible's Translators Brief "
                  "lexicon, Tyndale House, Cambridge, CC BY 4.0 — "
                  "https://github.com/STEPBible/STEPBible-Data.",
    }


def _word_space_counts(d):
    ws = _wordspace(d)
    words = list(ws["by"].values())
    return {"words": len(words),
            "greek": sum(1 for w in words if w.get("lang") == "G"),
            "with_portrait": sum(1 for w in words if w.get("portrait"))}


def api_coverage(d, _q):
    """Per book: what is parsed, and what anybody has reasoned about.

    The two columns are the point. A book can be **fully parsed and entirely
    unread** — every verse with its structure, and not one claim about what it
    says — and a reader who cannot see that difference will take an empty page
    for an absence in the text rather than an absence in the work. That is the
    failure this project names: *"a graph without it is worse than nothing,
    because it looks authoritative at exactly the points where it is empty."*
    """
    order = [b["id"] for b in d["chapters"].get("_order", [])] \
        if isinstance(d["chapters"].get("_order"), list) else None
    parsed = collections.Counter()
    evc = collections.Counter()
    # every verse with structure, from the chapter blocks' summary (the
    # distinct node refs, as the walk over every node counted them)
    for r in _structure().summary()["refs"]:
        parsed[r.split(".")[0]] += 1
    for rows in d["events"].values():
        for e in rows:
            evc[(e.get("ref") or "").split(".")[0]] += 1

    verses = collections.Counter()
    for (b, _c, _v) in d["verses"]:
        verses[b] += 1

    claims = collections.Counter()
    for eid, rels in d["rels"].items():
        for r in rels:
            for ref in r.get("refs", [])[:1]:
                m = re.match(r"^\s*(\S+?)[\s.](\d+)[:.](\d+)", str(ref))
                if m:
                    claims[m.group(1)] += 1

    parsed, evc = _bookfold(parsed), _bookfold(evc)
    # CLAUSES A MODEL HAS READ — the clause tags, a reading shown as one.
    # Added 2026-09-28 (the Coverage page had to be current): 20 pilot
    # sections are tagged and the rest of the canon is not, and a reader who
    # meets tags in John 3 must be able to see they stop there.
    tagged = collections.Counter(
        c.split(".")[0].lower() for c in _clause_tags())
    rows = []
    for b, n in sorted(verses.items(), key=lambda kv: -kv[1]):
        k = _mac(b).lower()
        rows.append({"book": b, "verses": n,
                     "parsed": parsed.get(k, 0),
                     "events": evc.get(k, 0),
                     "claims": claims.get(b, 0),
                     "tagged": tagged.get(k, 0)})
    return {"books": rows,
            "note": "Parsed is structure read off the grammar. Claims are what "
                    "someone reasoned and sourced. A book can be fully parsed "
                    "and entirely unread."}


def _mac(book):
    """The MACULA code for a KJV book, from the map the app already carries.

    This was a hand-written table and it was both redundant and wrong: coverage
    reported 1 Chronicles as **0 verses parsed** while showing 481 events in it,
    an impossible pair, because the node layer writes `1Ch` and the event layer
    writes `1ch`. Fixing the case then left Amos, Ruth and Joel at zero, because
    `Amo`, `Rut` and `Jol` are not truncations anyone would guess.

    `TO_MACULA` has been in this file the whole time, feeding `/api/books`. Four
    silent key-space mismatches in two days -- Strong's against lemma, KJV
    spelling against transliteration, gloss against lemma, and case -- and this
    one existed only because a second mapping was written beside the real one.
    """
    return TO_MACULA.get(book, book)


def _bookfold(counter):
    """A counter of book codes, re-keyed lowercase so either casing finds it."""
    out = collections.Counter()
    for k, v in counter.items():
        out[str(k).lower()] += v
    return out


def acts_of(d, key):
    """The narrative events this word IS, with who did them.

    Only a verb in the narrative form has these -- Hebrew's wayyiqtol, Greek's
    aorist indicative -- so a noun returns nothing and that is correct rather
    than missing. `tools/events.py` has the argument.
    """
    rows = d["events"].get(key) or []
    if not rows:
        return None
    agents = collections.Counter()
    for e in rows:
        for s in (e.get("participants") or {}).get("s", []):
            agents[s] += 1
    return {
        "count": len(rows),
        "verses": len({e["ref"] for e in rows}),
        "agents": [{"lemma": a, "n": n} for a, n in agents.most_common(6)],
        "examples": [{"ref": e["ref"], "gloss": e.get("gloss"),
                      "participants": e.get("participants") or {}}
                     for e in rows[:6]],
    }


def class_of(d, key):
    """The verbs this one behaves like, and the ones set against them.

    Clustered from context and MACULA's gloss, not named -- 25 of 113 classes
    carry a name because their members share a gloss word, and the rest are
    deliberately unnamed because naming a class is a ruling.
    """
    cid = d["vclass"].get(key)
    if cid is None:
        return None
    c = d["classes"].get(cid) or {}
    return {"id": cid, "name": c.get("name"),
            "size": len(c.get("verbs") or []),
            "glosses": sorted(c.get("glosses") or [])[:12]}


def top_of(d, key, field):
    vals = (d["lmeta"].get(key) or {}).get(field) or []
    return vals[0]["v"] if vals else None


def grammar_of(d, key):
    """How the word actually inflects, counted -- not a paradigm table.

    MACULA states stem and state for Hebrew, and case, tense, voice, mood and
    degree for Greek. Reporting the commonest few is more useful than a full
    parsing: it says what this word normally DOES.
    """
    m = d["lmeta"].get(key) or {}
    out = []
    for f, label in (("stem", "stem"), ("state", "state"), ("case", "case"),
                     ("tense", "tense"), ("voice", "voice"), ("mood", "mood"),
                     ("degree", "degree")):
        if m.get(f):
            out.append({"field": label,
                        "values": [{"v": x["v"], "n": x["n"]} for x in m[f]]})
    return out


def lxx_of(d, key):
    """The Greek the Septuagint used for a Hebrew word.

    MACULA carries `greek`/`greekstrong` on Hebrew words, which is the
    cross-language bridge the sense profiles could not build -- profile
    similarity across languages was measured at 0.039 and is noise. This is an
    alignment rather than an inference, so it is the honest route.
    """
    if not key.startswith("h"):
        return []
    m = d["lmeta"].get(key) or {}
    words = m.get("greek") or []
    codes = {x["v"]: x["n"] for x in (m.get("greekstrong") or [])}
    out = []
    for w in words:
        # MACULA writes a pair of primes where the Septuagint has NO word for
        # this one. It is the absence of a rendering, not a rendering, and it
        # was reaching the card as though it were Greek.
        v = (w.get("v") or "").strip()
        if not v or not v.strip("’'\""):
            continue
        gk = None
        for code in codes:
            gk = "g" + re.sub(r"^0+", "", re.sub(r"[^0-9]", "", code))
            break
        out.append({"word": v, "n": w["n"],
                    "key": gk if gk in d["profiles"] else None})
        if len(out) >= 4:
            break
    return out


def _where(d, key, ref, lang, look=4):
    """The verse at or just after `ref` that actually holds this word.

    Returns `ref` unchanged when the word is already there, or cannot be found
    within `look` verses -- guessing further would trade a slightly wrong
    citation for a badly wrong one. See the note in phrases() for the
    measurement behind the forward-only search.
    """
    try:
        b, c, v = ref.split(".")
        v = int(v)
    except ValueError:
        return ref
    for dd in range(0, look + 1):
        cand = f"{b}.{c}.{v + dd}"
        words = d["orig"].get(cand)
        if not words:
            continue
        if any(sense_key(lang, w.get("s")) == key for w in words):
            return cand
    return ref


def occurrences(d, key, cap=400):
    """EVERY verse this word is in, as refs -- the boxes, without the verses.

    2026-09-15: Words in a Phrase was the section with the redundancy, and it
    typically got through only a few references in Matthew (for Greek), as
    Matthew comes first. The fix: show all the boxes on expanding, and click
    one to see the verse.

    Both halves of that are right. The old card took the FIRST 8 occurrences in
    canonical order, so for any common Greek word all eight were Matthew and
    the reader learned nothing about its range. And eight full verses is a wall
    of text that mostly repeats what the reader already has.

    So the list is refs only and the verse is fetched when a box is clicked.
    That is what makes showing them all affordable: the median word has 2
    occurrences and only 147 keys in the corpus exceed 200.

    Above `cap` the selection is ROUND-ROBINED BY BOOK rather than truncated,
    because truncating is exactly the Matthew-only failure again -- Jesus
    (g2424) has 677 occurrences across 25 books and the point of the list is
    the range.
    """
    lang = "hebrew" if (key or "").startswith("h") else "greek"
    seen, rows = set(), []
    for ref, gloss in d["occ"].get(key, []):
        ref = _where(d, key, ref, lang)
        if ref in seen:
            continue
        seen.add(ref)
        rows.append({"ref": ref, "gloss": gloss})
    total = len(rows)
    if total <= cap:
        # CANONICAL ORDER, always. The index lists a word's verses book by
        # book in the order the files were read, which is alphabetical by
        # book name: the card of אהב opened with 1 Kings and Genesis was
        # fifth (2026-10-26). Only a list cut to `cap` was ever sorted.
        return sorted(rows, key=lambda r: _vkey_macula(r["ref"])), total
    bybook = collections.OrderedDict()
    for r in rows:
        bybook.setdefault(r["ref"].split(".")[0], []).append(r)
    out, i = [], 0
    while len(out) < cap and any(bybook.values()):
        for b in list(bybook):
            if bybook[b] and len(out) < cap:
                out.append(bybook[b].pop(0))
        i += 1
        if i > cap:
            break
    return sorted(out, key=lambda r: _vkey_macula(r["ref"])), total


def _vkey_macula(ref):
    b = MACULA_BACK.get(ref.split(".")[0], ref.split(".")[0])
    return _vkey(f"{b}.{'.'.join(ref.split('.')[1:])}")


def phrase_one(d, key, ref):
    """One example, built only when its box is opened."""
    lang = "hebrew" if (key or "").startswith("h") else "greek"
    gloss = next((g for r, g in d["occ"].get(key, []) if r == ref), "")
    # The English at the BEREAN's number; see bsb_ref.
    eref = bsb_ref(d, ref)
    b = MACULA_BACK.get(eref.split(".")[0])
    if not b:
        return {"found": False}
    try:
        _, c, v = eref.split(".")
        text = d["verses"].get((b, int(c), int(v))) or ""
    except ValueError:
        return {"found": False}
    gtok = [t for t in re.findall(r"[a-z]+", (gloss or "").lower())
            if len(t) > 2]
    hit = None
    for m in re.finditer(r"[A-Za-z][A-Za-z'-]*", text):
        w = re.sub(r"[^a-z]", "", m.group(0).lower())
        if any(w == t or w.rstrip("s") == t or w == t.rstrip("s")
               for t in gtok):
            hit = [m.start(), m.end()]
            break
    orig = [{"t": w.get("t"), "g": w.get("g"), "x": w.get("x"),
             "on": sense_key(lang, w.get("s")) == key}
            for w in d["orig"].get(ref, []) if w.get("t") or w.get("g")]
    return {"found": True, "ref": ref, "text": text, "hit": hit,
            "gloss": gloss, "orig": orig,
            "rtl": ref.split(".")[0] in HEBREW_BOOKS}


def describe_pattern(r):
    """Say what the pattern IS, in a sentence, from its own counts.

    2026-09-16: do more in the pattern pages and the pattern list pages --
    at a minimum show the specific verses, but better, describe the patterns.

    Nothing here is asserted: every clause is a restatement of a number already
    on the record. A description built that way can be checked against the
    figures beside it, which a generated summary cannot.
    """
    n, reach = r.get("instances", 0), r.get("reach", 0)
    slots = r.get("slots") or {}
    skew = r.get("skew") or 0
    bits = []

    fixed = [w for w in re.findall(r"[a-z]+", re.sub(r"\[[A-Z]\]", " ",
                                                     r.get("template", "")))]
    if fixed:
        # No trailing space: the bits are joined with one, and adding another
        # here printed "stay put and  [X] is".
        bits.append("The words " + ", ".join(f"“{w}”" for w in fixed)
                    + (" stay put and" if slots else " stay put."))
    if slots:
        name, fills = next(iter(slots.items()))
        top = sorted(fills.items(), key=lambda kv: -kv[1])
        if top:
            w, c = top[0]
            share = c / n if n else 0
            if share >= 0.8:
                bits.append(f"[{name}] is “{w}” in {c} of {n} — this is a "
                            f"fixed phrase rather than a shape the text "
                            f"composes with.")
            elif share >= 0.4:
                bits.append(f"[{name}] is usually “{w}” ({c} of {n}), but "
                            f"{r.get('distinct_fillers', 0)} different words "
                            f"fill it.")
            else:
                bits.append(f"[{name}] takes "
                            f"{r.get('distinct_fillers', 0)} different words, "
                            f"the commonest being “{w}” ({c}) — the text "
                            f"builds with this rather than repeating it.")

    if reach >= 30:
        bits.append(f"It runs through {reach} books, so it belongs to the "
                    f"language of the whole canon rather than to one writer.")
    elif reach <= 4:
        bits.append(f"It appears in only {reach} book"
                    f"{'s' if reach != 1 else ''}, which makes it a local "
                    f"habit rather than a canonical formula.")
    else:
        bits.append(f"It appears in {reach} books.")

    if skew >= 0.9 and n >= 10:
        bits.append("Every slot is filled the same way almost every time, "
                    "which is what distinguishes a formula from grammar.")
    return " ".join(bits)


def api_pattern_verse(d, q):
    """One instance of a pattern, with the pattern's own words marked.

    A verse list that only cites is a table of contents. Marking which words
    put the verse on the list is what lets a reader judge whether the pattern
    is really there -- and it is the same reason the word card shows the
    original with the word highlighted rather than the English alone.
    """
    key = (q.get("key") or [""])[0]
    ref = (q.get("ref") or [""])[0]
    r = d["patterns"].get(key)
    if not r or not ref:
        return {"found": False}
    # THE ENGLISH IS FETCHED AT THE BEREAN'S NUMBER, NOT THE HEBREW'S.
    # 2026-09-21, on the verse this card printed under Exodus 8:6: it had no
    # visible relation to the card. It did not: MACULA's Exo.8.6 is "there is no one
    # like the LORD our God" and the Berean text has that at 8:10. The
    # analysis stays on the Hebrew reference, which is what the graph is keyed
    # on; only the lookup of the English moves.
    eref = bsb_ref(d, ref)
    b = MACULA_BACK.get(eref.split(".")[0])
    try:
        _, c, v = eref.split(".")
        text = d["verses"].get((b, int(c), int(v))) or ""
    except (ValueError, TypeError):
        return {"found": False}

    # MARK THE ORIGINAL, NOT THE TRANSLATION. 2026-09-19, on Numbers
    # 24:4: the BSB highlighting was very misleading, as the wrong words were
    # emphasized. The fix: remove the emphasis/bolding from the BSB,
    # which is a guess anyway, and put boxes around the matched word, including
    # the slot word in the original language.
    #
    # It was worse than a guess. The old code collected every word of the
    # template AND of every filler anywhere in the pattern, then bolded any of
    # them wherever they appeared in the Berean text -- so at Numbers 24:4,
    # where the verse reads "the prophecy of one who hears the words of God",
    # it emphasised "the" and "words" because some OTHER instance of this
    # pattern is filled with "words". The marks pointed at the wrong things and
    # implied an alignment nobody had computed.
    #
    # What IS known is which original-language words carry the pattern: the
    # anchor's own lexeme, and the filler this verse contributes. Both are
    # recorded, so both can be marked exactly.
    anchor = r.get("lemma_key")
    anchor_lem = r.get("lemma")
    # EVERY FILLER THIS VERSE CONTRIBUTES, NOT THE FIRST ONE FOUND.
    # 2026-09-21, having drilled into `[S] like [X]` from the filler "lord"
    # and landed on Exodus 8:6: "Lord" was not highlighted, while "as", "you"
    # and "say" were, and it took a moment to realize that was a different
    # pattern.
    #
    # It is not a different pattern. The verse uses THIS one twice — כִּדְבָרְךָ
    # "as your word" and כַּיהוָה "like the LORD", both the preposition כְּ —
    # and the card marked whichever filler it happened to find first. So the
    # reader arrived from "lord", saw "say" boxed, and had no way to tell that
    # the two are one shape.
    fills_here = []
    for slot, fills in (r.get("slot_refs") or {}).items():
        for filler, refs in fills.items():
            if ref in refs:
                fills_here.append((slot, filler))
    want = (q.get("fill") or [""])[0]
    here = next((f for _s, f in fills_here if _slug(f) == _slug(want)),
                fills_here[0][1] if fills_here else None)
    # THE FILLER IS A GLOSS, NOT THE ORIGINAL. Since anchors and fillers were
    # keyed on the lexeme, a slot reads "lord" or "words" — the lexeme's
    # commonest English — so comparing it against the Hebrew surface text
    # matched nothing and the slot word never got boxed.
    want_fill = _slug(here) if here else None
    lang = "hebrew" if ref.split(".")[0] in HEBREW_BOOKS else "greek"

    others = {_slug(f) for _s, f in fills_here if _slug(f) != _slug(here)}

    def mark(w):
        s = w.get("s")
        k = sense_key(lang, s) if s else None
        # BY LEXEME WHERE THERE IS ONE. `sense_key` strips the letter off a
        # Strong's number, so כְּ (3509a) and a pronominal suffix (3509b) both
        # key to h3509 — and this verse duly boxed "you" as though it were the
        # preposition. The lemma cannot collide, so it decides when both sides
        # carry one, and the number is the fallback.
        if anchor_lem and w.get("l"):
            if w["l"] == anchor_lem:
                return "anchor"
        elif anchor and k == anchor:
            return "anchor"
        if others:
            prof = (d.get("profiles") or {}).get(k) or {}
            for cand in (prof.get("gloss"), w.get("g")):
                g = _slug(cand)
                if g and g in others:
                    return "slot2"
        if not want_fill:
            return None
        # The lexeme's own gloss first, since that is what the filler is; the
        # verse's gloss second, because a filler of several words is glossed
        # per word and the profile may not carry it.
        prof = (d.get("profiles") or {}).get(k) or {}
        for cand in (prof.get("gloss"), w.get("g")):
            g = _slug(cand)
            if g and (g == want_fill or g in want_fill.split()):
                return "slot"
        return None

    # AND NOW THE TRANSLATION TOO, from the editors' own tagging rather than a
    # guess. 2026-09-19: if the words can be pinpointed in the
    # BSB, the emphasis is wanted in both, and the reason:
    # it bridges oracle to prophecy in Num 24:4.
    #
    # That is exactly what it does. The interlinear glosses נְאֻם as "oracle"
    # there and the Berean text reads "the prophecy", and the editors tagged
    # that span H5002 — so boxing the Hebrew and marking the English shows a
    # reader the two are one word, which is the connection a reader had to find by
    # hand.
    #
    # `tools/bsbalign.py` says what this is: the editors' marking, winnowed to
    # spans whose English that lexeme is actually known to be rendered by, and
    # approximate rather than a computed word alignment.
    al = (d.get("align") or {}).get(eref) or {}
    spans = []
    got = set()
    if al.get("text") == text:
        for s0, e0, k in al.get("spans") or []:
            if anchor and k == anchor:
                spans.append([s0, e0, "anchor"])
                got.add("anchor")
            elif want_fill:
                prof = (d.get("profiles") or {}).get(k) or {}
                g = _slug(prof.get("gloss"))
                if g and (g == want_fill or g in want_fill.split()):
                    spans.append([s0, e0, "slot"])
                    got.add("slot")

    # WHERE THE EDITORS MIS-TAGGED, FALL BACK TO THIS VERSE'S OWN GLOSS.
    # 2026-09-19, seeing "the words of God" sitting unmarked: the words
    # should be marked too. Right — the Berean text plainly has it, and it went unmarked
    # only because the editors tagged that span H5002 when the word is אִמְרֵי
    # H561, so the winnowing threw the one span that was really the filler's.
    #
    # This is NOT the guess that was removed this morning. That one took every
    # word of the template and of every filler ANYWHERE in the pattern and lit
    # them up wherever they fell, which is how "the" and "words" got emphasised
    # at Numbers 24:4 for the wrong reasons. This takes one word's gloss IN
    # THIS VERSE, and only when it occurs exactly once, so there is nothing to
    # choose between and nothing to get wrong.
    for w in d["orig"].get(ref, []):
        kind = mark(w)
        if not kind or kind in got:
            continue
        g = (w.get("g") or "").strip()
        if not g or len(g) < 3:
            continue
        hits = [m for m in re.finditer(re.escape(g), text, re.I)]
        if len(hits) != 1:
            continue
        spans.append([hits[0].start(), hits[0].end(), kind])
        got.add(kind)
    spans.sort()

    # NEVER MARK MORE THAN THE VERSE HOLDS. 2026-09-19: nothing unreliable is to be
    # done.
    #
    # 1 Samuel 2:30 came back with five marks where the original has two
    # anchors and two fillers, because the Berean editors tag "God" with H3068
    # in "the LORD, the God of Israel" — their marking, and one a reader would
    # read as a second occurrence of the filler that is not there.
    #
    # The interlinear says exactly how many times each is present, so that is
    # the ceiling. Spans are kept in reading order, which is where the
    # editors' own tags fall.
    cap = collections.Counter()
    for w in d["orig"].get(ref, []):
        k = mark(w)
        if k:
            cap[k] += 1
    # AND WHEN TRIMMING, KEEP THE ONES THAT READ RIGHT. Position alone kept
    # "LORD," and "God" at 1 Samuel 2:30 and dropped the second, real "LORD"
    # later in the verse — the correct number of marks and the wrong two.
    # A span whose English is what this lexeme is normally rendered by is
    # better evidence than one that merely comes first.
    expect = {"anchor": _slug((d.get("profiles") or {})
                              .get(anchor or "", {}).get("gloss")),
              "slot": want_fill}

    def fits(sp):
        got_txt = _slug(text[sp[0]:sp[1]])
        want = expect.get(sp[2])
        if not want or not got_txt:
            return 0
        return 1 if (got_txt == want or want in got_txt.split()
                     or got_txt in want.split()) else 0

    keep = []
    for kind in ("anchor", "slot"):
        mine = [s for s in spans if s[2] == kind]
        mine.sort(key=lambda sp: (-fits(sp), sp[0]))
        keep.extend(mine[:cap.get(kind, 0)])
    spans = sorted(keep)

    return {"found": True, "ref": ref, "text": text,
            "spans": spans,
            # Every use of the shape in THIS verse, in the verse's own words,
            # so a reader can see that "as your word" and "like the LORD" are
            # one preposition and not a coincidence. See _instances_here.
            "instances": _instances_here(d, r, ref, lang),
            "fill": here,
            "orig": [{"t": w.get("t"), "g": w.get("g"), "x": w.get("x"),
                      "mark": mark(w)}
                     for w in d["orig"].get(ref, [])
                     if w.get("t") or w.get("g")],
            "rtl": ref.split(".")[0] in HEBREW_BOOKS}


# Hebrew cantillation and the marks that go with it. Vowel points are KEPT --
# they are part of the word as the index spells it -- but the accents are not,
# and a filler carrying one missed the lookup entirely.
_CANT = re.compile("[֑-ֽ֯׀׃׆]")


def _g(gloss, w):
    """Gloss a filler: whole, de-punctuated, de-accented, then word by word.

    2026-09-16: some of these could not be read; the Hebrew is fine
    if the English can be read too. Many fillers are several words -- `ὁ Ἰησοῦς`,
    `ταῖς ἐκκλησίαις`, `לְ מִנְחָֽה` -- and a whole-string lookup against a
    per-word index finds none of them, so the row printed untranslated with no
    English anywhere. Glossing token by token returns "the Jesus", "the
    churches", "to grain offering".

    Returns "" when nothing resolves, which lets the caller keep the original
    rather than print a half-translation as if it were the reading.
    """
    if not w:
        return ""
    for k in (w, w.strip(",.;:·"), _CANT.sub("", w)):
        if k in gloss:
            return gloss[k]
    parts = w.split()
    if len(parts) > 1:
        out, hit = [], 0
        for t in parts:
            g = (gloss.get(t) or gloss.get(t.strip(",.;:·"))
                 or gloss.get(_CANT.sub("", t)) or "")
            out.append(g or t)
            hit += bool(g)
        # Only worth showing when most of it resolved; a string that is half
        # English and half Hebrew reads as neither.
        if hit and hit >= len(parts) - 1:
            return " ".join(out)
    return ""


def api_layeritem(d, q):
    """A card for one member of a pattern layer that has no card of its own.

    2026-09-16: node structure links were not live, and ladder chains were
    confusing to a reader who does not speak the language, since clicking just
    navigated to the reader with no explanation.

    Both were listed without anywhere to go. A list that cannot be opened is a
    dead end, and a ladder rendered as eight Hebrew lemmas is a dead end even
    for someone who can open it -- so the chain is GLOSSED here, and the card
    says what a ladder is before showing one.
    """
    kind = (q.get("set") or [""])[0]
    key = (q.get("key") or [""])[0]
    gloss = d.get("lemgloss") or {}

    if kind == "ladder":
        row = next((r for r in d.get("gradatio") or []
                    if f"{r['start']}|{r['n']}|{r['steps'][0]}" == key), None)
        if not row:
            return {"found": False}
        span = ([row["start"]] if row["start"] == row["end"]
                else _span(row["start"], row["end"]))
        return {"found": True, "kind": "ladder",
                "title": " → ".join(_g(gloss, s) or s for s in row["steps"]),
                "subtitle": " → ".join(row["steps"]),
                "note": "A LADDER — gradatio. The word that ends one step "
                        "begins the next, so the sentence climbs: Romans 5:3-4 "
                        "runs suffering → endurance → character → hope. "
                        "Nothing asserts this; the repetition is in the text "
                        "and every step below is shown.",
                "steps": [{"lemma": s, "gloss": _g(gloss, s)}
                          for s in row["steps"]],
                "refs": span,
                "facts": [["steps", row["n"]],
                          ["spans", row["start"] if row["start"] == row["end"]
                           else f"{row['start']}–{row['end'].split('.')[-1]}"]]}

    if kind == "node":
        row = next((r for r in d.get("nodepat") or []
                    if r.get("shape") == key), None)
        if not row:
            return {"found": False}
        slots = []
        for i, fills in sorted((row.get("slots") or {}).items()):
            slots.append({"name": i,
                          "fills": [[w, c, _g(gloss, w)] for w, c in fills]})

        # A "STRUCTURE WITH SLOTS" WHOSE SLOTS NEVER VARY IS A FIXED PHRASE.
        # 2026-09-16, on `cl [pron s pp]`: all the examples of where it
        # is used are "grace and peace", so it calls out a pair more than a
        # generic pattern.
        #
        # That reading was right, and the card was mis-describing its own contents.
        # `nodepat.py` ranks by SKEW, so the top of that list is by
        # construction the shapes whose slots do not vary -- every one of these
        # is a set phrase, and calling them templates invites a reader to
        # expect variation that is not there. The card now says which it is,
        # from the same numbers it already shows.
        fixed = all(len(f) == 1 for f in (row.get("slots") or {}).values())
        note = ("A NODE STRUCTURE — the shape of one word-group in the "
                "sentence tree, with what fills each position. The bracketed "
                "codes are the grammar (`np` a noun phrase, `pp` a "
                "prepositional one); the words beneath are what the text "
                "actually puts there.")
        if fixed and (row.get("slots") or {}):
            note += (" EVERY POSITION HERE IS FILLED THE SAME WAY EVERY TIME, "
                     "so this is a set phrase rather than a shape the text "
                     "composes with — the grammar is what it was found by, "
                     "not what makes it interesting.")
        return {"found": True, "kind": "node", "title": row["shape"],
                # Tree order, NOT reading order: the shape lists a node's
                # children as the tree nests them, and Romans 1:7 reads
                # "χάρις ὑμῖν ... ἀπὸ". Saying so avoids printing a phrase the
                # text never has in that order.
                "subtitle": "",
                "fixed": fixed,
                "note": note,
                "slots": slots,
                "refs": [_normref(x) for x in (row.get("refs") or [])[:60]],
                "facts": [["instances", row.get("instances")],
                          ["books", len(row.get("books") or [])],
                          ["how constrained",
                           f"{round((row.get('skew') or 0) * 100)}%"]]}
    return {"found": False}


def _normref(ref):
    """nodepat stores refs uppercased (`ROM.1.7`); everything else does not."""
    p = ref.split(".")
    if not p:
        return ref
    b = p[0].capitalize()
    b = {"1co": "1Co", "2co": "2Co", "1th": "1Th", "2th": "2Th",
         "1ti": "1Ti", "2ti": "2Ti", "1pe": "1Pe", "2pe": "2Pe",
         "1jn": "1Jn", "2jn": "2Jn", "3jn": "3Jn",
         "1sa": "1Sa", "2sa": "2Sa", "1ki": "1Ki", "2ki": "2Ki",
         "1ch": "1Ch", "2ch": "2Ch"}.get(p[0].lower(), b)
    return ".".join([b] + p[1:])


def _span(start, end):
    """Every verse from start to end when they share a book and chapter."""
    a, b = start.split("."), end.split(".")
    if a[0] != b[0] or a[1] != b[1]:
        return [start, end]
    try:
        return [f"{a[0]}.{a[1]}.{v}" for v in range(int(a[2]), int(b[2]) + 1)]
    except ValueError:
        return [start, end]


# WHAT EACH DEVICE IS, in a sentence. 2026-09-16: the devices need explaining
# (a reader had never heard of 'hendiadys').
#
# The taxonomy names these and does not define them, which is fine for a
# stamping prompt and useless to a reader: a list of twenty-eight rhetorical
# terms explains nothing to anyone who does not already know them. Written
# plainly, and each says what to LOOK for rather than what it is called, since
# the point is to recognise it in the verse the card shows.
DEVICE_GLOSS = {
    "acrostic": "Successive lines or stanzas begin with successive letters of "
                "the Hebrew alphabet. Psalm 119 runs all 22 letters, eight "
                "verses each; Lamentations 1-4 and Psalms 25, 34, 37, 111, "
                "112, 145 do the same, as does the noble woman of Proverbs 31.",
    "hendiadys": "Two words joined by “and” that together mean one thing — "
                 "“kindness and truth” for faithful love, “good and evil” for "
                 "everything. The second word qualifies the first rather than "
                 "adding to it.",
    "merism": "Two opposite extremes standing for everything between them. "
              "“The heavens and the earth” means the whole creation; “from "
              "Dan to Beersheba” means the whole land.",
    "inclusio": "The same words close a passage that opened it, framing "
                "everything inside. Psalm 8 begins and ends “how majestic is "
                "your name in all the earth”.",
    "chiasm": "A sequence repeated in reverse — A B B A — so the turn at the "
              "centre is the point.",
    "anaphora": "The same word begins clause after clause, as “blessed is” "
                "does in the beatitudes.",
    "refrain": "A line that returns at intervals through a poem, marking its "
               "sections.",
    "a_fortiori": "An argument from the lesser to the greater: if this small "
                  "thing is so, how much more the large one.",
    "apostrophe": "The speaker turns aside to address someone or something "
                  "absent — the sea, the mountains, the dead.",
    "diatribe": "An argument staged against an imagined objector: “But someone "
                "will say…”, then the answer.",
    "irony": "The words say one thing and the situation says the opposite.",
    "hyperbole": "Deliberate overstatement — a camel through a needle’s eye.",
    "personification": "Something that is not a person acts like one: wisdom "
                       "calls out, the land mourns, the mountains skip.",
    "rhetorical_question": "A question asked to make a point rather than to "
                           "get an answer.",
    "synonymous_parallelism": "The second line says the same thing as the "
                              "first in different words — the commonest shape "
                              "of Hebrew poetry.",
    "antithetic_parallelism": "The second line says the opposite of the first. "
                              "Proverbs is built of these.",
    "synthetic_parallelism": "The second line carries the first further "
                             "instead of repeating or reversing it.",
    "messenger_formula": "“Thus says the LORD” — the herald's opening that "
                         "marks what follows as another's words.",
    "oath_formula": "A sworn saying with its penalty implied: “As the LORD "
                    "lives…”, “May God do so to me and more also”.",
    "covenant_formula": "“I will be your God and you will be my people”, and "
                        "its variants.",
    "regnal_formula": "The fixed frame around each king: he began to reign in "
                      "year X, reigned Y years, did what was right or evil.",
    "genealogy_formula": "“X lived so many years and fathered Y” repeated down "
                         "a line.",
    "itinerary_formula": "“They set out from A and camped at B”, the wilderness "
                         "march told as a list.",
    "call_narrative_formula": "The shape of a commissioning: confrontation, "
                              "objection, reassurance, sign.",
    "beatitude_formula": "“Blessed is the one who…”, a pronouncement of "
                         "well-being.",
    "woe_formula": "“Woe to you who…”, the beatitude's opposite.",
    "numerical_saying": "“Three things… four” — a count that names one more "
                        "than it promised, the last being the point.",
    "list_formula": "An enumeration the text sets out as a list rather than "
                    "as prose.",
}


# THE OLD GRAPH'S TAXONOMY, CARRIED FORWARD. 2026-09-16: people should
# be a subcategory under lists, including places, concepts, symbols, and other
# prominent lists identified over time; the old app graph was
# good at this and its taxonomy was fine to carry
# forward.
#
# These are the entity types the graph already holds, named for a reader rather
# than for the schema. `text` (2,305) and `passage` (701) are deliberately
# absent: they are how the corpus is cut up, not things the corpus is about, and
# listing them would repeat the reader's own navigation back at them.
LIST_KINDS = [
    ("person", "People"),
    ("concept", "Concepts"),
    ("place", "Places"),
    ("group", "Groups and peoples"),
    ("image", "Symbols and images"),
    ("object", "Objects"),
    ("title", "Titles"),
    ("assessment", "Judgements the text makes"),
    ("creature", "Creatures"),
    ("event", "Events"),
    ("covenant", "Covenants"),
    ("being", "Divine and spiritual beings"),
    ("observance", "Feasts and observances"),
]


# THE EVENT TAXONOMY, WHICH ALREADY EXISTED. 2026-09-16: could event nodes be
# ranked by interest, with a taxonomy that
# distinguishes parables, visions, dreams etc.?
#
# Yes, and it is stamped: 141 kinds over roughly 14,000 sections. This is the
# cheap half of the narratives major and needs NO participant resolution --
# what it cannot do is put those events in order or say who did them, which is
# the swimlane and is still unbuilt. The heading says so rather than implying
# a sequence that is not there.
#
# `prophetic_categories` is split rather than taken whole, because it mixes two
# things: a VISION is something seen and an ORACLE is something said, and
# filing them together would repeat the confound that broke the first stamping
# run.
EVENT_KINDS = [
    ("parables", "Parables", None,
     "Stories told to make a point, by the kind of point they make."),
    ("dreams", "Dreams and night visions", None,
     "What someone is shown while asleep, by what the dream does."),
    ("visions", "Visions", {"apocalyptic_vision", "restoration_vision",
                            "day_of_the_lord_vision"},
     "What a prophet is shown while awake."),
    ("oracles", "Prophetic speech", {"judgment_oracle", "salvation_oracle",
                                     "call_to_repentance", "indictment",
                                     "oracle_against_nations", "woe_oracle",
                                     "covenant_renewal", "messianic_prophecy"},
     "What a prophet is given to say — a different act from seeing."),
    ("event_images", "Things that happen", None,
     "The recurring shapes of biblical action: judgement, battle, sacrifice, "
     "exile, healing, coronation."),
    ("apocalyptic_crisis", "Crisis and undoing", None,
     "The imagery of things coming apart — the day of the LORD, the idol in "
     "the holy place, the scattering of the sheep."),
    ("significant_events", "Named events", None,
     "Particular happenings the taxonomy names outright, as the readings "
     "stamped them on sections. Those that have become event cards open the "
     "card."),
]


_BOOK_NAMES = None


def _parse_citation(d, s):
    """'Psalm 116:10', 'Isa 61:1', 'Genesis 6-7', 'Amos 9:11-12' -> the
    first verse, in MACULA numbering; None for anything not in the canon
    (Flash once offered Sirach)."""
    global _BOOK_NAMES
    if _BOOK_NAMES is None:
        _BOOK_NAMES = {}
        for code, title in TITLE.items():
            t = title.lower()
            for k in {code.lower(), t, t.rstrip("s"), t.replace(" ", "")}:
                _BOOK_NAMES.setdefault(k, code)
            if " " not in t:
                for n in (3, 4):
                    _BOOK_NAMES.setdefault(t[:n], code)
        _BOOK_NAMES.update({"psalm": "Ps", "psa": "Ps", "song of songs": "Song"})
    m = re.match(r"^\s*((?:[123]\s?)?[A-Za-z][A-Za-z ]*?)\.?\s+(\d+)(?::(\d+))?", s or "")
    if not m:
        return None
    code = _BOOK_NAMES.get(m.group(1).lower().replace("  ", " ").strip()) \
        or _BOOK_NAMES.get(m.group(1).lower().replace(" ", ""))
    if not code:
        return None
    return _macula_ref(d, f"{TITLE[code]} {int(m.group(2))}:{int(m.group(3) or 1)}")


_DECLARED = None


# THE MODEL'S SCAFFOLDING OUT OF ITS READING. The 2026-10-02 evaluation:
# reasons a model wrote against a numbered candidate list reached readers as
# "... which is Deuteronomy 21:23, candidate 2" and "none of the candidates
# (Deut 6:4 etc.) fits". The list was the prompt's, not the reader's; the
# substance of the reason stays.
_SCAFFOLD = [
    re.compile(r"[,;]?\s*(?:and |so )?none of the (?:listed )?candidates(?:\s*\([^)]*\))?"
               r"(?:\s+(?:match(?:es)?|fits?|relates? to it|appl(?:y|ies)))?"),
    re.compile(r"[,;]?\s*(?:which is\s+)?not any listed candidate"),
    re.compile(r"[,;]?\s*\(?candidate \d+\)?"),
]


def plain_reason(s):
    for rx in _SCAFFOLD:
        s = rx.sub("", s or "")
    return re.sub(r"\s+([,.;])", r"", s).strip()


def _declared_refs(d):
    """NT verse -> the OT verse it DECLARES it points to ("it is written",
    "that it might be fulfilled", "just as ... so"), as Flash read it
    (tools/meaning/declared_refs.py), high and medium only. Both regression
    cases right: John 3:14 -> Num 21:9, Matt 12:40 -> Jonah 1:17. A reading,
    credited, never merged; 'other' is Flash naming a passage the word
    search did not offer (Matt 1:22 -> Isa 7:14), marked as its suggestion."""
    global _DECLARED
    if _DECLARED is None:
        fwd, back = collections.defaultdict(list), collections.defaultdict(list)
        for r in _rows(OUT / "declared-refs.jsonl"):
            if r.get("confidence") not in ("high", "medium"):
                continue
            to = r.get("points_to") or (_parse_citation(d, r.get("other")) if r.get("other") else None)
            if not to:
                continue
            x = {"to": to, "trigger": r["trigger"], "reason": plain_reason(r.get("reason", "")),
                 "suggested": not r.get("points_to"), "confidence": r["confidence"]}
            fwd[r["from"]].append(x)
            back[to].append(dict(x, frm=r["from"]))
        _DECLARED = (fwd, back)
    return _DECLARED


def _section_start_of(d, ref):
    """The MACULA ref of the Berean section a verse stands in, or None."""
    import bisect
    try:
        mb, c, v = ref.split(".")
        c, v = int(c), int(v)
    except ValueError:
        return None
    starts = sorted(d.get("secstart", {}).get(FROM_MACULA.get(mb, mb), []))
    i = bisect.bisect_right(starts, (c, v)) - 1
    return f"{mb}.{starts[i][0]}.{starts[i][1]}" if i >= 0 else None


def _quote_index(d):
    """-> {ref: [(other, other_end, "quotes" | "quoted by")]} the Berean
    quotation footnotes (tools/quotenotes.py)."""
    got = d.get("_quotes")
    if got is not None:
        return got
    ix = collections.defaultdict(list)
    # THE EDITORS NUMBER AS THE BEREAN DOES, everything here as MACULA does.
    # Unconverted, Matt 4:15's "quotes Isaiah 9:2" printed Isaiah 9:3 ("You
    # have enlarged the nation") and Rom 9:25's Hosea 2:23 printed 2:21 --
    # every note into a chapter the Hebrew numbers differently showed the
    # wrong verse, and its Old Testament end, keyed by the English number,
    # was never found from the reader (2026-10-03). Converted once, here
    m = lambda x: _macula_ref(d, x) if x else x  # noqa: E731
    for r in _rows(OUT / "quotenotes.jsonl.gz"):
        a, b = m(r.get("from")), m(r.get("to"))
        if a and b:
            ix[a].append((b, m(r.get("to_end")), r.get("kind") or "quotes"))
            ix[b].append((a, None, {"points to": "pointed to by"}.get(r.get("kind"), "quoted by")))
    d["_quotes"] = ix
    return ix


_ALLUSIONS = None


def allusions_for(d, ref):
    """What a verse shares with another in the original, found by a phrase the
    two have word beside word (two nouns or adjectives, rare across the text),
    judged twice blind by Claude Sonnet, sorted and explained by Claude Opus,
    and the explanations reviewed as eight traditions would read them
    (ontology/allusions.jsonl; 2026-10-04). Three kinds, after the
    split of 2026-10-04:
      words  -- the NT verse takes up this OT verse's words ("new covenant",
                Luke 22:20 -> Jer 31:31), shown both ways;
      images -- both use one image or expression ("ten horns"), no pointing
                claimed: the verse's node, with every other verse in it;
      stories -- the passages tell stories whose beats match (John 6:9 and
                2 Kgs 4:42), the beats side by side.
    Every one is a reading, and credited."""
    global _ALLUSIONS
    if _ALLUSIONS is None:
        ix = collections.defaultdict(list)
        nodes = collections.defaultdict(list)
        for r in _rows(ROOT / "ontology" / "allusions.jsonl"):
            nt, ot = _macula_ref(d, r["nt"]), _macula_ref(d, r["ot"])
            if r["kind"] == "shared_image":
                nodes[r["node"]].append((nt, ot, r))
                continue
            ix[nt].append({"dir": "nt", "ref": ot, "r": r})
            ix[ot].append({"dir": "ot", "ref": nt, "r": r})
        # plan 6.18: stories told again, found by episode and judged twice
        # (ontology/told-again.jsonl). Shown on every verse that carries one
        # of the steps, on both sides, the other story's first step as the
        # link; the steps side by side as for the 6.17 ones
        for r in _rows(ROOT / "ontology" / "told-again.jsonl"):
            later = {_macula_ref(d, p[0][0]) for p in r["beats"]}
            earlier = {_macula_ref(d, p[1][0]) for p in r["beats"]}
            first = (_macula_ref(d, r["beats"][0][0][0]), _macula_ref(d, r["beats"][0][1][0]))
            row = {"kind": "story_echo", "words": None, "explanation": r.get("explanation"),
                   "differs": r.get("differs"), "reader": r.get("reader"), "beats": r["beats"],
                   "named": r.get("named")}
            for v in later:
                ix[v].append({"dir": "nt", "ref": first[1], "r": row})
            for v in earlier:
                ix[v].append({"dir": "ot", "ref": first[0], "r": row})
        # plan 6.21: a letter verse refers to a happening -- shown both ways,
        # and up front (2026-10-05: they should show on both sides; the
        # Connection panel is probably where they will be accessed more often
        # and they should be prominent there): the letter verse lists what it
        # refers to, the account verse whose words it matches lists the letter
        lx = collections.defaultdict(list)
        for eid, refs in _letter_refs().items():
            title = (_events(d)["events"].get(eid) or {}).get("title", eid)
            for r in refs:
                lref = _macula_ref(d, r["letter"][0])
                aref = _macula_ref(d, re.sub(r"\s*[-–]\s*\d+$", "", r["account_verse"]))
                base = {"event": eid, "event_title": title, "words": r["words"], "kind": r["kind"],
                        "pkind": r.get("pkind"),
                        "account_words": r["account_words"], "why": r["why"],
                        "certainty": r["certainty"], "reason": r["reason"]}
                lx[lref].append(dict(base, dir="to", ref=aref))
                lx[aref].append(dict(base, dir="by", ref=lref))
        # plan 6.22: Revelation's objective links to the rest of Scripture
        # (ontology/revelation-links.jsonl), four kinds kept apart, shown both
        # ways with both texts' words side by side; only once the site's
        # owner has read them (BIBLEONT_SHOW_UNREVIEWED=1 shows them on a
        # laptop before then). Nothing says what a vision refers to or when.
        rx = collections.defaultdict(list)
        show_all = os.environ.get("BIBLEONT_SHOW_UNREVIEWED") == "1"
        shown = [r for r in _rows(ROOT / "ontology" / "revelation-links.jsonl")
                 if r.get("reviewed_by_owner") or show_all]
        # GROUPED BY PASSAGE (2026-10-06: an explanation of the
        # connection was persuasive but its context was not apparent): a link
        # in a group carries the group's sentence and every pair in it, so
        # Rev 1:5's "faithful witness" is read beside its "firstborn ... the
        # kings of the earth" from the same psalm
        groups = collections.defaultdict(list)
        for r in shown:
            if r.get("group"):
                groups[r["group"]["id"]].append(r)
        for r in shown:
            rv, ov = _macula_ref(d, r["rev"][0]), _macula_ref(d, r["other"][0])
            g = r.get("group")
            base = {"kind": r["kind"], "rev_words": r["rev_words"], "other_words": r["other_words"],
                    "why": None if r.get("obvious") else r.get("why"),
                    "certainty": r.get("certainty", "clear"), "reason": r.get("apparent_reason"),
                    "group": {"id": g["id"], "label": g["label"], "pairs": [
                        {"rev": _verse_text(d, _macula_ref(d, m["rev"][0]))[0], "rev_words": m["rev_words"],
                         "other": _verse_text(d, _macula_ref(d, m["other"][0]))[0], "other_words": m["other_words"],
                         "certainty": m.get("certainty", "clear")}
                        for m in groups[g["id"]]]} if g else None}
            rx[rv].append(dict(base, dir="rev", ref=ov))
            rx[ov].append(dict(base, dir="other", ref=rv))
        # plan 6.23: the history books and the passages before them
        # (ontology/history-links.jsonl): a later passage tells again, quotes,
        # carries out, or says in its own words that something happened as
        # was said. Shown both ways, both texts' words side by side, a fixed
        # label per kind and no sentence (approved 2026-10-06).
        # Ordered by `rank`: across books first ("The interesting ones are
        # across books and time"), a nearby link alone last and folded
        # ("don't overemphasize isolated close references")
        hx = collections.defaultdict(list)
        hshown = [r for r in _rows(ROOT / "ontology" / "history-links.jsonl")
                  if r.get("reviewed_by_owner") or show_all]
        hgroups = collections.defaultdict(list)
        for r in hshown:
            if r.get("group"):
                hgroups[r["group"]["id"]].append(r)
        for r in hshown:
            lv, ev = _macula_ref(d, r["later"][0]), _macula_ref(d, r["earlier"][0])
            g = r.get("group")
            base = {"kind": r["kind"], "later_words": r["later_words"], "earlier_words": r["earlier_words"],
                    "certainty": r.get("certainty", "clear"), "also": r.get("also"), "reach": r["reach"],
                    "quiet": r.get("quiet", False), "rank": r.get("rank", 0),
                    "group": {"id": g["id"], "label": g["label"], "pairs": [
                        {"later": _verse_text(d, _macula_ref(d, m["later"][0]))[0], "later_words": m["later_words"],
                         "earlier": _verse_text(d, _macula_ref(d, m["earlier"][0]))[0],
                         "earlier_words": m["earlier_words"], "certainty": m.get("certainty", "clear")}
                        for m in hgroups[g["id"]]]} if g else None}
            hx[lv].append(dict(base, dir="later", ref=ev))
            hx[ev].append(dict(base, dir="earlier", ref=lv))
        _ALLUSIONS = (ix, nodes, lx, rx, hx)
    ix, nodes, lx, rx, hx = _ALLUSIONS
    out = {"words": [], "images": [], "stories": [], "letters": [], "revelation": [], "history": []}
    for x in sorted(hx.get(ref, []), key=lambda x: x["rank"]):
        eref, text = _verse_text(d, x["ref"])
        out["history"].append(dict(x, eref=eref, text=text))
    for x in lx.get(ref, []):
        eref, text = _verse_text(d, x["ref"])
        out["letters"].append(dict(x, eref=eref, text=text))
    for x in rx.get(ref, []):
        eref, text = _verse_text(d, x["ref"])
        out["revelation"].append(dict(x, eref=eref, text=text))
    for x in ix.get(ref, []):
        r = x["r"]
        eref, text = _verse_text(d, x["ref"])
        row = {"ref": x["ref"], "eref": eref, "text": text, "words": r["words"],
               "explanation": r.get("explanation"), "reader": r.get("reader")}
        if r["kind"] == "story_echo":
            row["beats"] = [[[_verse_text(d, _macula_ref(d, b[0]))[0], b[1]] for b in pair]
                            for pair in r.get("beats") or []]
            row["differs"] = r.get("differs")
            # one story told again shows once on a verse, however many of
            # its steps the verse carries
            if not any(s["beats"] == row["beats"] for s in out["stories"]):
                out["stories"].append(row)
        else:
            row["kind"] = "takes up the words of" if x["dir"] == "nt" else "its words taken up in"
            out["words"].append(row)
    for node, links in nodes.items():
        mine = [l for l in links if ref in (l[0], l[1])]
        if not mine:
            continue
        others = sorted({v for l in links for v in l[:2]} - {ref}, key=_vkey_macula)
        out["images"].append({
            "node": node,
            "members": [dict(zip(("eref", "text"), _verse_text(d, v)), ref=v) for v in others],
            "explanations": [{"pair": [_verse_text(d, l[0])[0], _verse_text(d, l[1])[0]],
                              "explanation": l[2].get("explanation")} for l in mine],
            "reader": mine[0][2].get("reader")})
    return out


def editor_notes(d, ref):
    """What the Berean EDITORS link this verse to — inherited, not derived,
    and labelled so. 2026-09-29, of John 1:1-5: the hope was to catch Gen
    1 in these 5 verses. No lexical method reaches it (tools/lxxbridge.py:
    one shared word), but the editors' parallel note under John 1's heading
    names Gen 1:1-2 and Heb 11:1-3. Parallel notes stand under a section
    heading and belong to the whole section; quotation footnotes belong to
    the verse. Both were only shown in the event sequence view before."""
    out, seen = [], set()
    start = _section_start_of(d, ref)
    # a note recorded both ways: the direction that carries the passage's
    # end first, so it reads "Gen 1:1-2" and not "Gen 1:1"
    for other, oend, direction in sorted(_xref_index(d).get(start, []) if start else [],
                                         key=lambda x: x[1] is None):
        # the Berean's numbering, shown through MACULA's like everything else
        other, oend = _macula_ref(d, other), (_macula_ref(d, oend) if oend else None)
        if other in seen or other == ref:
            continue
        seen.add(other)
        out.append({"kind": "parallel", "ref": other, "end": oend,
                    "direction": direction})
    # this verse's own note first: Gal 3:8's "See Genesis 12:3" before Gen
    # 12:3's "See Galatians 3:8", so it reads "points to", not "pointed to by"
    for other, oend, direction in sorted(_quote_index(d).get(ref, []),
                                         key=lambda x: x[2] in ("quoted by", "pointed to by")):
        if other in seen:
            continue
        seen.add(other)
        out.append({"kind": direction, "ref": other, "end": oend})
    for x in out:
        x["eref"], x["text"] = _verse_text(d, x["ref"])
        x["eend"] = bsb_ref(d, x["end"]) if x.get("end") else None
    return out


def _xref_index(d):
    """-> {ref: [(other, other_end, direction)]} the Berean parallel notes."""
    got = d.get("_xrefs")
    if got is not None:
        return got
    ix = collections.defaultdict(list)
    p = OUT / "xrefs.jsonl.gz"
    if p.exists():
        for line in gzip.open(p, "rt", encoding="utf-8"):
            r = json.loads(line)
            if any(k.startswith("_") for k in r):
                continue
            # KEYED AS THE SECTION STARTS ARE, in the Berean's numbering:
            # converting the key to MACULA's lost Psalm 84's note to John
            # 1:14 (the psalm's verse 1 is MACULA's 2). The passage a note
            # points to is converted where it is shown (editor_notes)
            a, b = r.get("from"), r.get("to")
            if a and b:
                ix[a].append((b, r.get("to_end"), "to"))
                ix[b].append((a, None, "from"))
    d["_xrefs"] = ix
    return ix


def _similar_sections(d, ref, top=8, least=3):
    """Sections sharing RARE stamps with this one.

    The same scoring as tools/crosslink.py: a shared trait is worth
    log(N / how many sections carry it), so two passages agreeing on
    `people_of_god` have agreed on nothing and two agreeing on
    `dying_and_rising_with_christ` have agreed on almost everything they could.

    `character_roles` and `devices` are excluded for the reasons measured
    there: roles are over-stamped, and every Hebrew poem carries parallelism so
    devices make all poetry look alike.
    """
    noise = {"character_roles", "devices"}
    by = {}
    for r, rows in (d.get("stamp_by_sec") or {}).items():
        by[r] = {x["id"] for x in rows if x.get("category") not in noise}
    me = by.get(ref)
    if not me:
        return []
    n = max(len(by), 1)
    df = d.get("stamp_df") or {}
    out = []
    for other, ids in by.items():
        if other == ref:
            continue
        both = me & ids
        if len(both) < least:
            continue
        score = sum(math.log(n / max(df.get(x, 1), 1)) for x in both)
        out.append((score, other, sorted(both, key=lambda x: df.get(x, 0))))
    out.sort(reverse=True)
    return [{"ref": r, "score": round(sc, 1),
             "title": d.get("sectitle", {}).get(r, ""),
             "shared": sh[:5]} for sc, r, sh in out[:top]]


def _events_index(d):
    """-> {ref: [event rows]} from out/events.jsonl.gz, loaded once."""
    got = d.get("_events")
    if got is not None:
        return got
    ix = collections.defaultdict(list)
    p = OUT / "events.jsonl.gz"
    if p.exists():
        for line in gzip.open(p, "rt", encoding="utf-8"):
            row = json.loads(line)
            if row.get("ref"):
                ix[row["ref"]].append(row)
    d["_events"] = ix
    return ix


_EVENT_PROFILES = None


def _event_profiles():
    """stamp id -> what its sections share (tools/event_profiles.py)."""
    global _EVENT_PROFILES
    if _EVENT_PROFILES is None:
        p = OUT / "event-profiles.json"
        _EVENT_PROFILES = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _EVENT_PROFILES


def _has_sequence(d, ref):
    """Whether api_sequence would find anything for this section: any
    narrative event in its span. The button used to be drawn on every row and
    did nothing where there was none (the events layer is mostly Hebrew
    narrative) — the sequence button worked inconsistently."""
    try:
        b, c0, v0 = ref.split(".")
        c0, v0 = int(c0), int(v0)
    except ValueError:
        return False
    keys = d.get("_ev_keys")
    if keys is None:
        keys = collections.defaultdict(list)
        for k in _events_index(d):
            p = k.split(".")
            if len(p) == 3 and p[1].isdigit() and p[2].isdigit():
                keys[p[0]].append((int(p[1]), int(p[2])))
        for v in keys.values():
            v.sort()
        d["_ev_keys"] = keys
    end = next((s for s in sorted(d.get("secstart", {}).get(b, [])) if s > (c0, v0)), None)
    import bisect
    ks = keys.get(TO_MACULA.get(b, b), [])
    i = bisect.bisect_left(ks, (c0, v0))
    return i < len(ks) and (end is None or ks[i] < end)


def api_sequence(d, q):
    """What happens in this passage, in order, with who does it.

    2026-09-16: allow drill-ins to sequence diagrams for the events.

    THE SCOPE IS ONE PASSAGE, AND THAT IS THE HONEST ONE. `events` records the
    participants of a CLAUSE -- who is named in it -- not who is the same
    person across an episode, so "Abraham", "he" and "the young man" are three
    strings and nothing here pretends otherwise. Within a passage that is
    enough to show the order of what happens and the actor each clause names,
    which is a sequence; tracking one actor through it is the swimlane, and
    that still needs the participant resolution BACKLOG records.

    Rows are MERGED on verse and verb. The extraction emits one row per
    verb-and-participant rather than per verb, so Genesis 22:3 arrives as 22
    rows for six actions -- "took" three times with a different object each
    time. Unmerged it reads as a stammer.

    `quoted` is carried through and not flattened: an action inside someone's
    speech is a different thing from a narrated one, and a sequence that mixes
    them silently would claim the text says something happened when it says
    someone said it would.
    """
    ref = (q.get("ref") or [""])[0]
    if not ref:
        return {"found": False}
    try:
        b, c0, v0 = ref.split(".")
        c0, v0 = int(c0), int(v0)
    except ValueError:
        return {"found": False}
    # an unknown book or chapter answers at once (2026-10-21, the security
    # seat, finding 3): it walked the whole events index to find nothing
    if c0 not in d["chapters"].get(b, ()):
        return {"found": False}

    # The section runs to the next section start in the same book.
    starts = sorted(d.get("secstart", {}).get(b, []))
    end = None
    for (c, v) in starts:
        if (c, v) > (c0, v0):
            end = (c, v)
            break

    mac = TO_MACULA.get(b, b)
    ix = _events_index(d)
    gl = d.get("lemgloss") or {}
    steps, seen = [], {}
    for (c, v) in sorted({(int(k.split(".")[1]), int(k.split(".")[2]))
                          for k in ix if k.split(".")[0] == mac}):
        if (c, v) < (c0, v0) or (end and (c, v) >= end):
            continue
        for row in ix.get(f"{mac}.{c}.{v}", []):
            key = (c, v, row.get("gloss"))
            if key in seen:
                cur = seen[key]
            else:
                cur = {"ref": f"{b}.{c}.{v}", "verse": v, "chapter": c,
                       "act": row.get("gloss") or row.get("lemma"),
                       "lemma": row.get("lemma"),
                       "quoted": bool(row.get("quoted")),
                       "who": [], "what": [], "where": []}
                seen[key] = cur
                steps.append(cur)
            for role, bucket in (("s", "who"), ("o", "what"), ("pp", "where")):
                for lem in (row.get("participants") or {}).get(role, []):
                    label = _g(gl, lem) or lem
                    if label not in cur[bucket]:
                        cur[bucket].append(label)
    if not steps:
        return {"found": False}
    # WHO POINTS AT THIS PASSAGE, and what resembles it. 2026-09-16: surface
    # "similar events", if possible, and "references
    # to this event", if they exist.
    #
    # They are different kinds of claim and are kept apart. A cross-reference
    # is an EDITOR's judgement, carried in from the Berean parallel notes --
    # 2,026 of them, precise and sparse. A similar section is a MODEL's
    # reading, scored on the rarity of what two passages share. One is
    # inherited and one is derived, and a card that merged them would launder
    # the second into the first.
    xi = _xref_index(d)
    refs = []
    lo, hi = (c0, v0), (end or (99, 99))
    for (c, v) in sorted({(int(k.split(".")[1]), int(k.split(".")[2]))
                          for k in xi if k.split(".")[0] == b}):
        if not (lo <= (c, v) < hi):
            continue
        for other, oend, direction in xi[f"{b}.{c}.{v}"]:
            # One row per TARGET. Several verses of a section can carry a note
            # to the same place, and listing it once per source verse says
            # nothing extra while looking like more evidence.
            if any(x["ref"] == other for x in refs):
                continue
            refs.append({"at": f"{b}.{c}.{v}", "ref": other, "end": oend,
                         "direction": direction})
    return {"found": True, "ref": ref,
            "title": d.get("sectitle", {}).get(ref, ""),
            "through": f"{b}.{end[0]}.{end[1]}" if end else None,
            "steps": steps,
            "narrated": sum(1 for x in steps if not x["quoted"]),
            "spoken": sum(1 for x in steps if x["quoted"]),
            "xrefs": refs,
            "similar": _similar_sections(d, ref)}


def api_events(d, q):
    """Events by kind, ranked within each by how much of the corpus they hold."""
    rows = collections.defaultdict(list)
    cat_of = {}
    for sid, refs in (d.get("stamp_secs") or {}).items():
        for ref in refs[:1]:
            for r in d.get("stamp_by_sec", {}).get(ref, []):
                if r["id"] == sid:
                    cat_of[sid] = r.get("category")
                    break
    for sid, refs in (d.get("stamp_secs") or {}).items():
        c = cat_of.get(sid)
        if c:
            rows[c].append((len(refs), sid,
                            len({x.split(".")[0] for x in refs})))

    out = []
    # EVENTS AS NODES FIRST. 2026-09-29: the tag-based list did a
    # nice job with categorization, but it was disappointing on reaching
    # the events, which were not really nodes. These are:
    # each opens a card with its tellings, the people in it, and its
    # cross-references. In canon order, which is not a claim of chronology.
    evs = _events(d)["events"]
    for scope, label in EVENT_SCOPES:
        got = {k: e for k, e in evs.items() if e.get("scope", "gospels") == scope}
        if not got:
            continue

        def sub(e):
            n, books = len(e["tellings"]), len({t["first"].split(".")[0] for t in e["tellings"]})
            return (f"told {n} {'time' if n == 1 else 'times'} · "
                    f"{books} {'book' if books == 1 else 'books'}")
        out.append({
            "id": "ev-nodes-" + scope, "name": label,
            "count": len(got), "instances": sum(len(e["tellings"]) for e in got.values()),
            "unit": "tellings",
            "note": "Each event is a card: every passage that tells it, who is in it, and "
                    "the passages it points to, with the evidence for each. " + EVENT_CREDIT,
            "items": [{"kind": "event", "key": k, "title": e["title"], "sub": sub(e)}
                      for k, e in got.items()]})
    by_stamp = _events(d)["by_stamp"]
    for key, label, only, note in EVENT_KINDS:
        src = ("prophetic_categories" if key in ("visions", "oracles") else key)
        got = [x for x in rows.get(src, []) if not only or x[1] in only]
        if not got:
            continue
        got.sort(reverse=True)
        out.append({
            "id": "ev-" + key, "name": label,
            "count": len(got), "instances": sum(c for c, _s, _b in got),
            "note": note,
            # a named event that has become a node opens the node; its
            # stamped sections are one click further, on the card
            "items": [{"kind": "event", "key": by_stamp[sid], "title": sid.replace("_", " "),
                       "sub": f"an event card · {c} sections stamped · {bk} books"}
                      if sid in by_stamp else
                      {"kind": "stamp", "key": "stamp:" + sid,
                       "title": sid.replace("_", " "),
                       "sub": f"{c} sections · {bk} books"}
                      for c, sid, bk in got]})
    return {"kinds": out}


def api_lists(d, q):
    """Everything the graph knows as a THING, by kind.

    One shape for all of them, ranked by the hub formula where it has an
    opinion -- closure x reach x narratives, see tools/hubrank.py -- and by
    citation count where it does not. The count that decides the order is
    printed, because an order a reader cannot check is the fault the People
    list had for months.
    """
    hub = d.get("hubscore") or {}
    verses_in = _person_verses(d)
    by = collections.defaultdict(list)
    for e in d["ents"].values():
        if e.get("type"):
            by[e["type"]].append(e)

    out = []
    for kind, label in LIST_KINDS:
        # RANK, DO NOT EXCLUDE. The standing rule, and this broke it twice over.
        #
        # A `len(refs) > 2` floor silently deleted most of every small list --
        # 13 of 15 covenants, 8 of 12 divine beings, 7 of 12 feasts -- while
        # `count` below counted the UNFILTERED set, so the header promised 15
        # and the list could never show more than 2. 2026-09-18, on
        # finding it: fix it as well. And earlier, on the same fault in
        # another list: better no list than just 2.
        #
        # Two references is not evidence of nothing; it is evidence of two
        # places, and a reader looking for a specific covenant is exactly who
        # the floor shut out. Ranking already puts thin entries last, which is
        # what the floor was really for.
        rows = list(by.get(kind, []))
        if not rows:
            continue

        def rank(e):
            sc = hub.get(e["id"])
            if sc is not None:
                return (2, sc)
            n = _person_count(verses_in, e) if kind == "person" else None
            return (1, n) if n is not None else (0, len(e.get("refs") or []))

        rows.sort(key=rank, reverse=True)
        items = []
        # UNCAPPED HERE, CUT IN `page_sets`. The 60 was a page the server
        # chose, and "Show more" could never reach past it -- 1,681 people
        # behind a list that stopped at 60.
        for e in rows:
            n = _person_count(verses_in, e) if kind == "person" else None
            items.append({"id": e["id"], "title": e["name"],
                          # the seven Marys in the people list say which is which
                          "sub": ((f"{n} verses · " if n is not None else "")
                                  + (_who(e) or e.get("desc") or "")[:64])})
        # `count` is what the list HAS, so the footer's "N more not loaded" is
        # true. It used to count the unfiltered set while the rows were
        # filtered, which is how a header could claim 15 over a list of 2.
        out.append({"id": "k-" + kind, "name": label,
                    "count": len(rows),
                    "shown": len(items), "items": items})
    one = page_sets(out, q, default=60)
    if one is not None:
        return one
    for s in out:
        s["shown"] = len(s.get("items") or [])
    return {"kinds": out}


def api_contrast(d, q):
    """One contrast pair, with the verses that set the two against each other.

    2026-09-16: this is a pattern and should be drillable; the way that
    reversals work would be a good way to handle it.

    Right on both counts. A contrast IS a pattern -- righteous against wicked,
    folly against knowledge -- and it was the one Explore list with no card
    behind it, so the rows read as a finding and went nowhere. The refs were on
    disk the whole time; nothing had asked for them.

    `kind` is carried through rather than hidden: `contrast` is a straight
    opposition and `frustrated` is the shape where the first is expected and
    the second happens instead -- "they did not listen" against "I spoke". They
    are different claims and the card says which.
    """
    a = (q.get("a") or [""])[0]
    b = (q.get("b") or [""])[0]
    if not a or not b:
        return {"found": False}
    rows = [c for lst in d["contrasts"].values() for c in lst
            if c.get("a") == a and c.get("b") == b]
    if not rows:
        return {"found": False}
    refs, kinds, slots = [], set(), set()
    for c in rows:
        for r in c.get("refs") or []:
            if r not in refs:
                refs.append(r)
        if c.get("kind"):
            kinds.add(c["kind"])
        if c.get("slot"):
            slots.add(c["slot"])
    return {"found": True, "a": a, "b": b,
            "kinds": sorted(kinds), "slots": sorted(slots),
            "count": sum(c.get("count", 0) for c in rows),
            "refs": sorted(refs, key=_vkey_macula),
            "note": ("The text sets these two against each other. "
                     + ("“frustrated” marks the shape where the first is "
                        "expected and the second happens instead — “they did "
                        "not listen” against “I spoke”. "
                        if "frustrated" in kinds else "")
                     + "Read from MACULA's contextual English rather than from "
                       "morphology, so it is an inherited reading, not a "
                       "derivation — see tools/contrast.py.")}


def api_theme(d, q):
    """One theme, with every axis of evidence that named it.

    2026-09-18: the theme links themselves were not working either.
    They were dead rows — the list rendered a name and the register
    behind it was unreachable.

    What it holds is the point: `axes` is which INDEPENDENT methods found this
    theme, `notes` is the measured corroboration between them, and `limits` is
    what the register itself says it cannot support. A theme three methods find
    is a different claim from one a model stamped often, and a reader can only
    weigh that if the axes are on the card.
    """
    tid = (q.get("id") or [""])[0]
    rows = [r for r in d.get("theme_register") or []
            if not any(k.startswith("_") for k in r)]
    r = next((x for x in rows if x.get("id") == tid), None)
    if not r:
        return {"found": False}
    return {"found": True, "id": r["id"], "name": r.get("name") or r["id"],
            "axes": r.get("axes") or [], "books": r.get("books") or [],
            "sections": r.get("sections"), "verses": r.get("verses"),
            "recall": r.get("recall"),
            "notes": r.get("notes") or [], "limits": r.get("limits") or []}


_MINED_SETS = [
    # (id, name, note, test)
    ("m-events", "Events both testaments repeat",
     "The same kind of event — the same verb or its Septuagint rendering, "
     "with the same named people, things or kinds of thing — told in both "
     "testaments. Counted in accounts: a retelling (Chronicles of Kings, one "
     "gospel of another) and a New Testament quotation count once.",
     lambda r: r["family"] == "event" and r["testaments"] == "OT+NT"),
    ("m-seq", "This, then that",
     "Two or three events told in the same order, in places far apart: the "
     "narrative's own sequence (the Hebrew wayyiqtol, the Greek past tense "
     "joined by καί or δέ), not a sequence imposed on it.",
     lambda r: r["kind"] in ("link: sequence", "chain: narrative sequence")),
    ("m-ties", "Tied by cause, purpose or condition",
     "Two events the text joins by what one does to the other — because, so "
     "that, if, but rather, as — repeated with the same parts.",
     lambda r: r["family"] == "link" and r["kind"] != "link: sequence"),
    ("m-one", "Repeated within one testament",
     "Events that recur, but only in the Old Testament or only in the New.",
     lambda r: r["family"] == "event" and r["testaments"] != "OT+NT"),
]


def _mined_sets(d):
    """The explorer's lists from the miner: the sure findings by kind, then
    the looser ones for digging, each saying why it is looser."""
    rows = [d["mined"]["rows"][i] for i in d["mined"]["top"]
            if i in d["mined"]["rows"]]
    item = lambda r: {"kind": "pat", "key": "m:" + r["id"],  # noqa: E731
                      "title": r["pattern"],
                      "crosses": {"direct": r["testaments"] == "OT+NT"},
                      "sub": f"{r['accounts']} accounts · {r['books']} books"}
    out, deeper = [], []
    for sid, name, note, test in _MINED_SETS:
        items = []
        for r in rows:
            if not test(r):
                continue
            if mined_tier(r)[0] == "sure":
                items.append(item(r))
        out.append({"id": sid, "name": name, "evidence": "counted",
                    "count": len(items), "note": note, "items": items})
    for r in rows:
        tier, why = mined_tier(r)
        if tier != "sure":
            it = item(r)
            it["sub"] += " · " + "; ".join(why)
            deeper.append(it)
    out.append({"id": "m-deeper", "name": "Looser matches, for digging",
                "evidence": "counted, less certain", "count": len(deeper),
                "note": "Repeats resting on less: a word that is only similar "
                        "to another rather than the same word, or only two "
                        "independent accounts. Each says which.",
                "items": deeper})
    return out


# ---- Patterns, by what recurs (plan A.8, P-58) ------------------------------
# 2026-09-30: Patterns were not working for the most part; the
# overhaul approved groups the section by what recurs -- what the text says
# it repeats, its refrains, the story shapes it retells, how it is built -- and
# keeps the counted statistics last, for digging, named by an example verse.

_RECURS = None


def _recurs():
    global _RECURS
    if _RECURS is None:
        p = OUT / "recurs.json"
        _RECURS = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _RECURS


def _store_ref(d, mref):
    """MACULA 'Gen.25.21' -> the store's 'Gen 25:21' (Berean numbering)"""
    b, c, v = bsb_ref(d, mref).split(".")
    return f"{MACULA_BACK.get(b, b)} {c}:{v}"


_SHAPE_VERSES = None


def _shape_verses():
    """reversal kind -> the verses the corpus clause tags pin it to (DeepSeek
    Flash, medium or high)"""
    global _SHAPE_VERSES
    if _SHAPE_VERSES is None:
        by = collections.defaultdict(set)
        for cid, ts in _clause_tags().items():
            for t in ts:
                if t.get("kind") == "stamp" and t.get("strength") in ("high", "medium"):
                    by[t["tag"]].add(cid.split("#")[0])
        _SHAPE_VERSES = by
    return _SHAPE_VERSES


def _story_shapes(d, sets):
    """The reversals, each as the event cards its passages fall in: "the
    barren woman conceives" is Rebekah, Manoah's wife, Hannah and Elizabeth
    side by side. A passage in no event is shown as a gap, which says where
    the event list is thin (Sarah, Gen 18 and 21; Rachel, Gen 30).

    WRONG TURN, KEPT: first built from the September SECTION stamps, whose
    sections are whole passages -- "humiliation to vindication" (315
    sections) brought in the golden calf and the allotment of the land. The
    clause tags pin a kind to its clauses, and the later pass disputed about
    half of the section stamps for the typological kinds; the clauses are
    used, and each event is ranked by how many of its verses carry the kind."""
    rev = next((s for s in sets if s["id"] == "reversals"), None)
    pinned = _shape_verses()
    out = []
    for it in (rev or {}).get("items", []):
        sid = it["key"].split(":", 1)[-1]
        vs = sorted(pinned.get(sid, ()), key=_vkey)
        evn, evt, gaps = collections.Counter(), {}, collections.OrderedDict()
        for ref in vs:
            got = events_at(d, _store_ref(d, ref))
            if got:
                e = got[0]
                evn[e["id"]] += 1
                evt[e["id"]] = e["title"]
            else:
                # a gap, shown once per chapter
                sr = _store_ref(d, ref)
                gaps.setdefault(sr.rsplit(":", 1)[0], sr)
        evs = [{"id": k, "title": evt[k], "n": n} for k, n in evn.most_common()]
        n = len(vs)
        out.append({"kind": "shape", "key": it["key"],
                    "title": it["title"][:1].upper() + it["title"][1:],
                    "sub": f"{n} verses · {len(evn)} event cards" if n else it.get("sub"),
                    "events": evs, "gaps": list(gaps.values()), "n_gaps": len(gaps)})
    # the sharpest first: most of its verses fall in event cards
    out.sort(key=lambda r: -(len(r["events"]) / (1 + r["n_gaps"])))
    # THE EVENT TEMPLATES FIRST (plan A.9): the eight families, each with the
    # events and arcs that are its instances
    fams = []
    for fid, f in (_templates().get("families") or {}).items():
        stages = " → ".join((f"[{s['name']}]" if s["optional"] else s["name"])
                            for s in f["stages"])
        fams.append({"kind": "shape", "key": "tpl_" + fid, "ent": True,
                     "title": "Story pattern: " + f["name"],
                     "sub": f"{stages} · {len(f['instances'])} instances",
                     "events": [{"id": i["instance"],
                                 "title": (d["ents"].get(i["instance"]) or {}).get("name",
                                                                                    i["title"])}
                                for i in f["instances"]],
                     "gaps": [], "n_gaps": 0})
    # a reversal a reading tagged that is now a story pattern says so: two rows
    # for one shape, the pattern built from the text, the tag from a reading
    built = {"barren_woman_conceives": "The barren woman conceives",
             "younger_over_elder": "The younger over the elder",
             "death_produces_life": "Death to life"}
    for r in out:
        sid = r["key"].split(":", 1)[-1]
        if sid in built:
            r["sub"] = f"also built as the story pattern “{built[sid]}” · " + (r["sub"] or "")
    return fams + out


def _taxonomy_rows(kind):
    """A row per group of messages or speech acts, or per role pattern, each
    member a way in (split out of the story shapes, 2026-09-30)."""
    fams = []
    if kind == "roles":
        for p in (_roles().get("patterns") or {}).values():
            fams.append({"kind": "shape", "key": p["id"], "ent": True,
                         "title": "Role pattern: " + p["name"],
                         "sub": " · ".join(s["name"] for s in p["slots"])
                                + f" · {len(p['rows'])} rows",
                         "events": [{"id": r["id"], "title": r["name"]} for r in p["rows"]],
                         "gaps": [], "n_gaps": 0})
        return fams
    if kind == "acts":
        for g in (_speech_acts().get("groups") or {}).values():
            acts = [_speech_acts()["acts"][a] for a in g["acts"]]
            fams.append({"kind": "shape", "key": g["id"], "ent": True,
                         "title": "Speech-act group: " + g["name"],
                         "sub": f"{len(acts)} acts · {sum(a['count'] for a in acts):,} verses",
                         "events": [{"id": a["id"], "title": a["name"]} for a in acts],
                         "gaps": [], "n_gaps": 0})
        return fams
    # the divine messages, a row per group, each message a way in
    for g in (_messages().get("groups") or {}).values():
        ms = [_messages()["messages"][m] for m in g["messages"]]
        fams.append({"kind": "shape", "key": g["id"], "ent": True,
                     "title": "Message group: " + g["name"],
                     "sub": f"{len(ms)} messages · {sum(m['count'] for m in ms):,} verses",
                     "events": [{"id": m["id"], "title": m["name"]} for m in ms],
                     "gaps": [], "n_gaps": 0})
    return fams


_TALIO = re.compile(r"\b(\w+) for (?:an? |the )?\1\b", re.I)


def _climaxes(d, sets):
    """Ladders that climb, not lists. "Eye for eye, tooth for tooth" (Exod
    21:23-25) and "gold for the gold, silver for the silver" (1 Chr 28) pass
    the chain test and are not gradatio; a chain whose verses say "X for X"
    is left out."""
    lad = next((s for s in sets if s["id"] == "ladder"), None)
    out = []
    for it in (lad or {}).get("items", []):
        start = it["key"].split("|")[0]
        _e, text = _verse_text(d, start)
        if _TALIO.search(text or ""):
            continue
        out.append(it)
    return out


def _dig_item(d, it):
    """A mined row named by an example verse instead of its notation"""
    r = d["mined"]["rows"].get(it["key"][2:]) if it.get("key", "").startswith("m:") else None
    ex = ((r or {}).get("examples") or [{}])[0].get("ref") if r else None
    if not ex:
        return it
    eref, text = _verse_text(d, ex)
    words = (text or "").split()
    line = " ".join(words[:12]) + ("…" if len(words) > 12 else "")
    return dict(it, title=f"“{line}” — {prettify_ref(eref)}",
                sub=f"{it.get('sub', '')} · {it['title']}")


def prettify_ref(eref):
    b, c, v = eref.split(".")
    return f"{TITLE.get(MACULA_BACK.get(b, b), b)} {c}:{v}"


def api_recurs(d, q):
    """The Patterns section, by what recurs."""
    sets = api_patternsets(d, q).get("sets", [])
    by = {s["id"]: s for s in sets}
    R = _recurs()
    declared = []
    if "type" in by:
        t = by["type"]
        declared.append({"kind": "set", "key": "type", "title": "Declared types",
                         "sub": f"{t['count']} · τύπος, ἀντίτυπος, σκιά",
                         "note": t["note"], "items": t["items"]})
    for x in R.get("declared", []):
        _e, ex = _verse_text(d, _macula_ref(d, x["verses"][0]["v"])) if x["verses"] else ("", "")
        declared.append({"kind": "recur", "key": "d:" + x["id"], "title": x["title"],
                         "sub": f"{x['n']} verses · {x['books']} books",
                         "line": ex})
    refrains = []
    for x in R.get("refrains", []):
        refrains.append({"kind": "recur", "key": x["id"], "title": x["title"],
                         "sub": f"{x['n']} verses · {x['chapters']} chapters · "
                                f"{x['books']} {'book' if x['books'] == 1 else 'books'}"
                                + (f" · {len(x['across'])} more in the "
                                   + " and ".join(x["signature"]) if x["across"] else "")})
    built = []
    for sid, title in (("devices", None), ("aggregates", None)):
        if sid in by:
            s = by[sid]
            built.append({"kind": "set", "key": sid, "title": title or s["name"],
                          "sub": f"{s['count']} kinds", "note": s["note"], "items": s["items"]})
    # NOT "GENUINE CLIMAXES", though plan A.8 says so. The chain test (each
    # link's end begins the next) finds Rom 5:3-5, 2 Pet 1:5-7, Jer 15:2-3 and
    # 1 Cor 15:12-14 -- and "cubits -> work -> wheels -> chariot" (1 Kgs 7),
    # "bosom -> morning -> son -> wife" (1 Kgs 3). No rule tried separated
    # them (five steps within three verses still kept Rom 13:6-8 and Esth
    # 9:26-28), so the chains go under digging, saying what they are, rather
    # than under a heading that claims a reading the rule cannot make.
    clim = _climaxes(d, sets)
    dig = []
    if clim:
        dig.append({"kind": "set", "key": "ladder", "title": "Word chains",
                    "sub": f"{len(clim)} chains",
                    "note": "Each link's last word begins the next. A few are the text's "
                            "climaxes — Rom 5:3–5, 2 Pet 1:5–7, Jer 15:2–3, 1 Cor 15:12–14 — "
                            "and most are coincidences of common words across verses; the "
                            "chain test cannot tell them apart, so check each. Lists made by "
                            "“X for X” (eye for eye) are left out.",
                    "items": clim})
    for sid in ("m-events", "m-seq", "m-ties", "m-one", "m-deeper"):
        if sid in by:
            s = by[sid]
            dig.append({"kind": "set", "key": sid, "title": s["name"],
                        "sub": f"{s['count']:,} · {s['evidence']}", "note": s["note"],
                        "items": [_dig_item(d, it) for it in s["items"]]})
    return {"groups": [
        {"id": "declared", "title": "The text says it repeats",
         "note": "Where the text itself says it echoes an earlier word. Its own claim, so first.",
         "rows": declared},
        {"id": "refrains", "title": "Refrains and formulas",
         "note": "Lines the text repeats word for word, five words or more, in at least three "
                 "chapters — mined from the Berean and searched in the Hebrew and Greek, so a "
                 "refrain rendered two ways is still one.",
         "rows": refrains},
        # FOUR GROUPS, NOT ONE (2026-09-30: the other taxonomy sections must be
        # complete and up to date): messages, speech
        # acts and role patterns had been filed under "Recurring story
        # shapes", whose note -- "the same kind of scene told of different
        # people" -- is true of stories only
        {"id": "shapes", "title": "Recurring story shapes",
         "note": "The same kind of scene told of different people, as event cards side by "
                 "side: the story patterns, each with the stories told that way, then the "
                 "reversals a reading tagged. A passage with no event card is shown as a gap.",
         "rows": _story_shapes(d, sets)},
        {"id": "roles", "title": "Role patterns",
         "note": "The roles the text returns to — shepherd, king, priest, bridegroom, father, "
                 "servant, prophet — each with the figures who fill it, a column for each part "
                 "of the role.",
         "rows": _taxonomy_rows("roles")},
        # plan 6.16 (2026-10-03: 40 deserves its own significant number
        # card; labelled "Significant number", not "symbolic")
        {"id": "numbers", "title": "Significant numbers",
         "note": "A number the text counts as a span — forty days, forty years — with "
                 "the phrases it repeats and the places where the text itself sets one "
                 "occasion beside another. What the number means is not said: the text does "
                 "not say it.",
         "rows": [{"kind": "shape", "key": nid, "ent": True,
                   "title": f"Significant number: {n['name']}",
                   "sub": f"{n['counts']['occasions']} occasions · {len(n['phrases'])} phrases · "
                          f"{len(n['joins'])} set side by side by the text",
                   "events": list({e["id"]: {"id": e["id"], "title": e["title"]}
                                   for o in n["occasions"] for e in o.get("events", [])}.values())}
                  for nid, n in _numbers().items()]},
        # plans 6.15, 6.17 (2026-10-04: these need to be consolidated
        # somewhere in the Explore page as well)
        {"id": "told-again", "title": "Stories told again",
         "note": "Where one account takes up an earlier one — its words, or the steps of its "
                 "story — each card setting the two side by side in the text's own words. Not a "
                 "claim that one was told with the other in mind; the reader draws the conclusion.",
         "rows": _told_again_rows(d)},
        {"id": "shared", "title": "What two verses share",
         "note": "A rare phrase two verses have word beside word in the Hebrew or Greek, read by "
                 "two judges and explained: words one verse takes up from another, and images or "
                 "expressions both use. Each opens its verse, with the explanation beside it.",
         "rows": _shared_rows(d)},
        {"id": "messages", "title": "Messages",
         "note": "What God, or someone on his behalf, says — “Do not fear”, “Return to "
                 "me” — in ten groups, each message found by its form in the Hebrew or Greek.",
         "rows": _taxonomy_rows("messages")},
        {"id": "acts", "title": "Speech acts",
         "note": "The kinds of speaking — blessing, lament, rebuke, vow — in five groups by "
                 "what the speaking does, found where the text names the act.",
         "rows": _taxonomy_rows("acts")},
        {"id": "built", "title": "How the text is built",
         "note": "Shape rather than subject: the devices a reading recognised, the "
                 "collections the text names, and the pairs it sets against each other.",
         "rows": built},
        {"id": "dig", "title": "For digging",
         "note": "Mechanical finds: word chains, and counted repeats of events and of their "
                 "order, each named by an example verse. Mostly the grammar of narrative; "
                 "check each.",
         "rows": dig}]}


def _told_again_rows(d):
    """Explore's "Stories told again": each recorded story echo as the two
    event cards it joins (ontology/relations/story-echoes.jsonl), then the
    stories told again that 6.17 found verse by verse."""
    rows = []
    label = {"re_enacts": "re-enacts", "takes_up": "takes up the words of"}
    for r in _rows(ROOT / "ontology" / "relations" / "story-echoes.jsonl"):
        a, b = d["ents"].get(r["src"]), d["ents"].get(r["dst"])
        if not a or not b:
            continue
        rows.append({"kind": "shape", "key": r["src"], "ent": True,
                     "title": f"{a['name']} — {b['name']}",
                     "sub": f"{label.get(r['type'], r['type'])} · {len(r.get('pairs') or [])} "
                            f"{'pair' if len(r.get('pairs') or []) == 1 else 'pairs'} side by side",
                     "events": [{"id": r["src"], "title": a["name"]}, {"id": r["dst"], "title": b["name"]}]})
    # plan 6.18: each story told again between two events as the two cards;
    # those with an end that has no event yet, as verses, below
    told = _rows(ROOT / "ontology" / "told-again.jsonl")
    for r in told:
        a, b = d["ents"].get(r.get("later_event") or ""), d["ents"].get(r.get("earlier_event") or "")
        if a and b and r["later_event"] != r["earlier_event"]:
            # the verses the steps come from, beside each event's name: some
            # events span chapters ("Samson's downfall" is Judges 13-16, and
            # its echo of Jacob at Peniel is the birth announced in Judg 13)
            def span(i):
                refs = sorted({p[i][0] for p in r["beats"]}, key=lambda x: _vkey_macula(_macula_ref(d, x)))
                return refs[0] if len(set(refs)) == 1 else f"{refs[0]}–{refs[-1].split(' ')[-1]}" \
                    if refs[0].rsplit(' ', 1)[0] == refs[-1].rsplit(' ', 1)[0] else f"{refs[0]}–{refs[-1]}"
            rows.append({"kind": "shape", "key": r["later_event"], "ent": True,
                         "title": f"{a['name']} ({span(0)}) — {b['name']} ({span(1)})",
                         "sub": f"has the same steps as · {len(r['beats'])} steps side by side"
                                + (" · named by the text" if r.get("named") else ""),
                         "events": [{"id": r["later_event"], "title": a["name"]},
                                    {"id": r["earlier_event"], "title": b["name"]}]})
    verse = [x for x in _rows(ROOT / "ontology" / "allusions.jsonl") if x["kind"] == "story_echo"]
    verse_items = [{"kind": "ref", "key": _verse_text(d, _macula_ref(d, x["nt"]))[0],
                    "title": f"{x['nt']} — {x['ot']}", "sub": x["words"]} for x in verse]
    verse_items += [{"kind": "ref", "key": _verse_text(d, _macula_ref(d, r["beats"][0][0][0]))[0],
                     "title": f"{r['later']} — {r['earlier']}",
                     "sub": f"{len(r['beats'])} steps side by side"}
                    for r in told if not (d["ents"].get(r.get("later_event") or "")
                                          and d["ents"].get(r.get("earlier_event") or ""))]
    if verse_items:
        rows.append({"kind": "set", "key": "told-again-verses", "title": "Told again, verse by verse",
                     "sub": f"{len(verse_items)} pairs",
                     "note": "Stories told again where one side has no event card yet; each opens its "
                             "verse with the steps side by side.",
                     "items": verse_items})
    return rows


def _shared_rows(d):
    """Explore's "What two verses share" (plan 6.17): the images and
    expressions both use, one row per node naming its verses; then the words
    taken up, one row per link. Each opens its verse in place."""
    nodes, words = {}, []
    for x in _rows(ROOT / "ontology" / "allusions.jsonl"):
        if x["kind"] == "shared_image":
            nodes.setdefault(x["node"], set()).update((x["nt"], x["ot"]))
        elif x["kind"] == "words_taken_up":
            words.append(x)
    def key(r):
        return _vkey_macula(_macula_ref(d, r))
    rows = [{"kind": "set", "key": "shared-images", "title": "An image or expression both use",
             "sub": f"{len(nodes)} images, {sum(len(v) for v in nodes.values())} verses",
             "note": "Each names what the verses have in common, in the text's words, with no claim "
                     "that one points to the other.",
             "items": [{"kind": "ref", "key": _verse_text(d, _macula_ref(d, min(v, key=key)))[0],
                        "title": n, "sub": " · ".join(sorted(v, key=key))}
                       for n, v in sorted(nodes.items(), key=lambda t: (-len(t[1]), t[0].lower()))]},
            {"kind": "set", "key": "words-taken-up", "title": "Words taken up",
             "sub": f"{len(words)} links",
             "note": "A New Testament verse that quotes or closely reproduces an Old Testament "
                     "verse's words. Where the Berean editors note the same link, the explanation "
                     "is shown with their note.",
             "items": [{"kind": "ref", "key": _verse_text(d, _macula_ref(d, x["nt"]))[0],
                        "title": f"{x['nt']} — {x['ot']}", "sub": x["words"]}
                       for x in sorted(words, key=lambda x: (key(x["nt"]), key(x["ot"])))]}]
    return rows


def api_recur(d, q):
    """One formula or refrain: every verse, by book, each saying how it was
    found (the Berean's wording, or the same Hebrew/Greek words rendered
    differently)."""
    key = (q.get("id") or [""])[0]
    R = _recurs()
    if key.startswith("d:"):
        x = next((y for y in R.get("declared", []) if y["id"] == key[2:]), None)
        if not x:
            return {"found": False}
        # the editors' sources are ALREADY the Berean's numbering (recurs.py):
        # through bsb_ref, Matt 4:14's Isa 9:2 printed as "Isaiah 9:3" -- the
        # Hebrew shift applied to an English number. Psalms escaped only
        # because the Berean code "Ps" is not a key of the MACULA map
        how = {_macula_ref(d, v["v"]): ("points to " + ", ".join(
                   prettify_ref(t) for t in v["to"]) if v["to"] else None)
               for v in x["verses"]}
        return {"found": True, "title": x["title"], "note": x["note"], "total": len(how),
                "books": _by_book(d, how)}
    x = next((y for y in R.get("refrains", []) if y["id"] == key), None)
    if not x:
        return {"found": False}
    how = {_macula_ref(d, v): None for v in x["english"]}
    for v in x["across"]:
        how[_macula_ref(d, v)] = "the same words in the original, translated differently"
    return {"found": True, "title": x["title"], "total": len(how),
            "note": "Every verse where the text says it"
                    + (", and where the same " + " and ".join(x["signature"])
                       + " words stand together under another rendering"
                       if x["across"] else "") + ".",
            "variants": x.get("variants") or [], "books": _by_book(d, how)}


def api_patternsets(d, q):
    """The pattern layers, side by side, each showing its strongest members.

    2026-09-16: add a second patterns prompt for richer patterns, or an
    overall patterns set of lists which includes the fixed phrases where the
    text repeats, but also a rich patterns taxonomy with the most interesting
    patterns in each category.

    The categories are not a classification of patterns; they are a
    classification of **what kind of evidence stands behind one**, which is the
    distinction this project keeps having to redraw:

        fixed phrases   a repeated shape with a dominated slot   COUNTED
        node templates  the same, over the word-group tree       COUNTED
        ladders         each link's end begins the next          MECHANICAL
        devices         chiasm, inclusio, merism                 A MODEL'S READING
        reversals       last-first, death-produces-life          A MODEL'S READING
        declared types  the NT naming an OT antecedent           THE TEXT'S CLAIM
        themes          30 themes with their evidence joined     MIXED, AND SHOWN

    A reader can then tell a ladder -- which no model asserted and every
    instance can show -- from a `chiasm` stamp, which is one model's opinion.
    Ordering within each is that layer's own strongest signal, never raw count.
    """
    out = []
    # THE COUNTED LAYERS ARE THE MINER'S NOW. 2026-09-28, choosing
    # "counted layers only": the English-template phrases and node templates
    # below give way to the pattern miner's findings (clean structure, the
    # original words, accounts not tellings); the readings — devices,
    # reversals, declared types, themes, ladders — stay. The old counted
    # layers remain only as the fallback when the miner has not been run.
    mined = bool(d["mined"]["rows"])
    if mined:
        out += _mined_sets(d)

    # FUNCTION-WORD ANCHORS GET THEIR OWN LIST. 2026-09-19, on
    # `[S] is behold` standing second among the fixed phrases: it feels
    # like a stand-alone command, and should be its own list.
    #
    # The objection holds twice. הִנֵּה is a PARTICLE and what fills [S] is a
    # pronominal suffix, so the template reads a presentative with a pronoun
    # attached as though it were subject and predicate. And "behold" is a real
    # thing the text does, so the row belongs somewhere rather than nowhere --
    # it is only wrong sitting among the phrases, pretending to predicate.
    FUNCTION_POS = {"particle", "ptcl", "suffix", "pronoun", "conjunction",
                    "preposition"}
    rank = lambda r: -((r.get("skew") or 0)
                       * math.log10(max(r.get("instances", 1), 10)))
    allp = [r for r in d["patterns"].values()
            if r.get("instances", 0) >= 8 and r.get("reach", 0) >= 3]
    pats = [r for r in allp if r.get("anchor_pos") not in FUNCTION_POS]
    gram = [r for r in allp if r.get("anchor_pos") in FUNCTION_POS]
    # THE OWNER'S RANKING, 2026-09-21: switch to the specified ranking and,
    # most importantly, pull in more complex patterns. The old key was skew x log
    # instances, which put `[S] said` — 4,892 uses, one slot, 460 different
    # subjects — at the head of the list on frequency alone. `pattern_score`
    # multiplies structure by fixed positions by root frequency by canonical
    # distance by word interest, so a shape has to be more than common.
    # Ties and unscorable rows fall back to the old key rather than to
    # nothing, so a template whose lexemes did not resolve still sorts.
    rank = lambda r: (-pattern_score(d, r),
                      -((r.get("skew") or 0)
                        * math.log10(max(r.get("instances", 1), 10))))
    pats.sort(key=rank)
    # ONE LIST WAS TWO THINGS. 2026-09-20: the list "shapes
    # built on a function word" was unremarkable, with most of the
    # patterns just triples with the relationship fixed on a common word;
    # and a highlighted list needs some level
    # of hook that makes the reader think there is some kind of deeper
    # meaning.
    #
    # The split: a function word with TWO slots relates two
    # things and is a preposition: under, between, after, before, beside,
    # like. A function word with ONE slot says something about that one thing
    # — and in Hebrew what it says is that the thing exists, does not exist,
    # or is standing right here, because the language has no present-tense
    # verb "to be" and uses a particle where English uses one.
    #
    # That is the hook, and it is not a flourish: it is why יֵשׁ and אַיִן are
    # words at all. The rule is mechanical, so nothing is hand-filed.
    nslots = lambda r: len(re.findall(r"\[[A-Z]\]", r.get("template") or ""))
    being = sorted([r for r in gram if nslots(r) <= 1], key=rank)
    relate = sorted([r for r in gram if nslots(r) > 1], key=rank)
    if being and not mined:
        n = sum(r.get("instances", 0) for r in being)
        out.append({
            "id": "being", "name": "Saying a thing is, is not, or is here",
            "evidence": "counted", "count": len(being),
            "note": "Hebrew has no present-tense verb “to be”. Where English "
                    "needs one, the text uses a bare particle: יֵשׁ that "
                    "something is, אַיִן that it is not, הִנֵּה that it is "
                    "here in front of you. The questions belong with them — "
                    "אַיֵּה asks where a thing is when the answer is meant to "
                    f"be nowhere. {n:,} uses, and not one of them a verb.",
            "items": [{"kind": "pat", "key": r["key"], "title": r["template"],
                       "lex": _lex_template(r),
                       "crosses": _crossing(d, r),
                       "sub": _pat_sub(r)} for r in being]})
    if relate and not mined:
        out.append({
            "id": "grammar", "name": "Shapes that place one thing against another",
            "evidence": "counted", "count": len(relate),
            "note": "A preposition with a slot at each end — under, between, "
                    "after, like. These are the frame the language provides "
                    "rather than anything the text composes, and they are "
                    "here so the list above is not padded with them.",
            "items": [{"kind": "pat", "key": r["key"], "title": r["template"],
                       "lex": _lex_template(r),
                       "crosses": _crossing(d, r),
                       "sub": _pat_sub(r)} for r in relate]})
    if not mined: out.append({  # noqa: E701
        # COUNT WHAT THE LIST CAN REACH. `pats` is filtered to 8+ instances in
        # 3+ books; counting `d["patterns"]` instead advertised 6,913 over a
        # list that can only ever show 2,541, with 63% unreachable. Same fault
        # as the covenants list, found by the same audit.
        "id": "fixed", "name": "Fixed phrases the text repeats",
        "evidence": "counted", "count": len(pats),
        "note": "A shape whose slot is filled the same way almost every time. "
                "Ranked by how constrained the slot is — the commonest shapes "
                "are grammar. Counts shapes occurring 8+ times across 3+ "
                "books; rarer ones are in search.",
        # CROSS-CORPUS IS THE INTERESTING KIND. 2026-09-19: the whole list was
        # to be filtered to cross-corpus patterns, as
        # they are the most interesting. A pattern the text uses in both
        # testaments is a habit of the whole Bible; one confined to a
        # testament may be a habit of a language.
        "items": [{"kind": "pat", "key": r["key"], "title": r["template"],
                       "lex": _lex_template(r),
                   "crosses": _crossing(d, r),
                   "sub": _pat_sub(r)} for r in pats]})

    # "node" -- set phrases in the sentence tree -- is deliberately absent.
    # 2026-09-16: clicking on set phrases in the sentence tree showed only
    # 2; there are many phrases that repeat, and better no list than just 2.
    #
    # The text does repeat many phrases, and the error was only about
    # where they live: that is the `fixed` layer, 12,492 clause templates. This
    # layer is the word-group TREE, 1,101 shapes at 8+ instances in 2+ books,
    # and exactly two of them have every position filled the same way every
    # time -- the Pauline greeting and "how much more".
    #
    # Loosening to 3+ instances yields 2,034 shapes and would populate the
    # list, and that is the wrong trade: a shape occurring three times with
    # identical fillers is far likelier to be chance than one occurring nine
    # times. It would buy length by weakening every entry.
    #
    # So the category is dropped rather than padded. The two rows remain in
    # out/nodepat.jsonl.gz for anyone who wants them.
    for name, rows in (("node", d.get("nodepat") or []),
                       ("nodeopen", d.get("nodepat") or []),
                       ("ladder", d.get("gradatio") or []),
                       ("type", d.get("declared_types") or []),
                       ("theme", d.get("theme_register") or [])):
        if not rows or (mined and name in ("node", "nodeopen")):
            continue
        out.append(_PSET[name](rows, d.get("lemgloss") or {})
                   if name in ("node", "nodeopen", "ladder")
                   else _PSET[name](rows))

    st = collections.defaultdict(list)
    n = max(len(d.get("stamp_by_sec") or {}), 1)
    for sid, refs in (d.get("stamp_secs") or {}).items():
        cat = None
        for ref in refs[:1]:
            for r in d.get("stamp_by_sec", {}).get(ref, []):
                if r["id"] == sid:
                    cat = r.get("category")
                    break
        if cat in ("devices", "reversals", "aggregates"):
            st[cat].append((len(refs), sid,
                            len({x.split(".")[0] for x in refs})))
    for cat, label, note in (
            ("devices", "Literary devices",
             "Shapes surfaced by automated analysis — chiasm, inclusio, merism. Rarer "
             "first, because every Hebrew poem carries parallelism."),
            ("reversals", "Reversals",
             "The last first, the barren bearing, death producing life."),
            # 2026-09-16: for the collections shape -- Fruits of the
            # Spirit, the Phil 4:8 list, Armor of God, the turn, turn list in
            # Ecclesiastes, the ten commandments, the beatitudes, the 12
            # disciples, the 12 tribes -- there are many interesting groups
            # and they would be worth surfacing.
            #
            # They were already stamped, in the `aggregates` category, and
            # nothing in the reader reached them. A COLLECTION is a third shape
            # beside the template and the ladder: not a slot filled different
            # ways and not a chain that climbs, but a set the text enumerates
            # and then treats as one thing.
            ("aggregates", "Collections the text lists",
             "A set the text names and enumerates — the fruit of the Spirit, "
             "the armor of God, the Ten Commandments, the beatitudes. Neither "
             "a template nor a ladder: a group the text counts out and then "
             "refers to as one.")):
        rows = sorted(st.get(cat, []))
        if not rows:
            continue
        # COUNT THE KINDS AND THE INSTANCES. 2026-09-16: reversals are
        # great, but are there really only 12?
        #
        # Twelve is the VOCABULARY -- the number of reversal types someone
        # wrote into the taxonomy -- and all twelve are used, between them
        # stamping 1,503 sections. Showing only the first number reads as a
        # claim about the text when it is a fact about the word list, and the
        # gap between them is the more interesting figure: a small vocabulary
        # over a large corpus is a limit of ours, not of the Bible.
        total = sum(c for c, _sid, _bk in rows)
        out.append({
            "id": cat, "name": label, "evidence": "surfaced by automated analysis",
            "count": len(rows), "instances": total,
            "note": note + f" {len(rows)} named kinds, stamped on "
                           f"{total:,} sections — the number of kinds is the "
                           f"size of our vocabulary, not a count of what the "
                           f"text does.",
            "items": [{"kind": "stamp", "key": "stamp:" + sid,
                       "title": sid.replace("_", " "),
                       "sub": (f"{c} sections · {bk} books"
                               + (" · " + DEVICE_GLOSS[sid][:74]
                                  if sid in DEVICE_GLOSS else ""))}
                      # These are VOCABULARIES, not corpora -- 28 device
                      # kinds, 12 reversal kinds, 13 collection kinds. Capping
                      # at 20 hid 8 of the devices behind a header that counted
                      # all 28, and there is nothing to page: the whole list
                      # fits on a screen.
                      for c, sid, bk in rows]})
    one = page_sets(out, q)
    return one if one is not None else {"sets": out}


# Glosses that mean a word is apparatus rather than content. Reused from the
# same judgement `tools/lexcoverage.py` had to make: no automatic test
# separates a function word from a content word, and the list is short enough
# to argue with.
_FUNCTION = {
    "and", "the", "a", "an", "of", "to", "in", "on", "at", "by", "for",
    "with", "from", "that", "this", "these", "those", "it", "its", "he",
    "she", "they", "we", "you", "i", "him", "her", "them", "us", "me",
    "my", "your", "his", "their", "our", "not", "no", "but", "or", "as",
    "if", "then", "so", "there", "here", "(et)", "et", "is", "was", "were",
    "be", "will", "all", "who", "which", "what", "when", "how", "up", "out",
    "down", "into", "upon", "also", "now", "very", "one", "two",
}


def _contentful(g):
    g = (g or "").strip().lower().strip("[]()")
    return len(g) > 2 and g not in _FUNCTION


def _node_is_fixed(r):
    s = r.get("slots") or {}
    return bool(s) and all(len(v) == 1 for v in s.values())


def _pset_node_open(rows, gloss):
    """Shapes whose reading is a template: one part holds, another varies.

    Everything the set-phrase list cannot render as a phrase arrives here, and
    it is the right home for it -- `[…] and […]` is a structure with an open
    slot, which is what this list is called. 2026-09-16: anything with
    […] is liked but has another list.

    Ranked by how much the held positions hold, so the tightest frames lead.
    Nothing is excluded: a shape is in exactly one of the two lists, and which
    one is decided by whether its own examples read as English.
    """
    def dominance(r):
        sh = []
        for v in (r.get("slots") or {}).values():
            tot = sum(c for _, c in v) or 1
            sh.append(max(c for _, c in v) / tot)
        return sum(sh) / len(sh) if sh else 0.0

    # RARITY, NOT DOMINANCE ALONE. 2026-09-16: on drilling in, the
    # examples in the list were pretty much noise.
    #
    # True, and it says something about the rows rather than the examples.
    # `[…] and […]` occurs 2,603 times across 38 books: that is coordination,
    # which is grammar, and no instance of it can be interesting because every
    # instance is the same fact. `not […] but […]` occurs 28 times and is a
    # rhetorical construction. Dominance ranked the first above the second,
    # because a shape whose only fixed part is "and" is perfectly consistent.
    #
    # Dividing by log(instances) is the same correction the Explore list
    # already carries one level up -- frequency finds grammar -- and it lifts
    # "not that but that", "not […] but […]", "this is […]" and "to when?" over
    # the conjunctions.
    # A ROW WITH NO SLOT DOES NOT BELONG AT THE TOP OF A LIST ABOUT SLOTS.
    # (Every row should show the slot.) Some of these shapes turn out to be
    # fixed in every position and merely unreadable, because every word in them
    # is a function word -- "for also now", "that what". They are still real
    # and still reachable, but they sort below the ones the heading describes.
    # SPLIT ON READABILITY, SORT ON HAVING A SLOT. Splitting on the slot
    # instead was tried and reverted: it is cleaner by definition and it
    # emptied the set-phrase list to five rows, destroying the list that had
    # just been called working. The heading still has to be honest, so rows that
    # really do vary lead, and the ones fixed in every position follow.
    keep = sorted((r for r in rows if not _readable(r, gloss)),
                  key=lambda r: (-_has_slot(r, gloss),
                                 -(dominance(r)
                                   / math.log10(max(r.get("instances", 1), 10)))))
    return {"id": "nodeopen", "name": "Structures with an open slot",
            "evidence": "counted", "count": len(keep),
            "note": "One position holds still while another varies — the "
                    "shape the text composes WITH. Ranked so CONSTRUCTIONS "
                    "lead and grammar sinks: “[…] and […]” is perfectly "
                    "consistent across 2,603 instances and tells you nothing, "
                    "while “not […] but […]” across 28 is a way of arguing. "
                    "The phrases that read as English are under “Set phrases "
                    "in the sentence tree”.",
            "items": [{"kind": "node", "key": r["shape"],
                       "title": _node_template(r, gloss) or r["shape"],
                       "sub": (lambda ph, rf: (f"{rf} · " if rf else "")
                               + f"{round(dominance(r) * 100)}% fixed · "
                               + f"{r['instances']}× · "
                               + f"{len(r.get('books') or [])} books · "
                               + r["shape"])(*_node_example(r, gloss))}
                      for r in keep]}


def _node_example(r, gloss):
    """-> (phrase, ref) an ACTUAL filling of this shape, glossed.

    2026-09-16, twice: of a row reading "Having seen that he had been
    outwitted", drilling in showed no phrase and no reason for being there;
    and of one reading "Hena and Ivvah", the reader was confused.

    Both titles were assembled from the commonest filler of each slot
    INDEPENDENTLY, and those fillers need not ever co-occur -- `cl [cl conj
    cl]` is 41% constrained, so its three top fillers come from three different
    verses and the phrase advertised exists nowhere. The second is worse for
    being half true: "Hena" and "Ivvah" really do stand together in 2 Kings
    19:13, but the first position's commonest filler comes from somewhere else
    entirely.

    A row must show a phrase the text actually has, with the verse that has it.
    """
    for ex in (r.get("examples") or []):
        parts = [(_g(gloss, f) or f) for f in ex.get("fills", [])]
        if parts:
            return " ".join(parts), ex.get("ref")
    return "", None


def _has_slot(r, gloss):
    """Does any position in this shape actually vary?

    THE SPLIT BETWEEN THE TWO LISTS. It used to be readability -- whether the
    example glossed into English -- which put 71 shapes that are fixed in every
    position into a list called "Structures with an open slot" purely because
    their words are function words. (Every row should show the slot.)

    Having a slot is what the headings are about, so it is what decides. How
    readable a row is then affects only how it is WRITTEN, not where it lives.
    """
    for v in (r.get("slots") or {}).values():
        tot = sum(c for _, c in v) or 1
        if not v or v[0][1] / tot < FIXED_SHARE:
            return True
    return False


def _readable(r, gloss):
    """Does this shape yield a phrase a reader can read, rather than a sketch?"""
    ph = _node_example(r, gloss)[0]
    # ONE content word is enough. At two, "to you grace from" -- the Pauline
    # greeting, and the most fixed shape in the corpus -- failed the test,
    # because only "grace" survives a function-word filter and the third
    # position is a nested phrase the gloss cannot reach. "(et) and (et)" still
    # scores zero and still goes to the template list.
    return sum(1 for w in ph.split() if _contentful(w)) >= 1


# How much of a position one filler must cover before it counts as holding
# still rather than varying. Two thirds is the line at which a reader stops
# seeing a slot and starts seeing a word.
FIXED_SHARE = 0.66


def _node_template(r, gloss):
    """The row written as a TEMPLATE: what holds, and what varies.

    2026-09-16: every row should show the slot -- of a list called
    "Structures with an open slot" in which most rows had none.

    The first version decided openness from the child's grammatical CLASS,
    with `np`/`pp`/`cl` open and everything else fixed. That is wrong twice
    over: a pronoun or an adjective is very often the position that varies
    (`np [pron cj pron]` is "[…] and […]", not "I and you"), and a class cannot
    know what the corpus actually does with it.

    The data already knows. A position whose commonest filler covers most of
    the instances is holding still; one spread across many fillers is the slot.
    So the share decides, and every row shows its own structure.
    """
    inner = r.get("shape", "")
    kids = inner[inner.find("[") + 1:inner.rfind("]")].split() if "[" in inner         else []
    slots = r.get("slots") or {}
    out = []
    for i, _cls in enumerate(kids):
        v = slots.get(str(i)) or []
        tot = sum(c for _, c in v) or 1
        top, n = (v[0] if v else ("", 0))
        word = _g(gloss, top) or top
        # Under FIXED_SHARE the position is doing different work in different
        # instances, which is what a slot is.
        out.append(word if v and n / tot >= FIXED_SHARE and word else "[…]")
    tidy = []
    for x in out:
        if x == "[…]" and tidy and tidy[-1] == "[…]":
            continue
        tidy.append(x)
    # A template of nothing but slots says nothing; the caller falls back to
    # the grammar code, which at least names the kind of node.
    if not any(x != "[…]" for x in tidy):
        return ""
    return " ".join(tidy)


def _pset_node(rows, gloss):
    """The twenty most FIXED phrases in the word-group tree.

    2026-09-16: loosen the list to a top 20 instead of 2? Even the two are
    not over the top interesting, but in a group of 20 they would be fine.

    That is the right instrument. The first version asked a yes/no question --
    is every position filled identically every time -- and exactly two shapes
    in 1,101 answered yes. Ranking instead of thresholding keeps the same
    evidence and stops it being all-or-nothing, and the point about the two
    is fair: the Pauline greeting is worth seeing in a list, not as a list.

    Ranked by how much the commonest filler dominates each position, averaged.
    A CONTENT-WORD FLOOR comes first, because dominance alone is highest where
    the fillers are particles: `np [np cj np]` occurs 2,603 times and reads
    "(et) and (et)", `np [om np]` occurs 7,733 times and reads "(et) כָּל".
    Requiring two positions to hold a real word cuts 1,101 to 573 and turns the
    list into "thus says LORD" (326x, 47 books), "what the Spirit says to the
    churches", "full of fine flour", "Truly I say to you", "day and night".
    """
    def words(r):
        return [((_g(gloss, v[0][0]) or v[0][0]) if v else "")
                for v in (r.get("slots") or {}).values()]

    def dominance(r):
        sh = []
        for v in (r.get("slots") or {}).values():
            tot = sum(c for _, c in v) or 1
            sh.append(max(c for _, c in v) / tot)
        return sum(sh) / len(sh) if sh else 0.0

    # RANK, DO NOT EXCLUDE. 2026-09-16: all 587 may be
    # worth navigating to for some people.
    #
    # That is right, and it corrects an instinct that runs through several of
    # these tools. The content-word floor dropped 530 shapes -- numerals,
    # chief-lists, census formulas -- on the grounds that they are not
    # interesting, which is a judgement about a reader rather than about the
    # text. Someone working through the Numbers censuses wants precisely those
    # rows, and the list pages and filters, so nothing is gained by their
    # absence and a whole kind of pattern is lost by it.
    #
    # The floor stays as a SORT KEY, because it is still true that dominance
    # alone puts "(et) and (et)" (2,603 instances) at the top. Contentful rows
    # lead; the rest follow in their own order rather than vanishing.
    # A ROW THAT RENDERS AS A TEMPLATE BELONGS IN THE OTHER LIST.
    # 2026-09-16: anything with […] belongs to another list. Right: `[…] and […]` is a structure with an open slot, which
    # is a category that already exists and is named for exactly that. Nothing
    # is dropped -- each row goes to the list whose name describes it.
    keep = sorted((r for r in rows if _readable(r, gloss)),
                  key=lambda r: (-dominance(r), -len(r.get("books") or [])))
    return {"id": "node", "name": "Set phrases in the sentence tree",
            "evidence": "counted", "count": len(keep),
            "note": "The most FIXED phrases in the word-group tree — ranked by "
                    "how much one filler dominates each position, not cut at a "
                    "threshold. Only two shapes are identical in every "
                    "instance, which is too few to be a list, so the whole "
                    "ranking is here — read down it until it stops being "
                    "interesting, which is roughly where the Gospel "
                    "“Jesus said to them” variants start repeating.",
            "items": [dict(zip(("kind", "key", "title", "sub"), (
                       "node", r["shape"],
                       # A REAL filling, not one assembled slot by slot.
                       # A readable filling where there is one; otherwise
                       # the shape written as the template it is.
                       # ASSEMBLING TOP FILLERS IS SAFE AT 100% AND ONLY
                       # THERE. When every position has exactly one filler
                       # they necessarily co-occur, so "to you grace from" is
                       # a real phrase; below that they need not, which is the
                       # fabrication caught in "Hena and Ivvah". So the
                       # assembly is used only to fill a gap the example left
                       # in an otherwise fully-fixed shape.
                       ((" ".join(words(r)) if dominance(r) >= 0.999
                         and "…" in _node_example(r, gloss)[0] else "")
                        or _node_example(r, gloss)[0]
                        or _node_template(r, gloss)
                        or r["shape"]),
                       (lambda ph, rf: (f"{rf} · " if rf else "")
                        + f"{round(dominance(r) * 100)}% fixed · "
                        + f"{r['instances']}× · "
                        + f"{len(r.get('books') or [])} books · "
                        + r["shape"])(*_node_example(r, gloss)))))
                      # NOT CUT AT ALL. 2026-09-16: if the list is
                      # interesting, extend the cut-off until it is not.
                      # Quality here declines gradually rather than falling off
                      # a cliff -- "the LORD commanded" (734x, 46 books) is at
                      # 26, "he shall surely die" at 47, "the serpent was
                      # crafty" at 55 -- so any number picked here would be
                      # arbitrary. The list block pages 15 at a time, and a
                      # COMPLETE list is also what re-enables its filter.
                      for r in keep]}


def _pset_ladder(rows, gloss):
    rows = sorted(rows, key=lambda r: -r.get("n", 0))
    return {"id": "ladder", "name": "Ladder chains",
            "evidence": "mechanical", "count": len(rows),
            "note": "Each link's end begins the next — gradatio. Romans 5:3-4 "
                    "and 2 Peter 1:5-7 are the named cases. No model asserts "
                    "these; every instance shows its own chain.",
            "items": [{"kind": "ladder",
                       "key": f"{r['start']}|{r['n']}|{r['steps'][0]}",
                       # GLOSSED. A chain of Hebrew lemmas is unreadable to
                       # most readers of this app; the lemmas stay on the card.
                       "title": " → ".join(_g(gloss, s) or s
                                           for s in r["steps"][:6]),
                       "sub": f"{r['n']} steps · " + (
                           r["start"] if r["start"] == r["end"]
                           else f"{r['start']}–{r['end'].split('.')[-1]}")}
                      for r in rows]}


def _pset_type(rows):
    return {"id": "type", "name": "Typology the text declares",
            "evidence": "the text's own claim", "count": len(rows),
            "note": "Verses where the New Testament NAMES an Old Testament "
                    "antecedent — τύπος, ἀντίτυπος, σκιά. Nothing is inferred; "
                    "30 verses carry the vocabulary and these 12 survived "
                    "reading.",
            "items": [{"kind": "ref", "key": r["ref"],
                       "title": f"{r['ref']} — {r.get('antecedent') or '—'}",
                       "sub": (r.get("reason") or "")[:90]} for r in rows]}


def _pset_theme(rows):
    return {"id": "theme", "name": "Themes, with their evidence",
            "evidence": "mixed, and shown", "count": len(rows),
            "note": "Ranked by how many INDEPENDENT kinds of evidence name "
                    "each one, then by spread — not by size. A theme three "
                    "methods find is better attested than one stamped often "
                    "by a single automated method.",
            # `kind: none` rendered these as dead text. 2026-09-18:
            # the theme links themselves were not working either.
            # They were never wired: no key, so the client fell through to
            # `data-flat` and the row could not be clicked. The register holds
            # the axes, the corroboration notes and the stated limits, which is
            # the most checkable evidence in the whole Explore tree, and none
            # of it was reachable.
            "items": [{"kind": "theme", "key": r["id"], "title": r["name"],
                       "sub": f"{len(r.get('axes') or [])} axes · "
                              f"{len(r.get('books') or [])} books · "
                              + ", ".join(r.get("axes") or [])
                              + (" · has a stated limit" if r.get("limits")
                                 else "")}
                      for r in rows]}


_PSET = {"node": _pset_node, "nodeopen": _pset_node_open, "ladder": _pset_ladder,
         "type": _pset_type, "theme": _pset_theme}


# Words the template writes that the original does not have: the copula of a
# verbless clause and the "of" of a construct chain. They are stepped over
# when naming a pattern by its lexemes, never transliterated.
_INSERTED = {"is", "the", "of", "a", "an"}

LIST_PAGE = 20


def _instances_here(d, r, ref, lang):
    """Each use of this pattern inside one verse, in the verse's own words.

    2026-09-21, told that Exodus 8:6 uses `[S] like [X]` twice: the
    same pattern used twice in a verse is very interesting if the reader knows
    what is being seen, but it is unintuitive that "as you say" fits the
    "like" pattern; the dots need more connecting.

    The dot is one word. כְּ is a single Hebrew preposition and English splits
    it: MACULA glosses the first occurrence **as** and the second **like**,
    because English uses one word for conformity and another for comparison.
    Told that, the double use stops being a coincidence and becomes the point
    — the verse says "according to your word" and "there is none like the
    LORD" with the same particle.

    So each occurrence is returned with what the VERSE calls it, not what the
    lexicon calls it. The card can then show that the two readings are one
    word, which is the thing a reader cannot get from the template.
    """
    anchor_lem = r.get("lemma")
    words = d["orig"].get(ref) or []
    fillers = {}
    for _slot, fills in (r.get("slot_refs") or {}).items():
        for f, refs in fills.items():
            if ref in refs:
                fillers[_slug(f)] = f
    if not anchor_lem or not fillers:
        return []

    def gloss_of(w):
        k = sense_key(lang, w.get("s")) if w.get("s") else None
        prof = (d.get("profiles") or {}).get(k) or {}
        return _slug(prof.get("gloss")), _slug(w.get("g"))

    out = []
    for i, w in enumerate(words):
        if w.get("l") != anchor_lem:
            continue
        # the filler is the nearest word after the anchor that this pattern
        # actually records here; for a prefixed preposition that is the very
        # next word, and the search is bounded so it cannot wander.
        for j in range(i + 1, min(i + 5, len(words))):
            a, b = gloss_of(words[j])
            hit = next((fillers[g] for g in (a, b) if g in fillers), None)
            if hit:
                out.append({
                    "filler": hit,
                    "anchor_text": w.get("t"),
                    "anchor_gloss": w.get("g"),
                    "fill_text": words[j].get("t"),
                    "fill_gloss": words[j].get("g")})
                break
    return out


def bsb_ref(d, ref):
    """The Berean verse carrying the text a MACULA reference names.

    Identity for all but 983 references. Every caller that reaches for the
    English of a graph reference goes through this, because the two sources
    number 142 chapters differently and the app was printing the Berean verse
    at the Hebrew's number. See tools/versify.py.
    """
    return (d.get("vmap") or {}).get(ref, ref)

# Scroll families, for the distance ladder. 2026-09-20: distance may be
# chapter/scroll/scroll family/testament or something like that.
_FAMILY = {
    "torah": "Gen Exo Lev Num Deu",
    "history": "Jos Jdg Rut 1Sa 2Sa 1Ki 2Ki 1Ch 2Ch Ezr Neh Est",
    "wisdom": "Job Psa Pro Ecc Sng",
    "major": "Isa Jer Lam Ezk Dan",
    "minor": "Hos Jol Amo Oba Jon Mic Nam Hab Zep Hag Zec Mal",
    "gospel": "Mat Mrk Luk Jhn", "acts": "Act",
    "paul": "Rom 1Co 2Co Gal Eph Php Col 1Th 2Th 1Ti 2Ti Tit Phm",
    "general": "Heb Jas 1Pe 2Pe 1Jn 2Jn 3Jn Jud", "apocalypse": "Rev",
}
_FAM = {b: f for f, bs in _FAMILY.items() for b in bs.split()}

_INTEREST: dict = {}
_IMAGES: set = set()
_PROPERS: set = set()


def _interest_tables(d):
    """Word interest: inverse frequency, with its tiers over it.

    2026-09-20: interest is inversion of word frequency with bonuses
    for words with meaning, and proper nouns with images being the highest.

    THE IMAGE TIER IS A RATE, NOT A MEMBERSHIP. `out/metaphor.jsonl.gz`
    records tenor and vehicle per clause, so a lemma used as a vehicle is one
    the text uses as an image — read off the corpus rather than declared. But
    taking every lemma that ever appears in one marked 1,789 of them,
    including εἰμί, λαμβάνω and ἀκούω, and the ranking duly called `is`,
    `took` and `heard` images. A vehicle clause contains its own verbs and
    articles; being inside one says nothing.

    Requiring the lemma to appear in vehicles at 3x its share of the corpus,
    with at least five occurrences, leaves 240. Same instrument as everywhere
    else here: lift, not presence.
    """
    if _INTEREST:
        return
    df, total = collections.Counter(), collections.Counter()
    caps = collections.defaultdict(collections.Counter)
    nverse = 0
    src = OUT / "interlinear.jsonl.gz"
    if not src.exists():
        return
    for line in gzip.open(src, "rt", encoding="utf-8"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not rec.get("ref"):
            continue
        nverse += 1
        seen = set()
        for w in rec.get("words") or []:
            lem = w.get("l")
            if not lem:
                continue
            total[lem] += 1
            seen.add(lem)
            # PROPER BY CAPITALISATION, which is MACULA's own marking and the
            # same signal tools/bridge.py reads names off. A lemma whose gloss
            # is capitalised most of the time is a name.
            g = (w.get("g") or "").strip()
            if g:
                caps[lem][g[:1].isupper()] += 1
    if not nverse:
        return
    for lem, c in caps.items():
        if c[True] >= 5 and c[True] > c[False]:
            _PROPERS.add(lem)
    veh = collections.Counter()
    p = OUT / "metaphor.jsonl.gz"
    if p.exists():
        for line in gzip.open(p, "rt", encoding="utf-8"):
            if line.startswith('{"_'):
                continue
            try:
                m = json.loads(line)
            except ValueError:
                continue
            for v in m.get("vehicle") or []:
                veh[v] += 1
    n_veh, n_all = sum(veh.values()), sum(total.values())
    for lem, c in veh.items():
        if c >= 5 and n_veh and n_all and \
                (c / n_veh) / max(total.get(lem, 1) / n_all, 1e-9) >= 3.0:
            _IMAGES.add(lem)
    for r in (d.get("patterns") or {}).values():
        for f in r.get("fixed") or []:
            lem = f.get("lemma")
            if not lem or lem in _INTEREST:
                continue
            idf = math.log(nverse / max(df.get(lem, 1), 1)) / math.log(nverse)
            if lem in _IMAGES:
                mult = 4.0
            elif lem in _PROPERS:
                mult = 2.5
            else:
                mult = 1.0
            _INTEREST[lem] = idf * mult


def _distance(refs, cap=120):
    """chapter < scroll < family < testament, averaged over instance pairs.

    As a CONTINUOUS number — mean canonical gap in books — this term ranged
    15 to 65 and a log of it discriminated nothing; the top sixteen came out
    in the same order with it and without it. As a ladder it ranges 0 to 4 and
    every step is a real jump, which is what the correction supplied.
    """
    keys = []
    for x in refs[:cap]:
        p = x.split(".")
        if len(p) < 3:
            continue
        keys.append((p[0] in NT_BOOKS, _FAM.get(p[0], "?"), p[0], p[1]))
    if len(keys) < 2:
        return 0.0
    tot = n = 0
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            d = (4 if a[0] != b[0] else 3 if a[1] != b[1]
                 else 2 if a[2] != b[2] else 1 if a[3] != b[3] else 0)
            tot += d
            n += 1
    return tot / n


def pattern_score(d, r):
    """The ranking of 2026-09-20.

        (total matched structure slots) * (number of fixed slots)
        * (sqrt of frequency, minimum frequency 2)
        * (log of average distance)
        * (average fixed word interest)

    `fixed_orig` is the count of ORIGINAL words, taken at harvest. Counting
    template words instead ranked translation verbosity — `[S] went out from
    [X]` led the list on three fixed positions where the Hebrew has two,
    because יָצָא is one verb that English needs two words for.

    Structure stands in for "total matched structure slots" as positions:
    slots plus original fixed words. The composed layer that would make the
    first term literal does not exist yet, and the substitution is named
    rather than hidden.
    """
    _interest_tables(d)
    nfix = r.get("fixed_orig") or 0
    if not nfix:
        return 0.0
    # A SLOT COUNTS AS STRUCTURE ONLY IF IT IS RESTRICTED. 2026-09-20:
    # at least 3 slots that are fixed or at least restricted. Counting
    # every slot instead put `[S] said to [X]` at the head — four positions,
    # and its [X] takes 386 different fillers, so three of those four are
    # open. An open slot is the ABSENCE of structure; adding it to the
    # structure term rewarded the most generic shapes in the corpus, which is
    # the fault this ranking exists to fix.
    open_slots = 0
    for fills in (r.get("slots") or {}).values():
        n = sum(fills.values())
        if n and max(fills.values()) / n >= 0.5:
            open_slots += 1
    positions = open_slots + nfix
    refs = [x for f in (r.get("slot_refs") or {}).values()
            for v in f.values() for x in v]
    # THE AVERAGE IS GEOMETRIC, because a formula is only as interesting as
    # its dullest fixed word. the specification was "average fixed word interest
    # level"; an arithmetic mean of נָתַן (0.19) and בְּ (~0.02) reads 0.11 and
    # hides the preposition entirely, so `[S] give in [X]` counted two fixed
    # positions and was scored as though both carried meaning. A geometric
    # mean cannot be rescued by one good member, which is the property wanted:
    # `declares the [X]` is one word at 0.43 and beats it.
    ints = [_INTEREST.get(f.get("lemma"), 0.0) for f in (r.get("fixed") or [])]
    if not ints:
        return 0.0
    prod = 1.0
    for x in ints:
        prod *= max(x, 1e-4)
    avg = prod ** (1.0 / len(ints))
    return (positions * nfix
            * math.sqrt(max(r.get("instances", 0), 2))
            * math.log(1 + _distance(refs))
            * avg)


def page_sets(sets, q, default=LIST_PAGE):
    """Cap each list to a page, or hand back one list's next slice.

    2026-09-21: the show-more buttons were not working again.
    They were wired and they were firing. The list they were
    attached to held twenty rows against a header of 2,516, so one click
    exhausted it and the button removed itself — which is indistinguishable
    from a broken button:

        showing 15 of 20 (2496 more not loaded)

    An earlier fix made the footer stop LYING about that, which was right and
    did not help: a reader could now see that 2,496 rows were missing and
    still not reach one of them. The list was never pageable; it was one
    server-chosen page with a button over it.

    So the sets are built whole and cut here, and `?set=<id>&offset=N` returns
    the next slice of one of them. The count a header shows and the rows a
    reader can reach are now the same number.
    """
    want = (q.get("set") or [""])[0] if q else ""
    if want:
        off = max(qint(q, "offset", 0), 0)
        lim = min(max(qint(q, "limit", 50), 1), 200)
        for s in sets:
            if s.get("id") == want:
                items = s.get("items") or []
                return {"id": want, "total": len(items),
                        "offset": off, "items": items[off:off + lim]}
        return {"id": want, "total": 0, "offset": off, "items": []}
    for s in sets:
        items = s.get("items") or []
        if len(items) > default:
            s["items"] = items[:default]
            # the id the client asks for when the reader wants the rest
            s["more"] = s.get("id")
    return None


def _lex_template(r):
    """The template written in the ORIGINAL words rather than one rendering.

    2026-09-21, asked which way to name a pattern: the right way is by the
    lexeme.

    The reason it matters is measured. A template is labelled with its
    lexeme's DOMINANT gloss, and **only 43.1% of 164,696 instances sit in a
    verse that contains that label**; `[S] got up [O]` has 230 instances and
    not one of them reads "got up". So the English name sends a reader to
    verses where the name does not appear — exactly the complaint at
    Numbers 24:4, that the word for "declares" was not to be seen, which was fixed on
    one card while the list of 2,516 still runs on the gloss.

    `fixed` carries one entry per word of the original, in template order, so
    the English runs are replaced by walking the two together. A run with no
    lexeme behind it is DROPPED rather than transliterated: the "is" of a
    verbless clause and the "of" of a construct chain are ours, not the
    text's, and writing them in Hebrew would be inventing words.

    Returns None where the harvest could not resolve the lexemes (1,021 of
    6,910 templates), so the caller falls back to the English rather than
    showing a half-translated label.
    """
    fixed = r.get("fixed") or []
    if not fixed or not all(f.get("lemma") for f in fixed):
        return None
    toks = [t for t in re.split(r"(\[[A-Z]\])", r.get("template") or "")
            if t.strip()]
    runs = [t for t in toks if not re.fullmatch(r"\[[A-Z]\]", t)]
    # WHERE THE TEMPLATE'S ENGLISH IS ITSELF UNRESOLVED, ORDER IS ALL THERE
    # IS. `[S] said to [O]` is λέγω + πρός, but its label was built from an
    # edge type the lexicon could not canonicalise, so it reads "said to"
    # while λέγω's own gloss is "saying" — and matching the two by text finds
    # nothing. With a single fixed run there is nothing to disambiguate: the
    # run is every fixed position, in order.
    single = len(runs) == 1
    parts, i = [], 0
    for tok in toks:
        if re.fullmatch(r"\[[A-Z]\]", tok):
            parts.append(tok)
            continue
        if single:
            parts.extend(f["lemma"] for f in fixed)
            i = len(fixed)
            continue
        # Consume this English run with as many recorded positions as it
        # holds, stepping over the words the template ADDS. `[S] is lord` is
        # one lexeme, יהוה, behind a copula this layer wrote itself; matching
        # strictly from the left dropped the lexeme and left a bare `[S]`.
        run = tok.strip()
        while i < len(fixed) and run:
            g = (fixed[i].get("gloss") or "").strip()
            if g and run.startswith(g):
                parts.append(fixed[i]["lemma"])
                run = run[len(g):].strip()
                i += 1
            elif run.split(" ", 1)[0] in _INSERTED:
                run = run.split(" ", 1)[1] if " " in run else ""
            else:
                break
    return " ".join(parts) if parts else None


def _pat_sub(r):
    """What actually fills the slots, which is the interesting part.

    "aroma of [X] · 36×" says a shape exists; "[X] is “pleasing” 36 of 36" says
    the text has a fixed phrase. The counts are shown rather than a percentage
    so a reader can see how much evidence is behind it.
    """
    bits = [f"{r['instances']}× · {r['reach']} books"]
    for name, fills in (r.get("slots") or {}).items():
        top = sorted(fills.items(), key=lambda kv: -kv[1])[:2]
        if not top:
            continue
        w, n = top[0]
        if n >= 0.8 * r["instances"]:
            bits.append(f"[{name}] almost always “{w}” ({n})")
        else:
            bits.append(f"[{name}] " + ", ".join(f"“{x}” {c}" for x, c in top))
    return " · ".join(bits)


def _occ_payload(d, key):
    rows, total = occurrences(d, key)
    return {"rows": rows, "total": total, "shown": len(rows),
            "books": len({r["ref"].split(".")[0] for r in rows})}


def api_sense_verse(d, q):
    """One example verse for the word card, fetched when its box is opened."""
    key = (q.get("key") or [""])[0]
    ref = (q.get("ref") or [""])[0]
    if not key or not ref:
        return {"found": False}
    return phrase_one(d, key, ref)


def phrases(d, key, n=8):
    """The word inside real sentences, which is how anyone learns one.

    The sections that should exist should include the word in the
    phrase, to be more intuitive. A list of properties tells you about a word;
    a handful of phrases shows it working. The English is matched against the
    gloss MACULA gives that same verse, so the highlight is local evidence
    rather than a global dictionary, and it is approximate by nature.
    """
    # The key's own language, so a word's Strong's can be turned back into a
    # key and compared. `h1254` is Hebrew, `g2842` Greek.
    lang = "hebrew" if (key or "").startswith("h") else "greek"
    out, seen = [], set()
    for ref, gloss in d["occ"].get(key, []):
        # THE NODE'S REF IS ITS UNIT'S FIRST VERSE, NOT THE WORD'S VERSE.
        # 2026-09-15, on two examples showing no marked Greek: Gal 2:7
        # and Phil 1:3, where koinonia is actually at Gal 2:9 and Phil 1:5.
        #
        # Measured across all 189,494 node occurrences against the interlinear:
        #
        #     ref lands on the word     188,512   99.5%
        #     word is nearby, not here      980    0.5%
        #     not found within 5 verses       2    0.0%
        #     offsets: +1 x866, +2 x95, +3 x15, +4 x2, +5 x2
        #
        # EVERY offset is forward and none is backward, which is what settles
        # it: versification noise would go both ways, and a ref that is always
        # at or before the word is the start of the unit containing it. So the
        # word is looked for in the next few verses and the example cites the
        # verse it is really in -- a citation that names the wrong verse is
        # worse than no example.
        ref = _where(d, key, ref, lang)
        if ref in seen or len(out) >= n:
            continue
        seen.add(ref)
        eref = bsb_ref(d, ref)          # the English at the Berean's number
        b = MACULA_BACK.get(eref.split(".")[0])
        if not b:
            continue
        try:
            _, c, v = eref.split(".")
            text = d["verses"].get((b, int(c), int(v)))
        except ValueError:
            continue
        if not text:
            continue
        # MATCH ANY WORD OF THE GLOSS, not the whole gloss. MACULA glosses a
        # word with a phrase often enough -- "a contribution", "a
        # participation" -- and comparing the whole gloss to one English word
        # could never match, so 6 of the 8 examples for `fellowship` came back
        # with nothing highlighted at all.
        # Tokenised with its own regex rather than through `_slug`, which is
        # this module's and strips every non-letter INCLUDING the spaces --
        # "a contribution" becomes one blob and matches no English word. The
        # sibling `_slug` in tools/senses.py was fixed to keep spaces; this one
        # is left alone because other callers depend on its current behaviour.
        gtok = [t for t in re.findall(r"[a-z]+", (gloss or "").lower())
                if len(t) > 2]
        hit = None
        for m in re.finditer(r"[A-Za-z][A-Za-z'-]*", text):
            w = _slug(m.group(0))
            if any(w == t or w.rstrip("s") == t or w == t.rstrip("s")
                   for t in gtok):
                hit = [m.start(), m.end()]
                break

        # THE ORIGINAL IS THE PRIMARY EVIDENCE. 2026-09-15: clicking on
        # the reference box showed what was already visible, and in the case of
        # fellowship it was hard to see how the word fit into several of the
        # examples, so the original language sequence is shown as primary
        # instead of the English emphasizing the word linked on.
        #
        # The English translation of a Greek word varies by context -- κοινωνία
        # is "fellowship", "contribution" and "participation" in three of these
        # verses -- so the English cannot show what the examples have in
        # common. The original can: the same word is visibly there every time.
        orig = []
        for w in d["orig"].get(ref, []):
            if not (w.get("t") or w.get("g")):
                continue
            orig.append({"t": w.get("t"), "g": w.get("g"), "x": w.get("x"),
                         "on": sense_key(lang, w.get("s")) == key})
        out.append({"ref": ref, "text": text, "hit": hit, "gloss": gloss,
                    "orig": orig,
                    "rtl": MACULA_BACK.get(ref.split(".")[0]) is not None
                           and ref.split(".")[0] in HEBREW_BOOKS})
    return out


# A word with fewer than this many uses has too thin a profile to be compared:
# unrestricted, `hesed` came back nearest to *charcoal*, because rare features
# dominate and a rare word's whole profile is rare features.
MIN_OBS = 20


def neighbours(d, key, n=8):
    """Words that behave like this one — measured, never asserted.

    Same-language only. `hesed` against `agape` scores 0.039: the features are
    English glosses over different syntactic conventions, so a cross-language
    number here is noise. The app must not offer a comparison already shown to
    be invalid.
    """
    me = d["vecs"].get(key)
    if not me:
        return []
    lang, out = key[0], []
    for other, vec in d["vecs"].items():
        if other == key or other[0] != lang:
            continue
        if (d["profiles"][other].get("observations") or 0) < MIN_OBS:
            continue
        shared = me.keys() & vec.keys()
        if not shared:
            continue
        dot = sum(me[k] * vec[k] for k in shared)
        s = dot / (d["norms"][key] * d["norms"][other] or 1)
        if s > 0.02:
            out.append((s, other))
    out.sort(reverse=True)
    return [{"key": o, "gloss": d["profiles"][o].get("gloss"),
             "score": round(s, 3),
             "observations": _uses(d, o)}
            for s, o in out[:n]]


# People type a book the way they say it, not the way a file names it. Without
# these, "Jn 3" and "Mt 5" returned nothing, which reads as "the app has no
# search" rather than "that abbreviation is unknown".
ALIAS = {
    "gen": "Gen", "ge": "Gen", "ex": "Exod", "exo": "Exod", "lv": "Lev",
    "nm": "Num", "dt": "Deut", "deu": "Deut", "jos": "Josh", "jdg": "Judg",
    "rt": "Ruth", "1sa": "1Sam", "2sa": "2Sam", "1ki": "1Kgs", "2ki": "2Kgs",
    "1ch": "1Chr", "2ch": "2Chr", "ne": "Neh", "es": "Esth", "jb": "Job",
    "ps": "Ps", "psa": "Ps", "psalm": "Ps", "psalms": "Ps", "pr": "Prov",
    "prv": "Prov", "ec": "Eccl", "sos": "Song", "song": "Song", "is": "Isa",
    "je": "Jer", "lam": "Lam", "ez": "Ezek", "eze": "Ezek", "da": "Dan",
    "ho": "Hos", "jl": "Joel", "am": "Amos", "ob": "Obad", "jon": "Jonah",
    "mi": "Mic", "na": "Nah", "hb": "Hab", "zep": "Zeph", "hag": "Hag",
    "zec": "Zech", "mal": "Mal", "mt": "Matt", "mat": "Matt", "mk": "Mark",
    "mrk": "Mark", "lk": "Luke", "luk": "Luke", "jn": "John", "jhn": "John",
    "ac": "Acts", "act": "Acts", "ro": "Rom", "rm": "Rom", "1co": "1Cor",
    "2co": "2Cor", "ga": "Gal", "ep": "Eph", "php": "Phil", "phil": "Phil",
    "col": "Col", "1th": "1Thess", "2th": "2Thess", "1ti": "1Tim",
    "2ti": "2Tim", "tit": "Titus", "phm": "Phlm", "heb": "Heb", "jas": "Jas",
    "jam": "Jas", "1pe": "1Pet", "2pe": "2Pet", "1jn": "1John",
    "2jn": "2John", "3jn": "3John", "jud": "Jude", "rev": "Rev", "re": "Rev",
}


_ALIASES = None
_ANCHORED = None
_SUFFIX = ("s", "es", "ed", "d", "ing", "er", "ers")


def _aliases():
    """out/word-aliases.json (tools/aliases.py): English form -> [[strong, n]]."""
    global _ALIASES
    if _ALIASES is None:
        p = OUT / "word-aliases.json"
        _ALIASES = json.loads(p.read_text(encoding="utf-8")).get("forms", {}) if p.exists() else {}
    return _ALIASES


def _forms_of(w):
    """A word and its inflections, by a fixed list of endings -- not by a
    shared prefix, which lets "love" reach "lovely"."""
    fs = {w} | {w + s for s in _SUFFIX}
    if w.endswith("e"):
        fs |= {w[:-1] + "ing", w[:-1] + "ed"}
    if w.endswith("y"):
        fs |= {w[:-1] + "ies", w[:-1] + "ied"}
    for s in sorted(_SUFFIX, key=len, reverse=True):
        if w.endswith(s) and len(w) - len(s) >= 3:
            fs.add(w[:-len(s)])
            fs.add(w[:-len(s)] + "e")
            break
    return fs


def _alias_keys(term):
    """The Strong's numbers a typed word (and its inflections) renders, most
    used first, each with the form that carried it."""
    al = _aliases()
    w = term.lower().strip()
    if not re.fullmatch(r"[a-z]{3,}", w):
        return []
    got = collections.Counter()
    form_of = {}
    for f in _forms_of(w):
        for k, n in al.get(f, []):
            got[k] += n
            if k not in form_of or f == w:
                form_of[k] = f
    return [(k, form_of[k]) for k, _n in got.most_common()]


def _anchored_to():
    """strong -> the records whose leading anchored word it is, and which
    their own name renders (image_dust is anchored to אֶרֶץ "earth" through
    an alias, and must not answer a search for "earth")."""
    global _ANCHORED
    if _ANCHORED is None:
        _ANCHORED = collections.defaultdict(list)
        al = _aliases()
        for r in _rows(OUT / "concept-anchors.jsonl.gz"):
            parts = [p for p in r.get("parts", []) if p.get("anchors")
                     and p.get("word") not in ("image", "as", "of", "the", "a")]
            if len(parts) != 1:
                continue
            top = max(parts[0]["anchors"], key=lambda a: a[2])
            if top[2] < 0.3:
                continue
            own = {k for f in _forms_of(parts[0]["word"].lower()) for k, _n in al.get(f, [])}
            if top[0] in own:
                _ANCHORED[top[0]].append(r["id"])
    return _ANCHORED


def _who(e):
    """Which one this is, among others of the same name: the record's own
    `disambiguation`, without its "distinct from ..." tail (that names the
    others, and the reader is already looking at them). None if it has none.

    2026-10-01, on searching "Mary": clearer disambiguation was needed both
    in the search and on the default card. Seven people
    are called Mary; search showed one, labelled "person", and her card said
    nothing about which Mary she was.
    """
    s = (e.get("disambiguation") or "").strip()
    s = re.split(r"[;,.]?\s*distinct from\b", s, maxsplit=1,
                 flags=re.I)[0].strip(" ;,.")
    # a record's own link markup, "[[jesus]]'s names", shown raw on the Jesus
    # card (2026-10-02): the id read as a name
    s = re.sub(r"\[\[([a-z0-9_]+)\]\]",
               lambda m: m.group(1).replace("_", " ").title(), s)
    return s or None


def _testament_lang(e):
    """'h' if every verse a record cites is in the Old Testament, 'g' if every
    one is in the New, else None. A name's original word is looked up by the
    name, so all seven Josephs got יוֹסֵף -- right for Jacob's son, wrong for
    Mary's husband, who is Ἰωσήφ."""
    nt = ORDER.index("Matt")
    sides = set()
    for ref in e.get("refs") or []:
        b = ref.split(" ")[0]
        if b in TITLE:
            sides.add("g" if ORDER.index(b) >= nt else "h")
    return sides.pop() if len(sides) == 1 else None


def _name_key(d, e):
    """The lemma key ("h3130", "g2501") of the word behind a record's name, or
    None. By the name first, then by the gloss; and where the record's verses
    are all in one testament, only a word of that testament's language -- the
    name map holds one code per NAME, so Mary's husband had Jacob's son's
    Hebrew (the second panel of first-time visitors, 2026-10-01)."""
    code = d["namemap"].get(e["name"])
    first = (code[0].lower() + re.sub(r"^0+", "", code[1:])) if code else None
    k = first
    got = [g[1] for g in d["gloss_ix"].get(_slug(e["name"])) or []]
    if not k:
        k = got[0] if got else None
    side = _testament_lang(e)
    if k and side and k[0] != side:
        k = next((g for g in got if g[0] == side), None)
    return _own_name_word(d, e, k, [first] + got)


_PROPER = None


def _own_names(d, e):
    """{"refs": the record's verses (MACULA), "keys": the proper names that
    stand in them}, or None where a record's name is not the text's name for
    it (see _own_name_word)."""
    global _PROPER
    if _PROPER is None:
        p = OUT / "proper-names.json"
        _PROPER = set(json.loads(p.read_text(encoding="utf-8"))["keys"]) if p.exists() else set()
    name = re.sub(r"^the\s+", "", e["name"].strip(), flags=re.I)
    if (not _PROPER or e["type"] in ("text", "being") or not name[:1].isupper()
            or not e.get("refs")):
        return None
    here = d.get("_occ_here")
    if here is None:
        here = collections.defaultdict(list)
        for key, rows in d["occ"].items():
            if key in _PROPER:
                for ref, t in rows:
                    here[ref].append((key, t))
        d["_occ_here"] = here
    own = {_macula_ref(d, r) for r in e["refs"]}
    return {"refs": own, "keys": {key for r in own for key, _t in here.get(r, ())}}


def _own_name_word(d, e, k, cands):
    """A NAME'S WORD STANDS IN THE RECORD'S OWN VERSES. The name map and the
    gloss index hold one word per NAME, so records sharing a name shared its
    word: the monster Rahab (Job 26:12) showed רָחָב, the woman of Jericho's,
    and Matt 1:5's Rahab showed Ῥαάβ where the verse reads Ῥαχάβ (N-D3 /
    C-D11, the 2026-10-02 evaluation). Where the word found never occurs in
    the record's own verses, the name word that does is taken: first one the
    name already pointed to, then one the text there renders by this name.
    Only for a record the text names (a capitalised name, a MACULA proper
    noun: out/proper-names.json) -- a concept's English ("fear", "lord")
    renders several words and its verses would pick one at random; never a
    speech record ("Mary" is not ῥαββονί) or a divine person (by hand only)."""
    names = _own_names(d, e)
    if names is None:
        return k
    here, own = d["_occ_here"], names["refs"]
    if k in names["keys"]:
        return k
    hit = next((c for c in cands if c in names["keys"]), None)
    if hit:
        return hit
    # the record's own name, the commonest such word across its verses; its
    # other names only where it has no word at all -- Sinai's one verse (Exod
    # 3:1) says Horeb, and a card titled Sinai showing חֹרֵב as the word
    # behind its name would mislead
    for nm in [e["name"]] + (list(e.get("aka") or []) if not k else []):
        want = _slug(re.sub(r"^the\s+", "", nm.strip(), flags=re.I))
        c = collections.Counter(key for r in own for key, t in here.get(r, ())
                                if _slug(t) == want)
        if c:
            return c.most_common(1)[0][0]
    return k


_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"|“[^”]*”|‘[^’]*’|\([^)]*\d[^)]*\)")
_KJV_FORM = re.compile(r"(?i)\b(thee|thou|thy|thine|ye|unto|hath|doth|shalt|"
                       r"wilt|saith|(?!nazareth|elisabeth|elizabeth|japheth|teeth|"
                       r"kenneth)\w+eth)\b")


def _search_sub(d, e):
    """The line under a search result: what it is and where it sits, not a
    verse. 2026-10-01: search suggestions should not mention a Bible verse
    (a theme, perhaps), and then, choosing:
    the kind and its major theme; with no theme, the kind and the
    description with its quotations and references taken out; failing that,
    the kind alone. A description that opened with a quotation put the KJV
    and a reference under nearly every concept."""
    desc = e.get("desc") or ""
    first = re.split(r"(?<=[.!?])\s", desc.strip(), maxsplit=1)[0]
    if (first and 12 <= len(first) <= 120 and first[0].isupper()
            and not re.search(r"['\"“”‘’*_#\d]|[:;,]$|:\s*$", first)
            and not _QUOTED.search(first) and not _KJV_FORM.search(first)):
        first = first.rstrip(".")
    else:
        first = None
    # a person or place is better told by who or where it is than by a theme
    # ("Moses -- in the major theme Messiah / Christology")
    if first and e["type"] in ("person", "place"):
        return f"{e['type']} · {first}"
    themes = [x["theme"] for x in _theme_map().get("by_node", {}).get(e["id"], [])
              if x["theme"] in _theme_map()["_by"]]
    if themes:
        return (f"{e['type']} · in the major theme "
                f"{_title(_theme_map()['_by'][themes[0]]['title'])}")
    # an event says which books tell it, not which verses
    told = re.search(r"an event told in (.+?)\.(?:\s|$)", desc)
    if told:
        books = []
        for part in told.group(1).split(";"):
            b = re.sub(r"\s*\d+[:.]\d.*$", "", part.strip())
            if b and b not in books:
                books.append(b)
        return f"{e['type']} · told in {', '.join(books)}"
    # otherwise the first sentence, only if it stands on its own: no
    # quotation, no reference, no markup, no King James forms, not a
    # fragment. Stripping the quotations out of a description left "One of
    # three named together and ranked:." -- worse than saying nothing.
    return f"{e['type']} · {first}" if first else e["type"]


_AKA = None


def _aka_index(d):
    """[(word key of another name, record id)] for every record's aka, built
    once: the names a record answers to besides its own."""
    global _AKA
    if _AKA is None:
        # and the old KJV title, which is searched but never shown: a reader
        # who types "Joseph's brethren" still finds "Joseph's brothers"
        # (kjv_titles.py; kept out of aka, which cards display as "Also
        # called", because the point is that no KJV text is shown)
        _AKA = [(k, eid) for eid, e in d["ents"].items()
                for a in (e.get("aka") or []) + ([e["name_kjv"]] if e.get("name_kjv") else [])
                + (e.get("aka_kjv") or [])     # aliases in KJV text, hidden the same way
                if (k := _wordkey(a))]
    return _AKA


_SMALL = set("the a an of and or in on to at by for with from is are be his her its their".split())
# the Patterns section's sets, by the words a reader may use for them that
# their titles do not contain (search, M-D17)
PSET_ALSO = {"type": ("typology", "types", "antitype", "shadow")}


def _all_words(w, key):
    """Every content word of the search begins a word of the name (two at
    least, so one word still has to match as a word or a phrase)."""
    want = [x for x in w.split() if x not in _SMALL]
    if len(want) < 2:
        return False
    have = key.split()
    return all(any(h.startswith(x) for h in have) for x in want)


# ---------------------------------------------------------------- the search's small doors
#
# 2026-10-26: the graph search stays primary and its ranking unchanged; these
# add rows, each deterministic (no embeddings, no model at query time) and
# each small in memory. What failed before: "take every thought" found nothing
# although 2 Cor 10:5 reads "we take captive every thought" (the phrase match
# wants the words side by side); "H157" and "G26" were read as a reference
# ("G26" was Genesis 26); and a form of a Hebrew or Greek word, as it stands
# in a verse, reached nothing.
import array
import bisect

_VTOK = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")
_SX = None
_SX_LOCK = threading.Lock()
_SCRIPT = re.compile("[֐-׿יִ-ﭏͰ-Ͽἀ-῿]")
_HEBREW = re.compile("[֐-׿יִ-ﭏ]")
_STRONGS = re.compile(r"^\s*([HhGg])0*(\d{1,5})[A-Za-z]?\s*$")
# a query the browser or a shell could not encode arrives as "???" or U+FFFD:
# it says nothing, and must not be read as the English letters left in it
_GARBLED = re.compile(r"\?{2,}|\ufffd")
_FINALS = str.maketrans("ךםןףץς", "כמנפצσ")
_PREFIXES = "והבכלמש"   # Hebrew one-letter prefixes


def _vtoks(text):
    """The words of a verse, for matching: lower case, curly apostrophes
    straight, an apostrophe kept only inside a word."""
    return _VTOK.findall((text or "").lower().replace("’", "'").replace("‘", "'"))


def _orig_norm(s):
    """A Hebrew or Greek word as its letters only: no vowel points,
    cantillation, accents or breathings, final forms made ordinary, lower
    case. (A letter is anything Unicode calls one; the rest of a word is
    marks and punctuation.)"""
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(ch for ch in s if unicodedata.category(ch)[0] == "L").translate(_FINALS)


def _search_index(d):
    """The indexes the small doors read, built once from what the server
    already holds:

      post   word -> the ids of the verses whose Berean text has it
             (integer ids into `keys`, in the order the verses are held; no
             verse text is copied)
      vocab  the words, sorted, so a half-typed last word finds its words
      forms  a Hebrew or Greek word as the text writes it, letters only ->
             the word cards (Strong's keys) it is a form of, from the
             interlinear, every word of which carries its form and its
             Strong's number
      lems   (letters of a lemma, key), sorted: a lemma by its letters, or
             by the start of them
    """
    global _SX
    if _SX is not None:
        return _SX
    with _SX_LOCK:
        if _SX is not None:
            return _SX
        keys = list(d["verses"])
        typ = "H" if len(keys) < 65536 else "I"
        post = {}
        for i, k in enumerate(keys):
            for w in set(_vtoks(d["verses"][k])):
                a = post.get(w)
                if a is None:
                    a = post[w] = array.array(typ)
                a.append(i)
        forms = {}

        def put(n, k):
            if not n:
                return
            cur = forms.get(n)
            if cur is None:
                forms[n] = k
            elif isinstance(cur, str):
                if cur != k:
                    forms[n] = (cur, k)
            elif k not in cur:
                forms[n] = cur + (k,)

        lem_pairs = set()
        for ref, ws in (d.get("orig") or {}).items():
            nt = ref.split(".")[0] in _NT_BOOKS
            for w in ws or ():
                digits = re.sub(r"\D", "", str(w.get("s") or ""))
                if not digits:
                    continue
                k = sys.intern(("g" if nt else "h") + str(int(digits)))
                put(_orig_norm(w.get("t")), k)
                if w.get("l"):
                    lem_pairs.add((_orig_norm(w["l"]), k))
        for k, lem in (d.get("lemmas") or {}).items():
            lem_pairs.add((_orig_norm(lem), k))
        for k, lx in (d.get("lex") or {}).items():
            if lx.get("word"):
                lem_pairs.add((_orig_norm(lx["word"]), k))
        lems = sorted(p for p in lem_pairs if p[0])
        _SX = {"keys": keys, "post": post, "vocab": sorted(post), "forms": forms,
               "lems": lems, "lem_norms": [p[0] for p in lems]}
        return _SX


def _word_ids(sx, words, last_prefix=False):
    """The ids (sorted) of the verses holding every one of `words`; with
    `last_prefix` the last may be only the start of a word. None when nothing
    narrows the search (a prefix too short to name its words constrains
    nothing)."""
    sets = []
    for i, w in enumerate(words):
        if last_prefix and i == len(words) - 1:
            lo = bisect.bisect_left(sx["vocab"], w)
            hi = bisect.bisect_left(sx["vocab"], w + "\uffff")
            if hi - lo > 300:
                continue
            ids = set()
            for x in sx["vocab"][lo:hi]:
                ids.update(sx["post"][x])
            if not ids:
                return []
        else:
            a = sx["post"].get(w)
            if a is None:
                return []
            ids = a
        sets.append(ids)
    if not sets:
        return None
    sets.sort(key=len)
    out = set(sets[0])
    for s in sets[1:]:
        out &= s if isinstance(s, set) else set(s)
        if not out:
            break
    return sorted(out)


def _phrase_verses(d, term, n=8):
    """THE PHRASE IN THE TEXT. The evaluation readers searched what they
    remembered -- "hung on a tree" (Gal 3:13) -- and nothing answered, because
    search looked at names and never at verses (C-D2). A search of two words
    or more also offers the verses whose Berean text has it, word for word."""
    words = _vtoks(_fold(term))
    if len(words) < 2:
        return []
    sx = _search_index(d)
    out = []
    for i in _word_ids(sx, words) or ():
        text = d["verses"][sx["keys"][i]]
        toks = _vtoks(text)
        if any(toks[j:j + len(words)] == words for j in range(len(toks) - len(words) + 1)):
            b, c, v = sx["keys"][i]
            out.append((b, c, v, text))
            if len(out) >= n:
                break
    return out


def _loose_verses(d, term, skip=(), n=5):
    """THE WORDS, NOT THE ORDER. The reader remembers "take every thought" and
    the verse says "we take captive every thought" (2 Cor 10:5): the phrase is
    not there word for word, the words are. Every word of the search (the last
    one may be half typed), in any order, case and punctuation aside. Single
    words stay with the graph search: three words at least, two of them not
    small words, or two words of five letters at least. Nearest first: the
    words in order and close together, then close in any order, then
    anywhere in the verse; a few rows. Each is (book, chapter, verse, a
    snippet, tier)."""
    if re.search(r"\d", term) or _SCRIPT.search(term):
        return []
    words = _vtoks(_fold(term))
    big = [w for w in words if w not in _SMALL]
    if not ((len(words) >= 3 and len(big) >= 2)
            or (len(words) == 2 and all(len(w) >= 5 for w in words))):
        return []
    sx = _search_index(d)
    ids = _word_ids(sx, words, last_prefix=True)
    if ids is None:
        return []
    m = len(words)
    scored = []
    for i in ids:
        key = sx["keys"][i]
        if key in skip:
            continue
        low = d["verses"][key].lower().replace("’", "'").replace("‘", "'")
        spans = [(x.start(), x.group()) for x in _VTOK.finditer(low)]
        at = []                           # for each word of the search: where the verse has it
        for j, w in enumerate(words):
            last = j == m - 1
            at.append([p for p, (_s, t) in enumerate(spans) if (t.startswith(w) if last else t == w)])
        if not all(at):
            continue
        # in order: the nearest chain, each word after the one before
        best = None
        for p0 in at[0]:
            prev, ok = p0, True
            for pos in at[1:]:
                nxt = next((p for p in pos if p > prev), None)
                if nxt is None:
                    ok = False
                    break
                prev = nxt
            if ok and (best is None or prev - p0 < best[0]):
                best = (prev - p0 + 1, p0)
        if best and best[0] <= m + 3:
            tier, span, start = 0, best[0], spans[best[1]][0]
        else:
            # nearest in any order: the smallest stretch holding all of them
            ev = sorted((p, j) for j, ps in enumerate(at) for p in ps)
            need, have, lo, win = len(at), collections.Counter(), 0, None
            for p, j in ev:
                have[j] += 1
                while have[ev[lo][1]] > 1:
                    have[ev[lo][1]] -= 1
                    lo += 1
                if len(have) == need and (win is None or p - ev[lo][0] < win[0]):
                    win = (p - ev[lo][0] + 1, ev[lo][0])
            tier = 1 if win[0] <= 2 * m + 4 else 2
            span, start = win[0], spans[win[1]][0]
        exact_last = any(t == words[-1] for _s, t in spans)
        scored.append((tier, span, 0 if exact_last else 1, i, start))
    scored.sort()
    out = []
    for tier, _span, _x, i, start in scored[:n]:
        b, c, v = sx["keys"][i]
        text = d["verses"][(b, c, v)]
        a = max(0, start - 20)
        a = text.rfind(" ", 0, a) + 1 if a else 0          # begin at a word
        out.append((b, c, v, ("…" if a else "") + text[a:a + 110]
                    + ("…" if len(text) > a + 110 else ""), tier))
    return out


def _word_row(d, k, r, sub_tail=""):
    """A word card's row in the search: its gloss, its original word, its language."""
    p = d["profiles"].get(k) or {}
    lx = d["lex"].get(k) or {}
    lem = (d.get("lemmas") or {}).get(k) or lx.get("word")
    n = _uses(d, k)
    lang = _lang_of(d, k)
    return {"kind": "sense", "id": k, "title": p.get("gloss") or _text_gloss(d, k) or lem or k,
            "orig": lem, "lang": "Hebrew" if lang == "Aramaic" else lang, "r": r,
            "sub": f"{lang} · {n} use{'s' * (n != 1)}{sub_tail}"}


def _has_word(d, k):
    """A word the text uses (the lexicon alone also holds words no verse has)."""
    return bool(k and ((d.get("lemmas") or {}).get(k) or d["profiles"].get(k)))


def _strongs_rows(d, term):
    """H157, g0026, G26: a Strong's number opens its word card, never a book
    (G26 was Genesis 26). Only where the site has that word."""
    m = _STRONGS.match(term)
    if not m:
        return None
    k = m.group(1).lower() + str(int(m.group(2)))
    if not _has_word(d, k):
        return None
    return [_word_row(d, k, -1, f" · Strong's {k[0].upper()}{k[1:]}")]


def _orig_rows(d, term):
    """Hebrew or Greek typed in goes to the word cards and nowhere else: the
    word by its letters (vowel points, accents and breathings aside), or any
    form of a word as a verse writes it, most used first. A word as it stands
    (a lemma) before a form of another word; a lemma that only begins so
    last."""
    sx = _search_index(d)
    rows, seen = [], set()
    lem_of = lambda k: (d.get("lemmas") or {}).get(k) or (d["lex"].get(k) or {}).get("word") or ""  # noqa: E731
    for word in [w for w in term.split() if _SCRIPT.search(w)][:3]:
        n = _orig_norm(word)
        if not n:
            continue
        hebrew = bool(_HEBREW.search(word))
        side = "h" if hebrew else "g"
        typed = unicodedata.normalize("NFC", word.strip())
        found = {}                                   # key -> (tier, how)

        def add(k, tier, how=""):
            if k[0] == side and _has_word(d, k) and (k not in found or tier < found[k][0]):
                found[k] = (tier, how)

        lo = bisect.bisect_left(sx["lem_norms"], n)
        hi = bisect.bisect_left(sx["lem_norms"], n + "\uffff")
        for ln, k in sx["lems"][lo:hi]:
            if ln == n:
                # the very word typed, points and all, before its look-alikes
                add(k, -1 if unicodedata.normalize("NFC", lem_of(k)) == typed else 0)
            else:
                add(k, 2)
        got = sx["forms"].get(n)
        for k in ((got,) if isinstance(got, str) else got or ()):
            if k not in found or found[k][0] > 1:
                add(k, 1, f"the form {typed} of ")
        if not found and hebrew:
            # a prefix written on (וַיֹּאמֶר: and + say): the text holds the
            # prefix apart from its word, so the word is looked up without it
            m = n
            for _ in range(2):
                if len(m) > 2 and m[0] in _PREFIXES:
                    m = m[1:]
                    got = sx["forms"].get(m)
                    for k in ((got,) if isinstance(got, str) else got or ()):
                        add(k, 3, "a form of ")
                    lo = bisect.bisect_left(sx["lem_norms"], m)
                    for ln, k in sx["lems"][lo:lo + 12]:
                        if ln == m:
                            add(k, 3, "a form of ")
                    if found:
                        break
        for k, (tier, how) in found.items():
            if k not in seen:
                seen.add(k)
                rows.append((tier, -_uses(d, k), k, f" · {how}{lem_of(k)}" if how else ""))
    rows.sort()
    return [_word_row(d, k, t, tail) for t, _u, k, tail in rows[:12]]


# an English word renders a word of the original in a good share of that
# word's uses (the alias count over the word's uses): at least this share,
# and at least this many
RENDER_SHARE, RENDER_MIN = 0.50, 3


def _rendered_words(d, term, res):
    """THE WORDS BEHIND THE ENGLISH, the weaker signal: for one to three
    English words, the Hebrew or Greek words the text renders with them
    (out/word-aliases.json, from MACULA's glosses and the Berean's own
    Strong's tags), where the word is rendered so in a good share of its uses.
    At most three, and not a word the search already offers (a sense whose name
    an entity row carries is dropped, as everywhere in the search)."""
    if len(re.findall(r"[A-Za-z]+", term)) > 3 or re.search(r"[^A-Za-z\s'’-]", term):
        return []
    words = [w for w in re.findall(r"[a-z]+", term.lower()) if w not in _SMALL and len(w) >= 3]
    if not words:
        return []
    have = {r["id"] for r in res if r["kind"] == "sense"}
    named = {_slug(r["title"]) for r in res if r["kind"] == "entity"}
    al = _aliases()
    out = []
    for w in words:
        got = collections.Counter()
        for f in _forms_of(w):
            for k, n in al.get(f, []):
                got[k] += n
        for k, n in got.items():
            uses = _uses(d, k)
            if k in have or not uses or n < RENDER_MIN or n / uses < RENDER_SHARE:
                continue
            row = _word_row(d, k, 8, "")
            if _slug(row["title"]) in named:
                continue
            row["sub"] += f" · the word behind “{w}” ({min(100, round(100 * n / uses))}% of its uses)"
            out.append((-min(1.0, n / uses), -n, row))
    out.sort(key=lambda x: x[:2])
    rows, seen = [], set()
    for _s, _n, row in out:
        if row["id"] not in seen and len(rows) < 3:
            seen.add(row["id"])
            rows.append(row)
    return rows


def api_search(d, q):
    """One box, searching UNITS. A passage and a topic are two doors, one room."""
    term = (q.get("q") or [""])[0].strip()
    if len(term) < 2:
        return {"q": term, "results": []}
    # THE ORIGINAL LANGUAGES HAVE THEIR OWN PATH, before anything reads the
    # words as English or as a reference. A Strong's number (H157, g0026)
    # opens its word card -- "G26" was read as Genesis 26. Hebrew or Greek
    # script goes to the word cards and nowhere else: it was matched, when
    # nothing else answered, against English names. And a query the browser
    # could not encode ("???p?") says nothing, so it is not read as the
    # English letters left in it (ἀγάπη arrived as "???p?" and offered "the poor").
    if _GARBLED.search(term):
        return {"q": term, "results": []}
    got_ = _strongs_rows(d, term)
    if got_:
        return {"q": term, "results": got_}
    if _SCRIPT.search(term):
        return {"q": term, "results": _orig_rows(d, term)}
    res = []
    # A RANGE OPENS AT ITS START (U-6, the 2026-10-02 evaluation: "Genesis
    # 1:1-3" and "Deut 28-30" found nothing): the end is read and shown in the
    # row's title, and the reader opens where the range begins
    m = re.match(r"^\s*([0-9]?\s*[A-Za-z]+)\.?\s*(\d+)?(?:[:.\s](\d+))?"
                 r"(?:\s*[-–]\s*(\d+)(?::(\d+))?)?\s*$", term)
    if m:
        want = _slug(m.group(1))
        ch = int(m.group(2) or 1)
        vs = int(m.group(3)) if m.group(3) else None
        hit = []
        alias = ALIAS.get(want)
        if alias:
            hit.append(alias)
        for b in ORDER:
            if b in hit:
                continue
            if _slug(TITLE.get(b, b)).startswith(want) or _slug(b).startswith(want):
                hit.append(b)
        for b in hit[:6]:
            last = max(d["chapters"].get(b, {1}))
            # A CHAPTER THE BOOK DOES NOT HAVE RULES THE BOOK OUT, rather than
            # being clamped to its last. Found 2026-10-01: "Phil 4" opened
            # Philemon 1 -- Philemon has one chapter, so "4" was clamped to 1,
            # and the passages were then ordered by title length, where
            # "Philemon 1" beats "Philippians 4".
            if m.group(2) and ch > last:
                continue
            c = min(max(ch, 1), last)
            # A VERSE THE CHAPTER DOES NOT HAVE is not offered: "John 3:99"
            # was, as a passage that then opened on nothing (the 2026-10-02
            # evaluation; John 3 has 36 verses)
            if vs and (b, c, vs) not in d["verses"]:
                continue
            # Say where it will take you. "Genesis" with "50 chapters" does not
            # look like a link to anywhere; "Genesis 1" does.
            # the sub-line says where it goes: "21 chapters" under "John
            # 3:16" read as if the verse had 21 chapters (the committee as
            # first-time Reddit visitors, 2026-10-01)
            # the range as typed: "1:1-3", "28-30", "1:1-2:3"
            upto = ""
            if m.group(4):
                upto = ("–" + m.group(4) + (":" + m.group(5) if m.group(5) else ""))
            res.append({"kind": "passage", "id": b,
                        "title": f"{TITLE.get(b, b)} {c}"
                                 + (f":{vs}" if vs else "") + upto,
                        "sub": (f"the verse, in chapter {c}" if vs
                                else f"chapter {c} of {last}"),
                        "chapter": c, "verse": vs,
                        # the abbreviation's own book first ("phil" is
                        # Philippians; Philemon is "phlm"), then by name
                        "r": 0 if b == alias else 1})
    s = _slug(term)
    # what the reader typed, and what the KJV would call it
    wants = {_wordkey(term)}
    wants.add(_wordkey(KJV_SAYS.get(_wordkey(term), "")))
    wants.discard("")

    def _rank(key):
        """How well a name matches, or None. Lower is better.

        The ranks are the point: an exact name still beats a name that merely
        contains the word, so typing *God* does not bury the entity called God
        under everything with "god" in it.
        """
        best = None
        for w in wants:
            if key == w:
                r = 0
            elif key.startswith(w):
                # A WHOLE WORD BEFORE A WORD THAT ONLY BEGINS SO: "sea" led
                # with seal, seat, search and season before the Red Sea (C-D3,
                # the 2026-10-02 evaluation)
                r = 1 if not key[len(w):len(w) + 1].isalnum() else 2
            elif any(key.startswith(a) and key[len(a):].startswith(w)
                     for a in LEADING):
                # "the Holy Ghost" for *holy ghost*: an article is not a
                # difference of name. This was 2, a rank below "Covenant
                # Signs", so of "covenant" the covenant with Noah, Abraham
                # and David all fell off the 24 shown (2026-10-02 evaluation)
                r = 0 if any(key == a + w for a in LEADING) else 1
            elif f" {w}" in f" {key}":
                r = 3                      # matches at a word start, anywhere
            elif _all_words(w, key):
                # EVERY WORD SEARCHED, IN THE NAME, small words aside: "tree of
                # knowledge" is "the tree of the knowledge of good and evil";
                # "east of eden", "the east side of the Garden of Eden" (C-D2)
                r = 4
            else:
                continue
            best = r if best is None else min(best, r)
        return best

    # THE MAJOR THEMES ARE SEARCHABLE: a theme by its name, a concept by its
    # own. 2026-09-29, of the theme map: the list is to be wired into
    # the reader and the search/graph. First, since a theme is the widest
    # door a search can open.
    themes_offered = set()
    for t in _theme_map().get("themes", []):
        title = _title(t["title"])
        rs = [x for x in [_rank(_wordkey(title))] + [_rank(_wordkey(p)) for p in
                                                      re.split(r"[/&()]", title) if p.strip()]
              if x is not None]
        if rs:
            themes_offered.add(t["id"])
            # a theme ranks just after passages: the widest door there is
            res.append({"kind": "mtheme", "id": t["id"], "title": title, "r": min(rs) - 1,
                        "sub": f"a major theme · {t.get('subtitle') or ''}"})
    for t in _theme_map().get("themes", []):
        for c_ in t["concepts"]:
            rk = _rank(_wordkey(c_["name"]))
            if rk is not None:
                # A THEME'S CONCEPT IS A READING, in the list as on its card (the
                # evaluation: "the reading mark carried wherever theme content
                # appears" -- "Messiah as Prophet (New Moses)" came up in search
                # unmarked)
                res.append({"kind": "mtheme", "id": t["id"], "title": c_["name"], "r": rk + 1,
                            "sub": f"in the major theme {_title(t['title'])} · a reading"})
    # EVERY RECORD OF A NAME, not the first. This took `ids[0]` of each name,
    # so of seven people called Mary only one could be found -- the mother of
    # James the less, not the mother of Jesus -- and 887 records in all were
    # hidden behind another of the same name, 566 of them people (the second
    # panel of first-time visitors, 2026-10-01). Same-named records rank by
    # how much the graph holds on each, so the one most readers mean leads.
    hits = []
    shared = set()
    for name, ids in d["byname"].items():
        if len(ids) > 1:
            shared.update(ids)
        for eid_ in ids:
            e = d["ents"].get(eid_)
            if not e or e.get("alias_of"):
                continue               # consolidated: found as the event's "also called"
            r = _rank(_wordkey(e["name"]))
            if r is None:
                break                      # same name, same rank: none match
            if SPEECH_NAME.match(e["name"]) and e["type"] == "text":
                # a saying matched only on its speaker's name ranks after the
                # real matches (and is capped below)
                r += 4
            # ONE DOOR TO A ROOM, NOT NINE. Of "covenant", nine of the 24 rows
            # were the Covenant theme's own concepts and eight were cells of
            # one role-pattern table -- all a click inside a row already shown
            # -- and the covenants themselves were not shown (the 2026-10-02
            # evaluation). So a concept of a theme already offered, and a
            # cell of a role pattern (matched on its column's name), rank
            # after the real matches; the cells are capped below with the
            # sayings. And a record that is the very kind searched for --
            # "the new covenant" for *covenant* -- counts as a name match.
            if r == 3 and e["type"] == _wordkey(term):
                r = 1
            m_ = re.match(r"theme_(.+)_c\d+$", e["id"])
            if m_ and m_.group(1) in themes_offered:
                r += 2
            if e["id"].startswith("rcell_"):
                r += 4
            hits.append((r, len(e["name"]), e,
                         -len(d["rels"].get(e["id"], []))))
    # A RECORD'S OTHER NAMES ARE SEARCHABLE TOO. 2026-10-02: Jesus
    # Christ and Christ needed to be searchable aliases for Jesus -- once the
    # duplicate "Jesus Christ" record was merged, neither found him, because
    # search matched a record's name and never its aka. A match on another
    # name ranks as a match on the name, and the row says which name matched.
    #
    # One step below a match on the name itself, so "Saul" leads with King
    # Saul and not Paul ("also called Saul"), as it first did; and able to
    # RAISE a weaker name match -- "Peter" matched "Simon Peter" only as a
    # word inside the name, and his exact other name "Peter" now counts.
    via_aka = {}
    for akey, eid_ in _aka_index(d):
        if eid_ not in d["ents"] or d["ents"][eid_].get("alias_of"):
            continue
        r = _rank(akey)
        if r is not None and (eid_ not in via_aka or r + 1 < via_aka[eid_][0]):
            via_aka[eid_] = (r + 1, akey)
    at = {h[2]["id"]: i for i, h in enumerate(hits)}
    aka_matched = {}
    for eid_, (r, akey) in via_aka.items():
        e = d["ents"][eid_]
        if eid_ in at:
            i = at[eid_]
            if r < hits[i][0]:
                hits[i] = (r, len(akey), e, hits[i][3])
                aka_matched[eid_] = akey
        else:
            hits.append((r, len(akey), e, -len(d["rels"].get(eid_, []))))
            aka_matched[eid_] = akey
    hits.sort(key=lambda h: (h[0], h[1], h[3]))
    hits = [h[:3] for h in hits]
    sayings = [h for h in hits
               if SPEECH_NAME.match(h[2]["name"]) and h[2]["type"] == "text"]
    cells = [h for h in hits if h[2]["id"].startswith("rcell_")]
    drop = {id(h[2]) for h in cells[3:]}
    hits = [h for h in hits if id(h[2]) not in drop]
    if not re.search(r"\d", term):
        # three at most, unless a reference was typed
        drop = {id(h[2]) for h in sayings[3:]}
        hits = [h for h in hits if id(h[2]) not in drop]
    # A dropdown of a dozen rows all reading "God" is a list of doors with no
    # labels. One row was elohim and the next eloh, so the Hebrew is shown in
    # the dropdown. So each row
    # carries whatever distinguishes it -- the original word first, then the
    # description, then the bare type as a last resort.
    shown = set()
    for r, _, e in hits[:40]:
        # a shared name is labelled by which one it is, before anything else
        who = _who(e) if e["id"] in shared else None
        if e["id"] in shared and not who:
            # two records of one name and kind that nothing tells apart (two
            # concepts both called "faith") would be two identical rows; the
            # one the graph holds most on stands for them, as before, and its
            # card lists the other (plan A.19 is the merge)
            if (e["name"], e["type"]) in shown:
                continue
            shown.add((e["name"], e["type"]))
        row = {"kind": "entity", "id": e["id"], "title": e["name"],
               "sub": (f"{e['type']} · {who}" if who else _search_sub(d, e)),
               "type": e["type"], "r": r}
        if e["id"] in aka_matched:
            # found by another name: say which, before anything else
            # (`alias`, not `shown`: reusing that name replaced the set of rows
            # already shown with a string, and the next same-named record
            # raised -- "heaven", "seed", "Judah" all answered 400, 2026-10-02)
            alias = next((a for a in e.get("aka") or [] if _wordkey(a) == aka_matched[e["id"]]), None)
            # matched on the hidden old title: the ordinary line, never the old words
            row["sub"] = f"{e['type']} · also called {alias}" if alias else _search_sub(d, e)
        lab = speech_label(d, e)
        if lab:
            row["title"] = lab
        if lab or e["type"] == "passage":
            # a saying or a passage from one Gospel's extraction points to its
            # event, which holds every Gospel that tells it
            ev = events_at(d, (e.get("refs") or [""])[0])
            if ev:
                row["sub"] = (f"{'said in' if lab else 'part of'} the event {ev[0]['title']}"
                              f" · told in " + ", ".join(ev[0]["told_in"]))
        k = _name_key(d, e)
        if k:
            lx = d["lex"].get(k) or {}
            meta = d["lmeta"].get(k) or {}
            lemma = lx.get("word") or _first(meta, "normalized")
            if lemma:
                row["orig"] = lemma
                row["translit"] = (_first(meta, "transliteration")
                                   or lx.get("translit"))
                row["lang"] = "Hebrew" if k[0] == "h" else "Greek"
        # Names the same thing answers to. On Jesus: it should be really
        # clear, on selecting one, that the other is available.
        aka = sorted({d["ents"][i]["name"] for i in
                      d["alias_ix"].get(_slug(e["name"]), set())
                      if i in d["ents"] and i != e["id"]
                      and _slug(d["ents"][i]["name"]) != _slug(e["name"])})
        # not on a shared name: the alias belongs to the NAME, so every Joseph
        # said "also recorded as Joseph of Arimathaea", who has a row of his own
        if aka and e["id"] not in shared:
            row["aka"] = aka[:3]
        res.append(row)
    for key, p in d["profiles"].items():
        if _rank(_wordkey(p.get("gloss"))) is not None and len(res) < 60:
            res.append({"kind": "sense", "id": key, "title": p.get("gloss"),
                        "sub": f"{p.get('observations')} uses · "
                               f"{'Hebrew' if key[0] == 'h' else 'Greek'}"})
    # PATTERNS ARE SEARCHABLE TOO. 2026-09-16: these are part of the
    # search as well, and all of this belongs in the overall search.
    #
    # They were not: the box reached passages, entities and words, so the only
    # way to a pattern was to remember which of nine lists held it. Searching
    # "thus says" or "grace" now offers the phrase itself alongside the word.
    #
    # The clause templates carry their own text; the node shapes are matched on
    # a real example rather than on the grammar code, since nobody searches for
    # `cl [pron s pp]`.
    # Given their own budget rather than whatever the senses loop leaves: it
    # fills to 60 on a common word, so patterns matched nothing at all for any
    # query that also hit a lot of lemmas.
    pat_room = 8
    for r in d["patterns"].values():
        if pat_room <= 0:
            break
        if _rank(_slug(r.get("template", ""))) is not None:
            pat_room -= 1
            res.append({"kind": "pattern", "id": r["key"],
                        "title": r["template"],
                        "sub": f"{r['instances']}× · {r.get('reach', 0)} books "
                               f"· fixed phrase"})
    gl = d.get("lemgloss") or {}
    node_room = 8
    for r in (d.get("nodepat") or []):
        if node_room <= 0:
            break
        ph = _node_example(r, gl)[0]
        if ph and _rank(_slug(ph)) is not None:
            node_room -= 1
            res.append({"kind": "node", "id": r["shape"], "title": ph,
                        "sub": f"{r['instances']}× · "
                               f"{len(r.get('books') or [])} books · "
                               f"sentence-tree shape"})

    # THE PATTERNS SECTION IS SEARCHABLE (M-D17, the 2026-10-02 evaluation:
    # "chiasm" and "typology" found nothing). Each literary device by its
    # name (it opens its own card), and each set of the section by its title
    # -- with the scholar's word for the one set whose own word differs:
    # "typology" is the set the text names with τύπος, "Declared types"
    sets = d.get("_psets")
    if sets is None:
        sets = d["_psets"] = [s for g in api_recurs(d, {}).get("groups", [])
                              for s in g.get("rows", []) if s.get("kind") == "set"]
    for s in sets:
        if _rank(_wordkey(s["title"])) is not None or \
                any(_rank(x) is not None for x in PSET_ALSO.get(s["key"], ())):
            res.append({"kind": "pset", "id": s["key"], "title": _title(s["title"]),
                        "r": 1, "sub": f"in Patterns · {s.get('sub') or ''}"})
        for it in s.get("items") or []:
            if it.get("kind") == "stamp" and _rank(_wordkey(it["title"])) is not None:
                res.append({"kind": "stamp", "id": it["key"], "title": it["title"],
                            "r": 1, "sub": f"{_title(s['title'])} · {it.get('sub') or ''}"})

    # A WORD FINDS WHAT IT RENDERS. 2026-09-30: mining Strongs/
    # MACULA for aliases would be a good thing for the search, then focus
    # there and drop the alternate translations. "earthquake" finds רַעַשׁ and
    # σεισμός; "loved" finds אָהַב; "lampstand" finds the image the graph still
    # calls "candlestick" -- by the original word, not the English name.
    if True:
        seen_k = {r["id"] for r in res if r["kind"] == "sense"}
        seen_e = {r["id"] for r in res if r["kind"] == "entity"}
        for k, form in _alias_keys(term)[:6]:
            # a verb has no sense profile but has a card (_verb_card), and so
            # has a rare noun (פִּנָּה, "corner"): the lexicon names them
            p = d["profiles"].get(k) or {}
            lx = d["lex"].get(k) or {}
            lemma = lx.get("word") or (d.get("lemmas") or {}).get(k)
            title = p.get("gloss") or lx.get("gloss") or form
            if (p or lx or lemma) and k not in seen_k:
                seen_k.add(k)
                n = p.get("observations")
                res.append({"kind": "sense", "id": k, "title": title, "r": 2,
                            "orig": lemma,
                            "sub": f"{'Hebrew' if k[0] == 'h' else 'Greek'}"
                                   + (f" · {n} uses" if n else "")
                                   + f" · the word behind “{form}”"})
            for eid in _anchored_to().get(k, [])[:3]:
                e = d["ents"].get(eid)
                if e and eid not in seen_e:
                    seen_e.add(eid)
                    res.append({"kind": "entity", "id": eid, "title": e["name"], "type": e["type"],
                                "r": 3, "sub": f"found by the word behind “{form}” · "
                                                 + _search_sub(d, e)})

    # One thing, one row. Searching "mercy" returned both the concept and the
    # Greek word glossed the same way, which is two doors to one place -- and
    # now that an entity lists the words the text uses for it, the entity row
    # reaches the word anyway. So a sense is dropped when an entity of the same
    # name is already offered.
    named = {_slug(r["title"]) for r in res if r["kind"] == "entity"}
    res = [r for r in res
           if not (r["kind"] == "sense" and _slug(r["title"]) in named)]

    # the verses saying the phrase, after the cards: a card for the thing
    # answers more than one verse that mentions it
    for b, c, v, text in _phrase_verses(d, term):
        res.append({"kind": "passage", "id": b, "title": f"{TITLE.get(b, b)} {c}:{v}",
                    "sub": text[:110] + ("…" if len(text) > 110 else ""),
                    "chapter": c, "verse": v, "r": 5, "phrase": True})

    # Passages first, then by how well the name matched, and only then by
    # length. Sorting on length alone put a loose match above an exact one.
    res.sort(key=lambda r: (r["kind"] != "passage" or r.get("phrase", False), r.get("r", 9),
                            len(r["title"])))
    # A PART AFTER ITS WHOLE. 2026-10-04: "temptation" offered the
    # section "Temptation in the wilderness" (part of the event) above the
    # event "Jesus' temptation" -- the section's name begins with the word, so
    # it matched better. Where both are offered, the part goes straight after
    # the event it belongs to.
    titles = {r["title"]: i for i, r in enumerate(res) if r["kind"] == "entity"}
    for r in [r for r in res if r["kind"] == "entity"
              and str(r.get("sub", "")).startswith(("part of the event ", "said in the event "))]:
        whole = r["sub"].split(" the event ", 1)[1].split(" · ")[0]
        if whole in titles and res.index(r) < res.index(next(x for x in res if x["title"] == whole
                                                             and x["kind"] == "entity")):
            res.remove(r)
            j = next(i for i, x in enumerate(res) if x["title"] == whole and x["kind"] == "entity")
            res.insert(j + 1, r)
    # A NEAR SPELLING, WHEN NOTHING ELSE ANSWERED (U-3: "Mosez" found
    # nothing). Close names offered as what the reader may have meant, and
    # the row says so; never mixed into real matches
    if not res and len(term) >= 4:
        import difflib
        names = d.get("_namekeys")
        if names is None:
            names = d["_namekeys"] = sorted({_wordkey(n) for n in d["byname"]})
        for near in difflib.get_close_matches(_wordkey(term), names, n=5, cutoff=0.8):
            # one row per name: the record the graph holds most on
            ids = d["byname"].get(next((n for n in d["byname"] if _wordkey(n) == near), ""), [])
            for eid_ in sorted(ids, key=lambda i: -len(d["rels"].get(i, [])))[:1]:
                e = d["ents"].get(eid_)
                if e:
                    res.append({"kind": "entity", "id": e["id"], "title": e["name"], "type": e["type"],
                                "r": 6, "sub": f"did you mean {e['name']}? · " + _search_sub(d, e)})
    # AFTER EVERYTHING THE GRAPH GIVES, the text and the original words (the
    # three small doors, above `_phrase_verses`): the verses holding the words
    # in any order, and the words behind the English
    seen_v = {(r["id"], r.get("chapter"), r.get("verse")) for r in res if r.get("phrase")}
    for b, c, v, snip, _tier in _loose_verses(d, term, skip={(b, c, v) for b, c, v in seen_v}):
        res.append({"kind": "passage", "id": b, "title": f"{TITLE.get(b, b)} {c}:{v}",
                    "sub": snip, "chapter": c, "verse": v, "r": 6, "phrase": True, "loose": True})
    res.extend(_rendered_words(d, term, res))
    return {"q": term, "results": res[:24]}


def _letters(s):
    """A Hebrew or Greek word's letters only: no vowel points, accents or
    breathings, final letter forms made ordinary, lower case."""
    s = "".join(ch for ch in unicodedata.normalize("NFD", s or "") if not unicodedata.combining(ch))
    return s.translate(str.maketrans("ךםןףץς", "כמנפצσ")).lower().strip()


# IDENTITY, ordered by closeness of the claim. The 'is' relationships are
# surfaced first when a page is ordered by closeness of match.
#
# The order is an argument, not a preference. A thing said of itself outranks a
# thing said about it; a name given outranks a figure drawn; and an explicit
# distinction is not weaker evidence, it is EVIDENCE OF THE OPPOSITE, so it gets
# its own block rather than a place in the ranking.
#
# All of this comes from the legacy graph -- reasoned out verse by verse and
# sourced. They are treated as an overlay until the pipeline does
# the work itself, because everything was sourced. So it is marked wherever it
# appears and never mixed with what the parser computed.
#
# And the mark is temporary by design: the overlay is not needed forever,
# because part of the goal is to retire the need for the
# overlays. `tools/derive.py` is the meter on that debt -- it measures how
# much of this the rules can already recompute, and the label comes off a
# relation type when the answer is "all of it".
IDENTITY_ORDER = [
    ("self_designated_as", "Said of himself", 1),
    ("spoken_of_as", "The text says he is", 2),
    ("assumed_form_of", "Took the form of", 2),
    ("named_with", "Named alongside", 3),
    ("titled", "Called", 4),
    ("deity_of", "Worshipped as the god of", 4),
    ("signifies", "Signified by", 5),
    ("instance_of", "An instance of", 5),
]
# NOT identity, and the taxonomy says so itself. `likened_to` "holds 'is like',
# leaving the meaning alone" and `draws_on` "holds only that a title is built on
# a word" -- both are the weaker neighbours of `signifies` in the schema's own
# note, and reading them as identity claims contradicts it.
#
# Caught on Noah: "who this is said to be" should not say Noah, and
# the fact that the graph says so means this is not a manual fix but a fix
# in the pipeline, to be repaired systemically. The relation is
# `noah likened_to jesus`, and its own note reads "the comparison is to the
# DAYS rather than to the man" -- the annotation was right and the rule
# outranked it. They stay in the imagery category below, where they read
# correctly.
FIGURATIVE = {"likened_to", "draws_on"}


def _rel_label(d, spec, typ, dst, out):
    """A relation's label read from one end: `label` from its source,
    `inverse` from its target.

    `draws_on` is labelled "draws on the image of", which is right for the
    219 edges into an image and wrong for the 270 into a person, place or
    being: Matthew 1:17 "drew on the image of" Babylon, and Babylon was "the
    image behind" the fourteen generations (the 2026-10-02 evaluation). So a
    type may carry `plain_label` / `plain_inverse` in the vocabulary, used
    when the target is not an image -- in the schema, where the Explore
    page's Upper ontologies reads it too, not only here.
    """
    lab = (spec.get("label") if out else spec.get("inverse")) or typ.replace("_", " ")
    plain = spec.get("plain_label") if out else spec.get("plain_inverse")
    if plain and (d["ents"].get(dst) or {}).get("type") != "image":
        lab = plain
    return lab

# An identity claim is between THINGS, not between a thing and a verse. Every
# `draws_on` target here was a text -- "God so loved the world", "fourteen
# generations" -- which is the verse-contains-word shape, not something anyone
# is said to be.
NOT_A_SUBJECT = {"text", "passage"}
IDENTITY_RANK = {k: (label, rank) for k, label, rank in IDENTITY_ORDER}
# Kept apart on purpose, and reported second.
DISTINCTION = {"distinguished_from", "contrary_to", "supersedes"}


def identity_of(d, eid, e):
    """The 'is' claims first, then the 'is not' claims, both with their verses.

    Why this deserves its own treatment: if the app has separate rules for
    Deity, it is because deities are the subject of the entire canon and
    because readers are so easily confused about what the Bible is saying
    about them; what the graph says about disambiguation is surfaced head on.
    """
    same, apart = [], []
    for r in d["rels"].get(eid, []):
        other = d["ents"].get(r["other"])
        row = {"type": r["type"], "dir": r["dir"], "id": r["other"],
               "name": other["name"] if other else r["other"],
               "otype": other["type"] if other else None,
               "refs": r["refs"][:6], "note": r.get("note"),
               "certainty": r.get("certainty")}
        # WHOSE WORDS (P-71). A speaker's claim kept its speaker in the
        # relationship tree but lost it here: "Called the Holy One of God" read
        # as the narrator's, where Mark 1:24 is the unclean spirit's. Found
        # 2026-10-03 while recording "you are the Christ" by speaker
        if r.get("claimed_by"):
            cby = d["ents"].get(r["claimed_by"])
            row["claimed_by"] = r["claimed_by"]
            row["claimed_by_name"] = cby["name"] if cby else r["claimed_by"]
        # A story told on a pattern's shape is not a claim about who anything
        # IS: "Bronze serpent is an instance of Sin, judgment and mercy" read
        # as "Who this is said to be" on the pattern's card. The pattern's own
        # table carries it (templates_for / template_family).
        if r["type"] == "instance_of" and ("pattern" in (row["otype"], e.get("type"))
                                           or r["other"].startswith(("tpl_", "tplstage_", "rolepat_", "rrow_", "msg"))
                                           or eid.startswith(("tpl_", "tplstage_", "rolepat_", "rrow_", "msg"))):
            continue
        if r["type"] in IDENTITY_RANK and row["otype"] not in NOT_A_SUBJECT:
            label, rank = IDENTITY_RANK[r["type"]]
            # an inbound `signifies` means something else stands for THIS one
            if r["dir"] == "in" and r["type"] in ("signifies", "instance_of",
                                                  "likened_to", "draws_on"):
                label = {"signifies": "Signified by",
                         "instance_of": "Has as an instance",
                         "likened_to": "Likened to",
                         "draws_on": "Its word drawn on by"}[r["type"]]
            elif r["dir"] == "in":
                # seen from the title's side: Jesus "Said of himself" the
                # Christ, so the Christ card reads "Said of himself by: Jesus"
                # ("Designates itself as: Jesus" read backwards)
                label = {"self_designated_as": "Said of himself by",
                         "spoken_of_as": "Spoken of as this",
                         "named_with": "Named alongside",
                         "titled": "Is a title of",
                         "assumed_form_of": "Was the form taken by",
                         "deity_of": "Worships this one as god"}.get(
                             r["type"], label)
            same.append({**row, "label": label, "rank": rank})
        elif r["type"] in DISTINCTION:
            apart.append({**row, "label": "Distinguished from"})
    same.sort(key=lambda x: (x["rank"], x["name"]))

    # A DISTINCTION ONLY MEANS SOMETHING WHERE AN IDENTITY CLAIM EXISTS.
    # Abraham and Moses have no need to be shown there, because there is
    # no equivalency established first. There is no "dispute" to settle.
    #
    # Exactly so. "Before Abraham was, I am" is a claim of priority, not a
    # denial that Jesus is Abraham -- nobody proposed that. The distinction is
    # load-bearing only against a figure the text ALSO identifies him with, so
    # the prominent block is filtered to those pairs and the rest stay in the
    # relationship tree below, where they read as what they are.
    claimed = {x["id"] for x in same}
    disputed = [x for x in apart if x["id"] in claimed]
    other = [x for x in apart if x["id"] not in claimed]
    disputed.sort(key=lambda x: x["name"])
    other.sort(key=lambda x: x["name"])
    return same, disputed, other


# The categories whose relations are claims by nature -- a verdict, a likeness,
# a title, a mention, who is whose God -- so a speaker's claim stays among them,
# marked as the speaker's. Every other category narrates (P-71).
CLAIM_STAYS = {"Verdicts", "Concepts", "Images & figures", "Language",
               "Father, Son & Spirit"}
# Where the speaker's words ARE the act -- God's "Go" (Gen 12:1) is God charging
# Abraham -- the relation is narrated by being spoken, so a speaker's claim of
# his own speech act stays in its category (still marked as his words).
PERFORMATIVE = {"charged", "told", "besought", "warned", "rebuked", "blessed",
                "cursed", "quoted", "explained", "appointed", "instituted",
                "commanded_the_making_of", "named", "answered", "self_designated_as"}


def _first(meta, field):
    vals = (meta or {}).get(field) or []
    return vals[0]["v"] if vals else None


# ---- the Knowledge Graph Navigator -------------------------------------------
# 2026-10-01: app1's node graph, kept as an Easter egg at the foot of
# Explore -- an awesome way to explore quickly, one that rewards the curious
# without being made the centerpiece.
# One hop, always; siblings inferred, always; the strength scoring is app1's
# (app/static/app.js edgeStrength), so the same ties are thick and thin.
#
# ONLY WHAT A NODE CAN HOLD. The app1 graph did not work well for
# "text" nodes, so it includes only what it supports well. A node's
# label is its name, and measured over the entity files a text's name is a
# quoted saying (median 24 characters, 39% over 28), a passage's 66% over, a
# pattern's 64%, an assessment's 32% -- against people 1% and places 1%. The
# types below are the ones app1 drew with a shape of their own, plus images,
# whose names are short ("young lion").
# "text" too (2026-10-11: the knowledge graph navigator did not really
# work for "love"; centred on a concept, it killed the
# graph): a concept is joined to the rest almost wholly through the passages
# that speak of it (love 17 of 17, faith 31 of 39), so without them a concept
# drew as one node and no edges. And then every kind (themes,
# events, aggregates, etc. were checked as well): an event lost the passages that tell it
# and the patterns it is an instance of ("Israel receives the law": 5 and 15),
# and a verdict or a pattern could not be centred at all
GRAPH_TYPES = {"person", "place", "group", "event", "concept", "object", "image",
               "title", "creature", "covenant", "being", "observance", "text",
               "passage", "assessment", "pattern"}
_GRAPH_IX = None


def _graph_ix(d):
    """Built on first use: each record's verses, from the resolved mentions
    (a pronoun's referent included), and each person's parents, for the
    inferred siblings."""
    global _GRAPH_IX
    if _GRAPH_IX is None:
        verses = collections.defaultdict(set)
        p = OUT / "mentions.jsonl.gz"
        if p.exists():
            for line in gzip.open(p, "rt", encoding="utf-8"):
                r = json.loads(line)
                occ = r.get("occurrence")
                if occ:
                    b, c, v = occ.split("#")[0].split(".")
                    verses[r["record"]].add((b, int(c), int(v)))
        # THE OLD GRAPH'S IDENTIFICATIONS COUNT TOO. 2026-10-01: the old
        # graph was meant to leave these things in a disambiguation overlay,
        # since much work goes into them for many persons. A record's own
        # verses and every verse a relation cites are where someone read the
        # text and placed that person -- Bathsheba at Matthew 1:6, where no
        # word names her, and at 2 Samuel 11, where the text says "the woman"
        # and "Uriah's wife". The resolver sees only names and pronouns; these
        # are the readings it cannot make. A range counts by its first verse.
        def place(rec, ref):
            m = _macula_ref(d, re.split(r"[-–]", str(ref))[0]).split(".")
            if len(m) == 3 and m[1].isdigit() and m[2].isdigit():
                verses[rec].add((m[0], int(m[1]), int(m[2])))
        for rid, ent in d["ents"].items():
            for ref in ent.get("refs") or []:
                place(rid, ref)
        for pid, rs in d["rels"].items():
            for r in rs:
                if r["dir"] == "out" and not r.get("claimed_by"):
                    for ref in r.get("refs") or []:
                        place(pid, ref)
                        place(r["other"], ref)
        parents = collections.defaultdict(list)        # child -> [(type, parent, refs)]
        for pid, rs in d["rels"].items():
            for r in rs:
                if r["dir"] == "out" and r["type"] in ("father_of", "mother_of"):
                    parents[r["other"]].append((r["type"], pid, r["refs"]))
        _GRAPH_IX = {"verses": verses, "parents": parents}
    return _GRAPH_IX


def _shared(ix, a, b):
    """app1's interaction(): verses naming both, and chapters naming both
    where no verse does -- one scene is weaker than one sentence, not nothing."""
    va, vb = ix["verses"].get(a, set()), ix["verses"].get(b, set())
    both = va & vb
    ch = lambda s: {(x[0], x[1]) for x in s}  # noqa: E731
    return len(both), len((ch(va) & ch(vb)) - ch(both))


_BARE_QUOTE = re.compile(r"[\"“‘'][^\"“”‘’]*[\"”’']\.?")


def _quote_ref(d, note, refs):
    """For a note that is nothing but a quotation, the cited verse it is
    quoted from, or "" when it is a bare quotation found in none of them, or
    None when the note is not a bare quotation at all. 2026-10-02, on
    Mary and Jesus: a "why it's recorded" reading "Jesus' mother and
    brothers came" -- a quotation is the text's words, not a reason, and the
    tie cited four verses without saying which one it was."""
    if not _BARE_QUOTE.fullmatch(note.strip()):
        return None
    want = " ".join(re.findall(r"[a-z]+", note.lower().replace("’", "'")))
    for ref in refs or []:
        mr = _macula_ref(d, re.split(r"[-–]", str(ref))[0])
        _eref, text = _verse_text(d, mr)
        have = " ".join(re.findall(r"[a-z]+", (text or "").lower().replace("’", "'")))
        if want and want in have:
            return re.split(r"[-–]", str(ref))[0]
    return ""


def api_graph(d, q):
    """One hop around an entity, for the Knowledge Graph Navigator: the
    entity, every drawable thing it is related to, and every relation among
    them. A speaker's claim (`claimed_by`, P-71) is left out: drawn as a line
    it would read as the narrator's fact, and the card already shows it as
    that speaker's words."""
    eid = (q.get("id") or [""])[0]
    e = d["ents"].get(eid)
    if not e:
        return {"found": False}
    if e.get("type") not in GRAPH_TYPES:
        return {"found": True, "drawable": False, "name": e.get("name"), "type": e.get("type")}
    ix = _graph_ix(d)
    ok = lambda x: (d["ents"].get(x) or {}).get("type") in GRAPH_TYPES  # noqa: E731
    ids = {eid} | {r["other"] for r in d["rels"].get(eid, [])
                   if not r.get("claimed_by") and ok(r["other"])}
    edges, seen = [], set()

    def add(src, dst, typ, refs, certainty, derived=False, note=None, label=None):
        key = (src, typ, dst, label)
        if key in seen:
            return
        seen.add(key)
        spec = d["cats"].get(typ, {})
        sv, sc = _shared(ix, src, dst)
        edge = {"id": f"e{len(edges)}", "source": src, "target": dst, "type": typ,
                      "label": label or _rel_label(d, spec, typ, dst, True),
                      "category": spec.get("category") or "other",
                      "certainty": certainty or "explicit", "refs": list(refs or [])[:4],
                      "weight": spec.get("weight") if spec.get("weight") is not None else 2,
                      "symmetric": bool(spec.get("symmetric")) or None,
                      "shared_verses": sv, "shared_chapters": sc,
                      **({"derived": 1} if derived else {}),
                      **({"note": note} if note else {})}
        edges.append(edge)
        return edge

    # each tie's own note, for the click (2026-10-02: show the notes on
    # click in the navigator, in a subtle way for the curious)
    for a in sorted(ids):
        for r in d["rels"].get(a, []):
            if r["dir"] == "out" and r["other"] in ids and not r.get("claimed_by"):
                edge = add(a, r["other"], r["type"], r["refs"], r.get("certainty"),
                           note=(r.get("note") or "").strip() or None, label=r.get("label_out"))
                if edge and edge.get("note"):
                    q = _quote_ref(d, edge["note"], r["refs"])
                    if q is not None:            # "" = a quotation, verse not found
                        edge["note_ref"] = q

    # SIBLINGS BY A SHARED PARENT, always (siblings are inferred by default).
    # app1's rule (bibleont.graph.derived_siblings): a child of the same
    # recorded father or mother, not already a stated sibling, drawn as
    # `sibling_of`, implied, citing the parentage verse it rests on.
    stated = {r["other"] for r in d["rels"].get(eid, [])
              if r["type"] in ("sibling_of", "half_sibling_of")}
    for ptype, parent, prefs in ix["parents"].get(eid, []):
        for r in d["rels"].get(parent, []):
            kid = r["other"]
            if (r["dir"] == "out" and r["type"] == ptype and kid != eid
                    and kid not in stated and ok(kid)):
                ids.add(kid)
                pname = (d["ents"].get(parent) or {}).get("name", parent)
                add(eid, kid, "sibling_of", (prefs or [])[:1] + (r["refs"] or [])[:1],
                    "implied", derived=True,
                    note=f"both children of {pname}")

    nodes = [{"id": x, "label": (d["ents"].get(x) or {}).get("name") or x,
              "etype": (d["ents"].get(x) or {}).get("type")} for x in sorted(ids)]
    catlabels = {}
    for spec in d["cats"].values():
        catlabels.setdefault(spec.get("category") or "other", spec.get("catlabel"))
    # every category, not only this centre's: the legend lists them all in a
    # fixed order, so a colour means the same thing on every node walked to,
    # and an empty one says "none recorded here" (app1's legend did the same)
    # THE NAVIGATOR'S RULE, SERVED FROM THE DECLARED POLICY (plan 8.1f,
    # ontology/schema/salience.json): its tie strength and how many records it
    # draws first, so the page keeps no copy of its own
    _membership()                                    # puts tools/meaning on the path
    import salience
    nav = salience.entry("navigator_tie_strength")
    return {"found": True, "drawable": True, "center": eid, "addr": _addr(eid),
            "name": e.get("name"),
            "policy": {"parameters": nav["parameters"], "rank": nav["rank"]},
            "nodes": nodes, "edges": edges,
            "categories": {k: v or k.replace("_", " ").capitalize()
                           for k, v in sorted(catlabels.items())}}


def api_entity(d, q):
    """A person or concept, with everything the graph relates it to.

    Grouped by the taxonomy's own CATEGORY rather than by relation type, so a
    reader meets "Kinship" and "Rule & succession" instead of 116 type names.
    The direction is kept and the inverse label used when this entity is on the
    receiving end -- "is the father of" reads wrong when someone is the child.
    """
    eid = (q.get("id") or [""])[0]
    e = d["ents"].get(eid)
    if not e:
        return {"found": False}
    # consolidated into an event (ontology/aliases.jsonl): the event's card
    if e.get("alias_of") and e["alias_of"] in d["ents"]:
        eid = e["alias_of"]
        e = d["ents"][eid]
    groups = collections.defaultdict(list)
    for r in d["rels"].get(eid, []):
        spec = d["cats"].get(r["type"], {})
        other = d["ents"].get(r["other"])
        label = r.get("label_out" if r["dir"] == "out" else "label_in") or \
            _rel_label(d, spec, r["type"], r["other"] if r["dir"] == "out" else eid, r["dir"] == "out")
        cat = spec.get("catlabel", "Other")
        # A story told in a pattern's shape is not a fact about language,
        # which is where the schema files `instance_of` (for refrains and
        # beatitudes). 2026-09-30, of the graph's lane: the story told
        # this way is good.
        ends = (eid, r["other"])
        if r["type"] == "spoken_in":
            cat = "Spoken in" if r["dir"] == "out" else (
                "Speech acts spoken in it" if r["other"].startswith("sact_") else "Messages spoken in it")
        elif r["type"] == "specializes" and any(x.startswith("msggroup_") for x in ends):
            cat = "Message group"
        elif r["type"] == "specializes" and any(x.startswith("sact") for x in ends):
            cat = "Speech act"
        elif any(x.startswith(("rolepat_", "rrow_", "rcell_")) for x in ends) \
                and r["type"] in ("instance_of", "part_of"):
            cat = "Role pattern"
        elif r["type"] == "specializes" and any(x.startswith("tpl_") for x in ends):
            cat = "Story told this way"
        elif r["type"] == "instance_of":
            if any(x.startswith("tpl_") for x in ends):
                cat = "Story told this way"
            elif any(x.startswith("tplstage_") for x in ends):
                cat = "Story stage"
        elif r["type"] == "part_of" and any(x.startswith("stage_") for x in ends):
            cat = "Story stage"
        # A SPEAKER'S CLAIM IS SHOWN AS THE SPEAKER'S (P-71, approved 2026-10-01
        # from the UI committee's card). Where the relation
        # narrates something happening -- killing, giving, going -- a claim of
        # it is not an event (Abraham's fear, Gen 12:12), so it leaves the
        # narrated categories for its own; where it is a verdict, a likeness or
        # a mention, it stays in its category and says whose words it is.
        claim = r.get("claimed_by")
        cby = d["ents"].get(claim) if claim else None
        doer = eid if r["dir"] == "out" else r["other"]
        if claim and cat not in CLAIM_STAYS \
                and not (r["type"] in PERFORMATIVE and claim == doer):
            cat = "In someone's words"
        groups[cat].append({
            "label": label, "type": r["type"], "dir": r["dir"],
            "other": r["other"],
            "name": other["name"] if other else r["other"],
            "otype": other["type"] if other else None,
            "refs": r["refs"][:4], "certainty": r.get("certainty"),
            **({"claimed_by": claim, "claimed_by_name": cby["name"] if cby else claim}
               if claim else {}),
            **({"reading": "the major-theme map"} if r.get("map") else
               {"reading": r["reading"], "note": r.get("note")} if r.get("reading") else {}),
            **({"pairs": r["pairs"]} if r.get("pairs") else {}),
            # a story told again carries its explanation and where the two
            # differ to the card, where it opens under the steps (plan 6.18)
            **({"note": r.get("note")} if r["type"] == "same_steps_as" and r.get("note") else {}),
        })
    # A stage reaches its pattern through its story (stage part_of arc,
    # arc instance_of pattern); the graph draws that second hop too, named
    # for what it is, so the pattern is one click from the stage.
    ts = template_stage(d, eid)
    if ts:
        role = ts["pattern_kind"] == "Role pattern"
        groups["Role pattern" if role else "Story told this way"].append({
            "label": "a cell of the pattern" if role else "a stage of the pattern",
            "type": "instance_of", "dir": "out",
            "other": ts["pattern_id"], "name": f"{ts['pattern_kind']}: {ts['family_name']}",
            "otype": "pattern", "refs": [], "certainty": "implied"})
    # a person reaches their role patterns through their rows
    for x in roles_for(d, eid):
        groups["Role pattern"].append({
            "label": "has a row in", "type": "instance_of", "dir": "out",
            "other": x["pattern_id"], "name": "Role pattern: " + x["pattern_name"],
            "otype": "pattern", "refs": [], "certainty": "implied" if x["given"] else "conjectured"})
    ordered = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    # the original-language word behind the name, where one was resolved
    orig = None
    code = d["namemap"].get(e["name"])
    k = _name_key(d, e) if code else None
    if k:
        if k != code[0].lower() + re.sub(r"^0+", "", code[1:]):
            code = k[0].upper() + k[1:].zfill(4)   # the other testament's word
        meta = d["lmeta"].get(k) or {}
        lx = d["lex"].get(k) or {}
        prof = d["profiles"].get(k)
        orig = {"key": k, "strong": code,
                "lang": "Hebrew" if k[0] == "h" else "Greek",
                "lemma": d["lemmas"].get(k) or lx.get("word") or _first(meta, "normalized"),
                "translit": _first(meta, "transliteration") or lx.get("translit"),
                "gloss": lx.get("gloss") or _text_gloss(d, k),
                "uses": _uses(d, k),
                "profiled": bool(prof),
                "lxx": [x["v"] for x in (meta.get("greek") or [])[:3]]}
    # A CONCEPT has no single word behind it. "Mercy" is hesed and rachamim and
    # eleos and oiktirmos, and picking one would be a claim the corpus does not
    # make -- so every profiled lemma the text glosses this way is offered,
    # commonest first, and the reader chooses which thread to follow.
    want = _slug(e["name"])
    words = []
    if want:
        for k, prof in d["profiles"].items():
            # a verb glossed "to love" is the concept love (φιλέω, John 21,
            # was on neither the love card nor its own way back, 2026-10-09)
            g = _slug(re.sub(r"^to\s+", "", prof.get("gloss") or ""))
            if g and g == want and (orig is None or k != orig["key"]):
                meta = d["lmeta"].get(k) or {}
                words.append({"key": k, "gloss": prof.get("gloss"),
                              "lang": _lang_of(d, k),
                              "lemma": d["lemmas"].get(k)
                                       or (d["lex"].get(k) or {}).get("word")
                                       or _first(meta, "normalized"),
                              "translit": _first(meta, "transliteration"),
                              "uses": _uses(d, k)})
        # AND THE WORDS THE TEXT SPELLS RATHER THAN TRANSLATES, where the text
        # itself says what they mean. 2026-09-19: what would it take
        # for Abba to show up on the main father page as well?
        #
        # It takes no lexicon. ἀββά is glossed "Abba", so matching on the gloss
        # could never find it — but the New Testament follows it with ὁ πατήρ
        # in all three of its occurrences, which is the text glossing its own
        # loanword. That apposition is the evidence, and the card says so
        # rather than quietly listing ἀββά as if it were a word for father.
        for k, ln in (d.get("loans") or {}).items():
            m = ln.get("means")
            if not m or _slug(m.get("gloss")) != want:
                continue
            if any(w["key"] == k for w in words):
                continue
            words.append({"key": k, "gloss": ln.get("gloss"),
                          "lang": _lang_of(d, k), "lemma": ln.get("lemma"),
                          "translit": ln.get("x"), "uses": ln.get("n") or 0,
                          "via": f"the text reads it “{m.get('gloss')}” "
                                 f"in all {ln.get('n')} of its occurrences"})
        words.sort(key=lambda w: -w["uses"])
        # THE WORD IN THE CARD'S OWN VERSES FIRST. Matching on the gloss alone,
        # the image card (Gen 1:26-27) offered εἰκών and סֶמֶל, an idol's
        # "image" (Deut 4:16), and not צֶלֶם, the word of the verses it cites
        # (M-D8, the 2026-10-02 evaluation) -- its gloss is not "image" alone,
        # though the card's anchors hold it. An anchored word that stands in
        # one of the card's own verses leads the list, the rest follow
        if e["type"] not in ("person", "place") and e.get("refs"):
            own = {_macula_ref(d, r) for r in e["refs"]}
            vs = _verses_of(d)
            mine = [k for k, _s in _anchors().get(eid, []) if vs.get(k, set()) & own]
            have = {w["key"] for w in words}
            for k in mine:
                if k not in have and (orig is None or k != orig["key"]):
                    meta = d["lmeta"].get(k) or {}
                    prof = d["profiles"].get(k) or {}
                    # MACULA's own lemma and gloss first: the lexicon is not on
                    # the live site, and a word with neither showed its bare
                    # key ("h2056" on the child card, 2026-10-03)
                    words.append({"key": k, "gloss": prof.get("gloss") or
                                  (d["lex"].get(k) or {}).get("gloss") or _text_gloss(d, k),
                                  "lang": _lang_of(d, k),
                                  "lemma": d["lemmas"].get(k)
                                           or (d["lex"].get(k) or {}).get("word")
                                           or _first(meta, "normalized"),
                                  "translit": _first(meta, "transliteration"),
                                  "uses": _uses(d, k)})
            words.sort(key=lambda w: (w["key"] not in mine, -w["uses"]))
        # a person or place whose verses are all in one testament is named in
        # that testament's language: Jacob's son is not the NT's Ἰωσήφ
        side = _testament_lang(e) if e["type"] in ("person", "place") else None
        if side:
            words = [w for w in words if (w.get("key") or side)[0] == side]
        # and a name belongs to whoever bears it: a proper name that never
        # stands in this record's verses is someone else's (the monster Rahab
        # listed Ῥαάβ, the woman of Jericho's, Heb 11:31 -- N-D3)
        names = _own_names(d, e)
        if names is not None:
            words = [w for w in words if w["key"] not in _PROPER or w["key"] in names["keys"]]
    # A CARD THAT NAMES ITS OWN WORDS. A name made of a phrase took its
    # parts as its words: "the chief priests" listed כֹּהֵן "priest" and רֹאשׁ
    # "head", and ἱερεύς, a different word; "the sons of Israel" listed בֵּן
    # "son" (2026-10-10, the review of the three cards). Where the record says
    # which words are its own, those are its words.
    if e.get("words"):
        named = []
        for k in e["words"]:
            lx = d["lex"].get(k) or {}
            meta = d["lmeta"].get(k) or {}
            named.append({"key": k, "gloss": (d["profiles"].get(k) or {}).get("gloss") or lx.get("gloss") or _text_gloss(d, k),
                          "lang": _lang_of(d, k), "lemma": d["lemmas"].get(k) or lx.get("word") or _first(meta, "normalized"),
                          "translit": _first(meta, "transliteration"), "uses": _uses(d, k)})
        words = named
    # others answering to the same name, kept separate and made visible
    same = []
    for nm in [e["name"]] + list(e.get("aka") or []):
        for other in d["alias_ix"].get(_slug(nm), ()):  # noqa: B007
            if other == eid:
                continue
            oe = d["ents"].get(other)
            if oe and not any(x["id"] == other for x in same):
                same.append({"id": other, "name": oe["name"],
                             "type": oe["type"], "who": _who(oe),
                             "desc": (oe.get("desc") or "")[:120],
                             "relations": len(d["rels"].get(other, []))})
    same.sort(key=lambda x: -x["relations"])
    ident, disputed, contrasted = identity_of(d, eid, e)
    return {"found": True, "id": e["id"], "name": e["name"],
            "addr": _addr(e["id"]),          # the card's public address
            # A CONCEPT HUB (plan 7.6f): the concept by the forms the text uses,
            # every row a door; on the live site only once its owner has seen
            # it (concept_hub). Not "hub": that field is the declared list's
            # (A.34), later in this answer
            "concept_hub": concept_hub(eid),
            # THE THEME IT STANDS AT THE CENTRE OF (ontology/concept-theme-bridges.json, by hand)
            "theme_bridge": theme_bridges(eid),
            # and a concept card without one gets its top half by rule
            # -- and a people's card too (2026-10-10, the card "the Jews":
            # who they are, in the text's words, before what some of them did)
            "face": (concept_face(d, eid, e, words[:8])
                     # every group: a faction's or an order's members may be
                     # its first readers too (the Pharisees, the chief priests)
                     if e["type"] in ("concept", "group")
                     and not concept_hub(eid) else None),
            # a saying, a speech, a parable: its words first (text_face)
            "said": text_face(d, eid, e) if e["type"] in ("text", "passage", "assessment") else None,
            # and a person with no description: who they are, from their own
            # record and kinship, and the verses that name them
            "pface": person_face(d, eid, e) if e["type"] == "person" else None,
            # ...and every person's family, for the line in the face
            "kin": person_kin(d, eid, e) if e["type"] == "person" else None,
            "mined": mined_for(d, f"record:{eid}"),
            "original": orig, "words": words[:8], "same_name": same[:8],
            "identity": ident, "distinct": disputed,
            "contrasted": contrasted,
            # what the readings tag with this record's name (its tag pages)
            "tags": tags_for_record(d, e),
            # the major themes and their concepts that map to this node (the
            # Copilot theme map; tools/themes/theme_map.py matched by name)
            "mthemes": [dict(x, title=_title(_theme_map()["_by"][x["theme"]]["title"]))
                        for x in _theme_map().get("by_node", {}).get(eid, [])
                        if x["theme"] in _theme_map()["_by"]],
            # an event node carries its tellings, people and cross-references;
            # every node carries the events its name is in
            "event": event_of(d, eid) if e["type"] == "event" else None,
            "events": events_for(d, eid),        # all: the card folds past 12
            # the event templates (plan A.9): the instances this node is or is
            # part of, and, for a template's own node, its stages and instances
            "templates": templates_for(d, eid),
            "template_family": template_family(d, eid),
            "template_stage": template_stage(d, eid),
            # a declared list's members and moves (A.34), on its one card
            "hub": hub_for(d, eid),
            # the role patterns (plan A.10) a person has a row in; not "roles",
            # which is the record's own list ("king", "shepherd") and won
            "role_patterns": roles_for(d, eid),
            # the divine messages: a message's own card, and the messages
            # spoken in this node (a story or role pattern, an event)
            "message": message_card(d, eid),
            # a significant number's card: its occasions, phrases and the
            # text's own joins (plan 6.16, tools/numbers/significant_numbers.py)
            "number": _numbers().get(eid),
            "messages_in": messages_in(d, eid),
            # the speech acts (plan A.12): an act's card, and the acts spoken here
            "speech_act": speech_card(d, eid),
            "acts_in": acts_in(d, eid),
            # a saying named by who said it and where is shown by its own
            # words, and placed in the event it belongs to
            "label": speech_label(d, e),
            # how many verses the phrase itself stands in (multi-word nodes)
            "phrase_n": (lambda r: len(set(r["english"]) | set(r["across"])) if r else 0)(
                _phrases().get(eid)),
            "within_events": events_at(d, (e.get("refs") or [""])[0])
                             if e["type"] in ("text", "passage") else [],
            "type": e["type"], "desc": e.get("desc"),
            # which one this is, said on the card itself when the name is shared:
            # people and places, where the note is plain ("son of Jacob", "town
            # of Issachar"); a concept's note is the graph's own working
            # language ("the God of the corpus, under every name ...")
            "who": _who(e) if same and e["type"] in ("person", "place") else None,
            # A THEME'S OWN CONCEPT IS A READING, and its card says so (the
            # BibleProject reader, 2026-10-02: "Eden as Proto-Temple" read as
            # the text's own idea). The tools stay in About.
            "reading": ({"of": "the major-theme map"}
                        if (e.get("attrs") or {}).get("kind") in ("theme_concept", "theme")
                        or str(e["id"]).startswith("theme_") else None),
            "aka": e.get("aka") or [], "refs": (e.get("refs") or [])[:12],
            "tribe": e.get("tribe"), "era": e.get("era"),
            "roles": e.get("roles") or [],
            "total_relations": sum(len(v) for v in groups.values()),
            "types": len({r["type"] for r in d["rels"].get(eid, [])}),
            # No truncation. Jesus carries 419 relations across 57 types and a
            # 40-per-category cap quietly hid most of him; the tree folds, so
            # volume costs nothing until someone opens a branch.
            "groups": [{"category": k, "items": v} for k, v in ordered]}


def _vkey(ref):
    """Sort a section ref in CANON order.

    Sorting the strings is wrong twice over: it puts chapter 10 before chapter
    2, and it opens an instance list with 1 Chronicles and 1 Corinthians
    because `1` sorts before `G`. A reader scanning where else a pattern
    appears is reading the canon, not an index. `TO_MACULA` is already in canon
    order, so its key order is the authority rather than a second list that
    could drift from it."""
    p = ref.split(".")
    try:
        return (_CANON.get(p[0], 999), int(p[1]), int(p[2]))
    except (IndexError, ValueError):
        return (_CANON.get(p[0], 999), 0, 0)


def api_pattern(d, q):
    """One pattern: its template, what fills each slot, and where it is used.

    This is the navigation that was asked for -- from a verse to the pattern it
    uses, and from the pattern to everywhere else it is used. A pattern is a
    unit like any other, so it opens as a card and the stack keeps working.
    """
    # A higher-level pattern -- thematic or arc -- is asked for by `id`; the
    # subsentence patterns this endpoint was built for are asked for by `key`.
    # One endpoint, because a pattern is a pattern to the reader and the card
    # that opens should not depend on which layer found it.
    pid = (q.get("id") or [""])[0]

    # A STAMP CHIP. `_chips()` mints ids shaped `stamp:merism`, and nothing
    # served them: this endpoint resolved ids against `hpat` only, returned
    # {"found": False}, and the client returned silently on that -- so the
    # chips have never been navigable in any version of the reader.
    #
    # What a stamp chip can honestly answer is WHERE ELSE, which is the second
    # half of this endpoint's own promise ("from the pattern to everywhere else
    # it is used"). It cannot answer with a template and slots, because a stamp
    # is a label rather than a form -- so `form` is left empty rather than
    # faked, and the card shows the label, how rare it is, and its sections.
    if pid.startswith("stamp:"):
        sid = pid[6:]
        # A DECLARED LIST IS ONE CARD (A.34, 2026-10-07): its chip opens
        # the list's graph card, which carries the members, the moves and
        # these same sections
        hub = _agg_hubs()["hubs"].get(sid)
        if hub and hub.get("card") in d["ents"]:
            return {"found": True, "redirect": hub["card"]}
        # each section ONCE: a section stamped twice with the same stamp
        # (citing two verses) was listed twice — 2026-09-29: the same
        # event/verse repeated multiple times in the display for no
        # visible reason
        refs = list(dict.fromkeys(d.get("stamp_secs", {}).get(sid) or []))
        if not refs:
            return {"found": False}
        rows = {}
        for ref in refs:
            for r in d.get("stamp_by_sec", {}).get(ref, []):
                if r["id"] == sid:
                    rows[ref] = r
                    break
        cat = next((r.get("category") for r in rows.values()
                    if r.get("category")), "stamp")
        books = {ref.split(".")[0] for ref in refs}
        det = (d.get("taxdetail") or {}).get(sid) or {}
        explain = DEVICE_GLOSS.get(sid)
        return {"found": True, "higher": True, "id": pid,
                "label": sid.replace("_", " "),
                # What the taxonomy itself records: the members, the passage
                # it is drawn from, and the shape it moves in.
                "explain": explain,
                "members": det.get("members"),
                "passage": det.get("ref"),
                "shape": det.get("pattern"),
                "detail": {k: v for k, v in det.items()
                           if k not in ("members", "ref", "pattern")
                           and isinstance(v, (str, int, float))},
                "family": cat, "form": [], "traits": [sid],
                "scores": {"support": len(refs), "spread": len(books)},
                "books": sorted(books),
                # the WHOLE list (it stopped at 60 with "...and N more" that
                # could not be opened), each with its book, and whether a
                # sequence exists for it (the button did nothing where none did)
                "instances": [
                    {"ref": ref, "book": ref.split(".")[0],
                     "title": d.get("sectitle", {}).get(ref, ""),
                     "seq": _has_sequence(d, ref),
                     "fill": ([[sid, rows[ref].get("cites")]]
                              if rows.get(ref, {}).get("cites") else None)}
                    for ref in sorted(refs, key=_vkey)],
                "total": len(refs),
                # WHAT THESE SHARE, mined from their structure
                # (tools/event_profiles.py): what sets them apart, and how
                # they divide — to reveal something more about the
                # characteristics of this list of events
                "profile": _event_profiles().get(sid)}

    if pid:
        h = d.get("hpat", {}).get(pid)
        if not h:
            return {"found": False}
        inst = d.get("hpat_inst", {}).get(pid, [])
        return {"found": True, "higher": True, "id": pid,
                "label": h.get("arc") or " + ".join(h.get("traits") or []),
                "family": h.get("family"), "form": h.get("form"),
                "traits": h.get("traits"), "scores": h.get("scores"),
                "books": h.get("books"),
                "instances": [{"ref": x["ref"],
                               "title": d.get("sectitle", {}).get(x["ref"], ""),
                               "fill": x.get("fill")} for x in inst[:60]],
                "total": len(inst)}
    r = d["patterns"].get((q.get("key") or [""])[0])
    if not r:
        return {"found": False}
    say = {"productive": "The text builds new sentences with this shape.",
           "formula": "The text repeats this rather than composing with it.",
           "local": "Confined to a book or two — a local habit."}
    return {"found": True, **r, "note": say.get(r["kind"], ""),
            "anchor": _anchor_node(d, r),
            "crossing": _crossing(d, r),
            "observed": _observed_pair(d, r),
            # The same template split by testament, so a pattern that crosses
            # through its OWN instances gets the section a pattern crossing
            # through a counterpart already had.
            "own_side": _side(d, r, (r.get("lemma_key") or "").startswith("g")),
            "other_side": _side(d, r,
                                not (r.get("lemma_key") or "").startswith("g")),
            "nt_books": [b for b in (r.get("books") or []) if b in NT_BOOKS],
            "counterparts": _counterparts(d, r),
            # The pattern named by its lexemes, and the per-position evidence
            # behind that name. `share` says whether a position is fixed in
            # the LANGUAGE or only in the English: `declares the [X]` holds
            # נְאֻם at 1.00 across one lexeme, while the `to` of
            # `[S] said to [X]` covers FOUR Hebrew prepositions at 0.63 — one
            # is a formula and the other is a rendering that coincides.
            "lex": _lex_template(r),
            "fixed": r.get("fixed") or [],
            "fixed_orig": r.get("fixed_orig"),
            "describes": describe_pattern(r)}


def _prop_index(d):
    """-> ({template key: proposition key}, {proposition key: [patterns]}).

    A proposition key names a predicate in a way both languages reach, via
    MACULA's `greekstrong`. 2026-09-19: no evidence was visible that
    the pattern exists in Greek; was that because the pattern does not
    extend, or because it had not been rendered?

    It was the second. `tools/propositions.py` established that נְאֻם and λέγω
    are one predicate, G3004, and nothing on the card read it — so a formula
    the text uses in both testaments looked Hebrew-only to a reader.
    """
    got = d.get("_props")
    if got is not None:
        return got
    meta = d.get("lmeta") or {}
    bykey, byprop = {}, collections.defaultdict(list)
    for key, r in (d.get("patterns") or {}).items():
        lk = r.get("lemma_key")
        if not lk:
            continue
        if lk.startswith("g"):
            pk = lk
        else:
            pk = None
            for x in ((meta.get(lk) or {}).get("greekstrong") or [])[:1]:
                n = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", x.get("v") or ""))
                if n:
                    pk = "g" + n
        if pk:
            bykey[key] = pk
            byprop[pk].append(r)
    d["_props"] = (bykey, byprop)
    return d["_props"]


NT_BOOKS = {"Mat", "Mrk", "Luk", "Jhn", "Act", "Rom", "1Co", "2Co", "Gal",
            "Eph", "Php", "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm",
            "Heb", "Jas", "1Pe", "2Pe", "1Jn", "2Jn", "3Jn", "Jud", "Rev"}


def _crossing(d, r):
    """How this template reaches the other testament, if it does.

    TWO MECHANISMS, and they find different things. 2026-09-19, spotting
    Matthew 11:10 and Luke 7:27 inside `[S] is behold`, in a slot filled
    `this`: the slot in the prior rendering carried NT references.

    That was right and it exposed a gap. `crosses` was computed from counterparts
    alone -- a SEPARATE template in the other language sharing a predicate
    through MACULA's Septuagint column -- and missed that a template can hold
    both languages ITSELF. 836 of 6,913 do, which is 12%.

    Those merged because both lexemes canonicalise to the same English gloss:
    הִנֵּה and ὁράω are each commonest as "behold", so their templates are one
    row. That is weaker evidence than the Septuagint bridge, being agreement
    between two lexicographers rather than a translator's own alignment -- and
    it is the mechanism criticised earlier today, now one level up.

    But it FINDS WHAT THE BRIDGE MISSES. The bridge fails on behold because
    the Septuagint column names the particle ἰδού, G2400, while MACULA
    lemmatises the New Testament's 243 ἰδοὺ under the verb ὁράω, G3708 -- the
    same word filed differently on each side. The gloss route crosses it
    anyway.

    So both are reported and the card says which is speaking.
    """
    books = set(r.get("books") or [])
    return {"direct": bool(books & NT_BOOKS) and bool(books - NT_BOOKS),
            "counterpart": bool(_counterparts(d, r))}


def _side(d, r, want_nt):
    """This template's own instances, restricted to one testament.

    2026-09-19: build out the Greek sections below as was done for
    the "Declare the" page; this should happen systemically, so that
    pattern 3 already has it.

    A pattern reaches the other testament one of two ways and only one of them
    had a section built. `declares the [X]` crosses through a SEPARATE Greek
    template, which already renders. `[S] is behold` crosses through its OWN
    instances -- Matthew 11:10 and Luke 7:27 are in it -- and those had nowhere
    to be shown, so the card said it crossed and then offered only Hebrew.

    This slices the template by testament so the second kind gets the same
    treatment as the first: its own fillers, its own shares, its own verses.
    """
    slots, slot_refs = {}, {}
    for slot, fills in (r.get("slot_refs") or {}).items():
        for filler, refs in fills.items():
            side = [x for x in refs
                    if (x.split(".")[0] in NT_BOOKS) == want_nt]
            if not side:
                continue
            slot_refs.setdefault(slot, {})[filler] = side
            slots.setdefault(slot, {})[filler] = len(side)
    if not slots:
        return None
    n = sum(sum(v.values()) for v in slots.values())
    books = sorted({x.split(".")[0] for fills in slot_refs.values()
                    for refs in fills.values() for x in refs},
                   key=lambda b: (r.get("books") or []).index(b)
                   if b in (r.get("books") or []) else 99)
    for slot in slots:
        slots[slot] = dict(sorted(slots[slot].items(), key=lambda kv: -kv[1]))
    return {"key": r["key"], "template": r["template"], "instances": n,
            "reach": len(books), "books": books, "slots": slots,
            "slot_refs": slot_refs,
            "distinct_fillers": sum(len(v) for v in slots.values())}


def _refs_of(r):
    """Every reference this template records, slots first."""
    out = []
    for fills in (r.get("slot_refs") or {}).values():
        for rs in fills.values():
            out.extend(rs)
    return out or (r.get("refs") or [])


def _observed_pair(d, r):
    """The other language's word AS IT STANDS in this template's own verses.

    2026-09-19, on `[S] is behold`: the Greek bridge of the prior pattern was
    wanted, this being an even better case for the bridge.

    Better, and for a clear reason. On `declares the [X]` the Greek had to
    be reached through the Septuagint column, which is a prediction about what
    a translator chose elsewhere. Here the template's own instances include
    Matthew 11:10 and Luke 7:27, so the Greek word is simply present -- ὁράω
    twice against הִנֵּה 172 times -- and pointing at it claims nothing beyond
    what the verses show.

    This is also the only bridge available for behold, since the Septuagint
    column names the particle ἰδού, G2400, while MACULA files the New
    Testament's ἰδοὺ under the verb ὁράω, G3708.
    """
    seen = r.get("lemmas") or []
    if len(seen) < 2:
        return None
    heb = [c for c in (r.get("lemma_key") or "")][:1] == ["h"]
    for lem, n in seen[1:]:
        other = not any("א" <= ch <= "ת" for ch in lem)
        if other == heb:
            key = None
            for k, v in (d.get("lemmas") or {}).items():
                if v == lem:
                    key = k
                    break
            # THE WORD IN THE VERSE, NOT THE DICTIONARY HEADWORD. The lemma
            # here is ὁράω, whose profile gloss is "having seen" -- true of
            # the lexeme and false of these instances, where the text reads
            # Ἰδοὺ, "Behold". Showing the headword would point a reader at a
            # word they will not find and a sense the passage does not use.
            surface = None
            for ref in _refs_of(r):
                for w in d["orig"].get(ref, []):
                    if w.get("l") == lem:
                        surface = w
                        break
                if surface:
                    break
            node = {"t": (surface or {}).get("t") or lem, "n": n, "key": key,
                    "x": (surface or {}).get("x"),
                    "g": (surface or {}).get("g"),
                    "lemma": lem}
            if not node["x"]:
                f = (d.get("gforms") or {}).get(node["t"]) or {}
                node["x"] = f.get("x")
                node["g"] = node["g"] or f.get("g")
            if not node["g"]:
                prof = (d.get("profiles") or {}).get(key or "") or {}
                node["g"] = prof.get("gloss")
            node["rtl"] = any("א" <= ch <= "ת" for ch in node["t"])
            return node
    return None


def _counterparts(d, r):
    """The same predicate's templates on the OTHER side of the testaments.

    Not a claim that the two templates are the same shape -- they are not, and
    that is the whole point: נְאֻם־יְהוָה is a construct and λέγει Κύριος a
    clause. It is a claim that they assert with the same word, which is what
    lets a reader see one formula where the grammar shows two.
    """
    bykey, byprop = _prop_index(d)
    pk = bykey.get(r.get("key"))
    if not pk:
        return []
    mine = (r.get("lemma_key") or "").startswith("g")
    out = []
    for other in byprop.get(pk, []):
        if other.get("key") == r.get("key"):
            continue
        if (other.get("lemma_key") or "").startswith("g") == mine:
            continue
        # The counterpart's OWN evidence travels with it. The card used to
        # show two boxes at the top and then describe only the Hebrew, so the
        # Greek was asserted and never shown. 2026-09-19: the text only
        # described the Hebrew and the two lists were Hebrew only, so both
        # Hebrew and Greek trees are shown.
        out.append({"key": other["key"], "template": other["template"],
                    "instances": other["instances"],
                    "reach": other.get("reach"),
                    "kind": other.get("kind"),
                    "books": other.get("books") or [],
                    "slots": other.get("slots") or {},
                    "slot_refs": other.get("slot_refs") or {},
                    "distinct_fillers": other.get("distinct_fillers"),
                    "skew": other.get("skew"),
                    "describes": describe_pattern(other),
                    "anchor": _anchor_node(d, other)})
    out.sort(key=lambda x: -x["instances"])
    return out[:3]


def _anchor_node(d, r):
    """The pattern's anchor as the READER'S OWN word node, plus the LXX Greek.

    2026-09-19: the Hebrew is displayed prominently in the formula pattern as
    in the reader, with phonetic and English below it (the node representation
    of the word); a click shows the same as a click in the reader; and drilling
    in shows the closest Greek equivalent, so the two can be compared easily.

    Three things, and the disconnect named is that a pattern card
    described a word in English while the reader shows the word itself. Same
    shape, same fields, same click target, so the anchor on a pattern is the
    object a reader already knows rather than a lookalike.

    `greek` is the Septuagint's rendering from MACULA's own column -- for
    נְאֻם it is λέγει, 246 times -- which is what makes a Hebrew formula
    comparable with a Greek one at all.
    """
    key = r.get("lemma_key")
    if not key:
        return None
    meta = d.get("lmeta", {}).get(key) or {}

    def top(field, n=3):
        out = []
        for x in (meta.get(field) or []):
            v = (x.get("v") or "").strip()
            # MACULA marks "no Greek here" with a pair of primes. It is not a
            # word and must not be offered as one.
            if v and v.strip("’'\"") and len(out) < n:
                out.append(v)
        return out

    trans = top("transliteration", 1)
    if not trans:
        # MACULA carries `transliteration` on Hebrew words and not on Greek, so
        # a Greek anchor had the box and no phonetic under it. The Greek New
        # Testament's own words do carry one, so the lemma is looked up there.
        f = (d.get("gforms") or {}).get(r.get("lemma")) or {}
        if f.get("x"):
            trans = [f["x"]]
    # The gloss is the lemma's own, not a slice of the template: splitting
    # "declares the [X]" at the bracket gave "declares the", which is the
    # template minus its slot rather than the word.
    prof = (d.get("profiles") or {}).get(key) or {}
    return {"key": key, "t": r.get("lemma"),
            "x": (trans[0].rstrip("-:") if trans else None),
            "g": prof.get("gloss") or (r.get("template") or "").split(" ")[0],
            "rtl": key.startswith("h"),
            "also": r.get("also") or [],
            # Separate from `also` on purpose. `also` is MACULA glossing the
            # lexeme; `reads` is the Berean text choosing a word in context,
            # and it is the one the reader will actually meet on screen.
            "reads": [w for w, _n in (d.get("bsbw", {}).get(key) or [])[:5]],
            # Only for a Hebrew anchor: a Greek one IS the Greek.
            "greek": top("greek", 3) if key.startswith("h") else []}


def _macula_ref(d, ref):
    """A verse reference in the graph's (MACULA's) numbering, from either
    spelling and either numbering (the reader's refs are the Berean's)."""
    m = re.match(r"^\s*([\w ]+?)[ .](\d+)[:.](\d+)\s*$", ref or "")
    if not m:
        return ref
    b = m.group(1)
    b = TITLE_BACK.get(b, b)
    if b not in d["chapters"] and b not in MACULA_BACK:
        b = book_of(b) or b             # "1 Cor", "Psalm" (2026-10-02)
    b = TO_MACULA.get(b, b)
    r = f"{b}.{int(m.group(2))}.{int(m.group(3))}"
    back = d.get("_vmap_back")
    if back is None:
        back = d["_vmap_back"] = {v: k for k, v in (d.get("vmap") or {}).items()}
    return back.get(r, r)


def api_patterns_for(d, q):
    """The patterns a verse is an instance of, from the miner's node index
    (the older English-template layer is retired from here:
    2026-09-28, "counted layers only"). Sure ones first; `tier` says which
    are for digging."""
    ref = _macula_ref(d, (q.get("ref") or [""])[0])
    return {"patterns": mined_for(d, f"verse:{ref}")}


_MCANON = {b: i for i, b in enumerate(TO_MACULA.values())}


def api_mined(d, q):
    """One mined finding: what it is, how sure, and every instance kept,
    grouped by book in canon order."""
    pid = (q.get("id") or [""])[0]
    r = d["mined"]["rows"].get(pid)
    if not r:
        return {"found": False}
    tier, why = mined_tier(r)
    books = collections.OrderedDict()
    inst = sorted(d["mined"]["inst"].get(pid, []),
                  key=lambda x: (_MCANON.get(x["ref"].split(".")[0], 99),
                                 [int(n) for n in x["ref"].split(".")[1:]]))
    for x in inst:
        b = x["ref"].split(".")[0]
        books.setdefault(TITLE.get(MACULA_BACK.get(b, b), b), []).append(
            {"ref": x["ref"], "m": x["m"]})
    return {"found": True, "id": pid, "tier": tier, "why": why,
            **{k: r.get(k) for k in (
                "pattern", "kind", "family", "support", "support_nt",
                "accounts", "books", "testaments", "reach", "variants",
                "score", "lift", "modes", "nt_echoes")},
            "shown": len(inst), "by_book": [{"book": b, "refs": rs}
                                             for b, rs in books.items()],
            "examples": mined_examples(d, pid, 6)}


def api_mined_verse(d, q):
    """One instance of a mined finding: the Berean text, plain, and the
    original with exactly the words that put this verse on the list boxed
    (by Strong's number, which the structure and the strip share)."""
    pid = (q.get("id") or [""])[0]
    ref = (q.get("ref") or [""])[0]
    marks = set()
    for x in d["mined"]["inst"].get(pid, []):
        if x["ref"] == ref:
            marks |= {str(s).lstrip("0") for s in x["m"]}
    eref = bsb_ref(d, ref)
    try:
        b, c, v = eref.split(".")
        text = d["verses"].get((MACULA_BACK.get(b, b), int(c), int(v))) or ""
    except (ValueError, TypeError):
        return {"found": False}
    orig = [{"t": w.get("t"), "g": w.get("g"), "x": w.get("x"),
             "on": str(w.get("s") or "").lstrip("0") in marks}
            for w in d["orig"].get(ref, []) if w.get("t") or w.get("g")]
    return {"found": True, "ref": ref, "eref": eref, "text": text,
            "orig": orig, "rtl": ref.split(".")[0] in HEBREW_BOOKS}


def book_of(name):
    """A book code from any name search reads: the alias table first ("phil"
    is Philippians), then the first book whose title or code begins with it
    ("1 cor", "psalm", "2 sam")."""
    want = _slug(name)
    if not want:
        return None
    if ALIAS.get(want):
        return ALIAS[want]
    return next((b for b in ORDER if _slug(TITLE.get(b, b)).startswith(want)
                 or _slug(b).startswith(want)), None)


def api_verse(d, q):
    """One verse's text, so a usage can be read WITHOUT leaving the pattern.

    The pattern tab should not easily cause the tab that led to it to
    be overridden when a verse is navigated to. Right -- scanning twenty
    usages should not cost you the passage you came from. The verse opens under
    the citation instead, and going to the chapter stays an explicit choice.
    """
    ref = (q.get("ref") or [""])[0]
    # BOTH SPELLINGS. Citations reach this endpoint as `Gen.18.21` from the
    # structural layers and as `Gen 18:21` -- the display form -- from the
    # concept cards, and only the first parsed. The second fell into the
    # ValueError branch and returned {"ref", "text": ""}, so the verse peek
    # showed an empty box and the button under it read "Read undefined →",
    # because the client formats `d.title` which was never sent.
    # 2026-09-15: clicking on a verse did not successfully show the
    # verse.
    #
    # Accepting both here rather than fixing one caller: this app already
    # carries a note that citations arrive in two spellings, so a parser that
    # handles one of them is a bug waiting for the next caller.
    m = re.match(r"^\s*([\w ]+?)[ .](\d+)[:.](\d+)\s*$", ref)
    # A RANGE, TOO. 2026-10-01, clicking a tie in the Knowledge Graph
    # Navigator: "Jesus was mentor / master to James · Matt 10:1-4 / No text
    # for Matt 10:1-4." 331 of the 25,594 relation citations are ranges
    # (327 within a chapter, "10:1-4"; 4 across, "1:28-2:3"), and this read
    # single verses only -- so every range citation anywhere peeked empty.
    # The verses come joined, each with its number; the reader's own
    # "view in reader" already highlights the span from the link's label.
    rm = None if m else re.match(
        r"^\s*([\w ]+?)[ .](\d+)[:.](\d+)\s*[-–]\s*(?:(\d+)[:.])?(\d+)\s*$", ref)
    if rm:
        return _verse_range(d, ref, rm)
    if not m:
        return {"ref": ref, "text": "", "found": False}
    mb, c, v = m.group(1), int(m.group(2)), int(m.group(3))
    b = MACULA_BACK.get(mb, TITLE_BACK.get(mb, mb))
    if b not in d["chapters"]:
        # "1 Cor 15:49", "2 Sam 7:12", "Psalm 110:4": the names search
        # already reads (the 2026-10-02 evaluation found the verse peek
        # returning nothing for them)
        b = book_of(mb) or b
    text = d["verses"].get((b, c, v), "")
    # THE ORIGINAL TOO. 2026-09-16: literary devices specifically need
    # to show the original language after the verse when clicking on an
    # example. A device is a feature of the Hebrew or Greek -- an acrostic is
    # invisible in English by definition, and a hendiadys is two words joined
    # by one conjunction, which the translation has usually already resolved
    # into a single English phrase. Served for every card rather than only the
    # device one: no card is worse for having the text beside the translation.
    mac = TO_MACULA.get(b, b)
    orig = [{"t": w.get("t"), "g": w.get("g"), "x": w.get("x")}
            for w in d["orig"].get(f"{mac}.{c}.{v}", [])
            if w.get("t") or w.get("g")]
    return {"ref": ref, "book": b, "title": TITLE.get(b, b),
            "chapter": c, "verse": v, "text": text, "found": bool(text),
            "vmarks": verse_marks(b, c, v),
            "orig": orig, "rtl": mac in HEBREW_BOOKS}


RANGE_MAX = 30                 # verses joined for one range citation
_SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _verse_range(d, ref, rm):
    """api_verse for "Matt 10:1-4" or "Gen 1:28-2:3": the verses in order,
    each led by its number in superscript, at most RANGE_MAX."""
    mb, c1, v1 = rm.group(1), int(rm.group(2)), int(rm.group(3))
    c2 = int(rm.group(4)) if rm.group(4) else c1
    v2 = int(rm.group(5))
    b = MACULA_BACK.get(mb, TITLE_BACK.get(mb, mb))
    if b not in d["chapters"]:
        b = book_of(mb) or b
    parts, c, v = [], c1, v1
    while (c, v) <= (c2, v2) and len(parts) < RANGE_MAX:
        t = d["verses"].get((b, c, v))
        if t:
            label = (f"{c}:{v}" if c != c1 else str(v)).translate(_SUP)
            parts.append(f"{label} {t}")
            v += 1
        elif d["verses"].get((b, c + 1, 1)) and c < c2:
            c, v = c + 1, 1            # the chapter ended; the range goes on
        else:
            break
    more = (c, v) <= (c2, v2) and len(parts) >= RANGE_MAX
    text = " ".join(parts) + (" …" if more else "")
    mac = TO_MACULA.get(b, b)
    return {"ref": ref, "book": b, "title": TITLE.get(b, b), "chapter": c1, "verse": v1,
            "text": text, "found": bool(parts), "orig": [], "rtl": mac in HEBREW_BOOKS,
            "range": True}


def api_query(d, q):
    """A deterministic slot query — no model, no parsing, no empty results.

    Twice asked for: some type of deterministic, but super intuitive
    query interface that those wanting to deep dive could use without invoking
    an LLM. This is its first cut, and the shape is the important part: you
    are not composing a query language, you are **narrowing a sentence**.

        [ anyone ]  [ any action ]  [ anything ]

    Every option offered is one that exists, with the count beside it, so a
    query can never come back empty -- the empty ones were never on the menu.
    It runs on the harvested patterns, which already hold every template with
    its slot fillers and its verses, so an answer is a lookup rather than a
    search and costs nothing to serve.
    """
    verb = (q.get("verb") or [""])[0].strip().lower()
    slot = (q.get("filler") or [""])[0].strip().lower()
    rows = []
    for r_ in d["patterns"].values():
        tmpl = r_["template"]
        if verb and verb not in tmpl.lower():
            continue
        fills = []
        for s_, f in (r_.get("slots") or {}).items():
            for w, n in f.items():
                if slot and slot not in w:
                    continue
                fills.append({"slot": s_, "word": w, "count": n})
        if slot and not fills:
            continue
        fills.sort(key=lambda x: -x["count"])
        rows.append({"key": r_["key"], "template": tmpl,
                     "instances": r_["instances"], "kind": r_["kind"],
                     "reach": r_["reach"], "first": r_.get("first"),
                     "fills": fills[:6]})
    rows.sort(key=lambda x: -x["instances"])
    return {"verb": verb, "filler": slot, "total": len(rows),
            "results": rows[:40]}


def api_collections(d, q):
    """What is in here, as CONTENT rather than as a feature list.

    The verdict on the earlier explorer: beautiful but really limited -- a
    reader could not even figure out how to search for a scripture. The failure was discoverability: one
    search box and no way to see what the app holds. Tabs would have fixed it
    by adding modes, which is what made the previous explorer sprawl.

    So this is a menu of THINGS TO LOOK AT, not of capabilities, and it opens
    as a card like everything else — the stack keeps working, and no mode is
    ever entered.
    """
    words = sorted(d["profiles"].values(),
                   key=lambda p: -(p.get("observations") or 0))
    # RANK BY HOW OFTEN THEY ACTUALLY APPEAR. 2026-09-16: Elihu
    # (or Elijah) was ranked right after Paul, Esau before Abraham,
    # and Moses sandwiched between Jesse and Anak.
    #
    # The list was sorted by `len(refs)` on the entity record, which counts the
    # citations the extraction attached to that entity's description -- not how
    # much of the Bible the person is in. Measured against the people
    # cross-reference layer, the order was close to meaningless:
    #
    #     ranked 5th   Elihu   11 verses   (and the wrong Elihu: "son of Tohu")
    #     ranked 12th  Anak     1 verse
    #     ranked 11th  Moses  784 verses
    #     ranked  7th  Abraham 159 verses
    #
    # `people-xref` counts the verses a name is actually in, so it is the
    # measure a reader means by "who is in this Bible most".
    # THE HUB RANKING, WHICH ALREADY EXISTED. 2026-09-16: the node explorer
    # of the old app had a really good weighted formula, still
    # sitting on port 8000.
    #
    # It is `src/bibleont/hubs.py` -- closure x reach x narratives: is my
    # neighbourhood real, does it open out, and am I spoken of in more than one
    # story. That module's own record of what was tried first is the argument
    # for it: degree alone puts a roster of eighty-four men fourth, and two-hop
    # reach alone puts Bethlehem above Moses because its few neighbours are
    # David and Jesus -- true, and a strange thing to head a list of hubs.
    #
    # Verse count, which this list used for about an hour, is better than the
    # `refs` length it replaced and still wrong in its own way: it put Judah
    # second, counting the tribe and the man as one, and cannot see that a
    # person matters by whom they connect.
    #
    # Precomputed by tools/hubrank.py into out/hubs.json, because survey()
    # takes minutes over the current graph and Explore is built on every load.
    verses_in = _person_verses(d)
    hub = d.get("hubscore") or {}
    people = [e for e in d["ents"].values() if e["type"] == "person"
              and len(e.get("refs") or []) > 4]

    def prominence(e):
        s = hub.get(e["id"])
        if s is not None:
            return (2, s)
        # Ranked below anyone the hub ranking scored, rather than interleaved
        # on a number that means something else.
        n = _person_count(verses_in, e)
        return (1, n) if n is not None else (0, len(e.get("refs") or []))

    people.sort(key=prominence, reverse=True)
    pairs = collections.Counter()
    seen = set()
    for lst in d["contrasts"].values():
        for c in lst:
            k = (c["a"], c["b"])
            if k not in seen and c.get("kind") == "contrast":
                seen.add(k)
                pairs[k] = c["count"]
    # CONSTRAINED, NOT COMMON. 2026-09-15: Explore started out very
    # uninteresting, with the most common (and obvious) patterns inside a sentence.
    #
    # Sorting by `instances` puts grammar on the front page -- "[S] said"
    # 2,859x, "son of [X]" 1,047x -- which is true, obvious, and says nothing
    # about this corpus. `tools/nodepat.py` measured the same thing one layer
    # down and the fix is the same: a template is interesting when its SLOTS
    # ARE CONSTRAINED. "[S] said" takes 402 different subjects; "aroma of [X]"
    # takes one, and that one is "pleasing".
    #
    # Skew alone over-rewards small formulas, so it is weighted by volume --
    # which keeps "[S] says" (601x, subject is "lord" 404 times), the messenger
    # formula, near the top where it belongs. `lift` is deliberately NOT used:
    # its values here run to 171,333 on 18 instances and the fillers behind
    # those are junk.
    #
    # What the ordering now surfaces first, none of which frequency showed:
    #
    #     declares of [X]      364x  [X] "lord" 335       the prophetic formula
    #     lord of [X]          224x  [X] "hosts" 208
    #     tent of [X]          123x  [X] "meeting" 103
    #     [S] slept with [X]    39x  [X] "fathers" 36     the regnal death notice
    #     [S] mixed with [X]    41x  [X] "oil" 37         the grain offering
    #     aroma of [X]          36x  [X] "pleasing" 36
    pats = [r for r in d["patterns"].values()
            if r.get("instances", 0) >= 8 and r.get("reach", 0) >= 3]
    pats.sort(key=lambda r: -((r.get("skew") or 0)
                              * math.log10(max(r.get("instances", 1), 10))))
    return {
        # As above: count the filtered set the items come from, not every
        # pattern on disk.
        "patterns": {"count": len(pats),
                     "note": "Ranked by how CONSTRAINED each slot is, not by "
                             "how often the shape occurs. The commonest shapes "
                             "are grammar — “[S] said” takes 402 different "
                             "subjects and tells you nothing. These take "
                             "almost always the same one.",
                     "items": [{"key": r["key"], "title": r["template"],
                                "sub": _pat_sub(r)}
                               for r in pats[:24]]},
        "words": {"count": len(d["profiles"]),
                  "items": [{"key": p["key"], "title": p.get("gloss"),
                             "sub": f"{p.get('observations')} uses"}
                            for p in words[:24]]},
        "people": {"count": sum(1 for e in d["ents"].values()
                                if e["type"] == "person"),
                   # The count leads, so the ORDER is checkable rather than
                   # asserted -- the previous ranking looked arbitrary and was,
                   # and nothing on screen would have revealed it.
                   "items": [{"id": e["id"], "title": e["name"],
                              "sub": ((f"{_person_count(verses_in, e)} verses · ")
                                      if _person_count(verses_in, e) is not None
                                      else "")
                                     + (e.get("desc") or "")[:64]}
                             for e in people[:24]]},
        "contrasts": {"count": len(seen),
                      "items": [{"title": f"{a} / {b}", "sub": f"{n}×",
                                 "a": a, "b": b}
                                for (a, b), n in pairs.most_common(24)]},
    }


_STRUCTURE = None


def api_structure(d, q):
    """One verse's clauses and a node diagram per clause, for the reader's
    structure chip (2026-09-25). English numbering in, mapped to
    MACULA's inside tools/structure.py; the module keeps a per-chapter cache,
    so it is imported once rather than reloaded per request."""
    global _STRUCTURE
    if _STRUCTURE is None:
        import importlib
        tdir = str(ROOT / "tools")
        if tdir not in sys.path:
            sys.path.insert(0, tdir)
        _STRUCTURE = importlib.import_module("structure")
    b = qbook(d, q)
    c = qchapter(d, q, b)
    v = qint(q, "v", 1)
    r = _STRUCTURE.verse(TO_MACULA.get(b, b), c, v)
    # the reader's book name, not MACULA's code ("John 3:16", not "Jhn");
    # and which original numbers the verse, now the graph holds the Greek
    r["english"] = f"{TITLE.get(b, b)} {c}:{v}"
    r["source_lang"] = "Hebrew" if TO_MACULA.get(b, b) in HEBREW_BOOKS \
        else "Greek"
    # WHAT EACH CLAUSE SPEAKS OF — a model's reading, shown as one.
    # 2026-09-28: these tags could be added to the structure expansions in
    # the reader, as they apply 1:1 (keyed by the same clause ids)
    tags = _clause_tags()
    for cl in r.get("clauses") or []:
        got = tags.get(cl.get("id"))
        if got:
            cl["tags"] = [t.as_dict() for t in got]
    return r


_UPPER = None


_THEME_MAP = None


def _theme_map():
    """out/theme-map.json (tools/themes/theme_map.py): Microsoft Copilot's
    major themes, parsed, each reference checked against the Berean text and
    each relationship marked grounded or not."""
    global _THEME_MAP
    if _THEME_MAP is None:
        p = OUT / "theme-map.json"
        # the outlines redone in the texts' words, before their owner has
        # approved them (plan 7.6c): only in the unreviewed preview
        pv = OUT / "theme-map-preview.json"
        if os.environ.get("BIBLEONT_SHOW_UNREVIEWED") == "1" and pv.exists():
            p = pv
        _THEME_MAP = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"themes": []}
        # THE SITE'S OWN THEMES WAIT FOR THEIR OWNER (plan 7.6b, 2026-10-07):
        # one of the four is shown only once theme-homes.json lists it in
        # "site_shown"; until then it is in no list, no verse's marks and no
        # page (the preview, BIBLEONT_SHOW_UNREVIEWED=1, shows it)
        shown = set(_theme_homes().get("site_shown") or [])
        if not os.environ.get("BIBLEONT_SHOW_UNREVIEWED"):
            hide = {t["id"] for t in _THEME_MAP["themes"]
                    if t.get("source") == "site" and t["id"] not in shown}
            if hide:
                _THEME_MAP["themes"] = [t for t in _THEME_MAP["themes"] if t["id"] not in hide]
                _THEME_MAP["verses"] = {v: [m for m in ms if m[0] not in hide]
                                        for v, ms in (_THEME_MAP.get("verses") or {}).items()}
                _THEME_MAP["by_node"] = {n: [m for m in ms if m["theme"] not in hide]
                                         for n, ms in (_THEME_MAP.get("by_node") or {}).items()}
        _THEME_MAP["_by"] = {t["id"]: t for t in _THEME_MAP["themes"]}
        # each theme and concept's own node (tools/themes/theme_nodes.py): a
        # merged one is the existing node, the rest are the theme-map nodes
        kn = ROOT / "ontology" / "themes" / "theme-nodes.json"
        _THEME_MAP["_node"] = json.loads(kn.read_text(encoding="utf-8")) if kn.exists() else {}
    return _THEME_MAP


_THEME_HUBS = None
_IMAGERY = {}
NAME2CODE = {**{v.lower(): k for k, v in TITLE.items()}, "psalm": "Ps", "song of songs": "Song"}


def _named_ref(s):
    """"Daniel 7:9" / "Psalm 2:9" -> ("Dan", 7, 9); a chapter alone gives v None"""
    m = re.match(r"^\s*(.+?)\s+(\d+)(?::(\d+))?", s or "")
    code = NAME2CODE.get(m.group(1).lower()) if m else None
    return (code, int(m.group(2)), int(m.group(3)) if m.group(3) else None) if code else None


def _theme_hubs():
    """ontology/themes/theme-hubs.json: a theme's front page (plan 7.6b)"""
    global _THEME_HUBS
    if _THEME_HUBS is None:
        p = ROOT / "ontology" / "themes" / "theme-hubs.json"
        _THEME_HUBS = {k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items()
                       if not k.startswith("_")} if p.exists() else {}
    return _THEME_HUBS


def _imagery(tid):
    """a theme's imagery side by side (ontology/themes/<file>), shown only
    once the site's owner has seen it"""
    if tid not in _theme_hubs():
        # an unknown id is answered, never kept: storing its None let every
        # distinct ?id= grow this dict for good (the security review,
        # 2026-10-22)
        return None
    if tid not in _IMAGERY:
        hub = _theme_hubs().get(tid) or {}
        f = (hub.get("imagery") or {}).get("file")
        p = ROOT / "ontology" / "themes" / f if f else None
        t = json.loads(p.read_text(encoding="utf-8")) if p and p.exists() else None
        _IMAGERY[tid] = t if t and (t.get("reviewed_by_owner") or
                                    os.environ.get("BIBLEONT_SHOW_UNREVIEWED") == "1") else None
    return _IMAGERY[tid]


def _see_also(hub):
    """A ROW THAT LIVES ON ANOTHER THEME'S TABLE (one home each), linked from
    this front page: Law / Wisdom's bridge to "The fear of the LORD is the
    beginning of wisdom" on Wisdom's table (2026-10-07). A link only
    where that table is shown, and only to a row that is there."""
    out = []
    for s in hub.get("see_also") or []:
        # or a card: Spiritual Warfare "hinges on Ephesians 6, which also has
        # its own Armor of God page" (2026-10-07)
        if s.get("card"):
            d = load()
            e = d["ents"].get(s["card"])
            if e:
                # with "door" it is drawn as a door beside the theme's heart, not
                # a hint (2026-10-07: Spiritual Warfare needs to link to
                # this Armor of God card)
                out.append({"card": s["card"], "title": e.get("name") or s["card"],
                            "path": f"/e/{_addr(s['card'])}", "label": s.get("label") or "the card",
                            "door": s.get("door"), "blurb": s.get("blurb")})
            continue
        img = _imagery(s["theme"])
        rows = [r["title"] for r in (img or {}).get("rows") or []]
        if s["row"] in rows:
            out.append({"theme": s["theme"], "row": rows.index(s["row"]), "title": s["row"],
                        "door": _theme_hubs()[s["theme"]]["imagery"]["door"], "path": _side_path(s["theme"])})
    return out


def _bridged_concepts(tid, hub):
    """The bridge the other way (ontology/concept-theme-bridges.json): the concept a theme is named for, as a door
    beside the theme's heart, as the Armor of God is on Spiritual Warfare. Doug, 2026-10-25: 'when the relationship
    is particularly close there should be a strong bridge to the theme'."""
    theme_bridges("")  # loads the list
    have = {s.get("card") for s in hub.get("see_also") or []}
    d = load()
    out = []
    for eid, tids in (_BRIDGES or {}).items():
        e = d["ents"].get(eid)
        if tid in tids and e and eid not in have:
            out.append({"card": eid, "title": e.get("name") or eid, "path": f"/e/{_addr(eid)}",
                        "label": "the concept", "door": "The concept",
                        "blurb": f"every verse where the text uses the word, by the forms it takes"})
    return out


def _hub(tid):
    """the front page's parts for the API: the opening, the door to the page
    it hinges on with its count, where a newcomer begins, the visions by
    chapter, and how many images each pair of books shares (the visual)"""
    hub = _theme_hubs().get(tid)
    if not hub:
        return None
    img = _imagery(tid)
    # A FRONT PAGE WAITS FOR ITS TABLE: the intro and the note are the site's
    # own words too, so a theme whose table the owner has not seen keeps its
    # old page (New Creation, 2026-10-06)
    if hub.get("imagery") and not img:
        return None
    rows = (img or {}).get("rows") or []
    idx = {r["title"]: k for k, r in enumerate(rows)}
    share = collections.Counter()
    for r in rows:
        cols = [c for c in (img or {}).get("columns", []) if r["cells"].get(c)]
        for i, a in enumerate(cols):
            for b in cols[i + 1:]:
                share[(a, b)] += 1
    return {"intro": hub.get("intro"), "note": hub.get("note"), "search_title": hub.get("search_title"),
            # the headings the page's sections carry (each theme's own words)
            "starters_label": hub.get("starters_label") or "New here? Begin with one",
            "starters_hint": hub.get("starters_hint") or "You do not need to take in all of it.",
            "chapters_label": hub.get("chapters_label") or "Chapter by chapter",
            "share_label": hub.get("share_label") or "How the sources share these",
            "opening": [{"ref": r, "words": w} for r, w in hub.get("opening") or []],
            "imagery": dict(hub["imagery"], n=len(rows), path=_side_path(tid)) if img else None,
            "starters": [{"title": s, "row": idx[s], "books": list(rows[idx[s]]["cells"])}
                         for s in hub.get("starters") or [] if s in idx],
            "visions": [{"label": c, "b": r[0], "c": r[1]} for c in hub.get("visions") or []
                        for r in [_named_ref(c)] if r],
            "see_also": _see_also(hub) + _bridged_concepts(tid, hub),
            "columns": (img or {}).get("columns") or [],
            "share": [{"a": a, "b": b, "n": n} for (a, b), n in share.items() if n >= 2]}


# A CELL OFF THE THEME, KEPT FOR ITS WORDS (2026-10-06, of Proverbs'
# "tree of life" in New Creation's table: asterisk it and note that
# it is off topic but included because of the shared imagery): a cell
# entry [verse, words, "aside"] is shown with an asterisk and this note
ASIDE_NOTE = "Off the theme's subject, and shown because it uses the same words."


_THEME_ADDR = None


def _theme_addr():
    """A THEME'S PUBLIC ADDRESS (plan 7.6d, 2026-10-08): /themes/<slug>, made
    once from its shown name (ontology/themes/theme-addresses.json,
    tools/themes/theme_addresses.py). 2026-10: the
    theme URLs moved to more standard forms, given that it was early,
    and the URL change was done first. Returns (id -> slug, slug -> id)."""
    global _THEME_ADDR
    if _THEME_ADDR is None:
        p = ROOT / "ontology" / "themes" / "theme-addresses.json"
        a = json.loads(p.read_text(encoding="utf-8"))["addresses"] if p.exists() else {}
        _THEME_ADDR = (a, {s: t for t, s in a.items()})
    return _THEME_ADDR


_BRIDGES = None


def theme_bridges(eid):
    """The themes a concept card opens prominently: Doug, 2026-10-25, 'when the relationship is particularly close
    there should be a strong bridge to the theme' ('wisdom and law are strong examples'). Listed by hand in
    ontology/concept-theme-bridges.json; each theme given with its title, subtitle and page."""
    global _BRIDGES
    if _BRIDGES is None:
        p = ROOT / "ontology" / "concept-theme-bridges.json"
        _BRIDGES = json.loads(p.read_text(encoding="utf-8")).get("bridges", {}) if p.exists() else {}
    out = []
    by = _theme_map().get("_by") or {}
    for tid in _BRIDGES.get(eid) or []:
        t = by.get(tid)
        if t:
            out.append({"id": tid, "title": _title(t.get("title") or tid), "subtitle": t.get("subtitle") or "",
                        "path": theme_path(tid)})
    return out


def theme_path(tid):
    """/themes/<slug>: every link, canonical and sitemap entry goes through
    here, so no route writes the old /theme/<id> form"""
    return f"/themes/{_theme_addr()[0].get(tid) or tid.replace('_', '-')}"


def theme_id(key):
    """a theme's id from its slug or its id (the API takes either)"""
    return _theme_addr()[1].get(key, key)


def _side_path(tid):
    """a theme's side-by-side table at its own address, the same ending for
    every theme (7.6d): /themes/apocalyptic/side-by-side. The endings before
    (imagery, taken-up, told-again, titles, sayings, blessed-and-sent; theme-
    hubs.json `slug`) answer 301 here (_old_theme_path)."""
    return theme_path(tid) + "/side-by-side"


def _old_theme_path(path):
    """/theme/<id> and /theme/<id>/<any ending> -> the new address, or None.
    The old addresses answer 301 while the search engines move over (P-99
    retires card redirects on evidence; these are kept the same way)."""
    tp = path[len("/theme/"):].strip("/ ")
    tid, _, sub = tp.partition("/")
    tid = theme_id(tid)
    if tid not in _theme_addr()[0]:
        return None
    return _side_path(tid) if sub else theme_path(tid)


def api_imagery(d, q):
    """A theme's imagery side by side (plan 7.6b): every row, its cells in
    the passages' own words, Alike and Different."""
    tid = theme_id((q.get("id") or [""])[0])          # the id or its address's slug
    img = _imagery(tid)
    if not img:
        return {"found": False}
    hub = _theme_hubs().get(tid) or {}
    tm = _theme_map()
    return {"found": True, "id": tid, "title": _title(tm["_by"][tid]["title"]) if tid in tm["_by"] else tid,
            "columns": img["columns"], "columns_note": img.get("columns_note"),
            "door": (hub.get("imagery") or {}).get("door") or "The imagery side by side",
            "aside_note": ASIDE_NOTE,
            "short": (hub.get("imagery") or {}).get("short") or {},
            "slug": _side_path(tid).rsplit("/", 1)[1], "path": _side_path(tid),
            "note": hub.get("note"), "starters": hub.get("starters") or [],
            "rows": [dict(r, n=k, cards=_row_cards(d, r)) for k, r in enumerate(img["rows"])]}


def _row_cards(d, row):
    """A ROW'S CARDS ON THE SAME SUBJECT, so a reader can turn from the
    side-by-side view to the imagery and concept cards (2026-10-07:
    there are imagery cards around the same topic, so the subject is covered
    from multiple angles). Named in the table file; a card is offered only
    where its own verses overlap the row's (tests/test_readings_text.py),
    so no link rests on a shared word alone. A card that is gone is
    dropped, never shown broken."""
    out = []
    for eid in row.get("cards") or []:
        eid = d["renamed"].get(eid, eid)
        e = d["ents"].get(eid)
        if not e:
            continue
        eid = e.get("alias_of") or eid
        e = d["ents"].get(eid) or e
        out.append({"id": eid, "name": e.get("name") or eid, "path": f"/e/{_addr(eid)}"})
    if out:
        return out
    # A ROW NOBODY NAMED CARDS FOR (2026-10-25: 704 of 705 rows linked nothing, so every side-by-side read to a
    # search engine as a wall of verses leading nowhere): the cards whose OWN references cite the row's verses --
    # written about those verses -- most of the row's verses first, five at most. The same test as the named ones,
    # a card's cited verse in the row (tests/test_readings_text.py), so none rests on a shared word.
    rowv = {_dot_ref(x[0]) for cs in (row.get("cells") or {}).values() for x in cs if not x[2:]}
    hits = collections.Counter(c for v in rowv if v for c in _cards_citing(d).get(v, ()))
    # one shared verse is enough only for a focused card (25 references or fewer: that verse is part of what it is
    # about); a broad word card needs two. First cut, one verse from any card, linked "Walking among them" to
    # "hear", "voice" and "wife" through Gen 3:8 among their dozens of references
    hits = {c: n for c, n in hits.items() if n >= 2 or len(d["ents"][c].get("refs") or []) <= 25}
    seen = set()  # two cards with one name (twins, e.g. "female") read as a repeat: the stronger one is shown
    for eid, _n in sorted(hits.items(), key=lambda kv: (-kv[1], (d["ents"][kv[0]].get("name") or kv[0]))):
        nm = d["ents"][eid].get("name") or eid
        if nm.lower() in seen:
            continue
        seen.add(nm.lower())
        out.append({"id": eid, "name": nm, "path": f"/e/{_addr(eid)}"})
        if len(out) == 5:
            break
    return out


_CARDS_CITING = None
_NOT_A_SEE_ALSO = re.compile(r"(_speech|_statement|_result|_condition|_messenger|^tell_|^stage_|^tpl|^msggroup|"
                             r"^theme_|_r\d+$|_c\d+$)")
_SEE_ALSO_KINDS = {"image", "concept", "object", "place", "person", "event", "group", "creature", "title",
                   "observance", "being"}


def _dot_ref(r):
    """"Exodus 25:8" (a table's cell) or "Exod 25:8" (a card's reference) as one verse key. _named_ref, which the
    verse links use, reads the full names the tables write but not the abbreviations most cards carry, so a card's
    reference is read by the project's parser first"""
    if not r:
        return None
    try:
        from bibleont.refs import parse_ref
        p = parse_ref(r)
        if p.start_verse:
            return f"{p.book}.{p.start_chapter}.{p.start_verse}"
    except Exception:
        pass
    n = _named_ref(r)
    return f"{n[0]}.{n[1]}.{n[2]}" if n and n[2] else None


def _cards_citing(d):
    """verse -> the cards whose own references cite it (cards a reader opens: not structural speech or telling
    records, not theme readings, not aliases)"""
    global _CARDS_CITING
    if _CARDS_CITING is None:
        idx = collections.defaultdict(set)
        for eid, e in d["ents"].items():
            if e.get("type") in _SEE_ALSO_KINDS and not e.get("alias_of") and not _NOT_A_SEE_ALSO.search(eid):
                for r in e.get("refs") or []:
                    k = _dot_ref(r)
                    if k:
                        idx[k].add(eid)
        _CARDS_CITING = idx
    return _CARDS_CITING


_QUESTIONS = None


def _questions():
    """QUESTION CARDS (plan 8.4h, 2026-10-25): "What does the Bible say about ...?", one card per question Christians
    genuinely disagree on, every reading with its own verses, credited to the traditions that hold it, none taken.
    ontology/questions/<id>.json; shown once the owner has read it (or in the preview, BIBLEONT_SHOW_UNREVIEWED)."""
    global _QUESTIONS
    if _QUESTIONS is None:
        qs = {}
        for p in sorted((ROOT / "ontology" / "questions").glob("*.json")):
            try:
                q = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if q.get("shown") or os.environ.get("BIBLEONT_SHOW_UNREVIEWED") == "1":
                qs[q["id"]] = q
        _QUESTIONS = qs
    return _QUESTIONS


def _question_related(d, q):
    """a question's themes and cards, each with its own address; one that does not exist is dropped"""
    tm = _theme_map().get("_by", {})
    themes = [{"id": t, "title": _title(tm[t]["title"]), "path": theme_path(t)}
              for t in (q.get("related") or {}).get("themes") or [] if t in tm]
    cards = []
    for c in (q.get("related") or {}).get("cards") or []:
        c = d["renamed"].get(c, c)
        e = d["ents"].get(c)
        if e:
            cid = e.get("alias_of") or c
            cards.append({"id": cid, "name": (d["ents"].get(cid) or e).get("name") or cid, "path": f"/e/{_addr(cid)}"})
    return themes, cards


# THE TRADITIONS (2026-10-26): what each tradition, church body and school of reading has itself written, in the
# graph (ontology/traditions/, built from the question cards by tools/traditions/build.py; bibleont.traditions
# checks it). Everything served here is derived from the cards that are SHOWN: a card that is not shown (and not
# previewed with BIBLEONT_SHOW_UNREVIEWED) contributes no tradition page, no document, no count and no line of About.
_TRAD_LAYER = None
_TRAD_MODEL = None


def _doc_id(title, url):
    """the layer's id for a document: one per distinct title and address (tools/traditions/build.py)"""
    import hashlib
    return "doc_" + hashlib.sha1(f"{title}|{url}".encode("utf-8")).hexdigest()[:10]


def _trad_layer():
    global _TRAD_LAYER
    if _TRAD_LAYER is None:
        base = ROOT / "ontology" / "traditions"
        _TRAD_LAYER = ({r["id"]: r for r in _rows(base / "nodes.jsonl")}, _rows(base / "edges.jsonl"))
    return _TRAD_LAYER


def _traditions():
    """slug -> the page of a tradition or school of reading, from shown cards only: its church bodies, its documents
    (each with its standing and outside link), and its positions question by question (each reading it states,
    with the documents that state it). A tradition no shown card reaches is not here, so it has no page."""
    global _TRAD_MODEL
    if _TRAD_MODEL is not None:
        return _TRAD_MODEL
    nodes, edges = _trad_layer()
    qs = _questions()
    qorder = {qid: i for i, qid in enumerate(qs)}
    qnode = {nid: n["attrs"]["id"] for nid, n in nodes.items()
             if n["type"] == "question" and n["attrs"].get("id") in qs}
    speaks, states = {}, {}
    for e in edges:
        if e["type"] == "speaks_on" and e["dst"] in qnode:
            speaks.setdefault(e["src"], {})[qnode[e["dst"]]] = e.get("note") or ""
        elif e["type"] == "states_reading":
            r = nodes.get(e["dst"])
            a = (r or {}).get("attrs") or {}
            if a.get("question") in qs and 1 <= a.get("index", 0) <= len(qs[a["question"]].get("readings") or []):
                states.setdefault(e["src"], set()).add((a["question"], a["index"]))
    model = {}
    for did, qmap in speaks.items():
        dn = nodes.get(did)
        if not dn:
            continue
        a = dn["attrs"]
        tn = nodes.get(a["tradition"])
        if not tn:
            continue
        t = tn["attrs"]
        m = model.setdefault(t["slug"], {"slug": t["slug"], "name": tn["name"], "level": t["level"],
                                         "order": t["order"], "path": f"/traditions/{t['slug']}",
                                         "docs": [], "positions": {}, "bodies": {}})
        bn = nodes.get(a.get("body") or "")
        info = {"id": did, "title": a["title"], "url": a["url"], "standing": a["standing"], "kind": a["kind"],
                "body": bn["name"] if bn else None, "body_slug": bn["attrs"]["slug"] if bn else None,
                "questions": sorted(qmap, key=lambda x: qorder[x])}
        m["docs"].append(info)
        for qid, says in qmap.items():
            m["positions"].setdefault(qid, {"readings": {}, "also": []})
            mine = sorted(i for (q2, i) in states.get(did, ()) if q2 == qid)
            for i in mine:
                m["positions"][qid]["readings"].setdefault(i, []).append(dict(info, says=says))
            if not mine:
                m["positions"][qid]["also"].append(dict(info, says=says))
    out = {}
    for slug, m in sorted(model.items(), key=lambda kv: (kv[1]["level"] == "school", kv[1]["order"], kv[1]["name"])):
        m["docs"].sort(key=lambda x: ((x["body"] or ""), qorder[x["questions"][0]], x["title"]))
        for x in m["docs"]:
            if x["body"]:
                m["bodies"][x["body"]] = m["bodies"].get(x["body"], 0) + 1
        pos = []
        for qid in sorted(m["positions"], key=lambda x: qorder[x]):
            card = qs[qid]
            p = m["positions"][qid]
            pos.append({"id": qid, "question": card.get("question"), "short": card.get("short") or qid,
                        "path": f"/questions/{qid}",
                        "readings": [{"index": i, "label": card["readings"][i - 1].get("label") or "",
                                      "path": f"/questions/{qid}#reading-{i}", "docs": ds}
                                     for i, ds in sorted(p["readings"].items())],
                        "also": p["also"]})
        m["positions"] = pos
        out[slug] = m
    _TRAD_MODEL = out
    return out


def _tradition_counts():
    """what About says: the traditions and documents of the SHOWN cards, counted"""
    ts = _traditions()
    docs = {x["id"] for m in ts.values() for x in m["docs"]}
    return {"traditions": sum(1 for m in ts.values() if m["level"] == "tradition"),
            "schools": sum(1 for m in ts.values() if m["level"] == "school"),
            "documents": len(docs),
            "bodies": len({(m["slug"], b) for m in ts.values() for b in m["bodies"]}),
            "questions": len({p["id"] for m in ts.values() for p in m["positions"]})} if ts else None


def _fr_enriched(item):
    """a card's further_reading, each source with the tradition page, standing and canonical body the layer gives it,
    and the sources grouped by tradition (the nine in the site's order, then the schools of reading)"""
    nodes, _edges = _trad_layer()
    ts = _traditions()
    fr = []
    for f in json.loads(json.dumps(item.get("further_reading") or [])):
        n = nodes.get(_doc_id(f.get("title"), f.get("url")))
        if n:
            a = n["attrs"]
            tn = nodes.get(a["tradition"]) or {}
            bn = nodes.get(a.get("body") or "")
            f["tname"], f["tlevel"] = tn.get("name") or f.get("tradition"), (tn.get("attrs") or {}).get("level")
            slug = (tn.get("attrs") or {}).get("slug")
            if slug in ts:
                f["tslug"], f["tpath"] = slug, f"/traditions/{slug}"
            f["bname"], f["standing"] = (bn["name"] if bn else None), a["standing"]
        else:
            f["tname"], f["bname"] = f.get("tradition"), f.get("body")
        fr.append(f)
    groups = {}
    for i, f in enumerate(fr):
        g = groups.setdefault(f.get("tslug") or f["tname"], {"slug": f.get("tslug"), "name": f["tname"],
                                                             "path": f.get("tpath"), "docs": [],
                                                             "school": f.get("tlevel") == "school"})
        g["docs"].append(i)
    order = {n: i for i, n in enumerate(["Catholic", "Eastern Orthodox", "Lutheran", "Reformed", "Anglican",
                                         "Wesleyan / Methodist", "Baptist / free church",
                                         "Pentecostal / Charismatic", "Anabaptist"])}
    return fr, sorted(groups.values(), key=lambda g: (g["school"], order.get(g["name"], 99)))


def api_question(d, q):
    qid = ((q.get("id") or [""])[0]).strip()
    item = _questions().get(qid)
    if not item:
        return {"found": False}
    themes, cards = _question_related(d, item)
    out = json.loads(json.dumps({k: v for k, v in item.items() if not k.startswith("_")}))

    def go(ps):          # each passage with the app's verse address, so its button opens the verse in place
        for p in ps or []:
            n = _named_ref(p.get("ref") or "")
            if n and n[2]:
                p["go"] = f"{n[0]}.{n[1]}.{n[2]}"
            # THE VERSES AROUND IT (2026-10-26, a seat for each tradition, then a judge: only where the quote alone
            # reads differently from the passage it sits in): the range's verses, text included, read in place
            m = re.match(r"^(.+?\s\d+):(\d+)(?:-(\d+))?$", (p.get("context") or "").strip())
            cn = _named_ref(m.group(1) + ":" + m.group(2)) if m else None
            if cn:
                p["context_verses"] = [{"go": f"{cn[0]}.{cn[1]}.{v}", "v": v,
                                        "text": _verse_text(d, f"{cn[0]}.{cn[1]}.{v}")[1]}
                                       for v in range(cn[2], int(m.group(3) or cn[2]) + 1)]
    go((out.get("agreed") or {}).get("passages"))
    for r in out.get("readings") or []:
        go(r.get("passages"))
    out["further_reading"], out["traditions"] = _fr_enriched(item)
    # nested questions (2026-10-26): the broader one this sits within, and the narrower ones within it
    _, within = _question_groups()
    qs = _questions()
    brief = lambda k: {"id": k, "question": qs[k].get("question"), "short": qs[k].get("short")}
    if within.get(qid):
        out["within"] = brief(within[qid])
    out["parts"] = [brief(k) for k, v in within.items() if v == qid]
    return {"found": True, **out, "themes": themes, "cards": cards, "path": f"/questions/{qid}"}


def _question_groups():
    """ontology/question-groups.json: the cards in a few groups, and the narrower questions nested in a broader one
    (2026-10-26). Only shown cards count: a group with none is left out, and a nested card whose parent is not
    shown stands on its own."""
    p = ROOT / "ontology" / "question-groups.json"
    g = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    shown = _questions()
    within = {k: v for k, v in (g.get("within") or {}).items() if k in shown and v in shown}
    groups = [{"name": x["name"], "questions": [k for k in x["questions"] if k in shown]} for x in g.get("groups") or []]
    placed = {k for x in groups for k in x["questions"]}
    rest = [k for k in shown if k not in placed]
    if rest:
        groups.append({"name": "Other questions", "questions": rest})
    return [x for x in groups if x["questions"]], within


def api_questions(d, q):
    groups, within = _question_groups()
    return {"questions": [{"id": k, "question": v.get("question"), "short": v.get("short"),
                           "path": f"/questions/{k}", "within": within.get(k)} for k, v in _questions().items()],
            "groups": groups}


def _doc_public(x):
    return {k: x.get(k) for k in ("id", "title", "url", "standing", "kind", "body", "says") if k in x}


def api_traditions(d, q):
    """the traditions and schools of reading that shown cards reach, with what each has to show"""
    return {"traditions": [{"slug": m["slug"], "name": m["name"], "level": m["level"], "path": m["path"],
                            "documents": len(m["docs"]), "questions": len(m["positions"]),
                            "bodies": sorted(m["bodies"])} for m in _traditions().values()],
            "path": "/traditions"}


def api_tradition(d, q):
    slug = ((q.get("id") or [""])[0]).strip()
    m = _traditions().get(slug)
    if not m:
        return {"found": False}
    return {"found": True, "slug": m["slug"], "name": m["name"], "level": m["level"], "path": m["path"],
            "bodies": [{"name": b, "documents": n} for b, n in sorted(m["bodies"].items())],
            "documents": [dict(_doc_public(x), questions=[
                {"id": qid, "short": _questions()[qid].get("short") or qid, "path": f"/questions/{qid}"}
                for qid in x["questions"]]) for x in m["docs"]],
            "positions": [dict(p, readings=[dict(r, docs=[_doc_public(x) for x in r["docs"]])
                                            for r in p["readings"]],
                              also=[_doc_public(x) for x in p["also"]]) for p in m["positions"]]}


def _trad_intro(m):
    n_d, n_q = len(m["docs"]), len(m["positions"])
    counts = f"{n_d} document{'s' if n_d != 1 else ''} on {n_q} question{'s' if n_q != 1 else ''}"
    if m["level"] == "school":
        return (f"A school of reading: readers who share a way of reading these texts, and whose reading no church's "
                f"own document states. This page gathers the scholars' works cited for it ({counts}), each set beside "
                f"the reading it states and the verses that reading rests on. They are the scholars' words, not this "
                f"site's claims, and the site takes none of them.")
    return (f"The {m['name']} tradition is one of nine this site sets side by side. This page gathers what it "
            f"has itself written on the questions the site sets out ({counts}), each set beside the reading it states "
            f"and the verses that reading rests on. They are the tradition's own statements, not this site's claims, "
            f"and the site takes none of them.")


def traditions_page(slug):
    """the page a search engine reads for a tradition or school of reading: its bodies, its documents with their
    standing and outside links, and its positions question by question, each linking back to the reading"""
    m = _traditions().get(slug)
    if not m:
        return None
    school = m["level"] == "school"
    title = f"{m['name']}: " + ("a school of reading, in its scholars' works" if school
                               else "the tradition's own statements")
    intro = _trad_intro(m)
    url = f"{SITE}/traditions/{slug}"
    head = (f"<title>{_esc(title)} · Bible Ontology</title>\n"
            f'<meta name="description" content="{_esc(intro[:300])}">\n'
            f'<link rel="canonical" href="{_esc(url)}">\n'
            f'<meta property="og:type" content="article">\n'
            f'<meta property="og:title" content="{_esc(title)}">\n'
            f'<meta property="og:description" content="{_esc(intro[:300])}">\n'
            f'<meta property="og:url" content="{_esc(url)}">\n')

    def doc(x, with_says=False):
        sub = [x["standing"]] + ([x["body"]] if x.get("body") else [])
        return (f'<a href="{_esc(x["url"])}" rel="noopener external">{_esc(x["title"])}</a> '
                f'<small>({_esc("; ".join(sub))}; outside link)</small>'
                + (f'<br><small>{_esc(x["says"])}</small>' if with_says and x.get("says") else ""))
    parts = []
    if m["bodies"]:
        parts.append("<h2>Church bodies</h2><p>" + "; ".join(
            f"{_esc(b)} ({n} document{'s' if n != 1 else ''})" for b, n in sorted(m["bodies"].items())) + "</p>")
    parts.append("<h2>Where it stands, question by question</h2>")
    for p in m["positions"]:
        parts.append(f'<h3><a href="{_esc(p["path"])}">{_esc(p["question"] or p["short"])}</a></h3><ul>')
        for r in p["readings"]:
            parts.append(f'<li><a href="{_esc(r["path"])}">{_esc(r["label"])}</a><ul>'
                         + "".join(f"<li>{doc(x, True)}</li>" for x in r["docs"]) + "</ul></li>")
        for x in p["also"]:
            parts.append(f"<li>Speaks on the question without stating one of its readings: {doc(x, True)}</li>")
        # the way to the other side (2026-10-26: "maybe the link back mentions across traditions or how
        # traditions differ"): the card sets every reading side by side, so this page need not list the others
        parts.append(f'</ul><p><a href="{_esc(p["path"])}">How the traditions differ on this question: every '
                     f"reading side by side, each with its own verses</a></p>")
    parts.append("<h2>Its documents</h2>")
    for body_name in dict.fromkeys(x["body"] for x in m["docs"]):
        parts.append((f"<h3>{_esc(body_name)}</h3>" if body_name else "") + "<ul>" + "".join(
            f"<li>{doc(x)}</li>" for x in m["docs"] if x["body"] == body_name) + "</ul>")
    any_school = any(x["level"] == "school" for x in _traditions().values())
    parts.append(f'<p><a href="/traditions">All the traditions{" and schools of reading" if any_school else ""}</a></p>')
    body = (f'<article id="ssr" class="ssr"><h1>{_esc(m["name"])}</h1>'
            f'<p class="ssr-sub">{"A school of reading" if school else "A tradition"} · its own words, '
            f'beside the verses they rest on</p><p>{_esc(intro)}</p>'
            + _open_btn(f"/traditions/{slug}", f"Open {m['name']} in Bible Ontology")
            + "".join(parts) + "</article>")
    return head, body, f"/traditions/{slug}"


def traditions_index_page():
    """/traditions: the traditions and schools of reading shown cards reach, or None when there are none"""
    ts = _traditions()
    if not ts:
        return None
    # schools of reading named only while one is listed (2026-10-27: every school came from held cards)
    any_school = any(m["level"] == "school" for m in ts.values())
    title = "Traditions and schools of reading" if any_school else "Traditions"
    works = " and the scholars' works" if any_school else ""
    desc = (f"What each of nine traditions{', and each school of reading,' if any_school else ''} has itself written "
            "on the questions the Bible is read on in more than one way, set beside the verses of the readings it "
            "states.")
    url = f"{SITE}/traditions"
    head = (f"<title>{_esc(title)} · Bible Ontology</title>\n"
            f'<meta name="description" content="{_esc(desc)}">\n'
            f'<link rel="canonical" href="{_esc(url)}">\n'
            f'<meta property="og:type" content="website">\n'
            f'<meta property="og:title" content="{_esc(title)}">\n'
            f'<meta property="og:description" content="{_esc(desc)}">\n'
            f'<meta property="og:url" content="{_esc(url)}">\n')

    def li(m):
        return (f'<li><a href="{_esc(m["path"])}">{_esc(m["name"])}</a> <small>({len(m["docs"])} documents on '
                f'{len(m["positions"])} question{"s" if len(m["positions"]) != 1 else ""})</small></li>')
    trad = [m for m in ts.values() if m["level"] == "tradition"]
    schools = [m for m in ts.values() if m["level"] == "school"]
    body = (f'<article id="ssr" class="ssr"><h1>{_esc(title)}</h1>'
            f'<p class="ssr-sub">Their own words, beside the verses they rest on</p><p>{_esc(desc)} They are the '
            f"traditions' statements{works}, not this site's claims.</p>"
            + _open_btn("/traditions", "Open the traditions in Bible Ontology")
            + (f"<h2>Traditions</h2><ul>{''.join(li(m) for m in trad)}</ul>" if trad else "")
            + (f"<h2>Schools of reading, in their scholars' works</h2><ul>{''.join(li(m) for m in schools)}</ul>"
               if schools else "") + "</article>")
    return head, body, "/traditions"


def _assumes_html(r):
    """What a reading starts from (2026-10-27): the other cards' readings it takes as given, each linked to its card,
    and a line on how it stands to them. The app draws the same line (index.html, assumes)."""
    items = " and ".join(f'<a href="/questions/{_esc(a["question"])}">{_esc(a["text"])}</a>' if a.get("question")
                         else _esc(a.get("text") or "") for a in r.get("assumes") or [])
    note = _esc(r.get("assumes_note") or "")
    if not items and not note:
        return ""
    return f'<p class="ssr-sub">{f"<b>Assumes</b> {items}. " if items else ""}{note}</p>'


def question_page(qid):
    """the page a search engine reads for a question card: the question as asked, what all agree on, each reading
    with its verses and who holds it, and the traditions' own words, each linking to its tradition's page"""
    d = load()
    item = _questions().get(qid)
    if not item:
        return None
    themes, cards = _question_related(d, item)
    title = item.get("question") or qid
    summary = (item.get("intro") or "")[:300]
    url = f"{SITE}/questions/{qid}"
    head = (f"<title>{_esc(title)} · Bible Ontology</title>\n"
            f'<meta name="description" content="{_esc(summary)}">\n'
            f'<link rel="canonical" href="{_esc(url)}">\n'
            f'<meta property="og:type" content="article">\n'
            f'<meta property="og:title" content="{_esc(title)}">\n'
            f'<meta property="og:description" content="{_esc(summary)}">\n'
            f'<meta property="og:url" content="{_esc(url)}">\n')

    def plist(ps):
        return "<ul>" + "".join(
            f'<li>{_ref_a(p.get("ref") or "")}: “{_esc(p.get("quote") or "")}”'
            + (f' <small>{_esc(p["note"])}</small>' if p.get("note") else "") + "</li>" for p in ps or []) + "</ul>"
    ag = item.get("agreed") or {}
    # the traditions' own statements are in the graph (ontology/traditions/): each source names its tradition,
    # linking to that tradition's page, and its document, linking outside
    fr, groups = _fr_enriched(item)

    def tlink(f):
        n = _esc(f.get("tname") or "")
        return f'<a href="{_esc(f["tpath"])}">{n}</a>' if f.get("tpath") else n

    def fr_name(f):
        return tlink(f) + (f" ({_esc(f['bname'])})" if f.get("bname") else "")

    def fr_link(f):
        k = f' <small>({_esc(f["standing"])}; outside link)</small>' if f.get("standing") else ""
        return (f'<a href="{_esc(f["url"])}" rel="noopener external">{_esc(f.get("title") or "")}</a>{k}'
                if f.get("url") else _esc(f.get("title") or "") + k)

    def own(r):
        srcs = [fr[i] for i in r.get("sources") or [] if isinstance(i, int) and i < len(fr)]
        return ("<p class=\"ssr-sub\">In its holders' own words: "
                + " · ".join(f"{fr_name(f)}, {fr_link(f)}" for f in srcs) + "</p>") if srcs else ""
    parts = []
    # nested questions (2026-10-26): the broader one this sits within, and the narrower ones within it
    _, within = _question_groups()
    qs = _questions()
    if within.get(qid):
        w = within[qid]
        parts.append(f'<p class="ssr-sub">Part of: <a href="/questions/{_esc(w)}">{_esc(qs[w].get("question") or w)}</a></p>')
    kids = [k for k, v in within.items() if v == qid]
    if kids:
        parts.append("<p class=\"ssr-sub\">Questions within this one: " + " · ".join(
            f'<a href="/questions/{_esc(k)}">{_esc(qs[k].get("question") or k)}</a>' for k in kids) + "</p>")
    if ag.get("summary") or ag.get("passages"):
        parts.append(f"<h2>What every reading agrees the text says</h2><p>{_esc(ag.get('summary') or '')}</p>"
                     + plist(ag.get("passages")))
    for i, r in enumerate(item.get("readings") or [], 1):
        parts.append(f'<h2 id="reading-{i}">{_esc(r.get("label") or "")}</h2>'
                     + (f"<p class=\"ssr-sub\">Held by: {_esc(', '.join(r.get('held_by') or []))}</p>"
                        if r.get("held_by") else "")
                     + _assumes_html(r)
                     + f"<p>{_esc(r.get('summary') or '')}</p>" + own(r) + plist(r.get("passages"))
                     + (f"<p>{_esc(r['answers'])}</p>" if r.get("answers") else ""))
    # IN THE TRADITIONS' OWN WORDS: part of the graph, grouped by tradition; the terms in a section of their own
    if fr:
        parts.append("<h2 id=\"traditions\">In the traditions' own words</h2>"
                     "<p class=\"ssr-sub\">What each tradition has itself written on this question, set beside the "
                     "verses of the readings it states. These are the traditions' statements, not this site's "
                     "claims. Each tradition's name opens its own page; each document's link goes to another "
                     "site.</p>")
        for heading, gs in (("", [g for g in groups if not g["school"]]),
                            ("Schools of reading, in their scholars' works", [g for g in groups if g["school"]])):
            if gs and heading:
                parts.append(f"<h2>{heading}</h2>")
            for g in gs:
                gn = (f'<a href="{_esc(g["path"])}">{_esc(g["name"])}</a>' if g["path"] else _esc(g["name"]))
                parts.append(f"<h3>{gn}</h3><ul>" + "".join(
                    f"<li>{fr_link(fr[i])}" + (f" <small>{_esc(fr[i]['bname'])}</small>" if fr[i].get("bname") else "")
                    + (f"<br><small>{_esc(fr[i]['says'])}</small>" if fr[i].get("says") else "") + "</li>"
                    for i in g["docs"]) + "</ul>")
    if item.get("terms"):
        parts.append("<h2 id=\"terms\">Terms the traditions use</h2><ul>" + "".join(
            f"<li><b>{_esc(t.get('term') or '')}</b>: {_esc(t.get('note') or '')}</li>" for t in item["terms"])
            + "</ul>")
    if themes or cards:
        parts.append("<h2>In the graph</h2><p>" + " · ".join(
            [f'<a href="{_esc(t["path"])}">{_esc(t["title"])}</a>' for t in themes]
            + [f'<a href="{_esc(c["path"])}">{_esc(c["name"])}</a>' for c in cards]) + "</p>")
    body = (f'<article id="ssr" class="ssr"><h1>{_esc(title)}</h1>'
            f'<p class="ssr-sub">A question the text is read on in more than one way · every reading shown, '
            f'none taken</p><p>{_esc(item.get("intro") or "")}</p>'
            + _open_btn(f"/questions/{qid}", "Open this question in Bible Ontology")
            + "".join(parts)
            + '<p><a href="/">Open Bible Ontology</a> to read every verse in place.</p></article>')
    return head, body, f"/questions/{qid}"


_THEME_HOMES = None


def _theme_homes():
    """ontology/themes/theme-homes.json: the five groups and each concept's
    home theme (plan 7.6b); a concept not listed stays where it was drawn"""
    global _THEME_HOMES
    if _THEME_HOMES is None:
        p = ROOT / "ontology" / "themes" / "theme-homes.json"
        _THEME_HOMES = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"groups": [], "concepts": {}}
    return _THEME_HOMES


def _theme_annotations():
    """ontology/themes/theme-annotations.json: readers' notes on themes,
    credited, with the passages they rest on."""
    p = ROOT / "ontology" / "themes" / "theme-annotations.json"
    if not p.exists():
        return {}
    # shown as "A reader's note": no one is named in the app outside About
    # (2026-10-01: no one is personally named or quoted in the app outside the
    # about page); the file keeps who wrote it
    return {k: dict(v, reader="A reader") if isinstance(v, dict) else v
            for k, v in json.loads(p.read_text(encoding="utf-8")).items()
            if not k.startswith("_")}


# Said about the TEXT, not the tools: the tools that drafted the map are named
# once, in About. 2026-09-30: AI helps generate things but ultimately
# everything is sourced in the Bible; the references to it had become a bit much.
# ...and said to BE a reading. The BibleProject reader (2026-10-02): "Eden as
# Proto-Temple" is a scholar's thesis, shown as if the text named it, while
# the comment that brought them said "without adding interpretation". "Mark
# theme readings" was chosen. Who drew the map stays in About.
# "resolved", not "checked": what is verified is that each reference names
# real verses in the Berean; the note beside a passage is the map's own
# (the 2026-10-02 evaluation found "checked" read as more than that)
# and from 2026-10-08 (plan 7.6c, "Quotations only") a note shows only where
# it is the text's own words; the outline is being redone in them
THEME_CREDIT = ("A reading: the major themes are a map drawn over the text, not the text's "
                "own headings (About says who drew it). Every passage a theme names is "
                "resolved against the Berean text, and a note beside one is shown only where "
                "it is the text's own words; this outline is being redone in them. "
                "Links between themes are shown with the scripture that grounds them.")
# the site's own four (plan 7.6b, 2026-10-07): an outline drafted from the texts
# for this site, in the texts' words, not the map's
SITE_THEME_CREDIT = ("This theme's outline is the site's own, added to the map: drafted from the "
                     "text, each concept named in the texts' words, every passage resolved against "
                     "the Berean text, and read by the panel of readers described in About. Links "
                     "between themes are shown with the scripture that grounds them.")
# a theme of the map whose outline the site has redone (plan 7.6c, 2026-10-08)
REDONE_THEME_CREDIT = ("The theme is from the major-theme map (About says who drew it); this outline "
                       "is the site's, redone from it in the texts' own words: each concept named as "
                       "its passages name it, every note a quotation, every passage resolved against "
                       "the Berean text, and read by the panel of readers described in About. Links "
                       "between themes are shown with the scripture that grounds them.")


def _title(s):
    """COPILOT'S CAPITALS to title case: 'WISDOM LITERATURE (POETIC THEOLOGY)'
    -> 'Wisdom Literature (Poetic Theology)', the bracket kept off the letter"""
    def cap(w, first):
        # a small word keeps lower case, except first ("The Law", 2026-10-07)
        if w.lstrip("(") in ("&", "of", "and", "the") and not first:
            return w        # "(the Trinity)" too
        i = next((k for k, ch in enumerate(w) if ch.isalpha()), 0)
        return w[:i] + w[i:].capitalize()
    return " ".join(cap(w, k == 0) for k, w in enumerate((s or "").lower().split()))


def api_majorthemes(d, q):
    """THE MAJOR THEMES, for Explore -- the top until 2026-10-04, now the last
    group under Patterns (the themes are no longer judged among the
    site's most impressive work). 2026-09-29: a quick
    way to detect, navigate to, and understand these major themes before
    diving into as much detail as desired."""
    tm = _theme_map()
    # FIRST ON EXPLORE AGAIN, in their five groups (2026-10-07: place
    # the themes first in the Explore page, explaining that these are topical
    # groupings for viewers to see related content grouped together); each
    # with its table, where shown
    by = tm["_by"]
    groups = [{"name": g["name"], "themes": [t for t in g["themes"] if t in by]}
              for g in _theme_homes().get("groups") or []]
    return {"credit": THEME_CREDIT, "source": tm.get("_source"), "groups": groups, "themes": [
        {"id": t["id"], "n": t["n"], "title": _title(t["title"]), "subtitle": t.get("subtitle"),
         "source": t.get("source") or "copilot",
         "door": (lambda h: {"title": h["imagery"]["door"], "n": h["imagery"]["n"], "path": h["imagery"]["path"]}
                  if h and h.get("imagery") else None)(_hub(t["id"])),
         "concepts": len(t["concepts"]),
         "passages": sum(len(p["refs"]) for c in t["concepts"] for p in c["passages"]),
         "links": len(t["links"]), "grounded": sum(1 for x in t["links"] if x["grounded"])}
        for t in tm["themes"]]}


def _passage_text(d, r):
    """A passage's Berean text: all of it up to three verses, else its first
    verse and an ellipsis; a whole book or long span shows none."""
    if not r.get("start"):
        return ""
    (c1, v1), (c2, v2) = r["start"], r["end"]
    b = r["book"]
    if c1 != c2 or v2 - v1 > 2:
        t = d["verses"].get((b, c1, v1)) or ""
        return (t + " …") if t else ""
    return " ".join(d["verses"].get((b, c1, v), "") for v in range(v1, v2 + 1)).strip()


def _span_text(d, r, cap=300):
    """a passage's whole Berean text (up to `cap` verses), for checking a note"""
    if not r.get("start"):
        return ""
    (c1, v1), (c2, v2), b, out = r["start"], r.get("end") or r["start"], r["book"], []
    for c in range(c1, c2 + 1):
        for v in range(v1 if c == c1 else 1, (v2 if c == c2 else 200) + 1):
            t = d["verses"].get((b, c, v))
            if t:
                out.append(t)
            if len(out) >= cap:
                return " ".join(out)
    return " ".join(out)


def _quoted_note(note, text):
    """True where every piece of a note (split at an ellipsis) is in the
    Berean text of its passages: '"And God said..."' is; 'light/dark' and
    'Christ as Melchizedekian priest' are not."""
    norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[‘’']", "'", s or "")).lower()  # noqa: E731
    body = norm(text)
    parts = [re.sub(r"^[\s\"“”'‘’,;:.—–-]+|[\s\"“”'‘’,;:.—–-]+$", "", x)
             for x in re.split(r"…|\.\.\.", note)]
    parts = [norm(x) for x in parts if len(x) >= 3]
    return bool(parts) and bool(body) and all(x in body for x in parts)


def api_majortheme(d, q):
    """One major theme: its core concepts with their passages (Berean text
    alongside), its secondary concepts, its links to other themes with what
    grounds each, and the ontology's own stamps it extends into."""
    tm = _theme_map()
    t = tm["_by"].get(theme_id((q.get("id") or [""])[0]))     # the id or its slug
    if not t:
        return {"found": False}
    # LITE: the passages without the headings' links, for _theme_tags. Those
    # links cost a search per term (about 700 for the twenty outlines), and
    # building the reader's tags through them made the first chapter after a
    # restart take 62 s (measured 2026-10-08; the load lagged after the
    # splash came down)
    lite = (q.get("lite") or [""])[0] == "1"

    def terms(name, nodes):
        return [] if lite else _name_terms(d, name, nodes, t["title"], t["id"])

    def passages(concepts, synthesis=False):
        out = []
        for c in concepts:
            ps = []
            for p in c["passages"]:
                refs = [dict(r, text=_passage_text(d, r),
                             go=(f"{TITLE.get(r['book'], r['book'])} {r['start'][0]}:"
                                 f"{r['start'][1]}" if r.get("start") else None))
                        for r in p["refs"]]
                # QUOTATIONS ONLY, UNTIL THE OUTLINE IS REDONE (plan 7.6c;
                # 2026-10-08, "Quotations only"): a Copilot note shows only
                # where it is the text's own words; its glosses ("Christ as
                # Melchizedekian priest") wait for the nine readers
                note = p.get("note")
                if note and t.get("source") != "site" and t.get("outline") != "redone" and not _quoted_note(
                        note, " ".join(_span_text(d, r) for r in p["refs"])):
                    note = None
                ps.append({"note": note, "label": p.get("label"), "group": p.get("group"), "refs": refs})
            # the synthesis's concepts are numbered on their own and have no
            # nodes of their own; a redone outline's concept opens a node only
            # once the nodes are rebuilt from it (a node still named for
            # Copilot's concept at that number is not this concept)
            node = None if synthesis else tm["_node"].get(f"{t['id']}:{c['n']}")
            if node and t.get("outline") == "redone" and not node.startswith("theme_"):
                pass                    # an existing card the sub-theme is (theme_nodes.py)
            elif node and t.get("outline") == "redone" and \
                    (d["ents"].get(node) or {}).get("name") != c["name"][:100]:
                node = None
            out.append({"n": c["n"], "name": c["name"], "grounded": c.get("grounded"),
                        "passages": ps, "nodes": c.get("nodes", []), "node": node,
                        # THE HEADING'S OWN WORDS LEAD INTO THE GRAPH (2026-10-08:
                        # don't lose track that this is a
                        # graph -- if concepts are mentioned in the outline
                        # headings, they should be hyperlinked for further
                        # exploration): each term the graph has a card for
                        "terms": _head_terms(d, terms(c["name"], c.get("nodes", [])))})
        return out

    def links(ls):
        by = tm["_by"]
        return [dict(x, to_title=_title(by[x["to"]]["title"]) if x.get("to") in by else x["to_label"],
                     shared=x.get("shared_passages", [])[:6])
                for x in ls]

    def secondary(ss):
        def keep(s):     # quotations only, as the concepts' notes (7.6c)
            return (not s.get("note") or t.get("source") == "site"
                    or _quoted_note(s["note"], " ".join(_span_text(d, r) for r in s.get("refs") or [])))
        return [dict(s, terms=terms(s["name"], s.get("nodes", [])),
                     note=s.get("note") if keep(s) else None)
                for s in ss]
    msgs_here = messages_in(d, None, theme=t["id"])
    acts_here = acts_in(d, None, theme=t["id"])

    # WHERE EACH CONCEPT BELONGS (plan 7.6b; ontology/themes/theme-homes.json).
    # Copilot's map is left as drawn; a concept whose home is another theme
    # leaves this page for a link, one whose home is this theme joins it
    # (said where it came from), and a sibling's concept that belongs here too
    # is linked. 2026-10-06: some overlap is ok, but strive to put
    # things in their logical place; each theme links to its group.
    homes = _theme_homes()
    def place(tid, n):
        # a concept moved to a theme not yet shown (one of the site's own,
        # waiting for its owner) stays where it was drawn until that theme is
        # The homes are keyed by Copilot's numbering: an outline redone in
        # the texts' words (7.6c) is drawn whole for its own theme, and its
        # concept n is not Copilot's concept n (New Creation's redone 4 and
        # 9 were being shown on Apocalyptic's page as Copilot's 4 and 9)
        if tm["_by"][tid].get("outline") == "redone":
            return {"home": tid, "also": []}
        p = homes["concepts"].get(f"{tid}:{n}") or {"home": tid, "also": []}
        # and a redone outline ends on its theme's own words of hope: a
        # Copilot concept placed there stays on its own page and is linked
        # from the redone one, not appended after that ending (New Creation)
        if p["home"] != tid and tm["_by"].get(p["home"], {}).get("outline") == "redone":
            p = {"home": tid, "also": [p["home"], *p.get("also", [])]}
        if p["home"] not in tm["_by"]:
            return {"home": tid, "also": [a for a in p.get("also", []) if a in tm["_by"] and a != tid]}
        return dict(p, also=[a for a in p.get("also", []) if a in tm["_by"]])
    own = [c for c in t["concepts"] if place(t["id"], c["n"])["home"] == t["id"]]
    moved_in, moved_out, also_here = [], [], []
    for x in tm["themes"]:
        for c in x["concepts"]:
            p = place(x["id"], c["n"])
            if x["id"] == t["id"] and p["home"] != t["id"]:
                moved_out.append({"name": c["name"], "home": p["home"], "home_title": _title(tm["_by"][p["home"]]["title"])})
            elif x["id"] != t["id"] and p["home"] == t["id"]:
                moved_in.append((x, c))
            elif x["id"] != t["id"] and t["id"] in p["also"]:
                also_here.append({"name": c["name"], "home": p["home"], "home_title": _title(tm["_by"][p["home"]]["title"])})
    concepts_here = passages(own)
    for x, c in moved_in:
        row = dict(passages([c])[0], node=tm["_node"].get(f"{x['id']}:{c['n']}"),
                   moved_from={"id": x["id"], "title": _title(x["title"])})
        concepts_here.append(row)
    for k, c in enumerate(concepts_here, 1):  # numbered as shown, not as drawn
        c["n"] = k
    group = next((g for g in homes["groups"] if t["id"] in g["themes"]), None)
    out = {"found": True, "id": t["id"], "path": theme_path(t["id"]), "n": t["n"], "title": _title(t["title"]),
           "group": {"name": group["name"], "themes": [{"id": g, "title": _title(tm["_by"][g]["title"])}
                                                       for g in group["themes"] if g in tm["_by"]]} if group else None,
           "moved_out": moved_out, "also_here": also_here,
           # a theme's front page, where one is built (plan 7.6b)
           "hub": _hub(t["id"]),
           "subtitle": t.get("subtitle"),
           "credit": SITE_THEME_CREDIT if t.get("source") == "site"
                     else REDONE_THEME_CREDIT if t.get("outline") == "redone" else THEME_CREDIT,
           "source": t.get("source") or "copilot",
           "outline": t.get("outline") or t.get("source") or "copilot",
           # its place among the themes shown, and how many (was "of 20")
           "pos": next(k for k, x in enumerate(tm["themes"], 1) if x["id"] == t["id"]),
           "count": len(tm["themes"]), "nodes": t.get("nodes", []),
           "node": tm["_node"].get("theme:" + t["id"]),
           # a reader's note on the theme (on Creation, 2026-09-29)
           "annotation": _theme_annotations().get(t["id"]),
           "concepts": concepts_here, "secondary": secondary(t["secondary"]),
           "messages": msgs_here, "acts": acts_here,
           "links": links(t["links"]),
           # "go deeper" to tag pages, the retired theme stamps left out (2026-10-08)
           "stamps": [s for s in t.get("stamps", []) if s.get("id") not in _theme_stamp_ids()],
           # the events that belong to it, each by its scripture (2026-09-29:
           # "Events to themes"): those Copilot also names the
           # theme for first, then by how many verses back the link -- raw
           # counts alone put "First return" first, because the theme cites
           # Ezra 2's 70-verse list of returnees
           "events": sorted(_events(d)["by_theme"].get(t["id"], []),
                            key=lambda x: (not x["listed"], -(x["n_cited"] + x["n_tagged"])))}
    if t.get("synthesis"):
        s = t["synthesis"]
        out["synthesis"] = {"title": _title(s["title"]), "subtitle": s.get("subtitle"),
                            "concepts": passages(s["concepts"], synthesis=True),
                            "secondary": secondary(s["secondary"]),
                            "links": links(s["links"])}
    return out


_JOIN = {"and", "or", "of", "the", "a", "an", "in", "to", "with", "for", "from", "on",
         "by", "as", "at", "into", "vs", "versus", "its", "his", "her", "their",
         "under", "over", "through", "within", "before", "after", "between", "among",
         "upon", "beyond", "about", "against", "toward", "towards", "without"}
_HITS = {}


_HEAD_PLAIN = set("they them their he him his she her it its we us our you your i me my all every "
                  "no not like old new first one many more own other such".split())
# cards named a heading's word in another sense: the birth-order firstborn,
# Rebekah's veil (Gen 24:65), the striking hand
_HEAD_NOT = {"firstborn", "vail", "stroke"}


def _head_terms(d, terms):
    """a sub-theme's heading, linked more strictly than an "also" name: a term
    opens a card only where the card is named that word (a plural or "-ed"
    aside), never a pronoun, quantifier or "like", and never a card a
    sub-theme is known not to mean (theme_nodes.NOT_THE_SAME). "mindful" does
    not open "mind", "They" does not open "the children of men"."""
    out = []
    for x in terms:
        if x.get("k") == "node":
            w = x["t"].lower().strip()
            nm = re.sub(r"^the ", "", ((d["ents"].get(x["id"]) or {}).get("name") or "").lower().strip())
            forms = {w, re.sub(r"s$", "", w), re.sub(r"e?d$", "", w), re.sub(r"ed$", "e", w)}
            if w in _HEAD_PLAIN or x["id"] in _HEAD_NOT or nm not in forms:
                x = {"t": x["t"], "k": "plain"}
        elif x.get("k") == "theme":
            # a theme only by its whole name: "wisdom" is not The Law, whose
            # map title is still "Law / Wisdom"
            t = (_theme_map().get("_by") or {}).get(x["id"]) or {}
            if x["t"].lower().strip() != _title(t.get("title") or "").lower().strip():
                x = {"t": x["t"], "k": "plain"}
        elif x.get("k") == "search":
            x = {"t": x["t"], "k": "plain"}
        out.append(x)
    return out


_NAME_TERMS: dict = {}


def _name_terms(d, name, nodes, theme_title, theme_id=None):
    """_name_terms_built, kept: a name's links never change while the server
    runs, and each costs searches (a theme page cold took seconds for them)"""
    key = (name, json.dumps(nodes or [], sort_keys=True), theme_title, theme_id)
    if key not in _NAME_TERMS:
        _NAME_TERMS[key] = _name_terms_built(d, name, nodes, theme_title, theme_id)
    return _NAME_TERMS[key]


def _name_terms_built(d, name, nodes, theme_title, theme_id=None):
    """A theme concept's name ("Creation and wisdom", "Covenant → New
    Creation", "Blessing embedded in creation") as terms, each linked as
    finely as it can be. 2026-09-30: "Creation and wisdom" was still
    one link that found nothing under search; it needed to parse and go more
    granular with the links.

    A run of content words is matched longest-first against: a major theme's
    title ("New Creation" is one term, not "New" + "Creation"), the terms the
    concept was matched to (its `nodes`), and an unambiguous node name. A
    word left over links to the search only if the search finds something
    for it -- a link that leads nowhere is worse than none. The theme's own
    words (you are on its card) and the joining words stay plain."""
    tm = _theme_map()
    # a theme answers to its whole title and to each part of a compound one:
    # "TEMPLE / PRESENCE" is the theme for "Presence", "LAW / WISDOM" for
    # "Wisdom" -- a major theme's page is the richest place a word can open
    # -- but NOT a parenthesis, which glosses the theme rather than naming it:
    # "APOCALYPTIC (REVELATION & UNVEILING)" had sent "Creation as revelation"
    # (the revelation in creation) to the Apocalypse
    themes = {}
    for x in tm.get("themes", []):
        themes.setdefault(_slug(_title(x["title"])), x["id"])
        for part in re.split(r"\s*[/&]\s*", re.sub(r"\(.*?\)", "", x["title"])):
            if part.strip():
                themes.setdefault(_slug(part), x["id"])
    # the node the concept was matched to; where several share a term, the
    # one whose own name IS the term ("land", not "lands")
    matched = {}
    for n in sorted(nodes or [], key=lambda n: _slug(n.get("name", "")) != _slug(n.get("matched", ""))):
        if n.get("matched"):
            matched.setdefault(_slug(n["matched"]), n["id"])
    own = {w.lower() for w in re.findall(r"[A-Za-z]+", _title(theme_title))}

    def hits(w):
        if w not in _HITS:
            try:
                _HITS[w] = bool(api_search(d, {"q": [w]}).get("results"))
            except Exception:                                   # noqa: BLE001
                _HITS[w] = False
        return _HITS[w]

    toks = re.findall(r"[A-Za-z’']+|[^A-Za-z’']+", name)
    out, i = [], 0
    while i < len(toks):
        tk = toks[i]
        if not re.match(r"[A-Za-z]", tk) or tk.lower() in _JOIN:
            out.append({"t": tk, "k": "plain"})
            i += 1
            continue
        # the longest run of content words from here that names something
        run = [i]
        j = i + 1
        while j + 1 < len(toks) and toks[j].strip() == "" and re.match(r"[A-Za-z]", toks[j + 1]) \
                and toks[j + 1].lower() not in _JOIN:
            run.append(j + 1)
            j += 2
        done = False
        for end in range(len(run), 1, -1):
            text = "".join(toks[run[0]:run[end - 1] + 1])
            key = _slug(text)
            if key in themes:
                # the card's own theme is where you are: plain
                out.append({"t": text, "k": "plain"} if themes[key] == theme_id
                           else {"t": text, "k": "theme", "id": themes[key]})
            elif key in matched:
                out.append({"t": text, "k": "node", "id": matched[key]})
            else:
                continue
            i = run[end - 1] + 1
            done = True
            break
        if done:
            continue
        w, key = tk, _slug(tk)
        ids = list(d["alias_ix"].get(key, ()))
        if w.lower() in own:
            out.append({"t": w, "k": "plain"})
        elif key in themes and themes[key] != theme_id:
            out.append({"t": w, "k": "theme", "id": themes[key]})
        elif key in matched:
            out.append({"t": w, "k": "node", "id": matched[key]})
        elif len(ids) == 1 or key in ids:
            # one node by that name; or, among several, the one whose id IS
            # the word ("God" -> god, not a search)
            out.append({"t": w, "k": "node", "id": key if key in ids else ids[0]})
        elif hits(w):
            out.append({"t": w, "k": "search"})
        else:
            out.append({"t": w, "k": "plain"})
        i += 1
    return out


def _theme_stamp_ids():
    """the theme ids of the September taxonomy's "themes" category, whose
    stamps (section and clause) are retired from view (2026-10-08)"""
    p = ROOT / "ontology" / "interest-taxonomy.json"
    try:
        items = json.loads(p.read_text(encoding="utf-8"))["themes"]["items"]
    except (OSError, ValueError, KeyError):
        return set()
    return {x["id"] for x in items if isinstance(x, dict) and x.get("id")}


_THEME_TAGS = None
# WHICH OF A THEME'S PAGES TAG THE TEXT. 2026-10-08: "The curated
# parts" was chosen: the tables, the quotations and the chapters singled out, drafted and
# reviewed with the front pages. The outline's concepts and "also" passages
# wait for the front-page audit (taken whole they tagged 15,246 verses, 49%,
# with brackets round Job 3-37), and join here as each part passes.
# "event" is not a kind that tags: tagging every verse of an event the theme
# cites took the reader from 11,047 tagged verses to 18,201 (2026-10-08),
# Exodus 20 to 16 theme brackets and Acts 2 to 14, because a theme lists an
# event if it cites one verse of it ("Revelation judgments" went to 17
# themes). "Panel only" was chosen: an event is named on a verse the theme
# already tags (put()), adding context, never a theme.
THEME_TAG_KINDS = {"row", "quote", "chapter"}


def _theme_tags():
    """-> {(book, chapter, verse): [{theme, n, title, kind, row, label, node}]}:
    the verses each theme's own pages point to, for the reader's brackets,
    its section chips and a verse's "In the themes".

    THE THEMES AS THEY NOW ARE, NOT AS THEY WERE MAPPED (2026-10-08:
    the Themes had been redefined and added to, so the existing tags were not
    trusted; the verses are tagged from what the theme itself references,
    and "The tables" was chosen). Then, the same
    day: verses on the front pages of the themes count too -- there are many
    references in the Core Concepts, and leaving those out is
    not being comprehensive; "In the texts' own words" are verses that are
    highlighted, and chapters are singled out. So every verse a shown
    theme's pages point to, read from the page's own answer (api_majortheme,
    after the concepts' moves between themes), by kind:

      row      a cell of the table (an aside -- shown only for its shared
               words, off the theme's subject -- left out); opens the row
      quote    "In the texts' own words" on the front page
      concept  a core concept's passage; opens the concept's card
      also     an "Also in this theme" passage
      chapter  a chapter the front page singles out, the whole of it
      event    an event on the page the theme's passages cite, named on the
               verses of its telling that the theme already tags (2026-10-08:
               "the full theme pages in their current states"; "Panel only")

    Before the first change the brackets were every passage the outline
    cited (3,908 verses, 1,697 of them in the tables' 5,543)."""
    global _THEME_TAGS
    if _THEME_TAGS is not None:
        return _THEME_TAGS
    d = load()
    maxv = collections.defaultdict(int)
    for (b, c, v) in d["verses"]:
        maxv[(b, c)] = max(maxv[(b, c)], v)
    ix = collections.defaultdict(list)
    checked_outlines = {t["id"] for t in _theme_map().get("themes", [])
                        if t.get("source") == "site" or t.get("outline") == "redone"}

    def put(b, c, v1, v2, entry):
        # an outline that has passed the readers tags the text too (plan 7.6c:
        # "A part that passes joins the reader's theme tags"): the site's own
        # four (7.6b) and each redone one once approved
        if entry["kind"] not in THEME_TAG_KINDS and entry["kind"] != "event" and not (
                entry["kind"] in ("concept", "also") and entry["theme"] in checked_outlines):
            return
        for vv in range(v1, min(v2, maxv.get((b, c), v2)) + 1):
            # AN EVENT NAMES ITSELF, IT ADDS NO THEME (2026-10-08,
            # choosing "Panel only"): only on a verse this theme already tags
            # by its own pages; so no bracket, and no verse, comes from it
            # (read with .get: indexing the defaultdict would make an empty
            # entry for every verse skipped)
            if entry["kind"] == "event" and not any(
                    x["theme"] == entry["theme"] and x["kind"] != "event"
                    for x in ix.get((b, c, vv), ())):
                continue
            here = ix[(b, c, vv)]
            if not any(x["theme"] == entry["theme"] and x["kind"] == entry["kind"]
                       and x["label"] == entry["label"] for x in here):
                here.append(entry)

    def put_ref(r, entry):
        """a theme map reference {book, start, end}: across chapters if it runs on"""
        if not r.get("start"):
            return
        b, (c1, v1), (c2, v2) = r["book"], r["start"], r.get("end") or r["start"]
        for c in range(c1, c2 + 1):
            put(b, c, v1 if c == c1 else 1, v2 if c == c2 else maxv.get((b, c), 999), entry)

    def put_named(s, entry):
        nr = _named_ref(s)
        if not nr:
            return
        m = re.search(r"[-–](\d+)$", s or "")
        if nr[2] is None:                                  # a whole chapter
            put(nr[0], nr[1], 1, maxv.get((nr[0], nr[1]), 999), entry)
        else:
            put(nr[0], nr[1], nr[2], int(m.group(1)) if m and ":" in s else nr[2], entry)

    for t in _theme_map().get("themes", []):
        tid = t["id"]
        page = api_majortheme(d, {"id": [tid], "lite": ["1"]})      # passages only
        if not page.get("found"):
            continue
        base = {"theme": tid, "n": t["n"], "title": _title(t["title"]), "row": None, "node": None}
        for i, row in enumerate((_imagery(tid) or {}).get("rows") or []):
            for cells in (row.get("cells") or {}).values():
                for cell in cells:
                    if not (len(cell) > 2 and cell[2] == "aside"):
                        put_named(cell[0], dict(base, kind="row", row=i, label=row.get("title") or ""))
        hub = page.get("hub") or {}
        for o in hub.get("opening") or []:
            put_named(o.get("ref") if isinstance(o, dict) else o[0], dict(base, kind="quote", label=""))
        for blk in [page] + ([page["synthesis"]] if page.get("synthesis") else []):
            for con in blk.get("concepts") or []:
                for p in con.get("passages") or []:
                    for r in p.get("refs") or []:
                        put_ref(r, dict(base, kind="concept", label=con.get("name") or "",
                                        node=con.get("node")))
            for sec in blk.get("secondary") or []:
                for r in sec.get("refs") or []:
                    put_ref(r, dict(base, kind="also", label=sec.get("name") or ""))
        for ch in hub.get("visions") or []:
            put(ch["b"], ch["c"], 1, maxv.get((ch["b"], ch["c"]), 999),
                dict(base, kind="chapter", label=ch.get("label") or ""))
        # THE EVENTS ON THE PAGE (2026-10-08: make sure the reader
        # verse theme tagging includes the full theme pages in their current
        # states), named on the verses of each telling the theme already
        # tags -- put() keeps them off any other verse ("Panel only"). Only an
        # event the theme's own passages cite: one joined by Copilot's list or
        # the retired stamps alone waits for 7.6c's check of the events.
        evs = _events(d)["events"]
        for x in page.get("events") or []:
            if not x.get("n_cited"):
                continue
            for tl in (evs.get(x["id"]) or {}).get("tellings") or []:
                try:
                    fb, fc, fv = bsb_ref(d, tl["first"]).split(".")
                    _lb, lc, lv = bsb_ref(d, tl["last"]).split(".")
                except (ValueError, KeyError, AttributeError):
                    continue
                put_ref({"book": MACULA_BACK.get(fb, fb), "start": [int(fc), int(fv)],
                         "end": [int(lc), int(lv)]},
                        dict(base, kind="event", label=x["title"], node=x["id"]))
    _THEME_TAGS = ix
    return ix


def _theme_marks(es):
    """one theme's marks on a verse or a run of verses: its table rows, core
    concepts, "also" items and chapters, each once, in that order"""
    rows, cons, also, chap, quote, evs = [], [], [], [], False, []
    for x in es:
        if x["kind"] == "event" and [x["node"], x["label"]] not in evs:
            evs.append([x["node"], x["label"]])
        if x["kind"] == "row" and [x["row"], x["label"]] not in rows:
            rows.append([x["row"], x["label"]])
        elif x["kind"] == "concept" and [x["node"], x["label"]] not in cons:
            cons.append([x["node"], x["label"]])
        elif x["kind"] == "also" and x["label"] not in also:
            also.append(x["label"])
        elif x["kind"] == "chapter" and x["label"] not in chap:
            chap.append(x["label"])
        elif x["kind"] == "quote":
            quote = True
    return {"rows": rows, "concepts": cons, "also": also, "chapters": chap, "quoted": quote,
            "events": evs}


def themes_for(d, ref):
    """The themes whose own pages point to this verse (MACULA ref): the table
    rows it stands in, the concepts that cite it, a chapter singled out."""
    e = bsb_ref(d, ref)
    try:
        b, c, v = e.split(".")
    except ValueError:
        return []
    by = collections.defaultdict(list)
    for x in _theme_tags().get((MACULA_BACK.get(b, b), int(c), int(v)), []):
        by[x["theme"]].append(x)
    return sorted(({"theme": tid, "title": es[0]["title"], **_theme_marks(es)} for tid, es in by.items()),
                  key=lambda x: x["title"])


_STORY_IX = None


def story_spans(b, c):
    """The story-pattern stages in one chapter (Berean book and numbering),
    for the reader. 2026-09-30: in the reader, the common patterns are
    called out so that other instances of the pattern can be seen. Each stage clipped to the chapter: its pattern, the stage, and
    the story it belongs to."""
    global _STORY_IX
    if _STORY_IX is None:
        ix = collections.defaultdict(list)
        seen = set()
        for insts in (_templates().get("by_node") or {}).values():
            for i in insts:
                if i.get("via_arc"):
                    continue
                for s in i["stages"]:
                    if s["id"] in seen:
                        continue
                    seen.add(s["id"])
                    for f, t in s.get("runs") or []:
                        fb, fc, fv = f.split(".")
                        _tb, tc, tv = t.split(".")
                        for ch in range(int(fc), int(tc) + 1):
                            ix[(fb, ch)].append({
                                "from": int(fv) if ch == int(fc) else 1,
                                "to": int(tv) if ch == int(tc) else 999,
                                "family": i["family"], "family_name": i["family_name"],
                                "pattern_id": "tpl_" + i["family"], "kind": "story",
                                "stage": s["name"], "instance": i["instance"],
                                "title": i["arc"] or i["title"],
                                "starts": ch == int(fc)})
        # ROLE PATTERNS TOO (plan A.10), but only a cell whose verses use the
        # part's own word -- a reading does not go on the text
        for pid, p in (_roles().get("patterns") or {}).items():
            for r in p["rows"]:
                for slot, cs in r["cells"].items():
                    for cell in cs:
                        if cell["reading"]:
                            continue
                        for f, t in cell.get("runs") or []:
                            fb, fc, fv = f.split(".")
                            _tb, tc, tv = t.split(".")
                            for ch in range(int(fc), int(tc) + 1):
                                ix[(fb, ch)].append({
                                    "from": int(fv) if ch == int(fc) else 1,
                                    "to": int(tv) if ch == int(tc) else 999,
                                    "family": pid, "family_name": p["name"],
                                    "pattern_id": p["id"], "kind": "role",
                                    "stage": slot.lower(), "instance": r["id"],
                                    "title": r["name"], "starts": ch == int(fc)})
        _STORY_IX = ix
    return sorted(_STORY_IX.get((b, c), []), key=lambda x: (x["from"], x["to"]))


def theme_spans(b, c, verses):
    """The major-theme passages in one chapter (Berean book and numbering),
    for the reader's brackets: each theme's verses in the chapter, one
    bracket per theme and run, carrying the table rows they stand in.
    2026-09-29: in the viewer these themes can rise to the section they
    cover, with brackets around the passage in the same
    color. A bare book ("Psalms") brackets nothing."""
    # FROM THE THEMES' TABLES (2026-10-08, _theme_tags): one bracket per
    # theme per run of consecutive verses it sets out, carrying the rows
    # those verses stand in; a tap opens the table at the first of them
    if not verses:
        return []
    ix = _theme_tags()
    per = collections.defaultdict(dict)          # theme -> verse -> [entries]
    for v in sorted(set(verses)):
        for x in ix.get((b, c, v), []):
            per[x["theme"]].setdefault(v, []).append(x)
    out = []
    for tid, byv in per.items():
        vs = sorted(byv)
        runs, cur = [], [vs[0]]
        for v in vs[1:]:
            if v == cur[-1] + 1:
                cur.append(v)
            else:
                runs.append(cur); cur = [v]
        runs.append(cur)
        for run in runs:
            es = [x for v in run for x in byv[v]]
            mk = _theme_marks(es)
            f, to = run[0], run[-1]
            out.append({"theme": tid, "n": es[0]["n"], "title": es[0]["title"], "from": f, "to": to,
                        "label": f"{TITLE.get(b, b)} {c}:{f}" + (f"-{to}" if to != f else ""),
                        # what a tap opens: the table's row, else the concept's
                        # card, else the theme's page
                        "row": mk["rows"][0][0] if mk["rows"] else None,
                        "node": mk["concepts"][0][0] if not mk["rows"] and mk["concepts"] else None,
                        "rows": [r[1] for r in mk["rows"]],
                        "marks": [r[1] for r in mk["rows"]] + [c_[1] for c_ in mk["concepts"]]
                                 + mk["also"] + mk["chapters"] + [e_[1] for e_ in mk["events"]]})
    return sorted(out, key=lambda x: (x["from"], -x["to"], x["n"]))


def api_verse_themes(d, q):
    """A verse's place in the major themes, for the reader's theme chip."""
    ref = _macula_ref(d, (q.get("ref") or [""])[0])
    return {"ref": ref, "themes": themes_for(d, ref), "credit": THEME_CREDIT}


# ---- events as nodes ---------------------------------------------------------
# 2026-09-29: the event section was completely tag based, and it
# was disappointing on reaching the events, which were not
# really nodes; and if the nodes are mentioned in the primary passages they
# are also associated with the events. The events are Microsoft Copilot's
# (tools/events/event_nodes.py, out/event-nodes.json); their tellings are
# checked against the Berean editors, who outrank Copilot where their parallel
# note and their heading agree (the editors are trusted over Copilot
# as the more credible source).

_EVENTS = None
# the groups built so far, in the chosen order (tools/events/event_nodes.py SCOPES)
EVENT_SCOPES = [("gospels", "Events in the Gospels"),
                ("kingdoms", "Events in Samuel, Kings and Chronicles"),
                ("law", "Events in Genesis to Deuteronomy"),
                ("histories", "Events in Joshua to Esther"),
                ("prophets_writings", "Events in the Writings and Prophets"),
                ("acts_revelation", "Events in Acts to Revelation")]
EVENT_CREDIT = ("Every passage is checked against the Berean text, and each telling "
                "against the Berean editors' own sections and parallel notes. Who is in "
                "the event is everyone its tellings name, and anyone no name was tied to "
                "whose own verses fall in them.")
# how much a cross-reference's evidence is worth, strongest first: the
# editors' own notes, then a declared reference, then a model's judgment,
# then two passages naming the same people
EVIDENCE_ORDER = ["quotation", "editors", "declared", "judged", "names", "read", "ruled"]
EVIDENCE_LABEL = {"read": "read as speaking of this event (Claude Sonnet, a reading)",
                  # a reader's ruling over the model's reading (Romans 5:20, read
                  # in the context Romans 5:13-14 sets up, 2026-10-03)
                  "ruled": "read as speaking of this event, in its context (a reader's reading)",
                  "quotation": "the Berean editors' quotation note",
                  "editors": "the Berean editors' parallel note",
                  "declared": "declared in the text (“as it is written”), read by "
                              "DeepSeek Flash",
                  "judged": "judged to say the same thing (DeepSeek Flash)",
                  "names": "the two passages name the same people or places"}


def _mention_ix():
    """out/mentions.jsonl.gz as book -> (chapter, verse) -> Counter(record):
    every resolved mention, a pronoun's referent included, in MACULA numbering"""
    ix = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    p = OUT / "mentions.jsonl.gz"
    if p.exists():
        for line in gzip.open(p, "rt", encoding="utf-8"):
            r = json.loads(line)
            if "occurrence" not in r:
                continue
            b, c, v = r["occurrence"].split("#")[0].split(".")
            ix[b][(int(c), int(v))][r["record"]] += 1
    return ix


def _events(d):
    """out/event-nodes.json, with each event's participants: every node its
    tellings mention, ranked by how often (the standing rule), and the reverse
    index a node card reads its events from."""
    global _EVENTS
    if _EVENTS is not None:
        return _EVENTS
    p = OUT / "event-nodes.json"
    ev = json.loads(p.read_text(encoding="utf-8")).get("events", {}) if p.exists() else {}
    # AN EVENT MERGED INTO ANOTHER IS ITS SURVIVOR'S (ontology/aliases.jsonl,
    # 2026-10-14 consolidation). tools/events/event_nodes.py joins events
    # whose verses overlap; "Jehoiakim Reigns in Judah" in 2 Kings 23 and in
    # 2 Chronicles 36 do not, so it made two. Folded here, where the alias is
    # applied, so deleting the alias line undoes this too: the survivor takes
    # the other's tellings and what it carried, and every list naming the
    # merged one names the survivor.
    gone = {k: d["ents"][k]["alias_of"] for k in ev
            if (d["ents"].get(k) or {}).get("alias_of") in ev}
    for old, new in gone.items():
        e_old, e_new = ev.pop(old), ev[new]
        have = {(t["first"], t["last"]) for t in e_new["tellings"]}
        e_new["tellings"] += [t for t in e_old["tellings"] if (t["first"], t["last"]) not in have]
        for k in ("within", "parallels", "themes", "mthemes", "secondary", "part_of", "parts"):
            got = list(e_new.get(k) or [])
            got += [x for x in (e_old.get(k) or []) if x not in got]
            e_new[k] = got
        # a parallel that is now one of its own tellings is no longer "elsewhere"
        firsts = {t["first"] for t in e_new["tellings"]}
        e_new["parallels"] = [x for x in e_new["parallels"] if x.get("first") not in firsts]
    if gone:
        for e in ev.values():
            for k in ("part_of", "parts"):
                seen, out = set(), []
                for x in e.get(k) or []:
                    x = dict(x, id=gone.get(x.get("id"), x.get("id"))) if isinstance(x, dict) else x
                    if (x.get("id") if isinstance(x, dict) else x) not in seen:
                        seen.add(x.get("id") if isinstance(x, dict) else x)
                        out.append(x)
                if k in e:
                    e[k] = out
    ix = _mention_ix()
    # PEOPLE THE TEXT DOES NOT NAME (P-74). 2026-10-01: the rich young
    # ruler's event did not show his card, and the Samaritan woman's card did
    # not show her event -- some key wiring between
    # events and persons was missing. A participant is a record the tellings MENTION, and
    # a mention is a name or a pronoun resolved to one; "a certain ruler" and
    # "a woman of Samaria" are neither. A person or group that no verse names
    # anywhere joins an event by its own record's verses instead, where they
    # fall inside a telling -- and says so (`via: "cited"`).
    named = {rec for b in ix.values() for got in b.values() for rec in got}
    unnamed = collections.defaultdict(list)          # book -> [((c, v), id)]
    for rid, ent in d["ents"].items():
        if ent.get("type") not in ("person", "group") or rid in named:
            continue
        for r in ent.get("refs") or []:
            m = _macula_ref(d, re.split(r"[-–]", str(r))[0]).split(".")
            if len(m) == 3 and m[1].isdigit() and m[2].isdigit():
                unnamed[m[0]].append(((int(m[1]), int(m[2])), rid))
    # NAMES NOT SETTLED (tools/meaning/mentions.py, hold_parallel_disagreements):
    # where an event's tellings resolved one name to different people on weak
    # evidence, the mention was held. The card lists it with its verse and the
    # possibilities. 2026-10-01: it is ok to say that some references
    # to Mary are not resolved in terms of which Mary they reference, and
    # the possibilities can be listed with the verse.
    unsettled = collections.defaultdict(list)       # MACULA book -> [((c, v), row)]
    up = OUT / "mentions-unsettled.jsonl"
    if up.exists():
        for line in up.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            b, c, v = r["occurrence"].split("#")[0].split(".")
            unsettled[b].append(((int(c), int(v)), r))
    by_node = collections.defaultdict(list)
    for eid, e in ev.items():
        e["unsettled"] = []
        for t in e["tellings"]:
            a = _macula_ref(d, t["first"]).split(".")
            z = _macula_ref(d, t["last"]).split(".")
            lo, hi = (int(a[1]), int(a[2])), (int(z[1]), int(z[2]))
            for cv, r in unsettled.get(a[0], ()):
                if lo <= cv <= hi:
                    eng = MACULA_BACK.get(a[0], a[0])
                    e["unsettled"].append({
                        "name": re.sub(r"^(of|to|the)\s+", "", r.get("text") or ""),
                        "ref": f"{TITLE.get(eng, eng)} {cv[0]}:{cv[1]}",
                        "go": f"{eng}.{cv[0]}.{cv[1]}",
                        "candidates": [{"id": i, "name": d["ents"][i]["name"],
                                        "who": _who(d["ents"][i])}
                                       for i in r["candidates"] if i in d["ents"]]})
        part, cited = collections.Counter(), collections.Counter()
        for t in e["tellings"]:
            a = _macula_ref(d, t["first"]).split(".")
            z = _macula_ref(d, t["last"]).split(".")
            lo, hi = (int(a[1]), int(a[2])), (int(z[1]), int(z[2]))
            for cv, got in ix.get(a[0], {}).items():
                if lo <= cv <= hi:
                    part.update(got)
            for cv, rid in unnamed.get(a[0], ()):
                if lo <= cv <= hi:
                    cited[rid] += 1
        e["participants"] = [{"id": n, "n": c} for n, c in part.most_common()
                             if n in d["ents"]] + \
                            [{"id": n, "n": c, "via": "cited"} for n, c in cited.most_common()]
        for x in e["participants"]:
            by_node[x["id"]].append({"id": eid, "name": e["title"], "n": x["n"],
                                     **({"via": x["via"]} if x.get("via") else {})})
    by_theme = collections.defaultdict(list)
    for eid, e in ev.items():
        for m in e.get("mthemes") or []:
            by_theme[m["theme"]].append({"id": eid, "title": e["title"],
                                         "n_cited": m["n_cited"], "n_tagged": m["n_tagged"],
                                         "listed": m["listed"]})
    _EVENTS = {"events": ev, "by_node": by_node, "by_theme": by_theme,
               "by_stamp": {e["stamp"]: k for k, e in ev.items() if e.get("stamp")}}
    return _EVENTS


_EVLINKS = None


_LETTERS = None


def _letter_refs():
    """event id -> the references to it from Romans-Jude (plan 6.21,
    ontology/letter-references.jsonl), in letter order. SHOWN ONLY ONCE THE
    SITE'S OWNER HAS READ THEM (`reviewed_by_owner`), as the stories told
    again were; BIBLEONT_SHOW_UNREVIEWED=1 shows them on a laptop to check
    the look before then. Each carries the letter's words and the account's,
    both machine-checked, and -- where the link is not obvious (2026-10-04:
    if it is obvious it does not require an explanation) --
    one sentence that passed the reader review (the letters' the eight, the
    poems' the nine of 2026-10-05)."""
    global _LETTERS
    if _LETTERS is None:
        show_all = os.environ.get("BIBLEONT_SHOW_UNREVIEWED") == "1"
        _LETTERS = collections.defaultdict(list)
        # ...and from the psalms and poems (plan 6.19, ontology/poem-
        # references.jsonl), the same in every respect: `kind` says which,
        # and `letter` holds the poem's span too, so one path shows both
        src = [("letter", r) for r in _rows(ROOT / "ontology" / "letter-references.jsonl")]
        src += [("poem", dict(r, letter=r["poem"])) for r in _rows(ROOT / "ontology" / "poem-references.jsonl")]
        # ...and between the prophets and events (plan 6.20, ontology/
        # prophet-references.jsonl), whose `kind` the plan keeps apart and
        # carries here as `pkind`: back (the prophet names an earlier
        # happening), own_time (the prophet's words date it to a happening of
        # its day), forward (a later text quotes the prophet or says it
        # happened as spoken -- the event is the later one's)
        src += [("prophet", dict(r, letter=r["prophet"])) for r in _rows(ROOT / "ontology" / "prophet-references.jsonl")]
        for kind, r in src:
            if not (r.get("reviewed_by_owner") or show_all):
                continue
            _LETTERS[r["event"]].append({
                "kind": kind, "pkind": r.get("kind") if kind == "prophet" else None,
                "letter": r["letter"], "words": r["distinctive"],
                "account_verse": r["account_verse"], "account_words": r["account_words"],
                "why": None if r.get("obvious") else r.get("why"),
                # APPARENT, NOT CERTAIN (2026-10-05: labelling them that
                # lets the user know that the reference is apparent, rather
                # than certain): readers differ on which account is meant,
                # or the tie rests on words other accounts share
                "certainty": r.get("certainty", "clear"),
                "reason": r.get("apparent_reason")})
        for v in _LETTERS.values():
            v.sort(key=lambda r: (r["certainty"] != "clear", _vkey_macula(r["letter"][0])))
    return _LETTERS


def _in_span(ref, span):
    """a BSB ref ('Heb.11.7') inside a letter span ['Heb.11.7', 'Heb.11.8']"""
    if not ref:
        return False
    try:
        return _vkey_macula(span[0]) <= _vkey_macula(ref) <= _vkey_macula(span[1])
    except (ValueError, KeyError, IndexError):
        return False


def _event_links():
    """(event id, suggested label) -> the reading of that link."""
    global _EVLINKS
    if _EVLINKS is None:
        _EVLINKS = {(r["event"], r["label"]): r for r in _rows(ROOT / "ontology" / "event-links.jsonl")}
    return _EVLINKS


def _section_heads(d, first, last):
    """The Berean editors' section headings that open inside a telling, each
    with its verse ("Adonijah Usurps the Kingdom", 1Kgs.1.5). `first` and
    `last` are the reader's refs (the Berean's numbering)."""
    try:
        b, c1, v1 = first.split(".")
        b2, c2, v2 = last.split(".")
    except (AttributeError, ValueError):
        return []
    if b != b2:
        return []
    keys = d.setdefault("_book_keys_app", {}).get(b)
    if keys is None:
        keys = d["_book_keys_app"][b] = sorted(k for k in d["verses"] if k[0] == b)
    lo, hi = (int(c1), int(v1)), (int(c2), int(v2))
    out = []
    for k in keys:
        if lo <= (k[1], k[2]) <= hi:
            sm = d.get("seams", {}).get(f"{TO_MACULA.get(b, b)}.{k[1]}.{k[2]}") or {}
            if sm.get("by") == "heading" and sm.get("title"):
                out.append({"title": sm["title"], "go": f"{b}.{k[1]}.{k[2]}"})
    return out


def event_of(d, eid):
    """One event, as its card shows it."""
    e = _events(d)["events"].get(eid)
    if not e:
        return None
    ents = d["ents"]
    part = [dict(x, name=ents[x["id"]]["name"], type=ents[x["id"]]["type"])
            for x in e["participants"]]
    sec = []
    # THE DRAFT'S SUGGESTIONS, READ (2026-10-03: Sonnet was to look at
    # all of these): 410 of 586 had no evidence. Each was read blind
    # against the event's own passage (ontology/event-links.jsonl): one that
    # speaks of the event gains a reading as its evidence; one that only
    # shares its subject stays suggested and says so; an unrelated one leaves
    read = _event_links()
    for s in e["secondary"]:
        # a reading applies where there was no evidence -- or where it was made
        # knowing the evidence (`over_evidence`): Romans 7:7 and 13:8-10 QUOTE
        # the commandments, so the quotation layer evidences them, but they
        # speak of what the law does, not of its giving (the eight-reader
        # review of "Israel receives the law", 2026-10-03)
        v = read.get((eid, s["label"]))
        if v and s["evidence"] and not v.get("over_evidence"):
            v = None
        if v and v["verdict"] == "unrelated":
            continue
        last = False
        if v and v["verdict"] == "recalls":
            s = dict(s, evidence=["ruled" if str(v.get("reader", "")).startswith("a reader")
                                  else "read"], read_why=v.get("why"))
        elif v and v["verdict"] == "same_subject":
            # a quotation that only shares the subject is shown with the rest
            # that share it, not under "with evidence"
            s = dict(s, evidence=[], read_note="shares its subject, but does not speak of "
                                               "this event (Claude Sonnet, a reading)")
            last = True
        ev = sorted(s["evidence"], key=EVIDENCE_ORDER.index)
        sec.append(dict(s, evidence=ev, why=[EVIDENCE_LABEL[k] for k in ev],
                        rank=99 if last or not ev else EVIDENCE_ORDER.index(ev[0])))
    sec.sort(key=lambda s: s["rank"])
    refs = _letter_refs().get(eid, [])
    letters = [r for r in refs if r["kind"] == "letter"]
    poems = [r for r in refs if r["kind"] == "poem"]
    prophets = [r for r in refs if r["kind"] == "prophet"]
    themes = []
    for t in e["themes"]:
        n = ents.get(t["node"]) if t.get("node") else None
        themes.append({"name": t["name"], "node": t["node"] if n else None,
                       "node_name": n["name"] if n else None})
    return {"id": eid, "title": e["title"], "credit": EVENT_CREDIT,
            "list": e["list"], "n": e["n"], "aliases": e.get("aliases") or [],
            "stamp": e.get("stamp"), "tellings": e["tellings"],
            "within": e.get("within") or [], "parallels": e.get("parallels") or [],
            # the grouping among events: the larger event this is part of,
            # and the events inside it (by their passages)
            "part_of": e.get("part_of") or [], "parts": e.get("parts") or [],
            # the major themes it belongs to, each with its scripture
            "mthemes": [dict(m, title=_title(_theme_map()["_by"][m["theme"]]["title"]))
                        for m in e.get("mthemes") or [] if m["theme"] in _theme_map()["_by"]],
            "participants": part, "themes": themes,
            # a letter or poem verse judged here (6.21, 6.19) is shown there,
            # not twice
            "secondary": [s for s in sec if not any(
                _in_span(s.get("first"), r["letter"]) for r in refs)],
            "letters": letters, "poems": poems, "prophets": prophets,
            "unsettled": e.get("unsettled") or [],
            # THE LEAD SENTENCE IS A RETELLING FROM THE TEXT. It was the event
            # draft's "Notes" (Copilot), in the site's own voice, and some took
            # positions the text does not ("succeeds where Adam and Israel
            # failed ... perfect obedience"; "affirm salvation by grace through
            # faith"). 2026-10-03: rewrite from the text. Only a
            # retelling written from the event's own passages and checked
            # against them (ontology/event-summaries.jsonl) is shown; the draft's
            # notes are not, in the meantime or after
            "notes": (_event_summaries().get(eid) or {}).get("summary"),
            # WHAT HAPPENS, IN THE EDITORS' WORDS, where no retelling has passed
            # its review yet (2026-10-13, items 1-4 done together: 385 of 452
            # event cards opened on the credit line, saying nothing of what
            # happens). The headings of the first telling, each its verse;
            # the Berean's, so nothing is said in the site's own voice
            "heads": [] if _event_summaries().get(eid) else
                     next((h for h in (_section_heads(d, t.get("first"), t.get("last"))
                                       for t in e["tellings"]) if h), [])}


_NUMBERS = None


def _numbers():
    """number id -> its card (out/significant-numbers.json)."""
    global _NUMBERS
    if _NUMBERS is None:
        p = OUT / "significant-numbers.json"
        _NUMBERS = json.loads(p.read_text(encoding="utf-8")).get("numbers", {}) if p.exists() else {}
    return _NUMBERS


_EVSUM = None


def _event_summaries():
    """event id -> its retelling from the text (ontology/event-summaries.jsonl)."""
    global _EVSUM
    if _EVSUM is None:
        _EVSUM = {r["event"]: r for r in _rows(ROOT / "ontology" / "event-summaries.jsonl")
                  if r.get("checked") == "ok"}
    return _EVSUM


_TPL = None


def _templates():
    """out/event-template-instances.json (tools/events/template_nodes.py): the
    eight event templates, their instances (events and arcs of events) and
    each instance's stages with their verses and evidence."""
    global _TPL
    if _TPL is None:
        p = OUT / "event-template-instances.json"
        _TPL = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _TPL


def templates_for(d, eid):
    """The template instances a node is, or is part of (an event in an arc)."""
    return _templates().get("by_node", {}).get(eid, [])


_MSGS = None


def _messages():
    """out/message-view.json (tools/themes/messages.py): the divine messages,
    each with every verse its form stands in, who speaks it, and where it is
    spoken in the other taxonomies."""
    global _MSGS
    if _MSGS is None:
        p = OUT / "message-view.json"
        _MSGS = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _MSGS


def messages_at(b, c):
    """{verse: [{id, name}]} the messages whose form stands in this chapter's
    verses (Berean book and numbering), for the reader's chips."""
    v = _messages()
    ms = v.get("messages") or {}
    out = {}
    pre = f"{b}.{c}."
    for ref, ids in (v.get("by_verse") or {}).items():
        if ref.startswith(pre):
            # the most specific first: "Do not fear" before "Thus says the LORD"
            out[int(ref[len(pre):])] = [{"id": i, "name": ms[i]["name"]}
                                        for i in sorted((i for i in ids if i in ms),
                                                        key=lambda i: ms[i]["count"])]
    return out


_ACTS_BY_VERSE = None


def acts_at(b, c):
    """{verse: [{id, name}]} the speech acts the text names in this chapter's
    verses, for the reader's chips (plan A.18; approved 2026-10-01 as
    P-73: Ps 23:1 is a confession of faith and the reader never said so).
    Rarest first, as the messages are; an act is left off a verse where one
    of its own narrower messages already has a chip there ("Do not fear" says
    "promise" without a second chip)."""
    global _ACTS_BY_VERSE
    acts = _speech_acts().get("acts") or {}
    if _ACTS_BY_VERSE is None:
        _ACTS_BY_VERSE = collections.defaultdict(list)
        for a in acts.values():
            for i in a.get("instances") or []:
                _ACTS_BY_VERSE[i["v"]].append(a["id"])
    mby = _messages().get("by_verse") or {}
    pre = f"{b}.{c}."
    out = {}
    for ref, ids in _ACTS_BY_VERSE.items():
        if not ref.startswith(pre):
            continue
        here = set(mby.get(ref) or ())
        keep = [i for i in ids if i in acts
                and not here & {m["id"] for m in acts[i].get("messages") or []}]
        if keep:
            out[int(ref[len(pre):])] = [{"id": i, "name": acts[i]["name"]}
                                        for i in sorted(set(keep), key=lambda i: acts[i]["count"])]
    return out


def message_card(d, eid):
    """A message's card, or a message group's."""
    v = _messages()
    if eid.startswith("msggroup_"):
        g = next((g for g in (v.get("groups") or {}).values() if g["id"] == eid), None)
        if not g:
            return None
        ms = [v["messages"][m] for m in g["messages"]]
        return {"group": True, "name": g["name"],
                "messages": [{"id": m["id"], "name": m["name"], "count": m["count"],
                              "speakers": m["speakers"][:3]} for m in ms]}
    m = (v.get("messages") or {}).get(eid)
    if not m:
        return None
    # the speech act it is a narrower form of
    act = next(({"id": a["id"], "name": a["name"]} for a in (_speech_acts().get("acts") or {}).values()
                if any(x["id"] == eid for x in a["messages"])), None)
    return dict({k: m[k] for k in ("name", "group", "group_name", "count", "speakers", "who",
                                   "story", "roles", "themes", "events", "refrain")},
                group_id="msggroup_" + m["group"], instances=m["instances"], act=act)


def _spoken_in(items, eid, theme=None):
    """What is spoken in a node: the other end of `spoken_in`, so the link
    reads from both sides. Taxonomy linking is what binds together.
    The edge lands on an INSTANCE (Huldah's row, Cain's story); a pattern's
    own card gathers what is spoken in any of its instances, and says where."""
    out = []
    for m in items:
        hits = ([s for s in m["story"] if eid in (s["id"], s.get("pattern"))]
                + [r for r in m["roles"] if eid in (r["id"], r.get("pattern"))]
                + [t for t in m["themes"] if (theme and t["id"] == theme) or t.get("node") == eid]
                + [e for e in m["events"] if e["id"] == eid])
        if hits:
            h = max(hits, key=lambda x: x["n"])
            where = h.get("stage") or h.get("slot") or ""
            if h.get("pattern") == eid:            # on the pattern: name the instance
                where = f"{h['name']} · {where.lower()}"
            out.append({"id": m["id"], "name": m["name"], "n": sum(x["n"] for x in hits)
                        if h.get("pattern") == eid else h["n"],
                        "where": where, "first": h.get("first")})
    out.sort(key=lambda x: -x["n"])
    return out


def messages_in(d, eid, theme=None):
    """The messages spoken in a story or role instance or pattern, a theme or
    an event."""
    return _spoken_in((_messages().get("messages") or {}).values(), eid, theme)


_SACTS = None


def _speech_acts():
    """out/speech-act-view.json (tools/themes/speech_acts.py): the kinds of
    speaking (plan A.12), each with the verses where the text names it."""
    global _SACTS
    if _SACTS is None:
        p = OUT / "speech-act-view.json"
        _SACTS = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _SACTS


def speech_card(d, eid):
    """A speech act's card, or a speech-act group's. (No reader chips was
    the choice on 2026-09-30; on 2026-10-01 P-73 was approved, and the
    reader now marks them: acts_at.)"""
    v = _speech_acts()
    if eid.startswith("sactgroup_"):
        g = next((g for g in (v.get("groups") or {}).values() if g["id"] == eid), None)
        if not g:
            return None
        return {"group": True, "name": g["name"], "desc": g["desc"],
                "acts": [{"id": a, "name": v["acts"][a]["name"], "count": v["acts"][a]["count"]}
                         for a in g["acts"]]}
    a = (v.get("acts") or {}).get(eid)
    if not a:
        return None
    return dict(a, group_id="sactgroup_" + a["group"])


def acts_in(d, eid, theme=None):
    """The speech acts spoken in a node, as `messages_in`."""
    return _spoken_in((_speech_acts().get("acts") or {}).values(), eid, theme)


_ROLES = None


def _roles():
    """out/role-pattern-view.json (tools/themes/role_nodes.py): the role
    patterns (plan A.10), a row per figure and a cell per slot."""
    global _ROLES
    if _ROLES is None:
        p = OUT / "role-pattern-view.json"
        _ROLES = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _ROLES


def _role_row(r):
    """A role pattern's row in the shape the story table draws."""
    return {"instance": r["id"], "title": r["name"], "name": r["name"],
            "conjectured": False, "mark": "by analogy" if r["reading"] else "",
            "given": r["given"],
            "stages": [{"kind": slot, "label": c["label"], "first": c["first"],
                        "added": c["added"], "reading": c["reading"], "id": c["id"]}
                       for slot, cs in r["cells"].items() for c in cs]}


def role_family(d, eid):
    """A role pattern's card (or one row's): its slots as the table's columns
    and a row per figure. The same table as a story pattern's, because
    both were asked for: this will be important for roles as well."""
    v = _roles()
    pid = eid[len("rolepat_"):] if eid.startswith("rolepat_") else \
        (v.get("by_node", {}).get(eid) or {}).get("pattern")
    p = v.get("patterns", {}).get(pid or "")
    if not p:
        return None
    rows = [r for r in p["rows"] if eid.startswith("rolepat_") or r["id"] == eid]
    return {"name": p["name"], "note": p["note"], "kind": "role", "frame": p["frame"],
            "pattern_id": p["id"], "single": not eid.startswith("rolepat_"),
            "stages": p["slots"], "instances": [_role_row(r) for r in rows]}


def roles_for(d, eid):
    """The role patterns a person has a row in, and whether the text gives
    them the role (in its own words) or a reader does (by analogy)."""
    v = _roles()
    out = []
    for x in v.get("by_figure", {}).get(eid, []):
        p = v["patterns"][x["pattern"]]
        r = next((r for r in p["rows"] if r["id"] == x["row"]), None)
        if r:
            out.append({"pattern_id": p["id"], "pattern_name": p["name"], "row": r["id"],
                        "row_name": r["name"], "given": r["given"], "reading": r["reading"],
                        "slots": [s["name"] for s in p["slots"] if s["name"] in r["cells"]]})
    return out


def template_family(d, eid):
    """A template family's card: its stages and its instances."""
    if eid.startswith(("rolepat_", "rrow_")):
        return role_family(d, eid)
    if not eid.startswith("tpl_"):
        return None
    f = _templates().get("families", {}).get(eid[4:])
    if not f:
        return None
    # Each instance carries its stages, so the card can set every story side by
    # side in one table, a column per stage. 2026-09-30: show a table
    # for each story pattern with each of the instances slotted in.
    ents, by_node = d["ents"], _templates().get("by_node", {})

    def stages(iid):
        for t in by_node.get(iid, []):
            if t["family"] == eid[4:] and t["instance"] == iid:
                return [{k: s[k] for k in ("kind", "label", "first", "added")}
                        for s in t["stages"]]
        return []
    return dict(f, kind="story", pattern_id=eid,
                instances=[dict(i, name=(ents.get(i["instance"]) or {}).get("name", i["title"]),
                                title=re.sub(r"^Story arc: ", "", i["title"]),
                                stages=stages(i["instance"]))
                           for i in f["instances"]])


def template_stage(d, eid):
    """A stage's card: the pattern it is a stage of, the story it is in, and
    that story's stages in order, this one marked. 2026-09-30, on a
    stage card: it should be obvious, on a pattern stage, how to
    navigate to the story pattern; the link could not be found from within
    -- the stage was two hops from its pattern (part_of the arc, which is
    instance_of the pattern) and neither hop said so."""
    if eid.startswith("rcell_"):
        # a role pattern's cell: its pattern, its row, and the row's cells
        v = _roles()
        at = v.get("by_node", {}).get(eid)
        p = v.get("patterns", {}).get((at or {}).get("pattern", ""))
        r = next((r for r in (p or {}).get("rows", []) if r["id"] == at["row"]), None) if at else None
        if not r:
            return None
        return {"family": at["pattern"], "family_name": p["name"], "pattern_id": p["id"],
                "pattern_kind": "Role pattern", "instance": r["id"], "instance_name": r["name"],
                "stages": [{"id": c["id"], "name": slot, "label": c["label"],
                            "first": c["first"], "here": c["id"] == eid}
                           for slot, cs in r["cells"].items() for c in cs]}
    if not eid.startswith("stage_"):
        return None
    for t in (t for ts in _templates().get("by_node", {}).values() for t in ts):
        if t.get("via_arc") or not any(s["id"] == eid for s in t["stages"]):
            continue
        ent = d["ents"].get(t["instance"]) or {}
        return {"family": t["family"], "family_name": t["family_name"],
                "pattern_id": "tpl_" + t["family"], "pattern_kind": "Story pattern",
                "instance": t["instance"],
                "instance_name": ent.get("name", t["title"]),
                "stages": [{"id": s["id"], "name": s["name"], "label": s["label"],
                            "first": s["first"], "here": s["id"] == eid}
                           for s in t["stages"]]}
    return None


def events_for(d, eid):
    """The events a node takes part in: its name is in their tellings."""
    return sorted(_events(d)["by_node"].get(eid, []), key=lambda x: -x["n"])


_EVENT_SPANS = None


def events_at(d, ref):
    """The events whose tellings hold a verse ("Mark 1:17", the store's form):
    the smallest first, so a saying lands in its scene before the larger
    event around it. Every Gospel an event is told in comes with it -- a
    saying extracted from Mark reaches Matthew and Luke through its event."""
    global _EVENT_SPANS
    if _EVENT_SPANS is None:
        _EVENT_SPANS = collections.defaultdict(list)
        for eid, e in _events(d)["events"].items():
            for t in e["tellings"]:
                b, c1, v1 = t["first"].split(".")
                _b, c2, v2 = t["last"].split(".")
                _EVENT_SPANS[b].append(((int(c1), int(v1)), (int(c2), int(v2)), eid,
                                        t.get("n") or 0))
    m = re.match(r"^(\S+) (\d+):(\d+)", ref or "")
    if not m:
        return []
    cv = (int(m.group(2)), int(m.group(3)))
    got = sorted({(n, eid) for lo, hi, eid, n in _EVENT_SPANS.get(m.group(1), [])
                  if lo <= cv <= hi})
    evs = _events(d)["events"]
    out = []
    for _n, eid in got:
        e = evs[eid]
        books = sorted({t["first"].split(".")[0] for t in e["tellings"]},
                       key=lambda b: ORDER.index(b) if b in ORDER else 99)
        out.append({"id": eid, "title": e["title"], "told_in": [TITLE.get(b, b) for b in books]})
    return out


# A SAYING RECORDED BY WHO SAID IT AND WHERE ("Jesus at Mark 1:17", 728 of
# them from the Genesis, Job and Mark extractions) says nothing about what was
# said. 2026-09-29, searching "Jesus": the first page showed Jesus at
# Mark 1:15, Jesus at Mark 1:17 ..., which led to pretty weak contents;
# the event should be given a meaningful name. Shown by its
# own opening words, from its record; the stored name is kept.
SPEECH_NAME = re.compile(r"^(.+) at ((?:[1-3] ?)?[A-Z][a-z]+\.? \d+:\d+)$")


def speech_label(d, e):
    """From the BEREAN verse, never the record's description: the records
    quote an older English (KJV) that the reader does not show, and one
    apostrophe ("Jesus's answer") broke a quote-hunt on it. The first quoted
    speech in the verse, or the verse's opening words where it has no
    quotation marks (Job's speeches are poetry, unquoted)."""
    m = SPEECH_NAME.match(e.get("name") or "")
    if not m or e.get("type") != "text":
        return None
    r = re.match(r"^(\S+) (\d+):(\d+)", (e.get("refs") or [""])[0])
    text = d["verses"].get((r.group(1), int(r.group(2)), int(r.group(3))), "") if r else ""
    q = re.search(r"“([^”]{3,})", text)
    words = (q.group(1) if q else text).split()
    if not words:
        return None
    return f"“{' '.join(words[:7]).rstrip(',.;:')}{'…' if len(words) > 7 else ''}”" \
           f" — {m.group(1)}, {m.group(2)}"


def api_upper(d, q):
    """THE UPPER ONTOLOGIES, for Explore's fourth section. 2026-09-28:
    the ontologies are to be visible somewhere, perhaps called
    Upper Ontologies. Built by tools/upper_ontologies.py (the server
    runs without rdflib and yaml, so it reads the file like any layer)."""
    global _UPPER
    if _UPPER is None:
        p = OUT / "upper-ontologies.json"
        _UPPER = json.loads(p.read_text(encoding="utf-8")) if p.exists()             else {"parts": [], "missing": "run tools/upper_ontologies.py"}
    # whether /ns/map is published, so Explore offers it only then (as About)
    return {**_UPPER, "schema_map": (OUT / "ns" / "map.html").exists()}


_TAG_XW = None


def _tag_crosswalk():
    """ontology/tag-crosswalk.json: every tag-taxonomy entry, with its home."""
    global _TAG_XW
    if _TAG_XW is None:
        p = ROOT / "ontology" / "tag-crosswalk.json"
        _TAG_XW = json.loads(p.read_text(encoding="utf-8"))["entries"] if p.exists() else {}
    return _TAG_XW


def _tag_taxonomy(tid):
    """Where a tag sits in the tag taxonomy: its category, group and gloss --
    or, for a thing tag folded into a node, the node that holds it."""
    v = _tag_crosswalk().get(tid) or _tag_crosswalk().get(tid.removesuffix("_ev"))
    if v and v.get("status") == "folded":
        return {"category": v.get("category") or "", "group": "", "label": v.get("label") or tid,
                "gloss": "", "note": "", "folded_into": v.get("home"),
                "folded_name": v.get("home_name") or v.get("home")}
    for p in (api_upper(None, {}).get("parts") or []):
        if p.get("id") != "tags":
            continue
        for g in p.get("groups", []):
            for s in g.get("sub", []):
                for it in s.get("items", []):
                    if tid in (it.get("id"), (it.get("label") or "").replace(" ", "_")):
                        return {"category": g["label"], "group": s.get("label") or "",
                                "label": it.get("label") or tid, "gloss": it.get("gloss") or "",
                                "note": g.get("note") or ""}
    return None


_ANCHORS = None
_VERSES_OF = None


_MEMBERSHIP = None


def _membership():
    """tools/meaning/membership.py: which words and verses belong to a card,
    the one definition the server, the concept audit and the resolution layer
    share (plan 4.8 step 0(a), 2026-10-19). The server passes it what it
    already holds; it keeps no copy of its own."""
    global _MEMBERSHIP
    if _MEMBERSHIP is None:
        import importlib
        mdir = str(ROOT / "tools" / "meaning")
        if mdir not in sys.path:
            sys.path.insert(0, mdir)
        _MEMBERSHIP = importlib.import_module("membership")
    return _MEMBERSHIP


def _anchors():
    """record id -> its anchored words [(key, share)], as readers are shown
    them (tools/meaning/membership.py)."""
    global _ANCHORS
    if _ANCHORS is None:
        _ANCHORS = _membership().anchors(_rows(OUT / "concept-anchors.jsonl.gz"))
    return _ANCHORS


def _verses_of(d):
    """word key (g907, h4196) -> the verses it occurs in, from the node layer."""
    global _VERSES_OF
    if _VERSES_OF is None:
        by = collections.defaultdict(set)
        # from the chapter blocks' word rows: what the walk over every node
        # gathered (a node with no Strong's number has no sense key)
        for lang, strong, ref, _text, _lemma in _structure().words():
            k = sense_key(lang, strong)
            if k and ref:
                by[k].add(sys.intern(ref))
        _VERSES_OF = by
    return _VERSES_OF


# ---- word families (plan 5.10) -----------------------------------------------
# 2026-10-01: a bridge was wanted between Phl 4:11 and 1 Tim 6:8
# and 1 Tim 6:6 -- αὐτάρκης, ἀρκέω and αὐτάρκεια, which every layer missed
# because every layer matched the exact lemma. out/word-families.json
# (tools/word_families.py) holds kin by the lexicon's own derivation notes,
# ONE step (if one level does it for the content example, one level
# suffices), keys and relationship only.
_FAMILIES = None
KIN_MAX = 40       # a family used more than this is a concordance, not a bridge
# AND THE WORD HERE MUST BE DISTINCTIVE. First built with KIN_MAX alone, John
# 3:16 listed 80 verses through δίδωμι, ἔχω, θεός, κόσμος and υἱός -- small
# families of very common words. αὐτάρκης (1 use), ἀρκέω (8), αὐτάρκεια (2)
# and εὐσέβεια (15) are what a reader means by a bridge; μέγας (190) is not.
KIN_WORD_MAX = 30
# the file says what THIS word is to its kin ("from" = this word comes from
# it); a row on screen says what the KIN is to this word, so it flips:
# on αὐτάρκης's card, ἀρκέω is "the source of αὐτάρκης"
KIN_HOW = {"from": "the source of", "gives": "from", "akin to": "akin to",
           # the lexicon's own cross-reference ("see:", "cf."): shown on the
           # card -- of ἀγάπη's showing ἄστοργος "unfeeling", which found its
           # opposite and was judged great -- never as descent,
           # and never used to bridge verses
           "compare": "the lexicon says to compare it with",
           "opposite": "the lexicon's opposite of"}
KIN_BRIDGES = {"from", "gives", "akin to"}     # only these bridge verses


def _families():
    global _FAMILIES
    if _FAMILIES is None:
        p = OUT / "word-families.json"
        _FAMILIES = (json.loads(p.read_text(encoding="utf-8")).get("families") or {}) \
            if p.exists() else {}
    return _FAMILIES


def _word_label(d, k):
    """A word as the app shows it everywhere: MACULA's lemma, and a gloss
    from its profile, the lexicon extract, or the text's own first gloss."""
    lx = d["lex"].get(k) or {}
    gloss = (d["profiles"].get(k) or {}).get("gloss") or lx.get("gloss")
    if not gloss:
        rows, _n = occurrences(d, k)
        gloss = rows[0]["gloss"] if rows else None
    return d["lemmas"].get(k) or lx.get("word") or k, gloss


def family_of(d, key):
    """The word card's kin: each word one derivation step away that the
    text actually uses, commonest first."""
    vo = _verses_of(d)
    out = []
    for k, how in _families().get(key, []):
        n = len(vo.get(k, ()))
        if not n:
            continue                     # in the lexicon, not in the text
        lemma, gloss = _word_label(d, k)
        out.append({"key": k, "lemma": lemma, "gloss": gloss, "uses": n,
                    "how": KIN_HOW.get(how, how)})
    return sorted(out, key=lambda x: -x["uses"])


_VERSE_KEYS = None


def _rendering(d, key, ref):
    """How the text renders word `key` in verse `ref` (MACULA's gloss there)."""
    rows, _n = occurrences(d, key)
    return next((r["gloss"] for r in rows if r["ref"] == ref), None)


def kin_verses(d, ref):
    """Verses elsewhere that use a kin word of a word in this one: Phil 4:11's
    αὐτάρκης finds 1 Tim 6:6 (αὐτάρκεια) and 1 Tim 6:8 (ἀρκέω). A bridge by
    the words, shown as such and never as "says the same thing". Only small
    families: past KIN_MAX uses it would list half a concordance (λόγος)."""
    global _VERSE_KEYS
    vo = _verses_of(d)
    if _VERSE_KEYS is None:
        vk = collections.defaultdict(set)
        for k, refs in vo.items():
            for r in refs:
                vk[r].add(k)
        _VERSE_KEYS = vk
    fam = _families()
    mine = _VERSE_KEYS.get(ref, set())
    out = []
    for k in sorted(mine, key=lambda x: len(vo.get(x, ()))):     # rarest first
        if len(vo.get(k, ())) > KIN_WORD_MAX:
            continue
        kin = [(k2, how) for k2, how in fam.get(k, [])
               if how in KIN_BRIDGES and k2 not in mine and vo.get(k2)]
        if not kin or sum(len(vo[k2]) for k2, _h in kin) > KIN_MAX:
            continue
        word, wgloss = _word_label(d, k)
        # RENDERED ALIKE FIRST. In Phil 4:11 αὐτάρκης is rendered "content";
        # ἀρκέω's verses in canon order put Matt 25:9 "enough" ahead of
        # 1 Tim 6:8 "we will be content" -- the one asked for. Each verse
        # records its own rendering of the word (MACULA's gloss), so verses
        # where the kin word is rendered with a word from this verse's
        # rendering come first, then canon order.
        here = {w[:5] for w in re.findall(r"[a-z]{4,}", (_rendering(d, k, ref) or "").lower())}
        for k2, how in kin:
            kword, kgloss = _word_label(d, k2)
            seen_as = {r["ref"]: (r["gloss"] or "").lower() for r in occurrences(d, k2)[0]}
            alike = lambda r: 0 if here and any(  # noqa: E731
                w[:5] in here for w in re.findall(r"[a-z]{4,}", seen_as.get(r, ""))) else 1
            refs = sorted(vo[k2] - {ref}, key=lambda x: (alike(x), _MCANON.get(x.split(".")[0], 99),
                                                         [int(n) for n in x.split(".")[1:]]))
            for r in refs:
                eref, text = _verse_text(d, r)
                out.append({"ref": r, "eref": eref, "text": text,
                            "word": word, "gloss": wgloss, "key": k,
                            "kin": kword, "kin_gloss": kgloss, "kin_key": k2,
                            "how": KIN_HOW.get(how, how)})
    return out


# (the Greek prefixes, the card's stems and their stop words moved to
# tools/meaning/membership.py with the rest of a card's membership)
_VSENSES = None


def _verse_senses():
    """(card, word key) -> verdict, from ontology/verse-senses.jsonl (C-D13)."""
    global _VSENSES
    if _VSENSES is None:
        _VSENSES = {(r["card"], r["key"]): r["verdict"]
                    for r in _rows(ROOT / "ontology" / "verse-senses.jsonl")}
    return _VSENSES



def api_entity_verses(d, q):
    """WHERE THE TEXT SPEAKS OF IT, for a card. 2026-09-28: the
    baptism card looked sparse, not mentioning baptism events like Acts 8:36
    and 8:38 — its record cited 2 verses. Every verse carrying one of the
    record's anchored words (concept_anchors.py), and the words of the SAME
    ROOT in the same language (first five letters: βάπτισμα finds βαπτίζω,
    which Acts 8:36 and 8:38 use), by book in canon order. The words used are
    returned, so the card says which."""
    eid = (q.get("id") or [""])[0]
    # WHICH WORDS AND VERSES ARE THE CARD'S: tools/meaning/membership.py, the
    # one definition the concept audit and the resolution layer also use
    # (plan 4.8 step 0(a)). The rules and their history are there: the same
    # root (βάπτισμα finds βαπτίζω, Acts 8:36), a Greek prefix not a root, a
    # name not a family, the lexicon's derived words only (P-79), and a word of
    # another sense giving only its card-sense uses (C-D13, the temple card)
    M = _membership()
    words = M.words(_anchors().get(eid, []), d.get("lemmas") or {}, _families(), card=eid)
    # a verse a ruled repair named (two judges said it speaks of the card) is
    # marked a reading where it shows (the concept-repair sheets, 2026-10-20)
    how = {}
    verses = M.verses(eid, d["ents"].get(eid) or {}, words, _verses_of(d), d["occ"], _verse_senses(), how)
    return {"id": eid, "words": sorted(words.values(), key=lambda w: w["family"]),
            "total": len(verses), "books": _by_book(d, {v: how.get(v) for v in verses}),
            "phrase": phrase_verses(d, eid)}


def _by_book(d, how):
    """{MACULA verse: how-or-None} -> books in canon order, each verse with
    its Berean text"""
    by = collections.defaultdict(list)
    for v in how:
        by[v.split(".")[0]].append(v)
    books = []
    for b, vs in sorted(by.items(), key=lambda kv: _MCANON.get(kv[0], 99)):
        vs.sort(key=lambda r: [int(x) for x in r.split(".")[1:]])
        items = []
        for v in vs[:300]:
            eref, text = _verse_text(d, v)
            items.append({"eref": eref, "text": text, "how": how[v]})
        books.append({"book": b, "title": TITLE.get(MACULA_BACK.get(b, b), b),
                      "n": len(vs), "items": items})
    return books


_PHRASES = None


def _phrases():
    """out/phrase-occurrences.jsonl.gz (tools/phrases/phrase_search.py): each
    multi-word node's phrase found in the text, in English and across the
    language divide."""
    global _PHRASES
    if _PHRASES is None:
        _PHRASES = {r["id"]: r for r in _rows(OUT / "phrase-occurrences.jsonl.gz")
                    if "id" in r}
    return _PHRASES


def phrase_verses(d, eid):
    """WHERE THE TEXT SAYS IT, for a multi-word node. 2026-09-30, on
    "living water": Blue Letter Bible listed all the verses, including several
    OT references that were missed by this site, because the multiple words
    got lost across the language divide. A phrase has no single anchored word, so the
    word list above found nothing for it; this is the phrase itself -- where an
    English translation says it, and where the same Hebrew or Greek words stand
    together under another rendering (Lev 14:5's "fresh water" is Jer 2:13's
    living water). An index of where the words are, not a reading of each."""
    r = _phrases().get(eid)
    if not r:
        return None
    how = {}
    for v, trs in r["english"].items():
        how[_macula_ref(d, v)] = "in English: " + ", ".join(trs)
    for v in r["across"]:
        how[_macula_ref(d, v)] = "the same " + (
            "Hebrew" if _MCANON.get(_macula_ref(d, v).split(".")[0], 0)
            < _MCANON.get("Mat", 39) else "Greek") + " words, translated differently"
    return {"phrase": r["phrase"], "common": r["common"], "total": len(how),
            "across": len(r["across"]), "english": len(r["english"]),
            "signature": {("Hebrew" if k == "h" else "Greek"): [x[1] for x in s]
                          for k, s in r["signature"].items()},
            "books": _by_book(d, how)}


def _tag_slug(t):
    """A tag's name as a record would carry it: "sacrifice_ev" -> sacrifice."""
    return _slug(re.sub(r"_ev$", "", str(t)).replace("_", " "))


_TAG_IX = None


def _tags_by_slug(d):
    """record-name slug -> the tag ids that read as that name (pinned clause
    tags and September section stamps alike)."""
    global _TAG_IX
    if _TAG_IX is None:
        ix = collections.defaultdict(set)
        for ts in _clause_tags().values():
            for t in ts:
                ix[_tag_slug(t["tag"])].add(t["tag"])
        for t in (d.get("stamp_secs") or {}):
            ix[_tag_slug(t)].add(t)
        _TAG_IX = ix
    return _TAG_IX


def tags_for_record(d, e):
    """TAGS AND CONCEPTS OF THE SAME NAME. 2026-09-28: where there are
    tags and concepts of the same name, the concept includes
    what the tagging reveals and the tag page links to
    the concept page. By the record's name and its aka, so an alias link
    ("an overseer" -> bishop) shows as what it is."""
    ix = _tags_by_slug(d)
    pinned = collections.Counter(t["tag"] for ts in _clause_tags().values() for t in ts)
    out = {}
    for nm in [e["name"]] + list(e.get("aka") or []):
        for t in ix.get(_slug(nm), ()):
            out[t] = {"id": t, "via": nm, "pinned": pinned.get(t, 0),
                      "stamped": len((d.get("stamp_secs") or {}).get(t, ()))}
    # A THING TAG FOLDED INTO THIS NODE (2026-09-30: fold into the
    # node), whatever its name: "suffering_servant" on the Servant role
    # pattern, "jonathan_and_david" on their covenant
    for t, v in _tag_crosswalk().items():
        if v.get("status") == "folded" and v.get("home") == e["id"]:
            for tid in (t, t + "_ev"):
                if tid not in out and (pinned.get(tid) or (d.get("stamp_secs") or {}).get(tid)):
                    out[tid] = {"id": tid, "via": v.get("label") or t, "pinned": pinned.get(tid, 0),
                                "stamped": len((d.get("stamp_secs") or {}).get(tid, ()))}
    return sorted(out.values(), key=lambda x: -(x["pinned"] * 10 + x["stamped"]))


_PAIR_JUDGMENTS = None


def _pair_judgments():
    """(verse, verse) sorted -> Flash's judgment of whether they say the
    same thing (tools/meaning/pair_judge.py). 2026-09-29, on the
    blind test that preceded it: of the matches the checklist kept, 22%
    were a clear yes and 32% no; shown only where Flash said same or
    partly, 1 in 26 was wrong. None when the run has not been made."""
    global _PAIR_JUDGMENTS
    if _PAIR_JUDGMENTS is None:
        p = OUT / "pair-judgments.jsonl.gz"
        _PAIR_JUDGMENTS = {tuple(sorted((r["a"], r["b"]))): r for r in _rows(p)} if p.exists() else {}
        # REVIEWED VERDICTS OVERRIDE THE MODEL'S. The 2026-10-02 evaluation
        # found two pairs Flash read as "saying the same" that do not (Job
        # 28:28 / Isa 59:15; 2 Sam 7:12 / 2 Kgs 20:21): a reading checked
        # against both verses is kept in ontology/pair-verdicts.jsonl and
        # wins, so a rebuilt pair-judgments file cannot bring them back.
        rv = ROOT / "ontology" / "pair-verdicts.jsonl"
        if rv.exists() and _PAIR_JUDGMENTS:
            for line in open(rv, encoding="utf-8"):
                if line.strip():
                    r = json.loads(line)
                    _PAIR_JUDGMENTS[tuple(sorted((r["a"], r["b"])))] = r
    return _PAIR_JUDGMENTS


_SECTION_STATUS = None


def _section_status():
    """(section, stamp) -> what the corpus run made of a September section
    stamp: "pinned" to clauses, "general" (the section's drift, no clause in
    particular), or "disputed" (Flash judged it wrong here, with a reason).
    2026-09-29: the section tags are not thrown away just because they
    did not hit nodes; in some cases they may apply better to sections."""
    global _SECTION_STATUS
    if _SECTION_STATUS is None:
        s = {}
        for r in _rows(OUT / "clause-tags.jsonl.gz"):
            if r.get("kind") == "stamp" and r.get("section"):
                s[(r["section"], r["tag"].removesuffix("_ev"))] = {"status": "pinned"}
        for r in _rows(OUT / "section-tags.jsonl"):
            k = (r["section"], r["tag"].removesuffix("_ev"))
            s.setdefault(k, {"status": r["status"], "reason": plain_reason(r.get("reason", ""))})
        _SECTION_STATUS = s
    return _SECTION_STATUS


def api_tag(d, q):
    """ONE TAG'S PAGE. 2026-09-28: tags are clickable on the clause
    level; clicking in shows the tag taxonomy and the books that
    include it, with a drill into the verses' assertions for the expanded
    book. Two sources, kept apart and labelled: the clauses a model PINNED
    the tag to (pass 2b, a pilot of sections), and the sections the 14
    September pass STAMPED with it (corpus-wide, never pinned to a clause,
    each citing one verse). Books in canon order."""
    tid = (q.get("id") or [""])[0]
    # A RETIRED THEME STAMP (2026-10-08) opens its theme: the same id, or
    # the theme the map matched it to (suffering_servant -> Messiah,
    # people_of_god -> Church); one with no theme says it is retired
    if tid in _theme_stamp_ids():
        by = _theme_map().get("_by") or {}
        home = tid if tid in by else next((t["id"] for t in by.values()
                                           if any(s.get("id") == tid for s in t.get("stamps") or [])), None)
        if home:
            return {"id": tid, "theme": home}
    canon = lambda b: _MCANON.get(b, 99)   # noqa: E731
    title = lambda b: TITLE.get(MACULA_BACK.get(b, b), b)   # noqa: E731
    # AN UNKNOWN TAG SKIPS THE WALK (2026-10-21, before the source went public;
    # the security seat, finding 3): it walked all 287,107 clause tags and
    # every stamped section to find nothing. The answer keeps its shape (a tag
    # with only a taxonomy entry still has a page), with nothing pinned.
    known = tid in _tag_ids(d)
    # pinned: every clause carrying the tag
    pinned = collections.defaultdict(list)
    for cid, ts in (_clause_tags().items() if known else ()):
        for t in ts:
            if t["tag"] != tid:
                continue
            v = cid.split("#")[0]
            eref, vtext = _verse_text(d, v)
            pinned[v.split(".")[0]].append({
                "clause": cid, "eref": eref, "text": t.get("text") or "",
                "verse": vtext, "strength": t["strength"], "reader": t.get("reader")})
    # stamped: every section the September pass gave it, with its cited verse
    stamped = collections.defaultdict(list)
    for sref in ((d.get("stamp_secs") or {}).get(tid, []) if known else ()):
        b_osis = sref.split(".")[0]
        b = TO_MACULA.get(b_osis, b_osis)
        for r in (d.get("stamp_by_sec") or {}).get(sref, []):
            if r["id"] != tid:
                continue
            cite = r.get("cites") or ""
            cm = _macula_ref(d, cite) if cite else None
            eref, vtext = _verse_text(d, cm) if cm else ("", "")
            st = _section_status().get((sref, tid.removesuffix("_ev"))) or {}
            stamped[b].append({"section": sref, "title": (d.get("sectitle") or {}).get(sref) or r.get("title") or "",
                               "cites": cite, "eref": eref, "verse": vtext,
                               "category": r.get("category"),
                               "corpus": st.get("status"), "reason": st.get("reason", "")})
            break

    def books(by):
        return [{"book": b, "title": title(b), "n": len(v),
                 "items": sorted(v, key=lambda x: [int(n) for n in (x.get("eref") or "0.0.0").split(".")[1:3]
                                                   if n.isdigit()] or [0])}
                for b, v in sorted(by.items(), key=lambda kv: canon(kv[0]))]
    # the record(s) of the same name: the tag page links to its concept
    records = [{"id": x, "name": d["ents"][x]["name"], "type": d["ents"][x]["type"]}
               for x in (d.get("alias_ix") or {}).get(_tag_slug(tid), ()) if x in d["ents"]]
    return {"id": tid, "taxonomy": _tag_taxonomy(tid), "records": records,
            "pinned": {"total": sum(len(v) for v in pinned.values()), "books": books(pinned)},
            "stamped": {"total": sum(len(v) for v in stamped.values()), "books": books(stamped)}}


_TAG_IDS = None


def _tag_ids(d):
    """Every tag id a tag page can show: pinned to a clause or stamped on a
    section. Built once."""
    global _TAG_IDS
    if _TAG_IDS is None:
        ids = {t["tag"] for ts in _clause_tags().values() for t in ts}
        ids.update((d.get("stamp_secs") or {}).keys())
        _TAG_IDS = ids
    return _TAG_IDS


_CLAUSE_TAGS = None


class ClauseTag:
    """ONE TAG ON ONE CLAUSE, READ LIKE THE DICT IT REPLACES (2026-10-14).
    The server sat at 2,973 MB under its 3 GB cap; the Patterns section's
    first request cost 512 MB, and 266 MB of it was these 287,107 tags,
    each a six-key dict. Slotted, each is a fraction of that; t["tag"] and
    t.get("reader") answer as before. Not JSON: a caller sending tags out
    uses as_dict(), and json.dumps raises on one sent bare, so a missed
    caller fails loudly instead of sending something else."""
    __slots__ = ("tag", "kind", "strength", "weight", "reader", "text")

    def __init__(self, tag, kind, strength, weight, reader, text):
        self.tag, self.kind, self.strength = tag, kind, strength
        self.weight, self.reader, self.text = weight, reader, text

    def __getitem__(self, k):
        if k not in ClauseTag.__slots__:
            raise KeyError(k)
        return getattr(self, k)

    def get(self, k, default=None):
        # every field is present, as every key was (a missing value is None)
        return getattr(self, k) if k in ClauseTag.__slots__ else default

    def as_dict(self):
        return {k: getattr(self, k) for k in ClauseTag.__slots__}


def _clause_tags():
    """clause id -> [ClauseTag(tag, kind, strength, weight, reader, text)],
    strongest first, from out/clause-tags.jsonl.gz (Flash's pass 2, 2026-09-28)."""
    global _CLAUSE_TAGS
    if _CLAUSE_TAGS is None:
        # one entry per (clause, tag), the stronger reading kept: Flash can
        # place the same name twice on a clause (as a stamp and as a concept —
        # Gen 22:2 "sacrifice" came out twice on the card)
        # ONE COPY OF EACH STRING (2026-10-01, docs/LAUNCH.md): every row
        # parsed into its own copy of the reader label and of its clause's
        # whole text, 280k times -- 420 MB. Interned, each distinct string is
        # held once; the records and their values are unchanged.
        si = sys.intern
        nums = {}                                 # one float object per weight
        best = {}
        # the theme stamps are retired here too (2026-10-08: "Retire
        # from view"): the 21 theme ids of the September taxonomy, as stamps;
        # a concept of the same name (the `judgment` node) stays
        retired = _theme_stamp_ids()
        # READ A LINE AT A TIME, not through _rows: _rows holds every parsed
        # row at once, and that list -- not the tags kept -- was most of the
        # cost (2026-10-14: 350 MB at the peak for 44 MB kept, and the process
        # does not hand the difference back)
        p = OUT / "clause-tags.jsonl.gz"
        for line in (gzip.open(p, "rt", encoding="utf-8") if p.exists() else ()):
            if not line.strip() or line.startswith('{"_'):
                continue
            r = json.loads(line)
            if any(k.startswith("_") for k in r):
                continue
            if r.get("kind") == "stamp" and r.get("tag") in retired:
                continue
            k = (r["clause"], r["tag"])
            if k not in best or (r.get("weight") or 0) > (best[k].get("weight") or 0):
                w = r.get("weight")
                best[k] = ClauseTag(*(si(v) if isinstance(v, str) else v
                                      for v in (r.get("tag"), r.get("kind"), r.get("strength"),
                                                nums.setdefault(w, w), r.get("reader"), r.get("text"))))
        by = collections.defaultdict(list)
        for (cid, _t), v in best.items():
            by[si(cid)].append(v)
        for v in by.values():
            v.sort(key=lambda x: -(x.get("weight") or 0))
        _CLAUSE_TAGS = {k: tuple(v) for k, v in by.items()}      # read-only, no spare slots
    return _CLAUSE_TAGS


# EXPLORE'S ANSWERS, COMPUTED ONCE (2026-10-01, the first hour of app2 live).
# The /ops report's first finding: /api/patternsets 11.9 s and the first
# card 10.7 s right after a restart, Explore's patterns 3.4 s and 8.2 s
# later. Locally, warm and one at a time, they cost 0.2-0.6 s -- but each was
# recomputed on every request (api_recurs even recomputes api_patternsets),
# and Explore asks for nine at once, which Python serves one at a time. Their
# answers cannot change while the server runs (the data is loaded at start),
# so the answer to the bare request is kept. Only the bare request: a query
# string would let anyone fill memory with variations, and Explore sends none.
# How long a browser or Cloudflare may reuse a page or an answer. Five
# minutes: long enough that a surge of readers opening the same things is
# served from Cloudflare, short enough that a deploy shows within minutes.
PUBLIC_TTL = 300
KEEP_ANSWERS = {"/api/books", "/api/collections", "/api/patternsets", "/api/recurs",
                "/api/lists", "/api/events", "/api/upper", "/api/majorthemes"}
_ANSWERS: dict = {}


# AND RECENT ANSWERS OF EVERY KIND (Fable's final review, 2026-10-01, M1):
# Python answers one request at a time on this box, so about ten a second of
# the heaviest kinds (Ps 119 is 660 KB; a word card ~120 ms) from one
# address would slow every reader. Every answer is a function of the path,
# the query and data that does not change while the server runs, so the
# most recent are kept -- bounded by BYTES, not count, so varied queries can
# only push older answers out, never grow memory past the cap.
_RECENT = collections.OrderedDict()
_RECENT_BYTES = 0
RECENT_CAP = 64 * 1024 * 1024     # bytes kept in all
RECENT_ONE = 2 * 1024 * 1024      # an answer larger than this is not kept
_RECENT_LOCK = threading.Lock()


# ONLY THE PARAMETERS A ROUTE READS (2026-10-21, before the source went
# public; the security seat, finding 3): the cache was keyed on the raw query,
# so "?nc=1" or any junk parameter missed it and was computed afresh. The names
# are read from this file's own source, so a new route's parameters join
# without a list to keep; the route is given the same filtered query its key
# names, so two requests that share a key can never get different answers.
_PARAMS = frozenset(
    re.findall(r"\bq(?:\.get\(|\[)[\"'](\w+)[\"']", Path(__file__).read_text(encoding="utf-8"))
    + re.findall(r"q(?:int|book|chapter)?\(q, [\"'](\w+)[\"']", Path(__file__).read_text(encoding="utf-8"))
    + ["b"])


def known_query(query):
    """The query with only the parameters some route reads, in a fixed order."""
    if not query:
        return query
    # sorted by name only: a repeated parameter keeps its values' order
    kept = sorted(((k, v) for k, v in parse_qsl(query, keep_blank_values=True) if k in _PARAMS),
                  key=lambda kv: kv[0])
    return urlencode(kept)


def answer(path, query):
    """A route's JSON body, as bytes, kept for KEEP_ANSWERS asked bare and
    for recent requests of any kind (bounded)."""
    global _RECENT_BYTES
    query = known_query(query)
    keep = path in KEEP_ANSWERS and not query
    if keep and path in _ANSWERS:
        return _ANSWERS[path]
    k = path + "?" + query
    with _RECENT_LOCK:
        hit = _RECENT.get(k)
        if hit is not None:
            _RECENT.move_to_end(k)
            return hit
    d, q = load(), parse_qs(query)
    # a card's name-made address (tools/card_slugs.py) names its record
    if q.get("id") and q["id"][0] in _slugs()[1]:
        q["id"] = [_card_id(q["id"][0])]
    if q.get("id") and q["id"][0] in d["renamed"]:
        q["id"] = [d["renamed"][q["id"][0]]]
    body = json.dumps(ROUTES[path](d, q), ensure_ascii=False)
    if path not in CREDIT_NAMED:
        body = scrub_credits(body)
    body = body.encode("utf-8")
    if keep:
        _ANSWERS[path] = body
    elif len(body) <= RECENT_ONE and path not in NOT_KEPT:
        # THE KEY COUNTS TOWARD THE CAP TOO (the security seat, 2026-10-22):
        # counted by the answer alone, a 2-byte answer under a 1 KB query
        # could be stored about 32 million times before anything was evicted
        with _RECENT_LOCK:
            if k not in _RECENT:
                _RECENT[k] = body
                _RECENT_BYTES += len(body) + len(k)
                while _RECENT_BYTES > RECENT_CAP and _RECENT:
                    old, b = _RECENT.popitem(last=False)
                    _RECENT_BYTES -= len(b) + len(old)
    return body


# the counting signals answer {} and are never worth keeping
NOT_KEPT = {"/api/open", "/api/seen"}


def _warm_structure():
    """Build what the first readers would otherwise build on first use: the
    structure view's chapter index, the word families, Explore's answers, a
    card, the concept index.

    BEFORE THE PORT OPENS, NOT BESIDE IT (2026-10-14: the
    splash was to stay up a little longer when this happens). This ran in a thread
    while the app was already answering, and the first readers raced it: a
    card took 26.7 s and another hit Caddy's 30 s limit, while a page that
    needed none of it took 0.37 s. Run first, it keeps the port closed, so
    Caddy shows "Back in a moment" for those seconds instead (11 s on the
    laptop, after the 12 s load). The theme pages, 60 s of it, still warm in
    the background after the port opens: _warm_themes."""
    global _STRUCTURE
    try:
        import importlib
        tdir = str(ROOT / "tools")
        if tdir not in sys.path:
            sys.path.insert(0, tdir)
        _STRUCTURE = _STRUCTURE or importlib.import_module("structure")
        _STRUCTURE.index()
        print("  structure index ready", flush=True)
    except Exception as e:           # the view still works, only slower
        print(f"  structure index not built: {e}", flush=True)
    # the word families' verse index (plan 5.10): 2 s on the first verse's
    # connections otherwise (Phil 4:11, measured 2026-10-01), a few ms after
    try:
        kin_verses(_data, "Php.4.11")
        print("  word-family index ready", flush=True)
    except Exception as e:                                   # noqa: BLE001
        print(f"  word-family index not built: {e}", flush=True)
    # Explore's answers, and a card, so the first reader after a restart does
    # not pay for every index built on first use (a card took 10.7 s then)
    try:
        for p in sorted(KEEP_ANSWERS):
            answer(p, "")
        api_entity(_data, {"id": ["jesus"]})
        api_echoes(_data, {"ref": ["Jhn.3.16"]})
        # and the indexes Fable's review found built on first use (L3):
        # a tag 1.2 s, a query 0.97 s, a chapter 0.62 s on a cold server
        api_tag(_data, {"id": ["chiasm"]})
        api_query(_data, {"filler": ["a"]})
        api_sequence(_data, {})
        api_chapter(_data, {"b": ["Gen"], "c": ["1"]})
        api_about(_data, {})
        # the indexes added 2026-10-03, each built by its first use otherwise:
        # the verse text for phrase searches, near spellings, the Patterns
        # sets, homographs (a word's patterns), the verse senses, the use
        # counts and the proper-name index (a card's name word)
        api_search(_data, {"q": ["hung on a tree"]})
        api_search(_data, {"q": ["Mosez"]})
        api_sense(_data, {"key": ["h5290"]})
        api_entity_verses(_data, {"id": ["image_temple"]})
        api_entity(_data, {"id": ["the_proud"]})
        print("  Explore's answers ready", flush=True)
    except Exception as e:                                   # noqa: BLE001
        print(f"  Explore's answers not prepared: {e}", flush=True)
    # the English renderings index every concept card's top half reads
    # (concept_face): 4.5 s once, not on a reader's first concept card
    try:
        _gloss_ix(_data)
        print("  concept cards ready", flush=True)
    except Exception as e:                                   # noqa: BLE001
        print(f"  concept cards not prepared: {e}", flush=True)


def _warm_themes():
    """THE THEME PAGES LAST (2026-10-08): each works out its headings' links
    once (_name_terms, searches), seconds per theme cold -- 60 s for all of
    them on the laptop. In the background once the port is open: holding the
    splash for them would keep every reader out for a page few open first."""
    try:
        for t in _theme_map().get("themes", []):
            api_majortheme(_data, {"id": [t["id"]]})
        print("  theme pages ready", flush=True)
    except Exception as e:                                   # noqa: BLE001
        print(f"  theme pages not prepared: {e}", flush=True)


ROUTES = {"/api/books": api_books, "/api/chapter": api_chapter,
          "/api/structure": api_structure,
          "/api/unit": api_unit, "/api/sense": api_sense,
          "/api/wordspace": api_wordspace,
          "/api/sense-verse": api_sense_verse,
          "/api/patternsets": api_patternsets, "/api/theme": api_theme,
          "/api/recurs": api_recurs, "/api/recur": api_recur,
          "/api/pattern-verse": api_pattern_verse,
          "/api/layeritem": api_layeritem,
          "/api/contrast": api_contrast,
          "/api/lists": api_lists,
          "/api/events": api_events,
          "/api/sequence": api_sequence,
          "/api/search": api_search, "/api/entity": api_entity,
          "/api/graph": api_graph,
          "/api/collections": api_collections,
          "/api/pattern": api_pattern, "/api/patterns": api_patterns_for,
          "/api/mined": api_mined, "/api/mined-verse": api_mined_verse,
          "/api/echoes": api_echoes, "/api/upper": api_upper, "/api/tag": api_tag,
          # a card section opened: answered empty, counted by app2/activity.py
          "/api/seen": lambda d, q: {},
          # the page's script has started: counts the visitor as a reader
          # (app2/activity.py, 2026-10-22); never cached, so it always arrives
          "/api/open": lambda d, q: {},
          "/api/majorthemes": api_majorthemes, "/api/majortheme": api_majortheme,
          "/api/imagery": api_imagery,
          "/api/question": api_question, "/api/questions": api_questions,
          "/api/tradition": api_tradition, "/api/traditions": api_traditions,
          "/api/verse-themes": api_verse_themes,
          "/api/entity-verses": api_entity_verses,
          "/api/verse": api_verse, "/api/query": api_query,
          "/api/about": api_about, "/api/coverage": api_coverage}

# THE TOOLS ARE NAMED ONCE, IN ABOUT. 2026-09-30: AI helps generate
# things but ultimately everything is sourced in the Bible; and the UI
# committee the same day found "DeepSeek Flash (corpus run, pass 2b,
# unreviewed)" on the verse panels. The model's name stays in the data (each
# reading's `reader`, its provenance); what a reader is shown says only that a
# model read it and whether anyone has reviewed it. Every route but About.
# NOT EVEN "A MODEL" (2026-10-16). The UI downplays AI: where AI was
# involved it says "Surfaced by
# automated analysis". What this rewrote to "a model" now reads "automated
# analysis", and the Claude models are rewritten too: they were left named
# because the app printed them itself ("a reading (Claude)").
CREDIT_SCRUB = [
    (re.compile(r"DeepSeek Flash \((?:corpus run, )?(?:pass [^,()]+|declared references|"
                r"pair judgment), unreviewed\)"), "automated analysis, unreviewed"),
    (re.compile(r"\(DeepSeek Flash, unreviewed\)"), "(automated analysis, unreviewed)"),
    (re.compile(r"\(DeepSeek (?:Flash|R\d+)\)"), "(automated analysis)"),
    (re.compile(r"two DeepSeek runs"), "two automated runs"),
    (re.compile(r"DeepSeek(?: Flash| V4 Pro| R\d+)?"), "automated analysis"),
    # Copilot the same way: the major themes and the major events are its
    # drafts, credited in About, and named on cards only as what they are.
    # Missed until the 2026-10-02 evaluation found 307 event lines reading
    # "the event, as Microsoft Copilot's event list names it" in search.
    (re.compile(r"(?:Microsoft )?Copilot's theme map"), "the major-theme map"),
    (re.compile(r"(?:Microsoft )?Copilot's event lists?"), "the major-event list"),
    (re.compile(r"(?:Microsoft )?Copilot's"), "an automated"),
    (re.compile(r"(?:Microsoft )?Copilot"), "automated analysis"),
    (re.compile(r"\(Claude(?: (?:Sonnet|Haiku|Opus))?, a reading\)"), "(surfaced by automated analysis)"),
    (re.compile(r"\bClaude (?:Code|Sonnet|Haiku|Opus)\b|\bClaude\b"), "automated analysis"),
    (re.compile(r"\ba model's (?:unreviewed )?reading\b"), "automated analysis"),
]
CREDIT_NAMED = {"/api/about"}

# NOR ANY PERSON. 2026-10-01: no one is personally named or quoted in the app
# outside the about page. The data keeps who read what
# (a reading's `reader` names the owner); what a page shows says "a reader", and
# a quotation of the owner is dropped with its attribution. Same shapes as
# tools/upper_ontologies.py UNNAME, held inside one JSON string ([^'"\\]).
UNNAME = [
    (re.compile(r"\s*\(Doug(?:, \d{4}-\d{2}-\d{2})?(?:, [^:()\"\\]*)?: '[^'\"\\]*'\)"), ""),
    (re.compile(r";\s*Doug(?:, \d{4}-\d{2}-\d{2})?: (?:'[^'\"\\]*'|[^)\"\\]*)(?=\))"), ""),
    # `\s*(?:[:—]\s*)?`, not `\s*[:—]?\s*`: two adjacent \s* split one run of
    # spaces every possible way, and a request echoing the name plus 2,000
    # spaces took 7.9 s (the security review, 2026-10-01)
    # (?<!\s): a match may start only where a run of spaces starts, or every
    # position inside the run is tried and fails -- still quadratic (8,000
    # spaces, 1.75 s) after the first fix
    (re.compile(r"(?<!\s)\s*(?:[:—]\s*)?Doug(?:, \d{4}-\d{2}-\d{2})?(?:, on [^,\"\\]+)?,? '[^'\"\\]*'"), ""),
    # the same with the words in double quotes, escaped inside the JSON string
    (re.compile(r"(?<!\s)\s*(?:[:—]\s*)?Doug(?:, \d{4}-\d{2}-\d{2})?: \\\"[^\"\\]*\\\""), ""),
    (re.compile(r"\bDoug Egge's\b|\bDoug's\b"), "a reader's"),
    (re.compile(r"\bDoug Egge\b|\bDoug\b"), "a reader"),
    (re.compile(r'"doug"'), '"a reader"'),
]


# THE CONTENT SECURITY POLICY (2026-10-01: go ahead with the CSP as
# well; the security review's medium finding). Scripts from this site only,
# plus the page's own inline script, named by the SHA-256 of its exact bytes
# -- computed from the file being served, so an edit can never leave a stale
# hash behind. No inline event handlers (the four the page had were moved
# into the script), no eval, no plugins, no framing, no other origin for
# fetch. Styles may be inline (the page and the diagram library both write
# them); styles and fonts otherwise come from this site only -- the fonts
# were moved off Google Fonts the same day (app2/VENDORED.md), so no other
# origin appears anywhere in the policy.
_CSP_CACHE: dict = {}


def csp_for(body: bytes) -> str:
    import base64
    import hashlib
    key = hashlib.sha256(body).hexdigest()
    if key not in _CSP_CACHE:
        # the browser hashes the script as parsed, and HTML parsing turns CR LF
        # and lone CR into LF -- a Windows checkout has CR LF on disk
        text = body.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        hashes = [base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode()
                  for m in re.finditer(rb"<script>(.*?)</script>", text, re.S)]
        _CSP_CACHE.clear()
        _CSP_CACHE[key] = "; ".join([
            "default-src 'self'",
            "script-src 'self' " + " ".join(f"'sha256-{h}'" for h in hashes),
            "style-src 'self' 'unsafe-inline'",
            "font-src 'self'",
            "img-src 'self' data:",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ])
    return _CSP_CACHE[key]


_RENAMES = None


def _theme_renames():
    """A THEME'S NEW NAME, EVERYWHERE IT IS SHOWN (plan 7.6b, P-2026-10-06-14;
    the Prophetic Word is to be renamed everywhere, including
    in the Apocalyptic card). The name Copilot drew is in the map, the
    theme's card, every concept's and event's note; the data keep it as
    drawn and the record of the rename is ontology/themes/theme-homes.json
    ("names"). Every reply is rewritten here, so no route can miss one. The
    id and address never change."""
    global _RENAMES
    if _RENAMES is None:
        _RENAMES = []
        for tid, n in (_theme_homes().get("names") or {}).items():
            words = [re.escape(w) for w in re.findall(r"[A-Za-z]+", n["was"])]
            # "Prophetic Word & Fulfillment", "&amp;", "and", Copilot's capitals;
            # "Messiah / Christology"
            pat = r"\b" + r"(?:\s*(?:&amp;|&|and|/)\s*|\s+)".join(words) + r"\b"
            _RENAMES.append((re.compile(pat, re.I), n["name"], n["was"].split()[0]))
    return _RENAMES


def scrub_credits(body: str) -> str:
    """The model names (CREDIT_SCRUB) and the owner's (UNNAME) out of what a
    reader is shown, and a renamed theme's old name (_theme_renames)."""
    if any(w in body for w in ("DeepSeek", "Copilot", "Claude", "a model's")):
        for pat, plain in CREDIT_SCRUB:
            body = pat.sub(plain, body)
    for pat, name, first in _theme_renames():
        if first.lower() in body.lower():
            body = pat.sub(name, body)
    if "Doug" in body or '"doug"' in body:
        for pat, plain in UNNAME:
            body = pat.sub(plain, body)
    return body


class Handler(BaseHTTPRequestHandler):
    # a connection that sends nothing, or reads slowly, gives up its thread
    # after this; without it ~60 idle sockets held every thread the unit
    # allows (TasksMax) and the site stopped answering (the security review)
    timeout = 20
    # no "BaseHTTP/0.6 Python/3.13" banner on every response
    server_version = "bibleontology"
    sys_version = ""

    def log_message(self, *a):        # quiet
        pass

    def _own_page(self, u, name, body, ctype, extra):
        """Answer one of the site's own addresses, or do nothing (the
        caller then serves the app page). Sets self._status when it answers."""
        # A CARD'S OWN PAGE (A.21): /e/<id> carries the card; an id that
        # is no card is a 404 with the app, so a search engine never keeps a
        # page for nothing. An old id (renamed or merged) is sent on to the
        # card it became, permanently. The script hashes stay those of the
        # app page: nothing injected runs.
        if u.path in ("/", "") and name == "index.html":
            head, home = home_page()
            extra["Cache-Control"] = self._public_cache()
            return self._send(200, with_card(body, head, home), ctype, extra)
        # THE NAVIGATOR CENTRED ON A RECORD: linkable, but the card is the
        # page search engines keep -- the same page as /e/<id>, whose
        # canonical names the card (2026-10-03: that is not to be
        # the dominant mode search engines use, as the cards answer
        # the direct questions much more thoroughly); never in the sitemap
        if u.path.rstrip("/") == "/about" and name == "index.html":
            head, page = about_page()
            extra["Cache-Control"] = self._public_cache()
            return self._send(200, with_card(body, head, page), ctype, extra)
        if u.path.rstrip("/") == "/graph" and name == "index.html":
            head, page = graph_page()
            extra["Cache-Control"] = self._public_cache()
            return self._send(200, with_card(body, head, page), ctype, extra)
        if u.path.startswith("/graph/") and name == "index.html":
            got = card_page(unquote(u.path[7:]).strip("/"))
            if got is None:
                return self._send(404, body, ctype, {**extra, "Cache-Control": "no-store"})
            head, card, _canon = got
            extra["Cache-Control"] = self._public_cache()
            return self._send(200, with_card(body, head, card), ctype, extra)
        if u.path.startswith("/explore/") and name == "index.html":
            got = explore_page(unquote(u.path[9:]).strip("/ "))
            if got is None:
                return self._send(404, body, ctype, {**extra, "Cache-Control": "no-store"})
            head, page, _canon = got
            extra["Cache-Control"] = self._public_cache()
            return self._send(200, with_card(body, head, page), ctype, extra)
        if u.path.startswith("/theme/") and name == "index.html":
            # THE OLD ADDRESSES (before 7.6d, 2026-10-08) move permanently
            new = _old_theme_path(unquote(u.path))
            if new is None:
                return self._send(404, body, ctype, {**extra, "Cache-Control": "no-store"})
            self.send_response(301)
            self.send_header("Location", quote(new) + (f"#{u.fragment}" if u.fragment else ""))
            self.end_headers()
            self._status = 301
            return
        if u.path.startswith("/themes/") and name == "index.html":
            tp = unquote(u.path[8:]).strip("/ ")
            # a theme, or its side-by-side table at /themes/<slug>/side-by-side
            slug_, _, sub = tp.partition("/")
            tid_ = _theme_addr()[1].get(slug_)
            got = None if tid_ is None else (
                (imagery_page(tid_) if sub == "side-by-side" else None) if sub else theme_page(tid_))
            if got is None:
                return self._send(404, body, ctype, {**extra, "Cache-Control": "no-store"})
            head, page, _canon = got
            extra["Cache-Control"] = self._public_cache()
            return self._send(200, with_card(body, head, page), ctype, extra)
        if u.path.startswith("/questions/") and name == "index.html":
            got = question_page(unquote(u.path[11:]).strip("/ "))
            if got is None:
                return self._send(404, body, ctype, {**extra, "Cache-Control": "no-store"})
            head, page, _canon = got
            extra["Cache-Control"] = self._public_cache()
            return self._send(200, with_card(body, head, page), ctype, extra)
        # THE TRADITIONS (2026-10-26): /traditions lists those the shown cards reach, /traditions/<slug> is one;
        # a tradition no shown card reaches answers 404, as does the list when there are none
        if u.path.rstrip("/") == "/traditions" and name == "index.html":
            got = traditions_index_page()
            if got is None:
                return self._send(404, body, ctype, {**extra, "Cache-Control": "no-store"})
            head, page, _canon = got
            extra["Cache-Control"] = self._public_cache()
            return self._send(200, with_card(body, head, page), ctype, extra)
        if u.path.startswith("/traditions/") and name == "index.html":
            got = traditions_page(unquote(u.path[12:]).strip("/ "))
            if got is None:
                return self._send(404, body, ctype, {**extra, "Cache-Control": "no-store"})
            head, page, _canon = got
            extra["Cache-Control"] = self._public_cache()
            return self._send(200, with_card(body, head, page), ctype, extra)
        if u.path.startswith("/p/") and name == "index.html":
            got = passage_page(unquote(u.path[3:]).strip("/ "))
            if got is None:
                return self._send(404, body, ctype, {**extra, "Cache-Control": "no-store"})
            if isinstance(got, str):
                self.send_response(301)
                self.send_header("Location", quote(got))
                self.end_headers()
                self._status = 301
                return
            head, page, _canon = got
            extra["Cache-Control"] = self._public_cache()
            return self._send(200, with_card(body, head, page), ctype, extra)
        if u.path.startswith("/word/") and name == "index.html":
            asked = unquote(u.path[6:]).strip("/ ")
            got = word_page(asked)
            if got is None:
                return self._send(404, body, ctype, {**extra, "Cache-Control": "no-store"})
            head, page, canon = got
            if canon != asked:
                self.send_response(301)
                self.send_header("Location", f"/word/{quote(canon)}")
                self.end_headers()
                self._status = 301
                return
            extra["Cache-Control"] = self._public_cache()
            return self._send(200, with_card(body, head, page), ctype, extra)
        if u.path.startswith("/e/") and name == "index.html":
            eid = unquote(u.path[3:]).strip("/")
            got = card_page(eid)
            if got is None:
                return self._send(404, body, ctype, {**extra, "Cache-Control": "no-store"})
            head, card, canon = got
            if canon != eid:
                self.send_response(301)
                self.send_header("Location", f"/e/{quote(canon)}")
                self.end_headers()
                self._status = 301
                return
            extra["Cache-Control"] = self._public_cache()
            return self._send(200, with_card(body, head, card), ctype, extra)

    def _public_cache(self):
        """Five minutes for the public site; nothing kept when the app is
        reached as localhost. 2026-10-02, testing the Mary note on a local
        server and still seeing the old one -- the server had the new
        note, the browser had kept the old answer for its five minutes. The
        public site is reached through Caddy under its own name, so this
        changes nothing there."""
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        if host in ("localhost", "127.0.0.1", "[::1]", "::1"):
            return "no-store"
        # STALE IF ERROR (2026-10-10, with the Cloudflare Cache Rule): if the
        # server answers an error -- a deploy's restart, a crash -- the edge may
        # serve its last good copy for up to an hour, so a deploy goes unseen
        # on any page read in that hour; caching buys some time during the
        # deploy. Purge only once the site is back (OPERATIONS).
        return f"public, max-age={PUBLIC_TTL}, stale-if-error=3600"

    def _send(self, code, body, ctype, headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------ the gate
    # Ported from app/server.py on 2026-10-01, for app2's private release
    # (docs/LAUNCH.md): app2 had no gate, so deploying it at all would have
    # been going public. Off unless an invite list exists, so a local
    # checkout runs open exactly as before.

    def _invite(self):
        """The invite behind this request, or None."""
        from bibleont import invites
        cookie = self.headers.get("Cookie") or ""
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name == invites.COOKIE:
                return invites.check(value)
        return None

    def _gate(self, u) -> bool:
        """True when the request may proceed. A token in the query is spent
        once: exchanged for an HttpOnly cookie, and the reader redirected to
        the same address without it, so it stops living in the address bar,
        the history and every referrer."""
        from bibleont import invites
        if not invites.enabled():
            return True
        if self._invite() is not None:
            return True
        token = (parse_qs(u.query).get("k") or [""])[0]
        found = invites.check(token)
        if found is not None:
            # back to the same page -- but only a plain path: "/\evil.example/"
            # would come back as a Location browsers read as another site
            # (the security review's open redirect)
            clean = u.path if re.fullmatch(r"/(?![/\\])[A-Za-z0-9_./-]*", u.path or "") else "/"
            rest = {k: v for k, v in parse_qs(u.query).items() if k != "k"}
            if rest:
                from urllib.parse import urlencode
                clean += "?" + urlencode(rest, doseq=True)
            secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
            self.send_response(302)
            self.send_header("Location", clean)
            self.send_header("Set-Cookie",
                             f"{invites.COOKIE}={found.token}; Path=/; Max-Age=31536000; "
                             f"HttpOnly; SameSite=Lax{secure}")
            self.end_headers()
            return False
        self._closed_door()
        return False

    def _closed_door(self) -> None:
        body = (
            "<!doctype html><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<meta name=robots content='noindex,nofollow'>"
            "<title>Bible Ontology &mdash; personal preview</title>"
            "<style>body{font:16px/1.6 system-ui,-apple-system,'Segoe UI',"
            "sans-serif;max-width:34em;margin:14vh auto;padding:0 1.2em;"
            "color:#1a1a19}h1{font-size:1.25em}p{color:#52514e}</style>"
            "<h1>This is a personal preview.</h1>"
            "<p>It is not open yet. If you were sent a link, open that link "
            "again &mdash; it carries the key, and it works on any device you "
            "own.</p>"
            "<p>If you have not been sent one, there is nothing here to see "
            "for the moment.</p>"
            "<p style='font-size:.85em'>Written to in error, or think you should have a link? "
            "<a href='mailto:bible.ontology@gmail.com'>bible.ontology@gmail.com</a></p>"
        ).encode("utf-8")
        self.send_response(403)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        # never kept anywhere: a cached closed door is an invite that looks
        # broken (2026-10-01, when Caddy's rule made it cacheable)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        """HEAD answers like GET without a body (uptime monitors send it;
        BaseHTTPRequestHandler answered 501). Only the gate's verdict and the
        status: nothing is built for a HEAD."""
        from bibleont import invites
        ok = (urlparse(self.path).path == "/healthz"       # the uptime check, outside the gate
              or not invites.enabled() or self._invite() is not None)
        self.send_response(200 if ok else 403)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def send_response(self, code, message=None):
        # the status, kept for the activity count (app2/activity.py)
        self._status = code
        super().send_response(code, message)

    def do_POST(self):
        """The one thing the site accepts: reader feedback (A.27). Every other
        POST is a 405, as it was when Caddy refused them all."""
        t0 = time.perf_counter()
        self._status = 0
        u = urlparse(self.path)
        try:
            self._feedback(u)
        finally:
            if ACTIVITY is not None and not self._uncounted():
                # the address and the status only -- never the note
                ACTIVITY.record(u.path, {}, self._status or 0, (time.perf_counter() - t0) * 1000,
                                self.headers.get("CF-Connecting-IP")
                                or (self.headers.get("X-Forwarded-For") or "").split(",")[0]
                                or self.client_address[0],
                                self.headers.get("User-Agent") or "", "",
                                self.headers.get("Host") or "")

    def _feedback(self, u):
        ok = lambda: self._send(200, b'{"ok":true}', "application/json")  # noqa: E731
        if u.path != "/api/feedback":
            return self._send(405, b"method not allowed", "text/plain")
        if not self._gate(u):
            return
        # from this site's own pages only: a form elsewhere cannot post here
        origin = urlparse(self.headers.get("Origin") or self.headers.get("Referer") or "")
        if (origin.hostname or "") not in FEEDBACK_HOSTS:
            return self._send(403, b'{"error":"not from this site"}', "application/json")
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._send(415, b'{"error":"json only"}', "application/json")
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0 or n > FEEDBACK_MAX_BODY:
            return self._send(413, b'{"error":"too long"}', "application/json")
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, UnicodeDecodeError):
            return self._send(400, b'{"error":"bad request"}', "application/json")
        if not isinstance(body, dict):
            return self._send(400, b'{"error":"bad request"}', "application/json")
        # the field a person never sees: filled means a bot -- thanked, dropped
        if str(body.get("website") or "").strip():
            return ok()
        text = str(body.get("text") or "").strip()
        if not text or len(text) > FEEDBACK_MAX_TEXT:
            return self._send(400, b'{"error":"say something, up to 1,000 characters"}',
                              "application/json")
        page = str(body.get("page") or "/")
        # a path on this site only: "//evil.example/x" starts with "/" and was
        # shown on /ops/feedback as a link off the site (security review,
        # 2026-10-19); the same shape the gate's redirect uses
        if len(page) > 300 or not re.fullmatch(r"/(?![/\\])\S*", page):
            page = "/"
        addr = (self.headers.get("CF-Connecting-IP")
                or (self.headers.get("X-Forwarded-For") or "").split(",")[0]
                or self.client_address[0])
        if not feedback_rate_ok(addr):
            return self._send(429, b'{"error":"thank you -- that is enough for now; try later"}',
                              "application/json")
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        save_feedback(text, page, str(body.get("title") or "")[:200],
                      str(body.get("device") or ""), host in ("localhost", "127.0.0.1"))
        return ok()

    def do_GET(self):
        """Every GET, counted once answered (app2/activity.py) -- except the
        /ops pages themselves, which are not reader activity."""
        import time
        t0 = time.perf_counter()
        self._status = 0
        u = urlparse(self.path)
        if u.path in ("/ops", "/ops.json", "/ops/feedback"):
            return self._ops(u)
        # THE UPTIME CHECK (2026-10-01: uptime alert first). Outside
        # the gate, so an outside monitor can tell "up" from "down" while the
        # site is invite-only -- the front page is a 403 either way. It says
        # "ok" and nothing else; when the app is down Caddy's "Back in a
        # moment" page answers instead, a 503, which the monitor reads as
        # down. Not counted as reader activity.
        if u.path == "/healthz":
            return self._send(200, b"ok", "text/plain", {"Cache-Control": "no-store",
                                                         "X-Robots-Tag": "noindex"})
        # THE NAMESPACE RESOLVES (plan 8.1, P-2026-10-10-3; 2026-10-10:
        # the upper ontology is what attribution is wanted for): every
        # class and property of the meaning layer -- bom: and the word layer's
        # bow:, both defined in meaning.ttl -- can be looked up at its address
        # ONE ADDRESS, TWO FORMS (2026-10-11): a browser gets the readable page
        # (tools/ns_docs.py), a tool gets Turtle; /ns/<name>.ttl and .html ask
        # for one outright. The bare address is not cached at the edge, since
        # Cloudflare keeps one copy per URL whatever the Accept header asked
        # for; the suffixed ones are.
        # .txt: the same Turtle as text/plain, so a browser shows it rather
        # than downloading it -- the page's "Turtle text" toggle
        # A RELEASE KEPT FOREVER (OWL evaluation Phase 0): /ns/<name>/<date> is
        # that release's owl:versionIRI, answered with the copy tools/
        # ns_freeze.py kept. And /ns/shapes: the closed-world checks, Turtle
        # only (no page of its own)
        # COUNTED (the committee's practitioner, W1, 2026-10-20): the /ns block
        # returned before the try/finally below that records activity, so the
        # vocabularies, the map and the alignment -- what the r/semanticweb
        # post sends readers to -- never reached /ops. It is a method now,
        # answered inside the counted path
        try:
            # _ns answers an /ns address (and returns None), or returns False
            if self._ns(u) is False:
                self._get(u)
        except CLIENT_GONE:
            # the reader hung up mid-answer (a page, a file): no traceback, 499
            self._status = 499
        finally:
            if ACTIVITY is not None and not self._uncounted():
                ACTIVITY.record(u.path, parse_qs(u.query) if len(u.query) <= MAX_QUERY else {},
                                self._status or 0, (time.perf_counter() - t0) * 1000,
                                self.headers.get("CF-Connecting-IP")
                                or (self.headers.get("X-Forwarded-For") or "").split(",")[0]
                                or self.client_address[0],
                                self.headers.get("User-Agent") or "",
                                self.headers.get("Referer") or "",
                                self.headers.get("Host") or "")

    def _ns(self, u):
        """The published ontology at /ns: answers the address if it is one of
        its, else returns False. (Moved out of do_GET so it is counted.)"""
        nsv = re.fullmatch(r"/ns/(meaning|word|relation|structure|claim|shapes|alignment)/(\d{4}-\d\d-\d\d)(\.ttl|\.txt)?/?",
                           u.path)
        if nsv:
            name = "meaning" if nsv.group(1) == "word" else nsv.group(1)
            p = OUT / "ns" / "versions" / f"{name}-{nsv.group(2)}.ttl"
            if not p.exists():
                return self._send(404, b"no such release", "text/plain", {"Cache-Control": "no-store"})
            return self._send(200, p.read_bytes(),
                              "text/plain; charset=utf-8" if nsv.group(3) == ".txt" else "text/turtle; charset=utf-8",
                              {"Cache-Control": self._public_cache(), "Access-Control-Allow-Origin": "*"})
        if re.fullmatch(r"/ns/shapes(\.ttl|\.txt|\.html)?/?", u.path):
            body = (OUT / "ns" / "shapes.ttl").read_bytes()
            plain = u.path.rstrip("/").endswith((".txt", ".html")) or \
                "text/html" in (self.headers.get("Accept") or "")
            return self._send(200, body, "text/plain; charset=utf-8" if plain else "text/turtle; charset=utf-8",
                              {"Cache-Control": "no-store" if u.path.rstrip("/") == "/ns/shapes" else self._public_cache(),
                               "Access-Control-Allow-Origin": "*", "Vary": "Accept"})
        # /ns/alignment (from 1.2.0, tools/ns_align.py): our terms mapped to
        # schema.org, FOAF, CIDOC CRM, OntoLex and Web Annotation; served as
        # the vocabularies are, and absent (404) until the release writes it
        # /ns/map (from 1.2.0, tools/ns_map.py): the schema as pictures, a page
        # only; absent (404) until the release writes it
        if re.fullmatch(r"/ns/map(\.html)?/?", u.path):
            p = OUT / "ns" / "map.html"
            if not p.exists():
                return self._send(404, b"not published yet", "text/plain", {"Cache-Control": "no-store"})
            body = p.read_bytes()
            return self._send(200, body, "text/html; charset=utf-8",
                              # one form only (no content negotiation), so the
                              # edge may keep it: the post sends readers here
                              # (the committee's practitioner, P5)
                              {"Cache-Control": self._public_cache(), "Content-Security-Policy": csp_for(body)})
        nsm = re.fullmatch(r"/ns/(meaning|word|relation|structure|claim|alignment)(\.ttl|\.html|\.txt)?/?", u.path)
        # both of its files, not only the Turtle: a missing page was a 500
        # (the committee's practitioner, W8)
        if nsm and nsm.group(1) == "alignment" and not all(
                (OUT / "ns" / f"alignment{x}").exists() for x in (".ttl", ".html")):
            return self._send(404, b"not published yet", "text/plain", {"Cache-Control": "no-store"})
        if nsm:
            name = "meaning" if nsm.group(1) == "word" else nsm.group(1)
            want = nsm.group(2) or ""
            if not want:
                acc = self.headers.get("Accept") or ""
                want = ".html" if "text/html" in acc and "turtle" not in acc else ".ttl"
            if want == ".html":
                body = (OUT / "ns" / f"{name}.html").read_bytes()
                return self._send(200, body, "text/html; charset=utf-8",
                                  {"Cache-Control": self._public_cache() if nsm.group(2) else "no-store",
                                   "Content-Security-Policy": csp_for(body), "Vary": "Accept"})
            # all three are the published copies in out/ns: tools/ns_meaning.py,
            # ns_relation.py, ns_structure.py. The meaning layer's working file
            # (ontology/meaning/meaning.ttl) keeps its history in comments that
            # name files and dated rulings, and is not served (2026-10-14)
            ttl = (OUT / "ns" / f"{name}.ttl").read_bytes()
            return self._send(200, ttl, "text/plain; charset=utf-8" if want == ".txt" else "text/turtle; charset=utf-8",
                              {"Cache-Control": self._public_cache() if nsm.group(2) else "no-store",
                               "Access-Control-Allow-Origin": "*", "Vary": "Accept"})
        return False

    # ------------------------------------------------------------ /ops
    # The activity report (app2/activity.py; 2026-10-01). Its own token,
    # never an invite's; without it, a 404 like any path that does not exist.
    # Read-only: it serves no control of any kind.

    def _uncounted(self):
        """THE SITE'S OWN BROWSERS ARE NOT COUNTED (2026-10-22: the browsers
        that open /ops should not be in its stats). Opening /ops sets
        UNCOUNTED, a site-wide cookie with no secret in it: the /ops token
        stays on Path=/ops, so it never reaches the counted pages. Anyone could
        set it, and it only ever leaves out their own visits. Read here and
        never kept."""
        return any(part.strip().partition("=")[0] == UNCOUNTED
                   for part in (self.headers.get("Cookie") or "").split(";"))

    def _uncounted_cookie(self, secure):
        return f"{UNCOUNTED}=1; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax{secure}"

    def _ops(self, u):
        import activity
        given = None
        auth = self.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            given = auth[7:].strip()
        for part in (self.headers.get("Cookie") or "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == "bo_ops":
                given = given or value
        k = (parse_qs(u.query).get("k") or [""])[0]
        if k and activity.ops_ok(k):
            # the link's token, spent once for a cookie, as an invite is
            secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
            self.send_response(302)
            self.send_header("Location", u.path)
            # SameSite=LAX, not Strict (2026-10-06). A phone answered
            # "not found" after a good setup: Safari withholds a Strict cookie
            # when /ops is opened from outside the site (a synced bookmark, a
            # link in Notes or Messages, a home-screen icon), and without the
            # cookie /ops is a 404 by design. Lax is sent on a top-level GET
            # from anywhere and never on another site's background requests;
            # /ops is read-only and serves no control, so nothing a forged
            # navigation could do with it
            self.send_header("Set-Cookie", f"bo_ops={k}; Path=/ops; Max-Age=31536000; "
                                           f"HttpOnly; SameSite=Lax{secure}")
            self.send_header("Set-Cookie", self._uncounted_cookie(secure))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if ACTIVITY is None or not activity.ops_ok(given):
            return self._send(404, b"not found", "text/plain")
        days = 7
        try:
            days = max(1, min(int((parse_qs(u.query).get("days") or ["7"])[0]), 90))
        except ValueError:
            pass
        rep = ACTIVITY.report(days)
        common = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"}
        if not self._uncounted():
            # a browser that already held the /ops cookie before UNCOUNTED
            # existed gets it on its next visit, with no new link needed
            common["Set-Cookie"] = self._uncounted_cookie(
                "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else "")
        if u.path == "/ops/feedback":
            # READER FEEDBACK, ITS OWN PAGE (2026-10-03: a /feedback
            # link would suffice, but an indicator of recent
            # feedback in ops, with a link, would also be handy). Under /ops so
            # the same token and cookie open it. Newest first, no read state.
            return self._send(200, ops_feedback_page().encode("utf-8"), "text/html; charset=utf-8",
                              {**common, "Content-Security-Policy":
                               "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"})
        if u.path == "/ops.json":
            # reader feedback too, newest first, so the report tool can show it
            # (fenced there, as readers' words); never in /ops.json's counts
            rep = {**rep, "feedback": ops_feedback_rows()}
            return self._send(200, json.dumps(rep, ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8", common)
        # ?day=YYYY-MM-DD picks the day the hourly charts show; anything else
        # is ignored (it names a file, so only the date's own shape passes)
        day = (parse_qs(u.query).get("day") or [""])[0]
        day = day if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) else ""
        sel = ACTIVITY.one_day(day) if day else None
        return self._send(200, ops_page(rep, day, sel).encode("utf-8"), "text/html; charset=utf-8",
                          {**common, "Content-Security-Policy":
                           "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"})

    def _get(self, u):
        if not self._gate(u):
            return
        if u.path in WORKING_PAGES and not DEV:
            return self._send(404, b"not found", "text/plain")
        if len(u.query) > MAX_QUERY or len(u.path) > MAX_QUERY:
            return self._send(414, b"request too long", "text/plain")
        # THE VERSE TREE, AS A PAGE. 2026-09-21: give a verse and see the
        # tree structure -- in fact this should be a standard capability of the
        # UI -- and show it like a graph.
        #
        # It is the instrument for the verse-by-verse pass, which does not
        # move on until the sentence-level structure is right --
        # so it belongs on a URL rather than in a scratch file. The graph of
        # what we extracted is drawn first and MACULA's own constituents
        # underneath it, because the question is always whether the second
        # produced the first.
        if u.path == "/suite":
            # THE WHOLE SUITE ON ONE PAGE, newest first. 2026-09-21:
            # a visualization that shows the whole suite at once, in
            # reverse order of when each was taken on, with the top diagram
            # and the verse being worked from as all that is needed for each.
            try:
                import importlib
                tdir = str(ROOT / "tools")
                if tdir not in sys.path:
                    sys.path.insert(0, tdir)
                vt = importlib.import_module("versetree")
                importlib.reload(vt)
                page = vt.suite_page()
            except Exception as ex:                          # noqa: BLE001
                page = (f"<!doctype html><meta charset='utf-8'>"
                        f"<body style='font:15px system-ui;padding:24px'>"
                        f"suite: {_esc(str(ex))}")
            return self._send(200, page.encode("utf-8"),
                              "text/html; charset=utf-8")
        if u.path == "/ontology":
            # THE ONTOLOGY, AS IT IS BUILT. 2026-09-24: build it out and make it
            # visible as structures are discovered working through verse by
            # verse. Every kind with its live count,
            # the verse that made it necessary, and whether the graph and
            # ontology/kinds.json agree.
            try:
                import importlib
                tdir = str(ROOT / "tools")
                if tdir not in sys.path:
                    sys.path.insert(0, tdir)
                on = importlib.import_module("ontology")
                importlib.reload(on)
                page = on.page()
            except Exception as ex:                          # noqa: BLE001
                page = (f"<!doctype html><meta charset='utf-8'>"
                        f"<body style='font:15px system-ui;padding:24px'>"
                        f"ontology: {_esc(str(ex))}")
            return self._send(200, page.encode("utf-8"),
                              "text/html; charset=utf-8")
        if u.path == "/plan":
            # THE PLAN, docs/PLAN.md, drawn. 2026-09-25: an expanded version of the
            # plan, readable on demand. Re-read on every request, so the page is the file.
            try:
                import importlib
                tdir = str(ROOT / "tools")
                if tdir not in sys.path:
                    sys.path.insert(0, tdir)
                pl = importlib.import_module("plan")
                importlib.reload(pl)
                page = pl.page()
            except Exception as ex:                          # noqa: BLE001
                page = (f"<!doctype html><meta charset='utf-8'>"
                        f"<body style='font:15px system-ui;padding:24px'>"
                        f"plan: {_esc(str(ex))}")
            return self._send(200, page.encode("utf-8"),
                              "text/html; charset=utf-8")
        if u.path == "/passage":
            # A PASSAGE AT THE CLAUSE LEVEL, typed by the ontology.
            # 2026-09-24: the frog plague graph, leveraging the
            # ontology. Defaults to the frog plague, Hebrew 7:26-8:11.
            q = parse_qs(u.query)
            a = (q.get("from") or ["Exo.7.26"])[0].strip()
            b = (q.get("to") or ["Exo.8.11"])[0].strip()
            try:
                import importlib
                tdir = str(ROOT / "tools")
                if tdir not in sys.path:
                    sys.path.insert(0, tdir)
                on = importlib.import_module("ontology")
                importlib.reload(on)
                # passage draws each verse with versetree, so a stale copy of
                # it here serves the old drawing (or fails on a new argument)
                importlib.reload(importlib.import_module("versetree"))
                pg = importlib.import_module("passage")
                importlib.reload(pg)
                page = pg.page(a, b)
            except Exception as ex:                          # noqa: BLE001
                page = (f"<!doctype html><meta charset='utf-8'>"
                        f"<body style='font:15px system-ui;padding:24px'>"
                        f"passage {_esc(a)}–{_esc(b)}: {_esc(str(ex))}")
            return self._send(200, page.encode("utf-8"),
                              "text/html; charset=utf-8")
        if u.path == "/tree":
            ref = (parse_qs(u.query).get("ref") or [""])[0].strip()
            try:
                import importlib
                tdir = str(ROOT / "tools")
                if tdir not in sys.path:
                    sys.path.insert(0, tdir)
                vt = importlib.import_module("versetree")
                importlib.reload(vt)
                (ws, rtl, spans, nrows, arcs,
                 edges, cls, cof) = vt.build(ref)
                nodes, _ = vt.our_graph(ref)
                loose = sum(1 for e in edges if vt.is_lost(e))
                page = vt.page(ref,
                               vt.mermaid(ref, nodes, edges, cls, cof),
                               vt.verse_block(ref, ws),
                               vt.svg(ref, ws, rtl, spans, nrows, arcs),
                               loose, len(edges),
                               vt.mermaid_built(ref))
            except Exception as ex:                          # noqa: BLE001
                page = (f"<!doctype html><meta charset='utf-8'>"
                        f"<body style='font:15px system-ui;padding:24px'>"
                        f"<b>{_esc(ref)}</b>: {_esc(str(ex))}"
                        f"<p>Try <code>/tree?ref=Exo.8.6</code></p>")
            return self._send(200, page.encode("utf-8"),
                              "text/html; charset=utf-8")
        if u.path in ROUTES:
            try:
                body = answer(u.path, u.query)
                # CACHEABLE FOR FIVE MINUTES, and only a success (Fable's final
                # review, M1: before a Reddit post, repeat answers should be
                # served by Cloudflare, not this one process). Every answer is
                # the same for everyone and fixed between deploys; an error
                # (400, 500) carries no such header and is never kept.
                # never listed by a search engine: robots.txt stops crawling,
                # but a disallowed address linked from elsewhere can still be
                # listed by its address alone (A.21, noindex off at the edge)
                # /api/open must reach the server every time: Cloudflare's rule
                # follows the answer's own header, and no-store keeps it out
                return self._send(200, body, "application/json; charset=utf-8",
                                  {"Cache-Control": "no-store" if u.path == "/api/open" else self._public_cache(),
                                   "X-Robots-Tag": "noindex"})
            except BadQuery:
                # a malformed query ("c=abc", a book that is not one): the
                # reader's mistake, not the server's -- a 400, and no
                # traceback in the journal for every bad request. ONLY that:
                # any other error is the server's and falls through to the
                # 500 below, with its traceback (plan A.24, 2026-10-02).
                body = json.dumps({"error": "bad request"}).encode()
                return self._send(400, body, "application/json")
            except CLIENT_GONE:
                # THE READER LEFT, NOT THE SERVER FAILING. Found 2026-10-03
                # from three "500"s on /ops: each was a good answer being
                # written when the reader's end hung up (a reload, a closed
                # tab, a deploy restart). The catch-all below took that for a
                # server error, wrote a traceback, tried to send a 500 down
                # the dead connection, and /ops counted it. Now: nothing sent,
                # nothing logged, counted as 499 ("client closed").
                self._status = 499
                return
            except Exception:                                # noqa: BLE001
                # the reason goes to the service log, never to the client: an
                # exception's text names files, calls and paths (docs/LAUNCH.md)
                import traceback
                traceback.print_exc()
                body = json.dumps({"error": "something went wrong"}).encode()
                return self._send(500, body, "application/json")
        # APP1'S ADDRESSES KEEP WORKING (2026-10-01: done so it
        # does not break first). Invitees hold links to app1's cards and
        # passages, /e/<id> and /p/<ref>; they get the app, which opens what
        # the address names (the boot script in index.html). A.21 gave these
        # addresses pages of their own (card_page, passage_page), and
        # /theme/<id> joined them.
        legacy = u.path.startswith(("/e/", "/p/", "/word/", "/theme/", "/themes/", "/graph/", "/explore/",
                                    "/questions/", "/traditions/")) or \
            u.path.rstrip("/") in ("/graph", "/about", "/traditions")
        # what the site is, for language models (the /llms.txt convention):
        # the About view's own principles and sources, and the address shapes
        if u.path == "/llms.txt":
            return self._send(200, llms_txt().encode("utf-8"), "text/plain; charset=utf-8",
                              {"Cache-Control": self._public_cache()})
        name = "index.html" if u.path in ("/", "") or legacy else u.path.lstrip("/")
        # THE BLOG (2026-10-05): pages built by tools/blog_build.py from
        # docs/blog/posts; /blog/ is the list, /blog/<slug> a post. The slug's
        # own shape only, so nothing else under static/ is reachable this way
        if u.path.rstrip("/") == "/blog":
            name = "blog/index.html"
        elif u.path.rstrip("/") == "/faq":              # tools/blog_build.py, from docs/faq.md
            name = "faq.html"
        elif re.fullmatch(r"/blog/[a-z0-9-]{1,120}/?", u.path):
            name = f"blog/{u.path.rstrip('/').rsplit('/', 1)[1]}.html"
        # NOTHING OUTSIDE static/. Found 2026-10-01 while planning the launch:
        # `GET /../server.py` returned this file and a private document under docs/
        # (via `/../../docs/`) -- anything the service account could read, to anyone
        # sending a raw request (a browser normalises "..", curl --path-as-is
        # does not). app/server.py had this guard; app2 never got it.
        f = (STATIC / name).resolve()
        if not f.is_relative_to(STATIC.resolve()) or not f.is_file():
            return self._send(404, b"not found", "text/plain")
        # ONLY THE KINDS OF FILE THE SITE IS MADE OF (2026-10-01, the
        # supply-chain review: static/vendor/README.md was readable, naming
        # the owner). Anything else under static/ is a 404, as if absent.
        ctype = {".html": "text/html; charset=utf-8", ".css": "text/css",
                 ".js": "application/javascript", ".woff2": "font/woff2"}.get(f.suffix)
        # AND THE LICENCES THAT MUST GO WITH WHAT IS SHIPPED (2026-10-18): the
        # fonts' SIL Open Font License and Mermaid's MIT licence, served beside
        # their files as the licences ask. Only a .txt under vendor/ whose name
        # says it is a licence; the rule above stands for everything else.
        # (NOTICE had said the Mermaid licence was served; it was a 404.)
        if ctype is None and f.suffix == ".txt" and \
                re.fullmatch(r"vendor/(?:[\w.-]+/)?[\w.-]*(?:LICENSE|OFL)[\w.-]*\.txt", name):
            ctype = "text/plain; charset=utf-8"
        if ctype is None:
            return self._send(404, b"not found", "text/plain")
        body = f.read_bytes()
        extra = {"Content-Security-Policy": csp_for(body)} if f.suffix == ".html" else {}
        # THE SITE'S OWN PAGES (A.21) -- built inside a guard: a page that
        # failed to build would otherwise drop the connection, and the reader
        # would get "Back in a moment" for that one address. Instead the
        # failure is logged and the reader gets the app, which works without
        # the page's own copy (found in the 2026-10-03 security look).
        if name == "index.html":
            try:
                self._own_page(u, name, body, ctype, dict(extra))
            except CLIENT_GONE:
                self._status = 499                             # the reader left (see above)
                return
            except Exception:                                  # noqa: BLE001
                import traceback
                traceback.print_exc()
            if self._status:
                return
        # A VENDORED FILE IS CACHED FOR A YEAR -- BUT ONLY WHEN IT IS SENT.
        # This was Caddy's job (@vendor), and Caddy set it on every answer,
        # the invite gate's 403 included. Found 2026-10-01 by the external
        # probe: a request without an invite got a 403 for the body font and
        # for Mermaid, Cloudflare kept both as "immutable, a year", and every
        # reader at those Cloudflare locations would have been served the
        # 403 instead of the file. Set here, it can only go on a 200: a
        # vendored file's name carries its version, so it never changes.
        if name.startswith("vendor/"):
            extra["Cache-Control"] = "public, max-age=31536000, immutable"
        elif name == "index.html":
            # the page, for five minutes once it is public (Fable, M2); set
            # here so only a 200 carries it -- Caddy's rule had put it on the
            # gate's 403 too
            extra["Cache-Control"] = self._public_cache()
        return self._send(200, body, ctype, extra)


ACTIVITY = None      # app2/activity.py's counter, set by main(), never on import


# A CARD AT ITS OWN ADDRESS (plan A.21). 2026-10-03: getting
# that process of showing up in search engines started means focusing
# on deep links first. The app draws every card by script, so a search engine
# -- or a reader whose browser runs none -- fetching /e/<id> got an empty
# shell. Now the address answers with the app page carrying the card itself:
# its name, what it is, its verses in the Berean's words and its connections
# as plain links, under a title phrased the way people ask (P-95: "Forgiveness
# in the Bible: every verse and connection"). The app hides this copy and
# draws the card as it always has, so a reader of the app sees no change --
# the question-shaped wording lives only in the browser tab and the search
# result (a subtitle can say all that).
SITE = "https://bibleontology.org"
CARD_VERSES = 12          # verses quoted on the page; the app shows them all
CARD_LINKS = 60           # connections listed; the app shows them all
CARD_SPEAKS = 25          # "Where the text speaks of it" quoted on the page; the app shows them all
EVENT_VERSES = 60         # an event's passage quoted on its page, across its tellings
EVENT_TELLINGS = 4        # the tellings quoted (a gospel event is told up to four times)
PERSON_EVENT_VERSES = 25  # of each event a person's page quotes (the card's first EVENT_TELLINGS events)


def _plain(s):
    """Card prose without the app's light markdown (**bold**, [x](y), and the
    [[id]] card links, which the page shows as the id in words: until
    2026-10-23 the server-rendered page, the one search engines read, showed
    them raw, on 21 cards)."""
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s or "")
    s = re.sub(r"\[\[([a-z0-9_]+)\]\]", lambda m: m.group(1).replace("_", " "), s)
    return re.sub(r"\*\*|__|`", "", s).strip()


def _open_btn(href, label):
    """The way into the app, first under the heading. 2026-10-03, of
    the John 3:16 page: "open in reader" needs to be prominent. The
    address is the page's own: with the app running it opens the reader (or
    the card) at that place."""
    return f'<p><a class="ssr-open" href="{_esc(href)}">{_esc(label)} →</a></p>'


_SLUGS = None


def _slugs():
    """({id: address}, {address: id}) for the cards whose id misleads
    (tools/card_slugs.py: /e/the_proud is Rahab, now /e/rahab_job_26_12)."""
    global _SLUGS
    if _SLUGS is None:
        p = OUT / "card-slugs.json"
        fwd = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        _SLUGS = (fwd, {v: k for k, v in fwd.items()})
    return _SLUGS


def _addr(eid):
    """A card's public address: its name-made one where its id misleads."""
    return _slugs()[0].get(eid, eid)


def _card_id(x):
    """The record a card address names: an address made from a name, or an id."""
    return _slugs()[1].get(x, x)


def card_page(eid):
    """(head, body, canonical address) for a card, or None when there is none.
    Built from the same answer the app gets, credits scrubbed the same way.
    The address is the card's own (_addr): an old id that misleads is sent
    there permanently by the caller, which compares it with what was asked."""
    d = load()
    eid = _card_id(eid)
    eid = d["renamed"].get(eid, eid)
    if eid not in d["ents"]:
        # ANOTHER NAME OPENS ITS CARD (a reader, 2026-10-13: "/e/jerubbaal
        # returns a 404. Someone searching 'Jerubbaal' would find nothing" --
        # Gideon carries it as `aka`). Only where the name is one record's,
        # so a shared name never sends a reader to the wrong one; the caller
        # answers 301 to that record's own address
        hits = [x for x in d["alias_ix"].get(_slug(eid.replace("_", " ")), ()) if x in d["ents"]]
        if len(set(hits)) != 1:
            return None
        eid = hits[0]
    # a record consolidated into an event (ontology/aliases.jsonl) answers
    # with the event's card; the caller sends the old address on (301)
    eid = d["ents"][eid].get("alias_of") or eid
    c = json.loads(answer("/api/entity", urlencode({"id": eid})))
    if not c.get("found"):
        return None
    name = c.get("name") or eid
    big = name[:1].upper() + name[1:]
    desc = _plain(c.get("desc"))
    first = re.split(r"(?<=[.!?])\s", desc.split("\n")[0])[0] if desc else ""
    n_refs, n_rel = len(c.get("refs") or []), c.get("total_relations") or 0
    # THE VERSES THE CARD SHOWS, not the record's own citations: the temple's
    # summary said "10 verses" over a card of 583 (the committee's falsifier,
    # 2026-10-23). The same answer the app's "Where the text speaks of it" gets;
    # a person's card is built from citations, so the larger of the two
    ev = {}
    try:
        ev = json.loads(answer("/api/entity-verses", urlencode({"id": eid})))
        n_refs = max(n_refs, ev.get("total") or 0)
    except (ValueError, KeyError, TypeError):
        pass
    title = f"{big} in the Bible: every verse and connection"
    summary = (first + " " if first else "") + \
        f"{n_refs} verse{'s' * (n_refs != 1)} and {n_rel} connection{'s' * (n_rel != 1)} " \
        f"in the text, each with its scripture."
    summary = summary[:300]
    verses = []
    for r in (c.get("refs") or [])[:CARD_VERSES]:
        eref, text = _verse_text(d, _macula_ref(d, r))
        if text:
            # THE VERSE PAGE'S OWN ADDRESS, not the dataset's book code: the
            # Berean numbering came back with MACULA's code ("1Ch.10.14"), so
            # every verse link on a card answered 301 to "/p/1Chr.10.14" -- 926
            # redirects to AhrefsBot in a few hours (2026-10-05), crawl spent
            # on bounces and each verse at two addresses
            b, _, cv = eref.partition(".")
            verses.append(f'<li><a href="/p/{_esc(MACULA_BACK.get(b, b))}.{_esc(cv)}">{_esc(r)}</a> '
                          f'{_esc(text)}</li>')
    # WHERE THE TEXT SPEAKS OF IT, in the page a search engine reads (2026-10-25). The card's verses loaded only in
    # the app, after its script ran, so "the hand of God" read to Google as 144 words and one verse over a card of
    # 457. The first CARD_SPEAKS of them, in the order the card lists them and not those already quoted above, each
    # with its text and its verse page; then how many more the app shows.
    # A card named for a phrase lists the verses with its phrase first ("the hand of the LORD"): until plan 8.2k
    # narrows such cards to their own figure, the rest can be any figurative use of the word ("delivered into your
    # hand", Gen 9:2), and those are not what the page should open with.
    shown = {v.split('href="/p/', 1)[1].split('"', 1)[0] for v in verses}
    # AN EVENT'S PASSAGE, quoted (2026-10-25). An event card cites only where its telling starts, so the prodigal son
    # read to Google as 185 words and Luke 15:11 alone, over a parable of 22 verses -- one of the pages people were
    # searching for. Each telling (at most EVENT_TELLINGS) quoted in full, EVENT_VERSES in all; tellings are in
    # MACULA's numbering, read in the Berean's (bsb_ref), as everywhere a telling's text is read.
    passage, left = [], EVENT_VERSES

    in_passage = set()

    def quote_telling(tl, heading, limit, skip_quoted=False):
        nonlocal left
        try:
            fb, fc, fv = bsb_ref(d, tl["first"]).split(".")
            _lb, lc, lv = bsb_ref(d, tl["last"]).split(".")
            fc, fv, lc, lv = int(fc), int(fv), int(lc), int(lv)
        except (ValueError, KeyError, AttributeError, TypeError):
            return
        bk, items = MACULA_BACK.get(fb, fb), []
        for ch in range(fc, lc + 1):
            for vn in range(fv if ch == fc else 1, (lv if ch == lc else 200) + 1):
                t = d["verses"].get((bk, ch, vn))
                if skip_quoted and f"{bk}.{ch}.{vn}" in in_passage:
                    continue  # two of a person's events overlap (Job 1:1-2:13 holds Job 1:13-22)
                if t and left > 0 and len(items) < limit:
                    items.append(f'<li><a href="/p/{_esc(bk)}.{ch}.{vn}">{ch}:{vn}</a> {_esc(t)}</li>')
                    shown.add(f"{bk}.{ch}.{vn}")
                    in_passage.add(f"{bk}.{ch}.{vn}")
                    left -= 1
        if items:
            passage.append(f"<h2>{heading}</h2><ul>{''.join(items)}</ul>")

    for tl in ((c.get("event") or {}).get("tellings") or [])[:EVENT_TELLINGS]:
        quote_telling(tl, _esc(tl.get("label") or ""), EVENT_VERSES)
    # A SAYING'S OWN WORDS (attrs.passages, 2026-10-25). The Ten Commandments' card cited where God begins to speak
    # (Exod 20:1) and where the text names them (34:28), and never the commandments: 344 words, on a page searched
    # for 41 times. The span of the saying itself, in the site's book codes, quoted as a telling is.
    for p_ in ((d["ents"][eid].get("attrs") or {}).get("passages") or [])[:EVENT_TELLINGS]:
        quote_telling(p_, _esc(p_.get("label") or ""), EVENT_VERSES)
    # A PERSON'S EVENTS, quoted the same way (Nicodemus: 221 words and two verses, over a night conversation of
    # 21). Each event's first telling, under the event's name and linked to its card; a long telling is cut at
    # PERSON_EVENT_VERSES, and the reader follows the link for the rest.
    # The card's own first events (its order is its priority: Jesus's opens with his trial, the Last Supper and the
    # crucifixion), shown in the order the text tells them (Abraham's page opened with Genesis 24 before Genesis 15).
    # Sorting more than those first and keeping four dropped the crucifixion for Jairus' daughter.
    if not c.get("event"):
        mine = []
        for e_ in (c.get("events") or [])[:EVENT_TELLINGS]:
            try:
                ec = json.loads(answer("/api/entity", urlencode({"id": e_["id"]})))
                tl = ((ec.get("event") or {}).get("tellings") or [])[0]
                b0, c0, v0 = bsb_ref(d, tl["first"]).split(".")
                at = (ORDER.index(MACULA_BACK.get(b0, b0)), int(c0), int(v0))
            except (ValueError, KeyError, TypeError, IndexError, AttributeError):
                continue
            mine.append((at, e_, ec, tl))
        for _at, e_, ec, tl in sorted(mine, key=lambda x: x[0]):
            quote_telling(tl, f'<a href="/e/{_esc(_addr(e_["id"]))}">{_esc(ec.get("name") or e_.get("name") or "")}'
                              f'</a> ({_esc(tl.get("label") or "")})', PERSON_EVENT_VERSES, skip_quoted=True)
    if passage:  # a cited verse the passage already quotes is not quoted twice
        quoted = {i.split('href="/p/', 1)[1].split('"', 1)[0] for p in passage for i in p.split("<li>")[1:]}
        verses = [v for v in verses if v.split('href="/p/', 1)[1].split('"', 1)[0] not in quoted]
    if passage and not c.get("event") and c.get("events"):
        names = [e_.get("name") for e_ in c["events"][:3] if e_.get("name")]
        summary = ((first + " " if first else "") + "In the text: " + "; ".join(names)
                   + (" and more" if len(c["events"]) > 3 else "") + ", each passage quoted in the Berean, with "
                   + f"{n_rel} connection{'s' * (n_rel != 1)}.")[:300]
    if passage and c.get("event"):
        # WHAT THE RESULT SAYS WHEN IT IS SHOWN (2026-10-25, from the r/websiteseo thread: new pages are given
        # impressions on trial, and the click decides what follows). "1 verse and 40 connections" was the prodigal
        # son's whole pitch. Now the passage by name and its opening words.
        labels = "; ".join(tl.get("label") or "" for tl in (c["event"].get("tellings") or [])[:EVENT_TELLINGS])
        opening = _plain(re.sub(r"<[^>]+>", "", passage[0].split("</a>", 1)[1].split("</li>", 1)[0])).strip()
        opening = html_unescape(opening)
        opening = opening if len(opening) <= 120 else opening[:117].rsplit(" ", 1)[0] + "…"
        title = f"{big} ({labels.split(';')[0]}): the passage and its connections"
        # not wrapped in quotation marks: a verse's own speech opens with one (Luke 15:11 "Then Jesus said, “There")
        summary = (f"{big}, {labels}. It opens: {opening} Every verse of the passage in the Berean, with "
                   f"everyone in it and where it connects.")[:300]
    speaks, more = [], 0
    phrase_books = (ev.get("phrase") or {}).get("books") or []
    for b_ in list(phrase_books) + list(ev.get("books") or []):
        for it in b_.get("items") or []:
            bk, _, cv = (it.get("eref") or "").partition(".")
            addr_v = f"{MACULA_BACK.get(bk, bk)}.{cv}"
            if not cv or addr_v in shown:
                continue
            if len(speaks) < CARD_SPEAKS:
                c_, _, v_ = cv.partition(".")
                speaks.append(f'<li><a href="/p/{_esc(addr_v)}">{_esc(b_.get("title") or bk)} {_esc(c_)}:{_esc(v_)}'
                              f'</a> {_esc(_plain(it.get("text") or ""))}</li>')
                shown.add(addr_v)
            else:
                more += 1
    groups, n = [], 0
    for g in c.get("groups") or []:
        items = []
        for it in g.get("items") or []:
            if n >= CARD_LINKS:
                break
            n += 1
            refs = ", ".join(it.get("refs") or [])
            items.append(f'<li>{_esc(it.get("label") or "")} '
                         f'<a href="/e/{_esc(_addr(it.get("other") or ""))}">{_esc(it.get("name") or "")}</a>'
                         + (f' <small>({_esc(refs)})</small>' if refs else "") + "</li>")
        if items:
            groups.append(f'<h3>{_esc(g.get("category") or "")}</h3><ul>{"".join(items)}</ul>')
    addr = _addr(eid)
    url = f"{SITE}/e/{addr}"
    # a major theme's card names the theme's own page as the one to keep
    tattr = (d["ents"][eid].get("attrs") or {})
    if tattr.get("kind") == "major_theme" and tattr.get("theme"):
        url = f"{SITE}{theme_path(tattr['theme'])}"
    head = (f"<title>{_esc(title)} · Bible Ontology</title>\n"
            f'<meta name="description" content="{_esc(summary)}">\n'
            f'<link rel="canonical" href="{_esc(url)}">\n'
            f'<meta property="og:type" content="article">\n'
            f'<meta property="og:title" content="{_esc(title)}">\n'
            f'<meta property="og:description" content="{_esc(summary)}">\n'
            f'<meta property="og:url" content="{_esc(url)}">\n')
    body = (f'<article id="ssr" class="ssr"><h1>{_esc(name)}</h1>'
            f'<p class="ssr-sub">In the Bible: every verse and connection · {_esc(c.get("type") or "")}</p>'
            + _open_btn(f"/e/{addr}", "Open this card in Bible Ontology")
            # the theme it stands at the centre of, first (ontology/concept-theme-bridges.json)
            + "".join(f'<p><b>The theme:</b> <a href="{_esc(t["path"])}">{_esc(t["title"])}</a>, '
                      f'{_esc(t["subtitle"][:1].lower() + t["subtitle"][1:])}, its passages set side by side.</p>'
                      for t in c.get("theme_bridge") or [])
            # a description in paragraphs stays in paragraphs (blank lines, as
            # the page's leadHtml splits them)
            + "".join(f"<p>{_esc(p.strip())}</p>" for p in re.split(r"\n\s*\n", desc or "") if p.strip())
            + "".join(passage)
            + (f"<h2>Verses</h2><ul>{''.join(verses)}</ul>" if verses else "")
            + (f"<h2>Where the text speaks of it</h2><ul>{''.join(speaks)}</ul>"
               + (f'<p>And {more} more, every one in <a href="/e/{_esc(addr)}">the card in Bible Ontology</a>.</p>'
                  if more else "") if speaks else "")
            + (f"<h2>Connections</h2>{''.join(groups)}" if groups else "")
            + '<p><a href="/">Open Bible Ontology</a> to read every verse and follow '
              'every connection.</p></article>')
    return head, body, addr


# A WORD CARD'S OWN ADDRESS, by its Strong's number. 2026-10-16: deep links for
# the original language word cards, with the Strong's number in the URL for
# clarity (a case came up where simply posting the word card link would have
# been perfect). The number is the
# key the card already answers by (sense_key: h1254, g26), so the address
# names the word the way every lexicon and concordance does: /word/H1254.
# Case and leading zeros are forgiven and sent on (301) to that one spelling,
# so a pasted "h01254" and "H1254" are one page, not two.
_WORD_ADDR = re.compile(r"^([HhGg])0*(\d+)[A-Za-z]?$")


def word_address(key):
    """/word/H1254 for the sense key h1254."""
    return f"/word/{key[:1].upper()}{key[1:]}" if key else ""


# What a word's page names its kind by, from STEP's morph code ("H:V", "G:N-F",
# "N:N-M-P"): the part before the first hyphen. Anything not listed is not named.
_POS_NAMES = {"V": "verb", "N": "noun", "A": "adjective", "ADV": "adverb",
              "PREP": "preposition", "CONJ": "conjunction", "PART": "particle",
              "PRT": "particle", "ART": "article", "INTJ": "interjection",
              "NEG": "negative particle", "COND": "conditional particle",
              "INTG": "interrogative", "PERP": "personal pronoun",
              "DEMP": "demonstrative pronoun", "RELP": "relative pronoun",
              "POSP": "possessive pronoun", "REFP": "reflexive pronoun"}
WORD_VERSES = 200         # a word page lists every use up to this many, in canonical order


def _word_pos_name(pos):
    pos = pos or ""
    if pos.startswith("N:"):
        return "proper name"
    if ":" not in pos:
        return ""
    return _POS_NAMES.get(pos.split(":", 1)[1].split("-")[0].upper(), "")


def _word_verse(d, ref):
    """(canonical key, book code, 'c.v', 'Genesis 22:2', Berean text) for a
    reference the word index holds, or None when the site has no such verse
    (a link on the page is always to a verse the site has)."""
    eref, text = _verse_text(d, ref)
    if not text:
        return None
    b, _, cv = eref.partition(".")
    bb = MACULA_BACK.get(b, b)
    if bb not in TITLE or not re.fullmatch(r"\d+\.\d+", cv):
        return None
    return (_vkey(f"{bb}.{cv}"), bb, cv, f"{TITLE[bb]} {cv.replace('.', ':')}", text)


def _word_trim(s, n=300):
    """A description cut at a word, never in the middle of one."""
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def word_page(spelt):
    """(head, body, canonical address) for a word, or None when there is none.
    The caller compares the address with what was asked and sends a variant
    spelling on, permanently.

    Everything the word's card shows, as plain HTML a search engine reads
    (2026-10-26: the page was a lemma, a gloss and a dozen verses -- 490 words
    -- while the card held the Septuagint's Greek, the stems, the phrases,
    what the text does with the word, its concepts and every verse). Nothing
    here that the card does not hold, and nothing the data does not.
    """
    m = _WORD_ADDR.match(spelt or "")
    if not m:
        return None
    key = m.group(1).lower() + m.group(2)
    c = json.loads(answer("/api/sense", urlencode({"key": key})))
    if not c.get("found"):
        return None
    d = load()
    addr = word_address(key)[len("/word/"):]
    lemma, translit = c.get("lemma") or "", c.get("translit") or ""
    gloss = (c.get("short") or c.get("gloss") or "").strip()
    lang = c.get("lang") or ("Hebrew" if key[:1] == "h" else "Greek")
    attr = "grc" if key[:1] == "g" else ("arc" if lang == "Aramaic" else "he")
    where = {"Hebrew": "Old Testament", "Aramaic": "Old Testament (in its Aramaic passages)",
             "Greek": "New Testament"}.get(lang, "Bible")
    n = c.get("observations") or 0
    pos = _word_pos_name(c.get("pos"))
    times = f"{n:,} time{'s' * (n != 1)}"

    # ---- every use, in canonical order, one entry to a verse
    rows, _t = occurrences(d, key, cap=10 ** 9)
    listed, seen = [], set()
    for r in rows:
        v = _word_verse(d, r.get("ref"))
        if v and (v[1], v[2]) not in seen:
            seen.add((v[1], v[2]))
            listed.append((v, r.get("gloss") or ""))
    listed.sort(key=lambda x: x[0][0])
    books = collections.Counter(v[1] for v, _g in listed)
    nb, nv = len(books), len(listed)
    ren = (c.get("renderings") or {}).get("rows") or []

    def quoted(rs, k=6):
        top = [f"“{r['gloss']}” ({r['n']:,})" for r in rs[:k]]
        if not top:
            return ""
        return ", ".join(top[:-1]) + (" and " if len(top) > 1 else "") + top[-1]

    def vlinks(refs, k=3):
        out = []
        for ref in refs[:k]:
            v = _word_verse(d, ref)
            if v:
                out.append(f'<a href="/p/{_esc(v[1])}.{_esc(v[2])}">{_esc(v[3])}</a>')
        return ", ".join(out)

    # ---- the head: what the word means and how often it occurs
    kind = f" {pos}" if pos else " word"
    said = f"{lemma} ({translit}), " if translit else f"{lemma}, "
    title = (f"{said}Strong's {addr}: {gloss}, used {times} in the {where}"
             if gloss else f"{said}Strong's {addr}, used {times} in the {where}")
    summary = _word_trim(
        f"The {lang}{kind} {lemma}{f' ({translit})' if translit else ''}, Strong's {addr}"
        + (f", “{gloss}”" if gloss else "")
        + f". Used {times} in the {where}, in {nv:,} verse{'s' * (nv != 1)} across "
          f"{nb} book{'s' * (nb != 1)}"
        + (f"; the Berean Standard Bible renders it {quoted(ren, 4)}" if ren else "")
        + ". Every verse, its Septuagint equivalents, family and what the text does with it.")
    url = f"{SITE}/word/{addr}"
    termset = {"@type": "DefinedTermSet", "name": "Hebrew and Greek words of the Bible",
               "url": SITE + "/"}
    ld = {"@context": "https://schema.org", "@type": "DefinedTerm", "name": lemma,
          "termCode": addr, "inLanguage": attr, "url": url, "inDefinedTermSet": termset}
    if translit:
        ld["alternateName"] = translit
    if gloss:
        ld["description"] = f"{gloss}. Used {times} in the {where}."
    head = (f"<title>{_esc(title)} · Bible Ontology</title>\n"
            f'<meta name="description" content="{_esc(summary)}">\n'
            f'<link rel="canonical" href="{_esc(url)}">\n'
            f'<meta property="og:type" content="article">\n'
            f'<meta property="og:title" content="{_esc(title)}">\n'
            f'<meta property="og:description" content="{_esc(summary)}">\n'
            f'<meta property="og:url" content="{_esc(url)}">\n'
            '<script type="application/ld+json">'
            + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>\n")

    # ---- the body
    P = []
    sub = " · ".join(x for x in (_esc(lang + (f" {pos}" if pos else "")), _esc(translit),
                                  f"Strong&rsquo;s {_esc(addr)}", times) if x)
    also = c.get("lemma_also") or {}
    if also.get("source") == "macula":
        other = ", ".join(f'<a href="{word_address(k)}">Strong&rsquo;s {_esc(word_address(k)[6:])}</a>'
                          for k in also.get("with") or [])
        sub += (f' · MACULA files it under <span lang="{attr}">{_esc(also["form"])}</span>'
                + (f", with {other}" if other else ""))
    elif also.get("form"):
        sub += f' · Strong&rsquo;s dictionary form: <span lang="{attr}">{_esc(also["form"])}</span>'
    P.append(f'<h1 lang="{attr}">{_esc(lemma)}</h1><p class="ssr-sub">{sub}</p>'
             + _open_btn(f"/word/{addr}", "Open this word in Bible Ontology"))
    lead = (f"<p><b>{_esc(gloss)}</b>. " if gloss else "<p>")
    lead += (f"The text uses this {_esc(lang)}{_esc(kind)} {times}, in {nv:,} verse{'s' * (nv != 1)} "
             f"of {nb} book{'s' * (nb != 1)} of the {where}.")
    if ren:
        lead += (f" The Berean Standard Bible renders it {_esc(quoted(ren, 8))}"
                 + (f", and {len(ren) - 8} other renderings" if len(ren) > 8 else "") + ".")
    P.append(lead + "</p>")
    if c.get("note"):
        P.append(f"<p>{_esc(_plain((c['note'] or {}).get('text') or ''))}</p>")
    if c.get("loan"):
        ln = c["loan"]
        P.append("<p>The New Testament spells this word rather than translating it"
                 + (f"; the text reads it “{_esc(ln['means']['gloss'])}” in all "
                    f"{ln.get('n')} of its occurrences" if ln.get("means") else "") + ".</p>")

    # the lexicon's entry, whole, with its credit
    defn = c.get("definition") or ""
    if defn:
        lines = "".join((f"<li><b>{_esc(x)}</b></li>" if x.startswith("Entry (") else f"<li>{_esc(x)}</li>")
                        for x in defn.split(" · ") if x.strip())
        P.append(f"<h2>The lexicon entry</h2><ul>{lines}</ul>"
                 f'<p class="ssr-sub">From {_esc(c.get("definition_credit") or "")} '
                 f'<a href="https://www.STEPBible.org">www.STEPBible.org</a></p>')

    if ren:
        items = []
        for r in ren:
            vs = vlinks(r.get("refs") or [], 5)
            items.append(f"<li><b>“{_esc(r['gloss'])}”</b> — {r['n']:,} use{'s' * (r['n'] != 1)}"
                         + (f" in {r['verses']:,} verse{'s' * (r['verses'] != 1)}" if r["verses"] != r["n"] else "")
                         + (f", for example {vs}" if vs else "") + "</li>")
        tot = (c.get("renderings") or {}).get("total") or 0
        P.append("<h2>How the Berean Standard Bible renders it</h2>"
                 f"<p>What the English text puts for this word, counted over {tot:,} use{'s' * (tot != 1)}"
                 + (f" (the interlinear counts {n:,}; the rest carry no separate rendering in the data)"
                    if tot != n else "") + f".</p><ul>{''.join(items)}</ul>")

    gram = c.get("grammar") or []
    if gram:
        P.append("<h2>Its forms and stems</h2><ul>" + "".join(
            f"<li><b>{_esc(g['field'])}</b>: " + ", ".join(
                f"{_esc(v['v'])} ({v['n']:,})" for v in g["values"]) + "</li>" for g in gram) + "</ul>")

    if books:
        order = [b for b in ORDER if b in books]
        P.append("<h2>Where it occurs</h2><p>" + ", ".join(
            f"{_esc(TITLE[b])} {books[b]:,}" for b in order)
            + f" (verses with the word, in {nb} book{'s' * (nb != 1)}).</p>")

    # ---- across the languages
    eq = c.get("equiv") or {}
    grp = collections.OrderedDict()
    for w in (eq.get("greek") or []):
        g = grp.setdefault(w.get("key") or w.get("t"), {"key": w.get("key"), "n": 0, "forms": []})
        g["n"] += w.get("n") or 0
        g["forms"].append(w.get("t"))
    cross = []
    for g in sorted(grp.values(), key=lambda x: -x["n"]):
        if g["key"]:
            lem, gl = _word_label(d, g["key"])
            cross.append(f'<li><a href="{_esc(word_address(g["key"]))}">{_esc(lem)}</a>'
                         + (f" “{_esc(gl)}”" if gl else "") + f" — {g['n']:,}</li>")
        else:
            cross.append(f"<li>{_esc(g['forms'][0])} — {g['n']:,}</li>")
    if cross:
        P.append("<h2>The Greek the Septuagint used for it</h2>"
                 "<p>An alignment recorded in the data (MACULA's Septuagint column), "
                 "with how many times: a translator's choice, not a guess.</p>"
                 f"<ul>{''.join(cross)}</ul>")
    heb = [w for w in (eq.get("hebrew") or []) if w.get("key")]
    if heb:
        P.append("<h2>The Hebrew the Septuagint used it for</h2><p>The same alignment read "
                 "from the Greek end, with how many times.</p><ul>" + "".join(
                     f'<li><a href="{_esc(word_address(w["key"]))}">{_esc(w.get("t") or w["key"])}</a>'
                     + (f" “{_esc(w['g'])}”" if w.get("g") else "") + f" — {w.get('n') or 0:,}</li>"
                     for w in heb) + "</ul>")
    ar = eq.get("aramaic")
    if ar:
        P.append("<h2>In the Aramaic passages</h2><p>The Aramaic parts of the Bible spell "
                 f"{_esc(ar.get('t') or '')}"
                 + (f" ({_esc(ar['x'])})" if ar.get("x") else "")
                 + (f", glossed “{_esc(ar['g'])}”," if ar.get("g") else "")
                 + f" with the same consonants, {ar.get('n') or 0:,} times: a cognate by spelling, "
                   "not a translation of this word.</p>")

    # ---- its family and the concepts it stands behind
    fam = c.get("family") or []
    grouped = c.get("grouped") or []
    if fam:
        P.append("<h2>Word family</h2><p>Kin by derivation, one step, as the Greek lexicon "
                 "(Abbott-Smith) records it, among the words the text uses.</p><ul>" + "".join(
                     f'<li><a href="{_esc(word_address(k["key"]))}">{_esc(k["lemma"])}</a>'
                     + (f" “{_esc(k['gloss'])}”" if k.get("gloss") else "")
                     + f" — {_esc(k['how'])} {_esc(lemma)}, {k['uses']:,} use{'s' * (k['uses'] != 1)}</li>"
                     for k in fam) + "</ul>")
    for g in grouped:
        P.append(f"<h2>Words the site groups it with: {_esc(g['name'])}</h2>"
                 "<p>A grouping made by hand to find passages by their words. It does not say "
                 "the words share a root.</p><ul>" + "".join(
                     f'<li><a href="{_esc(word_address(k["key"]))}">{_esc(k["lemma"])}</a>'
                     + (f" “{_esc(k['gloss'])}”" if k.get("gloss") else "")
                     + f" — {k['uses']:,} verse{'s' * (k['uses'] != 1)}</li>"
                     for k in g["members"]) + "</ul>")
    cons = c.get("concepts") or []
    if cons:
        P.append("<h2>Concept cards it stands behind</h2><ul>" + "".join(
            f'<li><a href="/e/{_esc(_addr(x["id"]))}">{_esc(x["name"])}</a></li>' for x in cons) + "</ul>")

    # ---- what the text does with it
    a = c.get("acts")
    if a:
        ag = ", ".join(f"{_esc(x['lemma'])} ({x['n']:,})" for x in (a.get("agents") or [])[:12])
        P.append("<h2>What happens when this word is used</h2>"
                 f"<p>Recorded {a['count']:,} times as something that happens, across "
                 f"{a['verses']:,} verses. It is read off the grammar (the form the language uses to "
                 "carry a story forward), and who did it is the clause's own subject."
                 + (f" Who does it: {ag}." if ag else "") + "</p>")
    vc = c.get("verb_class")
    if vc and vc.get("glosses"):
        P.append("<h2>Verbs it behaves like" + (f": {_esc(vc['name'])}" if vc.get("name") else "") + "</h2><p>"
                 + ", ".join(_esc(x) for x in vc["glosses"]) + ".</p>")
    byk = collections.OrderedDict()
    for f in c.get("features") or []:
        if f.get("kind") != "lxx":              # the Greek is given above
            byk.setdefault(f["says"], []).append(f)
    if byk:
        sec = []
        for says, fs in byk.items():
            li = ""
            for f in sorted(fs, key=lambda f: -f["count"])[:10]:
                vl = vlinks(f.get("refs") or [], 3)
                li += ("<li>" + (f"“{_esc(f['with'])}”" if f.get("quoted") else _esc(f.get("with") or ""))
                       + f" — {f['count']:,}×" + (f" ({vl})" if vl else "") + "</li>")
            sec.append(f"<h3>{_esc(says[:1].upper() + says[1:])}</h3><ul>{li}</ul>"
                       + (f"<p>And {len(fs) - 10} more, in the app.</p>" if len(fs) > 10 else ""))
        P.append("<h2>What the text does with it</h2><p>Counted from the sentences it stands in, "
                 "with how many times and a few of the verses.</p>" + "".join(sec))
    mined = c.get("mined") or []
    sure = [x for x in mined if x.get("tier") == "sure"]
    if sure:
        li = "".join(
            f"<li>{_esc(x['template'])} — {x['instances']:,} accounts in {x['books']} book{'s' * (x['books'] != 1)}"
            + (" (both testaments)" if x.get("testaments") == "OT+NT" else "") + "</li>" for x in sure)
        rest = len(mined) - len(sure)
        P.append(f"<h2>Patterns it is part of</h2><ul>{li}</ul>"
                 + (f"<p>And {rest} less certain match{'es' * (rest != 1)}, in the app.</p>" if rest else ""))

    near = c.get("neighbours") or []
    if near:
        P.append("<h2>Words it behaves most like</h2><p>Worked out from how the sentences are built, "
                 "not asserted: a weak signal, good for finding a thread and not an authority.</p><ul>"
                 + "".join(f'<li><a href="{_esc(word_address(x["key"]))}">{_esc(x.get("gloss") or x["key"])}</a>'
                           f" — {x['observations']:,} uses</li>" for x in near) + "</ul>")
    con = c.get("contrasts") or []
    if con:
        me = (c.get("gloss") or "").lower()
        P.append("<h2>What it is set against</h2><ul>" + "".join(
            f"<li>{_esc(x['b'] if x['a'] == me else x['a'])} ({_esc(x['kind'])}, {x['count']:,}×)</li>"
            for x in con) + "</ul>")

    # ---- the verses, every one up to the limit
    shown = listed[:WORD_VERSES]
    if shown:
        li = "".join(
            f'<li><a href="/p/{_esc(v[1])}.{_esc(v[2])}">{_esc(v[3])}</a>'
            + (f" <em>“{_esc(g)}”</em>" if g else "") + f" {_esc(v[4])}</li>"
            for v, g in shown)
        more = nv - len(shown)
        P.append("<h2>Its verses, in canonical order</h2>"
                 f"<p>{nv:,} verse{'s' * (nv != 1)}; each shows the word as the Berean Standard Bible renders it.</p>"
                 f"<ul>{li}</ul>"
                 + (f'<p>And {more:,} more, every one in <a href="/word/{_esc(addr)}">the card in '
                    f'Bible Ontology</a>.</p>' if more > 0 else ""))
    P.append('<p><a href="/">Open Bible Ontology</a> to see every use and what the text does with this word.</p>')
    body = '<article id="ssr" class="ssr">' + "".join(P) + "</article>"
    return head, body, addr


# THE FRONT PAGE SAYS WHAT THE SITE IS. 2026-10-03: the site should be able to
# respond to searches for Bible graph, Bible ontology,
# Bible Semantic web, scripture knowledge graph, bible connections, bible
# concept linking, etc. Those are searches for a KIND of site, answered by
# the front page saying plainly what this one is -- and it said nothing: `/`
# was the app's empty shell. Like About, it describes only what exists; the
# counts are live.
HOME_CONCEPTS = ("love", "forgiveness", "faith", "grace", "mercy", "salvation", "sin",
                 "repentance", "prayer", "hope", "wisdom", "righteousness", "justice",
                 "holiness", "covenant", "resurrection", "heaven", "the Holy Spirit")
_HOME = None


def home_page():
    global _HOME
    if _HOME is not None:
        return _HOME
    d = load()
    n_ents = len(d["ents"])
    n_rels = sum(len(v) for v in d["rels"].values()) // 2
    title = "Bible Ontology: a Bible knowledge graph built from the text"
    summary = (f"A knowledge graph of the Bible: {n_ents:,} people, places, concepts, events "
               f"and sayings, joined by {n_rels:,} connections the text itself makes, each "
               f"with its verse. Read in the Berean Standard Bible with the Hebrew and Greek "
               f"beneath it.")

    def link(eid, label=None):
        e = d["ents"].get(eid)
        return f'<a href="/e/{_esc(_addr(eid))}">{_esc(label or e["name"])}</a>' if e else ""

    hub = _hubscores()
    people = sorted((e for e in d["ents"].values() if e["type"] == "person"),
                    key=lambda e: -hub.get(e["id"], 0))[:30]
    # THE THEMES AS FRONT DOORS (plan 7.6b: "linked prominently from the home
    # page, at its own address"): each theme's own page, in its group, and
    # first the themes with a front page and the table each hinges on
    tm = _theme_map()
    tname = lambda tid: _title(tm["_by"][tid]["title"])  # noqa: E731
    starts = [f'<li><a href="{_esc(theme_path(tid))}">{_esc(tname(tid))}</a> · <a href="{_esc(h["imagery"]["path"])}">'
              f'{_esc(h["imagery"]["door"])}</a></li>'
              for tid in _theme_hubs() if tid in tm["_by"] for h in [_hub(tid)] if h and h.get("imagery")]
    groups = [f"<p><b>{_esc(g['name'])}</b>: " + " · ".join(
        f'<a href="{_esc(theme_path(tid))}">{_esc(tname(tid))}</a>' for tid in g["themes"] if tid in tm["_by"]) + "</p>"
        for g in _theme_homes().get("groups") or []]
    themes = (("<h2>Start with a theme</h2><ul>" + "".join(starts) + "</ul>") if starts else "") + \
        ("<h2>Themes</h2>" + "".join(groups) if groups else "")
    by = {}
    for e in d["ents"].values():
        if e["type"] in ("concept", "being", "covenant"):
            by.setdefault(e["name"].lower(), e["id"])
    concepts = [link(by[c.lower()]) for c in HOME_CONCEPTS if c.lower() in by]
    head = (f"<title>{_esc(title)}</title>\n"
            f'<meta name="description" content="{_esc(summary)}">\n'
            f'<link rel="canonical" href="{SITE}/">\n'
            f'<meta property="og:type" content="website">\n'
            f'<meta property="og:title" content="{_esc(title)}">\n'
            f'<meta property="og:description" content="{_esc(summary)}">\n'
            f'<meta property="og:url" content="{SITE}/">\n'
            '<script type="application/ld+json">'
            + json.dumps({"@context": "https://schema.org", "@type": "WebSite",
                          "name": "Bible Ontology", "url": SITE + "/",
                          "description": summary}, ensure_ascii=False)
            + "</script>\n")
    body = ('<article id="ssr" class="ssr"><h1>Bible Ontology</h1>'
            '<p class="ssr-sub">A Bible knowledge graph, built from the text itself</p>'
            + _open_btn("/", "Open Bible Ontology")
            + f"<p>{_esc(summary)}</p>"
            "<p>It maps what Scripture itself connects: who is related to whom, what a "
            "passage speaks of, which verses quote or echo earlier ones, and the Hebrew and "
            "Greek words behind the English. Every connection carries the verse it rests on, "
            "so each one can be checked against the text. Where readers of the text disagree, "
            "it shows the verses each reads and does not decide between them.</p>"
            + themes
            + (f"<h2>Concepts</h2><p>{' · '.join(x for x in concepts if x)}</p>" if concepts else "")
            + (f"<h2>People</h2><p>{' · '.join(link(e['id']) for e in people)}</p>" if people else "")
            + '<p><a href="/">Open Bible Ontology</a> to read the text and follow every '
              "connection.</p></article>")
    _HOME = (head, body)
    return _HOME


# A PASSAGE AT ITS OWN ADDRESS (A.21): /p/Ps.119 is the chapter, its whole
# Berean text; /p/Ps.119.105 is the verse -- with its neighbours, the cards
# that cite it and the passages it quotes, echoes or is echoed by, NOT the
# chapter again: 31,000 pages each repeating their chapter would read to a
# search engine as one page copied 31,000 times. Book codes are the reader's
# own (state.book); anything else -- app1's "Genesis 1", "John 3:16" -- is
# resolved the way the search box resolves it and sent on to its address.
_CARDS_AT = None


def _cards_at():
    """(book, chapter, verse) -> ids of the cards citing it."""
    global _CARDS_AT
    if _CARDS_AT is None:
        idx = collections.defaultdict(list)
        for eid, e in load()["ents"].items():
            for r in e.get("refs") or []:
                m = re.match(r"^(\w+) (\d+):(\d+)", r)
                if m and m.group(1) in TITLE:
                    idx[(m.group(1), int(m.group(2)), int(m.group(3)))].append(eid)
        _CARDS_AT = idx
    return _CARDS_AT


def _book_name(b, c=None):
    return "Psalm" if b == "Ps" and c is not None else TITLE.get(b, b)


def _vlink(eref):
    """An app ref ("Jon.1.4") as a link to its verse page, or plain text."""
    mm = re.match(r"^(\w+)\.(\d+)\.(\d+)$", eref or "")
    if not mm:
        return _esc(eref or "")
    ob = MACULA_BACK.get(mm.group(1), mm.group(1))
    if ob not in TITLE:
        return _esc(eref)
    oc, ov = int(mm.group(2)), int(mm.group(3))
    return f'<a href="/p/{ob}.{oc}.{ov}">{_esc(_book_name(ob, oc))} {oc}:{ov}</a>'


def _shared_html(ech):
    """What two verses share (plans 6.17, 6.18), in a verse page's plain HTML,
    so search engines read the explanations, not only the app.
    2026-10-04: this fits the obscure search category
    well. Each section marked a reading, as the app marks it; a story
    told again carries its steps side by side and the disclaimer."""
    al = ech.get("allusions") or {}
    out = []
    eds = [e for e in ech.get("editors") or [] if e.get("explanations")]
    words = al.get("words") or []
    if words or eds:
        items = [f'<li>{_vlink(x.get("eref"))} {_esc(x.get("text") or "")}'
                 + (f'<br><em>{_esc(x["explanation"])}</em>' if x.get("explanation") else "") + "</li>"
                 for x in words]
        items += [f'<li>{_vlink(e.get("eref"))} {_esc(e.get("text") or "")}'
                  + "".join(f'<br><em>{_esc(y["explanation"])}</em>' for y in e["explanations"]) + "</li>"
                  for e in eds]
        out.append("<h2>Words taken up</h2><p class=\"ssr-sub\">A reading: the words side by side in "
                   f"the Hebrew and Greek.</p><ul>{''.join(items)}</ul>")
    for n in al.get("images") or []:
        out.append(f"<h2>Both use “{_esc(n['node'])}”</h2><p class=\"ssr-sub\">An image or expression "
                   "both use, not a claim that one points to the other. A reading.</p><ul>"
                   + "".join(f'<li>{_vlink(m.get("eref"))} {_esc(m.get("text") or "")}</li>' for m in n["members"])
                   + "</ul>" + "".join(f'<p>{_esc(x.get("explanation") or "")}</p>' for x in n["explanations"]))
    for s in al.get("stories") or []:
        rows = "".join(f"<tr><td>“{_esc(a[1])}” {_vlink(a[0])}</td><td>“{_esc(b[1])}” {_vlink(b[0])}</td></tr>"
                       for a, b in s.get("beats") or [])
        out.append("<h2>A story told again</h2><p class=\"ssr-sub\">The steps of two stories side by side, "
                   "not a claim that one was told with the other in mind. A reading.</p>"
                   f"<table>{rows}</table>"
                   + (f"<p>{_esc(s['explanation'])}</p>" if s.get("explanation") else "")
                   + (f"<p>Where they differ: {_esc(s['differs'])}</p>" if s.get("differs") else ""))
    return out


def _marked(b, c, v, text):
    """A verse for a page with no script (/p/): the Berean's words escaped,
    an asterisk at a word where the original reads otherwise, a dagger for
    the Berean's manuscript note, and each note written out under the verse
    -- the same marks the reader shows (verse_marks)."""
    m = verse_marks(b, c, v) or {}
    h, notes = _esc(text), []
    for f in m.get("find", []):
        w = _esc(f["word"])
        h = h.replace(w, w + "<sup>*</sup>", 1) if w in h else h + "<sup>*</sup>"
        notes.append(f'<small class="vnote">* On the original (this site’s note): {_esc(f["note"])}</small>')
    for n in m.get("ms", []):
        h += "<sup>†</sup>"
        notes.append(f'<small class="vnote">† The Berean’s note: {_esc(n)}</small>')
    return h + ("<br>" + "<br>".join(notes) if notes else "")


def passage_page(ref):
    """(head, body, canonical path) for a chapter or verse address; a str
    (the canonical path) when the address should be sent on; None if none."""
    d = load()
    m = re.match(r"^([1-3]?[A-Za-z]+)\.(\d+)(?:\.(\d+))?$", ref)
    if not m or m.group(1) not in TITLE:
        # the search fallback ("John 3:16", "Genesis") only for what could be
        # a book and a reference: anything else was a full, uncached search
        # per request, answered 404 (the security review, 2026-10-22)
        if not re.fullmatch(r"[1-3]?\s?[A-Za-z][A-Za-z .']{0,30}(?:\s?\d{1,3}(?:[:.]\d{1,3})?)?", ref or ""):
            return None
        r = next((x for x in api_search(d, {"q": [ref]}).get("results", [])
                  if x["kind"] == "passage"), None)
        if not r:
            return None
        return f"/p/{r['id']}.{r.get('chapter') or 1}" + (f".{r['verse']}" if r.get("verse") else "")
    b, c = m.group(1), int(m.group(2))
    v = int(m.group(3)) if m.group(3) else None
    if c not in d["chapters"].get(b, set()) or (v and (b, c, v) not in d["verses"]):
        return None
    nch = max(d["chapters"][b])
    nm = _book_name(b, c)
    verses = [(n, d["verses"][(b, c, n)]) for n in range(1, 200) if (b, c, n) in d["verses"]]
    cards = _cards_at()

    def card_links(keys, cap):
        seen, out = set(), []
        for k in keys:
            for eid in cards.get(k, []):
                e = d["ents"].get(eid)
                if e and eid not in seen and e["type"] not in ("text", "passage"):
                    seen.add(eid)
                    out.append(f'<a href="/e/{_esc(_addr(eid))}">{_esc(e["name"])}</a>')
        return out[:cap]

    if v is None:
        path = f"/p/{b}.{c}"
        title = f"{nm} {c}: the full text, with its people, places and connections"
        summary = (" ".join(t for _n, t in verses)[:240] + "…") if verses else title
        nav = " · ".join(x for x in (
            f'<a href="/p/{b}.{c - 1}">{_esc(nm)} {c - 1}</a>' if c > 1 else "",
            f'<a href="/p/{b}.{c + 1}">{_esc(nm)} {c + 1}</a>' if c < nch else "") if x)
        people = card_links([(b, c, n) for n, _t in verses], 60)
        body = (f'<article id="ssr" class="ssr"><h1>{_esc(nm)} {c}</h1>'
                f'<p class="ssr-sub">Berean Standard Bible · chapter {c} of {nch}</p>'
                + _open_btn(f"/p/{b}.{c}", f"Open {nm} {c} in the reader")
                + "".join(f'<p><a href="/p/{b}.{c}.{n}"><sup>{n}</sup></a> {_marked(b, c, n, t)}</p>'
                          for n, t in verses)
                + (f"<h2>In this chapter</h2><p>{' · '.join(people)}</p>" if people else "")
                + (f"<p>{nav}</p>" if nav else ""))
    else:
        path = f"/p/{b}.{c}.{v}"
        text = d["verses"][(b, c, v)]
        title = f"{nm} {c}:{v}: {text[:80]}{'…' if len(text) > 80 else ''}"
        summary = (f"{nm} {c}:{v}, “{text}” Read in its chapter, with the "
                   f"original language and every passage it connects to.")[:300]
        near = [(n, t) for n, t in verses if v - 2 <= n <= v + 2 and n != v]
        cited = card_links([(b, c, v)], 40)
        ech = json.loads(answer("/api/echoes", urlencode({"ref": f"{b} {c}:{v}"})))
        links = []
        for kind, label in (("refers_to", "Quotes or points to"), ("earlier", "Echoes"),
                            ("later", "Echoed by"), ("parallel", "Told also in")):
            items = []
            for x in (ech.get(kind) or [])[:8]:
                er = x.get("eref") or x.get("ref") or ""
                mm = re.match(r"^(\w+)\.(\d+)\.(\d+)$", er)
                if not mm:
                    continue
                ob = MACULA_BACK.get(mm.group(1), mm.group(1))
                if ob not in TITLE:
                    continue
                oc, ov = int(mm.group(2)), int(mm.group(3))
                items.append(f'<li><a href="/p/{ob}.{oc}.{ov}">{_esc(_book_name(ob, oc))} '
                             f'{oc}:{ov}</a> {_esc(x.get("text") or "")}</li>')
            if items:
                links.append(f"<h2>{label}</h2><ul>{''.join(items)}</ul>")
        # what the app shows first: verses read as saying the same thing --
        # a reading, so marked as one, as the app marks it
        same = []
        for x in (ech.get("aligned") or []):
            if x.get("deeper") or len(same) >= 8:
                continue
            mm = re.match(r"^(\w+)\.(\d+)\.(\d+)$", x.get("eref") or "")
            ob = MACULA_BACK.get(mm.group(1), mm.group(1)) if mm else None
            if not mm or ob not in TITLE:
                continue
            oc, ov = int(mm.group(2)), int(mm.group(3))
            same.append(f'<li><a href="/p/{ob}.{oc}.{ov}">{_esc(_book_name(ob, oc))} '
                        f'{oc}:{ov}</a> {_esc(x.get("text") or "")}</li>')
        if same:
            links.insert(0, "<h2>Says the same thing</h2><p class=\"ssr-sub\">"
                            "Each a reading, not the text's own claim.</p>"
                            f"<ul>{''.join(same)}</ul>")
        links += _shared_html(ech)
        body = (f'<article id="ssr" class="ssr"><h1>{_esc(nm)} {c}:{v}</h1>'
                f'<p class="ssr-sub">Berean Standard Bible · <a href="/p/{b}.{c}">'
                f'{_esc(nm)} {c}</a></p>'
                + _open_btn(f"/p/{b}.{c}.{v}", f"Open {nm} {c}:{v} in the reader")
                + f"<blockquote><p>{_marked(b, c, v, text)}</p></blockquote>"
                + (f"<h2>Around it</h2>" + "".join(
                    f'<p><a href="/p/{b}.{c}.{n}"><sup>{n}</sup></a> {_marked(b, c, n, t)}</p>' for n, t in near)
                   if near else "")
                + (f"<h2>Cards that cite it</h2><p>{' · '.join(cited)}</p>" if cited else "")
                + "".join(links))
    body += ('<p><a href="/">Open Bible Ontology</a> to read it with the original '
             "language, its structure and every connection.</p></article>")
    url = SITE + path
    head = (f"<title>{_esc(title)} · Bible Ontology</title>\n"
            f'<meta name="description" content="{_esc(summary)}">\n'
            f'<link rel="canonical" href="{_esc(url)}">\n'
            f'<meta property="og:type" content="article">\n'
            f'<meta property="og:title" content="{_esc(title)}">\n'
            f'<meta property="og:description" content="{_esc(summary)}">\n'
            f'<meta property="og:url" content="{_esc(url)}">\n')
    return head, body, path


# A MAJOR THEME AT ITS OWN ADDRESS (A.21): /theme/covenant carries the theme's
# core concepts and the passages each names. A reading, said so first, as the
# app says it. The theme's card (/e/theme_covenant) names this page as the one
# to keep, so the two do not compete for one search.
def theme_page(tid):
    d = load()
    if not any(t["id"] == tid for t in _theme_map().get("themes", [])):
        return None
    t = json.loads(answer("/api/majortheme", urlencode({"id": tid})))
    if not t.get("found"):
        return None
    name = _title(t.get("title") or tid)
    title = f"{name} in the Bible: its core concepts and passages"
    summary = (f"{name}: {t.get('subtitle') or ''}. {len(t.get('concepts') or [])} core "
               f"concepts, each with the passages it names, in the Berean text.")[:300]
    # a theme with a front page is described by it, not by the map below it
    # (2026-10-07: Google's first indexed theme page showed the map's line)
    if (t.get("hub") or {}).get("imagery"):
        # a front page may name its own search title (Freedom: "from fear,
        # anxiety, shame and sin", plan 7.6b, approving P-2026-10-07-3)
        title = t["hub"].get("search_title") or f"{name} in the Bible: its passages side by side"
        summary = t["hub"].get("intro") or summary
        if len(summary) > 300:
            summary = summary[:300].rsplit(". ", 1)[0] + "."

    def ref_link(r):
        b = r.get("book")
        if b not in TITLE or not r.get("start"):
            return _esc(r.get("label") or "")
        c, v = r["start"]
        return f'<a href="/p/{b}.{c}.{v}">{_esc(r.get("label") or f"{b} {c}:{v}")}</a>'

    parts = []
    for label, cs in (("Core concepts", t.get("concepts") or []),
                      ("Also in this theme", t.get("secondary") or [])):
        items = []
        for c in cs:
            ps = "".join(
                f"<li>{' · '.join(ref_link(r) for r in p.get('refs') or [])}"
                + (f" — {_esc(p['note'])}" if p.get("note") else "") + "</li>"
                for p in c.get("passages") or [])
            # each concept's heading opens its card (everything is a link;
            # "The full armor of God" is the armor's own card, 2026-10-07)
            node = c.get("node")
            nm = _esc(c.get("name") or "")
            items.append((f'<h3><a href="/e/{_esc(_addr(node))}">{nm}</a></h3>'
                          if node and node in load()["ents"] else f"<h3>{nm}</h3>")
                         + (f"<ul>{ps}</ul>" if ps else ""))
        if items:
            parts.append(f"<h2>{label}</h2>" + "".join(items))
    path = theme_path(tid)
    url = SITE + path
    head = (f"<title>{_esc(title)} · Bible Ontology</title>\n"
            f'<meta name="description" content="{_esc(summary)}">\n'
            f'<link rel="canonical" href="{_esc(url)}">\n'
            f'<meta property="og:type" content="article">\n'
            f'<meta property="og:title" content="{_esc(title)}">\n'
            f'<meta property="og:description" content="{_esc(summary)}">\n'
            f'<meta property="og:url" content="{_esc(url)}">\n')
    # its group, each sibling at its own address (plan 7.6b)
    g = t.get("group")
    group = (f'<p class="ssr-sub">In {_esc(g["name"])}: ' + " · ".join(
        _esc(_title(x["title"])) if x["id"] == tid else f'<a href="{_esc(theme_path(x["id"]))}">{_esc(_title(x["title"]))}</a>'
        for x in g["themes"]) + "</p>") if g else ""
    # ITS FRONT PAGE (plan 7.6b): the opening in plain words and the texts'
    # own, the page it hinges on as the first door, where to begin, its note
    hub, hub_html = t.get("hub"), ""
    if hub:
        hub_html = f'<p>{_esc(hub.get("intro") or "")}</p>'
        if hub.get("imagery"):
            im = hub["imagery"]
            hub_html += (f'<p><b><a href="{_esc(im["path"])}">{_esc(im["door"])}</a></b>: {im["n"]} '
                         f'{_esc(im["blurb"])}</p>')
        # a card the theme hinges on, as a door of its own beside the heart
        for s in hub.get("see_also") or []:
            if s.get("card") and s.get("door"):
                cap = s["title"][:1].upper() + s["title"][1:]     # the card's own capitals, not title case
                hub_html += (f'<p><b><a href="{_esc(s["path"])}">{_esc(cap)}</a></b>: '
                             f'{_esc(s["label"])}; {_esc(s.get("blurb") or "")}</p>')
        if hub.get("starters"):
            hub_html += (f"<p>{_esc(hub['starters_label'])}: " + " · ".join(
                f'<a href="{_esc(hub["imagery"]["path"])}#row-{s["row"]}">{_esc(s["title"])}</a>'
                for s in hub["starters"]) + "</p>") if hub.get("imagery") else ""
        for s in hub.get("see_also") or []:
            if s.get("card") and s.get("door"):
                continue                      # drawn above, as a door
            hub_html += (f'<p>See also, {_esc(s["label"])}: <a href="{_esc(s["path"])}">{_esc(s["title"])}</a></p>'
                         if s.get("card") else
                         f'<p>See also, on {_esc(s["door"])}: <a href="{_esc(s["path"])}#row-{s["row"]}">'
                         f'{_esc(s["title"])}</a></p>')
        hub_html += "<ul>" + "".join(
            f'<li>“{_esc(o["words"])}” — {_ref_a(o["ref"])}</li>' for o in hub.get("opening") or []) + "</ul>"
        if hub.get("visions"):
            hub_html += f"<p>{_esc(hub['chapters_label'])}: " + " · ".join(
                _ref_a(c["label"]) for c in hub["visions"]) + "</p>"
        hub_html += f'<p class="ssr-sub">{_esc(hub.get("note") or "")}</p>'
    body = (f'<article id="ssr" class="ssr"><h1>{_esc(name)}</h1>'
            + group +
            f'<p class="ssr-sub">A major theme · {_esc(t.get("subtitle") or "")}</p>'
            + hub_html
            + _open_btn(path, f"Open {name} in Bible Ontology")
            + (f'<p class="ssr-sub">{_esc(t["credit"])}</p>' if t.get("credit") else "")
            + "".join(parts)
            + _theme_cards_html(d, tid, body_so_far="".join(parts) + hub_html)
            + '<p><a href="/">Open Bible Ontology</a> to read every passage in place.</p></article>')
    return head, body, path


_NOT_A_CARD_NAME = {"us", "we", "they", "them", "many", "one of them", "the seven", "every nation", "all",
                    "the many", "others", "some", "these", "those"}
_THEME_CARD_GROUPS = (("People", {"person", "group", "being"}), ("Places", {"place"}),
                      ("Images and figures", {"image"}), ("Events", {"event"}),
                      ("Things", {"object", "creature", "observance", "title"}), ("Concepts", {"concept"}))


def _theme_cards_html(d, tid, body_so_far=""):
    """CARDS IN THIS THEME (2026-10-25). Every card shows the major themes it belongs to (the theme map's by_node),
    but the theme's own page linked back only the concepts it heads: Temple / Presence did not link the temple. So
    the page lists the rest, by kind, each a link: the cards the map ties to the theme, not structural records,
    readings or aliases, and not a card the page already links"""
    seen, names, groups = set(), set(), collections.defaultdict(list)
    for node, xs in _theme_map().get("by_node", {}).items():
        if node in seen or not any(x.get("theme") == tid for x in xs):
            continue
        seen.add(node)
        e = d["ents"].get(node)
        if not e or e.get("alias_of") or _NOT_A_SEE_ALSO.search(node):
            continue
        # the map was matched by name, so a pronoun or a count came with it ("us", "On", "many"), and two cards
        # of one name read as a repeat ("Eden · Eden"): those are left out
        nm = (e.get("name") or node).strip()
        if len(nm) < 3 or nm.lower() in _NOT_A_CARD_NAME or nm.lower() in names:
            continue
        names.add(nm.lower())
        if f'href="/e/{_esc(_addr(node))}"' in body_so_far:
            continue
        for label, kinds in _THEME_CARD_GROUPS:
            if e.get("type") in kinds:
                groups[label].append((e.get("name") or node, node))
                break
    if not groups:
        return ""
    out = ["<h2>Cards in this theme</h2>"]
    for label, _k in _THEME_CARD_GROUPS:
        if groups.get(label):
            out.append(f"<p><b>{label}:</b> " + " · ".join(
                f'<a href="/e/{_esc(_addr(n))}">{_esc(nm)}</a>' for nm, n in sorted(groups[label], key=lambda x: x[0].lower()))
                + "</p>")
    return "".join(out)


def _ref_a(s):
    """"Daniel 7:9" as a link to its verse page; "Daniel 7" to its chapter"""
    r = _named_ref(s)
    if not r:
        return _esc(s)
    b, c, v = r
    return f'<a href="/p/{b}.{c}{f".{v}" if v else ""}">{_esc(s)}</a>'


# A THEME'S IMAGERY AT ITS OWN ADDRESS (plan 7.6b): /theme/apocalyptic/imagery,
# every row in plain HTML, each quotation linked to its verse in context
# (2026-10-06: the verse quotes provide a path to the
# reader where they can be examined with context)
def imagery_page(tid):
    load()
    im = json.loads(answer("/api/imagery", urlencode({"id": tid})))
    if not im.get("found"):
        return None
    name, door = im["title"], im["door"]
    title = f"{name} in the Bible: {door[:1].lower() + door[1:]}"
    summary = (f"{door}: {len(im['rows'])} things more than one book of the Bible describes, "
               f"from {im['columns'][0]} to {im['columns'][-1]}, each in the passages' own words, "
               f"with what is alike and what differs.")[:300]
    path = _side_path(tid)
    url = SITE + path
    head = (f"<title>{_esc(title)} · Bible Ontology</title>\n"
            f'<meta name="description" content="{_esc(summary)}">\n'
            f'<link rel="canonical" href="{_esc(url)}">\n'
            f'<meta property="og:type" content="article">\n'
            f'<meta property="og:title" content="{_esc(title)}">\n'
            f'<meta property="og:description" content="{_esc(summary)}">\n'
            f'<meta property="og:url" content="{_esc(url)}">\n')
    rows = []
    for r in im["rows"]:
        cells = "".join(
            f"<li><b>{_esc(c)}</b>: " + "; ".join(f"“{_esc(x[1])}” ({_ref_a(x[0])}){'*' if x[2:] == ['aside'] else ''}"
                                                  for x in r["cells"].get(c, []))
            + "</li>" for c in im["columns"] if r["cells"].get(c))
        aside = any(x[2:] == ["aside"] for cs in r["cells"].values() for x in cs)
        rows.append(f'<section id="row-{r["n"]}"><h2>{_esc(r["title"])}</h2><ul>{cells}</ul>'
                    + (f"<p>* {_esc(ASIDE_NOTE)}</p>" if aside else "")
                    + f'<p><b>Alike:</b> {_esc(r.get("alike") or "")}</p>'
                    + (f'<p><b>Different:</b> {_esc(r["different"])}</p>' if r.get("different") else "")
                    + (("<p>See also: " + " · ".join(f'<a href="{_esc(c["path"])}">{_esc(c["name"])}</a>'
                                                     for c in r["cards"]) + "</p>") if r.get("cards") else "")
                    + "</section>")
    body = (f'<article id="ssr" class="ssr"><h1>{_esc(name)}: {_esc(door[:1].lower() + door[1:])}</h1>'
            f'<p class="ssr-sub"><a href="{_esc(theme_path(tid))}">{_esc(name)}</a> · {len(im["rows"])} rows</p>'
            f'<p class="ssr-sub">{_esc(im.get("note") or "")}</p>'
            + _open_btn(path, f"Open {door[:1].lower() + door[1:]} in Bible Ontology")
            + "".join(rows) + "</article>")
    return head, body, path


# THE NAVIGATOR'S OWN PAGE. 2026-10-03: SEO gets a single
# generic graph link for questions like "how do I quickly navigate the
# nodes" -- one page that says what the Knowledge Graph Navigator is and
# how it is used, kept by search engines, while /graph/<id> defers to the
# card. It describes only what the Navigator does (its own hint in Explore).
GRAPH_STARTS = ("jesus", "david", "abraham", "moses", "paul", "jerusalem", "covenant_with_abraham",
                "ruth", "elijah", "peter")


def graph_page():
    d = load()
    title = "Bible Knowledge Graph Navigator: explore people, places and connections"
    summary = ("Draw any person, place or thing in the Bible with everything the text connects "
               "it to, one step out, and click to walk from one to the next. Each tie's "
               "thickness is how much the text gives the two together.")
    starts = [f'<a href="/graph/{_esc(i)}">{_esc(d["ents"][i]["name"])}</a>'
              for i in GRAPH_STARTS if i in d["ents"]]
    url = SITE + "/graph"
    head = (f"<title>{_esc(title)} · Bible Ontology</title>\n"
            f'<meta name="description" content="{_esc(summary)}">\n'
            f'<link rel="canonical" href="{url}">\n'
            f'<meta property="og:type" content="website">\n'
            f'<meta property="og:title" content="{_esc(title)}">\n'
            f'<meta property="og:description" content="{_esc(summary)}">\n'
            f'<meta property="og:url" content="{url}">\n')
    body = ('<article id="ssr" class="ssr"><h1>Knowledge Graph Navigator</h1>'
            '<p class="ssr-sub">Explore the Bible as a graph of people, places and connections</p>'
            + _open_btn("/graph", "Open the Navigator")
            + f"<p>{_esc(summary)}</p>"
            "<h2>How to use it</h2><ul>"
            "<li>It opens on the last card you looked at, or start from one below.</li>"
            "<li>Click any node to put it in the middle and see its own connections.</li>"
            "<li>Back steps to where you were; 'open card' opens the one in the middle "
            "with every verse.</li>"
            "<li>The Strength slider hides the weaker ties: how much the text gives two "
            "together, and how surely.</li>"
            "<li>Colours mark the kind of tie (family, place, meaning, and so on); the "
            "legend says which.</li></ul>"
            + (f"<h2>Start from</h2><p>{' · '.join(starts)}</p>" if starts else "")
            + '<p><a href="/">Open Bible Ontology</a> to read the text behind every tie.</p></article>')
    return head, body


# ABOUT, AT ITS OWN ADDRESS, AND /llms.txt. 2026-10-03: the site needs to
# prove credible with the chat engines, and let them know the
# principles of being text-based and unopinionated to the extent possible.
# Who built the site, its principles, what it does not attempt and where its
# words come from -- LIFTED from the app's own About view in index.html, not
# rewritten here, so the page a search engine keeps and the page a reader
# opens cannot say different things. A section that still holds a template
# value after the known ones are filled is left out rather than leaked.
ABOUT_SECTIONS = ("a-who", "a-principles", "a-not", "a-source")
_ABOUT = None


def _about_parts():
    global _ABOUT
    if _ABOUT is not None:
        return _ABOUT
    t = (STATIC / "index.html").read_text(encoding="utf-8")
    a = json.loads(answer("/api/about", ""))
    fill = [(r"\$\{/\*.*?\*/''\}", ""),
            (r"\$\{esc\(d\.source\)\}", _esc(a.get("source") or "")),
            (r"\$\{esc\(d\.translation\s*\|\|\s*'Berean Standard Bible'\)\}",
             _esc(a.get("translation") or "Berean Standard Bible"))]
    parts = []
    # AT A GLANCE first (2026-10-13): the overview above the folds,
    # plain text by its own rule; "Who built it" is a section like the rest
    m = re.search(r'<div class="aboutov">(.*?)</div>', t, re.S)
    if m:
        parts.append(("At a glance", m.group(1)))
    for sid in ABOUT_SECTIONS:
        m = re.search(r"\$\{sec\('" + re.escape(sid) + r"', '([^']*)', `(.*?)`(?:, [^)]*)?\)\}", t, re.S)
        if not m:
            continue
        body = m.group(2)
        for rx, to in fill:
            body = re.sub(rx, lambda _m, to=to: to, body, flags=re.S)
        if "${" in body:
            continue
        parts.append((m.group(1), body))
    _ABOUT = parts
    return parts


# AN EXPLORE GROUP AT ITS OWN ADDRESS (2026-10-04: consolidating on the
# explore page might work -- for searches
# no one else answers). /explore/told-again and /explore/shared carry every
# pair in plain HTML: the steps side by side, the explanation, the
# disclaimer. In the sitemap's pages; the app opens Explore at the group.
EXPLORE_PAGES = {
    "told-again": ("Stories told again in the Bible: the same steps, side by side",
                   "Stories in the Bible whose steps match -- Jesus asleep in the storm and Jonah, the "
                   "barley loaves and Elisha, Gibeah and Sodom -- each step quoted from both texts, with "
                   "where they differ. Not a claim that one was told with the other in mind."),
    "shared": ("What two Bible verses share: words taken up, images both use",
               "New Testament verses that take up Old Testament words, and images or expressions two "
               "verses both use -- ten horns, myriads of holy ones -- each explained from the text."),
}


# EVERY EXPLORE SECTION AT ITS OWN ADDRESS (2026-10-11: URLs for the
# various sections of the explore page that did not have them). The
# Patterns groups by a readable name (the app maps the same names to its
# group ids), and the top-level sections by theirs. Each page carries the
# group's own note and its rows, so a search engine reads what a reader sees.
EXPLORE_GROUPS = {"story-shapes": "shapes", "refrains": "refrains", "declared-repeats": "declared",
                  "role-patterns": "roles", "significant-numbers": "numbers", "messages": "messages",
                  "speech-acts": "acts", "how-the-text-is-built": "built", "for-digging": "dig"}
EXPLORE_SECTIONS = {
    "events": ("Events in the Bible, by kind", "The events the text tells, each a card with its passages: what happened, who was there, and where it is told again."),
    "lists": ("Lists in the Bible, in the text's own words", "The Bible's own lists -- the Beatitudes, the Ten Commandments, the armor of God and others -- each member in the Berean's words, checked against its verse."),
    "patterns": ("Patterns in the Bible: what recurs", "What the Bible repeats: the text's declared repeats, refrains and formulas, recurring story shapes, role patterns, messages, speech acts and significant numbers."),
    # "Schema", not "upper ontologies" (2026-10-21: it could even be called
    # schema, since "upper ontology" may not make sense); the address stays
    "upper-ontologies": ("The schema of Bible Ontology", "The vocabulary the graph is written in, published as pages to read and as RDF for semantic-web tools: the whole design as a map, and its meaning, structure, relation and claim vocabularies."),
}


def _explore_group_page(slug):
    gid = EXPLORE_GROUPS[slug]
    g = next((x for x in api_recurs(load(), {}).get("groups", []) if x["id"] == gid), None)
    if not g:
        return None
    title = f"{g['title']} in the Bible"
    summary = (g.get("note") or g["title"])[:300]
    rows = "".join(f"<li><b>{_esc(r.get('title') or '')}</b>"
                   + (f" — {_esc(str(r['sub']))}" if r.get("sub") else "") + "</li>"
                   for r in g.get("rows") or [])
    return title, summary, (f"<p>{_esc(g.get('note') or '')}</p>" if g.get("note") else "") + f"<ul>{rows}</ul>"


def explore_page(gid):
    if gid in EXPLORE_GROUPS or gid in EXPLORE_SECTIONS:
        got = _explore_group_page(gid) if gid in EXPLORE_GROUPS else (*EXPLORE_SECTIONS[gid], "")
        if got is None:
            return None
        title, summary, inner = got
        url = SITE + f"/explore/{gid}"
        head = (f"<title>{_esc(title)} · Bible Ontology</title>\n"
                f'<meta name="description" content="{_esc(summary)}">\n'
                f'<link rel="canonical" href="{url}">\n'
                f'<meta property="og:title" content="{_esc(title)}">\n'
                f'<meta property="og:description" content="{_esc(summary)}">\n'
                f'<meta property="og:url" content="{url}">\n')
        body = (f'<article id="ssr" class="ssr"><h1>{_esc(title)}</h1><p>{_esc(summary)}</p>'
                + _open_btn(f"/explore/{gid}", "Open in Bible Ontology's Explore")
                + inner + '<p><a href="/">Open Bible Ontology</a>.</p></article>')
        return head, body, f"/explore/{gid}"
    if gid not in EXPLORE_PAGES:
        return None
    d = load()
    title, summary = EXPLORE_PAGES[gid]
    parts = []
    if gid == "told-again":
        for r in _rows(ROOT / "ontology" / "relations" / "story-echoes.jsonl"):
            a, b = d["ents"].get(r["src"]), d["ents"].get(r["dst"])
            if a and b:
                # a pair's later side may cite several Gospels (Matt 4:4, Luke 4:4)
                def cites(x):
                    return ", ".join(x if isinstance(x, list) else [x])
                rows = "".join(f"<tr><td>“{_esc(p[0][1])}” {_esc(cites(p[0][0]))}</td>"
                               f"<td>“{_esc(p[1][1])}” {_esc(cites(p[1][0]))}</td></tr>"
                               for p in r.get("pairs") or [])
                parts.append(f'<h2><a href="/e/{_esc(_addr(r["src"]))}">{_esc(a["name"])}</a> and '
                             f'<a href="/e/{_esc(_addr(r["dst"]))}">{_esc(b["name"])}</a></h2>'
                             f"<table>{rows}</table>")
        for r in _rows(ROOT / "ontology" / "told-again.jsonl"):
            rows = "".join(f"<tr><td>“{_esc(x[1])}” {_esc(x[0])}</td><td>“{_esc(y[1])}” {_esc(y[0])}</td></tr>"
                           for x, y in r["beats"])
            parts.append(f"<h2>{_esc(r['later'])} and {_esc(r['earlier'])}</h2><table>{rows}</table>"
                         + (f"<p>{_esc(r['explanation'])}</p>" if r.get("explanation") else "")
                         + (f"<p>Where they differ: {_esc(r['differs'])}</p>" if r.get("differs") else ""))
        for x in _rows(ROOT / "ontology" / "allusions.jsonl"):
            if x["kind"] == "story_echo":
                rows = "".join(f"<tr><td>“{_esc(p[0][1])}” {_esc(p[0][0])}</td><td>“{_esc(p[1][1])}” "
                               f"{_esc(p[1][0])}</td></tr>" for p in x.get("beats") or [])
                parts.append(f"<h2>{_esc(x['nt'])} and {_esc(x['ot'])}</h2><table>{rows}</table>"
                             f"<p>{_esc(x.get('explanation') or '')}</p>")
        lead = ("Where one account takes up an earlier one — its words, or the steps of its story — set "
                "side by side in the text's own words. Not a claim that one was told with the other in "
                "mind; the reader draws the conclusion. Each is a reading, found by readers of every event "
                "and checked by two judges, by machine against the Berean, and by an eight-reader review.")
    else:
        nodes, words = {}, []
        for x in _rows(ROOT / "ontology" / "allusions.jsonl"):
            if x["kind"] == "shared_image":
                nodes.setdefault(x["node"], []).append(x)
            elif x["kind"] == "words_taken_up":
                words.append(x)
        parts.append("<h2>An image or expression both use</h2>")
        for n, xs in sorted(nodes.items(), key=lambda t: (-len(t[1]), t[0].lower())):
            vs = sorted({v for x in xs for v in (x["nt"], x["ot"])},
                        key=lambda r: _vkey_macula(_macula_ref(d, r)))
            parts.append(f"<h3>“{_esc(n)}”: {_esc(' · '.join(vs))}</h3>"
                         + "".join(f"<p>{_esc(x.get('explanation') or '')}</p>" for x in xs))
        parts.append("<h2>Words taken up</h2>")
        for x in sorted(words, key=lambda x: (_vkey_macula(_macula_ref(d, x["nt"])),
                                             _vkey_macula(_macula_ref(d, x["ot"])))):
            parts.append(f"<h3>{_esc(x['nt'])} and {_esc(x['ot'])}</h3>"
                         f"<p>{_esc(x.get('explanation') or '')}</p>")
        lead = ("A rare phrase two verses have word beside word in the Hebrew or Greek, read by two judges "
                "and explained: words one verse takes up from another, and images or expressions both use, "
                "with no claim that one points to the other. Each is a reading.")
    url = SITE + f"/explore/{gid}"
    head = (f"<title>{_esc(title)} · Bible Ontology</title>\n"
            f'<meta name="description" content="{_esc(summary)}">\n'
            f'<link rel="canonical" href="{url}">\n'
            f'<meta property="og:type" content="article">\n'
            f'<meta property="og:title" content="{_esc(title)}">\n'
            f'<meta property="og:description" content="{_esc(summary)}">\n'
            f'<meta property="og:url" content="{url}">\n')
    body = (f'<article id="ssr" class="ssr"><h1>{_esc(title)}</h1><p>{_esc(lead)}</p>'
            + _open_btn(f"/explore/{gid}", "Open in Bible Ontology's Explore")
            + "".join(parts) + '<p><a href="/">Open Bible Ontology</a>.</p></article>')
    return head, body, f"/explore/{gid}"


def about_page():
    parts = _about_parts()
    title = "About Bible Ontology: how this Bible knowledge graph is built"
    summary = ("What Bible Ontology is and who it is for, who built it, its principles -- built "
               "from the text, the original language decides, structure not doctrine, readings "
               "marked as readings -- what it does not attempt, and where its words come from.")
    url = SITE + "/about"
    head = (f"<title>{_esc(title)}</title>\n"
            f'<meta name="description" content="{_esc(summary)}">\n'
            f'<link rel="canonical" href="{url}">\n'
            f'<meta property="og:type" content="website">\n'
            f'<meta property="og:title" content="{_esc(title)}">\n'
            f'<meta property="og:description" content="{_esc(summary)}">\n'
            f'<meta property="og:url" content="{url}">\n')
    body = ('<article id="ssr" class="ssr"><h1>About Bible Ontology</h1>'
            '<p class="ssr-sub">A Bible knowledge graph, built from the text itself</p>'
            + _open_btn("/about", "Open About in Bible Ontology")
            + "".join(f"<h2>{_esc(h)}</h2>" + b for h, b in parts)
            + '<p><a href="/">Open Bible Ontology</a>.</p></article>')
    return head, body


def llms_txt():
    """The same text, plain, for language models (the /llms.txt convention),
    with how the site's addresses are shaped."""
    def plain(h):
        """Paragraphs, each on one line, a blank line between."""
        h = re.sub(r"<a [^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"\2 (\1)", h, flags=re.S)
        paras = []
        for p in re.split(r"</p>", h):
            t = re.sub(r"\s+", " ", html_unescape(re.sub(r"<[^>]+>", "", p))).strip()
            if t:
                paras.append(t)
        return "\n\n".join(paras)
    out = ["# Bible Ontology", "",
           "> A knowledge graph of the Bible built from the text itself: people, places, concepts, "
           "events and sayings, and the connections the text makes between them, each with its "
           "verse. Read in the Berean Standard Bible with the Hebrew, Aramaic and Greek beneath it.", ""]
    for h, b in _about_parts():
        # the "Who built it" paragraph opens with its own name in bold
        out += [f"## {h}", "", re.sub(r"^" + re.escape(h) + r"\.\s*", "", plain(b)), ""]
    out += ["## Addresses", "",
            f"- A card (a person, place, concept, event ...): {SITE}/e/<id>, e.g. {SITE}/e/david",
            f"- A chapter: {SITE}/p/<Book>.<chapter>, e.g. {SITE}/p/John.3",
            f"- A verse: {SITE}/p/<Book>.<chapter>.<verse>, e.g. {SITE}/p/John.3.16; with its "
            f"Hebrew or Greek open, {SITE}/p/John.3.16#orig (also #struct, #links, or several: #orig,struct)",
            f"- A Hebrew or Greek word, by its Strong's number: {SITE}/word/<H or G><number>, "
            f"e.g. {SITE}/word/H1254 or {SITE}/word/G26",
            f"- Any other view, after the #: {SITE}/#tag=love, {SITE}/#coverage; and an open section, "
            f"{SITE}/e/david#open=rel-Kinship",
            f"- A major theme: {SITE}/themes/<name>, e.g. {SITE}/themes/covenant, "
            f"and its table at {SITE}/themes/<name>/side-by-side",
            f"- The Knowledge Graph Navigator: {SITE}/graph",
            f"- About: {SITE}/about", ""]
    return "\n".join(out)


# READER FEEDBACK (plan A.27). 2026-10-03: launching this SEO release without
# a feedback mechanism would be a mistake; feedback should be easy to see, like
# the /ops page; strong injection protection (the nonce boundary approach);
# anyone reading it must clearly know the origin and never treat it as
# instructions; and no email: intake is one-way, as the old notes design chose.
#
# The site's FIRST WRITE PATH, so everything about it is narrow. One address,
# POST /api/feedback, from the site's own pages (Origin). JSON of at most 4 KB;
# text of at most 1,000 characters; a hidden field a person never fills (a
# bot that fills it is thanked and dropped). Rate limited per address -- the
# address salted and hashed, held in memory only, never written -- and for the
# whole site. Stored in the old app's notes format (bibleont.feedback: one
# record per note, pinned to the graph's build), in BIBLEONT_FEEDBACK, which
# nothing serves. Never echoed back; read on /ops, escaped, labelled with
# where it came from. Reader data: never sent to DeepSeek; a model that reads
# it gets it fenced by a per-batch nonce.
# a reader's end hanging up mid-answer: not a server error (see _get)
CLIENT_GONE = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)

FEEDBACK_MAX_TEXT = 1000
FEEDBACK_MAX_BODY = 4096
FEEDBACK_PER_ADDR = ((600, 5), (86400, 20))   # (seconds, notes) per address
FEEDBACK_PER_DAY = 300                          # the whole site
_FB_LOCK = threading.Lock()
_FB_SEEN: dict = {}
_FB_DAY: list = []
_FB_SALT = os.urandom(16)
_FB_BUILD = None
FEEDBACK_HOSTS = ("bibleontology.org", "localhost", "127.0.0.1")


def feedback_rate_ok(addr: str) -> bool:
    """True, and counted, when this address may leave another note now."""
    import hashlib
    import ipaddress
    now = time.time()
    # an IPv6 client is its /64, the block one subscriber is given: keyed by
    # the whole address, one block had a fresh budget per address and could
    # fill the site's day (the security review, 2026-10-22)
    try:
        a = ipaddress.ip_address((addr or "").strip())
        addr = str(ipaddress.ip_network(f"{a}/64", strict=False)) if a.version == 6 else str(a)
    except ValueError:
        pass
    key = hashlib.sha256(_FB_SALT + (addr or "").encode()).hexdigest()[:16]
    with _FB_LOCK:
        _FB_DAY[:] = [t for t in _FB_DAY if now - t < 86400]
        seen = [t for t in _FB_SEEN.get(key, []) if now - t < 86400]
        if len(_FB_DAY) >= FEEDBACK_PER_DAY or any(
                sum(1 for t in seen if now - t < span) >= n for span, n in FEEDBACK_PER_ADDR):
            _FB_SEEN[key] = seen
            return False
        seen.append(now)
        _FB_SEEN[key] = seen
        _FB_DAY.append(now)
        # forget addresses with nothing in the last day, so the map stays small
        for k in [k for k, v in _FB_SEEN.items() if not v or now - v[-1] >= 86400]:
            del _FB_SEEN[k]
        return True


def save_feedback(text: str, page: str, title: str, device: str, internal: bool) -> None:
    """One note, in the notes format, appended under a lock (one process)."""
    from bibleont import feedback, version
    global _FB_BUILD
    if _FB_BUILD is None:
        _FB_BUILD = version.build().as_dict()      # once: the graph does not change while running
    ctx = {"view": page[:200]}
    if title:
        ctx["query"] = title[:200]                 # the tab's title, as the reader saw it
    m = re.match(r"^/e/([^/?#]+)", page)
    if m:
        ctx["entity"] = unquote(m.group(1))[:200]
    m = re.match(r"^/p/([^/?#]+)", page)
    if m:
        ctx["verse"] = unquote(m.group(1))[:200]
    note = feedback.Note(id=os.urandom(5).hex(), at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                         text=text, context=ctx, build=_FB_BUILD,
                         channel="internal" if internal else "public",
                         device=device if device in ("desktop", "mobile") else "")
    with _FB_LOCK:
        feedback._append(note)


def with_card(page: bytes, head: str, body: str) -> bytes:
    """The app page with a card's own title, description and text. The
    page's own <title> is replaced; the card goes first in <body>."""
    t = page.decode("utf-8")
    # A RENAMED THEME ON EVERY PAGE BUILT HERE TOO: the home page lists the
    # themes from the records, not the API, and still said "Prophetic Word &
    # Fulfillment" after the rename (2026-10-06)
    for pat, name, first in _theme_renames():
        if first.lower() in (head + body).lower():
            head, body = pat.sub(name, head), pat.sub(name, body)
    t = re.sub(r"<title>.*?</title>\n?", lambda _m: head, t, count=1, flags=re.S)
    t = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + "\n" + body, t, count=1)
    return t.encode("utf-8")


def perf_rows(perf) -> str:
    from activity import perf_summary
    ms = lambda v: f"&lt;{v:,} ms"  # noqa: E731
    return "".join(
        f"<tr><td>{_esc(r['kind'])}</td><td class=n>{r['n']:,}</td><td class=n>{ms(r['p50'])}</td>"
        f"<td class=n>{ms(r['p95'])}</td><td class=n>{r['max']:,} ms</td></tr>"
        for r in perf_summary(perf)) or "<tr><td colspan=5 class=g>none</td></tr>"


def _bars(stacks, labels, tips, h=96, log=False, ticks=()):
    """A bar chart as inline SVG -- no script, so /ops keeps its CSP. `stacks`
    is [(colour, [value per bar])], drawn bottom up; with `log`, values are
    placed on a log scale (response times run from 1 ms to seconds) and the
    stacks overlay instead of adding (a typical time inside its 95th)."""
    import math
    n = len(labels)
    # width, left gutter, bottom gutter; text at 13 of 480 so a phone, which
    # draws the chart about 340 px wide, still shows it at 9 px
    W, L, B = 480, 44, 20
    bw = (W - L) / n
    if log:
        top = max([1000] + [v for _, vs in stacks for v in vs])
        y = lambda v: 0 if v <= 1 else (math.log10(v) / math.log10(top)) * h  # noqa: E731
    else:
        tot = [sum(vs[i] for _, vs in stacks) for i in range(n)]
        top = max(tot + [1])
        y = lambda v: v / top * h  # noqa: E731
    out = [f"<svg viewBox='0 0 {W} {h + B + 14}' width='100%' role='img' "
           f"style='display:block;margin:4px 0 2px'><g transform='translate(0,10)'>"]
    for t in (ticks if log else (top,)):
        ty = h + 2 - y(t)
        lab = (f"{t // 1000}s" if t >= 1000 else f"{t}ms") if log else f"{t:,}"
        out.append(f"<line x1='{L}' x2='{W}' y1='{ty:.1f}' y2='{ty:.1f}' stroke='#e3e1dc'/>"
                   f"<text x='{L - 4}' y='{ty + 4:.1f}' font-size='13' text-anchor='end' "
                   f"fill='#8a887f'>{lab}</text>")
    for i in range(n):
        x = L + i * bw + 1
        base = 0
        for colour, vs in stacks:
            v = vs[i]
            if not v:
                continue
            hh = y(v) if log else y(v)
            yy = h + 2 - (hh if log else base + hh)
            out.append(f"<rect x='{x:.1f}' y='{yy:.1f}' width='{bw - 2:.1f}' "
                       f"height='{max(hh if log else hh, 0.8):.1f}' fill='{colour}'>"
                       f"<title>{_esc(tips[i])}</title></rect>")
            if not log:
                base += hh
        if labels[i]:
            out.append(f"<text x='{x + (bw - 2) / 2:.1f}' y='{h + 18}' font-size='13' "
                       f"text-anchor='middle' fill='#8a887f'>{_esc(labels[i])}</text>")
    out.append(f"<line x1='{L}' x2='{W}' y1='{h + 2}' y2='{h + 2}' stroke='#b9b6ad'/></g></svg>")
    return "".join(out)


def ops_charts(day: str, c: dict, days: list, pick: str) -> str:
    """The time charts on /ops: one day by the hour (New York time) -- volume,
    response time, errors -- and the last days side by side. 2026-10-01:
    time based graphs or buckets with volumes, response times,
    and errors. """
    from activity import hour_summary
    H = hour_summary((c or {}).get("hours"))
    ampm = lambda h: f"{(h % 12) or 12}{'a' if h < 12 else 'p'}"  # noqa: E731
    lab = [ampm(r["hour"]) if r["hour"] % 3 == 0 else "" for r in H]
    PEOPLE, BOTS, P95, P50, E4, E5 = "#33415c", "#c9c6bd", "#d9b77a", "#a8742a", "#d9b77a", "#b3261e"
    vol = _bars([(PEOPLE, [r["people"] for r in H]), (BOTS, [r["bots"] for r in H])], lab,
                [f"{ampm(r['hour'])}: {r['people']} by people, {r['bots']} by bots, "
                 f"{r['pages']} page loads" for r in H])
    rt = _bars([(P95, [r["p95"] for r in H]), (P50, [r["p50"] for r in H])], lab,
               [f"{ampm(r['hour'])}: typical under {r['p50']:,} ms, 95% under {r['p95']:,} ms, "
                f"slowest {r['max']:,} ms ({r['n']} answered)" for r in H],
               log=True, ticks=(10, 100, 1000))
    err = _bars([(E5, [r["e5"] for r in H]), (E4, [r["e4"] for r in H])], lab,
                [f"{ampm(r['hour'])}: {r['e5']} server errors, {r['e4']} not found or refused"
                 for r in H])
    old = list(reversed(days))                  # oldest first, left to right
    dl = [d["day"][5:] for d in old]
    dvol = _bars([(PEOPLE, [d.get("requests_people", 0) for d in old]),
                  (BOTS, [d.get("requests_bots", 0) for d in old])], dl,
                 [f"{d['day']}: {d.get('visitors', 0)} visitors, {d.get('requests_people', 0)} "
                  f"requests by people, {d.get('requests_bots', 0)} by bots" for d in old])
    e5 = lambda d: sum(v for k, v in (d.get("status") or {}).items() if k.startswith("5"))  # noqa: E731
    e4 = lambda d: sum(v for k, v in (d.get("status") or {}).items() if k.startswith("4"))  # noqa: E731
    derr = _bars([(E5, [e5(d) for d in old]), (E4, [e4(d) for d in old])], dl,
                 [f"{d['day']}: {e5(d)} server errors, {e4(d)} not found or refused" for d in old])
    import datetime as _dt
    try:
        cur = _dt.date.fromisoformat(day)
        one = _dt.timedelta(days=1)
        prev, nxt = (cur - one).isoformat(), (cur + one).isoformat()
    except ValueError:
        prev = nxt = ""
    nav = (f"<p class=g><a href='/ops?day={prev}'>← {prev}</a>"
           + (f" · <a href='/ops?day={nxt}'>{nxt} →</a>" if pick else "")
           + (" · <a href='/ops'>today</a>" if pick else "") + "</p>")
    key = lambda *kv: " ".join(  # noqa: E731
        f"<span style='display:inline-block;width:9px;height:9px;background:{col};"
        f"margin:0 3px 0 8px'></span>{_esc(t)}" for col, t in kv)
    return (f"<h2>{_esc(day)}, by the hour (New York time)</h2>{nav}"
            + ("" if c else "<p class=g>Nothing recorded that day.</p>")
            + f"<p class=g style='margin:6px 0 0'>Requests{key((PEOPLE, 'people'), (BOTS, 'bots'))}</p>{vol}"
            f"<p class=g style='margin:10px 0 0'>Response time, log scale{key((P50, 'typical'), (P95, '95%'))}</p>{rt}"
            f"<p class=g style='margin:10px 0 0'>Errors{key((E5, 'server (5xx)'), (E4, 'not found or refused (4xx)'))}</p>{err}"
            f"<p class=g style='margin:6px 0 0'>Point at a bar for its numbers. Hours before this "
            f"chart existed (2026-10-01) are empty.</p>"
            f"<h2>{'The last day' if len(old) == 1 else f'The last {len(old)} days'}</h2>"
            f"<p class=g style='margin:6px 0 0'>Requests{key((PEOPLE, 'people'), (BOTS, 'bots'))}</p>{dvol}"
            f"<p class=g style='margin:10px 0 0'>Errors{key((E5, 'server (5xx)'), (E4, '4xx'))}</p>{derr}")


OPS_FEEDBACK_SHOWN = 40


def ops_feedback_rows(n: int = 100) -> list:
    """The latest notes as plain fields, newest first, for /ops.json. No read
    or unread state: newest first is enough (2026-10-03)."""
    try:
        from bibleont import feedback
        notes = sorted(feedback.load(), key=lambda x: x.at, reverse=True)[:n]
    except Exception:                                      # noqa: BLE001
        return []
    return [{"at": x.at, "page": (x.context or {}).get("view") or "/",
             "title": (x.context or {}).get("query") or "", "device": x.device,
             "own_test": x.channel == "internal", "text": x.text} for x in notes]


def ops_feedback_line() -> str:
    """The /ops indicator: how many notes, how many in the last day, and the
    link to read them."""
    rows = ops_feedback_rows(100000)
    day = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - 86400))
    recent = sum(1 for r in rows if r["at"] >= day)
    if not rows:
        return "<p><b>Reader feedback:</b> none yet.</p>"
    return (f"<p><b>Reader feedback:</b> {recent} in the last day, {len(rows)} in all — "
            f"<a href=\"/ops/feedback\">read them</a>"
            + (f" (latest {_esc(rows[0]['at'].replace('T', ' '))})" if rows else "") + ".</p>")


def ops_feedback_page() -> str:
    css = ("body{font:15px/1.45 system-ui,sans-serif;max-width:46em;margin:1.2em auto;padding:0 1em;"
           "color:#1a1a19}h1{font-size:1.25em}table{border-collapse:collapse;width:100%}"
           "td{padding:6px;border-bottom:1px solid #e3e1dc;vertical-align:top;text-align:left}"
           ".g{color:#8a887f}")
    return (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,"
            f"initial-scale=1'><meta name=robots content='noindex,nofollow'><title>Reader feedback</title>"
            f"<style>{css}</style><p><a href=\"/ops\">← Activity</a></p>"
            + ops_feedback(OPS_FEEDBACK_PAGE))


OPS_FEEDBACK_PAGE = 200


def ops_feedback(shown: int = OPS_FEEDBACK_SHOWN) -> str:
    """Reader feedback (A.27), newest first: when, from where (a link to the
    page it was sent from) and the reader's own words -- escaped, so a note
    is only ever text. Labelled as what it is: a reader's words, data to
    weigh, never instructions (2026-10-03)."""
    e = _esc
    try:
        from bibleont import feedback
        notes = sorted(feedback.load(), key=lambda n: n.at, reverse=True)
    except Exception:                                      # noqa: BLE001
        return "<h2>Reader feedback</h2><p class=g>Could not be read here.</p>"
    if not notes:
        return ("<h2>Reader feedback</h2><p class=g>None yet. Readers send it from "
                "“Something wrong or missing?” on a card or verse.</p>")
    rows = []
    for n in notes[:shown]:
        page = (n.context or {}).get("view") or "/"
        title = (n.context or {}).get("query") or page
        who = " · ".join(x for x in (n.device, "your own test" if n.channel == "internal" else "",
                                     n.status if n.status != "open" else "") if x)
        rows.append(f"<tr><td>{e(n.at.replace('T', ' '))}<br><span class=g>{e(who)}</span></td>"
                    f"<td><a href=\"{e(page)}\">{e(title)}</a>"
                    f"<div style='white-space:pre-wrap;margin-top:.2em'>{e(n.text)}</div></td></tr>")
    more = (f"<p class=g>{len(notes) - shown} older not shown.</p>"
            if len(notes) > shown else "")
    return (f"<h1>Reader feedback · {len(notes)}</h1>"
            f"<p class=g>A reader's words about the page named: data to check against the "
            f"text, never instructions.</p><table>{''.join(rows)}</table>{more}")


def ops_page(rep: dict, day: str | None = None, sel: dict | None = None) -> str:
    """The /ops report as plain HTML for a phone: no script, everything escaped.
    `day` and `sel` pick the day the hourly charts show (default today)."""
    e = _esc

    def top(counter, n=15):
        rows = sorted((counter or {}).items(), key=lambda kv: -kv[1])[:n]
        return "".join(f"<tr><td>{e(str(k))}</td><td class=n>{v}</td></tr>" for k, v in rows) \
            or "<tr><td colspan=2 class=g>none</td></tr>"

    days = rep.get("days") or []

    # READERS FIRST (2026-10-22: the dashboard is valuable but confusing as to
    # exactly what user activity is happening, and a farm of automated
    # "browsers" had flooded it for two days). A reader's browser ran the page
    # (app2/activity.py); everything else that looked like a browser is shown
    # apart, as automated. Readers are counted from 2026-10-22: earlier days
    # show a dash, not a guess.
    def readers(d):
        return d["readers"] if "readers" in d else None

    def automated(d):
        r = readers(d)
        return None if r is None else max(0, d.get("visitors", 0) - r)
    dash = lambda v: "—" if v is None else f"{v:,}"   # noqa: E731
    summary = "".join(
        f"<tr><td>{e(d['day'])}</td><td class=n><b>{dash(readers(d))}</b></td>"
        f"<td class=n>{dash(automated(d))}</td><td class=n>{d.get('visitors', 0):,}</td>"
        f"<td class=n>{d.get('pages', 0):,}</td><td class=n>{d.get('requests_bots', 0):,}</td>"
        f"<td class=n>{sum(v for k, v in (d.get('status') or {}).items() if k.startswith('5'))}</td></tr>"
        for d in days)
    t = days[0] if days else {}
    # THE WHOLE PAGE FOLLOWS THE DAY CHOSEN (2026-10-21: going back
    # in time, the whole page shows data for the date being viewed): the tables below "Today" show the chosen day, named, not
    # only the hourly charts
    when = "Today"
    if day and sel:
        t, when = sel, day
    blog_all = collections.Counter()
    ns_all = collections.Counter()
    for d in days:
        blog_all.update(d.get("blog") or {})
        ns_all.update(d.get("ns") or {})
        ns_all.update(d.get("ns_tools") or {})
    checks = (f" Our own checks today (load tests, probes), counted nowhere else: "
              f"{t['checks']:,}." if t.get("checks") else "")

    # THE DAY IN PLAIN WORDS: what readers did, then what else came
    def n(counter):
        return sum((counter or {}).values())

    def plural(k, word, many=None):
        return f"{k:,} {word if k == 1 else (many or word + 's')}"
    r_today = readers(t)
    did = [x for x in (
        plural(n(t.get("cards")), "card") + " opened" if n(t.get("cards")) else "",
        plural(n(t.get("chapters")), "chapter") + " read" if n(t.get("chapters")) else "",
        plural(n(t.get("searches")), "search", "searches") if n(t.get("searches")) else "",
        plural(n(t.get("themes")) + n(t.get("tags")), "theme or tag", "themes or tags") + " opened"
        if n(t.get("themes")) + n(t.get("tags")) else "",
        plural(n(t.get("blog")), "blog view") if n(t.get("blog")) else "") if x]
    came = ", ".join(f"{e(k)} ({v})" for k, v in sorted((t.get("referrers") or {}).items(),
                                                       key=lambda kv: -kv[1])[:4])
    words = (f"<p style='font-size:1.05em'><b>{e(when)}: "
             + (f"{plural(r_today, 'reader')}</b> (their browser ran the page)" if r_today is not None
                else "readers are counted from 22 October 2026</b>")
             + (f". Between them: {', '.join(did)}." if did else ".")
             + (f" They came from {came}." if came else "")
             + "</p><p class=g>Not readers: "
             + (f"{automated(t):,} browser-like visitors that never ran the page (automated), and "
                if automated(t) is not None else "")
             + f"{t.get('requests_bots', 0):,} requests from tools and crawlers that name themselves.</p>")
    recent = lambda xs, k: "".join(  # noqa: E731
        f"<tr><td>{e(x['at'])}</td><td>{e(x['path'])}</td><td class=n>{e(str(x[k]))}</td></tr>"
        for x in reversed(xs or [])) or "<tr><td colspan=3 class=g>none</td></tr>"
    css = ("body{font:15px/1.45 system-ui,sans-serif;max-width:46em;margin:1.2em auto;padding:0 1em;"
           "color:#1a1a19}h1{font-size:1.25em}h2{font-size:1em;margin:1.4em 0 .3em;color:#52514e}"
           "table{border-collapse:collapse;width:100%}td,th{padding:3px 6px;border-bottom:1px solid #e3e1dc;"
           "text-align:left}th{font-weight:600;font-size:.85em;color:#52514e}.n{text-align:right}"
           ".g{color:#8a887f}")
    return (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,"
            f"initial-scale=1'><meta name=robots content='noindex,nofollow'><title>Activity</title>"
            f"<style>{css}</style><h1>Activity</h1>"
            f"{words}"
            f"{ops_feedback_line()}"
            f"{ops_charts(day or t.get('day', ''), sel if day else t, days, day or '')}"
            f"<h2>By day</h2><table><tr><th>day</th><th class=n>readers</th><th class=n>automated</th>"
            f"<th class=n>all browser-like</th><th class=n>page loads</th><th class=n>tool requests</th>"
            f"<th class=n>errors</th></tr>{summary}</table>"
            f"<p class=g>Readers: their browser ran the page. Automated: looked like a browser, never ran it. "
            f"Page loads include both. Tool requests: crawlers and scripts that say what they are.</p>"
            f"<p class=g>Server memory: {e(str(rep['memory_mb']) + ' MB') if rep.get('memory_mb') else 'not available here'}. "
            f"{e(rep.get('note', ''))}{checks}</p>"
            # THE BLOG (2026-10-05: track blog views on ops): views by
            # people, never bots, today and over the days shown
            f"<h2>The blog: views {'today' if when == 'Today' else 'on ' + e(when)}, and over {len(days)} "
            f"day{'s' if len(days) != 1 else ''}</h2>"
            f"<table><tr><th>page</th><th class=n>{'today' if when == 'Today' else e(when)}</th>"
            f"<th class=n>all days shown</th></tr>"
            + ("".join(f"<tr><td>{e(k)}</td><td class=n>{(t.get('blog') or {}).get(k, 0)}</td>"
                       f"<td class=n>{v}</td></tr>" for k, v in blog_all.most_common())
               or "<tr><td colspan=3 class=g>none yet</td></tr>") + "</table>"
            # THE PUBLISHED ONTOLOGY (/ns; the committee's practitioner, W1):
            # the vocabularies, the map and the alignment, by people and by
            # tools (Turtle fetches, crawlers), today and over the days shown
            f"<h2>The published ontology (/ns): {'today' if when == 'Today' else e(when)}, and over {len(days)} "
            f"day{'s' if len(days) != 1 else ''}</h2>"
            f"<table><tr><th>address</th><th class=n>people</th><th class=n>tools</th>"
            f"<th class=n>all days shown</th></tr>"
            + ("".join(f"<tr><td>{e(k)}</td><td class=n>{(t.get('ns') or {}).get(k, 0)}</td>"
                       f"<td class=n>{(t.get('ns_tools') or {}).get(k, 0)}</td>"
                       f"<td class=n>{v}</td></tr>" for k, v in ns_all.most_common(40))
               or "<tr><td colspan=4 class=g>none yet</td></tr>") + "</table>"
            f"<h2>{e(when)}:&#32;cards opened</h2><table>{top(t.get('cards'))}</table>"
            # the card-sections review (2026-10-13): which sections readers
            # open, by id alone, and how often they open them all
            f"<h2>{e(when)}:&#32;card sections opened</h2><table>{top(t.get('sections'))}</table>"
            f"<h2>{e(when)}:&#32;chapters read</h2><table>{top(t.get('chapters'))}</table>"
            f"<h2>{e(when)}:&#32;searches</h2><table>{top(t.get('searches'))}</table>"
            f"<h2>{e(when)}:&#32;themes and tags</h2><table>{top({**(t.get('themes') or {}), **(t.get('tags') or {})})}</table>"
            f"<h2>{e(when)}:&#32;came from</h2><table>{top(t.get('referrers'))}</table>"
            f"<h2>{e(when)}:&#32;readers by device, browser and system</h2>"
            f"<p class=g>Readers only from 22 October 2026; before that, every browser-like visitor.</p>"
            f"<table>{top(t.get('devices'))}</table><table>{top(t.get('browsers'))}</table>"
            f"<table>{top(t.get('systems'))}</table>"
            f"<p class=g>Countries are in Cloudflare's dashboard; the site does not ask.</p>"
            f"<p>Structure panels opened: {t.get('structure', 0)} · connections: {t.get('connections', 0)}</p>"
            f"<h2>{e(when)}:&#32;how fast, by activity</h2><p class=g>Typical and 95th-percentile times "
            f"are bucketed (“under 200 ms”); slowest is exact.</p>"
            f"<table><tr><th>activity</th><th class=n>count</th><th class=n>typical</th>"
            f"<th class=n>95%</th><th class=n>slowest</th></tr>{perf_rows(t.get('perf'))}</table>"
            f"<h2>{e(when)}:&#32;server errors</h2><table>{recent(t.get('errors'), 'status')}</table>"
            f"<h2>{e(when)}:&#32;slow requests (over 2 s)</h2><table>{recent(t.get('slow'), 'ms')}</table>")


def main() -> int:
    port = 8001
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    print(f"Explorer starting on http://localhost:{port}")
    load()
    d = _data
    print(f"  {len(d['verses']):,} verses · {len(d['nodes']):,} nodes · "
          f"{len(d['byref']):,} units · {len(d['profiles']):,} word profiles")
    # warmed before the port opens, so Caddy's splash covers it (see
    # _warm_structure); the theme pages after, in the background
    _warm_structure()
    import threading
    threading.Thread(target=_warm_themes, daemon=True).start()
    # counting reader activity starts with the server, not when a tool imports
    # this module (app2/activity.py)
    global ACTIVITY
    import activity
    ACTIVITY = activity.Activity()
    print(f"  counting activity in {ACTIVITY.dir}"
          f"{'' if activity.ops_token() else ' (no ops-token: /ops is off)'}", flush=True)
    # A LISTEN QUEUE OF 64, not Python's default of 5. The 2026-10-02
    # evaluation ran four local instances under 16 parallel clients and 24 of
    # 9,844 searches were refused outright -- every one succeeded on retry,
    # so it was the queue, not the work. A burst from a shared link would
    # meet the same five slots; Linux caps this at net.core.somaxconn.
    class Server(ThreadingHTTPServer):
        request_queue_size = 64
    Server(("127.0.0.1", port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
