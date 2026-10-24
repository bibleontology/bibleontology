"""How close Hebrew, Aramaic and Greek words are: two independent bridges.

2026-09-27: see how close the Greek/Hebrew/Aramaic words are together.

  septuagint  every Hebrew and Aramaic word records the Greek word the
              Septuagint translators used (MACULA's alignment), in the same
              Strong's numbering as the New Testament. A Hebrew word and a
              Greek word are as close as the share of the Hebrew word's
              renderings that ARE that Greek word; two Old Testament words
              are as close as their Greek renderings are alike.
  english     the Berean editors tagged both testaments with Strong's
              numbers, so every word, in any language, has English
              renderings; two words are as close as their renderings are
              alike (base forms). Independent of the Septuagint.

TESTED on standard correspondences (never tuned to): for each Hebrew word,
is its Greek partner the nearest Greek word, or in the top five, among ALL
Greek words; and the same for Aramaic -> Hebrew.

    python tools/wordgraph/crosslang.py test
    python tools/wordgraph/crosslang.py near <lemma> [lang H|A|G]
"""
import collections
import math
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import similarity as SIM                                   # noqa: E402

HEB_GRK = [
    ("חֶסֶד", "ἔλεος"), ("אֱמֶת", "ἀλήθεια"), ("צְדָקָה", "δικαιοσύνη"),
    ("תּוֹרָה", "νόμος"), ("נֶפֶשׁ", "ψυχή"), ("רוּחַ", "πνεῦμα"),
    ("בְּרִית", "διαθήκη"), ("שָׁלוֹם", "εἰρήνη"), ("מֶלֶךְ", "βασιλεύς"),
    ("כֹּהֵן", "ἱερεύς"), ("חַטָּאת", "ἁμαρτία"), ("יָשַׁע", "σῴζω"),
    ("אָהַב", "ἀγαπάω"), ("בָּרַךְ", "εὐλογέω"), ("קָדוֹשׁ", "ἅγιος"),
    ("אֱלֹהִים", "θεός"), ("דָּבָר", "λόγος"), ("לֵב", "καρδία"),
    ("עַם", "λαός"), ("בַּיִת", "οἶκος"), ("אֶרֶץ", "γῆ"),
    ("שָׁמַיִם", "οὐρανός"), ("יוֹם", "ἡμέρα"), ("אִישׁ", "ἀνήρ"),
    ("בֵּן", "υἱός"), ("אָב", "πατήρ"), ("אֵם", "μήτηρ"),
    ("עַיִן", "ὀφθαλμός"), ("יָד", "χείρ"), ("מַיִם", "ὕδωρ"),
    ("לֶחֶם", "ἄρτος"), ("אוֹר", "φῶς"), ("חֹשֶׁךְ", "σκότος"),
    ("מָוֶת", "θάνατος"), ("כָּבוֹד", "δόξα"), ("גּוֹי", "ἔθνος"),
    ("עֶבֶד", "δοῦλος"), ("נָבִיא", "προφήτης"), ("מִשְׁפָּט", "κρίσις"),
    ("חָיָה", "ζάω"),
]
ARAM_HEB = [
    ("מֶלֶךְ", "מֶלֶךְ"), ("אֱלָהּ", "אֱלֹהִים"), ("בַּיִת", "בַּיִת"),
    ("שְׁמַיִן", "שָׁמַיִם"), ("אֲרַע", "אֶרֶץ"), ("יוֹם", "יוֹם"),
    ("בַּר", "בֵּן"), ("מִלָּה", "דָּבָר"), ("אֱנָשׁ", "אָדָם"),
]


# Aramaic -> Hebrew regular correspondences, applied to the Aramaic root
ARAM_TO_HEB = str.maketrans({"ד": "ז", "ת": "ש", "ט": "צ"})


def root(lemma, aramaic):
    """Consonants, with final forms plain, the Aramaic definite/plural
    endings (-א, -ין) and the Hebrew plural (-ים) and feminine (-ה) off."""
    c = SIM.bare(lemma).translate(str.maketrans("ךםןףץ", "כמנפצ"))
    if aramaic:
        for end in ("ינ", "א"):
            if len(c) > 2 and c.endswith(end):
                c = c[: -len(end)]
                break
        alt = c.translate(ARAM_TO_HEB)
        c = alt if alt != c else c.replace("ע", "צ") if len(c) == 3 else c
    else:
        for end in ("ימ", "ה"):
            if len(c) > 2 and c.endswith(end):
                c = c[: -len(end)]
                break
    return c


def gbare(s):
    """Greek without accents or breathings, lower case."""
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if not unicodedata.combining(c)).lower()


def num(s):
    return re.sub(r"\D", "", str(s or "")).lstrip("0")


