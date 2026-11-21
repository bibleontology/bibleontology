"""THE ERRORS PASS: does the cited verse say this? (Mac mini, gemma4:26b; asked 2026-10-30.)

One narrow question per relation: the relation in plain English ("Gentiles -- killed -- Jesus") and the BSB text of the
verses it cites. The model answers yes / implied / no / unclear, with a line quoting the words that decide it. The Mac
only FLAGS candidates ("no", "unclear"); nothing it answers reaches a card or the data. Claude judges the flags later.

What the model sees: the names of the two ends (ontology/entities), the relation type with its underscores as spaces,
and verse text. It does not see the relation's `note` (that is the graph's own claim) and nothing from docs/.
Rows with `held` or `described` are skipped, with one exception: the known-wrong rows the sample uses as positives.

The answer key and the planted faults stay on the laptop, in out/grunt/jobs/<name>.key.jsonl, never in the job file.
Planted faults (about 15% of the sample, each must come back "no"):
  plant_verse   the verse swapped for a verse from another book
  plant_target  the target swapped for another entity of the same kind that the verses do not name
  plant_type    the relation type swapped for an unrelated one

JOB 5 IS CONCRETE ROWS ONLY (lead's ruling 2026-10-30, after the first sample). "Do the verses say this?" is the wrong
question for a relation that links a graph node (a speech, a message, a pattern, a passage, a theme) to something: no
verse "says" it. The sample flagged those 52% against 23% for the concrete types. Excluded, with the count of each
(21,763 eligible on 2026-10-30; 7,158 stay):
  by relation type: speaks_of 4509, in_theme 2045, asserted_by 1617, part_of 1435, spoken_in 1155, instance_of 881,
                    recounts 658, specializes 235, conditional_on 91, answered_in 21
  by node: any other type whose source or target is a saying/speech (`text`), `passage` or `pattern` record (messages,
                    speech acts and message groups are patterns): told 1181, draws_on 508, quoted 60, grounds 50,
                    occasion_of 35, likened_to 31, heard 24, explained 18, aspect_of 11, assessed_as 10,
                    contrary_to 8, described_as 8, answered 6, signifies 5, ascribed_to 3
Divine-person rows stay in; the report lists their flags apart. `export-sample` still draws from every type (that is
the run of 2026-10-30; add --event-rows to reproduce it exactly: the 20 event cast rows are no longer a default
positive group, since those rows are correct and rest on pronouns the Mac cannot resolve).

    python tools/meaning/local_relation_check.py export-sample [--event-rows] -> out/grunt/jobs/5a-relation-check-sample.jsonl
    python tools/meaning/local_relation_check.py export          -> out/grunt/jobs/5-relation-check.jsonl (concrete rows)
    python tools/meaning/local_relation_check.py report [5a|5]    after `grunt.py pull` (default 5a)
"""
import collections
import csv
import glob
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
from derive import BOOK  # noqa: E402
from bibleont.refs import parse_ref  # noqa: E402

JOBS, DONE = ROOT / "out" / "grunt" / "jobs", ROOT / "out" / "grunt" / "done"
NAMES = {"5a": "5a-relation-check-sample", "5": "5-relation-check",
         # the same pass over today's graph (2026-11-12, Doug: "make sure that the Mac is working hard identifying
         # issues"): every concrete relation again, the thousands added since 10-30 among them
         "28": "28-relation-check",
         # and again on 2026-11-16, after the speaker pass and the day's fixes (run overnight, read 2026-11-17)
         "37": "37-relation-recheck",
         # 2026-11-19, night (Doug: "make sure we are making optimal use of the Mac"): exported whole, then cut to the
         # rows job 37 did not ask, less acted_in (event cast rows rest on pronouns the Mac cannot resolve; see above)
         "38": "38-relation-recheck-new",
         # model bench, 2026-10-31: job 5a's items again, the model named in the _job header (docs/review/mac-models-2026-10-31.md)
         "8a": "8a-bench-qwen3.8-27b", "8b": "8b-bench-gemma4-31b-qat"}
