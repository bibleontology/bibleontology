"""The farm's loop body actually runs.

Written after `supervise` was read inside `_run` while being defined only in
`main`, so every farm command died with a NameError on its first window --
Genesis, Job and Mark, all three the same way. The runs already in flight were
unaffected only because they had been started from a module that predated the
bug, which is what hid it for several hours.

**`--dry` did not catch it and could not.** Dry mode lists the windows it
would do and exits before the loop body, so it exercises setup, window
selection and the budget arithmetic, and none of the code that touches a
result. It returned 0 on the broken module. A smoke test that passes on code
which cannot run a single window is worse than none, because it was consulted
and believed.

The unit test for `_should_review` passed too, for the same reason: it checked
the helper's arithmetic. What broke was whether anything ever called it.

So this stubs the network seam and runs the real loop. It is the cheapest
thing that would have failed.

    python tests/test_farm_loop.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bibleont import farm                                        # noqa: E402

FAILED: list = []


def check(name: str, cond: bool, why: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}" + (f" -- {why}" if not cond and why else ""))
    if not cond:
        FAILED.append(name)


class _Prefix:
    text = "PREFIX"
    tokens = 100
    mode = "concept"


def _stub(tmp: Path):
    """The real loop with the network, the disk and the reviewer removed.

    Returns (originals, calls) -- `calls` collects every ref the supervisor
    was asked about, which is how the armed/disarmed pair below tells the
    difference between a flag that arrives and one that is merely parsed.
    """
    calls: list = []

    def fake_span(refs, prompt):
        # `new_entities` is a read-only property derived from `entities`, so
        # the fake supplies the field rather than the view.
        return farm.Result(ref=str(refs[0]), ok=True, entities=[], relations=[],
                           questions=[], usage={})

    def fake_supervise(book, ref, state, spent, gov=None):
        calls.append(ref)
        # The loop must hand the governor down, or the ceiling governs
        # nothing. Recorded so the assertion below can see it arrived.
        calls.append(("gov", gov is not None))
        return "sound", ""

    subs = {
        "STATE_DIR": tmp,
        "journal": lambda *a, **k: None,
        "_log": lambda *a, **k: None,
        "_lint_feedback": lambda r: "",
        # Otherwise an empty window reads as "answered and useless" and the
        # run stops after two, before it ever reaches the supervisor branch.
        "sound": lambda *a, **k: (1.0, ""),
        "build_prefix": lambda book: _Prefix(),
        "run_span": fake_span,
        "_supervise": fake_supervise,
    }
    originals = {k: getattr(farm, k) for k in subs}
    for k, v in subs.items():
        setattr(farm, k, v)
    # AND THE BATCH. `write_batch` writes through decompose's own PROPOSALS
    # and QUESTIONS, which nothing above reached: every run of this test left
    # three 3 John 1:1 proposals ($0) and their question files in
    # ontology/proposals -- 48 of them by 2026-10-02, each one an
    # "uncommitted change" in preflight. Into the temp dir with the rest.
    from bibleont import decompose
    originals["__decompose__"] = (decompose.PROPOSALS, decompose.QUESTIONS)
    # AND THE MONEY. The governor read the real spending ledger, so whether
    # the armed supervisor was "reached" depended on what was left of the
    # owner's grant -- and a public clone, with no ledger, could afford no
    # review at all (the code review, 2026-10-22). A governor with no grant
    # limit, so the loop's wiring is what is tested
    from bibleont import governor
    originals["__governor__"] = governor.from_ledger
    governor.from_ledger = lambda per_run=governor.DEFAULT_PER_RUN: governor.Governor(per_run=per_run,
                                                                                    grant_left=None)
    decompose.PROPOSALS = tmp / "proposals"
    decompose.QUESTIONS = decompose.PROPOSALS / ".questions"
    return originals, calls


def _restore(originals: dict) -> None:
    from bibleont import decompose
    for k, v in originals.items():
        if k == "__decompose__":
            decompose.PROPOSALS, decompose.QUESTIONS = v
        elif k == "__governor__":
            from bibleont import governor
            governor.from_ledger = v
        else:
            setattr(farm, k, v)


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    print()

    # Inside the repo on purpose: the run summary prints
    # `state.path.relative_to(ROOT)`, which raises for a state dir anywhere
    # else. Cleaned up either way.
    with tempfile.TemporaryDirectory(dir=farm.ROOT) as td:
        originals, calls = _stub(Path(td))
        try:
            # The NameError itself: the loop body must be able to run at all.
            rc = farm._run("3John", budget=1.0, limit=1)
            check("a window completes", rc == 0, f"returned {rc}")

            # Deletes detectably: with the flag not threaded through this
            # raises NameError; with it threaded but never consulted, `calls`
            # stays empty and this still fails.
            calls.clear()
            farm._run("3John", budget=1.0, limit=1, supervise=True)
            check("armed supervisor is reached", bool(calls),
                  "armed and never called")
            check("the governor reaches the supervisor",
                  ("gov", True) in calls,
                  "loop did not pass a governor")

            # And the other direction, or the flag is decoration.
            calls.clear()
            farm._run("3John", budget=1.0, limit=1, supervise=False)
            check("disarmed supervisor is skipped", not calls,
                  "ran with supervise=False")
        finally:
            _restore(originals)

    # The gap that produced the outage was between PARSING the flag and USING
    # it, so parsing is not what this checks. Arrival is.
    from bibleont import providers

    seen: dict = {}
    # `main` does `from .providers import current` at call time, so the patch
    # has to land on the providers module, not on farm.
    real_run, real_cur = farm.run, providers.current
    try:
        farm.run = lambda book, budget, **kw: (seen.update(kw), 0)[1]
        providers.current = lambda: type("P", (), {"key": "x", "key_env": "K"})()
        farm.main(["3John", "--budget=1.00"])
        check("main defaults to armed", seen.get("supervise") is True,
              f"got {seen.get('supervise')!r}")
        seen.clear()
        farm.main(["3John", "--budget=1.00", "--no-supervisor"])
        check("--no-supervisor arrives", seen.get("supervise") is False,
              f"got {seen.get('supervise')!r}")
    finally:
        farm.run, providers.current = real_run, real_cur

    # State.save is the only record of which windows are done -- 145 of them
    # for Genesis, at $2.73. Job died writing it with Errno 22 on a Store
    # Python, which is what prompted these.
    with tempfile.TemporaryDirectory(dir=farm.ROOT) as td:
        real_dir = farm.STATE_DIR
        farm.STATE_DIR = Path(td)
        try:
            s = farm.State(book="Job", done={f"w{i}": {} for i in range(107)})
            s.save()
            check("state round-trips", len(farm.State.load("Job").done) == 107)

            # A transient failure must leave the previous file untouched, not
            # a truncated one. Fails if `save` ever goes back to writing in
            # place, because the old content would already be gone.
            real_replace = os.replace
            tries = {"n": 0}

            def flaky(src, dst):
                tries["n"] += 1
                if tries["n"] < 3:
                    raise OSError(22, "Invalid argument")
                return real_replace(src, dst)

            os.replace = flaky
            try:
                s.done["w107"] = {}
                s.save()
            finally:
                os.replace = real_replace
            check("retries a transient write failure", tries["n"] == 3,
                  f"gave up after {tries['n']}")
            check("and the retry landed", len(farm.State.load("Job").done) == 108)

            # Permanent failure: old state survives and the error says so.
            os.replace = lambda src, dst: (_ for _ in ()).throw(
                OSError(22, "Invalid argument"))
            try:
                s.done["w108"] = {}
                s.save()
                check("permanent failure raises", False, "it did not")
            except OSError as exc:
                # It must not claim a count for what is ON DISK -- `done` is
                # the in-memory map and includes the change that failed.
                msg = str(exc)
                check("permanent failure says the file is untouched",
                      "was NOT modified" in msg and "unrecorded" in msg,
                      msg[:90])
            finally:
                os.replace = real_replace
            check("old state intact after permanent failure",
                  len(farm.State.load("Job").done) == 108)
            check("no temp files left behind",
                  not list(Path(td).glob("*.tmp*")))
        finally:
            farm.STATE_DIR = real_dir

    # The provider must come back after a review. This leaked once and cost
    # $6.70: `current()` reads the env var per call, so setting it for the
    # supervisor redirected the WORKER too, permanently, from the first
    # review onward.
    import os as _os
    from bibleont.decompose import cost as _cost, UnpriceableUsage

    before = _os.environ.get("BIBLEONT_PROVIDER")
    with farm._provider("anthropic"):
        check("provider switches inside the block",
              _os.environ["BIBLEONT_PROVIDER"] == "anthropic")
    check("provider is restored after the block",
          _os.environ.get("BIBLEONT_PROVIDER") == before,
          f"left as {_os.environ.get('BIBLEONT_PROVIDER')!r}")

    try:
        with farm._provider("anthropic"):
            raise RuntimeError("review blew up")
    except RuntimeError:
        pass
    check("provider is restored even when the review raises",
          _os.environ.get("BIBLEONT_PROVIDER") == before)

    # And the second line of defence: a usage shape the pricer does not know
    # must never score as free. Zero is indistinguishable from thrift, which
    # is why the budget ceiling counted correctly to nothing and never fired.
    try:
        _cost([{"cache_read_input_tokens": 50000, "output_tokens": 2000}])
        check("foreign usage is refused, not priced at zero", False,
              "it returned a number")
    except UnpriceableUsage:
        check("foreign usage is refused, not priced at zero", True)
    check("deepseek usage still prices",
          _cost([{"prompt_cache_miss_tokens": 50000,
                  "completion_tokens": 3000}]) > 0)

    # The Opus governor. Asked before the call and against the worst case,
    # because a ceiling consulted afterwards is a receipt.
    from bibleont.governor import Governor, WORST_REVIEW

    g = Governor(per_run=0.20, grant_left=100.0)
    check("a fresh governor allows a call", g.may_spend()[0])
    for _ in range(2):
        g.record(0.05)
    check("still allows while under the ceiling", g.may_spend()[0],
          f"spent {g.spent}")
    g.record(0.06)                       # 0.16 spent, +0.08 worst > 0.20
    ok, why = g.may_spend()
    check("refuses when the worst case would cross", not ok)
    check("and names which ceiling", "per-run" in why, why[:60])
    check("refusal is sticky", not g.may_spend()[0])

    # The grant is the other ceiling and fails differently.
    g2 = Governor(per_run=10.0, grant_left=WORST_REVIEW / 2)
    ok, why = g2.may_spend()
    check("refuses when the grant cannot cover one call", not ok)
    check("and says it is the grant", "grant" in why, why[:60])

    # A failed call still burns tokens, so cost is recorded regardless.
    g3 = Governor(per_run=1.0)
    g3.record(0.03)
    check("records cost with no grant configured", g3.spent == 0.03)
    check("no grant means no grant ceiling", g3.may_spend()[0])

    # The worker-provider guard. It refuses to spend when the process is
    # pointed somewhere other than the worker's provider, which is the exact
    # state the leak left behind.
    with tempfile.TemporaryDirectory(dir=farm.ROOT) as td:
        originals, calls = _stub(Path(td))
        try:
            was = os.environ.get("BIBLEONT_PROVIDER")
            os.environ["BIBLEONT_PROVIDER"] = "anthropic"
            try:
                rc = farm._run("3John", budget=1.0, limit=1)
                st = farm.State.load("3John")
                check("refuses to run the worker on the wrong provider",
                      len(st.done) == 0,
                      f"it did {len(st.done)} window(s) anyway")
            finally:
                if was is None:
                    os.environ.pop("BIBLEONT_PROVIDER", None)
                else:
                    os.environ["BIBLEONT_PROVIDER"] = was
            rc = farm._run("3John", budget=1.0, limit=1)
            check("and runs normally when it is right",
                  len(farm.State.load("3John").done) == 1)
        finally:
            _restore(originals)

    print()
    if FAILED:
        print(f"  {len(FAILED)} failed: {', '.join(FAILED)}")
        return 1
    print("  all passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
