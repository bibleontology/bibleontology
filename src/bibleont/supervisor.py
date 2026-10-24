"""The supervisor's ledger: what it has spent, and what that leaves.

The supervisor is an Opus process that samples the farm's output, coaches the
worker when it finds a problem, and can suspend or stop a run. This module is
its memory. The judgement lives in the model; the arithmetic that judgement
needs lives here.

## Why a ledger at all

**Each run starts with no memory of the last one.** A supervisor told "you have
twenty dollars for the whole Bible" cannot honour that instruction if it does
not know whether two dollars or eighteen are already gone. Without this file it
would either spend freely every night or refuse to spend at all, and both are
failures -- the first exhausts the budget in Genesis, the second watches the
whole corpus go wrong cheaply and reports a healthy balance.

## The rule that decides when to spend

Coaching is an investment and its return is **the corpus not yet extracted**. A
fix made in Genesis is amortised across every remaining window; the same fix
made in Revelation earns almost nothing back. So willingness to spend tracks
remaining runway, which is the arithmetic version of a manager investing
heavily in someone's first month and not sending them on a course in their
final week.

That single principle produces both required behaviours. Early, deliberate
overspending is correct. Late, the same spend is waste and cutting losses is
right. The supervisor is given the principle and its position, not a schedule.

## The two guards

**A reserve floor**, so a bad night in Exodus cannot leave Isaiah unsupervised.
It shrinks as the corpus is consumed, because there is less left to protect.

**An under-intervention trigger**, because a cautious supervisor that watches
quality collapse while spending nothing is failing expensively and the ledger
would otherwise show it as thrift. Not intervening is a decision and it is
recorded as one.

## What this module does not do

It does not call a model, and it does not decide anything. It reports position.
Everything that requires judgement is the supervisor's, and everything that
changes what the graph *means* -- the vocabulary, identity decisions, what the
About view claims -- is escalated past the supervisor to a person.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from .paths import ROOT

DIR = ROOT / "ontology" / "proposals" / ".supervisor"
LEDGER = DIR / "ledger.json"
REPORTS = DIR / "reports"

# The corpus, in windows of twelve. The denominator for every "how much is
# left to benefit" question, and the reason the whole Bible is affordable at
# all: measured at $0.018 a window against DeepSeek.
TOTAL_WINDOWS = 2592

# Below this the supervisor may only observe and escalate -- never coach, and
# never start an investigation it cannot finish. Expressed as a share of the
# grant rather than a figure, so it scales if the grant changes.
RESERVE_SHARE = 0.15

# An error rate this high with no intervention is itself a finding. Set from
# measured behaviour: the merged graph runs at roughly 1% faulty relations,
# and Job's speaker-index failure sat at 0% by every mechanical measure --
# which is exactly why the trigger cannot be the only signal.
CONCERN_RATE = 0.03


RUBRIC = """\
You are supervising an extraction worker that is decomposing the King James
Bible into a graph. You are not extracting. You are judging whether what the
worker produced records **what the passage communicates**, or merely which
words appear in it.

That distinction is the whole job, because everything mechanical is already
checked before you see it. Citations resolve, relation types exist, quotations
match the verse, entity types satisfy the vocabulary. A batch can pass every
one of those and still be worthless.

## The failure you exist to catch

Job's three friends argue with him for thirty-five chapters. The worker
recorded 109 of the 128 relations around them as:

    bildad -told-> job_8_3          (a node whose name is the verse text)
    bildad -told-> job_8_10
    bildad -told-> job_8_11

That is a **speaker index**, not an argument. It says who spoke which verse
and nothing about what anyone claimed. The book's own verdict -- "ye have not
spoken of me the thing that is right" (Job 42:7) -- produced no relations at
all. Every one of those edges is well-formed, correctly cited, correctly
typed, and passes every automated check.

Related shapes, all seen in real output:

  **Tag clouds.** `job_1_1 -speaks_of-> man`, `-> perfect`, `-> upright`. Five
  edges restating the nouns in the sentence. Measured across the graph, 80% of
  `speaks_of` edges point at a word already present in the verse. The verse is
  not *about* the words it contains.

  **A node named with a whole verse.** Ids are references (`job_1_1`); names
  should be short labels a reader recognises. Names of 100+ characters are the
  worker storing a second copy of scripture.

  **Compression into single-use nodes.** `perfect_and_upright` as one node
  means Job cannot be connected to Noah, whom the corpus pairs with him
  explicitly (Ezek 14:14). Split claims are shareable; compound ones are dead
  ends.

## What good output looks like

