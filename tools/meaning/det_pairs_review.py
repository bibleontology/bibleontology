"""A blind test of the rule stamps as a MATCH signal (P-52), for grading.

On the 63 judged pairs a shared rule stamp marked 17 true or related pairs
and no false one; graded verse by verse, the rule was the weaker reader
(53% against Flash's 72%). The use that matters is the pair, so this tests
the pair: matches that pass the trimming checklist, half sharing a rule
stamp and half not, shuffled and unlabelled. The question is whether the
two verses say the same thing. Each verse carries its section heading and,
on a tap, the verses either side (the earlier sheet showed too little context).

    python tools/meaning/det_pairs_review.py  -> docs/review/det-pairs-test.html
"""
from __future__ import annotations

import collections
import gzip
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools"))
from event_profiles import OSIS, MAC, CODE   # noqa: E402

EACH, SEED, MIN_SCORE = 30, 29, 10.0
_bsb = {}


def bsb(osis):
    """(chapter, verse) -> (text, section heading), from the Berean USFM"""
    if osis not in _bsb:
        f = next((ROOT / "data" / "raw" / "usfm" / "engbsb").glob(f"*{CODE[osis]}engbsb.usfm"))
        out, head, ch, cur, title = {}, {}, 0, None, ""
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\\c (\d+)", line)
            if m:
                ch = int(m.group(1))
                continue
            m = re.match(r"\\s1 (.*)", line)
            if m:
                title = re.sub(r"\\\S+\*?", "", m.group(1)).strip()
                continue
            if re.match(r"\\(s\d?|r|d|mt\d?|h|toc\d?|id|ms\d?|mr)\b", line):
                continue
            t = re.sub(r"\\f .*?\\f\*", "", line)
            t = re.sub(r"\\w ([^|]*)\|[^\\]*\\w\*", r"\1", t)
            for piece in re.split(r"(\\v \d+)", t):
                m = re.match(r"\\v (\d+)", piece)
                if m:
                    cur = (ch, int(m.group(1)))
                    out[cur], head[cur] = "", title
                    continue
                if cur:
                    out[cur] += " " + re.sub(r"\\\S+\*?", "", piece).strip()
        _bsb[osis] = ({k: re.sub(r"\s+", " ", v).strip() for k, v in out.items()}, head)
    return _bsb[osis]


