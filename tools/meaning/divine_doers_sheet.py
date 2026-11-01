"""WHO DOES IT, WHERE THE ANSWER IS GOD OR JESUS: A SHEET FOR DOUG'S RULING
(2026-10-27, the Mac's whole-graph structure check). Nothing is resolved by
this sheet: divine persons are resolved only by hand, record by record (memory:
divine persons by hand). It lays out each clause whose unnamed doer the Mac
named as God or Jesus, the name found in the verse or the three before, and a
Claude Haiku judge read as the doer, with a recommendation under his rule of
2026-10-25: a "He" resolved by its own clause or the verse beside counts as
resolved. Resolve where the verse or the verse before names him; otherwise hold.

    python tools/meaning/divine_doers_sheet.py
      reads  ontology/provenance/meaning/structure-check-2026-10-27.jsonl.gz (the judged trail)
      ->     docs/review/divine-doers-2026-10-27.html
"""
import gzip
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRAIL = ROOT / "ontology" / "provenance" / "meaning" / "structure-check-2026-10-27.jsonl.gz"
DEST = ROOT / "docs" / "review" / "divine-doers-2026-10-27.html"
NAMES = {"god": "God", "jesus": "Jesus"}
e = html.escape


# the judge often quotes the action's own clause as its "deciding words" ("I form
# the light and create the darkness"), so where those words sit proves nothing; the
# test is whether the verse or the verse before NAMES him
NAMED = {"god": re.compile(r"\b(LORD|God|Lord GOD|Almighty|Most High)\b"), "jesus": re.compile(r"\b(Jesus|Christ)\b")}


def near(who, text, before):
    """he is named in the verse or the verse before"""
    return bool(NAMED[who].search(text or "") or NAMED[who].search(before or ""))


def main():
    rows, speakers = [], []
    with gzip.open(TRAIL, "rt", encoding="utf-8") as f:
        for ln in f:
            r = json.loads(ln)
            if r.get("pass") == "doer" and r["candidate"] in NAMES and r["verdict"] == "yes":
                rows.append(r)
            # the held relations whose speaker two judges found to be God or Jesus
            if r.get("pass") == "speaker" and r.get("pinned") in NAMES and (r.get("confirm") or {}).get("verdict") == "yes":
                speakers.append(r)
    rows.sort(key=lambda r: (r["candidate"], r["ref"]))
    for r in rows:
        r["rec"] = "resolve" if near(r["candidate"], r["text"], r["before"]) else "hold"
    n_res = sum(r["rec"] == "resolve" for r in rows)
    out = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Divine doers to rule</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem;color:#222}}
table{{border-collapse:collapse;width:100%}}td,th{{border-top:1px solid #ddd;padding:.5rem;vertical-align:top;text-align:left}}
.b{{color:#666}}.res{{color:#05603a;font-weight:600}}.hold{{color:#8a4b00;font-weight:600}}q{{font-style:italic}}</style></head><body>
<h1>Who does it: God or Jesus, {len(rows)} clauses to rule</h1>
<p>Each clause's doer was unnamed in the graph. The Mac's structure check named God or Jesus; the name was found in
the verse or the three before; a Claude Haiku judge, asked only "is this the one who does it?", answered yes and quoted
the words that decide it. Nothing here is applied: divine persons are resolved by hand, record by record.</p>
<p><b>Recommendation</b> (your rule of 2026-10-25, a "He" resolved by its own clause or the verse beside counts):
<span class="res">resolve</span> where the verse or the verse before names him
({n_res}); <span class="hold">hold</span> where only an earlier verse does ({len(rows) - n_res}).</p>
<p><b>To rule:</b> "as recommended", or list the numbers to change.</p>
<table><tr><th>#</th><th>Verse</th><th>Action</th><th>Doer</th><th>Deciding words</th><th>Recommend</th></tr>"""]
    for i, r in enumerate(rows, 1):
        out.append(f"<tr><td>{i}</td><td><b>{e(r['ref'])}</b> {e(r['text'])}<div class='b'>before: {e(r['before'] or '')}"
                   f"</div></td><td>{e(r['action'])}</td><td>{NAMES[r['candidate']]}</td><td><q>{e(r['words'])}</q></td>"
                   f"<td class='{'res' if r['rec'] == 'resolve' else 'hold'}'>{r['rec']}</td></tr>")
    out.append("</table>")
    speakers.sort(key=lambda r: (r["pinned"], r["verse"]))
    out.append(f"""<h2>Whose words: God or Jesus, {len(speakers)} held relations</h2>
<p>Each relation is held because the verse it rests on is someone's speech and the graph had no speaker on record. A
Claude Haiku reader named the speaker; the name was matched to the record named in the chapter; a Claude Sonnet judge
confirmed it. Crediting the words to God or Jesus releases the relation in His voice. <b>Recommendation:</b> credit
all, as the two judges agree. <b>To rule:</b> "as recommended", or list the numbers to hold.</p>
<table><tr><th>#</th><th>Relation</th><th>Verse</th><th>Speaker</th><th>Deciding words</th></tr>""")
    for i, r in enumerate(speakers, 1):
        out.append(f"<tr><td>S{i}</td><td>{e(r['relation'].replace('|', ' · '))}</td><td>{e(r['verse'])}</td>"
                   f"<td>{NAMES[r['pinned']]}</td><td><q>{e((r['confirm'] or {}).get('words') or '')}</q></td></tr>")
    out.append("</table></body></html>\n")
    DEST.write_text("\n".join(out), encoding="utf-8")
    print(f"{len(rows)} rows ({n_res} resolve, {len(rows) - n_res} hold), {len(speakers)} speakers -> {DEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
