"""Which original-language word a node is actually about.

The graph was keyed to English, and English lies in both directions. It merged
`wisdom` with `understanding`, which are H2451 and H0998 and share nothing but
a translator's habit; and it was about to split `trust` from `refuge`, which
are one word, H2620, rendered two ways in Ps 34:8 by translators who disagreed.
**No amount of reading English can tell those two situations apart.**

So node identity moves to the lemma, and English becomes a display label.

## How a node's lemma is found without a tagged KJV

STEPBible's tagged texts give every Hebrew and Greek word with its verse, its
disambiguated Strong's number and an English gloss -- but aligned to the
original, not to the KJV. There is no column saying "this KJV word is that
lemma".

There does not need to be. Every node already carries citations, so:

    `wisdom` cites Prov 9:10, Ps 111:10, Job 28:28
    which lemma appears in all three?  ->  H2451, and nothing else does

The alignment is derived from data we can cite rather than trusted from
someone's scrape, and it degrades honestly: a node with several citations
resolves cleanly, a node with one comes back ambiguous and goes to the queue,
which is what the queue is for.

## Scoring

**Coverage** is the fraction of the node's cited verses containing the lemma.
A lemma in all of them is the candidate.

**Specificity** breaks the ties, because "and" is also in all of them. A lemma
found in nine thousand verses says nothing about a node cited in three; one
found in forty says a great deal. Ranking is coverage first, then rarity.

## What may be committed, and what may not

STEPBible is CC BY 4.0 with an explicit condition: *refer others to
github.com/STEPBible as the source, please do not redistribute it yourself.*

So the **dataset** stays in `data/raw/stepbible/`, gitignored, fetched by
whoever clones this, and the indexes built from it are gitignored for the same
reason. Nobody should get their data second-hand from us.

Their licence is explicit that *using* it is a different matter: "include any
part of this data in software or publications without requesting permission".
So a node carries its Strong's code, the word in its own script, and a short
gloss -- enough for a reader to check the claim rather than take a catalogue
number on trust -- with the credit in `lemma_source` on every record that has
one, and in the About view.

The distinction that matters: **redistributing the corpus is discouraged,
building on it is invited.**
"""

from __future__ import annotations

import glob
import io
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

from .paths import ROOT

RAW = ROOT / "data" / "raw" / "stepbible"
INDEX = RAW / "index.json"

# STEPBible's three-letter codes to the abbreviations this graph cites with.
BOOKS = {
    "Gen": "Gen", "Exo": "Exod", "Lev": "Lev", "Num": "Num", "Deu": "Deut",
    "Jos": "Josh", "Jdg": "Judg", "Rut": "Ruth", "1Sa": "1Sam", "2Sa": "2Sam",
    "1Ki": "1Kgs", "2Ki": "2Kgs", "1Ch": "1Chr", "2Ch": "2Chr", "Ezr": "Ezra",
    "Neh": "Neh", "Est": "Esth", "Job": "Job", "Psa": "Ps", "Pro": "Prov",
    "Ecc": "Eccl", "Sng": "Song", "Isa": "Isa", "Jer": "Jer", "Lam": "Lam",
    "Ezk": "Ezek", "Dan": "Dan", "Hos": "Hos", "Jol": "Joel", "Amo": "Amos",
    "Oba": "Obad", "Jon": "Jonah", "Mic": "Mic", "Nam": "Nah", "Hab": "Hab",
    "Zep": "Zeph", "Hag": "Hag", "Zec": "Zech", "Mal": "Mal", "Mat": "Matt",
    "Mrk": "Mark", "Luk": "Luke", "Jhn": "John", "Act": "Acts", "Rom": "Rom",
    "1Co": "1Cor", "2Co": "2Cor", "Gal": "Gal", "Eph": "Eph", "Php": "Phil",
    "Col": "Col", "1Th": "1Thess", "2Th": "2Thess", "1Ti": "1Tim",
    "2Ti": "2Tim", "Tit": "Titus", "Phm": "Phlm", "Heb": "Heb", "Jas": "Jas",
    "1Pe": "1Pet", "2Pe": "2Pet", "1Jn": "1John", "2Jn": "2John",
    "3Jn": "3John", "Jud": "Jude", "Rev": "Rev",
}

