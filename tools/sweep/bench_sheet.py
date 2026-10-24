"""THE BENCH, FOR A HUMAN TO JUDGE (plan 1.34). The bench (docs/BENCH.md) has
no gold, so its passages are measured for what needs none, and laid out for
a reader to judge:

  agreement   of the three blind runs, per decision: all three, two, or none
  cost        tokens per verse, from the run ledgers
  traps       each passage's known trap, checked:
                Prov 10   the two lines of each proverb set side by side
                          (a parallel group, or a contrast/but link)
                Rom 3     the questions: shown with every link that touches them,
                          so a question taken as a claim is visible
                Mark 15   who says what: every turn's sender
                Job 38    one utterance: how many verses sit inside the LORD's turn
  structure   the voted and derived answer, in sentences with the verse's words
  held        decisions with no majority
  none_fit    what the vocabulary could not say

    python tools/sweep/bench_sheet.py   -> docs/review/sweep-bench-2026-10-15.html
"""
import collections
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import score as S  # noqa: E402

RUNS = [ROOT / "out" / "sweep" / "runs" / f"bench-{i}" for i in (1, 2, 3)]
VOTED = ROOT / "out" / "sweep" / "runs" / "bench-voted"
DERIVED = ROOT / "out" / "sweep" / "runs" / "bench-derived"
CTX = ROOT / "out" / "sweep" / "context"
PASSAGES = {
    "P-gen1": ("Genesis 1:1-5", [f"Gen.1.{v}" for v in range(1, 6)], "narrative, and the translator's-phrase trap"),
    "P-prov10": ("Proverbs 10:1-7", [f"Pro.10.{v}" for v in range(1, 8)], "two lines per proverb, the second answering the first"),
    "P-rom3": ("Romans 3:1-8", [f"Rom.3.{v}" for v in range(1, 9)], "an argument: questions that are not claims"),
    "P-mark15a": ("Mark 15:1-8", [f"Mrk.15.{v}" for v in range(1, 9)], "a trial: who says what"),
    "P-mark15b": ("Mark 15:9-15", [f"Mrk.15.{v}" for v in range(9, 16)], "a trial: who says what"),
    "P-job38": ("Job 38:1-11", [f"Job.38.{v}" for v in range(1, 12)], "one utterance, not eleven verses"),
}
e = html.escape


