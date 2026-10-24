"""Anchor every concept node to its words (plan 4.7, the seed of the loop).

2026-09-28: the nodes should provide more of a clue where the important word
instances are than the words, while the words are good for finding synonyms.
The 1,194 concept nodes (and 74 titles) came from the
first extraction anchored to 1-16 cited verses each and to no lexemes, so
nothing downstream could use them.

A concept's words are found BY METHOD, not by hand: the Berean editors
tagged their own English with Strong's numbers, so the Hebrew and Greek the
BSB renders "love" with are the lexemes the text calls love. A concept's
English (its name and its aka) is stemmed ("loved", "loves" -> love) and
matched against every tagged span's words; the Strong's numbers under them,
by share, are its anchors.

Three kinds come out, and the page says which:
    word       one English word, anchored (faith -> πίστις, πιστεύω)
    compound   several words that must occur together (eternal life:
               ζωή with αἰώνιος) — anchored per part, instances need all
    marked     a title whose word is ordinary ("the Son of God" is 99% בֵּן,
               plain "son"): its instances need the text's marks, not its
               lexeme — listed, not anchored here

    python tools/meaning/concept_anchors.py
        -> out/concept-anchors.jsonl.gz
        -> docs/review/CONCEPT-ANCHORS.md   (the table to check)
"""
import collections
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
SHARE = 0.08           # a Strong's number under at least this share
MIN_N = 3              # and at least this many tags
LANG_SHARE = 0.30      # or: the main rendering within its own language
LANG_MIN = 5           # ... in at least this many uses
STOP = set("the of a an and in to for his her their my your our god lord "
           "s it is be that with by as at on from".split())
TITLES = {"title"}
THINGS = {"image", "object"}


def same_root(a, b):
    """One word family: a noun beside its own verb (זֶבַח / זָבַח, ἀγάπη /
    ἀγαπάω) is one meaning named two ways, not a double meaning. Letters
    only, no vowels or accents; Hebrew without its vowel letters and final
    forms, compared on the first two consonants; Greek on the first four."""
    import unicodedata

    def plain(s):
        s = unicodedata.normalize("NFD", s or "")
        s = "".join(ch for ch in s if unicodedata.category(ch)[0] == "L")
        return s.translate(str.maketrans("ךםןףץ", "כמנפצ"))
    pa, pb = plain(a), plain(b)
    if not pa or not pb:
        return False
    if "א" <= pa[0] <= "ת":
        pa, pb = (p[0] + p[1:].replace("ו", "").replace("י", "") for p in (pa, pb))
        return pa[:2] == pb[:2]
    return pa[:4].lower() == pb[:4].lower()


