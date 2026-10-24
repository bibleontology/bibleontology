"""How much the app itself can take, measured on the server, behind nothing.

2026-10-01, the night before the Reddit posts: how to stress test with the
rate limiting in place.

WHAT THIS MEASURES, AND WHY HERE. A surge from a Reddit post is many readers,
each well under Cloudflare's rate limit (60 /api requests per 10 s per
address, which in practice stops ~10-12 a second; docs/OPERATIONS.md), so the
limit never fires on it. Cloudflare's cache takes the repeats once the Cache
Rule is on; what is left reaches this one Python process. So the question is
the origin's: how many requests a second it answers, and how slow it gets,
before it falls over. That is measured here, from the server, against
127.0.0.1:8000 -- not through Cloudflare, which would mostly measure
Cloudflare and would trip the rate limit and Bot Fight Mode on our own
address long before the app noticed.

HOW. Workers loop with no pause between requests (each is a reader who never
stops), in steps: 1, 2, 4, 8, 16, 32 workers, 30 s each by default. Requests
are a reader's mix -- the page and its start-up calls, chapters, cards,
searches, a verse's connections and structure -- with chapters, cards and
verses drawn at random across the whole Bible, so few repeat: the worst case
for any cache, the case a Cloudflare miss sends here. It stops at the first
step where the 95th percentile passes --stop-p95 ms or errors pass 2%.

Every request says "bibleont-check/loadtest", which the app counts as its own
check and nowhere else (app2/activity.py): no visitors, no timings, no
hourly bars.

    python3 /srv/bibleontology/tools/loadtest.py               # the stepped run
    python3 /srv/bibleontology/tools/loadtest.py --soak 30     # memory over 30 min
    python3 tools/loadtest.py --steps 1,4 --seconds 10          # a short look
    python3 tools/loadtest.py --base http://127.0.0.1:8002      # the local preview

(127.0.0.1, not localhost: on Windows "localhost" tries IPv6 first and every
request then waits two seconds for the fallback -- the first trial measured
2,000 ms a request at any load, and it was that, not the app.)

Measured locally, 2026-10-01 (laptop, random across the whole Bible): about
77 req/s, flat from 4 workers -- one Python process. A reader's page load is
9 requests and each action after it about 1, so that is hundreds of readers
active at once. The droplet is slower; the server run gives its number.

Run it when nobody is reading (the stepped run takes about 3 minutes and the
top steps will slow the site for anyone on it), and watch /ops or `htop`.
"""
import argparse
import json
import os
import random
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "bibleont-check/loadtest"
ROOT = Path(__file__).resolve().parents[1]
BOOT = ["/api/books", "/api/collections", "/api/lists", "/api/majorthemes",
        "/api/events", "/api/upper", "/api/recurs", "/api/patternsets"]
WORDS = ["grace", "love", "faith", "mercy", "David", "Moses", "Mary", "Joseph",
         "John 3:16", "Psalm 23", "covenant", "kingdom", "shepherd", "lamb",
         "Abraham", "Jerusalem", "temple", "prayer", "peace", "light", "spirit",
         "anxiety", "forgive", "Romans 8", "Genesis 1", "Paul", "Peter", "Ruth",
         "wisdom", "fear", "hope", "joy", "sin", "law", "Elijah", "Egypt"]
# BSB chapter counts, for random chapters and verses across the whole Bible
MACULA = {"Gen": 50, "Exo": 40, "Lev": 27, "Num": 36, "Deu": 34, "Jos": 24, "Jdg": 21,
          "Rut": 4, "1Sa": 31, "2Sa": 24, "1Ki": 22, "2Ki": 25, "1Ch": 29, "2Ch": 36,
          "Ezr": 10, "Neh": 13, "Est": 10, "Job": 42, "Psa": 150, "Pro": 31, "Ecc": 12,
          "Isa": 66, "Jer": 52, "Ezk": 48, "Dan": 12, "Hos": 14, "Mat": 28, "Mrk": 16,
          "Luk": 24, "Jhn": 21, "Act": 28, "Rom": 16, "1Co": 16, "Gal": 6, "Eph": 6,
          "Php": 4, "Heb": 13, "Jas": 5, "1Pe": 5, "1Jn": 5, "Rev": 22}
