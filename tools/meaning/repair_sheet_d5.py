"""DECISION 5 OF THE CONCEPT-REPAIR SHEET, IN FULL (2026-10-20: the section was
unclear when only a few verses were given and some cards lacked verses
altogether).

The first sheet showed three of each card's verses to add and never named the
words to drop or split, so the decision could not be made as built. And four
of its six cards were caught by the word "women", meant for the debates on
women's roles, though none of them is one. This page shows every verse to add
(with the word that brought it, as the verse renders it), every word to drop
or split (its share and the verses both judges read), what each change does to
what readers see, and marks per verse as well as per card.

Reads out/meaning/repairs.jsonl (written by repair_sheet.py); the first sheet
is not rebuilt, so marks already made there are untouched.

    python tools/meaning/repair_sheet_d5.py   -> docs/review/concept-repairs-d5-2026-10-20.html
"""
import collections
import gzip
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "sweep"))
import context as C  # noqa: E402

DEST = ROOT / "docs" / "review" / "concept-repairs-d5-2026-10-20.html"
e = html.escape
CONTESTED = ["the_tithe", "justification"]
NOT_CONTESTED = ["young_women", "daughters_of_canaan", "aged_women", "custom_of_women"]

# what each card's decision turns on, in plain words (the recommendation is a
# default the marks override; nothing is applied by the page)
NOTES = {
    "the_tithe": (
        "Every verse to add names the tithe or the tenth given: the verb <i>to tithe</i> (עָשַׂר) and the Greek "
        "<i>tenth</i> and <i>tithe</i> (δεκάτη, ἀποδεκατόω), Hebrews 7 among them. None is a verse a tradition reads "
        "as teaching whether Christians must tithe; they are the act itself.",
        "Add all ten.",
        "Your note, from the first sheet: <i>maybe there is a related concept of a tenth which has a tie to tithe - "
        "I feel like the bridge should be there</i>. There is no card for <i>a tenth</i> as a measure (עֲשִׂירִית, "
        "\"a tenth of an ephah\", Ex 16:36). Proposed for later: such a card, joined to the tithe, so the measure and "
        "the offering meet without the measure being called a tithe."),
    "justification": (
        "Two parts, and they are not alike. The two verses to add use the noun δικαίωσις itself (Rom 4:25, 5:18): "
        "safe. The split is the real question. Its word, צָדֵק, is the Hebrew <i>be in the right, declare in the "
        "right</i>, and the verses both judges said mean justification are court language: \"justifying the "
        "righteous\" (1 Kgs 8:32), \"I will not acquit the guilty\" (Ex 23:7), \"acquit the guilty for a bribe\" "
        "(Isa 5:23). Putting them on the theological card draws a line from the Old Testament court to Paul. That "
        "line is a well-known argument for one reading of what justification is (a verdict declared) against "
        "others (a making righteous). Today the word is hidden on this card (its share is under the cut), so "
        "readers see none of these verses.",
        "Add the two δικαίωσις verses. Leave צָדֵק as it is now, hidden, and do not add its verses: structure "
        "yes, doctrine no.",
        "If you want the court verses visible somewhere, the neutral home is a card for the legal act itself "
        "(acquit, declare in the right), with its own verses, and no link to this card unless the text makes one."),
    "young_women": (
        "Not contested: caught by the word \"women\". The 66 verses to add come from נַעֲרָה (girl, young woman) and "
        "בְּתוּלָה (virgin), each shown below with the word as the verse renders it. The two drops (אִשָּׁה, γυνή: "
        "<i>woman</i>) are words the site already hides on this card, so dropping them changes nothing readers see.",
        "Add the 66, leaving out any you mark; drop the two words.",
        "Next to a real dispute: the audit's own note says עַלְמָה (young woman) is missing, and adding it would "
        "bring Isa 7:14, where translations divide (\"virgin\" or \"young woman\"). It is not among these 66. If it "
        "is ever proposed, Isa 7:14 comes to you by itself."),
    "daughters_of_canaan": (
        "Not contested: caught by the word \"women\". Nothing to add. The three words to drop are hidden on this card "
        "already; dropping them changes nothing readers see and makes the audit agree with the page.",
        "Drop the three words. The card keeps the verses it cites.",
        "Its audit note: the card is the Hebrew phrase בְּנוֹת כְּנַעַן (literally \"daughters of Canaan\"; the Berean's "
        "\"Canaanite women\", Gen 28:1, 8; 36:2), which decision 3 would anchor by the phrase itself."),
    "aged_women": (
        "Not contested: caught by the word \"women\". Nothing to add. The three words to drop (woman, great, woman) "
        "are hidden on this card already; the two judges together said yes to none of their judged verses.",
        "Drop the three words. The card keeps the verse it cites.",
        "Its audit note: זְקֵנָה (old woman, Zech 8:4) is the word that names it; a later add."),
    "custom_of_women": (
        "Not contested: caught by the word \"women\". Nothing to add. <b>The 0% here is not a measurement:</b> the "
        "judges answered on no verses for these words, and the merge counted that as 0. The case for dropping rests "
        "on the card, not the count: it is one Hebrew idiom, דֶּרֶךְ נָשִׁים (literally \"the way of women\"), which "
        "the Berean renders \"I am having my period\" (Gen 31:35, Rachel), and the words for <i>woman</i> and "
        "<i>custom</i> carry hundreds of verses that are not it. All three are hidden already.",
        "Drop the three words. The card keeps the verse it cites.",
        "The card's name, \"custom of women\", is the KJV's wording of Gen 31:35. Under A.22 it should be renamed; "
        "a name in the Berean's terms, or the literal \"the way of women\", is yours to choose."),
}


