"""A blind sheet of poetic couplets, for a gold set the probe can be judged on.

The 3B scores 75/120 against the rough prior -- 62.5% where a constant scores
50%. That number cannot be acted on, because **it is impossible to tell model
error from gold error**. The prior is that Proverbs 10-15 runs antithetical and
Psalms runs synonymous, and both are tendencies rather than labels: Psalms is
perhaps 60-70% synonymous, so a model scoring 43% there might be wrong, or the
corpus might be mixed and the model right.

A tendency cannot settle a 62% result. Real labels can.

## Why blind, and blind of what

The reference is hidden. Shown "Prov 12:4" a reader who knows the book answers
from the prior -- Proverbs is antithetical, therefore OPPOSITE -- and the sheet
measures the prior rather than the couplet. The same trap the lemma-pair sheet
avoided by stripping Strong's numbers, language markers and headwords, and for
the same reason: every one of those leaks the answer.

So each item is two lines of English and nothing else, in an order that mixes
the two books, seeded so the key is reproducible.

## Three options, not two

Classical Hebrew parallelism has three kinds, and forcing a binary would put
the synthetic ones somewhere false and call the result noise. NEITHER is a real
answer here, and how often it is chosen is itself worth knowing -- if a third
of the corpus is neither, the whole binary framing is wrong and the overnight
run should not happen in this shape at all.

    python tools/parallelism_sheet.py            # writes out/parallel-sheet.html
"""
import json
import pathlib
import random
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
from parallelism import couplets                                 # noqa: E402

SEED = 2024
N_EACH = 20


SPLIT = re.compile(r"\s*[;:]\s+|,\s+(?=but |yet |and |for |nor |so )")


