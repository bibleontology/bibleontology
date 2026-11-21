"""THE GAPS PASS: what well-known thing the Bible says about this person or event is missing from its card?
(Mac mini, gemma4:26b; asked 2026-10-30, queued behind the errors pass.)

One card per call: a person (or group, or being) or an event, the way the graph holds it: its name, what it is also
called, and up to 40 short plain-English lines of what the card says, each with its verses (the strongest by number of
citing verses), and for an event the verses that tell it. The model lists up to 3 things the Bible text itself says
about the person or event that are important and missing, each with book, chapter and verse and the few words of that
verse. The Mac only FLAGS candidates; nothing it answers reaches a card or the data. Claude judges the flags later.

What the model sees: names, aliases, the one-line identification of a person (`disambiguation`), relation lines and
verse references. It sees no note, no description and nothing from docs/. It is never shown verse text: it has to
bring the verse from what it knows, so the mechanical filter in `report` (does the cited verse exist, are the quoted
words in it) is the first check on every flag.

THE CARD'S LINES
  person  every relation (src or dst) with refs that is not `held` or `described`, minus the structural types that only
          wire a node to an idea (STRUCTURAL_SKIP). "denied Jesus", "brother of Andrew", "Herod killed John the Baptist".
          Eligible: a person, group or being with at least MIN_REL such relations.
  event   all events (ids starting event_). The structure the event card holds (parts, patterns, echoes, speeches
          spoken in it) plus its CAST, the way the app's event card builds it: relations of a cast kind whose own verse
          lies inside one of the event's tellings.
  Lines with the same text are merged (their verses joined). Ranked by number of citing verses, concrete first.

PLANTED FAULTS (recall). About 20% of the sample: a copy of a real card with one of its strongest, best-known lines
REMOVED (a concrete line, one of the top three by citing verses, whose other end is a person, place, group, being,
object, creature or event). The key records the removed line and its verses. Caught = the model lists something in
the same chapter as one of them. Plants are made only from cards that show whole (at most 40 lines), so a cut never
hides the removed line's sibling. The key and the plants stay in out/grunt/jobs/<name>.key.jsonl, never in the job.

EXAMPLES. The three worked examples in the brief use Peter, Paul and the death of Abel; those three cards are left
out of the 6a sample and its plants (they are in the full job).

    python tools/meaning/local_gap_check.py export-sample -> out/grunt/jobs/6a-gap-check-sample.jsonl (+ .key.jsonl)
    python tools/meaning/local_gap_check.py export        -> out/grunt/jobs/6b-gap-check.jsonl (+ .key.jsonl); `report 6` reads it
    python tools/meaning/local_gap_check.py report [6a|6]    after `grunt.py pull` (default 6a)
"""
import collections
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from derive import BOOK  # noqa: E402
from bibleont.refs import parse_ref  # noqa: E402
from local_relation_check import (DIVINE, NODE_TYPES, STRUCTURAL_TYPES, bible, ename, entities,  # noqa: E402
                                  phrase)

JOBS, DONE = ROOT / "out" / "grunt" / "jobs", ROOT / "out" / "grunt" / "done"
# The full job is 6b, not 6: the runner takes queue files in name order and "6-" sorts before "6a", which would run the
# whole pass before the sample that decides whether it is worth running.
NAMES = {"6a": "6a-gap-check-sample", "6": "6b-gap-check",
         # the same pass over today's cards (2026-11-12; Doug: "completeness tends to be an issue")
         "28": "28-gap-check",
         # the thin people job 28 left out (2026-11-13; Doug: "make sure mac is working as well"): persons, groups
         # and beings with 1 or 2 lines (1,130 cards had two or fewer relations), exported with
         # BIBLEONT_GAP_MIN_REL=1 and filtered to the cards 28 did not ask about, events excluded (28 had them all)
         "32": "32-gap-check-thin",
         # every event card again after the cast rewrite of 2026-11-14 (filtered to events at export)
         "35": "35-gap-check-events"}
