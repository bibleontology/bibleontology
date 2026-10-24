"""A concept hub's spec by rule (plan 7.6g, step 3).

2026-10-09, approved: every concept card gets the hub's layout and look by rule
... The 532 cards with 50+ verses also get rule-made rows, marked as grouped
by rule. A light check (a 16-verse spot sample) is the gate.

Love's and righteousness's rows were chosen by hand and read by nine readers.
These are chosen from the grammar's own counts, with labels made from the
words' glosses, and say so on the page ("by_rule"):

- the verbs whose object is the concept's word, four verses or more ("Keep
  the covenant", "Make the covenant") -- object_of;
- the words standing next to it, four verses or more ("Darkness and light",
  "Joy and gladness") -- with, adjacent;
- the divine name next to it, as one row ("The covenant of the LORD, of
  God");
- for its verbs: commanded ("Rejoice!"), and said of God.

The spec is written to ontology/concept-hubs/<id>.json with "shown": false
and built by hub_build into out/concept-hubs/<id>.json, so it is seen in the
preview (BIBLEONT_SHOW_UNREVIEWED) and nowhere else until approved.

    python tools/concepts/auto_spec.py joy covenant darkness
"""
from __future__ import annotations

import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "concepts"))
import hub_build as H  # noqa: E402

S = H.S
NF, LETTERS = H.NF, H.LETTERS
DIVINE = ["יהוה", "θεός", "אֱלֹהִים", "κύριος", "אֲדֹנָי"]
MINV = 4


def head(gloss):
    """a gloss's head word: "to keep: guard" -> "keep" """
    g = re.split(r"[:;,(/]", gloss or "")[0].strip()
    return re.sub(r"^(to|be) ", "", g).strip()


