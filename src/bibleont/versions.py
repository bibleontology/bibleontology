"""Lifting a quoted phrase from one translation into another.

A `text` record's name is a quotation -- "the whole armour of God", "Thou
shalt not muzzle the ox", "Before Abraham was, I am". Two hundred and
seventy-four of them, every one carrying citations. Shown to a reader who has
chosen a different translation, a quotation in the wrong wording is not merely
awkward: the record claims a verse says something, and in their Bible it does
not say that.

So each phrase needs a label per version, and the honest way to get one is not
to retype it. It is to find the phrase inside its own cited verse and then map
that span onto the same verse in the other text.

## How

Three steps, and the third is the only interesting one.

1. **Locate.** The record's name is a span of one of its cited verses. Find
   which verse, and where, by sliding a window over the verse's words and
   scoring against the name.

2. **Align.** `difflib.SequenceMatcher` over the two verses' *word sequences*
   gives matching blocks. Translations of the same verse share most of their
   words, so the blocks are long and the mapping is mostly unambiguous.

3. **Map the boundaries.** Walk the blocks to carry the span's start and end
   from one word sequence to the other. Where a boundary falls inside a block
   the mapping is exact; where it falls in a gap -- one text says "shewbread"
   and the other "showbread", or one drops a word entirely -- it is snapped to
   the nearest block edge and the result is marked uncertain.

## What it refuses to do

**It does not guess.** Every result carries a confidence, and the ones below
the floor are returned as candidates for a person to read rather than written
into the graph. That distinction is the whole point: a phrase label is a
quotation, and a quotation nobody checked is worse than no quotation.

It also declines outright when the cited verse is empty in the target text --
which is how this corpus stores a verse a translation omits -- because there is
no wording to lift. That case is not a failure and is reported separately.

## Why prove it on KJV/ASV first

The two texts already here are a hard case in one direction and an easy one in
the other: the ASV is a revision of the KJV, so most verses share most words
and the alignment has plenty to hold on to. A modern translation will share
fewer, and the confidence floor is what will catch the difference. Measuring
the hit rate on the pair we have tells us what the floor should be before
three more texts arrive and there is more at stake in getting it wrong.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from functools import lru_cache

from .corpus import get_corpus, parse_ref
from .paths import VERSES_JSONL

# Below this, a lift is a candidate for review and not an answer.
FLOOR = 0.72

_WORD = re.compile(r"[A-Za-z']+")


def _words(text: str) -> list[str]:
    return _WORD.findall(text)


def _norm(words: list[str]) -> list[str]:
    return [w.lower().strip("'") for w in words]


@dataclass
class Lift:
    """One phrase carried from the base text into a target translation."""

    pid: str
    ref: str
    base: str
    lifted: str = ""
    score: float = 0.0
    note: str = ""
    exact: bool = False

    @property
    def confident(self) -> bool:
        return bool(self.lifted) and self.score >= FLOOR

    @property
    def changed(self) -> bool:
        return self.confident and self.lifted.lower() != self.base.lower()


@lru_cache(maxsize=4)
def load(translation: str) -> dict[str, str]:
    """Verse id -> text for a translation held beside the KJV."""
    import json

    if translation.lower() in ("kjv", ""):
        return {str(v.id): v.text for v in get_corpus().iter_verses()}
    path = VERSES_JSONL.with_suffix(f".{translation.lower()}.jsonl")
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not present. Put the raw text at data/raw/"
            f"{translation.upper()}.json and run python -m bibleont.build_corpus"
        )
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "b" not in row:
            continue  # the header line naming the translation
        out[f"{row['b']} {row['c']}:{row['v']}"] = row["t"]
    return out


# Words a quotation does not end on. Trimming these off the tail cleans up
# "HOLY UNTO JEHOVAH; and" and "Take off your sandals, for the" -- a window
# that ran one word past the phrase and swept up the connective that follows
# it. Only trimmed when the original phrase does not itself end there, so
# "the wages of sin is death; but the gift of God" keeps its own conjunction.
_TAIL = frozenset("""a an and the of to for but or nor so that which who whom
whose in on at by with from as is are was were be been am shall will unto
into upon""".split())


def _trim_tail(lifted: str, phrase: list[str]) -> str:
    if phrase and phrase[-1] in _TAIL:
        return lifted
    out = lifted
    for _ in range(3):
        stripped = out.rstrip(" ,;:—–-")
        words = _WORD.findall(stripped)
        if len(words) <= 1 or words[-1].lower() not in _TAIL:
            return stripped
        cut = stripped.rfind(words[-1])
        out = stripped[:cut]
    return out.rstrip(" ,;:—–-")


def _locate(phrase: list[str], verse: list[str]) -> tuple[int, int, float]:
    """Best window of `verse` matching `phrase`, as (start, end, score)."""
    if not phrase or not verse:
        return 0, 0, 0.0
    target = " ".join(phrase)
    n = len(phrase)
    best = (0, 0, 0.0)
    # A translation may use a word more or fewer, so try windows either side of
    # the phrase's own length rather than only its exact length.
    for width in {max(1, n - 2), max(1, n - 1), n, n + 1, n + 2}:
        for i in range(0, max(1, len(verse) - width + 1)):
            window = verse[i:i + width]
            score = difflib.SequenceMatcher(
                None, target, " ".join(window)).ratio()
            if score > best[2]:
                best = (i, i + width, score)
    return best


def _carry(start: int, end: int, base: list[str],
           other: list[str]) -> tuple[int, int, bool]:
    """Map a word span from one verse's words onto another's.

    Returns the mapped span and whether both boundaries landed inside a
    matching block, which is what `exact` means downstream.
    """
    blocks = difflib.SequenceMatcher(None, base, other).get_matching_blocks()

    def move(idx: int) -> tuple[int, bool]:
        for b in blocks:
            if b.a <= idx < b.a + b.size:
                return b.b + (idx - b.a), True
        # Not inside any block: snap to the start of the first block that
        # begins after it, or to the end of the last one before it.
        after = [b for b in blocks if b.a >= idx and b.size]
        if after:
            return after[0].b, False
        before = [b for b in blocks if b.a + b.size <= idx and b.size]
        if before:
            return before[-1].b + before[-1].size, False
        return min(idx, len(other)), False

    s, s_ok = move(start)
    e, e_ok = move(max(start, end - 1))
    return s, min(len(other), e + 1), (s_ok and e_ok)


def _refine(phrase: list[str], other: list[str], s: int, e: int,
            width: int) -> tuple[int, int, float]:
    """Nudge a mapped span to the best local match for the original phrase.

    Block mapping alone loses the front of a phrase whenever the two
    translations open it differently. "Thou shalt not muzzle the ox" has no
    block to anchor "Thou shalt" against the BSB's "Do", so the start snapped
    inward and the label came back "not muzzle an ox" -- a fragment presented
    as a quotation.

    So the block mapping becomes a seed rather than an answer. Around it,
    windows of several widths are scored against the original phrase directly,
    and the best one wins. The comparison is across translations and will never
    be perfect; it does not need to be, because it is only choosing between
    candidate spans of the same verse.
    """
    target = " ".join(phrase)
    wanted = set(phrase)

    def score(i: int, j: int) -> float:
        span = other[i:j]
        ratio = difflib.SequenceMatcher(None, target, " ".join(span)).ratio()
        # Character similarity alone prefers a short span that matches
        # cleanly over a longer one that carries the whole quotation: for
        # "Before Abraham was, I am" it chose the WEB's "before Abraham came"
        # over "before Abraham came into existence, I AM". Recall of the
        # phrase's own words is what tells those apart -- two of five against
        # four of five -- so it is weighed alongside.
        recall = len(wanted & set(span)) / len(wanted) if wanted else 0.0
        return ratio * (0.55 + 0.45 * recall)

    best = (s, e, score(s, e))
    for w in range(max(1, width - 2), width + 5):
        for i in range(max(0, s - 4), min(len(other), s + 5)):
            j = min(len(other), i + w)
            if j <= i:
                continue
            got = score(i, j)
            if got > best[2]:
                best = (i, j, got)
    return best


def lift(pid: str, name: str, refs, translation: str) -> Lift | None:
    """Carry one record's phrase into `translation`, best citation first."""
    other = load(translation)
    kjv = load("kjv")
    corpus = get_corpus()

    phrase = _norm(_words(name))
    if not phrase:
        return None

    best: Lift | None = None
    for ref in refs:
        try:
            verses = [str(v) for v in corpus.expand(parse_ref(ref))]
        except Exception:
            verses = [ref]
        for vid in verses:
            base_text = kjv.get(vid, "")
            other_text = other.get(vid, "")
            if not base_text:
                continue
            if not other_text.strip():
                cand = Lift(pid, vid, name, "", 0.0,
                            f"{translation.upper()} has no text at {vid}")
                if best is None:
                    best = cand
                continue

            bw = _words(base_text)
            ow = list(_WORD.finditer(other_text))
            s, e, found = _locate(phrase, _norm(bw))
            if found < 0.5:
                continue
            ow_norm = _norm([m.group() for m in ow])
            ms, me, exact = _carry(s, e, _norm(bw), ow_norm)
            ms, me, local = _refine(phrase, ow_norm, ms, me, len(phrase))
            if ms >= me or ms >= len(ow):
                continue
            # Slice the ORIGINAL string between the first and last matched
            # word rather than rejoining the words. A phrase label is shown to
            # a reader, and "Before Abraham was born, I am" is the quotation
            # while "Before Abraham was born I am" is a word list.
            lifted = other_text[ow[ms].start():ow[min(me, len(ow)) - 1].end()]
            # Slicing between word boundaries picks up whatever punctuation
            # opened the span. Young's marks all direct speech with a single
            # quote, so nearly every saying lifted out of it began with a
            # stray apostrophe -- "'Thou dost not muzzle an ox". Trim the
            # openers and unpaired closers; keep everything inside.
            lifted = lifted.strip().strip("“”‘’\"'").strip()
            lifted = lifted.lstrip("-—– ").strip()
            lifted = _trim_tail(lifted, phrase)
            if not lifted:
                continue

            # Confidence combines three things, and the third was added after
            # the first run let "by faith the elders obtained a good report"
            # through as "the elders had" at 0.82. Finding the phrase well in
            # its own verse is necessary and not sufficient; a lift that comes
            # back a third the length has lost most of the quotation, and no
            # amount of match quality on the remainder should hide that.
            ratio = len(_words(lifted)) / max(1, len(phrase))
            fit = min(ratio, 1 / ratio) if ratio else 0.0
            score = found * (1.0 if exact else 0.9) * (0.5 + 0.5 * fit)
            why = []
            if not exact:
                why.append("span snapped to a block edge")
            if fit < 0.75:
                why.append(f"length {len(_words(lifted))} against {len(phrase)}")
            cand = Lift(pid, vid, name, lifted, round(score, 3),
                        "; ".join(why), exact)
            if best is None or cand.score > best.score:
                best = cand
    return best


