"""The Psalm 73 LRM/LRMoo pilot (tools/lrm_pilot.py), checked on its fixture with the standard library alone
(2026-10-31, P-2026-10-31-2). Written before the code, as its acceptance test; its author may not change it.

    python -X utf8 tests/test_lrm_pilot.py

What it holds the pilot to: a Work is not its text (Expressions realise it, Manifestations embody them); a
translation is an Expression, never a new Work; a section of the Psalter's order is not a Work; the two texts'
verses are separate segments, aligned, never shared; the Work Creation has no agent or date; and who composed the
psalm, or which Asaph the superscription names, is described as the editors' claim and never stated.
"""
import copy
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import lrm_pilot  # noqa: E402

FX = json.loads((ROOT / "tests" / "fixtures" / "lrm_psalm73.json").read_text(encoding="utf-8"))
NS = FX["ns"]
fails = []


def T(term):
    p, _, local = term.partition(":")
    return "<" + NS[p] + local + ">"


def I(x):
    return "<" + (x if x.startswith("http") else FX["base"] + x) + ">"


TYPE = "<" + NS["rdf"] + "type>"
INT = "^^<" + NS["xsd"] + "integer>"
LINE = re.compile(r'^(<[^<>"\s]+>) (<[^<>"\s]+>) (<[^<>"\s]+>|"(?:[^"\\\n\r]|\\["\\nrt])*"(?:@[a-zA-Z]+(?:-[a-zA-Z0-9]+)*|\^\^<[^<>"\s]+>)?) \.$')


def parse(text):
    """[(s, p, o)] from N-Triples text, and the lines that do not parse."""
    good, bad = [], []
    for ln in text.split("\n"):
        if not ln:
            continue
        m = LINE.match(ln)
        (good.append(m.groups()) if m else bad.append(ln))
    return good, bad


