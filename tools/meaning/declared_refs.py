"""NT verses that DECLARE a reference, and which Old Testament passage each
points to (BACKLOG, "the trigger inverted"; approved 2026-09-29).

tools/lxxbridge.py (2026-09-16) measured that shared vocabulary cannot tell
resembling from citing, and inverted the trigger: the NT verse must itself
say it points somewhere —

    γέγραπται / γεγραμμένον     "it is written"
    ἵνα πληρωθῇ / ἐπληρώθη      "that it might be fulfilled"
    καθὼς ... οὕτως             "just as ... so"   (John 3:14, the serpent)
    ὥσπερ ... οὕτως             "just as ... so"   (Matt 12:40, Jonah)
    τύπος, ἀλληγορέω            "a type", "allegorically"

— and vocabulary only RETRIEVES candidate passages, through the Septuagint
(lxxbridge's norm(), which folds MACULA's chi-written-as-xi). A verse the
Berean editors already give a quotation source or an Old Testament parallel
for is left to them. Flash then reads each remaining verse in context
against its candidates and says which it points to, or none, or names
another passage it knows (credited as a suggestion, a lower claim).

    python tools/meaning/declared_refs.py --count      what remains, and the price
    python tools/meaning/declared_refs.py --run        -> out/declared-refs.jsonl
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
from lxxbridge import load, lxx_of, norm, NSTOP, strongkey, NT  # noqa: E402

CANDIDATES, PER_CALL = 6, 5


def trigger(words):
    t = [norm(w.get("t") or "").strip(",.;·:’'\"") for w in words]
    l = [norm(w.get("l") or "") for w in words]
    if any(x.startswith("γεγραπ") or x.startswith("γεγραμμεν") for x in t):
        return "it is written"
    if any(x.startswith("πληρωθ") or x.startswith("επληρωθ") for x in t):
        return "fulfilled"
    # MACULA's lemma is οὕτω, not οὕτως (the first count found none); and
    # norm() casefolds a final sigma, so the words are put through it too
    # (John 3:14's καθώς is "καθωσ" after it — the second count missed it)
    if norm("οὕτω") in l and (norm("καθώς") in l or norm("ὥσπερ") in l):
        return "just as ... so"
    if norm("τύπος") in l or norm("ἀλληγορέω") in l:
        return "a type"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    il, meta = load()
    nt = {r: w for r, w in il.items() if r.split(".")[0] in NT}
    ot = {r: w for r, w in il.items() if r.split(".")[0] not in NT}
    trig = {r: trigger(w) for r, w in nt.items()}
    trig = {r: k for r, k in trig.items() if k}
    # the editors first: a quotation source, or a parallel note into the OT
    quoted = {json.loads(l)["from"] for l in gzip.open(OUT / "quotenotes.jsonl.gz", "rt",
                                                       encoding="utf-8") if '"from"' in l}
    otpar = set()
    for l in gzip.open(OUT / "xrefs.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(l)
        if r.get("from") and r.get("to"):
            for x, y in ((r["from"], r["to"]), (r["to"], r["from"])):
                if x.split(".")[0] in NT and y.split(".")[0] not in NT:
                    otpar.add(x)
    covered = {r for r in trig if r in quoted}
    todo = sorted(r for r in trig if r not in quoted)
    kinds = collections.Counter(trig.values())
    print(f"{len(trig)} NT verses declare a reference: " +
          ", ".join(f"{k} {n}" for k, n in kinds.most_common()))
    print(f"  {len(covered)} have an editors' quotation source; {len(todo)} do not "
          f"({sum(1 for r in todo if r in otpar)} of those sit under an editors' OT parallel note)")
    # retrieval, as lxxbridge: NT words (form and lemma) against the LXX's
    # renderings of each OT verse's Hebrew, weighted by rarity in the NT
    ntv = {r: {x for w in ws for x in (norm(w.get("l") or ""), norm((w.get("t") or "").strip(",.;·:")))
               if x and x not in NSTOP and len(x) > 2} for r, ws in nt.items()}
    df = collections.Counter(x for s in ntv.values() for x in s)
    idf = {x: math.log(len(ntv) / c) for x, c in df.items()}
    otv = {}
    for r, ws in ot.items():
        got = set()
        for w in ws:
            k = strongkey("hebrew", w.get("s"))
            if k:
                got |= lxx_of(meta, k)
        otv[r] = {x for x in got if x not in NSTOP and len(x) > 2}
    where = collections.defaultdict(set)
    for r, s in otv.items():
        for x in s:
            where[x].add(r)
    cands = {}
    for r in todo:
        sc = collections.Counter()
        for x in ntv[r]:
            if idf.get(x, 0) > 3.0:
                for o in where.get(x, ()):
                    sc[o] += idf[x]
        cands[r] = [o for o, _ in sc.most_common(CANDIDATES)]
    for r, want in (("Jhn.3.14", "Num.21"), ("Mat.12.40", "Jon.")):
        got = cands.get(r)
        print(f"  check {r}: " + ("covered by the editors" if r in covered else
              ("not a trigger verse" if r not in trig else
               f"candidates {got}; wanted {want} " + ("FOUND" if any(o.startswith(want) for o in got or []) else "missing"))))
    calls = math.ceil(len(todo) / PER_CALL)
    print(f"  {calls} Flash calls of {PER_CALL} verses x {CANDIDATES} candidates; about "
          f"${calls * 0.0012:.2f} off-peak")
    if a.count:
        return
    run(todo, trig, cands)


HEAD = """Below are New Testament verses (Berean Standard Bible, public domain), each shown with the verse before and after it. Each one says it points to something earlier: "it is written", "that it might be fulfilled", "just as ... so", or "a type". Under each are numbered CANDIDATE Old Testament passages that a word search found; they may or may not include the right one.