def load(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def agreement(refs):
    c = collections.Counter()
    for ref in refs:
        ans = [load(r / f"{ref}.json") for r in RUNS]
        ans = [a for a in ans if a]
        if len(ans) < 3:
            continue
        slots = collections.defaultdict(list)
        for a in ans:
            for r in a.get("referents") or []:
                slots[r.get("slot")].append(S.suffix(r.get("choice")))
        for s, v in slots.items():
            k = collections.Counter(v).most_common(1)[0][1]
            c[{3: "all three", 2: "two of three"}.get(k, "none")] += 1
        keys = collections.defaultdict(lambda: ["absent"] * len(ans))
        for i, a in enumerate(ans):
            for l in a.get("links") or []:
                keys[(l.get("src"), l.get("type"), S.suffix(l.get("dst")))][i] = l.get("action")
        for k, v in keys.items():
            n = collections.Counter(v).most_common(1)[0][1]
            c[{3: "all three", 2: "two of three"}.get(n, "none")] += 1
    return c


def sentences(ctx, v):
    gl = {c["id"]: c["gloss"] for c in ctx["clauses"]}
    cand = {c["id"]: c["text"] for c in ctx["candidates"]}
    cand.update({S.suffix(c["id"]): c["text"] for c in ctx["candidates"]})
    out = []
    for s, x in v.refs.items():
        sl = v.slots[s]
        if x:
            out.append(f"“{sl.get('text')}” ({sl.get('in_text') or sl.get('in')}) → <b>{e(cand.get(x) or cand.get(S.suffix(x)) or x)}</b>")
    for a, t, b in sorted(v.links):
        if t in ("then", "and") and a in gl and b in gl:
            continue
        out.append(f"“{e(gl.get(a, a))}” <i>{e(t)}</i> “{e(gl.get(b, b))}”")
    for gid, g in v.groups.items():
        mem = "; ".join(f"{r}: {e(gl.get(S.suffix(n)) or cand.get(n) or cand.get(S.suffix(n)) or n)}" for r, n in g["members"])
        out.append(f"<span class=k>[{e(g['kind'])} {e(gid)}]</span> {mem}")
    return out


def main():
    ledger = {}
    for r in RUNS:
        lp = r / "_ledger.json"
        if lp.exists():
            for p, d in load(lp)["passages"].items():
                ledger.setdefault(p, []).append(d["tokens"])
    held = load(VOTED / "held.json") or {}
    parts = []
    for pid, (title, refs, trap) in PASSAGES.items():
        refs = [r for r in refs if (CTX / f"{r}.json").exists()]
        ag = agreement(refs)
        tot = sum(ag.values()) or 1
        toks = ledger.get(pid, [])
        cost = f"{sum(toks) / len(toks) / len(refs):,.0f} tokens per verse per run" if toks else "cost not recorded"
        rows = []
        trap_lines = []
        for ref in refs:
            ctx = load(CTX / f"{ref}.json")
            ans = load(DERIVED / f"{ref}.json") or load(VOTED / f"{ref}.json")
            if not ctx or not ans:
                continue
            v = S.Verse(ctx, ans)
            if pid == "P-prov10":
                ok = any(g["kind"] == "parallel" for g in v.groups.values()) or any(t in ("contrast", "but_rather") for _, t, _ in v.links)
                trap_lines.append(f"{ctx['verse']}: {'lines set side by side' if ok else '<b>no parallel or contrast</b>'}")
            if pid == "P-rom3":
                qs = [c["id"] for c in ctx["clauses"] if c.get("force") == "question"]
                for q in qs:
                    touching = [f"{a} {t} {b}" for a, t, b in v.links if q in (a, b)]
                    trap_lines.append(f"{ctx['verse']} question “{e(next(c['gloss'] for c in ctx['clauses'] if c['id'] == q))}”: "
                                      + (e(", ".join(touching)) or "no links"))
            if pid in ("P-mark15a", "P-mark15b", "P-job38"):
                cand = {c["id"]: c["text"] for c in ctx["candidates"]}
                for gid, g in v.groups.items():
                    if g["kind"] == "turn":
                        snd = [cand.get(n) or cand.get(S.suffix(n)) or n for r, n in g["members"] if r == "sender"]
                        trap_lines.append(f"{ctx['verse']}: turn {e(gid)}, sender <b>{e(', '.join(snd) or 'none')}</b>")
            rows.append(f"<div class=verse><div class=ref>{e(ctx['verse'])}</div><div class=t>{e(ctx['text'])}</div><ul>"
                        + "".join(f"<li>{s}</li>" for s in sentences(ctx, v)) + "</ul>"
                        + (f"<div class=held>held (no majority): {e(json.dumps(held.get(ref), ensure_ascii=False))}</div>" if held.get(ref) else "")
                        + "".join(f"<div class=nf>none fit: {e((x.get('what') or '')[:220])}</div>" for x in (ans.get("none_fit") or [])[:3])
                        + "</div>")
        parts.append(f"<h2>{e(title)} <span class=k>— {e(trap)}</span></h2>"
                     f"<p class=meta>Agreement of the three blind runs: all three {ag['all three']} · two of three {ag['two of three']} · "
                     f"none {ag['none']} (of {tot} decisions; {100 * (ag['all three'] + ag['two of three']) / tot:.0f}% settled by a majority) · {cost}</p>"
                     + (f"<details open><summary>The trap, checked</summary><ul>" + "".join(f"<li>{x}</li>" for x in trap_lines) + "</ul></details>" if trap_lines else "")
                     + "".join(rows))
    page = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sweep bench</title><style>
body{{margin:0;background:#F3F5F8;color:#141F2C;font:15.5px/1.5 Spectral,Georgia,serif}} main{{max-width:900px;margin:0 auto;padding:16px}}
h1{{font-size:24px}} h2{{font-size:20px;margin:28px 0 4px}} .k{{color:#5C6A7B;font-size:14px;font-weight:normal}} .meta{{color:#5C6A7B;font-size:14px}}
.verse{{background:#fff;border:1px solid #BAC4D0;border-radius:8px;padding:9px 12px;margin:9px 0}} .ref{{font-weight:600}}
.t{{border-left:3px solid #356A8C;padding-left:8px;margin:4px 0}} ul{{margin:4px 0 4px 18px;padding:0;font-size:14.5px}}
.held{{color:#96591A;font-size:13.5px}} .nf{{color:#5C6A7B;font-size:13.5px}} details{{background:#fff;border:1px solid #BAC4D0;border-radius:8px;padding:6px 12px}}
</style></head><body><main><h1>The sweep on the bench</h1>
<p class=meta>Three blind Haiku runs per passage, a passage per call, majority vote, then Doug's rulings applied as code. The bench has no
gold, so nothing here is scored: read the structure against the verse, and the trap each passage was chosen for. Quoted clause words are the
word-by-word rendering of the original, in its order.</p>
{''.join(parts)}</main></body></html>"""
    dst = ROOT / "docs" / "review" / "sweep-bench-2026-10-15.html"
    dst.write_text(page, encoding="utf-8")
    print("->", dst.relative_to(ROOT))


if __name__ == "__main__":
    main()