class Index:
    def __init__(self):
        self.lex, self.layers, _ = SIM.load()
        self.by = {"H": {}, "A": {}, "G": {}}
        for lid, L in self.lex.items():
            lang = L.get("lang")
            if lang not in self.by:
                continue
            key = gbare(L["lemma"]) if lang == "G" else SIM.bare(L["lemma"])
            t = self.by[lang]
            if key not in t or L["count"] > self.lex[t[key]]["count"]:
                t[key] = lid
        # Greek lexeme by its Strong's number (the Septuagint's bridge)
        self.greek_by_strong = collections.defaultdict(list)
        for lid, L in self.lex.items():
            if L.get("lang") == "G" and L.get("strong"):
                self.greek_by_strong[num(L["strong"])].append(lid)
        self.sept = {}           # OT lexeme -> {greek strong: count}
        self.eng = {}            # any lexeme -> {english base: weight}
        for lid, Y in self.layers.items():
            s = (Y.get("septuagint") or {}).get("counts") or []
            v = collections.Counter()
            for c in s:
                v[num(c["greekstrong"])] += c["count"]
            if v:
                self.sept[lid] = v
            b = (Y.get("bsb_renderings") or {}).get("counts") or []
            v = collections.Counter()
            for c in b:
                ws = [w for w in (x.strip(".,;:!?'\"()[]") for x in
                                  c["english"].lower().split())
                      if w and w not in SIM.EN_STOP]
                for w in ws:
                    v[SIM.en_base(w)] += c["count"] / len(ws)
            if v:
                self.eng[lid] = v

    def get(self, lemma, lang):
        key = gbare(lemma) if lang == "G" else SIM.bare(lemma)
        return self.by[lang].get(key)

    # ---- the two bridges
    def sept_score(self, a, b):
        """Septuagint closeness: OT -> Greek is the share of a's renderings
        that are b; OT -> OT is how alike their renderings are."""
        la, lb = self.lex[a].get("lang"), self.lex[b].get("lang")
        if la != "G" and lb == "G":
            v = self.sept.get(a) or {}
            tot = sum(v.values())
            return v.get(num(self.lex[b].get("strong")), 0) / tot if tot else 0
        if la == "G" and lb != "G":
            return self.sept_score(b, a)
        if la != "G" and lb != "G":
            return SIM.cos(self.sept.get(a), self.sept.get(b)) or 0
        return 0

    def eng_score(self, a, b):
        return SIM.cos(self.eng.get(a), self.eng.get(b)) or 0

    def cognate_score(self, a, b):
        """Aramaic <-> Hebrew: the same root, allowing the regular sound
        correspondences (Aramaic ד / Hebrew ז, ת / שׁ, ט / צ, ע / צ) and
        the Aramaic plural and emphatic endings. 1 for the same root,
        else 0. Hebrew <-> Aramaic only; Greek has no cognates here."""
        la, lb = self.lex[a].get("lang"), self.lex[b].get("lang")
        if {la, lb} != {"A", "H"}:
            return 0
        ar, he = (a, b) if la == "A" else (b, a)
        return 1.0 if root(self.lex[ar]["lemma"], True) ==             root(self.lex[he]["lemma"], False) else 0

    def both_score(self, a, b):
        return (self.sept_score(a, b) + self.eng_score(a, b)
                + self.cognate_score(a, b)) / 3

    def nearest(self, a, lang, by, n=5, min_count=3):
        pool = [l for l, L in self.lex.items() if L.get("lang") == lang
                and L.get("count", 0) >= min_count and l != a]
        f = {"septuagint": self.sept_score, "english": self.eng_score,
             "cognate": self.cognate_score, "together": self.both_score}[by]
        return sorted(((f(a, b), b) for b in pool), reverse=True)[:n]


def test():
    X = Index()
    for title, pairs, la, lb in (("Hebrew -> Greek", HEB_GRK, "H", "G"),
                                 ("Aramaic -> Hebrew", ARAM_HEB, "A", "H")):
        found = [(X.get(a, la), X.get(b, lb), a, b) for a, b in pairs]
        miss = [(a, b) for x, y, a, b in found if not x or not y]
        found = [f for f in found if f[0] and f[1]]
        print(f"{title}: {len(found)} pairs" +
              (f" ({len(miss)} not found: {miss})" if miss else ""))
        for by in ("septuagint", "english", "cognate", "together"):
            if by == "cognate" and la != "A":
                continue
            top1 = top5 = 0
            for a, b, *_ in found:
                nb = [x for _, x in X.nearest(a, lb, by, 5)]
                top1 += bool(nb) and nb[0] == b
                top5 += b in nb
            print(f"  {by:10} partner first: {top1}/{len(found)}   "
                  f"in top 5: {top5}/{len(found)}")


def near(lemma, lang="H"):
    X = Index()
    a = X.get(lemma, lang)
    if not a:
        print("no such lemma")
        return
    L = X.lex[a]
    print(f"{L['lemma']} ({lang}), {L['count']} occurrences")
    for other in ("H", "A", "G"):
        if other == lang:
            continue
        for by in ("septuagint", "english"):
            nb = X.nearest(a, other, by, 6)
            if nb and nb[0][0] > 0:
                print(f"  {other} by {by:10}: " + ", ".join(
                    f"{X.lex[b]['lemma']} "
                    f"({((X.layers.get(b) or {}).get('glosses') or {}).get('usual')}) "
                    f"{s:.2f}" for s, b in nb if s > 0))


if __name__ == "__main__":
    if sys.argv[1:2] == ["near"]:
        near(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "H")
    else:
        test()
