"""Where the KJV and the ASV say materially different things.

The graph is built on the KJV, and it should stay that way -- one text, quoted
exactly, so a reader can check any claim against the book in their hand. But a
citation is only as good as the wording behind it, and on the verses people
argue about the wording is sometimes the whole argument.

Four examples found by hand while building the Father/Son/Spirit edges:

    1Tim 3:16   KJV "God was manifest"
                ASV "He who was manifested in the flesh"
    Matt 19:17  KJV "Why callest thou me good? ... none good but one, that is,
                     God"
                ASV "Why askest thou me concerning that which is good?"
    Phil 2:6    KJV "thought it not robbery to be equal with God"
                ASV "counted not the being on an equality with God a thing to
                     be grasped"
    1John 5:7   KJV names the Father, the Word and the Holy Ghost
                ASV does not have the clause at all

**Finding those four by hand is the problem this module exists to fix.** They
were the ones that came to mind on one afternoon's work; nothing says they are
the only ones, and a reader who checks a fifth and finds the graph silent about
it has good reason to doubt the four. A hand-kept list of caveats is the same
failure as a hand-kept status page.

So the check is computed over any verse the graph cites, and the app can say
"this reads differently in the ASV" wherever it is true rather than wherever
somebody remembered.

## What counts as material

Not spelling, not archaism, not word order. The two texts differ constantly in
ways that carry nothing -- brake for broke, thy for your, saith for says -- and
reporting those would bury the cases that matter under thousands that do not.

The test is **content words present in one and absent from the other**, after
folding the archaic forms that are the same word. "God" appearing in one text
and not in the other is material. "Whiles" against "While" is not.

The result is deliberately conservative in one direction: it will miss
differences of sense that use the same vocabulary. It is meant to flag verses
worth a second look, not to be the last word on them.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache

from .paths import VERSES_JSONL

# Pairs the two texts use for the same word. Folding these is what keeps the
# report down to differences that mean something.
ARCHAIC = {
    "thou": "you", "thee": "you", "ye": "you", "thy": "your",
    "thine": "your", "hath": "has", "hast": "has", "doth": "does",
    "dost": "does", "saith": "says", "shalt": "shall", "wilt": "will",
    "art": "are", "wast": "was", "were": "was", "brake": "broke",
    "spake": "spoke", "unto": "to", "whiles": "while", "cometh": "comes",
    "goeth": "goes", "knoweth": "knows", "believeth": "believes",
    "sayeth": "says", "hearken": "hear", "behold": "see", "yea": "yes",
    "nay": "no", "hither": "here", "thither": "there", "whence": "where",
    "wherefore": "why", "howbeit": "however", "peradventure": "perhaps",
    # The single largest systematic difference between the two texts, and the
    # least informative: where the KJV puts "the LORD" the ASV transliterates
    # "Jehovah". It accounts for 386 of the first run's differences on its own
    # and tells a reader nothing they did not already know about the
    # translations. `crosswalk` is the module that studies it properly.
    "jehovah": "lord",
}

# Style, not substance. Both texts render the same Greek and Hebrew with
# different connectives and narrative verbs -- "and it came to pass" against
# "and it came about", "straightway" against "immediately" -- and these words
# drove most of what survived the first fold while carrying none of the
# meaning anybody argues over.
STYLE = frozenset("""
also now even therefore again upon into forth straightway did come came
went go goeth gone said say saith spake behold thus lo yet still very
made make made set put over under before after among between through
""".split())

# Words too common to be evidence of anything.
STOP = frozenset("""
a an and are as at be been but by for from had has have he her him his i if
in is it its me my no nor not of on or our out shall she should so than that
the their them then there these they this those to unto up us was we were
what when which who whom why will with would you your yours their s t
""".split())

_WORD = re.compile(r"[A-Za-z']+")


@dataclass(frozen=True)
class Divergence:
    ref: str
    kjv: str
    asv: str
    only_kjv: tuple[str, ...]
    only_asv: tuple[str, ...]

    @property
    def material(self) -> bool:
        return bool(self.only_kjv or self.only_asv)

    def as_dict(self) -> dict:
        return {
            "ref": self.ref,
            "kjv": self.kjv,
            "asv": self.asv,
            "only_kjv": list(self.only_kjv),
            "only_asv": list(self.only_asv),
        }


@lru_cache(maxsize=1)
def _vocabulary() -> frozenset[str]:
    """Every word the KJV uses, for testing whether a stem is a real word.

    Stripping -eth and -est blindly turns "manifest" into "manif" and reports
    it as a difference from the ASV's "manifested", which is the opposite of
    what the fold is for. The corpus is the cheapest available dictionary:
    strip the suffix only when what is left is itself a word the text uses.
    """
    from .corpus import get_corpus

    out: set[str] = set()
    for v in get_corpus().iter_verses():
        out.update(w.strip("'") for w in _WORD.findall(v.text.lower()))
    return frozenset(out)


def _stem(w: str) -> str:
    """Fold an inflection only when the result is a word in its own right."""
    vocab = _vocabulary()
    for suffix in ("eth", "est"):
        if w.endswith(suffix) and len(w) > 5:
            base = w[: -len(suffix)]
            if base in vocab:
                return base
            if base + "e" in vocab:
                return base + "e"
    # Singular and plural of the same noun are not a divergence worth
    # reporting -- "heaven" against "heavens" is the whole difference in
    # Genesis 1:1, and it is not one anybody argues about.
    if w.endswith("s") and len(w) > 3 and w[:-1] in vocab:
        return w[:-1]
    return w


# A word in this many verses or more is common enough that its coming and
# going is a translator's habit rather than a change of claim.
COMMON = 400


@lru_cache(maxsize=1)
def _frequency() -> dict[str, int]:
    from .corpus import get_corpus

    counts: dict[str, int] = {}
    for v in get_corpus().iter_verses():
        for w in set(_WORD.findall(v.text.lower())):
            counts[w] = counts.get(w, 0) + 1
    return counts


def _similar(a: str, b: str, floor: float = 0.72) -> bool:
    """Close enough to be one word spelled two ways."""
    from difflib import SequenceMatcher

    if a == b:
        return True
    if abs(len(a) - len(b)) > 3:
        return False
    return SequenceMatcher(None, a, b).ratio() >= floor


def _weighty(word: str) -> bool:
    return _frequency().get(word, 0) < COMMON


def _fold(text: str) -> set[str]:
    out = set()
    for w in _WORD.findall(text.lower()):
        w = ARCHAIC.get(w.strip("'"), w.strip("'"))
        w = _stem(w)
        if w and w not in STOP:
            out.add(w)
    return out


@lru_cache(maxsize=1)
def _asv() -> dict[str, str]:
    path = VERSES_JSONL.with_suffix(".asv.jsonl")
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "t" in row:
                out[f"{row['b']} {row['c']}:{row['v']}"] = row["t"]
    return out


def has_asv() -> bool:
    return bool(_asv())


def check(ref: str, kjv_text: str) -> Divergence | None:
    """Compare one verse. None when the ASV has nothing to add.

    A verse the ASV does not carry at all is the strongest possible result and
    is reported with an empty ASV text: 1 John 5:7 is the case that matters,
    and reporting it as "no difference" would be the worst available answer.
    """
    asv = _asv()
    if not asv:
        return None
    other = asv.get(ref)
    if other is None:
        return Divergence(ref, kjv_text, "", ("(the ASV does not carry this "
                                              "verse)",), ())
    a, b = _fold(kjv_text), _fold(other)
    only_kjv = tuple(sorted(w for w in a - b if w not in STYLE))
    only_asv = tuple(sorted(w for w in b - a if w not in STYLE))
    if not only_kjv and not only_asv:
        return None
    return Divergence(ref, kjv_text, other, only_kjv, only_asv)


def affects(div: "Divergence", claim: str) -> tuple[str, ...]:
    """Which of a divergence's words the claim itself leans on.

    **This is the test that matters, and the earlier ones were wrong.**
    Comparing the two texts and reporting every difference flags 70% of the
    verses the graph cites; filtering to rarer words still flags 58%, because
    the ASV differs from the KJV in vocabulary almost everywhere -- coast for
    country, hill for mountain, prince for ruler. None of that is news.

    What a reader needs to know is narrower and more useful: **the wording
    this particular citation rests on is not the same in both texts.** So the
    divergence is measured against the claim -- the note written for the edge,
    which quotes the words it depends on. "Robbery" against "grasped" matters
    on Philippians 2:6 because the note quotes "thought it not robbery". The
    same verse's "existing" for "being" does not, because nothing was built
    on it.

    Returns the overlapping words, empty when the claim does not touch the
    difference.
    """
    words = {_stem(ARCHAIC.get(w, w)) for w in _WORD.findall(claim.lower())}
    hit = {w for w in div.only_kjv + div.only_asv if w in words}
    # Two spellings of one name are not a divergence of meaning. The ASV
    # transliterates from the Hebrew where the KJV came through Latin, so
    # Nethaneel is Nethanel and Socho is Soco, and flagging those would bury
    # the cases where the sense changed. `crosswalk` is the module that
    # derives these pairs properly; this is the cheap test at the point of use.
    spelling = set()
    for a in div.only_kjv:
        for b in div.only_asv:
            if _similar(a, b):
                spelling.add(a)
                spelling.add(b)
    # And compounding, which is one word against two: the KJV writes
    # "armourbearer" and "threshingfloor" where the ASV hyphenates, so the
    # halves show up as differences on both sides at once.
    for side, other in ((div.only_kjv, div.only_asv),
                        (div.only_asv, div.only_kjv)):
        for whole in side:
            for i in range(3, len(whole) - 2):
                head, tail = whole[:i], whole[i:]
                if head in other and tail in other:
                    spelling.update({whole, head, tail})
                    break
    return tuple(sorted(hit - spelling))


def main(argv: list[str] | None = None) -> int:
    import argparse

    from .corpus import get_corpus

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("refs", nargs="*", help="verses to check")
    ap.add_argument("--cited", action="store_true",
                    help="every verse the graph cites")
    args = ap.parse_args(argv)

    corpus = get_corpus()
    if not has_asv():
        print("ASV text not present; nothing to compare against.")
        return 1

    refs = list(args.refs)
    if args.cited:
        from .graph import Store
        from .refs import parse_ref
        seen = set()
        for rel in Store.load().relations:
            for r in rel.refs:
                try:
                    for v in corpus.expand(parse_ref(r)):
                        seen.add(str(v))
                except Exception:
                    continue
        refs = sorted(seen)

    found = 0
    for ref in refs:
        verses = corpus.verses_for(ref)
        for v in verses:
            d = check(str(v.id), v.text)
            if not d:
                continue
            found += 1
            print(f"{v.id}")
            print(f"   KJV  {v.text[:150]}")
            print(f"   ASV  {d.asv[:150] or '(absent)'}")
            if d.only_kjv:
                print(f"   only in KJV: {', '.join(d.only_kjv[:10])}")
            if d.only_asv:
                print(f"   only in ASV: {', '.join(d.only_asv[:10])}")
            print()
    print(f"{found} of {len(refs)} verses differ materially")
    return 0


# Words that carry no sense of their own and would otherwise dominate any
# count of what one translation put where the other put something else.
_ALIAS_STOP = frozenset("""the and of to in that he shall for unto is his with
be not it they thou him them which but me my we you your ye are was were all
when there their so as if then this these those from by up out into upon at on
or no nor do did done will would may might can also have has had hath having
who whom whose what where how why any every each other than more most much many
one two three both such same own very now here after before while until because
thy thee thine her shalt doth man men thing things even yet still likewise
therefore wherefore behold verily saith said say jehovah lord god""".split())


def alias_candidates(word: str, floor: int = 3) -> list[tuple[str, int]]:
    """What the ASV puts where the KJV puts `word`, ranked by how often.

    **A search aid, and deliberately not a claim about meaning.** The graph is
    built on one translation and a reader does not arrive knowing which. Someone
    who learned Psalm 136 from a modern Bible will search *lovingkindness* and
    the King James never uses the word once; someone taught 1 Corinthians 13
    will search *charity* or *love* depending entirely on which pew they sat in.

    Verse alignment does the work. For every verse where the King James uses
    the word and the American Standard does not, whatever the ASV has instead
    is a word a reader might come looking with. Run over the concept layer it
    finds the pairs anyone would name -- charity/love, mercy/lovingkindness,
    grace/favor, patience/stedfastness -- without anyone naming them.

    It is a rough instrument and should be read by a person before anything is
    recorded. The result is a bag of words from a whole verse, so genuine
    renderings arrive mixed with whatever else that verse happens to say, and
    at least one confident-looking pair is an artefact: `strength` returns
    *weaknesses*, because 2 Corinthians 12:9 sets the two against each other in
    one sentence. **The frequency column is the filter** -- 113 for
    lovingkindness against 3 for skies -- and the eye is the second one.

    This is the first step toward the graph not being a King James model. It
    does not get there: the aliases point at one translation's wording, and
    what is actually wanted underneath is the word behind both. That is a
    different and much larger job, deliberately not started here.
    """
    import collections

    from .corpus import get_corpus

    corpus = get_corpus()
    asv = _asv()
    low = word.lower()

    def tokens(text: str) -> set[str]:
        return {w for w in re.findall(r"[a-z]{3,}", text.lower())
                if w not in _ALIAS_STOP}

    found: collections.Counter = collections.Counter()
    for verse in corpus.iter_verses():
        other = asv.get(str(verse.id))
        if not other:
            continue
        here = tokens(verse.text)
        if low not in here:
            continue
        there = tokens(other)
        if low in there:
            continue
        for w in there - here:
            found[w] += 1
    return [(w, n) for w, n in found.most_common() if n >= floor]


def aliases_main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="What the ASV says where the KJV says a given word.")
    ap.add_argument("words", nargs="*",
                    help="words to check; default is every concept node")
    ap.add_argument("--floor", type=int, default=3)
    args = ap.parse_args(argv)

    words = args.words
    if not words:
        from .graph import Store
        store = Store.load()
        words = sorted({p.name.lower() for p in store.people.values()
                        if p.type == "concept" and " " not in p.name})

    for word in words:
        rows = alias_candidates(word, args.floor)
        if not rows:
            continue
        print(f"{word:16} {rows[:8]}")
    return 0


def spelling_pairs(floor: int = 3) -> dict[str, str]:
    """Words the King James spells one way and the American Standard another.

    **The largest single searchability defect this project has had, and it is
    entirely mechanical.** The King James uses British and archaic forms; the
    ASV uses American and modern ones. Every record named from the King James
    is unreachable by the spelling a reader would actually type:

    ```
    KJV          ASV          verses     what it costs
    armour       armor        24 / 28    "the armour of God" is unfindable
    colours      colors       10 / 9     the coat of many colours
    vail         veil          7 / 44    a reader typing veil gets nothing
    nazarite     nazirite      9 / 9     Samson's vow
    kirjath      kiriath      31 / 34    four place records
    bezaleel     bezalel       9 / 10    a person record
    shewbread    showbread    18 / 18
    ```

    A hundred and six such pairs, affecting fifty records.

    Found by alignment rather than by a dictionary: a word that appears in one
    translation and not the other, whose nearest spelling in the other appears
    in most of the same verses, is the same word spelled differently. Sharing
    the verses is what separates a spelling from a synonym -- `mercy` and
    `lovingkindness` share verses too, but they are not close enough in
    spelling to be matched here, and `honour`/`honor` are.

    The verse floor keeps rare coincidences out; below three occurrences the
    evidence is not there.

    ## The ligature

    The ASV spells Caesarea `Cæsarea`, Arimathea `Arimathæa` and Cenchrea
    `Cenchreæ` -- 135 occurrences of U+00E6 in all. A plain `[a-z]+` scan cuts
    each of those in half and leaves `sarea`, `arimath` and `cenchre` sitting
    in the ASV vocabulary as words the KJV lacks. Every one of them is then a
    near match for the real name, so the miner proposes `Cesarea -> Sarea`
    with perfect confidence.

    Folding it is one line, but the failure is worth naming, because nothing
    about it looks like a failure: the pairs it invents are the right shape,
    the right length and the right verses. **A tokenizer that silently drops a
    character produces evidence, not errors.** The `æ` was found by counting
    non-ASCII characters in both texts rather than by reading the output --
    which also turned up the Hebrew letters of the Psalm 119 acrostic, one
    each, in both translations, and those are content and must stay.
    """
    import collections
    import difflib
    import re

    from .corpus import get_corpus

    def words(text: str) -> set[str]:
        text = text.lower().replace("æ", "ae").replace("œ", "oe")
        return set(re.findall(r"[a-z']+", text))

    def index(corpus):
        where: dict[str, set[str]] = collections.defaultdict(set)
        for verse in corpus.iter_verses():
            vid = str(verse.id)
            for w in words(verse.text):
                where[w].add(vid)
        return where

    kjv = index(get_corpus())
    asv_text = _asv()
    asv: dict[str, set[str]] = collections.defaultdict(set)
    for vid, text in asv_text.items():
        for w in words(text):
            asv[w].add(vid)

    only_asv = [w for w in asv if w not in kjv]
    pairs: dict[str, str] = {}
    for word, verses in kjv.items():
        if word in asv or len(verses) < floor:
            continue
        near = difflib.get_close_matches(word, only_asv, n=1, cutoff=0.8)
        if not near:
            continue
        other = near[0]
        shared = len(verses & asv[other])
        if shared >= max(2, 0.5 * min(len(verses), len(asv[other]))):
            pairs[word] = other
    return pairs


def spellings_main(argv: list[str] | None = None) -> int:
    import argparse
    import re

    from .graph import Store

    ap = argparse.ArgumentParser(
        description="Words the KJV and ASV spell differently.")
    ap.add_argument("--records", action="store_true",
                    help="show the graph records each pair would reach")
    args = ap.parse_args(argv)

    pairs = spelling_pairs()
    if not args.records:
        print(f"{'KJV':20}{'ASV':20}")
        for kjv_word, asv_word in sorted(pairs.items()):
            print(f"{kjv_word:20}{asv_word:20}")
        print(f"\n{len(pairs)} spelling pairs")
        return 0

    store = Store.load()
    hits = 0
    for pid, person in sorted(store.people.items()):
        names = " ".join(person.names()).lower()
        for name in person.names():
            for w in re.findall(r"[a-z']+", name.lower()):
                if w in pairs and pairs[w] not in names:
                    print(f"  {pid[:34]:36}{person.type:10}"
                          f"{name[:26]:28}{w} -> {pairs[w]}")
                    hits += 1
                    break
            else:
                continue
            break
    print(f"\n{hits} records reachable only by a King James spelling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
