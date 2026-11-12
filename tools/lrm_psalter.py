"""The Psalter in /ns/biblio (plan 8.1g, step 3; 2026-11-06): 150 psalms, each its own Work, the Psalter a Work that
incorporates them, and the order of the Masoretic Text in its five books.

    python tools/lrm_psalter.py            -> out/lrm/psalter.nt, and a tally

Built on the pilot (tools/lrm_pilot.py): the same addresses and the same mapping, with step 1's corrections. A
psalm is a Work, and its Hebrew (MACULA, after the Leningrad Codex) and its Berean English are two Expressions of
it, the English a translation of the Hebrew. The Psalter's two Expressions incorporate the psalms' (R75), never
have them as parts (R67), and every Work has its own creation event, with no agent, date or place.

THE VERSES. The Hebrew counts a heading as verses of its own, and the Berean folds it into verse 1: 2,527 Hebrew
verses against 2,461 English ones, with 62 psalms numbered differently. Each text's verses are its own segments,
and each Hebrew verse is aligned to the English verse the versification map (structure.to_english) places it in.
Psalm 51's two-verse heading and first line are all English 51:1, so there the alignment is many to one.

THE HEADINGS. Only who a heading names, with the two approved terms: `superscriptionNames` and `composedBy`, each
inside a described claim, never a plain triple. The 101 attributions were judged by the Mac and twice by DeepSeek
(`16-psalm-headings`, 2026-11-06: all 286 claims agreed, 24 of 24 plants caught).
  - A name the graph holds once (David, Solomon, Moses): the heading names that person, which the text states.
    The narrator's claim, explicit.
  - A name the graph holds more than once (Asaph, Heman, Ethan): which one the heading means is the editors'
    identification. Conjectured, as in the pilot.
  - Who composed the psalm: always the editors', disputed. "A Psalm of David" may name an author, a collection
    or a dedication.
  - "The sons of Korah" (11 psalms): the graph has no record for them (korah_son_of_izhar is Korah himself),
    so those are held and counted, not pointed at the wrong record.
The heading's kind ("Maskil"), its directions ("For the choirmaster") and its occasions have no approved term yet,
so they are counted and not published.
"""
import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
import lrm_pilot  # noqa: E402
from structure import to_english  # noqa: E402
import psalm_headings as PH  # noqa: E402

OUT = ROOT / "out" / "lrm" / "psalter.nt"
PUBLISHED = ROOT / "out" / "export" / "psalter.nt.gz"
SITE = "https://bibleontology.org"
FX = json.loads((ROOT / "tests" / "fixtures" / "lrm_psalm73.json").read_text(encoding="utf-8"))
BOOKS = [("I", 1, 41), ("II", 42, 72), ("III", 73, 89), ("IV", 90, 106), ("V", 107, 150)]
# who a heading names -> (the record, whether the graph holds that name once)
NAMED = {"David": ("david", True), "Solomon": ("solomon", True), "Moses": ("moses", True),
         "Asaph": ("asaph_singer", False), "Heman the Ezrahite": ("heman_singer", False),
         "Ethan the Ezrahite": ("ethan_singer", False)}
HELD = {"the sons of Korah": "the graph has no record for the sons of Korah (korah_son_of_izhar is Korah himself)"}
NARRATOR = f"{SITE}/voice/narrator"
EDITORS = f"{SITE}/voice/reader/editors"


def hebrew_verses():
    heb = collections.defaultdict(set)
    for line in gzip.open(ROOT / "out" / "structure-nodes.jsonl.gz", "rt", encoding="utf-8"):
        d = json.loads(line)
        if d.get("word") and d["ref"].startswith("Psa."):
            _b, c, v = d["ref"].split(".")
            heb[int(c)].add(int(v))
    return heb


def english_verses():
    eng, first = collections.defaultdict(set), {}
    for line in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("b") == "Ps":
            eng[r["c"]].add(r["v"])
            if r["v"] == 1:
                first[r["c"]] = r["t"]
    return eng, first


