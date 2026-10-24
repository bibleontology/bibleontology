"""THE CONCEPT-REPAIR SHEET (2026-10-18: a prioritized backlog of concept
repairs is to be built from this data; 2026-10-19: the concept repair sheet
approved).

Brings together, per card:
  the audit's phase 1   words to add, a grade, notes on what the words miss;
                        the 472 cards the book-name bug touched taken from the
                        re-judge (sonnet-2, card-2), the rest from the first run
  phase 2               verses a repair would add, kept where BOTH passes said
                        yes AND the verse holds a word the final phase 1 still adds
  the sense flags       a card's own word judged on 20 of its verses by two
                        models: drop (<30% mean the card), split by verse
                        (30-60%), keep (>=60%)

The sheet is a few decisions, each a rule over many cards with a spot-check in
full verse text, and the cases that need a reader's eye listed one by one. Marks
default to the recommendation (override / discuss); nothing is applied by the
sheet. Applying it is plan 4.8's one card pipeline.

    python tools/meaning/repair_sheet.py   -> docs/review/concept-repairs-2026-10-19.html,
                                              out/meaning/repairs.jsonl (the decisions' data)
"""
import collections
import gzip
import html
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
M = ROOT / "out" / "meaning"
sys.path.insert(0, str(ROOT / "tools" / "sweep"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
import context as C  # noqa: E402
from concept_verses import _verdicts  # noqa: E402

DEST = ROOT / "docs" / "review" / "concept-repairs-2026-10-19.html"
# cards where deciding which verses "speak of" the concept could take a side
# (memory: structure yes, doctrine no); listed for a reader's eye, never bulk
CONTESTED = re.compile(r"baptis|elect|predestin|foreknow|chosen|persever|rapture|millenn|tongues|dispensation|"
                       r"sabbath|tithe|eucharist|lord's supper|communion|justif|sanctif|free will|hell|"
                       r"eternal security|apostasy|falling away|gifts of the spirit|prophecy|women|divorce", re.I)
FUNCTION = {"the", "a", "an", "of", "and", "his", "her", "my", "your", "our", "their", "its", "to", "in", "on",
            "for", "with", "by", "from", "that", "this", "who", "which", "me", "him", "them", "us", "is", "be"}
PRONOUNS = {"me", "my", "mine", "your", "yours", "you", "his", "him", "her", "hers", "our", "us", "we", "their",
             "them", "they", "i", "thy", "thee", "thou"}
e = html.escape


def jl(p):
    op = gzip.open if str(p).endswith(".gz") else open
    with op(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def phase1(d, runs):
    out = {}
    for r in runs:                      # later runs override earlier
        for p in sorted((d / r).glob("A-*.json")):
            for c in json.loads(p.read_text(encoding="utf-8")).get("cards") or []:
                out[c.get("id")] = c
    return out


def vpass(d, run):
    return {p.stem[2:]: json.loads(p.read_text(encoding="utf-8")).get("verses") or {} for p in (d / run).glob("V-*.json")}


def main():
    random.seed(19)
    bsb = C._bsb()
    ents = {x["id"]: x for x in jl(ROOT / "ontology" / "entities" / "entities.jsonl")}
    verses_of = collections.defaultdict(set)
    lemma = {}
    for d in jl(ROOT / "out" / "placeholder-nodes.jsonl.gz"):
        if d.get("word") and d.get("class") in ("noun", "verb", "adj"):
            s = re.sub(r"\D", "", str(d.get("strong") or "")).lstrip("0")
            if s:
                k = ("g" if d.get("lang") == "greek" else "h") + s
                verses_of[k].add(d["ref"])
                lemma.setdefault(k, d.get("lemma"))

    cards, before = {}, {}
    for kind, d, p1runs, vruns in (("concept", M / "concept-audit", ["sonnet-1", "sonnet-2"],
                                    [("verses-1", "verses-2"), ("verses-3", "verses-4")]),
                                   ("other", M / "card-audit", ["card-1", "card-2"], [("verses-1", "verses-2")])):
        items = {i["id"]: i for i in json.loads((d / "items.json").read_text(encoding="utf-8"))}
        first = phase1(d, p1runs[:1])
        final = phase1(d, p1runs)
        rejudged = set(phase1(d, p1runs[1:]))
        yes = collections.defaultdict(set)
        for a, b in vruns:
            va, vb = vpass(d, a), vpass(d, b)
            for cid in set(va) & set(vb):
                yes[cid] |= {r for r, x in va[cid].items() if x == "yes" and vb[cid].get(r) == "yes"}
        for cid, it in items.items():
            a = final.get(cid)
            if not a:
                continue
            adds = [k for k, x in _verdicts(a.get("candidates")).items() if x == "add"]
            have = set().union(set(), *[verses_of[x["key"]] for x in it["anchors"]])
            ok = sorted(v for v in yes.get(cid, set()) if any(v in verses_of[k] for k in adds))
            judged_adds = {k for k, x in _verdicts((first.get(cid) or {}).get("candidates")).items() if x == "add"}
            cards[cid] = {"id": cid, "kind": kind, "type": ents.get(cid, {}).get("type"), "name": it["name"],
                          "cited": it["cited"], "verses_now": len(have), "grade": a.get("grade"),
                          "confidence": a.get("confidence"), "missing": a.get("missing") or [],
                          "anchors": [x["key"] for x in it["anchors"]], "adds": adds,
                          "adds_not_yet_judged": sorted(set(adds) - judged_adds),
                          "verses_to_add": ok, "drops": [], "splits": [], "kept_after_check": []}
            if cid in first and cid in rejudged:
                before[cid] = (first[cid].get("grade"), a.get("grade"))

    # WHAT READERS SEE: the server shows a card's anchor only at a share of
    # 0.15 or more (word cards), plus the words of its own cited verses
    # (app2/server.py _anchors). The audit and the resolver took every anchor
    # (the practitioner's finding, committee 2026-10-19): 621 of the 833 drops
    # were already hidden
    import membership as Mb                  # the one definition (plan 4.8 step 0(a))
    shown = {cid: {k for k, _s in base} for cid, base in Mb.anchors(jl(ROOT / "out" / "concept-anchors.jsonl.gz")).items()}
    senses = list(jl(M / "concept-audit" / "senses.jsonl"))
    for s in senses:
        c = cards.get(s["card"])
        if not c:
            continue
        row = {"key": s["key"], "lemma": s["lemma"], "uses": s["uses"], "share": s["share_yes"],
               "yes": s["yes_verses"], "no": s["no_verses"], "shown": s["key"] in shown.get(s["card"], set())}
        {"drop candidate": c["drops"], "mixed: split by verse": c["splits"], "keep": c["kept_after_check"]}[s["verdict"]].append(row)

    # a card the drops would leave with no words of its own
    for c in cards.values():
        c["left_without_words"] = bool(c["anchors"]) and not (set(c["anchors"]) - {x["key"] for x in c["drops"]}) \
            and not c["adds"]
        c["contested"] = bool(CONTESTED.search(c["name"] or ""))
        # a card named by a PHRASE ("the hand of the Lord") taking a single word's
        # verses is the drops' fault coming back in through the adds (the first
        # sheet's spot-check: Ps 110:5 "at Your right hand"); held, not added
        # and a name with a pronoun is a fragment of a verse, not a concept ("crushed
        # me" took Mic 1:7's smashed idols; "your children" took the Child, Matt 2:13)
        ws = [w.lower() for w in re.findall(r"[A-Za-z']+", c["name"] or "")]
        c["phrase"] = len([w for w in ws if w not in FUNCTION]) >= 2 or any(w in PRONOUNS for w in ws)
    (M / "repairs.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cards.values()),
                                     encoding="utf-8")

    # ---------------------------------------------------------------- the page
    def vt(r):
        return e(bsb(r)[1] or "")

    def marks(mid):
        return (f"<div class=mk data-id='{e(mid)}'><label><input type=radio name='{e(mid)}' value=override> override</label>"
                f"<label><input type=radio name='{e(mid)}' value=discuss> discuss</label>"
                f"<label><input type=radio name='{e(mid)}' value=''> as recommended</label>"
                f"<input class=nt placeholder='what you would change, or want to talk about'></div>")

    allc = list(cards.values())
    c_add = [c for c in allc if c["verses_to_add"] and not c["contested"] and not c["phrase"]]
    n_add = sum(len(c["verses_to_add"]) for c in c_add)
    p_add = sorted([c for c in allc if c["verses_to_add"] and c["phrase"] and not c["contested"]], key=lambda c: -c["cited"])
    drops = [(c, x) for c in allc for x in c["drops"]]
    splits = [(c, x) for c in allc for x in c["splits"]]
    keeps = [(c, x) for c in allc for x in c["kept_after_check"]]
    orphans = sorted([c for c in allc if c["left_without_words"]], key=lambda c: -c["cited"])
    contested = sorted([c for c in allc if c["contested"] and (c["verses_to_add"] or c["drops"] or c["splits"])],
                       key=lambda c: -c["cited"])
    changed_grade = collections.Counter(f"{a} → {b}" for a, b in before.values() if a != b)
    pending = sum(len(c["adds_not_yet_judged"]) for c in allc)

    body = []
    # D1: verses to add
    sample = random.sample([(c, v) for c in c_add for v in c["verses_to_add"]], 24)
    rows = "".join(f"<tr><td><b>{e(c['name'])}</b><br><span class=k>{e(c['type'] or '')}</span></td><td>{e(v)}</td>"
                   f"<td>{vt(v)}</td></tr>" for c, v in sorted(sample, key=lambda x: x[0]['name']))
    body.append(f"<section><h2>1. Add the verses both passes agreed on <span class=k>· {n_add:,} verses on {len(c_add)} cards</span></h2>"
                f"<p>Each verse uses a word the audit said names the card's concept, and two independent passes each read "
                f"the verse and said it speaks of the concept. A verse is counted only if the word is still an add after "
                f"this morning's re-judge. Cards named by a phrase are not here (decision 3) and neither are the "
                f"contested ones (decision 5).</p><p class=rec><b>Recommended: add, as readings</b> (credited to the audit, "
                f"two judges).</p>"
                f"<details open><summary>A random 24 to spot-check</summary><table><tr><th>card</th><th>verse</th><th>Berean</th></tr>"
                f"{rows}</table></details>{marks('d1-add-verses')}</section>")
    # D2: drops
    d_shown = sum(1 for _, x in drops if x["shown"])
    dsample = random.sample([(c, x) for c, x in drops if x["shown"]], min(14, d_shown))
    drows = "".join(
        f"<tr><td><b>{e(c['name'])}</b></td><td>{e(x['lemma'] or '')} <span class=k>{e(x['key'])}, {x['uses']:,} uses</span><br>"
        f"<span class=k>{int(100 * x['share'])}% mean the card</span></td><td>"
        + "".join(f"<div><span class=no>no</span> {e(r)} {vt(r)}</div>" for r in x["no"][:2])
        + "".join(f"<div><span class=yes>yes</span> {e(r)} {vt(r)}</div>" for r in x["yes"][:1]) + "</td></tr>"
        for c, x in dsample)
    body.append(f"<section><h2>2. Drop a card's word where it mostly means something else <span class=k>· {len(drops)} words on "
                f"{len({c['id'] for c, _ in drops})} cards</span></h2>"
                f"<p>Each word was read in 20 of its verses, spread over all its uses, by two models blind to each other. "
                f"These are the words both put under 30%. Most are cards named by a phrase that carry a common word: "
                f"\"faithful saying\" carried אָמַר <i>say</i> and so every verse where anyone says anything.</p>"
                f"<p><b>Only {d_shown} of the {len(drops)} change what readers see.</b> The other {len(drops) - d_shown} "
                f"are words the site already hides (their share is under 0.15), but the audit and the new resolution layer "
                f"still used them. Dropping them makes all three agree with the page. (The committee's practitioner found "
                f"the mismatch; one shared definition of a card's words is proposed.)</p>"
                f"<p class=rec><b>Recommended: drop.</b> The card keeps the verses it cites and its other words; the few "
                f"verses where the word did mean the card are kept as single verses, not dropped with the word.</p>"
                f"<details open><summary>14 of the {d_shown} readers see, to spot-check: two verses both judges read as another sense and one as the card</summary>"
                f"<table><tr><th>card</th><th>word</th><th>verses</th></tr>{drows}</table></details>{marks('d2-drop-words')}</section>")
    # D3: orphans
    orows = "".join(f"<li><b>{e(c['name'])}</b> <span class=k>cited {c['cited']}, {c['verses_now']:,} verses now</span></li>"
                    for c in orphans[:60])
    prows = "".join(f"<li><b>{e(c['name'])}</b> <span class=k>cited {c['cited']}; {len(c['verses_to_add'])} single-word verses held, "
                    f"e.g. {e(c['verses_to_add'][0])}: {vt(c['verses_to_add'][0])[:140]}</span></li>" for c in p_add[:40])
    body.append(f"<section><h2>3. Cards named by a phrase <span class=k>· {len(p_add)} with single-word adds held, "
                f"{sum(len(c['verses_to_add']) for c in p_add):,} verses; {len(orphans)} the drops leave with no words</span></h2>"
                f"<p>\"The hand of the Lord\" is not every verse with <i>hand</i> in it, yet the audit offered single words to "
                f"phrase cards just as it had given them their wrong anchors (Ps 110:5, \"The Lord is at Your right hand\", "
                f"offered to \"the hand of the Lord\"). So did cards named by a fragment of a verse (\"crushed me\" was "
                f"offered Mic 1:7's smashed idols). Those adds are held, not added. And {len(orphans)} phrase cards lose every "
                f"word they carry in decision 2, keeping only the verses they cite.</p>"
                f"<p class=rec><b>Recommended: hold the adds, make the drops, and anchor phrase cards by their phrase</b> "
                f"(the verses where the phrase itself occurs in the original, a new item for plan 4.8). A card showing "
                f"1,600 verses of the wrong word is worse than one showing its few cited verses.</p>"
                f"<details><summary>The 40 most-cited phrase cards with adds held</summary><ul>{prows}</ul></details>"
                f"<details><summary>The {min(60, len(orphans))} most-cited cards left with no words</summary>"
                f"<ul>{orows}</ul></details>{marks('d3-phrase-cards')}</section>")
    # D4: splits
    srows = "".join(
        f"<tr><td><b>{e(c['name'])}</b></td><td>{e(x['lemma'] or '')} <span class=k>{int(100 * x['share'])}%</span></td><td>"
        + "".join(f"<div><span class=yes>yes</span> {e(r)} {vt(r)}</div>" for r in x["yes"][:1])
        + "".join(f"<div><span class=no>no</span> {e(r)} {vt(r)}</div>" for r in x["no"][:1]) + "</td></tr>"
        for c, x in random.sample(splits, min(10, len(splits))))
    body.append(f"<section><h2>4. Words with two senses: keep them verse by verse <span class=k>· {len(splits)} words</span></h2>"
                f"<p>Between 30% and 60% of the verses mean the card. Dropping the word loses real verses; keeping it shows "
                f"wrong ones. The site already has the mechanism: a word kept on a card only for named verses.</p>"
                f"<p class=rec><b>Recommended: keep each word only on the verses both judges said yes to</b>, and judge its "
                f"remaining verses in a later pass, not all at once.</p><details open><summary>10 to spot-check</summary>"
                f"<table><tr><th>card</th><th>word</th><th>verses</th></tr>{srows}</table></details>{marks('d4-split-words')}</section>")
    # D5: contested, one by one
    crows = []
    for c in contested[:40]:
        ex = c["verses_to_add"][:3]
        crows.append(f"<div class=q><p><b>{e(c['name'])}</b> <span class=k>cited {c['cited']}; {len(c['verses_to_add'])} to add, "
                     f"{len(c['drops'])} words to drop, {len(c['splits'])} to split</span></p>"
                     + "".join(f"<div class=d>{e(r)} {vt(r)}</div>" for r in ex)
                     + marks(f"d5:{c['id']}") + "</div>")
    body.append(f"<section><h2>5. Cards where the verses themselves could take a side <span class=k>· {len(contested)}</span></h2>"
                f"<p>Which verses \"speak of\" baptism, election or the Sabbath is where structure could start answering a "
                f"question traditions divide on. These are held out of decision 1 and shown here one by one.</p>"
                f"<p class=rec><b>Recommended: add only verses whose word names the thing itself</b> (βαπτίζω where someone "
                f"is baptised), never a verse a tradition reads as teaching about it. Discuss any you doubt.</p>"
                f"{''.join(crows)}</section>")
    # D6: thin cards, for later work
    thin = sorted([c for c in allc if c["grade"] == "thin"], key=lambda c: -c["cited"])
    trows = "".join(f"<li><b>{e(c['name'])}</b> <span class=k>cited {c['cited']}</span>: {e('; '.join(c['missing'][:2]))}</li>"
                    for c in thin[:40])
    body.append(f"<section><h2>6. Thin cards: what the words miss <span class=k>· {len(thin)} cards</span></h2>"
                f"<p>The audit's notes on where the text speaks of a concept without its words: an idiom, a narrative that "
                f"shows it without naming it. No verses are proposed; these are leads for passage work.</p>"
                f"<p class=rec><b>Recommended: into the backlog</b>, most-read first, nothing changed now.</p>"
                f"<details><summary>The 40 most cited</summary><ul>{trows}</ul></details>{marks('d6-thin-backlog')}</section>")

    gl = ", ".join(f"{k} {v}" for k, v in changed_grade.most_common())
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Concept repairs</title><style>
:root{{--paper:#F3F5F8;--surface:#fff;--ink:#141F2C;--muted:#5C6A7B;--rule:#BAC4D0;--accent:#356A8C;--ok:#1F7A4D;--bad:#A23B3B}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2C3A4A;--accent:#7FB2D6;--ok:#5CC28F;--bad:#E58A8A}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Georgia,serif}} main{{max-width:1040px;margin:0 auto;padding:16px}}
section{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:8px 14px;margin:14px 0;overflow-x:auto}}
h2{{font-size:18px;margin:6px 0}} .k{{color:var(--muted);font-size:13px}} .d{{font-size:13.5px;margin:2px 0}}
table{{border-collapse:collapse;width:100%}} td,th{{text-align:left;vertical-align:top;padding:6px;border-bottom:1px solid var(--rule);font-size:13.5px}} th{{font-size:12px;color:var(--muted);font-weight:normal}}
.yes,.no{{font:11px system-ui,sans-serif;border-radius:6px;padding:0 5px;margin-right:4px}} .yes{{color:var(--ok);border:1px solid var(--ok)}} .no{{color:var(--bad);border:1px solid var(--bad)}}
.mk{{font-size:13px;border-top:1px dashed var(--rule);margin-top:8px;padding-top:6px}} .mk label{{margin-right:10px}}
.lead{{font-size:15.5px}} .rec{{border-left:3px solid var(--ok);padding-left:8px}} details{{margin:6px 0}} .q{{border-bottom:1px solid var(--rule);padding:6px 0}}
.nt{{display:block;margin-top:4px;width:min(520px,100%);font:inherit;font-size:13px;background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:5px}}
button{{font:inherit;padding:5px 12px;border-radius:6px;border:1px solid var(--accent);background:var(--surface);color:var(--accent)}}
</style></head><body><main><h1>Concept repairs</h1>
<p class=lead>The completeness audit of {len(allc):,} cards ({sum(1 for c in allc if c['kind'] == 'concept'):,} concepts and
{sum(1 for c in allc if c['kind'] == 'other'):,} objects, images, titles, observances, creatures and covenants), brought
into six decisions. Each is a rule over many cards with a sample in full Berean text to spot-check; the cases that need your
eye are listed one by one. <b>Mark only what you want to override or discuss</b>; anything unmarked goes as recommended.
Nothing is applied by this sheet: the repairs go in through the one card pipeline (plan 4.8).</p>
<p class=k>Grades of the {len(before)} cards re-judged after this morning's book-name fix changed: {e(gl or 'none')}.
{pending} added words came only from the re-judge and have no verses judged yet; they wait for the next pass.
Words flagged on the objects, images and other cards are not yet checked on their verses, and are not here.</p>
<p><button id=exp>Copy my marks</button> <span id=st class=k></span></p>
{''.join(body)}</main><script>
const KEY='concept-repairs-2026-10-19'; let M={{}}; try{{M=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(M))}}catch(e){{}}}}
document.querySelectorAll('.mk').forEach(m=>{{const id=m.dataset.id,s=M[id]||{{}};
 m.querySelectorAll('input[type=radio]').forEach(i=>{{if(i.value===s.mark)i.checked=true;i.onchange=()=>{{(M[id]=M[id]||{{}}).mark=i.value;save()}}}});
 const n=m.querySelector('.nt');n.value=s.note||'';n.oninput=()=>{{(M[id]=M[id]||{{}}).note=n.value;save()}};}});
// the marks are always shown in a box, selected: a sandboxed viewer blocks both
// the clipboard and prompt(), and the button then did nothing (2026-10-19)
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
    print(f"{len(allc)} cards; {n_add:,} verses to add on {len(c_add)}; phrase cards' adds held: "
          f"{sum(len(c['verses_to_add']) for c in p_add):,} on {len(p_add)}; {len(drops)} drops; {len(splits)} splits; "
          f"{len(keeps)} kept after check; {len(orphans)} left without words; {len(contested)} contested; "
          f"grades changed by the re-judge: {dict(changed_grade)}; {pending} adds not yet judged -> {DEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
