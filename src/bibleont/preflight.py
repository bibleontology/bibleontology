"""Check the money guards before a run, not after it.

2026-08-31, after a provider leak bought $14.55 of DeepSeek work from Opus:
double and triple checking of cost-overrun protection became a high priority,
as did avoiding too much processing without catching errors.

Every one of that night's failures was invisible for the same reason: a number
that should have moved did not, or a number presented as real was fiction.

    the cost column froze at $0.0351 and nobody looked
    the ledger said "$12.43 left" and the account held nothing
    the supervisor said "unavailable: HTTPError" 119 times and meant "no credit"
    Mark and Exodus scored 0% verse-nodes and it was the MODEL, not the prompt

So this asks each guard to demonstrate itself rather than be trusted. It costs
about two hundredths of a cent -- one 16-token ping to Anthropic -- and it is
meant to be run before every session that will spend.

    python -m bibleont.preflight
    python -m bibleont.preflight --no-ping     skip the paid check

## What it will not do

It does not check that the extraction is any good. That is the gate, the
linter and the supervisor. This checks only that the machinery which stops
runaway spending is present and working, which is a different question and was
the one nobody was asking.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

from .paths import ROOT

OK, BAD = "  ok  ", "  FAIL"
_failures: list[str] = []


def check(name: str, passed: bool, detail: str = "") -> bool:
    print(f"{OK if passed else BAD}  {name}" + (f"  -- {detail}" if detail else ""))
    if not passed:
        _failures.append(name)
    return passed


def _worker_provider() -> None:
    """The worker must be pointed at the worker's provider."""
    from .providers import current

    want = os.environ.get("BIBLEONT_WORKER_PROVIDER", "deepseek")
    actual = os.environ.get("BIBLEONT_PROVIDER", "deepseek").strip().lower()
    check(f"worker provider is {want!r}", actual == want, f"it is {actual!r}")
    prov = current()
    check("worker key is present", bool(prov.key),
          "" if prov.key else f"{prov.key_env} is empty")


def _pricing() -> None:
    """A foreign usage shape must refuse to price, not price at zero."""
    from .decompose import UnpriceableUsage, cost

    ds = cost([{"prompt_cache_miss_tokens": 50000, "completion_tokens": 3000}])
    check("DeepSeek usage prices above zero", ds > 0, f"got ${ds:.5f}")

    try:
        cost([{"cache_read_input_tokens": 50000, "output_tokens": 2000}])
        check("foreign usage is REFUSED, not priced at zero", False,
              "it returned a number -- this is the $14.55 bug")
    except UnpriceableUsage:
        check("foreign usage is REFUSED, not priced at zero", True)


def _governor() -> None:
    from .governor import Governor, WORST_REVIEW

    g = Governor(per_run=0.20, grant_left=100.0)
    check("governor allows a call when funded", g.may_spend()[0])
    g.record(0.16)
    allowed, why = g.may_spend()
    check("governor refuses on the WORST case, not the average",
          not allowed and "per-run" in why, why[:60])

    g2 = Governor(per_run=10.0, grant_left=WORST_REVIEW / 2)
    allowed, why = g2.may_spend()
    check("governor refuses when the grant cannot cover one call",
          not allowed and "grant" in why, why[:60])


def _stop_conditions() -> None:
    """An exhausted balance must stop a run, in either provider's dialect."""
    from .farm import _http_stop

    ds = _http_stop(Exception("HTTP Error 402: Insufficient Balance"))
    check("DeepSeek's 402 stops a run", bool(ds), ds[:50])

    class _Fake(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("u", 400, "Bad Request", {}, None)

        def read(self):
            return (b'{"error":{"message":"Your credit balance is too low '
                    b'to access the Anthropic API."}}')

    an = _http_stop(_Fake())
    check("Anthropic's 400-with-a-reason stops a run", bool(an), an[:60])


def _balances(ping: bool) -> None:
    from .providers import PROVIDERS

    bal = None
    try:
        from .ops import balance as _bal
        got = _bal() or {}
        bal = got.get("usd")
        if bal is None:
            bal = got.get("balance") or got.get("total")
    except Exception:                                        # noqa: BLE001
        bal = None
    if bal is not None:
        check("DeepSeek balance is readable and funded", float(bal) > 0.10,
              f"${float(bal):.2f}")
    else:
        print("  --    DeepSeek balance not cached locally (not a failure)")

    if not ping:
        print("  --    Anthropic credit not checked (--no-ping)")
        return

    prov = PROVIDERS["anthropic"]
    if not prov.key:
        check("Anthropic key present", False, f"{prov.key_env} is empty")
        return
    body = {"model": "claude-opus-5", "max_tokens": 16,
            "system": [{"type": "text", "text": "Reply with: ok"}],
            "messages": [{"role": "user", "content": "ping"}]}
    from .providers import HEADERS

    h = dict(HEADERS)
    h.pop("Authorization", None)
    h["x-api-key"] = prov.key
    h["anthropic-version"] = "2023-06-01"
    try:
        req = urllib.request.Request(prov.chat_url,
                                     data=json.dumps(body).encode(), headers=h)
        with urllib.request.urlopen(req, timeout=60):
            check("Anthropic credit is live", True, "16-token ping, ~$0.0002")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:90]
        except Exception:                                    # noqa: BLE001
            pass
        check("Anthropic credit is live", False, f"{exc.code} {detail}")


def _ledger_is_honest() -> None:
    """The ledger must not present a projection as a balance."""
    p = ROOT / "ontology" / "proposals" / ".supervisor" / "ledger.json"
    if not p.exists():
        print("  --    no supervisor ledger yet")
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    check("ledger records what it was verified against",
          bool(d.get("verified_against")),
          "it is a budget, not a balance, and should say so")


def _suite() -> None:
    t = ROOT / "tests" / "test_farm_loop.py"
    r = subprocess.run([sys.executable, str(t)], capture_output=True, text=True,
                       cwd=ROOT)
    n = r.stdout.count("ok  ")
    check(f"the farm guard suite passes ({n} checks)", r.returncode == 0,
          r.stdout.strip().splitlines()[-1] if r.stdout else "")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ping = "--no-ping" not in argv

    print("  money guards")
    print()
    _worker_provider()
    _pricing()
    _governor()
    _stop_conditions()
    _ledger_is_honest()
    _suite()
    print()
    print("  live")
    print()
    _balances(ping)

    print()
    if _failures:
        print(f"  {len(_failures)} FAILED: {', '.join(_failures)}")
        print("  Do not start a run.")
        return 1
    print("  all guards demonstrated. Safe to spend.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
