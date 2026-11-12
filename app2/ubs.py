"""THE UBS DICTIONARIES' SENSES, for the word and verse pages (2026-11-04).

The UBS Dictionary of Biblical Hebrew (after SDBH) and the UBS Dictionary of New Testament Greek (after Louw-Nida),
read from data/raw/ubs/ubs-hebrew.jsonl and ubs-greek.jsonl as tools/fetch_ubs.py builds them on the server. They
are CC BY-SA 4.0, the graph CC BY 4.0: shown here, credited in UBS's words, and never committed or exported
(docs/review/permissions/sdbh-2026-11-02.md). Where the files are absent (the public copy, a fresh worktree) every
answer is empty and the pages show no UBS panel.

Keys are Strong's numbers as the site writes them ("h1", "g26"). A sense's references are UBS's own, in the
original's versification (Malachi 3:24 is the English 4:6), which is MACULA's: they are kept as UBS writes them
("Mal.3.24") and as MACULA does ("Mal.3.24", "Jud.1.12") side by side, so a verse is matched by its MACULA address.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ubs"

LICENCE = "CC BY-SA 4.0"
LICENCE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
SOURCE_URL = "https://github.com/ubsicap/ubs-open-license"
# exactly as each README gives it (docs/review/permissions/sdbh-2026-11-02.md)
CREDIT = {
    "h": "UBS Dictionary of Biblical Hebrew © United Bible Societies, 2023. Adapted from Semantic Dictionary of "
         "Biblical Hebrew © 2000-2023 United Bible Societies.",
    "g": "UBS Dictionary of New Testament Greek, © United Bible Societies, 2023. Adapted from Semantic Dictionary of "
         "Biblical Greek: © United Bible Societies 2018-2023, which is adapted from Greek-English Lexicon of the New "
         "Testament: Based on Semantic Domains, Eds. J P Louw, Eugene Albert Nida © United Bible Societies 1988, "
         "1989.",
}
EDITED = ("Edited here: the dictionary's notation marks (= ► ◄ ≈) and its link codes are left out, its "
          "Louw-Nida numbers are written \"LN\", and each sense is shown under the Strong's number its verses carry "
          "here, so a sense filed under another number of the same word is shown on that word's page, saying where "
          "it is filed.")
FILES = {"h": "ubs-hebrew.jsonl", "g": "ubs-greek.jsonl"}

_KEY = re.compile(r"^([hg])0*(\d+)[a-z]?$")


def base_key(key):
    """'H6213a' -> 'h6213'; 'g0026' -> 'g26'; None for anything else. UBS numbers carry no letter."""
    m = _KEY.match((key or "").strip().lower())
    return f"{m.group(1)}{m.group(2)}" if m else None


def _ref_label(code):
    """UBS's verse code in a definition ('05600101200026', book chapter verse word) -> 'Titus 1:12' style text."""
    sys.path.insert(0, str(ROOT / "tools" / "lexicon"))
    import ubs_extract
    ref = ubs_extract.ref_of(code)
    if not ref:
        return code
    b, c, v = ref.split(".")
    return f"{b} {c}:{v}"


def clean(text):
    """A definition as it is shown: link codes resolved to their words, notation marks left out (EDITED says so)."""
    t = text or ""
    t = re.sub(r"\{L:([^<}]*)<[^}]*\}", r"\1", t)            # {L:Judah<SDBH:יְהוּדָה>} -> Judah
    t = re.sub(r"\{D:([^}]*)\}", r"LN \1", t)                  # {D:15.215} -> LN 15.215
    t = re.sub(r"\{A:([^}]*)\}", r"\1", t)                     # {A:ABD} -> ABD
    t = re.sub(r"\{N:[^}]*\}", "", t)                          # a footnote's number
    t = re.sub(r"\{S:([^}]*)\}", lambda m: _ref_label(m.group(1)), t)
    t = re.sub(r"\[[a-z]\]", "", t)                            # a footnote's letter
    t = re.sub(r"^\s*=\s*", "", t)
    t = re.sub(r"\s*[►◄≈=]\s*", " ", t)
    t = re.sub(r"\s+([,;:.)])", r"\1", t)
    t = re.sub(r"([,;])\s*([,;])", r"\2", t)
    return re.sub(r"\s{2,}", " ", t).strip(" ,;")


