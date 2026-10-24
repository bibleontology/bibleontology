"""A blind test of the rule stamps against Flash (P-52), for grading.

2026-09-29: test it first. For six stamps, verses where the two
DISAGREE: five the rule stamps and Flash does not (at medium or better),
five Flash stamps and the rule does not. Shown shuffled and unlabelled —
the question is only "does this verse speak of it?" — and the source is
revealed with the tally once graded, so neither side is read generously.

    python tools/meaning/det_stamps_review.py   -> docs/review/det-stamps-test.html
"""
from __future__ import annotations

import collections
import gzip
import html
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools"))
from event_profiles import OSIS, MAC, CODE   # noqa: E402

_bsb = {}


def bsb(osis):
    """a book's BSB verses, (chapter, verse) -> text (as tools/stamp_lists.py,
    which runs its whole script on import)"""
    if osis not in _bsb:
        f = next((ROOT / "data" / "raw" / "usfm" / "engbsb").glob(f"*{CODE[osis]}engbsb.usfm"))
        out, ch, cur = {}, 0, None
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\\c (\d+)", line)
            if m:
                ch = int(m.group(1))
                continue
            if re.match(r"\\(s\d?|r|d|mt\d?|h|toc\d?|id|ms\d?|mr)\b", line):
                continue
            t = re.sub(r"\\f .*?\\f\*", "", line)
            t = re.sub(r"\\w ([^|]*)\|[^\\]*\\w\*", r"\1", t)
            for piece in re.split(r"(\\v \d+)", t):
                m = re.match(r"\\v (\d+)", piece)
                if m:
                    cur = (ch, int(m.group(1)))
                    out[cur] = ""
                    continue
                if cur:
                    out[cur] += " " + re.sub(r"\\\S+\*?", "", piece).strip()
        _bsb[osis] = {k: re.sub(r"\s+", " ", v).strip() for k, v in out.items()}
    return _bsb[osis]

STAMPS = ["sacrifice", "mercy_restoration", "judgment", "temple_presence", "resurrection", "idolatry"]
EACH = 5
SEED = 29


