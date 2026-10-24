"""MENTIONS: every place the text names an individual, joined to its record.

2026-09-28, on the structure graph and the general graph: link them
level-agnostically (mentions, tells, narrates/describes), starting with
mentions. The entity store ties each record to the text by a handful of
sample verses (the ark of the covenant: 2, in ~200); this joins every word
occurrence that names a person, place or people to its record — and every
pronoun S5 resolved to one of those words.

WHICH RECORD, WHEN A NAME IS SHARED (dozens of Azariahs), by the strongest
evidence there is, recorded on each mention:
    cited      the record cites this very verse
    tipnr      STEP Bible's TIPNR names the individual at this verse, for
               this word's Strong's number, and that individual is this
               record (tools/meaning/tipnr.py; plan A.17b). Only between
               people, never for an ancestor of a people, never where it
               would join two of our records. Where TIPNR names someone with
               no record here, the mention is held, not guessed
    chapter    only one record of that name cites this chapter
    book       only one record of that name cites this book
    only       only one record has that name at all
    (else)     left unassigned, and counted — never guessed
A pronoun inherits its referent's record, with `via: refers_to` (and
`reading: BSB` where S6's layer resolved it).

Names are matched after normalising both sides: lower case, no possessive
('s), no leading of/the/to/and, MACULA's dot-joins undone. The divine name
יְהוָה ("the LORD", 6,348 occurrences) is keyed by its Hebrew lemma to the
store's one record for the designations of God (`god`, PRINCIPLES 2's
held-together subject).

    python tools/meaning/mentions.py            # report
    python tools/meaning/mentions.py --write    # out/mentions.jsonl.gz
"""
import argparse
import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "builder"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
from source import norm  # noqa: E402
from sort_concepts import BOOK  # noqa: E402
import tipnr  # noqa: E402

TYPES = ("person", "place", "group", "being", "creature")
NT = {"Mat", "Mrk", "Luk", "Jhn", "Act", "Rom", "1Co", "2Co", "Gal", "Eph", "Php",
      "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm", "Heb", "Jas", "1Pe", "2Pe",
      "1Jn", "2Jn", "3Jn", "Jud", "Rev"}
# THE FAULTS THE UI COMMITTEE FOUND (2026-09-30; plan A.17, P-72):
#   A SHARED NAME'S PERSON NEEDS THE NOMINATIVE. "the King of Israel" (Matt
#     27:42) went to Jacob by the book test (Jacob is cited in Matthew 1), and
#     the clause subjects of "let him come down ... he trusts in God" followed
#     it. Where the original marks case and the name is held by a person AND a
#     group, a genitive, dative or accusative occurrence is not given to the
#     person on chapter or book evidence: "of Israel", "to Israel" are the
#     people. Held, not guessed; the pronouns that pointed at it hold with it.
#   NOT A NAME. Ἠλί and Ἐλωΐ are Aramaic for "my God" (Matt 27:46, Mark
#     15:34), which MACULA tags proper; they went to Eli the priest as the
#     only record of that name. A lexical fact about two lemmas.
#   Tried and withdrawn the same day: "a name assigned only because it is
#   unique is not assigned across the testaments" held 135 names, Eli's 2
#   among them and Isaiah's 22, Gomorrah's 19, Sodom's 9, Jonah's 7 beside
#   them -- the New Testament names the Old's people constantly. And "a
#   pronoun inherits nothing from a genitive antecedent" held 252, 131 of
#   them Jesus ("the words of Jesus ... he"); the nominative rule alone
#   already empties the Matt 27:42 chain.
OBLIQUE = {"genitive", "dative", "accusative"}
NOT_A_NAME = {"Ἠλί", "Ἐλωΐ"}
LEMMA_TO = {"יהוה": "god", "יה": "god"}
LEAD = {"of", "the", "to", "and", "a", "an", "from", "in", "by", "for"}
GLUE = LEAD | {"at", "on", "into", "with", "toward", "unto", "as"}