def faults(fx, text):
    f = []
    trs, bad = parse(text)
    if bad:
        f.append(f"{len(bad)} line(s) are not valid N-Triples, e.g. {bad[0][:90]!r}")
    lines = [l for l in text.split("\n") if l]
    if lines != sorted(set(lines)):
        f.append("the lines are not sorted and unique")
    if text and not text.endswith("\n"):
        f.append("the text does not end with a newline")
    S = set(trs)

    def objs(s, p):
        return [o for (a, b, o) in trs if a == s and b == p]

    def subs(p, o):
        return [a for (a, b, c) in trs if b == p and c == o]
    # ---- every IRI is the site's, the base's or a declared namespace's
    known = [fx["site"]] + list(NS.values()) + [m["source"] for m in fx["manifestations"]]
    for t in trs:
        for x in t:
            if x.startswith("<") and not any(x[1:].startswith(k) for k in known):
                f.append(f"an IRI outside the declared namespaces: {x}")
    # ---- Works, Expressions, Manifestations
    works = set(subs(TYPE, T(fx["terms"]["Work"])))
    if works != {I(w["id"]) for w in fx["works"]}:
        f.append(f"the Works are {sorted(works)}, not exactly the fixture's two")
    for w in fx["works"]:
        if f'"{w["label"]}"@en' not in objs(I(w["id"]), T(fx["terms"]["label"])):
            f.append(f"{w['id']}: no English label")
    for m in fx["members"]:
        if (I(m["whole"]), T(fx["terms"]["has_member"]), I(m["part"])) not in S:
            f.append(f"{m['whole']} does not have {m['part']} as a member")
    exprs = set(subs(TYPE, T(fx["terms"]["Expression"])))
    if exprs != {I(e["id"]) for e in fx["expressions"]}:
        f.append("the Expressions are not exactly the fixture's two")
    for e in fx["expressions"]:
        who = subs(T(fx["terms"]["is_realised_in"]), I(e["id"]))
        if who != [I(e["realises"])]:
            f.append(f"{e['id']}: realised by {who}, not exactly by {e['realises']}")
        if f'"{e["language"]}"' not in objs(I(e["id"]), T(fx["terms"]["language"])):
            f.append(f"{e['id']}: no language")
        if e.get("translationOf") and (I(e["id"]), T(fx["terms"]["translationOf"]), I(e["translationOf"])) not in S:
            f.append(f"{e['id']}: not marked a translation of {e['translationOf']}")
        if I(e["id"]) in works:
            f.append(f"{e['id']}: an Expression typed as a Work (a translation is not a new Work)")
    mans = set(subs(TYPE, T(fx["terms"]["Manifestation"])))
    if mans != {I(m["id"]) for m in fx["manifestations"]}:
        f.append("the Manifestations are not exactly the fixture's two")
    for m in fx["manifestations"]:
        for x in m["embodies"]:
            if (I(m["id"]), T(fx["terms"]["embodies"]), I(x)) not in S:
                f.append(f"{m['id']} does not embody {x}")
        if (I(m["id"]), T(fx["terms"]["source"]), "<" + m["source"] + ">") not in S:
            f.append(f"{m['id']}: no source")
    # ---- segments: 28 per text, never shared, aligned one to one
    seg = fx["segments"]
    n = seg["verses"]
    heb = [I(seg["hebrew"]["id"].format(n=i)) for i in range(1, n + 1)]
    eng = ["<" + seg["english"]["iri"].format(n=i) + ">" for i in range(1, n + 1)]
    for lst, ex in ((heb, seg["hebrew"]["expression"]), (eng, seg["english"]["expression"])):
        for i, s in enumerate(lst, 1):
            if objs(s, T(fx["terms"]["segmentOf"])) != [I(ex)]:
                f.append(f"segment {s} is not a segment of exactly {ex}")
                break
            if objs(s, T(fx["terms"]["segmentNumber"])) != [f'"{i}"' + INT]:
                f.append(f"segment {s}: segmentNumber is not {i}")
                break
            if T(fx["terms"]["Segment"]) not in objs(s, TYPE):
                f.append(f"segment {s}: not typed a Segment")
                break
    if set(heb) & set(eng):
        f.append("a segment shared by the two texts")
    al = {(a, c) for (a, b, c) in trs if b == T(fx["terms"]["alignedWith"])}
    if al != set(zip(eng, heb)):
        f.append("the alignment is not exactly English verse n to Hebrew verse n")
    # ---- the Work Creation: what it created, and nothing else
    wc = I(fx["workCreation"]["id"])
    rest = {(b, c) for (a, b, c) in trs if a == wc}
    if rest != {(TYPE, T(fx["terms"]["WorkCreation"])), (T(fx["terms"]["created"]), I(fx["workCreation"]["created"]))}:
        f.append(f"the Work Creation says more or less than what it created: {sorted(rest)}")
    # ---- the arrangement
    A = fx["arrangement"]
    if (I(A["id"]), TYPE, T(fx["terms"]["Arrangement"])) not in S or \
            (I(A["id"]), T(fx["terms"]["arrangementOf"]), I(A["of"])) not in S:
        f.append("the arrangement is not typed or not of the Psalter")
    for sc in A["sections"]:
        need = {(TYPE, T(fx["terms"]["Section"])), (T(fx["terms"]["sectionOf"]), I(A["id"])),
                (T(fx["terms"]["firstPosition"]), f'"{sc["first"]}"' + INT),
                (T(fx["terms"]["lastPosition"]), f'"{sc["last"]}"' + INT),
                (T(fx["terms"]["label"]), f'"{sc["label"]}"@en')}
        if not need <= {(b, c) for (a, b, c) in trs if a == I(sc["id"])}:
            f.append(f"section {sc['id']}: not described in full")
        if I(sc["id"]) in works:
            f.append(f"section {sc['id']} typed as a Work (a division is not a Work)")
    for en in A["entries"]:
        need = {(TYPE, T(fx["terms"]["ArrangementEntry"])), (T(fx["terms"]["member"]), I(en["member"])),
                (T(fx["terms"]["inArrangement"]), I(A["id"])), (T(fx["terms"]["position"]), f'"{en["position"]}"' + INT),
                (T(fx["terms"]["inSection"]), I(en["section"])),
                (T(fx["terms"]["positionInSection"]), f'"{en["positionInSection"]}"' + INT)}
        if not need <= {(b, c) for (a, b, c) in trs if a == I(en["id"])}:
            f.append(f"entry {en['id']}: not described in full")
    # ---- the readings: described as claims, never stated
    for c in fx["claims"]:
        need = {(TYPE, T(fx["terms"]["Claim"])), (T(fx["terms"]["subject"]), I(c["subject"])),
                (T(fx["terms"]["relation"]), T(fx["terms"][c["relation"]])), (T(fx["terms"]["object"]), "<" + c["object"] + ">"),
                (T(fx["terms"]["verse"]), "<" + c["verse"] + ">"), (T(fx["terms"]["certainty"]), T(c["certainty"])),
                (T(fx["terms"]["voice"]), "<" + c["voice"] + ">")}
        if not need <= {(b, c2) for (a, b, c2) in trs if a == I(c["id"])}:
            f.append(f"claim {c['id']}: not described in full")
        if (I(c["subject"]), T(fx["terms"][c["relation"]]), "<" + c["object"] + ">") in S:
            f.append(f"claim {c['id']}: its reading is STATED as a plain triple")
    persons = {"<" + c["object"] + ">" for c in fx["claims"]}
    for (a, b, c) in trs:
        if c in persons and b != T(fx["terms"]["object"]):
            f.append(f"a person is the object of a stated triple: {b}")
        if re.search(r"#(date|dateTime|gYear)>$", c):
            f.append("a date: the text gives none")
        if c.startswith('"') and b != T(fx["terms"]["language"]) and \
                not ("@" in c.rsplit('"', 1)[1] or "^^" in c.rsplit('"', 1)[1]):
            f.append("a literal with neither a language nor a datatype")
        if re.search(r"\b(colour|honour|centre|favour|catalogue)\b", c, re.I):
            f.append("British spelling")
    return f


