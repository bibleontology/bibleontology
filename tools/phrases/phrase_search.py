"""Multi-word concepts, found everywhere the text says them -- in English and
across the language divide.

2026-09-30, comparing the site with Blue Letter Bible on "living water":
that site listed all the verses, including several OT references, which the
site here missed; the multiple words got lost across the language divide.
The remedy asked for was an English-based search for all multi-word concepts
like this one, to ensure that all references across languages are picked up
and that all relevant ones are represented in the graph.

Why they were missed: a card's "where the text speaks of it" follows a
node's ANCHORED WORD (concept_anchors.py), one lemma. A phrase has no single
word, so `image_living_water` found nothing beyond its three cited verses
(John 4:10, 7:38, 7:39).

Two passes per multi-word node (concept, image, title, object, creature,
covenant, observance; not assessments, which are claims):

1. ENGLISH. The node's name as a phrase in the public-domain translations on
   disk -- the Berean first, then ASV, WEB and YLT for other renderings (the
   KJV is not used: licensing). Words match with their plural ("waters").
2. ACROSS THE LANGUAGE DIVIDE. The Berean editors tagged their English with
   Strong's numbers (out/bsb-align.jsonl.gz, approximate), so each English hit
   says which Hebrew or Greek words stand behind the phrase. The words that
   stand behind it in most hits are its SIGNATURE (per language); then every
   verse where those words stand together (within a few words) is found,
   however it was translated -- Leviticus 14:5's "fresh water" is the same
   mayim chayyim as Jeremiah 2:13's "living water".

What it does NOT decide: whether each occurrence is the concept (Leviticus
14's living water is literal, for cleansing). Every occurrence is kept with
HOW it was found; a phrase used in more than COMMON verses is marked common,
as too frequent to mark a concept on its own.

    python tools/phrases/phrase_search.py   -> out/phrase-occurrences.jsonl.gz
                                               docs/review/PHRASE-SEARCH.md
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
BIBLE = ROOT / "data" / "bible"
TRANSLATIONS = [("BSB", "verses.bsb.jsonl"), ("ASV", "verses.asv.jsonl"),
                ("WEB", "verses.web.jsonl"), ("YLT", "verses.ylt.jsonl")]
TYPES = {"concept", "image", "title", "object", "creature", "covenant", "observance"}
STOP = {"the", "of", "a", "an", "and", "in", "to", "for", "by", "on", "at", "with", "from",
        "his", "her", "their", "our", "my", "your", "its", "as", "is", "be", "o"}
LEAD = {"the", "a", "an"}
COMMON = 150          # a phrase in more verses than this is too common to mark a concept
SIGNATURE = 0.6       # a word stands behind the phrase in this share of its hits
WINDOW = 2            # signature words within this many words of each other: at 3,
                      # Gen 1:20 "let the WATERS teem with LIVING creatures" (mayim
                      # ... nefesh chayyah, three apart) passed as living water
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
    "3John": "3Jn", "Jude": "Jud", "Rev": "Rev"}     # as app2/server.py
FROM_MACULA = {v: k for k, v in TO_MACULA.items()}
ORDER = list(TO_MACULA)


def toks(s):
    return re.findall(r"[a-z]+", s.lower().replace("’", "").replace("'", ""))


def variants(t):
    v = {t, t + "s", t + "es"}
    if t.endswith("s") and len(t) > 3:
        v.add(t[:-1])
    if t.endswith("es") and len(t) > 4:
        v.add(t[:-2])
    return v


def phrase_of(name):
    """the words to find: the name without a leading article or a trailing
    bracket ("bearing fruit (as an image)" -> bearing fruit)"""
    w = toks(re.sub(r"\(.*?\)", "", name))
    while w and w[0] in LEAD:
        w = w[1:]
    return w


def vkey(v):
    b, c, n = v.split(".")
    return (ORDER.index(b) if b in ORDER else 99, int(c), int(n))


def load_text():
    """translation -> verse id 'Gen.1.1' -> (tokens, text)"""
    out = {}
    for tr, fn in TRANSLATIONS:
        p = BIBLE / fn
        if not p.exists():
            continue
        vs = {}
        for ln in p.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            r = json.loads(ln)
            if "b" in r:
                vs[f"{r['b']}.{r['c']}.{r['v']}"] = (toks(r["t"]), r["t"])
        out[tr] = vs
    return out


def english_hits(words, text, index):
    """verses where the phrase stands, word for word (plurals allowed)"""
    content = [w for w in words if w not in STOP]
    cand = None
    for w in content:
        s = set().union(*(index.get(x, set()) for x in variants(w)))
        cand = s if cand is None else cand & s
        if not cand:
            return set()
    vs = [variants(w) for w in words]
    got = set()
    for v in cand:
        t = text[v][0]
        for i in range(len(t) - len(vs) + 1):
            if all(t[i + j] in vs[j] for j in range(len(vs))):
                got.add(v)
                break
    return got


CONTENT_CLASS = {"noun", "verb", "adj", "adv", "pron", "num"}


def hebrew_words():
    """MACULA Hebrew, read from its own files (data/raw/macula, CC BY 4.0,
    not redistributed): per verse, its content words as (written position,
    key, preposition-prefixed). A prefix shares its host's written position
    (LEV 14:51!11 is הַ and צִּפֹּר), so the article adds no distance --
    הַמַּיִם הַחַיִּים, "the fresh water", stands side by side as מַיִם חַיִּים
    does -- and whether a word carries a PREPOSITION is kept, because "day of
    the LORD" is יוֹם יְהוָה and "today to the LORD" is הַיּוֹם לַיהוָה."""
    out = collections.defaultdict(list)
    lemma = {}
    for f in sorted((ROOT / "data" / "raw" / "macula" / "hebrew").glob("*.xml")):
        prep_at, art_at = set(), set()
        rows_ = []
        for a, _t in re.findall(r"<w\b([^>]*)>([^<]*)", f.read_text(encoding="utf-8")):
            d = dict(re.findall(r'([\w:]+)="([^"]*)"', a))
            ref, cls = d.get("ref"), d.get("class")
            if not ref or "!" not in ref:
                continue
            vref, n = ref.split("!")
            n = int(re.sub(r"\D", "", n) or 0)
            # a conjunction breaks a phrase as a preposition does: "... in
            # years, AND the LORD blessed" (Gen 24:1) is not "day of the LORD"
            if cls in ("prep", "cj"):
                prep_at.add((vref, n))
                continue
            if cls == "art":
                art_at.add((vref, n))
                continue
            if cls not in CONTENT_CLASS:
                continue
            s = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", d.get("strongnumberx", "")))
            if s:
                rows_.append((vref, n, "h" + s, d.get("lemma")))
        for vref, n, k, lem in rows_:
            b, cv = vref.split(" ")
            c, v = cv.split(":")
            # "LEV" -> "Lev", "1SA" -> "1Sa": the MACULA codes the graph uses
            b = b[:2] + b[2:].lower() if b[0].isdigit() else b[:1] + b[1:].lower()
            key = f"{b}.{c}.{v}"
            # (article?, preposition-or-conjunction?) on this written word
            out[key].append((n, k, ((vref, n) in art_at, (vref, n) in prep_at)))
            lemma.setdefault(k, lem)
    return out, lemma