OPTIONS = {"temperature": 0, "num_ctx": 6144}
SEED = 31
CARD_MAX = 40          # lines shown of one card
MIN_REL = 8            # a person needs this many relations that become lines
# Job 28 (2026-11-12) asks of thinner cards too: at 8, 1,811 people were left out, the cards where completeness is
# likeliest to fail (Doug: "completeness tends to be an issue"). BIBLEONT_GAP_MIN_REL overrides, for one export.
MIN_REL = int(__import__("os").environ.get("BIBLEONT_GAP_MIN_REL", MIN_REL))
N_PERSONS, N_EVENTS = 100, 50
N_PLANT_PERSONS, N_PLANT_EVENTS = 22, 8
EXAMPLE_IDS = {"peter", "paul", "event_cain_murders_abel"}
PERSON_KINDS = ("person", "group", "being")
CONCRETE_ENDS = {"person", "place", "group", "being", "object", "creature", "event"}
# the structural types that only wire a node to an idea: a person's card has no use for them in this question
STRUCTURAL_SKIP = {"speaks_of", "in_theme", "asserted_by", "spoken_in", "instance_of", "recounts", "conditional_on",
                   "answered_in", "specializes"}
# what the app's event card prints as the cast (app2/server.py EVENT_CAST_KINDS, minus the withheld came_upon)
EVENT_CAST_KINDS = frozenset((
    "told", "states", "took", "gave", "traveled_to", "killed", "persecuted", "healed", "appeared_to", "sent",
    "besought", "blessed", "cursed", "conquered", "fought", "attacked", "destroyed", "conspired_against",
    "imprisoned", "accused", "judged", "deceived", "rebuked", "warned", "ate", "heard", "explained", "quoted",
    "appointed", "charged", "ministered_to", "buried_at", "born_at", "died_at", "built", "repaired", "made",
    "carried", "wrote_to", "answered"))
EVENT_STRUCTURE = {"part_of", "same_steps_as", "re_enacts", "instance_of", "spoken_in", "takes_up", "drawn_from",
                   "occasion_of"}
IS = {"part_of": "is part of", "spoken_in": "is spoken in", "located_in": "is located in",
      "instance_of": "is an instance of", "occasion_of": "is the occasion of", "same_steps_as": "tells the same steps as",
      "re_enacts": "re-enacts", "takes_up": "takes up", "drawn_from": "is drawn from"}

BRIEF = """You check a Bible knowledge graph for gaps. You get a card: who or what it is, and what the card already \
says, each with its verses. List up to 3 things the Bible text itself says about this person or event that are \
important and missing from the card. Each must give the book, chapter and verse where the text says it, and the few \
words of that verse. Only things the Bible states; no tradition, no later history, no interpretation. If nothing \
important is missing, answer an empty list.

How to judge:
- The card is a person, a group or an event. "card_lines" is what it already says, each with its verses. For an event, \
"tellings" are the passages that tell it.
- "Important" means a reader who knows the Bible would expect the card to hold it: a major act, a well-known saying, \
a defining event, a main relationship. Not a small detail, and not something the card already says in other words: \
check every line before you list anything.
- If "more_not_shown" is given, the card holds that many more lines than you see. Then list only what is plainly \
important and could not be among them.
- "ref" is one verse, like "Matt 26:74". "words" is a few words copied from that verse in the Berean Standard Bible's \
wording. Give a ref and words only if you are sure of them; leave the item out otherwise.
- Most important first. An empty list is a good answer when the card is full.

Worked examples:

Card: {"card": "person", "name": "Simon Peter", "also_called": ["Cephas", "Simon"], "who": "the apostle", \
"card_lines": ["brother of Andrew -- Matt 4:18", "followed Jesus -- Luke 18:28", "loved Jesus -- John 21:15"]}
Answer: {"missing": [{"what": "Peter denied Jesus three times", "ref": "Matt 26:74", "words": "I do not know the \
man!"}]}
(The denial is a defining act of Peter and the card does not hold it.)

Card: {"card": "event", "name": "Cain murders Abel", "tellings": ["Gen 4:1-16"], "card_lines": ["Cain brought some of \
the fruit of the soil as an offering to the LORD -- Gen 4:3", "Abel brought the best portions of his flock -- Gen 4:4", \
"Cain killed Abel -- Gen 4:8", "the LORD asked Cain where his brother Abel was -- Gen 4:9", "the LORD cursed Cain -- \
Gen 4:11", "Cain settled in the land of Nod -- Gen 4:16"]}
Answer: {"missing": []}
(The card holds the offerings, the killing, the question and the curse; nothing important is left out.)

Card: {"card": "person", "name": "Paul", "also_called": ["Saul"], "who": "the apostle to the Gentiles", \
"card_lines": ["breathed out murderous threats against the disciples -- Acts 9:1", "requested letters to the \
synagogues in Damascus -- Acts 9:2"]}
Answer: {"missing": [{"what": "On the road to Damascus Jesus spoke to Saul and asked why he persecuted Him", "ref": \
"Acts 9:4", "words": "Saul, Saul, why do you persecute Me?"}]}
(Not listed, though many people know it: that Paul was beheaded in Rome. That is tradition. The Bible does not say it.)

Answer with ONLY a JSON object: {"missing": [{"what": "...", "ref": "Book c:v", "words": "..."}]}"""


