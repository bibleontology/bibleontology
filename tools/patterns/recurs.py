"""What the text repeats, for the Patterns section (plan A.8, P-58).

2026-09-30: the Patterns section was judged unsatisfactory for the most part;
the overhaul approved then groups the section by what recurs. This builds the two
groups that need the text itself:

- **The text says it repeats** -- the formulas by which the text declares
  that it echoes an earlier word: "to fulfill what was spoken", "as it is
  written". Each verse with the source the Berean editors' quotation note
  gives, where they give one (out/quotenotes.jsonl.gz).
- **Refrains and formulas** -- lines the Berean repeats word for word, five
  words or more, in at least three chapters: "This is what the LORD says",
  "His loving devotion endures forever", "did evil in the sight of the LORD".
  Mined, not listed by hand: every run of five or more words that recurs is
  kept at its longest, and one that is only a piece of a longer refrain is
  folded into it. Each is then searched across the language divide by the
  same means as the multi-word concepts (tools/phrases/phrase_search.py), so
  a refrain the Berean renders two ways is still one refrain.

    python tools/patterns/recurs.py   -> out/recurs.json
"""
from __future__ import annotations

import collections
import gzip
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "phrases"))
from phrase_search import FROM_MACULA, ORDER, STOP, build, toks, vkey  # noqa: E402

N = 5                 # a refrain is five words or more
MIN_VERSES = 4
MIN_CHAPTERS = 3      # in at least three chapters: a refrain, not one passage's list
GROW = 0.6            # a line grows a word while the longer line keeps this share of
                      # its verses: at 0.7 "evil in the sight of the LORD" stopped
                      # short of "did" (40 of 63)
TOP = 60
# the formulas by which the text says it echoes an earlier word.
# FULFILLED: an earlier word (spoken, written, the Scripture) and "fulfill" in
# one clause, either order. The first list was a set of exact phrasings and
# missed 9 of the verses the 2026-10-02 evaluation named (M-D3: Matt 2:15
# "This fulfilled what the Lord had spoken", Luke 4:21 "Today this Scripture is
# fulfilled", Jas 2:23 ...). Not a wish ("May the LORD fulfill the words you
# have prophesied", Jer 28:6) and not keeping a law ("fulfill the royal law",
# Jas 2:8): both matched the clause test and neither declares a fulfilment.
# 14 verses -> 36, none of the 14 lost.
_WORD = (r"(?:Scriptures?|what (?:was|had been|is|the Lord had|He had) (?:spoken|said|written)|"
         r"the words?(?: written| spoken)?|the writings of the prophets|spoken through the "
         r"prophets?)")
DECLARED = [
    ("fulfilled", "Fulfilment formulas",
     rf"{_WORD}[^.;:]{{0,80}}\bfulfill(?:ed)?\b|(?<!May the LORD )(?<!may )\bfulfill(?:ed)?\b"
     rf"(?![^.;:]{{0,20}}\blaw\b)[^.;:]{{0,40}}{_WORD}|\bthis (?:took place|happened|was) to "
     r"fulfill",
     "The narrator or a speaker says that something happened so that an earlier word "
     "would be fulfilled."),
    ("written", "“As it is written”",
     r"\b(?:as |for |because )?it is written\b|\bas it has been written\b",
     "The text points to an earlier written word as its authority or its pattern."),
]