def pick():
    """Couplets in a modern translation, because the reader has to read them.

    The KJV version was shown and found harder to read. That is not a small
    thing -- a sheet that costs effort to parse measures parsing rather than
    judgement, and the whole point of a gold set is that the labels are clean.

    The KJV also punctuates the caesura where the Masoretes accented it, which
    is why it was used first. BSB reads plainly and still splits 60% of Psalms
    and Proverbs, against the KJV's 58% -- so nothing is lost.

        KJV  Treasures of wickedness profit nothing: but righteousness delivereth from death
        BSB  Ill-gotten treasures profit nothing, but righteousness brings deliverance from death
    """
    from bibleont.decompose import _load
    bsb = _load("verses.bsb.jsonl")
    cs = []
    for ref, txt in sorted(bsb.items()):
        m = re.match(r"([1-3]?[A-Za-z]+) ", ref)
        if not m or m.group(1) not in ("Ps", "Prov"):
            continue
        parts = [p for p in SPLIT.split(txt.strip())
                 if p and len(p.split()) >= 3]
        if len(parts) >= 2:
            cs.append({"ref": ref, "a": parts[0], "b": " ".join(parts[1:])})

    def num(c):
        m = re.match(r"([1-3]?[A-Za-z]+) (\d+):(\d+)", c["ref"])
        return (int(m.group(2)), int(m.group(3))) if m else (0, 0)

    prov = sorted([c for c in cs if c["ref"].startswith("Prov ")
                   and 10 <= num(c)[0] <= 15], key=num)
    psa = sorted([c for c in cs if c["ref"].startswith("Ps ")
                  and num(c)[0] <= 50], key=num)
    # Spread across the range rather than taking the first N, so the sample is
    # not all of Proverbs 10 and all of Psalm 1.
    def spread(xs, n):
        step = max(len(xs) // n, 1)
        return [xs[i * step] for i in range(n) if i * step < len(xs)]

    items = ([{"src": "Prov", **c} for c in spread(prov, N_EACH)]
             + [{"src": "Ps", **c} for c in spread(psa, N_EACH)])
    random.seed(SEED)
    random.shuffle(items)
    return items


CSS = """
 :root{--ground:#f6f4ef;--panel:#fffefc;--sunk:#ebe7de;--line:#dfd9cc;
   --ink:#191817;--mid:#5e594f;--faint:#8e887b;
   --same:#2f6f5e;--same-s:#e3efeb;--opp:#9a4230;--opp-s:#f6e8e4;
   --nei:#5a5f7a;--nei-s:#e8e9f0;
   --serif:"Spectral",Georgia,serif;--sans:"Archivo",system-ui,sans-serif;
   --mono:"IBM Plex Mono",ui-monospace,monospace}
 @media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
   --ground:#141412;--panel:#1c1b19;--sunk:#242220;--line:#332f2a;
   --ink:#eeebe5;--mid:#a5a094;--faint:#7d776c;
   --same:#6fb59d;--same-s:#1a2a26;--opp:#d98a72;--opp-s:#2c1e1a;
   --nei:#9aa0c2;--nei-s:#20222c}}
 :root[data-theme="dark"]{
   --ground:#141412;--panel:#1c1b19;--sunk:#242220;--line:#332f2a;
   --ink:#eeebe5;--mid:#a5a094;--faint:#7d776c;
   --same:#6fb59d;--same-s:#1a2a26;--opp:#d98a72;--opp-s:#2c1e1a;
   --nei:#9aa0c2;--nei-s:#20222c}
 *{box-sizing:border-box}
 body{background:var(--ground);color:var(--ink);font-family:var(--sans);
      font-size:15px;line-height:1.5;margin:0}
 .wrap{max-width:760px;margin:0 auto;padding:2.2rem 1.3rem 5rem}
 h1{font-family:var(--serif);font-size:2rem;font-weight:600;margin:0 0 .35rem;
    letter-spacing:-.01em}
 .lede{color:var(--mid);max-width:60ch;margin:0 0 1rem}
 .how{background:var(--sunk);border-left:3px solid var(--line);
      padding:.7rem .95rem;font-size:.9rem;max-width:62ch;border-radius:0 4px 4px 0}
 .bar{position:sticky;top:0;z-index:10;background:var(--ground);
      border-bottom:1px solid var(--line);padding:.55rem 0;margin:1.2rem 0 .8rem;
      display:flex;gap:.8rem;align-items:center;font-family:var(--mono);
      font-size:.76rem;color:var(--mid)}
 .save{margin-left:auto;font-size:.7rem;padding:.15rem .5rem;border-radius:3px;
       background:var(--sunk);color:var(--faint)}
 .save.on{background:var(--same-s);color:var(--same)}
 .save.off{background:var(--opp-s);color:var(--opp)}
 .item{background:var(--panel);border:1px solid var(--line);border-radius:5px;
       padding:.75rem .95rem;margin:.55rem 0}
 .item.done{border-left:3px solid var(--same)}
 .n{font-family:var(--mono);font-size:.68rem;color:var(--faint);
    letter-spacing:.06em}
 .h{font-family:var(--serif);font-size:1.06rem;margin:.3rem 0;line-height:1.45}
 .h.b{color:var(--mid)}
 .opts{display:flex;gap:.4rem;margin-top:.55rem;flex-wrap:wrap}
 button{font:inherit;font-size:.84rem;background:var(--sunk);
        border:1px solid var(--line);color:var(--mid);padding:.26rem .8rem;
        border-radius:3px;cursor:pointer}
 button:hover{color:var(--ink)}
 button[aria-pressed="true"][data-v="RESTATE"]{background:var(--same-s);
        color:var(--same);border-color:var(--same);font-weight:600}
 button[aria-pressed="true"][data-v="CONTRAST"]{background:var(--opp-s);
        color:var(--opp);border-color:var(--opp);font-weight:600}
 button[aria-pressed="true"][data-v="ADVANCE"]{background:var(--nei-s);
        color:var(--nei);border-color:var(--nei);font-weight:600}
 button:focus-visible{outline:2px solid var(--ink);outline-offset:1px}
 footer{margin-top:2.5rem;border-top:1px solid var(--line);padding-top:1rem;
        color:var(--faint);font-size:.85rem;max-width:62ch}
"""

JS = r"""
const ITEMS = __ITEMS__;
const state = {answers:{}, updated:null};
let dbRef=null, timer=null, dirty=false;
const saveEl=document.getElementById("save"), progEl=document.getElementById("prog");
const host=document.getElementById("list");
ITEMS.forEach((it,i) => {
  const d=document.createElement("div");
  d.className="item"; d.dataset.q=String(i);
  d.innerHTML='<div class="n">'+(i+1)+' of '+ITEMS.length+'</div>'
    +'<div class="h">'+it.a+'</div><div class="h b">'+it.b+'</div>'
    +'<div class="opts">'
    +'<button data-v="RESTATE">Restates it</button>'
    +'<button data-v="CONTRAST">Sets an opposite case beside it</button>'
    +'<button data-v="ADVANCE">Carries it forward</button></div>';
  host.appendChild(d);
});
function paint(){
  document.querySelectorAll(".item").forEach(el => {
    const v=state.answers[el.dataset.q];
    el.querySelectorAll("button").forEach(b =>
      b.setAttribute("aria-pressed", String(b.dataset.v===v)));
    el.classList.toggle("done", !!v);
  });
  const n=Object.keys(state.answers).length;
  progEl.textContent=n+" of "+ITEMS.length+" answered";
}
function mark(c,t){saveEl.className="save "+c; saveEl.textContent=t;}
function save(){
  dirty=true;
  if(!dbRef){mark("off","not saved");return;}
  mark("","saving…"); clearTimeout(timer);
  timer=setTimeout(async () => {
    try{ state.updated=new Date().toISOString(); await dbRef.set(state);
         dirty=false; mark("on","saved"); }
    catch(e){ mark("off","save failed"); }
  },500);
}
document.addEventListener("click", e => {
  const b=e.target.closest("button[data-v]"); if(!b) return;
  const q=b.closest(".item").dataset.q;
  state.answers[q]= state.answers[q]===b.dataset.v ? undefined : b.dataset.v;
  if(!state.answers[q]) delete state.answers[q];
  paint(); save();
});
paint(); mark("","connecting…");
(async () => {
  const db=await claude.use("db");
  if(!db){mark("off","offline — answers won't be saved");return;}
  dbRef=db.doc("parallelism/answers");
  dbRef.onSnapshot(s => {
    if(!s.exists){mark("on","ready");return;}
    if(dirty) return;
    state.answers=Object.assign({}, (s.data()||{}).answers||{});
    paint(); mark("on","saved");
  }, () => mark("off","sync error"));
})();
"""

HTML = """<title>Parallelism Gold Set</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;600&family=Archivo:wght@400;500;600&family=IBM+Plex+Mono:wght@400&display=swap">
<style>__CSS__</style>
<div class="wrap">
<h1>Parallelism Gold Set</h1>
<p class="lede">Forty poetic couplets. For each, does the second line
<b>restate</b> the first, set an <b>opposite case</b> beside it, or
<b>carry it forward</b>?</p>
<div class="how">References are hidden on purpose. If you can see the book you
answer from what you know about the book &mdash; Proverbs is antithetical,
therefore opposite &mdash; and the sheet measures that instead of the couplet.
Same reason the lemma sheet stripped Strong&rsquo;s numbers.
<br><br>Go on instinct; these are meant to be quick. Answers save as you click.
<br><br><b>What it decides.</b> A one-line rule &mdash; does the second half
open with <i>but</i>, <i>yet</i>, <i>nevertheless</i> &mdash; scores 86%
against a rough prior, where the local model scored 62% and chance is 50%. So
the model is out and the rule stands in for it, free and instant.
<br><br>But 86% is measured against a <i>tendency</i>, not against labels:
&ldquo;Proverbs runs contrastive, Psalms runs restating&rdquo; is broadly true
and not reliably true. Your forty answers are the first real labels, and they
say what the rule&rsquo;s accuracy actually is &mdash; and, more usefully,
<b>where it fails</b>, since a contrast carried without a conjunction is
invisible to it.</div>
<div class="bar"><span id="prog">&mdash;</span><span class="save" id="save">loading&hellip;</span></div>
<div id="list"></div>
<footer><b>On the middle option:</b> an opposite case is not a contradiction.
&ldquo;The hope of the righteous shall be gladness, but the expectation of the
wicked shall perish&rdquo; asserts both halves as true &mdash; two different
subjects, mirrored outcomes. That is the option to pick there. The first draft
of this sheet called it &ldquo;contradicts&rdquo;, which made the right answer
look wrong; Doug caught it before any of it was scored.
<br><br>If <b>carries it forward</b> comes up often, that is a finding &mdash;
it would mean a two-way framing is too narrow for the corpus.</footer>
</div>
<script>__JS__</script>
"""


def main() -> int:
    items = pick()
    key = [{"i": i, "ref": c["ref"], "src": c["src"]}
           for i, c in enumerate(items)]
    (ROOT / "out" / "parallel-sheet-key.json").write_text(
        json.dumps(key, indent=1), encoding="utf-8")
    payload = json.dumps([{"a": c["a"], "b": c["b"]} for c in items],
                         ensure_ascii=False)
    out = ROOT / "out" / "parallel-sheet.html"
    out.write_text(
        HTML.replace("__CSS__", CSS).replace("__JS__", JS.replace("__ITEMS__", payload)),
        encoding="utf-8")
    n_prov = sum(1 for c in items if c["src"] == "Prov")
    print(f"{len(items)} couplets ({n_prov} Proverbs, {len(items)-n_prov} Psalms), "
          f"shuffled on seed {SEED}")
    print(f"  sheet {out}")
    print(f"  key   {ROOT / 'out' / 'parallel-sheet-key.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