def fixture():
    """The pilot's fixture, grown to the whole Psalter (everything but the verses)."""
    fx = {k: FX[k] for k in ("site", "base", "ns", "terms")}
    fx["works"] = [{"id": "work/psalter", "label": "The Psalter"}] + \
        [{"id": f"work/psalm-{c}", "label": f"Psalm {c}"} for c in range(1, 151)]
    ex = [{"id": "expr/psalter-hebrew", "label": "The Psalter in Hebrew (MACULA Hebrew, after the Westminster Leningrad Codex)",
           "realises": "work/psalter", "language": "hbo",
           "incorporates": [f"expr/psalm-{c}-hebrew" for c in range(1, 151)]},
          {"id": "expr/psalter-bsb", "label": "The Psalter in English (the Berean Standard Bible)",
           "realises": "work/psalter", "language": "en", "translationOf": "expr/psalter-hebrew",
           "incorporates": [f"expr/psalm-{c}-bsb" for c in range(1, 151)]}]
    for c in range(1, 151):
        ex.append({"id": f"expr/psalm-{c}-hebrew", "realises": f"work/psalm-{c}", "language": "hbo",
                   "label": f"Psalm {c} in Hebrew (MACULA Hebrew, after the Westminster Leningrad Codex)"})
        ex.append({"id": f"expr/psalm-{c}-bsb", "realises": f"work/psalm-{c}", "language": "en",
                   "label": f"Psalm {c} in English (the Berean Standard Bible)", "translationOf": f"expr/psalm-{c}-hebrew"})
    fx["expressions"] = ex
    fx["manifestations"] = [
        {"id": "man/macula-hebrew", "label": "MACULA Hebrew, the dataset release by Biblica",
         "embodies": [e["id"] for e in ex if e["language"] == "hbo"], "source": "https://github.com/Clear-Bible/macula-hebrew"},
        {"id": "man/bsb", "label": "The Berean Standard Bible, the public-domain text",
         "embodies": [e["id"] for e in ex if e["language"] == "en"], "source": "https://berean.bible"}]
    fx["segments"] = {"verses": 0, "hebrew": {"expression": "", "id": ""}, "english": {"expression": "", "iri": ""}}
    fx["workCreations"] = [{"id": "event/psalter-creation", "created": "work/psalter"}] + \
        [{"id": f"event/psalm-{c}-creation", "created": f"work/psalm-{c}"} for c in range(1, 151)]
    sections = [{"id": f"arr/psalter-mt/book-{n.lower()}", "label": f"Book {n}", "first": a, "last": b}
                for n, a, b in BOOKS]
    entries = []
    for n, a, b in BOOKS:
        for c in range(a, b + 1):
            entries.append({"id": f"arr/psalter-mt/entry-{c}", "member": f"work/psalm-{c}", "position": c,
                            "section": f"arr/psalter-mt/book-{n.lower()}", "positionInSection": c - a + 1})
    fx["arrangement"] = {"id": "arr/psalter-mt", "of": "work/psalter",
                         "label": "The order of the Psalms in the Masoretic Text, as the Berean prints it",
                         "sections": sections, "entries": entries}
    return fx


def heading_claims(first):
    """The claims of who each heading names; and what is held or not yet publishable, counted."""
    claims, held, unpublished = [], collections.Counter(), collections.Counter()
    for c in range(1, 151):
        head = PH.heading_of(first.get(c, ""))
        if not head:
            continue
        for kind, _text in PH.claims_for(c, head):
            if kind != "author":
                unpublished[kind] += 1
        for a in PH.AUTHORS:
            if not re.search(r"\b[Oo]f " + re.escape(a) + r"\b", head):
                continue
            if a in HELD:
                held[a] += 1
                continue
            rec, once = NAMED[a]
            obj = f"{SITE}/e/{rec}"
            claims.append({"id": f"claim/psalm-{c}-superscription", "subject": f"work/psalm-{c}",
                           "relation": "superscriptionNames", "object": obj, "verse": f"{SITE}/p/Ps.{c}.1",
                           "certainty": "claim:explicit" if once else "claim:conjectured",
                           "voice": NARRATOR if once else EDITORS,
                           "label": f"The superscription of Psalm {c} names {a}" + ("" if once else
                                    f"; which {a} the graph holds is the editors' identification")})
            claims.append({"id": f"claim/psalm-{c}-composer", "subject": f"work/psalm-{c}", "relation": "composedBy",
                           "object": obj, "verse": f"{SITE}/p/Ps.{c}.1", "certainty": "claim:disputed",
                           "voice": EDITORS,
                           "label": f"{a} composed Psalm {c}: a reading of the superscription, which may name an "
                                    f"author, a collection or a dedication"})
    return claims, held, unpublished


