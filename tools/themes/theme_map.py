"""The major-theme map: Microsoft Copilot's 20 themes, parsed, checked
against the text, grounded, and tied into the ontology.

2026-09-29: build a high-level mapping layer for each theme and map the
themes into the ontology/node structure in general, naming MS Copilot as the
source, so a user has a quick way to detect, navigate to, and understand
these major themes before diving into as much detail as desired; ground every
relationship in some kind of scripture backup, and give Copilot a list of
those that cannot be grounded from the graph or deterministically, so that a
reader can reference some scripture and not just take Copilot's word for it.

Source: ontology/themes/copilot-major-themes.md, Copilot's text verbatim.

What this does, and what it refuses to do quietly:

- PARSES each theme: its core concepts (A), the passages given for each
  (B), its secondary concepts (C) and its links to other themes (D).
  Theme 21 ("Covenant, full canonical synthesis") is kept as an EXTENSION
  of theme 4, not a 21st theme.
- RESOLVES every reference against the Berean text: "Genesis 1:3,6,9",
  "Psalm 89:3–4,28–37", "Judges 3:10; 6:34", "Genesis 8:20–9:17",
  "Exodus 25–40", "Gen 6–9", a bare "Psalms". A reference that names a
  chapter or verse the Berean does not have is reported, not dropped.
- GROUNDS every relationship. A concept is grounded by its passages. A
  secondary concept by the passages in its brackets. A link between two
  themes by SCRIPTURE ON BOTH SIDES: a passage both themes cite, or verses
  the corpus clause tags (DeepSeek Flash) give both themes' stamps. What
  cannot be grounded is written to docs/review/THEMES-UNGROUNDED.md, for
  a hand follow-up with Copilot.
- TIES each theme to the ontology's own stamps (so a reader can go from the
  map to every clause tagged with it) and to the other themes.

    python tools/themes/theme_map.py   -> out/theme-map.json
                                          docs/review/THEMES-UNGROUNDED.md
"""
from __future__ import annotations

import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
SRC = ROOT / "ontology" / "themes" / "copilot-major-themes.md"
# THE SITE'S OWN THEMES (plan 7.6b, 2026-10-07: Trinity, Spiritual Warfare,
# Freedom, Children of God), in Copilot's format, parsed and checked by the
# same code; each theme carries its source, so a page credits Copilot's
# outlines to Copilot and these to the site. Decided on the card: "Drafted here".
SITE_SRC = ROOT / "ontology" / "themes" / "site-themes.md"
# the twenty Copilot outlines redone in the texts' words (plan 7.6c)
REDONE_SRC = ROOT / "ontology" / "themes" / "redone-outlines.md"
REDONE_SOURCE = ("the site: the theme from Microsoft Copilot's map, its outline redone in the "
                 "texts' words by Claude Opus, checked, and approved by the site's owner")
SITE_SOURCE = "the site (drafted by Claude Opus from the texts, checked, and approved by its owner)"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
from det_pairs_review import bsb  # noqa: E402

SOURCE = "Microsoft Copilot"
# A.22 FOR THE THEME NOTES (P-90, approved 2026-10-02, with the
# theme notes started). Copilot's source stays verbatim; a note that quotes the
# KJV is shown in the Berean's words for the same verse, from this file
# (original note -> shown note), and the original is kept as `note_kjv`.
REQUOTED = ROOT / "ontology" / "themes" / "theme-notes-requoted.json"
_REQ = (json.loads(REQUOTED.read_text(encoding="utf-8")).get("notes", {})
        if REQUOTED.exists() else {})


def requote(note):
    return _REQ.get(note, note) if note else note
INDEX_CHAPTERS = 4       # a passage up to this many chapters marks its verses
CO_TAGS = 3              # verses both stamps must share to ground a link by the tags
GROUND_MAX = 30          # a passage longer than this does not count toward grounding a link

THEME_ID = {1: "creation", 2: "image_of_god", 3: "blessing_commission", 4: "covenant",
            5: "kingdom", 6: "law_wisdom", 7: "sacrifice", 8: "priesthood",
            9: "temple_presence", 10: "sin_exile_death", 11: "judgment",
            12: "mercy_restoration", 13: "deliverance", 14: "prophetic_word",
            15: "messiah", 16: "spirit", 17: "church", 18: "new_creation",
            19: "wisdom_literature", 20: "apocalyptic", 21: "covenant",
            22: "trinity", 23: "spiritual_warfare", 24: "freedom", 25: "children_of_god"}
