"""Scoring the standing reviewer against cases whose answers are known.

The reviewer described in `docs/REVIEWER.md` is pass one: a cheap model asking
a fixed list of questions about every relation, before a person looks. This
module is how we find out whether it is any good, and keep finding out.

## Why per-rule scoring rather than one number

The obvious comparison is SonarQube, and it holds for the shape -- a fixed
rule set, applied to everything, growing as new defect classes are found. It
breaks in one place, and the break is the reason this module exists.

SonarQube's rules are deterministic. A pattern either matches an AST or it
does not, so a rule that fires is right by construction and the only question
is whether the rule was worth writing. Three of our checks require reading:
whether a quote is evidence or illustration, whether a note asserts intent,
whether a claim holds in every cited verse. Those have a false-positive rate,
and a rule that fires on sound relations is worse than no rule -- it trains
the reader to skim, which is the failure the reviewer exists to prevent.

So each check is scored on its own, both ways:

- **recall** -- of the known-bad cases this check should catch, how many did it
- **precision** -- of the cases it flagged, how many deserved flagging

A check with high recall and low precision is noisy and should be narrowed or
retired. A check with high precision and low recall is worth keeping and
worth improving. One number hides both.

## The answer key

`ontology/proposals/.eval/cases.jsonl`, and every case in it is a failure this
project actually had -- the four relations quoting "God is no respecter of
persons" to evidence claims it does not evidence, the note quoting Gal 4:6
while citing Rom 8:15, the quotation marks around a compression of Mark 12:30.

Nothing in it is invented, deliberately. A reviewer scored against imagined
failures learns to catch imagined failures.

The set grows the same way: when a real defect gets past the reviewer and is
caught by a person, it is added, and every later version of the reviewer is
measured against it. That is the ratchet.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from bibleont.paths import ROOT

EVAL = ROOT / "ontology" / "proposals" / ".eval" / "cases.jsonl"


def load_cases(path: Path | None = None) -> list[dict]:
    path = EVAL if path is None else path
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def as_prompt(case: dict) -> str:
    """One case, rendered as it should be put to a reviewer.

    The verses are included in full. A reviewer asked to judge whether a quote
    supports a claim, without the verse in front of it, is being asked to
    recall rather than to read -- which is the one thing it is worst at.
    """
    lines = [
        f'RELATION   {case["src_name"]} --{case["type"]}--> {case["dst_name"]}',
        f'CERTAINTY  {case["certainty"]}',
        f'CITES      {", ".join(case["refs"])}',
        "",
        "NOTE",
        f'  {case["note"]}',
        "",
        "THE CITED VERSES IN FULL",
    ]
    for ref, text in case["verses"].items():
        lines.append(f"  {ref:14} {text}")
    return "\n".join(lines)


def score(verdicts: list[dict], cases: list[dict] | None = None) -> dict:
    """Compare a reviewer's answers to the key.

    A verdict is {"id": ..., "verdict": "bad"|"good"|"unsure", "check": int,
    "quote": str}. `unsure` counts as not flagged, which is the conservative
    reading: an unsure verdict does not stop anything.
    """
    cases = load_cases() if cases is None else cases
    key = {c["id"]: c for c in cases}
    given = {v["id"]: v for v in verdicts}

    per = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    unquoted = []
    missing = []
    overall = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}

    for cid, c in key.items():
        v = given.get(cid)
        if v is None:
            missing.append(cid)
            continue
        flagged = v.get("verdict") == "bad"
        should = c["expected"] == "bad"

        if flagged and not str(v.get("quote", "")).strip():
            unquoted.append(cid)

        if should and flagged:
            overall["tp"] += 1
            per[c["check"]]["tp"] += 1
            if v.get("check") and v["check"] != c["check"]:
                per[c["check"]]["tp"] -= 1
                per[c["check"]]["fn"] += 1
                per[v["check"]]["fp"] += 1
        elif should and not flagged:
            overall["fn"] += 1
            per[c["check"]]["fn"] += 1
        elif not should and flagged:
            overall["fp"] += 1
            per[v.get("check", 0)]["fp"] += 1
        else:
            overall["tn"] += 1

    def rate(n, d):
        return None if d == 0 else round(100.0 * n / d, 1)

    return {
        "overall": {
            **overall,
            "recall": rate(overall["tp"], overall["tp"] + overall["fn"]),
            "precision": rate(overall["tp"], overall["tp"] + overall["fp"]),
        },
        "per_check": {
            k: {**s,
                "recall": rate(s["tp"], s["tp"] + s["fn"]),
                "precision": rate(s["tp"], s["tp"] + s["fp"])}
            for k, s in sorted(per.items())
        },
        "unquoted_flags": unquoted,
        "missing": missing,
        "cases": len(key),
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "cases"

    cases = load_cases()
    if not cases:
        print(f"no answer key at {EVAL}")
        return 1

    if cmd == "cases":
        bad = sum(1 for c in cases if c["expected"] == "bad")
        print(f"{len(cases)} cases, {bad} known-bad, {len(cases)-bad} known-good\n")
        for c in cases:
            mark = "BAD " if c["expected"] == "bad" else "good"
            print(f'  {mark} check {c["check"]}  {c["id"]}')
            print(f'          {c["why"][:104]}')
        return 0

    if cmd == "prompt":
        for c in cases:
            print("=" * 72)
            print(as_prompt(c))
            print()
        return 0

    if cmd == "diagnose":
        # Judging the reviewer rather than its verdicts. These are the numbers
        # that say whether it is reading, whether it is being served by the
        # model we asked for, and what it costs -- none of which the score can
        # show, because a fabricating reviewer and a careful one can reach the
        # same recall by different routes.
        if len(argv) < 2:
            print("usage: diagnose <run-log.jsonl>")
            return 2
        rows = [json.loads(l) for l in
                Path(argv[1]).read_text(encoding="utf-8").splitlines() if l.strip()]
        n = len(rows)
        errs = [r for r in rows if r.get("error")]
        ok = [r for r in rows if not r.get("error")]

        fabricated = [r for r in ok if r.get("quote_is_real") is False]
        unquoted = [r for r in ok if r.get("quote_is_real") is None]
        unsure = [r for r in ok if r.get("verdict") == "unsure"]
        truncated = [r for r in ok if r.get("finish_reason") not in (None, "stop")]
        models = {r.get("model_returned") for r in ok if r.get("model_returned")}

        lat = sorted(r["latency_s"] for r in ok if r.get("latency_s") is not None)
        tok_in = sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in ok)
        tok_out = sum((r.get("usage") or {}).get("completion_tokens", 0) for r in ok)

        print(f"{n} calls, {len(errs)} failed\n")
        print("  reading, or not")
        print(f"    quote not in the material shown  {len(fabricated):3}"
              f"   <- fabrication; discard the verdict")
        print(f"    no quote given                   {len(unquoted):3}"
              f"   <- guessing; the verdict is unusable")
        print(f"    answered unsure                  {len(unsure):3}")
        print("\n  the service")
        print(f"    model returned                   "
              f"{', '.join(sorted(models)) if models else 'unreported'}")
        print(f"    replies cut short                {len(truncated):3}")
        if lat:
            print(f"    latency  min {lat[0]:.2f}s   median {lat[len(lat)//2]:.2f}s"
                  f"   max {lat[-1]:.2f}s")
        print(f"    tokens   {tok_in} in, {tok_out} out")
        if errs:
            print("\n  failures")
            for r in errs[:6]:
                print(f"    {r['id'][:44]:46} {str(r.get('error'))[:60]}")

        # Where the verdicts and the key disagree, and under which check --
        # this is what says whether a rule is broken or the reviewer is.
        wrong = [r for r in ok
                 if r.get("expected") and
                 ((r["verdict"] == "bad") != (r["expected"] == "bad"))]
        if wrong:
            print(f"\n  {len(wrong)} disagreement(s) with the key")
            for r in wrong:
                print(f"    {r['id'][:40]:42} said {r['verdict']:6} "
                      f"check {str(r.get('check')):4} expected {r['expected']}")
                print(f"      why: {str(r.get('why'))[:88]}")
        if fabricated:
            print("\n  fabricated quotes in full")
            for r in fabricated:
                print(f"    {r['id'][:44]}")
                print(f'      "{str(r.get("quote"))[:96]}"')
        return 0

    if cmd == "score":
        if len(argv) < 2:
            print("usage: score <verdicts.jsonl>")
            return 2
        verdicts = [json.loads(l) for l in
                    Path(argv[1]).read_text(encoding="utf-8").splitlines() if l.strip()]
        r = score(verdicts, cases)
        o = r["overall"]
        print(f'answered {r["cases"] - len(r["missing"])} of {r["cases"]} cases\n')
        print(f'  caught      {o["tp"]:3} of {o["tp"] + o["fn"]} known-bad   '
              f'(recall {o["recall"]}%)')
        print(f'  false flags {o["fp"]:3} of {o["fp"] + o["tn"]} known-good  '
              f'(precision {o["precision"]}%)')
        print("\n  per check:")
        for k, s in r["per_check"].items():
            print(f'    check {k}: recall {s["recall"]}%  precision {s["precision"]}%  '
                  f'(tp {s["tp"]} fp {s["fp"]} fn {s["fn"]})')
        if r["unquoted_flags"]:
            print(f'\n  {len(r["unquoted_flags"])} flag(s) with no quote -- '
                  f'discard these unread:')
            for cid in r["unquoted_flags"]:
                print(f"    {cid}")
        if r["missing"]:
            print(f'\n  {len(r["missing"])} case(s) not answered')
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