OPTIONS = {"temperature": 0, "num_ctx": 6144}
DIVINE = {"god", "holy_ghost", "spirit_of_the_lord_in_the_hebrew_bible", "the_father", "jesus", "spirit", "spirit_of_god"}
RANGE_CAP = 6   # verses shown of one cited range
TOTAL_CAP = 12  # verses shown of one relation
SEED = 30
N_REAL, N_PLANT_EACH = 400, 20
ANSWERS = ("yes", "implied", "no", "unclear")
PLANT_TYPES = ["killed", "buried_at", "born_at", "healed", "baptized", "imprisoned", "destroyed", "wrote_to",
               "spouse_of", "built", "anointed", "died_at", "betrayed", "sibling_of"]
STRUCTURAL_TYPES = {"speaks_of", "in_theme", "asserted_by", "part_of", "spoken_in", "instance_of", "recounts",
                    "specializes", "conditional_on", "answered_in"}
NODE_TYPES = {"text", "passage", "pattern"}  # entity types that are sayings, passages, messages, speech acts, patterns
KINDS = ("person", "place", "group", "being")
EVENT_ROWS = ROOT / "docs" / "review" / "card-panel-appeal" / "walkthrough-2026-10-30" / "event-rows-left-off.tsv"

BRIEF = """You check a Bible knowledge graph against the text. You get ONE relation, written SUBJECT -- relation -- \
OBJECT, and the verses the graph cites for it. Answer one question: do these verses, as given, say this?

- "yes": a verse states it. A pronoun ("he", "Him") counts as naming its person when the verses given make clear who it is.
- "implied": the verses imply it without stating it; a reader would draw it from them.
- "no": the verses do not say it, or say something else: the wrong person, the wrong place, a prediction or someone's \
claim presented as what happened, a different event, a different relation between the same two.
- "unclear": the verses given are not enough to tell (they leave out who is meant, or the passage is cut off).

Judge only from the verses given, never from memory of the Bible. The subject and object may be a person, place, group, \
event, saying or idea; judge each as the verses use it. Quote the few words of the verse that decide it.

Worked examples:
- Cain -- killed -- Abel; Gen 4:8 "...Cain rose up against his brother Abel and killed him." -> yes. why: "Cain rose \
up against his brother Abel and killed him".
- Gentiles -- killed -- Jesus; Matt 20:19 "and will deliver Him over to the Gentiles to be mocked and flogged and \
crucified. And on the third day He will be raised to life." -> no. why: "will deliver Him over" is a prediction, and it \
says they will crucify him, not that it happened; the verse is Jesus foretelling.
- Jerusalem -- contains -- Golgotha; John 19:20 "...the place where Jesus was crucified was near the city..." -> no. \
why: "near the city" puts the place beside Jerusalem, not inside it.
- Saul -- killed -- Goliath; 1 Sam 17:50 "Thus David prevailed over the Philistine with a sling and a stone; ... he \
struck down the Philistine and killed him." -> no. why: the one who killed him is David; Saul is not named.
- Obed -- grandfather of -- David; Ruth 4:17 "... they named him Obed. He became the father of Jesse, the father of \
David." -> implied. why: "father of Jesse, the father of David" makes Obed David's grandfather without saying so.
- Mary -- mother of -- Jesus; Luke 2:6-7 "While they were there, the time came for her Child to be born. And she gave \
birth to her firstborn, a Son. ..." -> unclear. why: the verses say "she" and "her Child" and name no one.

Answer with ONLY a JSON object: {"answer": "yes" | "implied" | "no" | "unclear", "why": "<one line quoting the \
verse>"}"""


# ------------------------------------------------------------------ the text and the graph
def bible():
    """book -> [(chapter, verse, label book, text)] in order, and the same keyed by short book."""
    by = collections.defaultdict(list)
    for ln in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        if "b" in d:
            by[BOOK.get(d["b"], d["b"])].append((d["c"], d["v"], d["b"], d["t"]))
    return by


