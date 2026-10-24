"""Events as nodes: Copilot's events, their tellings, participants and
cross-references, written into the ontology.

2026-09-29: the event section was completely tag based; it did a nice job with
categorization but was disappointing when one actually reached the events, as
they were not really nodes; and, generally speaking, if the nodes are mentioned
in the primary passages they are also associated with the events. The decision
card the same day: Gospels first; secondary references without graph evidence
SHOWN, marked as Copilot's reading; `recounts` extended so a passage is a
telling of an event; placeholders dropped, non-events held (2026-09-29, events
are tags, not nodes).

Input: out/copilot-events.json (tools/events/copilot_events.py).

For each event in scope:

- **Tellings.** Copilot's primary passages. For the Gospels each is checked
  against the harmony (out/gospel-events.jsonl.gz: the Berean editors'
  sections joined by their parallel notes and by shared wording): a telling
  the editors join to it is `both`; one only Copilot gives is `copilot`; a
  parallel the editors give and Copilot does not is added as `editors`.
  Nothing is reconciled (PRINCIPLES: read without harmonising); where the
  two disagree, both tellings stand and the report says so.
- **Within.** The harmony's sections the event contains (Matthew 5-7 holds
  the Beatitudes, Salt and Light ...): the event is a group of them.
- **Participants** are NOT written here. The rule is computed live from
  the mention index by the server, so it improves as the mentions do. This
  script counts them only for the report.
- **Secondary references**, each with the evidence the graph has for it:
  an editors' parallel note, an editors' quotation note, a declared
  reference ("as it is written", Flash), a pair judged "same" (Flash), or
  the participants the two passages share. Without any, it is kept and
  marked Copilot's reading (a choice made by hand), with Copilot's note verbatim.
- **Themes**: Copilot's names, mapped to the 20 major-theme nodes where the
  name is the theme's (tools/themes/theme_map LINK).
- **Duplicates.** Copilot's lists overlap. An event whose verses lie within
  another's (80%+ of the smaller) is the same occurrence and joins it, its
  title kept as an alias; a pair with identical passages (Resurrection /
  Empty tomb) likewise. Every join is reported.

Writes (idempotent, only these files):
  ontology/entities/events-copilot.jsonl    event and telling (passage) nodes
  ontology/relations/events-copilot.jsonl   `recounts`: telling -> event
  out/event-nodes.json                      the server's view (secondary
                                            evidence, within, themes)
  docs/review/EVENTS-GOSPELS.md             the report

    python tools/events/event_nodes.py [--scope gospels]
"""
from __future__ import annotations

import argparse
import collections
import glob
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "themes"))
from theme_map import BOOKS, CANON, CO_TAGS, LINK, STAMPS  # noqa: E402

ENT = ROOT / "ontology" / "entities" / "events-copilot.jsonl"
REL = ROOT / "ontology" / "relations" / "events-copilot.jsonl"
VIEW = OUT / "event-nodes.json"
REPORT = ROOT / "docs" / "review" / "EVENTS-GOSPELS.md"
SOURCE = "copilot-events"
GOSPELS = {"Matt", "Mark", "Luke", "John"}
SAME = 0.8            # share of the smaller event's verses inside the larger: one occurrence
WITHIN = 0.5          # share of a harmony section inside the event: the event holds it
NAMES_MAX = 30        # a secondary passage longer than this is not grounded by shared names
PROTAGONIST = 300     # a node named in more verses than this grounds nothing by being
                      # named: Jerusalem (788) is a shared setting, Abraham (294) a person
EVIDENCE_CHAPTERS = 4

TO_MACULA = {
    "Gen": "Gen", "Exod": "Exo", "Lev": "Lev", "Num": "Num", "Deut": "Deu",
    "Josh": "Jos", "Judg": "Jdg", "Ruth": "Rut", "1Sam": "1Sa", "2Sam": "2Sa",
    "1Kgs": "1Ki", "2Kgs": "2Ki", "1Chr": "1Ch", "2Chr": "2Ch", "Ezra": "Ezr",
    "Neh": "Neh", "Esth": "Est", "Job": "Job", "Ps": "Psa", "Prov": "Pro",
    "Eccl": "Ecc", "Song": "Sng", "Isa": "Isa", "Jer": "Jer", "Lam": "Lam",
    "Ezek": "Ezk", "Dan": "Dan", "Hos": "Hos", "Joel": "Jol", "Amos": "Amo",
    "Obad": "Oba", "Jonah": "Jon", "Mic": "Mic", "Nah": "Nam", "Hab": "Hab",
    "Zeph": "Zep", "Hag": "Hag", "Zech": "Zec", "Mal": "Mal",
    "Matt": "Mat", "Mark": "Mrk", "Luke": "Luk", "John": "Jhn", "Acts": "Act",
    "Rom": "Rom", "1Cor": "1Co", "2Cor": "2Co", "Gal": "Gal", "Eph": "Eph",
    "Phil": "Php", "Col": "Col", "1Thess": "1Th", "2Thess": "2Th",
    "1Tim": "1Ti", "2Tim": "2Ti", "Titus": "Tit", "Phlm": "Phm", "Heb": "Heb",
    "Jas": "Jas", "1Pet": "1Pe", "2Pet": "2Pe", "1John": "1Jn", "2John": "2Jn",
    "3John": "3Jn", "Jude": "Jud", "Rev": "Rev"}      # as app2/server.py
FROM_MACULA = {v: k for k, v in TO_MACULA.items()}
# Copilot's event-theme names that ARE a major theme under another spelling
THEME_EXTRA = {"presence": "temple_presence", "temple": "temple_presence",
               "messiah": "messiah", "deliverance": "deliverance",
               "new covenant": "covenant", "prophetic fulfillment": "prophetic_word"}
KINDS = [("parallel", r"parallel account|parallel$|^parallel\b(?! judgment)"),
         ("retelling", r"retell|retold|recount|testimony|account of|historical interpretation"),
         ("quotation", r"\bquot|cited|text .* reads|texts jesus quotes"),
         ("fulfilment", r"fulfil"),
         ("prophecy", r"prophec|foretold|predict|promise"),
         ("typology", r"typolog|foreshadow|\btype\b|pattern|archetype"),
         ("background", r"background|law\b|laws\b"),
         ("echo", r"echo|thematic|imagery|motif|parallel")]


def kind_of(note):
    n = (note or "").lower()
    for k, rx in KINDS:
        if re.search(rx, n):
            return k
    return "reference"


# ---- verses ---------------------------------------------------------------

def verses(span):
    """a span record -> BSB verse ids 'Matt.14.13'; [] for a bare book"""
    if not span.get("start"):
        return []
    code, (c1, v1), (c2, v2) = span["book"], span["start"], span["end"]
    last = CANON.book(code)
    out = []
    for c in range(c1, c2 + 1):
        lo = v1 if c == c1 else 1
        hi = v2 if c == c2 else last.get(c, 0)
        out += [f"{code}.{c}.{v}" for v in range(lo, hi + 1)]
    return out


def chapters(span):
    return span["end"][0] - span["start"][0] + 1 if span.get("start") else 99


