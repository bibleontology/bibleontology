"""Sweep word-closeness thresholds: at what closeness do patterns emerge?

2026-09-28: the point of a 90-minute budget is to experiment with the
closeness ranges to see at what thresholds patterns emerge. Runs the
miner once per threshold (words at least that close share a class, S) and
writes docs/review/PATTERN-SWEEP.md: per threshold, the classes, candidate
counts, cross-testament counts, and the top patterns that are NEW at that
threshold (not present at the stricter one before it).

    python tools/patterns/sweep.py
"""
import gzip
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools" / "builder"))
import mine  # noqa: E402
from source import norm  # noqa: E402

THRESHOLDS = [None, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.5]
LANG = {"H": "hebrew", "A": "hebrew", "G": "greek"}


def clusters(words, t):
    key = {w["id"]: (LANG.get(w["lang"], "?"), norm(w["lemma"])) for w in words}
    gl = {w["id"]: w.get("gloss") or w["lemma"] for w in words}
    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x
    for w in words:
        for kind in ("all", "cross"):
            for nid, s in (w.get("near") or {}).get(kind) or []:
                if s >= t and nid in key and w["cls"] in ("noun", "verb"):
                    a, b = find(w["id"]), find(nid)
                    if a != b:
                        parent[a] = b
    groups = {}
    for i in key:
        groups.setdefault(find(i), []).append(i)
    sim, label = {}, {}
    for root, ms in groups.items():
        if len(ms) < 2 or len(ms) > 40:
            continue
        cid = len(label)
        label[cid] = "/".join(sorted({gl[m] for m in ms})[:4])
        for m in ms:
            sim[key[m]] = cid
    return sim, label


def main():
    words = json.load(gzip.open(ROOT / "out" / "wordpage-data.json.gz", "rt",
                                encoding="utf-8"))["words"]
    rep = ["# Pattern sweep — word closeness thresholds", "",
           "Made by `tools/patterns/sweep.py` (Doug, 2026-09-28: \"experiment "
           "with the closeness ranges to see at what thresholds patterns "
           "emerge\"). ~{a/b} is a class of similar words.", ""]
    prev = set()
    for t in THRESHOLDS:
        t0 = time.time()
        if t is None:
            mine.SIM, mine.SIM_LABEL, mine.OUT_TAG = {}, {}, "-sim-none"
        else:
            mine.SIM, mine.SIM_LABEL = clusters(words, t)
            mine.OUT_TAG = f"-sim{t}"
        mine.main()
        rows = [json.loads(l) for l in gzip.open(
            ROOT / "out" / f"pattern-candidates{mine.OUT_TAG}.jsonl.gz", "rt",
            encoding="utf-8")]
        pats = {r["pattern"] for r in rows}
        new = [r for r in rows if r["pattern"] not in prev and "~{" in
               r["pattern"] and not r["kind"].startswith("formula")]
        cross = sum(1 for r in rows if r["testaments"] == "OT+NT")
        rep += [f"## threshold {t}", "",
                f"classes {len(set(mine.SIM.values()))}, words in classes "
                f"{len(mine.SIM)}; candidates {len(rows):,}; "
                f"cross-testament {cross:,}; new with a similar-word class "
                f"{len(new):,}; {time.time() - t0:.0f}s", "",
                "| score | support | books | testaments | pattern |",
                "|---|---|---|---|---|"]
        for r in new[:30]:
            rep.append(f"| {r['score']} | {r['support']} | {r['books']} | "
                       f"{r['testaments']} | {r['pattern'][:110]} |")
        rep.append("")
        prev = pats
        (ROOT / "docs" / "review" / "PATTERN-SWEEP.md").write_text(
            "\n".join(rep) + "\n", encoding="utf-8")
        print(f"threshold {t} done", flush=True)


if __name__ == "__main__":
    main()
