"""DeepSeek's second, blind reading of the Mac's "yes" answers (jobs 35 and 36, 2026-11-19).

    python -X utf8 tools/pending/second_pass.py build     -> out/second-pass/batch-NNN.txt (10 questions each)
    python -X utf8 tools/pending/second_pass.py report    -> out/second-pass/agreed.json, the pairs both said "yes" to

Each question is the Mac's own question, word for word (Berean text and names only). DeepSeek is not told what the
Mac answered. A pair goes on for Claude's reading only if both say "yes"; where they differ it stays out.
"""
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "second-pass"
JOBS = {"place": (ROOT / "out" / "took-place-at-yes.json", ROOT / "out" / "grunt" / "jobs" / "35-took-place-at.jsonl"),
        "passage": (ROOT / "out" / "suggested-yes.json", ROOT / "out" / "grunt" / "jobs" / "36-suggested-passages.jsonl")}
HEAD = """You answer narrow questions about Bible verses (the Berean Standard Bible). Each question below is separate and
numbered; read each on its own. Return ONLY a JSON array, one object per question, in order:
[{"n": 1, "answer": "yes" or "no", "why": "the exact words that decide it"}, ...]

"""


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    items = []
    for kind, (yes, job) in JOBS.items():
        want = {r["key"] for r in json.load(open(yes, encoding="utf-8"))}
        for ln in list(open(job, encoding="utf-8"))[1:]:
            r = json.loads(ln)
            if r["key"] in want:
                q = r["messages"][0]["content"].split("Return ONLY")[0].strip()
                items.append({"kind": kind, "key": r["key"], "q": q})
    index = []
    for b in range(0, len(items), 10):
        chunk = items[b:b + 10]
        text = HEAD + "\n\n".join(f"=== QUESTION {i + 1} ===\n{it['q']}" for i, it in enumerate(chunk))
        (OUT / f"batch-{b // 10:03d}.txt").write_text(text, encoding="utf-8", newline="\n")
        index.append([{"kind": it["kind"], "key": it["key"]} for it in chunk])
    json.dump(index, open(OUT / "index.json", "w", encoding="utf-8"), indent=1)
    print(len(items), "questions in", len(index), "batches ->", OUT.relative_to(ROOT))


def report():
    index = json.load(open(OUT / "index.json", encoding="utf-8"))
    agreed, differ, missing = [], [], 0
    for b, chunk in enumerate(index):
        a = OUT / f"batch-{b:03d}.answer.txt"
        got = {}
        if a.exists():
            m = re.search(r"^\[.*\]", a.read_text(encoding="utf-8"), re.S | re.M)
            try:
                got = {x["n"]: x for x in json.loads(m.group(0))} if m else {}
            except ValueError:
                got = {}
        for i, it in enumerate(chunk):
            x = got.get(i + 1)
            if not x:
                missing += 1
            elif str(x.get("answer")).lower() == "yes":
                agreed.append({**it, "why": x.get("why")})
            else:
                differ.append({**it, "why": x.get("why")})
    json.dump({"agreed": agreed, "differ": differ}, open(OUT / "agreed.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    print(f"both yes {len(agreed)}, DeepSeek no {len(differ)}, unanswered {missing} -> out/second-pass/agreed.json")


if __name__ == "__main__":
    {"build": build, "report": report}[sys.argv[1]]()
