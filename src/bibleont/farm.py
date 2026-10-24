"""Run the decomposer over a book, unattended, and stop before it hurts.

The thing that makes an unattended run different from an attended one is not
throughput. It is that nobody is watching when it goes wrong, so every way it
can go wrong has to be decided in advance and written down here.

## What stops it

**A budget ceiling, always.** Not optional and not defaulted to infinity. The
run keeps a running total from the usage each call reports and stops the moment
the next call could exceed the ceiling. The owner puts a couple of dollars on the
account at a time and the point of that habit is that nothing can spend more
than was decided; a runner that ignores it would quietly undo the safeguard.

**An empty account.** DeepSeek answers 402 when the balance is gone. That is
not an error to retry -- retrying it is how a loop turns one failure into four
hundred.

**A dead key.** 401 likewise. A key revoked mid-run (which happened while this
was being built) should stop the run, not hammer the endpoint.

**Repeated failure.** Three consecutive failures of any kind. One bad passage
is a passage; three in a row is the prompt, the model, or the network, and none
of those get better by continuing.

**Rate limiting.** 429 backs off and retries, twice, then counts as a failure.
That one really is transient.

**Work that answers cleanly and cannot be used.** Two windows in a row whose
relations mostly cannot enter the graph. This is the subtlest stop and both
halves of it were learned the expensive way.

*A type the vocabulary does not have.* The first Proverbs run reported `ok`
three times while every composition edge in it was refused downstream, because
the prompt told the worker to use `composed_of` and the schema had never heard
of it.

*A reference to something that does not exist.* Proverbs 10 then produced 31
relations out of 121 naming concepts the window never declared -- and that was
found only after the run, at the gate. The gate is the right place to refuse
such a relation and the wrong place to notice it, because by then it is paid
for.

A 200, valid JSON, and a batch that cannot be merged all look identical from
inside the loop. Over 89 windows that is five hours and $1.90 for nothing.

It is deliberately *not* an Opus reviewer sitting in the farm. The failure that
justifies stopping a run is the one that repeats identically every window, and
arithmetic can see it.

## What it remembers

State is written after **every window**, and so is the output. A crash, a
closed laptop or a killed terminal loses at most the window in flight.
Resuming is the same command: finished windows are skipped, and the run says
how many it skipped so that "it did nothing" and "it was already done" cannot
be confused.

That claim was false for most of this module's life, and read as true. State
was written per window and the BATCH was written once at the end, so a window
that returned was marked done on disk while its relations existed only in
memory. A run killed at window 40 left forty windows recorded as finished with
their output gone, and because finished windows are skipped, nothing ever went
back for them. No count disagreed with any other count; the book simply had a
hole in it and reported itself complete.

Now each window is appended to a journal in `.progress/` **before** it is
marked done, and the batch is derived from the journal at the end. A journal
whose run died is adopted by the next run over the same book, so work that was
paid for reaches the graph even though it will never be re-extracted.

## Why windows and not chapters

Measured on Ps 23:1, a single-verse call spent 10,895 of 11,569 completion
tokens reasoning -- 94% of the cost was thinking and 674 tokens were writing.
Reasoning is per call, so twelve verses in one call pay for it once. Psalm 119
is 176 verses, which is why the unit is a window of twelve rather than a
chapter.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from .decompose import (MAX_TOKENS, Result, collapse, cost, journal,
                        journal_path, orphans, replay, run_span, windows,
                        write_batch)
from .paths import ROOT
from .prefix import build as build_prefix

STATE_DIR = ROOT / "ontology" / "proposals" / ".farm"

STOP_HTTP = {401: "the key was rejected (401) -- revoked or wrong",
             402: "the account is out of credit (402)",
             403: "forbidden (403)"}


@dataclass
class State:
    book: str
    done: dict = field(default_factory=dict)      # "Ps 23:1-6" -> summary
    created: dict = field(default_factory=dict)   # id -> name, in creation order
    spent: float = 0.0
    started: str = ""
    # The linter's last word, replaced rather than accumulated. Appending
    # every window's findings would grow the prompt without bound and stack
    # corrections that contradict each other; the most recent failure is the
    # one the worker is about to repeat.
    coaching: str = ""

    @property
    def path(self) -> Path:
        return STATE_DIR / f"{self.book.lower()}.json"

    @classmethod
    def load(cls, book: str) -> "State":
        p = STATE_DIR / f"{book.lower()}.json"
        if p.exists():
            raw = json.loads(p.read_text(encoding="utf-8"))
            return cls(book=book, done=raw.get("done") or {},
                       created=raw.get("created") or {},
                       spent=raw.get("spent") or 0.0,
                       started=raw.get("started") or "",
                       coaching=raw.get("coaching") or "")
        return cls(book=book,
                   started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def save(self) -> None:
        """Write the state, atomically, and never in place.

        This file is the only record of which windows are done. Genesis holds
        145 of them and cost $2.73; a half-written `done` map silently re-runs
        finished work or, worse, is unreadable JSON and loses the lot.
        `write_text` truncates first, so an interruption between truncate and
        write is exactly that catastrophe. Writing beside it and renaming means
        the file is either the old state or the new one, never a fragment --
        `os.replace` is atomic on both platforms.

        The retries are for Windows. Job died with `OSError: [Errno 22]
        Invalid argument` opening this path, on a Store-installed Python whose
        filesystem is virtualized; the same write succeeded moments later from
        a normal interpreter. Antivirus and search indexers produce the same
        transient failure on a file that was just written. Three tries a
        quarter-second apart costs nothing and turns a lost run into a pause.
        """
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        blob = json.dumps({
            "book": self.book, "started": self.started,
            "spent": round(self.spent, 5), "done": self.done,
            "created": self.created, "coaching": self.coaching,
        }, indent=1)
        tmp = self.path.with_suffix(f".json.tmp{os.getpid()}")
        last: OSError | None = None
        for attempt in range(3):
            try:
                tmp.write_text(blob, encoding="utf-8", newline="")
                os.replace(tmp, self.path)
                break
            except OSError as exc:                       # noqa: PERF203
                last = exc
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
                if attempt < 2:
                    time.sleep(0.25)
        else:
            # Out of retries. The old file is still intact -- that is the
            # point of the rename -- so say what was not recorded and let the
            # caller decide, rather than dying with a traceback that looks
            # like the state is gone.
            raise OSError(
                f"could not save farm state after 3 tries ({last}). "
                f"{self.path.name} was NOT modified and still holds whatever "
                f"the last successful save wrote; the {len(self.done)} "
                f"window(s) in memory are unrecorded beyond that point. "
                f"Finished windows are in the run journal either way."
            ) from last
        self._refresh_balance()

    _balance_at = 0.0

    def _refresh_balance(self, every: int = 900) -> None:
        """Record the provider balance while we have the key in hand.

        The dashboard cannot fetch this itself -- the web server deliberately
        holds no API credential -- so the process that is doing the spending
        reports what is left. Every fifteen minutes: often enough that the
        figure is current while a run is burning through credit, rare enough
        to be invisible against the cost of the run itself.

        Never fatal. A provider that will not answer a balance query is not a
        reason to stop extracting.
        """
        now = time.time()
        if now - State._balance_at < every:
            return
        State._balance_at = now
        try:
            from .ops import refresh_balance
            refresh_balance()
        except Exception:                                    # noqa: BLE001
            pass



def _review_interval(n_done: int, clean_streak: int) -> int:
    """How many windows apart reviews should be, on quality grounds alone.

    Split out of `_should_review` so the governor can widen it for money
    without either concern having to know about the other. Returns the
    interval; the caller decides whether this window lands on it.
    """
    if n_done < 3:
        return 1
    return min(2 ** clean_streak, 32)


def _should_review(n_done: int, clean_streak: int) -> bool:
    """Whether the supervisor looks at this window.

    The review should be frequent early and gradually become less frequent
    depending on how well the agent is doing.

    So the schedule is not a fixed rate. The first three windows are always
    reviewed, because a prompt change shows itself immediately and a run that
    is going wrong should be caught in the first ten minutes rather than the
    fourth hour. After that the interval doubles for each clean verdict and
    resets the moment one is not clean.

    The economics agree with the pedagogy, which is the useful part. A fix
    made early is amortised over every remaining window; the same fix in the
    last chapter earns nothing back. Reviewing heavily at the start is both
    the better teaching and the better investment.
    """
    if n_done < 3:
        return True
    interval = min(2 ** clean_streak, 32)
    return n_done % interval == 0


def _supervise(book: str, ref: str, state, spent_here: float,
               gov=None) -> tuple[str, str]:
    """One supervisor review of the chapter this window sits in.

    Returns (verdict, coaching). Any failure returns ("", "") -- a supervisor
    that cannot be reached must never stop a run that is otherwise working,
    and an unreachable reviewer is not a finding about the extraction.

    **It reads the run journal, not the merged graph.** The chapter under review
    was extracted minutes ago and is nowhere near a merge; reviewing the
    merged graph would return a verdict on last week's work while reporting it
    as current. `draw.py` and the supervisor's own `material` both had that
    defect and both showed stale results confidently.
    """
    import os
    import re as _re

    try:
        from .supervisor import RUBRIC, material, position, price
        from .reviewer import ask

        pos = position()
        if not pos["configured"] or not pos["coaching_allowed"]:
            # Say so ONCE rather than standing down in silence. Titus ran
            # three windows with the supervisor disarmed and nothing on
            # screen said why: the ledger still held the balance from before
            # $5 was added, so `coaching_allowed` was false while the account
            # was funded. A guard that declines quietly is indistinguishable
            # from one that is working.
            if not getattr(_supervise, "_said", False):
                _supervise._said = True
                print(f"  supervisor STAND-DOWN: ledger says "
                      f"${pos.get('left', 0):.2f} left of ${pos.get('granted', 0):.2f}. "
                      f"If the account was topped up, the ledger needs it too.",
                      flush=True)
            return "", ""

        # Asked BEFORE the call and against the worst case, because a ceiling
        # consulted afterwards is a receipt.
        if gov is not None:
            ok, why = gov.may_spend()
            if not ok:
                print(f"  supervisor OFF for the rest of this run -- {why}",
                      flush=True)
                return "", ""

        m = _re.match(r"^(.+) (\d+):", ref)
        if not m:
            return "", ""
        chapter = int(m.group(2))

        # RESTORED, always. This used to be a bare assignment, and because
        # `current()` reads the env var on every call it did not switch the
        # reviewer to Anthropic -- it switched THE WHOLE PROCESS, permanently,
        # from the first review onward. Exodus ran eight worker windows on
        # Opus believing they were DeepSeek: $6.70 against the $20 grant,
        # invisible to both ledgers, and the run only stopped because
        # Anthropic rejected `max_tokens=48000` with a 400.
        with _provider("anthropic"):
            user = material(book, chapter)
            verdict, raw = ask(RUBRIC, user, timeout=240, max_tokens=4000)
            cost = price(raw.get("usage") or {})
        if gov is not None:
            gov.record(cost)

        from .supervisor import Run, record
        v = str(verdict.get("verdict") or "")
        coach = str(verdict.get("coach") or "")
        esc = str(verdict.get("escalate") or "")
        record(Run(when=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   book=f"{book} {chapter}", reviewed=1,
                   findings=len(verdict.get("faults") or []),
                   interventions=1 if coach.strip() else 0,
                   escalations=[esc] if esc.strip() else [],
                   spent=cost, note=v))
        mark = {"sound": "ok", "concern": "CONCERN", "stop": "STOP"}.get(v, v)
        print(f"  supervisor {mark:8} {book} {chapter}  "
              f"{len(verdict.get('faults') or [])} fault(s)  ${cost:.4f}",
              flush=True)
        if esc.strip():
            print(f"    ESCALATED: {esc[:120]}", flush=True)
        return v, coach
    except Exception as exc:                                 # noqa: BLE001
        # Say WHY, and disarm on a failure that will repeat.
        #
        # This printed only the exception class, so an exhausted Anthropic
        # balance read as "(supervisor unavailable: HTTPError)" on every
        # window -- indistinguishable from a timeout, and a run went hours
        # with no supervision while reporting a shrug each time. A cause that
        # cannot get better by trying again must stop trying.
        why = _http_stop(exc)
        if why and gov is not None:
            gov.stopped = why
        print(f"  supervisor unavailable: {why or type(exc).__name__}"
              + (" -- OFF for the rest of this run" if why else ""),
              flush=True)
        return "", ""


@contextmanager
def _provider(name: str):
    """Point `providers.current()` somewhere else, and always point it back.

    `current()` resolves the provider per call from the environment, so
    setting the variable is not scoping a client -- it is redirecting every
    subsequent call in the process, including the worker's.
    """
    was = os.environ.get("BIBLEONT_PROVIDER")
    os.environ["BIBLEONT_PROVIDER"] = name
    try:
        yield
    finally:
        if was is None:
            os.environ.pop("BIBLEONT_PROVIDER", None)
        else:
            os.environ["BIBLEONT_PROVIDER"] = was


def _lint_feedback(r: Result) -> str:
    """Check a window the moment it lands, and phrase the faults as a lesson.

    Free and instant, which is the whole argument for it: a DeepSeek retry
    costs $0.018 and an Opus review $0.094, while this costs nothing and
    answers before the next call is made. It also arrives at the only moment
    that teaches -- with the worker's own mistake in front of it.

    Fed FORWARD rather than retried. The window that erred is already paid
    for, and a book is 145 windows, so correcting the next one is both
    cheaper and compounding. Retrying would buy one clean window at the price
    of never learning across them.
    """
    try:
        from .lint import feedback, run as lint_run
        from .schema import Person, Relation, canonical_fields, load_entities

        # THE GRAPH FIRST, THEN THE WINDOW ON TOP.
        #
        # Passing only the window's new entities made this silently useless: a
        # relation reaching a node the worker REUSED -- which is most of them,
        # because the prefix hands it the whole vocabulary and says to reuse
        # ids verbatim -- had no type to check, so every rule skipped it. A
        # Hagai batch with 18 level-skips and 14 speaker-index findings
        # reported clean.
        ents = dict(load_entities())
        for e in r.new_entities:
            try:
                ents[e["id"]] = Person(**canonical_fields(dict(e)))
            except Exception:                                # noqa: BLE001
                continue
        rels = []
        for rel in r.relations:
            try:
                rels.append(Relation(**canonical_fields(dict(rel))))
            except Exception:                                # noqa: BLE001
                continue
        mine = {e["id"] for e in r.new_entities if e.get("id")}
        return feedback(lint_run(ents, rels, subject=mine))
    except Exception:                                        # noqa: BLE001
        # A linter that breaks must not stop a run that is otherwise working.
        return ""


def chapters_of(book: str) -> list[int]:
    import json as _json
    seen = []
    from .paths import text_path
    with open(text_path(), encoding="utf-8") as fh:
        for line in fh:
            r = _json.loads(line)
            if r.get("b") == book and r.get("c") not in seen:
                seen.append(r["c"])
    return seen


RUNS = ROOT / "ontology" / "proposals" / ".runs"
_LOG: Path | None = None


def _log(r: Result) -> None:
    """Append one call's usage to the run log.

    The farm did not write these at first, so the only record of a long run
    was its own console output and `bibleont.spend` -- which reads this
    directory -- could not see the farm at all. A spend tracker blind to the
    thing doing the spending is worse than none, because it reports a
    confident and wrong total.
    """
    global _LOG
    if _LOG is None:
        RUNS.mkdir(parents=True, exist_ok=True)
        _LOG = RUNS / (time.strftime("%Y%m%d-%H%M%S", time.gmtime())
                       + "-farm.jsonl")
    with open(_LOG, "a", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps({"ref": r.ref, "ok": r.ok, "error": r.error,
                             "usage": r.usage, "producer": "farm",
                             "max_tokens": MAX_TOKENS},
                            ensure_ascii=False, sort_keys=True) + "\n")


DELTA_HEAD = """