# ------------------------------------------------------------------ the graph
def eligible_relations():
    """every relation with refs, minus held and described"""
    import glob
    rows = []
    for f in sorted(glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl"))):
        for ln in open(f, encoding="utf-8"):
            if not ln.strip():
                continue
            r = json.loads(ln)
            if r.get("refs") and not r.get("held") and not r.get("described"):
                rows.append(r)
    return rows


def nm(ents, i):
    """a node's name as a line prints it: a saying, passage or pattern in quotes and cut short"""
    n = ename(ents, i)
    if (ents.get(i) or {}).get("type") in NODE_TYPES:
        if re.search(r" at \w+ \d+:\d+$", n):   # a placeholder name ("Leah at Gen 30:13"), not words
            return "a saying"
        n = n.strip("“”\"")
        n = "“" + (n if len(n) <= 60 else n[:57].rstrip() + "...") + "”"
    return n


def refs_label(refs, k=3):
    seen = []
    for x in refs:
        if x not in seen:
            seen.append(x)
    s = ", ".join(seen[:k])
    return s + (f" +{len(seen) - k} more" if len(seen) > k else "")


def add_line(lines, text, refs, rtype, other_type):
    ln = lines.get(text)
    if ln is None:
        lines[text] = {"text": text, "refs": [], "type": rtype,
                       "concrete": rtype not in STRUCTURAL_TYPES and other_type in CONCRETE_ENDS}
        ln = lines[text]
    for x in refs:
        if x not in ln["refs"]:
            ln["refs"].append(x)


def ranked(lines):
    out = list(lines.values())
    for n, ln in enumerate(out):
        ln["n"] = len(ln["refs"])
        ln["_o"] = n
    out.sort(key=lambda ln: (-ln["n"], not ln["concrete"], ln["_o"]))
    for ln in out:
        del ln["_o"]
    return out


def person_card(ents, rels_of, pid):
    e = ents[pid]
    name = ename(ents, pid)
    lines, rows = {}, 0
    for r in rels_of.get(pid, ()):
        if r["type"] in STRUCTURAL_SKIP or r["src"] == r["dst"]:
            continue
        rows += 1
        if r["src"] == pid:
            other = r["dst"]
            text = f"{phrase(r)} {nm(ents, other)}"
        else:
            other = r["src"]
            text = f"{nm(ents, other)} {IS.get(r['type'], phrase(r))} {name}"
        add_line(lines, text, r["refs"], r["type"], (ents.get(other) or {}).get("type"))
    return card_dict(ents, pid, "person", ranked(lines), rows)


def card_dict(ents, i, kind, lines, rows, tellings=None):
    e = ents[i]
    name = ename(ents, i)
    aka = []
    for a in list(e.get("aka") or []) + list((e.get("attrs") or {}).get("aliases") or []):
        if a and a != name and a not in aka:
            aka.append(a)
    return {"id": i, "kind": kind, "name": name, "also_called": aka[:8],
            "who": (e.get("disambiguation") or "")[:200] if kind == "person" else "",
            "tellings": tellings, "rows": rows, "lines": lines, "divine": i in DIVINE}


def shown_lines(card):
    return [f"{ln['text']} -- {refs_label(ln['refs'])}" for ln in card["lines"][:CARD_MAX]]


# ------------------------------------------------------------------ events
def book_index(by):
    """short book -> {(c, v): position} and the list, to expand a span"""
    return {b: [(c, v) for c, v, _, _ in vs] for b, vs in by.items()}


def span_keys(idx, ref_first, ref_last=None):
    """the (book, c, v) keys from the first verse of one ref to the last verse of another (or the same)"""
    p = parse_ref(ref_first)
    q = parse_ref(ref_last) if ref_last else p
    b = BOOK.get(p.book, p.book)
    lo, hi = (p.start_chapter, p.start_verse), (q.end_chapter, q.end_verse)
    return {(b, c, v) for c, v in idx.get(b, ()) if lo <= (c, v) <= hi}


def ref_keys(idx, ref):
    """the (book, c, v) keys one ref covers (a single verse, or its range)"""
    try:
        p = parse_ref(ref)
    except Exception:
        return set()
    b = BOOK.get(p.book, p.book)
    if (p.start_chapter, p.start_verse) == (p.end_chapter, p.end_verse):
        return {(b, p.start_chapter, p.start_verse)}
    return span_keys(idx, ref)


def tell_label(ref_first, ref_last):
    """'Gen 38:1-30' for a telling given as its first and last verse"""
    p, q = parse_ref(ref_first), parse_ref(ref_last or ref_first)
    a, z = f"{p.book} {p.start_chapter}:{p.start_verse}", f"{q.end_chapter}:{q.end_verse}"
    if (p.start_chapter, p.start_verse) == (q.end_chapter, q.end_verse):
        return a
    return f"{a}-{z.split(':')[1]}" if p.start_chapter == q.end_chapter else f"{a}-{z}"


def event_cards(ents, rels, by):
    idx = book_index(by)
    cast_idx = collections.defaultdict(list)   # (book, c, v) -> relations of a cast kind
    for r in rels:
        if r["type"] in EVENT_CAST_KINDS and (ents.get(r["src"]) or {}).get("type") in PERSON_KINDS:
            keys = set()
            for ref in r["refs"]:
                keys |= ref_keys(idx, ref)
            for k in keys:
                cast_idx[k].append(r)
    touching = collections.defaultdict(list)
    tellers = collections.defaultdict(list)
    for r in rels:
        for end in ("src", "dst"):
            if r[end].startswith("event_"):
                touching[r[end]].append(r)
        if r["type"] == "recounts" and r["dst"].startswith("event_"):
            tellers[r["dst"]].append(r["src"])
    out = []
    for eid in sorted(i for i, e in ents.items() if i.startswith("event_") and e.get("type") == "event"):
        e = ents[eid]
        name = ename(ents, eid)
        spans, labels = [], []
        for t in tellers.get(eid, ()):
            te = ents.get(t) or {}
            tr = te.get("refs") or []
            if tr:
                try:
                    spans.append(span_keys(idx, tr[0], tr[-1]))
                    labels.append(tell_label(tr[0], tr[-1]))
                except Exception:
                    pass
        if not spans:
            for ref in e.get("refs") or []:
                try:
                    spans.append(span_keys(idx, ref))
                    labels.append(tell_label(ref, None))
                except Exception:
                    pass
        verses = set().union(*spans) if spans else set()
        lines, rows = {}, 0
        for r in touching[eid]:
            if r["type"] not in EVENT_STRUCTURE or r["src"] == r["dst"]:
                continue
            rows += 1
            if r["src"] == eid:
                other, text = r["dst"], f"it {IS.get(r['type'], phrase(r))} {nm(ents, r['dst'])}"
            else:
                other = r["src"]
                text = f"{nm(ents, other)} {IS.get(r['type'], phrase(r))} it"
            add_line(lines, text, r["refs"], r["type"], (ents.get(other) or {}).get("type"))
        seen = set()
        for k in sorted(verses):
            for r in cast_idx.get(k, ()):
                if id(r) in seen:
                    continue
                seen.add(id(r))
                rows += 1
                other = r["dst"]
                inside = [x for x in r["refs"] if ref_keys(idx, x) & verses]   # only the verses of this telling
                add_line(lines, f"{nm(ents, r['src'])} {phrase(r)} {nm(ents, other)}", inside, r["type"],
                         (ents.get(other) or {}).get("type"))
        out.append(card_dict(ents, eid, "event", ranked(lines), rows, labels))
    return out


# ------------------------------------------------------------------ items
def messages(it):
    msg = {"card": it["kind"], "name": it["name"]}
    if it["also_called"]:
        msg["also_called"] = it["also_called"]
    if it["who"]:
        msg["who"] = it["who"]
    if it["kind"] == "event":
        msg["tellings"] = it["tellings"]
    msg["card_lines"] = it["shown"]
    if it["more"]:
        msg["more_not_shown"] = it["more"]
    return [{"role": "system", "content": BRIEF}, {"role": "user", "content": json.dumps(msg, ensure_ascii=False)}]


def make_item(card, lines=None):
    """the key item (answer key side) for a card, optionally with its lines replaced (a planted copy)"""
    c = dict(card)
    c["lines"] = card["lines"] if lines is None else lines
    c["shown"] = shown_lines(c)
    c["more"] = max(0, len(c["lines"]) - CARD_MAX)
    c.update(plant=None, removed=None, twin=None)
    return c


def write_job(name, its):
    JOBS.mkdir(parents=True, exist_ok=True)
    with open(JOBS / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "local_gap_check"}}) + "\n")
        for it in its:
            f.write(json.dumps({"key": it["key"], "messages": messages(it)}, ensure_ascii=False) + "\n")
    with open(JOBS / f"{name}.key.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in its:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def all_cards():
    ents, by = entities(), bible()
    rels = eligible_relations()
    rels_of = collections.defaultdict(list)
    for r in rels:
        rels_of[r["src"]].append(r)
        if r["dst"] != r["src"]:
            rels_of[r["dst"]].append(r)
    people = [person_card(ents, rels_of, i) for i, e in sorted(ents.items()) if e.get("type") in PERSON_KINDS]
    # the count of relations that become lines decides who is eligible (the long tail is too thin to judge)
    persons = [c for c in people if c["rows"] >= MIN_REL]
    events = event_cards(ents, rels, by)
    return persons, events, people


def plant_from(rnd, item, require_whole=True):
    """a copy of an item with one of its three strongest concrete lines removed; None when it has none"""
    if require_whole and len(item["lines"]) > CARD_MAX:
        return None
    cands = [ln for ln in item["lines"] if ln["concrete"]][:3]
    if not cands:
        return None
    ln = rnd.choice(cands)
    rest = [x for x in item["lines"] if x is not ln]
    p = make_item(item, rest)
    p.update(plant="removed_line", removed={"text": ln["text"], "refs": ln["refs"], "n": ln["n"]}, twin=item["id"])
    return p


def sample_items(persons, events):
    rnd = random.Random(SEED)
    pp = [c for c in persons if c["id"] not in EXAMPLE_IDS]
    ee = [c for c in events if c["id"] not in EXAMPLE_IDS]
    real = [make_item(c) for c in rnd.sample(pp, N_PERSONS)] + [make_item(c) for c in rnd.sample(ee, N_EVENTS)]
    its = list(real)
    notes = []
    for kind, n in (("person", N_PLANT_PERSONS), ("event", N_PLANT_EVENTS)):
        pool = [it for it in real if it["kind"] == kind and not it["divine"]
                and sum(ln["concrete"] for ln in it["lines"]) >= 3 and len(it["lines"]) >= 5]
        rnd.shuffle(pool)
        made = 0
        for it in pool:
            p = plant_from(rnd, it)
            if p:
                its.append(p)
                made += 1
            if made == n:
                break
        notes.append(f"{made} planted {kind} copies (of {len(pool)} eligible bases)")
    rnd.shuffle(its)
    for i, it in enumerate(its):
        it["key"] = f"g{i:04d}"
    return its, notes


def export_sample():
    persons, events, people = all_cards()
    its, notes = sample_items(persons, events)
    write_job(NAMES["6a"], its)
    c = collections.Counter((i["kind"], bool(i["plant"])) for i in its)
    print("\n".join(notes))
    print(f"{len(its)} items {dict(c)} -> {JOBS / (NAMES['6a'] + '.jsonl')}")


def export_all(which="6"):
    persons, events, people = all_cards()
    its = [make_item(c) for c in persons + events]
    for i, it in enumerate(its):
        it["key"] = f"a{i:04d}"
    write_job(NAMES[which], its)
    rows = collections.Counter(min(c["rows"], 40) // 8 * 8 for c in people)
    print(f"{len(persons)} persons/groups/beings with >= {MIN_REL} lines of {len(people)} (divine: "
          f"{sum(c['divine'] for c in persons)}) + {len(events)} events = {len(its)} calls "
          f"({sum(1 for it in its if it['more'])} cards cut at {CARD_MAX} lines; "
          f"{sum(1 for e in events if not e['lines'])} events with no line at all) "
          f"-> {JOBS / (NAMES[which] + '.jsonl')}")
    print("people by relations that become lines (floor of 8s, 40 = 40 or more):", dict(sorted(rows.items())))


# ------------------------------------------------------------------ the report
def parse_answer(content):
    """-> (list of flags, parsed ok)"""
    s = (content or "").strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.M).strip()
    try:
        d = json.loads(s)
        items = d.get("missing") if isinstance(d, dict) else None
        if isinstance(items, list):
            return [{"what": str(x.get("what", "")), "ref": str(x.get("ref", "")), "words": str(x.get("words", ""))}
                    for x in items if isinstance(x, dict)], True
    except Exception:
        pass
    m = re.search(r'"missing"\s*:\s*\[\s*\]', s)
    if m:
        return [], True
    return [], False


def norm(s):
    s = s.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.replace("'", ""))).strip()


