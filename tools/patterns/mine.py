"""A deterministic miner for discrete event patterns — candidates, not findings.

2026-09-28: a deterministic pattern miner that looks at millions of pattern
combos and keeps a filtered list of the best candidates, not only the best
but the most interesting, so that the result can have criteria applied to
it; weighting on the results is wanted but the query capability can come
later. Plan 6.8. Every term of the score is written as its own column, so weights can be
applied later without mining again.

UNITS — every clause with a verb (Hebrew, Aramaic, Greek):
    verb     the exact lemma (V), or its situation type (T: motion, contact …)
    roles    s, o, io, p (a predicate noun), pp (with its preposition); each
             EXACT (a named record from the mentions layer, or the noun's
             lemma), a KIND (record type, noun category, pronoun person), or
             OPEN
    mode     narrated / reported / projected / command / question /
             negated / conditional / other — also an optional part (M)

PATTERNS (three families, all counted in full):
    event     every combination of verb option, role options and mode
    link      a pair of events joined by a clause link, keyed by the link's
              type (then, because, purpose, if, but_rather, as ...), each
              side reduced to core templates, with a SAME-AGENT variant
    chain     three events along the narrative's then-chain
A pattern of kinds, types and records only carries no language, so it can
span the testaments.

THE RANKING (decided 2026-09-20), every term computed from the original:
    slots     structure slots the pattern matches (its parts)
    fixed     parts fixed to a word or a record (exact)
    freq      sqrt(support), support >= 2; an NT instance counts OT_SCALE
              times (the testaments' sizes), and an NT instance that echoes
              an OT instance (ECHO) not at all
    distance  log2(1 + the REACH: the furthest rung any two instances stand
              apart): same chapter 0, same book 1, same family of books 2,
              same testament 3, across 4 ("maybe distance is chapter/
              scroll/scroll family/testament"); the mean over all pairs is
              kept as a column. A pattern across the testaments is weighted
              x sqrt(50) ("A single cross reference from OT to NT is worth
              as much to me than 50 repetitions within a single books")
    interest  mean over fixed parts of inverse clause frequency, x1.5 for a
              named record, x2 for a word the text uses as an image (in a
              simile or copular image at >= 3x its share) — "inversion of
              word frequency with bonuses for words with meaning and proper
              nouns with images being the highest"
    score     slots * fixed * freq * distance * interest
Also written: lift (x chance), books, testaments, modes, examples.

CLASSES held off the main lists: formulas (speech introductions, including
through [communication]; genealogies) and references (a pattern that reaches
the NT only where the NT verse echoes one of its OT verses — the NT
restating the OT, plan 6.8). Patterns matching exactly the same clauses are
one row, the others counted in `variants`.

    python tools/patterns/echoes.py     (first: quotations and parallels)
    python tools/patterns/mine.py       (closeness 0.8, the reader's set)
        -> out/pattern-candidates.jsonl.gz   (every finding, one row each)
        -> out/pattern-index.jsonl.gz        (node -> its best patterns)
        -> out/pattern-instances.jsonl.gz    (instances of served findings)
        -> docs/review/pattern-candidates.html  (the explorer's lists)
"""
import collections
import gzip
import heapq
import itertools
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "builder"))
from source import norm  # noqa: E402

ROLES = ("s", "o", "io", "p", "pp")
SIMILE = {"כ", "ως", "ωσπερ", "ωσει"}
PAST_HE, FUTURE_HE = {"wayyiqtol", "qatal"}, {"weqatal", "yiqtol"}
LINKS = {"then", "sequence", "and", "because", "purpose", "result", "if",
         "contrast", "but_rather", "or", "that", "as", "when_if_though",
         "until_limit", "lest", "therefore", "likewise", "fulfils",
         "elaborates", "describing", "though", "unless", "undecided",
         "failed_result"}
FAMILY = [("Torah", "Gen Exo Lev Num Deu"),
          ("History", "Jos Jdg Rut 1Sa 2Sa 1Ki 2Ki 1Ch 2Ch Ezr Neh Est"),
          ("Wisdom", "Job Psa Pro Ecc Sng"),
          ("Prophets", "Isa Jer Lam Ezk Dan"),
          ("Twelve", "Hos Jol Amo Oba Jon Mic Nam Hab Zep Hag Zec Mal"),
          ("Gospels", "Mat Mrk Luk Jhn"), ("Acts", "Act"),
          ("Paul", "Rom 1Co 2Co Gal Eph Php Col 1Th 2Th 1Ti 2Ti Tit Phm"),
          ("General", "Heb Jas 1Pe 2Pe 1Jn 2Jn 3Jn Jud"), ("Revelation", "Rev")]