# Only these kinds of text record hold a quotation as their name.
#
# `description` and `abridged` were added after the first full run, and both
# describe names the aligner cannot lift for the same reason: they are not a
# span of any one verse. A `description` is this project's own words -- "the
# Sermon on the Mount", "the words for sin". An `abridged` is a real quotation
# with words taken out of the middle -- "except the Father draw him" is John
# 6:44 without "which hath sent me". Neither is liftable and they are kept
# apart because calling the second a description would be wrong about it.
QUOTED = frozenset({"saying"})


@lru_cache(maxsize=1)
def approvals() -> dict[tuple[str, str], str]:
    """Label decisions a person has made, overriding the aligner either way.

    The floor is deliberately strict, and being strict costs real labels. The
    World English Bible renders Exodus 3:5 "Take off your sandals", which is
    both correct and exactly what a WEB reader should see -- and it scores
    below the floor because it shares almost no words with "Put off thy shoes
    from off thy feet". Suppressing it means showing that reader a quotation
    from a Bible they are not reading, which is the failure this whole feature
    exists to prevent.

    Lowering the floor to catch it would let in "count it all joy" as
    "encounter trials". So the floor stays where it is and a human decision
    can override it, one lift at a time, recorded where it can be audited.
    It corrects as well as rescues. A lift can also be confidently wrong:
    Young's renders Exodus 3:5 "cast thy shoes from off thy feet" and the
    aligner returned five of those six words, high enough to pass while
    dropping the verb. An accept-only file could not have fixed that.

    **Presence in this file means somebody read the verse.** It is not a
    tuning parameter and should never be filled in in bulk.
    """
    import json

    from .paths import ONTOLOGY

    path = ONTOLOGY / "versions" / "approved.jsonl"
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        row = json.loads(line)
        out[(row["id"], row["translation"])] = row["label"]
    return out