CREATED EARLIER IN THIS RUN -- these are as real as the vocabulary above.
Reuse these ids verbatim rather than minting a second node for the same thing.

"""


def delta_block(created: dict) -> str:
    """What this run has made since the prefix was built.

    The prefix is built once and the run is 89 windows long, so without this
    the worker is blind to everything it created after window 1 and mints a
    second `image_refuge` in good faith at window 40. That is not a risk, it is
    a certainty, and it is how this graph acquired duplicates six times over.

    **Append-only, and that is the whole trick.** DeepSeek caches on the
    longest identical prefix, so a block that only ever grows at the end keeps
    hitting:

        call N-1   [rules][vocabulary][d1..dN-2][verses]
        call N     [rules][vocabulary][d1..dN-1][verses]
                                      ^ still a prefix match; the cached
                                        region grows with the run

    Rewriting or re-sorting this block would break the cache on every call.
    Insertion order, never touched again.

    Id and name only. The full record costs four times as much and the worker
    does not need a description to avoid re-creating something -- it needs to
    know the name is taken.
    """
    if not created:
        return ""
    lines = [f"  {eid} | {name}" for eid, name in created.items()]
    return DELTA_HEAD + "\n".join(lines) + "\n"


def sound(r: Result, known: set | None = None) -> tuple[float, str]:
    """What fraction of a window's relations could possibly enter the graph.

    A window that returns 200 OK and valid JSON has not necessarily produced
    anything usable. The first Proverbs run came back "ok" three times and
    every composition edge in it was refused by the gate, because the rules
    told the worker to use `composed_of` and the vocabulary had never heard of
    it. Nothing in the loop noticed. Over 89 windows that is five hours and
    $1.79 spent producing a batch that cannot be merged.

    So this asks the cheap half of the gate's question, per window, in
    process: is the relation type real, and do the endpoints exist. It is not
    the gate -- it cannot see whether a citation supports a claim -- but the
    failure it catches is the one that repeats identically for a whole run,
    which is exactly the failure worth stopping for.

    Returns the pass rate and a one-line reason for the commonest failure.
    """
    from .schema import load_vocabulary
    vocab = load_vocabulary()
    rels = r.relations or []
    if not rels:
        return 1.0, ""
    # Everything this window may legally point at: the graph, whatever earlier
    # windows made, and whatever this window declared itself.
    reachable = set(known or ())
    reachable |= {e.get("id") for e in (r.entities or []) if e.get("id")}
    bad: dict[str, int] = {}
    ok = 0
    for rel in rels:
        t = rel.get("type", "")
        if t not in vocab:
            k = f"relation type '{t}' is not in the vocabulary"
            bad[k] = bad.get(k, 0) + 1
            continue
        # Dangling references were not checked here at first and it cost a
        # whole chapter: 31 of 121 relations named concepts the window never
        # declared, every one refused downstream, and it was discovered only
        # after the run finished. The gate is the right place to *refuse* them
        # and the wrong place to *notice* them, because by then it is paid for.
        miss = [x for x in (rel.get("src"), rel.get("dst"))
                if x and reachable and x not in reachable]
        if miss:
            k = f"relations naming ids that do not exist (e.g. '{miss[0]}')"
            bad[k] = bad.get(k, 0) + 1
            continue
        ok += 1
    if not bad:
        return 1.0, ""
    worst = max(bad.items(), key=lambda kv: kv[1])
    return ok / len(rels), f"{worst[1]}x {worst[0]}"


def truncated(r: "Result") -> bool:
    """Did the model run out of room mid-answer?

    Proverbs 10:13-24 came back as malformed JSON with finish_reason=length
    and exactly 32,000 completion tokens -- the ceiling, to the token. Twelve
    antithetical couplets are twelve unrelated decomposition tasks in one call
    and they generate far more than twelve connected verses do.

    Raising the ceiling alone is guessing at a number. A window that will not
    fit should be **cut in half and retried**, which needs no guess and works
    whatever the chapter turns out to be like.
    """
    e = r.error or ""
    return "finish_reason=length" in e or "Expecting" in e and "char 3" in e


def _http_stop(exc: Exception) -> str:
    """Which HTTP failures mean stop rather than retry.

    **An empty Anthropic balance arrives as 400, not 402.** DeepSeek answers
    402 and says "Insufficient Balance", which is what this was written
    against; Anthropic answers `400 invalid_request_error` with "Your credit
    balance is too low to access the Anthropic API" in the BODY, and a bare
    400 is otherwise an ordinary bad-request that should not stop a run.

    So the body has to be read. It cost a night to find out: the supervisor
    failed on every Exodus window with "supervisor unavailable: HTTPError",
    which was caught, reported as a generic failure, and carried on -- so a
    run continued for hours with no supervision at all and nothing said why.
    """
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in STOP_HTTP:
            return STOP_HTTP[exc.code]
        if exc.code == 400:
            try:
                body = exc.read().decode("utf-8", "replace")
            except Exception:                                # noqa: BLE001
                body = ""
            if "credit balance" in body.lower() or "billing" in body.lower():
                return ("the account is out of credit (400, in the body: "
                        f"{body[:120]})")
    text = str(exc)
    for code, why in STOP_HTTP.items():
        if f"HTTP Error {code}" in text or f"{code}:" in text:
            return why
    if "Insufficient Balance" in text or "insufficient" in text.lower():
        return STOP_HTTP[402]
    if "credit balance" in text.lower():
        return "the account is out of credit"
    return ""


def _claim(book: str) -> "object | None":
    """One run per book at a time. Returns the lock, or None if held.

    Two runs on one book silently destroy each other's bookkeeping. Both load
    `done` at startup and both write their own view of it, so every window the
    other finished disappears from the record -- observed on 2026-08-30, where
    Genesis went from four completed windows to three while running.

    **The extraction survived and only the accounting was lost**, because the
    journal is written before the state and a later run adopts an unfinished
    one. That is the durability fix doing its job. It is not a reason to allow
    the collision: a corrupted `done` map makes windows be re-run at full
    price, or skipped entirely if the clobbering goes the other way.

    Parallel farming is still fine and still the recommended way to use the
    budget -- one process per BOOK, which is what the lock enforces. Each book
    has its own state, its own journal and its own prefix, so there is nothing
    to contend over between them.

    Deliberately not `fcntl` or `msvcrt`: this has to behave the same on the
    laptop and the server, and a stale lock must be recoverable by deleting a
    visible file rather than by knowing an incantation.
    """
    import os

    path = STATE_DIR / f"{book.lower()}.lock"
    try:
        fh = open(path, "x", encoding="utf-8")
    except FileExistsError:
        try:
            held = path.read_text(encoding="utf-8").strip()
        except OSError:
            held = "unknown"
        print(f"another run already has {book}: {held}")
        print(f"if that process is gone, delete the lock and retry:")
        print(f"  {path.relative_to(ROOT)}")
        return None
    fh.write(f"pid {os.getpid()} since "
             f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
    fh.close()
    return path


def run(book: str, budget: float, size: int = 12, limit: int = 0,
        dry: bool = False, only: set | None = None,
        supervise: bool = True, opus_budget: float | None = None) -> int:
    lock = None if dry else _claim(book)
    if lock is None and not dry:
        return 1
    try:
        return _run(book, budget, size, limit, dry, only, supervise,
                    opus_budget)
    finally:
        if lock is not None:
            try:
                lock.unlink()
            except OSError:
                pass


def _run(book: str, budget: float, size: int = 12, limit: int = 0,
         dry: bool = False, only: set | None = None,
         supervise: bool = True, opus_budget: float | None = None) -> int:
    state = State.load(book)
    pre = build_prefix(book)

    # One per run. Knows this book's ceiling and what is left of the whole
    # grant, and refuses on either -- see `governor.py` for why two.
    from .governor import DEFAULT_PER_RUN, from_ledger

    gov = from_ledger(DEFAULT_PER_RUN if opus_budget is None else opus_budget)

    # Named before the first call, because the journal has to exist before
    # anything is worth losing. A run that dies leaves its journal behind;
    # the next run adopts it, so windows already marked done still reach a
    # batch instead of vanishing.
    run_name = f"{book.lower()}-farm-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}"
    adopted: list[Result] = []
    for old_journal in orphans(book):
        rows = replay(old_journal.stem)
        if rows:
            adopted.extend(rows)
            print(f"  adopting {len(rows)} window(s) from an unfinished run "
                  f"({old_journal.name})", flush=True)

    todo = []
    for ch in chapters_of(book):
        if only and ch not in only:
            continue
        for refs in windows(book, ch, size):
            key = f"{refs[0]}-{refs[-1].rsplit(':', 1)[1]}"
            if key not in state.done:
                todo.append((key, refs))

    already = len(state.done)
    print(f"{book}: {len(todo)} window(s) to do, {already} already done, "
          f"${state.spent:.4f} spent so far")
    print(f"prefix {pre.tokens:,} tokens, {pre.mode} mode, "
          f"max_tokens {MAX_TOKENS}, budget ${budget:.2f}", flush=True)
    if limit:
        todo = todo[:limit]
        print(f"limited to {len(todo)} window(s) this run")
    if dry:
        for key, refs in todo[:5]:
            print(f"  would do {key}  ({len(refs)} verses)")
        print(f"  ... {len(todo)} total")
        return 0
    if not todo:
        print("nothing to do. Delete the state file to start over:")
        print(f"  {state.path.relative_to(ROOT)}")
        return 0

    # Every id already in the graph, so the soundness check can tell a
    # reference to something real from a reference to nothing at all.
    from .schema import load_entities
    graph_ids = set(load_entities())

    results: list[Result] = []
    consecutive = 0
    clean_streak = 0
    unusable = 0
    stopped = ""
    last_pacing = ""

    queue = list(todo)
    split_again: set = set()
    while queue:
        key, refs = queue.pop(0)
        # Stop BEFORE a call that could cross the line, using the worst case
        # rather than the average -- the ceiling is the promise, not a target.
        worst = MAX_TOKENS * 0.66 / 1e6 + pre.tokens * 0.22 / 1e6
        if state.spent + worst > budget:
            stopped = (f"budget: ${state.spent:.4f} spent, one more window "
                       f"could reach ${state.spent + worst:.4f}, "
                       f"ceiling ${budget:.2f}")
            break

        # THE WORKER IS ON THE WORKER'S PROVIDER, CHECKED EVERY WINDOW.
        #
        # Cheap, and it is the guard that was missing. The supervisor's
        # provider switch leaked and eighteen windows ran on Opus at $14.55
        # against $0.34 -- forty-three times -- while every ledger read $0.00
        # because the usage came back in a shape the pricer did not know.
        #
        # Asked BEFORE the call, because after it the money is gone. A run
        # that cannot confirm which provider it is about to pay stops.
        want = os.environ.get("BIBLEONT_WORKER_PROVIDER", "deepseek")
        actual = os.environ.get("BIBLEONT_PROVIDER", "deepseek").strip().lower()
        if actual != want:
            stopped = (f"the worker is pointed at {actual!r}, not {want!r}. "
                       f"Refusing to spend: this is how $14.55 of DeepSeek "
                       f"work was bought from Opus.")
            break

        try:
            r = run_span(refs, pre.text + state.coaching
                         + delta_block(state.created))
        except Exception as exc:                    # noqa: BLE001
            why = _http_stop(exc)
            if why:
                stopped = why
                break
            r = Result(ref=key, ok=False,
                       error=f"{type(exc).__name__}: {exc}")

        state.spent += cost([r.usage]) if r.usage else 0.0
        _log(r)   # every call, so `bibleont.spend` sees farm work too

        # Too big to answer: halve it and put both halves back at the front.
        # Once only -- a window that truncates at three verses is not a size
        # problem and re-splitting it forever would be a loop.
        if not r.ok and truncated(r) and len(refs) > 2 and key not in split_again:
            mid = len(refs) // 2
            for half in (refs[mid:], refs[:mid]):
                hk = f"{half[0]}-{half[-1].rsplit(':', 1)[1]}"
                split_again.add(hk)
                queue.insert(0, (hk, half))
            print(f"  SPLIT {key:16} ran out of room at {len(refs)} verses; "
                  f"retrying as {mid} + {len(refs) - mid}", flush=True)
            continue

        results.append(r)

        rate, why = (sound(r, graph_ids | set(state.created))
                     if r.ok else (1.0, ""))
        if r.ok and rate < 0.5:
            # Answered, parsed, and useless. Counted as a failure so that the
            # three-in-a-row rule stops a run whose every window is being
            # refused downstream -- the composed_of case, which cost three
            # windows before a person happened to look.
            unusable += 1
            print(f"  WEAK {key:16} only {rate:.0%} of {len(r.relations)} "
                  f"relations can enter: {why}", flush=True)
            if unusable >= 2:
                stopped = (f"two windows in a row produced relations the "
                           f"vocabulary refuses ({why}). The prompt and the "
                           f"schema disagree; fix that before spending more.")
                results.append(r)
                state.spent += cost([r.usage]) if r.usage else 0.0
                _log(r)
                break
        elif r.ok:
            unusable = 0

        if r.ok:
            consecutive = 0
            # ON DISK BEFORE IT IS CALLED DONE. This ordering is the whole
            # fix: `done` is what makes a window be skipped on resume, so
            # marking it before the output is durable is what let a crash
            # discard finished work with nothing to show it had.
            journal(run_name, r)
            state.coaching = _lint_feedback(r)

            # The supervisor, where it is armed and the schedule calls for it.
            #
            # Deliberately AFTER the window is journalled and marked done, so
            # a review that fails, hangs or costs more than expected can never
            # cost extracted work. The reviewer is an observer of the record,
            # not a gate in front of it.
            # Quality wants a rate; money allows one; the wider wins.
            want = _review_interval(len(state.done) + 1, clean_streak)
            paced, why = gov.pace(want, len(queue) + 1) if gov else (want, "")
            if why and why != last_pacing:
                print(f"  supervisor: {why}", flush=True)
                last_pacing = why
            due = paced and (len(state.done) + 1) % paced == 0
            if supervise and paced and (due or len(state.done) < 3):
                v, coach = _supervise(book, key, state, state.spent, gov)
                if v == "sound":
                    clean_streak += 1
                elif v in ("concern", "stop"):
                    clean_streak = 0
                    if coach.strip():
                        # Replaces the linter's note rather than joining it.
                        # Two corrections at once is a wall of text the worker
                        # skims; the supervisor's is the more considered one.
                        state.coaching = (
                            "\n\nA REVIEW OF THIS RUN FOUND THIS:\n"
                            + coach + "\n\nApply it from here on.\n")
                    if v == "stop":
                        stopped = "the supervisor stopped the run"
                        state.save()
                        break
            for e in r.new_entities:
                if e.get("id") and e["id"] not in state.created:
                    state.created[e["id"]] = e.get("name", e["id"])
            state.done[key] = {
                "entities": len(r.new_entities), "relations": len(r.relations),
                "questions": len(r.questions),
                "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            print(f"  ok   {key:16} {len(r.new_entities):>3} new  "
                  f"{len(r.relations):>3} rel  {len(r.questions):>2} q   "
                  f"${state.spent:.4f}   {time.strftime('%H:%M:%S')}",
                  flush=True)
        else:
            consecutive += 1
            why = _http_stop(Exception(r.error))
            print(f"  FAIL {key:16} {r.error[:110]}", flush=True)
            if why:
                stopped = why
                break
            if consecutive >= 3:
                stopped = "three windows failed in a row"
                break

        state.save()          # after every window, not at the end

    state.save()

    # Adopted windows are indistinguishable from this run's own by the time
    # they get here, which is the point: whoever extracted them, they are
    # output that has not reached a batch yet.
    ok = [r for r in adopted + results if r.ok]
    if ok:
        name = run_name
        d = write_batch(name, ok, book)
        grouped = collapse([q for r in ok for q in r.questions])
        print()
        print(f"wrote {d.relative_to(ROOT)}")
        print(f"  {sum(len(r.new_entities) for r in ok)} new entities, "
              f"{sum(len(r.relations) for r in ok)} relations")
        print(f"  {sum(len(r.questions) for r in ok)} questions collapse to "
              f"{len(grouped)} distinct")
        print(f"  next: python -m bibleont.proposals check {name}")

        # Retired only now, and only on the success path. A journal is
        # cheap; losing one whose windows are marked done is not, so the
        # rule is that nothing is deleted until its contents are in a batch
        # on disk. Renamed rather than removed, so a bad batch can still be
        # rebuilt from what produced it.
        # Every journal for this book, this run's included: all of them were
        # folded into the batch above.
        for spent_journal in orphans(book):
            done_name = spent_journal.with_suffix(".jsonl.written")
            # `Path.rename` is not atomic-overwrite on Windows: it raises
            # FileExistsError rather than replacing, and crashed two runs at
            # the very last step -- after the batch was safely written, which
            # is the one place an exception is least welcome and most alarming.
            #
            # A `.written` of the same name already existing means the journal
            # was retired before and a later run re-created the name, so the
            # newer content is the one to keep. `replace` overwrites, and the
            # whole loop is guarded because a bookkeeping failure must never
            # discard a batch that is already on disk.
            try:
                spent_journal.replace(done_name)
            except OSError as exc:                               # noqa: BLE001
                print(f"  (could not retire {spent_journal.name}: {exc})")

    print()
    # This run's own windows. `ok` also carries adopted ones, which belong in
    # the batch but not in "how far did tonight get" -- counting them gave
    # "2/1 of Obad complete".
    done_now = len([r for r in results if r.ok])
    if stopped:
        print(f"STOPPED -- {stopped}")
    print(f"{done_now} window(s) this run, "
          f"{len(state.done)}/{len(state.done) + len(todo) - done_now} "
          f"of {book} complete, ${state.spent:.4f} spent in total")
    if stopped or todo[done_now:]:
        print(f"resume with the same command; finished windows are skipped:")
        print(f"  python -m bibleont.farm {book} --budget={budget}")
    if gov is not None and gov.calls:
        print(f"  {gov.summary()}")
    return 0


def health(book: str, last: int = 12) -> list[str]:
    """The signals that say a run is going wrong while it looks fine.

    The question was whether a run should stream to Claude or sit in a
    terminal with a channel back. The channel already exists -- every window is
    journalled -- and what was missing is something cheap to READ. Streaming
    every window costs context and hides the four things that actually matter,
    each of which was invisible on the night they cost money:

        the provider      eighteen windows ran on Opus and nothing said so
        cost moving       the column froze at $0.0351 and stayed there
        supervision       "unavailable: HTTPError" 119 times, meaning no credit
        escalations       raised for a person, and easy to scroll past

    Read-only and safe from another terminal while a run is working.
    """
    out: list[str] = []
    runs = sorted((ROOT / "ontology" / "proposals" / ".runs").glob("*farm*.jsonl"))
    rows = []
    for f in runs[-4:]:
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if str(d.get("ref", "")).startswith(book):
                rows.append(d)
    rows = rows[-last:]
    if not rows:
        return ["no calls journalled for this book yet"]

    shapes = set()
    for d in rows:
        u = d.get("usage") or {}
        if "cache_read_input_tokens" in u:
            shapes.add("anthropic")
        elif "prompt_cache_hit_tokens" in u or "completion_tokens" in u:
            shapes.add("deepseek")
    want = os.environ.get("BIBLEONT_WORKER_PROVIDER", "deepseek")
    if shapes and shapes != {want}:
        out.append(f"PROVIDER: the last {len(rows)} calls look like "
                   f"{'/'.join(sorted(shapes))}, expected {want}. This is the "
                   f"shape of the $14.55 misroute.")
    else:
        out.append(f"provider: last {len(rows)} calls are {want}, as expected")

    priced = []
    for d in rows:
        u = d.get("usage") or {}
        try:
            priced.append(cost([u]) if u else 0.0)
        except Exception:                                    # noqa: BLE001
            priced.append(None)
    if any(c is None for c in priced):
        out.append("COST: some calls returned usage this build cannot price -- "
                   "refused rather than counted as free")
    elif priced and sum(c for c in priced if c) == 0:
        out.append(f"COST: {len(rows)} calls priced at exactly $0.00. A cost "
                   f"that does not move is the first sign of a misroute.")
    else:
        out.append(f"cost: ${sum(c for c in priced if c):.4f} over the last "
                   f"{len(rows)} call(s), moving")

    try:
        led = json.loads((ROOT / "ontology" / "proposals" / ".supervisor"
                          / "ledger.json").read_text(encoding="utf-8"))
        mine = [r for r in led.get("runs", [])
                if str(r.get("book", "")).startswith(book)]
        left = led.get("granted", 0) - led.get("spent", 0)
        if mine:
            verdicts = ", ".join(f"{r.get('book')}={r.get('note')}"
                                 for r in mine[-4:])
            out.append(f"supervisor: {len(mine)} review(s) -- {verdicts}")
        else:
            out.append(f"SUPERVISOR: no reviews recorded for {book}. If the "
                       f"run is past its third window this is a stand-down.")
        out.append(f"ledger: ${left:.2f} left of ${led.get('granted', 0):.2f}")
        esc = [e for r in mine for e in (r.get("escalations") or []) if e.strip()]
        for e in esc:
            out.append(f"ESCALATED, for a person: {e[:150]}")
    except Exception:                                        # noqa: BLE001
        out.append("supervisor: no ledger readable")
    return out


def status(book: str) -> int:
    """Where an unattended run has got to, read from the state file.

    Safe to run from a second terminal while the first is working, and safe to
    run from a different process entirely -- it only reads. State is written
    after every window, so this is never more than one window stale.

    Exists because a five-hour run in somebody else's terminal is otherwise
    opaque: the console output belongs to whoever started it, and "is it still
    going" should not require interrupting the thing you are asking about.
    """
    state = State.load(book)
    if not state.done:
        print(f"{book}: nothing done yet"
              f"  (no state at {state.path.relative_to(ROOT)})")
        return 0

    total = sum(len(windows(book, ch)) for ch in chapters_of(book))
    done = len(state.done)
    stamps = sorted(v.get("when", "") for v in state.done.values() if v.get("when"))
    ents = sum(v.get("entities", 0) for v in state.done.values())
    rels = sum(v.get("relations", 0) for v in state.done.values())
    qs = sum(v.get("questions", 0) for v in state.done.values())

    print(f"{book}: {done}/{total} windows  ({done / total:.0%})   "
          f"${state.spent:.4f} spent")
    print(f"  {ents:,} entities, {rels:,} relations, {qs} questions so far")
    print(f"  {len(state.created):,} distinct nodes created this run")

    # Which chapters are finished, so that mixing up the order stays legible.
    # The state is keyed by window and a reader wants chapters.
    import collections as _c
    per = _c.Counter()
    for k in state.done:
        per[k.split(":")[0].rsplit(" ", 1)[-1]] += 1
    whole = [ch for ch in per
             if per[ch] == len(windows(book, int(ch)))]
    part = [ch for ch in per if ch not in whole]
    if whole:
        print(f"  complete: {', '.join(sorted(whole, key=int))}")
    if part:
        print(f"  partial:  {', '.join(sorted(part, key=int))}")

    if len(stamps) >= 2:
        from datetime import datetime
        t0 = datetime.fromisoformat(stamps[0].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(stamps[-1].replace("Z", "+00:00"))
        secs = (t1 - t0).total_seconds()
        if secs > 0 and done > 1:
            per = secs / (done - 1)
            left = total - done
            print(f"  {per / 60:.1f} min/window; {left} left "
                  f"-> about {left * per / 3600:.1f}h and "
                  f"${left * state.spent / done:.2f} more")
        print(f"  last window finished {stamps[-1]}")
    print()
    for line in health(book):
        print(f"  {line}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry" in argv
    supervise = "--no-supervisor" not in argv
    opus_budget = None
    budget = None
    size, limit = 12, 0
    only = None
    for a in argv:
        if a.startswith("--budget="):
            budget = float(a.split("=", 1)[1])
        elif a.startswith("--size="):
            size = int(a.split("=", 1)[1])
        elif a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])
        elif a.startswith("--opus-budget="):
            opus_budget = float(a.split("=", 1)[1])
        elif a.startswith("--chapter="):
            only = {int(x) for x in a.split("=", 1)[1].split(",")}
    rest = [a for a in argv if not a.startswith("--")]

    if "--status" in argv and rest:
        return status(rest[0])

    if not rest:
        print("usage: python -m bibleont.farm <Book> --budget=2.00 "
              "[--opus-budget=0.50] [--chapter=N] [--size=12] "
              "[--limit=N] [--dry] [--no-supervisor]")
        print("       python -m bibleont.farm Ps --budget=0.25 --limit=2")
        print()
        print("--budget is required. An unattended run with no ceiling is")
        print("the one thing this module exists to prevent.")
        print()
        print("--budget governs DeepSeek, the worker. --opus-budget")
        print("governs the supervisor and defaults to $0.50 a run.")
        print("They are separate because they failed separately: a")
        print("provider leak once put worker windows on Opus and the")
        print("DeepSeek ceiling priced every one of them at $0.00.")
        return 2
    if budget is None and not dry:
        print("refusing to run without --budget. See --help by running with "
              "no arguments.")
        return 2

    from .providers import current
    prov = current()
    if not dry and not prov.key:
        print(f"{prov.key_env} is not set, and no key is in the keystore.")
        return 1

    return run(rest[0], budget or 0.0, size=size, limit=limit, dry=dry,
               only=only, supervise=supervise, opus_budget=opus_budget)


if __name__ == "__main__":
    raise SystemExit(main())