class Refs:
    """MACULA-keyed layers read into BSB verse ids"""
    def __init__(self):
        vm = json.loads((OUT / "versemap.json").read_text(encoding="utf-8"))["moved"]
        self.m2b = vm                                   # MACULA -> BSB

    def bsb(self, ref, macula_numbering=True):
        if not ref:
            return None
        if macula_numbering:
            ref = self.m2b.get(ref, ref)
        b, c, v = ref.split(".")
        return f"{FROM_MACULA.get(b, b)}.{c}.{v}"

    def span(self, a, b, macula_numbering=True):
        """'Jhn.1.1' .. 'Jhn.1.5' -> the BSB verse ids between"""
        s = self.bsb(a, macula_numbering)
        e = self.bsb(b, macula_numbering) if b else s
        bk, c1, v1 = s.split(".")
        _b, c2, v2 = e.split(".")
        return verses({"book": bk, "start": [int(c1), int(v1)], "end": [int(c2), int(v2)]})


def rows(p):
    op = gzip.open if str(p).endswith(".gz") else open
    with op(p, "rt", encoding="utf-8") as f:
        for ln in f:
            r = json.loads(ln)
            if not any(k.startswith("_") for k in r):
                yield r


def evidence_layers(R):
    """verse -> [(other verses, kind, detail)] from the four layers the graph
    already has; each pair indexed both ways"""
    idx = collections.defaultdict(list)

    def add(a_vs, b_vs, kind, detail):
        for a in a_vs:
            idx[a].append((frozenset(b_vs), kind, detail))
        for b in b_vs:
            idx[b].append((frozenset(a_vs), kind, detail))

    # the editors' parallel notes and quotation notes are the Berean's own
    # numbering (USFM), MACULA book codes
    for r in rows(OUT / "xrefs.jsonl.gz"):
        add([R.bsb(r["from"], False)], R.span(r["to"], r.get("to_end"), False),
            "editors", "the Berean editors' parallel note")
    for r in rows(OUT / "quotenotes.jsonl.gz"):
        add([R.bsb(r["from"], False)], R.span(r["to"], r.get("to_end"), False),
            "quotation", "the Berean editors' quotation note")
    for r in rows(OUT / "declared-refs.jsonl"):
        if r.get("points_to") and r.get("verdict") not in ("none", None):
            add([R.bsb(r["from"])], [R.bsb(r["points_to"])], "declared",
                f"declared: “{r.get('trigger')}” (DeepSeek Flash)")
    for r in rows(OUT / "pair-judgments.jsonl.gz"):
        if r.get("verdict") == "same":
            add([R.bsb(r["a"])], [R.bsb(r["b"])], "judged",
                "judged to say the same thing (DeepSeek Flash)")
    return idx


def mention_index(R):
    """BSB verse -> Counter(node id), every mention; the same for NAMED
    mentions only; node -> number of verses naming it.

    A pronoun resolved to its referent (`refers_to`) is a mention but not a
    naming: 1 Pet 1:3's "us" resolves to Peter the writer, and "names
    Simon Peter" would be a false ground for a link to the resurrection."""
    by = collections.defaultdict(collections.Counter)
    named = collections.defaultdict(collections.Counter)
    for r in rows(OUT / "mentions.jsonl.gz"):
        v = R.bsb(r["occurrence"].split("#")[0])
        by[v][r["record"]] += 1
        if not r["how"].startswith("refers_to"):
            named[v][r["record"]] += 1
    freq = collections.Counter()
    for v, c in named.items():
        for n in c:
            freq[n] += 1
    return by, named, freq


def theme_evidence(R):
    """What says a verse belongs to a major theme, from scripture:
    CITED -- the theme map cites the passage (out/theme-map.json `verses`,
    passages of up to four chapters); TAGGED -- the corpus clause tags
    (DeepSeek Flash, medium or high) put one of the theme's stamps on it."""
    tm = json.loads((OUT / "theme-map.json").read_text(encoding="utf-8"))
    # A VERSE GOES WITH ITS CONCEPT (plan 7.6b; 2026-10-06: the sections will need
    # to be retagged based on this, but there are verses to do
    # so): a concept placed in another theme (ontology/themes/theme-homes.
    # json) cites its verses for that theme, and for the themes it is also
    # in -- overlap is kept ("some overlap is ok"): counted at its home only,
    # the Fall of Babylon left Apocalyptic, its tie having come through
    # "Judgment of Wicked Powers & Nations", now Judgment's and also
    # Apocalyptic's. Each hit is [theme, concept n, "" or "synthesis"]; the
    # synthesis's own concepts are not placed and stay
    homes = json.loads((ROOT / "ontology" / "themes" / "theme-homes.json").read_text(encoding="utf-8"))["concepts"]
    # (keyed by Copilot's numbering: a theme whose outline is redone, 7.6c,
    # keeps its own concepts)
    redone = {t["id"] for t in tm["themes"] if t.get("outline") == "redone"}
    cited = collections.defaultdict(set)                 # verse -> theme ids
    for v, hits in tm.get("verses", {}).items():
        for h in hits:
            place = homes.get(f"{h[0]}:{h[1]}") if not h[2] and h[0] not in redone else None
            # a concept placed into a redone theme stays on its own page and
            # is linked from there (the server's place()), so it counts for both
            if place and place["home"] in redone and place["home"] != h[0]:
                place = {"home": h[0], "also": [place["home"], *place["also"]]}
            cited[v].update([place["home"], *place["also"]] if place else [h[0]])
    stamp_theme = collections.defaultdict(set)
    for tid, stamps in STAMPS.items():
        for s in stamps:
            stamp_theme[s].add(tid)
    tagged = collections.defaultdict(set)
    for r in rows(OUT / "clause-tags.jsonl.gz"):
        if r.get("kind") != "stamp" or r.get("strength") not in ("high", "medium"):
            continue
        for tid in stamp_theme.get(r["tag"], ()):
            tagged[R.bsb(r["clause"].split("#")[0])].add(tid)
    # "PROPHETIC WORD & FULFILLMENT" -> "Prophetic Word & Fulfillment", the
    # form the theme nodes use (tools/themes/theme_nodes.py title_of)
    titles = {t["id"]: " ".join(w if w in ("&", "of") else w[:1].upper() + w[1:]
                                for w in t["title"].lower().split())
              for t in tm["themes"]}
    return cited, tagged, titles


