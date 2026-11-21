"""Card access from /ops, for the UI designer's recurring review (Doug, 2026-11-19: "have the UI expert look at card
access from /ops and evaluate for UX - this is something that I will want to do on a recurring basis"; "have it keep
track of what it looked at so the recurring runs don't repeat").

    python -X utf8 tools/card_access.py pick [--days 7] [--top 8]     # this run's cards and the week's access
    python -X utf8 tools/card_access.py record FINDINGS.json           # the designer's findings into the ledger
    python -X utf8 tools/card_access.py fixed CARD_ID [CARD_ID ...]    # a fix landed: look again next run

Counts only, as /ops keeps them: which cards engaged readers opened, which card sections, where readers came from,
on what device. Nothing about any one reader exists to be read. The ledger
(docs/review/card-access/ledger.json) holds every card the designer has looked at, with the date, the commit and the
findings; `pick` skips them, except a card marked `recheck` by `fixed`, which comes first so the fix is seen.
"""
import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "review" / "card-access"
LEDGER = DIR / "ledger.json"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "app2"))


def token_file():
    """the ops token lives at the main checkout's root (git ignores it); a worktree has none of its own"""
    for p in (ROOT / ".ops-token", *(q / ".ops-token" for q in ROOT.parents)):
        if p.exists():
            return p
    sys.exit("no .ops-token found (python tools/ops_report.py --new-token makes one)")


def load_ledger():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"cards": {}, "runs": []}


def save_ledger(led):
    DIR.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def head():
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def pick(days, top):
    import ops_report
    import server as S
    rep = ops_report.fetch(ops_report.SITE, days, token_file())
    ds = rep.get("days") or []
    tot = {k: Counter() for k in ("cards", "sections", "navigator", "referrers", "engaged_devices", "searches")}
    for d in ds:
        for k in tot:
            tot[k].update(d.get(k) or {})
    engaged = sum(d.get("engaged") or 0 for d in ds)
    g = S.load()
    led = load_ledger()
    seen = led["cards"]

    def info(cid):
        e = g["ents"].get(cid) or {}
        tgt = e.get("alias_of")
        return {"id": cid, "name": e.get("name") or cid, "kind": e.get("type") or "?", "merged_into": tgt,
                "relations": len(g["rels"].get(tgt or cid) or []), "opens": tot["cards"][cid],
                "local": f"http://localhost:8002/e/{cid}", "live": f"https://bibleontology.org/e/{cid}"}

    recheck = [info(c) for c, v in seen.items() if v.get("status") == "recheck"]
    fresh = [info(c) for c, _n in tot["cards"].most_common() if c not in seen]
    fresh = [x for x in fresh if not x["merged_into"]]
    chosen = (recheck + fresh)[:max(top, len(recheck))]
    today = date.today().isoformat()
    out = {"run": today, "days": [d.get("day") for d in ds], "engaged_readers": engaged, "commit": head(),
           "cards_opened": sum(tot["cards"].values()), "distinct_cards": len(tot["cards"]),
           "already_looked": sum(1 for c in tot["cards"] if c in seen),
           "this_run": chosen,
           "sections": tot["sections"].most_common(30), "navigator": tot["navigator"].most_common(15),
           "came_from": tot["referrers"].most_common(15), "devices": tot["engaged_devices"].most_common(),
           "searches": tot["searches"].most_common(25),
           "by_kind": Counter(info(c)["kind"] for c in tot["cards"]).most_common()}
    DIR.mkdir(parents=True, exist_ok=True)
    p = DIR / f"{today}-access.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(ds)} days, {engaged} engaged readers, {out['cards_opened']} card opens of {out['distinct_cards']} cards "
          f"({out['already_looked']} looked at before); this run: {len(chosen)} ({len(recheck)} to recheck) -> {p.name}")
    for x in chosen:
        print(f"  {x['opens']:>3}  {x['id']} ({x['kind']}, {x['relations']} relations)")


def record(path):
    """FINDINGS.json: {"run": "YYYY-MM-DD", "review": "docs/review/card-access/....md",
    "cards": {"<id>": {"findings": ["..."], "verdict": "fine|polish|urgent"}}}"""
    f = json.loads(Path(path).read_text(encoding="utf-8"))
    led, c = load_ledger(), head()
    for cid, v in f["cards"].items():
        prev = led["cards"].get(cid, {})
        led["cards"][cid] = {"looked": f["run"], "commit": c, "verdict": v.get("verdict"), "findings": v.get("findings", []),
                             "review": f.get("review"), "status": "looked",
                             "history": prev.get("history", []) + ([{k: prev[k] for k in ("looked", "verdict", "review")
                                                                      if k in prev}] if prev else [])}
    led["runs"].append({"run": f["run"], "review": f.get("review"), "cards": sorted(f["cards"]), "commit": c})
    save_ledger(led)
    print(f"ledger: {len(led['cards'])} cards looked at over {len(led['runs'])} runs")


def fixed(ids):
    led = load_ledger()
    for cid in ids:
        if cid not in led["cards"]:
            sys.exit(f"{cid} is not in the ledger")
        led["cards"][cid]["status"] = "recheck"
    save_ledger(led)
    print(f"marked for recheck: {', '.join(ids)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("pick"); a.add_argument("--days", type=int, default=7); a.add_argument("--top", type=int, default=8)
    b = sub.add_parser("record"); b.add_argument("findings")
    c = sub.add_parser("fixed"); c.add_argument("ids", nargs="+")
    x = ap.parse_args()
    {"pick": lambda: pick(x.days, x.top), "record": lambda: record(x.findings), "fixed": lambda: fixed(x.ids)}[x.cmd]()
