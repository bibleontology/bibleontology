"""THE DIVINE FLAGS, AS A SHEET TO RULE ON BY HAND (plan 1.34; 2026-10-17).

From out/sweep/divine-flags.json (divine_flags.py). Every choice the two sweep
passes flagged divine falls in one of these groups:
  pattern A  a pronoun pointing to a divine word in the text ("he" -> "LORD")
  pattern B  a speech whose speaker or addressee is divine
  pattern C  "Lord": a pronoun pointing to the word "Lord" (whether that Lord
             is God or Jesus is NOT decided here: that is an identity, a
             record-level question, done by hand per the rule on divine persons)
  no flag    the speech is divine but the person named is not (David speaking
             to God); nothing divine to rule
  one by one several together with one divine ("the Father and the Son"), and
             a lowercase "god" (mostly Aramaic elah, "the God of heaven"; maybe
             other gods): each shown with its verse and its own mark
The patterns are shown by sample, with counts, to approve or not as a
pattern; the one-by-one rows each get a mark.

    python tools/sweep/divine_sheet.py   -> docs/review/divine-flags-2026-10-17.html
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
sys.path.insert(0, str(Path(__file__).parent))
import context as C  # noqa: E402

DIV = {"LORD", "LORD’s", "GOD", "God", "God’s", "of God", "Lord", "Lord’s", "Jesus", "to Jesus", "Christ", "Father",
       "Son", "Spirit", "Almighty", "Most High", "Holy One", "Yahweh", "the LORD", "Lord GOD"}
e = html.escape


def group(r):
    names = r["names"]
    if any(re.fullmatch(r"gods?|god’s|of god", n or "") for n in names):
        return "god"
    if not any(n in DIV or "LORD" in (n or "") or "God" in (n or "") or "Jesus" in (n or "") for n in names):
        return "none"
    if len(names) > 1:
        return "several"
    if r["kind"] in ("sender", "addressee"):
        return "B"
    if names[0].startswith("Lord") and not names[0].startswith("LORD"):
        return "C"
    return "A"


def main():
    rows = json.loads((ROOT / "out" / "sweep" / "divine-flags.json").read_text(encoding="utf-8"))
    words, clause_w = {}, {}
    with gzip.open(ROOT / "out" / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("word"):
                words[d["id"]] = d.get("text")
                for i in d.get("w") or []:
                    words[f"{d['ref']}#@{i}"] = d.get("text")
            elif d.get("clause"):
                clause_w[d["id"]] = d.get("w") or []
    bsb = C._bsb()
    by = collections.defaultdict(list)
    for r in rows:
        by[group(r)].append(r)

    def word_of(r):
        s = r.get("slot") or ""
        m = re.match(r"^cl(\d+)s$", s)
        if m:
            # THE CLAUSE'S OWN WORDS, not only its number. Shown as "clause 5"
            # beside the whole verse, Luke 12:37's flag ("Truly I tell you":
            # Jesus, right) was misread as the parable's "he will dress
            # himself" (2026-10-17), and a pattern was ruled on that misreading
            ws = [words.get(f"{r['ref']}#@{i}") for i in clause_w.get(f"{r['ref']}#cl{m.group(1)}", [])]
            said = " ".join(w for w in ws if w)
            return f"the unstated subject of “{e(said)}”" if said else f"the unstated subject of clause {m.group(1)}"
        return f"“{words.get(r['ref'] + '#' + s) or s}”"

    def line(r, mark=False):
        title, text = bsb(r["ref"])
        who = " + ".join(r["names"])
        what = (f"{word_of(r)} → <b>{e(who)}</b>" if r["kind"] == "referent"
                else f"the speech's {e(r['kind'])} → <b>{e(who)}</b>")
        m = (f"""<span class=mk data-id="{e(r['ref'] + '|' + (r.get('slot') or r['kind']) + '|' + who)}">
