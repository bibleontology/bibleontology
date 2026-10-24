"""TIPNR: which individual a proper name means, verse by verse.

STEP Bible's "Translators Individualised Proper Names with all References"
(CC BY 4.0, www.STEPBible.org, from work at Tyndale House Cambridge) gives
every person and place a unique tag and lists, under each original-language
form of its name, every verse where that form means that individual. So at
(Strong's number, verse) it says WHO -- which is what the mentions resolver's
chapter and book tests could only guess from a record's 1-4 sample verses.

Why it was needed (plan A.17b, 2026-10-04): "James" in Matt 10:2, Mark 3:17
and Luke 6:14, 8:51, 9:28, 9:54 went to Alphaeus's son, because Zebedee's
James record cites neither Matthew 10 nor Luke; the book test gave every bare
"Simon" in John to Judas Iscariot's father (his record cites only John 6:71),
and "John" in John 1:6 to Peter's father. Fetching it was approved the same
day.

STEP Bible asks that the file be distributed only from github.com/STEPBible,
so it lives in data/raw/stepbible/ (gitignored); what is committed is the
resolver's output, out/mentions.jsonl.gz, which names our records.

    tools/fetch_tipnr.py fetches it.
"""
import collections
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "data" / "raw" / "stepbible" / \
    "TIPNR - Translators Individualised Proper Names with all References - STEPBible.org CC BY.txt"
BOOKREF = re.compile(r"^([1-3]?[A-Z][a-z]{1,2})\.(\d+)\.(\d+)(?:-(\d+))?")
CHAPREF = re.compile(r"^(\d+)\.(\d+)(?:-(\d+))?")


def verses(field):
    """'Mat.10.3; Mrk.2.14; 3.18; Luk.6.15-16' -> {'Mat.10.3', 'Mrk.2.14',
    'Mrk.3.18', 'Luk.6.15', 'Luk.6.16'}: a ref without a book is in the last
    one named; a range within a chapter is every verse of it."""
    out, book = set(), None
    for tok in field.split(";"):
        tok = tok.strip().rstrip("(?)").strip()
        m = BOOKREF.match(tok)
        if m:
            book, c, v, hi = m.groups()
        else:
            m = CHAPREF.match(tok)
            if not (m and book):
                continue
            c, v, hi = m.groups()
        for n in range(int(v), int(hi or v) + 1):
            out.add(f"{book}.{c}.{n}")
    return out


def strong_key(lang, s):
    """'0121' (hebrew) -> 'H0121'; '76' (greek) -> 'G0076'; '5867a' -> 'H5867'.
    None for a word without one."""
    m = re.match(r"\D*(\d+)", str(s or ""))
    if not m:
        return None
    return ("H" if lang == "hebrew" else "G") + m.group(1).zfill(4)


def load(path=FILE):
    """{(strong_key, 'Book.c.v'): {tipnr_id}}, {tipnr_id: {'Book.c.v'}},
    {tipnr_id: {english name}}. Verse refs are TIPNR's (English numbering).
    Returns None if the file is absent."""
    if not path.exists():
        return None
    at = collections.defaultdict(set)
    refs = collections.defaultdict(set)
    names = collections.defaultdict(set)
    # PEOPLE ONLY. TIPNR files a nation or tribe under its ancestor (Israel
    # the people under the man Israel, the tribe of Levi under Levi); used for
    # those, it gave Jacob 1,941 mentions of the nation -- A.17's fault again.
    # So it is read for one question, which of several people of one name,
    # and an ancestor of a people is left out: one whose entry has a "Group"
    # form (Israel: Israelite; Levi: Levite) or whom a people's entry names
    # as its parent with "(d)" ("Canaan@Gen.9.18-1Ch(d)"). Isaiah's "Jacob",
    # "Levi" at Num 3:6 and "the house of Joseph" at Judg 1:35 went to the
    # man before this; for these names the resolver's own tests stand.
    text = path.read_text(encoding="utf-8")
    eponyms = {m.split("|")[-1] for m in re.findall(r"([^\s,+\t]+@[^\s,+\t(]+)\(d\)", text)}
    cur = section = None
    for line in text.splitlines():
        if line.startswith("$=========="):
            section = line.strip("$= \t").upper()
            cur = None
            continue
        if not section or not section.startswith("PERSON"):
            continue
        cols = line.split("\t")
        if cur is None and "@" in cols[0] and "=" in cols[0] and line[0] not in "–@":
            cur = cols[0].split("=")[0].strip()
            names[cur].add(cur.split("@")[0])
            continue
        if cur and cols[0].startswith("– Group"):
            eponyms.add(cur)
        if cur and line.startswith("–") and len(cols) >= 5 and \
                not cols[0].startswith("– Total"):
            forms = set()
            for part in re.split(r"[«=,;\s]+", cols[2]):
                k = re.match(r"([HG])(\d{1,4})", part)
                if k:
                    forms.add(k.group(1) + k.group(2).zfill(4))
            vs = verses(cols[4])
            for f in forms:
                for v in vs:
                    at[(f, v)].add(cur)
            refs[cur] |= vs
            # 'Alphaeus =ESV,NIV; Alpheus =KJV' -> Alphaeus, Alpheus
            for n in cols[3].split(";"):
                n = n.split("=")[0].strip()
                if n:
                    names[cur].add(n)
            names[cur] |= {n for n in cols[1].split("@")[0].split("|") if n}
    # a verse where the form may be an ancestor says nothing, rather than
    # leaving the other person there looking certain
    for k in list(at):
        if at[k] & eponyms:
            del at[k]
    for t in eponyms:
        refs.pop(t, None)
        names.pop(t, None)
    return at, refs, names