def event_themes(pv, copilot_names, cited, tagged, key2node, titles):
    """The major themes an event is linked to, each with its scripture."""
    listed = {LINK.get(re.sub(r"\s*/\s*", "/", n.lower()).strip())
              or THEME_EXTRA.get(n.lower().strip()) for n in copilot_names} - {None}
    by_c, by_t = collections.defaultdict(list), collections.defaultdict(list)
    for v in pv:
        for tid in cited.get(v, ()):
            by_c[tid].append(v)
        for tid in tagged.get(v, ()):
            by_t[tid].append(v)
    out = []
    for tid in sorted(set(by_c) | set(by_t)):
        c, t = sorted(by_c.get(tid, []), key=vkey), sorted(by_t.get(tid, []), key=vkey)
        # a theme reached only through a stand-in stamp (Church through
        # "people of God", Messiah through "suffering servant") links on its
        # tags alone only when Copilot names the theme for the event: the
        # Passover's people-of-God verses do not make it an event of the Church
        own_stamp = tid in STAMPS.get(tid, [])
        ok_t = len(t) >= CO_TAGS and (tid in listed or
                                      (own_stamp and len(t) / max(1, len(pv)) >= 0.2))
        if not c and not ok_t:
            continue
        node = key2node.get(f"theme:{tid}")
        if not node:
            continue
        out.append({"theme": tid, "title": titles.get(tid, tid), "node": node,
                    "listed": tid in listed, "cited": c[:5], "n_cited": len(c),
                    "tagged": t[:5] if ok_t else [], "n_tagged": len(t) if ok_t else 0})
    return out


def participants(vs, men):
    got = collections.Counter()
    for v in vs:
        got.update(men.get(v, {}))
    return got


# ---- the harmony ------------------------------------------------------------

def harmony(R):
    out = []
    for g in rows(OUT / "gospel-events.jsonl.gz"):
        tel = []
        for t in g.get("tellings", []):
            vs = R.span(t["start"], t["end"], False)
            tel.append({"book": vs[0].split(".")[0] if vs else None, "verses": set(vs),
                        "start": t["start"], "end": t["end"], "why": t.get("why", [])})
        aligned = collections.Counter()
        for j in g.get("joined_by", []):
            for k in (j["a"], j["b"]):
                aligned[k] = max(aligned[k], j.get("verses_aligned", 0))
        for t in tel:
            t["aligned"] = aligned.get(t["start"], 0)
        out.append({"id": g["id"], "title": g["title"], "tellings": tel})
    return out


USFM = ROOT / "data" / "raw" / "usfm" / "engbsb"
USFM_CODE = {b: m.upper() for b, m in TO_MACULA.items()}     # "Exod" -> "EXO"


def bsb_sections():
    """The Berean editors' sections (\\s1), every book: BSB verse id -> its
    heading (lowercased), and -> the section's verses. Public Domain text."""
    head, span = {}, {}
    for code in BOOKS:
        fs = list(USFM.glob(f"*-{USFM_CODE.get(code, code.upper())}engbsb.usfm"))
        if not fs:
            continue
        ch, pend, cur = 0, None, None
        for line in fs[0].read_text(encoding="utf-8").splitlines():
            m = re.match(r"\\c (\d+)", line)
            if m:
                ch = int(m.group(1))
            m = re.match(r"\\s1 (.*)", line)
            if m:
                pend = m.group(1).strip()
            for v in re.findall(r"\\v (\d+)", line):
                ref = f"{code}.{ch}.{v}"
                if pend is not None:
                    cur = {"title": pend, "verses": []}      # the editors' casing
                    pend = None
                if cur is not None:
                    cur["verses"].append(ref)
                    head[ref] = cur["title"].lower()         # compared, never shown
                    span[ref] = cur
    return head, span


HEAD, SPAN = {}, {}


def editors_harmony(R):
    """The editors' parallel notes as groups, the shape harmony() gives for
    the Gospels: each section that carries notes, with the section itself and
    every passage it notes as a telling. Not a claim that they are one event;
    the builder decides that (synoptic histories, or the same heading)."""
    groups = {}
    for r in rows(OUT / "xrefs.jsonl.gz"):
        a = R.bsb(r["from"], False)
        sec = SPAN.get(a)
        if not sec:
            continue
        key = sec["verses"][0]
        g = groups.setdefault(key, {"id": "ed:" + key, "title": sec["title"],
                                    "book": key.split(".")[0],
                                    "tellings": [{"book": key.split(".")[0],
                                                  "verses": set(sec["verses"]),
                                                  "aligned": 0}]})
        vs = R.span(r["to"], r.get("to_end"), False)
        if vs:
            g["tellings"].append({"book": vs[0].split(".")[0], "verses": set(vs), "aligned": 0})
    return list(groups.values())


def decide(scope, e, g, t, vs, keep, tellings, mine, copilot_histories):
    """Is the editors' noted passage `vs` a telling of event e?"""
    if scope == "gospels":
        # the note and the same heading (see the comment where this is used)
        return bool(({HEAD.get(v) for v in vs} - {None}) & mine)
    # THE HISTORIES: Copilot's events are whole chapters that overlap one
    # another, so a note from any of their sections reaches a neighbour (2
    # Sam 1, David's lament, is noted against 1 Chr 10, Saul's death). A
    # note is a telling only when it pairs two parallel histories, fills one
    # this event has no telling of from Copilot -- Abijah is in Chronicles
    # alone, and the editors give 1 Kgs 15:1-8 -- and the passage is not
    # another event's. Otherwise it links two events: the editors' parallel.
    if not (g.get("book") and synoptic(g["book"], t["book"])):
        return False
    if history(t["book"]) in copilot_histories:
        return False
    if any(k is not e and len(set(k["vs"]) & set(vs)) / len(vs) >= WITHIN for k in keep):
        return False
    # and the noted section must be most of the telling it sits in: 2 Kgs
    # 8:16-24 (Jehoram's reign, noted against 2 Chr 21) is 9 verses of
    # Copilot's 200-verse "Elisha's miracles" -- or its heading must name
    # the event: Chronicles cuts finer, so "Abijah Reigns in Judah" is 3 of
    # the 22 verses of 2 Chr 13 and is Abijah's event; "Jehoram Reigns in
    # Judah" does not name Elisha, nor "Amon Reigns in Judah" Manasseh
    src_vs = g["tellings"][0]["verses"]
    return any(tt["by"] != "editors" and
               len(src_vs & set(tt["verses"])) / len(tt["verses"]) >= WITHIN
               for tt in tellings) or bool(title_words(e["title"]) & title_words(g["title"]))


def next_verse(v):
    b, c, n = v.split(".")
    last = CANON.book(b)
    c, n = int(c), int(n)
    return f"{b}.{c}.{n + 1}" if n < last.get(c, 0) else f"{b}.{c + 1}.1"


def merge_runs(tellings):
    """The editors' tellings in one book that run on from each other are one
    telling: 2 Chr 32:1-8 and 32:9-19, noted from two sections of 2 Kings 18,
    are 2 Chr 32:1-19. Copilot's own tellings are left as given."""
    ed = sorted((t for t in tellings if t["by"] == "editors"), key=lambda t: vkey(t["verses"][0]))
    out = [t for t in tellings if t["by"] != "editors"]
    for t in ed:
        prev = next((p for p in reversed(out) if p["by"] == "editors" and p["book"] == t["book"]),
                    None)
        if prev and (next_verse(prev["verses"][-1]) == t["verses"][0]
                     or set(prev["verses"]) & set(t["verses"])):
            prev["verses"] = sorted(set(prev["verses"]) | set(t["verses"]), key=vkey)
            prev["disputed"] = prev.get("disputed") or t.get("disputed")
            continue
        out.append(dict(t))
    return out


