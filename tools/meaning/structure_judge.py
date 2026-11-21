"""Judge the apply step's candidate rows (structure_apply.py rows) blind, twice, by DeepSeek: for each, is the card
the very thing the verse speaks of, and does the verse state the relation? Written 2026-11-13, after the first
sample of the gated rows came back about half wrong: "Abijah bore Ashhur" wired to a card for the word "wife",
"Samuel took a stone" to Jacob's stone, "Solomon did evil" to a card for "mischief". The gates check the words;
only a reading checks the thing.

    python tools/meaning/structure_judge.py send A|B START STOP   one batch of 20 rows a call, labels sjudge-A-N
    python tools/meaning/structure_judge.py tally                  both runs read back: kept = right in both
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
BATCH = 20
ROWS = os.environ.get("SJ_ROWS", "rows.jsonl")      # rows-set2.jsonl: the 22 the title-stripping resolver added
SET = "" if ROWS == "rows.jsonl" else f"(SET-{ROWS})"
BRIEF = """You check proposed relations in a graph of the Bible (Berean Standard Bible). Each ROW gives a verse, a
relation as SOURCE -act-> TARGET, and the two graph cards it would connect, each with its name and a short
description. Decide each row on the verse alone:

  right       the verse states this act, by this doer, on this thing, AND each card is the very person or thing
              the verse speaks of (a card for that particular thing, or for the general kind of thing when the
              verse means the kind)
  wrong_card  either card is a different person or thing that only shares a word with the verse (a card for one
              particular stone used for any stone; a card for "wife" when the verse names a particular wife who is
              not that card; a card for an abstract word when the verse means something concrete)
  wrong_act   the cards are right but the act misstates what the verse says (reversed, negated, a different act,
              figurative read as literal)
  not_stated  the verse does not say this

Worked examples:
  Lev 8:10 "Moses took the anointing oil" | moses -took-> oil (card: oil, the general kind) -> right
  1Ch 2:24 "his wife Abijah bore to him Ashhur" | wife -mother_of-> ashhur (card: "wife", the general word) ->
    wrong_card (the mother is Abijah, a particular woman, not the general word)
  Ezk 19:14 "Fire has gone out from its main branch and devoured its fruit" | fire -ate-> fruit -> wrong_act
    (devoured by fire is consuming, not eating)

Return ONLY a JSON array, one object per row in order:
[{"n": <row number>, "verdict": "right|wrong_card|wrong_act|not_stated", "why": "a few words"}]
"""


def card(e, ents):
    x = ents.get(e) or {}
    d = (x.get("desc") or "").replace("\n", " ")[:160]
    return f"{x.get('name') or e} ({x.get('type')}){': ' + d if d else ''}"


def load():
    ents = {}
    for path in sorted((ROOT / "ontology" / "entities").glob("*.jsonl")):
        for line in open(path, encoding="utf-8"):
            e = json.loads(line)
            if e.get("id"):
                ents.setdefault(e["id"], e)
    rows = [json.loads(l) for l in open(OUT / ROWS, encoding="utf-8")]
    verses = {}
    for l in open(OUT / "resolved.jsonl", encoding="utf-8"):
        r = json.loads(l)
        b, c, v = r["ref"].split(".")
        verses[f"{b} {c}:{v}"] = (r.get("verse") or "").replace("«", "").replace("»", "")
    return ents, rows, verses


def send(run, start, stop):
    ents, rows, verses = load()
    env = dict(os.environ, PYTHONPATH="src", PYTHONIOENCODING="utf-8")
    for s in range(start, min(stop, len(rows)), BATCH):
        lines = []
        for i, r in enumerate(rows[s:s + BATCH]):
            ref = r["refs"][0]
            lines.append(f"ROW {s + i}: {ref} \"{verses.get(ref, '')}\"\n  {r['src']} -{r['type']}-> {r['dst']}\n"
                         f"  SOURCE card: {card(r['src'], ents)}\n  TARGET card: {card(r['dst'], ents)}")
        task = BRIEF + "\nROWS:\n" + "\n".join(lines)
        p = subprocess.run([sys.executable, "-m", "bibleont.delegate", "run", "--level", "2", "--blind", "--think",
                            "--label", f"sjudge-{run}-{s}", "--task", task], capture_output=True, text=True,
                           encoding="utf-8", env=env, cwd=ROOT)
        ok = p.returncode == 0 and '"verdict"' in p.stdout
        print(f"{run} {s}: {'OK' if ok else 'FAIL'}", flush=True)
        if not ok:
            print(p.stdout[-500:], p.stderr[-500:])
            return


def tally():
    ents, rows, verses = load()
    got = {"A": {}, "B": {}}
    for p in sorted(RES.glob("*.md")):
        t = p.read_text(encoding="utf-8", errors="replace")
        if "You check proposed relations in a graph of the Bible" not in t or "## Answer" not in t:
            continue
        task = t.split("## Answer", 1)[0]
        ans = t.split("## Answer", 1)[1].split("\n## Tool calls", 1)[0]
        if (SET and SET not in task) or (not SET and "(SET-" in task):
            continue
        run = "A" if "RUN-A" in task else "B" if "RUN-B" in task else None
        s, e = ans.find("["), ans.rfind("]")
        try:
            arr = json.loads(ans[s:e + 1])
        except ValueError:
            continue
        for x in arr:
            n = x.get("n")
            if isinstance(n, int) and run:
                got[run][n] = x
    import collections
    both = [n for n in got["A"] if n in got["B"]]
    c = collections.Counter((got["A"][n]["verdict"], got["B"][n]["verdict"]) for n in both)
    print(len(both), "rows judged by both;", c.most_common(10))
    keep = [rows[n] for n in sorted(both) if got["A"][n]["verdict"] == got["B"][n]["verdict"] == "right"]
    tag = ROWS.replace("rows", "").replace(".jsonl", "")
    (OUT / f"kept{tag}.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in keep), encoding="utf-8")
    (OUT / f"judged{tag}.json").write_text(json.dumps({"A": got["A"], "B": got["B"]}, ensure_ascii=False), encoding="utf-8")
    print(len(keep), "kept (right in both)")


if __name__ == "__main__":
    if sys.argv[1] == "send":
        BRIEF = BRIEF + f"\n(RUN-{sys.argv[2]}){SET}\n"
        send(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    else:
        tally()