# Ref is Book.Chap.Verse, optionally with the Hebrew numbering in brackets,
# then #word=texttype:  Psa.34.8(34.9)#01=L
_REF = re.compile(r"^([A-Za-z0-9]+)\.(\d+)\.(\d+)(?:\([^)]*\))?#")
# The two files are laid out differently and neither says so in a header, so
# the parser is chosen by filename.
#
#   TAHOT   ref | Hebrew | translit | English | H9005/{H3045}
#           the root sits in curly brackets, prefixes and suffixes outside
#   TAGNT   ref | Greek (translit) | English | G0976=N-NSF | lemma=gloss
#           no brackets; the dStrong is the head of the grammar field
#
# Reading TAGNT with the TAHOT parser is silent -- it finds no braces and
# returns nothing at all, which is how the whole Greek New Testament came back
# as zero words on the first build without raising anything.
_ROOT = re.compile(r"\{([HG]\d+[A-Za-z]?)\}")
_GREEK = re.compile(r"^([HG]\d+[A-Za-z]?)=")


def _fields(path: str) -> tuple[int, int]:
    """(gloss column, strongs column) for this file's layout."""
    return (2, 3) if "TAGNT" in os.path.basename(path) else (3, 4)

# A lemma in more than this share of all verses is a function word.
STOPWORD_SHARE = 0.12

_INDEX: dict | None = None


def build(verbose: bool = True) -> dict:
    """Parse the tagged texts into {verse: [[gloss, root], ...]}."""
    verses: dict[str, list] = defaultdict(list)
    files = sorted(glob.glob(str(RAW / "TA*")))
    if not files:
        raise SystemExit(
            f"no STEPBible data in {RAW}.\n"
            "Fetch it from github.com/STEPBible/STEPBible-Data (CC BY 4.0);\n"
            "it is deliberately not committed -- their licence asks that it be\n"
            "distributed from their repository only.")
    for path in files:
        n = 0
        gcol, scol = _fields(path)
        greek = "TAGNT" in os.path.basename(path)
        for line in io.open(path, encoding="utf-8", errors="replace"):
            m = _REF.match(line)
            if not m:
                continue
            book = BOOKS.get(m.group(1))
            if not book:
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) <= scol:
                continue
            if greek:
                g = _GREEK.match(cols[scol].strip())
                roots = [g.group(1)] if g else []
            else:
                roots = _ROOT.findall(cols[scol])
            if not roots:
                continue
            ref = f"{book} {m.group(2)}:{m.group(3)}"
            gloss = cols[gcol].strip()
            for r in roots:
                verses[ref].append([gloss, r])
            n += 1
        if n == 0:
            raise SystemExit(
                f"parsed 0 words from {os.path.basename(path)} -- the layout "
                f"is not what _fields() expects. Check the columns before "
                f"trusting any index built from it.")
        if verbose:
            print(f"  {n:>7,} words  {os.path.basename(path)[:46]}")
    freq = Counter()
    for rows in verses.values():
        for _, root in set(tuple(x) for x in rows):
            freq[root] += 1
    out = {"verses": verses, "freq": freq}
    INDEX.write_text(json.dumps(out), encoding="utf-8", newline="")
    if verbose:
        print(f"  {len(verses):,} verses, {len(freq):,} distinct lemmas "
              f"-> {INDEX.relative_to(ROOT)}")
    return out


FORMS = RAW / "forms.json"
_FORMS: dict | None = None


def build_forms(verbose: bool = True) -> dict:
    """lemma -> (word in its own script, commonest English gloss).

    The index carries glosses per verse, which answers "which lemma is this
    node" and cannot answer "what does H2451 look like in Hebrew". A reader who
    wants to check our work needs the word itself, not a catalogue number.

    STEPBible's licence permits exactly this -- *include any part of this data
    in software or publications without requesting permission* -- provided the
    credit is given and people are pointed at their repository for the data
    itself. Seventy-odd words in a detail panel is squarely that.

    The commonest form is taken rather than the first, because Hebrew inflects:
    the same root appears as several surface forms and the modal one is the
    closest thing to a dictionary entry we can get without a lexicon.
    """
    out: dict[str, Counter] = defaultdict(Counter)
    gl: dict[str, Counter] = defaultdict(Counter)
    for path in sorted(glob.glob(str(RAW / "TA*"))):
        gcol, scol = _fields(path)
        greek = "TAGNT" in os.path.basename(path)
        for line in io.open(path, encoding="utf-8", errors="replace"):
            if not _REF.match(line):
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) <= scol:
                continue
            if greek:
                m = _GREEK.match(cols[scol].strip())
                if not m:
                    continue
                pairs = [(m.group(1), cols[1].split("(")[0].strip(),
                          cols[gcol].strip())]
            else:
                # Hebrew, English and dStrongs are all split on "/" into the
                # same segments -- prefixes, root, suffixes -- so the root is
                # the segment whose Strong's is in curly brackets.
                #
                # Taking the LAST segment instead was the first attempt and it
                # collected suffixes: H2617A (chesed) came out as the
                # possessive ending glossed "his", because "his lovingkindness"
                # is written root/suffix and the suffix is last.
                segs = cols[scol].split("/")
                heb = cols[1].split("/")
                eng = cols[gcol].split("/")
                pairs = []
                for i, seg in enumerate(segs):
                    m = _ROOT.search(seg)
                    if not m:
                        continue
                    pairs.append((m.group(1),
                                  heb[i].strip() if i < len(heb) else "",
                                  eng[i].strip() if i < len(eng) else ""))
            for root, word, g in pairs:
                # "\" separates trailing punctuation (sof pasuq, maqqef) from
                # the word in their notation; it is not part of the lemma.
                word = word.split("\\")[0].strip()
                g = g.split("\\")[0].strip()
                if word:
                    out[root][word] += 1
                if g and not g.startswith("<") and not g.startswith("["):
                    gl[root][g] += 1
    table = {r: [c.most_common(1)[0][0],
                 gl[r].most_common(1)[0][0] if gl.get(r) else ""]
             for r, c in out.items() if c}
    FORMS.write_text(json.dumps(table, ensure_ascii=False),
                     encoding="utf-8", newline="")
    if verbose:
        print(f"  {len(table):,} lemma forms -> {FORMS.relative_to(ROOT)}")
    return table


