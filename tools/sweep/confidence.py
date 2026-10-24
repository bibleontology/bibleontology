"""DOES A JUDGE KNOW WHEN IT IS RIGHT? (2026-10-15: does Haiku know
the confidence that it has in its first pass; thinking about scaling, could
it just mark what it thinks needs a review).

One blind run, every decision carrying a confidence. Each in-scope gold row
is traced to the decision that settles it:
  a link row        the judge's link with that src, type and dst
  an absent row     the same link: present (added or kept) means wrong
  a referent row    the slot's referent
  a group row       the judge's group of that kind holding those members
and scored right or wrong. A row no decision settles is SILENT: the judge
missed it without knowing, which no confidence can flag.

The question it answers: if only "medium" and "low" were reviewed, how much
would be reviewed, and how often is "high" wrong?

    python tools/sweep/confidence.py <run dir>
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import score as S  # noqa: E402


def main():
    run = Path(sys.argv[1])
    gold = json.loads(S.GOLD.read_text(encoding="utf-8"))
    table = collections.Counter()
    dec_all = collections.Counter()
    rows_out = []
    for ref, want in gold.items():
        if ref.startswith("_") or not (run / f"{ref}.json").exists():
            continue
        ctx = json.loads((S.CTX / f"{ref}.json").read_text(encoding="utf-8"))
        ans = json.loads((run / f"{ref}.json").read_text(encoding="utf-8"))
        for kind in ("referents", "links", "groups"):
            for d in ans.get(kind) or []:
                dec_all[d.get("confidence") or "none"] += 1
        v = S.Verse(ctx, ans)
        links = {(l.get("src"), l.get("type"), S.suffix(l.get("dst"))): l for l in ans.get("links") or []}
        refs = {r.get("slot"): r for r in ans.get("referents") or []}
        for row, ins, ok in S.score(ref, want, v):
            if not ins:
                continue
            body = row.split(": ", 1)[1]
            conf = None
            if " -" in body and "-> " in body:
                a, rest = body.split(" -", 1)
                t, b = rest.split("-> ", 1)
                a, t, b = a.strip(), t.strip(), b.strip()
                if t in ("refers_to", "possessor"):
                    sl = S.gold_slots(v, a) if t == "refers_to" else \
                        [s for s, d in v.slots.items() if S.norm(d.get("in_text")) == S.norm(a[:-1] if a.endswith("S") else a)]
                    cs = [refs[s].get("confidence") for s in sl if s in refs]
                    conf = min(cs, key=["low", "medium", "high"].index) if cs and all(c in ("low", "medium", "high") for c in cs) else (cs[0] if cs else None)
                else:
                    l = links.get((a, t, b)) or next((x for k, x in links.items() if k[0] == a and k[1] == t), None)
                    if l:
                        conf = l.get("confidence")
                    else:
                        g = next((g for g in ans.get("groups") or [] if any(m.get("role") == t for m in g.get("members") or [])), None)
                        conf = g.get("confidence") if g else None
            else:
                kindname = body.split("|")[0].strip()
                g = next((g for g in ans.get("groups") or [] if g.get("kind") == kindname), None)
                conf = g.get("confidence") if g else None
            if row.startswith("absent:") and conf is None:
                conf = "nothing made"           # right by not making it
            key = conf or "silent"
            table[(key, ok)] += 1
            rows_out.append((ref, row, key, ok))
    print(f"{run}: decisions made, by confidence: {dict(dec_all)}")
    print(f"{'confidence':14s} {'rows':>5s} {'right':>6s} {'wrong':>6s}  right%")
    for c in ("high", "medium", "low", "nothing made", "silent"):
        r, w = table[(c, True)], table[(c, False)]
        if r + w:
            print(f"{c:14s} {r + w:5d} {r:6d} {w:6d}  {100 * r / (r + w):5.1f}%")
    tot = sum(table.values())
    hi_w = table[("high", False)]
    review = sum(v for (c, _), v in table.items() if c in ("medium", "low"))
    print(f"\nIf only medium and low were reviewed: {review} of {tot} rows reviewed; "
          f"{hi_w} wrong rows passed as high; {table[('silent', False)]} silent misses no flag can catch")
    (run / "confidence.json").write_text(json.dumps(
        {"table": {f"{c}|{ok}": v for (c, ok), v in table.items()}, "decisions": dec_all,
         "rows": rows_out}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
