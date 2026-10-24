"""The review list for sorting the entity store's `concept` records.

2026-09-28: sort them — ideas stay concepts, things become what they
are — it is important to get this right, particularly with regard to items as
symbols, and "heart" is an interesting case on the edge of symbol and tangible
thing in the way that it is normally used.

THE RULE THE LIST FOLLOWS (docs/MEANING-ONTOLOGY.md, layer 4): image or
thing is decided PER USE, not per record. A viper in Acts 28:3 is a snake;
"you brood of vipers" (Mat 3:7) is an image. So every cited verse of a
record is marked on its own evidence:

    figurative   the BSB puts "like" / "as" right before the word, or the
                 record's `likened_to` / `signifies` relation cites that
                 verse
    literal      a relation of handling cites that verse: gave, took, ate,
                 bought, made, destroyed, carried, kept at
    unmarked     neither — which says nothing either way

and the record's proposal follows from its verses:

    THING        a physical thing, no figurative use among its verses
    IMAGE        a physical thing, every marked use figurative
    BOTH         a physical thing used both ways: split — the thing for
                 its literal verses, an Image for the figurative ones
    EDGE         a word whose ordinary senses straddle body and inner life,
                 or thing and idea (heart, hand, face, flesh, horn, way):
                 the "heart" case — its own section, for decision
    IDEA         stays a concept (counted, not listed)

"Physical" is WordNet's reading of the head of the name (PRINCIPLES 44a:
via English, an overlay): its usual sense is a thing. "Straddles" means its
first four senses include both a physical thing and an inner or abstract
one.

    python tools/meaning/sort_concepts.py     # docs/review/CONCEPT-SORT.md
                                              # out/concept-sort.jsonl
"""
import collections
import glob
import gzip
import json
import re
from pathlib import Path

from nltk.corpus import wordnet as wn

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
THING = {"noun.artifact", "noun.animal", "noun.plant", "noun.object",
         "noun.substance", "noun.food", "noun.body", "noun.location"}
INNER = {"noun.feeling", "noun.cognition", "noun.attribute", "noun.state",
         "noun.motive", "noun.act", "noun.communication", "noun.group",
         "noun.relation", "noun.possession"}
CLASS = {"noun.artifact": "Artifact", "noun.animal": "Animal",
         "noun.plant": "Plant", "noun.object": "NaturalObject",
         "noun.substance": "Substance", "noun.food": "Food",
         "noun.body": "BodyPart", "noun.location": "Place"}
FIGURE_REL = {"likened_to", "signifies"}
HANDLED = {"gave", "took", "ate", "bought", "made", "destroyed", "carried",
           "kept_at"}
SKIP = {"the", "a", "an", "his", "her", "my", "your", "their", "its", "our",
        "new", "best", "wild", "ruined", "morning", "boundary", "threshing"}
BOOK = {"Gen": "Gen", "Exod": "Exo", "Lev": "Lev", "Num": "Num",
        "Deut": "Deu", "Josh": "Jos", "Judg": "Jdg", "Ruth": "Rut",
        "1Sam": "1Sa", "2Sam": "2Sa", "1Kgs": "1Ki", "2Kgs": "2Ki",
        "1Chr": "1Ch", "2Chr": "2Ch", "Ezra": "Ezr", "Neh": "Neh",
        "Esth": "Est", "Job": "Job", "Ps": "Psa", "Prov": "Pro",
        "Eccl": "Ecc", "Song": "Sng", "Isa": "Isa", "Jer": "Jer",
        "Lam": "Lam", "Ezek": "Ezk", "Dan": "Dan", "Hos": "Hos",
        "Joel": "Jol", "Amos": "Amo", "Obad": "Oba", "Jonah": "Jon",
        "Mic": "Mic", "Nah": "Nam", "Hab": "Hab", "Zeph": "Zep",
        "Hag": "Hag", "Zech": "Zec", "Mal": "Mal", "Matt": "Mat",
        "Mark": "Mrk", "Luke": "Luk", "John": "Jhn", "Acts": "Act",
        "Rom": "Rom", "1Cor": "1Co", "2Cor": "2Co", "Gal": "Gal",
        "Eph": "Eph", "Phil": "Php", "Col": "Col", "1Thess": "1Th",
        "2Thess": "2Th", "1Tim": "1Ti", "2Tim": "2Ti", "Titus": "Tit",
        "Phlm": "Phm", "Heb": "Heb", "Jas": "Jas", "1Pet": "1Pe",
        "2Pet": "2Pe", "1John": "1Jn", "2John": "2Jn", "3John": "3Jn",
        "Jude": "Jud", "Rev": "Rev"}


