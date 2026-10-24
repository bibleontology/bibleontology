"""Convert the KJV quotations embedded in overlay prose, span by span.

Job A converted entity NAMES. This converts the quotations inside `desc` and
`note` -- the passages the overlay quotes while making its argument. After Job A
the graph says *the whole armor of God* in its names and *"Put on the whole
armour of God, that ye may be able to stand"* in its prose.

## Why this is verifiable after all

It was said earlier that no substring test covers prose. That is true of a whole
note and **false of the quotations inside it**: each is delimited and carries its
own citation, so each is the Job A problem again -- find the BSB rendering of
this span at this verse, and accept it only if it appears there.

    entity desc     5,635 rows with the field    789 carry a quoted span + ref
    relation note  12,702 rows with the field  1,271 carry a quoted span + ref
                                                 ~2,386 spans in total

Quotations with no citation attached are left alone. They cannot be checked, and
an unverifiable edit to prose is exactly the kind this project does not make.

## The risk Job A did not have

Replacing a span INSIDE a sentence can orphan the sentence around it -- if the
note says *"note the word 'charity' here"* and the quotation becomes *love*, the
commentary no longer matches. Two mitigations: the whole original field is kept
as `desc_kjv` / `note_kjv`, and only the quoted span is touched, never the prose.
A wrong edit is visible and reversible in one field on one row.

    $env:GEMINI_API_KEY = "..."
    python tools/bsbprose.py --limit 20     # look first
    python tools/bsbprose.py --apply
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import glob
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from genusage import Usage, config as _cfg   # noqa: E402
from bsbconvert import norm, verses, vkey                     # noqa: E402

USAGE = Usage()
CFG = None
MODEL = "gemini-flash-latest"
QUEUE = ROOT / "out" / "bsb-prose-review.jsonl"
TARGETS = [("ontology/entities/entities.jsonl", "desc")] + \
          [(p, "note") for p in sorted(glob.glob("ontology/relations/*.jsonl"))]

# a quotation of at least a dozen characters, immediately followed by its ref
QUOTE = re.compile(r"([‘'\"“])([^’'\"”]{12,400})([’'\"”]\s*\()([\w\d]+ \d+:\d+)")

PROMPT = """Rewrite this King James quotation in the wording the Berean \
Standard Bible uses for the SAME passage.

BSB text of {ref}: {bsb}

KJV quotation: "{quote}"

Reply with ONLY the corresponding span of the BSB text above, copied exactly. \
Do not paraphrase, do not add words, do not explain. If the BSB text does not \
cover it, reply exactly: NONE"""


def spans(kjv, bsb):
    """-> [(path, lineno, field, quote, ref, bsbtext)] every checkable quotation."""
    out = []
    for path, field in TARGETS:
        p = ROOT / path
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(d, dict) or not d.get(field):
                continue
            for _o, quote, _c, ref in QUOTE.findall(d[field]):
                k = vkey(ref)
                if k and k in bsb:
                    out.append((path, i, field, quote, ref, bsb[k]))
    return out


def verified(proposal, bsbtext):
    """Same guarantee as Job A: it must exist in the BSB text of THAT verse."""
    # BSB uses CURLY quotes for speech, so a returned span routinely opens or
    # closes with one. `norm()` ignores punctuation, so such a span verifies --
    # and then embeds a stray quote mark inside an already-quoted passage:
    #   '"Tell me, what can I do for you..." (2Kgs 2:9)
    # Caught in the 20-item sample; it would otherwise have landed in up to
    # 2,386 places.
    p = (proposal or "").strip()
    p = p.strip("\"'“”‘’").strip()
    if not p or p.upper() == "NONE" or len(p) > 500:
        return None
    return p if norm(p) and norm(p) in norm(bsbtext) else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--think", action="store_true",
                    help="allow the model to deliberate; billed as output")
    a = ap.parse_args()
    if not os.environ.get("GEMINI_API_KEY"):
        print('GEMINI_API_KEY not set.  PowerShell:  $env:GEMINI_API_KEY = "..."')
        return 2

    kjv, bsb = verses("verses.jsonl"), verses("verses.bsb.jsonl")
    work = spans(kjv, bsb)
    if a.limit:
        work = work[:a.limit]
    print(f"quotations to convert: {len(work):,}   model {MODEL}", flush=True)

    global CFG
    CFG = _cfg(think=a.think)
    from google import genai
    client = genai.Client()

    def ask(item):
        path, i, field, quote, ref, bsbtext = item
        try:
            r = client.models.generate_content(
                config=CFG,
                model=MODEL,
                contents=PROMPT.format(ref=ref, bsb=bsbtext, quote=quote))
            USAGE.add(r)
            return item, (r.text or "").strip()
        except Exception as ex:                                # noqa: BLE001
            return item, f"__ERROR__ {ex}"

    fixes, rejected, errors = {}, [], 0
    done = 0
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for item, resp in ex.map(ask, work):
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(work)}  accepted {sum(len(v) for v in fixes.values())}",
                      flush=True)
            path, i, field, quote, ref, bsbtext = item
            if resp.startswith("__ERROR__"):
                errors += 1
                continue
            good = verified(resp, bsbtext)
            if good:
                fixes.setdefault((path, i, field), []).append((quote, good))
            else:
                rejected.append({"path": path, "ref": ref, "quote": quote,
                                 "proposed": resp})

    n_ok = sum(len(v) for v in fixes.values())
    print(f"\n  accepted (verified in BSB)  {n_ok:>6,}  "
          f"{100*n_ok/max(len(work),1):5.1f}%")
    print(f"  rejected (queued)           {len(rejected):>6,}")
    print(f"  errors                      {errors:>6,}")
    for (p_, i_, f_), v in list(fixes.items())[:5]:
        q, g = v[0]
        print(f"     {q[:44]:<46} -> {g[:44]}")

    print(USAGE.report())

    QUEUE.parent.mkdir(exist_ok=True)
    with QUEUE.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"_note": "Quotations whose BSB rendering did not "
                                     "verify. Nothing here was written."}) + "\n")
        for r in rejected:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  queued -> {QUEUE.relative_to(ROOT)}")

    if not a.apply:
        print("\nnot written -- pass --apply")
        return 0

    for path, field in TARGETS:
        p = ROOT / path
        if not p.exists():
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        touched = 0
        for i, line in enumerate(lines):
            v = fixes.get((path, i, field))
            if not v or not line.strip():
                continue
            d = json.loads(line)
            text = d.get(field) or ""
            before = text
            for quote, good in v:
                text = text.replace(quote, good)
            if text != before:
                d.setdefault(f"{field}_kjv", before)   # the whole original kept
                d[field] = text
                lines[i] = json.dumps(d, ensure_ascii=False)
                touched += 1
        if touched:
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"  {path}: {touched:,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