def check_flag(by, f):
    """-> (ref exists, words found in the cited verse(s), verse text)"""
    try:
        p = parse_ref(f["ref"])
    except Exception:
        return False, False, ""
    b = BOOK.get(p.book, p.book)
    vs = [t for c, v, _, t in by.get(b, ()) if (p.start_chapter, p.start_verse) <= (c, v) <= (p.end_chapter, p.end_verse)]
    if not vs:
        return False, False, ""
    text = norm(" ".join(vs))
    frags = [norm(x) for x in re.split(r"\.\.\.|…|\[[^\]]*\]", f["words"])]
    frags = [x for x in frags if x]
    ok = bool(frags) and sum(len(x.split()) for x in frags) >= 2 and all(x in text for x in frags)
    return True, ok, " ".join(vs)


def chapters_of(refs):
    out = set()
    for ref in refs:
        try:
            p = parse_ref(ref)
        except Exception:
            continue
        b = BOOK.get(p.book, p.book)
        for c in range(p.start_chapter, p.end_chapter + 1):
            out.add((b, c))
    return out


def verses_of(ref):
    try:
        p = parse_ref(ref)
    except Exception:
        return set()
    b = BOOK.get(p.book, p.book)
    if (p.start_chapter, p.start_verse) == (p.end_chapter, p.end_verse):
        return {(b, p.start_chapter, p.start_verse)}
    if p.start_chapter == p.end_chapter:
        return {(b, p.start_chapter, v) for v in range(p.start_verse, p.end_verse + 1)}
    return {(b, p.start_chapter, p.start_verse)}