LEXICON = RAW / "lexicon.json"
_LEX: dict | None = None

# THE ENTRY IS SHOWN WHOLE (2026-10-26). It was cut at 340 characters "because
# a detail panel wants the sense, not the article", and the cut landed
# mid-entry ("... 1a5b)") on the live card of אהב; the word cards are now what
# a search engine reads, and half an outline reads as a fault. The cards
# fold the entry under its own heading, so its length costs the reader nothing.

# NO KJV RENDERING IS SHOWN, ANYWHERE (the site removes every visible trace of
# KJV text). STEP's entries carry some, in two shapes: a name's "also called
# Jeiel (Ketiv: Jeuel; KJV: Jehiel)", and Abbott-Smith's "(AV, such as is
# common to man)" -- the Authorised Version is the KJV. A parenthesis that
# names either is cut out whole; an entry still naming either afterwards
# (the 15 where it stands in a clause -- "also called in KJV: Dodavah;") is
# withheld rather than shown with the rendering in it. Measured 2026-10-26
# over the 22,717 rows of both lexicons: 147 name the KJV or the AV, 132 are
# cleared by the cut, 15 are withheld.
_KJV = re.compile(r"\b(?:KJV|AV|A\.V\.|KJB)\b")


def scrub_translation(text: str) -> str:
    """The entry without its KJV/AV renderings, or "" if one cannot be cut out
    cleanly. Idempotent."""
    if not text or not _KJV.search(text):
        return text or ""
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i] == "(":
            depth, j = 0, i
            while j < n:
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j < n and _KJV.search(text[i:j + 1]):
                while out and out[-1] == " ":
                    out.pop()
                i = j + 1
                continue
        out.append(text[i])
        i += 1
    cut = re.sub(r"\s+([,;.:])", r"\1", "".join(out))
    return "" if _KJV.search(cut) else cut


def headline_gloss(gloss: str) -> str:
    """The word's main sense from a STEP gloss. The brief lexicons write a
    word's sub-meaning after a colon -- "to love: lover", "to love: friend",
    "land: soil", "angel: messenger" -- and an entry for the participle
    ("friend") must not head the word's card. The part before the colon is the
    umbrella sense."""
    g = (gloss or "").strip()
    return g.split(":", 1)[0].strip() if ":" in g else g