Propositions, not tags. From "There was a man in the land of Uz, whose name
was Job; and that man was perfect and upright":

    job -dwelt_at----> uz
    job -assessed_as-> perfect
    job -assessed_as-> upright

Each is a claim with a citation. Each connects entities that other verses also
touch. That is a graph; the tag cloud is a concordance.

## Your verdict

Return ONLY this JSON. **No prose, no preamble, no explanation outside the
fields.** Output tokens cost five times input here and your reasoning is
charged as output, so a long answer is a worse answer at the same accuracy.

{
  "verdict": "sound" | "concern" | "stop",
  "faults": [
    {"kind": "tag-cloud|speaker-index|verse-as-name|compound|other",
     "example": "one id or edge, verbatim",
     "why": "at most 15 words"}
  ],
  "coach": "",
  "escalate": ""
}

  sound     record it and move on
  concern   real defects; set `coach` to the instruction the worker should be
            given, written as rule + worked example + why. It is appended to
            the worker's prompt and takes effect on the next window.
  stop      the output is not usable and continuing wastes money

`escalate` is for what you must NOT decide alone: anything that would change
the vocabulary, an identity ruling, or what the graph claims about scripture.
Name it there and let a person settle it.

Leave `coach` and `escalate` empty strings when they do not apply.
"""


def count_tokens(system: str, user: str, model: str = "claude-opus-5") -> int:
    """What a call would cost to send, without sending it.

    `/v1/messages/count_tokens` prices the input side exactly. With a hard
    stop and no auto-reload, being able to ask before committing is the
    difference between a budget and a hope.
    """
    import urllib.request
    from .providers import PROVIDERS, auth

    prov = PROVIDERS["anthropic"]
    body = json.dumps({
        "model": model,
        "system": [{"type": "text", "text": system}],
        "messages": [{"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        prov.base.rstrip("/") + "/messages/count_tokens",
        data=body, headers=auth(prov))
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(json.loads(r.read()).get("input_tokens") or 0)


def price(usage: dict, model: str = "claude-opus-5") -> float:
    """Dollars for one Anthropic call, from the usage it reports.

    `decompose.cost` speaks DeepSeek's shape -- `prompt_cache_hit_tokens` and
    friends. Anthropic reports `input_tokens`, `output_tokens`,
    `cache_read_input_tokens` and `cache_creation_input_tokens`, and the
    supervisor's whole budget discipline rests on reading them correctly.

    **Thinking tokens are output tokens.** The first live call spent 68 of its
    133 output tokens thinking, and output is the expensive side -- so a
    supervisor that reasons at length about a small window costs more than the
    window did to produce. That is the number to watch, and it is why reviews
    are asked for verdicts rather than essays.

    Cache writes are charged above the base input rate and reads far below it;
    both are folded in at the miss and hit rates the provider table carries,
    which are rounded up on purpose. See the note there.
    """
    from .providers import PROVIDERS
    rates = (PROVIDERS["anthropic"].rates or {}).get(model)
    if not rates:
        return 0.0
    read = int(usage.get("cache_read_input_tokens") or 0)
    written = int(usage.get("cache_creation_input_tokens") or 0)
    plain = int(usage.get("input_tokens") or 0)
    out = int(usage.get("output_tokens") or 0)
    hit, miss, o = rates["hit"][0], rates["miss"][0], rates["out"][0]
    # Cache writes cost more than plain input, not the same. Falls back to the
    # base rate for a model whose table predates the `write` key.
    w = (rates.get("write") or (miss,))[0]
    return round((read * hit + plain * miss + written * w + out * o) / 1e6, 6)


@dataclass
class Run:
    """One night's supervision, as reported by the supervisor itself."""
    when: str = ""
    book: str = ""
    windows_seen: int = 0
    reviewed: int = 0
    findings: int = 0
    interventions: int = 0
    escalations: list = field(default_factory=list)
    spent: float = 0.0
    clean_before: float | None = None
    clean_after: float | None = None
    note: str = ""

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def _read() -> dict:
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return {}


def grant(amount: float) -> dict:
    """Record what the supervisor has been given. Adds to any prior grant."""
    led = _read()
    led["granted"] = round(float(led.get("granted") or 0) + amount, 4)
    led.setdefault("spent", 0.0)
    led.setdefault("runs", [])
    led["auto_reload"] = False          # a hard stop, and it should be
    DIR.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, indent=1), encoding="utf-8", newline="")
    return led


def record(run: Run) -> dict:
    led = _read()
    led.setdefault("granted", 0.0)
    led["spent"] = round(float(led.get("spent") or 0) + run.spent, 4)
    led.setdefault("runs", []).append(run.as_dict())
    DIR.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, indent=1), encoding="utf-8", newline="")
    return led