<label><input type=radio name="{e(r['ref'] + (r.get('slot') or r['kind']) + who)}" value=right> right</label>
<label><input type=radio name="{e(r['ref'] + (r.get('slot') or r['kind']) + who)}" value=wrong> wrong</label></span>""" if mark else "")
        return (f"<li><b>{e(title)}</b> {what} <span class=k>({e(r.get('by') or '')}, {e(r.get('confidence') or '')})</span>{m}"
                f"<div class=t>{e(text)}</div><div class=k>{e(r.get('why') or '')}</div></li>")

    random.seed(17)
    sec = []
    labels = {"A": ("Pattern A — a pronoun pointing to a divine word in the text", True),
              "B": ("Pattern B — a speech whose speaker or addressee is divine", True),
              "C": ("Pattern C — a pronoun pointing to the word “Lord”", True),
              "none": ("No ruling needed — the speech is divine, the person named is not", False),
              "several": ("One by one — several together, one of them divine", None),
              "god": ("One by one — a lowercase “god”", None)}
    for g, (title, pattern) in labels.items():
        rs = by.get(g, [])
        if pattern is None:
            body = "".join(line(r, True) for r in rs)
            sec.append(f"<section><h2>{e(title)} · {len(rs)}</h2><p class=lead>Each with its own mark.</p><ol>{body}</ol></section>")
        else:
            sample = random.sample(rs, min(14, len(rs)))
            choice = (f"""<div class=pat data-pat="{g}"><b>Approve as a pattern?</b>
<label><input type=radio name="pat-{g}" value=approve> approve all {len(rs):,}</label>
<label><input type=radio name="pat-{g}" value=hold> hold</label>
<textarea placeholder="note (optional)"></textarea></div>""" if pattern else
                      "<p class=lead>Shown for completeness: the divine member of these speeches is ruled under pattern B.</p>")
            sec.append(f"<section><h2>{e(title)} · {len(rs):,}</h2>{choice}<p class=k>A random sample of {len(sample)}:</p>"
                       f"<ol>{''.join(line(r) for r in sample)}</ol></section>")
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Divine flags</title><style>
:root{{--paper:#F3F5F8;--surface:#fff;--ink:#141F2C;--muted:#5C6A7B;--rule:#BAC4D0;--accent:#356A8C}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2C3A4A;--accent:#7FB2D6}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Georgia,serif}} main{{max-width:900px;margin:0 auto;padding:16px}}
section{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:10px 16px;margin:14px 0}}
h2{{font-size:18px}} li{{margin:8px 0}} .t{{border-left:3px solid var(--accent);padding-left:8px;margin:2px 0}}
.k,.lead{{color:var(--muted);font-size:13px}} .pat{{background:var(--paper);border-radius:8px;padding:8px;display:flex;gap:12px;flex-wrap:wrap;align-items:center}}
.pat textarea{{flex:1 1 220px;font:inherit;background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:6px}}
.mk{{margin-left:8px;font-size:13px}} button{{font:inherit;padding:5px 12px;border-radius:6px;border:1px solid var(--accent);background:var(--surface);color:var(--accent)}}
</style></head><body><main><h1>The divine flags</h1>
<p class=lead>Every choice the structure sweep made that names God, the LORD, the Father, Jesus or the Holy Spirit was held
for you: {len(rows):,} in all. These link a pronoun, or a speech, to a divine WORD in the text; none decides which record a word
belongs to (whether a “Lord” is God or Jesus), which stays a question you rule record by record. The patterns can be approved
as patterns, from their samples; the rest are one by one.</p>
<p><button id=exp>Copy my marks</button> <span id=st class=k></span></p>
{''.join(sec)}</main><script>
const KEY='divine-flags-2026-10-17'; let M={{pat:{{}},rows:{{}}}}; try{{M=JSON.parse(localStorage.getItem(KEY)||'')||M}}catch(e){{}}
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(M))}}catch(e){{}}}}
document.querySelectorAll('.pat').forEach(p=>{{const g=p.dataset.pat,s=M.pat[g]||{{}};
 p.querySelectorAll('input').forEach(i=>{{if(i.value===s.mark)i.checked=true;i.onchange=()=>{{(M.pat[g]=M.pat[g]||{{}}).mark=i.value;save()}}}});
 const t=p.querySelector('textarea');t.value=s.note||'';t.oninput=()=>{{(M.pat[g]=M.pat[g]||{{}}).note=t.value;save()}};}});
document.querySelectorAll('.mk').forEach(m=>{{const id=m.dataset.id;m.querySelectorAll('input').forEach(i=>{{if(i.value===M.rows[id])i.checked=true;
 i.onchange=()=>{{M.rows[id]=i.value;save()}}}})}});
document.getElementById('exp').onclick=async()=>{{const x=JSON.stringify({{sheet:KEY,marks:M}},null,1);
 try{{await navigator.clipboard.writeText(x);document.getElementById('st').textContent='Copied: paste it into the chat.'}}catch(e){{prompt('Copy this',x)}}}};
</script></body></html>"""
    out = ROOT / "docs" / "review" / "divine-flags-2026-10-17.html"
    out.write_text(page, encoding="utf-8")
    print({g: len(v) for g, v in by.items()}, "->", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