# the ontology's own stamps each theme extends into (the corpus clause tags)
STAMPS = {"creation": ["creation"], "image_of_god": ["image_of_god"],
          "blessing_commission": ["blessing_commission", "blessing"],
          "covenant": ["covenant", "covenant_at_sinai", "covenant_with_abraham",
                       "covenant_with_david", "covenant_with_noah", "new_covenant"],
          "kingdom": ["kingdom"], "law_wisdom": ["law_wisdom"],
          "sacrifice": ["sacrifice", "sacrificial_system"],
          "priesthood": ["priesthood", "priest"], "temple_presence": ["temple_presence"],
          "sin_exile_death": ["sin_exile_death"], "judgment": ["judgment"],
          "mercy_restoration": ["mercy_restoration"], "deliverance": ["deliverance"],
          "prophetic_word": ["prophetic_word"],
          "messiah": ["suffering_servant", "redemption_in_christ"],
          "spirit": ["spirit"], "church": ["people_of_god"],
          "new_creation": ["new_creation"], "wisdom_literature": ["law_wisdom"],
          "apocalyptic": ["day_of_the_lord_sym", "beast_anti_kingdom"]}
LINK = {"creation": "creation", "image of god": "image_of_god",
        "blessing & commission": "blessing_commission", "covenant": "covenant",
        "kingdom": "kingdom", "law/wisdom": "law_wisdom", "sacrifice": "sacrifice",
        "priesthood": "priesthood", "temple/presence": "temple_presence",
        "sin/exile/death": "sin_exile_death", "judgment": "judgment",
        "mercy & restoration": "mercy_restoration",
        "deliverance/salvation": "deliverance",
        "prophetic word & fulfillment": "prophetic_word", "christology": "messiah",
        "messiah/christology": "messiah", "spirit": "spirit", "church": "church",
        "new creation": "new_creation", "wisdom literature": "wisdom_literature",
        "wisdom": "wisdom_literature", "apocalyptic": "apocalyptic",
        "father, son and holy spirit": "trinity", "trinity": "trinity",
        "spiritual warfare": "spiritual_warfare", "freedom": "freedom",
        "children of god": "children_of_god",
        "new covenant": "covenant", "atonement": "sacrifice"}
BOOKS = {
    "Gen": ["Genesis", "Gen"], "Exod": ["Exodus", "Exod"], "Lev": ["Leviticus", "Lev"],
    "Num": ["Numbers", "Num"], "Deut": ["Deuteronomy", "Deut"], "Josh": ["Joshua", "Josh"],
    "Judg": ["Judges", "Judg"], "Ruth": ["Ruth"], "1Sam": ["1 Samuel", "1 Sam"],
    "2Sam": ["2 Samuel", "2 Sam"], "1Kgs": ["1 Kings", "1 Kgs"], "2Kgs": ["2 Kings", "2 Kgs"],
    "1Chr": ["1 Chronicles", "1 Chr"], "2Chr": ["2 Chronicles", "2 Chr"], "Ezra": ["Ezra"],
    "Neh": ["Nehemiah", "Neh"], "Esth": ["Esther", "Esth"], "Job": ["Job"],
    "Ps": ["Psalms", "Psalm", "Ps"], "Prov": ["Proverbs", "Prov"],
    "Eccl": ["Ecclesiastes", "Eccl"], "Song": ["Song of Solomon", "Song"],
    "Isa": ["Isaiah", "Isa"], "Jer": ["Jeremiah", "Jer"], "Lam": ["Lamentations", "Lam"],
    "Ezek": ["Ezekiel", "Ezek"], "Dan": ["Daniel", "Dan"], "Hos": ["Hosea", "Hos"],
    "Joel": ["Joel"], "Amos": ["Amos"], "Obad": ["Obadiah"], "Jonah": ["Jonah"],
    "Mic": ["Micah", "Mic"], "Nah": ["Nahum"], "Hab": ["Habakkuk", "Hab"],
    "Zeph": ["Zephaniah", "Zeph"], "Hag": ["Haggai", "Hag"], "Zech": ["Zechariah", "Zech"],
    "Mal": ["Malachi", "Mal"], "Matt": ["Matthew", "Matt"], "Mark": ["Mark"],
    "Luke": ["Luke"], "John": ["John"], "Acts": ["Acts"], "Rom": ["Romans", "Rom"],
    "1Cor": ["1 Corinthians", "1 Cor"], "2Cor": ["2 Corinthians", "2 Cor"],
    "Gal": ["Galatians", "Gal"], "Eph": ["Ephesians", "Eph"], "Phil": ["Philippians", "Phil"],
    "Col": ["Colossians", "Col"], "1Thess": ["1 Thessalonians", "1 Thess"],
    "2Thess": ["2 Thessalonians", "2 Thess"], "1Tim": ["1 Timothy", "1 Tim"],
    "2Tim": ["2 Timothy", "2 Tim"], "Titus": ["Titus"], "Phlm": ["Philemon"],
    "Heb": ["Hebrews", "Heb"], "Jas": ["James", "Jas"], "1Pet": ["1 Peter", "1 Pet"],
    "2Pet": ["2 Peter", "2 Pet"], "1John": ["1 John"], "2John": ["2 John"],
    "3John": ["3 John"], "Jude": ["Jude"], "Rev": ["Revelation", "Rev"]}