PREP = r"\b(?:of|in|into|to|from|with|for|on|at|by|upon|over|under|among)\b"


def head(name):
    """The word the name is about: before any preposition ("fifty righteous
    ones IN the city" is about the ones; "consolation TO me" about
    consolation) and any relative ("a rebuke THAT insults me")."""
    n = re.split(PREP, name.lower())[0]
    n = re.split(r"\b(?:that|which|who|and)\b", n)[0]
    ws = [w for w in re.findall(r"[a-z]+", n) if w not in SKIP]
    return ws[-1] if ws else None


def senses(h):
    """WordNet's first four senses of the head, and what they say:
    thing — the leading senses are physical;
    straddles — the TWO LEADING senses split a physical thing against an
      inner or abstract one, as heart's do (the locus of feeling; the
      organ). The first pass used any of four senses and swept in 195
      words, because nearly every English noun has SOME abstract sense;
    idea — otherwise."""
    ss = wn.synsets(h, pos="n") if h else []
    if not ss:
        return [], "none"
    lex = [s.lexname() for s in ss[:4]]
    if wn.morphy(h, "v") == h and len(wn.synsets(h, pos="v")) > len(ss):
        return lex, "verb-like"
    top2 = lex[:2]
    if len(top2) == 2 and any(x in THING for x in top2) and \
            any(x in INNER for x in top2):
        return lex, "straddles"
    phys = [x in THING for x in lex]
    if phys[0] and sum(phys) >= min(2, len(lex)):
        return lex, "thing"
    return lex, "idea"


FIGURE_WORDS = re.compile(r"\b(figure|figurative|image|picture|metaphor|"
                          r"symbol|symbolic|likened|stands? for|simile|"
                          r"emblem)\b", re.I)


def bsb_verse(ref, bsb):
    b, cv = ref.rsplit(" ", 1)
    c, v = cv.split(":")[0], cv.split(":")[1].split("-")[0]
    return bsb.get(f"{BOOK.get(b, b)}.{c}.{v}", "")


def snippet(text, word, width=46):
    m = re.search(r"\b" + re.escape(word[:5]), text, re.I) if word else None
    if not m:
        return text[:2 * width]
    a = max(0, m.start() - width)
    return ("…" if a else "") + text[a:m.end() + width] + "…"