def survey(translation: str = "asv", kinds=QUOTED):
    """Lift the quoted records and report how well it went.

    Scoped to `saying` by default, and the first run is what showed why. Sorted
    by `attrs.kind`, the lift rate splits the text records almost perfectly in
    two:

        saying   91%     dream 14%     vision 33%     sign 55%   parable 64%

    That is not a tuning failure. A `saying` record is named with the corpus's
    own words -- "Before Abraham was, I am" -- so there is something in the
    verse to find. A `dream` or `parable` record is named with *ours*: "the
    baker's dream", "the parable of the lost sheep", "Pharaoh's dream of the
    kine and the ears". No translation contains those phrases because no
    translation wrote them, and the aligner was right to fail.

    **So they must not be translated, and that is a semantic point rather than
    a practical one.** Lifting "the parable of the lost sheep" into the ASV
    would produce a string that looks like a quotation, sits where a quotation
    goes, and is nobody's wording. Descriptive titles are the project speaking
    in its own voice, and they stay in one form across every version for the
    same reason the `id` does.

    Pass `kinds=None` to run over everything, which is how the split above was
    measured and is worth repeating when a new translation lands.
    """
    from .graph import Store

    store = Store.load()
    rows = []
    for p in store.people.values():
        if p.type != "text" or not p.refs:
            continue
        if kinds is not None:
            kind = (getattr(p, "attrs", None) or {}).get("kind")
            if kind not in kinds:
                continue
        got = lift(p.id, p.name, p.refs, translation)
        if got:
            rows.append(got)
    return rows