def label_of(vs):
    """sorted BSB verse ids of one book -> 'Matthew 14:13–21'"""
    b, c1, v1 = vs[0].split(".")
    _b, c2, v2 = vs[-1].split(".")
    name = "Psalm" if b == "Ps" else BOOKS[b][0]
    if c1 == c2:
        return f"{name} {c1}:{v1}" + (f"–{v2}" if v2 != v1 else "")
    return f"{name} {c1}:{v1}–{c2}:{v2}"


def vkey(v):
    b, c, n = v.split(".")
    return (list(BOOKS).index(b), int(c), int(n))


# ---- the build ----------------------------------------------------------------

KINGDOMS = {"1Sam", "2Sam", "1Kgs", "2Kgs", "1Chr", "2Chr"}
# built so far, in the decided order: the Gospels, then Samuel/Kings/Chronicles,
# then the rest by the canon's own divisions, each event by its first passage
SCOPES = ["gospels", "kingdoms", "law", "histories", "prophets_writings", "acts_revelation"]
_ORDER = list(BOOKS)
DIVISION = {"law": ("Gen", "Deut"), "histories": ("Josh", "Esth"),
            "prophets_writings": ("Job", "Mal"), "acts_revelation": ("Acts", "Rev")}
LIST_RANK = ["canonical", "ot_parallel", "gospel", "additional", "hand"]
# EVENTS A READER NAMED, not on Copilot's lists (ontology/events/hand-events.json).
# 2026-10-03: "Israel receives the law" -- the event the temptation's
# third answer and the Sermon's "you have heard that it was said" both point
# back to, told at Sinai and again at Moab. Built exactly as Copilot's are
# (tellings checked against the editors, participants, parts by passages);
# only the credit differs, and it is carried on the event itself
HAND = ROOT / "ontology" / "events" / "hand-events.json"
# EPISODES THE STORY-ECHO SEARCH NEEDED (plan 6.18, 2026-10-04): 48 approved
# told-again pairs had a side no event list covered -- the widow of
# Zarephath, Tabitha, Elisha's hundred fed. Each is the Berean editors' own
# section(s) holding the steps the pair quotes, titled by their heading, and
# credited to them; built here exactly as the listed events are.
SECTIONS = ROOT / "ontology" / "events" / "section-events.json"
# THE PARALLEL HISTORIES. Between these, an editors' parallel note is a
# telling of one event even when their headings differ -- the same reign
# headed "Abijam Reigns in Judah" in Kings and "Abijah Reigns in Judah" in
# Chronicles, Azariah and Uzziah. Measured 2026-09-29 on the notes between
# Samuel/Kings/Chronicles/Isaiah/Jeremiah/Psalms: 210 same heading, 149
# different, and the different ones that are NOT one event were notes to a
# psalm's setting (1 Sam 21 -> Psalm 34, 56) or from a prophecy to its
# fulfilment inside one history (1 Kgs 13 -> 2 Kgs 23): neither pairs two
# of these histories.
SYNOPTIC = [({"1Sam", "2Sam", "1Kgs", "2Kgs"}, {"1Chr", "2Chr"}),
            ({"2Kgs"}, {"Isa", "Jer"}), ({"2Chr"}, {"Ezra"})]


def history(b):
    """which parallel history a book belongs to (Samuel and Kings are one)"""
    return {"1Sam": "SK", "2Sam": "SK", "1Kgs": "SK", "2Kgs": "SK",
            "1Chr": "CH", "2Chr": "CH"}.get(b, b)


def synoptic(a, b):
    return any((a in x and b in y) or (a in y and b in x) for x, y in SYNOPTIC)


def in_scope(ev, scope):
    books = {s["book"] for s in ev["primary"]}
    if scope == "gospels":
        # the Gospels, or first told there and carried on in Acts (the
        # ascension: Luke 24:50-53, Acts 1:6-11)
        return bool(books) and (books <= GOSPELS or books <= GOSPELS | {"Acts"}
                                and min(_ORDER.index(b) for b in books) < _ORDER.index("Acts"))
    if scope == "kingdoms":
        return bool(books & KINGDOMS) and not books <= GOSPELS
    if scope in DIVISION:
        # what the Gospels and the histories did not take, by where its
        # first passage stands
        if (books and books <= GOSPELS) or books & KINGDOMS or not ev["primary"]:
            return False
        lo, hi = (_ORDER.index(b) for b in DIVISION[scope])
        first = min(_ORDER.index(b) for b in books)
        return lo <= first <= hi
    return False


def slug(t):
    t = t.lower().replace("’", "").replace("'", "")
    t = re.sub(r"\(.*?\)", "", t)
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")[:60]


def taxonomy_ids():
    t = json.loads((ROOT / "ontology" / "interest-taxonomy.json").read_text(encoding="utf-8"))
    return t["significant_events"]["items"]


def match_taxonomy(title, ids):
    """Copilot's title -> the significant_events id it names, by words"""
    stop = {"of", "the", "a", "and", "in", "to", "at", "by", "on", "s", "jesus"}
    w = {x for x in re.findall(r"[a-z0-9]+", title.lower().replace("’", "")) if x not in stop}
    best, score = None, 0.0
    for i in ids:
        iw = {x for x in i.split("_") if x not in stop}
        if not iw or not w:
            continue
        j = len(w & iw) / len(w | iw)
        if j > score:
            best, score = i, j
    return best if score >= 0.5 else None


def theme_of(name, key2node):
    n = re.sub(r"\s*/\s*", "/", name.lower()).strip()
    tid = LINK.get(n) or THEME_EXTRA.get(n)
    return key2node.get(f"theme:{tid}") if tid else None


CONTENT_STOP = {"of", "the", "a", "and", "in", "to", "at", "by", "on", "s", "for", "with",
                "from", "his", "her", "is", "&"}


def title_words(t):
    w = re.findall(r"[a-z]+", t.lower().replace("’s", "").replace("'s", ""))
    return {x.rstrip("s") for x in w if x not in CONTENT_STOP and len(x) > 2}


def same_event(e, k):
    """Is e the same occurrence as k (k listed first, by LIST_RANK)?

    WITHIN ONE LIST, only when their verses match both ways (80%): an event
    inside a larger one is a part of it. Copilot's 101 (the cleansing, John 2
    AND the synoptics) holds 120 (the synoptics, "final"); joining them would
    decide there was one cleansing, a harmonising claim the list does not make.

    ACROSS LISTS, Copilot's supplements repeat its canonical events at another
    grain ("David anointed" is 1 Sam 16:1-13 in one list and 1 Sam 16 in the
    other; the OT table adds the Chronicles column): the same when, in the
    books both give, the smaller lies 80% inside the larger and fills half of
    it, and the two titles share a word. "Solomon's judgment between two
    women" (1 Kgs 3:16-28) is inside "Solomon's wisdom" (3:1-28) but fills
    less than half: a part, kept apart."""
    s, ks = set(e["vs"]), set(k["vs"])
    if not s or not ks:
        return False
    if e["list"] == k["list"]:
        n = len(s & ks)
        return n / min(len(s), len(ks)) >= SAME and n / max(len(s), len(ks)) >= SAME
    books = {v.split(".")[0] for v in s} & {v.split(".")[0] for v in ks}
    s2 = {v for v in s if v.split(".")[0] in books}
    k2 = {v for v in ks if v.split(".")[0] in books}
    if not s2 or not k2:
        return False
    n = len(s2 & k2)
    return (n / min(len(s2), len(k2)) >= SAME and n / max(len(s2), len(k2)) >= WITHIN
            and bool(title_words(e["title"]) & title_words(k["title"])))