def main():
    rng = random.Random(SEED)
    back = dict(zip(MAC, OSIS))
    moved = json.loads((OUT / "versemap.json").read_text(encoding="utf-8")).get("moved") or {}
    tax = json.loads((ROOT / "ontology" / "interest-taxonomy.json").read_text(encoding="utf-8"))
    label = {i["id"]: (i["label"], i.get("gloss", "")) for i in tax["themes"]["items"]}
    rule = {}
    for l in gzip.open(OUT / "det-stamps.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(l)
        if "verse" in r:
            rule[r["verse"]] = {s["stamp"]: s["by"] for s in r["stamps"]}
    flash, anyflash = collections.defaultdict(set), collections.defaultdict(set)
    for line in gzip.open(OUT / "clause-tags.jsonl.gz", "rt", encoding="utf-8").read().splitlines()[1:]:
        t = json.loads(line)
        if t["kind"] != "stamp":
            continue
        v, k = t["clause"].split("#")[0], re.sub(r"_ev$", "", t["tag"])
        anyflash[v].add(k)
        if t["weight"] >= 0.67:
            flash[v].add(k)
    universe = sorted(set(rule) | set(flash))

    def text(v):
        e = moved.get(v, v)
        b, c, n = e.split(".")
        return f"{back.get(b, b)} {c}:{n}", bsb(back.get(b, b)).get((int(c), int(n)), "")

    items = []
    for s in STAMPS:
        ronly = [v for v in universe if s in rule.get(v, {}) and s not in anyflash[v]]
        fonly = [v for v in universe if s in flash[v] and s not in rule.get(v, {})]
        for src, pool in (("rule", ronly), ("flash", fonly)):
            for v in rng.sample(pool, min(EACH, len(pool))):
                ref, t = text(v)
                if not t:
                    continue
                items.append({"stamp": s, "src": src, "ref": ref, "text": t,
                              "by": rule.get(v, {}).get(s, [])})
        print(f"{s}: rule-only {len(ronly):,}, flash-only {len(fonly):,}")
    by = collections.defaultdict(list)
    for it in items:
        by[it["stamp"]].append(it)
    for s in by:
        rng.shuffle(by[s])
    data = [dict(it, id=f"{it['stamp']}:{it['ref']}") for s in STAMPS for it in by[s]]
    heads = {s: label.get(s, (s.replace("_", " ").capitalize(), "")) for s in STAMPS}
    page = PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False)) \
               .replace("__HEADS__", json.dumps(heads, ensure_ascii=False))
    (ROOT / "docs" / "review" / "det-stamps-test.html").write_text(page, encoding="utf-8")
    print(f"{len(data)} verses -> docs/review/det-stamps-test.html")


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stamp Blind Test</title>
<style>
:root{--bg:#fbfaf7;--fg:#1d1b18;--mut:#6b655c;--line:#e4dfd6;--hd:#f1ede5;--yes:#2f7d4f;--part:#a8741a;--no:#a3392f}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#181715;--fg:#ece8e1;--mut:#a39c90;--line:#34312c;--hd:#23211e;--yes:#5fbf85;--part:#e0a948;--no:#e0736a}}
:root[data-theme=dark]{--bg:#181715;--fg:#ece8e1;--mut:#a39c90;--line:#34312c;--hd:#23211e;--yes:#5fbf85;--part:#e0a948;--no:#e0736a}
body{background:var(--bg);color:var(--fg);font:16px/1.5 Georgia,serif;margin:0;padding:16px}
main{max-width:760px;margin:0 auto}
h1{font-size:1.4rem;margin:.2em 0}h2{font-size:1.1rem;margin:1.6em 0 .2em;border-bottom:1px solid var(--line);padding-bottom:4px}
.g{color:var(--mut);font-size:.9rem}
.row{border-bottom:1px solid var(--line);padding:10px 0}
.ref{font-weight:bold;margin-right:.4em}
.btns{margin-top:6px;display:flex;gap:6px;flex-wrap:wrap}
button{font:inherit;font-size:.85rem;border:1px solid var(--line);background:var(--hd);color:var(--fg);border-radius:6px;padding:3px 10px;cursor:pointer}
button.on[data-v=yes]{border-color:var(--yes);color:var(--yes);font-weight:bold}
button.on[data-v=partly]{border-color:var(--part);color:var(--part);font-weight:bold}
button.on[data-v=no]{border-color:var(--no);color:var(--no);font-weight:bold}
.src{display:none;font-size:.85rem;color:var(--mut);margin-top:4px}
body.shown .src{display:block}
#bar{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);z-index:1}
table{border-collapse:collapse;margin-top:8px;font-size:.9rem}td,th{border:1px solid var(--line);padding:3px 8px;text-align:left}
</style></head><body><main>
<h1>Does this verse speak of it?</h1>
<p class="g">Two readers disagree on every verse below: one says it speaks of the heading,
the other says it does not. Which reader said which is hidden until you reveal it.
Grade each one: yes, partly, or no. Your grades stay in this browser.</p>
<div id="bar"><span id="count"></span> <button id="reveal">Reveal readers and tally</button></div>
<div id="list"></div><div id="tally"></div>
</main><script>
const DATA=__DATA__, HEADS=__HEADS__;
let grades={}; try{grades=JSON.parse(localStorage.getItem('detgrades')||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem('detgrades',JSON.stringify(grades))}catch(e){}};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let html='',cur=null;
for(const it of DATA){
  if(it.stamp!==cur){cur=it.stamp;const [l,g]=HEADS[cur];html+=`<h2>${esc(l)}</h2>${g?`<div class="g">${esc(g)}</div>`:''}`;}
  html+=`<div class="row" data-id="${esc(it.id)}"><span class="ref">${esc(it.ref)}</span>${esc(it.text)}
   <div class="btns">${['yes','partly','no'].map(v=>`<button data-v="${v}">${v}</button>`).join('')}</div>
   <div class="src">${it.src==='rule'?'the rule said yes'+(it.by.length?' — on: '+esc(it.by.join(', ')):''):'Flash said yes; the rule said no'}</div></div>`;
}
document.getElementById('list').innerHTML=html;
const paint=()=>{document.querySelectorAll('.row').forEach(r=>r.querySelectorAll('button').forEach(b=>b.classList.toggle('on',grades[r.dataset.id]===b.dataset.v)));
  document.getElementById('count').textContent=`${Object.keys(grades).length} of ${DATA.length} graded`;};
document.getElementById('list').addEventListener('click',e=>{const b=e.target.closest('button[data-v]');if(!b)return;
  const id=b.closest('.row').dataset.id;grades[id]=grades[id]===b.dataset.v?undefined:b.dataset.v;if(!grades[id])delete grades[id];save();paint();});
document.getElementById('reveal').onclick=()=>{document.body.classList.add('shown');
  const t={rule:{n:0,s:0},flash:{n:0,s:0}};
  for(const it of DATA){const g=grades[it.id];if(!g)continue;t[it.src].n++;t[it.src].s+=g==='yes'?1:g==='partly'?.5:0;}
  const pct=x=>x.n?Math.round(100*x.s/x.n)+'%':'—';
  document.getElementById('tally').innerHTML=`<h2>Tally</h2><table><tr><th>reader</th><th>graded</th><th>right (partly = half)</th></tr>
   <tr><td>the rule</td><td>${t.rule.n}</td><td>${pct(t.rule)}</td></tr><tr><td>Flash</td><td>${t.flash.n}</td><td>${pct(t.flash)}</td></tr></table>`;};
paint();
</script></body></html>
"""

if __name__ == "__main__":
    main()
