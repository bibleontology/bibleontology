"""THE TWO-LEVEL RE-JUDGE, AS A SHEET DOUG CAN MARK (plan 2.13; 2026-10-18).

A stratified sample of the judged phrases in out/wordgraph/prep-phrases-
judged-2.jsonl.gz, weighted to where a new schema can go wrong: six from each
new type (target, dominion, authority, rests_on, sphere, circumstance), six
named only at the family level, and six `purpose` under לְ (the pilot's one
tendency: an infinitive that completes its verb, "determined to go", called
purpose). Each with its verse in the Berean, its words, and a mark.

    python tools/wordgraph/pp_sheet2.py   -> docs/review/prep-phrases-2-2026-10-18.html
"""
import gzip
import html
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "sweep"))
import context as C  # noqa: E402

SRC = ROOT / "out" / "wordgraph" / "prep-phrases-judged-2.jsonl.gz"
e = html.escape
GROUPS = [("target", "target: what comes or falls upon someone, nothing handed over"),
          ("dominion", "dominion: rule over someone"),
          ("authority", "authority: by whose authority an act is done"),
          ("rests_on", "rests_on: what something rests or relies on"),
          ("sphere", "sphere: a reading, only where no other type fits"),
          ("circumstance", "circumstance: the situation in which something happens"),
          ("FAMILY", "named only at the family level"),
          ("PURPOSE_L", "purpose under לְ: is it the aim, or does the infinitive complete its verb?")]


def main():
    pool = {g: [] for g, _ in GROUPS}
    total = named = family = 0
    with gzip.open(SRC, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            d = json.loads(line)
            for p in d["pp"]:
                total += 1
                named += bool(p.get("relation"))
                family += p.get("level") == "family"
                if p.get("kind") != "judged" or not p.get("relation"):
                    continue
                if p["relation"] in pool:
                    pool[p["relation"]].append((d["ref"], p))
                if p.get("level") == "family":
                    pool["FAMILY"].append((d["ref"], p))
                if p["relation"] == "purpose" and p["prep"]["s"].startswith("3807"):
                    pool["PURPOSE_L"].append((d["ref"], p))
    random.seed(18)
    bsb = C._bsb()
    secs = []
    for g, title in GROUPS:
        items = random.sample(pool[g], min(6, len(pool[g])))
        lis = []
        for ref, p in items:
            _t, text = bsb(ref)
            mk = e(p["id"])
            lis.append(
                f"<li><b>{e(_t)}</b> “{e(p.get('gloss') or '')}” → <b>{e(p['relation'])}</b> "
                f"<span class=k>({e(p.get('family') or '')}, {e(p.get('confidence') or '')}; attaches to "
                f"{e(p.get('attaches') or '')})</span>"
                f"<span class=mk data-id='{mk}'><label><input type=radio name='{mk}' value=right> right</label>"
                f"<label><input type=radio name='{mk}' value=partly> partly</label>"
                f"<label><input type=radio name='{mk}' value=wrong> wrong</label>"
                f"<input class=nt placeholder='note'></span>"
                f"<div class=t>{e(text)}</div><div class=k>{e(p.get('text') or '')} · {e(p.get('by') or '')}</div></li>")
        secs.append(f"<section><h2>{e(title)} <span class=k>· {len(pool[g]):,} in all</span></h2><ol>{''.join(lis)}</ol></section>")
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Prepositions, re-judged</title><style>
:root{{--paper:#F3F5F8;--surface:#fff;--ink:#141F2C;--muted:#5C6A7B;--rule:#BAC4D0;--accent:#356A8C}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2C3A4A;--accent:#7FB2D6}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Georgia,serif}} main{{max-width:900px;margin:0 auto;padding:16px}}
section{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:8px 16px;margin:14px 0}}
li{{margin:10px 0}} .t{{border-left:3px solid var(--accent);padding-left:8px;margin:3px 0}} .k{{color:var(--muted);font-size:13px}}
.mk{{margin-left:8px;font-size:13px}} .nt{{font:inherit;font-size:13px;margin-left:6px;width:220px;background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:5px}}
button{{font:inherit;padding:5px 12px;border-radius:6px;border:1px solid var(--accent);background:var(--surface);color:var(--accent)}}
</style></head><body><main><h1>Prepositional phrases, re-judged with the two-level schema</h1>
<p class=k>The bold relation is what was judged; the grey line is the judge's reason. Mark the bold one. A sample of
where the new schema can go wrong; the whole run: {named:,} of {total:,} phrases named, {family:,} at the family level only, low
confidence counted as none (your ruling).</p>
<p class=k>Each phrase is shown with the verse its words are in, read from MACULA. The first build of this sheet
guessed the verse and filed about one phrase in seven under a later one; the 10,848 phrases judged under the wrong
verse were judged again under the right one.</p>
<p><button id=exp>Copy my marks</button> <span id=st class=k></span></p>
{''.join(secs)}</main><script>
const KEY='prep-phrases-2-2026-10-18'; let M={{}}; try{{M=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(M))}}catch(e){{}}}}
document.querySelectorAll('.mk').forEach(m=>{{const id=m.dataset.id; const s=M[id]||{{}};
 m.querySelectorAll('input[type=radio]').forEach(i=>{{if(i.value===s.mark)i.checked=true; i.onchange=()=>{{(M[id]=M[id]||{{}}).mark=i.value;save()}}}});
 const n=m.querySelector('.nt'); n.value=s.note||''; n.oninput=()=>{{(M[id]=M[id]||{{}}).note=n.value;save()}};}});
document.getElementById('exp').onclick=async()=>{{const x=JSON.stringify({{sheet:KEY,marks:M}},null,1);
 try{{await navigator.clipboard.writeText(x);document.getElementById('st').textContent='Copied: paste it into the chat.'}}catch(e){{prompt('Copy this',x)}}}};
</script></body></html>"""
    dest = ROOT / "docs" / "review" / "prep-phrases-2-2026-10-18.html"
    dest.write_text(page, encoding="utf-8")
    print({g: len(v) for g, v in pool.items()}, "->", dest.relative_to(ROOT))


if __name__ == "__main__":
    main()
