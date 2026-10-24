"""A sheet for judging grammatical tuples, so the floor has a measured accuracy.

The extractor produces 15,065 tuples for free, and four of five Genesis samples
looked right. Four of five is a sample of five, and today has already shown
twice what happens when a plausible-looking count is reported against no ground
truth -- the parallelism prior scored exactly chance, and every number measured
against it was noise.

So: 40 tuples, the verse beside each, and four options rather than two. Which
part is wrong matters more than how often something is, because the failures
are diagnostic. A wrong subject in Hebrew means the noun between verb and
object marker was not the subject; a wrong object means the particle was
attached to something else.

The Greek is included and expected to fail. Its heuristic takes the first
nominative and first accusative in a verse, which is wrong wherever a verse
holds more than one clause -- Acts 1:1 comes out "Jesus composed account" when
the subject is Luke. Ten Greek items are here to put a number on that rather
than to rescue it.

    python tools/tuple_sheet.py          # writes out/tuple-sheet.html
"""
import json
import pathlib
import random
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
from tuples import corpus, hebrew, greek                         # noqa: E402

SEED = 1847
N_HEB, N_GRK = 30, 10

BOOK = {"Gen": "Gen", "Exo": "Exod", "Lev": "Lev", "Num": "Num", "Deu": "Deut",
        "Jos": "Josh", "Jdg": "Judg", "Rut": "Ruth", "1Sa": "1Sam",
        "2Sa": "2Sam", "1Ki": "1Kgs", "2Ki": "2Kgs", "1Ch": "1Chr",
        "2Ch": "2Chr", "Ezr": "Ezra", "Neh": "Neh", "Est": "Esth",
        "Job": "Job", "Psa": "Ps", "Pro": "Prov", "Ecc": "Eccl",
        "Sng": "Song", "Isa": "Isa", "Jer": "Jer", "Lam": "Lam",
        "Ezk": "Ezek", "Dan": "Dan", "Hos": "Hos", "Jol": "Joel",
        "Amo": "Amos", "Oba": "Obad", "Jon": "Jonah", "Mic": "Mic",
        "Nam": "Nah", "Hab": "Hab", "Zep": "Zeph", "Hag": "Hag",
        "Zec": "Zech", "Mal": "Mal", "Mat": "Matt", "Mrk": "Mark",
        "Luk": "Luke", "Jhn": "John", "Act": "Acts", "Rom": "Rom",
        "1Co": "1Cor", "2Co": "2Cor", "Gal": "Gal", "Eph": "Eph",
        "Php": "Phil", "Col": "Col", "1Th": "1Thess", "2Th": "2Thess",
        "1Ti": "1Tim", "2Ti": "2Tim", "Tit": "Titus", "Phm": "Phlm",
        "Heb": "Heb", "Jas": "Jas", "1Pe": "1Pet", "2Pe": "2Pet",
        "1Jn": "1John", "2Jn": "2John", "3Jn": "3John", "Jud": "Jude",
        "Rev": "Rev"}


def verse_ref(step_ref):
    b, c, v = step_ref.split(".")
    return f"{BOOK.get(b, b)} {c}:{v}"


def pick():
    from bibleont.decompose import _load
    bsb = _load("verses.bsb.jsonl")
    kjv = _load("verses.jsonl")
    rows = corpus()
    heb = [t for t in hebrew(rows) if t["s"]]
    grk = [t for t in greek(rows) if t["s"]]
    random.seed(SEED)
    items = random.sample(heb, N_HEB) + random.sample(grk, N_GRK)
    random.shuffle(items)
    out = []
    for t in items:
        ref = verse_ref(t["ref"])
        txt = bsb.get(ref) or kjv.get(ref) or ""
        if not txt:
            continue
        out.append({**t, "vref": ref, "text": txt})
    return out