def windows_done() -> int:
    """Windows the farm has finished across every book."""
    state = ROOT / "ontology" / "proposals" / ".farm"
    if not state.is_dir():
        return 0
    n = 0
    for path in state.glob("*.json"):
        try:
            n += len(json.loads(path.read_text(encoding="utf-8")).get("done") or {})
        except Exception:                                    # noqa: BLE001
            continue
    return n


def position() -> dict:
    """Where the supervisor stands, and what that permits.

    Everything here is arithmetic the supervisor should not have to redo, and
    that a person should be able to read on a phone without doing sums.
    """
    led = _read()
    granted = float(led.get("granted") or 0)
    spent = float(led.get("spent") or 0)
    left = max(0.0, granted - spent)
    reserve = round(granted * RESERVE_SHARE, 4)

    done = windows_done()
    remaining = max(0, TOTAL_WINDOWS - done)

    # What a window of supervision may cost, on average, if the remaining
    # budget is to reach the end of the corpus. The headline number: it falls
    # when spending outruns progress and rises when it does not.
    per_window = (left / remaining) if remaining else 0.0

    runs = led.get("runs") or []
    interventions = sum(int(r.get("interventions") or 0) for r in runs)
    return {
        "configured": bool(granted),
        "granted": round(granted, 4),
        "spent": round(spent, 4),
        "left": round(left, 4),
        "reserve": reserve,
        # Below the reserve the supervisor observes and escalates only. Said
        # plainly rather than left for the reader to compare two numbers.
        "coaching_allowed": left > reserve,
        "auto_reload": bool(led.get("auto_reload")),
        "windows_done": done,
        "windows_total": TOTAL_WINDOWS,
        "windows_remaining": remaining,
        "corpus_share": round(done / TOTAL_WINDOWS, 4) if TOTAL_WINDOWS else 0.0,
        "per_remaining_window": round(per_window, 5),
        "runs": len(runs),
        "interventions": interventions,
        "last": runs[-1] if runs else None,
    }


SAMPLE = 40