def join_duplicates(evs):
    """One occurrence, one node. The first-ranked list's event is the host and
    keeps its title and passages; a joined event adds its tellings in books
    the host does not have (the OT table's Chronicles column), its
    cross-references and themes, and its title as an alias."""
    order = sorted(evs, key=lambda e: (LIST_RANK.index(e["list"]), -len(e["vs"]), e["n"]))
    joined, keep = {}, []
    for e in order:
        host = next((k for k in keep if same_event(e, k)), None)
        if not host:
            keep.append(e)
            continue
        joined[e["id"]] = host["id"]
        host.setdefault("aliases", []).append({"title": e["title"], "list": e["list"],
                                               "n": e["n"]})
        have = {s["book"] for s in host["primary"]}
        for sp in e["primary"]:
            if sp["book"] not in have:
                host["primary"].append(dict(sp, via=e["title"]))
        host["vs"] = sorted({v for s in host["primary"] for v in verses(s)}, key=vkey)
        host["secondary"] += e["secondary"]
        for t in e["themes"]:
            if t not in host["themes"]:
                host["themes"].append(t)
    keep.sort(key=lambda e: vkey(e["vs"][0]))
    overlaps = []
    for i, x in enumerate(keep):
        for y in keep[i + 1:]:
            sx, sy = set(x["vs"]), set(y["vs"])
            if sx & sy and len(sx & sy) / min(len(sx), len(sy)) >= WITHIN:
                overlaps.append((x["title"], y["title"], len(sx & sy), len(sx), len(sy)))
    return keep, joined, overlaps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scopes", default=",".join(SCOPES))
    scopes = ap.parse_args().scopes.split(",")
    src = json.loads((OUT / "copilot-events.json").read_text(encoding="utf-8"))
    for extra in (HAND, SECTIONS):
        if extra.exists():
            src["events"] += json.loads(extra.read_text(encoding="utf-8"))["events"]
    R = Refs()
    h, sp = bsb_sections()
    HEAD.update(h)
    SPAN.update(sp)
    ents, text_passages = {}, set()
    for f in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
        if Path(f).name == ENT.name:
            continue
        for ln in open(f, encoding="utf-8"):
            r = json.loads(ln)
            ents[r["id"]] = r
            # A TELLING REUSES ONLY THE TEXT'S OWN PASSAGE RECORDS (mark_6_35_44,
            # from the decomposition). The role patterns' cells and the
            # templates' stages are passages too, and a cell with the same two
            # verses as a telling became it on 2026-10-03's rerun: the ten
            # virgins "told" by rcell_bridegroom_..._1, fourteen in all
            if Path(f).name == "entities.jsonl":
                text_passages.add(r["id"])
    men, named, freq = mention_index(R)
    C = {"R": R, "src": src, "ents": ents, "men": men, "named": named, "freq": freq,
         "ev_idx": evidence_layers(R),
         "passages": {tuple(r["refs"][:2]): i for i, r in ents.items()
                      if r.get("type") == "passage" and len(r.get("refs") or []) == 2
                      and i in text_passages},
         "key2node": json.loads((ROOT / "ontology" / "themes" / "theme-nodes.json")
                                .read_text(encoding="utf-8")),
         "tax": taxonomy_ids(), "nodes": [], "rels": [], "view": {}, "joined": {},
         "themes": theme_evidence(R),
         "used": set()}
    for scope in scopes:
        build(scope, C)
    nodes, rels = C["nodes"], C["rels"]
    for path, rs in ((ENT, nodes), (REL, rels)):
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for r in rs:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    VIEW.write_text(json.dumps({"_source": "Microsoft Copilot's event lists "
                                "(ontology/events/copilot-events.md), checked and "
                                "evidenced by tools/events/event_nodes.py",
                                "events": C["view"], "joined": C["joined"]},
                               ensure_ascii=False, indent=1), encoding="utf-8")


