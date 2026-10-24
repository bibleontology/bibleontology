"""One snapshot of everything running, for a phone in another room.

The state already exists -- the farm writes after every window, every call
logs its usage, the gate is reproducible, the graph validates. What did not
exist was a way to see it without a terminal, which meant that checking on a
six-hour run required being at the machine it was running on.

**Read-only, deliberately.** Nothing here starts, stops, deploys or pushes.
The dangerous version of this idea is a web page that executes commands, and
the safe version is a web page that reports. Wanting the second is not a
reason to build the first.

## What it costs to render

Everything except the gate is a file read and some arithmetic -- milliseconds.
Running the gate over twenty proposal batches takes several seconds, so it is
opt-in (`gate=1`) rather than part of every poll: a status page that takes six
seconds to load is a status page nobody opens.
"""

from __future__ import annotations

import glob
import json
import math
import os
import time
from datetime import datetime, timezone

from .paths import ROOT

FARM = ROOT / "ontology" / "proposals" / ".farm"
RUNS = ROOT / "ontology" / "proposals" / ".runs"
PROPOSALS = ROOT / "ontology" / "proposals"

# Off-peak flash. Deliberately the same arithmetic `spend` uses, and known to
# run about 14% above what DeepSeek actually bills -- so a figure here is a
# ceiling rather than a surprise.
RATE = {"hit": 0.007, "miss": 0.22, "out": 0.66}

# Longer than this between two windows and the run was not running.
PAUSE = 15 * 60


def _cost(u: dict) -> float:
    return (u.get("prompt_cache_hit_tokens", 0) * RATE["hit"]
            + u.get("prompt_cache_miss_tokens", 0) * RATE["miss"]
            + u.get("completion_tokens", 0) * RATE["out"]) / 1e6