READER = {"Gen": "Gen", "Exo": "Exod", "Lev": "Lev", "Num": "Num", "Deu": "Deut",
          "Jos": "Josh", "Jdg": "Judg", "Rut": "Ruth", "1Sa": "1Sam", "2Sa": "2Sam",
          "1Ki": "1Kgs", "2Ki": "2Kgs", "1Ch": "1Chr", "2Ch": "2Chr", "Ezr": "Ezra",
          "Neh": "Neh", "Est": "Esth", "Job": "Job", "Psa": "Ps", "Pro": "Prov",
          "Ecc": "Eccl", "Isa": "Isa", "Jer": "Jer", "Ezk": "Ezek", "Dan": "Dan",
          "Hos": "Hos", "Mat": "Matt", "Mrk": "Mark", "Luk": "Luke", "Jhn": "John",
          "Act": "Acts", "Rom": "Rom", "1Co": "1Cor", "Gal": "Gal", "Eph": "Eph",
          "Php": "Phil", "Heb": "Heb", "Jas": "Jas", "1Pe": "1Pet", "1Jn": "1John",
          "Rev": "Rev"}


def entity_ids():
    p = ROOT / "ontology" / "entities" / "entities.jsonl"
    ids = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                ids.append(json.loads(line)["id"])
    return ids


def make_request(rng, ids):
    """One reader action: (kind, path)."""
    b = rng.choice(list(MACULA))
    c = rng.randint(1, MACULA[b])
    v = rng.randint(1, 12)
    q = urllib.parse.urlencode
    r = rng.random()
    if r < 0.06:
        return "page", "/"
    if r < 0.22:
        return "start-up", rng.choice(BOOT)
    if r < 0.42:
        return "chapter", "/api/chapter?" + q({"b": READER[b], "c": c})
    if r < 0.62:
        return "card", "/api/entity?" + q({"id": rng.choice(ids)})
    if r < 0.72:
        return "card verses", "/api/entity-verses?" + q({"id": rng.choice(ids)})
    if r < 0.84:
        return "search", "/api/search?" + q({"q": rng.choice(WORDS)})
    if r < 0.94:
        return "connections", "/api/echoes?" + q({"ref": f"{b}.{c}.{v}"})
    return "structure", "/api/structure?" + q({"b": READER[b], "c": c, "v": v})


def app_rss_mb():
    """The app's resident memory, if this is the server (best effort)."""
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                cmd = Path(f"/proc/{pid}/cmdline").read_bytes()
            except OSError:
                continue
            if b"app2/server.py" in cmd:
                for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                    if line.startswith("VmRSS:"):
                        return round(int(line.split()[1]) / 1024)
    except OSError:
        pass
    return None