def key(s):
    # a hyphen is a space: "Ebed-melech" (a record) and "Ebed Melech" (two
    # words MACULA split one name into) are one name
    s = (s or "").lower().replace("’", "'").replace(".", " ").replace("-", " ")
    s = re.sub(r"'s\b|'\b", "", s)
    ws = re.findall(r"[a-z]+(?:-[a-z]+)*", s)
    while ws and ws[0] in LEAD:
        ws = ws[1:]
    return " ".join(ws)


def macula_ref(ref, moved_back):
    """'Gen 25:21' (English numbering) -> 'Gen.25.21' (MACULA's)."""
    b, cv = ref.rsplit(" ", 1)
    c, v = cv.split(":")[0], cv.split(":")[1].split("-")[0]
    eng = f"{BOOK.get(b, b)}.{c}.{v}"
    return moved_back.get(eng, eng)


# PEOPLE THE TEXT CALLS BY A RELATIONSHIP. 2026-10-01, on Bathsheba:
# Uriah's wife is counted too. 2 Samuel names her once in the story that is about
# her (11:3) and otherwise calls her "the wife of Uriah" (11:26, 12:10, 12:15)
# -- so a resolver that follows names finds her in four verses of two
# chapters. An epithet is a kin word (its Hebrew and Greek lemmas) qualified by
# a word resolved to a given person; where the structure has exactly that, the
# kin word is a mention of the record. Each entry is one reading, with the
# verse that grounds it; add one only where the text makes the identification
# itself (2 Sam 11:3: "Bathsheba ... the wife of Uriah the Hittite").
EPITHETS = [
    {"record": "bath_sheba", "kin": {"אִשָּׁה", "γυνή"}, "of": "uriah_hittite",
     "grounds": "2Sam 11:3"},
]


def known_by_epithet(mentions, words):
    """Assign each kin word qualified by a resolved person to the record its
    epithet names. Returns how many were assigned. Runs before the pronouns,
    so "she" after "the wife of Uriah" follows it."""
    # lemmas compared normalised: a Hebrew word typed here and the same word in
    # the data can order their vowel marks differently, and the first run of
    # this matched nothing for that reason
    want = {}
    for ep in EPITHETS:
        for lem in ep["kin"]:
            want.setdefault(norm(lem), []).append(ep)
    n = 0
    for line in gzip.open(OUT / "structure-edges.jsonl.gz", "rt", encoding="utf-8"):
        e = json.loads(line)
        if e["type"] != "qualifier" or e["src"] in mentions:
            continue
        head = words.get(e["src"])
        lem = norm((head or {}).get("lemma") or "")
        if lem not in want:
            continue
        of = mentions.get(e["dst"], (None,))[0]
        for ep in want[lem]:
            if of == ep["of"]:
                mentions[e["src"]] = (ep["record"], "epithet")
                n += 1
    return n


