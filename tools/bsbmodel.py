"""The verified model pass: the 2,418 overlay names a word map cannot reach.

`tools/bsbconvert.py` settled 51 names deterministically and measured the rest.
This handles the residue, under one rule that makes a model acceptable here:

    **A proposal is written only if it appears verbatim in the BSB text of a
    verse the entity already cites.** Anything else is queued, never written.

That is the same substring test that FOUND these 2,418 in the first place, so
the check is the measurement run backwards and costs nothing. It is why a
non-deterministic tool is safe for this job and would not be safe for a stamp:
a stamp is a claim, and a claim has nothing to be checked against.

A fuzzy-similarity pass was tried and rejected (see `bsbconvert.py`): at any
threshold loose enough to catch *colours -> colors* it also accepted
*"a dead man" -> "a dream and"*.

## Cost

~2,418 items, roughly 180 input and 25 output tokens each. On Gemini 3.8 Flash
batch rates ($0.375 / $1.875 per 1M) that is about **$0.35**. Synchronous rates
double it. Either is a rounding error against a $10 budget, so this runs
synchronously with a small thread pool for immediate feedback rather than
through the batch API's upload-and-poll cycle.

    $env:GEMINI_API_KEY = "..."            # PowerShell, this shell only
    python tools/bsbmodel.py --limit 20    # try twenty first
    python tools/bsbmodel.py --apply       # convert what verifies
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from genusage import Usage, config as _cfg   # noqa: E402
from bsbconvert import (ENT, classify, norm, verses, vkey)   # noqa: E402

USAGE = Usage()
CFG = None
MODEL = "gemini-flash-latest"
QUEUE = ROOT / "out" / "bsb-name-review.jsonl"

PROMPT = """You are converting a phrase from the King James Version into the \
wording the Berean Standard Bible uses for the SAME phrase in the SAME verse.

KJV verse: {kjv}
BSB verse: {bsb}

KJV phrase: "{name}"

Reply with ONLY the span of the BSB verse above that renders that phrase. \
Copy it exactly from the BSB verse, including its own spelling and word order. \
Do not paraphrase, do not add words, do not explain. If the BSB verse does not \
render it, reply exactly: NONE"""


def build(ents, kjv, bsb):
    """-> [(entity, refs, prompt)] for the names needing conversion."""
    out = []
    for e, refs in classify(ents, kjv, bsb)["needs"]:
        r = next((x for x in refs if norm(e["name"]) in norm(kjv[x])), refs[0])
        out.append((e, refs, PROMPT.format(kjv=kjv[r], bsb=bsb[r], name=e["name"])))
    return out


STOPW = {"a", "an", "the", "of", "and", "in", "to", "is", "was", "that",
         "his", "her", "their", "my", "your", "with", "for", "he", "she"}


def _content(s):
    return [w for w in norm(s).split() if w not in STOPW]


def adequate(original, proposal):
    """Does the proposal still NAME the thing? Existence is not adequacy.

    The substring check alone accepted **"a dead man" -> "dead"**: the word is
    genuinely in the BSB verse, and the result is no longer a noun phrase. A
    100% accept rate was the tell -- a check that never rejects is not checking.

    **The first guard was worse than none.** It required the original's head
    word to survive, and queued *"a fugitive and a vagabond" -> "a fugitive and
    a wanderer"* -- a correct conversion. Replacing the head IS what translating
    does; the rule assumed the thing that changes stays the same.

    What is left is a shape rule that never looks at word identity: **a name of
    two or more content words may not collapse to one.** That is the actual
    damage in "a dead man" -> "dead", and it leaves synonym swaps alone however
    completely they replace the vocabulary.

    It queues "a certain man" -> "a man" too, which is an acceptable conversion.
    Conservative in the cheap direction: a queued good name costs a glance, a
    written bad one sits in the graph.
    """
    oc, pc = _content(original), _content(proposal)
    if not pc:
        return False
    return not (len(oc) >= 2 and len(pc) < 2)


def verified(proposal, refs, bsb, original=None):
    """The safety property: the span must EXIST in BSB and still NAME the thing."""
    p = (proposal or "").strip().strip('"').strip()
    if not p or p.upper() == "NONE" or len(p) > 300:
        return None
    if not any(norm(p) and norm(p) in norm(bsb[r]) for r in refs):
        return None
    if original is not None and not adequate(original, p):
        return None
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--think", action="store_true",
                    help="allow the model to deliberate; billed as output")
    a = ap.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY is not set in this shell.\n"
              "  PowerShell:  $env:GEMINI_API_KEY = \"...\"\n"
              "It is session-scoped, so it must be set in the shell that runs "
              "this.")
        return 2

    kjv, bsb = verses("verses.jsonl"), verses("verses.bsb.jsonl")
    ents = [json.loads(l) for l in ENT.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    ents = [e for e in ents if isinstance(e, dict) and e.get("name")]
    work = build(ents, kjv, bsb)
    if a.limit:
        work = work[:a.limit]
    print(f"to convert: {len(work):,}   model {MODEL}   workers {a.workers}",
          flush=True)

    global CFG
    CFG = _cfg(think=a.think)
    from google import genai
    client = genai.Client()

    def ask(item):
        e, refs, prompt = item
        try:
            r = client.models.generate_content(
                config=CFG,model=MODEL, contents=prompt)
            USAGE.add(r)
            return e, refs, (r.text or "").strip()
        except Exception as ex:                                # noqa: BLE001
            return e, refs, f"__ERROR__ {ex}"

    accepted, rejected, errors = [], [], []
    done = 0
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for e, refs, resp in ex.map(ask, work):
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(work)}  accepted {len(accepted)}",
                      flush=True)
            if resp.startswith("__ERROR__"):
                errors.append((e, resp))
                continue
            good = verified(resp, refs, bsb, original=e["name"])
            if good:
                accepted.append((e, good))
            else:
                rejected.append((e, resp))

    n = len(work)
    print(f"\n  accepted (verified in BSB)  {len(accepted):>6,}  "
          f"{100*len(accepted)/max(n,1):5.1f}%")
    print(f"  rejected (queued for Doug)  {len(rejected):>6,}")
    print(f"  errors                      {len(errors):>6,}")
    for e, g in accepted[:8]:
        print(f"     {e['name'][:38]:<40} -> {g[:38]}")

    print(USAGE.report())

    QUEUE.parent.mkdir(exist_ok=True)
    with QUEUE.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"_note": "Names the model proposed that did NOT "
                            "verify against the BSB text of a cited verse. "
                            "Nothing here was written to the overlay."}) + "\n")
        for e, resp in rejected:
            why = ("not found in the BSB verse"
                   if verified(resp, [r for r in (e.get("refs") or [])][:0] or [], {}) is None
                   and resp.strip().upper() != "NONE" else "model said NONE")
            f.write(json.dumps({"id": e["id"], "name": e["name"],
                                "refs": e.get("refs"), "proposed": resp,
                                "why": why},
                               ensure_ascii=False) + "\n")
    print(f"  queued -> {QUEUE.relative_to(ROOT)}")

    if not a.apply:
        print("\nnot written -- pass --apply")
        return 0

    fix = {e["id"]: g for e, g in accepted}
    out, changed = [], 0
    for line in ENT.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("id") in fix:
            d.setdefault("name_kjv", d["name"])      # never overwrite an original
            d["name"] = fix[d["id"]]
            changed += 1
        out.append(json.dumps(d, ensure_ascii=False))
    ENT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\nwrote {ENT.relative_to(ROOT)}  ({changed:,} converted, "
          f"ids untouched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
