"""PREPOSITIONAL PHRASES, DETERMINISTICALLY FIRST (plan 2.13; 2026-10-17:
break down the prepositional phrases as well, deterministically if possible;
P-2026-10-17-1 approved).

Every prepositional phrase in MACULA's trees (out/phrases.jsonl.gz, `cls`
"pp") becomes a unit:
  prep      the preposition (the phrase's first word)
  object    the head of what it governs: the first noun, name or pronoun after
            the preposition (a pronoun object is resolved by the sweep)
  attaches  what the tree hangs it on: the clause (it modifies the action), a
            noun phrase (it modifies a thing: "the land OF MORIAH"), or another
            prepositional phrase
  relation  named ONLY where a rule is certain; otherwise null, and left for
            judgment (plan 2.13): unresolved is better than wrong

The certain rules, each keyed to the original's words, never the English:
  comparison      כְּ ("like, as")
  accompaniment   עִם ("with"); σύν ("with")
  between         בֵּין
  without         χωρίς; בְּלִי / בִּלְתִּי
  cause           ἕνεκα / ἕνεκεν ("because of, for the sake of")
  time            a preposition of time or place whose object is a word for a
                  time (day, night, morning, evening, year, month, hour,
                  sabbath, season)
Place is NOT named yet: the proper-name lists file some names as both a
person and a place (TIPNR: Adam), so a place rule waits for a clean list.

    python tools/wordgraph/prep_phrases.py           -> out/wordgraph/prep-phrases.jsonl.gz, a count
    python tools/wordgraph/prep_phrases.py --sheet   -> docs/review/prep-phrases-2026-10-17.html
"""
import collections
import gzip
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "out" / "phrases.jsonl.gz"
DST = ROOT / "out" / "wordgraph" / "prep-phrases.jsonl.gz"

# BY STRONG'S NUMBER, NOT THE HEBREW STRING. The first build keyed on the
# lemma as typed and named no comparison and no "between" at all: MACULA writes
# the dagesh before the vowel (כּ + ְ), the reverse of the typed rule, so 3,133
# כְּ and 518 בֵּין never matched (2026-10-17). A number has one spelling.
# H = Hebrew, G = Greek; MACULA's own suffixes ("3807a") and zeros are dropped.
SURE = {"H3509": "comparison", "H5973": "accompaniment", "H854": "accompaniment", "G4862": "accompaniment",
        "H996": "between", "G5565": "without", "H1097": "without", "H1115": "without",
        "G1752": "cause"}
TIME_WORDS = {"H3117", "H3915", "H1242", "H6153", "H8141", "H2320", "H6256", "H7676", "H4283", "H6672",
              "G2250", "G3571", "G5610", "G2094", "G3376", "G2540", "G5550", "G4521", "G2073"}
TIME_PREPS = {"H871", "H3807", "H5704", "H4480", "H310", "G1722", "G3326", "G4253", "G2193", "G575",
              "G1909", "G1223", "G891", "G3360"}


def key(w, lang):
    """A word's Strong's number as H871 / G1722."""
    s = "".join(ch for ch in (w or {}).get("s") or "" if ch.isdigit()).lstrip("0")
    return f"{lang}{s}" if s else None


# THE OBJECT IS THE THING, NOT ITS QUANTIFIER (the first sheet, 2026-10-17):
# "with all your heart" read "all", "on one of the mountains" read "one", and
# "from before Midian" (מִפְּנֵי, a preposition built from "face") read
# "before". A quantifier, a number, or a compound preposition's own noun
# ("face", "midst") passes the head on to the noun after it, if there is one.
QUANT = {"H3605", "G3956"}                    # כֹּל, πᾶς
COMPOUND = {"H6440", "H8432", "H7130"}        # פָּנִים "face", תָּוֶךְ and קֶרֶב "midst"


def head_of(after, shape, lang):
    if shape == "PrepCL":
        # the phrase governs a clause ("to hide it"): its object is that verb
        v = next((w for w in after if w.get("cls") == "verb"), None)
        if v:
            return v
    cands = [w for w in after if w.get("cls") in HEADS]
    for i, w in enumerate(cands):
        if (key(w, lang) in QUANT | COMPOUND or w.get("cls") == "num") and i + 1 < len(cands):
            continue
        # THE NOUN OVER ITS ADJECTIVE (Hebrews 1:1, 2026-10-17: the
        # object of this is 'last days' and not just 'last')
        if w.get("cls") == "adj":
            noun = next((x for x in cands[i + 1:] if x.get("cls") in ("noun", "name")), None)
            if noun:
                return noun
        return w
    return None
HEADS = {"noun", "pron", "name", "adj", "num", "x"}