def auto(d, eid, frames, clauses):
    ent = S.api_entity(d, {"id": [eid]})
    if not ent.get("found"):
        raise SystemExit(f"no card {eid}")
    name = ent["name"]
    keys = [w["key"] for w in ent["words"] if not w.get("via") and w["key"] not in S._PROPER]
    # the card's English, three letters up ("joy" is three)
    def toks(g):
        return {S._gstem(t) for t in re.findall(r"[a-z]+", (g or "").lower()) if len(t) >= 3 and t not in S._GSTOP}
    stems = toks(name)
    for w in ent["words"]:
        stems |= toks(head(w.get("gloss")))
    sense = r"\b(" + "|".join(sorted(stems)) + ")" if stems else "."
    mine = {LETTERS(d["lemmas"].get(k) or "") for k in keys}
    pos = {}
    for k in keys:
        p = ((d["lex"].get(k) or {}).get("pos") or "").split(":")[-1][:1]
        pos[k] = H.POS.get(p) or "noun"
    forms = set(pos.values())
    # lemma -> key, for the companions' glosses and parts of speech: the
    # commonest key of a lemma (the first was the preposition בְּ read as the
    # place "Atharim", 2026-10-09)
    of_lemma = {}
    for k, lm in d["lemmas"].items():
        n = len(d["occ"].get(k) or ())
        if n > of_lemma.get(NF(lm), (None, -1))[1]:
            of_lemma[NF(lm)] = (k, n)
    of_lemma = {lm: kn[0] for lm, kn in of_lemma.items()}

    def gloss(lm, refs=None):
        """how the text renders it: in the given verses where it can (the
        Berean's "make a covenant", not the lexicon's "cut"), else its gloss"""
        k = of_lemma.get(NF(lm))
        if not k:
            return lm
        if refs:
            c = collections.Counter(head(g) for r, g in d["occ"].get(k) or () if r in refs and g)
            if c:
                return c.most_common(1)[0][0]
        return head((d["lex"].get(k) or {}).get("gloss") or (d["profiles"].get(k) or {}).get("gloss") or lm)

    def is_noun(lm):
        k = of_lemma.get(NF(lm))
        p = ((d["lex"].get(k) or {}).get("pos") or "").split(":")[-1][:1] if k else ""
        return p == "N" and k not in S._PROPER

    rows = []
    # verbs whose object is the concept's word
    obj = collections.defaultdict(set)
    for fr in frames:
        if any(LETTERS(p) in mine for p in fr.get("patient") or []):
            obj[NF(fr.get("lemma"))].add(fr["ref"])
    for v, refs in sorted(obj.items(), key=lambda x: -len(x[1]))[:6]:
        if len(refs) >= MINV and LETTERS(v) not in mine:
            rows.append({"form": "noun", "label": f"{gloss(v, refs).capitalize()} the {name}", "object_of": [v]})
    # the divine name next to it, as a phrase
    divine = set()
    dset = {NF(x) for x in DIVINE}
    art = {NF(x) for x in ("ὁ", "הַ", "וְ", "γάρ", "δέ", "οὖν", "μέν")}
    for cl in clauses:
        for part in cl.get("parts") or []:
            seq = [NF(x) for x in part.get("lemmas") or [] if NF(x) not in art]
            for i, x in enumerate(seq):
                if LETTERS(x) in mine and set(seq[max(0, i - 1):i] + seq[i + 1:i + 2]) & dset:
                    divine.add(cl["ref"])
    if "noun" in forms and len(divine) >= MINV:
        rows.append({"form": "noun", "label": f"The {name} of the LORD, of God", "with": "@divine", "adjacent": True,
                     "note": "The text's own phrase, kept as written."})
    # THE NOUNS IT SHARES A VERSE WITH, by how much more than chance: darkness
    # and light stand in one verse far more than apart (Gen 1:4, John 1:5),
    # though seldom side by side. Common nouns (God, day, man) weigh less.
    # Each verse's own words, with their own Strong's number and part of
    # speech (the lemma alone named the preposition בְּ "Atharim" and let
    # "all", "not" through as nouns). כֹּל / πᾶς "all" is tagged a noun in
    # Hebrew and says nothing beside a concept.
    STOPN = {NF(x) for x in ("כֹּל", "πᾶς", "דָּבָר", "λόγος", "אִישׁ", "ἄνθρωπος", "יוֹם", "ἡμέρα")}
    vl, gl = {}, {}
    for mref, ws in d["orig"].items():
        s = set()
        for w in ws:
            lm = NF(w.get("l"))
            if not lm:
                continue
            s.add(lm)
            # a noun by the lexicon's own part of speech, under its own
            # Strong's number: MACULA marks pronouns and particles "noun" too
            # ("you", "this", "[obj.]"), and numbers from 9000 are its codes
            # for prefixes (בְּ, וְ, מִן)
            num = re.match(r"\d+", str(w.get("s") or ""))
            if not num or int(num.group()) >= 9000:
                continue
            key = ("h" if re.search(r"[֐-׿]", lm) else "g") + str(int(num.group()))
            lx = d["lex"].get(key) or {}
            if ((lx.get("pos") or "").split(":")[-1][:1] == "N" and key not in S._PROPER
                    and not re.search(r"\bpron|demonstr|particle", lx.get("pos") or "", re.I)):
                gl.setdefault(lm, head(lx.get("gloss") or w.get("g") or ""))
        vl[mref] = s
    df = collections.Counter(x for s in vl.values() for x in s)
    nv = len(vl)
    with_me = [s for s in vl.values() if any(LETTERS(x) in mine for x in s)]
    co = collections.Counter(x for s in with_me for x in s
                             if x in gl and x not in STOPN and LETTERS(x) not in mine and x not in dset
                             and (of_lemma.get(x) not in S._PROPER))
    import math
    scored = sorted(((n * math.log(nv / df[x]), x, n) for x, n in co.items() if n >= MINV), reverse=True)
    # the Hebrew and the Greek word that English renders alike make one row
    # ("Darkness and light": אוֹר and φῶς)
    merged = {}
    for _sc, y, _n in scored[:10]:
        lab = (gl.get(y) or gloss(y)).lower()
        if not re.fullmatch(r"[a-z][a-z '-]+", lab):
            continue
        merged.setdefault(lab, []).append(y)
    for lab, ys in list(merged.items())[:6]:
        rows.append({"form": "noun" if "noun" in forms else sorted(forms)[0],
                     "label": f"{name.capitalize()} and {lab}", "in_verse": ys})
    # its verbs
    if "verb" in forms:
        vg = next((head((d["lex"].get(k) or {}).get("gloss")) for k in keys if pos[k] == "verb"), name)
        rows.append({"form": "verb", "label": f"Commanded: {vg}", "stance": ["command"]})
        rows.append({"form": "verb", "label": "Said of God", "agent": "@divine", "not_stance": ["command"]})
    # what nothing above took, one row a form
    for f in sorted(forms):
        rows.append({"form": f, "label": {"noun": f"Every other {name}", "verb": f"Every other use",
                                          "adjective": f"Every other use"}[f]})
    lead = "noun" if "noun" in forms else sorted(forms)[0]
    spec = {"_about": "Made by tools/concepts/auto_spec.py from the grammar's counts (plan 7.6g step 3); "
                      "not read. Rows as in love.json.",
            "id": eid, "shown": False, "by_rule": True, "match": "all", "lead": lead,
            "titles": {"noun": f"What {name} stands beside", "verb": f"Who and when", "adjective": "Who is called it"},
            "words": keys, "sense": sense, "leads": [], "own_words": [o["id"] for o in (ent.get("face") or {}).get("own_words") or []],
            "gather": [], "sets": {"divine": DIVINE}, "rows": rows}
    (ROOT / "ontology" / "concept-hubs" / f"{eid}.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    return spec


def main():
    d = S.load()
    with gzip.open(ROOT / "out/frames.jsonl.gz", "rt", encoding="utf-8") as f:
        frames = [r for r in map(json.loads, f) if r.get("lemma")]
    with gzip.open(ROOT / "data/macula-clauses.jsonl.gz", "rt", encoding="utf-8") as f:
        clauses = [r for r in map(json.loads, f) if r.get("parts")]
    speaker = {}
    with gzip.open(ROOT / "out/speakers.jsonl.gz", "rt", encoding="utf-8") as f:
        for r in map(json.loads, f):
            if r.get("ref"):
                speaker.setdefault(r["ref"], r.get("speaker"))
    for eid in sys.argv[1:]:
        spec = auto(d, eid, frames, clauses)
        out = H.build(d, eid, frames, clauses, speaker)
        print(f"== {eid}: {len(spec['rows'])} rows; sense /{spec['sense']}/")
        for f in out["forms"]:
            print(f"   {f['form']} ({f['verses']} verses)")
            for r in f["rows"]:
                print(f"     {r['label'][:44]:44} {r['n']:4}  {', '.join(e['ref'] for e in r['eg'][:3])}")
            print(f"     {'More':44} {f['more']['n']:4}")


if __name__ == "__main__":
    main()
