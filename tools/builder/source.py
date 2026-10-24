"""S0 — the source: MACULA's words and trees, as they are.

Every morpheme becomes a record with its MACULA id (xml:id), its position in
its verse, and the grammatical facts MACULA states on it. Nothing is
decided here. Only these attributes are read; never SDBH, lexdomain,
coredomain, domain or ln (docs/WORKERS.md, the floor).

HEBREW AND GREEK INTO ONE SHAPE (2026-09-27: match the Hebrew
as well as possible; the more aligned in structure, the more effective the
pattern matching). MACULA's two datasets name some things differently; the
records are made alike here, once, so no later stage has to know which
language it reads:
  - Greek `strong` is recorded as `strongnumberx`, as the Hebrew names it
  - Greek class `conj` is `cj`, and `det` is `art`, as the Hebrew names them
  - a Greek verb's `mood` is also its `type`, which is where the Hebrew
    carries the verb's form (wayyiqtol, qatal ...)
  - Greek has no `english`; its gloss is used, with the supplied words
    (in brackets) removed
  - αὐτός carries no person in MACULA; it is the third-person pronoun
What Greek states that Hebrew does not (tense, voice, case, degree) is kept.
"""
import collections
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from macula import MAC, _ref                               # noqa: E402

XID = "{http://www.w3.org/XML/1998/namespace}id"
FIELDS = ("class", "lemma", "strongnumberx", "strong", "type", "stem",
          "person", "gender", "number", "state", "english", "gloss", "role",
          "lang", "mood", "tense", "voice", "case", "degree", "normalized")
GREEK_CLASS = {"conj": "cj", "det": "art"}
GREEK_PERSON = {"αυτος": "third", "εγω": "first", "συ": "second"}


def norm(s):
    """The key a lexicon looks a word up by: Hebrew consonants, or Greek
    without accents and breathings, lower case."""
    s = s or ""
    heb = "".join(ch for ch in s if "א" <= ch <= "ת")
    if heb:
        return heb
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c)).lower()


def files(lang="hebrew"):
    if lang == "greek":
        # the Greek folder also holds two WHOLE-NT files (commonformat.xml,
        # nestle1904lowfat.xml); reading them would repeat every word
        return sorted(p for p in (MAC / "greek").glob("*.xml")
                      if p.name[:2].isdigit())
    return sorted((MAC / lang).glob("*.xml"))


def words(root, lang="hebrew"):
    """Every <w> under a tree root, in document order, as records. Positions
    are 0-based within each verse, across the file."""
    pos = collections.Counter()
    out = {}
    for w in root.iter("w"):
        ref = _ref((w.get("ref") or "").split("!")[0])
        if not ref:
            continue
        r = {k: w.get(k) for k in FIELDS if w.get(k) is not None}
        r.update(id=w.get(XID), ref=ref, pos=pos[ref], text=w.text or "",
                 after=w.get("after") or "")
        if lang == "greek":
            r["lang"] = "G"
            if r.get("strong") and not r.get("strongnumberx"):
                r["strongnumberx"] = r["strong"]
            r["class"] = GREEK_CLASS.get(r.get("class"), r.get("class"))
            if r.get("class") == "verb" and r.get("mood"):
                r["type"] = r["mood"]
            if not r.get("english") and r.get("gloss"):
                g = re.sub(r"\[[^\]]*\]", " ", r["gloss"]).replace(".", " ")
                r["english"] = " ".join(g.split()) or r["gloss"]
            if r.get("class") == "pron" and not r.get("person"):
                p = GREEK_PERSON.get(norm(r.get("lemma")))
                if p:
                    r["person"] = p
        pos[ref] += 1
        out[r["id"]] = r
    return out


def load(path, lang="hebrew"):
    """(tree root, {xml id: word record}) for one MACULA file."""
    root = ET.parse(path).getroot()
    return root, words(root, lang)