def jl(p):
    op = gzip.open if str(p).endswith(".gz") else open
    with op(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def main():
    cards = {c["id"]: c for c in jl(ROOT / "out" / "meaning" / "repairs.jsonl")}
    want = CONTESTED + NOT_CONTESTED
    keys = {k for cid in want for k in cards[cid]["adds"] + cards[cid]["anchors"]
            + [x["key"] for x in cards[cid]["drops"] + cards[cid]["splits"]]}
    refs = {r for cid in want for r in cards[cid]["verses_to_add"]}
    # the word in each verse that brought it, as that verse renders it; and each
    # word's commonest renderings, for a gloss
    in_verse, renders, lemma = collections.defaultdict(list), collections.defaultdict(collections.Counter), {}
    for d in jl(ROOT / "out" / "placeholder-nodes.jsonl.gz"):
        if not d.get("word"):
            continue
        s = re.sub(r"\D", "", str(d.get("strong") or "")).lstrip("0")
        k = ("g" if d.get("lang") == "greek" else "h") + s if s else None
        if k in keys:
            renders[k][(d.get("text") or "").strip().lower()] += 1
            lemma.setdefault(k, d.get("lemma"))
            if d["ref"] in refs:
                in_verse[d["ref"]].append((k, d.get("text") or ""))
    bsb = C._bsb()

    def gloss(k):
        return ", ".join(w for w, _ in renders[k].most_common(4) if w) or "?"

    def word(k):
        return f"{e(lemma.get(k) or '')} <span class=k>{e(k)}: {e(gloss(k))}</span>"

    def verse(r, mid):
        title, text = bsb(r)
        ws = [(k, t) for k, t in in_verse.get(r, [])]
        tag = "; ".join(f"{e(lemma.get(k) or k)} “{e(t)}”" for k, t in ws[:2]) or "<span class=k>word not found</span>"
        return (f"<tr><td class=ref>{e(title)}</td><td>{e(text)}<div class=k>the word: {tag}</div></td>"
                f"<td class=lo><label><input type=checkbox class=out data-id='{e(mid)}' data-ref='{e(r)}'> leave out</label></td></tr>")

    def wordrow(x, kind, mid):
        judged = len(x["yes"]) + len(x["no"])
        share = (f"{int(100 * x['share'])}% of {judged} judged verses mean the card" if judged
                 else "<b>not measured</b>: no verse was judged by both")
        ys = "".join(f"<div><span class=yes>yes</span> {e(bsb(r)[0])}: {e(bsb(r)[1])}</div>" for r in x["yes"][:6])
        ns = "".join(f"<div><span class=no>no</span> {e(bsb(r)[0])}: {e(bsb(r)[1])}</div>" for r in x["no"][:3])
        return (f"<div class=w><p><b>{kind}</b> {word(x['key'])} <span class=k>· {x['uses']:,} uses · {share} · "
                f"{'readers see it on this card now' if x['shown'] else 'already hidden from readers on this card'}</span></p>"
                f"{ys}{ns}<label class=k><input type=checkbox class=keepw data-id='{e(mid)}' data-key='{e(x['key'])}'> "
                f"{'keep this word instead' if kind == 'drop' else 'add its yes verses after all'}</label></div>")

    def card(cid):
        c = cards[cid]
        what, rec, more = NOTES[cid]
        mid = f"d5:{cid}"
        adds = c["verses_to_add"]
        body = [f"<section id='{e(cid)}'><h2>{e(c['name'])} <span class=k>· {e(c['type'] or '')} · cited in "
                f"{c['cited']} verse{'s' if c['cited'] != 1 else ''} · words now: "
                + (", ".join(word(k) for k in c["anchors"]) or "none") + "</span></h2>",
                f"<p>{what}</p><p class=rec><b>Recommended:</b> {rec}</p>"]
        if more:
            body.append(f"<p class=more>{more}</p>")
        if adds:
            body.append(f"<h3>Verses to add <span class=k>· {len(adds)}, each said yes by both passes; "
                        f"tick any to leave out</span></h3><table>"
                        + "".join(verse(r, mid) for r in adds) + "</table>")
        for x in c["drops"]:
            body.append(wordrow(x, "drop", mid))
        for x in c["splits"]:
            body.append(wordrow(x, "split", mid))
        body.append(f"<div class=mk data-id='{e(mid)}'><label><input type=radio name='{e(mid)}' value=''> as recommended</label>"
                    f"<label><input type=radio name='{e(mid)}' value=override> override</label>"
                    f"<label><input type=radio name='{e(mid)}' value=discuss> discuss</label>"
                    f"<textarea class=nt rows=2 placeholder='what you would change, or want to talk about'></textarea></div></section>")
        return "".join(body)

    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Concept repairs: decision 5</title><style>
:root{{--paper:#F3F5F8;--surface:#fff;--ink:#141F2C;--muted:#5C6A7B;--rule:#BAC4D0;--accent:#356A8C;--ok:#1F7A4D;--bad:#A23B3B;--warn:#8A5A00}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2C3A4A;--accent:#7FB2D6;--ok:#5CC28F;--bad:#E58A8A;--warn:#E0B060}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Georgia,serif}} main{{max-width:1040px;margin:0 auto;padding:16px}}
section{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:8px 14px;margin:14px 0;overflow-x:auto}}
h2{{font-size:18px;margin:6px 0}} h3{{font-size:15px;margin:12px 0 4px}} .k{{color:var(--muted);font-size:13px}}
table{{border-collapse:collapse;width:100%}} td{{text-align:left;vertical-align:top;padding:5px 6px;border-bottom:1px solid var(--rule);font-size:13.5px}}
td.ref{{white-space:nowrap;width:9em}} td.lo{{white-space:nowrap;width:7em;font-size:12.5px}}
.yes,.no{{font:11px system-ui,sans-serif;border-radius:6px;padding:0 5px;margin-right:4px}} .yes{{color:var(--ok);border:1px solid var(--ok)}} .no{{color:var(--bad);border:1px solid var(--bad)}}
.w{{border-top:1px solid var(--rule);margin-top:8px;padding-top:4px;font-size:13.5px}} .w p{{margin:4px 0}}
.rec{{border-left:3px solid var(--ok);padding-left:8px}} .more{{border-left:3px solid var(--warn);padding-left:8px;font-size:14px}}
.mk{{font-size:13px;border-top:1px dashed var(--rule);margin-top:10px;padding-top:6px}} .mk label{{margin-right:12px}}
.nt{{display:block;margin-top:6px;width:min(620px,100%);font:inherit;font-size:13.5px;background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:5px}}
.group{{margin:22px 0 4px;font-size:20px}} button{{font:inherit;padding:5px 12px;border-radius:6px;border:1px solid var(--accent);background:var(--surface);color:var(--accent)}}
#out{{display:block;width:100%;margin-top:6px;font:12px monospace;background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:5px}}
</style></head><body><main><h1>Concept repairs: decision 5, in full</h1>
<p>The first sheet showed three verses per card and never named the words to drop. Here is everything each change would
do. Two cards are where the verses could take a side; four were caught by the word "women" and are ordinary repairs.
<b>Each card is set to "as recommended" until you mark it.</b> Tick "leave out" on any verse you would not add, and
"keep this word" on any drop you would not make. Nothing is applied by this page.</p>
<p><button id=exp>Copy my marks</button> <span id=st class=k></span></p>
<h2 class=group>Where the verses could take a side</h2>{''.join(card(c) for c in CONTESTED)}
<h2 class=group>Caught by the word "women": not contested</h2>{''.join(card(c) for c in NOT_CONTESTED)}
</main><script>
const KEY='concept-repairs-d5-2026-10-20'; let M={{}}; try{{M=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(M))}}catch(e){{}}}}
function rec(id){{return M[id]=M[id]||{{mark:'',note:'',leave_out:[],keep_words:[]}}}}
document.querySelectorAll('.mk').forEach(m=>{{const id=m.dataset.id,s=rec(id);
 m.querySelectorAll('input[type=radio]').forEach(i=>{{if(i.value===(s.mark||''))i.checked=true;i.onchange=()=>{{rec(id).mark=i.value;save()}}}});
 const n=m.querySelector('.nt');n.value=s.note||'';n.addEventListener('input',()=>{{rec(id).note=n.value;save()}});}});
