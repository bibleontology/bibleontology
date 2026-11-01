"""THE STRUCTURAL-TYPES PASS: the errors pass's question, re-asked in the form each structural type can answer.
(Mac mini, gemma4:26b; asked 2026-10-30.)

tools/meaning/local_relation_check.py left out 14,605 relations of the graph's structural types because "do the cited
verses say this?" is the wrong question for a relation that links a graph node (a saying, an event, a theme) to a
passage: no verse "says" it. Its sample flagged them 52% against 23% for the concrete types. This pass puts the three
largest of them a question that fits the type, ONE narrow question per type (a different brief each):

  speaks_of   4,509  "does this verse speak of this topic, by name or plainly?"       (saying -> concept, object,
                                                                                         person, being)
  asserted_by 1,617  "is this person (or being) the one speaking, in this verse?"    (saying -> speaker)
  in_theme    2,045  "do these verses take up this theme?"                            (event or concept -> theme)

What stays out, with the reason: part_of 1,435, spoken_in 1,155, instance_of 881, recounts 658, specializes 235,
conditional_on 91, answered_in 21 link two graph nodes (patterns, passages, events) and are checked against the
graph itself, not against a verse; recounts and spoken_in are, besides, derived from the Berean's own section
headings. They stay out of this pass.

What the model sees: the names of the two ends (ontology/entities), the verse text, and for asserted_by the three
verses before the one cited (the speaker is usually named there). Not the relation's `note`, nothing from docs/. The
Mac only FLAGS ("no", "unclear"); Claude judges the flags. The answer key and the planted faults stay on the laptop, in
out/grunt/jobs/<name>.key.jsonl.

Planted faults (about 15% of the sample; each must come back "no" or, for in_theme, "no" or "unclear"):
  plant_verse    the verse swapped for a verse from another book that names neither end
  plant_target   speaks_of / asserted_by: the topic or the speaker swapped for another of its kind that the verses
                 (and, for a speaker, the three before) do not name

    python tools/meaning/local_structural_check.py export-sample    -> out/grunt/jobs/7a-structural-sample.jsonl (~300)
    python tools/meaning/local_structural_check.py export           -> 7b-structural-speaks-of, 7c-structural-asserted-by,
                                                                       7d-structural-in-theme (every eligible row)
    python tools/meaning/local_structural_check.py report [7a|7b|7c|7d]    after `grunt.py pull`
"""
import collections
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
sys.path.insert(0, str(ROOT / "src"))
from derive import BOOK  # noqa: E402
from bibleont.refs import parse_ref  # noqa: E402
import local_relation_check as L  # noqa: E402  (the text, the entities, the ranges and the answer parser are its)

JOBS, DONE = L.JOBS, L.DONE
NAMES = {"7a": "7a-structural-sample", "7b": "7b-structural-speaks-of", "7c": "7c-structural-asserted-by",
         "7d": "7d-structural-in-theme"}
TYPE_OF = {"7b": "speaks_of", "7c": "asserted_by", "7d": "in_theme"}
OPTIONS = {"temperature": 0, "num_ctx": 6144}
DIVINE = L.DIVINE
SEED = 31
N_SAMPLE, PLANT_SHARE = 100, 0.15  # per type: 85 real and 15 planted
BEFORE = 3  # verses before the one cited, shown for asserted_by only
SPEAKER_KINDS = ("person", "being", "group")
TOPIC_KINDS = ("concept", "object", "person", "being", "place", "group")

ANSWER_LINE = ('Answer with ONLY a JSON object: {"answer": "yes" | "implied" | "no" | "unclear", "why": "<one line '
               'quoting the verse>"}')