class Ubs:
    """The two dictionaries as the pages read them. `entries` key -> record; `at` (MACULA ref, key) -> sense
    indexes; `domain` (letter, code) -> {"label", "weight": {key: uses in that domain}}.

    ONE ENTRY, SEVERAL NUMBERS (measured 2026-11-04). UBS gives one entry for בֵּן "son" under H1121, H1122, H1123
    and H4192, and the extract files it under each, so every one of those cards had all 3,760 of its verses: 146,182
    of the 485,130 references (30%) named a verse where the site has not that number. `has(key, mref)`, when given,
    says where the site has a number; a shared entry then keeps, under each number, only the verses where the site
    has that number, and a sense left with no verse is dropped from that number's card. A number left with nothing
    shows no UBS senses: H1122 (Ben, a Levite, 1 Chr 15:18) shares a record with H1123 and H4192 whose 3,760 verses
    are H1121's "son", none of them his, and showing "son, child" on his card would be another word's meanings.
    Sharing only among the listed numbers was not enough for the same reason.

    ONE ENTRY, ONE NUMBER, ANOTHER WORD'S VERSES (2026-11-07). The split ran only where UBS lists several numbers, and
    UBS files ἱερός under G2413 alone with two senses, "holy" (3 verses) and "temple" (71, every one of them ἱερόν,
    G2411): so G2413 "sacred" showed "temple" with 67 verses, and G2411, the temple, showed nothing. 973 senses were
    shown under a number holding under half their verses (849 Hebrew, 124 Greek: inflected forms Strong's numbers
    apart, ἡμῶν G2257 under ἐγώ G1473; a prefixed ב under its own number). Now every entry keeps, under its number,
    only the verses where the site has it; and a sense whose verses belong to a number with no UBS entry of its own
    is shown there, saying where UBS files it (`owners(mref)`: the numbers the site has in a verse)."""

    def __init__(self, to_macula, root=RAW, has=None, owners=None, kin=None):
        """kin(key, lemma): whether the site's number `key` is the word UBS's `lemma` names (its MACULA lemma, letters
        only). A stray sense goes only to the same word: counting every number in its verses gave G2411 a sense of
        ἡμέτερος "our" from one verse, and ἐγώ the senses of δέ."""
        self.entries, self.at, self.domain, self.loaded = {}, {}, {}, set()
        for letter, name in FILES.items():
            p = Path(root) / name
            if not p.exists():
                continue
            self.loaded.add(letter)
            rows = [json.loads(line) for line in open(p, encoding="utf-8")]
            own = {r["key"] for r in rows}
            shared = {}
            for r in rows:
                shared.setdefault(json.dumps([r.get("lemma"), r.get("senses")], sort_keys=True), []).append(r["key"])
            built, borrowed = {}, {}
            for r in rows:
                key = r["key"]
                group = shared[json.dumps([r.get("lemma"), r.get("senses")], sort_keys=True)]
                lem = r.get("lemma") or ""
                if has is not None and len(group) == 1 and owners is not None:
                    # one number: a verse leaves it only for another number OF THE SAME WORD (ἱερόν's 67 under ἱερός).
                    # A verse no number of the word holds stays: the site tags many names otherwise (Beth-aven, H1007,
                    # lost all its senses to the strict rule, 805 numbers, 156 of them listed pages)
                    def keep(k, m, lem=lem):
                        return has(k, m) or not any(o != k and o[:1] == letter and (kin is None or kin(o, lem))
                                                    for o in owners(m) or ())
                    senses = self._senses(r, to_macula, keep, key)
                else:
                    senses = self._senses(r, to_macula, has if len(group) > 1 else None, key)
                built[key] = {"key": key, "lemma": r.get("lemma") or "", "version": r.get("version") or "",
                              "senses": senses, "shared": [k for k in group if k != key]}
                if has is None or owners is None or len(group) > 1:
                    continue
                # a sense's verses the site gives another number: shown under that number if UBS has no entry for it
                for s in self._senses(r, to_macula, None, key):
                    away = [m for m in s["refs"] if not keep(key, m)]
                    if not away:
                        continue
                    count = {}
                    for m in away:
                        for k in owners(m) or ():
                            if k != key and k[:1] == letter and k not in own and (kin is None or kin(k, r.get("lemma") or "")):
                                count[k] = count.get(k, 0) + 1
                    if not count:
                        continue
                    to = max(sorted(count), key=lambda k: count[k])
                    refs = [m for m in s["refs"] if has(to, m)]
                    if len(refs) * 2 < len(away):
                        continue                       # most of the stray verses are not that number's either
                    b = borrowed.setdefault(to, {"key": to, "lemma": r.get("lemma") or "",
                                                 "version": r.get("version") or "", "senses": [], "shared": [],
                                                 "filed_under": {"key": key, "lemma": r.get("lemma") or ""}})
                    b["senses"].append(dict(s, refs=refs, uses=len(refs)))
            built.update({k: v for k, v in borrowed.items() if k not in built})
            for key, e in built.items():
                for i, s in enumerate(e["senses"]):
                    for mref in s["refs"]:
                        self.at.setdefault((mref, key), []).append(i)
                    for x in s["domains"]:
                        dm = self.domain.setdefault((letter, x["code"]), {"label": x["label"], "weight": {}})
                        dm["weight"][key] = dm["weight"].get(key, 0) + s["uses"]
                self.entries[key] = e

    @staticmethod
    def _senses(r, to_macula, has, key):
        """A record's senses with MACULA addresses; with `has`, only the verses where the site has `key`, and only
        the senses left with one."""
        out = []
        for s in r.get("senses") or []:
            refs, seen, uses = [], set(), 0
            for ref in s.get("refs") or []:
                b, _, cv = ref.partition(".")
                mref = f"{to_macula.get(b, b)}.{cv}"
                if has and not has(key, mref):
                    continue
                uses += 1
                if mref not in seen:
                    seen.add(mref)
                    refs.append(mref)
            if has and not refs:
                continue
            out.append({"short": clean(s.get("short")), "glosses": s.get("glosses") or [],
                        "domains": [{"code": x["code"], "label": x["label"]} for x in s.get("domains") or []],
                        "refs": refs, "uses": uses})
        return out

    def __bool__(self):
        return bool(self.entries)

    def source(self, key):
        """The credit block an answer carries with UBS text in it."""
        letter = (base_key(key) or "x")[0]               # a verse card's word is "G26": the letter, lowercased
        return {"credit": CREDIT.get(letter, ""), "licence": LICENCE, "licence_url": LICENCE_URL,
                "url": SOURCE_URL, "edited": EDITED,
                "version": (self.entries.get(base_key(key)) or {}).get("version") or ""}

    def entry(self, key):
        return self.entries.get(base_key(key))

    def senses_at(self, mref, key):
        """The senses UBS lists this verse under, for this word; [] where it lists none (never a guess)."""
        k = base_key(key)
        e = self.entries.get(k)
        if not e:
            return []
        return [e["senses"][i] for i in self.at.get((mref, k), [])]

    def domain_keys(self, key, code):
        """The other words UBS files under this domain, by how many of their uses it files there (not by how common
        the word is: ποιέω "do" has a sense under Attitudes and Emotions, and led that list by its 568 uses)."""
        k = base_key(key)
        w = (self.domain.get((k[0], code)) or {}).get("weight", {}) if k else {}
        return sorted((x for x in w if x != k and w[x]), key=lambda x: (-w[x], x))
