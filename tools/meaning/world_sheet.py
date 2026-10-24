"""'WORLD', THE WORKED EXAMPLE: A DECISION SHEET (plan 8.2b; 2026-10-18:
continue on "world").

An override sheet, in the form requested on the 1.2.0 inventory: each
decision in plain words, with an example, a recommendation and its reason;
the reader marks only what would be overridden or discussed. The evidence comes from
out/meaning/world-evidence.json (gathered 2026-10-18 and re-counted by Claude:
κόσμος 185 occurrences in 150 verses, John 57; οἰκουμένη 15; תֵּבֵל 36).

    python tools/meaning/world_sheet.py   -> docs/review/world-2026-10-18.html
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "sweep"))
import context as C  # noqa: E402

e = html.escape


def main():
    ev = json.loads((ROOT / "out" / "meaning" / "world-evidence.json").read_text(encoding="utf-8"))
    bsb = C._bsb()
    w = ev["words"]
    k, o, t = w["kosmos"], w["oikoumene"], w["tevel"]
    john = [v for v in k["verse_list"] if str(v.get("ref", "")).startswith("Jhn.")]
    uncarried = ev["coverage"]["kosmos"]["no_record_verse_list"]

    def verses(refs):
        return "".join(f"<div class=v><b>{e(bsb(r)[0])}</b> {e(bsb(r)[1])}</div>" for r in refs)

    def marks(mid):
        return (f"<div class=mk data-id='{e(mid)}'><label><input type=radio name='{e(mid)}' value=override> override</label>"
                f"<label><input type=radio name='{e(mid)}' value=discuss> discuss</label>"
                f"<label><input type=radio name='{e(mid)}' value=''> as recommended</label>"
                f"<input class=nt placeholder='what you would change, or want to talk about'></div>")

    D = [
        ("concept", "'World' becomes a concept again, at the same address",
         "Today /e/world is filed as a place, carrying one verse (Job 18:18). It began as a concept; on 28 September a model's sorting pass refiled it as a place, recording no reason. No one ruled on it.",
         ["Jhn.1.10"], "Make it a concept, keeping /e/world so every link to it still works.",
         "The text uses the word for the created order, for people, and for the order set against God, none of them a place on a map."),
        ("words", "Organised by its original words, carrying all their verses",
         f"The card carries every verse of its three words, grouped by word: κόσμος ({k['verses']} verses, John {len(john)} of them), οἰκουμένη ({o['verses']}), and the Hebrew תֵּבֵל ({t['verses']}). Today {len(uncarried)} of κόσμος's verses are carried by no card at all, John 17 among them.",
         ["Psa.24.1", "Luk.2.1"], "Include all three words.",
         "The translation varies, the word does not: the Berean renders οἰκουμένη 'the whole empire' in Luke 2:1. Grouping by the original keeps those together."),
        ("adornment", "One use of κόσμος is not 'world' at all",
         "κόσμος also means adornment, its first meaning in Greek. 1 Peter 3:3 is that sense, and it does not belong on the world card.",
         ["1Pe.3.3"], "Leave 1 Peter 3:3 off the world card (it stays on κόσμος's word page).",
         "A card that shows a verse claims the verse is about it."),
        ("earth", "'Earth' stays its own card, linked, not merged",
         f"Earth is a different word (אֶרֶץ, about 2,181 verses; γῆ, 223), mostly 'land' or 'ground'. The poetry sets the two side by side, and the cards link there.",
         ["Psa.24.1"], "A link between the two cards, citing the verses that pair them; no merge.",
         "Your rule: consolidation joins one thing recorded twice, never two related things."),
        ("senses", "Senses, only where the verse makes them plain",
         "Proposed senses: (1) the created order; (2) people at large; (3) the world as set against God; (4) the inhabited earth (mostly οἰκουμένη). A verse gets a sense only where two judges agree it is plain, shown as a reading; otherwise none.",
         ["Act.17.24", "Jhn.12.19", "Jhn.15.18"], "These four, assigned by two judges agreeing, as with the warnings.",
         "They are the uses the verses themselves separate; a sense is a reading, never a fact."),
        ("divided", "Where traditions divide, no sense at all",
         "Some verses are read differently by different traditions as to whom 'the world' includes: John 3:16, 1 John 2:2, and others where the world is what God loves or saves. These get no sense, whatever the judges say, and the card does not group them under one.",
         ["Jhn.3.16", "1Jn.2.2"], "No sense on any verse where the world is the object of God's love or saving work; you review the list before it ships.",
         "Structure yes, doctrine no: the site takes no position on who 'the world' is in these verses, and grouping them under 'people at large' would."),
        ("john316", "John 3:16, end to end",
         "On the verse: the Berean text with its original words; κόσμος links to the world card; the verse's structure (God loved the world, so He gave His Son, so that everyone who believes has life) is checked clause by clause; no sense is shown for 'world'. On the card: 3:16 is listed under κόσμος and John, without a sense.",
         ["Jhn.3.16"], "Check the verse's structure and links by hand and fix what is wrong, before anything else on the card ships.",
         "Your words: 'john 3:16 is a go to verse so we need to handle this one well.'"),
    ]
    body = "".join(
        f"<section><h2>{i}. {e(title)}</h2><p>{e(what)}</p>{verses(ex)}"
        f"<p class=rec><b>Recommended:</b> {e(rec)} <span class=k>{e(why)}</span></p>{marks('world:' + did)}</section>"
        for i, (did, title, what, ex, rec, why) in enumerate(D, 1))
    john_list = "".join(f"<div class=v><b>{e(bsb(v['ref'])[0])}</b> {e(bsb(v['ref'])[1])}</div>" for v in john)
    unc = "".join(f"<div class=v><b>{e(bsb(r)[0])}</b> {e(bsb(r)[1])}</div>" for r in uncarried)
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>World</title><style>
:root{{--paper:#F3F5F8;--surface:#fff;--ink:#141F2C;--muted:#5C6A7B;--rule:#BAC4D0;--accent:#356A8C;--ok:#1F7A4D}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2C3A4A;--accent:#7FB2D6;--ok:#5CC28F}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 Georgia,serif}} main{{max-width:860px;margin:0 auto;padding:16px}}
section{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:8px 16px;margin:14px 0}}
h2{{font-size:18px;margin:6px 0}} .k{{color:var(--muted);font-size:13.5px}} .v{{border-left:3px solid var(--accent);padding:1px 10px;margin:5px 0;font-size:14.5px}}
.rec{{border-left:3px solid var(--ok);padding-left:8px}} .mk{{font-size:13px;border-top:1px dashed var(--rule);margin-top:8px;padding-top:6px}} .mk label{{margin-right:10px}}
.nt{{display:block;margin-top:4px;width:min(520px,100%);font:inherit;font-size:13px;background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:5px}}
details{{margin:6px 0}} button{{font:inherit;padding:5px 12px;border-radius:6px;border:1px solid var(--accent);background:var(--surface);color:var(--accent)}}
</style></head><body><main><h1>"World": the worked example</h1>
<p>Plan 8.2b. Today the site files "world" as a place with one verse, while κόσμος alone is in 150 verses, 57 in
John. Below are the decisions to fix it, each with what I recommend and why. <b>Mark only what you would override or
want to discuss</b>; the rest goes as recommended. Nothing changes on the site until you have seen it.</p>
<p><button id=exp>Copy my marks</button> <span id=st class=k></span></p>
{body}
<section><h2>The evidence</h2>
<details><summary>κόσμος in John: {len(john)} verses</summary>{john_list}</details>
<details><summary>κόσμος verses no card carries today: {len(uncarried)}</summary>{unc}</details>
<p class=k>Counts: κόσμος {k['occurrences']} occurrences in {k['verses']} verses; οἰκουμένη {o['verses']}; תֵּבֵל {t['verses']}.
Gathered from MACULA's word data and re-counted.</p></section>
</main><script>
const KEY='world-2026-10-18'; let M={{}}; try{{M=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(M))}}catch(e){{}}}}
document.querySelectorAll('.mk').forEach(m=>{{const id=m.dataset.id,s=M[id]||{{}};
 m.querySelectorAll('input[type=radio]').forEach(i=>{{if(i.value===s.mark)i.checked=true;i.onchange=()=>{{(M[id]=M[id]||{{}}).mark=i.value;save()}}}});
 const n=m.querySelector('.nt');n.value=s.note||'';n.oninput=()=>{{(M[id]=M[id]||{{}}).note=n.value;save()}};}});
document.getElementById('exp').onclick=async()=>{{const x=JSON.stringify({{sheet:KEY,marks:M}},null,1);
 try{{await navigator.clipboard.writeText(x);document.getElementById('st').textContent='Copied: paste it into the chat.'}}catch(e){{prompt('Copy this',x)}}}};
</script></body></html>"""
    dest = ROOT / "docs" / "review" / "world-2026-10-18.html"
    dest.write_text(page, encoding="utf-8")
    print(f"{len(D)} decisions, John {len(john)}, uncarried {len(uncarried)} ->", dest.relative_to(ROOT))


if __name__ == "__main__":
    main()
