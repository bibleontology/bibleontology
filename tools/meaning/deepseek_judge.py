"""DeepSeek (V4.1 Flash, through the capped delegate tool) judges the Mac's flagged findings (2026-10-31).

The Mac's passes (tools/meaning/local_*.py, gemma4:26b) only FLAG; a judge says which flags are real. Doug: "delegate the
judging to DeepSeek 4.1 flash". This builds narrow batches (one question per type, worked examples, planted answers mixed
in so its own accuracy is measured), runs them blind through `bibleont.delegate` (digest only, no tools, thinking off,
daily and weekly caps checked per call) and collects the verdicts. Nothing is written to the graph.

WHAT DEEPSEEK IS SENT (the owner's rule: nothing confidential): Berean verse text, entity names, relation types, the
Mac's proposed answer. Never docs/, readers' notes, MACULA's data/raw, settings or keys. Divine persons (God, the Father,
Jesus, the Holy Spirit) are never sent: their rows are the owner's, record by record (docs/review/mac-runs-2026-10-30-divine.tsv).

    python tools/meaning/deepseek_judge.py build              -> out/grunt/deepseek-judge/batches-<type>.jsonl (+ counts)
    python tools/meaning/deepseek_judge.py run TYPE [N]       run the first N unrun batches of TYPE (doer, flag, err, gap)
    python tools/meaning/deepseek_judge.py report [TYPE]      accuracy on the planted answers, verdict counts
"""
import collections
import gzip
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT.parents[2] if ".claude" in ROOT.parts else ROOT   # the main checkout holds the gitignored clause records
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))

WORK = ROOT / "out" / "grunt" / "deepseek-judge"
JOBS, DONE = ROOT / "out" / "grunt" / "jobs", ROOT / "out" / "grunt" / "done"
DIVINE = {"god", "the_father", "jesus", "holy_ghost", "spirit", "spirit_of_god"}
DIVINE_NAMES = {"god", "the lord", "lord", "jesus", "christ", "jesus christ", "the father", "holy spirit", "the spirit",
                "the holy spirit", "spirit of god", "the spirit of god", "yahweh", "the lord god", "lord god", "jehovah"}
BATCH = 36                  # items a call
SEED = 20261031
import os
RESULTS = "results" + os.environ.get("DSJ_RUN", "")      # DSJ_RUN=2 reruns every batch into results2 (a judgement that
                                                          # matters runs twice: compare, and treat differences as unsettled)

FORMAT_TAIL = """
Answer with one JSON object per line, one line per item, in the order given, and nothing else (no heading, no \
commentary): """


# ------------------------------------------------------------------ shared data
def load_bible():
    import local_resolve as LR
    return LR, LR.context(k_before=3)


def short_ctx(c):
    """-> (before lines 'Gen.1.1 text', the verse's own line)"""
    return c["before"], f"{c['ref']} {c['text']}"


def card_label(ents, rid):
    e = ents.get(rid) or {}
    nm = e.get("name") or rid.replace("_", " ")
    d = (e.get("disambiguation") or "").strip()
    if d and not d.startswith("a person of this name"):
        return f"{nm} ({d[:110]})"
    return nm


def is_divine_name(s):
    return (s or "").strip().lower() in DIVINE_NAMES


# ------------------------------------------------------------------ DOERS
BRIEF_DOER = """You judge one narrow question about Bible verses. The text is the Berean Standard Bible. For each item \
you get a verse with the verses before it, one ACTION in the verse (with what it is done to, as a graph recorded it), \
and a CANDIDATE: a name proposed as the one who does the action.

Question: in this verse, is the CANDIDATE the one who does the ACTION?
- "yes": the verse, or the verses just before it, make plain that this person does it: the clause names them, or \
"he", "she", "they", "I" or "you" clearly stands for them (the speaker of "I", the person spoken to for "you", the \
last person named for "he").
- "no": someone else does it; or the candidate is the one it is done to; or speaker and listener are swapped; or the \
candidate is only named nearby without doing this.
- "unclear": the text shown does not settle who does it.
Judge from the text shown only, never from memory of the story. The ACTION word is the graph's, so it may not match the \
verse's wording exactly: find the clause it stands for, using RECEIVER when the same verb appears twice. Quote the few \
words of the text that decide it.

Worked examples:
- Gen 4:8 "Cain rose up against his brother Abel and killed him." ACTION "killed", RECEIVER Abel, CANDIDATE Cain -> \
{"verdict": "yes", "words": "Cain rose up against his brother Abel and killed him"}
- Gen 22:3 "So Abraham got up early the next morning and saddled his donkey. He took with him two servants and his son \
Isaac. And he split the wood for the burnt offering, and set out", ACTION "split", CANDIDATE Isaac -> \
{"verdict": "no", "words": "Abraham got up early ... And he split the wood"} (the "he" is Abraham; Isaac is only taken along)
- Gen 22:2 "Then God said, 'Take your son, your only son Isaac, whom you love'" with Gen 22:1 "God tested Abraham and \
said to him, 'Abraham!'", ACTION "love", RECEIVER Isaac, CANDIDATE Abraham -> {"verdict": "yes", "words": "your son, \
your only son Isaac, whom you love"} ("you" is Abraham, the one God speaks to)
- Psa 12:2 "They speak falsehood to one another" with nothing before naming who, CANDIDATE "the godly" -> \
{"verdict": "unclear", "words": ""}
""" + FORMAT_TAIL + """{"id": "<item id>", "verdict": "yes" | "no" | "unclear", "words": "<deciding words>"}"""