def stem(w):
    """A crude English stem: enough that loved/loves/loving meet love."""
    w = w.lower().strip(".,;:!?'\"“”‘’()[]-")
    for suf in ("ingly", "eth", "est", "ing", "ies", "ied", "ed", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            w = w[: -len(suf)]
            break
    return w.rstrip("e")


USFM = ROOT / "data" / "raw" / "usfm" / "engbsb"
TAG = re.compile(r'\\w ([^|\\]+)\|strong="([HG]\d+)[a-z]?"\\w\*')


def main():
    # MACULA'S OWN GLOSS ON EVERY WORD. Tried first, and wrong: the Berean
    # tags. out/bsb-align.jsonl.gz left Deut 6:5's "love" untagged and
    # tagged John 3:16's "so loved" as οὕτως; the BSB USFM it came from has
    # not one tag for ἀγαπάω or αἰώνιος in all of John — "love" got 86 tags,
    # led by φιλέω and "good". MACULA glosses every word ("loved",
    # "eternal"), so a concept's English meets the lexemes it glosses.
    import sys
    sys.path.insert(0, str(ROOT / "tools" / "builder"))
    import source as S
    by_stem = collections.defaultdict(collections.Counter)
    klass = collections.defaultdict(collections.Counter)   # Strong's -> MACULA class
    lemma_of = {}
    gloss_of = collections.defaultdict(collections.Counter)
    by_stem_nom = collections.defaultdict(collections.Counter)
    for lang in ("hebrew", "greek"):
        for p in S.files(lang):
            _root, ws = S.load(p, lang)
            for w in ws.values():
                st = "".join(ch for ch in (w.get("strongnumberx") or
                                           w.get("strong") or "")
                             if ch.isdigit())
                if not st or w.get("class") not in ("noun", "verb", "adj"):
                    continue
                k = ("g" if lang == "greek" else "h") + str(int(st))
                klass[k][w.get("class")] += 1
                lemma_of.setdefault(k, w.get("lemma"))
                gloss_of[k][(w.get("english") or w.get("gloss") or "").lower()] += 1
                # used as a thing: a noun, an adjective, or a participle that
                # stands as one -- רֹעֶה "shepherd" (Ps 23:1) and יוֹצֵר "potter"
                # are verbs in form. A participle that is its clause's verb
                # (MACULA role v/vc) is not: "those crossing over" kept עָבַר
                # on the cross card until this
                nominal = w.get("class") != "verb" or (
                    str(w.get("type") or "").startswith("participle")
                    and w.get("role") not in ("v", "vc"))
                for x in re.findall(r"[A-Za-z]+", w.get("english") or
                                    w.get("gloss") or ""):
                    if x.lower() not in STOP:
                        by_stem[stem(x)][k] += 1
                        if nominal:
                            by_stem_nom[stem(x)][k] += 1
    rows, candidates = [], []
    # THE WORD IN THE CARD'S OWN VERSE (plan 4.7a, tools/meaning/card_words.py):
    # where none of a card's cited verses held its anchored words, the word
    # its verse does use, judged blind ("scales" -> Job 41:15's מָגֵן)
    from_verses = collections.defaultdict(list)
    cw = ROOT / "ontology" / "card-words.jsonl"
    if cw.exists():
        for ln in open(cw, encoding="utf-8"):
            r = json.loads(ln)
            from_verses[r["card"]].append({"key": r["key"], "verse": r["verse"]})
    senses = collections.defaultdict(set)
    sp = ROOT / "ontology" / "anchor-senses.jsonl"
    if sp.exists():
        for ln in open(sp, encoding="utf-8"):
            r = json.loads(ln)
            if r["verdict"] == "drop":
                senses[(r["card"], r["word"])].add(r["key"])
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl",
                     encoding="utf-8"):
        e = json.loads(line)
        # observances, objects and images too (2026-09-28): the baptism card
        # showed 2 verses (Matt 3:6, Acts 2:38) because an OBSERVANCE was
        # never anchored to βαπτίζω — the baptism card looked sparse, not
        # mentioning baptism events like Acts 8:36 and 8:38
        # A PLACE NAMED BY AN ORDINARY WORD too -- east, north, the garden, the
        # desert -- one word, and as a thing (nouns only). The BibleProject
        # reader (2026-10-02) could not follow the eastward thread: the "east"
        # card listed no verses at all, because places were never anchored
        # (their names are resolved as names, which is right for Jerusalem
        # and wrong for "east"). Cases to catch: Psalm 103:12 ("as far as the east is
        # from the west") and the Magi "from the east" (Matt 2:1). Phrases
        # ("a place where gold") are left alone.
        #
        # ONLY THE COMPASS, for now. Tried first on every one-word ordinary
        # name (54 places): the directions came out right, but some records so
        # named are one particular place -- "the house at Capernaum", Isaac's
        # field, Job's land -- and would have listed every house, field and
        # land in the Bible. A compass point is never one place. The rest wait
        # for a ruling (P-83).
        common_place = (e["type"] == "place" and re.sub(r"^the\s+", "", e["name"].strip().lower())
                        in ("east", "west", "north", "south"))
        # A KIND OF CREATURE TOO (C-D14, the 2026-10-02 evaluation: the
        # cherubim and leviathan cards listed no verses at all -- creatures
        # were never anchored). Only a kind, named by one word without "the":
        # "lions", "cherubim", "leviathan". A particular animal is named with
        # "the" -- "the serpent" of Gen 3, "the ram caught in a thicket", "the
        # scapegoat" -- and must not take every serpent or ram in the text.
        # "The" is not enough: Abram's heifer, ram and goat (Gen 15:9) and
        # Abraham's calf (Gen 18:7) are particular animals named without it.
        # A kind is one the card cites in two chapters or more.
        chapters = {re.sub(r":\d+.*$", "", r) for r in e.get("refs") or []}
        kind_of_creature = (e["type"] == "creature" and not re.match(r"(?i)the\s", e["name"])
                            and len(re.findall(r"[A-Za-z]+", e["name"])) == 1
                            and len(chapters) >= 2)
        if e["type"] not in ("concept", "title", "observance", "object", "image") \
                and not common_place and not kind_of_creature:
            continue
        names = [e["name"]] + (e.get("aka") or [])
        head = [w for w in re.findall(r"[A-Za-z]+", e["name"])
                if w.lower() not in STOP]
        if not head:
            continue
        kind = "marked" if e["type"] in TITLES else \
            "word" if len(head) == 1 else "compound"
        parts = []
        # each part of the name (a compound has several), aka widening it
        # A THING IS A NOUN (2026-09-30, "Rule, then candidates"): the
        # cross card was anchored to עָבַר "cross over" at 70% and σταυρός at
        # 29%, because the English "cross" renders both, and its "Where the
        # text speaks of it" listed 561 verses of crossings. An image or an
        # object named by ONE word names a thing, so only the words used as
        # things count: nouns, adjectives, participles. Not concepts or
        # observances ("love" is ἀγαπάω and ἀγάπη, baptism is βαπτίζω), and
        # not compound names, whose other parts may be verbs ("streams
        # flowing down"; applied to them, 26 parts lost every anchor and
        # "lie down" fell through to שֶׁקֶר, a lie).
        thing = (e["type"] in THINGS or common_place or kind_of_creature) and kind == "word"

        def anchors_of(src):
            c = collections.Counter()
            for nm in names:
                for x in re.findall(r"[A-Za-z]+", nm):
                    if x.lower() not in STOP and (len(head) == 1 or
                                                  stem(x) == stem(w)):
                        c.update(src.get(stem(x), {}))
            tot = sum(c.values())
            # THE SHARE WITHIN EACH LANGUAGE. Measured over both together, the
            # Old Testament's hundreds swamped the New's handful: "east" kept
            # מִזְרָח and קֶדֶם and dropped ἀνατολή, the Magi's "from the east"
            # (Matt 2:1). A word is an anchor if it holds the share among the
            # words of its own language that render the name.
            #
            # Only as a second door, and a narrow one. Tried first as THE rule
            # (8% within the language): 1,047 cards gained words and the
            # sample was noisy wherever a language had few renderings --
            # "wages" took עָשָׂה "make", "outward man" took unrelated Greek,
            # "east" took פָּנִים "face". So the old rule stands, and a word
            # comes in this way only if it is the main rendering in its own
            # language: 30% of it, in at least 5 uses.
            by_lang = collections.Counter()
            for k, v in c.items():
                by_lang[k[0]] += v
            #
            # And for now only on the places just brought in. Even narrowed, a
            # sample of 20 of the 329 existing cards it changed had about 5
            # wrong ("multitude" took χρόνος "time", "plenty of silver" took
            # fine linen) -- a change to every card is decided on a sample
            # (P-83), not a side effect of fixing "east".
            # A word in by this door carries its share WITHIN its language: the
            # server keeps anchors at 15% or more, and ἀνατολή's share of all
            # renderings of "east" is a few percent, so it was filtered out
            # again on the card.
            def share(k, v):
                s = v / tot
                if common_place and by_lang[k[0]] and v >= LANG_MIN:
                    s = max(s, v / by_lang[k[0]])
                return round(s, 2)
            out = [(k, v, share(k, v)) for k, v in c.most_common()
                   if (tot and v / tot >= SHARE and v >= MIN_N)
                   or (common_place and by_lang[k[0]]
                       and v / by_lang[k[0]] >= LANG_SHARE and v >= LANG_MIN)]
            return tot, out[:8]
        for w in head:
            tot, anchors = anchors_of(by_stem)
            dropped = []
            if thing:
                t2, a2 = anchors_of(by_stem_nom)
                if a2:
                    dropped = [k for k, *_ in anchors if k not in {x for x, *_ in a2}]
                    tot, anchors = t2, a2
            # a word both judges said is another sense (tools/meaning/
            # anchor_senses.py): off this card, even if none is left -- "No
            # word of the text is tied to this yet" is true, and the fig
            # leaves' "leave behind" was not. Shares stay as measured.
            judged = senses.get((e["id"], w.lower()), set())
            anchors = [a for a in anchors if a[0] not in judged]
            parts.append({"word": w.lower(), "tags": tot, "anchors": anchors,
                          **({"not_nouns": dropped} if dropped else {})})
        rows.append({"id": e["id"], "name": e["name"], "kind": kind,
                     "refs": len(e.get("refs") or []), "parts": parts,
                     **({"from_verses": from_verses[e["id"]]} if e["id"] in from_verses
                        else {})})
        # THE REST GO TO A JUDGE: two anchors of one language that differ in
        # class, or two nouns of one language that each hold a fifth -- a
        # double meaning the rule cannot see (Rahab the woman, rahab the
        # monster), or one meaning named two ways. Not decided here.
        # every anchor, not only those at a fifth: a judge reads them (decided
        # 2026-09-30), and at 20% the well card's טוֹב "it is well" (16%) hid
        for p in parts:
            a = [(k, s) for k, _v, s in p["anchors"]]
            for i, (k1, s1) in enumerate(a):
                for k2, s2 in a[i + 1:]:
                    if k1[0] != k2[0] or same_root(lemma_of.get(k1), lemma_of.get(k2)):
                        continue
                    c1, c2 = (klass[k].most_common(1)[0][0] for k in (k1, k2))
                    candidates.append((e["id"], e["type"], p["word"], k1, c1, s1,
                                       k2, c2, s2))
    with gzip.open(OUT / "concept-anchors.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    anchored = [r for r in rows if all(p["anchors"] for p in r["parts"])]
    counts = collections.Counter(r["kind"] for r in rows)
    lines = ["# Concept anchors — the concepts' words, by the Berean tags", "",
             "Made by `tools/meaning/concept_anchors.py` (plan 4.7). For each "
             "concept node: the Strong's numbers the Berean editors tagged "
             "its English with, by share. **word**: one English word; "
             "**compound**: parts that must occur together; **marked**: a "
             "title whose word is ordinary — its instances need the text's "
             "marks, so its anchors below are NOT its instances.", "",
             f"{len(rows):,} concepts and titles ({dict(counts)}); every part "
             f"anchored: {len(anchored):,}.", "",
             "Sorted by how often the old graph cited the concept (its "
             "importance there), then name.", "",
             "| concept | kind | part | tags | anchors (Strong's, share) |",
             "|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (-r["refs"], r["name"]))[:250]:
        for i, p in enumerate(r["parts"]):
            a = ", ".join(f"{k} {int(s * 100)}%" for k, _v, s in p["anchors"]) \
                or "—"
            lines.append(f"| {r['name'] if i == 0 else ''} | "
                         f"{r['kind'] if i == 0 else ''} | {p['word']} | "
                         f"{p['tags']} | {a} |")
    thinned = [(r["id"], p["word"], p["not_nouns"]) for r in rows for p in r["parts"]
               if p.get("not_nouns")]
    lines += ["", "## Images and objects: verbs set aside", "",
              "A thing is a noun (Doug, 2026-09-30). The verbs each image or object "
              "card's English also renders, no longer its anchors:", ""]
    lines += [f"- `{i}` ({w}): " + ", ".join(f"{k} {lemma_of.get(k) or ''}" for k in ks)
              for i, w, ks in sorted(thinned)]
    lines += ["", "## Double meanings for Doug to judge", "",
              "Two anchors of one language, each at least a fifth of the card's words, "
              "that differ in class (a noun and a verb) or are two different nouns. "
              "Some are one meaning named two ways (a noun beside its own verb), some "
              "are two words sharing an English spelling. The rule above cannot tell "
              "which; a reader can.", "",
              "| card | type | word | first | second |", "|---|---|---|---|---|"]
    for i, t, w, k1, c1, s1, k2, c2, s2 in sorted(candidates):
        lines.append(f"| `{i}` | {t} | {w} | {k1} {lemma_of.get(k1) or ''} ({c1}, "
                     f"{int(s1 * 100)}%) | {k2} {lemma_of.get(k2) or ''} ({c2}, {int(s2 * 100)}%) |")
    # the same list, per card, for a judge: which of the card's words carry
    # its meaning (2026-09-30: Sonnet 5.5 judges them)
    ents = {json.loads(ln)["id"]: json.loads(ln) for ln in
            open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8")}
    by_card = {}
    for i, t, w, *_ in candidates:
        if (i, w) in by_card:
            continue
        r = next(r for r in rows if r["id"] == i)
        p = next(p for p in r["parts"] if p["word"] == w)
        by_card[(i, w)] = {
            "card": i, "type": t, "name": r["name"], "word": w,
            "desc": (ents[i].get("desc") or "")[:400],
            "anchors": [{"key": k, "lemma": lemma_of.get(k), "class": klass[k].most_common(1)[0][0],
                         "share": s, "glosses": [g for g, _ in gloss_of[k].most_common(4)]}
                        for k, _v, s in p["anchors"]]}
    (OUT / "anchor-candidates.json").write_text(
        json.dumps(list(by_card.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(by_card)} cards to judge; "
          f"verbs set aside on {len(thinned)} image/object parts; "
          f"{len(candidates)} double-meaning candidates")
    (ROOT / "docs" / "review" / "CONCEPT-ANCHORS.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows):,} concepts; {dict(counts)}; fully anchored "
          f"{len(anchored):,}")


if __name__ == "__main__":
    main()
