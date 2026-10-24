"""Build a concept hub from its spec (plan 7.6f).

    python tools/concepts/hub_build.py love [righteousness ...]
      reads  ontology/concept-hubs/<id>.json
      writes out/concept-hubs/<id>.json

The spec names the concept's words, its rows and the cards each row opens.
This sorts every verse those words stand in into the rows, by the grammar
and nothing else:

  verb rows       by who acts (agent) and on whom (patient), from the frames
                  (out/frames.jsonl.gz); "I" takes the verse's speaker
  noun rows       by the words standing in the noun's own phrase (MACULA's
                  clauses): "the love of God", "faith, hope and love"
  adjective rows  the same, for the adjective
  pick rows       verses named in the spec ("What the text says love is")

The first row a verse matches in its form takes it; the rest are listed under
"More". THE RIGHT SENSE: a word counts in a verse only where the verse
renders it in this concept's sense (the spec's "sense", matched against
MACULA's rendering there) -- ἀφίημι "left" is not forgiveness, אהב "friend"
and φιλέω "kiss" are not love (the committee, 2026-10-09). Hebrew is
compared normalized (NFC): typed and stored vowel points differ in order.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

def NF(x):
    """NFC: typed and stored Hebrew order their vowel points differently.
    The rows' words (who, whom, beside) keep their points: without them רַע
    "evil" and רֵעַ "neighbor" are one spelling (Ps 52:3, "You love evil",
    fell under "Love your neighbor" when points were dropped, 2026-10-09)"""
    return unicodedata.normalize("NFC", x or "")


def LETTERS(x):
    """the concept's own words compared on their letters: the card holds אהב
    unpointed, the frames and clauses אָהֵב -- the word is one"""
    x = unicodedata.normalize("NFD", x or "")
    return unicodedata.normalize("NFC", "".join(ch for ch in x if not ("֑" <= ch <= "ׇ")))


FIRST = {NF(x) for x in ("ἐγώ", "אֲנִי", "אָנֹכִי")}
POS = {"V": "verb", "N": "noun", "A": "adjective"}


def build(d, hid, frames, clauses, speaker):
    spec = json.loads((ROOT / "ontology" / "concept-hubs" / f"{hid}.json").read_text(encoding="utf-8"))
    sets = {k: {NF(x) for x in v} for k, v in (spec.get("sets") or {}).items()}

    def lemset(v):
        out = set()
        for x in ([v] if isinstance(v, str) else (v or [])):
            out |= sets[x[1:]] if x.startswith("@") else {NF(x)}
        return out

    sense = re.compile(spec["sense"], re.I)
    if not d["verses"]:
        raise SystemExit("no verse text loaded")

    # a verse the Greek and the Berean divide differently, moved by hand
    # with its reason in the spec ("moves")
    hand = spec.get("moves") or {}

    def bsb(mref):
        b, c, v = S.bsb_ref(d, mref).split(".")
        vid = f"{S.MACULA_BACK.get(b, b)}.{c}.{v}"
        return (hand.get(vid) or {}).get("to", vid)

    # NO REPAIR BY THE ENGLISH (2026-10-09, both tried and withdrawn): moving
    # a verse whose Berean text lacks the word to a neighbour that has it, and
    # then dropping it there, each caught only verses that render the word
    # otherwise (Song 1:3 "adore", Isa 45:23 "truth"), 2 of 2 and 2 of 2
    # wrong. Acts 13:38, the case that prompted it, was the clause filing
    # below: the occurrences already have the word at 13:39.

    # A CLAUSE IS FILED UNDER THE VERSE IT STARTS IN: "the love of God" at the
    # end of Rom 8:38-39's one sentence was shown as 8:38 (found 2026-10-09,
    # 27 such in love). The word's own occurrences know its verse, so a clause
    # hit goes to the first verse from the clause's start where the word is.
    allocc = {}

    def locate(k, cref):
        b, c, v = bsb(cref).split(".")
        for n in range(int(v), int(v) + 9):
            if f"{b}.{c}.{n}" in allocc[k]:
                return f"{b}.{c}.{n}"
        return f"{b}.{c}.{v}"

    # the words, their form, and the verses where each carries this sense
    # Keyed by the word's key. Letters alone were the key until 2026-10-09:
    # צֶדֶק (noun) and צָדֵק (verb) share them, the verb overwrote the noun, and
    # 105 of 111 צֶדֶק verses (Ps 23:3, 85:10, 89:14) reached no row. So the
    # pointed form decides, and letters only where they name one word.
    words, form_of_lemma, ok, pointed, letters = [], {}, {}, {}, {}

    def which(x, form=None):
        """the concept's word this lemma is, or None"""
        n = NF(x)
        k = pointed.get(n)
        if k and (form is None or form_of_lemma[k] == form):
            return k
        c = [k for k in letters.get(LETTERS(n), []) if form is None or form_of_lemma[k] == form]
        return c[0] if len(c) == 1 else None
    # Two hand settings a worker on hope needed (2026-10-10): "forms" gives a
    # word its part of speech where the lexicon has none (קָוָה came out a noun
    # and its verb verses fell into noun rows); "sense_keep" keeps a verse the
    # gloss rule would drop where the Berean itself has the concept's word
    # (MACULA glosses קָוָה "wait" at Isa 42:4; the Berean prints "hope") --
    # each with its reason in the spec.
    forms_hand = spec.get("forms") or {}
    sense_keep = set(spec.get("sense_keep") or {})
    # and its opposite (the joy, grace and praise workers, 2026-10-10):
    # "sense_drop" {"Book.c.v": "reason"} takes a verse out of the concept
    # where the gloss passes it but the word is in another sense there --
    # χαίρω as the greeting (2 John 10), χαρίζομαι "handed over" (Acts 3:14).
    # {"Book.c.v": {"why": ..., "words": ["g5463"]}} limits it to those words,
    # for a verse that also holds the concept in another of its words.
    sense_drop = spec.get("sense_drop") or {}

    def dropped(vid, k):
        x = sense_drop.get(vid)
        return x is not None and (not isinstance(x, dict) or not x.get("words") or k in x["words"])
    for k in spec["words"]:
        lx = d["lex"].get(k) or {}
        p = (lx.get("pos") or "").split(":")[-1][:1]
        form = forms_hand.get(k) or POS.get(p) or ("verb" if S.api_sense(d, {"key": [k]}).get("kind") == "verb" else "noun")
        lemma = d["lemmas"].get(k) or lx.get("word")
        form_of_lemma[k] = form
        pointed[NF(lemma)] = k
        letters.setdefault(LETTERS(lemma), []).append(k)
        rows, _n = S.occurrences(d, k, cap=10 ** 6)
        keep = {bsb(r["ref"]) for r in rows if sense.search(r.get("gloss") or "") or bsb(r["ref"]) in sense_keep}
        keep = {v for v in keep if not dropped(v, k)}
        allocc[k] = {bsb(r["ref"]) for r in rows}
        drop = len(allocc[k]) - len(keep)
        ok[k] = keep
        meta = d["lmeta"].get(k) or {}
        words.append({"key": k, "lemma": d["lemmas"].get(k) or lx.get("word"), "form": form,
                      "translit": lx.get("translit") or S._first(meta, "transliteration"),
                      "gloss": lx.get("gloss") or (d["profiles"].get(k) or {}).get("gloss"),
                      "lang": "Hebrew" if k.startswith("h") else "Greek", "uses": len(keep), "other_sense": drop})
    # OTHER WORDS THE ENGLISH RENDERS THE SAME WAY (2026-10-09: focus on
    # agape love and then have a section at the bottom for other uses of the
    # English word love). The rows stand on the concept's own words and their
    # counterparts across the testaments; φιλέω, חֶסֶד, דּוֹד are different words
    # the English also calls love, so they are named apart, each with its
    # verses, and the reader is never handed one as the other. A word counts
    # where its in-verse gloss matches often enough to be a rendering of it,
    # not a stray ("lovers" once in 185 uses of רֵעַ).
    others = []
    osp = spec.get("others")
    if osp:
        orx = re.compile(osp["gloss"], re.I)
        own = set(spec["words"]) | set(osp.get("exclude") or [])
        for k, occ in d["occ"].items():
            if k in own:
                continue
            refs = []
            for ref, g in occ:
                if orx.search(g or ""):
                    vid = bsb(ref)
                    if vid not in refs:
                        refs.append(vid)
            if not refs or (len(refs) < osp.get("min_n", 10) and len(refs) < osp.get("min_share", .25) * len({r for r, _ in occ})):
                continue
            lx = d["lex"].get(k) or {}
            meta = d["lmeta"].get(k) or {}
            others.append({"key": k, "lemma": d["lemmas"].get(k) or lx.get("word"),
                           "translit": lx.get("translit") or S._first(meta, "transliteration"),
                           "gloss": lx.get("gloss") or (d["profiles"].get(k) or {}).get("gloss"),
                           "lang": "Hebrew" if k.startswith("h") else "Greek", "n": len(refs), "verses": refs})
        # BY HAND (the mercy panel, 2026-10-10): "add" {key: {verses, note}}
        # puts verses the gloss rule cannot reach (Hos 6:6 and Mic 6:8 are
        # חֶסֶד, and the Berean prints "mercy" there) first, so they are the
        # ones a reader sees, and carries a note; a word the rule did not
        # find at all is made from the lexicon. A key with no such word fails.
        by_key = {o["key"]: o for o in others}
        for k, a in (osp.get("add") or {}).items():
            o = by_key.get(k)
            if o is None:
                lx = d["lex"].get(k) or {}
                meta = d["lmeta"].get(k) or {}
                lemma = d["lemmas"].get(k) or lx.get("word")
                if not lemma:
                    raise SystemExit(f"others.add: no word {k}")
                o = by_key[k] = {"key": k, "lemma": lemma,
                                 "translit": lx.get("translit") or S._first(meta, "transliteration"),
                                 "gloss": lx.get("gloss") or (d["profiles"].get(k) or {}).get("gloss"),
                                 "lang": "Hebrew" if k.startswith("h") else "Greek", "verses": []}
                others.append(o)
            added = list(a.get("verses") or [])
            o["verses"] = added + [v for v in o["verses"] if v not in added]
            o["n"] = len(o["verses"])
            o["lead"] = added
            if a.get("note"):
                o["note"] = a["note"]
        others.sort(key=lambda o: -o["n"])
    # WHICH WORD EACH VERSE USES (2026-10-09: Matthew 23:6 does not use
    # agape ... when it is clearly a different word the user should be
    # informed): every placed verse keeps the concept's words it stands on
    lemma_of = {w["key"]: w["lemma"] for w in words}
    wordat = {}

    def note_word(vid, k, form):             # by form: a verb row names its verbs
        wordat.setdefault((form, vid), set()).add(k)
    rows = [dict(r, verses=[]) for r in spec["rows"]]
    placed = {f: set() for f in ("verb", "noun", "adjective")}
    seen_form = {f: set() for f in ("verb", "noun", "adjective")}
    # picked verses first
    for r in rows:
        for vid in r.get("pick") or []:
            r["verses"].append(vid)
            placed[r["form"]].add(vid)
    # A HEBREW OBJECT WITH לְ: "you will love (to) your neighbor" (Lev 19:18)
    # records no patient in the frames; the clause has it as a phrase led by
    # לְ beside the verb. Read as the one loved, for the concept's own verbs.
    lamed = {}
    LAMED = NF("לְ")
    for cl in clauses:
        parts = cl.get("parts") or []
        if any(pp["role"] == "v" and which((pp.get("lemmas") or [""])[0], "verb") for pp in parts):
            for pp in parts:
                lm = [NF(x) for x in pp.get("lemmas") or []]
                if pp["role"] == "pp" and lm and lm[0] == LAMED:
                    lamed.setdefault(cl["ref"], set()).update(lm[1:])
    # every word in a verse, for rows whose companion stands elsewhere in it
    # ("do righteousness": the verb is not in the noun's phrase) -- "in_verse"
    vwords = {}
    for cl in clauses:
        for part in cl.get("parts") or []:
            vwords.setdefault(cl["ref"], set()).update(NF(x) for x in part.get("lemmas") or [])
    # every word in a verb's own clause -- "in_clause": "justified ... by faith"
    # is one clause (Rom 3:28); a hymn's next line is not (1 Tim 3:16)
    cwords = {}
    for cl in clauses:
        ws, vs = set(), set()
        for part in cl.get("parts") or []:
            lm = {NF(x) for x in part.get("lemmas") or []}
            ws |= lm
            if part["role"] == "v":
                vs |= lm
        for v in vs:
            cwords.setdefault((cl["ref"], v), set()).update(ws)
    # the verbs whose object is one of the concept's words -- "object_of":
    # "pursue righteousness" (Prov 21:21), not "persecuted because of
    # righteousness" (Matt 5:10), though διώκω is both
    objverbs = {}
    for fr in frames:
        if any(which(p) for p in fr.get("patient") or []):
            objverbs.setdefault(fr["ref"], set()).add(NF(fr.get("lemma")))

    # THE VERSE'S OWN WORDS, from the word-by-word text: "in_verse" read the
    # words of clauses starting in a verse, so Eph 6:14 found "peace" from
    # 6:15 and Luke 1:75 "salvation" from 1:74 (second review, 2026-10-09)
    vlem = {}
    for mref, ws in d["orig"].items():
        try:
            v = bsb(mref)
        except Exception:
            continue
        vlem.setdefault(v, set()).update(NF(w.get("l")) for w in ws if w.get("l"))

    def fits(r, ref, clause_words, vid):
        # a verse taken out by hand, its reason in the spec ("πίστις" at Acts
        # 17:31 is "proof"): for what no rule can tell
        if vid in (r.get("not_verses") or {}):
            return False
        if r.get("in_verse") and not vlem.get(vid, set()) & lemset(r["in_verse"]):
            return False
        if r.get("in_clause") and not clause_words & lemset(r["in_clause"]):
            return False
        if r.get("object_of") and not objverbs.get(ref, set()) & lemset(r["object_of"]):
            return False
        if r.get("not_object_of") and objverbs.get(ref, set()) & lemset(r["not_object_of"]):
            return False
        return True

    # HOW A VERSE IS PLACED. "first": the first row it fits takes it, rows
    # disjoint (love: who is loved). "all": every row it fits, and the rows
    # with no condition take only what none took -- for a hub where the row
    # order would otherwise decide a contested verse (2026-10-09 review: Jas
    # 2:24, "justified by works and not by faith alone", stood under faith
    # only because the faith row came first)
    every = spec.get("match") == "all"
    CONDS = ("agent", "patient", "not_patient", "with", "in_verse", "in_clause", "object_of", "subject", "stance")

    def fallback(r):
        return not r.get("pick") and not any(r.get(c) for c in CONDS)
    # verbs, from the frames
    for fr in frames:
        lem = which(fr.get("lemma"), "verb")
        if not lem:
            continue
        vid = bsb(fr["ref"])
        if vid not in ok[lem]:
            continue
        note_word(vid, lem, "verb")
        seen_form["verb"].add(vid)
        clw = cwords.get((fr["ref"], NF(fr.get("lemma"))), set())
        ag = {NF(x) for x in fr.get("agent") or []}
        pa = {NF(x) for x in fr.get("patient") or []} | (set() if fr.get("patient") else lamed.get(fr["ref"], set()))
        spk = NF(speaker.get(fr["ref"]) or "")
        if spk and ag & FIRST:
            ag.add(spk)
        if spk and pa & FIRST:
            pa.add(spk)
        for r in rows:
            if r["form"] != "verb" or r.get("pick"):
                continue
            if r.get("agent") and not ag & lemset(r["agent"]):
                continue
            # a command's agent is the one addressed: "fathers ... do not love
            # the world" (1 John 2:15) is not the Father loving
            if fr.get("stance") in (r.get("not_stance") or []):
                continue
            # only these stances: "Commanded" (rule-made hubs, auto_spec.py)
            if r.get("stance") and fr.get("stance") not in r["stance"]:
                continue
            if r.get("not_patient") and pa & lemset(r["not_patient"]):
                continue
            if r.get("patient") and not pa & lemset(r["patient"]):
                continue
            if every and fallback(r):
                continue
            if not fits(r, fr["ref"], clw, vid):
                continue
            if vid not in r["verses"]:
                r["verses"].append(vid)
            placed["verb"].add(vid)
            if not every:
                break
    # nouns and adjectives, from the phrases
    ART = {NF(x) for x in ("ὁ", "הַ", "וְ", "γάρ", "δέ", "οὖν", "μέν")}   # and postpositives:
    # "δικαιοσύνη γὰρ θεοῦ" (Rom 1:17)
    PREP = {NF(x) for x in ("ἐπί", "ἐν", "εἰς", "πρός", "ἐνώπιον", "παρά", "μετά", "ἀπό", "ἐκ", "διά", "κατά", "ὑπέρ",
                            "אֶל", "בְּ", "לְ", "כְּ", "מִן", "עַל", "עִם", "אֵת")}
    for cl in clauses:
        parts = cl.get("parts") or []
        clw = set()
        for part in parts:
            clw |= {NF(x) for x in part.get("lemmas") or []}
        subj = set()                         # the subject's head word
        for part in parts:
            if part["role"] == "s":
                subj |= set([y for y in (NF(x) for x in part.get("lemmas") or []) if y not in ART][:1])
        for part in parts:
            seq = [NF(x) for x in part.get("lemmas") or []]
            lems = set(seq)
            for lem in {k for k in map(which, seq) if k}:
                form = form_of_lemma.get(lem)
                if form not in ("noun", "adjective"):
                    continue
                vid = locate(lem, cl["ref"])
                if vid not in ok[lem]:
                    continue
                note_word(vid, lem, form)
                seen_form[form].add(vid)
                if vid in placed[form] and not every:
                    continue
                # the two words after the concept's, articles aside: "the
                # righteousness of God" as a phrase, not God anywhere in a
                # clause that may hold another (Deut 9:4, 1 John 3:10)
                after = set()
                bare = [y for y in seq if y not in ART]
                span = 2
                for r in rows:
                    if r["form"] == form and isinstance(r.get("adjacent"), int) and r["adjacent"] is not True:
                        span = max(span, r["adjacent"])
                near = {}                        # both sides: "τὴν τοῦ θεοῦ
                for i, x in enumerate(bare):     # δικαιοσύνην" (Rom 10:3)
                    if which(x) == lem:
                        for k, y in enumerate(bare[max(0, i - span):i + span + 1]):
                            dist = abs(max(0, i - span) + k - i)
                            if dist:
                                near[y] = min(near.get(y, 99), dist)
                # true: the very next word either side -- "צִדְקַת יְהוָה", not
                # "oaks of righteousness, the planting of the LORD" (Isa 61:3)
                after = {y for y, dd in near.items() if dd <= 1}
                for r in rows:
                    if r["form"] != form or r.get("pick"):
                        continue
                    if every and fallback(r):
                        continue
                    # "adjacent": true is two words either side; a number
                    # widens it ("faith ... love ... hope", 1 Thess 1:3)
                    adj = r.get("adjacent")
                    win = lems if not adj else after if adj is True else {y for y, dd in near.items() if dd <= adj}
                    if r.get("with") and not win & lemset(r["with"]):
                        continue
                    # "the LORD is righteous": the clause's subject, the word
                    # its predicate (Ps 145:17)
                    # -- not "the eyes of the LORD are on the righteous" (Ps
                    # 34:15): a predicate opening with a preposition says
                    # where, not what
                    if r.get("subject") and not (part["role"] == "p" and subj & lemset(r["subject"])
                                                 and seq and seq[0] not in PREP):
                        continue
                    if not fits(r, cl["ref"], clw, vid):
                        continue
                    if vid not in r["verses"]:
                        r["verses"].append(vid)
                    placed[form].add(vid)
                    if not every:
                        break
    # added by hand, with the reason in the spec ("add"): where the text names
    # its subject in a way no rule here reads -- "Righteous are You, O LORD"
    # (Ps 119:137), the LORD as the subject of a vocative
    for r in rows:
        for vid in r.get("add") or []:
            if vid in seen_form[r["form"]] and vid not in r["verses"]:
                r["verses"].append(vid)
                placed[r["form"]].add(vid)
    if every:                                # what no condition took
        for f in placed:
            fb = next((r for r in rows if r["form"] == f and fallback(r)), None)
            if fb:
                for vid in sorted(seen_form[f] - placed[f]):
                    # the catch-all's own exclusions hold too (several workers,
                    # 2026-10-10: it took them back); such a verse is under More
                    if vid in (fb.get("not_verses") or {}):
                        continue
                    fb["verses"].append(vid)
                    placed[f].add(vid)

    # the Bible's order: the book's place in the canon, then chapter and verse
    # (the holiness worker, 2026-10-10: "Justice and righteousness" read 1 Chr,
    # 1 Kgs, 2 Chr, 2 Sam, Amos, Deut -- live on love and righteousness since
    # they were built; the cause was a later "order" shadowing this one)
    order = {}
    for bb, cc, vv in d["verses"]:
        order[f"{bb}.{cc}.{vv}"] = (S._CANON.get(bb, 99), cc, vv)
    NT = {"Matt", "Mark", "Luke", "John", "Acts"}
    LET = {"Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim", "Titus",
           "Phlm", "Heb", "Jas", "1Pet", "2Pet", "1John", "2John", "3John", "Jude", "Rev"}

    def spread(vs):
        """the verses in the Bible's order, the first examples one from each
        part (the Law, Prophets and Writings; the Gospels and Acts; the
        letters and Revelation) where the row has them"""
        vs = sorted(vs, key=lambda v: order.get(v, (999, 0, 0)))
        heads = []
        for test in (lambda b: b not in NT and b not in LET, lambda b: b in NT, lambda b: b in LET):
            x = next((v for v in vs if test(v.split(".")[0]) and v not in heads), None)
            if x:
                heads.append(x)
        return heads + [v for v in vs if v not in heads]

    # picked verses: their words too -- from every use of the word, not only
    # the concept's sense, since a row may gather the word's other senses on
    # purpose (glory's honor and wealth; grace's thanks), and the tag says
    # only which word is in the verse (the glory and grace panels, 2026-10-10)
    for lem, vs in allocc.items():
        for r in rows:
            for vid in r.get("pick") or []:
                if vid in vs:
                    note_word(vid, lem, r["form"])

    def wd(vid, form):
        return [{"key": k, "lemma": lemma_of[k]} for k in sorted(wordat.get((form, vid), ()))]

    def shown(r):
        """the row's verses in the order shown: its "lead" first (the spec's
        choice of example, where the spread's first would not show the
        label), then the spread"""
        vs = r["verses"] if r.get("pick") else spread(r["verses"])
        lead = [v for v in r.get("lead") or [] if v in r["verses"]]
        return lead + [v for v in vs if v not in lead]

    def text(vid):
        b, c, v = vid.split(".")
        return d["verses"].get((b, int(c), int(v)), "")

    def label(vid):
        b, c, v = vid.split(".")
        return f"{S.TITLE.get(b, b)} {c}:{v}"

    def card(i):
        e = d["ents"].get(i)
        return {"id": i, "name": (e or {}).get("name") or i, "type": (e or {}).get("type"), "missing": e is None}
    # not "order": spread() reads that name when it runs, after this line, and
    # a dict of forms there put every row's verses in insertion order
    form_rank = {"verb": 0, "noun": 1, "adjective": 2}
    lead = spec.get("lead")
    forms = sorted({r["form"] for r in rows}, key=lambda f: (f != lead, form_rank[f]))
    out = {"id": hid, "built": "tools/concepts/hub_build.py", "lead": lead, "words": words,
           "titles": spec.get("titles") or {},
           "by_rule": bool(spec.get("by_rule")),
           "leads": [card(i) for i in spec.get("leads") or []],
           "gather": [card(i) for i in spec.get("gather") or []],
           "own_words": [{"id": v, "ref": label(v), "text": text(v)} for v in spec.get("own_words") or []],
           "forms": []}
    for f in forms:
        fr_rows = [r for r in rows if r["form"] == f]
        more = sorted(seen_form[f] - placed[f], key=lambda v: S._canon_sort(v) if hasattr(S, "_canon_sort") else v)
        out["forms"].append({
            "form": f, "verses": len(seen_form[f] | placed[f]),
            "rows": [{"label": r["label"], "note": r.get("note"), "doors": [card(i) for i in r.get("doors") or []],
                      "n": len(r["verses"]), "verses": shown(r),
                      "eg": [{"id": v, "ref": label(v), "text": text(v), "words": wd(v, f)} for v in shown(r)[:4]]}
                     for r in fr_rows],
            "more": {"n": len(more), "verses": more}})
    # the lead form first, the rest by the text's own weight
    out["forms"].sort(key=lambda f: (f["form"] != lead, -f["verses"]))
    for o in others:
        added = o.pop("lead", [])
        o["verses"] = added + [v for v in spread(o["verses"]) if v not in added]
        o["eg"] = [{"id": v, "ref": label(v), "text": text(v)} for v in o["verses"][:2]]
    out["others"] = {"title": (osp or {}).get("title"), "words": others}
    dest = ROOT / "out" / "concept-hubs"
    dest.mkdir(exist_ok=True)
    (dest / f"{hid}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


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
    for hid in sys.argv[1:]:
        h = build(d, hid, frames, clauses, speaker)
        print(f"== {hid}")
        for w in h["words"]:
            print(f"   word {w['lemma']} {w['form']}: {w['uses']} in this sense, {w['other_sense']} not")
        miss = [c["id"] for c in h["leads"] + h["gather"] + [x for f in h["forms"] for r in f["rows"] for x in r["doors"]] if c["missing"]]
        print(f"   cards missing: {miss}")
        for f in h["forms"]:
            print(f"   {f['form']} ({f['verses']} verses)")
            for r in f["rows"]:
                print(f"     {r['label']:42} {r['n']:4}  {', '.join(e['ref'] for e in r['eg'][:3])}")
            print(f"     {'More':42} {f['more']['n']:4}")


if __name__ == "__main__":
    main()