def build(scope, C):
    R, src, ents, men, named, freq = C["R"], C["src"], C["ents"], C["men"], C["named"], C["freq"]
    ev_idx, passages, key2node, tax = C["ev_idx"], C["passages"], C["key2node"], C["tax"]
    used = C["used"]
    evs = [json.loads(json.dumps(e)) for e in src["events"]
           if not e.get("held") and in_scope(e, scope)]
    for e in evs:
        # the OT table's "Other" column (Ps 89; "Hos; Amos (prophetic
        # backdrop)"; Isa 36-39) is Copilot's pointer to related texts, not
        # a telling: a cross-reference, promoted only if the editors join it
        e["secondary"] += [dict(s, line=s["label"]) for s in e["primary"]
                           if s.get("column") == "Other"]
        e["primary"] = [s for s in e["primary"] if s.get("column") != "Other"]
        e["vs"] = sorted({v for s in e["primary"] for v in verses(s)}, key=vkey)
    evs = [e for e in evs if e["vs"]]
    keep, joined, overlaps = join_duplicates(evs)
    C["joined"].update(joined)
    # the Gospels have their own harmony (the editors joined by wording as
    # well, tools/gospel_events.py); elsewhere the editors' notes directly
    H = harmony(R) if scope == "gospels" else editors_harmony(R)
    nodes, rels, view, rep = C["nodes"], C["rels"], C["view"], []
    for e in keep:
        s = set(e["vs"])
        eid = "event_" + slug(e["title"])
        while eid in used or eid in ents:
            eid += "_"
        used.add(eid)
        e["eid"] = eid
        # whose list the event is from, said on everything made from it
        reader = e.get("reader", "Microsoft Copilot")
        lname = e.get("list_name", "Microsoft Copilot's event list")
        esrc = e.get("source", SOURCE)
        # tellings: Copilot's, each checked against the harmony
        tellings = []
        for sp in e["primary"]:
            vs = sorted(set(verses(sp)), key=vkey)
            tellings.append({"book": sp["book"], "verses": vs, "by": "copilot",
                             "note": sp.get("note"), "via": sp.get("via")})
        # one of Copilot's passages inside another of the same book is one
        # telling, the narrower: its OT table gives "Golden calves" both 1
        # Kgs 12:25-33 and all of 1 Kgs 12, whose first half is "Kingdom
        # divided"
        tellings = [t for t in tellings if not any(
            u is not t and u["book"] == t["book"] and set(u["verses"]) < set(t["verses"])
            for u in tellings)]
        s = {v for t in tellings for v in t["verses"]}
        within, added = [], []
        for g in H:
            # in the histories a group is one section and the passages its
            # note points to: it belongs to the event when the SECTION does
            cand = g["tellings"] if scope == "gospels" else g["tellings"][:1]
            hit = [t for t in cand if t["verses"] and
                   len(t["verses"] & s) / len(t["verses"]) >= WITHIN]
            if not hit:
                continue
            # the part's own parallels in the other Gospels: Mark 16:9-11 is
            # the appearance to Mary Magdalene, one part of the resurrection.
            # One row per heading: a section Kings and Chronicles both head
            # "Asa Reigns in Judah" is listed once, its passages together
            elsewhere = [{"label": label_of(sorted(t["verses"], key=vkey)),
                          "first": min(t["verses"], key=vkey)}
                         for t in g["tellings"] if t["verses"] and not t["verses"] & s]
            prior = next((w for w in within if w["title"] == g["title"]), None)
            if prior:
                prior["elsewhere"] += [x for x in elsewhere if x not in prior["elsewhere"]]
            else:
                within.append({"id": g["id"], "title": g["title"], "elsewhere": elsewhere})
            # the section IS the event, not a part of it, only when it also
            # covers most of the event in that gospel: the Beatitudes are in
            # the Sermon on the Mount, and their Luke parallel is a parallel
            # of that part, not a telling of the sermon
            # CONFIRMATION: Copilot's tellings that lie inside this section's
            # tellings (Mark 1:29-31 inside the editors' Mark 1:29-34), two
            # or more Gospels of them -- the editors join them as one event
            # (or the other way: the editors' Sower, Matthew 13:1-9, inside
            # Copilot's Matthew 13:1-23) -- one inside the other
            joins = [tt for tt in tellings if any(
                t["verses"] and len(set(tt["verses"]) & t["verses"])
                / min(len(tt["verses"]), len(t["verses"])) >= SAME
                for t in g["tellings"])]
            if len({tt["book"] for tt in joins}) >= 2:
                for tt in joins:
                    tt["by"] = "both"
            whole = any(len(t["verses"] & s) / len(t["verses"]) >= SAME and
                        len(t["verses"] & s) / max(1, sum(1 for v in s if v.split(".")[0]
                                                          == t["book"])) >= SAME
                        for t in hit)
            # In the histories Copilot's events are chapters and the editors'
            # sections are parts of them, so a part's note into Chronicles is
            # the event's Chronicles telling (2 Kgs 18:13 -> 2 Chr 32:1-8,
            # 18:17 -> 32:9-19): every section counts there, and whether a
            # noted passage is a telling is the synoptic rule's to decide
            if not whole and scope == "gospels":
                continue
            for t in g["tellings"]:
                if not (t["verses"] & s) and t["book"] and t["verses"]:
                    added.append((g, t))
        # a telling Copilot gives in one list and the host lacked. It comes at
        # that list's grain: "Hezekiah's reforms & Assyrian crisis" gives 2
        # Chr 29-32, the reforms included, to "Hezekiah's deliverance". Where
        # the editors' notes from the host's own sections point inside it (2
        # Kgs 18:13 -> 2 Chr 32:1-8, 18:17 -> 32:9-19 ...), it is narrowed to
        # what they point to
        own = {v for tt in tellings if not tt.get("via") for v in tt["verses"]}
        for tt in tellings:
            if not tt.get("via"):
                continue
            tt["note"] = f"from Copilot's '{tt['via']}'"
            linked = set()
            for g in H:
                if scope != "gospels" and g["tellings"][0]["verses"] & own:
                    for t in g["tellings"][1:]:
                        linked |= t["verses"] & set(tt["verses"])
            if linked:
                lo, hi = min(linked, key=vkey), max(linked, key=vkey)
                tt["verses"] = [v for v in tt["verses"] if vkey(lo) <= vkey(v) <= vkey(hi)]
                tt["note"] += ", narrowed to what the Berean editors link"
        # an editors' parallel Copilot does not give: a telling in its own
        # right, credited to them -- merged per book into runs
        # THE EDITORS OUTRANK COPILOT (2026-09-29: the
        # editors are trusted over copilot as the more credible source). But their \r
        # notes mark parallel PASSAGES, which is not always one event: Luke
        # 16:19, the rich man, is noted against John 5:39, "if you believed
        # Moses". So an editors' parallel is a TELLING when the editors also
        # give the two sections the same heading ("The Great Commission",
        # Matthew 28:16 and Mark 16:14) -- their note and their naming
        # agree. Shared wording alone is not enough: Luke 7:36 (a sinful
        # woman, a Pharisee's house) aligns in 13 verses with the anointing
        # at Bethany, and the editors head the two differently. The rest
        # stay the editors' parallels, credited and shown above Copilot's.
        mine = {h for tt in tellings for v in tt["verses"] for h in [HEAD.get(v)] if h}
        copilot_histories = {history(tt["book"]) for tt in tellings}
        # EVERY NOTE IS WEIGHED BEFORE ANY IS FILED: one passage can be
        # reached by two notes (1 Kgs 15:1-8 from two sections of 2 Chr
        # 13), and filing it as a parallel off the first must not stop the
        # second from making it a telling
        decided = []
        for g, t in added:
            vs = sorted(t["verses"], key=vkey)
            decided.append((decide(scope, e, g, t, vs, keep, tellings, mine, copilot_histories),
                            g, t, vs))
        decided.sort(key=lambda x: not x[0])
        parallels = []
        for promote, g, t, vs in decided:
            if any(set(vs) & set(tt["verses"]) for tt in tellings) or \
                    any(p["first"] == vs[0] for p in parallels):
                continue
            if promote:
                # Copilot made these verses a separate event: the editors
                # overrule it, and the disagreement is recorded, not hidden
                other = [k["title"] for k in keep if k is not e and
                         len(set(k["vs"]) & set(vs)) / len(vs) >= WITHIN]
                tellings.append({"book": t["book"], "verses": vs, "by": "editors",
                                 "note": None, "section": g["title"],
                                 # said about the text; the tools are named in
                                 # About (2026-09-30)
                                 "disputed": ("the event list also gives these verses as "
                                              + " and ".join(f"'{o}'" for o in other))
                                 if other else None})
                continue
            # the parallel's OWN heading: g["title"] is the section the note
            # sits in -- this event's -- so every parallel of "Feeding a
            # Hundred Men" was shown under that title, Matthew 15 included
            parallels.append({"label": label_of(vs), "first": vs[0],
                              "section": (SPAN.get(vs[0]) or {}).get("title") or g["title"],
                              "aligned": t["aligned"]})
        tellings = merge_runs(tellings)
        # participants, for the report only (the server computes them live)
        part = participants([v for t in tellings for v in t["verses"]], men)
        top = [(ents.get(n, {}).get("name", n), c) for n, c in part.most_common(8)]
        # secondary references, each with its evidence
        pv = {v for t in tellings for v in t["verses"]}
        pnames = {n for n in participants(pv, named) if freq[n] <= PROTAGONIST}
        sec = []
        seen = set()
        for r in e["secondary"]:
            svs = set(verses(r)) if r.get("start") and chapters(r) <= EVIDENCE_CHAPTERS else set()
            key = (r["label"], r.get("note"))
            if key in seen:
                continue
            # a cross-reference that is now a telling ("1 Chronicles 17:1-15
            # (parallel account)") is shown once, as the telling
            if svs and len(svs & pv) / len(svs) >= SAME:
                continue
            seen.add(key)
            evid = []
            # IN CANON ORDER: `pv` is a set, and which verse a detail's example
            # came from changed run to run (44 events' details differed on an
            # unchanged rebuild, 2026-10-06) -- a builder whose output depends
            # on the hash seed cannot show what a change changed
            for v in sorted(pv, key=vkey):
                for other, k, detail in ev_idx.get(v, ()):
                    if other & svs:
                        evid.append({"kind": k, "detail": detail,
                                     "from": v, "to": sorted(other & svs, key=vkey)[0]})
            if svs and len(svs) <= NAMES_MAX:
                shared = pnames & set(participants(svs, named))
                if shared:
                    evid.append({"kind": "names", "detail": "names " + ", ".join(
                        sorted(ents.get(n, {}).get("name", n) for n in shared)[:4])})
            kinds = sorted({x["kind"] for x in evid})
            sec.append({"label": r["label"], "go": go_of(r),
                        "first": (f"{r['book']}.{r['start'][0]}.{r['start'][1]}"
                                  if r.get("start") else None),
                        "note": r.get("note"),
                        "kind": kind_of(r.get("note")), "evidence": kinds,
                        "detail": dedupe(evid)[:4],
                        "reading": None if evid else reader})
        themes = [{"name": t, "node": theme_of(t, key2node)} for t in e["themes"]]
        # EVENTS TO THEMES (2026-09-29), each link
        # with scripture: the theme map cites a passage of this event, or the
        # clause tags put the theme's stamps on its verses
        mthemes = event_themes(pv, e["themes"], *C["themes"][:2], key2node, C["themes"][2])
        stamp = match_taxonomy(e["title"], tax)
        first = [t["verses"][0] for t in tellings if t["verses"]]
        tell_nodes = []
        for t in tellings:
            if not t["verses"]:
                continue
            a, b = t["verses"][0].split("."), t["verses"][-1].split(".")
            lab = label_of(t["verses"])
            # a passage node the graph already has for exactly these verses
            # (mark_6_35_44, "Feeding of the five thousand") is the telling;
            # a second node for the same stretch would be a duplicate
            pid = passages.get((f"{a[0]} {a[1]}:{a[2]}", f"{b[0]} {b[1]}:{b[2]}")) \
                or f"tell_{a[0]}_{a[1]}_{a[2]}_{b[1]}_{b[2]}".lower()
            tell_nodes.append((pid, lab, t))
            if pid not in used and pid not in ents:
                used.add(pid)
                nodes.append({"attrs": {"kind": "telling"},
                              "desc": f"{lab}, a telling of an event.",
                              "gender": "unknown", "id": pid, "name": lab,
                              "refs": [f"{a[0]} {a[1]}:{a[2]}", f"{b[0]} {b[1]}:{b[2]}"],
                              "source": esrc, "type": "passage"})
            who = {"both": f"{lname} and the Berean editors' parallel notes",
                   "copilot": lname,
                   "editors": "the Berean editors' parallel notes"}[t["by"]]
            rels.append({"certainty": "disputed" if t.get("disputed") else "implied",
                         "dst": eid,
                         "note": f"{lab} tells '{e['title']}' ({who})"
                                 + (f"; disputed: {t['disputed']}, and the Berean editors, "
                                    f"the more credible source (decided 2026-09-29), join it here"
                                    if t.get("disputed") else ""),
                         "refs": [f"{a[0]} {a[1]}:{a[2]}"], "source": esrc,
                         "src": pid, "type": "recounts"})
        nodes.append({"attrs": {"kind": "major_event", "list": e["list"], "n": e["n"],
                                "reader": reader,
                                **({"stamp": stamp} if stamp else {}),
                                **({"aliases": [x["title"] for x in e["aliases"]]}
                                   if e.get("aliases") else {})},
                      "desc": f"{e['title']}: an event told in "
                              + "; ".join(lab for _p, lab, _t in tell_nodes)
                              + ". Every passage is checked against the Berean text"
                              + " and each telling against the Berean editors' parallel "
                                "notes.",
                      "disambiguation": f"the event, as {lname} names "
                                        "it (not the person, place or passage of that name)",
                      "gender": "unknown", "id": eid, "name": e["title"],
                      "refs": [f"{v.split('.')[0]} {v.split('.')[1]}:{v.split('.')[2]}"
                               for v in first],
                      "source": esrc, "type": "event"})
        view[eid] = {"title": e["title"], "list": e["list"], "n": e["n"], "scope": scope,
                     "aliases": e.get("aliases", []), "stamp": stamp,
                     "tellings": [{"id": p, "label": lab, "by": t["by"], "note": t.get("note"),
                                   "disputed": t.get("disputed"), "section": t.get("section"),
                                   "first": t["verses"][0], "last": t["verses"][-1],
                                   "n": len(t["verses"])} for p, lab, t in tell_nodes],
                     "within": within, "parallels": parallels, "themes": themes,
                     "mthemes": mthemes,
                     "secondary": sec, "notes": e.get("notes")}
        rep.append((e, eid, tell_nodes, within, sec, top, themes, stamp, parallels))
        for m in mthemes:
            refs = [f"{v.split('.')[0]} {v.split('.')[1]}:{v.split('.')[2]}"
                    for v in (m["cited"] or m["tagged"])[:3]]
            why = (f"the major-theme map cites {m['n_cited']} of its verses" if m["n_cited"]
                   else f"the clause tags (DeepSeek Flash) give {m['n_tagged']} of its verses "
                        f"the theme's stamps")
            rels.append({"certainty": "implied", "dst": m["node"],
                         "note": f"'{e['title']}' belongs to the major theme {m['title']}: {why}"
                                 + (f"; {lname if e.get('list_name') else 'Copilot' + chr(39) + 's event list'} names the theme too"
                                    if m["listed"] else ""),
                         "refs": refs, "source": esrc, "src": eid, "type": "in_theme"})

    # GROUPING: an event whose passages lie (80%) inside a larger one's is a
    # part of it -- Ehud, Deborah, Gideon and Samson inside "Judges raised
    # up", Paul at Athens inside "Paul's missionary journeys". Derived from
    # Copilot's passages and shown as that; not an edge (`part_of` joins
    # passages, and extending it to events is decided by hand)
    for x in keep:
        for y in keep:
            sx, sy = set(x["vs"]), set(y["vs"])
            if x is not y and len(sx) < len(sy) and len(sx & sy) / len(sx) >= SAME:
                view[x["eid"]].setdefault("part_of", []).append(
                    {"id": y["eid"], "title": y["title"]})
                view[y["eid"]].setdefault("parts", []).append(
                    {"id": x["eid"], "title": x["title"], "first": x["vs"][0]})
    for x in keep:
        # only the nearest whole: Gideon's fleece is part of "Gideon's
        # victory", which is part of "Judges raised up"
        po = view[x["eid"]].get("part_of") or []
        if len(po) > 1:
            size = {k["eid"]: len(k["vs"]) for k in keep}
            po.sort(key=lambda p: size[p["id"]])
            view[x["eid"]]["part_of"] = po[:1]
    for x in keep:
        ps = view[x["eid"]].get("parts") or []
        view[x["eid"]]["parts"] = sorted(
            [p for p in ps if (view[p["id"]].get("part_of") or [{}])[0].get("id") == x["eid"]],
            key=lambda p: vkey(p["first"]))
    # and as edges (2026-09-29: extend part_of), cited to the
    # part's first verse, which lies inside the whole's passages
    by_eid = {k["eid"]: k for k in keep}
    for x in keep:
        for p in view[x["eid"]].get("part_of") or []:
            b, c, v = x["vs"][0].split(".")
            names = sorted({k.get("list_name", "Microsoft Copilot's event list")
                            for k in (x, by_eid[p["id"]])})
            rels.append({"certainty": "implied", "dst": p["id"],
                         "note": f"'{x['title']}' lies within '{p['title']}': its passages are "
                                 + ("inside the larger event's (both from Microsoft Copilot's "
                                    "event lists)" if names == ["Microsoft Copilot's event list"]
                                    else "inside the larger event's (from " + " and ".join(names) + ")"),
                         "refs": [f"{b} {c}:{v}"], "source": by_eid[p["id"]].get("source", SOURCE),
                         "src": x["eid"], "type": "part_of"})
    write_report(rep, joined, src, scope, overlaps)
    secs = [x for _e, _i, _t, _w, sec, *_ in rep for x in sec]
    tel = collections.Counter(t["by"] for _e, _i, tn, *_ in rep for _p, _l, t in tn)
    print(f"{scope}: events {len(rep)}, tellings {sum(tel.values())} ({dict(tel)}), "
          f"joined {len(joined)}; secondary {len(secs)}: "
          f"{sum(1 for x in secs if x['evidence'])} with evidence, "
          f"{sum(1 for x in secs if not x['evidence'])} Copilot's reading")


