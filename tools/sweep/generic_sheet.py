"""THE GENERIC CHECK, AS A SHEET TO MARK BY HAND (plan 1.41; 2026-10-18).

A sample of out/sweep/generic-links.jsonl: 14 "same", 10 "part_of" and 8
"neither", each with the generic's label, the candidate word, and the verses.

    python tools/sweep/generic_sheet.py   -> docs/review/generic-check-2026-10-18.html
"""
import collections
import gzip
import html
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import context as C  # noqa: E402

e = html.escape


def main():
    rows = [json.loads(x) for x in (ROOT / "out" / "sweep" / "generic-links.jsonl").read_text(encoding="utf-8").splitlines()]
    gens = {g["id"]: g for g in json.loads((ROOT / "out" / "sweep" / "runs" / "resolve-1" / "generics.json").read_text(encoding="utf-8"))}
    want = {r["candidate"] for r in rows if r.get("candidate")}
    # WHAT EACH GENERIC STANDS FOR: the words the sweep resolved to it ("they"
    # in Isaiah 8:15). The first sheet left them out, so the thing to compare
    # with the candidate was invisible (2026-10-18: the reader had to
    # know that the subsequent 'they' references were what the candidate
    # was compared to)
    stands = collections.defaultdict(list)
    with gzip.open(ROOT / "out" / "sweep-layer.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("type") == "refers_to" and "#generic:" in str(d.get("dst")) and d.get("action") != "remove":
                stands[d["dst"]].append(d["src"])
    need = want | {s for v in stands.values() for s in v} | {s.rsplit("s", 1)[0] for v in stands.values() for s in v}
    words = {}
    with gzip.open(ROOT / "out" / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["id"] in need:
                words[d["id"]] = (d.get("text"), d.get("original"))

    def stand_text(slot):
        """'they' and, for an unstated subject, the clause it is the subject of."""
        t = (words.get(slot) or ("", ""))[0] or "?"
        if slot.endswith("s") and "#cl" in slot:
            cl = (words.get(slot[:-1]) or ("", ""))[0]
            short = " ".join((cl or "").split()[:5])
            return f"“{t}” (unstated, of “{short}…”, {slot.split('#')[0]})"
        return f"“{t}” ({slot.split('#')[0]})"
    bsb = C._bsb()
    random.seed(41)
    by = collections.defaultdict(list)
    for r in rows:
        by[r["decision"]].append(r)
    secs = []
    for dec, n, title in (("same", 14, "Same: the generic is the group the text names there"),
                          ("part_of", 10, "Part of: the generic is some of, or one of, that group"),
                          ("neither", 8, "Neither: no candidate names them")):
        lis = []
        for r in random.sample(by[dec], min(n, len(by[dec]))):
            g = gens.get(r["generic"], {})
            cand = r.get("candidate") or r.get("low_candidate")
            wt, wo = words.get(cand, ("", ""))
            used = stands.get(r["generic"], [])
            refs = sorted({g.get("first", "")} | ({cand.split("#")[0]} if cand else set())
                          | {s.split("#")[0] for s in used[:3]})
            verses = "".join(f"<div class=t><b>{e(bsb(x)[0])}</b> {e(bsb(x)[1])}</div>" for x in refs if x)
            mk = e(r["generic"])
            lis.append(
                f"<li>“{e(g.get('label', ''))}” → <b>{e(dec)}</b>"
                + (f" “{e(wt)}” <span class=k>({e(wo)}, {e(cand.split('#')[0])})</span>" if cand and dec != "neither" else "")
                + f" <span class=k>({e(r.get('confidence') or '')})</span>"
                f"<span class=mk data-id='{mk}'><label><input type=radio name='{mk}' value=right> right</label>"
                f"<label><input type=radio name='{mk}' value=wrong> wrong</label>"
                f"<input class=nt placeholder='note'></span>"
                f"<div class=st><b>Stands for</b> <span class=k>(the original's word-for-word gloss: \"of him\" "
                f"is the Berean's \"his\")</span>: {', '.join(stand_text(s) for s in used[:4]) or 'no word yet'}"
                f"{f' and {len(used) - 4} more' if len(used) > 4 else ''}</div>{verses}"
                f"<div class=k>{e(r.get('why') or '')}</div></li>")
        secs.append(f"<section><h2>{e(title)} <span class=k>· {len(by[dec])} in all</span></h2><ol>{''.join(lis)}</ol></section>")
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Generic check</title><style>
:root{{--paper:#F3F5F8;--surface:#fff;--ink:#141F2C;--muted:#5C6A7B;--rule:#BAC4D0;--accent:#356A8C}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2C3A4A;--accent:#7FB2D6}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Georgia,serif}} main{{max-width:900px;margin:0 auto;padding:16px}}
section{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:8px 16px;margin:14px 0}}
li{{margin:12px 0}} .st{{margin:3px 0;font-size:14px}} .t{{border-left:3px solid var(--accent);padding-left:8px;margin:3px 0}} .k{{color:var(--muted);font-size:13px}}
.mk{{margin-left:8px;font-size:13px}} .nt{{font:inherit;font-size:13px;margin-left:6px;width:200px;background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:5px}}
button{{font:inherit;padding:5px 12px;border-radius:6px;border:1px solid var(--accent);background:var(--surface);color:var(--accent)}}
</style></head><body><main><h1>The generics, checked against the text's own words</h1>
<p class=k>Plan 1.41. A generic is a group or person the sweep named in its own words, because the verse did not
("the twelve disciples"). Each was offered the nouns near its first use that share a word with it, and the judge said
whether it is the same group, a part of it, or neither. <b>The question you mark: are the words under "Stands for"
the same people as the bold word?</b> (For "part of": are they some of that group?) The grey line is the judge's
reason. Of 887 checked: 498 same, 65 part of, 324 neither (low confidence counted as neither).</p>
<p><button id=exp>Copy my marks</button> <span id=st class=k></span></p>
{''.join(secs)}</main><script>
const KEY='generic-check-2026-10-18'; let M={{}}; try{{M=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(M))}}catch(e){{}}}}
document.querySelectorAll('.mk').forEach(m=>{{const id=m.dataset.id; const s=M[id]||{{}};
 m.querySelectorAll('input[type=radio]').forEach(i=>{{if(i.value===s.mark)i.checked=true; i.onchange=()=>{{(M[id]=M[id]||{{}}).mark=i.value;save()}}}});
 const n=m.querySelector('.nt'); n.value=s.note||''; n.oninput=()=>{{(M[id]=M[id]||{{}}).note=n.value;save()}};}});
document.getElementById('exp').onclick=async()=>{{const x=JSON.stringify({{sheet:KEY,marks:M}},null,1);
 try{{await navigator.clipboard.writeText(x);document.getElementById('st').textContent='Copied: paste it into the chat.'}}catch(e){{prompt('Copy this',x)}}}};
</script></body></html>"""
    dest = ROOT / "docs" / "review" / "generic-check-2026-10-18.html"
    dest.write_text(page, encoding="utf-8")
    print("->", dest.relative_to(ROOT))


if __name__ == "__main__":
    main()