NAME = {n: code for code, ns in BOOKS.items() for n in ns}
BOOK_RE = re.compile(r"(?<![\w])(" + "|".join(sorted((re.escape(n) for n in NAME),
                                                      key=len, reverse=True)) + r")(?![a-z])")


class Canon:
    """chapter -> last verse, from the Berean text itself"""
    def __init__(self):
        self.last = {}

    def book(self, code):
        if code not in self.last:
            txt, _h = bsb(code)
            m = collections.defaultdict(int)
            for (c, v) in txt:
                m[c] = max(m[c], v)
            self.last[code] = dict(m)
        return self.last[code]


CANON = Canon()


def spans_in(text, problems):
    """Every reference in a string -> [(book, (c1, v1), (c2, v2)), ...]; a
    bare book -> (book, None, None). Unresolvable pieces go to problems."""
    out = []
    t = text.replace("–", "-").replace("—", " — ")
    ms = list(BOOK_RE.finditer(t))
    for i, m in enumerate(ms):
        code = NAME[m.group(1)]
        tail = t[m.end(): ms[i + 1].start() if i + 1 < len(ms) else len(t)]
        # the numbers that follow the book, up to anything that is not a
        # reference (a bracket, a letter)
        nm = re.match(r"^\s*([0-9][0-9:,;\-\s]*)", tail)
        if not nm:
            out.append((code, None, None))
            continue
        spec = nm.group(1).strip().rstrip(",;")
        chap_level = None
        for group in spec.split(";"):
            group = group.strip()
            if not group:
                continue
            cur_c = None
            parts = [p.strip() for p in group.split(",") if p.strip()]
            chap_level = ":" not in parts[0]
            for p in parts:
                try:
                    if ":" in p or (cur_c is not None and not chap_level):
                        if ":" in p:
                            a, _, b = p.partition("-")
                            c1, v1 = (int(x) for x in a.split(":"))
                            if b and ":" in b:
                                c2, v2 = (int(x) for x in b.split(":"))
                            else:
                                c2, v2 = c1, int(b) if b else v1
                            cur_c = c1
                        else:
                            a, _, b = p.partition("-")
                            c1 = c2 = cur_c
                            v1, v2 = int(a), int(b) if b else int(a)
                        out.append((code, (c1, v1), (c2, v2)))
                    else:
                        a, _, b = p.partition("-")
                        c1, c2 = int(a), int(b) if b else int(a)
                        last = CANON.book(code)
                        out.append((code, (c1, 1), (c2, last.get(c2, 0))))
                        cur_c = None
                except ValueError:
                    problems.append(f"unreadable reference '{m.group(1)} {p}' in: {text}")
    return out


def check(span, problems, where):
    code, a, b = span
    if a is None:
        return True
    last = CANON.book(code)
    ok = a[0] in last and b[0] in last and 1 <= a[1] <= last[a[0]] and 1 <= b[1] <= last[b[0]] \
        and a <= b
    if not ok:
        problems.append(f"{where}: {code} {a[0]}:{a[1]}-{b[0]}:{b[1]} is not in the Berean text")
    return ok


def label(span):
    code, a, b = span
    if a is None:
        return BOOKS[code][0]
    last = CANON.book(code)
    t = "Psalm" if code == "Ps" and a[0] == b[0] else BOOKS[code][0]
    if a[1] == 1 and b[1] == last.get(b[0]):
        return f"{t} {a[0]}" + (f"–{b[0]}" if b[0] != a[0] else "")
    if a == b:
        return f"{t} {a[0]}:{a[1]}"
    if a[0] == b[0]:
        return f"{t} {a[0]}:{a[1]}–{b[1]}"
    return f"{t} {a[0]}:{a[1]}–{b[0]}:{b[1]}"


ORDER = {code: i for i, code in enumerate(BOOKS)}


def ranges(verses):
    """verse ids -> passages in canon order, runs of consecutive verses
    merged: ['1Kgs.6.1', '1Kgs.6.2', ...] -> [{'label': '1 Kings 6:1–38', 'go': ...}]"""
    key = lambda v: (ORDER.get(v.split(".")[0], 99), int(v.split(".")[1]), int(v.split(".")[2]))  # noqa: E731
    out, run = [], []
    for v in sorted(set(verses), key=key):
        b, c, n = v.split(".")
        if run and run[-1][0] == b and run[-1][1] == int(c) and run[-1][2] == int(n) - 1:
            run.append((b, int(c), int(n)))
            continue
        if run:
            out.append(run)
        run = [(b, int(c), int(n))]
    if run:
        out.append(run)
    res = []
    for r in out:
        (b, c, v1), (_b, _c, v2) = r[0], r[-1]
        name = "Psalm" if b == "Ps" else BOOKS[b][0]
        res.append({"label": f"{name} {c}:{v1}" + (f"–{v2}" if v2 != v1 else ""),
                    "go": f"{name} {c}:{v1}", "verses": len(r)})
    return res


