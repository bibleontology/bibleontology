"""THE PANEL OF ELEVEN ON THE HELD DIVINE ENDS, AS DECISIONS FOR RULING
(B4 of the committee sheet, 2026-10-19). Nothing is released by this sheet:
divine persons are resolved only by hand, record by record; the sheet puts
the panel's evidence in front of that ruling.

    python tools/meaning/divine_sheet.py   -> docs/review/divine-ends-2026-10-19.html
"""
import collections
import html
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "sweep"))
import context as C  # noqa: E402

DEST = ROOT / "docs" / "review" / "divine-ends-2026-10-19.html"
NAMES = {"god": "God", "jesus": "Jesus"}
e = html.escape


def main():
    bsb = C._bsb()
    rows = [json.loads(x) for x in (ROOT / "out/meaning/divine-panel/verdicts.jsonl").read_text(encoding="utf-8").splitlines()]
    cand = [r for r in rows if r["verdict"].startswith("candidate")]
    obj = sorted([r for r in rows if r["verdict"] == "objected"], key=lambda r: r["ref"])
    opn = sorted([r for r in rows if r["verdict"] == "held open"], key=lambda r: r["ref"])
    by = collections.Counter((r["person"], r["verdict"]) for r in rows)
    random.seed(19)

    def verse(r):
        refs = []
        for c in r["chain"]:
            if c["ref"] and c["ref"] not in refs:
                refs.append(c["ref"])
        return "".join(f"<div class=v><b>{e(x)}</b> {e(bsb(x)[1] or '')}</div>" for x in sorted(refs))

    def chain(r):
        w = r["chain"][0]["text"] or "(unstated subject)"
        return (f"<b>“{e(w)}”</b> → " + " → ".join(f"“{e(c['text'] or '')}” {e(c['ref'] or '')}" for c in r["chain"][1:])
                + f" = <b>{NAMES.get(r['person'], r['person'])}</b>")

    def objections(r):
        seen, out = set(), []
        for o in (r["pass1"] or []) + (r["pass2"] or []):
            k = (o.get("seat"), o.get("why"))
            if k not in seen:
                seen.add(k)
                out.append(f"<li><span class={'no' if o.get('kind') == 'object' else 'un'}>{e(o.get('kind') or '')}</span> "
                           f"<b>{e((o.get('seat') or '').replace('_', ' '))}</b>: {e(o.get('why') or '')}</li>")
        return "<ul>" + "".join(out[:6]) + "</ul>"

    def marks(mid):
        return f"<div class=mk data-id='{e(mid)}'></div>"

    sample = random.sample(cand, 40)
    s_rows = "".join(f"<div class=q>{chain(r)}{verse(r)}</div>" for r in sorted(sample, key=lambda r: r["ref"]))
    o_rows = "".join(f"<div class=q>{chain(r)}{verse(r)}{objections(r)}</div>" for r in obj)
    p_rows = "".join(f"<div class=q>{chain(r)}{verse(r)}{objections(r)}</div>" for r in opn)
    body = f"""
<section><h2>1. Release the words no reader objects to <span class=k>· {len(cand):,}: God {by[('god', 'candidate: no seat objects, both passes')]:,}, Jesus {by[('jesus', 'candidate: no seat objects, both passes')]:,}</span></h2>
<p>Each word was followed back to God or Jesus by the structure, then read by the panel of eleven twice, independently,
in a different order each time. In both passes no seat objected or held it open. Most are plain narrative and speech:
"I am the LORD", "He said to Moses".</p>
<p class=rec><b>Recommended: release them as a class, by your ruling</b>, each credited as a reading (the structure's
pointer chain, the panel's two passes) and recorded as your spot-check approval, not a line-by-line review. Released
words then go through the statement judges like any other (plan 2.17), so a wrong statement can still be dropped.</p>
<details open><summary>A random 40 to spot-check</summary>{s_rows}</details>{marks('d1-release')}</section>

<section><h2>2. Objected: mostly a wrong pointer, not a question about God <span class=k>· {len(obj)}: God {by[('god', 'objected')]}, Jesus {by[('jesus', 'objected')]}</span></h2>
<p>At least one reader read the word as pointing to someone else, and most are plainly right: in Deut 15:2 "he" is the
creditor; in Ezek 33:27 "him" is the one in the open field; in Mark 9:35 "he" is anyone who wants to be first. Those
are faults in the sweep's pointer links, wrong wherever they are used, not only here.</p>
<p class=rec><b>Recommended: keep all of these held, and send each link back to the sweep as a correction</b> (two
judges, as every sweep correction is), so the fault is fixed at the layer that made it (plan 2.18).</p>
<details><summary>All {len(obj)}, with each objection</summary>{o_rows}</details>{marks('d2-objected')}</section>

<section><h2>3. Held open: where the text itself is disputed <span class=k>· {len(opn)}: God {by[('god', 'held open')]}, Jesus {by[('jesus', 'held open')]}</span></h2>
<p>No reader said the pointer is wrong, but at least one tradition holds the reference open: 1 John 5:16 "he will give
life" (God, or the one who prays), 1 John 3:2 "we shall see Him" (the Father or Christ).</p>
<p class=rec><b>Recommended: these stay held, permanently</b>, and become the first entries of the page of where the
text is open (plan 8.5, item 6): the candidates shown, nothing decided.</p>
<details><summary>All {len(opn)}, with what each reader said</summary>{p_rows}</details>{marks('d3-open')}</section>"""

    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Divine ends</title><style>