CSS = """
 :root{--ground:#f5f4f0;--panel:#fffefc;--sunk:#eae7df;--line:#ded8cc;
   --ink:#1a1917;--mid:#5f5a51;--faint:#8d877b;
   --ok:#2f6a4f;--ok-s:#e2eee8;--s:#8a4a2c;--s-s:#f5e9e2;
   --o:#4a5580;--o-s:#e7e9f2;--x:#8f3535;--x-s:#f5e4e4;
   --serif:"Spectral",Georgia,serif;--sans:"Archivo",system-ui,sans-serif;
   --mono:"IBM Plex Mono",ui-monospace,monospace}
 @media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
   --ground:#141412;--panel:#1c1b19;--sunk:#232220;--line:#332f2a;
   --ink:#eeebe5;--mid:#a5a095;--faint:#7d776c;
   --ok:#71b593;--ok-s:#1a2721;--s:#d08e64;--s-s:#2b1f18;
   --o:#8f9ad0;--o-s:#1e2130;--x:#d47b7b;--x-s:#2b1a1a}}
 :root[data-theme="dark"]{
   --ground:#141412;--panel:#1c1b19;--sunk:#232220;--line:#332f2a;
   --ink:#eeebe5;--mid:#a5a095;--faint:#7d776c;
   --ok:#71b593;--ok-s:#1a2721;--s:#d08e64;--s-s:#2b1f18;
   --o:#8f9ad0;--o-s:#1e2130;--x:#d47b7b;--x-s:#2b1a1a}
 *{box-sizing:border-box}
 body{background:var(--ground);color:var(--ink);font-family:var(--sans);
      font-size:15px;line-height:1.5;margin:0}
 .wrap{max-width:800px;margin:0 auto;padding:2.2rem 1.3rem 5rem}
 h1{font-family:var(--serif);font-size:2rem;font-weight:600;margin:0 0 .35rem}
 .lede{color:var(--mid);max-width:62ch;margin:0 0 1rem}
 .how{background:var(--sunk);border-left:3px solid var(--line);
      padding:.7rem .95rem;font-size:.9rem;max-width:64ch;border-radius:0 4px 4px 0}
 .bar{position:sticky;top:0;z-index:10;background:var(--ground);
      border-bottom:1px solid var(--line);padding:.55rem 0;margin:1.2rem 0 .8rem;
      display:flex;gap:.8rem;align-items:center;font-family:var(--mono);
      font-size:.76rem;color:var(--mid)}
 .save{margin-left:auto;font-size:.7rem;padding:.15rem .5rem;border-radius:3px;
       background:var(--sunk);color:var(--faint)}
 .save.on{background:var(--ok-s);color:var(--ok)}
 .save.off{background:var(--x-s);color:var(--x)}
 .item{background:var(--panel);border:1px solid var(--line);border-radius:5px;
       padding:.75rem .95rem;margin:.55rem 0}
 .item.done{border-left:3px solid var(--ok)}
 .n{font-family:var(--mono);font-size:.68rem;color:var(--faint)}
 .n b{color:var(--mid);font-weight:500}
 .v{font-family:var(--serif);font-size:1.02rem;margin:.35rem 0 .5rem;
    color:var(--mid);line-height:1.45}
 .t{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;
    background:var(--sunk);padding:.42rem .6rem;border-radius:3px;
    font-family:var(--mono);font-size:.86rem}
 .t i{font-style:normal;color:var(--faint);font-size:.75rem}
 .t b.vb{background:var(--ink);color:var(--panel);padding:.06rem .38rem;
    border-radius:2px;font-weight:600}
 .arrow{color:var(--faint)}
 .opts{display:flex;gap:.35rem;margin-top:.55rem;flex-wrap:wrap}
 button{font:inherit;font-size:.82rem;background:var(--sunk);
        border:1px solid var(--line);color:var(--mid);padding:.24rem .7rem;
        border-radius:3px;cursor:pointer}
 button:hover{color:var(--ink)}
 button[aria-pressed="true"][data-v="OK"]{background:var(--ok-s);color:var(--ok);
        border-color:var(--ok);font-weight:600}
 button[aria-pressed="true"][data-v="SUBJ"]{background:var(--s-s);color:var(--s);
        border-color:var(--s);font-weight:600}
 button[aria-pressed="true"][data-v="OBJ"]{background:var(--o-s);color:var(--o);
        border-color:var(--o);font-weight:600}
 button[aria-pressed="true"][data-v="BAD"]{background:var(--x-s);color:var(--x);
        border-color:var(--x);font-weight:600}
 button[aria-pressed="true"][data-v="NOVERB"]{background:var(--x-s);
        color:var(--x);border-color:var(--x);font-weight:600;
        text-decoration:underline}
 button:focus-visible{outline:2px solid var(--ink);outline-offset:1px}
 footer{margin-top:2.5rem;border-top:1px solid var(--line);padding-top:1rem;
        color:var(--faint);font-size:.85rem;max-width:64ch}
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
  d.innerHTML='<div class="n">'+(i+1)+' of '+ITEMS.length+' &nbsp;&middot;&nbsp; <b>'
    +it.vref+'</b></div>'
    +'<div class="v">'+it.text+'</div>'
    +'<div class="t"><span>'+(it.s_gloss||"?")+'</span>'
    +'<span class="arrow">&mdash;</span><b class="vb">'+it.v_gloss+'</b>'
    +'<span class="arrow">&rarr;</span><span>'+it.o_gloss+'</span>'
    +'<i>'+(it.lang==="H"?"Hebrew":"Greek")+'</i></div>'
    +'<div class="opts">'
    +'<button data-v="OK">Both right</button>'
    +'<button data-v="SUBJ">Wrong subject</button>'
    +'<button data-v="OBJ">Wrong object</button>'
    +'<button data-v="BAD">Both wrong</button>'
    +'<button data-v="NOVERB">The verb itself is wrong</button></div>';
  host.appendChild(d);
});
function paint(){
  document.querySelectorAll(".item").forEach(el => {
    const v=state.answers[el.dataset.q];
    el.querySelectorAll("button").forEach(b =>
      b.setAttribute("aria-pressed", String(b.dataset.v===v)));
    el.classList.toggle("done", !!v);
  });
  progEl.textContent=Object.keys(state.answers).length+" of "+ITEMS.length+" answered";
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
  dbRef=db.doc("tuples/answers");
  dbRef.onSnapshot(s => {
    if(!s.exists){mark("on","ready");return;}
    if(dirty) return;
    state.answers=Object.assign({}, (s.data()||{}).answers||{});
    paint(); mark("on","saved");
  }, () => mark("off","sync error"));
})();
"""