def entities():
    ents = {}
    for f in sorted(glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl"))):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                e = json.loads(ln)
                ents.setdefault(e["id"], e)
    return ents


def ename(ents, i):
    return (ents.get(i) or {}).get("name") or i.replace("_", " ")


def shown(by, refs):
    """The verses of a relation's refs the model is shown: at most RANGE_CAP of a range, TOTAL_CAP overall.
    Returns ([{ref, text}], number of verses cited that are not shown, ok)."""
    out, seen, hidden, found = [], set(), 0, False
    for ref in refs:
        try:
            p = parse_ref(ref)
        except Exception:
            continue
        vs = [(c, v, b, t) for c, v, b, t in by.get(BOOK.get(p.book, p.book), ())
              if (p.start_chapter, p.start_verse) <= (c, v) <= (p.end_chapter, p.end_verse)]
        found = found or bool(vs)
        for n, (c, v, b, t) in enumerate(vs):
            k = (b, c, v)
            if k in seen:
                continue
            if n >= RANGE_CAP or len(out) >= TOTAL_CAP:
                hidden += 1
                continue
            seen.add(k)
            out.append({"ref": f"{b} {c}:{v}", "text": t})
    return out, hidden, found


def eligible(ents, by):
    """every relation with refs, minus held and described: a list of dicts"""
    rows, skipped = [], collections.Counter()
    for f in sorted(glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl"))):
        for n, ln in enumerate(open(f, encoding="utf-8"), 1):
            if not ln.strip():
                continue
            r = json.loads(ln)
            if not r.get("refs"):
                skipped["no refs"] += 1
            elif r.get("held"):
                skipped["held"] += 1
            elif r.get("described"):
                skipped["described"] += 1
            else:
                rows.append({"file": Path(f).name, "line": n, "r": r})
    return rows, skipped


def check_ranges(by, rows):
    """a cited range must yield more than one verse (never just its first), and never more than RANGE_CAP"""
    for row in rows:
        for ref in row["r"]["refs"]:
            try:
                p = parse_ref(ref)
            except Exception:
                continue
            if (p.start_chapter, p.start_verse) == (p.end_chapter, p.end_verse):
                continue
            vs, hidden, _ = shown(by, [ref])
            if len(vs) + hidden < 2 or len(vs) > RANGE_CAP:
                raise SystemExit(f"range {ref!r} ({row['file']}:{row['line']}) shows {len(vs)} verses, "
                                 f"{hidden} hidden: the expansion is wrong")


def concrete(ents, r):
    """False for a relation whose question 'do the verses say this?' is malformed (see the docstring)"""
    return r["type"] not in STRUCTURAL_TYPES and not any(
        (ents.get(r[x]) or {}).get("type") in NODE_TYPES for x in ("src", "dst"))


def phrase(r):
    """the relation's verb in plain words; a verse statement carries its own label"""
    if r.get("label"):
        return ("NOT " if r.get("negated") else "") + r["label"]
    return r["type"].replace("_", " ")


def build(ents, by, row, *, rtype=None, dst=None, verses=None, hidden=0):
    """one item (key file side) for a relation, optionally with a planted corruption applied"""
    r = row["r"]
    ph = phrase(r) if rtype is None else rtype.replace("_", " ")
    sn, dn = ename(ents, r["src"]), ename(ents, dst or r["dst"])
    if verses is None:
        verses, hidden, _ = shown(by, r["refs"])
    return {"file": row["file"], "line": row["line"], "src": r["src"], "dst": dst or r["dst"],
            "type": rtype or r["type"], "phrase": ph, "text": f"{sn} — {ph} — {dn}",
            "subject": sn, "object": dn, "refs": r["refs"], "verses": verses, "hidden": hidden,
            "divine": bool({r["src"], dst or r["dst"]} & DIVINE), "kind": "real", "expect": None}


def messages(it):
    msg = {"relation": it["text"], "subject": it["subject"], "relation_type": it["phrase"], "object": it["object"],
           "verses": it["verses"]}
    if it["hidden"]:
        msg["not_shown"] = f"{it['hidden']} more verses of the cited passage are not shown here"
    return [{"role": "system", "content": BRIEF}, {"role": "user", "content": json.dumps(msg, ensure_ascii=False)}]


def write_job(name, its):
    JOBS.mkdir(parents=True, exist_ok=True)
    with open(JOBS / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "local_relation_check"}}) + "\n")
        for it in its:
            f.write(json.dumps({"key": it["key"], "messages": messages(it)}, ensure_ascii=False) + "\n")
    with open(JOBS / f"{name}.key.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in its:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ the sample
def named(text, name):
    n = re.sub(r"^(the|a|an)\s+", "", (name or "").lower().strip())
    return len(n) > 2 and n in text.lower()


def event_row_positives(ents, by, rows, rnd):  # off by default: see the docstring
    """20 relations behind event cast rows whose subject the cited verses do not name (the owner's list of 610)"""
    if not EVENT_ROWS.exists():
        return [], "event-rows-left-off.tsv is not there: that group is skipped"
    byname = collections.defaultdict(set)
    for e in ents.values():
        byname[(e.get("name") or "").lower()].add(e["id"])
    idx = collections.defaultdict(list)
    for row in rows:
        idx[(row["r"]["src"], row["r"]["dst"])].append(row)
    cands = []
    for t in csv.DictReader(open(EVENT_ROWS, encoding="utf-8"), delimiter="\t"):
        S, O = byname.get(t["subjects"].lower(), set()), byname.get(t["object"].lower(), set())
        cited = set()
        for ref in t["verses cited inside the telling"].split(";"):
            try:
                p = parse_ref(ref.strip())
                cited.add((BOOK.get(p.book, p.book), p.start_chapter, p.start_verse))
            except Exception:
                pass
        for s in S:
            for o in O:
                for row in idx.get((s, o), ()):
                    vs, _, _ = shown(by, row["r"]["refs"])
                    if not vs or not any((BOOK.get(parse_ref(v["ref"]).book, parse_ref(v["ref"]).book),
                                          parse_ref(v["ref"]).start_chapter, parse_ref(v["ref"]).start_verse) in cited
                                         for v in vs):
                        continue
                    text = " ".join(v["text"] for v in vs)
                    names = [ents[s].get("name")] + list(ents[s].get("aka") or [])
                    if any(named(text, n) for n in names):
                        continue
                    cands.append((t["actor named one verse earlier"].strip() != "", t["subjects"], row))
    # rows whose actor is not named one verse earlier first: those are the clear cases
    seen, pool = set(), []
    for earlier, subj, row in cands:
        k = (row["file"], row["line"])
        if k not in seen:
            seen.add(k)
            pool.append((earlier, row))
    clear = [r for e, r in pool if not e]
    rnd.shuffle(clear)
    rest = [r for e, r in pool if e]
    rnd.shuffle(rest)
    return (clear + rest)[:20], f"{len(clear)} candidates with the actor not named one verse earlier, {len(rest)} with"


def sample_items(ents, by, event_rows=False):
    rows, skipped = eligible(ents, by)
    check_ranges(by, rows)
    rnd = random.Random(SEED)
    notes = [f"eligible {len(rows)}; skipped {dict(skipped)}"]
    taken = set()
    # the known-wrong positives
    pos = []
    gentiles = held_beside = None
    for f in sorted(glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl"))):
        for n, ln in enumerate(open(f, encoding="utf-8"), 1):
            if not ln.strip():
                continue
            r = json.loads(ln)
            row = {"file": Path(f).name, "line": n, "r": r}
            if Path(f).name == "groups-nt.jsonl" and r["src"] == "gentiles" and r["dst"] == "jesus" \
                    and r["type"] == "killed":
                pos.append(("known_no:gentiles", row))
            if r.get("held_beside"):
                pos.append(("known_no:held_beside", row))
    if event_rows:
        evrows, evnote = event_row_positives(ents, by, rows, rnd)
        notes.append(evnote)
    else:
        evrows = []
    pos += [("known_no:event_row", row) for row in evrows]
    for _, row in pos:
        taken.add((row["file"], row["line"]))
    pool = [r for r in rows if (r["file"], r["line"]) not in taken and shown(by, r["r"]["refs"])[2]]
    # 400 real: 200 drawn evenly from all rows, 200 with the relation type drawn first, then the file, then the row
    real = [("prop", r) for r in rnd.sample(pool, N_REAL // 2)]
    chosen = {(r["file"], r["line"]) for _, r in real}
    bytf = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in pool:
        bytf[r["r"]["type"]][r["file"]].append(r)
    types = sorted(bytf)
    while len(real) < N_REAL:
        t = rnd.choice(types)
        f = rnd.choice(sorted(bytf[t]))
        r = rnd.choice(bytf[t][f])
        if (r["file"], r["line"]) not in chosen:
            chosen.add((r["file"], r["line"]))
            real.append(("type", r))
    its = []
    for stratum, row in real:
        it = build(ents, by, row)
        it["stratum"] = stratum
        its.append(it)
    # planted faults, each built on a distinct real relation between persons, places, groups or beings
    ok = [it for it in its if all((ents.get(x) or {}).get("type") in KINDS for x in (it["src"], it["dst"]))]
    rnd.shuffle(ok)
    bases = [ok[i * N_PLANT_EACH:(i + 1) * N_PLANT_EACH] for i in range(3)]
    books = sorted(by)
    by_kind = collections.defaultdict(list)
    for e in ents.values():
        if e.get("type") in KINDS and e.get("name"):
            by_kind[e["type"]].append(e["id"])
    rowof = {(r["file"], r["line"]): r for _, r in real}
    for it in bases[0]:  # (a) the verse swapped for one from a different book
        mybook = BOOK.get(parse_ref(it["refs"][0]).book, parse_ref(it["refs"][0]).book)
        while True:
            b = rnd.choice([x for x in books if x != mybook])
            i = rnd.randrange(len(by[b]) - 1)
            vs = [{"ref": f"{lb} {c}:{v}", "text": t} for c, v, lb, t in by[b][i:i + 2]]
            text = " ".join(v["text"] for v in vs)
            if len(text) > 60 and not named(text, it["subject"]) and not named(text, it["object"]):
                break
        p = build(ents, by, rowof[(it["file"], it["line"])], verses=vs, hidden=0)
        p.update(kind="plant_verse", expect="no", refs=[vs[0]["ref"]], stratum="plant")
        its.append(p)
    for it in bases[1]:  # (b) the target swapped for another of the same kind that the verses do not name
        text = " ".join(v["text"] for v in it["verses"])
        k = ents[it["dst"]]["type"]
        while True:
            x = rnd.choice(by_kind[k])
            if x not in (it["src"], it["dst"]) and not named(text, ename(ents, x)):
                break
        p = build(ents, by, rowof[(it["file"], it["line"])], dst=x)
        p.update(kind="plant_target", expect="no", stratum="plant")
        its.append(p)
    for it in bases[2]:  # (c) the relation type swapped for an unrelated one
        t = rnd.choice([x for x in PLANT_TYPES if x != it["type"]])
        p = build(ents, by, rowof[(it["file"], it["line"])], rtype=t)
        p.update(kind="plant_type", expect="no", stratum="plant")
        its.append(p)
    for kind, row in pos:
        it = build(ents, by, row)
        it.update(kind=kind, expect="no", stratum="known_no")
        its.append(it)
    rnd.shuffle(its)
    for i, it in enumerate(its):
        it["key"] = f"c{i:04d}"
    return its, notes


def export_sample(event_rows=False):
    ents, by = entities(), bible()
    its, notes = sample_items(ents, by, event_rows)
    write_job(NAMES["5a"], its)
    print("\n".join(notes))
    print(f"{len(its)} items {dict(collections.Counter(i['kind'].split(':')[0] for i in its))} "
          f"{dict(collections.Counter(i['kind'] for i in its if i['kind'].startswith('known')))} "
          f"-> {JOBS / (NAMES['5a'] + '.jsonl')}")


def export_all(which="5"):
    ents, by = entities(), bible()
    rows, skipped = eligible(ents, by)
    check_ranges(by, rows)
    its, nov, out = [], 0, collections.Counter()
    for row in rows:
        if not concrete(ents, row["r"]):
            out[row["r"]["type"]] += 1
            continue
        it = build(ents, by, row)
        if not it["verses"]:
            nov += 1
            continue
        it["stratum"] = "all"
        it["key"] = f"r{len(its):05d}"
        its.append(it)
    write_job(NAMES[which], its)
    print(f"{len(its)} calls of {len(rows)} eligible (no verse text found for {nov}); skipped {dict(skipped)}; "
          f"left out as structural {sum(out.values())}: {dict(out.most_common())} -> {JOBS / (NAMES[which] + '.jsonl')}")


# ------------------------------------------------------------------ the report
def parse_answer(content):
    s = (content or "").strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.M).strip()
    try:
        d = json.loads(s)
        if d.get("answer") in ANSWERS:
            return d["answer"], str(d.get("why", ""))
    except Exception:
        pass
    m = re.search(r'"answer"\s*:\s*"(yes|implied|no|unclear)"', s)
    if m:
        w = re.search(r'"why"\s*:\s*"(.*)', s, re.S)
        return m[1], (w[1] if w else "")
    return None, ""


def report(which="5a"):
    name = NAMES[which]
    key = {}
    for ln in open(JOBS / f"{name}.key.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        key[d["key"]] = d
    rows = [json.loads(l) for l in open(DONE / f"{name}.jsonl", encoding="utf-8")]
    ans, why, secs, errs = {}, {}, [], 0
    for d in rows:
        if "error" in d:
            errs += 1
            continue
        a, w = parse_answer(d.get("content"))
        if a:
            ans[d["key"]], why[d["key"]] = a, w
        secs.append((d["key"], d.get("secs") or 0, d.get("in_tok") or 0, d.get("out_tok") or 0))
    print(f"{len(rows)} answer lines, {len(ans)} parsed of {len(key)} items; {errs} errors, "
          f"{len(rows) - errs - len(ans)} unparseable")

    def of(pred):
        return [k for k in ans if pred(key[k])]

    print("\nPLANTED FAULTS (must be \"no\"):")
    for kind in ("plant_verse", "plant_target", "plant_type"):
        ks = of(lambda i: i["kind"] == kind)
        print(f"  {kind}: caught {sum(ans[k] == 'no' for k in ks)} of {len(ks)}; "
              f"flagged (no or unclear) {sum(ans[k] in ('no', 'unclear') for k in ks)}; "
              f"{dict(collections.Counter(ans[k] for k in ks))}")
    print("\nKNOWN WRONG ROWS (must be \"no\"):")
    for kind in sorted({i["kind"] for i in key.values() if i["kind"].startswith("known")}):
        ks = of(lambda i: i["kind"] == kind)
        print(f"  {kind}: caught {sum(ans[k] == 'no' for k in ks)} of {len(ks)}; "
              f"flagged {sum(ans[k] in ('no', 'unclear') for k in ks)}; "
              f"{dict(collections.Counter(ans[k] for k in ks))}")
    real = of(lambda i: i["kind"] == "real")
    c = collections.Counter(ans[k] for k in real)
    print(f"\nREAL ({len(real)}): {dict(c)}; flag rate (no + unclear) "
          f"{(c['no'] + c['unclear']) / max(len(real), 1):.1%}, no alone {c['no'] / max(len(real), 1):.1%}")
    for s in ("prop", "type"):
        ks = [k for k in real if key[k].get("stratum") == s]
        cs = collections.Counter(ans[k] for k in ks)
        print(f"  stratum {s} ({len(ks)}): {dict(cs)}; flag rate {(cs['no'] + cs['unclear']) / max(len(ks), 1):.1%}")
    cut = [k for k in real if key[k]["hidden"]]
    cc = collections.Counter(ans[k] for k in cut)
    print(f"  with verses cut off ({len(cut)}): {dict(cc)}")
    by_type = collections.defaultdict(collections.Counter)
    for k in real:
        by_type[key[k]["type"]][ans[k]] += 1
    print("\nFLAG RATE BY RELATION TYPE (real; n, no, unclear, flag rate):")
    for t, cs in sorted(by_type.items(), key=lambda x: -sum(x[1].values())):
        n = sum(cs.values())
        print(f"  {t:24s} {n:4d} no={cs['no']:3d} unclear={cs['unclear']:3d} implied={cs['implied']:3d} "
              f"flag {(cs['no'] + cs['unclear']) / n:.0%}")
    div = [k for k in ans if key[k]["divine"] and key[k]["kind"] == "real" and ans[k] in ("no", "unclear")]
    print(f"\nFLAGS ON DIVINE PERSONS (the owner's, record by record): {len(div)} of "
          f"{sum(key[k]['divine'] for k in real)} real rows touching one")
    for k in div:
        print(f"  [{ans[k]}] {key[k]['text']} | {', '.join(key[k]['refs'])} | {why[k][:140]}")
    # speed
    tot = sum(s for _, s, _, _ in secs)
    nv = sum(len(key[k]["verses"]) for k, *_ in secs)
    print(f"\nSPEED: {len(secs)} calls, {tot / 60:.1f} min of model time, {len(secs) / max(tot / 60, 1e-9):.1f} calls/min, "
          f"{nv / max(tot / 60, 1e-9):.1f} verses/min, mean {tot / max(len(secs), 1):.1f} s/call, "
          f"mean in_tok {sum(t for _, _, t, _ in secs) / max(len(secs), 1):.0f}")
    if which == "5a":
        full = JOBS / f"{NAMES['5']}.key.jsonl"
        if full.exists():
            n5 = sum(1 for _ in open(full, encoding="utf-8"))
            chars = [len(json.dumps(messages(key[k]))) for k, *_ in secs]
            n_v = sum(len(json.loads(l)["verses"]) for l in open(full, encoding="utf-8"))
            mean_v = sum(len(key[k]["verses"]) for k, *_ in secs) / len(secs)
            print(f"  job 5: {n5} calls, {n_v / n5:.1f} verses/call (sample {mean_v:.1f}); at the sample's mean "
                  f"{n5 * tot / len(secs) / 3600:.1f} h; scaled by verses/call "
                  f"{n5 * tot / len(secs) * (n_v / n5) / mean_v / 3600:.1f} h")
        else:
            print("  (export job 5 first for the projection)")
    # precision sample
    rnd = random.Random(5)
    no = [k for k in real if ans[k] == "no"]
    print(f"\n15 OF THE {len(no)} REAL \"no\" FLAGS:")
    for k in rnd.sample(no, min(15, len(no))):
        i = key[k]
        print(f"\n--- {i['text']}   [{i['type']}; {i['file']}:{i['line']}]")
        for v in i["verses"]:
            print(f"    {v['ref']}: {v['text']}")
        if i["hidden"]:
            print(f"    (+{i['hidden']} verses not shown)")
        print(f"    MODEL: no -- {why[k]}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "export-sample":
        export_sample("--event-rows" in sys.argv)
    elif cmd == "export":
        export_all(sys.argv[2] if len(sys.argv) > 2 else "5")
    else:
        report(sys.argv[2] if len(sys.argv) > 2 else "5a")