function boxes(cls,field,attr){{document.querySelectorAll('.'+cls).forEach(b=>{{const s=rec(b.dataset.id),v=b.dataset[attr];
 b.checked=(s[field]||[]).includes(v);
 b.onchange=()=>{{const a=new Set(rec(b.dataset.id)[field]||[]);b.checked?a.add(v):a.delete(v);rec(b.dataset.id)[field]=[...a];save()}}}})}}
boxes('out','leave_out','ref'); boxes('keepw','keep_words','key');
// the marks are read from the page itself at the moment of copying, not only
// from storage, so a note typed and not yet saved is never lost
document.getElementById('exp').onclick=async()=>{{
 document.querySelectorAll('.mk').forEach(m=>{{const s=rec(m.dataset.id);const r=m.querySelector('input[type=radio]:checked');
  s.mark=r?r.value:'';s.note=m.querySelector('.nt').value}});save();
 const x=JSON.stringify({{sheet:KEY,marks:M}},null,1);
 let box=document.getElementById('out');
 if(!box){{box=document.createElement('textarea');box.id='out';box.rows=10;box.readOnly=true;document.getElementById('st').after(box)}}
 box.value=x;box.focus();box.select();let ok=false;
 try{{await navigator.clipboard.writeText(x);ok=true}}catch(e){{try{{ok=document.execCommand('copy')}}catch(e2){{}}}}
 document.getElementById('st').textContent=ok?'Copied: paste it into the chat.':'Press Ctrl+C to copy the selected marks below, then paste them into the chat.'}};
</script></body></html>"""
    DEST.write_text(page, encoding="utf-8")
    print(f"{len(want)} cards; {sum(len(cards[c]['verses_to_add']) for c in want)} verses to add; "
          f"{sum(len(cards[c]['drops']) for c in want)} drops; {sum(len(cards[c]['splits']) for c in want)} splits; "
          f"verses with no word found: {sum(1 for c in want for r in cards[c]['verses_to_add'] if not in_verse.get(r))} "
          f"-> {DEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
