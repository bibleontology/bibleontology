"""Keep the public repository's traffic beyond GitHub's 14 days (2026-10-23).

GitHub's Insights -> Traffic shows views, unique visitors, clones, the top
referring sites and the top ten files and pages opened, and keeps only the
last 14 days. This fetches the same numbers from GitHub's API and appends one
line per day to a private log, so the history survives:

    python tools/github_traffic.py           # fetch and append, then print a summary
    python tools/github_traffic.py --report  # the summary only, from the log

The token is read from the system keyring (service "bibleontology", user
"github-traffic"), never from this repository and never printed. To store it,
once (a fine-grained token on bibleontology/bibleontology, read-only
"Administration" permission, which is what GitHub's traffic API asks for):

    python -m keyring set bibleontology github-traffic

The log is ops/github-traffic.jsonl, which is not in the public copy.
"""
import argparse
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "bibleontology/bibleontology"
LOG = ROOT / "ops" / "github-traffic.jsonl"
API = "https://api.github.com/repos/" + REPO + "/traffic/"


def token() -> str:
    try:
        import keyring
    except ImportError:
        sys.exit("keyring is not installed: pip install keyring")
    t = keyring.get_password("bibleontology", "github-traffic")
    if not t:
        sys.exit("no token stored: python -m keyring set bibleontology github-traffic")
    return t


def get(path: str, tok: str):
    req = urllib.request.Request(API + path, headers={
        "Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "bibleontology-traffic"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch():
    tok = token()
    views, clones = get("views", tok), get("clones", tok)
    paths, refs = get("popular/paths", tok), get("popular/referrers", tok)
    today = dt.date.today().isoformat()
    # one line per fetch: the daily series (GitHub's 14 days, overlapping the
    # last fetch; the report keeps the newest value for each day) and today's
    # top paths and referrers, which GitHub gives only as 14-day totals
    rec = {"fetched": today,
           "views": {v["timestamp"][:10]: [v["count"], v["uniques"]] for v in views.get("views", [])},
           "clones": {c["timestamp"][:10]: [c["count"], c["uniques"]] for c in clones.get("clones", [])},
           "paths_14d": [[p["path"], p["count"], p["uniques"]] for p in paths],
           "referrers_14d": [[r["referrer"], r["count"], r["uniques"]] for r in refs]}
    LOG.parent.mkdir(exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def report():
    if not LOG.exists():
        sys.exit(f"no log yet: {LOG.relative_to(ROOT)}")
    recs = [json.loads(x) for x in LOG.read_text(encoding="utf-8").splitlines() if x.strip()]
    views, clones = {}, {}
    for r in recs:                      # later fetches win for a day they share
        views.update(r["views"])
        clones.update(r["clones"])
    print("day         views  visitors  clones")
    for d in sorted(views)[-14:]:
        v, c = views.get(d, [0, 0]), clones.get(d, [0, 0])
        print(f"{d}  {v[0]:5}  {v[1]:8}  {c[0]:6}")
    print(f"all days logged: {sum(v[0] for v in views.values())} views, {len(views)} days")
    last = recs[-1]
    print("top pages (last 14 days):")
    for p, n, u in last["paths_14d"][:10]:
        print(f"  {n:4} views, {u:3} visitors  {p}")
    print("came from (last 14 days):")
    for r, n, u in last["referrers_14d"][:10]:
        print(f"  {n:4} views, {u:3} visitors  {r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if not a.report:
        fetch()
    report()


if __name__ == "__main__":
    main()