FAM = {b: i for i, (_, bs) in enumerate(FAMILY) for b in bs.split()}
NTFAM = 5
# SIMILAR WORDS SHARE A KEY (2026-09-28: this is where the word graph
# should allow similar words to match; a 90-minute budget to experiment with
# the closeness ranges to see at what thresholds patterns emerge). Set by tools/patterns/sweep.py: words whose word-space
# closeness (the word graph's `all` and `cross` neighbours) is >= SIM_T are
# joined into one class, and verbs, objects and predicates get that class
# as one more option (S). SIM_T None: no similarity.
SIM_T = None
SIM = {}
SIM_LABEL = {}
OUT_TAG = ""
GENEALOGY = {"ילד", "γενναω"}
# "X said" with nothing else fixed is the speech formula, not an event
# pattern ("Jesus said", 342): a class of its own, off the main lists
SPEECH = {"אמר", "דבר", "ענה", "λεγω", "λαλεω", "αποκρινομαι", "φημι"}
CROSS_W = math.sqrt(50)
GEN_CLASSES, SPEECH_CLASSES, VERB_TYPE = set(), set(), {}
OT_SCALE = 68074 / 24900          # Hebrew / Greek clauses with a verb
# A REFERENCE IS NOT A REPEAT (plan 6.8; 2026-09-28, of Rom 4:3 beside
# Gen 15:6, a great match). An NT instance whose verse echoes a verse that
# holds an OT instance of the same pattern (tools/patterns/echoes.py) is the
# NT restating the OT, not the pattern recurring: it is not counted as an
# independent occurrence, and a pattern that recurs only that way is classed
# "reference" — written out for the reader, kept off the explorer's lists.
ECHO = {}                         # NT verse -> OT verses it echoes
# ONE ACCOUNT, ONE OCCURRENCE (2026-09-28: quotations and parallel
# accounts are important in their own right and handy to have in the
# reader, but not as interesting for the explorer). Verses in a parallel
# run (echoes.py: Chronicles and Kings, one gospel and another) are one
# account; within one pattern, NT instances restating the same OT verse are
# one account (Rom 9:7 and Heb 11:18, both Gen 21:12). The pattern's
# support counts accounts, not tellings. NOT one account: two verses that
# merely share rare words — that is a repeated phrase, the thing sought
# (2026-09-28: treating them as one sent references 533 -> 4,306).
ACCOUNT = {}                      # verse -> the account it belongs to


def speechy(p):
    """A verb part that is a saying: the lemma, its similar-word class, or
    the situation type the lemma belongs to."""
    return (p[0] in ("V", "X") and p[2] in SPEECH) or \
        (p[0] == "S" and p[1] == "v" and p[2] in SPEECH_CLASSES) or \
        (p[0] == "T" and p[1] == "communication")


def reach_level(chapters):
    """The furthest rung of the distance ladder any two instances stand apart:
    across the testaments 4, same testament 3, same family 2, same book 1,
    same chapter 0."""
    bks = {c.split(".")[0] for c in chapters}
    fams = {FAM.get(b, 99) for b in bks}
    if min(fams) < NTFAM <= max(fams):
        return 4
    if len(fams) > 1:
        return 3
    if len(bks) > 1:
        return 2
    return 1 if len(set(chapters)) > 1 else 0
greek_gloss = {}
KEEP_HTML = 6000
# A FIRST PATTERN ONTOLOGY (2026-09-28: a simple pattern ontology is needed
# to know what kinds of patterns to look for). Every
# candidate is classed; the classes are what the relations and verbs the
# text marks already say, and the ontology grows from what the results show.
LINK_KIND = {"then": "sequence", "sequence": "sequence", "and": "sequence",
             "because": "cause", "therefore": "cause", "result": "cause",
             "failed_result": "cause", "purpose": "purpose", "lest": "purpose",
             "if": "condition", "unless": "condition",
             "when_if_though": "condition", "undecided": "condition",
             "contrast": "contrast", "but_rather": "contrast",
             "though": "contrast", "as": "comparison",
             "likewise": "comparison", "fulfils": "fulfilment",
             "that": "content", "elaborates": "elaboration",
             "describing": "elaboration", "until_limit": "limit",
             "or": "alternative"}


def rows(p):
    for line in gzip.open(p, "rt", encoding="utf-8"):
        yield json.loads(line)


# ---------------------------------------------------------------- loading
def _strong_key(s):
    """Extended Strong's as an identity: zeros dropped, the letter kept
    (3820 "heart" is not 3820b "entrance")."""
    import re
    m = re.match(r"^[hg]?0*(\d+)([a-z]?)", (s or "").strip().lower())
    return (m.group(1) + m.group(2)) if m else ""


def label_of(label, lang, lem, strong=None):
    """A word's English label: by the word itself (its Strong's number) where
    known, its consonants otherwise -- see the gloss table in load()."""
    sk = _strong_key(strong)
    return label.get((lang, lem, sk)) or label.get((lang, lem), lem) if sk \
        else label.get((lang, lem), lem)


def bridge_of(bridge, lang, lem, strong):
    """A word's Septuagint key: by lexeme first, consonants as fallback."""
    if lang == "greek":
        return lem
    sk = _strong_key(strong)
    return bridge.get(("H", sk)) if sk and ("H", sk) in bridge \
        else bridge.get((lang, lem))