def material(book: str, chapter: int, limit: int = SAMPLE,
             batch: str | None = None) -> str:
    """What the supervisor is shown: the passage, and what was made of it.

    **Sampled, not exhaustive, and that is not a compromise.** Every failure
    this is looking for is systemic -- a tag cloud, a speaker index, ids that
    are sentences. Twenty edges show the pattern as clearly as two hundred,
    and the supervisor is not auditing individual relations: the gate already
    did that, per relation, for nothing.

    Sending everything cost $0.17 to $0.29 for one chapter, which is $20 for
    about a hundred reviews. Sampled, the same judgement costs a third of
    that. The saving is not in what it reads but in what it then has to say.

    Spread across the chapter rather than taken from the front, so a worker
    that starts well and degrades is not reviewed only on its first verses.
    """
    from .decompose import chapter as verses_of
    from .schema import load_entities, load_relations

    rows = verses_of(book, chapter)
    refs = {ref for ref, _ in rows}
    # A batch, when given, or the merged graph.
    #
    # Without this the supervisor reviews the MERGED graph -- which for any
    # freshly extracted book is yesterday's work, silently. `draw.py` had the
    # identical defect and showed stale diagrams for a whole afternoon while
    # being described as current. A reviewer reading the wrong source is worse
    # than no reviewer: it returns a verdict on work nobody is shipping.
    if batch:
        from .draw import from_batch

        ents, all_rels = from_batch(batch)
    else:
        ents, all_rels = load_entities(), load_relations()
    rels = [r for r in all_rels
            if any(x in refs for x in (r.refs or []))]
    total = len(rels)
    if limit and total > limit:
        step = total / limit
        rels = [rels[int(i * step)] for i in range(limit)]

    out = [f"PASSAGE — {book} {chapter}", ""]
    for ref, text in rows:
        out.append(f"{ref}  {text}")

    head = (f"WHAT THE WORKER PRODUCED — {total} relations"
            + (f", {len(rels)} shown, sampled evenly across the chapter"
               if len(rels) < total else ""))
    out += ["", head, ""]
    seen: set[str] = set()
    for r in rels:
        out.append(f"  {r.src} -{r.type}-> {r.dst}   {r.refs}")
        seen.update((r.src, r.dst))

    out += ["", "NODES THOSE TOUCH", ""]
    for i in sorted(seen):
        e = ents.get(i)
        if not e:
            continue
        name = e.name if len(e.name) <= 70 else e.name[:67] + "..."
        out.append(f"  {i}  [{e.type}]  {name!r}")

    out += ["", "Judge it. Return only the JSON."]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] == "review":
        if len(argv) < 3:
            print("usage: python -m bibleont.supervisor review <Book> <chapter> [--dry]")
            return 2
        book, chapter = argv[1], int(argv[2])
        dry = "--dry" in argv
        batch = None
        for a in argv:
            if a.startswith("--batch="):
                batch = a.split("=", 1)[1]
        user = material(book, chapter, batch=batch)

        pos = position()
        if not pos["configured"]:
            print("no grant recorded:  python -m bibleont.supervisor grant 20")
            return 1

        n = count_tokens(RUBRIC, user)
        rubric_tokens = count_tokens(RUBRIC, ".")
        # The generation side is the unknown until it runs; quoted at the
        # terse end and the long end so the range is visible rather than a
        # single number that will turn out wrong.
        lo = price({"input_tokens": n, "output_tokens": 400})
        hi = price({"input_tokens": n, "output_tokens": 2000})
        # Review two onwards reads the rubric from cache instead of paying to
        # send it. Shown separately because the first review's price is not
        # the one that multiplies across a night's run.
        warm_lo = price({"input_tokens": n - rubric_tokens,
                         "cache_read_input_tokens": rubric_tokens,
                         "output_tokens": 400})
        print(f"  reviewing  {book} {chapter}")
        print(f"  payload    {n:,} input tokens "
              f"({rubric_tokens:,} of them the rubric)")
        print(f"  cost       ${lo:.4f} terse … ${hi:.4f} verbose   (first review)")
        print(f"             ${warm_lo:.4f} terse once the rubric is cached")
        pos_left = pos["left"]
        if warm_lo > 0:
            print(f"             ${pos_left:.2f} buys ~{int(pos_left / warm_lo)} "
                  f"reviews, against {pos['windows_remaining']:,} windows left "
                  f"(1 in {max(1, round(pos['windows_remaining'] / max(1, pos_left / warm_lo)))})")
        print(f"  budget     ${pos['left']:.2f} left of ${pos['granted']:.2f}"
              f"   reserve ${pos['reserve']:.2f}")
        if dry:
            print()
            print("  --- what would be sent (user turn) ---")
            head = user.splitlines()
            for line in head[:34]:
                print(f"  {line}")
            if len(head) > 34:
                print(f"  … {len(head) - 34} more lines")
            print()
            print("  dry run: nothing was generated, nothing was charged for output")
            return 0

        if not pos["coaching_allowed"]:
            print("  BELOW RESERVE — observing only, no coaching")
        os.environ["BIBLEONT_PROVIDER"] = "anthropic"
        from .reviewer import ask
        verdict, raw = ask(RUBRIC, user, timeout=240, max_tokens=4000)
        spent = price(raw.get("usage") or {})
        print()
        print(f"  verdict    {verdict.get('verdict')}   (${spent:.4f}, "
              f"{(raw.get('usage') or {}).get('output_tokens')} output tokens)")
        for f in verdict.get("faults") or []:
            print(f"    [{f.get('kind')}] {f.get('example')}")
            print(f"        {f.get('why')}")
        if verdict.get("coach"):
            print(f"  coach      {verdict['coach'][:400]}")
        if verdict.get("escalate"):
            print(f"  ESCALATE   {verdict['escalate']}")
        record(Run(when=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   book=f"{book} {chapter}", reviewed=1,
                   findings=len(verdict.get("faults") or []),
                   interventions=1 if verdict.get("coach") else 0,
                   escalations=[verdict["escalate"]] if verdict.get("escalate") else [],
                   spent=spent, note=verdict.get("verdict", "")))
        return 0

    if argv and argv[0] == "grant":
        if len(argv) < 2:
            print("usage: python -m bibleont.supervisor grant <usd>")
            return 2
        led = grant(float(argv[1]))
        print(f"  granted ${led['granted']:.2f} in total")
        return 0

    p = position()
    if not p["configured"]:
        print("  no grant recorded yet:")
        print("    python -m bibleont.supervisor grant 20")
        return 1
    print(f"  budget     ${p['left']:.2f} of ${p['granted']:.2f} left"
          + ("" if p["auto_reload"] else "   (auto-reload OFF: a hard stop)"))
    print(f"  reserve    ${p['reserve']:.2f}"
          + ("" if p["coaching_allowed"] else "   -- BELOW RESERVE: observe and escalate only"))
    print(f"  corpus     {p['windows_done']}/{p['windows_total']} windows "
          f"({100 * p['corpus_share']:.0f}%), {p['windows_remaining']} remaining")
    print(f"  runway     ${p['per_remaining_window']:.4f} per remaining window")
    print(f"  history    {p['runs']} run(s), {p['interventions']} intervention(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
