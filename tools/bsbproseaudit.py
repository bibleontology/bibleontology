"""Re-check the prose conversion from scratch, and repair what the run got wrong.

`bsbprose.py --apply` ran on 2026-09-13 and wrote 1,669 rows. **It ran on code
that predated two of its own fixes** -- the process imported its modules before
the curly-quote strip (c29a281) and the usage report (749fa41) were written, so
what is on disk was produced by a version with a known defect and reported no
cost. Verifying a run with the same code that produced it proves nothing; this
re-derives every accepted span independently and repairs three separate faults.

## What it checks

1. **Does the span still verify?** Every quotation now in the prose must appear
   in the BSB text of the verse it cites. This is the run's own guarantee,
   re-run against the file rather than against the run's memory.
2. **Stray quote marks.** BSB uses curly quotes for speech, so an accepted span
   routinely carries one, and it lands INSIDE an already-quoted passage:

       'Tell me, what can I do for you before I am taken away from you?"
        "Please, let me inherit a double portion of your spirit,' Elisha replied.

   The outer quotation now contains two orphan marks and a speaker attribution
   that was never part of the quoted claim. Measured below, not estimated.
3. **Orphaned commentary.** The risk `bsbprose.py` named and did not test for:
   a note that says *note the word 'charity' here* is broken when the quotation
   becomes *love*. Short quoted words elsewhere in the same field are checked
   against the converted quotation.

## What it repairs

Only 1 and 2, and only by rule. A span that no longer verifies is **reverted**
to its KJV original -- the field keeps `*_kjv`, so the original is always in
hand and reversion is exact. Stray interior quote marks are stripped. Orphaned
commentary is REPORTED and never auto-edited: repairing it means rewriting
the commentary's argument, which is not a mechanical operation.

    python tools/bsbproseaudit.py            # measure
    python tools/bsbproseaudit.py --fix      # strip strays, revert failures
"""
from __future__ import annotations

import argparse
import glob
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from bsbconvert import norm, verses, vkey                      # noqa: E402
from bsbprose import QUOTE, TARGETS                            # noqa: E402

CURLY = "“”‘’"
# a short quoted word inside prose -- the commentary's own mentions
MENTION = re.compile(r"[‘']([a-zA-Z][a-zA-Z \-]{2,20})[’']")


def strays(quote):
    """-> count of quote marks stranded inside a quoted span."""
    return sum(quote.count(c) for c in CURLY) + quote.count('"')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fix", action="store_true")
    a = ap.parse_args()

    kjv, bsb = verses("verses.jsonl"), verses("verses.bsb.jsonl")
    tot = dict(rows=0, spans=0, ok=0, bad=0, stray=0, orphan=0, noref=0,
               left=0, apos=0)
    bad_ex, stray_ex, orphan_ex, apos_ex = [], [], [], []
    edits = {}                                   # path -> {lineno: newline}

    for path, field in TARGETS:
        p = ROOT / path
        if not p.exists():
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            old = d.get(f"{field}_kjv")
            if not isinstance(d, dict) or not old:
                continue
            tot["rows"] += 1
            text = d.get(field) or ""
            new_text = text

            # every quotation now standing in the converted prose
            for o, quote, c, ref in QUOTE.findall(text):
                tot["spans"] += 1
                k = vkey(ref)
                if not k or k not in bsb:
                    tot["noref"] += 1
                    continue
                nq = norm(quote)
                if quote in old:
                    # UNTOUCHED. The run rejected or errored this span, so it is
                    # still exactly as written -- including the elided
                    # (`Of clean beasts ... two and two`) and multi-verse
                    # quotations, which verify against no single verse and never
                    # did. Judging those against BSB would report 36 defects
                    # where the run's correct refusal to touch them is the
                    # finding. Only spans the run WROTE are its responsibility.
                    tot["left"] += 1
                elif nq and nq in norm(bsb[k]):
                    tot["ok"] += 1
                elif o == "'" and re.search(r"[a-z]'$", text[:text.find(quote)]):
                    # The regex opens a quotation on any apostrophe, so a
                    # POSSESSIVE starts one: `Abishai's brother, "Who will...`
                    # was read as a quotation beginning at `s brother`. These
                    # were never quotations and must not be judged as ones.
                    tot["apos"] += 1
                    if len(apos_ex) < 4:
                        apos_ex.append((ref, quote[:60]))
                else:
                    tot["bad"] += 1
                    if len(bad_ex) < 6:
                        bad_ex.append((ref, quote[:70]))
                    # revert this span alone to the KJV the row still carries
                    for _o2, q2, _c2, r2 in QUOTE.findall(old):
                        if r2 == ref:
                            new_text = new_text.replace(quote, q2)
                            break
                    continue
                n = strays(quote)
                if n:
                    tot["stray"] += 1
                    if len(stray_ex) < 6:
                        stray_ex.append((ref, quote[:70]))
                    clean = quote
                    for ch in CURLY + '"':
                        clean = clean.replace(ch, "")
                    clean = re.sub(r"\s{2,}", " ", clean).strip()
                    # only if the cleaned span still verifies
                    if norm(clean) and norm(clean) in norm(bsb[k]):
                        new_text = new_text.replace(quote, clean)

            # commentary that mentions a word the conversion may have removed
            outside = QUOTE.sub(" ", text)
            quoted = " ".join(norm(q) for _o, q, _c, _r in QUOTE.findall(text))
            oldq = " ".join(norm(q) for _o, q, _c, _r in QUOTE.findall(old))
            for w in MENTION.findall(outside):
                nw = norm(w)
                if nw and nw in oldq and nw not in quoted:
                    tot["orphan"] += 1
                    if len(orphan_ex) < 8:
                        orphan_ex.append((path, w))

            if new_text != text:
                d[field] = new_text
                edits.setdefault(path, {})[i] = json.dumps(d, ensure_ascii=False)

    print(f"rows carrying a KJV original   {tot['rows']:>7,}")
    print(f"quotations now in the prose    {tot['spans']:>7,}")
    print(f"  verify against BSB           {tot['ok']:>7,}")
    print(f"  untouched (as Doug wrote it) {tot['left']:>7,}   not the run's")
    print(f"  a possessive apostrophe      {tot['apos']:>7,}   never a quotation")
    print(f"  verify against NEITHER       {tot['bad']:>7,}   <- reverted with --fix")
    print(f"  citation unresolvable        {tot['noref']:>7,}")
    print(f"  carry a stray quote mark     {tot['stray']:>7,}   <- stripped with --fix")
    print(f"commentary orphaned by a swap  {tot['orphan']:>7,}   <- reported only")
    for ref, q in bad_ex:
        print(f"   BAD   {ref:<12} {q}")
    for ref, q in stray_ex:
        print(f"   STRAY {ref:<12} {q}")
    for path, w in orphan_ex:
        print(f"   ORPHAN {pathlib.Path(path).name:<34} '{w}'")

    if not a.fix:
        print("\nnothing written -- pass --fix")
        return 0

    for path, byline in edits.items():
        p = ROOT / path
        lines = p.read_text(encoding="utf-8").splitlines()
        for i, new in byline.items():
            lines[i] = new
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  {path}: {len(byline):,} rows repaired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
