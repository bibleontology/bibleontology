"""WHAT THE SWEEP DOES, BY KIND OF VERSE (2026-10-16). After the
one-vote decision was shown to rest on cost, a sheet of examples of what the
sweep does with different types of verses was asked for.

One verse of each kind, from the headless run (one judgement each), laid out
the way it reads: the verse, then who each pronoun and unstated subject is
(the parser's answer beside the sweep's), how the clauses connect (what the
sweep added and removed), the speeches and other groups, and what the judge
said it could not express. A mark per verse (right / partly / wrong, and a
note) is kept in the browser and exported as JSON.

    python tools/sweep/example_sheet.py   -> docs/review/sweep-examples-2026-10-16.html
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import context as C  # noqa: E402
import score as S  # noqa: E402

RUN = ROOT / "out" / "sweep" / "runs" / "sweep-1"
# the resolution pass's answers, where it has filled a verse's blanks
SECOND = ROOT / "out" / "sweep" / "runs" / "resolve-pilot"
EXAMPLES = [
    ("Rut.1.14", "Narrative, pronouns", "who wept, who kissed whom, who clung"),
    ("Rut.2.4", "Dialogue", "a greeting and its reply, the speakers taken from the alternation"),
    ("Gen.3.9", "God speaks", "a call and a question; divine choices are flagged for you"),
    ("Gen.4.9", "Question and evasion", "the LORD's question and Cain's reply, itself a question"),
    ("Gen.22.2", "Divine command", "a run of commands, the speech's content"),
    ("Exo.9.1", "Commanded speech", "speech nested three deep: the LORD tells Moses to say what the LORD says"),
    ("Exo.9.10", "Command carried out", "a report that a command was done (fulfils)"),
    ("Gen.5.6", "Genealogy", "the formula of the begettings"),
    ("Exo.21.2", "Law", "a condition and what follows from it"),
    ("Exo.15.2", "Poetry", "a song: the singer's own voice, lines side by side"),
    ("Jon.3.4", "Proclamation", "a prophet's message inside a narrative"),
    ("Mrk.4.4", "Parable", "a story inside Jesus' speech"),
    ("Mrk.2.7", "Hostile question", "the scribes' question, rhetorical"),
    ("Mrk.8.36", "Rhetorical question", "a question whose answer is implied"),
    ("Jhn.14.2", "Long speech", "a verse inside a speech that runs across chapters"),
    ("Act.9.4", "Voice from heaven", "a voice and who it is"),
    ("Act.2.25", "Scripture quoted", "Peter quoting David quoting the Lord"),
    ("Act.2.9", "List", "a catalogue of peoples, which the vocabulary has no group for"),
    ("Act.1.10", "Time", "a 'while' clause, which the vocabulary has no link for"),
]
e = html.escape


def main():
    refs = [r for r, _k, _w in EXAMPLES]
    ctxs = C.build(refs)
    labels = {l["type"]: l.get("label") or l["type"] for l in C.vocabulary()}
    generics = {g["id"]: g["label"] for g in json.loads((SECOND / "generics.json").read_text(encoding="utf-8"))} \
        if (SECOND / "generics.json").exists() else {}
    far = {}

    def far_label(x):
        """A cast member from a verse outside this one's window: its word there."""
        if x in generics:
            return f"{generics[x]} <span class=k>(generic)</span>"
        r, _, w = x.partition("#")
        if r not in far:
            try:
                far[r] = C.build([r])[r]
            except Exception:                       # noqa: BLE001 -- a label, not a decision
                far[r] = {"candidates": [], "verse": r}
        c = next((c for c in far[r]["candidates"] if S.suffix(c["id"]) == w or c["id"] == x), None)
        return f"{e(c['text'])} <span class=k>({e(far[r]['verse'])})</span>" if c else None

    cards = []
    for ref, kind, why in EXAMPLES:
        ctx = ctxs[ref]
        p = RUN / f"{ref}.json"
        if not p.exists():
            continue
        ans = json.loads(p.read_text(encoding="utf-8"))
        second = SECOND / "merged" / f"{ref}.json"
        if second.exists():
            ans = json.loads(second.read_text(encoding="utf-8"))
        # the scorer takes one candidate per slot: a second-pass list or generic
        # is shown from the answer itself, not through it
        plain = json.loads(json.dumps(ans))
        for x in plain.get("referents") or []:
            if x.get("resolved_by") and (isinstance(x.get("choice"), list) or "#" in str(x.get("choice"))):
                x["choice"] = "none"
        for g in plain.get("groups") or []:
            g["members"] = [m for m in g.get("members") or [] if not m.get("resolved_by")]
        before, after = S.Verse(ctx), S.Verse(ctx, plain)
        gl = {c["id"]: c["gloss"] for c in ctx["clauses"]}
        cand = {}
        for c in ctx["candidates"]:
            cand[c["id"]] = c.get("text") or c["id"]
            cand.setdefault(S.suffix(c["id"]), c.get("text") or c["id"])

        def who(x, none="<i>none chosen</i>"):
            if x is None:
                return none
            if x in cand or S.suffix(x) in cand:
                return e(cand.get(x) or cand.get(S.suffix(x)))
            return f"<span class=k>{e(x)} (an id it was not offered)</span>"

        def node(n, depth=0):
            n = n or ""
            n2 = S.suffix(n)
            other = "#" in n and not n.startswith(ref + "#")
            if other:
                b, _, rest = n.partition("#")
                return f"<span class=k>{e(b.replace('.', ' ', 1).replace('.', ':'))}’s {e(rest)}</span>"
            if n2 in gl:
                return f"“{e(gl[n2])}”"
            if n2 in after.groups and depth < 2:
                g = after.groups[n2]
                inner = [node(m, depth + 1) for _r, m in g["members"] if S.suffix(m) in gl or S.suffix(m) in after.groups][:3]
                name = {"imperative": "the commands", "turn": "the speech", "conditional": "the condition",
                        "parallel": "the lines"}.get(g["kind"], f"the {g['kind']}")
                return f"<span class=gk>{e(name)}</span>" + (f" ({', '.join(inner)})" if inner else "")
            if n in cand or n2 in cand:
                return f"<b>{who(n)}</b>"
            if n2.startswith("cl"):
                return "<span class=k>a clause of the verse before</span>"
            return f"<span class=k>{e(n)}</span>"

        refm = {r.get("slot"): r for r in ans.get("referents") or []}
        rows = []
        for s in ctx["slots"]:
            sid = s["id"]
            was = s.get("builder_says_text") or (cand.get(s.get("builder_says")) if s.get("builder_says") else None)
            now = after.refs.get(sid)
            r = refm.get(sid) or {}
            nowt = who(now)
            # A RIGHT ANSWER THE SCORER CANNOT SEE. The first pass may name a
            # person from an earlier verse it was not offered (God in Genesis
            # 22:2, from 22:1: the context offers only proper names from earlier
            # verses, and elohim is not one). The scorer drops it as invalid;
            # the sheet showed "none chosen" for a right answer (2026-10-16).
            raw = r.get("choice")
            if now is None and isinstance(raw, str) and "#" in raw and not r.get("resolved_by"):
                lab = far_label(raw)
                if lab:
                    nowt = f"{lab} <span class=k>(named in an earlier verse; not on its offered list)</span>"
                    now = raw
            if r.get("resolved_by"):
                ch = r.get("choice")

                def one(x):
                    if x in cand or S.suffix(str(x)) in cand and "#" not in str(x):
                        return who(x)
                    return far_label(x) or who(x)
                nowt = (" + ".join(one(x) for x in ch) if isinstance(ch, list) else one(ch)) \
                    + " <span class=p2>second pass</span>"
                now = ch
            if r.get("rhetorical"):
                extra = []
                if r.get("implied"):
                    extra.append(f"implies “{e(r['implied'])}”")
                if r.get("answered_by"):
                    extra.append(f"answered by {node(r['answered_by'])}")
                nowt = "<span class=rh>rhetorical answer</span>" + (": " + "; ".join(extra) if extra else ", left unanswered")
            changed = bool(r.get("resolved_by")) or (was or None) != (cand.get(now) if isinstance(now, str) and now else None)
            # WHICH "he said": an unstated subject names its clause (cl3s), so
            # the clause number is shown (of Genesis 4:9: there was no
            # obvious way to know which 'he said' was meant)
            m_cl = re.match(r"^(cl\d+)s$", sid)
            word = f"“{e(s.get('text') or '')}”" + (f" <span class=k>(clause {e(m_cl.group(1)[2:])})</span>" if m_cl else "") \
                + (f" <span class=k>in “{e(s['in_text'])}”</span>" if s.get("in_text") else "") \
                + f" <span class=k>{e(s.get('morph') or '')}</span>"
            conf = r.get("confidence") or ""
            div = " <span class=dv>divine: yours to rule</span>" if r.get("divine") else ""
            rows.append(f"<tr class={'ch' if changed else 'same'}><td>{word}</td><td>{e(was) if was else '<i>none</i>'}</td>"
                        f"<td>{nowt}{div}</td><td class=k>{e(conf)}</td></tr>")
        added = sorted(after.links - before.links)
        removed = sorted(before.links - after.links)
        kept = sorted(before.links & after.links)
        link_li = [f"<li class=add>+ {node(a)} <b>{e(labels.get(t, t))}</b> {node(b)}</li>" for a, t, b in added]
        link_li += [f"<li class=rem>− {node(a)} <s>{e(labels.get(t, t))}</s> {node(b)}</li>" for a, t, b in removed]
        link_li += [f"<li class=kept>{node(a)} {e(labels.get(t, t))} {node(b)}</li>" for a, t, b in kept]
        grp = []
        for gid, g in after.groups.items():
            mem = g["members"]
            roles = {}
            for rl, n in mem:
                roles.setdefault(rl, []).append(n)
            if g["kind"] == "turn":
                # the second pass's speaker or addressee, where it filled one
                raw = next((x for x in ans.get("groups") or [] if S.suffix(x.get("id")) == gid), {})
                for m in raw.get("members") or []:
                    if m.get("resolved_by"):
                        v = m.get("node")
                        lab = " + ".join((far_label(x) or who(x)) for x in v) if isinstance(v, list) else (far_label(v) or who(v))
                        roles.setdefault(m["role"] + "2", []).append(lab + " <span class=p2>second pass</span>")
                full = {S.suffix(m.get("node") or ""): m.get("node") for m in raw.get("members") or []
                        if isinstance(m.get("node"), str) and "#" in m.get("node")}

                def person(n):
                    if n in cand or (S.suffix(n) in cand and n not in full):
                        return who(n)
                    return (far_label(full[n]) if n in full else None) or who(n)
                snd = ", ".join(person(n) for n in roles.get("sender", [])) or ", ".join(roles.get("sender2", [])) or "<i>speaker not given</i>"
                adr = ", ".join(person(n) for n in roles.get("addressee", [])) or ", ".join(roles.get("addressee2", [])) or "<i>addressee not given</i>"
                body = f"<b>{snd}</b> → {adr}"
                if roles.get("frame"):
                    body += f"; said in {', '.join(node(n) for n in roles['frame'])}"
                if roles.get("part"):
                    body += f"; says {', '.join(node(n) for n in roles['part'])}"
            else:
                body = "; ".join(f"{e(rl)}: {', '.join(node(n) for n in ns)}" for rl, ns in roles.items())
            ext = next((x for x in ans.get("groups") or [] if S.suffix(x.get("id")) == gid and x.get("action") == "extend"), None)
            tag = f"<span class=gk>{e(g['kind'])}</span>" + (f" <span class=k>continues {e(ext['id'])}</span>" if ext else "")
            grp.append(f"<li>{tag} {body}</li>")
        notes = [f"<li><b>No term fits:</b> {e(x.get('what') or '')}</li>" for x in ans.get("none_fit") or []]
        notes += [f"<li><b>Can't tell:</b> {e(x.get('what') or '')} <span class=k>({e(x.get('why') or '')})</span></li>"
                  for x in ans.get("cant_tell") or []]
        clauses = "".join(f"<li><span class=k>clause {e(c['id'][2:])}</span> “{e(c['gloss'])}” <span class=k>{e(c.get('mood') or '')}</span></li>"
                          for c in ctx["clauses"])
        cards.append(f"""<section class=card id="{e(ref)}"><div class=top><span class=kind>{e(kind)}</span>
<h2>{e(ctx['verse'])}</h2><span class=why>{e(why)}</span></div>
<div class=t>{e(ctx['text'])}</div>
<details><summary>Its clauses, word by word in the original's order</summary><ul class=cl>{clauses}</ul></details>
{('<h3>Who is who</h3><table><tr><th>word</th><th>the parser said</th><th>the sweep says</th><th>sure?</th></tr>' + ''.join(rows) + '</table>') if rows else '<p class=k>No pronouns or unstated subjects to resolve.</p>'}
{('<h3>How the clauses connect</h3><ul class=links>' + ''.join(link_li) + '</ul>') if link_li else ''}
{('<h3>Speeches and groups</h3><ul>' + ''.join(grp) + '</ul>') if grp else ''}
{('<h3>What the judge said it could not do</h3><ul class=notes>' + ''.join(notes) + '</ul>') if notes else ''}
<div class=mark data-ref="{e(ref)}"><label><input type=radio name="m-{e(ref)}" value=right> right</label>
<label><input type=radio name="m-{e(ref)}" value=partly> partly</label>
<label><input type=radio name="m-{e(ref)}" value=wrong> wrong</label>
<textarea placeholder="What is off, in your words (optional)"></textarea></div></section>""")
    page = f"""<!doctype html><html lang=en><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sweep examples</title><style>
:root{{--paper:#F3F5F8;--surface:#fff;--ink:#141F2C;--muted:#5C6A7B;--rule:#BAC4D0;--add:#1F7A4D;--rem:#A23B3B;--accent:#356A8C;--warm:#96591A}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2C3A4A;--add:#5CC28F;--rem:#E07A7A;--accent:#7FB2D6;--warm:#E2B04A}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15.5px/1.5 Georgia,serif}} main{{max-width:940px;margin:0 auto;padding:16px}}
h1{{font-size:24px;margin:8px 0}} h2{{display:inline;font-size:19px;margin:0 8px}} h3{{font-size:14px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin:12px 0 4px}}
.lead,.k{{color:var(--muted)}} .k{{font-size:13px}} .why{{color:var(--muted);font-size:14px}}
.card{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:12px 14px;margin:14px 0}}
.kind{{background:var(--accent);color:var(--surface);border-radius:12px;padding:2px 9px;font-size:13px}}
.t{{border-left:3px solid var(--accent);padding:2px 10px;margin:8px 0;font-size:16.5px}}
table{{border-collapse:collapse;width:100%;font-size:14.5px}} th,td{{text-align:left;padding:4px 6px;border-bottom:1px solid var(--rule);vertical-align:top}}
th{{font-size:12.5px;color:var(--muted);font-weight:normal}} tr.ch td:nth-child(3){{color:var(--add);font-weight:600}}
ul{{margin:2px 0 2px 18px;padding:0;font-size:14.5px}} li.add{{color:var(--add)}} li.rem{{color:var(--rem)}} li.kept{{color:var(--muted)}}
.gk{{border:1px solid var(--rule);border-radius:4px;padding:0 5px;font-size:12.5px}} .rh{{color:var(--warm);font-weight:600}} .dv{{color:var(--warm);font-size:12.5px}}
.p2{{border:1px solid var(--accent);color:var(--accent);border-radius:9px;padding:0 6px;font-size:11.5px;font-weight:normal}}
.notes li{{color:var(--muted)}} details{{font-size:14px;color:var(--muted)}} .cl{{color:var(--ink)}}
.mark{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;border-top:1px dashed var(--rule);margin-top:10px;padding-top:8px;font-size:14px}}
.mark textarea{{flex:1 1 260px;min-height:2.2em;font:inherit;background:var(--paper);color:var(--ink);border:1px solid var(--rule);border-radius:6px;padding:4px 6px}}
.bar{{position:sticky;top:0;background:var(--paper);padding:8px 0;border-bottom:1px solid var(--rule);z-index:2;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
button{{font:inherit;font-size:14px;padding:5px 12px;border-radius:6px;border:1px solid var(--accent);background:var(--surface);color:var(--accent);cursor:pointer}}
</style></head><body><main>
<h1>What the sweep does, verse by kind of verse</h1>
<p class=lead>{len(cards)} verses from the unattended run: Haiku, one judgement per passage, 12 verses a call, your rulings R1–R8 in its
instructions. For each, the parser's answer is beside the sweep's; a changed answer is in green. Added links are marked +, removed ones −,
kept ones grey. An answer tagged <span class=p2>second pass</span> came from the resolution pass (Sonnet, the whole chapter
and the one before, the book's cast), which only fills what the first pass left open; it ran on Ruth 2, Genesis 22 and John 14
among these. A <i>generic</i> is someone the text describes but never names. Quoted clause words are the word-by-word rendering
of the original, in its order. Nothing here is in the graph yet.</p>
<div class=bar><button id=exp>Copy my marks</button><span id=st class=k>Marks are kept in this browser.</span></div>
{''.join(cards)}
</main><script>
const KEY='sweep-examples-2026-10-16';
let M={{}}; try{{M=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
document.querySelectorAll('.mark').forEach(m=>{{const r=m.dataset.ref, s=M[r]||{{}};
  m.querySelectorAll('input').forEach(i=>{{if(i.value===s.mark)i.checked=true; i.onchange=()=>{{(M[r]=M[r]||{{}}).mark=i.value;save()}}}});
  const t=m.querySelector('textarea'); t.value=s.note||''; t.oninput=()=>{{(M[r]=M[r]||{{}}).note=t.value;save()}};}});
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(M))}}catch(e){{}}}}
document.getElementById('exp').onclick=async()=>{{const txt=JSON.stringify({{sheet:KEY,marks:M}},null,1);
  try{{await navigator.clipboard.writeText(txt);document.getElementById('st').textContent='Copied: paste it into the chat.'}}
  catch(e){{prompt('Copy this',txt)}}}};
</script></body></html>"""
    dst = ROOT / "docs" / "review" / "sweep-examples-2026-10-16.html"
    dst.write_text(page, encoding="utf-8")
    print(f"{len(cards)} verses -> {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