def step(base, workers, seconds, ids, timeout, salt=0):
    stop = time.monotonic() + seconds
    lock = threading.Lock()
    times, errors, slow_kind = [], [], {}

    def run(seed):
        rng = random.Random(seed)
        while time.monotonic() < stop:
            kind, path = make_request(rng, ids)
            req = urllib.request.Request(base + path, headers={"User-Agent": UA})
            t0 = time.monotonic()
            status = 0
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    resp.read()
                    status = resp.status
            except urllib.error.HTTPError as e:
                status = e.code
            except Exception:                               # noqa: BLE001
                status = -1                                 # timeout, refused
            ms = (time.monotonic() - t0) * 1000
            with lock:
                # a 404 on a random id or verse is an answer, not a fault
                if status in (200, 404):
                    times.append(ms)
                    k = slow_kind.setdefault(kind, [])
                    k.append(ms)
                else:
                    errors.append((status, kind, path))
    # A FRESH DRAW EACH STEP. The first soak on the server (2026-10-01) seeded
    # every minute alike, so every minute asked for the same chapters, cards
    # and verses as the first: alternate minutes answered in 3-4 ms from the
    # app's cache of recent answers, and memory measured the cache filling,
    # not readers reaching new parts of the site.
    ts = [threading.Thread(target=run, args=(salt * 100_003 + workers * 1000 + i,))
          for i in range(workers)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    n = len(times) + len(errors)
    q = lambda xs, p: (sorted(xs)[min(len(xs) - 1, int(p * len(xs)))] if xs else 0)  # noqa: E731
    return {"workers": workers, "n": n, "rps": n / seconds,
            "p50": q(times, 0.5), "p95": q(times, 0.95), "max": max(times or [0]),
            "err": len(errors), "err_rate": len(errors) / n if n else 0,
            "errors": errors[:5], "rss": app_rss_mb(),
            "by_kind": {k: (len(v), q(v, 0.5), q(v, 0.95)) for k, v in slow_kind.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--steps", default="1,2,4,8,16,32")
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--stop-p95", type=int, default=3000)
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--soak", type=int, default=0, metavar="MINUTES",
                    help="instead of steps: --workers for this many minutes, a line a minute")
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    ids = entity_ids()
    if a.soak:
        # THE SLOW BUILD-UP. 2026-10-01: the gradual
        # build-up is the bigger risk -- and with a low-profile post, a fast
        # surge is not the shape traffic will take. What builds up here is
        # memory: the app loads its data as readers first reach each part
        # (2,090 MB on the first public night, against systemd's MemoryMax=3G,
        # past which it is killed and restarts cold). A steady, modest load
        # drawn across the whole Bible and every kind of request touches all
        # of it; the line a minute shows where memory levels off, and whether
        # the answers slow as it climbs.
        print(f"soak: {a.workers} workers for {a.soak} min against {a.base}; "
              f"app memory {app_rss_mb() or '?'} MB at the start")
        print(f"{'minute':>6} {'req/s':>7} {'typical':>8} {'95%':>8} {'errors':>7} {'memory':>8}")
        for m in range(1, a.soak + 1):
            r = step(a.base, a.workers, 60, ids, a.timeout, salt=m)
            print(f"{m:>6} {r['rps']:>7.1f} {r['p50']:>6.0f}ms {r['p95']:>6.0f}ms "
                  f"{r['err']:>7} {str(r['rss'] or '?') + ' MB':>8}", flush=True)
            if r["err_rate"] > 0.02:
                print("stopped: errors over 2%", r["errors"])
                break
        return
    print(f"against {a.base}, {len(ids):,} card ids, {a.seconds} s a step; "
          f"app memory {app_rss_mb() or '?'} MB before")
    print(f"{'workers':>7} {'req/s':>7} {'typical':>8} {'95%':>8} {'slowest':>8} "
          f"{'errors':>7} {'memory':>7}")
    results = []
    for w in [int(x) for x in a.steps.split(",")]:
        r = step(a.base, w, a.seconds, ids, a.timeout, salt=w)
        results.append(r)
        print(f"{w:>7} {r['rps']:>7.1f} {r['p50']:>6.0f}ms {r['p95']:>6.0f}ms "
              f"{r['max']:>6.0f}ms {r['err']:>7} {str(r['rss'] or '?') + ' MB':>7}", flush=True)
        if r["p95"] > a.stop_p95 or r["err_rate"] > 0.02:
            print(f"stopped: {'95% over ' + str(a.stop_p95) + ' ms' if r['p95'] > a.stop_p95 else 'errors over 2%'}")
            for e in r["errors"]:
                print("   ", e)
            break
    last = results[-1]
    print("\nby kind at the last step (count, typical, 95%, ms):")
    for k, (n, p50, p95) in sorted(last["by_kind"].items(), key=lambda kv: -kv[1][2]):
        print(f"  {k:12} {n:>6} {p50:>7.0f} {p95:>7.0f}")
    best = max(results, key=lambda r: r["rps"] if r["p95"] <= 1000 and not r["err"] else 0)
    print(f"\nmost it answered with 95% under 1 s and no errors: {best['rps']:.0f} req/s "
          f"at {best['workers']} workers")


if __name__ == "__main__":
    main()
