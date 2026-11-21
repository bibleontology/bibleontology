"""The third and fourth reads of the event cards' "Who did what" rows the Mac twice called not said (26-cast-check and
27-cast-reread, both "not_said"): DeepSeek, blind, twice. Written 2026-11-13. A row is held only when all four reads
agree the passage does not say it. "told" rows are left out: the Mac read a speech's label ("Isaac at Gen 27:35") as
the words spoken, so its "not said" there is the model's misreading, not the row's fault. Divine rows go to Doug.

    python tools/meaning/cast_judge.py send A|B     batches of 10, labels cjudge-A-N
    python tools/meaning/cast_judge.py tally        -> out/structure-apply/cast-hold.json
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "structure-apply"
RES = ROOT.parents[2] / ".delegate" / "results"
sys.stdout.reconfigure(encoding="utf-8")
BATCH = 10
BRIEF = """You check claims printed on a Bible study site against the passage each comes from (Berean Standard Bible).
Each CLAIM is SUBJECT - ACT - OBJECT. Decide each on its passage alone:

  stated     the passage says the subject does this act to the object, in these words or plainly equivalent ones
  implied    not said outright, but a plain reader takes it from the scene
  not_said   a different act, a different person or thing, the act only planned, asked for or refused, or the
             passage is about something else

A place may be named in a verse beside the cited one; a group acts when one of them acts for them.
Worked examples:
  CLAIM Joab - killed - Abner. "Joab stabbed him in the stomach, and he died" -> stated
  CLAIM Julius - imprisoned - Paul. "Paul and other prisoners were handed over to Julius ... Julius treated Paul
    with consideration" -> not_said (he guarded a prisoner handed to him)
  CLAIM Saul - died at - Mount Gilboa. "many fell slain on Mount Gilboa ... Saul fell on his sword" -> stated

Return ONLY a JSON array, one object per claim in order:
[{"n": <claim number>, "verdict": "stated|implied|not_said", "why": "a few words"}]
"""


def rows():
    return [r for r in json.load(open(OUT / "cast-candidates.json", encoding="utf-8")) if r["verb"] != "told"]


def send(run):
    rs = rows()
    env = dict(os.environ, PYTHONPATH="src", PYTHONIOENCODING="utf-8")
    for s in range(0, len(rs), BATCH):
        lines = [f"CLAIM {s + i}: {r['claim'].replace('CLAIM ', '')}\nPASSAGE:\n{r['verse']}" for i, r in
                 enumerate(rs[s:s + BATCH])]
        task = BRIEF + f"\n(CAST-RUN-{run})\n\n" + "\n\n".join(lines)
        p = subprocess.run([sys.executable, "-m", "bibleont.delegate", "run", "--level", "2", "--blind", "--think",
                            "--label", f"cjudge-{run}-{s}", "--task", task], capture_output=True, text=True,
                           encoding="utf-8", env=env, cwd=ROOT)
        ok = p.returncode == 0 and '"verdict"' in p.stdout
        print(f"{run} {s}: {'OK' if ok else 'FAIL'}", flush=True)
        if not ok:
            print(p.stdout[-400:], p.stderr[-400:])
            return


def tally():
    rs = rows()
    got = {"A": {}, "B": {}}
    for p in sorted(RES.glob("*.md")):
        t = p.read_text(encoding="utf-8", errors="replace")
        if "(CAST-RUN-" not in t or "## Answer" not in t:
            continue
        run = "A" if "(CAST-RUN-A)" in t else "B"
        ans = t.split("## Answer", 1)[1].split("\n## Tool calls", 1)[0]
        s, e = ans.find("["), ans.rfind("]")
        try:
            for x in json.loads(ans[s:e + 1]):
                if isinstance(x.get("n"), int):
                    got[run][x["n"]] = x
        except ValueError:
            continue
    import collections
    c = collections.Counter((got["A"].get(n, {}).get("verdict"), got["B"].get(n, {}).get("verdict")) for n in range(len(rs)))
    print(len(rs), "rows;", c.most_common())
    hold = [dict(rs[n], a=got["A"][n], b=got["B"][n]) for n in range(len(rs))
            if got["A"].get(n, {}).get("verdict") == got["B"].get(n, {}).get("verdict") == "not_said"]
    json.dump(hold, open(OUT / "cast-hold.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(hold), "to hold (all four reads not said)")


if __name__ == "__main__":
    send(sys.argv[2]) if sys.argv[1] == "send" else tally()
