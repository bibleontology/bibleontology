"""THE 1.2.0 VOCABULARY, AS A SHEET TO READ BEFORE IT IS RELEASED
(plan 1.35; 2026-10-17).

A term's address is permanent once published (ontology/ns-version.json: "a
term's address never changes"), so every new or changed term is shown here
first, as it would read, with the verse it was established on and the
Berean's words for that verse. Two naming questions are asked at the top.

    python tools/vocab_sheet.py   -> docs/review/vocab-1.2.0.html
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
e = html.escape
NEW_REL = ["when", "comes_true", "means", "heading", "item"]
NEW_CLS = ["List"]
WIDENED = ["content", "clause_link", "member_of_group"]
BOOK = {"Gen": "Gen", "Act": "Acts", "Jhn": "John", "1Ki": "1Kgs", "Mat": "Matt"}


def main():
    k = json.loads((ROOT / "ontology/kinds.json").read_text(encoding="utf-8"))
    p = json.loads((ROOT / "ontology/schema/prep_relations.json").read_text(encoding="utf-8"))
    V = {}
    for line in open(ROOT / "data/bible/verses.bsb.jsonl", encoding="utf-8"):
        d = json.loads(line)
        if "c" in d:
            V[f"{d['b']}.{d['c']}.{d['v']}"] = d["t"]
    rel = {r["id"]: r for r in k["relations"]}
    cls = {c["id"]: c for c in k["classes"]}

    def verse(ref):
        if not ref:
            return ""
        b, c, v = ref.split(".")
        t = V.get(f"{BOOK.get(b, b)}.{c}.{v}")
        return f"<div class=v><b>{e(ref)}</b> {e(t)}</div>" if t else ""

    def card(x, kind):
        est = x.get("established") or {}
        meta = " · ".join(filter(None, [kind, x.get("status"),
                                         f"from {x['from']} to {x['to']}" if x.get("from") else "",
                                         f"reads “{x['reads']}”" if x.get("reads") else "",
                                         f"on {x['on']}" if x.get("on") else ""]))
        return (f"<section><h3>{e(x['id'])} <span class=k>{e(x.get('label') or '')}</span></h3>"
                f"<p class=k>{e(meta)}</p><p>{e(x.get('definition') or '')}</p>{verse(est.get('ref'))}"
                f"<p class=k>{e(est.get('note') or '')}</p>"
                + (f"<p class=k><b>Widened:</b> {e(x['widened'])}</p>" if x.get("widened") else "")
                + "</section>")

    out = []
    out.append("<h2>New clause links</h2>" + "".join(card(rel[i], "clause link") for i in NEW_REL[:3]))
    out.append("<h2>A new group: the list</h2>" + card(cls["List"], "group kind")
               + "".join(card(rel[i], "member role") for i in NEW_REL[3:]))
    out.append("<h2>A new member of a command group (plan 1.42)</h2>"
               "<p class=k>A name for you to approve: the clean builder had filed these under a speech turn's "
               "<i>part</i>.</p>" + card(rel["attached"], "member role"))
    out.append("<h2>A person who is one of a group (plan 1.41)</h2>"
               "<p class=k>Your choice of 2026-10-18 (\"go with partitive\"): the same term as the "
               "prepositional type below.</p>" + card(rel["partitive"], "link"))
    out.append("<h2>Kinds only the readings make (plan 1.43)</h2>"
               "<p class=k>Declared so the check can hold the sweep's layer to the file; always readings.</p>"
               + "".join(card(cls[i], "class") for i in ("Generic", "Together")))
    out.append("<h2>A parent for a group's roles (P-2026-10-18-15)</h2>"
               "<p class=k>A placeholder name for you to choose: <i>participant</i> is taken (the clause roles' "
               "parent). Under it: sender, addressee, group_subject.</p>" + card(rel["group_role"], "relation"))
    out.append("<h2>Widened</h2><p class=k>clause_link and member_of_group (plan 8.1b): published as the parents of "
               "their relations, so their range must cover every child's.</p>"
               + "".join(card(rel[i], "relation") for i in WIDENED))
    out.append("<h2>Marks (a value on a clause or a link, not a link)</h2>"
               + "".join(card(a, "mark") for a in k.get("attributes") or []))
    out.append("<h2>What the vocabulary does not attempt</h2>"
               + "".join(f"<section><p>{e(x)}</p></section>" for x in k["scope"]["excludes"]))
    rows = "".join(
        f"<tr><td><b>{e(f)}</b><br><span class=k>{e(v['means'])}</span></td><td>"
        + "<br>".join(f"<b>{e(t)}</b>: {e(d)}" + (" <span class=k>(the same term as the clause link)</span>"
                                                   if t in ("means", "purpose") else
                                                   " <span class=k>(the same term as the link from a person to a group)</span>"
                                                   if t == "partitive" else
                                                   " <span class=k>(was basis: see the decisions)</span>"
                                                   if t == "rests_on" else "")
                      for t, d in v["types"].items()) + "</td></tr>"
        for f, v in p["families"].items())
    out.append("<h2>Prepositional relations: six families, each with its types</h2>"
               "<p class=k>Each type is a sub-property of its family, so a query for a family finds every type in "
               "it. A rule or a judge names the most specific level it is sure of.</p>"
               f"<table>{rows}</table>")
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Vocabulary 1.2.0</title><style>
:root{{--paper:#F3F5F8;--surface:#fff;--ink:#141F2C;--muted:#5C6A7B;--rule:#BAC4D0;--accent:#356A8C;--warn:#9a6b2f}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2C3A4A;--accent:#7FB2D6;--warn:#d9a35b}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 Georgia,serif}} main{{max-width:900px;margin:0 auto;padding:16px}}
section{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:8px 16px;margin:10px 0}}
h3{{margin:6px 0 2px}} .k{{color:var(--muted);font-size:13px}} .q{{color:var(--warn);font-size:13px}}
.v{{border-left:3px solid var(--accent);padding-left:8px;margin:6px 0;font-size:14px}}
table{{border-collapse:collapse;width:100%;background:var(--surface)}} td{{border:1px solid var(--rule);padding:6px 10px;vertical-align:top;font-size:14px}}
.ask{{border:2px solid var(--warn)}}
</style></head><body><main><h1>Vocabulary 1.2.0, before release</h1>
<p class=k>Every new or changed term, as it would be published at bibleontology.org/ns/structure. New terms are
<i>proposed</i>: declared, not yet built, until a pass produces them. Once released, a term's address is permanent.</p>
<section><h3>Two naming decisions (Doug, 2026-10-17)</h3>
<p><b>purpose</b> is one term at both levels, the clause link ("so that") and the prepositional type ("for an
offering"), as <i>means</i> is: "share purpose like means".</p>
<p><b>rests_on</b> is the prepositional type that was drafted as <i>basis</i> ("lean not on your own understanding",
Proverbs 3:5). The structure vocabulary's <i>basis</i> is the reason given for a command, a different meaning, so
it keeps the name: "rename basis to rests_on".</p></section>
{''.join(out)}</main></body></html>"""
    dest = ROOT / "docs/review/vocab-1.2.0.html"
    dest.write_text(page, encoding="utf-8")
    print("->", dest.relative_to(ROOT))


if __name__ == "__main__":
    main()