def report(which="6a"):
    name = NAMES[which]
    by = bible()
    key = {}
    for ln in open(JOBS / f"{name}.key.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        key[d["key"]] = d
    rows = [json.loads(l) for l in open(DONE / f"{name}.jsonl", encoding="utf-8")]
    flags, errs, bad, secs = {}, 0, 0, []
    for d in rows:
        if "error" in d:
            errs += 1
            continue
        fl, ok = parse_answer(d.get("content"))
        if not ok:
            bad += 1
            continue
        flags[d["key"]] = fl
        secs.append((d["key"], d.get("secs") or 0, d.get("in_tok") or 0, d.get("out_tok") or 0))
    print(f"{len(rows)} answer lines, {len(flags)} parsed of {len(key)} cards; {errs} errors, {bad} unparseable")
    checked = {k: [(f, *check_flag(by, f)) for f in fl] for k, fl in flags.items()}

    def passes(t):
        return t[1] and t[2]

    plants = [k for k in flags if key[k]["plant"]]
    if plants:
        caught = missed = twin_hit = 0
        pass_caught = 0
        by_kind = collections.defaultdict(lambda: [0, 0])
        for k in plants:
            ch = chapters_of(key[k]["removed"]["refs"])
            hit = [t for t in checked[k] if chapters_of([t[0]["ref"]]) & ch]
            by_kind[key[k]["kind"]][1] += 1
            if hit:
                caught += 1
                by_kind[key[k]["kind"]][0] += 1
                pass_caught += any(passes(t) for t in hit)
            real_twin = [r for r in flags if not key[r]["plant"] and key[r]["id"] == key[k]["twin"]]
            if real_twin and any(chapters_of([t[0]["ref"]]) & ch for t in checked[real_twin[0]]):
                twin_hit += 1
        print(f"\nPLANTED (a strong line removed; caught = a flag in the same chapter): caught {caught} of "
              f"{len(plants)} ({dict((k, f'{a} of {b}') for k, (a, b) in by_kind.items())}); of those caught, with a "
              f"flag that also passes the mechanical filter: {pass_caught}; the real twin (line present) flagged "
              f"that chapter too: {twin_hit}")
        for k in plants[:6]:
            r = key[k]["removed"]
            got = [t[0]["ref"] + " " + t[0]["what"][:50] for t in checked[k]]
            print(f"  [{key[k]['name']}] removed: {r['text']} -- {refs_label(r['refs'])}; model listed: {got}")

    real = [k for k in flags if not key[k]["plant"]]
    for kind in ("person", "event", None):
        ks = [k for k in real if kind is None or key[k]["kind"] == kind]
        nflag = sum(1 for k in ks if flags[k])
        nall = sum(len(flags[k]) for k in ks)
        dist = collections.Counter(len(flags[k]) for k in ks)
        print(f"\nREAL {kind or 'all'} cards ({len(ks)}): {nflag} with any flag ({nflag / max(len(ks), 1):.0%}); "
              f"{nall} flags in all; flags per card {dict(sorted(dist.items()))}")
    allf = [(k, t) for k in real for t in checked[k]]
    n_ref = sum(1 for _, t in allf if t[1])
    n_ok = sum(1 for _, t in allf if passes(t))
    print(f"\nMECHANICAL FILTER on {len(allf)} real flags: ref exists in verses.bsb for {n_ref}; and the quoted words "
          f"(2 or more) are in that verse for {n_ok} ({n_ok / max(len(allf), 1):.0%}); cards with a passing flag: "
          f"{len({k for k, t in allf if passes(t)})} of {len(real)}")
    # a flag that lands on a verse a card line already cites is probably not missing
    dup = 0
    for k, t in allf:
        if passes(t):
            have = set()
            for ln in key[k]["lines"]:
                for ref in ln["refs"]:
                    have |= verses_of(ref)
            dup += bool(verses_of(t[0]["ref"]) & have)
    print(f"  of the passing flags, {dup} cite a verse that a line on the card already cites (likely not missing)")
    div = [(k, t) for k, t in allf if key[k]["divine"]]
    print(f"\nFLAGS ON DIVINE PERSONS (the owner's, record by record): {len(div)} on "
          f"{sum(key[k]['divine'] for k in real)} cards")
    for k, t in div:
        print(f"  [{key[k]['name']}] {t[0]['what'][:100]} | {t[0]['ref']} | \"{t[0]['words'][:80]}\" | "
              f"{'passes' if passes(t) else 'fails the filter'}")
    tot = sum(s for _, s, _, _ in secs)
    print(f"\nSPEED: {len(secs)} calls, {tot / 60:.1f} min of model time, mean {tot / max(len(secs), 1):.1f} s/call, "
          f"mean in_tok {sum(t for _, _, t, _ in secs) / max(len(secs), 1):.0f}, "
          f"mean out_tok {sum(t for _, _, _, t in secs) / max(len(secs), 1):.0f}")
    if which == "6a":
        full = JOBS / f"{NAMES['6']}.key.jsonl"
        if full.exists() and secs:
            n6 = sum(1 for _ in open(full, encoding="utf-8"))
            print(f"  job 6: {n6} calls at the sample's mean = {n6 * tot / len(secs) / 3600:.1f} h")
    rnd = random.Random(6)
    good = [(k, t) for k, t in allf if passes(t)]
    print(f"\n15 OF THE {len(good)} PASSING REAL FLAGS:")
    for k, t in rnd.sample(good, min(15, len(good))):
        f = t[0]
        print(f"\n--- {key[k]['name']} ({key[k]['kind']}; {len(key[k]['lines'])} lines on the card)")
        print(f"    MODEL: {f['what']}")
        print(f"    {f['ref']}: \"{f['words']}\"")
        print(f"    VERSE: {t[3]}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "export-sample":
        export_sample()
    elif cmd == "export":
        export_all(sys.argv[2] if len(sys.argv) > 2 else "6")
    else:
        report(sys.argv[2] if len(sys.argv) > 2 else "6a")
