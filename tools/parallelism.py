"""Sort Hebrew poetic couplets into synonymous and antithetical, resumably.

The machine is needed the next day, so the job must be pausable at any time
and save its place.

That is the whole design here. **Every answer is appended the moment
it is produced**, and a restart reads what is already on disk and skips it. Kill
it at any point, including mid-item; the worst case is one couplet redone. A
seven-hour job becomes seven one-hour jobs if that is what the day allows.

This is the lesson from 2026-09-02, when an unattended run lost eleven of
twelve probes and the log could not say why, because results were written at
the end and the return code was never recorded.

## Why this job is worth a night

The graph holds **8 `distinguished_from` edges** in 15,023 relations. Contrast
is what stops antonyms floating to the top of any similarity measure -- an
issue is that opposites would actually be semantically similar. Without
negative anchors a correlation design has nothing to push down with.

Hebrew parallelism supplies both anchor sets from one mechanism. The athnach
splits a verse into two cola deterministically; whether the second restates the
first or contradicts it is the one judgement a rule cannot make. **21,479
splittable couplets** exist across the poetic books.

## The gold set, and why it is only rough

Proverbs 10-15 is antithetical by long consensus -- almost every verse runs
"the righteous X, but the wicked Y". Psalms is predominantly synonymous. Neither
holds universally, so `--probe` measures a tendency, and a model that always
answers one way scores 50% overall while looking perfect on half the set.

**That is not hypothetical.** The untuned qwen2.5:3b answered OPPOSITE 33 times
out of 36: a flawless 18/18 on Proverbs and 3/18 on Psalms. Forty seconds of
probing saved two hours of confident nonsense. Run `--probe` before `--run`,
every time, on every model.

    python tools/parallelism.py --probe                    # 36 items, ~1 min
    python tools/parallelism.py --probe --model=qwen2.5:7b-instruct-q4_K_M
    python tools/parallelism.py --run --limit=500          # resumable
    python tools/parallelism.py --status
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from markers import corpus, words                                # noqa: E402

ATH = "֑"
OUT = ROOT / "out" / "parallelism.jsonl"
DEFAULT_MODEL = "qwen2.5:3b-instruct-q4_K_M"

POETIC = {"Ps", "Prov", "Job", "Isa", "Jer", "Ezek", "Hos", "Joel", "Amos",
          "Obad", "Jonah", "Mic", "Nah", "Hab", "Zeph", "Zech", "Mal", "Lam",
          "Song", "Eccl"}

# On the first framing: the contradicts are not contradictions if they
# are talking about an opposite group having an opposite experience, so the
# framing was confusing; it was wrong for the model too. In
#     "The hope of the righteous shall be gladness,
#      but the expectation of the wicked shall perish"
# nothing is contradicted -- both halves are asserted, about DIFFERENT
# subjects, with mirrored outcomes. That is what antithetical parallelism is,
# and calling it contradiction makes the right answer look wrong.
SYSTEM = """You compare the two halves of a line of Hebrew poetry.

Answer with ONE word and nothing else:

  RESTATE   the second half says the same thing again in different words
  CONTRAST  the second half sets an opposite case beside the first --
            usually a different subject with a mirrored outcome. Both halves
            are true; they are not contradicting each other.
  ADVANCE   the second half carries the thought forward: a consequence, a
            reason, a completion