def main():
    find, text = build()
    bsb = text["BSB"]
    moved = json.loads((OUT / "versemap.json").read_text(encoding="utf-8"))["moved"]

    def _code(eref):
        b, c, n = eref.split(".")
        return f"{FROM_MACULA.get(b, b)}.{c}.{n}"

    # the editors' quotation notes: NT verse -> the OT source they give
    source = collections.defaultdict(list)
    for ln in gzip.open(OUT / "quotenotes.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if "from" in r and r.get("to"):
            b, c, n = r["from"].split(".")
            source[f"{FROM_MACULA.get(b, b)}.{c}.{n}"].append(r["to"])

    def sources(v):
        """the editors' source for v; for a verse that ends on a colon, the
        quotation it introduces is the next verse, and so is the editors' note
        (Matt 2:17 "...was fulfilled:" / 2:18 Jer 31:15) -- five of the first
        fourteen showed no source until this"""
        if source.get(v) or not bsb[v][1].rstrip().endswith(":"):
            return source.get(v, [])
        b, c, n = v.split(".")
        return source.get(f"{b}.{c}.{int(n) + 1}", [])

    declared = []
    for did, title, pat, note in DECLARED:
        rx = re.compile(pat, re.I)
        vs = sorted((v for v, (_t, raw) in bsb.items() if rx.search(raw)), key=vkey)
        declared.append({
            "id": did, "title": title, "note": note, "n": len(vs),
            "books": len({v.split(".")[0] for v in vs}),
            # the editors' notes are ALREADY the Berean's numbering (as
            # event_nodes.py says): book code only, no shift. Shifting them as
            # if they were MACULA's sent John 19:24 to "Psalms 22:17" and
            # John 19:36 to "34:19" (the 2026-10-02 evaluation; 22:18, 34:20)
            "verses": [{"v": v, "to": [_code(x) for x in sources(v)][:3]} for v in vs]})

    # ---- refrains: lines of five or more words the Berean repeats
    where = collections.defaultdict(set)         # 5-word piece -> verses
    for v, (t, _raw) in bsb.items():
        for i in range(len(t) - N + 1):
            where[tuple(t[i:i + N])].add(v)
    frequent = {g: vs for g, vs in where.items() if len(vs) >= MIN_VERSES}

    def verses_of(p):
        """verses carrying phrase p (a tuple of words)"""
        vs = set.intersection(*(where.get(tuple(p[i:i + N]), set())
                                for i in range(len(p) - N + 1)))
        return {v for v in vs if f" {' '.join(p)} " in f" {' '.join(bsb[v][0])} "}

    # EACH REFRAIN AT ITS OWN LENGTH. A frequent five-word piece is grown a
    # word at a time, left or right, while the longer line keeps 70% of its
    # verses: "is what the LORD says" grows to "this is what the LORD says"
    # and stops, where the next word varies. Without it one refrain showed
    # as four ("is what the LORD says", "that this is what the" ...)
    def grow(p, vs):
        while True:
            best = None
            for v in list(vs)[:400]:
                t = bsb[v][0]
                for i in range(len(t) - len(p) + 1):
                    if tuple(t[i:i + len(p)]) == p:
                        if i > 0:
                            best = best or collections.Counter()
                            best[("L", t[i - 1])] += 1
                        if i + len(p) < len(t):
                            best = best or collections.Counter()
                            best[("R", t[i + len(p)])] += 1
            if not best:
                return p, vs
            (side, w), n = best.most_common(1)[0]
            if n < GROW * len(vs):
                return p, vs
            q = (w,) + p if side == "L" else p + (w,)
            qv = verses_of(q)
            if len(qv) < GROW * len(vs):
                return p, vs
            p, vs = q, qv

    # A REFRAIN SAYS SOMETHING. "The house of the LORD" and "of the land of
    # Egypt" recur more than any refrain and are names, not lines; a refrain
    # has a verb in it. Which English words are verbs is read off the
    # original words they render (the lexicon's part of speech, weighted by
    # how often the Berean renders each word that way)
    verbish = collections.Counter()
    nounish = collections.Counter()
    bw = json.loads((OUT / "bsb-words.json").read_text(encoding="utf-8")).get("words", {})
    lexp = ROOT / "data" / "raw" / "stepbible" / "lexicon.json"
    pos = {}
    if lexp.exists():
        for code, v in json.loads(lexp.read_text(encoding="utf-8")).items():
            if isinstance(v, list) and len(v) >= 3:
                pos[code[0].lower() + re.sub(r"^0+", "", code[1:])] = str(v[2])
    for k, rs in bw.items():
        is_v = pos.get(k, "").split(":")[-1].upper().startswith("V")   # "H:V", "G:V"
        for r_, n in rs:
            t = toks(r_)
            if len(t) == 1:
                (verbish if is_v else nounish)[t[0]] += n
    COPULA = {"is", "was", "be", "are", "were", "been", "am"}

    def is_verb(w):
        v, n = verbish[w], nounish[w]
        if v + n == 0:
            # the Berean seldom tags it alone ("says" in "This is what the LORD
            # says", "endures"): read the English form
            return len(w) > 4 and w.endswith(("s", "ed")) and not w.endswith("ss")
        return v >= 0.3 * (v + n)

    # WRONG TURN, KEPT: the verb test read off the lexicon rejected the very
    # refrains it was for -- in "This is what the LORD says" and "declares
    # the LORD" the Berean's "says" and "declares" render נְאֻם, a NOUN
    # ("utterance"), and "endures forever" renders a noun too. What the test
    # was meant to keep out is a NAME: "(of / in / to) the X of the Y". So
    # that shape is what is excluded, and anything else may be a refrain.
    NAME_SHAPE = re.compile(r"^(?:(?:of|in|to|out|from|into|on|by|with|before|for|at)\s)*"
                            r"the\s\w+(?:\s(?:of|to)\s(?:the\s)?\w+)+$")

    # and a refrain SAYS something, so it has a verb -- counting the speech
    # words the Berean uses for the noun נְאֻם as verbs, since as English they
    # are: "The LORD, the God of Israel" and "The Feast of Unleavened Bread"
    # are designations, "His loving devotion endures forever" a refrain
    SPEECH = {"says", "declares", "said", "saying", "lives", "endures", "spoke", "spoken",
              # irregular pasts the English-form fallback cannot see: "And he
              # DID evil in the sight of the LORD"
              "did", "done", "made", "came", "went", "gave", "took", "saw", "knew",
              "heard", "sent", "brought", "put", "set", "fell", "rose", "stood", "sat"}
    # a line cannot end on an auxiliary or a relative word ("The LORD your
    # God will", "Son of Man will", "the LORD your God, who")
    OPEN_END = {"will", "has", "have", "had", "shall", "who", "whom", "not", "may", "can",
                "would", "should", "did", "is", "was", "are", "were", "i", "he", "she",
                "they", "we", "which", "when", "if", "because"}

    def says_something(p):
        return (not NAME_SHAPE.match(" ".join(p)) and p[-1] not in OPEN_END
                and any(w in SPEECH or (w not in COPULA and w not in STOP and is_verb(w))
                        for w in p))

    cands = {}
    for g, vs in sorted(frequent.items(), key=lambda kv: -len(kv[1])):
        p, pv = grow(g, vs)
        if p in cands:
            continue
        chapters = {v.rsplit(".", 1)[0] for v in pv}
        content = [w for w in p if w not in STOP]
        # a line that ends on "the" or "to" is a piece of one, not a refrain
        if (len(pv) >= MIN_VERSES and len(chapters) >= MIN_CHAPTERS and len(content) >= 2
                and p[-1] not in STOP and says_something(p)):
            cands[p] = pv
    # VARIANTS FOLD INTO THE REFRAIN THEY CONTAIN: "Then the LORD said to
    # Moses" and "The LORD said to Moses and Aaron" are the refrain "the LORD
    # said to Moses", listed under it rather than beside it
    keep, variants_of = {}, collections.defaultdict(list)
    for p in sorted(cands, key=len):
        s = f" {' '.join(p)} "
        host = next((q for q in keep if f" {' '.join(q)} " in s), None)
        if host is None:
            keep[p] = set(cands[p])
        else:
            variants_of[host].append(p)
            keep[host] |= cands[p]
    ranked = sorted(keep.items(), key=lambda kv: -(
        len({v.rsplit('.', 1)[0] for v in kv[1]}) * math.log(1 + len(kv[1]))))

    refrains = []
    for p, vs in ranked[:TOP * 2]:
        # NAMED BY ITS COMMONEST FULL FORM: "this is what the LORD" is where
        # the line stops being shared (says / of Hosts says / GOD says); a
        # variant carried by a third of its verses or more names it -- "This
        # is what the LORD says"
        full = max(variants_of.get(p, []), key=lambda q: len(cands[q]), default=None)
        shown = full if full and len(cands[full]) >= len(vs) / 3 else p
        first = min(cands.get(shown, vs), key=vkey)
        raw = bsb[first][1]
        # the refrain in the Berean's own letters and punctuation
        m = re.search(r"\b" + r"\W+".join(re.escape(w) for w in shown) + r"\b",
                      raw.replace("’", "").replace("'", ""), re.I)
        line = m.group(0) if m else " ".join(shown)
        line = line[:1].upper() + line[1:]
        eng, sig, orig = find(list(p))
        allv = set(vs) | set(eng) | set(orig)
        refrains.append({
            "id": "r:" + "_".join(p[:8]), "title": line, "phrase": " ".join(p),
            "n": len(allv), "chapters": len({v.rsplit(".", 1)[0] for v in allv}),
            "books": len({v.split(".")[0] for v in allv}),
            "english": sorted(set(vs) | set(eng), key=vkey),
            "across": sorted(set(orig) - set(vs) - set(eng), key=vkey),
            "signature": {("Hebrew" if k == "h" else "Greek"): [x[1] for x in s]
                          for k, s in sig.items()},
            "example": first,
            "variants": [" ".join(q) for q in variants_of.get(p, [])][:6]})
        if len(refrains) >= TOP:
            break
    (OUT / "recurs.json").write_text(json.dumps(
        {"_note": "What the text repeats (tools/patterns/recurs.py): the formulas by which "
                  "it declares an echo, and the refrains it repeats word for word, each "
                  "searched across the language divide.",
         "declared": declared, "refrains": refrains}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print("declared:", [(x["title"], x["n"], x["books"]) for x in declared])
    print(f"refrains {len(refrains)}")
    for x in refrains[:TOP]:
        print(f"  {x['n']:4} v {x['chapters']:3} ch {x['books']:2} bk  "
              f"+{len(x['across'])} across  {x['title']}")


if __name__ == "__main__":
    main()