def verses_of(span):
    code, a, b = span
    if a is None or b[0] - a[0] + 1 > INDEX_CHAPTERS:
        return []
    last = CANON.book(code)
    out = []
    for c in range(a[0], b[0] + 1):
        lo = a[1] if c == a[0] else 1
        hi = b[1] if c == b[0] else last.get(c, 0)
        out += [f"{code}.{c}.{v}" for v in range(lo, hi + 1)]
    return out


def parse(problems, src=SRC, source="copilot"):
    if not src.exists():
        return []
    lines = src.read_text(encoding="utf-8").splitlines()
    themes, cur, state, concept, group = [], None, None, None, None
    for raw in lines:
        s = raw.strip()
        m = re.match(r"^THEME (\d+) — (.+)$", s)
        if m:
            n = int(m.group(1))
            cur = {"n": n, "id": THEME_ID[n], "title": m.group(2).strip(), "subtitle": None,
                   "concepts": [], "secondary": [], "links": [], "source": source}
            themes.append(cur)
            state, concept, group = "head", None, None
            continue
        if cur is None:
            continue
        if state == "head" and s and cur["subtitle"] is None and not s.startswith("Condensed"):
            cur["subtitle"] = s
            continue
        if s.startswith("A. Core Ontological Concepts"):
            state = "A"
            continue
        if s.startswith("B. Scriptural Support"):
            state = "B"
            continue
        if s.startswith("C. Secondary Ontological Concepts"):
            state = "C"
            continue
        if s.startswith("D. Suggested Ontology Linkages"):
            state = "D"
            continue
        if s.startswith("E. Optional Expansion"):
            state = None
            cur = None if cur["n"] == 21 else cur
            continue
        if not s or s.startswith(("Useful for", "(You can", "(Use these", "Canonical anchors",
                                  "These are the canonical", "Multiple passages",
                                  "Each concept is backed")):
            continue
        if state == "A":
            m = re.match(r"^(\d+)\. (.+)$", s)
            if m:
                cur["concepts"].append({"n": int(m.group(1)), "name": m.group(2).strip(),
                                        "passages": []})
        elif state == "B":
            m = re.match(r"^(\d+)\. (.+)$", s)
            if m:
                concept = next((c for c in cur["concepts"] if c["n"] == int(m.group(1))), None)
                group = None
                if concept is None:
                    problems.append(f"theme {cur['n']}: section B names concept {m.group(1)}, "
                                    f"not in section A")
                continue
            if s.startswith("*"):
                item = s.lstrip("* ").strip()
                note = None
                lab = None
                if " — " in item:
                    lab, item = item.split(" — ", 1)
                nm = re.match(r"^(.*?)\s*\((.*)\)\s*$", item)
                refs, note = (nm.group(1), nm.group(2)) if nm else (item, None)
                spans = spans_in(refs, problems)
                if not spans and note:          # "Noah (Gen 6–9)"
                    lab, spans, note = refs, spans_in(note, problems), None
                if not spans:
                    problems.append(f"theme {cur['n']} concept "
                                    f"{concept and concept['n']}: no reference in '{s}'")
                for sp in spans:
                    check(sp, problems, f"theme {cur['n']} concept {concept and concept['n']}")
                if concept is not None:
                    concept["passages"].append({"refs": spans, "note": requote(note),
                                                "label": lab, "group": group,
                                                **({"note_kjv": note}
                                                   if requote(note) != note else {})})
            else:
                # the list letter only ("B. Abrahamic Covenant"): lstrip("ABCDE. ")
                # strips characters, and took the A of Abrahamic and the D of
                # Davidic with it (found in the front-page audit, 2026-10-08)
                group = re.sub(r"^[A-E]\.\s+", "", s.rstrip(":")).strip()   # "Noahic Covenant", "Present"
        elif state == "C" and s.startswith("*"):
            item = s.lstrip("* ").strip()
            nm = re.match(r"^(.*?)\s*\((.*)\)\s*$", item)
            name, inside = (nm.group(1), nm.group(2)) if nm else (item, "")
            spans = spans_in(inside, problems)
            for sp in spans:
                check(sp, problems, f"theme {cur['n']} secondary '{name}'")
            cur["secondary"].append({"name": name.strip(), "refs": spans,
                                     "note": inside if not spans else None})
        elif state == "D" and s.startswith("*"):
            item = s.lstrip("* ").strip()
            nm = re.match(r"^(.*?)→\s*(.*?)\s*(?:\((.*)\))?$", item)
            if nm:
                target = nm.group(2).strip()
                cur["links"].append({"to_label": target, "note": nm.group(3),
                                     "to": LINK.get(target.lower())})
    return themes