def variant_entries(raw: dict) -> dict[str, list]:
    """Entries for the Strong's numbers STEP holds only as letter variants.

    STEP splits some numbers into homograph entries by BDB (H6213a "to make",
    H6213b "to press"; H4480a "from", H4480b "portion"), and a word card is
    keyed by the number alone, so none of the 538 numbers split that way and
    used in the text (67,930 uses, among them 'house', 'son', 'do', 'for')
    had a lexicon entry at all (measured 2026-10-26). The card shows STEP's
    entries for the number, each headed by its own sense; it does NOT choose
    one (the first letter is not reliably the main sense: H1004a is "place",
    H1004b "house: home"), so the number has no headline sense from here.
    Keyed by the zero-padded number, like the other entries.
    """
    bare = {(c[0], int(c[1:])) for c in raw if re.fullmatch(r"[HG]\d+", c)}
    groups: dict[tuple, list] = {}
    for code in raw:
        m = re.fullmatch(r"([HG])0*(\d+)([A-Za-z])", code)
        if m and (m.group(1), int(m.group(2))) not in bare:
            groups.setdefault((m.group(1), int(m.group(2))), []).append((m.group(3).lower(), code))
    out: dict[str, list] = {}
    for (lang, num), vs in groups.items():
        vs.sort()
        ents = [(letter, raw[code]) for letter, code in vs]
        agree = lambda i: ents[0][1][i] if len({e[i] for _l, e in ents}) == 1 else ""  # noqa: E731
        lines = []
        for letter, e in ents:
            lines.append(f"Entry ({letter}) — {headline_gloss(e[3])}")
            if len(e) > 4 and e[4]:
                lines.append(e[4])
        out[f"{lang}{num:04d}"] = [agree(0), agree(1), agree(2), "", " · ".join(lines)]
    return out


def tbes_entries() -> dict[str, list]:
    """eStrong -> [dictionary form, transliteration, part of speech, gloss,
    definition], from TBESH and TBESG as STEP publishes them.

    **One row per number, and the main one.** STEP splits a number into
    disambiguated rows (H0157G "to love: lover", H0157H "a Meaning of H0157G"
    "to love: friend"), and the build kept the LAST: אהב was headed "friend",
    and H0430 (God) was headed "(Gibeath)-elohim", a combined name. The row
    whose dStrong is a plain "=" is the word itself; with none (H0430's three
    are all "a Name of / a Part of"), the first row, which is STEP's own
    order of precedence.
    """
    rows: dict[str, list] = {}
    for path in sorted(glob.glob(str(RAW / "TBES*"))):
        for line in io.open(path, encoding="utf-8", errors="replace"):
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 7 or not re.match(r"^[HG]\d+[A-Za-z]?$", cols[0]):
                continue
            rows.setdefault(cols[0], []).append(cols)
    out: dict[str, list] = {}
    for code, group in rows.items():
        cols = next((c for c in group if re.search(r"=\s*$", c[1])), group[0])
        out[code] = [
            cols[3].strip(),                        # dictionary form
            cols[4].strip(),                        # transliteration
            cols[5].strip(),                        # part of speech
            cols[6].strip(),                        # short gloss
            # a row for a sub-meaning opens with its own colon fragment
            # (": lover"), which the gloss already carries; the outline follows.
            # And its closing "Also means: a.hav (אָהֵב ": friend" H0157H)" is
            # a pointer to STEP's other row of the same word, in STEP's own
            # codes, and shows the participle's sense again: left out (176 rows)
            scrub_translation(re.sub(r"\s*(?:·\s*)?Also means:[^·]*", "",
                                     re.sub(r"^:[^·]*(?:·\s*)?", "", _plain(cols[7]))).strip(" ·")
                              ) if len(cols) > 7 else "",
        ]
    return out