def load():
    t0 = time.time()
    nodes, gloss = {}, collections.defaultdict(collections.Counter)
    for n in rows(OUT / "structure-nodes.jsonl.gz"):
        if n.get("clause") or n.get("word") or n.get("implicit"):
            nodes[n["id"]] = n
            if n.get("word") and n.get("lemma"):
                g = (n.get("text") or "").split(" ")[-1].strip(".")
                gloss[(n["lang"], norm(n["lemma"]))][g] += 1
                # AND BY THE WORD ITSELF: consonants alone join homographs,
                # and the commoner labelled both -- עוּר "stir up" read
                # "skin" (עוֹר), Aramaic אֲתָה "come" read "you" (the 2026-10-02
                # evaluation, C-D12 / M-D6). Looked up first where a word's
                # Strong's number is known (label_of)
                sk = _strong_key(n.get("strong"))
                if sk:
                    gloss[(n["lang"], norm(n["lemma"]), sk)][g] += 1
    roles = collections.defaultdict(dict)
    neg, part, cond, links = set(), set(), set(), []
    simile_lemma = collections.Counter()
    for e in rows(OUT / "structure-edges.jsonl.gz"):
        t = e["type"]
        if e.get("clause_role") and "#ct" in e["src"]:
            if t in ROLES and t not in roles[e["src"]]:
                roles[e["src"]][t] = (e["dst"], norm(e.get("prep") or ""))
            if t == "neg":
                neg.add(e["src"].replace("#ct", "#cl"))
            if t == "pp" and norm(e.get("prep") or "") in SIMILE:
                w = nodes.get(e["dst"]) or {}
                simile_lemma[(w.get("lang"), norm(w.get("lemma") or ""))] += 1
        elif t == "part" and "#turn" in e["src"]:
            part.add(e["dst"])
        elif t in ("condition", "consequence"):
            cond.add(e["dst"])
        if e.get("clause_link") and t in LINKS and "#cl" in e["src"] and \
                "#cl" in (e.get("dst") or ""):
            links.append((e["src"], e["dst"], t))
    mention = {m["occurrence"]: m["record"]
               for m in rows(OUT / "mentions.jsonl.gz")}
    ents = {}
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl",
                     encoding="utf-8"):
        e = json.loads(line)
        ents[e["id"]] = (e["name"], e["type"])
    cat = {}
    for r in rows(OUT / "meaning-categories.jsonl.gz"):
        if r.get("verdict") in ("decided", "leaning"):
            cat[(r["lang"], r["lemma"])] = r["class"]
    # copular images (tools/meaning/figures.py): the predicate's lemma
    for r in rows(OUT / "meaning-figures.jsonl.gz"):
        if r.get("verdict") == "image":
            dst = (roles.get(r["ct"]) or {}).get("p")
            if dst:
                w = nodes.get(dst[0]) or {}
                simile_lemma[(w.get("lang"), norm(w.get("lemma") or ""))] += 1
    label = {k: c.most_common(1)[0][0] for k, c in gloss.items()}
    for k, g in label.items():
        if k[0] == "greek" and len(k) == 2:
            greek_gloss[k[1]] = g
    # THE SEPTUAGINT BRIDGE (2026-09-28: the cross-testament patterns were
    # not particularly interesting): Hebrew and Greek lemmas never
    # match, so only names and kinds could span the testaments. A Hebrew
    # word keyed by the Greek the Septuagint renders it with (the word
    # graph's layer) meets the NT's own word: עָלָה and ἀναβαίνω, one key.
    sys.path.insert(0, str(ROOT / "tools" / "meaning"))
    import categorize as CZ
    lex, lxx = CZ.lexemes()
    bridge = {}
    for lid, g in lxx.items():
        x = lex.get(lid)
        if x:
            bridge[("hebrew", norm(x["lemma"]))] = norm(g)
            # BY LEXEME as well (lex:H:5341:נצר): keyed by consonants alone
            # נָצַר "guard" and נֵצֶר "branch" were one key, and Prov 4:23's
            # "guard" read as "dead" (2026-09-28)
            parts = lid.split(":")
            if len(parts) >= 3 and parts[1] in ("H", "A"):
                sk = _strong_key(parts[2])
                if sk:
                    bridge[("H", sk)] = norm(g)
    print(f"Septuagint bridge: {len(bridge):,} keys", flush=True)
    print(f"loaded in {time.time() - t0:.0f}s", flush=True)
    return (nodes, roles, neg, part, cond, links, mention, ents, cat, label,
            simile_lemma, bridge)


def mode_of(c, cid, neg, part, cond, nodes):
    f, lang, mood, tense = (c.get("upper_force"), c.get("lang"),
                            c.get("verb_mood"), c.get("verb_tense"))
    if f == "directive":
        return "command"
    if f == "question":
        return "question"
    if cid in neg:
        return "negated"
    if cid in cond:
        return "conditional"
    if (lang == "hebrew" and mood in FUTURE_HE) or tense == "future":
        return "projected"
    if (lang == "hebrew" and mood in PAST_HE) or (
            lang == "greek" and mood == "indicative" and
            tense in ("aorist", "imperfect", "pluperfect")):
        x, seen = cid, 0
        while x and seen < 8:
            if x in part:
                return "reported"
            x, seen = (nodes.get(x) or {}).get("nested_in"), seen + 1
        return "narrated"
    return "other"


def role_options(r, dst, prep, lang, nodes, mention, ents, cat):
    w = nodes.get(dst) or {}
    name = f"pp:{prep}" if r == "pp" and prep else r
    rec = mention.get(dst)
    if rec:
        return (("R", name, rec), ("K", name, (ents.get(rec) or ("", "?"))[1]))
    if w.get("implicit") or w.get("class") in ("pron", "art", "det"):
        return (None, ("P", name, f"{w.get('person') or '?'}-"
                                  f"{w.get('number') or '?'}"))
    lem = norm(w.get("lemma") or "")
    c = cat.get((lang, lem))
    kind = ("C", name, c.split(".")[1]) if c and c.startswith("noun.") \
        else None
    return (("L", name, lang, lem) if lem else None, kind)