def build():
    """Load the translations and the original words once; return find(words)
    -> (english {verse: [translations]}, signature, original verses), the
    search every caller shares (phrase nodes here; refrains in
    tools/patterns/recurs.py), and the translations."""
    text = load_text()
    index = {tr: collections.defaultdict(set) for tr in text}
    for tr, vs in text.items():
        for v, (t, _raw) in vs.items():
            for w in t:
                index[tr][w].add(v)
    moved = json.loads((OUT / "versemap.json").read_text(encoding="utf-8"))["moved"]
    to_mac = {b: m for m, b in moved.items()}                 # BSB -> MACULA

    def mac(v):
        b, c, n = v.split(".")
        r = f"{TO_MACULA[b]}.{c}.{n}"
        return to_mac.get(r, r)

    def bsb(v):
        v = moved.get(v, v)
        b, c, n = v.split(".")
        return f"{FROM_MACULA.get(b, b)}.{c}.{n}"

    # the Berean editors' Strong's tagging, per verse: character spans
    spans = {}
    for ln in gzip.open(OUT / "bsb-align.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if "ref" in r:
            spans[r["ref"]] = (r["text"], r["spans"])
    # the original words, per verse (MACULA numbering), in order
    words = collections.defaultdict(list)
    lemma = {}
    # Hebrew from MACULA's own files (written positions, prefixes kept as
    # flags); Greek from the word layer, where each word is written alone
    hw, hl = hebrew_words()
    for ref, ws in hw.items():
        words[ref] = sorted(ws)
    lemma.update(hl)
    greek = collections.defaultdict(list)
    for ln in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if not r.get("word") or not r.get("strong") or r.get("lang") != "greek":
            continue
        s = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", r["strong"]))
        if not s:
            continue
        k = "g" + s
        # the Greek article does not count as distance (ὕδωρ τὸ ζῶν)
        if k == "g3588":
            continue
        greek[r["ref"]].append((int(r["local"][1:]), k, r.get("case")))
        lemma.setdefault(k, r.get("lemma"))
    for ref, ws in greek.items():
        # renumbered without the article. In place of the Hebrew prefix, a
        # Greek word's CASE: "the day of the Lord" is ἡμέρα κυρίου (genitive);
        # "on that day, 'Lord, Lord'" (Matt 7:22, vocative) and "observes the
        # day ... to the Lord" (Rom 14:6, dative) are not the phrase
        words[ref] = [(n, k, (False, c)) for n, (_i, k, c) in enumerate(sorted(ws))]
    # what English each original word stands for: the Berean's own
    # single-word renderings (out/bsb-words.json, from its Strong's tags; a
    # rendering under 2% of a word's uses is noise -- יְהוָה "said") and the
    # lexicon gloss (STEPBible, read from disk, not redistributed)
    renders = collections.defaultdict(set)
    bw = json.loads((OUT / "bsb-words.json").read_text(encoding="utf-8")).get("words", {})
    for k, rs in bw.items():
        tot = sum(n for _r, n in rs) or 1
        for r_, n in rs:
            t = toks(r_)
            if len(t) == 1 and n >= 2 and n / tot >= 0.02:
                renders[k] |= variants(t[0])
    lexp = ROOT / "data" / "raw" / "stepbible" / "lexicon.json"
    if lexp.exists():
        for code, v in json.loads(lexp.read_text(encoding="utf-8")).items():
            if isinstance(v, list) and len(v) >= 4:
                k = code[0].lower() + re.sub(r"^0+", "", code[1:])
                for t in toks(v[3]):
                    if t not in STOP and len(t) > 2:
                        renders[k] |= variants(t)
    key_verses = collections.defaultdict(set)
    for ref, ws in words.items():
        for _i, k, _p in ws:
            key_verses[k].add(ref)

    def find(w):
        eng = collections.defaultdict(list)
        for tr in text:
            for v in english_hits(w, text[tr], index[tr]):
                eng[v].append(tr)
        if not eng:
            return {}, {}, set()
        # THE WORDS BEHIND THE PHRASE. In each Berean hit, for each content
        # word of the phrase, the original word in that verse that renders it
        # (its Berean renderings or its lexicon gloss say so). The Berean
        # editors' span tagging was tried first and is too sparse: at Matt
        # 6:33 "the kingdom" carries καί's number and "of God" none.
        content = [x for x in w if x not in STOP]
        per_lang = collections.defaultdict(list)   # lang -> [ {token: (key, pos, prep)} ]
        for v, trs in eng.items():
            if "BSB" not in trs:
                continue
            m = mac(v)
            lang = "h" if ORDER.index(v.split(".")[0]) < ORDER.index("Matt") else "g"
            got = {}
            for tkn in content:
                vs_ = variants(tkn)
                cands = [(i, k, p) for i, k, p in words.get(m, [])
                         if renders.get(k, set()) & vs_]
                if cands:
                    got[tkn] = cands
            if len(got) == len(content):
                # the choice that puts them closest together
                best = None
                for i0, k0, p0 in got[content[0]]:
                    pick = {content[0]: (k0, i0, p0)}
                    for tkn in content[1:]:
                        i, k, p = min(got[tkn], key=lambda c: abs(c[0] - i0))
                        pick[tkn] = (k, i, p)
                    spread = max(p[1] for p in pick.values()) - min(p[1] for p in pick.values())
                    if best is None or spread < best[0]:
                        best = (spread, pick)
                if best[0] <= WINDOW * (len(content) - 1):
                    per_lang[lang].append(best[1])
        signature, original = {}, set()
        for lang, picks in per_lang.items():
            # at least two hits: one occurrence is not yet a phrase ("You are
            # the God who sees me", Gen 16:13 alone, took every "the LORD saw")
            if len(picks) < 2:
                continue
            sig = []
            for tkn in content:
                cnt = collections.Counter(p[tkn][0] for p in picks)
                k, n = cnt.most_common(1)[0]
                if n / len(picks) < SIGNATURE:
                    break
                sig.append(k)
            if len(sig) != len(content) or len(set(sig)) < 2:
                continue
            # ORDER AND SPACING, learned from the hits: יוֹם יְהוָה is "day"
            # then "LORD", side by side; "in six days the LORD made" is not it
            # -- and whether each word after the phrase's first (in the text)
            # takes a preposition, Hebrew. A preposition on the FIRST word
            # governs the whole phrase and is no part of it: בַּמַּיִם הַחַיִּים,
            # "in the fresh water" (Lev 14:51), is the same phrase as מַיִם
            # חַיִּים. The arrangement is (spacing..., prefix-or-None...)
            # THE ARTICLE is part of it too: a construct chain (יוֹם יְהוָה,
            # "day of the LORD") never has it on the first word, so הַיּוֹם
            # יְהוָה, "today the LORD" (Lev 9:4), is not the phrase; a noun and
            # its adjective take it on both (הַמַּיִם הַחַיִּים), which is the same
            # phrase as neither, so an article on every word counts as none
            def arrangement(p):
                P = [p[t][1] for t in content]
                first = P.index(min(P))
                X = tuple(None if i == first else p[t][2][1] for i, t in enumerate(content))
                A = tuple(p[t][2][0] for t in content)
                if all(A):
                    A = tuple(False for _ in A)
                return tuple(x - P[0] for x in P[1:]) + X + A
            offs = collections.Counter(
                arrangement(p) for p in picks if all(p[t][0] == k for t, k in zip(content, sig)))
            # the phrase's own arrangement, and any other used as often as
            # 40% of the time: a stray spacing in a few hits ("the day the
            # LORD made") must not become a pattern to search for
            top = offs.most_common(1)[0][0] if offs else None
            ok = {o for o, n in offs.items()
                  if o == top or n / max(1, sum(offs.values())) >= 0.4}
            if not ok:
                continue
            signature[lang] = [[k, lemma.get(k)] for k in sig]
            cand = set.intersection(*(key_verses[k] for k in sig))
            nlater = len(sig) - 1
            for ref in cand:
                at = {(i, k): fl for i, k, fl in words[ref]}
                found = False
                for arr in ok:
                    for (i0, k0), fl0 in at.items():
                        if k0 != sig[0]:
                            continue
                        pick = {content[0]: (k0, i0, fl0)}
                        for j, (t, k) in enumerate(zip(content[1:], sig[1:])):
                            fl = at.get((i0 + arr[j], k))
                            if fl is None:
                                break
                            pick[t] = (k, i0 + arr[j], fl)
                        if len(pick) == len(content) and arrangement(pick) == arr:
                            found = True
                            break
                    if found:
                        break
                if found:
                    original.add(bsb(ref))
        return eng, signature, original
    return find, text


def main():
    find, text = build()
    nodes = []
    for f in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            r = json.loads(ln)
            if r.get("type") in TYPES:
                w = phrase_of(r["name"])
                if len([x for x in w if x not in STOP]) >= 2:
                    nodes.append((r, w))
    rows = []
    for r, w in nodes:
        eng, signature, original = find(w)
        if not eng:
            continue
        refs = set()
        for x in r.get("refs") or []:
            mm = re.match(r"^(\S+) (\d+):(\d+)", x)
            if mm:
                refs.add(f"{mm.group(1)}.{mm.group(2)}.{mm.group(3)}")
        allv = set(eng) | original
        rows.append({
            "id": r["id"], "name": r["name"], "type": r["type"], "phrase": " ".join(w),
            "refs": sorted(refs, key=vkey),
            "english": {v: eng[v] for v in sorted(eng, key=vkey)},
            "signature": signature,
            "original": sorted(original, key=vkey),
            "across": sorted(original - set(eng), key=vkey),
            "new": sorted(allv - refs, key=vkey),
            "common": len(allv) > COMMON})
    rows.sort(key=lambda x: (x["common"], -len(x["new"])))
    with gzip.open(OUT / "phrase-occurrences.jsonl.gz", "wt", encoding="utf-8") as f:
        f.write(json.dumps({"_note": "Multi-word concept nodes found where the text says them: "
                            "in English (BSB, ASV, WEB, YLT) and, through the Berean "
                            "editors' Strong's tagging, wherever the same Hebrew or Greek "
                            "words stand together however translated "
                            "(tools/phrases/phrase_search.py). An index of where the "
                            "phrase occurs, not a claim that each occurrence is the concept."})
                + "\n")
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    report(rows, text)
    print(f"multi-word nodes {len(nodes)}; found in the text {len(rows)}; "
          f"common {sum(1 for x in rows if x['common'])}; with verses beyond their refs "
          f"{sum(1 for x in rows if x['new'] and not x['common'])}; found across the "
          f"language divide {sum(1 for x in rows if x['across'])} nodes, "
          f"{sum(len(x['across']) for x in rows)} verses")


def label(v):
    b, c, n = v.split(".")
    return f"{b} {c}:{n}"


def report(rows, text):
    L = ["# Multi-word concepts found in the text", "",
         "Built by `tools/phrases/phrase_search.py`. Doug, 2026-09-30, on \"living water\": "
         "*\"make sure all relevant ones are represented in the graph\"*. Each node's name "
         "searched as a phrase in the Berean, ASV, WEB and YLT; then, through the words the "
         "Berean editors tagged behind it, the same Hebrew or Greek words wherever they stand "
         "together. **Across** = found only in the original, under another English "
         "rendering.", "",
         f"- nodes found in the text: {len(rows)}; common (over {COMMON} verses, marked, "
         f"not a concept marker on their own): {sum(1 for x in rows if x['common'])}", ""]
    for x in rows:
        if not x["new"] and not x["across"]:
            continue
        sig = "; ".join(f"{l}: " + " + ".join(f"{k[1]} ({k[0]})" for k in s)
                        for l, s in x["signature"].items())
        L.append(f"### {x['name']}  `{x['id']}`" + ("  · common" if x["common"] else ""))
        L.append(f"- cited before: {len(x['refs'])}; in English: {len(x['english'])}; "
                 f"original words together: {len(x['original'])}; across the language "
                 f"divide: {len(x['across'])}; new to the node: {len(x['new'])}")
        if sig:
            L.append(f"- words behind it: {sig}")
        if x["across"]:
            L.append("- across: " + "; ".join(
                f"{label(v)} “{text['BSB'].get(v, ([], ''))[1][:70]}”" for v in x["across"][:8]))
        if not x["common"]:
            L.append("- new: " + ", ".join(label(v) for v in x["new"][:40])
                     + (f" … +{len(x['new']) - 40}" if len(x["new"]) > 40 else ""))
        L.append("")
    (ROOT / "docs" / "review" / "PHRASE-SEARCH.md").write_text("\n".join(L) + "\n",
                                                               encoding="utf-8")


if __name__ == "__main__":
    main()
