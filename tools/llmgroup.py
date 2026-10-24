"""Can a local model group verses from METADATA ALONE?

2026-09-09: if enough metadata can be surfaced, a grouping pass with a local
model might complete the work; start with the local Llama, with a comparison
to follow, at 3b.

**No Llama is installed.** Ollama holds qwen2.5 at 7b, 3b and 1.5b, so this
runs `qwen2.5:3b-instruct-q4_K_M` and the model is a parameter, which is what
the planned comparison will need anyway.

## The failure mode this is built to prevent

A model shown Psalm 103 produces a plausible grouping **from its own knowledge
of Psalm 103**, not from our metadata -- and it looks like success while proving
nothing. That is the same trap as two earlier results: a
57% recurrence figure that came from deleting word terms, and a 1.02x
pattern-fit test guaranteed by construction.

So the model is told nothing that identifies the passage:

    NOT GIVEN   the verse text, the reference, the book, any person's name,
                any allusion target, the number of groups expected
    GIVEN       per verse: colon count and word counts, discourse role and
                direction, quotation depth, thematic strength, how many
                allusion links it has, how many people it names, and how many
                of five editors put a paragraph break before it

## The ground truth, chosen because it cannot be guessed

**Psalm 119 is 22 acrostic stanzas of exactly 8 verses.** `tools/cola.py`
detects them with zero errors -- 22 runs of a shared opening letter, every one
of length 8 -- from the Hebrew consonants. A model that has not been told which
psalm this is has no way to reach that answer except through the metadata.

Scored two ways, both pre-registered: **boundary recall** against the 21
internal stanza starts, and **precision**, since a model that proposes a break
everywhere would score perfect recall and be worthless.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import unicodedata
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
OLLAMA = "http://127.0.0.1:11434/api/generate"


def load(name, pref=None):
    rows = []
    p = OUT / name
    if not p.exists():
        return rows
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            if pref and not str(d.get("ref", "")).startswith(pref):
                continue
            rows.append(d)
    return rows


def truth_119():
    """Stanza starts, from the acrostic. Ground truth, no editor involved."""
    W = re.compile(r"<w\s([^>]*?)/?>", re.S)
    A = re.compile(r'([\w:.-]+)="([^"]*)"', re.S)
    REF = re.compile(r"^([A-Z0-9]{3})\s+(\d+):(\d+)!(\d+)")
    f = next((ROOT / "data/raw/macula/hebrew").glob("*Psa-119-lowfat.xml"))
    byv = collections.defaultdict(list)
    for m in W.finditer(f.read_text(encoding="utf-8")):
        a = dict(A.findall(m.group(1)))
        r = REF.match(a.get("ref", "") or "")
        if r:
            byv[int(r.group(3))].append((int(r.group(4)), a))
    first = {}
    for v, ws in byv.items():
        for _, a in sorted(ws, key=lambda x: x[0]):
            got = None
            for ch in unicodedata.normalize("NFD", a.get("unicode") or ""):
                if "א" <= ch <= "ת":
                    got = ch
                    break
            if got:
                first[v] = got
                break
    starts, last = set(), None
    for v in sorted(first):
        if first[v] != last:
            starts.add(v)
        last = first[v]
    return starts, len(first)


def ask(model, prompt, timeout=900):
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": 0, "seed": 7, "num_ctx": 8192},
    }).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["response"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", default="qwen2.5:3b-instruct-q4_K_M")
    ap.add_argument("--passage", default="Psa.119")
    ap.add_argument("--show-prompt", action="store_true")
    a = ap.parse_args()

    pref = a.passage + "."
    sf = {int(d["ref"].split(".")[2]): d
          for d in load("sentence-function.jsonl.gz", pref)}
    co = {int(d["ref"].split(".")[2]): d for d in load("cola.jsonl.gz", pref)}
    th = {int(d["ref"].split(".")[2]): d
          for d in load("themespace.jsonl.gz", pref)}
    dp = {int(d["ref"].split(".")[2]): d
          for d in load("speech-depth.jsonl.gz", pref)}
    al = {int(d["ref"].split(".")[2]): d for d in load("allusions.jsonl.gz", pref)}
    pe = {int(d["ref"].split(".")[2]): d
          for d in load("people-xref.jsonl.gz", pref)}
    st = collections.Counter()
    for d in load("structure.jsonl.gz", pref):
        st[int(d["ref"].split(".")[2])] = d.get("agree", 0)

    vs = sorted(co)
    print(f"{a.passage}: {len(vs)} verses of metadata")

    lines = []
    for i, v in enumerate(vs, 1):
        c = co.get(v, {})
        s = sf.get(v, {})
        t = th.get(v, {})
        shape = "|".join(str(x["words"]) for x in c.get("cola", []))
        lines.append(
            f"{i:>3} cola={c.get('n','?')} words={shape:<9} "
            f"role={str(s.get('relation') or '-'):<12} "
            f"dir={str(s.get('direction') or '-'):<9} "
            f"depth={dp.get(v,{}).get('depth','-')} "
            f"strength={t.get('strength','-'):<5} "
            f"links={len(al.get(v,{}).get('links') or [])} "
            f"people={len(pe.get(v,{}).get('people') or [])} "
            f"editors={st.get(v,0)}")

    prompt = (
        "Below are rows of computed features, one per line, for a sequence of "
        "poetic lines. Line 1 is the first, and they are in order.\n\n"
        "Columns: cola = how many parts the line divides into; words = word "
        "count of each part; role = logical relation to its neighbour; dir = "
        "which way it points; depth = quotation nesting; strength = how "
        "distinctive its vocabulary is (0-1); links = how many other lines "
        "elsewhere share its wording; people = how many persons it names; "
        "editors = how many of five human editors began a paragraph here.\n\n"
        + "\n".join(lines) +
        "\n\nThe sequence divides into consecutive groups. Using ONLY the "
        "features above, give the line numbers that BEGIN each group.\n"
        "Answer with numbers separated by commas and nothing else."
    )

    if a.show_prompt:
        print(prompt[:1600])
        print("...\n")
    print(f"prompt: {len(prompt)} chars, asking {a.model} ...", flush=True)

    reply = ask(a.model, prompt)
    print(f"reply: {reply.strip()[:300]}")
    got = sorted({int(x) for x in re.findall(r"\d+", reply)
                  if 1 <= int(x) <= len(vs)})
    print(f"parsed {len(got)} boundaries: {got[:30]}")

    if a.passage != "Psa.119":
        print("\n(no ground truth for this passage -- Psa.119 is the test)")
        return 0

    starts, n = truth_119()
    idx = {v: i + 1 for i, v in enumerate(vs)}
    truth = sorted(idx[v] for v in starts if v in idx)
    print(f"\nGROUND TRUTH: {len(truth)} stanza starts (acrostic) {truth[:12]} ...")
    hit = sorted(set(got) & set(truth))
    print(f"  model found {len(hit)} of {len(truth)}: {hit[:12]}")
    rec = len(hit) / len(truth)
    prec = len(hit) / max(len(got), 1)
    print(f"  recall {100*rec:.1f}%   precision {100*prec:.1f}%")
    base = len(truth) / len(vs)
    print(f"  a rule firing {len(got)} times at random would hit "
          f"{len(got)*base:.1f}")
    print(f"  VERDICT: {'beats chance' if len(hit) > len(got)*base + 2 else 'AT OR BELOW CHANCE'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
