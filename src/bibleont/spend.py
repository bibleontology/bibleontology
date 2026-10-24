"""What the workers have cost, read from here rather than from a dashboard.

Two questions, and only one of them needs the network.

**What has been spent** is already on disk. Every call writes its `usage` into
`ontology/proposals/.runs/`, so the totals and the per-run costs are a local
sum. That matters more than convenience: a dashboard tells you the number, and
a run log tells you which brief produced it, which is the thing that decides
whether to run it again.

**What is left** is the one figure only the provider knows, and it is a single
GET.

## Why the arithmetic is not just tokens times a rate

Cached input is priced roughly thirty times below uncached, and this workload
is unusually cacheable -- the system prompt is identical on every call and
sits first, so after the first request most of the input should hit. DeepSeek
reports the split as `prompt_cache_hit_tokens` and `prompt_cache_miss_tokens`,
and the difference between assuming a hit and being told one is the difference
between an estimate and a measurement.

Peak hours double everything. They are 01:00-04:00 and 06:00-10:00 UTC on
weekdays, which is late evening and small hours in the eastern United States
-- so the natural time to work is the expensive one, and an overnight job
started after midnight Eastern lands in the cheap window.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from bibleont.paths import ROOT

RUNS = ROOT / "ontology" / "proposals" / ".runs"
BALANCE_URL = os.environ.get(
    "BIBLEONT_BALANCE_URL", "https://api.deepseek.com/user/balance")

# USD per million tokens, off-peak / peak. Pro as published 26 August 2026;
# Flash re-read 25 September 2026 (the page was pasted in): the model is now
# DeepSeek-V4.1-Flash, named `deepseek-flash`, and cheaper on every line. The
# legacy name `deepseek-v4-flash` is still accepted, served by V4.1-Flash and
# billed at the Flash price — so it keeps the same rates here.
_FLASH = {"hit": (0.003, 0.006), "miss": (0.15, 0.30), "out": (0.60, 1.20)}
RATES = {
    "deepseek-flash":    _FLASH,
    "deepseek-v4-flash": _FLASH,
    "deepseek-v4-pro":   {"hit": (0.022, 0.044), "miss": (0.66, 1.32),
                          "out": (1.98, 3.96)},
}
DEFAULT = RATES["deepseek-flash"]


def is_peak(when: datetime) -> bool:
    """01:00-04:00 and 06:00-10:00 UTC, Monday to Friday."""
    if when.weekday() >= 5:
        return False
    h = when.hour
    return 1 <= h < 4 or 6 <= h < 10


def cost_of(usage: dict, model: str, peak: bool) -> float:
    r = RATES.get(model or "", DEFAULT)
    i = 1 if peak else 0
    hit = usage.get("prompt_cache_hit_tokens")
    miss = usage.get("prompt_cache_miss_tokens")
    if hit is None and miss is None:
        # No split reported. Charging it all at the miss rate overstates the
        # bill, which is the safe direction to be wrong in.
        miss, hit = usage.get("prompt_tokens", 0), 0
    out = usage.get("completion_tokens", 0)
    return ((hit or 0) * r["hit"][i]
            + (miss or 0) * r["miss"][i]
            + out * r["out"][i]) / 1_000_000


def runs() -> list[tuple[Path, dict]]:
    out = []
    if not RUNS.exists():
        return out
    for p in sorted(RUNS.glob("*.jsonl")):
        rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
                if l.strip()]
        try:
            when = datetime.strptime(p.stem, "%Y%m%d-%H%M%S").replace(
                tzinfo=timezone.utc)
        except ValueError:
            when = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
        peak = is_peak(when)
        tally = {"calls": len(rows), "failed": sum(1 for r in rows if r.get("error")),
                 "in_hit": 0, "in_miss": 0, "out": 0, "cost": 0.0,
                 "peak": peak, "models": set(), "when": when}
        for r in rows:
            u = r.get("usage") or {}
            tally["models"].add(r.get("model_returned") or "?")
            hit = u.get("prompt_cache_hit_tokens") or 0
            miss = u.get("prompt_cache_miss_tokens")
            if miss is None:
                miss = u.get("prompt_tokens", 0) - hit
            tally["in_hit"] += hit
            tally["in_miss"] += max(miss, 0)
            tally["out"] += u.get("completion_tokens", 0)
            tally["cost"] += cost_of(u, r.get("model_returned"), peak)
        out.append((p, tally))
    return out


def balance() -> dict | None:
    key = os.environ.get("BIBLEONT_REVIEW_KEY", "")
    if not key:
        return None
    req = urllib.request.Request(
        BALANCE_URL, headers={"Authorization": f"Bearer {key}",
                              "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    rows = runs()
    if rows:
        print(f'{"run":18} {"calls":>6} {"fail":>5} {"in (hit/miss)":>18} '
              f'{"out":>7} {"cost":>9}  window')
        total = 0.0
        for p, t in rows:
            total += t["cost"]
            print(f'  {p.stem:16} {t["calls"]:6} {t["failed"]:5} '
                  f'{t["in_hit"]:8}/{t["in_miss"]:<8} {t["out"]:7} '
                  f'{t["cost"]:9.5f}  {"PEAK" if t["peak"] else "off-peak"}')
            models = {m for m in t["models"] if m and m != "?"}
            if len(models) > 1:
                print(f'{"":18} more than one model answered: {", ".join(sorted(models))}')
        print(f'\n  {len(rows)} run(s), ${total:.4f} spent locally recorded')
    else:
        print(f"no runs recorded under {RUNS}")

    now = datetime.now(timezone.utc)
    print(f'\n  it is {now:%H:%M} UTC, a {"PEAK" if is_peak(now) else "off-peak"} '
          f'window right now')

    if "--no-remote" in argv:
        return 0
    try:
        b = balance()
    except Exception as exc:
        print(f"\n  balance unavailable: {exc}")
        return 0
    if b is None:
        print("\n  BIBLEONT_REVIEW_KEY not set, so no balance was requested")
        return 0
    infos = b.get("balance_infos") or []
    if not infos:
        print(f"\n  balance: {json.dumps(b)[:200]}")
        return 0
    for info in infos:
        print(f'\n  balance  {info.get("total_balance")} {info.get("currency")}'
              f'   (granted {info.get("granted_balance")}, '
              f'topped up {info.get("topped_up_balance")})')
    if b.get("is_available") is False:
        print("  the account is NOT available for requests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