def farms() -> list[dict]:
    """Every book the farm has state for, with a live estimate of the rest."""
    from .decompose import windows
    from .farm import chapters_of

    out = []
    for path in sorted(FARM.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        book = raw.get("book")
        if not book:
            continue
        done = raw.get("done") or {}
        try:
            total = sum(len(windows(book, c)) for c in chapters_of(book))
        except Exception:                                    # noqa: BLE001
            total = 0
        stamps = sorted(v.get("when", "") for v in done.values() if v.get("when"))
        # Median gap between consecutive windows, not total span over count.
        # A book resumed hours later -- Psalm 23 this morning, Psalm 34 this
        # afternoon -- has an enormous span and three windows, and the mean
        # said the Psalms would finish in 2,705 hours. The median ignores the
        # gap where nothing was running, which is exactly what it is for.
        # A gap between two windows is either work or a pause, and only the
        # first is a rate. A window takes about three minutes; anything over
        # PAUSE is a session that stopped and started again -- Psalm 23 this
        # morning and Psalm 34 this afternoon, which first produced an
        # estimate of 2,705 hours and then, after a naive median, 5,395.
        rate = eta = None
        ts = [datetime.fromisoformat(x.replace("Z", "+00:00")) for x in stamps]
        gaps = sorted(g for g in ((b - a).total_seconds()
                                  for a, b in zip(ts, ts[1:])) if g <= PAUSE)
        if gaps:
            rate = gaps[len(gaps) // 2]
            eta = (total - len(done)) * rate

        # Running, or stopped? Nothing records that, and asking the OS would
        # tie this to one machine -- so it is inferred from whether a window
        # landed recently. Wrong only in the window between two calls.
        idle = None
        if stamps:
            last = datetime.fromisoformat(stamps[-1].replace("Z", "+00:00"))
            idle = (datetime.now(timezone.utc) - last).total_seconds()

        out.append({
            "book": book,
            "done": len(done),
            "total": total,
            "spent": round(raw.get("spent") or 0.0, 4),
            "created": len(raw.get("created") or {}),
            "entities": sum(v.get("entities", 0) for v in done.values()),
            "relations": sum(v.get("relations", 0) for v in done.values()),
            "questions": sum(v.get("questions", 0) for v in done.values()),
            "minutes_per_window": round(rate / 60, 1) if rate else None,
            "hours_left": round(eta / 3600, 1) if eta else None,
            "idle_seconds": round(idle) if idle is not None else None,
            "live": bool(idle is not None and rate and idle < rate * 3),
        })
    return out


def spend() -> dict:
    """What every logged call has cost, and how much of it was today."""
    today = time.strftime("%Y%m%d")
    total = todays = 0.0
    calls = todays_calls = 0
    for f in glob.glob(str(RUNS / "*.jsonl")):
        is_today = os.path.basename(f).startswith(today)
        for line in open(f, encoding="utf-8"):
            u = (json.loads(line).get("usage") or {})
            if not u:
                continue
            c = _cost(u)
            total += c
            calls += 1
            if is_today:
                todays += c
                todays_calls += 1
    return {"total": round(total, 4), "calls": calls,
            "today": round(todays, 4), "today_calls": todays_calls}


BALANCE_CACHE = PROPOSALS / ".farm" / ".balance.json"


def refresh_balance() -> dict:
    """Ask DeepSeek what is left, and write it where the server can read it.

    **The web server never sees the API key, and that is the point.** The
    obvious build has the ops endpoint call the provider directly -- which
    puts a live credential in the process that answers requests from the
    internet, to save a file write. It was tried here and failed for an
    unrelated reason (the server cannot reach Credential Manager), and the
    failure was worth keeping: the key belongs with the command line, which
    already holds it and is not listening on a port.

    So this runs where the key is -- from the farm as it works, or by hand.
    """
    import urllib.request
    from .providers import from_keystore

    key = from_keystore("deepseek") or os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        return {"usd": None, "why": "no key in keystore or environment"}
    try:
        req = urllib.request.Request(
            "https://api.deepseek.com/user/balance",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as fh:
            raw = json.loads(fh.read())
        info = (raw.get("balance_infos") or [{}])[0]
        val = {"usd": float(info.get("total_balance") or 0),
               "available": bool(raw.get("is_available")), "at": time.time()}
    except Exception as exc:                                 # noqa: BLE001
        return {"usd": None, "why": f"{type(exc).__name__}: {str(exc)[:80]}"}
    BALANCE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    BALANCE_CACHE.write_text(json.dumps(val), encoding="utf-8")
    return val


def balance() -> dict | None:
    """Credit left, as last recorded, with how old the figure is.

    The ask was a webview of the provider's usage page. That cannot work:
    `platform.deepseek.com` sends frame-blocking headers, and this origin
    embedding theirs is the cross-origin case third-party cookie blocking
    exists to stop -- it would render blank, or logged-out. But the number is
    what the webview was wanted for, and the number can simply be fetched.

    **Age is reported, never hidden.** A stale balance shown as current is
    worse than no balance: it is precisely the figure someone decides not to
    top up on. The farm refreshes it while it runs, so it is freshest exactly
    when it is being spent.
    """
    try:
        raw = json.loads(BALANCE_CACHE.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return {"usd": None,
                "why": "not fetched yet — python -m bibleont.ops --balance"}
    raw["age_minutes"] = round((time.time() - float(raw.get("at") or 0)) / 60)
    return raw


def supervisor_position() -> dict:
    """The supervisor's ledger, for the dashboard.

    Reads files only -- no key and no network, like everything else the web
    server does. The supervisor writes; this reads.
    """
    try:
        from .supervisor import position
        return position()
    except Exception:                                        # noqa: BLE001
        return {"configured": False}


def proposals(with_gate: bool = False) -> list[dict]:
    """Batches waiting for a decision, newest first."""
    out = []
    for d in sorted(PROPOSALS.glob("*/"), key=os.path.getmtime, reverse=True):
        rel = d / "relations.jsonl"
        ent = d / "entities.jsonl"
        if not rel.exists():
            continue
        row = {
            "name": d.name,
            "relations": sum(1 for _ in open(rel, encoding="utf-8")),
            "entities": sum(1 for _ in open(ent, encoding="utf-8"))
            if ent.exists() else 0,
            "when": datetime.fromtimestamp(
                os.path.getmtime(d), timezone.utc).isoformat(timespec="minutes"),
        }
        if with_gate:
            try:
                from .proposals import assess
                a = assess(d)
                row["gate"] = "pass" if a.ok else "fail"
                row["errors"] = len(a.errors)
            except Exception as exc:                         # noqa: BLE001
                row["gate"] = f"?{type(exc).__name__}"
        out.append(row)
    return out


def graph() -> dict:
    from .schema import load_entities, load_relations, load_vocabulary
    from .corpus import get_corpus
    from .validate import validate

    people = load_entities()
    rels = load_relations()
    issues = validate(people, rels, load_vocabulary(), get_corpus())
    keyed = sum(1 for p in people.values() if (p.attrs or {}).get("lemma"))
    return {
        "entities": len(people),
        "relations": len(rels),
        "errors": sum(1 for i in issues if i.level == "error"),
        "warnings": sum(1 for i in issues if i.level != "error"),
        "lemma_keyed": keyed,
    }


def questions() -> dict:
    """Collapsed judgement calls waiting, across every queue."""
    seen: dict[str, int] = {}
    files = 0
    for f in glob.glob(str(PROPOSALS / ".questions" / "*.jsonl")):
        files += 1
        for line in open(f, encoding="utf-8"):
            row = json.loads(line)
            k = row.get("key", "?")
            seen[k] = seen.get(k, 0) + int(row.get("n", 1))
    return {"distinct": len(seen), "occurrences": sum(seen.values()),
            "queues": files,
            "top": sorted(seen.items(), key=lambda kv: -kv[1])[:8]}


def snapshot(with_gate: bool = False) -> dict:
    return {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "farms": farms(),
        "spend": spend(),
        "balance": balance(),
        "supervisor": supervisor_position(),
        "graph": graph(),
        "questions": questions(),
        "proposals": proposals(with_gate),
    }


def main(argv: list[str] | None = None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--balance" in argv:
        b = refresh_balance()
        if b.get("usd") is None:
            print(f"  balance    unavailable — {b.get('why')}")
            return 1
        print(f"  balance    ${b['usd']:.2f} at DeepSeek"
              + ("" if b.get("available") else "  (ACCOUNT UNAVAILABLE)"))
        return 0

    s = snapshot("--gate" in argv)

    for f in s["farms"]:
        bar = ""
        if f["total"]:
            n = int(18 * f["done"] / f["total"])
            bar = "#" * n + "." * (18 - n)
        live = "running" if f["live"] else "idle"
        print(f"  {f['book']:6}{bar} {f['done']:>4}/{f['total']:<4} "
              f"${f['spent']:>6.2f}  {live}"
              + (f"  ~{f['hours_left']}h left" if f["hours_left"] else ""))
    g = s["graph"]
    print(f"\n  graph      {g['entities']:,} entities, {g['relations']:,} "
          f"relations, {g['errors']} errors, {g['lemma_keyed']} lemma-keyed")
    q = s["questions"]
    print(f"  questions  {q['distinct']} distinct from {q['occurrences']} "
          f"occurrences, across {q['queues']} queues")
    sp = s["spend"]
    print(f"  spend      ${sp['today']:.2f} today, ${sp['total']:.2f} all time "
          f"({sp['calls']} calls)")
    b = s.get("balance") or {}
    if b.get("usd") is not None:
        age = b.get("age_minutes")
        print(f"  balance    ${b['usd']:.2f} left"
              + (f", as of {age} min ago" if age else ", just now"))
    print(f"  waiting    {len(s['proposals'])} proposal batches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