def leaves(n):
    if "w" in n:
        yield n
    for k in n.get("kids") or []:
        yield from leaves(k)


def core_leaves(n, keep_clause):
    """The phrase's own words: the preposition and its object, stopping where a
    clause inside it begins (a relative clause describing the object). In
    Hebrews 1:1, "in [His] Son": the word-by-word listing was not ended -- the
    phrase ran on through verse 4, because 'whom He appointed heir ...' hangs
    inside it. A phrase that governs a clause (PrepCL: "to hide it") keeps it."""
    if "w" in n:
        yield n
        return
    for k in n.get("kids") or []:
        if k.get("cls") == "cl" and not keep_clause:
            continue
        yield from core_leaves(k, keep_clause)


def verse_of_words(tree, ref):
    """Which verse each word is in: (chapter, verse). MACULA keeps a sentence
    that runs across verses under its first verse: Romans 8:39's phrases were
    filed under 8:38 and the sheet showed none (the one "wrong" marked,
    2026-10-17). Each word's own verse is in MACULA's reference for it, which
    tools/phrases.py now keeps as `at` wherever it differs from the
    sentence's first verse.
    WRONG TURNS, KEPT:
    - the first fix moved to the next verse wherever the numbering dropped.
      The trees list words in grammatical order, not reading order, so the
      numbering drops inside a verse too; it scattered phrases across 31,133
      verses and lost Nehemiah 8.
    - the second placed a word by its number AND its spelling against the
      clause layer's word nodes, trying the first verse, then the next five.
      "Spelling" was a containment test, and a one-letter Hebrew morpheme is
      contained in nearly any word, so a phrase could match a verse it is not
      in, and one that missed its own verse's spelling could match a later
      one: 2 Samuel 6:3 showed verse 2's phrase, Acts 11:4 had 11:5's "in the
      city of Joppa" (found 2026-10-18; up to 19% of phrases suspect). The
      verse was in MACULA all along; tools/phrases.py read it and threw it
      away."""
    _b, c, v = mref(ref).split(".")
    out = {}
    for w in leaves(tree):
        at = w.get("at")
        out[id(w)] = tuple(int(x) for x in at.split(":")) if at else (int(c), int(v))
    return out


def mref(usfm_ref):
    """USFM's "1SA.17.45" -> the project's "1Sa.17.45"."""
    b, c, v = usfm_ref.split(".")
    b = b[:2] + b[2:].lower() if b[0].isdigit() else b[0] + b[1:].lower()
    return f"{b}.{c}.{v}"


def phrases_of(tree, ref, vmap=None):
    out = []

    def walk(n, parent, grand):
        if n.get("cls") == "pp":
            ws = list(core_leaves(n, n.get("rule") == "PrepCL"))
            if ws:
                prep = ws[0]
                lang = "G" if any("Ͱ" <= ch <= "Ͽ" or "ἀ" <= ch <= "῿"
                                  for ch in prep.get("t") or "") else "H"
                obj = head_of(ws[1:], n.get("rule"), lang)
                pcls = (parent or {}).get("cls")
                attaches = {"cl": "the action (its clause)", "np": "a noun", "pp": "another phrase"}.get(pcls, pcls or "")
                head = None
                if pcls == "np":
                    head = next((w for w in leaves(parent) if w.get("cls") in ("noun", "name") and w not in ws), None)
                # INSIDE A CLAUSE THAT DESCRIBES A NOUN, it says where or what
                # that noun is (Nehemiah 8:1: "'[was] before the gate of
                # the water' attaches to 'the open space'")
                elif pcls == "cl" and (grand or {}).get("cls") == "np":
                    attaches = "a noun (through the clause describing it)"
                    head = next((w for w in leaves(grand) if w.get("cls") in ("noun", "name") and w not in ws), None)
                # (lang above: Greek and Greek Extended only. One range from
                # U+0370 to U+1FFF also holds Hebrew, U+0590, and read every
                # Hebrew word as Greek on the second build.)
                pk, ok = key(prep, lang), key(obj, lang)
                rel, rule = SURE.get(pk), None
                if rel:
                    rule = f"preposition {prep.get('l')} ({pk})"
                elif obj and ok in TIME_WORDS and pk in TIME_PREPS:
                    rel, rule = "time", f"{prep.get('l')} with a word for a time ({obj.get('l')})"
                b, c, v = mref(ref).split(".")
                # the phrase's verse is its preposition's: a phrase never
                # starts in one verse and is filed by a word in the next
                cno, vno = (vmap or {}).get(id(ws[0]), (int(c), int(v)))
                out.append({"id": f"{mref(ref)}#pp{len(out) + 1}",
                            "verse": f"{b}.{cno}.{vno}",
                            "w": [ws[0]["w"], ws[-1]["w"]],
                            "text": " ".join(w.get("t") or "" for w in ws),
                            "gloss": " ".join(w.get("g") or "" for w in ws),
                            "prep": {k: prep.get(k) for k in ("t", "g", "l", "s")},
                            "object": {k: obj.get(k) for k in ("t", "g", "l", "s", "cls")} if obj else None,
                            "attaches": attaches,
                            "attaches_head": {k: head.get(k) for k in ("t", "g", "l")} if head else None,
                            "macula_role": n.get("role"), "rule_shape": n.get("rule"),
                            "relation": rel, "by": rule})
        for k in n.get("kids") or []:
            walk(k, n, parent)

    walk(tree, None, None)
    return out