# ---------------------------------------------------------------- mining
class Miner:
    """Two passes over the same generator: count, then keep chapter lists
    and examples only for patterns that occur at least twice."""

    def __init__(self, events, links, chapter_of):
        self.events, self.links, self.chapter_of = events, links, chapter_of

    def event_patterns(self, cid):
        vopts, ropts, mode, _agent = self.events[cid]
        for v in vopts:
            for combo in itertools.product(*ropts) if ropts else [()]:
                parts = tuple(sorted(o for o in combo if o))
                if not parts:
                    continue
                # "Moses speaks" is a profile, not an event pattern: the
                # verb, or something other than the subject, must be fixed
                if v[0] not in ("V", "X", "S") and not any(
                        p[0] in ("R", "L", "X", "S") and p[1] != "s"
                        for p in parts):
                    continue
                yield ("E", v) + parts
                yield ("E", v, ("M", mode)) + parts

    def core(self, cid):
        vopts, ropts, _, _agent = self.events[cid]
        out = set()
        for v in vopts:
            out.add((v,))
            for ro in ropts:
                for o in ro:
                    if o and o[1] in ("s", "o"):
                        out.add((v, o))
        return out

    def link_patterns(self):
        for a, b, t in self.links:
            if a in self.events and b in self.events:
                same = self.events[a][3] and \
                    self.events[a][3] == self.events[b][3]
                for x in self.core(a):
                    for y in self.core(b):
                        yield a, ("L", t, x, y)
                        if same:
                            yield a, ("L", t + "+same agent", x, y)

    def chain_patterns(self):
        nxt = collections.defaultdict(list)
        for a, b, t in self.links:
            if t in ("then", "sequence") and a in self.events and \
                    b in self.events:
                nxt[a].append(b)
        for a, bs in nxt.items():
            for b in bs:
                for c in nxt.get(b, []):
                    ca, cb, cc = self.core(a), self.core(b), self.core(c)
                    # the verb-only and verb+agent-kind cores keep the
                    # product bounded
                    ca = {x for x in ca if len(x) == 1 or x[1][0] == "K"
                          or x[1][0] == "C"}
                    cb = {x for x in cb if len(x) == 1 or x[1][0] in "KC"}
                    cc = {x for x in cc if len(x) == 1 or x[1][0] in "KC"}
                    for x in ca:
                        for y in cb:
                            for z in cc:
                                yield a, ("C", x, y, z)

    def all(self):
        for cid in self.events:
            for k in self.event_patterns(cid):
                yield cid, k
        yield from self.link_patterns()
        yield from self.chain_patterns()


def examples(cids):
    """Four examples from distinct books, both testaments where the pattern
    has both, in canon order (the clause file is not in canon order, so the
    first found were 1 Chronicles' again and again)."""
    nt = [c for c in cids if FAM.get(c.split(".")[0], 0) >= NTFAM]
    ot = [c for c in cids if c not in nt]
    pick = ot[:2] + nt[:2]
    pick += [c for c in cids if c not in pick][:4 - len(pick)]
    return sorted(pick, key=lambda c: (BOOK_ORDER.get(c.split(".")[0], 99),
                                       c))


BOOK_ORDER = {b: i for i, b in enumerate(
    b for _, bs in FAMILY for b in bs.split())}