For EACH New Testament verse, say which Old Testament passage it points to:
  - the number of a candidate, if one of them is what the verse points to;
  - or "other", with the reference (book chapter:verse), if you know it points to a passage not listed;
  - or "none", if the verse does not point to an Old Testament passage at all (for example "just as the Father sent me, so I send you" compares, it does not cite).
Give a confidence: high, medium or low. Your answers are scored: 3 points for a correct high answer, 2 for a correct medium and 1 for a correct low; you lose 10 points for a wrong high answer and 3 for a wrong medium, and nothing for a wrong low one.

Return ONLY this JSON:
{"answers": [{"verse": "<id>", "points_to": "<candidate number | other | none>", "other": "<book chapter:verse, only for other>", "confidence": "<high|medium|low>", "reason": "<one short sentence>"}]}

"""


def run(todo, trig, cands):
    from bibleont import delegate
    from det_pairs_review import bsb
    from event_profiles import OSIS, MAC
    back = dict(zip(MAC, OSIS))
    moved = json.loads((OUT / "versemap.json").read_text(encoding="utf-8")).get("moved") or {}

    def verse(v):
        e = moved.get(v, v)
        b, c, n = e.split(".")
        txt, head = bsb(back.get(b, b))
        c, n = int(c), int(n)
        return f"{back.get(b, b)} {c}:{n}", txt.get((c, n), ""), txt.get((c, n - 1), ""), \
            txt.get((c, n + 1), ""), head.get((c, n), "")

    out, cost = [], 0.0
    for i in range(0, len(todo), PER_CALL):
        batch = todo[i:i + PER_CALL]
        parts = []
        for r in batch:
            ref, t, before, after, _h = verse(r)
            parts.append(f"VERSE {r}  ({trig[r]})\n  [{before}]\n  {ref}: {t}\n  [{after}]\n  candidates:")
            for j, o in enumerate(cands[r], 1):
                oref, ot, _b, _a, oh = verse(o)
                parts.append(f"    {j}. {oref} ({oh}): {ot}")
        res = delegate.run(HEAD + "\n".join(parts), 1, label=f"declared-refs {i // PER_CALL}",
                           blind=True, timeout=180, check_balance=False)
        cost += res.get("cost") or 0
        if res.get("refused") or res.get("stopped"):
            print("stopped:", res.get("refused") or res.get("stopped"))
            break
        m = re.search(r'\{\s*"answers"', res.get("answer") or "")
        got = {}
        if m:
            try:
                got = {x.get("verse"): x for x in json.JSONDecoder().raw_decode(
                    res["answer"][m.start():])[0].get("answers", [])}
            except json.JSONDecodeError:
                pass
        for r in batch:
            x = got.get(r)
            if not x:
                continue
            p = str(x.get("points_to", "")).strip()
            target = cands[r][int(p) - 1] if p.isdigit() and 0 < int(p) <= len(cands[r]) else None
            out.append({"from": r, "trigger": trig[r], "points_to": target,
                        "other": x.get("other") if p == "other" else None,
                        "verdict": "candidate" if target else p, "confidence": x.get("confidence"),
                        "reason": x.get("reason", ""), "candidates": cands[r],
                        "reader": "DeepSeek Flash (declared references, unreviewed)"})
    with (OUT / "declared-refs.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps({"_note": "NT verses that declare a reference, and the OT passage "
                            "Flash reads each as pointing to (tools/meaning/declared_refs.py). "
                            "A reading, credited; 'other' is Flash's own suggestion, a lower claim."}) + "\n")
        for x in out:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    c = collections.Counter(x["verdict"] for x in out)
    print(f"{len(out)} of {len(todo)} answered, ${cost:.4f}: " + ", ".join(f"{k} {n}" for k, n in c.most_common()))
    for x in out:
        if x["from"] in ("Jhn.3.14", "Mat.12.40"):
            print(f"  {x['from']} -> {x['points_to'] or x['other'] or x['verdict']} ({x['confidence']}): {x['reason']}")


if __name__ == "__main__":
    main()