text = lrm_pilot.to_ntriples(lrm_pilot.build(FX))
for x in faults(FX, text):
    fails.append(x)
if lrm_pilot.to_ntriples(lrm_pilot.build(copy.deepcopy(FX))) != text:
    fails.append("not deterministic")
# a label with a quote, a backslash and a line break must still make valid N-Triples
fx2 = copy.deepcopy(FX)
fx2["works"][0]["label"] = 'Psalm "73"\\ \nline two'
_, bad = parse(lrm_pilot.to_ntriples(lrm_pilot.build(fx2)))
if bad:
    fails.append("a label with a quote, backslash or line break is not escaped")
# main() writes the file
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "psalm73.nt"
    lrm_pilot.main([str(ROOT / "tests" / "fixtures" / "lrm_psalm73.json"), str(out)])
    if not out.exists() or out.read_text(encoding="utf-8") != text:
        fails.append("main(fixture, out) does not write the N-Triples")
# planted faults the check must catch
planted = 0
lines = text.split("\n")
w73 = I("work/psalm-73")
asaph = "<" + FX["claims"][1]["object"] + ">"
for what, bad_text in [
        ("authorship stated", text + f'{w73} {T("biblio:composedBy")} {asaph} .\n'),
        ("Book III typed a Work", text + f'{I("arr/psalter-mt/book-3")} {TYPE} {T("lrmoo:F1_Work")} .\n'),
        ("a date", text + f'{I("event/psalm-73-creation")} {T("dcterms:date")} "-1000"^^<{NS["xsd"]}gYear> .\n'),
        ("a dropped segment", "\n".join(l for l in lines if "Ps.73.28" not in l) + "\n")]:
    planted += 1
    srt = "".join(sorted(set(l + "\n" for l in bad_text.split("\n") if l)))
    if not faults(FX, srt):
        fails.append(f"planted: the check did not catch {what}")
for m in fails:
    print("FAIL", m)
print(f"LRM pilot: {len(parse(text)[0])} triples; planted faults caught: "
      f"{planted - sum(1 for m in fails if m.startswith('planted'))} of {planted}; {len(fails)} failures")
sys.exit(1 if fails else 0)