def dedupe(evid):
    seen, out = set(), []
    for x in evid:
        k = (x["kind"], x.get("from"), x.get("to"), x["detail"])
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def go_of(r):
    if not r.get("start"):
        return None
    name = "Psalm" if r["book"] == "Ps" else BOOKS[r["book"]][0]
    return f"{name} {r['start'][0]}:{r['start'][1]}"


def write_report(rep, joined, src, scope, overlaps):
    tel = collections.Counter(t["by"] for _e, _i, tn, *_ in rep for _p, _l, t in tn)
    L = [f"# Events as nodes — {scope}", "",
         "From Microsoft Copilot's event lists (ontology/events/copilot-events.md), built by "
         "`tools/events/event_nodes.py`. Decision card, 2026-09-29: Gospels first; "
         "secondary references without evidence shown and marked as Copilot's reading.", "",
         f"- **{len(rep)} events**; **{len(joined)} joined** into another as the same "
         f"occurrence (below).",
         f"- **Copilot's tellings:** {tel['both']} joined to another telling of the "
         f"event by the Berean editors' notes; {tel['copilot']} not (including every "
         f"event told once, and Copilot's larger groupings, which hold several of the "
         f"editors' sections).",
         f"- **The editors' tellings Copilot does not give:** {tel['editors']} "
         + ("(the editors' note and the same heading)" if scope == "gospels" else
            "(an editors' note between the parallel histories — Samuel/Kings and "
            "Chronicles, Kings and Isaiah/Jeremiah, Chronicles and Ezra — or the same "
            "heading)") + ".",
         f"- **The editors' parallels, not tellings:** {sum(len(r[8]) for r in rep)}.",
         ""]
    if scope != "gospels":
        mis = [p for p in src.get("problems", []) if " is under " in p]
        if mis:
            L += ["## Copilot's OT table: passages in the wrong column", "",
                  "Kept as tellings (each is a real passage of the event); the column is "
                  "Copilot's slip.", ""] + [f"- {p}" for p in mis] + [""]
    L += ["## The editors' tellings Copilot did not give", ""]
    for e, eid, tn, *_ in rep:
        ed = [f"{lab}" + (f" — disputed: {t['disputed']}" if t.get("disputed") else "")
              for _p, lab, t in tn if t["by"] == "editors"]
        if ed:
            L.append(f"- **{e['title']}**: " + "; ".join(ed))
    L += [""]
    L += ["## Joined as one occurrence", ""]
    names = {e["id"]: e["title"] for e in src["events"]}
    for a_, b_ in joined.items():
        L.append(f"- {names[a_]} ({a_}) → {names[b_]} ({b_})")
    L += ["", "## Kept apart, but sharing passages (for decision)", "",
          "Half or more of the smaller event's verses lie in the other. Kept as two "
          "nodes because they are not the same both ways; which is right is a reading.", ""]
    for x, y, n, nx, ny in overlaps:
        L.append(f"- {x} ({nx} verses) and {y} ({ny}): {n} shared")
    L += ["", "## Tellings in two or more books that no editors' note joins", ""]
    for e, eid, tn, *_ in rep:
        solo = [lab for _p, lab, t in tn if t["by"] == "copilot"]
        if solo and len({t["book"] for _p, _l, t in tn}) > 1:
            L.append(f"- **{e['title']}**: {', '.join(solo)}")
    L += ["", "## The editors' parallels (not tellings)", "",
          "The editors' `\\r` notes mark similar passages as well as one event told twice, "
          "so these are shown as their parallels. 'aligned' is how many verses share "
          "wording (Gospels only).", ""]
    for r in rep:
        if r[8]:
            L.append(f"- **{r[0]['title']}**: " + ", ".join(
                f"{p['label']} ({p['section']}; aligned {p['aligned']})" for p in r[8]))
    L += ["", "## Every event", ""]
    for e, eid, tn, within, sec, top, themes, stamp, _par in rep:
        L.append(f"### {e['title']}  `{eid}`" + (f"  · stamp `{stamp}`" if stamp else ""))
        L.append("- Tellings: " + "; ".join(f"{lab} ({t['by']})" for _p, lab, t in tn))
        if within:
            L.append("- Within: " + "; ".join(w["title"] for w in within[:12])
                     + (f" … +{len(within) - 12}" if len(within) > 12 else ""))
        L.append("- Participants: " + ", ".join(f"{n} {c}" for n, c in top))
        if themes:
            L.append("- Themes: " + ", ".join(t["name"] + ("" if t["node"] else " (no node)")
                                              for t in themes))
        for x in sec:
            ev = ", ".join(x["evidence"]) or "Copilot's reading"
            L.append(f"  - {x['label']} — {x['kind']} · **{ev}**"
                     + (f" — {x['note']}" if x["note"] else ""))
        L.append("")
    (REPORT.parent / f"EVENTS-{scope.upper()}.md").write_text("\n".join(L) + "\n",
                                                               encoding="utf-8")


if __name__ == "__main__":
    main()