BRIEF_SPEAKS_OF = """You check a Bible knowledge graph against the text. You get ONE verse (sometimes two or three) \
and ONE topic: a thing, idea, person, group or being. Answer one question: does this verse speak of this topic?

- "yes": the verse names the topic, or speaks of it plainly in other words (a pronoun counts when the verse makes \
clear who or what it is).
- "implied": the verse is plainly about the topic without naming it; a reader would say so.
- "no": the verse does not speak of it. The word may be there in another sense, or the verse may be about \
something else, or only share a word with the topic.
- "unclear": the verses given are not enough to tell.

Judge only from the verses given, never from memory of the Bible. Quote the few words of the verse that decide it.

Worked examples:
- Topic "sun"; Gen 15:17 "When the sun had set and darkness had fallen, behold, a smoking firepot and a flaming torch appeared and passed between the halves of the carcasses." -> yes. why: "When the sun had set".
- Topic "judgment"; Ps 94:2 "Rise up, O Judge of the earth; render a reward to the proud." -> yes. why: "Judge of the earth; render a reward to the proud" speaks of judgment without the word.
- Topic "eyes"; Job 15:12 "Why has your heart carried you away, and why do your eyes flash," -> yes. why: "why do your eyes flash".
- Topic "bread"; Matt 4:4 "But Jesus answered, 'It is written: Man shall not live on bread alone, but on every word that comes from the mouth of God.'" -> yes. why: "Man shall not live on bread alone".
- Topic "Mount Zion"; Ps 2:6 "I have installed My King on Zion, upon My holy mountain." -> yes. why: "on Zion, upon My holy mountain".
- Topic "sacrifice"; Gen 22:6 "Abraham took the wood for the burnt offering and placed it on his son Isaac. He himself carried the fire and the sacrificial knife, and the two of them walked on together." -> implied. why: the wood for the burnt offering, the fire and the knife are the sacrifice being prepared.
- Topic "sword"; Gen 3:24 "...along with a whirling sword of flame to guard the way to the tree of life." -> yes. why: "a whirling sword of flame".
- Topic "water"; Gen 12:2 "I will make you into a great nation, and I will bless you; I will make your name great, so that you will be a blessing." -> no. why: the verse is a promise of a nation and a blessing; no water.
- Topic "king"; Ruth 1:1 "In the days when the judges ruled, there was a famine in the land. And a certain man from Bethlehem in Judah, with his wife and two sons, went to reside in the land of Moab." -> no. why: the verse is about the judges, a famine and a family; no king is named.
- Topic "grain"; Ruth 2:3 "So Ruth departed and went out into the field and gleaned after the harvesters." -> implied. why: "gleaned after the harvesters" is gathering the grain left in a field.

""" + ANSWER_LINE

BRIEF_ASSERTED_BY = """You check a Bible knowledge graph against the text. You get ONE verse that holds a saying \
(a statement, question, command or prayer), the SAYING as the graph labels it, up to three verses that come BEFORE it, \
and ONE person or being. Answer one question: is this person or being the one who says it?

- "yes": the verse or the verses before it show that this one is speaking ("Then Job replied", "the LORD said to \
Job", "I", "my" in a psalm whose heading names the author).
- "implied": the speaker is not named in the verses given but is plainly the one speaking (a prayer in the first \
person by the person who has just prayed, a reply by the one who was just addressed).
- "no": the verses show someone else saying it, or show this one as the person spoken to or spoken about, not the one \
speaking.
- "unclear": the verses given do not say who speaks (a long speech whose opening is further back).

Judge only from the verses given, never from memory of the Bible. Quote the few words that decide it.

Worked examples:
- Saying "God at Job 40:2"; Job 40:1 "And the LORD said to Job:" ; speaker God -> yes. why: "the LORD said to Job".
- Saying "the dream of the sheaves"; Gen 37:7 "We were binding sheaves of grain in the field, and suddenly my sheaf rose and stood upright, while your sheaves gathered around and bowed down to mine." ; before: Gen 37:5 "Then Joseph had a dream, and when he told it to his brothers, they hated him even more." and Gen 37:6 "He said to them, 'Listen to this dream I had:" ; speaker Joseph -> yes. why: "Joseph had a dream, and when he told it to his brothers".
- Same saying and verses; speaker Reuben -> no. why: Joseph tells the dream; Reuben is not in these verses.
- Saying "Greet those who love us in the faith"; Titus 3:15 "All who are with me send you greetings. Greet those who love us in the faith. Grace be with all of you." ; speaker Paul -> implied. why: the letter's writer sends the greeting; "me" and "us" are the writer's.
- Saying "I will make you into a great nation"; Gen 12:2 "I will make you into a great nation, and I will bless you..." ; before: Gen 12:1 "Then the LORD said to Abram, 'Leave your country...'" ; speaker Abram -> no. why: the LORD is speaking to Abram.
- Saying "Out of the depths"; Ps 130:1 "A song of ascents. Out of the depths I cry to You, O LORD!" ; no verse before names a speaker ; speaker David -> unclear. why: the verse and the heading give no speaker.

""" + ANSWER_LINE

