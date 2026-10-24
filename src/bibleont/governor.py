"""A ceiling on Opus spending, checked before the call rather than after.

## Why a second budget exists at all

The farm already has `--budget`, and it governs DeepSeek. It did not govern
the supervisor, and on 2026-08-31 that gap cost $6.70 in a single run: the
provider leaked, eight worker windows ran on Opus, and neither ledger saw a
penny of it. The DeepSeek budget could not — it prices DeepSeek's usage shape
and read every Anthropic call as exactly $0.00. The supervisor's ledger
recorded only calls the supervisor knew it had made.

Two budgets that each believe the other is watching are one budget with a
hole in it.

## What this governs, and what it deliberately does not

**It stops supervision, never extraction.** Running out of review money is
not a reason to throw away a night's extraction; it is a reason to stop
reviewing and say so. The DeepSeek ceiling stops the run. This one stops the
watching and lets the work finish, which is the right way round: the windows
are the expensive, unrepeatable thing.

## Two ceilings, because they fail differently

    PER RUN     what this one book may spend on review. Bounds a single
                mistake -- a rubric that says CONCERN on every window, a
                prompt that makes every chapter look broken. Exodus asked for
                a review on all ten of its first windows and would have spent
                ~$3.50 across the book on a back-off that never engaged.

    THE GRANT   what the whole corpus may spend, from the ledger. The aim: a
                given $20 should last for the whole Bible. A per-run
                ceiling alone cannot promise that; twenty runs of fifty cents
                is the grant.

Both are checked against the WORST case before a call, never the average
after it. A ceiling consulted after the fact is a receipt.
"""

from __future__ import annotations

# What one supervisor review can cost if it goes long. Measured: reviews have
# run $0.024 to $0.055, and thinking bills as output, so the tail is the risk
# rather than the mean. Rounded up on purpose -- erring high stops early and
# leaves money unspent, which is recoverable; erring low is how a ceiling gets
# stepped over.
WORST_REVIEW = 0.08

# Default per-run ceiling. About twelve reviews, which covers the early dense
# phase of a book plus a clean run's back-off tail.
DEFAULT_PER_RUN = 0.50


class Governor:
    """Decides whether the next Opus call may be made, and records what it cost.

    Deliberately dumb and synchronous. It holds no opinion about whether a
    review is worth making -- only whether it is affordable -- because mixing
    those two questions is how a budget acquires exceptions.
    """

    def __init__(self, per_run: float = DEFAULT_PER_RUN,
                 grant_left: float | None = None) -> None:
        self.per_run = float(per_run)
        self.grant_left = grant_left
        self.spent = 0.0
        self.calls = 0
        self.stopped = ""

    def may_spend(self, worst: float = WORST_REVIEW) -> tuple[bool, str]:
        """Can the next call be afforded, in the worst case?

        Returns (allowed, reason). The reason is filled in only on a refusal
        and is meant to be printed verbatim: a governor that stops a run
        without saying which ceiling it hit sends someone to read the source.
        """
        if self.stopped:
            return False, self.stopped

        if self.spent + worst > self.per_run:
            self.stopped = (
                f"per-run Opus ceiling: ${self.spent:.4f} spent on review, "
                f"one more could reach ${self.spent + worst:.4f}, "
                f"ceiling ${self.per_run:.2f}")
            return False, self.stopped

        if self.grant_left is not None and worst > self.grant_left - self.spent:
            self.stopped = (
                f"the grant is nearly gone: ${self.grant_left - self.spent:.2f} "
                f"left of the supervisor's credit, and one review could cost "
                f"${worst:.2f}")
            return False, self.stopped

        return True, ""

    def affordable_interval(self, windows_left: int) -> int:
        """How many windows must pass between reviews for the money to last.

        2026-08-31: the supervisor should be aware of its own balance against
        budget and size of job and may adjust accordingly, but if things seem
        off it should shut down unless it is able to adjust on its own.

        A ceiling alone stops the run halfway and calls that safety. Pacing
        spends the same money across the whole book instead, which is what
        the ceiling was for.

        The arithmetic is deliberately plain: what is left, divided by what a
        review can cost, is how many reviews remain affordable. Spread those
        over the windows remaining and the answer is an interval.

        Returns 1 when everything is affordable, which is the early phase and
        the one that matters most -- a fault found in the first ten minutes is
        amortised over the whole run. Returns 0 when not even one more review
        fits, meaning supervision must stand down rather than the run stop:
        the extraction is the expensive, unrepeatable half.
        """
        if windows_left <= 0:
            return 1
        left = self.per_run - self.spent
        if self.grant_left is not None:
            left = min(left, self.grant_left - self.spent)
        affordable = int(left // WORST_REVIEW)
        if affordable <= 0:
            return 0
        if affordable >= windows_left:
            return 1
        return max(1, -(-windows_left // affordable))     # ceil

    def pace(self, wanted_interval: int, windows_left: int) -> tuple[int, str]:
        """Reconcile what quality wants with what the money allows.

        `_should_review` widens the interval as the worker proves itself,
        which is a judgement about quality. This widens it as money runs
        short, which is a different pressure. **The wider of the two wins**,
        because relaxing either constraint to satisfy the other is how a
        budget or a review schedule quietly stops meaning anything.
        """
        afford = self.affordable_interval(windows_left)
        if afford == 0:
            return 0, ("not one more review is affordable; supervision stands "
                       "down and the extraction continues")
        if afford <= wanted_interval:
            return wanted_interval, ""
        return afford, (f"money paces this: {afford} windows between reviews "
                        f"rather than {wanted_interval}, to cover "
                        f"{windows_left} remaining")

    def record(self, cost: float) -> None:
        """What a call actually cost. Called whether or not it succeeded.

        A failed call still burns tokens -- a review that times out after
        thinking for three thousand tokens has spent them -- so this is not
        conditional on a usable answer.
        """
        self.spent += max(0.0, float(cost))
        self.calls += 1

    def summary(self) -> str:
        line = (f"supervisor spent ${self.spent:.4f} over {self.calls} "
                f"review(s), ceiling ${self.per_run:.2f}")
        return line + (f" -- STOPPED: {self.stopped}" if self.stopped else "")


def from_ledger(per_run: float = DEFAULT_PER_RUN) -> Governor:
    """A governor that also knows what is left of the whole grant."""
    try:
        from .supervisor import position
        left = float(position().get("left") or 0.0)
    except Exception:                                        # noqa: BLE001
        left = None
    return Governor(per_run=per_run, grant_left=left)