def main():
    rng = random.Random(SEED)
    back = dict(zip(MAC, OSIS))
    moved = json.loads((OUT / "versemap.json").read_text(encoding="utf-8")).get("moved") or {}
    rule = collections.defaultdict(set)
    for l in gzip.open(OUT / "det-stamps.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(l)
        if "verse" in r:
            rule[r["verse"]] = {s["stamp"] for s in r["stamps"]}
    verdict = {}
    for l in gzip.open(OUT / "trim.jsonl.gz", "rt", encoding="utf-8"):
        t = json.loads(l)
        if "from" in t:
            verdict[(t["from"], t["to"])] = t["verdict"]
    best = {}
    for l in gzip.open(OUT / "aligned.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(l)
        if r.get("tier") != "same" or r["score"] < MIN_SCORE:
            continue
        if verdict.get((r["from"], r["to"])) != "keep":
            continue
        a, b = r["from"].split("#")[0], r["to"].split("#")[0]
        if a.rsplit(".", 1)[0] == b.rsplit(".", 1)[0]:
            continue                      # the same chapter: a neighbour, not a match
        k = tuple(sorted((a, b)))
        if k not in best or r["score"] > best[k]["score"]:
            best[k] = r
    shared = {k: rule[k[0]] & rule[k[1]] for k in best}
    yes = [k for k in best if shared[k]]
    no = [k for k in best if not shared[k]]
    print(f"{len(best):,} kept verse pairs: {len(yes):,} share a rule stamp, {len(no):,} do not")

    def verse(v):
        e = moved.get(v, v)
        b, c, n = e.split(".")
        o = back.get(b, b)
        txt, head = bsb(o)
        c, n = int(c), int(n)
        return {"ref": f"{o} {c}:{n}", "text": txt.get((c, n), ""), "head": head.get((c, n), ""),
                "before": txt.get((c, n - 1), ""), "after": txt.get((c, n + 1), "")}

    items = []
    for src, pool in (("shared", yes), ("none", no)):
        for k in rng.sample(pool, min(EACH, len(pool))):
            r = best[k]
            items.append({"src": src, "a": verse(k[0]), "b": verse(k[1]),
                          "how": f"{r['verb'][0]} · {r['obj'][0]}",
                          "stamps": sorted(shared[k]), "score": r["score"]})
    rng.shuffle(items)
    for i, it in enumerate(items):
        it["id"] = f"p{i}"
    page = PAGE.replace("__DATA__", json.dumps(items, ensure_ascii=False))
    (ROOT / "docs" / "review" / "det-pairs-test.html").write_text(page, encoding="utf-8")
    print(f"{len(items)} pairs -> docs/review/det-pairs-test.html")


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Match Blind Test</title>
<style>
:root{--bg:#fbfaf7;--fg:#1d1b18;--mut:#6b655c;--line:#e4dfd6;--hd:#f1ede5;--yes:#2f7d4f;--part:#a8741a;--no:#a3392f}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#181715;--fg:#ece8e1;--mut:#a39c90;--line:#34312c;--hd:#23211e;--yes:#5fbf85;--part:#e0a948;--no:#e0736a}}
:root[data-theme=dark]{--bg:#181715;--fg:#ece8e1;--mut:#a39c90;--line:#34312c;--hd:#23211e;--yes:#5fbf85;--part:#e0a948;--no:#e0736a}
body{background:var(--bg);color:var(--fg);font:16px/1.5 Georgia,serif;margin:0;padding:16px}
main{max-width:760px;margin:0 auto}
h1{font-size:1.4rem;margin:.2em 0}h2{font-size:1.1rem;margin:1.2em 0 .2em}
.g{color:var(--mut);font-size:.9rem}
.pair{border-bottom:1px solid var(--line);padding:12px 0}
.v{margin:4px 0}.ref{font-weight:bold;margin-right:.4em}
.head{color:var(--mut);font-size:.85rem;font-style:italic}
.ctx{display:none;color:var(--mut);font-size:.9rem;margin:2px 0 2px 12px}
.v.open .ctx{display:block}
.tog{font-size:.75rem;padding:0 6px;margin-left:4px}
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
<h1>Do these two verses say the same thing?</h1>
<p class="g">Each pair was matched by the structure of its sentences and passed the trimming
checklist. Some also share a theme by rule; which ones is hidden until you reveal it.
Grade each pair: yes, partly (the same theme, or one part of it), or no. "context" shows the
verses either side. Your grades stay in this page until it is reloaded.</p>
<div id="bar"><span id="count"></span> <button id="reveal">Reveal and tally</button></div>
<div id="list"></div><div id="tally"></div>
</main><script>
const DATA=__DATA__;
let grades={}; try{grades=JSON.parse(localStorage.getItem('detpairs')||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem('detpairs',JSON.stringify(grades))}catch(e){}};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const vh=x=>`<div class="v">${x.head?`<div class="head">${esc(x.head)}</div>`:''}
  <div class="ctx">${esc(x.before)}</div><span class="ref">${esc(x.ref)}</span>${esc(x.text)}
  <button class="tog">context</button><div class="ctx">${esc(x.after)}</div></div>`;
document.getElementById('list').innerHTML=DATA.map((it,i)=>`<div class="pair" data-id="${it.id}">
  <h2>${i+1}.</h2>${vh(it.a)}${vh(it.b)}
  <div class="btns">${['yes','partly','no'].map(v=>`<button data-v="${v}">${v}</button>`).join('')}</div>
  <div class="src">${it.src==='shared'?'shares by rule: '+esc(it.stamps.join(', ').replace(/_/g,' ')):'no shared rule stamp'}
   · matched on ${esc(it.how)} · ${it.score}</div></div>`).join('');
const paint=()=>{document.querySelectorAll('.pair').forEach(r=>r.querySelectorAll('button[data-v]').forEach(b=>b.classList.toggle('on',grades[r.dataset.id]===b.dataset.v)));
  document.getElementById('count').textContent=`${Object.keys(grades).length} of ${DATA.length} graded`;};
document.getElementById('list').addEventListener('click',e=>{
  const t=e.target.closest('.tog'); if(t){t.closest('.v').classList.toggle('open');return;}
  const b=e.target.closest('button[data-v]');if(!b)return;
  const id=b.closest('.pair').dataset.id;if(grades[id]===b.dataset.v)delete grades[id];else grades[id]=b.dataset.v;save();paint();});
document.getElementById('reveal').onclick=()=>{document.body.classList.add('shown');
  const t={shared:{n:0,y:0,p:0,no:0},none:{n:0,y:0,p:0,no:0}};
  for(const it of DATA){const g=grades[it.id];if(!g)continue;const x=t[it.src];x.n++;if(g==='yes')x.y++;else if(g==='partly')x.p++;else x.no++;}
  const row=(l,x)=>`<tr><td>${l}</td><td>${x.n}</td><td>${x.y}</td><td>${x.p}</td><td>${x.no}</td><td>${x.n?Math.round(100*(x.y+x.p/2)/x.n)+'%':'—'}</td></tr>`;
  document.getElementById('tally').innerHTML=`<h2>Tally</h2><table><tr><th></th><th>graded</th><th>yes</th><th>partly</th><th>no</th><th>partly = ½</th></tr>
   ${row('share a rule stamp',t.shared)}${row('do not',t.none)}</table>`;};
paint();
</script></body></html>
"""

if __name__ == "__main__":
    main()