HTML = """<title>Tuple Floor Check</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;600&family=Archivo:wght@400;500;600&family=IBM+Plex+Mono:wght@400&display=swap">
<style>__CSS__</style>
<div class="wrap">
<h1>Tuple Floor Check</h1>
<p class="lede">Forty subject&ndash;verb&ndash;object triples pulled from the
tagged text by grammar alone &mdash; no model, no relation vocabulary. Does
each one say what the verse says?</p>
<div class="how"><b>Judge each one against its verb, which is shown in bold.</b>
A verse holds several clauses and the extractor can pull its parts from
different ones, so &ldquo;wrong subject&rdquo; only means something once a
clause is fixed. The verb fixes it.
<br><br>So the question is: <i>taking that verb as given, are the subject and
object the ones it governs?</i> If the verb belongs to one clause and the
object was lifted from another, that is <b>wrong object</b>.
<br><br><b>Which part fails matters more than how often</b> &mdash; a wrong
subject and a wrong object need different fixes. And <b>ten of these are
Greek and expected to fail</b>: that rule takes the first nominative and first
accusative in the verse, which breaks wherever a verse holds more than one
clause. They are here to put a number on it, not to be rescued, so don&rsquo;t
labour over them.
<br><br>Answers save as you click.</div>
<div class="bar"><span id="prog">&mdash;</span><span class="save" id="save">loading&hellip;</span></div>
<div id="list"></div>
<footer>The extractor produces 15,065 of these across the canon, free and
instantly &mdash; against 15,023 relations in the graph built by a reasoning
model. Whether that is a floor worth building on or a pile of plausible noise
depends entirely on this sheet.</footer>
</div>
<script>__JS__</script>
"""


def main() -> int:
    items = pick()
    key = [{"i": i, "ref": t["ref"], "lang": t["lang"],
            "s": t["s"], "v": t["v"], "o": t["o"]}
           for i, t in enumerate(items)]
    (ROOT / "out" / "tuple-sheet-key.json").write_text(
        json.dumps(key, indent=1), encoding="utf-8")
    payload = json.dumps([{k: t[k] for k in
                           ("vref", "text", "s_gloss", "v_gloss", "o_gloss", "lang")}
                          for t in items], ensure_ascii=False)
    out = ROOT / "out" / "tuple-sheet.html"
    out.write_text(
        HTML.replace("__CSS__", CSS).replace("__JS__", JS.replace("__ITEMS__", payload)),
        encoding="utf-8")
    nh = sum(1 for t in items if t["lang"] == "H")
    print(f"{len(items)} tuples ({nh} Hebrew, {len(items)-nh} Greek), seed {SEED}")
    print(f"  sheet {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