Judge the relation between the halves, not the wording."""


SPLIT = re.compile(r"\s*[:;]\s+")


def couplets() -> list:
    """Every poetic couplet, split at the caesura the translators marked.

    **This reads English, and that decision is the whole result.** The first
    version fed the models interlinear glosses -- Hebrew word order, slashes,
    truncated fragments. Proverbs 10:2 arrived as

        "they profit treasures of wickedness" || "and/ righteousness it delivers from/ d"

    On that, the 3B scored 24/36 and the 7B 20/36, both by answering OPPOSITE
    almost every time. I concluded local models could not do the task. The
    conclusion was wrong: doubling the model made it *worse*, which is the
    signature of bad input rather than a weak model.

    The same verse in the KJV:

        "Treasures of wickedness profit nothing" || "but righteousness delivereth from death"

    On that the 3B scores 27/36 with a genuine spread -- 72% of Proverbs
    antithetical, 77% of Psalms synonymous -- and it beats the 7B while running
    at 0.8s against 2.0s.

    This is the finding from the blind pair sheet, arriving again: the same
    rating would have come from the words alone, but the dictionary
    definitions pushed the scoring onto a tougher curve. **The input format sets
    the answer.**

    Cost of the switch: English punctuation is not the athnach, so coverage
    drops from 9,350 couplets to 5,736 -- 58% of poetic verses. Better input on
    fewer verses beats noise on all of them. The athnach remains the right
    split for anything read in Hebrew.
    """
    from bibleont.decompose import _load
    kjv = _load("verses.jsonl")
    out = []
    for ref, txt in sorted(kjv.items()):
        m = re.match(r"([1-3]?[A-Za-z]+) ", ref)
        if not m or m.group(1) not in POETIC:
            continue
        parts = [p for p in SPLIT.split(txt.strip()) if len(p.split()) >= 3]
        if len(parts) >= 2:
            out.append({"ref": ref, "a": parts[0], "b": " ".join(parts[1:])})
    return out


def ask(a: str, b: str, model: str) -> str:
    body = json.dumps({
        "model": model, "system": SYSTEM,
        "prompt": f"First half: {a}\nSecond half: {b}\n\nAnswer:",
        "stream": False,
        "options": {"temperature": 0, "num_predict": 6, "num_ctx": 2048},
    }).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate",
                                 data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        t = (json.loads(r.read()).get("response") or "").upper()
    m = re.search(r"\b(RESTATE|CONTRAST|ADVANCE)\b", t)
    return m.group(1) if m else "?"


def done() -> dict:
    """What is already on disk. This is what makes a pause free."""
    if not OUT.exists():
        return {}
    out = {}
    with OUT.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
                out[d["ref"]] = d
            except Exception:                                    # noqa: BLE001
                continue                      # a half-written final line
    return out


def _num(ref):
    """Sort a reference the way the canon runs, not the way ASCII does.

    Sorting "Ps 10:1" before "Ps 2:1" drew the probe's Psalms sample from
    chapters 1, 10, 11, 12 rather than 1, 2, 3, 4 -- and scored 19/36 where the
    canonical sample scored 27/36, same model, same task. A swing that large on
    n=36 says the probe was too small to settle anything, so it is now 120.
    """
    m = re.match(r"([1-3]?[A-Za-z]+) (\d+):(\d+)", ref)
    return (m.group(1), int(m.group(2)), int(m.group(3))) if m else (ref, 0, 0)


def probe(model: str, n: int = 60) -> int:
    """Measure against the rough gold set before spending a night."""
    cs = sorted(couplets(), key=lambda c: _num(c["ref"]))
    prov = [c for c in cs if c["ref"].startswith("Prov ")
            and 10 <= int(c["ref"].split(" ")[1].split(":")[0]) <= 15][:n]
    psa = [c for c in cs if c["ref"].startswith("Ps ")
           and int(c["ref"].split(" ")[1].split(":")[0]) <= 50][:n]
    print(f"{len(cs):,} couplets available. Probing {model}\n")
    t0, tally = time.time(), collections.Counter()
    for label, batch, expect in (("Prov 10-15", prov, "CONTRAST"),
                                 ("Psa 1-50", psa, "RESTATE")):
        got = collections.Counter()
        for c in batch:
            got[ask(c["a"], c["b"], model)] += 1
        n, hit = sum(got.values()), got[expect]
        tally[expect] = hit
        print(f"  {label:12} {hit}/{n} matched the prior "
              f"({100 * hit // max(n, 1)}%)   {dict(got)}")
    total = sum(tally.values())
    per = (time.time() - t0) / 36
    print(f"\n  overall {total}/36. A model that always answered one way "
          f"would score 18/36.")
    if total <= 22:
        print("  VERDICT: too close to a constant. Do not spend the night.")
    else:
        print(f"  VERDICT: a real spread. {len(cs) * per / 3600:.1f} hours "
              f"for all {len(cs):,}.")
    return 0


def run(model: str, limit: int) -> int:
    cs = couplets()
    have = done()
    todo = [c for c in cs if c["ref"] not in have]
    if limit:
        todo = todo[:limit]
    print(f"{len(cs):,} couplets, {len(have):,} already done, "
          f"{len(todo):,} this run. Ctrl-C is safe.\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    t0, n = time.time(), 0
    # What will likely happen is that the machine goes to sleep and the job
    # resumes when it picks up. A sleeping laptop suspends this process mid-request;
    # on wake the socket is dead and ollama may have unloaded the model. So a
    # failure is retried rather than fatal, with a widening wait -- the first
    # request after a wake is slow because the model reloads from disk.
    # Nothing is lost either way, since every line is flushed, but retrying is
    # the difference between resuming by itself and resuming when noticed.
    misses = 0
    try:
        with OUT.open("a", encoding="utf-8") as fh:
            for c in todo:
                v = None
                for attempt in range(4):
                    try:
                        v = ask(c["a"], c["b"], model)
                        break
                    except KeyboardInterrupt:
                        raise
                    except Exception as exc:                     # noqa: BLE001
                        if attempt == 0:
                            print(f"  paused? {type(exc).__name__} — waiting "
                                  f"for ollama", flush=True)
                        time.sleep(5 * (attempt + 1) ** 2)
                if v is None:
                    misses += 1
                    if misses >= 20:
                        print("  20 consecutive failures — stopping. "
                              "Is ollama running? Re-run to continue.")
                        break
                    continue
                misses = 0
                fh.write(json.dumps({**c, "v": v, "model": model}) + "\n")
                fh.flush()                    # the line that makes a pause free
                n += 1
                if n % 25 == 0:
                    el = time.time() - t0
                    print(f"  {n:>6}/{len(todo)}  {el/n:.1f}s each  "
                          f"{(len(todo)-n)*el/n/3600:.1f}h left", flush=True)
    except KeyboardInterrupt:
        print(f"\n  stopped after {n}. Re-run to continue where it left off.")
    print(f"\n{n} done this run, {len(have)+n:,} total -> {OUT}")
    return 0


def status() -> int:
    have = done()
    if not have:
        print("nothing done yet")
        return 0
    c = collections.Counter(d["v"] for d in have.values())
    bk = collections.Counter(r.rsplit(" ", 1)[0] for r in have)
    print(f"{len(have):,} couplets judged")
    print(f"  verdicts: {dict(c)}")
    print(f"  books: {dict(bk.most_common(8))}")
    tot = sum(c.values())
    if tot and max(c.values()) / tot > 0.85:
        print("  WARNING: over 85% one answer -- check this is not a constant")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    model = next((a.split("=", 1)[1] for a in argv
                  if a.startswith("--model=")), DEFAULT_MODEL)
    limit = int(next((a.split("=", 1)[1] for a in argv
                      if a.startswith("--limit=")), "0"))
    if "--status" in argv:
        return status()
    if "--run" in argv:
        return run(model, limit)
    if "--probe" in argv:
        return probe(model, int(next((a.split("=", 1)[1] for a in argv
                                      if a.startswith("--n=")), "60")))
    print(__doc__.strip().rsplit("\n\n", 1)[-1])
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