def distance(chapters):
    """Mean of the distance ladder over all pairs of instances, by counting."""
    n = len(chapters)
    if n < 2:
        return 0.0
    ch = collections.Counter(chapters)
    bk = collections.Counter(c.split(".")[0] for c in chapters)
    fm = collections.Counter(FAM.get(c.split(".")[0], 99) for c in chapters)
    ts = collections.Counter(FAM.get(c.split(".")[0], 0) >= NTFAM
                             for c in chapters)
    pairs = lambda c: sum(k * (k - 1) // 2 for k in c.values())  # noqa: E731
    tot = n * (n - 1) // 2
    p_ch, p_bk, p_fm, p_ts = pairs(ch), pairs(bk), pairs(fm), pairs(ts)
    s = 0 * p_ch + 1 * (p_bk - p_ch) + 2 * (p_fm - p_bk) + \
        3 * (p_ts - p_fm) + 4 * (tot - p_ts)
    return s / tot


def verb_strongs(nodes):
    """clause id -> the Strong's number of its verb word."""
    words = collections.defaultdict(list)
    for nid, n in nodes.items():
        if n.get("word"):
            words[nid.split("#")[0]].append(n)
    out = {}
    for cid, c in nodes.items():
        if c.get("clause") and c.get("verb_lemma"):
            for w in words[cid.split("#")[0]]:
                if w.get("verb") and w.get("lemma") == c["verb_lemma"] and \
                        set(w.get("w") or ()) <= set(c.get("w") or ()):
                    out[cid] = w.get("strong")
                    break
    return out


def main():
    t0 = time.time()
    (nodes, roles, neg, part, cond, links, mention, ents, cat, label,
     simile_lemma, bridge) = load()
    vstrong = verb_strongs(nodes)
    events, chapter_of = {}, {}
    for cid, c in nodes.items():
        if not c.get("clause") or not c.get("verb_lemma"):
            continue
        lang = c["lang"]
        lem = norm(c["verb_lemma"])
        vopts = [("V", lang, lem)]
        xb = bridge_of(bridge, lang, lem, vstrong.get(cid))
        if xb:
            vopts.append(("X", "v", xb))
        if (lang, lem) in SIM:
            vopts.append(("S", "v", SIM[(lang, lem)]))
        st = cat.get((lang, lem))
        if st and st.startswith("verb."):
            vopts.append(("T", st.split(".")[1]))
        ropts, agent = [], None
        rs = roles.get(cid.replace("#cl", "#ct"), {})
        for r in ROLES:
            if r in rs:
                dst, prep = rs[r]
                ex, kd = role_options(r, dst, prep, lang, nodes, mention,
                                      ents, cat)
                opts = [o for o in (ex, kd) if o]
                if ex and ex[0] == "L":
                    xb = bridge_of(bridge, lang, ex[3],
                                   (nodes.get(dst) or {}).get("strong"))
                    if xb:
                        opts.append(("X", ex[1], xb))
                    if ex[1] in ("o", "p") and (lang, ex[3]) in SIM:
                        opts.append(("S", ex[1], SIM[(lang, ex[3])]))
                ropts.append(opts + [None])
                if r == "s":
                    agent = mention.get(dst)
        events[cid] = (vopts, ropts, mode_of(c, cid, neg, part, cond, nodes),
                       agent)
        chapter_of[cid] = cid.rsplit(".", 1)[0]
    # the similar-word classes that hold a genealogy or a speech verb are
    # formulas too ("~{begat/fathered}" got back in through them)
    GEN_CLASSES.clear()
    SPEECH_CLASSES.clear()
    for (lg, lm), c in SIM.items():
        if lm in GENEALOGY:
            GEN_CLASSES.add(c)
        if lm in SPEECH:
            SPEECH_CLASSES.add(c)
    # a verb option's situation type, for naming a pattern's kind
    for cid, (vopts, _r, _m, _a) in events.items():
        ts = [o[1] for o in vopts if o[0] == "T"]
        for o in vopts:
            if o[0] != "T" and ts:
                VERB_TYPE.setdefault(o, ts[0])
    N = len(events)
    print(f"{N:,} clauses with a verb; {len(links):,} clause links",
          flush=True)
    m = Miner(events, links, chapter_of)

    # ---- pass 1: support and part counts
    count, part_count = collections.Counter(), collections.Counter()
    for cid, (vopts, ropts, mode, _) in events.items():
        for v in vopts:
            part_count[v] += 1
        part_count[("M", mode)] += 1
        for ro in ropts:
            for o in ro:
                if o:
                    part_count[o] += 1
    for _, k in m.all():
        count[k] += 1
    print(f"pass 1: {len(count):,} distinct patterns from "
          f"{sum(count.values()):,} matches ({time.time() - t0:.0f}s)",
          flush=True)
    keep = {k for k, n in count.items() if n >= 2}

    # ---- pass 2: verses and examples for patterns seen twice or more; and
    # a signature of the clauses matched, so two patterns that match exactly
    # the same clauses are known to be one finding said two ways
    verse_of = {cid: cid.split("#")[0] for cid in events}
    vss = collections.defaultdict(list)
    sig = collections.Counter()
    ex = collections.defaultdict(list)
    modes = collections.defaultdict(collections.Counter)
    for cid, k in m.all():
        if k in keep:
            vss[k].append(verse_of[cid])
            sig[k] = (sig[k] + hash(cid)) & 0xFFFFFFFFFFFFFFFF
            # up to 8 candidates from distinct books; examples() picks 4
            if len(ex[k]) < 8 and all(
                    x.split(".")[0] != cid.split(".")[0] for x in ex[k]):
                ex[k].append(cid)
            modes[k][events[cid][2]] += 1
    ECHO.clear()
    ACCOUNT.clear()
    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    def join(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)
    try:
        for r in rows(OUT / "echoes.jsonl.gz"):
            if r["kind"] == "NT->OT":
                ECHO.setdefault(r["from"], set()).add(r["to"])
            elif r["kind"] == "parallel":
                join(r["from"], r["to"])
        for v in list(parent):
            ACCOUNT[v] = find(v)
        print(f"{len(ACCOUNT):,} verses in shared accounts", flush=True)
    except OSError:
        print("no out/echoes.jsonl.gz: references not separated", flush=True)
    print(f"pass 2: {len(keep):,} patterns kept ({time.time() - t0:.0f}s)",
          flush=True)

    # ---- interest: inverse clause frequency, with the decided bonuses
    vehicle_total = sum(simile_lemma.values()) or 1
    lemma_total = collections.Counter()
    for c in nodes.values():
        if c.get("word") and c.get("lemma"):
            lemma_total[(c["lang"], norm(c["lemma"]))] += 1
    all_words = sum(lemma_total.values())
    image = {k for k, v in simile_lemma.items()
             if v >= 3 and v / vehicle_total >= 3 * lemma_total[k] / all_words}

    def interest(p):
        idf = math.log(N / max(1, part_count[p]))
        if p[0] == "R":
            return idf * 1.5
        if p[0] in ("X", "S"):
            return idf
        if p[0] in ("V", "L"):
            key = (p[1], p[2]) if p[0] == "V" else (p[2], p[3])
            return idf * (2.0 if key in image else 1.0)
        return None

    def parts_of(k):
        if k[0] == "E":
            return [p for p in k[1:] if p[0] != "M"]
        if k[0] == "L":
            return list(k[2]) + list(k[3])
        return list(k[1]) + list(k[2]) + list(k[3])

    out = []
    for k in keep:
        n = count[k]
        vs = vss[k]
        chs_k = [v.rsplit(".", 1)[0] for v in vs]
        d = distance(chs_k)
        if d <= 0:
            continue
        ps = parts_of(k)
        fixed = [p for p in ps if p[0] in ("V", "R", "L", "X", "S")]
        ints = [interest(p) for p in fixed]
        it = sum(ints) / len(ints) if ints else 0.0
        slots = len(ps)
        lift = n * N ** (len(ps) - 1) / math.prod(
            max(1, part_count[p]) for p in ps) if k[0] == "E" else None
        bks = sorted({v.split(".")[0] for v in vs})
        is_nt = lambda v: FAM.get(v.split(".")[0], 0) >= NTFAM  # noqa: E731
        nt_vs = [v for v in vs if is_nt(v)]
        n_nt = len(nt_vs)
        ot_vs = set(vs) - set(nt_vs)
        n_echo = sum(1 for v in nt_vs if ECHO.get(v, set()) & ot_vs)
        # ACCOUNTS: an NT instance restating an OT instance is dropped, and
        # the tellings of one account (a parallel run; NT verses restating
        # one OT verse) count once. Everything below is over accounts.
        indep, seen_acc, sources = [], set(), set()
        for v in vs:
            src = ECHO.get(v, set()) if is_nt(v) else set()
            if src & ot_vs or src & sources:
                continue
            sources |= src
            a = ACCOUNT.get(v)
            if a is not None:
                if a in seen_acc:
                    continue
                seen_acc.add(a)
            indep.append(v)
        n_acc = len(indep)
        reference = n_acc < 2
        basis = vs if reference else indep
        fams = {FAM.get(v.split(".")[0], 99) for v in basis}
        # FREQUENCY PER TESTAMENT: the OT has OT_SCALE times the NT's
        # clauses, so an NT occurrence counts OT_SCALE times; otherwise the
        # smaller testament is outvoted by size alone (2026-09-28: the best
        # NT-only pattern ranked 283rd).
        n_nt_acc = sum(1 for v in basis if is_nt(v))
        n_eff = (len(basis) - n_nt_acc) + n_nt_acc * OT_SCALE
        # REACH, NOT THE AVERAGE: 2026-09-28 — a single cross reference
        # from OT to NT is worth as much as 50 repetitions within a single
        # book. The mean ladder distance (kept as a column)
        # lets 50 same-book pairs drown one crossing; the score uses the
        # furthest level the pattern reaches, and a crossing is weighted
        # CROSS_W = sqrt(50), that equivalence on the sqrt-frequency scale.
        cross = min(fams) < NTFAM <= max(fams)
        reach = reach_level([v.rsplit(".", 1)[0] for v in basis])
        cross_w = CROSS_W if cross else 1.0
        score = slots * len(fixed) * math.sqrt(n_eff) * \
            math.log2(1 + reach) * it * cross_w
        allp = [p for p in ps]
        verbs = {p[2] for p in allp if p[0] in ("V", "X")}
        classes = {p[2] for p in allp if p[0] == "S" and p[1] == "v"}
        vparts = [p for p in allp if p[0] in ("V", "T") or
                  (p[0] in ("X", "S") and p[1] == "v")]
        # nothing fixed but who speaks, and to whom ("said to Jesus", 37)
        bare = not any(p[0] in ("R", "L", "X", "S") and
                       p[1] not in ("s", "v", "io") for p in allp)
        if verbs & GENEALOGY or classes & GEN_CLASSES:
            kind = "formula: genealogy"
        elif bare and ((verbs & SPEECH or classes & SPEECH_CLASSES) or (
                vparts and all(speechy(p) for p in vparts))):
            # also "Jesus [communication] then Jesus [communication]": the
            # speech formula arriving through the situation type
            kind = "formula: speech"
        elif reference:
            # recurs only as quotation or retelling: for the reader, not
            # the explorer
            kind = "reference: quotation or parallel account"
        elif k[0] == "E":
            ts = [p[1] for p in k[1:] if p[0] == "T"]
            kind = "event: " + (ts[0] if ts else VERB_TYPE.get(
                next((p for p in k[1:] if p[0] in ("V", "X", "S")
                      and p[1] in ("v",) or p[0] == "V"), None), "action"))
        elif k[0] == "L":
            kind = "link: " + LINK_KIND.get(k[1].split("+")[0], "other")
        else:
            kind = "chain: narrative sequence"
        out.append({
            "family": {"E": "event", "L": "link", "C": "chain"}[k[0]],
            "kind": kind,
            "pattern": text_of(k, ents, label),
            "score": round(score, 2), "slots": slots, "fixed": len(fixed),
            "support": n, "support_nt": n_nt, "nt_echoes": n_echo,
            "accounts": n_acc,
            "_sig": (k[0], n, sig[k]), "_k": k,
            "freq": round(math.sqrt(n_eff), 2),
            "distance": round(d, 2), "reach": reach,
            "cross_weight": cross_w, "interest": round(it, 2),
            "lift": round(lift, 1) if lift else None,
            "books": len(bks), "book_list": bks[:14],
            "testaments": "OT+NT" if min(fams) < NTFAM <= max(fams)
            else "NT" if min(fams) >= NTFAM else "OT",
            "images": sum(1 for p in fixed if (
                (p[1], p[2]) if p[0] == "V" else
                (p[2], p[3]) if p[0] == "L" else None) in image),
            "modes": dict(modes[k].most_common(4)),
            "examples": [{"ref": c.split("#")[0],
                          "text": nodes[c].get("text", "")[:110]}
                         for c in examples(ex[k])]})
    out.sort(key=lambda r: -r["score"])
    # ONE FINDING, ONE ROW: patterns of one family that match exactly the
    # same clauses (the exact verb, its bridged form, its similar-word class,
    # with and without the mode) are one finding; the best-scoring wording
    # is kept and the others counted as its variants
    best, dup = {}, 0
    for r in out:
        s = r.pop("_sig")
        if s in best:
            best[s]["variants"] += 1
            dup += 1
        else:
            r["variants"] = 0
            best[s] = r
    out = [r for r in out if "variants" in r]
    print(f"{dup:,} variants folded into {len(out):,} findings", flush=True)
    keys = {}
    for i, r in enumerate(out):
        r["id"] = f"p{i}"
        keys[r["id"]] = r.pop("_k")
    with gzip.open(OUT / f"pattern-candidates{OUT_TAG}.jsonl.gz", "wt",
                   encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    senses = collections.defaultdict(set)
    for n in nodes.values():
        if n.get("word") and n.get("lemma") and n.get("strong"):
            digits = "".join(ch for ch in n["strong"] if ch.isdigit())
            if digits:
                senses[(n["lang"], norm(n["lemma"]))].add(
                    ("g" if n["lang"] == "greek" else "h") + str(int(digits)))
    served = node_index(out, keys, vss, parts_of, senses)
    instances(out, keys, served, m, events, nodes, roles)
    # the page (the explorer): repeats only — quotations and retellings go
    # to the reader (2026-09-28) — by score in each family, the
    # formulas apart, and the top by lift
    repeat = [r for r in out
              if not r["kind"].startswith(("formula", "reference"))]
    top = []
    for fam, n in (("event", 3000), ("link", 1500), ("chain", 700)):
        top += [r for r in repeat if r["family"] == fam][:n]
    top += [r for r in out if r["kind"].startswith("formula")][:200]
    seen = {id(r) for r in top}
    top += [r for r in sorted((r for r in repeat if r["lift"]),
                              key=lambda r: -r["lift"])
            if r["accounts"] >= 4 and id(r) not in seen][:800]
    html = (ROOT / "tools" / "patterns" / "viewer.html").read_text(
        encoding="utf-8").replace("/*DATA*/[]",
                                  json.dumps(top, ensure_ascii=False))
    (ROOT / "docs" / "review" / f"pattern-candidates{OUT_TAG}.html").write_text(
        html, encoding="utf-8")
    print(f"{len(out):,} candidates written; {len(top):,} on the page; "
          f"{len(image)} image words; done in {time.time() - t0:.0f}s")


INDEX_TOP = 12
NODE_INTEREST = 4.5       # 25th percentile of findings' mean interest
NODE_FIXED = 2            # meaningful fixed parts a node's pattern needs
NODE_REPEAT = 1           # a pattern must fix a word none above it fixes


def node_index(out, keys, vss, parts_of, senses):
    """Every node's most interesting patterns (2026-09-28: patterns show up
    in the search results or specifically in the node descriptions: what are
    the most interesting patterns a node participates in?). A node takes part in a pattern through
    a part that names it — a record (R), a word (V, L; X is the Greek the
    Septuagint gives it; S its similar-word class, so every member) — or
    through a verse that is one of its instances. Repeats only; formulas
    and references are not a node's patterns. Best INDEX_TOP by score.

    -> out/pattern-index{OUT_TAG}.jsonl.gz: {"node", "patterns": [{id,
       score, via}]}; node is record:<id>, word:<lang>:<lemma> (and the
       same as sense:<h539|g4100>, the reader's key), verse:<ref>
    """
    members = collections.defaultdict(list)
    for (lg, lm), c in SIM.items():
        members[c].append(f"word:{lg}:{lm}")
    idx = collections.defaultdict(list)
    cap = 3 * INDEX_TOP          # a bounded heap per node; deduped below

    def add(node, item):
        h = idx[node]
        if len(h) < cap:
            heapq.heappush(h, item)
        elif item > h[0]:
            heapq.heapreplace(h, item)
    for r in out:
        if r["kind"].startswith(("formula", "reference")):
            continue
        k = keys[r["id"]]
        # A NODE'S PATTERN MUST SAY SOMETHING: at least one fixed word, and
        # a mean interest of NODE_INTEREST — "be/become" is 3.1, below the
        # 10th percentile (3.3); believe 5.7, stumble 6.5 (2026-09-28)
        # and it must fix WHAT IS ACTED ON (an object, predicate or phrase),
        # or two things. On Prov 4:13's list ("[you] · weak · <command>" — a
        # verb, a pronoun and a mood), no good matches, and the noise hurts
        # credibility; on Prov 4:23's "[you] · [a verb of state] · heart"
        # (Ps 119:36 "turn my heart", Prov 2:2 "direct your heart"), 3 out
        # of 4 were good matches (2026-09-28). Two fixed parts alone would drop the second.
        acted_on = any(p[0] in ("R", "L", "X", "S") and p[1] not in ("s", "v")
                       for p in parts_of(k))
        if not (acted_on or r["fixed"] >= NODE_FIXED) or \
                r["interest"] < NODE_INTEREST:
            continue
        # FOR A NODE, INTEREST, NOT FREQUENCY: the list score carries
        # sqrt(frequency), so "[he] · be" (1,033 accounts) led Isa 8:14's
        # patterns over "[state] -> stumble -> fall" (2026-09-28). Divided
        # out, what is left ranks a pattern by its structure, rarity and
        # reach — what it says about this node, not how common it is.
        r_node = r["score"] / math.sqrt(max(r["accounts"], 1))
        named = set()
        for p in parts_of(k):
            if p[0] == "R":
                named.add((f"record:{p[2]}", "names it"))
            elif p[0] == "V":
                named.add((f"word:{p[1]}:{p[2]}", "its word"))
            elif p[0] == "L":
                named.add((f"word:{p[2]}:{p[3]}", "its word"))
            elif p[0] == "X":
                named.add((f"word:greek:{p[2]}", "its word (Septuagint)"))
            elif p[0] == "S":
                for w in members.get(p[2], ()):
                    named.add((w, "a similar word"))
        for node, via in named:
            add(node, (r_node, r["id"], via))
            # the reader keys a word by its Strong's number (h539, g4100)
            if node.startswith("word:"):
                _, lg, lm = node.split(":", 2)
                for sk in senses.get((lg, lm), ()):
                    add(f"sense:{sk}", (r_node, r["id"], via))
        for v in set(vss[k]):
            add(f"verse:{v}", (r_node, r["id"], "an instance"))
    verses_of = {r["id"]: set(vss[keys[r["id"]]]) for r in out
                 if not r["kind"].startswith(("formula", "reference"))}
    fixed_of = {pid: {(p[0],) + tuple(p[2:]) for p in parts_of(keys[pid])
                      if p[0] in ("V", "R", "L", "X", "S")}
                for pid in verses_of}
    n, served = 0, set()
    with gzip.open(OUT / f"pattern-index{OUT_TAG}.jsonl.gz", "wt",
                   encoding="utf-8") as f:
        for node, ps in idx.items():
            best, used = {}, collections.Counter()
            for s, pid, via in sorted(ps, reverse=True):
                # one finding once: a narrower pattern whose verses all fall
                # inside one already listed is the same finding again ("they
                # stoned with stones" under "stoned with stones")
                if pid in best or any(verses_of[pid] <= verses_of[b]
                                      for b in best):
                    continue
                # and variety: skip a pattern whose every fixed word is
                # already in one listed above (a word's six stoning shapes)
                fx = fixed_of[pid]
                if fx and all(used[f] >= NODE_REPEAT for f in fx):
                    continue
                used.update(fx)
                best[pid] = {"id": pid, "score": round(s, 2), "via": via}
                if len(best) >= INDEX_TOP:
                    break
            served.update(best)
            f.write(json.dumps({"node": node, "patterns": list(best.values())},
                               ensure_ascii=False) + "\n")
            n += 1
    print(f"pattern index: {n:,} nodes, {len(served):,} findings", flush=True)
    return served


INSTANCES_MAX = 60
INSTANCES_PER_BOOK = 8


def instances(out, keys, served, m, events, nodes, roles):
    """Pass 3: the instances of every finding a reader can reach (the node
    index and the explorer's lists), each with the Strong's numbers of the
    words that put it there — so a card can box exactly those words in the
    original and nothing else (2026-09-19: put boxes around the matched
    word in the original language). A link or chain marks its
    first clause only; the pass does not see which clause answered it.

    -> out/pattern-instances{OUT_TAG}.jsonl.gz: {id, instances: [{ref, m}]}
    """
    want = {r["id"] for r in out[:KEEP_HTML * 2]} | served
    by_key = {keys[i]: i for i in want}
    verb_strong = verb_strongs(nodes)
    got = collections.defaultdict(list)
    per_book = collections.Counter()
    for cid, k in m.all():
        pid = by_key.get(k)
        if pid is None or len(got[pid]) >= INSTANCES_MAX or (
                got[pid] and got[pid][-1][0] == cid):
            continue
        # spread over the books: the clause file is not in canon order
        bk = (pid, cid.split(".")[0])
        if per_book[bk] >= INSTANCES_PER_BOOK:
            continue
        per_book[bk] += 1
        side = k[1:] if k[0] == "E" else k[2] if k[0] == "L" else k[1]
        mark = set()
        rs = roles.get(cid.replace("#cl", "#ct"), {})
        for p in side:
            if p[0] in ("V", "T") or (p[0] in ("X", "S") and p[1] == "v"):
                if p[0] != "T" and verb_strong.get(cid):
                    mark.add(verb_strong[cid])
            elif p[0] in ("R", "L", "X", "S") and len(p) > 1:
                role = "pp" if p[1].startswith("pp:") else p[1]
                dst = (rs.get(role) or (None,))[0]
                st = (nodes.get(dst) or {}).get("strong")
                if st:
                    mark.add(st)
        got[pid].append((cid, sorted(mark)))
    with gzip.open(OUT / f"pattern-instances{OUT_TAG}.jsonl.gz", "wt",
                   encoding="utf-8") as f:
        for pid, xs in got.items():
            f.write(json.dumps({"id": pid, "instances": [
                {"ref": c.split("#")[0], "m": mk} for c, mk in xs]},
                ensure_ascii=False) + "\n")
    print(f"instances for {len(got):,} findings", flush=True)


def render(p, ents, label):
    if p[0] == "V":
        return label.get((p[1], p[2]), p[2])
    if p[0] == "T":
        return f"[{p[1]}]"
    if p[0] == "M":
        return f"<{p[1]}>"
    if p[0] == "S":
        r = "" if p[1] in ("v", "o") else "is " if p[1] == "p" else ""
        return r + "~{" + SIM_LABEL.get(p[2], str(p[2])) + "}"
    if p[0] == "X":
        r = "" if p[1] in ("v", "s", "o") else "to " if p[1] == "io" else             "is " if p[1] == "p" else p[1][3:] + " " if p[1].startswith("pp:")             else ""
        return r + "≈" + greek_gloss.get(p[2], p[2])
    role = "" if p[1] in ("s", "o") else "to " if p[1] == "io" else \
        "is " if p[1] == "p" else p[1][3:] + " " if p[1].startswith("pp:") \
        else "pp "
    if p[0] == "R":
        return role + (ents.get(p[2]) or (p[2],))[0]
    if p[0] == "K":
        return role + f"[a {p[2]}]"
    if p[0] == "L":
        return role + label.get((p[2], p[3]), p[3])
    if p[0] == "C":
        return role + f"[{p[2]}]"
    if p[0] == "P":
        return role + f"[{p[2]}]"
    return str(p)


def side(parts, ents, label):
    v = [p for p in parts if p[0] in ("V", "T", "M") or
         (p[0] in ("X", "S") and p[1] == "v")]
    s = [p for p in parts if len(p) > 1 and p[1] == "s" and p not in v]
    rest = [p for p in parts if p not in v and p not in s]
    return " · ".join(render(p, ents, label) for p in s + v + rest)


def text_of(k, ents, label):
    if k[0] == "E":
        return side(k[1:], ents, label)
    if k[0] == "L":
        return f"{side(k[2], ents, label)}  —{k[1]}→  {side(k[3], ents, label)}"
    return "  →  ".join(side(x, ents, label) for x in k[1:])


DEFAULT_SIM = 0.8


if __name__ == "__main__":
    # THE READER'S CONFIGURATION: similar-word classes at closeness 0.8 (the
    # sweep: classes merge into a few giant ones below 0.7), untagged file
    # names, which app2 loads. tools/patterns/sweep.py runs the others.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sweep
    _words = json.load(gzip.open(OUT / "wordpage-data.json.gz", "rt",
                                 encoding="utf-8"))["words"]
    SIM, SIM_LABEL = sweep.clusters(_words, DEFAULT_SIM)
    SIM_T = DEFAULT_SIM
    main()