# NODE TYPES a theme or concept may map to: things the text is about, not
# verses, passages, assessments or pattern records
NODE_TYPES = {"concept", "image", "title", "observance", "object", "covenant", "event",
              "being", "person", "group", "place", "creature"}
STOP = {"as", "of", "the", "and", "in", "to", "for", "through", "a", "an", "by", "over",
        "into", "with", "from", "not", "merely", "yet", "all", "its", "his", "god's", "gods",
        "between", "before", "under", "after", "new", "present", "future", "final"}
# when one phrase names several nodes, the kinds preferred, and how many
TYPE_ORDER = ["concept", "observance", "title", "covenant", "image", "object", "event",
              "being", "group", "place", "person", "creature"]
PER_PHRASE = 2
# people who are also books: an adjective on one names the book
BOOK_NAMES = {"daniel", "isaiah", "jeremiah", "ezekiel", "hosea", "joel", "amos", "obadiah",
              "jonah", "micah", "nahum", "habakkuk", "zephaniah", "haggai", "zechariah",
              "malachi", "ezra", "nehemiah", "esther", "joshua", "samuel", "matthew",
              "timothy", "titus", "philemon", "james", "peter", "jude"}
GENERIC = {"god", "lord", "man", "men", "people", "humanity", "human", "earth", "world",
           "life", "word", "things", "thing"}


def node_index():
    """name / aka -> entity ids, with and without a leading 'the', singular
    and plural: the graph's own names for things"""
    ix = collections.defaultdict(set)
    ents = {}
    for line in (ROOT / "ontology" / "entities" / "entities.jsonl").open(encoding="utf-8"):
        e = json.loads(line)
        if e.get("type") not in NODE_TYPES:
            continue
        ents[e["id"]] = e
        for n in [e.get("name")] + list(e.get("aka") or []):
            k = re.sub(r"[^a-z' ]", " ", (n or "").lower()).strip()
            k = re.sub(r"\s+", " ", k)
            if not k:
                continue
            for v in {k, re.sub(r"^the ", "", k)}:
                ix[v].add(e["id"])
                # singular and plural, only for words long enough that the
                # other form is the same word ("news" is not "new")
                if len(v) >= 5 and not v.endswith("ss"):
                    ix[v[:-1] if v.endswith("s") else v + "s"].add(e["id"])
    return ix, ents


_DEG = None


def _degrees():
    """record id -> how many relations touch it, over ontology/relations."""
    global _DEG
    if _DEG is None:
        _DEG = collections.Counter()
        for p in sorted((ROOT / "ontology" / "relations").glob("*.jsonl")):
            for line in open(p, encoding="utf-8"):
                if line.strip():
                    r = json.loads(line)
                    _DEG[r.get("src")] += 1
                    _DEG[r.get("dst")] += 1
    return _DEG


def map_nodes(name, ix, ents):
    """the existing graph nodes a theme or concept name speaks of: its
    longest phrases first, generic words ('God', 'humanity') only when
    nothing more specific matched"""
    words = [re.sub(r"'s$", "", w)          # "Christ's" is Christ, not a near match
             for w in re.sub(r"[^a-z' ]", " ", name.lower().replace("’", "'")).split()]
    found, used = [], set()
    for size in (4, 3, 2, 1):
        for i in range(len(words) - size + 1):
            span = words[i:i + size]
            if set(range(i, i + size)) & used or span[0] in STOP or span[-1] in STOP:
                continue
            k = " ".join(span)
            if size == 1 and k in GENERIC:
                continue
            hit, near = ix.get(k), None
            # a longer word built on a node's name: "Melchizedekian" ->
            # Melchizedek (single words, the node's name 6+ letters). A NEAR
            # match, marked so, for discussion: "Priesthood" -> "the priests"
            # is a group of people, not the institution
            if not hit and size == 1 and len(k) >= 8:
                stem = max((x for x in ix if " " not in x and len(x) >= 6 and k.startswith(x)),
                           key=len, default=None)
                # an adjective on a name that is also a BOOK names the book:
                # "Danielic Figure" is Daniel 7's figure, and was wired to
                # Daniel the man (the 2026-10-02 evaluation, N-D14)
                hit = ix.get(stem) if stem and stem not in BOOK_NAMES else None
                near = f"{k} -> {stem}" if hit else None
            if hit:
                # A CAPITALISED PHRASE IS A NAME: "Son of Man" in a concept's
                # name is the title, not Job's lowercase "the son of man, who
                # is but a worm" (Job 25:6), which shares the words. Where the
                # source capitalises the phrase and some hits are named with
                # it capitalised, the lowercase ones go (M-D10).
                pat = re.compile(r"\b" + r"\W+".join(map(re.escape, span)) + r"\b", re.I)
                cap = pat.search(name)
                if cap and cap.group(0)[:1].isupper() and len(span) > 1:
                    # by its first letter only ("the Son of man" is the title
                    # too), and in any name the record answers to (Jesus is
                    # "the Son of God" by alias)
                    named = {x for x in hit
                             if any(m.group(0)[:1].isupper()
                                    for n in [ents[x]["name"]] + list(ents[x].get("aka") or [])
                                    for m in pat.finditer(n))}
                    if named:
                        hit = named
                used |= set(range(i, i + size))
                # ONE RECORD PER KIND OF A SHARED NAME, the one the graph holds
                # most on. In id order, "Kingdom Manifested Through Jesus"
                # attached to Jesus Justus (Col 4:11) beside Jesus of
                # Nazareth -- found 2026-10-02 when the duplicate "Jesus
                # Christ" record that had held the second slot was merged.
                deg = _degrees()
                ids = sorted(hit, key=lambda x: (TYPE_ORDER.index(ents[x]["type"])
                                                 if ents[x]["type"] in TYPE_ORDER else 99,
                                                 -deg.get(x, 0) if ents[x]["type"] == "person"
                                                 else 0, x))
                # people only: tried for every kind, it moved 26 theme links
                # beyond the Jesus fix (concepts sharing a name with another
                # concept), which is a wider change than this one
                seen_person = False
                keep = []
                for x in ids:
                    if ents[x]["type"] == "person":
                        if seen_person:
                            continue
                        seen_person = True
                    keep.append(x)
                ids = keep
                for eid in ids[:PER_PHRASE]:
                    if any(f["id"] == eid for f in found):
                        continue
                    e = ents[eid]
                    found.append({"id": eid, "name": e["name"], "type": e["type"], "matched": k,
                                  "near": near})
    return found