BRIEF_IN_THEME = """You check a Bible knowledge graph against the text. You get an EVENT or a CONCEPT, the verses \
the graph cites for it, and ONE major theme of the Bible (a broad subject, like "Judgment" or "Mercy & \
Restoration"). Answer one question: do these verses take up this theme?

- "yes": the verses are plainly about the theme, or one of the verses states it.
- "implied": the theme is in the passage without being its main point, and a reader would agree it belongs there.
- "no": the verses are about something else; the theme is not in them.
- "unclear": the verses given are too few or too short to tell.

A theme is broad, so judge generously for "implied", but do not invent: the verses must give you the reason. Judge \
only from the verses given, never from memory of the Bible. Quote the few words that decide it.

Worked examples:
- Event "The flood"; Gen 7:23 "And every living thing on the face of the earth was destroyed-man and livestock, crawling creatures and birds of the air; they were blotted out from the earth, and only Noah and those with him in the ark remained."; theme "Judgment" -> yes. why: "every living thing on the face of the earth was destroyed".
- Event "Sodom destroyed"; Gen 19:24-25 "Then the LORD rained down sulfur and fire on Sodom and Gomorrah-from the LORD out of the heavens. Thus He destroyed these cities and the entire plain..."; theme "Judgment" -> yes. why: "the LORD rained down sulfur and fire".
- Event "The prodigal son returns"; Luke 15:20 "...his father saw him and was filled with compassion. He ran to his son, embraced him, and kissed him."; theme "Mercy & Restoration" -> yes. why: "was filled with compassion".
- Event "Ruth gleans"; Ruth 2:3 "So Ruth departed and went out into the field and gleaned after the harvesters. And she happened to come to the part of the field belonging to Boaz..."; theme "Judgment" -> no. why: gleaning in Boaz's field; no judgment is in the verse.
- Event "Pentecost"; Acts 2:4 "And they were all filled with the Holy Spirit and began to speak in other tongues as the Spirit enabled them."; theme "Spirit" -> yes. why: "filled with the Holy Spirit".
- Event "Solomon builds the temple"; 1 Kgs 6:1 "In the four hundred and eightieth year after the Israelites had come out of the land of Egypt, in the fourth year of Solomon's reign over Israel ... he began to build the house of the LORD."; theme "Temple / Presence" -> implied. why: "he began to build the house of the LORD".
- Concept "How long, O LORD?"; Ps 13:1 "For the choirmaster. A Psalm of David. How long, O LORD? Will You forget me forever? How long will You hide Your face from me?"; theme "Judgment" -> unclear. why: the lament asks how long; it names no judgment.

""" + ANSWER_LINE

BRIEFS = {"speaks_of": BRIEF_SPEAKS_OF, "asserted_by": BRIEF_ASSERTED_BY, "in_theme": BRIEF_IN_THEME}
ELIGIBLE_ENDS = {"speaks_of": TOPIC_KINDS + ("object",), "asserted_by": SPEAKER_KINDS}