TRANSLATIONS = ("asv", "ylt", "web", "bsb")


def overlay_path():
    from .paths import ONTOLOGY

    return ONTOLOGY / "versions" / "labels.jsonl"


def write_overlay(translations=TRANSLATIONS) -> dict:
    """Generate the per-version label overlay and the absence list.

    **Deliberately not a field on the entity records.** Everything in
    `ontology/entities` is authored in a batch and merged; these labels are
    computed from the corpora and regenerated whenever a translation or a
    record's citation changes. Putting machine output into the batch model
    would mean hand-carrying it through every future batch, and the first time
    someone edited a generated label by hand the two would diverge with nothing
    to catch it.

    So it lives beside the graph rather than inside it, in one small file that
    can be deleted and rebuilt. Three things go in each row:

        labels   the phrase as that translation words it
        review   translations whose lift fell below the floor, to be read
        absent   translations with no text at the cited verse

    `absent` is the interesting one and it is computed, never asserted: a
    record whose only citation is John 5:4 has no wording in the ASV or the
    BSB because those translations do not carry the verse.
    """
    import json

    from .graph import Store

    store = Store.load()
    rows = []
    for p in sorted(store.people.values(), key=lambda x: x.id):
        if p.type != "text" or not p.refs:
            continue
        kind = (getattr(p, "attrs", None) or {}).get("kind")
        if kind not in QUOTED:
            continue
        labels, review, absent = {}, [], []
        ok = approvals()
        for t in translations:
            got = lift(p.id, p.name, p.refs, t)
            if got is None:
                continue
            # A human decision wins outright, whatever the score. The file
            # started as a way to rescue correct lifts the floor rejected, and
            # the first pass immediately turned up the other case: Young's
            # renders Exodus 3:5 "cast thy shoes from off thy feet" and the
            # aligner returned five of those six words, scoring high enough to
            # pass while quietly dropping the verb. A reviewer needs to be able
            # to fix a wrong label as much as to accept a good one.
            if (p.id, t) in ok:
                labels[t] = ok[(p.id, t)]
            elif not got.lifted:
                absent.append(t)
            elif got.confident:
                if got.lifted != p.name:
                    labels[t] = got.lifted
            else:
                review.append(t)
        if labels or review or absent:
            row = {"id": p.id, "kjv": p.name}
            if labels:
                row["labels"] = labels
            if review:
                row["review"] = review
            if absent:
                row["absent"] = absent
            rows.append(row)

    path = overlay_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return {
        "records": len(rows),
        "labels": sum(len(r.get("labels", ())) for r in rows),
        "review": sum(len(r.get("review", ())) for r in rows),
        "absent": sum(len(r.get("absent", ())) for r in rows),
        "path": str(path),
    }


