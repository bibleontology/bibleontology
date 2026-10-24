"""Is a computed link real? A benchmark with a key, across models.

The overnight run of 2026-09-10 asked a 3b to triage 1,500 of our top computed
links — quote, echo, stock formula, or unrelated — and **had no key**, so the
answer was a distribution and not a result.

It turns out a key existed and was not used. 93 of those 1,500 pairs are
**editorial cross-references**: links a BSB editor independently judged worth
printing. Scoring the old run against them retroactively:

                                  editor-linked    all 1,500
    A/B  real quote or echo            75%            34%
    D    not meaningfully related       5%            30%

A six-fold drop in the false-negative rate on known-good pairs. The 3b was
carrying real signal and nobody could see it.

## What this module does

Builds that key into a proper benchmark and runs any model against it.

    POSITIVES   editorial cross-reference verse pairs (17,527 available).
                An editor thought these belonged together, working from the
                text and not from anything we computed.
    NEGATIVES   random verse pairs. Overwhelmingly unrelated, and the few
                that are not are a known, measurable contamination rather
                than a guess.

One number comes out: **separation** — how much likelier a model is to call a
genuine pair related than a random one. Chance is 1.0x.

## Why it is worth running before spending anything

The architecture puts cheap models on the many low-level nodes and
expensive models on the few high-level ones. That only works if we know where
cheap stops tracking expensive, and that boundary is measurable for about a
dollar:

    1,000 pairs, ~800 tokens in and 10 out
    Gemini 3.1 Flash-Lite (batch)   ~$0.11
    Gemini 3.1 Pro        (batch)   ~$0.81

2.5-series models are CLOSED TO NEW USERS as of 2026-09-11 -- the API returns
404 "no longer available to new users" -- so the 2.5 prices quoted elsewhere
are not reachable on a new key.

against a full-corpus triage of all 161,201 computed links at $6.77 on
Flash-Lite or $88.60 on Pro. **Learn the boundary at $0.55 rather than
discover it at $88.**

## Backends

`--backend ollama` runs locally and free. `--backend gemini` needs
`GEMINI_API_KEY` in the environment; it is deliberately SYNCHRONOUS, because
the Batch API is not available on Google's free tier — the batch rate-limit
table has no free row. A thousand calls paced under the free tier's limits is
an overnight job, which is what this is.

**The prompt carries no methodology.** It asks a generic relatedness question
about public-domain text, which is why the free tier is an acceptable place to
run it. A prompt that encodes how this project reasons is not.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import os
import pathlib
import random
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "triage.jsonl"
OLLAMA = "http://127.0.0.1:11434/api/generate"
GEMINI = ("https://generativelanguage.googleapis.com/v1beta/models/"
          "{model}:generateContent")

BACK = {"Gen": "Gen", "Exo": "Exod", "Lev": "Lev", "Num": "Num", "Deu": "Deut",
        "Jos": "Josh", "Jdg": "Judg", "Rut": "Ruth", "1Sa": "1Sam",
        "2Sa": "2Sam", "1Ki": "1Kgs", "2Ki": "2Kgs", "1Ch": "1Chr",
        "2Ch": "2Chr", "Ezr": "Ezra", "Neh": "Neh", "Est": "Esth",
        "Job": "Job", "Psa": "Ps", "Pro": "Prov", "Ecc": "Eccl",
        "Sng": "Song", "Isa": "Isa", "Jer": "Jer", "Lam": "Lam",
        "Ezk": "Ezek", "Dan": "Dan", "Hos": "Hos", "Jol": "Joel",
        "Amo": "Amos", "Oba": "Obad", "Jon": "Jonah", "Mic": "Mic",
        "Nam": "Nah", "Hab": "Hab", "Zep": "Zeph", "Hag": "Hag",
        "Zec": "Zech", "Mal": "Mal", "Mat": "Matt", "Mrk": "Mark",
        "Luk": "Luke", "Jhn": "John", "Act": "Acts", "Rom": "Rom",
        "1Co": "1Cor", "2Co": "2Cor", "Gal": "Gal", "Eph": "Eph",
        "Php": "Phil", "Col": "Col", "1Th": "1Thess", "2Th": "2Thess",
        "1Ti": "1Tim", "2Ti": "2Tim", "Tit": "Titus", "Phm": "Phlm",
        "Heb": "Heb", "Jas": "Jas", "1Pe": "1Pet", "2Pe": "2Pet",
        "1Jn": "1John", "2Jn": "2John", "3Jn": "3John", "Jud": "Jude",
        "Rev": "Rev"}


def load_text():
    t = {}
    for line in (ROOT / "data/bible/verses.bsb.jsonl").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            if "b" in d:
                t[(d["b"], d["c"], d["v"])] = d["t"]
    return t


def rows(name):
    p = OUT / name
    if not p.exists():
        return
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                if not any(k.startswith("_") for k in d):
                    yield d


def span(b, e):
    if not e:
        return [b]
    bb, bc, bv = b.split(".")
    _, _, ev = e.split(".")
    try:
        return [f"{bb}.{bc}.{v}" for v in range(int(bv), int(ev) + 1)]
    except ValueError:
        return [b]


def ask_ollama(model, prompt, timeout=240):
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0, "seed": 11,
                                   "num_ctx": 4096}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["response"].strip()


_CLIENT = None


def ask_gemini(model, prompt, timeout=120):
    """One call through the official SDK.

    Uses `client.interactions.create(...)`, which is the shape the current
    Gemini docs give. `genai.Client()` reads GEMINI_API_KEY from the
    environment on its own, so the key is never passed on a command line and
    never lands in shell history.

        pip install -U google-genai

    NOT VERIFIED AGAINST A LIVE KEY. Written from the documented signature;
    the first real run is the test. If the SDK is a version whose surface
    differs, the error will name the attribute rather than fail silently,
    which is the failure mode worth having.
    """
    global _CLIENT
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is not set in this shell. "
                           "PowerShell: $env:GEMINI_API_KEY = \"...\"")
    if _CLIENT is None:
        try:
            from google import genai
        except ImportError as e:
            # NAME THE INTERPRETER. "pip install -U google-genai" was written
            # 765 times against a machine where the package WAS installed --
            # just not for the python that `python` resolves to in that
            # shell. An error that does not say which interpreter looked
            # sends everyone to re-run an install that already worked.
            import sys
            raise RuntimeError(
                f"google-genai not importable by {sys.executable} "
                f"-- install it for THAT interpreter: "
                f'"{sys.executable}" -m pip install -U google-genai '
                f"(underlying: {e})") from e
        _CLIENT = genai.Client()
    out = _CLIENT.interactions.create(model=model, input=prompt)
    return (getattr(out, "output_text", "") or "").strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backend", choices=("ollama", "gemini"),
                    default="ollama")
    ap.add_argument("--model", default=None)
    ap.add_argument("--n", type=int, default=500,
                    help="pairs per class; 500 = 1,000 calls")
    ap.add_argument("--sleep", type=float, default=0.0,
                    help="seconds between calls, to stay under a rate limit")
    ap.add_argument("--tag", default=None, help="label for this run")
    a = ap.parse_args()
    model = a.model or ("qwen2.5:3b-instruct-q4_K_M" if a.backend == "ollama"
                        else "gemini-3.1-flash-lite")
    tag = a.tag or f"{a.backend}:{model}"

    text = load_text()

    def say(ref):
        b, c, v = ref.split(".")
        return text.get((BACK.get(b, b), int(c), int(v)), "")

    # ---- the key -----------------------------------------------------------
    pos = set()
    for d in rows("xrefs.jsonl.gz"):
        for t in span(d["to"], d.get("to_end")):
            if say(d["from"]) and say(t) and d["from"] != t:
                pos.add(tuple(sorted((d["from"], t))))
    # every verse we can quote, keyed the way the graph refers to it, for the
    # negative sample
    inv = {}
    for (b, c, v), t in text.items():
        for short, full in BACK.items():
            if full == b:
                inv[f"{short}.{c}.{v}"] = t
                break
    pool = sorted(inv)
    rng = random.Random(17)
    neg = set()
    while len(neg) < a.n * 2:
        x, y = rng.choice(pool), rng.choice(pool)
        k = tuple(sorted((x, y)))
        if x != y and k not in pos:
            neg.add(k)

    positives = rng.sample(sorted(pos), min(a.n, len(pos)))
    negatives = rng.sample(sorted(neg), a.n)
    cases = ([(p, "genuine") for p in positives]
             + [(n, "random") for n in negatives])
    rng.shuffle(cases)
    print(f"benchmark: {len(positives)} editorial pairs + {len(negatives)} "
          f"random pairs = {len(cases)} calls")
    print(f"backend {a.backend}  model {model}")

    done = set()
    if DEST.exists():
        for line in DEST.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    d = json.loads(line)
                    # ONLY A LABELLED ROW IS DONE. Error rows carry the same
                    # (tag, a, b) key, so counting them as completed made
                    # every failure permanent: 781 failed calls meant the
                    # next run skipped all 1,000 cases and exited silently,
                    # looking exactly like a successful run that had nothing
                    # left to do.
                    if d.get("label"):
                        done.add((d["tag"], d["a"], d["b"]))
                except Exception:
                    pass
        if done:
            print(f"already labelled, will skip: {len(done):,}")
    ask = ask_ollama if a.backend == "ollama" else ask_gemini
    fh = DEST.open("a", encoding="utf-8")
    t0 = time.time()
    seen = 0
    fatal = 0
    labels = collections.Counter()
    for i, ((x, y), truth) in enumerate(cases):
        if (tag, x, y) in done:
            continue
        p = (f"TEXT 1: {x} — {say(x)[:180]}\n"
             f"TEXT 2: {y} — {say(y)[:180]}\n\n"
             f"How are these two related?\n"
             f"A. One quotes the other\n"
             f"B. One echoes the other's wording without quoting\n"
             f"C. Both use a shared stock phrase or formula\n"
             f"D. Not meaningfully related\n\n"
             f"Answer with one letter only.")
        try:
            ans = ask(model, p)
        except Exception as e:
            msg = str(e)[:120]
            fh.write(json.dumps({"tag": tag, "a": x, "b": y, "truth": truth,
                                 "error": msg}) + "\n")
            fh.flush()
            # STOP ON A FAULT THAT WILL NOT FIX ITSELF. A missing package or
            # an unset key fails identically on every one of a thousand calls;
            # the first run wrote the same "pip install -U google-genai" 759
            # times and looked like progress. A rate limit is the opposite --
            # it clears on its own, so those keep going.
            fatal += 1
            if fatal >= 3 and seen == 0:
                print(f"\n  ABORTED after {fatal} failures and no successes.")
                print(f"  {msg}")
                print("  Nothing here will change by retrying; fix it and "
                      "re-run. Completed work is kept and skipped.")
                break
            if a.sleep:
                time.sleep(a.sleep)
            continue
        fatal = 0
        got = next((ch for ch in ans.upper() if ch in "ABCD"), "?")
        labels[got] += 1
        seen += 1
        fh.write(json.dumps({"tag": tag, "a": x, "b": y, "truth": truth,
                             "label": got}, ensure_ascii=False) + "\n")
        fh.flush()
        if a.sleep:
            time.sleep(a.sleep)
        if (i + 1) % 50 == 0:
            el = time.time() - t0
            print(f"  {i+1}/{len(cases)}  {el/(i+1):.2f}s/call  {dict(labels)}",
                  flush=True)
    fh.close()
    print(f"\nwrote {DEST.relative_to(ROOT)}  (tag {tag})")
    print("score every run so far with:  python tools/triage.py --score")
    return 0


def score():
    if not DEST.exists():
        print("nothing to score yet")
        return 0
    by = collections.defaultdict(lambda: collections.defaultdict(
        collections.Counter))
    err = collections.Counter()
    for line in DEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("error"):
            err[d["tag"]] += 1
            continue
        by[d["tag"]][d["truth"]][d["label"]] += 1
    print("SEPARATION — how much likelier is a model to call a GENUINE pair")
    print("related than a RANDOM one? chance = 1.00x\n")
    print(f"  {'model':<34}{'genuine':>9}{'random':>9}{'separation':>12}")
    # A TAG WITH NOTHING BUT ERRORS MUST STILL PRINT A LINE. The first
    # version skipped any tag lacking scoreable rows, so a Gemini run in which
    # all 759 calls failed on a missing SDK showed as nothing at all -- the
    # report looked healthy because the broken run was invisible.
    for tag in sorted(set(by) | set(err)):
        t = by.get(tag, {})
        g, r = t.get("genuine", {}), t.get("random", {})
        gn, rn = sum(g.values()), sum(r.values())
        if not gn and not rn:
            print(f"  {tag:<34}{'--':>8}{'--':>8}  NO SCOREABLE ROWS"
                  f"   ({err.get(tag,0)} errors)")
            continue
        if not gn or not rn:
            print(f"  {tag:<34}   only one class present -- not scoreable"
                  f"   ({err.get(tag,0)} errors)")
            continue
        grel = (g.get("A", 0) + g.get("B", 0)) / gn
        rrel = (r.get("A", 0) + r.get("B", 0)) / rn
        # A ratio against zero is not "infinitely good" -- a model that says
        # "unrelated" to almost everything scores inf and is useless. The
        # 3b did exactly that: 1.7% of genuine pairs called related, 0% of
        # random. Report the rates and let them speak; only call it a
        # separation when the model actually says yes to something.
        if grel < 0.10:
            verdict = "  says NO to nearly everything"
        elif not rrel:
            verdict = f"  >{grel/(1/max(rn,1)):.0f}x (no random positives)"
        else:
            verdict = f"  {grel/rrel:.2f}x"
        print(f"  {tag:<34}{100*grel:>8.1f}%{100*rrel:>8.1f}%{verdict}"
              + (f"   ({err[tag]} errors)" if err.get(tag) else ""))
    print("\n  'related' = labelled A (quotes) or B (echoes).")
    print("  A model at 1.00x is guessing. The editorial pairs are a HARD")
    print("  positive set: an editor printed them, which does not guarantee")
    print("  shared wording, so 100% is not the target.")
    return 0


if __name__ == "__main__":
    import sys
    if "--score" in sys.argv:
        raise SystemExit(score())
    raise SystemExit(main())