def _plain(html: str) -> str:
    """Strip the lexicons' markup without losing the sense divisions."""
    t = re.sub(r"<ref='[^']*'>|</ref>", "", html)
    t = re.sub(r"<BR\s*/?>|<br\s*/?>", " · ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = t.replace("&amp;", "&").replace("&nbsp;", " ")
    t = re.sub(r"\s+", " ", t).strip(" ·\t")
    return t


def build_lexicon(verbose: bool = True) -> dict:
    """code -> dictionary form, transliteration, part of speech, gloss, sense.

    From TBESH (Hebrew, after Brown-Driver-Briggs 1906) and TBESG (Greek,
    after Abbott-Smith 1922). Both are public domain by age and both are keyed
    to the same extended Strong's numbers the nodes already carry, so this is a
    join rather than an alignment problem.

    **The dictionary form is better than the one `build_forms` derives.** That
    one takes the commonest surface form out of running text, so H2617A came
    back as `חַסְדּ` -- chesed with its ending sheared off by a suffix. The
    lexicon gives `חֶסֶד`, which is what a reader would look up.
    """
    out = tbes_entries()
    if verbose:
        print(f"  {len(out):>6,} entries from {len(glob.glob(str(RAW / 'TBES*')))} lexicons")
    LEXICON.write_text(json.dumps(out, ensure_ascii=False),
                       encoding="utf-8", newline="")
    if verbose:
        print(f"  {len(out):,} lemmas -> {LEXICON.relative_to(ROOT)}")
    return out


def lexicon() -> dict:
    global _LEX
    if _LEX is None:
        _LEX = (json.loads(LEXICON.read_text(encoding="utf-8"))
                if LEXICON.exists() else build_lexicon(verbose=False))
    return _LEX


def forms() -> dict:
    global _FORMS
    if _FORMS is None:
        _FORMS = (json.loads(FORMS.read_text(encoding="utf-8"))
                  if FORMS.exists() else build_forms(verbose=False))
    return _FORMS


def load() -> dict:
    global _INDEX
    if _INDEX is None:
        if not INDEX.exists():
            _INDEX = build(verbose=False)
        else:
            _INDEX = json.loads(INDEX.read_text(encoding="utf-8"))
    return _INDEX


def candidates(refs: list[str], top: int = 5) -> list[tuple]:
    """Rank lemmas by how well they explain this set of citations.

    Returns (root, coverage, corpus_frequency, score, sample_gloss).
    """
    ix = load()
    verses, freq = ix["verses"], ix["freq"]
    present = [r for r in refs if r in verses]
    if not present:
        return []
    seen = Counter()
    gloss: dict[str, str] = {}
    for ref in present:
        # Deduplicate on the ROOT, not on (gloss, root). A word can appear
        # twice in one verse under different glosses -- "thrones" and "his
        # throne" -- and counting the pair made coverage exceed 100%, which
        # is not merely untidy: coverage is a fraction of verses and a value
        # above 1.0 outranks every honest candidate.
        for root in {r for _g, r in verses[ref]}:
            seen[root] += 1
        for g, root in verses[ref]:
            gloss.setdefault(root, g)
    total = len(verses)
    out = []
    for root, n in seen.items():
        corpus = freq.get(root, 1)
        # A function word carries no information about what a node is about,
        # however completely it covers the citations. G3588 -- the Greek
        # article -- is in 13,931 verses, so it covers *everything* and the
        # first scoring here duly resolved `faith` to "the". Damping was too
        # gentle; a lemma this common is excluded outright.
        if corpus > total * STOPWORD_SHARE:
            continue
        coverage = n / len(present)
        # Inverse document frequency, which is the right shape: a lemma in 240
        # verses is worth six times one in 13,931, not marginally more.
        score = coverage * math.log(total / corpus)
        out.append((root, coverage, corpus, score, gloss.get(root, "")))
    out.sort(key=lambda t: -t[3])
    return out[:top]


NT = set("Matt Mark Luke John Acts Rom 1Cor 2Cor Gal Eph Phil Col 1Thess "
         "2Thess 1Tim 2Tim Titus Phlm Heb Jas 1Pet 2Pet 1John 2John 3John "
         "Jude Rev".split())


def testament(ref: str) -> str:
    return "G" if ref.rsplit(" ", 1)[0] in NT else "H"


def by_language(refs: list[str]) -> dict[str, str | None]:
    """Resolve the Hebrew and Greek halves of a node separately.

    A node citing both testaments cannot have one lemma, and treating that as
    ambiguity hides the actual finding. `wisdom` cites eighteen verses and is
    H2451 in the Hebrew ones and G4678 in the Greek -- not a failure to
    resolve, but **two words that English renders alike**, which is exactly the
    cross-language case that wants two nodes and a stated mapping between them
    rather than a silent merge.

    Returns {"H": lemma or None, "G": lemma or None}, omitting a language the
    node does not cite.
    """
    out: dict[str, str | None] = {}
    for lang in ("H", "G"):
        side = [r for r in refs if testament(r) == lang]
        if side:
            out[lang] = resolved(side)
    return out


def resolved(refs: list[str], floor: float = 0.4,
             margin: float = 1.3) -> str | None:
    """The lemma this node is most likely about, or None if it is a close call.

    Requiring the lemma in *every* cited verse was the first attempt and it is
    wrong, because **a node's citations are verses relevant to the idea, not
    occurrences of the word.** `wisdom` cites Prov 1:7 -- "the fear of the LORD
    is the beginning of knowledge" -- which is H1847 and contains no H2451 at
    all. The citation is sound and the word is absent.

    So the test is a plurality with a clear margin: the top candidate must
    appear in at least `floor` of the cited verses and outscore the runner-up
    by `margin`. Anything closer is a judgement call and says so, which costs a
    place in the queue and never costs a wrong lemma silently written onto a
    node.
    """
    rows = candidates(refs, top=8)
    if not rows:
        return None
    if rows[0][1] < floor:
        return None
    if len(rows) == 1:
        return rows[0][0]
    return rows[0][0] if rows[0][3] >= rows[1][3] * margin else None


def _accounts_for(words: list[str], gloss: str, close: float = 0.8) -> bool:
    """Does a lemma's English gloss account for any word of a node's name?
    A shared stem (first five letters, as the phrase test uses), or two words
    WordNet puts close together (Wu-Palmer >= `close`, same part of speech).
    Without WordNet installed, the stem test alone decides."""
    g = [w for w in re.findall(r"[a-z]+", (gloss or "").lower())
         if w not in ("the", "a", "an", "of", "and", "to", "in", "his", "her")]
    if not g:
        return False
    if any(w[:5] == x[:5] or w[:5] in x or x[:5] in w for w in words for x in g):
        return True
    from .wn import wordnet
    wn = wordnet()            # None, with one warning, where nltk is absent
    if wn is None:
        return False
    for w in words:
        for x in g:
            for a in wn.synsets(w)[:4]:
                for b in wn.synsets(x)[:4]:
                    if a.pos() == b.pos() and (a.wup_similarity(b) or 0) >= close:
                        return True
    return False


ABSTRACT = ("concept", "image", "title", "covenant", "assessment")
SOURCE = "STEPBible TAHOT/TAGNT, CC BY 4.0, www.STEPBible.org"


def apply(dry: bool = False) -> dict:
    """Write every resolvable lemma onto its node. **Run after every merge.**

    This is derived, not authored, and that is the whole reason it lives here
    as a command rather than in someone's scratch directory. `merge` rebuilds
    the entity files from the staged batches and discards whatever was in the
    output, so a lemma written once by hand survives exactly until the next
    merge and then vanishes without an error -- which is the pipeline working
    correctly and is why it would never be noticed.

    Anything that can be recomputed should be, every time.

    Only `attrs` is touched: no name, description, alias or citation is
    modified, so the diff is readable and a wrong approach reverts with one git
    command.

    **Only the Strong's code is stored.** That identifier is public domain
    (1890) and the claim "this node means H2451" is ours. STEPBible's glosses
    and transliterations are their editorial work and stay in their files,
    which their licence asks us not to redistribute.
    """
    from .schema import load_entities

    ents = load_entities()
    plan = {}
    unresolved: list = []
    for e in ents.values():
        if e.type not in ABSTRACT or not e.refs:
            continue
        langs = by_language(e.refs)
        if not langs or not all(langs.values()):
            continue
        top = candidates(e.refs, top=1)
        codes = [v for v in langs.values() if v]
        tbl = forms()

        # A phrase has no single original word, and pretending otherwise
        # produces a confident wrong answer. `eternal_life` resolved to G0166
        # -- aionios, "eternal" -- with zoe missing; `good_works` got ergon
        # and lost agathos. Each is half a concept wearing a whole one's
        # identifier.
        #
        # A phrase node's identity is compositional: a label, plus composed_of
        # into the word nodes that DO carry lemmas. So it gets no lemma here,
        # and the gap is honest rather than filled in.
        #
        # The test is whether the lemma's gloss accounts for the node's name,
        # not the word count: "lovingkindness" is one Hebrew word and
        # "burnt offering" very nearly is, while "eternal life" is two.
        content = [w for w in re.findall(r"[a-z]+", e.name.lower())
                   if w not in ("the", "a", "an", "of", "and", "to", "in")]
        gloss = next((tbl[c][1] for c in codes if c in tbl and tbl[c][1]), "")
        if len(content) > 1:
            covered = {w for w in content
                       if w[:5] in gloss.lower() or gloss.lower()[:5] in w}
            if len(covered) < len(content):
                unresolved.append((e.id, e.name, "+".join(codes), gloss))
                continue
        # A ONE-WORD NAME WAS NEVER CHECKED, and it is where the rarity
        # tie-break goes wrong. A node citing one verse finds EVERY word of
        # that verse at 100% coverage, and "coverage first, then rarity" then
        # picks the verse's rarest word, not the node's: `cubit` -> H8392
        # "ark", `daughters` -> H8083 "eight", `God` -> H6491 "open", `a
        # flood` -> H8229 "company". Measured 2026-09-28 against the meaning
        # crosswalk: 101 of 319 tagged nodes had a gloss sharing nothing with
        # their name, about 7 in 10 of them wrong on reading. The same test
        # as a phrase's, for every name: the gloss must account for a word of
        # it (a shared stem, or a close WordNet neighbour: "burial site" /
        # "grave", "clans" / "families"); otherwise the node goes to the
        # queue unresolved rather than carrying another word's number.
        # (the node's id and aliases count as its name too: `bosom` named
        # "heart"; and no gloss is no evidence either way)
        named = content + [w for t in [e.id.replace("_", " ")] +
                           list(getattr(e, "aka", None) or [])
                           for w in re.findall(r"[a-z]+", t.lower())
                           if w not in ("the", "a", "an", "of", "and", "to",
                                        "in", "assessment")]
        if gloss and named and not _accounts_for(named, gloss):
            unresolved.append((e.id, e.name, "+".join(codes), gloss))
            continue
        # The word in its own script and a short gloss, so a reader can check
        # the claim instead of taking a catalogue number on trust. Permitted by
        # STEPBible's licence for inclusion in software, with the credit that
        # `lemma_source` carries.
        words = [tbl[c][0] for c in codes if c in tbl and tbl[c][0]]
        gloss = next((tbl[c][1] for c in codes if c in tbl and tbl[c][1]), "")
        plan[e.id] = {
            "lemma": "+".join(codes),
            "lemma_word": " · ".join(words),
            "lemma_gloss": gloss,
            "lemma_coverage": round(top[0][1], 2) if top else None,
            "lemma_source": SOURCE,
        }

    written = removed = files = 0
    if not dry:
        for path in (glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl"))
                     + glob.glob(str(ROOT / "ontology" / "persons" / "*.jsonl"))):
            # Keep each untouched row's own text and the file's own line
            # ending: rewriting all 8,416 rows (CRLF -> LF, re-serialised)
            # once buried 322 real changes in an 8,416-line diff (2026-09-28).
            text = io.open(path, encoding="utf-8", newline="").read()
            eol = "\r\n" if "\r\n" in text else "\n"
            lines = [l for l in text.split(eol) if l.strip()]
            rows = [json.loads(l) for l in lines]
            before = [json.dumps(r, sort_keys=True) for r in rows]
            hit = False
            for r in rows:
                p = plan.get(r["id"])
                attrs = r.get("attrs") or {}
                if p:
                    # Compare the whole payload, not just the code. Comparing
                    # `lemma` alone meant that adding two new fields changed
                    # nothing anywhere: every node already had the right code,
                    # so every node was skipped and the run reported success
                    # having written nothing.
                    if all(attrs.get(k) == v for k, v in p.items()):
                        continue
                    r["attrs"] = dict(attrs, **p)
                    hit = True
                    written += 1
                elif attrs.get("lemma"):
                    # Resolves no longer. **This must be removed, not left.**
                    # A scoring bug once let coverage exceed 100% and eight
                    # nodes resolved on it; fixing the bug unresolved them, and
                    # a writer that only ever adds would have left all eight
                    # carrying a lemma no evidence supported -- with the
                    # correction itself being what made them stale.
                    for k in ("lemma", "lemma_word", "lemma_gloss",
                              "lemma_coverage", "lemma_source"):
                        attrs.pop(k, None)
                    if attrs:
                        r["attrs"] = attrs
                    else:
                        r.pop("attrs", None)
                    hit = True
                    removed += 1
            if hit:
                with io.open(path, "w", encoding="utf-8", newline="") as fh:
                    for line, was, r in zip(lines, before, rows):
                        now = json.dumps(r, sort_keys=True)
                        fh.write((line if now == was else json.dumps(
                            r, ensure_ascii=False, sort_keys=True)) + eol)
                files += 1
    return {"resolved": len(plan), "written": written, "removed": removed,
            "files": files, "phrases": unresolved,
            "both": sum(1 for p in plan.values() if "+" in p["lemma"])}


def why_unresolved(refs: list[str]) -> tuple[str, list]:
    """Why this node did not resolve, and the evidence for deciding it.

    132 nodes came back "ambiguous", which is honest and useless as a work
    queue: it is one label over three different situations, and the reader
    cannot tell a thirty-second confirmation from a real question.

        near      the top candidate beats the runner-up, but by less than the
                  margin. Usually right, wants a glance.
        contest   two words genuinely competing. Wants a decision.
        thin      the best candidate is in under two fifths of the citations.
                  Usually means the node's refs are about the idea rather than
                  the word, which is not a fault in either.

    Sorting a queue by how hard its items are is most of what makes it
    finishable, and it is the same move as collapsing the merge queue by
    question rather than by occurrence.
    """
    c = candidates(refs, top=3)
    if not c:
        return "thin", []
    if len(c) == 1:
        return "near", c
    if c[0][1] < 0.4:
        return "thin", c
    ratio = c[0][3] / c[1][3] if c[1][3] else 99
    return ("near" if ratio >= 1.15 else "contest"), c


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "build":
        build()
        return 0

    if argv and argv[0] == "review":
        from .schema import load_entities
        kind = next((a for a in argv[1:] if not a.startswith("-")), "near")
        limit = 20
        for a in argv:
            if a.startswith("--limit="):
                limit = int(a.split("=", 1)[1])
        ents = load_entities()
        rows = [e for e in ents.values()
                if e.type in ABSTRACT and e.refs
                and not (e.attrs or {}).get("lemma")]
        picked = []
        for e in rows:
            k, c = why_unresolved(e.refs)
            if k == kind:
                picked.append((e, c))
        picked.sort(key=lambda t: -len(t[0].refs))
        head = {"near": "probably right, wants a glance",
                "contest": "two words genuinely competing",
                "thin": "best candidate is in under two fifths of the refs"}
        print(f"{len(picked)} '{kind}' -- {head.get(kind, '')}"
              f"  (showing {min(limit, len(picked))})\n")
        for e, _c in picked[:limit]:
            print(f"  {e.id}  ({e.type}, {len(e.refs)} refs)")
            # Split the evidence by testament. A node citing both is not a
            # contest between a Hebrew word and a Greek one -- they cannot
            # compete, they are in different books -- and showing them in one
            # ranked list invites exactly that misreading.
            sides = [(lang, [r for r in e.refs if testament(r) == lang])
                     for lang in ("H", "G")]
            sides = [(l, rs) for l, rs in sides if rs]
            for lang, side in sides:
                label = "Hebrew" if lang == "H" else "Greek"
                got = resolved(side)
                mark = f"-> {got}" if got else "unresolved"
                if len(sides) > 1:
                    print(f"      {label} ({len(side)} refs)  {mark}")
                for root, cov, corpus, _s, g in candidates(side, top=3):
                    print(f"        {root:9}{cov:>5.0%} of refs"
                          f"  {corpus:>6,} in corpus   {g[:32]}")
            print(f"      {', '.join(e.refs[:6])}")
            print()
        if len(picked) > limit:
            print(f"  ... {len(picked) - limit} more; --limit=N to see them")
        return 0

    if argv and argv[0] == "apply":
        dry = "--dry" in argv
        r = apply(dry=dry)
        print(f"  {r['resolved']} nodes resolve to a lemma "
              f"({r['both']} to a Hebrew AND a Greek one)")
        if dry:
            print("  --dry: nothing written")
        else:
            print(f"  {r['written']} written, {r['removed']} removed "
                  f"across {r['files']} file(s)")
        return 0

    from .schema import load_entities
    ents = load_entities()

    if argv and argv[0] == "survey":
        types = ("concept", "image", "title", "covenant", "assessment")
        rows = [e for e in ents.values() if e.type in types and e.refs]
        done = amb = none = 0
        print(f"{'node':30}{'type':9}{'refs':>5}  lemma      cov  corpus  gloss")
        for e in sorted(rows, key=lambda x: x.id):
            c = candidates(e.refs)
            if not c:
                none += 1
                continue
            langs = by_language(e.refs)
            got = "+".join(v for v in langs.values() if v) or None
            if got and all(langs.values()):
                done += 1
            else:
                amb += 1
            root, cov, corpus, _, g = c[0]
            mark = " " if (got and all(langs.values())) else "?"
            print(f"{e.id[:28]:30}{e.type:9}{len(e.refs):>5}  {mark}"
                  f"{(got or root)[:16]:18}{g[:24]}")
        print(f"\n{done} resolved, {amb} ambiguous, {none} with no tagged "
              f"verse, of {len(rows)} nodes")
        return 0

    if not argv:
        print("usage: python -m bibleont.lemma build")
        print("       python -m bibleont.lemma survey")
        print("       python -m bibleont.lemma <node-id>")
        return 2

    e = ents.get(argv[0])
    if not e:
        print(f"no such node: {argv[0]}")
        return 1
    print(f"{e.id}  ({e.type})  {len(e.refs)} citation(s)")
    print(f"  {', '.join(e.refs[:12])}")
    print()
    print(f"  {'lemma':10}{'coverage':>9}{'corpus':>9}   gloss")
    for root, cov, corpus, _, g in candidates(e.refs, top=6):
        print(f"  {root:10}{cov:>9.0%}{corpus:>9,}   {g[:40]}")
    langs = by_language(e.refs)
    print()
    if len(langs) > 1:
        print("  cites both testaments -- one node, two words:")
    for lang, got in langs.items():
        n = sum(1 for r in e.refs if testament(r) == lang)
        name = "Hebrew" if lang == "H" else "Greek"
        print(f"  {name:8} ({n:>2} refs)  ->  {got or 'ambiguous; needs a person'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