# ------------------------------------------------------------------ the items
def theme_name(name):
    return re.sub(r"\s*\(major theme\)\s*$", "", name or "")


def verses_before(by, ref, n=BEFORE):
    """the n verses just before the first verse a ref cites, in the same book, as [{ref, text}]"""
    try:
        p = parse_ref(ref)
    except Exception:
        return []
    seq = by.get(BOOK.get(p.book, p.book), [])
    for i, (c, v, b, t) in enumerate(seq):
        if (c, v) == (p.start_chapter, p.start_verse):
            return [{"ref": f"{lb} {cc}:{vv}", "text": tt} for cc, vv, lb, tt in seq[max(0, i - n):i]]
    return []


def build(ents, by, row, *, dst=None, verses=None, hidden=0, before=None):
    r = row["r"]
    t = r["type"]
    if verses is None:
        verses, hidden, _ = L.shown(by, r["refs"])
        before = verses_before(by, r["refs"][0]) if t == "asserted_by" else []
    sn = L.ename(ents, r["src"])
    dn = L.ename(ents, dst or r["dst"])
    if t == "in_theme":
        dn = theme_name(dn)
    text = {"speaks_of": f"{sn} — speaks of — {dn}", "asserted_by": f"{sn} — said by — {dn}",
            "in_theme": f"{sn} — belongs to the theme — {dn}"}[t]
    return {"file": row["file"], "line": row["line"], "src": r["src"], "dst": dst or r["dst"], "type": t,
            "text": text, "subject": sn, "object": dn, "refs": r["refs"], "verses": verses, "before": before or [],
            "hidden": hidden, "divine": bool({r["src"], dst or r["dst"]} & DIVINE), "kind": "real", "expect": None}


def messages(it):
    t = it["type"]
    if t == "speaks_of":
        msg = {"topic": it["object"], "verses": it["verses"]}
    elif t == "asserted_by":
        msg = {"saying": it["subject"], "person_or_being": it["object"], "verse": it["verses"],
               "verses_before": it["before"]}
    else:
        msg = {"event_or_concept": it["subject"], "theme": it["object"], "verses": it["verses"]}
    if it["hidden"]:
        msg["not_shown"] = f"{it['hidden']} more verses of the cited passage are not shown here"
    return [{"role": "system", "content": BRIEFS[t]}, {"role": "user", "content": json.dumps(msg, ensure_ascii=False)}]


