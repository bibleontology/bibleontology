"""One verse in, a piece of graph out.

The finder looks for phrases that recur across books, which is a cross-
reference detector and not the engine. This is the engine: read a verse, name
what is in it, connect what is already known, and hand up the judgement calls
rather than making them.

## What it refuses to decide

Two things, deliberately, and both for the same reason -- they are cheap to
defer and expensive to get wrong.

**Whether two things are the same.** If `wisdom` in "the beginning of wisdom"
reads as a quality and `wisdom` in "wisdom's instruction" reads as an actor,
this splits them and raises a question. Splitting wrongly is repaired by a
later merge. Merging wrongly destroys the distinction and no later pass can
recover which edges belonged to which sense.

**Whether the vocabulary needs a new word.** Nothing here may invent a relation
type. It picks the closest that fits, and records the wording it wanted.

## Questions are keyed by question, not by verse

This is the part that decides whether a run over the Psalms is finishable. At
roughly three judgement calls per ten verses, 2,461 verses produce something
like 700 of them, and nobody is going to answer 700 of anything after work.

But they are not 700 different questions. "Is Wisdom-the-actor the same as
Wisdom-the-quality" is *one* question that forty verses happen to raise. So
every question carries a `key` naming the question rather than the occurrence,
and the queue collapses on it. One answer, forty verses resolved.

The worker is told to key them and cannot be trusted to do it consistently, so
`collapse()` groups on the key it gave and reports the spread. A key that
appears once is either a genuinely singular problem or a badly named one, and
the two look different when you see them next to each other.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .paths import ROOT
from .prefix import build as build_prefix, mode_of

PROPOSALS = ROOT / "ontology" / "proposals"
QUESTIONS = PROPOSALS / ".questions"
RUNS = PROPOSALS / ".runs"

TRANSLATIONS = [("KJV", "verses.jsonl"), ("ASV", "verses.asv.jsonl"),
                ("WEB", "verses.web.jsonl"), ("BSB", "verses.bsb.jsonl"),
                ("YLT", "verses.ylt.jsonl")]

_CACHE: dict[str, dict] = {}


def _load(fname: str) -> dict:
    """Verses of one translation, keyed 'Ps 23:1'."""
    if fname in _CACHE:
        return _CACHE[fname]
    out = {}
    path = ROOT / "data" / "bible" / fname
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if "b" in r:
                    out[f"{r['b']} {r['c']}:{r['v']}"] = r["t"]
    _CACHE[fname] = out
    return out


def chapter(book: str, ch: int) -> list[tuple[str, str]]:
    """Every verse of one chapter, KJV, in order -- the Berean where the KJV
    is absent (the public repository), since the verse ids are the same: an
    empty KJV read silently gave every chapter no verses there (the code
    review, 2026-10-22)."""
    kjv = _load("verses.jsonl") or _load("verses.bsb.jsonl")
    out = []
    v = 1
    while f"{book} {ch}:{v}" in kjv:
        ref = f"{book} {ch}:{v}"
        out.append((ref, kjv[ref]))
        v += 1
    return out


def material(ref: str, context: int = 1) -> str:
    """The variable half of the prompt: the verse, its neighbours, and the
    places the translations disagree.

    Divergence is carried because it is evidence and it is free. Ps 34:8 is
    "trusteth in him" in the KJV and "taketh refuge in him" in three others --
    not a spelling difference but a different node, and the split itself says
    the underlying word carries more than one English word can. A worker shown
    only the KJV would mint `trust` and never know there was a question.
    """
    kjv = _load("verses.jsonl")
    book, cv = ref.rsplit(" ", 1)
    ch, vn = (int(x) for x in cv.split(":"))

    lines = [f"VERSE {ref}", f"  KJV  {kjv.get(ref, '(missing)')}", ""]

    others = []
    for tag, fname in TRANSLATIONS[1:]:
        t = _load(fname).get(ref)
        if t:
            others.append((tag, t))
    if others:
        lines.append("OTHER TRANSLATIONS -- where these differ in a word that "
                     "would change a node, raise a question")
        for tag, t in others:
            lines.append(f"  {tag}  {t}")
        lines.append("")

    around = []
    for d in range(-context, context + 1):
        if d == 0:
            continue
        r = f"{book} {ch}:{vn + d}"
        if r in kjv:
            around.append(f"  {r}  {kjv[r]}")
    if around:
        lines.append("CONTEXT (do not extract from these; they are here so "
                     "that 'immediately after' and 'the same speaker' are "
                     "visible)")
        lines += around
        lines.append("")

    lines.append("Decompose ONLY " + ref + ". Return the JSON object.")
    return "\n".join(lines)


def material_span(refs: list[str], context: int = 1) -> str:
    """The variable half for a window of consecutive verses.

    One call per verse spends a full reasoning pass on each. Measured on
    Ps 23:1 that pass was 10,895 of 11,569 completion tokens -- **94% of the
    cost was thinking, and 674 tokens were writing.** A window amortises the
    thinking across every verse in it, which is the difference between $241
    and something near $50 for the corpus.

    It is also the better prompt. A worker shown all of Psalm 23 can see that
    verse 5 abandons the shepherd for a host and a table; a worker shown verse
    5 alone cannot, and that observation is the whole point of the psalm's
    structure. The risk is the other way -- one verse's mistake bleeding into
    the next -- which is why the answer key exists.
    """
    kjv = _load("verses.jsonl")
    book, cv = refs[0].rsplit(" ", 1)
    ch = int(cv.split(":")[0])

    lines = [f"PASSAGE {refs[0]} - {refs[-1].rsplit(':', 1)[1]}", ""]
    for r in refs:
        lines.append(f"  {r}   {kjv.get(r, '(missing)')}")
    lines.append("")

    orig = _original(refs)
    if orig:
        lines.append("THE ORIGINAL WORDS, in order, each as gloss{lemma}. This "
                     "is the text; the English above is a rendering of it. Name "
                     "nodes from what these words mean, and where a single "
                     "original word is split across several English words, or "
                     "several original words collapse into one, follow the "
                     "original.")
        lines += orig
        lines.append("")

    diverge = []
    for r in refs:
        others = {tag: _load(f).get(r) for tag, f in TRANSLATIONS[1:]}
        base = kjv.get(r, "")
        wordy = {t: v for t, v in others.items()
                 if v and _differs(base, v)}
        if wordy:
            diverge.append((r, wordy))
    if diverge:
        lines.append("WHERE THE TRANSLATIONS DIFFER IN A WORD THAT WOULD "
                     "CHANGE A NODE -- raise a question rather than choosing")
        for r, wordy in diverge[:8]:
            lines.append(f"  {r}")
            for tag, v in wordy.items():
                lines.append(f"    {tag}  {v}")
        lines.append("")

    around = []
    for r, d in ((refs[0], -1), (refs[-1], 1)):
        b, cvv = r.rsplit(" ", 1)
        c, vn = (int(x) for x in cvv.split(":"))
        nb = f"{b} {c}:{vn + d}"
        if nb in kjv:
            around.append(f"  {nb}  {kjv[nb]}")
    if around:
        lines.append("CONTEXT (do not extract from these)")
        lines += around
        lines.append("")

    lines.append(f"Decompose EVERY verse from {refs[0]} to "
                 f"{refs[-1].rsplit(':', 1)[1]}. Each entity and each relation "
                 f"must carry the specific verse it came from in `refs` -- not "
                 f"the whole range. Return one JSON object for the passage.")
    return "\n".join(lines)


_TAGGED: dict | None = None


def _original(refs: list[str]) -> list[str]:
    """The tagged Hebrew or Greek for a window, as `gloss{lemma}` in order.

    2026-09-02: decided to start from Genesis and do a pass of every book on
    an original-language base, since the English alone is not fully trusted.

    Until now the worker saw four English translations and no original at all.
    The divergence block was a **proxy** for the original -- Ps 34:8 splitting
    into "trusteth" and "taketh refuge" is evidence that one Hebrew word
    carries more than one English word can, inferred from the disagreement
    rather than read off the text. The proxy only fires where translators
    happened to differ, and says nothing where they agree on a bad rendering.

    The tagged text is the thing itself and it is already on disk for 29,126
    verses. No script is shown: the blind pair test established that a judge
    reads glosses and definitions, and unpointed consonants would be decoration
    the worker cannot use. What it can use is *which* word, in what order, and
    what that word means -- which is exactly gloss plus lemma.

    Particles and object markers are kept rather than filtered. They are the
    text, they are cheap, and deciding which words do not matter is the
    judgement being delegated.
    """
    global _TAGGED
    if _TAGGED is None:
        try:
            from .lemmas import load_tagged
            _TAGGED = load_tagged()
        except Exception:                                        # noqa: BLE001
            _TAGGED = {}
    if not _TAGGED:
        return []
    out = []
    for r in refs:
        words = _TAGGED.get(r) or []
        if not words:
            continue
        out.append(f"  {r}   "
                   + " ".join(f"{w.gloss}{{{w.lemma}}}" for w in words))
    return out


def _differs(a: str, b: str) -> bool:
    """A wording difference worth showing, not a spelling one."""
    import re
    wa = set(re.findall(r"[a-z]{4,}", a.lower()))
    wb = set(re.findall(r"[a-z]{4,}", b.lower()))
    return len(wa ^ wb) >= 3


def units(book: str, ch: int) -> list[list[str]]:
    """A chapter split where the text itself says to split, or one piece.

    Two markers are explicit enough to trust, and both are in the Psalms.

    **Selah.** 71 occurrences, 67 of them verse-final, across 39 psalms. It is
    a break the text prints, and no interpretation is needed to see it.

    **The acrostic of Psalm 119** -- 176 verses as 22 stanzas of exactly eight,
    one per Hebrew letter. A fixed twelve-verse window cuts every one of them,
    which is a definite fault rather than a risk.

    Everything else returns whole, because a break inferred from content is the
    judgement this pipeline is not competent to make. A reader's own reading of
    Psalm 103 makes the point: it puts a break at v7/v8 that carries no lexical
    marker at all, and argues into and out of another at v13. If a reader
    needs two paragraphs to defend a boundary, a worker guessing at it is
    inventing structure rather than finding it.
    """
    refs = [r for r, _ in chapter(book, ch)]
    if not refs:
        return []

    if book == "Ps" and ch == 119:                    # the acrostic
        return [refs[i:i + 8] for i in range(0, len(refs), 8)]

    if book == "Ps":
        kjv = _load("verses.jsonl")
        out, cur = [], []
        for ref in refs:
            cur.append(ref)
            if "Selah" in (kjv.get(ref) or "") and cur:
                out.append(cur)
                cur = []
        if cur:
            out.append(cur)
        return out

    return [refs]


def windows(book: str, ch: int, size: int = 12) -> list[list[str]]:
    """Units packed into calls of at most `size` verses.

    Two costs pull against each other. Reasoning is charged per call and is
    roughly fixed -- 10,895 tokens on the measured window -- so a two-verse
    call wastes most of what it pays for. But a unit split across two calls is
    read by a worker that cannot see the whole of it.

    Packing resolves both: **never split a unit, but put several whole units in
    one call.** Psalm 3 breaks after verses 2, 4 and 8 and becomes a single
    eight-verse call containing three complete units. Psalm 119 becomes 22
    calls of eight, because two stanzas would exceed the limit.

    A unit longer than `size` is split -- there is nothing else to do with it,
    and a chapter with no marked breaks has told us nothing to preserve.
    """
    out: list[list[str]] = []
    cur: list[str] = []
    for unit in units(book, ch):
        if len(unit) > size:
            if cur:
                out.append(cur)
                cur = []
            out += [unit[i:i + size] for i in range(0, len(unit), size)]
            continue
        if len(cur) + len(unit) > size:
            out.append(cur)
            cur = []
        cur += unit
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------------------
# running
# ---------------------------------------------------------------------------

@dataclass
class Result:
    ref: str
    ok: bool
    entities: list = field(default_factory=list)
    relations: list = field(default_factory=list)
    questions: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    error: str = ""
    raw: str = ""

    @property
    def new_entities(self) -> list:
        return [e for e in self.entities if not e.get("existing")]


# The reviewer answers one checklist question and averages 1,303 completion
# tokens. Decomposing a verse into nodes, edges and questions is a different
# size of task, and on the first real run all six verses of Psalm 23 spent the
# reviewer's whole 8,000-token ceiling reasoning and emitted no content at all
# -- six failures at $0.0054 each, the price of 8,000 output tokens exactly.
# Reasoning bills as output and is spent before any content appears, so the
# budget has to cover both or the money buys nothing.
# Then measured again on a six-verse window, which used ~18,600 of a 20,000
# ceiling -- 93%, and only survived because Psalm 23 is short. The split is
# ~10,900 reasoning, which is FIXED per call, and ~1,290 of content per verse,
# which is not. So a twelve-verse window needs ~26,400 and would have truncated
# every window of the overnight run after the first.
#
# The ceiling is a cap, not a purchase: tokens are billed as generated, so
# raising it costs nothing and only removes a failure. The fixed reasoning cost
# is also why bigger windows are cheaper per verse -- 6 verses carry it at
# $0.00205 each, 12 verses at $0.00145.
# Raised again after Prov 10:13-24 hit 32,000 exactly and came back as JSON
# cut off mid-object. Twelve antithetical couplets are twelve unrelated tasks
# in one call; connected verses are far cheaper to write out than independent
# ones. The farm also halves a window that still will not fit, so this number
# no longer has to be right -- only generous.
MAX_TOKENS = int(os.environ.get("BIBLEONT_DECOMPOSE_MAX_TOKENS", "48000"))


def _diagnose(raw: dict) -> str:
    """Say which of the two silences this was.

    An empty reply with finish_reason 'length' and a large reasoning count is
    a budget failure and is fixed by raising the ceiling. An empty reply that
    stopped normally is a refusal or a confused prompt and raising the ceiling
    would only cost more. They are indistinguishable from the exception text.
    """
    usage = raw.get("usage") or {}
    reasoning = ((usage.get("completion_tokens_details") or {})
                 .get("reasoning_tokens"))
    done = raw.get("finish_reason")
    out = usage.get("completion_tokens")
    bits = []
    if done:
        bits.append(f"finish_reason={done}")
    if out is not None:
        bits.append(f"completion={out}")
    if reasoning is not None:
        bits.append(f"reasoning={reasoning}")
    if done == "length":
        bits.append(f"-> raise BIBLEONT_DECOMPOSE_MAX_TOKENS above {MAX_TOKENS}")
    return "  ".join(bits)


def run_span(refs: list[str], prefix_text: str,
             timeout: int = 300) -> Result:
    """One call for a window of verses. Same contract as `run_one`."""
    from .reviewer import ReplyError, ask

    label = f"{refs[0]}-{refs[-1].rsplit(':', 1)[1]}"
    try:
        got, meta = ask(prefix_text, material_span(refs), timeout=timeout,
                        max_tokens=MAX_TOKENS)
    except ReplyError as exc:
        return Result(ref=label, ok=False, usage=exc.raw.get("usage") or {},
                      error=f"{exc}  [{_diagnose(exc.raw)}]",
                      raw=(exc.raw.get("content") or "")[:400])
    except Exception as exc:                       # noqa: BLE001
        return Result(ref=label, ok=False, error=f"{type(exc).__name__}: {exc}")

    usage = meta.get("usage") or {}
    if not isinstance(got, dict):
        return Result(ref=label, ok=False, usage=usage,
                      error=f"reply was {type(got).__name__}, not an object")
    if meta.get("finish_reason") == "length":
        return Result(ref=label, ok=False, usage=usage,
                      error=f"truncated  [{_diagnose(meta)}]",
                      raw=(meta.get("content") or "")[:400])

    for row in got.get("questions") or []:
        row.setdefault("refs", [refs[0]])
    return Result(ref=label, ok=True,
                  entities=got.get("entities") or [],
                  relations=got.get("relations") or [],
                  questions=got.get("questions") or [],
                  usage=usage)


def run_one(ref: str, prefix_text: str, timeout: int = 120) -> Result:
    """One call. `ask` returns (parsed, meta) and has already stripped fences
    and parsed the JSON, so there is nothing to decode here -- and a
    ReplyError still carries its usage, which is the only way a run that
    burned its budget on reasoning is distinguishable from one that returned
    nothing."""
    from .reviewer import ReplyError, ask

    try:
        got, meta = ask(prefix_text, material(ref), timeout=timeout,
                        max_tokens=MAX_TOKENS)
    except ReplyError as exc:
        # The envelope is the diagnosis. Without it "no JSON object in reply"
        # is printed six times and says nothing about why.
        return Result(ref=ref, ok=False, usage=exc.raw.get("usage") or {},
                      error=f"{exc}  [{_diagnose(exc.raw)}]",
                      raw=(exc.raw.get("content") or "")[:400])
    except Exception as exc:                       # noqa: BLE001
        return Result(ref=ref, ok=False, error=f"{type(exc).__name__}: {exc}")

    usage = meta.get("usage") or {}
    if not isinstance(got, dict):
        return Result(ref=ref, ok=False, usage=usage,
                      error=f"reply was {type(got).__name__}, not an object",
                      raw=(meta.get("content") or "")[:400])
    if meta.get("finish_reason") == "length":
        return Result(ref=ref, ok=False, usage=usage,
                      error="truncated: max_tokens reached before the reply "
                            "finished", raw=(meta.get("content") or "")[:400])

    for row in got.get("questions") or []:
        row.setdefault("refs", [ref])
    return Result(ref=ref, ok=True,
                  entities=got.get("entities") or [],
                  relations=got.get("relations") or [],
                  questions=got.get("questions") or [],
                  usage=usage)


def collapse(questions: list[dict]) -> dict[str, dict]:
    """Group by the question, not the occurrence. See the module docstring."""
    out: dict[str, dict] = {}
    for q in questions:
        key = (q.get("key") or "unkeyed").strip().lower()
        slot = out.setdefault(key, {"key": key, "kind": q.get("kind", ""),
                                    "asks": q.get("asks", ""),
                                    "nodes": set(), "refs": [], "n": 0})
        slot["n"] += 1
        slot["nodes"].update(q.get("nodes") or [])
        slot["refs"] += q.get("refs") or []
        if len(q.get("asks", "")) > len(slot["asks"]):
            slot["asks"] = q["asks"]
    for slot in out.values():
        slot["nodes"] = sorted(slot["nodes"])
    return out


class UnpriceableUsage(Exception):
    """A call reported usage in a shape this function cannot price.

    Raised rather than returning 0.0, because the alternative is what
    actually happened: the farm's provider leaked to Anthropic mid-run, every
    worker window came back with `cache_read_input_tokens` instead of
    `prompt_cache_hit_tokens`, and this function -- reading only DeepSeek's
    keys -- scored eight Opus calls at exactly $0.00. The budget ceiling did
    not fail; it counted correctly to zero and never fired. $6.70 went
    unrecorded and the run continued until the API refused a request.

    **A spend guard that cannot price a call has to stop, not shrug.** Zero is
    the one answer it must never give by default, because zero is
    indistinguishable from thrift.
    """


def cost(usages: list[dict], peak: bool = False) -> float:
    i = 1 if peak else 0
    for u in usages:
        if not u:
            continue
        if not ({"prompt_cache_hit_tokens", "prompt_cache_miss_tokens",
                 "completion_tokens"} & set(u)):
            raise UnpriceableUsage(
                "usage does not look like DeepSeek's "
                f"(keys: {sorted(u)[:6]}). This is what a provider switch "
                "looks like from inside the budget -- refusing to price it "
                "as free.")
    hit = sum(u.get("prompt_cache_hit_tokens", 0) for u in usages)
    miss = sum(u.get("prompt_cache_miss_tokens", 0) for u in usages)
    out = sum(u.get("completion_tokens", 0) for u in usages)
    return (hit * (0.007, 0.014)[i] + miss * (0.22, 0.44)[i]
            + out * (0.66, 1.32)[i]) / 1e6


PROGRESS = PROPOSALS / ".progress"


def journal_path(run: str) -> Path:
    return PROGRESS / f"{run}.jsonl"


def journal(run: str, r: Result) -> None:
    """Persist one window's output the moment it arrives.

    **The batch is written once, at the end of a run. State is written after
    every window.** Those two facts together were a silent data-loss bug: a
    window that returned was marked `done` on disk while its relations existed
    only in memory, so a crash, a closed laptop or a killed terminal left the
    book recorded as complete with a hole where the run died. Resuming skips
    finished windows, so nothing ever went back for them, and no count
    disagreed with any other count. The farm's own docstring promised the
    opposite: "loses at most the window in flight".

    So the journal is the durable record and the batch is derived from it.
    Written BEFORE the window is marked done, which is what makes `done`
    mean "the output is on disk" rather than "the call returned".

    Append-only and one line per window: a partial line from a crash mid-write
    costs that window and nothing else, and is discarded on load.
    """
    PROGRESS.mkdir(parents=True, exist_ok=True)
    with open(journal_path(run), "a", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps({
            "ref": r.ref, "ok": r.ok, "entities": r.entities,
            "relations": r.relations, "questions": r.questions,
            "usage": r.usage, "error": r.error,
        }, ensure_ascii=False, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def replay(run: str) -> list[Result]:
    """Everything a journal holds, as Results. Bad lines are skipped."""
    p = journal_path(run)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue                    # a torn final line from a hard kill
        out.append(Result(
            ref=row.get("ref", ""), ok=bool(row.get("ok")),
            entities=row.get("entities") or [],
            relations=row.get("relations") or [],
            questions=row.get("questions") or [],
            usage=row.get("usage") or {}, error=row.get("error", "")))
    return out


def orphans(book: str) -> list[Path]:
    """Journals for this book that no batch was ever written from.

    A run that died left one. Its windows are marked done, so nothing will
    ever redo them -- the only way they reach the graph is by being folded
    into the next run's batch.
    """
    if not PROGRESS.exists():
        return []
    return sorted(PROGRESS.glob(f"{book.lower()}-*.jsonl"))


def write_batch(name: str, results: list[Result], book: str) -> Path:
    """A proposal directory of the shape the existing gate already reads.

    The gate is batch-local on purpose: it resolves a relation against the
    records in the same directory and nowhere else, so a batch that names an
    id it does not carry is rejected rather than trusted. That is the check
    doing its job, and it means every batch must restate the records it
    touches. `carry` does that from the graph, so a worker only has to name
    the id.
    """
    from .schema import load_entities

    d = PROPOSALS / name
    d.mkdir(parents=True, exist_ok=True)
    ents, rels = [], []
    seen = set()
    for r in results:
        for e in r.new_entities:
            if e.get("id") and e["id"] not in seen:
                seen.add(e["id"])
                e.pop("existing", None)
                e.setdefault("gender", "unknown")
                e["source"] = name
                ents.append(e)
        for rel in r.relations:
            rel["source"] = name
            rels.append(rel)

    # carry: every id a relation touches that the batch did not mint
    known = load_entities()
    missing, unknown = [], []
    for rel in rels:
        for side in (rel.get("src"), rel.get("dst")):
            if not side or side in seen:
                continue
            seen.add(side)
            got = known.get(side)
            if got is None:
                unknown.append(side)
                continue
            row = {"id": got.id, "name": got.name, "type": got.type,
                   "gender": got.gender, "source": name}
            if got.aka:
                row["aka"] = got.aka
            if got.refs:
                row["refs"] = got.refs
            if got.attrs:
                row["attrs"] = got.attrs
            missing.append(row)
    ents.extend(missing)

    def _dump(path: Path, rows: list) -> None:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False,
                                    sort_keys=True) + "\n")

    _dump(d / "entities.jsonl", ents)
    _dump(d / "relations.jsonl", rels)
    from .prefix import revision as _rev
    (d / "META.json").write_text(json.dumps({
        "producer": "bibleont.decompose",
        # Which build of the instructions made this. See prefix.revision.
        "rules_revision": _rev(),
        "book": book,
        "mode": mode_of(book),
        "verses": [r.ref for r in results],
        "failed": [r.ref for r in results if not r.ok],
        "carried": len(missing),
        "unknown_ids": sorted(set(unknown)),
        "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cost_usd": round(cost([r.usage for r in results if r.usage]), 5),
    }, indent=2), encoding="utf-8", newline="")

    QUESTIONS.mkdir(parents=True, exist_ok=True)
    grouped = collapse([q for r in results for q in r.questions])
    with open(QUESTIONS / f"{name}.jsonl", "w", encoding="utf-8",
              newline="") as fh:
        for slot in sorted(grouped.values(), key=lambda s: -s["n"]):
            fh.write(json.dumps(slot, ensure_ascii=False,
                                sort_keys=True) + "\n")
    return d


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry" in argv
    limit = 0
    for a in argv:
        if a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])
    argv = [a for a in argv if not a.startswith("--")]
    if len(argv) < 2:
        print("usage: python -m bibleont.decompose <Book> <chapter> "
              "[--dry] [--limit=N]")
        print("       python -m bibleont.decompose Ps 23 --limit=1")
        return 2

    book, ch = argv[0], int(argv[1])
    verses = chapter(book, ch)
    if not verses:
        print(f"no such chapter: {book} {ch}")
        return 1
    if limit:
        verses = verses[:limit]

    pre = build_prefix(book)
    print(f"{book} {ch}: {len(verses)} verses, {pre.mode} mode, "
          f"prefix {pre.tokens:,} tokens over {pre.nodes} nodes")

    if dry:
        print(f"\n{'=' * 70}\nPREFIX (cached, first {600} chars)\n{'=' * 70}")
        print(pre.text[:600] + "\n...")
        print(f"\n{'=' * 70}\nVARIABLE PART, first verse\n{'=' * 70}")
        print(material(verses[0][0]))
        var = len(material(verses[0][0])) // 4
        print(f"\nvariable ~{var} tokens/verse")
        print(f"estimate  ${pre.cost_per_call() * len(verses) + var * 0.22 / 1e6 * len(verses) + 2500 * 0.66 / 1e6 * len(verses):.4f} "
              f"for {len(verses)} verses (assuming 2,500 output tokens each)")
        return 0

    # Ask the active provider which variable it wants. Naming DeepSeek's here
    # was wrong the moment a second provider existed: it would refuse a Groq
    # run whose key was perfectly well set, and name the wrong variable while
    # doing it.
    from .providers import current as _provider
    prov = _provider()
    if not prov.key:
        print(f"{prov.key_env} is not set; nothing was called.")
        print(f"  (provider is {prov.name} -- "
              f"`python -m bibleont.providers show`)")
        return 1
    if not prov.model:
        print(f"{prov.model_env} is not set; nothing was called.")
        return 1

    results = []
    for ref, _ in verses:
        r = run_one(ref, pre.text)
        results.append(r)
        mark = "ok " if r.ok else "FAIL"
        extra = (f"{len(r.new_entities)} new, {len(r.relations)} rel, "
                 f"{len(r.questions)} q") if r.ok else r.error
        print(f"  {mark} {ref:12} {extra}")

    RUNS.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    with open(RUNS / f"{stamp}.jsonl", "w", encoding="utf-8",
              newline="") as fh:
        for r in results:
            fh.write(json.dumps({"ref": r.ref, "ok": r.ok,
                                 "error": r.error, "usage": r.usage,
                                 "producer": "decompose",
                                 "max_tokens": MAX_TOKENS},
                                ensure_ascii=False, sort_keys=True) + "\n")

    name = f"{book.lower()}-{ch}-decomposed"
    d = write_batch(name, results, book)
    spent = cost([r.usage for r in results if r.usage])
    grouped = collapse([q for r in results for q in r.questions])
    print(f"\nwrote {d.relative_to(ROOT)}")
    print(f"  {sum(len(r.new_entities) for r in results)} new entities, "
          f"{sum(len(r.relations) for r in results)} relations")
    print(f"  {sum(len(r.questions) for r in results)} questions collapse to "
          f"{len(grouped)} distinct")
    print(f"  ${spent:.5f} spent  (${spent / max(len(verses), 1):.5f}/verse, "
          f"${spent / max(len(verses), 1) * 31102:,.0f} for the Bible)")
    print(f"\nnext: python -m bibleont.proposals check {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