def doer_item_text(it):
    lines = [f"[{it['id']}] {it['ref']}"]
    for b in it["before"]:
        lines.append(f"  before: {b}")
    lines.append(f"  VERSE: {it['text']}")
    lines.append(f"  ACTION: {it['action']!r}   RECEIVER: {it['receiver']}   (form: {it['modality']})")
    lines.append(f"  CANDIDATE: {it['cand']}")
    return "\n".join(lines)


def build_doers(rnd):
    import local_resolve as LR
    from local_resolve import PRONOUN, names, norm, parse
    LRm, ctx = load_bible()
    ents, alias = names()
    full = {}
    import glob
    for f in sorted(glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl"))):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                e = json.loads(ln)
                full.setdefault(e["id"], e)
    order = []
    for ln in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        if "b" in d:
            order.append(f"{LR.BOOK.get(d['b'], d['b'])}.{d['c']}.{d['v']}")
    pos = {k: i for i, k in enumerate(order)}
    moved = json.load(open(ROOT / "out" / "versemap.json", encoding="utf-8"))["moved"]
    ment = collections.defaultdict(set)
    for ln in gzip.open(ROOT / "out" / "mentions.jsonl.gz", "rt", encoding="utf-8"):
        m = json.loads(ln)
        if m.get("record"):
            ref = m["occurrence"].split("#")[0]
            ment[moved.get(ref, ref)].add(m["record"])
    crec = {}
    for ln in open(MAIN / "out" / "meaning" / "clause-records.jsonl", encoding="utf-8"):
        r = json.loads(ln)
        crec[r["clause"]] = r
    corr = set()
    for f in ("pointer-corrections-2026-10-27.json", "pointer-corrections-divine-2026-10-27.json"):
        for c in json.load(open(ROOT / "ontology/provenance/sweep" / f, encoding="utf-8"))["corrections"]:
            s = c["src"]
            corr.add(s[:-1] if s.endswith("s") and "#cl" in s else s)

    def pin(ref, who):
        ids = alias.get(norm(who), set())
        if not ids:
            return None
        k = moved.get(ref, ref)
        i = pos.get(k)
        if i is None:
            return None
        near = set()
        for j in range(max(0, i - 3), i + 1):
            near |= ment.get(order[j], set())
        hit = ids & near
        return next(iter(hit)) if len(hit) == 1 else None

    def jobrows(name):
        return [json.loads(l) for l in open(DONE / f"{name}.jsonl", encoding="utf-8")]

    items3 = {}
    for l in open(JOBS / "structure-all.items.jsonl", encoding="utf-8"):
        d = json.loads(l)
        items3[d["key"]] = d
    cands = collections.defaultdict(dict)
    d3 = jobrows("3-structure-all")
    for i, d in enumerate(d3):
        if i < 22543:
            continue
        it = items3[d["key"]]
        if it.get("planted") or it["doer"] != "unnamed":
            continue
        who = re.search(r'"doer"\s*:\s*"([^"]*)"', d["content"] or "")
        if who and who[1] and who[1].lower() != "not stated":
            cands[d["key"]]["3"] = who[1]
    act = {}
    for src, name in (("2e", "2e-resolve-subjects"), ("4", "4-resolve-pronouns")):
        its = {}
        for l in open(JOBS / f"{name}.items.jsonl", encoding="utf-8"):
            d = json.loads(l)
            its[d["key"]] = d
        for d in jobrows(name):
            it = its.get(d["key"])
            if not it or "answer" in it:
                continue
            act.setdefault(d["key"], it["action"])
            p = parse(d["content"])
            if p and p["how"] not in ("not stated", "general") and p["who"] and not PRONOUN.match(p["who"].strip()):
                cands[d["key"]][src] = p["who"]
    res = []
    n_div = 0
    for key, srcs in cands.items():
        cr = crec.get(key)
        if not cr or (cr.get("subject") or {}).get("how") != "unnamed" or key in corr:
            continue
        obj = (cr.get("object") or {}).get("record")
        if not obj:
            continue                      # completes no relation
        pins = {}
        for s, w in srcs.items():
            if PRONOUN.match(w.strip()):
                continue
            r = pin(cr["ref"], w)
            if r:
                pins.setdefault(r, []).append((s, w))
        for rid, lst in pins.items():
            if rid in DIVINE:
                n_div += 1
                continue
            c = ctx(cr["ref"])
            if not c:
                continue
            res.append({"type": "doer", "clause": key, "ref": c["ref"], "before": c["before"], "text": c["text"],
                        "action": act.get(key) or items3[key]["action"],
                        "receiver": (full.get(obj) or {}).get("name") or (obj or "(none)").replace("_", " "),
                        "modality": cr.get("modality") or "", "cand": lst[0][1], "card": card_label(full, rid),
                        "rec": rid, "srcs": sorted({s for s, _ in lst}), "planted": None, "mac_says": "yes"})
    rnd.shuffle(res)
    # --- planted: known answers (kept out of the real list)
    noplants, yesplants = [], []
    for k, it in items3.items():
        if it.get("planted") == "wrong_who" and it["doer"] != "unnamed" and is_divine_name(it["doer"]) is False:
            base = k.split("#planted")[0]
            cr = crec.get(base)
            if not cr:
                continue
            noplants.append((it, cr))
    d3map = {d["key"]: d for d in d3}
    for k, it in items3.items():
        if it.get("planted") or it["doer"] in ("unnamed", "") or is_divine_name(it["doer"]):
            continue
        cr = crec.get(k)
        if not cr or (cr.get("subject") or {}).get("how") != "named":
            continue
        if cr["subject"].get("record") in DIVINE:
            continue
        d = d3map.get(k)
        if not d or '"answer": "yes"' not in (d["content"] or "")[:60]:
            continue
        first = it["doer"].split()[0].lower()
        if first in (it["text"] or "").lower():
            yesplants.append((it, cr))
    rnd.shuffle(noplants)
    rnd.shuffle(yesplants)

    def plant_item(it, cr, truth):
        base = it["key"].split("#planted")[0]
        c = ctx(cr["ref"])
        if not c:
            return None
        obj = (cr.get("object") or {}).get("record")
        return {"type": "doer", "clause": it["key"], "ref": c["ref"], "before": c["before"], "text": c["text"],
                "action": it["action"], "receiver": it["receiver"] if it["receiver"] != "unnamed" else
                ((full.get(obj) or {}).get("name") or obj.replace("_", " ") if obj else "(none)"),
                "modality": cr.get("modality") or "",
                "cand": it["doer"], "card": it["doer"], "rec": None, "srcs": [], "planted": truth,
                "mac_says": None}
    return res, [p for p in (plant_item(i, c, "no") for i, c in noplants[:80]) if p], \
        [p for p in (plant_item(i, c, "yes") for i, c in yesplants[:80]) if p], n_div


# ------------------------------------------------------------------ FLAGS ON SHOWN STATEMENTS (job 3 tail)
BRIEF_FLAG = """You judge one narrow question about Bible verses. The text is the Berean Standard Bible. For each item \
you get a verse (with the verse before it) and a RECORD written DOER -action-> RECEIVER [form], made by a program from \
the original text.

Question: does this verse have this action, done by this doer, to this receiver?
- "yes": the verse says it. The record's words are the graph's, so "God -gave-> Saul" is also said by "the LORD \
delivered you into my hand" if the "you" is Saul; the doer and receiver may be named by a pronoun that the text makes \
plain. Different wording for the same act is fine.
- "no": the action is not in the verse, or someone else does it, or it is done to someone or something else (a place \
for a person, a group for one man), or the verse says the opposite or only that it was asked or promised when the \
record says it was done. Say in "means" what the verse actually says.
- "unclear": the text shown does not settle it.
The form is how the verse puts the action: "stated" (asserted, in any tense), "promised", "commanded", "asked", \
"wished", "nonfinite" (an infinitive or participle, often a purpose). The record already carries it; judge only the \
who and the what. Judge from the text shown only. Quote the few words that decide it.

Worked examples:
- Gen 4:8 "Cain rose up against his brother Abel and killed him." record "Cain -killed-> Abel [stated]" -> \
{"verdict": "yes", "means": "", "words": "Cain rose up against his brother Abel and killed him"}
- 1Chr 13:11 "Then David became angry because the LORD had burst forth against Uzzah. So he named that place \
Perez-uzzah" record "David -called-> Perez [stated]" -> {"verdict": "no", "means": "David named the place \
Perez-uzzah; Perez the man is not in the verse", "words": "he named that place Perez-uzzah"}
- 1Sam 7:15 "Samuel judged Israel all the days of his life." record "Samuel -judged-> Israel [stated]" -> \
{"verdict": "yes", "means": "", "words": "Samuel judged Israel"}
""" + FORMAT_TAIL + """{"id": "<item id>", "verdict": "yes" | "no" | "unclear", "means": "<what the verse says, \
when no>", "words": "<deciding words>"}"""


def flag_item_text(it):
    lines = [f"[{it['id']}] {it['ref']}"]
    for b in it["before"]:
        lines.append(f"  before: {b}")
    lines.append(f"  VERSE: {it['text']}")
    lines.append(f"  RECORD: {it['record']} [{it['modality']}]")
    return "\n".join(lines)


def build_flags(rnd):
    LRm, ctx = load_bible()
    import local_resolve as LR
    full = {}
    import glob
    for f in sorted(glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl"))):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                e = json.loads(ln)
                full.setdefault(e["id"], e)
    crec = {}
    for ln in open(MAIN / "out" / "meaning" / "clause-records.jsonl", encoding="utf-8"):
        r = json.loads(ln)
        crec[r["clause"]] = r
    shown = set()
    for l in open(ROOT / "ontology" / "relations" / "verb-statements.jsonl", encoding="utf-8"):
        shown |= set(json.loads(l)["clauses"])
    items3 = {}
    for l in open(JOBS / "structure-all.items.jsonl", encoding="utf-8"):
        d = json.loads(l)
        items3[d["key"]] = d
    d3 = [json.loads(l) for l in open(DONE / "3-structure-all.jsonl", encoding="utf-8")]
    d3map = {d["key"]: d for d in d3}

    def rec_text(it, cr):
        a = it["action"].split(" (")[0]
        return f"{it['doer']} -{a}-> {it['receiver']}"

    real, n_div = [], 0
    for i, d in enumerate(d3):
        if i < 22543:
            continue
        it = items3[d["key"]]
        if it.get("planted") or d["key"] not in shown:
            continue
        a = re.search(r'"answer"\s*:\s*"([^"]*)"', d["content"] or "")
        if not a or a[1] not in ("no", "wrong_who"):
            continue
        cr = crec.get(d["key"])
        if not cr:
            continue
        ends = {(cr.get("subject") or {}).get("record"), (cr.get("object") or {}).get("record")}
        if ends & DIVINE or is_divine_name(it["doer"]) or is_divine_name(it["receiver"]):
            n_div += 1
            continue
        c = ctx(cr["ref"])
        if not c:
            continue
        real.append({"type": "flag", "clause": d["key"], "ref": c["ref"], "before": c["before"][-1:], "text": c["text"],
                     "record": rec_text(it, cr), "modality": it["mode"], "planted": None, "mac_says": a[1]})
    no, yes = [], []
    for k, it in items3.items():
        if it.get("planted") == "wrong_who" and it["doer"] != "unnamed" and not is_divine_name(it["doer"]) \
                and not is_divine_name(it["receiver"]):
            cr = crec.get(k.split("#planted")[0])
            c = cr and ctx(cr["ref"])
            if c:
                no.append({"type": "flag", "clause": k, "ref": c["ref"], "before": c["before"][-1:], "text": c["text"],
                           "record": rec_text(it, cr), "modality": it["mode"], "planted": "no", "mac_says": None})
        elif not it.get("planted") and k in shown and it["doer"] not in ("unnamed", "") and it["receiver"] != "unnamed" \
                and not is_divine_name(it["doer"]) and not is_divine_name(it["receiver"]):
            d = d3map.get(k)
            cr = crec.get(k)
            if d and '"answer": "yes"' in (d["content"] or "")[:60] and cr and it["receiver"] != "name" \
                    and it["doer"].split()[0].lower() in it["text"].lower() \
                    and it["receiver"].split()[0].lower() in it["text"].lower():
                c = ctx(cr["ref"])
                if c:
                    yes.append({"type": "flag", "clause": k, "ref": c["ref"], "before": c["before"][-1:],
                                "text": c["text"], "record": rec_text(it, cr), "modality": it["mode"],
                                "planted": "yes", "mac_says": None})
    rnd.shuffle(no)
    rnd.shuffle(yes)
    return real, no[:60], yes[:60], n_div


# ------------------------------------------------------------------ THE ERRORS PASS (job 5)
STRATA = ["took", "father_of", "gave", "charged", "sent", "built", "carried", "traveled_to", "likened_to", "assessed_as"]
NOISE_TYPES = {"composed_of", "drawn_from", "same_steps_as", "issues_from"}
BRIEF_ERR = """You check a Bible knowledge graph against the text. The text is the Berean Standard Bible. For each item \
you get ONE relation, written SUBJECT -- relation -- OBJECT, and the verses the graph cites for it. Answer one question: \
do these verses, as given, say this?

- "yes": a verse states it. A pronoun ("he", "Him") counts as naming its person when the verses given make clear who it is.
- "implied": the verses imply it without stating it; a reader would draw it from them.
- "no": the verses do not say it, or say something else: the wrong person, the wrong place, a prediction or someone's \
claim presented as what happened, a different event, a different relation between the same two.
- "unclear": the verses given are not enough to tell (they leave out who is meant, or the passage is cut off).

Judge only from the verses given, never from memory of the Bible. The subject and object may be a person, place, group, \
event, saying or idea; judge each as the verses use it. Quote the few words of the verse that decide it.

Worked examples:
- Cain -- killed -- Abel; Gen 4:8 "...Cain rose up against his brother Abel and killed him." -> yes. words: "Cain rose \
up against his brother Abel and killed him".
- Saul -- killed -- Goliath; 1 Sam 17:50 "Thus David prevailed over the Philistine with a sling and a stone; ... he \
struck down the Philistine and killed him." -> no. words: the one who killed him is David; Saul is not named.
- Jerusalem -- contains -- Golgotha; John 19:20 "...the place where Jesus was crucified was near the city..." -> no. \
words: "near the city" puts the place beside Jerusalem, not inside it.
- Obed -- grandfather of -- David; Ruth 4:17 "... they named him Obed. He became the father of Jesse, the father of \
David." -> implied. words: "the father of Jesse, the father of David".
""" + FORMAT_TAIL + """{"id": "<item id>", "verdict": "yes" | "implied" | "no" | "unclear", "words": "<deciding words>"}"""


def err_item_text(it):
    lines = [f"[{it['id']}] {it['text']}"]
    for v in it["verses"]:
        lines.append(f"  {v['ref']}: {v['text']}")
    if it.get("hidden"):
        lines.append(f"  (+{it['hidden']} cited verses not shown)")
    return "\n".join(lines)


def _key(name):
    return [json.loads(l) for l in open(JOBS / f"{name}.key.jsonl", encoding="utf-8")]


def _parse5(content):
    s = (content or "").strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.M).strip()
    try:
        d = json.loads(s)
        if d.get("answer") in ("yes", "implied", "no", "unclear"):
            return d["answer"]
    except Exception:
        pass
    m = re.search(r'"answer"\s*:\s*"(yes|implied|no|unclear)"', s)
    return m[1] if m else None


def build_errors(rnd, all_no=False):
    key5 = {k["key"]: k for k in _key("5-relation-check")}
    ans = {}
    for l in open(DONE / "5-relation-check.jsonl", encoding="utf-8"):
        d = json.loads(l)
        if "error" not in d:
            a = _parse5(d.get("content"))
            if a:
                ans[d["key"]] = a
    nodiv = lambda k: not k["divine"] and not is_divine_name(k["subject"]) and not is_divine_name(k["object"])  # noqa: E731
    by_type = collections.defaultdict(list)
    n_div = 0
    for k, a in ans.items():
        kk = key5[k]
        if a != "no" or kk["kind"] != "real":
            continue
        if not nodiv(kk):
            n_div += 1
            continue
        by_type[kk["type"]].append(kk)
    sample = []
    for t in STRATA:
        pool = by_type.get(t, [])
        rnd.shuffle(pool)
        sample += pool[:6]
    sample_keys = {k["key"] for k in sample}
    rest = [k for t, lst in by_type.items() if t not in NOISE_TYPES for k in lst if k["key"] not in sample_keys]
    # planted: the 5a sample's known-wrong rows (must be "no") and rows the Mac and the cited verse agree on (yes)
    key5a = _key("5a-relation-check-sample")
    ans5a = {}
    for l in open(DONE / "5a-relation-check-sample.jsonl", encoding="utf-8"):
        d = json.loads(l)
        if "error" not in d:
            a = _parse5(d.get("content"))
            if a:
                ans5a[d["key"]] = a
    no_pl = [k for k in key5a if k["kind"].startswith("plant") and nodiv(k) and k["key"] in ans5a]
    yes_pl = [k for k in key5a if k["kind"] == "real" and ans5a.get(k["key"]) == "yes" and nodiv(k)
              and k["type"] in ("father_of", "mother_of", "husband_of", "wife_of", "brother_of", "son_of", "killed",
                                "built", "gave", "sent", "took", "traveled_to")
              and not k["hidden"]
              and k["subject"].split()[0].lower() in " ".join(v["text"] for v in k["verses"]).lower()
              and k["object"].split()[0].lower() in " ".join(v["text"] for v in k["verses"]).lower()]
    # read by hand (2026-10-31): these two are not clean "yes" (Sheol for "the grave"; Bethuel's mother is in verses
    # that are cut off), so they are not used as planted answers
    yes_pl = [k for k in yes_pl if k["text"] not in ("the wicked people — traveled to — the grave",
                                                     "Nahor — father of — Bethuel")]
    rnd.shuffle(no_pl)
    rnd.shuffle(yes_pl)

    def mk(k, planted, mac):
        return {"type": "err", "src": k["src"], "dst": k["dst"], "rtype": k["type"], "text": k["text"],
                "verses": k["verses"], "hidden": k["hidden"], "planted": planted, "mac_says": mac,
                "file": k["file"], "line": k["line"], "refs": k["refs"], "keyid": k["key"]}
    return [mk(k, None, "no") for k in sample], [mk(k, None, "no") for k in rest], \
        [mk(k, "no", None) for k in no_pl[:40]], [mk(k, "yes", None) for k in yes_pl[:40]], n_div


# ------------------------------------------------------------------ THE GAPS (job 6b)
BRIEF_GAP = """You check a Bible knowledge graph for gaps. The text is the Berean Standard Bible. For each item you get a \
CARD (a person, group or event as the graph holds it: its name and the lines it already says, each with its verses), a \
STATEMENT that a program says the Bible makes about it but the card does not hold, and the CITED verse.

Question: does the cited verse say this about this card, and is it missing from the card's lines?
- "real_gap": the cited verse says the statement, it is about this card's person or event, and no line of the card \
already says it (in other words or by the same verses).
- "not_a_gap": the card already says it (name the line); or the cited verse does not say it; or it is about someone \
else; or it is a trivial detail no reader would expect on the card.
- "unclear": the verse might say it but you cannot tell from the text shown.
Judge from the verse and the lines shown only. Look at every line before you answer.

Worked examples:
- Card "Peter": lines "brother of Andrew -- Matt 4:18", "followed Jesus -- Luke 18:28". STATEMENT "Peter denied Jesus three \
times"; CITED Matt 26:74 "Then he began to curse and swear, 'I do not know the man!' Immediately a rooster crowed." -> \
{"verdict": "real_gap", "why": "the denial is not among the lines"}
- Card "Cain murders Abel": lines "Cain killed Abel -- Gen 4:8", "the LORD cursed Cain -- Gen 4:11". STATEMENT "Cain \
killed his brother Abel"; CITED Gen 4:8 -> {"verdict": "not_a_gap", "why": "the line 'Cain killed Abel' says it"}
""" + FORMAT_TAIL + """{"id": "<item id>", "verdict": "real_gap" | "not_a_gap" | "unclear", "why": "<one short \
line>"}"""


def gap_item_text(it):
    lines = [f"[{it['id']}] CARD: {it['name']} ({it['kind']}" + (f"; {it['who']}" if it.get('who') else "") + ")"]
    lines.append("  lines on the card:" + ("" if it["shown"] else " (none)"))
    for s in it["shown"]:
        lines.append(f"    - {s}")
    if it.get("more"):
        lines.append(f"    (+{it['more']} more lines not shown)")
    lines.append(f"  STATEMENT: {it['what']}")
    lines.append(f"  CITED {it['ref']}: {it['verse']}")
    return "\n".join(lines)


def build_gaps(rnd):
    import local_gap_check as G
    from local_relation_check import bible
    by = bible()
    key = {k["key"]: k for k in _key("6b-gap-check")}
    rows = {}
    for l in open(DONE / "6b-gap-check.jsonl", encoding="utf-8"):
        d = json.loads(l)
        if "error" in d:
            continue
        fl, ok = G.parse_answer(d.get("content"))
        if ok:
            rows[d["key"]] = fl
    real, n_div, n_all, n_pass, n_dup = [], 0, 0, 0, 0
    for k, fl in rows.items():
        kk = key[k]
        for f in fl:
            n_all += 1
            ex, ok, verse = G.check_flag(by, f)
            if not (ex and ok):
                continue
            n_pass += 1
            have = set()
            for ln in kk["lines"]:
                for ref in ln["refs"]:
                    have |= G.verses_of(ref)
            if G.verses_of(f["ref"]) & have:
                n_dup += 1
                continue
            if kk["divine"] or is_divine_name(kk["name"]):
                n_div += 1
                continue
            real.append({"type": "gap", "card": kk["id"], "kind": kk["kind"], "name": kk["name"], "who": kk["who"],
                         "shown": kk["shown"], "more": kk["more"], "nlines": len(kk["lines"]), "what": f["what"],
                         "ref": f["ref"], "words": f["words"], "verse": verse[:420], "planted": None,
                         "mac_says": "real_gap"})
    # planted pairs from the 6a sample: a card with its strong line removed (the statement is a real gap), and the
    # same statement against the twin card that still has the line (not a gap)
    key6a = _key("6a-gap-check-sample")
    by_id = {k["id"]: k for k in key6a if not k["plant"]}
    yes_pl, no_pl = [], []
    for k in key6a:
        if not k["plant"] or k["divine"] or is_divine_name(k["name"]):
            continue
        tw = by_id.get(k["twin"])
        rem = k["removed"]
        if not tw or len(rem["refs"]) < 1:
            continue
        # read by hand (2026-10-31): the verse does not say these (a relation drawn from the graph's own sense of
        # the passage, or a place the cited verse does not name), so they cannot serve as known gaps
        if k["name"] in ("Judah & Tamar", "the wicked people", "Miriam"):
            continue
        ref = rem["refs"][0]
        ex, ok, verse = G.check_flag(by, {"ref": ref, "words": "a b"})
        if not ex:
            continue
        base = {"type": "gap", "kind": k["kind"], "name": k["name"], "who": k["who"], "what": rem["text"], "ref": ref,
                "verse": verse[:420], "words": "", "mac_says": None}
        yes_pl.append({**base, "card": k["id"], "shown": k["shown"], "more": k["more"], "planted": "real_gap"})
        no_pl.append({**base, "card": tw["id"], "shown": tw["shown"], "more": tw["more"], "planted": "not_a_gap"})
    return real, yes_pl, no_pl, (n_all, n_pass, n_dup, n_div)


# ------------------------------------------------------------------ batches
def mix(real, yes, no, per_batch_plants, rnd, prefix, text_fn, brief, size=BATCH):
    """real items spread over batches, each with `per_batch_plants` yes and as many no planted answers mixed in"""
    nb = max(1, -(-len(real) // (size - 2 * per_batch_plants)))
    chunks = [real[i::nb] for i in range(nb)]
    yes, no = list(yes), list(no)
    batches = []
    for bi, ch in enumerate(chunks, 1):
        items = list(ch)
        for _ in range(per_batch_plants):
            if yes:
                items.append(yes.pop())
            if no:
                items.append(no.pop())
        rnd.shuffle(items)
        for n, it in enumerate(items, 1):
            it["id"] = f"{prefix}{n}"
        body = "\n\n".join(text_fn(it) for it in items)
        task = brief + "\n\nITEMS (" + str(len(items)) + "):\n\n" + body + "\n"
        batches.append({"batch": f"{prefix.upper()}-{bi:02d}", "task": task, "items": items})
    return batches


def write_batches(name, batches):
    WORK.mkdir(parents=True, exist_ok=True)
    with open(WORK / f"batches-{name}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for b in batches:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")


def build(only=None):
    rnd = random.Random(SEED)
    out = {}
    if only in (None, "doer"):
        real, no, yes, nd = build_doers(rnd)
        # one item per (clause, record); a clause pinned two ways shows twice
        bs = mix(real, yes, no, 3, rnd, "d", doer_item_text, BRIEF_DOER)
        write_batches("doer", bs)
        out["doer"] = f"{len(real)} real, {nd} divine pins left out, {sum(len(b['items']) for b in bs)} items in {len(bs)} batches"
    if only in (None, "flag"):
        real, no, yes, nd = build_flags(rnd)
        bs = mix(real, yes, no, 4, rnd, "f", flag_item_text, BRIEF_FLAG)
        write_batches("flag", bs)
        out["flag"] = f"{len(real)} real, {nd} divine left out, {sum(len(b['items']) for b in bs)} items in {len(bs)} batches"
    if only in (None, "err"):
        sample, rest, no, yes, nd = build_errors(rnd)
        bs = mix(sample, yes, no, 8, rnd, "e", err_item_text, BRIEF_ERR, size=40)
        write_batches("err", bs)
        bs2 = mix(rest, yes[8:], no[8:], 3, rnd, "x", err_item_text, BRIEF_ERR)
        write_batches("errrest", bs2)
        out["err"] = (f"{len(sample)} sample, {len(rest)} rest (noise types left out), {nd} divine left out; "
                      f"{sum(len(b['items']) for b in bs)} items in {len(bs)} batches; rest {len(bs2)} batches")
    if only in (None, "gap"):
        real, yes, no, st = build_gaps(rnd)
        # a planted pair (the card with the line removed, and its twin that still holds it) must never share a call:
        # the first run put both in one call and the judge cited the twin ("contrast item g25"). mix() takes planted
        # answers off the END of each list, so rotating one list by a batch's worth keeps every pair apart
        no = no[3:] + no[:3]
        bs = mix(real, yes, no, 3, rnd, "g", gap_item_text, BRIEF_GAP, size=30)
        for b in bs:
            cards = [it["card"] for it in b["items"] if it["planted"]]
            names = [it["name"] for it in b["items"] if it["planted"]]
            assert len(set(names)) == len(names), "a planted pair shares a call"
        write_batches("gap", bs)
        out["gap"] = f"{len(real)} real ({st}), {sum(len(b['items']) for b in bs)} items in {len(bs)} batches"
    for k, v in out.items():
        print(f"{k}: {v}")


# ------------------------------------------------------------------ run and collect
def parse_lines(answer):
    """one JSON object a line, read tolerantly: the worker sometimes leaves a quote unescaped in "words" or adds a
    comment after the object, and a strict parse dropped whole batches (X-18: 0 of 29). The id and verdict are read by
    pattern; where an id appears twice (it corrected itself) the LAST line wins; "words"/"means"/"why" are kept as
    far as they read."""
    got = {}
    for line in (answer or "").splitlines():
        m = re.search(r'"id"\s*:\s*"([^"]+)"', line)
        v = re.search(r'"verdict"\s*:\s*"([a-z_]+)"', line)
        if not (m and v):
            continue
        d = {"id": m[1], "verdict": v[1]}
        for fld in ("words", "means", "why"):
            w = re.search(r'"%s"\s*:\s*"(.*?)"\s*(?:,\s*"[a-z]+"\s*:|\}|$)' % fld, line)
            if w:
                d[fld] = w[1]
        if "words" not in d and "why" not in d:
            d["words"] = line[v.end():][:300].strip(" ,}")
        got[d["id"]] = d
    return got


def reparse(name):
    """re-read every stored answer of a type with the current parser"""
    for f in sorted((WORK / RESULTS).glob("*.json")):
        res = json.loads(f.read_text(encoding="utf-8"))
        if not res["batch"].startswith(name):
            continue
        text = (MAIN / res["result_file"]).read_text(encoding="utf-8")
        ans = text.split("## Answer", 1)[1].rsplit("## Tool calls", 1)[0]
        res["got"] = parse_lines(ans)
        res["answered"] = len(res["got"])
        f.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")


def call(delegate, task, level, label):
    """delegate.run, with its one fault worked around: from a worktree the call is made, billed and written to the shared
    .delegate/, and then `result_file` (a path made relative to this checkout) raises ValueError. The answer is read
    back from the ledger's newest entry and its result file."""
    try:
        return delegate.run(task, level, label=label, blind=True)
    except ValueError:
        last = [json.loads(x) for x in open(delegate.LEDGER, encoding="utf-8") if x.strip()][-1]
        assert last["label"] == label, (last["label"], label)
        text = (delegate.RESULTS / f"{last['id']}.md").read_text(encoding="utf-8")
        ans = text.split("## Answer", 1)[1].rsplit("## Tool calls", 1)[0].strip()
        return {**last, "answer": ans, "result_file": f".delegate/results/{last['id']}.md"}


def run(name, n=None, level=2):
    from bibleont import delegate
    batches = [json.loads(l) for l in open(WORK / f"batches-{name}.jsonl", encoding="utf-8")]
    resdir = WORK / RESULTS
    resdir.mkdir(exist_ok=True)
    done = 0
    for b in batches:
        f = resdir / f"{b['batch']}.json"
        if f.exists():
            continue
        if n is not None and done >= n:
            break
        r = call(delegate, b["task"], level, f"judge {b['batch']}")
        if r.get("refused") or r.get("stopped") or not r.get("answer"):
            print(b["batch"], "STOPPED:", r.get("refused") or r.get("stopped") or "empty answer")
            return
        got = parse_lines(r["answer"])
        f.write_text(json.dumps({"batch": b["batch"], "cost": r["cost"], "tokens": r["tokens"], "calls": r["calls"],
                                 "got": got, "answered": len(got), "asked": len(b["items"]),
                                 "result_file": r["result_file"]}, ensure_ascii=False), encoding="utf-8")
        print(f"{b['batch']}: {len(got)} of {len(b['items'])} answered, ${r['cost']:.4f}, tokens {r['tokens']}")
        done += 1


def collect(name):
    batches = [json.loads(l) for l in open(WORK / f"batches-{name}.jsonl", encoding="utf-8")]
    rows = []
    for b in batches:
        f = WORK / RESULTS / f"{b['batch']}.json"
        if not f.exists():
            continue
        res = json.loads(f.read_text(encoding="utf-8"))
        for it in b["items"]:
            a = res["got"].get(it["id"])
            rows.append({**it, "batch": b["batch"], "ds": a})
    return rows


def report(name):
    rows = collect(name)
    if not rows:
        print(name, "nothing run")
        return
    plant = [r for r in rows if r["planted"]]
    real = [r for r in rows if not r["planted"]]
    miss = sum(1 for r in rows if not r["ds"])
    print(f"{name}: {len(rows)} items, {miss} unanswered")
    for truth in ("yes", "no", "real_gap", "not_a_gap"):
        ps = [r for r in plant if r["planted"] == truth]
        if ps:
            right = {"yes": ("yes", "implied"), "no": ("no",), "real_gap": ("real_gap",),
                     "not_a_gap": ("not_a_gap",)}[truth]
            ok = [r for r in ps if r["ds"] and r["ds"].get("verdict") in right]
            print(f"  planted {truth}: right {len(ok)} of {len(ps)}")
    print("  verdicts on real:", dict(collections.Counter((r["ds"] or {}).get("verdict") for r in real)))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        build(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "run":
        run(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else None)
    elif cmd == "reparse":
        reparse(sys.argv[2])
    elif cmd == "report":
        for nm in (sys.argv[2:] or ["doer", "flag", "err", "errrest", "gap"]):
            report(nm)