def write_job(name, its):
    JOBS.mkdir(parents=True, exist_ok=True)
    with open(JOBS / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "local_structural_check"}}) + "\n")
        for it in its:
            f.write(json.dumps({"key": it["key"], "messages": messages(it)}, ensure_ascii=False) + "\n")
    with open(JOBS / f"{name}.key.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in its:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def rows_of(ents, by, t):
    rows, _ = L.eligible(ents, by)
    rows = [r for r in rows if r["r"]["type"] == t]
    out = []
    for r in rows:
        vs, _, found = L.shown(by, r["r"]["refs"])
        if found and vs:
            out.append(r)
    L.check_ranges(by, rows)
    return out


# ------------------------------------------------------------------ the sample
def far_verse(by, rnd, avoid, books, mybook):
    """two consecutive verses from another book that name none of `avoid`"""
    while True:
        b = rnd.choice([x for x in books if x != mybook])
        i = rnd.randrange(len(by[b]) - 1)
        vs = [{"ref": f"{lb} {c}:{v}", "text": t} for c, v, lb, t in by[b][i:i + 2]]
        text = " ".join(v["text"] for v in vs)
        if len(text) > 60 and not any(L.named(text, a) for a in avoid):
            return vs


def sample_items(ents, by):
    rnd = random.Random(SEED)
    its, notes = [], []
    books = sorted(by)
    by_kind = collections.defaultdict(list)
    for e in ents.values():
        if e.get("name") and e["name"][:1].isupper() and e.get("type") in set(TOPIC_KINDS) | set(SPEAKER_KINDS):
            by_kind[e["type"]].append(e["id"])
    for t in ("speaks_of", "asserted_by", "in_theme"):
        rows = rows_of(ents, by, t)
        n_plant = round(N_SAMPLE * PLANT_SHARE)
        picked = rnd.sample(rows, N_SAMPLE)  # the first N_SAMPLE - n_plant are real; the last n_plant are the bases
        real, bases = picked[:N_SAMPLE - n_plant], picked[N_SAMPLE - n_plant:]
        notes.append(f"{t}: {len(rows)} eligible rows; {len(real)} real, {n_plant} planted")
        for row in real:
            it = build(ents, by, row)
            it["stratum"] = "real"
            its.append(it)
        for k, row in enumerate(bases):
            base = build(ents, by, row)
            if t == "in_theme" or k % 2 == 0:  # (a) the verse swapped for one from another book
                mybook = BOOK.get(parse_ref(base["refs"][0]).book, parse_ref(base["refs"][0]).book)
                vs = far_verse(by, rnd, [base["subject"], base["object"]], books, mybook)
                p = build(ents, by, row, verses=vs, hidden=0, before=verses_before(by, vs[0]["ref"]) if t == "asserted_by" else [])
                p.update(kind="plant_verse", expect="no", refs=[vs[0]["ref"]])
            else:  # (b) the topic or the speaker swapped for another of its kind that the text does not name
                kinds = TOPIC_KINDS if t == "speaks_of" else SPEAKER_KINDS
                shown_text = " ".join(v["text"] for v in base["verses"] + base["before"])
                while True:
                    x = rnd.choice(by_kind[rnd.choice(kinds)])
                    if x not in (base["src"], base["dst"]) and not L.named(shown_text, L.ename(ents, x)):
                        break
                p = build(ents, by, row, dst=x, verses=base["verses"], hidden=base["hidden"], before=base["before"])
                p.update(kind="plant_target", expect="no")
            p["stratum"] = "plant"
            its.append(p)
    rnd.shuffle(its)
    for i, it in enumerate(its):
        it["key"] = f"s{i:04d}"
    return its, notes


def export_sample():
    ents, by = L.entities(), L.bible()
    its, notes = sample_items(ents, by)
    write_job(NAMES["7a"], its)
    print("\n".join(notes))
    print(f"{len(its)} calls {dict(collections.Counter((i['type'], i['kind']) for i in its))} "
          f"-> {JOBS / (NAMES['7a'] + '.jsonl')}")


def export_all():
    ents, by = L.entities(), L.bible()
    for which, t in TYPE_OF.items():
        rows = rows_of(ents, by, t)
        its = []
        for row in rows:
            it = build(ents, by, row)
            it["stratum"] = "all"
            it["key"] = f"{which}{len(its):05d}"
            its.append(it)
        write_job(NAMES[which], its)
        nv = sum(len(i["verses"]) + len(i["before"]) for i in its)
        print(f"{NAMES[which]}: {len(its)} calls, {nv / len(its):.2f} verses per call -> {JOBS / (NAMES[which] + '.jsonl')}")


# ------------------------------------------------------------------ the report
def report(which="7a"):
    name = NAMES[which]
    key = {json.loads(l)["key"]: json.loads(l) for l in open(JOBS / f"{name}.key.jsonl", encoding="utf-8")}
    rows = [json.loads(l) for l in open(DONE / f"{name}.jsonl", encoding="utf-8")]
    ans, why, secs, errs = {}, {}, [], 0
    for d in rows:
        if "error" in d:
            errs += 1
            continue
        a, w = L.parse_answer(d.get("content"))
        if a:
            ans[d["key"]], why[d["key"]] = a, w
        secs.append((d["key"], d.get("secs") or 0, d.get("in_tok") or 0))
    print(f"{len(rows)} answer lines, {len(ans)} parsed of {len(key)} items; {errs} errors, "
          f"{len(rows) - errs - len(ans)} unparseable")
    types = sorted({i["type"] for i in key.values()})
    for t in types:
        ks = [k for k in ans if key[k]["type"] == t]
        print(f"\n== {t}")
        for kind in ("plant_verse", "plant_target"):
            pk = [k for k in ks if key[k]["kind"] == kind]
            if pk:
                print(f"  {kind}: caught \"no\" {sum(ans[k] == 'no' for k in pk)} of {len(pk)}; flagged (no or unclear) "
                      f"{sum(ans[k] in ('no', 'unclear') for k in pk)}; {dict(collections.Counter(ans[k] for k in pk))}")
        real = [k for k in ks if key[k]["kind"] == "real"]
        c = collections.Counter(ans[k] for k in real)
        print(f"  REAL ({len(real)}): {dict(c)}; flag rate (no + unclear) {(c['no'] + c['unclear']) / max(len(real), 1):.1%}, "
              f"no alone {c['no'] / max(len(real), 1):.1%}")
        by_obj = collections.defaultdict(collections.Counter)
        for k in real:
            by_obj[key[k]["file"].split("-farm")[0].split("-2026")[0]][ans[k]] += 1
        print("  by source file (n, no, unclear):")
        for f, cs in sorted(by_obj.items(), key=lambda x: -sum(x[1].values()))[:12]:
            print(f"    {f:26s} {sum(cs.values()):5d} no={cs['no']:4d} unclear={cs['unclear']:4d}")
        div = [k for k in real if key[k]["divine"] and ans[k] in ("no", "unclear")]
        print(f"  FLAGS ON DIVINE PERSONS (the owner's, record by record): {len(div)} of "
              f"{sum(key[k]['divine'] for k in real)} real rows touching one")
        for k in div[:40]:
            print(f"    [{ans[k]}] {key[k]['text']} | {', '.join(key[k]['refs'])} | {why[k][:130]}")
    tot = sum(s for _, s, _ in secs)
    nv = sum(len(key[k]["verses"]) + len(key[k]["before"]) for k, *_ in secs)
    print(f"\nSPEED: {len(secs)} calls, {tot / 60:.1f} min of model time, {len(secs) / max(tot / 60, 1e-9):.1f} calls/min, "
          f"mean {tot / max(len(secs), 1):.1f} s/call, mean in_tok {sum(t for _, _, t in secs) / max(len(secs), 1):.0f}")
    if which == "7a":
        for w, t in TYPE_OF.items():
            full = JOBS / f"{NAMES[w]}.key.jsonl"
            ks = [k for k, *_ in secs if key[k]["type"] == t]
            if full.exists() and ks:
                n = sum(1 for _ in open(full, encoding="utf-8"))
                mean = sum(s for k, s, _ in secs if key[k]["type"] == t) / len(ks)
                print(f"  {NAMES[w]}: {n} calls at the sample's {mean:.1f} s/call = {n * mean / 3600:.1f} h")
    rnd = random.Random(5)
    for t in types:
        no = [k for k in ans if key[k]["type"] == t and key[k]["kind"] == "real" and ans[k] == "no"]
        print(f"\n10 OF THE {len(no)} REAL \"no\" FLAGS, {t}:")
        for k in rnd.sample(no, min(10, len(no))):
            i = key[k]
            print(f"\n--- {i['text']}   [{i['file']}:{i['line']}]")
            for v in i["before"]:
                print(f"    (before) {v['ref']}: {v['text']}")
            for v in i["verses"]:
                print(f"    {v['ref']}: {v['text']}")
            print(f"    MODEL: no -- {why[k]}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "export-sample":
        export_sample()
    elif cmd == "export":
        export_all()
    else:
        report(sys.argv[2] if len(sys.argv) > 2 else "7a")