def build():
    DST.parent.mkdir(parents=True, exist_ok=True)
    n, rel, att = 0, collections.Counter(), collections.Counter()
    with gzip.open(SRC, "rt", encoding="utf-8") as f, gzip.open(DST, "wt", encoding="utf-8") as g:
        next(f)
        g.write(json.dumps({"_note": "Prepositional phrases from MACULA's trees (Biblica, CC BY 4.0), by "
                            "tools/wordgraph/prep_phrases.py; relation named only where a rule is certain (plan 2.13)."},
                           ensure_ascii=False) + "\n")
        by_verse = collections.defaultdict(list)
        for line in f:
            d = json.loads(line)
            pps = []
            for t in d.get("trees") or []:
                pps += phrases_of(t, d["ref"], verse_of_words(t, d["ref"]))
            # the id the judged pass knew (numbered per entry: a verse of two
            # sentences has two trees, and numbering per tree gave Mark 2:13
            # two "#pp1"), kept so its answers still join
            for i, p in enumerate(pps):
                p["old_id"] = f"{mref(d['ref'])}#pp{i + 1}"
                by_verse[p.pop("verse")].append(p)
        # filed under the verse each phrase is in, numbered there
        for vref, pps in by_verse.items():
            for i, p in enumerate(pps):
                p["id"] = f"{vref}#pp{i + 1}"
            g.write(json.dumps({"ref": vref, "pp": pps}, ensure_ascii=False) + "\n")
            for p in pps:
                n += 1
                rel[p["relation"] or "(left for judgment)"] += 1
                att[p["attaches"]] += 1
    print(f"{n:,} prepositional phrases -> {DST.relative_to(ROOT)}")
    print("relation:", {k: f"{v:,}" for k, v in rel.most_common()})
    print("attaches to:", {k: f"{v:,}" for k, v in att.most_common()})


SHEET = ["Gen.1.1", "Gen.22.2", "Exo.14.21", "Lev.1.3", "Deu.6.5", "Jos.1.9", "Jdg.6.11", "Rut.1.1",
         "1Sa.17.45", "Neh.8.1", "Job.38.4", "Psa.23.2", "Pro.3.5", "Isa.53.5", "Jon.1.3",
         "Mat.5.1", "Mrk.1.9", "Luk.2.4", "Jhn.1.1", "Act.1.8", "Rom.8.39", "1Co.13.12", "Heb.1.1", "Rev.1.9"]