def load_overlay() -> dict[str, dict]:
    """Read the overlay, or an empty map if it has not been generated."""
    import json

    path = overlay_path()
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["id"]] = row
    return out


def relation_absence(translations=TRANSLATIONS) -> list[dict]:
    """Which relations lose their evidence in which translations.

    A relation is listed only when **every** verse it cites is empty in a
    translation. One citation surviving is enough: the claim still rests on
    something a reader of that Bible can check.
    """
    from .graph import Store

    corpus = get_corpus()
    texts = {t: load(t) for t in translations}
    store = Store.load()

    out = []
    for rel in store.relations:
        vids = set()
        for ref in rel.refs:
            try:
                vids.update(str(v) for v in corpus.expand(parse_ref(ref)))
            except Exception:
                vids.add(ref)
        if not vids:
            continue
        gone = [t for t in translations
                if all(not texts[t].get(v, "").strip() for v in vids)]
        if gone:
            out.append({"src": rel.src, "type": rel.type, "dst": rel.dst,
                        "refs": sorted(vids), "absent": gone})
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    import collections

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("translation", nargs="?", default="asv")
    ap.add_argument("--show", choices=["changed", "review", "missing", "all"],
                    default="changed")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--write", action="store_true",
                    help="generate ontology/versions/labels.jsonl and report "
                         "which relations lose their evidence per translation")
    ap.add_argument("--all-kinds", action="store_true",
                    help="include dreams, visions and parables, whose names "
                         "are this project's descriptions rather than "
                         "quotations and are not meant to be translated")
    args = ap.parse_args(argv)

    if args.write:
        stats = write_overlay()
        print(f"{stats['records']} records -> {stats['path']}")
        print(f"  {stats['labels']} version-specific labels")
        print(f"  {stats['review']} lifts below the floor, for a person")
        print(f"  {stats['absent']} where the translation lacks the verse")
        gone = relation_absence()
        print(f"\n{len(gone)} relations lose every cited verse in some "
              f"translation:")
        for g in gone:
            print(f"  {g['src']} -{g['type']}-> {g['dst']}")
            print(f"      {', '.join(g['refs'])}  absent in "
                  f"{', '.join(t.upper() for t in g['absent'])}")
        return 0

    rows = survey(args.translation, None if args.all_kinds else QUOTED)
    tally = collections.Counter()
    for r in rows:
        if r.note.endswith("no text at " + r.ref):
            tally["verse absent"] += 1
        elif not r.confident:
            tally["needs review"] += 1
        elif r.changed:
            tally["lifted, differs"] += 1
        else:
            tally["lifted, identical"] += 1

    want = {
        "changed": lambda r: r.changed,
        "review": lambda r: r.lifted and not r.confident,
        "missing": lambda r: not r.lifted,
        "all": lambda r: True,
    }[args.show]

    shown = 0
    for r in rows:
        if not want(r) or shown >= args.top:
            continue
        shown += 1
        print(f"{r.score:5.2f}  {r.ref:12}{r.base[:44]:46}-> {r.lifted[:44]}")
        if r.note:
            print(f"{'':7}{'':12}{r.note}")

    print(f"\n{len(rows)} phrase records against {args.translation.upper()}")
    for k in ("lifted, identical", "lifted, differs", "needs review",
              "verse absent"):
        print(f"  {k:20}{tally[k]:5}")
    print(f"\nConfidence floor {FLOOR}. Anything under it is a candidate for a "
          f"person to read,\nnot an answer -- a phrase label is a quotation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