:root{{--paper:#F3F5F8;--surface:#fff;--ink:#141F2C;--muted:#5C6A7B;--rule:#BAC4D0;--accent:#356A8C;--ok:#1F7A4D;--warm:#96591A;--bad:#A23B3B}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2C3A4A;--accent:#7FB2D6;--ok:#5CC28F;--warm:#E2B04A;--bad:#E58A8A}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Georgia,serif}} main{{max-width:980px;margin:0 auto;padding:16px}}
section{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:8px 14px;margin:14px 0;overflow-x:auto}}
h2{{font-size:18px;margin:6px 0}} .k{{color:var(--muted);font-size:13px}} .rec{{border-left:3px solid var(--ok);padding-left:8px}}
.q{{border-bottom:1px solid var(--rule);padding:6px 0;font-size:14px}} .v{{font-size:13.5px;color:var(--muted);margin:2px 0 0 10px}}
.no,.un{{font:11px system-ui,sans-serif;border-radius:6px;padding:0 5px}} .no{{color:var(--bad);border:1px solid var(--bad)}} .un{{color:var(--warm);border:1px solid var(--warm)}}
ul{{margin:4px 0 4px 18px;padding:0;font-size:13.5px}} details{{margin:6px 0}}
.mk{{font-size:13px;border-top:1px dashed var(--rule);margin-top:8px;padding-top:6px}} .mk label{{margin-right:10px}}
.nt{{display:block;margin-top:4px;width:min(520px,100%);font:inherit;font-size:13px;background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:5px}}
button{{font:inherit;padding:5px 12px;border-radius:6px;border:1px solid var(--accent);background:var(--surface);color:var(--accent)}}
</style></head><body><main><h1>Words that reach God or Jesus through a pointer</h1>
<p>{len(rows):,} words reach God or Jesus only by following "he", "him", "I" back through the text. They were held,
because divine persons are resolved only by your ruling. The panel of eleven read every one twice
(<code>tools/meaning/divine_panel.py</code>, 8.0M tokens), on one question: does this word point to that person, as a
careful reader of each tradition reads the text? Reference, not belief. <b>Mark only what you want to override or
discuss</b>; unmarked goes as recommended. Nothing is released until you have marked this sheet.</p>
<p class=k>Objections by seat, across both passes: secular 489, rabbi 388, biblical-theological 270, reformed 186,
orthodox 147, lutheran 146, baptist 143, catholic 140, young African American believer 136, wesleyan 134, pentecostal
132. Two words were not read by both passes and stay held.</p>
<p><button id=exp>Copy my marks</button> <span id=st class=k></span></p>
{body}</main><script>
document.querySelectorAll('.mk').forEach(m=>{{const id=m.dataset.id;
 m.innerHTML=`<label><input type=radio name="${{id}}" value=override> override</label><label><input type=radio name="${{id}}" value=discuss> discuss</label><label><input type=radio name="${{id}}" value=""> as recommended</label><input class=nt placeholder="what you would change, or want to talk about">`}});
const KEY='divine-ends-2026-10-19'; let M={{}}; try{{M=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(M))}}catch(e){{}}}}
document.querySelectorAll('.mk').forEach(m=>{{const id=m.dataset.id,s=M[id]||{{}};
 m.querySelectorAll('input[type=radio]').forEach(i=>{{if(i.value===s.mark)i.checked=true;i.onchange=()=>{{(M[id]=M[id]||{{}}).mark=i.value;save()}}}});
 const n=m.querySelector('.nt');n.value=s.note||'';n.oninput=()=>{{(M[id]=M[id]||{{}}).note=n.value;save()}};}});
// the marks are always shown in a box, selected: a sandboxed viewer blocks both
// the clipboard and prompt() (2026-10-19)
document.getElementById('exp').onclick=async()=>{{const x=JSON.stringify({{sheet:KEY,marks:M}},null,1);
 let box=document.getElementById('out');
 if(!box){{box=document.createElement('textarea');box.id='out';box.rows=8;box.readOnly=true;
  box.style.cssText='display:block;width:100%;margin-top:6px;font:12px monospace;background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:5px';
  document.getElementById('st').after(box)}}
 box.value=x;box.focus();box.select();let ok=false;
 try{{await navigator.clipboard.writeText(x);ok=true}}catch(e){{try{{ok=document.execCommand('copy')}}catch(e2){{}}}}
 document.getElementById('st').textContent=ok?'Copied: paste it into the chat.':'Press Ctrl+C to copy the selected marks below, then paste them into the chat.'}};
</script></body></html>"""
    DEST.write_text(page, encoding="utf-8")
    print(f"{len(rows)} words: {len(cand)} candidates, {len(obj)} objected, {len(opn)} open -> {DEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