def main():
    E = {}
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl",
                     encoding="utf-8"):
        e = json.loads(line)
        E[e["id"]] = e
    bsb = {}
    for line in gzip.open(OUT / "bsb-align.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(line)
        if r.get("ref"):
            bsb[r["ref"]] = r.get("text") or ""
    fig_refs = collections.defaultdict(set)      # record -> refs, figurative
    lit_refs = collections.defaultdict(set)      # record -> refs, handled
    partners = collections.defaultdict(list)
    for p in glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl")):
        for line in open(p, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            for me, other in ((r.get("src"), r.get("dst")),
                              (r.get("dst"), r.get("src"))):
                if (E.get(me) or {}).get("type") != "concept":
                    continue
                if r["type"] in FIGURE_REL:
                    fig_refs[me] |= set(r.get("refs") or [])
                    partners[me].append(
                        f"{r['type']} {(E.get(other) or {}).get('name', other)}")
                elif r["type"] in HANDLED and me == r.get("dst"):
                    lit_refs[me] |= set(r.get("refs") or [])

    # the figure detector's images and similes (tools/meaning/figures.py),
    # by BSB verse and the vehicle's words: a copular "X is Y" whose Y is
    # this word, or "like Y"
    moved = json.loads((OUT / "versemap.json").read_text(
        encoding="utf-8")).get("moved") or {}
    detected = collections.defaultdict(set)
    for line in gzip.open(OUT / "meaning-figures.jsonl.gz", "rt",
                          encoding="utf-8"):
        r = json.loads(line)
        if r.get("verdict") in ("image", "simile"):
            v = (r.get("predicate") or r.get("vehicle") or "").lower()
            detected[moved.get(r["ref"], r["ref"])] |= set(
                re.findall(r"[a-z]+", v))

    rows, counts = [], collections.Counter()
    for e in E.values():
        if e["type"] != "concept":
            continue
        h = head(e["name"])
        lex, kind = senses(h)
        marks = {}
        for ref in e.get("refs") or []:
            t = bsb_verse(ref, bsb)
            like = bool(h) and re.search(
                r"\b(like|as)\s+(?:\w+\s+){0,3}" + re.escape(h[:5]), t, re.I)
            b, cv = ref.rsplit(" ", 1)
            key = f"{BOOK.get(b, b)}.{cv.split(':')[0]}." \
                  f"{cv.split(':')[1].split('-')[0]}"
            clash = bool(h) and any(w[:5] == h[:5] for w in detected[key])
            if ref in fig_refs[e["id"]] or like or clash:
                marks[ref] = "figurative"
            elif ref in lit_refs[e["id"]]:
                marks[ref] = "literal"
            else:
                marks[ref] = "unmarked"
        figs = sum(v == "figurative" for v in marks.values())
        lits = sum(v == "literal" for v in marks.values())
        # the record's own description calling it a figure counts for the
        # record as a whole (the extraction read the verse)
        described = bool(FIGURE_WORDS.search(e.get("desc") or ""))
        if described and not figs:
            figs = 1
        if kind == "straddles":
            prop = "EDGE"
        elif kind == "thing":
            prop = "BOTH" if figs and lits else "IMAGE" if figs else "THING"
        else:
            prop = "IDEA"
        counts[prop] += 1
        if prop == "IDEA":
            continue
        refs = e.get("refs") or []
        rows.append({
            "id": e["id"], "name": e["name"], "head": h, "wordnet": lex,
            "proposal": prop,
            "to": CLASS.get(lex[0]) if lex else None,
            "marks": marks, "partners": partners[e["id"]][:3],
            "desc": (e.get("desc") or "")[:160].replace("\n", " "),
            "verse": snippet(bsb_verse(refs[0], bsb), h) if refs else "",
            "first_ref": refs[0] if refs else ""})

    with open(OUT / "concept-sort.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    write_md(rows, counts)
    print(dict(counts))


SECTION = {
    "IMAGE": ("Images — a thing, and every marked use is a picture",
              "Proposed: type `image` (an Image node collecting these uses). "
              "Check: is each use really figurative?"),
    "BOTH": ("Both — a thing in some verses, a picture in others",
             "Proposed: split. The thing (its class below) for the literal "
             "verses; an Image for the figurative ones."),
    "THING": ("Things — no figurative use found among the cited verses",
              "Proposed: the class shown. **Check the symbol question here "
              "first**: 'no figurative use found' means nothing MARKED one — "
              "a verse can use a thing as a picture without 'like'."),
    "EDGE": ("On the edge — the word's ordinary senses straddle body and "
             "inner life, or thing and idea",
             "Doug's heart case. Not moved by this list: see the proposal "
             "at the top."),
}


READ = [
    ("image", "Images — used as a picture in their verses",
     "Each becomes (or joins) an **Image** node, `drawn_from` the thing of the "
     "same word — two nodes, as Doug asked: the literal thing and its image. "
     "Where an Image record already exists for the word (image_table, "
     "image_clay ...), this record merges into it."),
    ("both", "Both — a thing in some verses, a picture in others",
     "Split: the thing for its literal verses, an Image for the figurative "
     "ones."),
    ("edge", "On the edge — Doug's heart case: a body or thing word whose "
     "ordinary biblical sense is inner or abstract",
     "Proposed: not moved as things, and not flagged as a figure on every "
     "verse. Each becomes a SENSE of its own, `extendedFrom` the literal one "
     "(heart the inner self, from heart the organ) — the language made the "
     "figure, not the verse. **Decide per word**: which of these are that, "
     "and which are plain things after all."),
    ("other", "Not concepts at all",
     "A group of people, a named place, a time — moved to that type."),
    ("thing", "Things — literal in their verses",
     "Moved to the class shown (legacy type `concept` kept). Where a thing "
     "sits INSIDE a picture (the heel in the trap, the neck 'like the tower "
     "of David'), the note says which word is the image."),
    ("idea", "Stays an idea — the rule's flag was wrong",
     "Acts, qualities, idioms, misparsed names: they stay `concept`."),
]


def write_md(rows, counts):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from concept_verdicts import V
    p = ROOT / "docs" / "review" / "CONCEPT-SORT.md"
    p.parent.mkdir(exist_ok=True)
    by = {r["id"]: r for r in rows}
    tally = {k: sum(1 for i in by if V.get(i, ("?",))[0].split(":")[0] == k)
             for k, *_ in READ}
    agree = sum(1 for i, r in by.items() if i in V and (
        (r["proposal"] == "THING" and V[i][0].startswith("thing")) or
        (r["proposal"] == "IMAGE" and V[i][0] == "image") or
        (r["proposal"] == "EDGE" and V[i][0] == "edge")))
    out = [
        "# Sorting the `concept` records — review list",
        "",
        "Doug, 2026-09-28: *\"to me this is important to get right, "
        "particularly with regard to items as symbols\"*, and *\"heart is an "
        "interesting case that is on the edge of symbol and tangible thing\"*. "
        "Then: *\"I would go with the llm analysis and mark it as such.\"* "
        "**Applied 2026-09-28** — each record carries `attrs.sorted` (by: "
        "\"LLM reading: Claude Opus 5.5, 2026-09-28\", verdict, why) and its "
        "old type as `attrs.legacy_type`; re-laid after every merge by "
        "`python -m bibleont.conceptsort apply` from "
        "`ontology/concept-sort.json`. To change a verdict, change "
        "`tools/meaning/concept_verdicts.py` and re-export.",
        "",
        "**Corrected while applying** — the validator found four records "
        "that the old graph's relations handled as things (gave, took, "
        "destroyed): *beautiful fawns* (Gen 49:21) is the BSB's reading; the "
        "Hebrew lemma is אֵמֶר 'word' — Naphtali 'gives words of beauty', so "
        "an idea; *ox* is a real ox in Job 24:3 and a picture in Job 6:5, so "
        "both; *fangs* are a body part inside a picture, as the heel in the "
        "trap; *plenty of silver* stays an image and the old relation was "
        "the error — God is LIKENED to silver (Job 22:25), not giving it, "
        "corrected in its staged batch.",
        "",
        "**How it was made.** A rule (`tools/meaning/sort_concepts.py`) "
        f"listed {len(by)} of the 1,388 concept records whose name is a "
        "physical thing by WordNet, or straddles thing and inner life; the "
        f"other {counts['IDEA']:,} stay ideas and are not listed. Then Claude "
        "read every listed record against its cited verses (BSB) and wrote a "
        "verdict with a reason — **the READING column is that reading; the "
        "RULE column is what the rule proposed.** They agree on "
        f"{agree} of {len(by)}, which is why the rule is not applied blind: "
        "the images it misses are mostly unmarked (Job's poetry — Bildad's "
        "papyrus, Leviathan's potsherds — has no 'like'), and its 'edge' list "
        "caught ordinary things.",
        "",
        "**Image or thing is decided per USE, not per word** (the design, "
        "layer 4): the literal thing and its image are two nodes joined by "
        "`drawn_from`, as the old graph did — 'the lion of 1 Peter 5:8 and "
        "the lion Daniel was shut in with are not one node'.",
        "",
        "| reading | records |", "|---|---|"] + [
        f"| {title.split(' — ')[0]} | {tally[k]} |" for k, title, _ in READ] + [
        "",
        "One trap worth knowing: *'this stream of words'* (Job 11:2) is an "
        "image only in the BSB — the Hebrew says 'a multitude of words'. A "
        "translation supplies no identity (PRINCIPLES 44), so it stays an "
        "idea.",
        ""]
    for key, title, note in READ:
        rs = sorted((by[i] for i in by
                     if V.get(i, ("?",))[0].split(":")[0] == key),
                    key=lambda r: r["name"].lower())
        out += [f"## {title} ({len(rs)})", "", note, "",
                "| record | reading | why | rule | first verse (BSB) |",
                "|---|---|---|---|---|"]
        for r in rs:
            verdict, why = V[r["id"]]
            rule = {"THING": f"thing:{r['to']}", "IMAGE": "image",
                    "BOTH": "both", "EDGE": "edge"}[r["proposal"]]
            verse = r["verse"].replace("|", "/")
            out.append(f"| **{r['name']}** `{r['id']}` | {verdict} | "
                       f"{why.replace('|', '/')} | {rule} | "
                       f"{r['first_ref']}: {verse} |")
        out.append("")
    p.write_text("\n".join(out) + "\n", encoding="utf-8")


def write_md_rule_only(rows, counts):
    p = ROOT / "docs" / "review" / "CONCEPT-SORT.md"
    p.parent.mkdir(exist_ok=True)
    out = ["# Sorting the `concept` records — review list",
           "",
           "Made by `tools/meaning/sort_concepts.py` (2026-09-28). Doug: "
           "*\"to me this is important to get right, particularly with regard "
           "to items as symbols.\"* Nothing has been moved; this is the list "
           "to correct first.",
           "",
           f"Of 1,388 concept records: **{counts['IDEA']:,} stay ideas** "
           f"(not listed), **{counts['THING']}** proposed as things, "
           f"**{counts['IMAGE']}** as images, **{counts['BOTH']}** split both "
           f"ways, **{counts['EDGE']}** on the edge.",
           "",
           "How each cited verse is marked: *figurative* — the BSB has "
           "\"like\"/\"as\" just before the word, or the record's "
           "`likened_to`/`signifies` relation cites the verse; *literal* — a "
           "relation of handling (gave, took, ate, bought, made, destroyed, "
           "carried) cites it; *unmarked* — neither, which is not a claim "
           "either way. The class is WordNet's reading of the name's head "
           "word, via English.",
           ""]
    for key in ("IMAGE", "BOTH", "THING", "EDGE"):
        rs = sorted((r for r in rows if r["proposal"] == key),
                    key=lambda r: r["name"].lower())
        title, note = SECTION[key]
        out += [f"## {title} ({len(rs)})", "", note, "",
                "| record | proposed | verses: fig / lit / unmarked | "
                "first verse (BSB) | also |", "|---|---|---|---|---|"]
        for r in rs:
            m = collections.Counter(r["marks"].values())
            figs = [k for k, v in r["marks"].items() if v == "figurative"]
            to = r["to"] or "?"
            prop = {"IMAGE": "image", "BOTH": f"{to} + image",
                    "THING": to, "EDGE": "decide"}[key]
            also = "; ".join(r["partners"]) or (
                "fig: " + ", ".join(figs[:3]) if figs else "")
            verse = r["verse"].replace("|", "/")
            out.append(
                f"| **{r['name']}** `{r['id']}` | {prop} | "
                f"{m['figurative']} / {m['literal']} / {m['unmarked']} | "
                f"{r['first_ref']}: {verse} | {also} |")
        out.append("")
    p.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
