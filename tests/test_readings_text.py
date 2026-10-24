"""The site-voice text of what two verses share (ontology/allusions.jsonl, plan
6.17), held to what the checks of 2026-10-04 established, on every push.

2026-10-04: the owner can only spot-check this work, and it is released to the
public frequently, so the checks must be vigilant. So what was checked by hand once is checked by machine every time:

  - every row has a known kind; a shared image names its node; only a story
    told again carries beats
  - every quotation in an explanation is the Berean's words, found in a verse
    the sentence cites (a bare "8:8" read in every book its sentence names --
    "Hebrews quotes Jer 31:31 outright at 8:8" means Heb 8:8) or in either
    verse's chapter
  - every beat's words stand in the verse it names
  - outside quotation marks, the site never says a text fulfils, foreshadows,
    predicts or prefigures anything, and uses no prophetic-scheme term the
    verses themselves do not (structure yes, doctrine no)
  - no reader is named (readings are "a reader's")
  - references from the letters (6.21): the letter's words in the verse the
    row names, the account's words in its verse, a known certainty
    ("apparent" only with its fixed reason, and no sentence), the same voice
    rules. Its first run caught 5 rows pointing at the wrong verse; proven
    with 4 planted faults (BIBLEONT_LETTERS), all caught, 2026-10-05
  - references from the psalms and poems (6.19): the same checks, the poem's
    span in place of the letter's (BIBLEONT_POEMS)

Data only, about two seconds. Run: python tests/test_readings_text.py"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
V = {}
for line in (ROOT / "data" / "bible" / "verses.bsb.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        d = json.loads(line)
        if "b" in d:
            V[f"{d['b']} {d['c']}:{d['v']}"] = d["t"]
CHAP = {}
for k, t in V.items():
    CHAP.setdefault(k.rsplit(":", 1)[0], []).append(t)
CHAP = {k: " ".join(v) for k, v in CHAP.items()}

NAMES = {"Genesis": "Gen", "Exodus": "Exod", "Leviticus": "Lev", "Numbers": "Num", "Deuteronomy": "Deut",
         "Psalm": "Ps", "Psalms": "Ps", "Proverbs": "Prov", "Isaiah": "Isa", "Jeremiah": "Jer",
         "Ezekiel": "Ezek", "Daniel": "Dan", "Hosea": "Hos", "Zechariah": "Zech", "Habakkuk": "Hab",
         "Nahum": "Nah", "Malachi": "Mal", "Matthew": "Matt", "Romans": "Rom", "Galatians": "Gal",
         "Ephesians": "Eph", "Hebrews": "Heb", "James": "Jas", "Revelation": "Rev", "Stephen": "Acts",
         "2 Corinthians": "2Cor", "1 Corinthians": "1Cor", "1 Peter": "1Pet", "2 Peter": "2Pet",
         "2 Kgs": "2Kgs", "1 Kgs": "1Kgs", "1 Cor": "1Cor", "2 Cor": "2Cor", "1 Pet": "1Pet",
         "2 Pet": "2Pet", "2 Chr": "2Chr", "1 Thess": "1Thess", "1 Sam": "1Sam", "2 Sam": "2Sam"}
BOOKS = sorted({k.rsplit(" ", 1)[0] for k in V}, key=len, reverse=True)
TOK = re.compile(r"(" + "|".join(re.escape(n) for n in sorted(NAMES, key=len, reverse=True)) + "|"
                 + "|".join(re.escape(b) for b in BOOKS) + r")\b|(?<![\w:])(\d+):(\d+)(?:\s*[-–]\s*(\d+))?")
# the site's own voice, outside quotation marks (a quoted "to fulfill what was
# spoken" is the text's claim, and fine)
VOICE = re.compile(r"\b(fulfil\w*|fulfill\w*|foreshadow\w*|predict\w*|prefigur\w*|antitype\w*|"
                   r"rapture|millenni\w*|tribulation|dispensation\w*|end times|antichrist)\b", re.I)
READERS = re.compile(r"\bDoug\b|\bEgge\b")


def refs(text, default):
    out = set()
    for sent in re.split(r"(?<=[.;])\s+", text):
        books = [default]
        for m in TOK.finditer(sent):
            if m.group(1):
                b = NAMES.get(m.group(1), m.group(1))
                if b not in books:
                    books.append(b)
                continue
            c, v1, v2 = int(m.group(2)), int(m.group(3)), m.group(4)
            for book in books:
                for v in range(v1, (int(v2) if v2 else v1) + 1):
                    if f"{book} {c}:{v}" in V:
                        out.add(f"{book} {c}:{v}")
    return out


def norm(s):
    words = re.sub(r"[^a-z' ]", " ", s.lower().replace("’", "'").replace("‘", "'")).split()
    return " " + " ".join(w.strip("'") for w in words if w.strip("'")) + " "


# A QUOTATION IN SINGLE QUOTES (2026-10-07: 192 table lines quoted 'so', and
# neither check read them): opened after a space or a bracket, closed before
# punctuation or a space; an apostrophe between two letters ("devil's") is
# inside the quotation, not its end
SQ = re.compile(r"(?:^|(?<=[\s(\[;:,—–]))'((?:[^'\n]|(?<=[A-Za-z])'(?=[A-Za-z]))+?)'(?=[\s.,;:)\]!?—–]|$)")


def quoted(s):
    """every quotation in a line: double, curly or single quotes"""
    return re.findall(r"“([^“”]*?)”", s) + re.findall(r"\"([^\"“”]*?)\"", s) + SQ.findall(s)


def unquoted(s):
    return SQ.sub(" ", re.sub(r"“[^“”]*”|\"[^\"]*\"", " ", s))


fails = []
# BIBLEONT_ALLUSIONS points the check at another file -- how it was proven to
# fail: one planted fault of each kind, every one caught (journal 2026-10-04)
SRC = Path(__import__("os").environ.get("BIBLEONT_ALLUSIONS") or ROOT / "ontology" / "allusions.jsonl")
rows = [json.loads(l) for l in open(SRC, encoding="utf-8") if l.strip()]
for r in rows:
    tag = f"{r.get('nt')} -> {r.get('ot')}"
    if r.get("nt") not in V or r.get("ot") not in V:
        fails.append(f"{tag}: a verse that is not in the Berean")
        continue
    k = r.get("kind")
    if k not in ("words_taken_up", "shared_image", "story_echo"):
        fails.append(f"{tag}: kind {k!r}")
    if (k == "shared_image") != bool(r.get("node")):
        fails.append(f"{tag}: a node is named exactly when the kind is a shared image")
    if (k == "story_echo") != bool(r.get("beats")):
        fails.append(f"{tag}: beats are given exactly when the kind is a story told again")
    ex = r.get("explanation") or ""
    if not ex.strip():
        fails.append(f"{tag}: no explanation")
    pool = [norm(V[x]) for x in refs(ex, r["nt"].rsplit(" ", 1)[0])]
    pool += [norm(CHAP[r["nt"].rsplit(":", 1)[0]]), norm(CHAP[r["ot"].rsplit(":", 1)[0]])]
    qs = re.findall(r"“([^“”]*?)”", ex) + re.findall(r"\"([^\"“”]*?)\"", ex)
    for q in (q for q in qs if len(q) >= 6):
        for piece in re.split(r"\.\.\.|…", q):
            p = norm(piece)
            if len(p.split()) >= 2 and not any(p in t for t in pool):
                fails.append(f"{tag}: quotation not found in a verse it cites: {piece.strip()!r}")
    for pair in r.get("beats") or []:
        for ref, words in pair:
            if norm(words) not in norm(V.get(ref, "")):
                fails.append(f"{tag}: beat {words!r} is not in {ref}")
    for text in (unquoted(ex), r.get("node") or ""):
        m = VOICE.search(text)
        if m:
            fails.append(f"{tag}: the site's own voice says {m.group(0)!r}")
    if READERS.search(ex + " " + (r.get("node") or "")):
        fails.append(f"{tag}: names a reader")

# stories told again (plan 6.18, ontology/told-again.jsonl): every step in its
# verse inside its passage, every quotation in one of the two passages, no
# word claiming intent unless the later text names the earlier story
ORDER = list(V)
POS = {k: i for i, k in enumerate(ORDER)}
SOFT = re.compile(r"\b(recall\w*|echo\w*|allud\w*|allusion\w*|draws? on|evok\w*|mirror\w*|re-?enact\w*)\b", re.I)
TOLD = Path(__import__("os").environ.get("BIBLEONT_TOLD") or ROOT / "ontology" / "told-again.jsonl")
told = [json.loads(l) for l in open(TOLD, encoding="utf-8") if l.strip()] if TOLD.exists() else []
for r in told:
    tag = f"told again {r.get('later')} / {r.get('earlier')}"
    rng = (r["later_range"], r["earlier_range"])
    if not all(a in POS and b in POS for a, b in rng):
        fails.append(f"{tag}: a passage outside the Berean")
        continue
    pool = [norm(V[k]) for a, b in rng for k in ORDER[POS[a]:POS[b] + 1]]
    if len(r.get("beats") or []) < 3:
        fails.append(f"{tag}: fewer than three steps")
    for pair in r.get("beats") or []:
        for (ref, words), (a, b) in zip(pair, rng):
            if not (ref in POS and POS[a] <= POS[ref] <= POS[b] and norm(words) in norm(V[ref])):
                fails.append(f"{tag}: step {words!r} is not in {ref}")
    text = " ".join(t for t in (r.get("explanation"), r.get("differs")) if t)
    for q in re.findall(r"“([^“”]*?)”", text) + re.findall(r"\"([^\"“”]*?)\"", text):
        for piece in re.split(r"\.\.\.|…", q):
            p = norm(piece)
            if len(q) >= 6 and len(p.split()) >= 2 and not any(p in t for t in pool):
                fails.append(f"{tag}: quotation not in either passage: {piece.strip()!r}")
    m = VOICE.search(unquoted(text)) or (None if r.get("named") else SOFT.search(unquoted(text)))
    if m:
        fails.append(f"{tag}: the site's own voice says {m.group(0)!r}")
    if READERS.search(text):
        fails.append(f"{tag}: names a reader")

# references from the letters (plan 6.21, ontology/letter-references.jsonl):
# the letter's words in its span, the account's words in its verse, every
# quotation in a sentence from the chapters involved, a known certainty --
# "apparent" only with its fixed reason -- and the same voice rules
sys.path.insert(0, str(ROOT / "tools" / "themes"))
from theme_map import BOOKS as _BK  # noqa: E402
FULL = {n: code for code, names in _BK.items() for n in names}
FULL.update({c: c for c in _BK})


def bsb(ref):
    """'Heb.11.7' or 'Genesis 7:1' or 'Genesis 7:1-3' -> ['Gen 7:1', ...]"""
    m = re.match(r"^\s*([1-3]?\s?[A-Za-z ]+?)[ .](\d+)[:.](\d+)(?:\s*[-–]\s*(\d+))?\s*$", ref or "")
    if not m or m.group(1).strip() not in FULL:
        return []
    b, c, v1, v2 = FULL[m.group(1).strip()], int(m.group(2)), int(m.group(3)), m.group(4)
    return [f"{b} {c}:{v}" for v in range(v1, (int(v2) if v2 else v1) + 1) if f"{b} {c}:{v}" in V]


LET = Path(__import__("os").environ.get("BIBLEONT_LETTERS") or ROOT / "ontology" / "letter-references.jsonl")
letters = [json.loads(l) for l in open(LET, encoding="utf-8") if l.strip()] if LET.exists() else []
# references from the psalms and poems (plan 6.19, ontology/poem-references.jsonl):
# the same checks, the poem's span in place of the letter's (BIBLEONT_POEMS)
POE = Path(__import__("os").environ.get("BIBLEONT_POEMS") or ROOT / "ontology" / "poem-references.jsonl")
poems = [json.loads(l) for l in open(POE, encoding="utf-8") if l.strip()] if POE.exists() else []
# between the prophets and events (plan 6.20, ontology/prophet-references.jsonl):
# the same checks, the prophet's span in place of the letter's, and one of the
# plan's three kinds kept apart (BIBLEONT_PROPHETS). A forward link's sentence
# says only what the later text says: "fulfil" in the site's own voice is the
# VOICE rule's, so a sentence may carry it only inside the later text's quotation
PRO = Path(__import__("os").environ.get("BIBLEONT_PROPHETS") or ROOT / "ontology" / "prophet-references.jsonl")
prophets = [json.loads(l) for l in open(PRO, encoding="utf-8") if l.strip()] if PRO.exists() else []
for r in prophets:
    if r.get("kind") not in ("back", "own_time", "forward"):
        fails.append(f"prophet {r.get('prophet')}: kind {r.get('kind')!r} is not one of the plan's three")
for kind, r in [("letter", r) for r in letters] + [("poem", r) for r in poems] + [("prophet", r) for r in prophets]:
    tag = f"{kind} {r.get(kind)}"
    a, b = (bsb(x) for x in r.get(kind) or ["", ""])
    if not (a and b and POS[a[0]] <= POS[b[0]]):
        fails.append(f"{tag}: a span outside the Berean")
        continue
    span = ORDER[POS[a[0]]:POS[b[0]] + 1]
    acc = bsb(r.get("account_verse"))
    if not acc:
        fails.append(f"{tag}: account verse {r.get('account_verse')!r} is not in the Berean")
        continue
    if norm(r.get("distinctive", "")) not in norm(" ".join(V[k] for k in span)):
        fails.append(f"{tag}: the {kind}'s words are not in it: {r.get('distinctive')!r}")
    if norm(r.get("account_words", "")) not in norm(" ".join(V[k] for k in acc)):
        fails.append(f"{tag}: the account's words are not in {r.get('account_verse')}: {r.get('account_words')!r}")
    if r.get("certainty") not in ("clear", "apparent") or \
            (r.get("certainty") == "apparent") != (r.get("apparent_reason") in ("disputed", "thin")):
        fails.append(f"{tag}: certainty {r.get('certainty')!r} / reason {r.get('apparent_reason')!r}")
    why = r.get("why") or ""
    if r.get("certainty") == "apparent" and why:
        fails.append(f"{tag}: an apparent reference carries a sentence (only its fixed reason is shown)")
    chaps = {k.rsplit(":", 1)[0] for k in span + acc}
    pool = [norm(CHAP[c]) for c in chaps] + [norm(V[x]) for x in refs(why, acc[0].rsplit(" ", 1)[0])]
    for q in re.findall(r"“([^“”]*?)”", why) + re.findall(r"\"([^\"“”]*?)\"", why):
        for piece in re.split(r"\.\.\.|…", q):
            p = norm(piece)
            if len(q) >= 6 and len(p.split()) >= 2 and not any(p in t for t in pool):
                fails.append(f"{tag}: quotation not in the chapters it involves: {piece.strip()!r}")
    m = VOICE.search(unquoted(why))
    if m:
        fails.append(f"{tag}: the site's own voice says {m.group(0)!r}")
    if READERS.search(why):
        fails.append(f"{tag}: names a reader")

# Revelation's links to the rest of Scripture (plan 6.22, ontology/
# revelation-links.jsonl): one of the four kinds; Revelation's words in its
# span and the other passage's in its own (or the verse after, where a
# quotation runs on); the two spans never the same verse; "apparent" only with
# its fixed reason and never with a sentence; every quotation in a sentence
# from one of the two passages; and the voice rules (BIBLEONT_REVELATION)
REVL = Path(__import__("os").environ.get("BIBLEONT_REVELATION") or ROOT / "ontology" / "revelation-links.jsonl")
revel = [json.loads(l) for l in open(REVL, encoding="utf-8") if l.strip()] if REVL.exists() else []
dot = lambda k: (lambda b, c, v: f"{b} {c}:{v}")(*k.split("."))
for r in revel:
    tag = f"revelation {r.get('rev')} / {r.get('other')}"
    if r.get("kind") not in ("words", "image", "names", "key"):
        fails.append(f"{tag}: kind {r.get('kind')!r}")
    try:
        rs = ORDER[POS[dot(r["rev"][0])]:POS[dot(r["rev"][1])] + 2]
        os_ = ORDER[POS[dot(r["other"][0])]:POS[dot(r["other"][1])] + 2]
    except (KeyError, IndexError, TypeError, ValueError):
        fails.append(f"{tag}: a span outside the Berean")
        continue
    if not r["rev"][0].startswith("Rev."):
        fails.append(f"{tag}: the Revelation side is not in Revelation")
    if set(rs[:-1]) & set(os_[:-1]):
        fails.append(f"{tag}: a verse linked to itself")
    if norm(r.get("rev_words", "")) not in norm(" ".join(V[k] for k in rs)):
        fails.append(f"{tag}: Revelation's words are not in it: {r.get('rev_words')!r}")
    if norm(r.get("other_words", "")) not in norm(" ".join(V[k] for k in os_)):
        fails.append(f"{tag}: the other passage's words are not in it: {r.get('other_words')!r}")
    if r.get("certainty") not in ("clear", "apparent") or \
            (r.get("certainty") == "apparent") != (r.get("apparent_reason") in ("disputed", "thin")):
        fails.append(f"{tag}: certainty {r.get('certainty')!r} / reason {r.get('apparent_reason')!r}")
    why = r.get("why") or ""
    if r.get("certainty") == "apparent" and why:
        fails.append(f"{tag}: an apparent link carries a sentence (only its fixed reason is shown)")
    pool = [norm(" ".join(V[k] for k in rs)), norm(" ".join(V[k] for k in os_))]
    for q in re.findall(r"“([^“”]*?)”", why) + re.findall(r"\"([^\"“”]*?)\"", why):
        for piece in re.split(r"\.\.\.|…", q):
            p = norm(piece)
            if len(q) >= 6 and len(p.split()) >= 2 and not any(p in t for t in pool):
                fails.append(f"{tag}: quotation not in either passage: {piece.strip()!r}")
    m = VOICE.search(unquoted(why))
    if m:
        fails.append(f"{tag}: the site's own voice says {m.group(0)!r}")
    if READERS.search(why):
        fails.append(f"{tag}: names a reader")

# The history books and the passages before them (plan 6.23, ontology/
# history-links.jsonl): one of the four kinds; the later side in Genesis-
# Esther and before the earlier side never; each side's words in its own span
# (or the verse after); the spans never overlapping; certainty clear or
# apparent; `reach` and `quiet` as the rule says (nearby = same book, 0-5
# chapters; quiet = nearby and alone); and every group's label true by
# counting -- its number is the links in it (BIBLEONT_HISTORY)
HISTL = Path(__import__("os").environ.get("BIBLEONT_HISTORY") or ROOT / "ontology" / "history-links.jsonl")
hist = [json.loads(l) for l in open(HISTL, encoding="utf-8") if l.strip()] if HISTL.exists() else []
HISTORY_BOOKS = {"Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth", "1Sam", "2Sam", "1Kgs", "2Kgs",
                 "1Chr", "2Chr", "Ezra", "Neh", "Esth"}
gcount = __import__("collections").Counter(r["group"]["id"] for r in hist if r.get("group"))
gthings = __import__("collections").defaultdict(set)
for r in hist:
    if r.get("group"):
        gthings[r["group"]["id"]].add(" ".join(re.findall(r"[a-z]+", r.get("later_words", "").lower())))
for r in hist:
    tag = f"history {r.get('later')} / {r.get('earlier')}"
    if r.get("kind") not in ("back", "fulfilled", "carried_out", "quotes"):
        fails.append(f"{tag}: kind {r.get('kind')!r}")
    try:
        ls = ORDER[POS[dot(r["later"][0])]:POS[dot(r["later"][1])] + 2]
        es = ORDER[POS[dot(r["earlier"][0])]:POS[dot(r["earlier"][1])] + 2]
    except (KeyError, IndexError, TypeError, ValueError):
        fails.append(f"{tag}: a span outside the Berean")
        continue
    if r["later"][0].split(".")[0] not in HISTORY_BOOKS:
        fails.append(f"{tag}: the later side is not in Genesis-Esther")
    if set(ls[:-1]) & set(es[:-1]):
        fails.append(f"{tag}: the two passages overlap")
    if norm(r.get("later_words", "")) not in norm(" ".join(V[k] for k in ls)):
        fails.append(f"{tag}: the later passage's words are not in it: {r.get('later_words')!r}")
    if norm(r.get("earlier_words", "")) not in norm(" ".join(V[k] for k in es)):
        fails.append(f"{tag}: the earlier passage's words are not in it: {r.get('earlier_words')!r}")
    if r.get("certainty") not in ("clear", "apparent"):
        fails.append(f"{tag}: certainty {r.get('certainty')!r}")
    lb, lc = r["later"][0].split(".")[:2]
    eb, ec = r["earlier"][0].split(".")[:2]
    reach = "across books" if lb != eb else "within the book" if int(lc) - int(ec) > 5 else "nearby"
    if r.get("reach") != reach:
        fails.append(f"{tag}: reach {r.get('reach')!r}, by the rule {reach!r}")
    if bool(r.get("quiet")) != (reach == "nearby" and not r.get("group")):
        fails.append(f"{tag}: quiet {r.get('quiet')!r} against the rule")
    g = r.get("group")
    # TRUE BY COUNTING WHAT IS RECALLED: the number in a label is the group's
    # distinct later quotations (one phrase matched to a happening told twice
    # is one thing, not two -- Josh 24:5, seen in the preview); a group of one
    # such phrase carries no number
    if g:
        things = len(gthings[g["id"]])
        nums = [int(x) for x in re.findall(r"\b(\d+) (?:things|instructions|passages)\b", g.get("label", ""))]
        if (things > 1 and nums != [things]) or (things == 1 and nums):
            fails.append(f"{tag}: group label not true by counting ({things} quoted): {g.get('label')!r}")
        if gcount[g["id"]] != g.get("n"):
            fails.append(f"{tag}: group n {g.get('n')} but {gcount[g['id']]} links")

# A theme's front page and its imagery side by side (plan 7.6b, ontology/
# themes/theme-hubs.json and the imagery file it names): every cell's words
# in the verse it names (or the next); every quotation in an Alike or
# Different line from the row's own verses; those lines in the site's voice
# by its rules; the front page's opening quotations in their verses; every
# starter an image the table has (BIBLEONT_IMAGERY overrides the table)
HUBS = json.loads((ROOT / "ontology" / "themes" / "theme-hubs.json").read_text(encoding="utf-8")) \
    if (ROOT / "ontology" / "themes" / "theme-hubs.json").exists() else {}
NAMEB = {"genesis": "Gen", "exodus": "Exod", "leviticus": "Lev", "numbers": "Num", "deuteronomy": "Deut",
         "joshua": "Josh", "judges": "Judg", "ruth": "Ruth", "1 samuel": "1Sam", "2 samuel": "2Sam",
         "1 kings": "1Kgs", "2 kings": "2Kgs", "1 chronicles": "1Chr", "2 chronicles": "2Chr", "ezra": "Ezra",
         "nehemiah": "Neh", "esther": "Esth", "job": "Job", "psalm": "Ps", "psalms": "Ps", "proverbs": "Prov",
         "ecclesiastes": "Eccl", "song of solomon": "Song", "isaiah": "Isa", "jeremiah": "Jer",
         "lamentations": "Lam", "ezekiel": "Ezek", "daniel": "Dan", "hosea": "Hos", "joel": "Joel", "amos": "Amos",
         "obadiah": "Obad", "jonah": "Jonah", "micah": "Mic", "nahum": "Nah", "habakkuk": "Hab",
         "zephaniah": "Zeph", "haggai": "Hag", "zechariah": "Zech", "malachi": "Mal", "matthew": "Matt",
         "mark": "Mark", "luke": "Luke", "john": "John", "acts": "Acts", "romans": "Rom", "1 corinthians": "1Cor",
         "2 corinthians": "2Cor", "galatians": "Gal", "ephesians": "Eph", "philippians": "Phil",
         "colossians": "Col", "1 thessalonians": "1Thess", "2 thessalonians": "2Thess", "1 timothy": "1Tim",
         "2 timothy": "2Tim", "titus": "Titus", "philemon": "Phlm", "hebrews": "Heb", "james": "Jas",
         "1 peter": "1Pet", "2 peter": "2Pet", "1 john": "1John", "2 john": "2John", "3 john": "3John",
         "jude": "Jude", "revelation": "Rev"}


def named(s):
    """"Daniel 7:9" -> the Berean verse key and the next, or []"""
    m = re.match(r"^\s*(.+?)\s+(\d+):(\d+)", s or "")
    b = NAMEB.get(m.group(1).lower()) if m else None
    k = dot(f"{b}.{m.group(2)}.{m.group(3)}") if b else None
    return ORDER[POS[k]:POS[k] + 2] if k in POS else []


nimg = 0
CARDREFS = None
for tid, hub in HUBS.items():
    if tid.startswith("_"):
        continue
    for ref_, words in hub.get("opening") or []:
        ks = named(ref_)
        if not ks or norm(words) not in norm(" ".join(V[k] for k in ks)):
            fails.append(f"hub {tid}: opening quotation not in {ref_}: {words!r}")
    f = (hub.get("imagery") or {}).get("file")
    p = Path(__import__("os").environ.get("BIBLEONT_IMAGERY") or ROOT / "ontology" / "themes" / f) if f else None
    if not (p and p.exists()):
        continue
    img = json.loads(p.read_text(encoding="utf-8"))
    titles = {r["title"] for r in img["rows"]}
    for s in hub.get("starters") or []:
        if s not in titles:
            fails.append(f"hub {tid}: starter is no image in the table: {s!r}")
    for r in img["rows"]:
        nimg += 1
        tag = f"imagery {tid} '{r['title']}'"
        pool = []
        for col, cells in r["cells"].items():
            if col not in img["columns"]:
                fails.append(f"{tag}: column {col!r} is not one of the table's")
            for x in cells:
                v, w = x[0], x[1]
                if x[2:] not in ([], ["aside"]):
                    fails.append(f"{tag}: a cell's third value is {x[2:]!r}, not 'aside'")
                ks = named(v)
                text = norm(" ".join(V[k] for k in ks)) if ks else ""
                pool.append(text)
                if not ks or norm(w) not in text:
                    fails.append(f"{tag}: cell words not in {v}: {w!r}")
        if sum(1 for c in r["cells"].values() if c) < 2:
            fails.append(f"{tag}: an image in fewer than two books")
        # A ROW'S CARDS (2026-10-07): each exists, and its own verses overlap
        # the row's, so no "See also" rests on a shared word alone
        if r.get("cards"):
            if CARDREFS is None:
                CARDREFS = {}
                for line_ in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
                    e_ = json.loads(line_)
                    CARDREFS[e_["id"]] = {dot(re.sub(r"^(\S+) (\d+):(\d+).*$", r"\1.\2.\3", x))
                                          for x in e_.get("refs") or []}
            rowkeys = {named(x[0])[0] for cs in r["cells"].values() for x in cs if named(x[0])}
            for cid in r["cards"]:
                if cid not in CARDREFS:
                    fails.append(f"{tag}: names a card that does not exist: {cid!r}")
                elif not CARDREFS[cid] & rowkeys:
                    fails.append(f"{tag}: card {cid!r} shares no verse with the row")
        for line in (r.get("alike") or "", r.get("different") or ""):
            for q in quoted(line):
                for piece in re.split(r"\.\.\.|…", q):
                    pn = norm(piece)
                    if len(pn.split()) >= 2 and not any(pn in t for t in pool):
                        fails.append(f"{tag}: Alike/Different quotes words not in its verses: {piece.strip()!r}")
            m = VOICE.search(unquoted(line))
            if m:
                fails.append(f"{tag}: the site's own voice says {m.group(0)!r}")
            if READERS.search(line):
                fails.append(f"{tag}: names a reader")

print(f"{len(rows)} links, {len(told)} stories told again, {len(letters)} letter references, "
      f"{len(poems)} poem references, {len(prophets)} prophet references, {len(revel)} Revelation links, "
      f"{len(hist)} history links, {nimg} images side by side, {len(fails)} failures")
for f in fails:
    print("FAIL", f)
sys.exit(1 if fails else 0)