def segment_triples(heb, eng, fx):
    ns, base = fx["ns"], fx["base"]
    T = lambda t: "<" + ns[t.split(":")[0]] + t.split(":")[1] + ">"       # noqa: E731
    typ, seg = "<" + ns["rdf"] + "type>", T(fx["terms"]["Segment"])
    of, num, al = T(fx["terms"]["segmentOf"]), T(fx["terms"]["segmentNumber"]), T(fx["terms"]["alignedWith"])
    integer = lambda n: f'"{n}"^^<{ns["xsd"]}integer>'                     # noqa: E731
    out = []
    for c in range(1, 151):
        for v in sorted(heb[c]):
            s = f"<{base}seg/hebrew/Ps.{c}.{v}>"
            out += [(s, typ, seg), (s, of, f"<{base}expr/psalm-{c}-hebrew>"), (s, num, integer(v))]
        for v in sorted(eng[c]):
            s = f"<{SITE}/p/Ps.{c}.{v}>"
            out += [(s, typ, seg), (s, of, f"<{base}expr/psalm-{c}-bsb>"), (s, num, integer(v))]
        home = {}
        for v in sorted(heb[c]):
            _b, ec, ev = to_english(f"Psa.{c}.{v}").split(".")
            assert int(ec) == c, f"Ps {c}:{v} maps out of its psalm, to {ec}:{ev}"
            home.setdefault(int(ev), []).append(v)
            out.append((f"<{SITE}/p/Ps.{c}.{ev}>", al, f"<{base}seg/hebrew/Ps.{c}.{v}>"))
        # AN ENGLISH VERSE WITH NO HEBREW OF ITS OWN continues the Hebrew verse before it: Hebrew Psalm 13:6 ("But I
        # have trusted ... I will sing to the LORD") is English 13:5 and 13:6, and the map gives a Hebrew verse one
        # English home. So such a verse is aligned to the Hebrew verse(s) of the English verse before it.
        last = []
        for ev in sorted(eng[c]):
            if ev in home:
                last = home[ev]
            else:
                assert last, f"Ps {c}:{ev} has no Hebrew verse, and none before it"
                for v in last:
                    out.append((f"<{SITE}/p/Ps.{c}.{ev}>", al, f"<{base}seg/hebrew/Ps.{c}.{v}>"))
    return out


def build():
    heb = hebrew_verses()
    eng, first = english_verses()
    fx = fixture()
    claims, held, unpublished = heading_claims(first)
    fx["claims"] = claims
    triples = lrm_pilot.build(fx) + segment_triples(heb, eng, fx)
    stats = {"psalms": 150, "hebrew_verses": sum(len(v) for v in heb.values()),
             "english_verses": sum(len(v) for v in eng.values()),
             "numbered_differently": sum(1 for c in range(1, 151) if len(heb[c]) != len(eng[c])),
             "claims": len(claims), "held": dict(held), "unpublished": dict(unpublished)}
    return triples, stats, fx


def main():
    triples, stats, _fx = build()
    text = lrm_pilot.to_ntriples(triples)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    # THE PUBLISHED COPY, beside the claims (plan 8.1g, the 1.4.0 release; 2026-11-11): reproducible gzip, committed
    # like the other exports and listed in out/export/void.ttl (tools/export_void.py)
    # opened, like every published export, by its terms and its sources (MACULA's credit in MACULA's words); N-Triples
    # takes "#" comment lines
    from ns_common import export_rights, gz_text
    with gz_text(PUBLISHED) as f:
        f.write("# The Psalter as LRMoo Works (bibleontology.org/ns/biblio)\n" + "\n".join(export_rights()) + "\n" + text)
    print(f"{OUT.relative_to(ROOT)}: {text.count(chr(10)):,} triples; {json.dumps(stats)}; "
          f"published copy {PUBLISHED.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