def hold_parallel_disagreements(mentions, words):
    """THE TELLINGS OF ONE EVENT MUST AGREE ON WHO A NAME IS, or the weak
    evidence gives way. The second panel of first-time visitors, 2026-10-01:
    Mark 6:3's "the son of Mary" went to Mary the mother of James and Joses
    by the book test -- she is the only Mary whose record cites Mark -- while
    Matthew 13:55, the same scene, went to Jesus' mother. The ruling: find why the
    reference went to the wrong Mary and fix the rule, not just this one
    case; and it is acceptable that some references to Mary are not
    resolved in terms of which Mary they reference.

    Within one event told in more than one book, where a name is resolved to
    different records in different books: an assignment by `cited` stands.
    A weaker one (chapter, book) stands only if it agrees with the one
    record the event's cited assignments give that name; otherwise it is
    held -- unresolved, said so, never swapped for the other record (a long
    event can name two people of one name: 1 Chr 11:43's Maacah is not
    David's wife).

    Measured before it was built: 28 names disagree across tellings, and the
    weak side was usually wrong -- "John" in Luke 9:28 as the Baptist, "John"
    in Mark 1:4 as Zebedee's son, "Simon" in John 1:41 as Judas Iscariot's
    father, "Philip" in Mark 3:18 as Herod's brother, "Eliakim" in 2 Kings
    18:18 as Jehoiakim. The rule holds those; it also holds some that were
    right (Matthew 13:55's Mary), which is the price of not guessing.
    Returns {occurrence: how it had been assigned} for what it held."""
    p = OUT / "event-nodes.json"
    if not p.exists():
        return {}
    events = json.loads(p.read_text(encoding="utf-8")).get("events", {})
    spans = collections.defaultdict(list)
    for eid, e in events.items():
        books = {t["first"].split(".")[0] for t in e["tellings"]}
        if len(books) < 2:
            continue
        for t in e["tellings"]:
            b, c1, v1 = t["first"].split(".")
            _b, c2, v2 = t["last"].split(".")
            spans[BOOK.get(b, b)].append(((int(c1), int(v1)), (int(c2), int(v2)), eid))
    groups = collections.defaultdict(list)   # (event, name) -> [(occ, rec, how, book)]
    for occ, (rid, how) in mentions.items():
        w = words.get(occ)
        if not w or not w.get("proper"):
            continue
        b, c, v = occ.split("#")[0].split(".")
        for lo, hi, eid in spans.get(b, ()):
            if lo <= (int(c), int(v)) <= hi:
                groups[(eid, key(w.get("text")))].append((occ, rid, how, b))
    held = {}
    for rows in groups.values():
        if len({r for _, r, _, _ in rows}) < 2:
            continue
        # a disagreement BETWEEN books; one book naming two people is not one
        by_rec_books = collections.defaultdict(set)
        for _, r, _, b in rows:
            by_rec_books[r].add(b)
        if len({frozenset(s) for s in by_rec_books.values()}) < 2 or \
                len({b for _, _, _, b in rows}) < 2:
            continue
        cited = {r for _, r, h, _ in rows if h == "cited"}
        # the possibilities are the records the tellings themselves gave the
        # name; the card lists them with the verse (decided: list the
        # possibilities with the verse)
        maybe = sorted({r for _, r, _, _ in rows})
        for occ, r, how, _b in rows:
            if how in ("chapter", "book") and not (len(cited) == 1 and r in cited):
                held[occ] = (how, maybe)
    for occ in held:
        mentions.pop(occ, None)
    return held


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    moved = json.loads((OUT / "versemap.json").read_text(
        encoding="utf-8")).get("moved") or {}
    back = {e: m for m, e in moved.items()}
    E = [json.loads(l) for l in open(ROOT / "ontology" / "entities" /
                                    "entities.jsonl", encoding="utf-8")]
    by_name = collections.defaultdict(set)
    refs_of = {}
    for e in E:
        if e["type"] not in TYPES:
            continue
        for n in [e["name"]] + (e.get("aka") or []) + \
                ([e["name_kjv"]] if e.get("name_kjv") else []):
            if key(n):
                by_name[key(n)].add(e["id"])
        rs = set()
        for r in e.get("refs") or []:
            try:
                rs.add(macula_ref(r, back))
            except (ValueError, IndexError):
                pass
        refs_of[e["id"]] = rs

    type_of = {e["id"]: e["type"] for e in E}

    # TIPNR's people joined to our person records of the same name: a pair
    # is joined when each is the other's best match by shared verses. Best
    # one way only is not enough -- Acts 1:13 lists all the apostles, so the
    # James of Luke 6:16 (Judas's father) shares a verse with both our James
    # records and tied them, and his "James" stayed with Alphaeus's son. An
    # individual no record chooses is someone we have no record of. TIPNR's
    # refs are English-numbered; `moved` turns ours (MACULA's) into those.
    tip = tipnr.load()
    tip_rec, tip_none, tip_skip = {}, set(), set()
    if tip:
        tip_at, tip_refs, tip_names = tip
        tip_vs = {t: {back.get(v, v) for v in vs} for t, vs in tip_refs.items()}
        rec_ts = collections.defaultdict(set)
        for t in tip_vs:
            for n in tip_names[t]:
                for c in by_name.get(key(n), ()):
                    if type_of.get(c) == "person":
                        rec_ts[c].add(t)

        def best(score):
            score = sorted(score, reverse=True)
            if score and score[0][0] and (len(score) == 1 or score[1][0] < score[0][0]):
                return score[0][1]
        rec_best = {c: best((len(refs_of[c] & tip_vs[t]), t) for t in ts)
                    for c, ts in rec_ts.items()}
        # ONE OF THEIRS THAT IS TWO OF OURS is not used. TIPNR follows
        # tradition where the text does not decide: the letter's James is the
        # Lord's brother, Mark 15:40's "James the less" is Alphaeus's son,
        # Revelation's John is Zebedee's. The records keep those apart (read
        # without harmonizing), and TIPNR would have joined them a verse at a
        # time.
        claimed = collections.Counter(rec_best.values())
        tip_skip = {t for t, n in claimed.items() if t and n > 1}
        for t, vs in tip_vs.items():
            if t in tip_skip:
                continue
            cands = {c for c, ts in rec_ts.items() if t in ts}
            r = best((len(refs_of[c] & vs), c) for c in cands)
            if r and rec_best.get(r) == t:
                tip_rec[t] = r
            elif not any(rec_best.get(c) == t for c in cands) and \
                    not any(refs_of[c] & vs and rec_best.get(c) is None for c in cands):
                tip_none.add(t)
    else:
        print("TIPNR not found (tools/fetch_tipnr.py) -- shared names fall to "
              "the chapter and book tests")

    def pick(cands, ref, case=None, strong=None):
        # only between people: whether "Israel" is the man or the nation is
        # not TIPNR's to say (see tipnr.py)
        S = tip_at.get((strong, moved.get(ref, ref))) if tip and strong and \
            all(type_of.get(i) == "person" for i in cands) else None
        # a record that cites this very verse is our own reading of it, and
        # outranks TIPNR's
        if S and (S & tip_skip or any(ref in refs_of[i] for i in cands)):
            S = None
        if S:
            if len(S) == 1:
                t = next(iter(S))
                r = tip_rec.get(t)
                if r in cands:
                    return r, "tipnr"
                if t in tip_none:
                    return None, "held: TIPNR names someone without a record"
            else:
                # several of the name in one verse (Acts 1:13's three
                # Jameses): only they remain, for the tiers below
                cands = {tip_rec.get(t) for t in S} & set(cands) or cands
        chap, book = ref.rsplit(".", 1)[0], ref.split(".")[0]
        shared = ({type_of.get(i) for i in cands} >= {"person", "group"})
        for how, test in (("cited", lambda i: ref in refs_of[i]),
                          ("chapter", lambda i: any(r.rsplit(".", 1)[0] == chap
                                                    for r in refs_of[i])),
                          ("book", lambda i: any(r.split(".")[0] == book
                                                 for r in refs_of[i]))):
            hit = [i for i in cands if test(i)]
            if len(hit) == 1:
                if how != "cited" and shared and case in OBLIQUE \
                        and type_of.get(hit[0]) == "person":
                    return None, f"held: oblique, person and group share it ({how})"
                return hit[0], how
            if len(hit) > 1:
                return None, f"several ({how})"
        if len(cands) == 1:
            return next(iter(cands)), "only"
        return None, "several"

    words, mentions, stats = {}, {}, collections.Counter()
    for line in gzip.open(OUT / "structure-nodes.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if d.get("word"):
            words[d["id"]] = d
    for nid, d in words.items():
        lem = norm(d.get("lemma") or "")
        if lem in LEMMA_TO:
            mentions[nid] = (LEMMA_TO[lem], "lemma")
            stats["lemma"] += 1
            continue
        if not d.get("proper"):
            continue
        if d.get("lemma") in NOT_A_NAME:
            stats["held: not a name (my God)"] += 1
            continue
        # ONE NAME IN SEVERAL WORDS. MACULA splits some compound names into
        # words that each carry the whole name's lemma -- בַּעַל שָׁלִשָׁה as
        # "Baal" + "Shalisha" (2 Kgs 4:42) -- and the piece "Baal" matched the
        # god as the only record of that name; "Baal" of Baal-Peor and
        # "Melech" of Ebed-Melech the same way. The pieces are read together.
        text = d.get("text")
        lem = (d.get("lemma") or "").strip()
        if " " in lem:
            base, n = nid.split("#w")
            i = j = int(n)
            while (words.get(f"{base}#w{i - 1}") or {}).get("lemma", "").strip() == lem:
                i -= 1
            while (words.get(f"{base}#w{j + 1}") or {}).get("lemma", "").strip() == lem:
                j += 1
            if j > i:
                # the pieces' English: each may repeat the whole name
                # ("Obed-Edom", "Obed-Edom") or be a word around it ("at",
                # Micah's vocative "O", the Berean's supplied "[is]"); only
                # distinct pieces that begin with a capital are joined
                pieces = []
                for x in range(i, j + 1):
                    t = (words[f"{base}#w{x}"].get("text") or "").strip()
                    if t and t not in pieces and t[0].isupper() and t != "O" \
                            and t.lower() not in GLUE:
                        pieces.append(t)
                text = " ".join(pieces) or text
        k = key(text)
        cands = by_name.get(k)
        # two names for one place, side by side: "Bethlehem Ephrathah" (Mic
        # 5:2) is no record's name, but each piece names Bethlehem. Taken
        # only when EVERY piece names a record and they agree -- "Baal Meon"
        # does not ("Meon" names nothing), so "Baal" is not the god
        if not cands and " " in lem and text != d.get("text"):
            sets = [by_name.get(key(p)) for p in text.split(" ")]
            if all(sets):
                cands = set.intersection(*map(set, sets)) or None
        if not cands:
            stats["no record of that name"] += 1
            continue
        rid, how = pick(cands, d["ref"], d.get("case"),
                        tipnr.strong_key(d.get("lang"), d.get("strong")))
        stats[how] += 1
        if rid:
            mentions[nid] = (rid, how)
    held = hold_parallel_disagreements(mentions, words)
    for how, _maybe in held.values():
        stats[f"held: tellings disagree ({how})"] += 1
        stats[how] -= 1
    stats["epithet (a kin word qualified by a resolved person)"] = \
        known_by_epithet(mentions, words)
    # pronouns: through S5's refers_to (and S6's BSB readings), each checked
    # for agreement first (2026-10-04, after the small errors were to be fixed):
    #   THE BEREAN'S CAPITAL. It capitalises a pronoun for God -- Acts 7:47
    #     "Solomon built a house for Him" -- and the Greek there reads "the
    #     house of Jacob" at 7:46, so the only agreeing antecedent in the
    #     Greek was Jacob. A capital Him / Himself / Me / Myself resolved to a
    #     record that is not divine was wrong in about 140 places: Jesus's
    #     "Him" as Pilate, the Baptist, Judas, the Jordan river; "in
    #     remembrance of Me" (1 Cor 11:24) as Paul; the Father's "of Me"
    #     (2 Pet 1:17) as Peter. ("My" is left out: it starts sentences.)
    #   NUMBER. A plural pronoun is not one person: "Grace be with you all"
    #     (1 Tim 6:21) is not Timothy, "our God" (1 Chr 13:2) is not David.
    #     567 were. God is not a person record here, so Genesis 1:26's "Let
    #     us" is untouched.
    #   A capital counts only where the Berean's verse shows it mid-sentence:
    #     a sentence-initial "My" reaches the word as "of Me" (James 2:1, "My
    #     brothers", is James; Luke 1:46, "My soul", is Mary), so the verse
    #     must have "Me" / "Him" / "Himself", or "My" / "His" after a
    #     lower-case word ("This is My beloved Son", 2 Pet 1:17).
    DIVINE = {"god", "jesus", "holy_ghost", "the_father", "yahweh",
              "spirit_of_god", "angel_of_the_lord"}
    CAPITAL = {"Him", "Himself", "Me", "Myself"}
    to_bsb = {m: e for e, m in BOOK.items()}
    bsb = {}
    for line in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        v = json.loads(line)
        if "b" in v:
            bsb[f"{v['b']}.{v['c']}.{v['v']}"] = v["t"]

    def berean(ref):
        b, c, v = moved.get(ref, ref).split(".")
        return bsb.get(f"{to_bsb.get(b, b)}.{c}.{v}", "")

    def disagrees(src, rec):
        w = words.get(src) or {}
        last = (w.get("text") or "").split()[-1:] or [""]
        if last[0] in CAPITAL and rec not in DIVINE:
            poss = {"Me": "My", "Myself": "My", "Him": "His", "Himself": "His"}[last[0]]
            text = berean(src.split("#")[0])
            if re.search(rf"\b{last[0]}\b", text) or re.search(rf"[a-z]\s+{poss}\b", text):
                return "held: the Berean's capital says God"
        if w.get("number") == "plural" and type_of.get(rec) == "person":
            return "held: a plural pronoun is not one person"
        return None

    pron = 0
    for f, reading in (("structure-edges.jsonl.gz", None),
                       ("structure-readings.jsonl.gz", "BSB")):
        for line in gzip.open(OUT / f, "rt", encoding="utf-8"):
            e = json.loads(line)
            if e["type"] != "refers_to":
                continue
            tgt = e["dst"]
            if tgt in mentions and e["src"] not in mentions:
                why = disagrees(e["src"], mentions[tgt][0])
                if why:
                    stats[why] += 1
                    continue
                mentions[e["src"]] = (mentions[tgt][0],
                                      "refers_to" + (" (BSB)" if reading
                                                     else ""))
                pron += 1
    stats["pronouns and implicit subjects"] = pron

    tot = sum(v for k, v in stats.items()
              if k not in ("pronouns and implicit subjects",))
    print("NAME OCCURRENCES and how each was assigned:")
    for k, v in stats.most_common():
        print(f"  {k:32} {v:>7,}")
    per = collections.Counter(r for r, _ in mentions.values())
    E_by = {e["id"]: e for e in E}
    verses_before = {i: len(refs_of[i]) for i in refs_of}
    verses_after = collections.defaultdict(set)
    for nid, (rid, _) in mentions.items():
        verses_after[rid].add(nid.split("#")[0])
    gained = [(len(verses_after[i]), verses_before.get(i, 0), i)
              for i in verses_after]
    print(f"\n{len(mentions):,} mentions of {len(per):,} records "
          f"(of {len(refs_of):,} person/place/group/being/creature records)")
    print("records' verses, cited before -> mentioned now (the largest):")
    for after, before, i in sorted(gained, reverse=True)[:12]:
        print(f"  {E_by[i]['name'][:34]:34} {before:>4} -> {after:>5,}")
    if a.write:
        with gzip.open(OUT / "mentions.jsonl.gz", "wt", encoding="utf-8") as f:
            for nid, (rid, how) in sorted(mentions.items()):
                f.write(json.dumps({"occurrence": nid, "record": rid,
                                    "how": how}, ensure_ascii=False) + "\n")
        print(f"\nwrote out/mentions.jsonl.gz")
        # what was held, with its possibilities: a card says "not settled"
        # rather than leaving a gap that looks like nothing was there
        def fuller(occ):
            """'Mary' followed within two words by 'Magdalene' is first a
            possibility for Mary Magdalene, whose record the bare name misses"""
            base, w = occ.split("#w")
            for k in (1, 2):
                nxt = words.get(f"{base}#w{int(w) + k}")
                if nxt and nxt.get("proper"):
                    got = by_name.get(key(f"{words[occ].get('text')} {nxt.get('text')}"))
                    return sorted(got or ())
            return []

        with open(OUT / "mentions-unsettled.jsonl", "w", encoding="utf-8") as f:
            for occ, (how, maybe) in sorted(held.items()):
                maybe = fuller(occ) + [m for m in maybe if m not in fuller(occ)]
                f.write(json.dumps({"occurrence": occ,
                                    "text": words.get(occ, {}).get("text"),
                                    "candidates": maybe, "was": how},
                                   ensure_ascii=False) + "\n")
        print(f"wrote out/mentions-unsettled.jsonl ({len(held)})")


if __name__ == "__main__":
    main()