def main():
    """the map as published (a redone outline only once its theme is listed in
    theme-homes.json "outlines_shown"), and the preview with every redone
    outline, which the server reads only with BIBLEONT_SHOW_UNREVIEWED"""
    homes = json.loads((ROOT / "ontology" / "themes" / "theme-homes.json").read_text(encoding="utf-8"))
    build(set(homes.get("outlines_shown") or []), "theme-map.json", docs=True)
    build(None, "theme-map-preview.json", docs=False)


def build(redone_ok, out_name, docs):
    problems = []
    themes = parse(problems) + parse(problems, SITE_SRC, "site")
    # AN OUTLINE REDONE IN THE TEXTS' WORDS (plan 7.6c, 2026-10-08) replaces
    # Copilot's for its theme: the concepts, secondary concepts and links;
    # the theme, its table and its front page are unchanged. Copilot's stays
    # in copilot-major-themes.md, verbatim, and is credited where shown.
    if REDONE_SRC.exists():
        # theme 21, Copilot's second Covenant outline, shares the id
        # "covenant": the redone outline replaces theme 4, never it
        by_id = {t["id"]: t for t in themes if t["n"] != 21}
        for r in parse(problems, REDONE_SRC, "redone"):
            if r["id"] in by_id and (redone_ok is None or r["id"] in redone_ok):
                t = by_id[r["id"]]
                for k in ("concepts", "secondary", "links", "subtitle"):
                    t[k] = r[k]
                t["outline"] = "redone"
    ix, ents = node_index()
    for t in themes:
        # THE TRINITY THEME MAPS TO NO NODE BY NAME: its concepts name the
        # Father, the Son and the Spirit, and a divine person's card is joined
        # or relabelled only by the owner's hand (decided: the Trinity is not
        # to be modelled either way)
        skip = t["id"] == "trinity"
        parts = [p.strip() for p in re.split(r"[/&()]", t["title"]) if p.strip()]
        t["nodes"] = [] if skip else [n for p in parts for n in map_nodes(p, ix, ents)]
        for c in t["concepts"]:
            c["nodes"] = [] if skip else map_nodes(c["name"], ix, ents)
        for s in t["secondary"]:
            s["nodes"] = [] if skip else map_nodes(s["name"].split("→")[-1], ix, ents)
    base = {t["id"]: t for t in themes if t["n"] != 21}
    ext = next((t for t in themes if t["n"] == 21), None)
    # Copilot's second Covenant outline retires with the first once the theme
    # is redone: the one redone outline takes what held from both (7.6c)
    if ext and base["covenant"].get("outline") != "redone":
        base["covenant"]["synthesis"] = {k: ext[k] for k in ("title", "subtitle", "concepts",
                                                               "secondary", "links")}
    # every verse a theme's passages mark (passages up to INDEX_CHAPTERS long)
    marks = collections.defaultdict(list)
    cites = collections.defaultdict(set)          # theme -> verses it cites SPECIFICALLY
    for t in base.values():
        blocks = [("", t)] + ([("synthesis", t["synthesis"])] if t.get("synthesis") else [])
        for part, blk in blocks:
            for c in blk["concepts"]:
                for p in c["passages"]:
                    for sp in p["refs"]:
                        vs = verses_of(sp)
                        for v in vs:
                            marks[v].append([t["id"], c["n"], part])
                        # GROUNDING needs a passage cited for what it says, not
                        # a verse swept up in a long span: Creation cites 1 Kings
                        # 6–8 (the temple), which put 1 Kings 8:46 ("no one who
                        # does not sin") under Creation and "grounded" Creation ->
                        # Sin by accident. Nothing should exist without
                        # Biblical backup -- so only passages of GROUND_MAX
                        # verses or fewer count toward a link.
                        if len(vs) <= GROUND_MAX:
                            cites[t["id"]].update(vs)
    # the corpus clause tags, by verse (medium or better): the second ground
    # for a link between themes
    tagged = collections.defaultdict(set)
    for l in gzip.open(OUT / "clause-tags.jsonl.gz", "rt", encoding="utf-8"):
        if '"kind": "stamp"' not in l:
            continue
        r = json.loads(l)
        if r.get("weight", 0) >= 0.67:
            tagged[re.sub(r"_ev$", "", r["tag"])].add(r["clause"].split("#")[0])
    stamp_count = {s: len(v) for s, v in tagged.items()}
    by_theme_tags = {tid: set().union(*(tagged.get(s, set()) for s in ss)) if ss else set()
                     for tid, ss in STAMPS.items()}
    ungrounded = []
    for t in base.values():
        t["stamps"] = [{"id": s, "verses": stamp_count.get(s, 0)} for s in STAMPS.get(t["id"], [])
                       if stamp_count.get(s)]
        for blk in [t] + ([t["synthesis"]] if t.get("synthesis") else []):
            for c in blk["concepts"]:
                c["grounded"] = any(p["refs"] for p in c["passages"])
                if not c["grounded"]:
                    ungrounded.append((t, "concept", c["name"], "no passage given"))
            for s in blk["secondary"]:
                s["grounded"] = bool(s["refs"])
                if not s["grounded"]:
                    ungrounded.append((t, "secondary", s["name"], "no passage in its brackets"))
            for ln in blk["links"]:
                o = ln["to"]
                shared = sorted(cites[t["id"]] & cites.get(o, set())) if o else []
                both = sorted(by_theme_tags.get(t["id"], set()) & by_theme_tags.get(o, set())) \
                    if o and o != t["id"] else []
                ln["shared_passages"] = ranges(shared)[:8]
                ln["shared_count"] = len(shared)
                ln["tagged_both"] = len(both)
                ln["tagged_examples"] = both[:6]
                ln["grounded"] = bool(shared) or len(both) >= CO_TAGS
                ln["grounded_by"] = ("a passage both themes cite" if shared else
                                     "verses the clause tags give both" if len(both) >= CO_TAGS
                                     else None)
                if not ln["grounded"]:
                    why = ("not a theme on this map" if not o else
                           "no passage cited by both, and the clause tags give both to "
                           f"{len(both)} verse(s)")
                    ungrounded.append((t, "link", f"{t['title'].title()} → {ln['to_label']}", why))
    def jsonable(t):
        def fix(x):
            if isinstance(x, tuple) and len(x) == 3 and isinstance(x[0], str):
                return {"book": x[0], "start": x[1], "end": x[2], "label": label(x),
                        "id": f"{x[0]}.{x[1][0]}.{x[1][1]}" if x[1] else None}
            if isinstance(x, dict):
                return {k: fix(v) for k, v in x.items()}
            if isinstance(x, list):
                return [fix(v) for v in x]
            return x
        return fix(t)

    order = [base[THEME_ID[n]] for n in range(1, 21)] + \
        [base[THEME_ID[n]] for n in range(22, 26) if THEME_ID[n] in base]
    # node -> the themes and concepts that map to it, for the node's own card
    by_node = collections.defaultdict(list)
    for t in order:
        for nd in t["nodes"]:
            by_node[nd["id"]].append({"theme": t["id"], "concept": None})
        for c in t["concepts"]:
            for nd in c["nodes"]:
                by_node[nd["id"]].append({"theme": t["id"], "concept": c["name"]})
    out = {"_source": f"{SOURCE}. Harvested by Doug Egge, 2026-09-29; "
                      "ontology/themes/copilot-major-themes.md, verbatim.",
           "_note": "The major-theme map, parsed and checked by tools/themes/theme_map.py. "
                    "Each reference resolved against the Berean text; each relationship "
                    "marked grounded (and how) or not; each theme and concept mapped to the "
                    "graph's existing nodes where one exists.",
           "themes": [jsonable(t) for t in order],
           "verses": dict(marks),
           "by_node": dict(by_node),
           "problems": problems}
    # THE NODES: which themes and concepts the graph already has a node for,
    # and which it does not. 2026-09-29: map to concepts that
    # already exist in the graph; where there is no existing node, note it.
    g = ["# The major themes against the graph's existing nodes",
         "",
         "Made by `tools/themes/theme_map.py`. Each theme and core concept of the Microsoft "
         "Copilot theme map, matched by name (and the graph's own alternative names) to nodes "
         "that already exist in `ontology/entities/entities.jsonl`. Nothing was created. "
         "2026-09-29: where there is no existing node, a note is made of it.",
         ""]
    no_theme = [(t, p) for t in order for p in [x.strip() for x in re.split(r"[/&()]", t["title"])
                                                 if x.strip()]
                if not map_nodes(p, ix, ents)]
    no_conc = [(t, c) for t in order for c in t["concepts"] if not c["nodes"]]
    g += [f"**Themes: {sum(1 for t in order if t['nodes'])} of {len(order)} map to at least one "
          f"node. Theme names with no node: {len(no_theme)}. Core concepts with no node: "
          f"{len(no_conc)} of {sum(len(t['concepts']) for t in order)}.**", "",
          "## Theme names with no existing node — for discussion", ""]
    g += [f"- {t['title'].title()}: **{p.title()}**" for t, p in no_theme] or ["- none"]
    g += ["", "## Core concepts with no existing node — for discussion", ""]
    for t in order:
        miss = [c for tt, c in no_conc if tt is t]
        if miss:
            g.append(f"- **{t['title'].title()}**: " + "; ".join(c["name"] for c in miss))
    nears = sorted({n["near"] for t in order for n in t["nodes"] + [x for c in t["concepts"]
                                                                  for x in c["nodes"]]
                    if n.get("near")})
    g += ["", "## Near matches — a word built on a node's name, for discussion", ""]
    g += [f"- {x}" for x in nears] or ["- none"]
    fmt = lambda n: f"{n['name']} ({n['type']}{', near' if n.get('near') else ''})"  # noqa: E731
    g += ["", "## What each theme maps to", ""]
    for t in order:
        g.append(f"### {t['n']}. {t['title'].title()}")
        g.append("- theme: " + (", ".join(fmt(n) for n in t["nodes"]) or "**no node**"))
        for c in t["concepts"]:
            g.append(f"- {c['n']}. {c['name']}: " + (", ".join(fmt(n) for n in c["nodes"])
                                                     or "**no node**"))
        g.append("")
    if docs:
        (ROOT / "docs" / "review" / "THEMES-GRAPH-MAP.md").write_text("\n".join(g) + "\n",
                                                                       encoding="utf-8")
    print(f"graph: themes with a node {sum(1 for t in order if t['nodes'])}/{len(order)}; "
          f"theme names without {len(no_theme)}; concepts without "
          f"{len(no_conc)}/{sum(len(t['concepts']) for t in order)}")
    (OUT / out_name).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    # the list for Copilot
    lines = ["# Theme-map relationships without scripture — for Microsoft Copilot",
             "",
             "Made by `tools/themes/theme_map.py` from the major-theme map "
             "(ontology/themes/copilot-major-themes.md, Microsoft Copilot). 2026-09-29: "
             "a list is given to Copilot of those that cannot be grounded from the graph or "
             "deterministically, to provide scripture for, so that a reader can reference some "
             "scripture and not just take Copilot's word for it.",
             "",
             "A link between two themes is grounded here when a passage is cited under BOTH themes, "
             f"or when the corpus clause tags give both themes' stamps to {CO_TAGS}+ of the same "
             "verses. The ones below are neither. Suggested question for Copilot, per line: "
             "*which passages show this relationship?*",
             ""]
    by = collections.defaultdict(list)
    for t, kind, what, why in ungrounded:
        by[t["n"]].append((kind, what, why))
    for n in sorted(by):
        t = base[THEME_ID[n]] if n != 21 else base["covenant"]
        lines.append(f"## Theme {n} — {t['title'].title()}")
        for kind, what, why in by[n]:
            lines.append(f"- {kind}: **{what}** — {why}")
        lines.append("")
    if problems:
        lines += ["## References the Berean text does not have, or that could not be read", ""]
        lines += [f"- {p}" for p in problems]
    if docs:
        (ROOT / "docs" / "review" / "THEMES-UNGROUNDED.md").write_text("\n".join(lines) + "\n",
                                                                         encoding="utf-8")
    print(f"-- {out_name}")
    nconc = sum(len(t["concepts"]) for t in base.values())
    npas = sum(len(p["refs"]) for t in base.values() for c in t["concepts"] for p in c["passages"])
    nlinks = sum(len(t["links"]) for t in base.values())
    gl = sum(ln["grounded"] for t in base.values() for ln in t["links"])
    print(f"{len(base)} themes (+ the covenant synthesis), {nconc} core concepts, {npas} references, "
          f"{len(marks):,} verses marked")
    print(f"links {nlinks}: grounded {gl}, not {nlinks - gl}; ungrounded items {len(ungrounded)}; "
          f"problems {len(problems)}")
    for p in problems[:25]:
        print("  !", p)


if __name__ == "__main__":
    main()