def sheet():
    sys.path.insert(0, str(ROOT / "tools" / "sweep"))
    import context as C  # noqa: E402
    bsb = C._bsb()
    rows = {}
    # the judged pass's answers where they exist (pp_merge.py), else the rules alone
    joined = DST.with_name("prep-phrases-judged.jsonl.gz")
    with gzip.open(joined if joined.exists() else DST, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            d = json.loads(line)
            if d["ref"] in SHEET:
                rows[d["ref"]] = d["pp"]
    e = html.escape
    cards = []
    for ref in SHEET:
        title, text = bsb(ref)
        items = []
        for p in rows.get(ref, []):
            obj = p["object"]
            if p.get("kind") == "judged":
                rel = (f"<b class=jud>{e(p['relation'])}</b> <span class=tag>judged · {e(p.get('confidence') or '')}</span> "
                       f"<span class=k>{e(p.get('by') or '')}</span>" if p["relation"]
                       else f"<span class=open>none: not plain</span> <span class=k>{e(p.get('by') or '')}</span>")
            else:
                rel = (f"<b class=rel>{e(p['relation'])}</b> <span class=tag>rule</span> <span class=k>({e(p['by'])})</span>"
                       if p["relation"] else "<span class=open>left for judgment</span>")
            items.append(f"<tr><td class=orig>{e(p['text'])}</td><td>{e(p['gloss'])}</td>"
                         f"<td>{e(p['prep']['l'] or '')} <span class=k>{e(p['prep']['g'] or '')}</span></td>"
                         f"<td>{e((obj or {}).get('g') or '—')}{' <span class=k>(pronoun: the sweep resolves it)</span>' if (obj or {}).get('cls') == 'pron' else ''}</td>"
                         f"<td>{e(p['attaches'])}{(' <span class=k>' + e(p['attaches_head'].get('g') or '') + '</span>') if p.get('attaches_head') else ''}</td>"
                         f"<td>{rel}</td></tr>")
        cards.append(f"<section class=card><h2>{e(title)}</h2><div class=t>{e(text)}</div>"
                     + (f"<table><tr><th>original</th><th>word by word</th><th>preposition</th><th>its object</th>"
                        f"<th>attaches to</th><th>relation</th></tr>{''.join(items)}</table>" if items
                        else "<p class=k>No prepositional phrase in this verse.</p>")
                     + f"""<div class=mark data-ref="{e(ref)}"><label><input type=radio name="m-{e(ref)}" value=right> right</label>
<label><input type=radio name="m-{e(ref)}" value=partly> partly</label><label><input type=radio name="m-{e(ref)}" value=wrong> wrong</label>
<textarea placeholder="What is off (optional)"></textarea></div></section>""")
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Prepositional phrases</title><style>
:root{{--paper:#F3F5F8;--surface:#fff;--ink:#141F2C;--muted:#5C6A7B;--rule:#BAC4D0;--accent:#356A8C;--ok:#1F7A4D;--warm:#96591A}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2C3A4A;--accent:#7FB2D6;--ok:#5CC28F;--warm:#E2B04A}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Georgia,serif}} main{{max-width:980px;margin:0 auto;padding:16px}}
.card{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:10px 14px;margin:12px 0;overflow-x:auto}}
h2{{font-size:18px;margin:0 0 4px}} .t{{border-left:3px solid var(--accent);padding:2px 10px;margin:6px 0 8px}}
table{{border-collapse:collapse;width:100%;font-size:14px}} th,td{{text-align:left;padding:4px 6px;border-bottom:1px solid var(--rule);vertical-align:top}}
th{{font-size:12px;color:var(--muted);font-weight:normal}} .orig{{font-size:16px;white-space:nowrap}} .k{{color:var(--muted);font-size:12.5px}}
.rel{{color:var(--ok)}} .jud{{color:var(--accent)}} .open{{color:var(--warm);font-size:13px}} .lead{{color:var(--muted)}}
.tag{{border:1px solid var(--rule);border-radius:8px;padding:0 5px;font-size:11px;color:var(--muted)}}
.mark{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;border-top:1px dashed var(--rule);margin-top:8px;padding-top:6px;font-size:14px}}
.mark textarea{{flex:1 1 240px;min-height:2em;font:inherit;background:var(--paper);color:var(--ink);border:1px solid var(--rule);border-radius:6px}}
button{{font:inherit;padding:5px 12px;border-radius:6px;border:1px solid var(--accent);background:var(--surface);color:var(--accent)}}
</style></head><body><main><h1>Prepositional phrases, by rule only</h1>
<p class=lead>Plan 2.13 on {len(SHEET)} verses across the canon. Each phrase is read off MACULA's tree: its preposition,
its object, and what it attaches to. A relation tagged <span class=tag>rule</span> (green) is named by a rule that cannot
be wrong; one tagged <span class=tag>judged</span> (blue) is a reading by automated analysis, a passage at a time, choosing
from a closed list or <span class=open>none</span> where it is not plain. The relation names are provisional until you
rule on them. Nothing here is in the graph.</p><p><button id=exp>Copy my marks</button> <span id=st class=k></span></p>
{''.join(cards)}</main><script>
const KEY='prep-phrases-2026-10-17'; let M={{}}; try{{M=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
document.querySelectorAll('.mark').forEach(m=>{{const r=m.dataset.ref,s=M[r]||{{}};
 m.querySelectorAll('input').forEach(i=>{{if(i.value===s.mark)i.checked=true;i.onchange=()=>{{(M[r]=M[r]||{{}}).mark=i.value;save()}}}});
 const t=m.querySelector('textarea');t.value=s.note||'';t.oninput=()=>{{(M[r]=M[r]||{{}}).note=t.value;save()}};}});
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(M))}}catch(e){{}}}}
document.getElementById('exp').onclick=async()=>{{const x=JSON.stringify({{sheet:KEY,marks:M}},null,1);
 try{{await navigator.clipboard.writeText(x);document.getElementById('st').textContent='Copied: paste it into the chat.'}}catch(e){{prompt('Copy this',x)}}}};
</script></body></html>"""
    out = ROOT / "docs" / "review" / "prep-phrases-2026-10-17.html"
    out.write_text(page, encoding="utf-8")
    print(f"{len(SHEET)} verses -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    sheet() if "--sheet" in sys.argv else build()
