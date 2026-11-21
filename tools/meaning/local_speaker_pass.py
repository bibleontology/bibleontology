"""THE SPEAKER PASS: who speaks the quoted words that begin here? (Mac mini, gemma4:26b; Doug, 2026-11-15: "yes,
design the speaker pass for the Mac".)

WHY. The MCP names a verse's speaker only where the graph's relations or MACULA's own annotation say who speaks it.
Measured 2026-11-15, of the verses inside quotation marks: Job 81%, but John 41%, Mark 37%, Luke 26%, Matthew 23%,
Acts 23%. The rest are speeches introduced by "he", "I" or the Greek article ("He began to teach them, saying"), which
the annotation names in place of the person. Matthew 5:44, "love your enemies", names no one. This pass proposes who.

THE UNIT IS A RUN, so one answer never spans a change of speaker:
  - it starts at a verse that introduces speech without naming a resolvable speaker (MACULA marks a speaker there,
    but as a pronoun, an article or a common noun), or at the first quoted verse after narration;
  - it continues through the next verses that sit inside quotation marks (out/speech-depth.jsonl.gz) and have no
    speech introduction of their own;
  - it ends at the next verse that introduces a speaker, or at narration.
  Runs whose speaker the graph or the annotation already gives are not asked.

ONE QUESTION, ANSWERED FROM A CLOSED LIST. The model sees the four verses before the run and its first three verses
(the Berean text, public domain), and a list of candidates: the people the verse-names layer finds in those verses,
plus "God" where the verses name God or the LORD. It answers one candidate key, or "unclear", and the verse that shows
who speaks. It cannot name anyone outside the list, so a wrong answer is still a person the passage names.

PLANTED CHECKS (precision). About 15% of the calls are verses whose speaker the graph's own relations record (told /
asserted_by on the saying), asked the same way with the answer hidden; the key is in <job>.key.jsonl, never in the
job. Keys are opaque (s0000...).

AFTERWARD (`report`): plants scored first. Then each run's answer becomes a candidate in out/speaker-pass/, for Claude
to judge. Nothing reaches the MCP or the graph from the Mac's word alone, and an answer of God or Jesus that rests on
more than the verse beside goes to Doug's sheet (divine persons are his, record by record; a "He" resolved by the
verse beside counts as resolved, 2026-10-25).

    python tools/meaning/local_speaker_pass.py export-sample -> 36a-speaker-pass-sample: 300 runs and ~53 plants, the
                                                               bench (about 40 minutes); report-sample reads it
    python tools/meaning/local_speaker_pass.py export   -> out/grunt/jobs/36-speaker-pass.jsonl (+ .key.jsonl)
    python tools/meaning/local_speaker_pass.py count    -> the runs and verses it would ask, by book; writes nothing
    python tools/meaning/local_speaker_pass.py report   after `grunt.py pull`
"""
import collections
import gzip
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
JOBS = ROOT / "out" / "grunt" / "jobs"
DONE = ROOT / "out" / "grunt" / "done"
NAME = "36-speaker-pass"
OPTIONS = {"temperature": 0, "num_ctx": 6144}
SEED = 36
BEFORE, FIRST = 4, 3
PLANT_SHARE = 0.15
SPEAKER_TYPES = ("person", "being", "creature", "group", "people")
DIVINE_WORDS = re.compile(r"\b(LORD|God|Lord GOD)\b")
FIRST_PERSON = {"ἐγώ", "ἡμεῖς", "אֲנִי", "אָנֹכִי", "אֲנַחְנוּ", "נַחְנוּ"}
# the brief's worked examples; their runs are left out of the job
EXAMPLES = {"Job.4.2", "Mark.4.3", "Gen.18.9"}

SYSTEM = """You read the Bible closely to say who is speaking. You get a few verses of narrative, then the first \
verses of some quoted words, and a list of candidates. Say which candidate speaks the quoted words that begin at the \
verse marked "start".

How to judge:
- A verse marked "earlier_in_this_speech" comes from further back in the same unbroken quotation; the verses \
between it and the others are left out.
- A verse before may carry "speaker_recorded": who speaks in that verse, as already recorded. Quoted words that \
go on from it are usually the same speaker's, unless a new speaker is introduced in between.
- Read the verses before the start: the speaker is usually named there ("Then Eliphaz the Temanite replied") or \
just before ("When Jesus saw the crowds ... He began to teach them, saying").
- "He", "she", "they" and "I" are not answers: find who the pronoun refers to in the verses shown.
- Answer only with a key from "candidates". If the verses do not make clear who speaks, or the speaker is not in the \
list, answer "unclear". A wrong name is worse than "unclear".
- "shown_by" is the one verse that most clearly shows who speaks, such as the verse that names him before "said".
- If the words at the start are not speech at all (narration, a letter's own words, a list), answer "unclear".

Answer JSON only: {"speaker": "<key or unclear>", "shown_by": "<ref>"}

Example 1. Verses before: Job 4:1 "Then Eliphaz the Temanite replied:". Start: Job 4:2 "If one ventures a word with \
you, will you be impatient? ..." Candidates: {"eliphaz_the_temanite": "Eliphaz", "job": "Job"}.
Answer: {"speaker": "eliphaz_the_temanite", "shown_by": "Job 4:1"}

Example 2. Verses before: Mark 4:1 "Once again Jesus began to teach beside the sea ...", Mark 4:2 "He taught them \
many things in parables, and in His teaching He said:". Start: Mark 4:3 "Listen! A farmer went out to sow his seed." \
Candidates: {"jesus": "Jesus"}.
Answer: {"speaker": "jesus", "shown_by": "Mark 4:1"}

Example 3. Verses before: Gen 18:8, the visitors eat while Abraham stands by. Start: Gen 18:9 "Where is your wife \
Sarah?" they asked. Candidates: {"abraham": "Abraham", "sarah": "Sarah", "GOD": "God (the LORD)"}.
Answer: {"speaker": "unclear", "shown_by": "Gen 18:9"}
(The visitors speak, and they are not in the list; Abraham and Sarah are spoken to.)"""


def _load():
    import server as S
    S.load()
    d = S.mcp_backend().d
    return S, d


def _depths():
    dep = {}
    with gzip.open(ROOT / "out" / "speech-depth.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("ref"):
                try:
                    dep[r["ref"]] = int(r.get("depth") or 0)
                except ValueError:
                    pass
    return dep


def _relation_speakers(S, d):
    """{(book, chapter, verse): {speaker id}} from the sayings' own told / asserted_by / claimed_by relations."""
    out = collections.defaultdict(set)
    for tid, e in d["ents"].items():
        if e.get("type") != "text":
            continue
        for r in d["rels"].get(tid, []):
            if (r["type"] == "told" and r["dir"] == "in") or \
                    (r["type"] in ("asserted_by", "claimed_by") and r["dir"] == "out"):
                if (d["ents"].get(r["other"]) or {}).get("type") not in SPEAKER_TYPES:
                    continue
                for ref in r.get("refs") or []:
                    s = S._site_span(d, ref)
                    if s and (s[1], s[2]) == (s[3], s[4]):
                        out[(s[0], s[1], s[2])].add(r["other"])
    return out


def _label(k):
    return "%s %d:%d" % k


def _runs(S, d):
    """[(run verses [keys], intro key or None)] and the planted verses [(key, speaker id)], in canon order."""
    dep, rel_sp = _depths(), _relation_speakers(S, d)
    layers = d.get("layers") or {}
    by_book = collections.defaultdict(list)
    for k in d["verses"]:
        by_book[k[0]].append(k)
    runs, plants = [], []
    for b, keys in by_book.items():
        keys.sort(key=lambda k: (k[1], k[2]))
        cur, intro = [], None
        for k in keys:
            mref = S._vc_mref(d, *k)
            quoted = dep.get(mref, 0) >= 1
            stated = [r for r in (layers.get(mref) or {}).get("speaks") or [] if r.get("by") == "stated"]
            # "I tell you" inside a speech is the same speaker going on (the first export broke the Sermon on the
            # Mount into 24 runs at every one): a first-person speaker inside quotation marks is no new introduction
            if quoted and stated and all(r.get("who") in FIRST_PERSON for r in stated):
                stated = []
            known = bool(rel_sp.get(k))
            if known and quoted and len(rel_sp[k]) == 1:
                plants.append((k, next(iter(rel_sp[k]))))
            starts = bool(stated) and not known
            if cur and (not quoted or known or stated):
                runs.append((cur, intro))
                cur, intro = [], None
            if known:
                continue
            if starts:
                cur, intro = [k], k
            elif quoted:
                if not cur:
                    intro = None
                cur.append(k)
        if cur:
            runs.append((cur, intro))
    # a run that is only its introduction, with no quoted verse in it, asks nothing
    runs = [(vs, i) for vs, i in runs if any(dep.get(S._vc_mref(d, *k), 0) >= 1 for k in vs)]
    return runs, plants


_REL = None
_DEP = None
LOOKBACK = 60


def _depths_cached():
    global _DEP
    if _DEP is None:
        _DEP = _depths()
    return _DEP


DIVINE_KEY = {"YHWH", "Adonai", "Elohim", "Theos", "El"}


def _known(S, d, k):
    """(candidate key, name) of the one speaker recorded for verse k, or None: the graph's relation first, then
    MACULA's stated speaker where it is a name the verse-names layer resolves, or a divine name (key GOD)."""
    global _REL
    if _REL is None:
        _REL = _relation_speakers(S, d)
    rs = _REL.get(k) or set()
    if len(rs) == 1:
        sid = next(iter(rs))
        return sid, (d["ents"].get(sid) or {}).get("name") or sid
    if rs:
        return None
    rows = [r for r in ((d.get("layers") or {}).get(S._vc_mref(d, *k)) or {}).get("speaks") or []
            if r.get("by") == "stated"]
    if len({r.get("who") for r in rows}) != 1:
        return None
    if rows[0].get("divine") in DIVINE_KEY:
        return "GOD", "God (the LORD)"
    names = [n for n in S._vc_names(d, *k) if n["type"] in SPEAKER_TYPES]
    return (names[0]["id"], names[0]["name"]) if len(names) == 1 else None


def _call(S, d, start, key):
    """One call's user message: the verses before, the first verses from the start, the candidates."""
    b, c, v = start
    order = sorted((k for k in d["verses"] if k[0] == b), key=lambda k: (k[1], k[2]))
    i = order.index(start)
    before, first = order[max(0, i - BEFORE):i], order[i:i + FIRST]
    cands, divine = collections.OrderedDict(), False
    shown = []
    # EARLIER IN THE SAME SPEECH (the Sermon on the Mount: Matt 5:26-44 had no candidate, Jesus last named at 5:1):
    # back through the unbroken quoted verses, up to LOOKBACK, to the last one whose speaker is recorded
    j, dep = i - len(before) - 1, _depths_cached()
    while j >= 0 and i - j <= LOOKBACK and dep.get(S._vc_mref(d, *order[j]), 0) >= 1:
        sp = _known(S, d, order[j])
        if sp:
            shown.append({"ref": _label(order[j]), "text": d["verses"][order[j]], "speaker_recorded": sp[1],
                          "earlier_in_this_speech": True})
            cands.setdefault(sp[0], sp[1])
            break
        j -= 1
    for k in before:
        # A VERSE BEFORE SAYS WHO SPEAKS IT where that is recorded (Matt 5:2 names Jesus; the first export never told
        # the model so): the graph's relation, or the original language's own stated name
        row = {"ref": _label(k), "text": d["verses"][k]}
        sp = _known(S, d, k)
        if sp:
            row["speaker_recorded"] = sp[1]
            cands.setdefault(sp[0], sp[1])
        shown.append(row)
    for k in before + first:
        for n in S._vc_names(d, *k):
            if n["type"] in SPEAKER_TYPES:
                cands.setdefault(n["id"], n["name"])
        divine = divine or bool(DIVINE_WORDS.search(d["verses"][k]))
    if divine:
        cands["GOD"] = "God (the LORD)"
    if not cands:
        return None
    msg = {"verses_before": shown,
           "start": _label(start),
           "quoted_from_start": [{"ref": _label(k), "text": d["verses"][k]} for k in first],
           "candidates": dict(cands)}
    return {"key": key, "messages": [{"role": "system", "content": SYSTEM},
                                     {"role": "user", "content": json.dumps(msg, ensure_ascii=False)}]}


def count():
    S, d = _load()
    runs, plants = _runs(S, d)
    by = collections.Counter()
    vs = collections.Counter()
    for r, _ in runs:
        by[r[0][0]] += 1
        vs[r[0][0]] += len(r)
    print("%d runs, %d verses; %d verses available as plants" % (len(runs), sum(vs.values()), len(plants)))
    for b in ("Gen", "Exod", "Job", "Isa", "Jer", "Matt", "Mark", "Luke", "John", "Acts"):
        print("  %-5s runs %4d  verses %5d" % (b, by[b], vs[b]))
    longest = sorted(runs, key=lambda r: -len(r[0]))[:5]
    print("longest:", [(_label(r[0][0]), _label(r[0][-1]), len(r[0])) for r in longest])


def export(sample=0):
    """The whole pass, or (sample > 0) a bench of that many runs first: precision is read before 12 hours are spent."""
    global NAME
    S, d = _load()
    runs, plants = _runs(S, d)
    runs = [(vs, i) for vs, i in runs if "%s.%d.%d" % vs[0] not in EXAMPLES]
    rng = random.Random(SEED)
    if sample:
        NAME = NAME.replace("36-", "36a-") + "-sample"
        runs = rng.sample(runs, min(sample, len(runs)))
        # the Sermon on the Mount's run always goes in: the case that started this
        runs += [r for r in _runs(S, d)[0] if any("%s.%d.%d" % k == "Matt.5.44" for k in r[0]) and r not in runs]
    n_plants = int(len(runs) * PLANT_SHARE / (1 - PLANT_SHARE))
    plants = rng.sample(plants, min(n_plants, len(plants)))
    items = [("run", vs, i) for vs, i in runs] + [("plant", [k], sp) for k, sp in plants]
    rng.shuffle(items)
    JOBS.mkdir(parents=True, exist_ok=True)
    job, key = JOBS / (NAME + ".jsonl"), JOBS / (NAME + ".key.jsonl")
    n = 0
    with job.open("w", encoding="utf-8", newline="\n") as fj, key.open("w", encoding="utf-8", newline="\n") as fk:
        fj.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "local_speaker_pass"}}) + "\n")
        for kind, vs, extra in items:
            k = "s%04d" % n
            call = _call(S, d, vs[0], k)
            if call is None:
                continue
            fj.write(json.dumps(call, ensure_ascii=False) + "\n")
            fk.write(json.dumps({"key": k, "kind": kind, "verses": ["%s.%d.%d" % x for x in vs],
                                 "intro": ("%s.%d.%d" % extra) if kind == "run" and extra else None,
                                 "speaker": extra if kind == "plant" else None,
                                 "candidates": json.loads(call["messages"][1]["content"])["candidates"]},
                                ensure_ascii=False) + "\n")
            n += 1
    print("%d calls (%d planted) -> %s" % (n, sum(1 for x in items if x[0] == "plant"), job))


def _answer(content):
    m = re.search(r"\{.*\}", content or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except ValueError:
        return {}


def report(sample=False):
    global NAME
    if sample:
        NAME = NAME.replace("36-", "36a-") + "-sample"
    key = {r["key"]: r for r in map(json.loads, (JOBS / (NAME + ".key.jsonl")).open(encoding="utf-8"))}
    got = {r["key"]: _answer(r.get("content")) for r in map(json.loads, (DONE / (NAME + ".jsonl")).open(encoding="utf-8"))}
    plants = [k for k, r in key.items() if r["kind"] == "plant" and k in got]
    # the divine candidate is offered as GOD, and the graph's card is "god" (the bench of 2026-11-15 scored 3 right
    # answers wrong this way); a name given in place of its key ("God") is the same answer
    same = lambda a, b: bool(a) and (a.lower() == (b or "").lower() or  # noqa: E731
                                     (a.upper() == "GOD" and (b or "").lower() == "god"))
    for k in plants:
        if same(got[k].get("speaker") or "", key[k]["speaker"]):
            got[k]["speaker"] = key[k]["speaker"]
    right = sum(1 for k in plants if got[k].get("speaker") == key[k]["speaker"])
    unclear = sum(1 for k in plants if got[k].get("speaker") == "unclear")
    wrong = len(plants) - right - unclear
    print("plants: %d asked; right %d, unclear %d, wrong %d (precision on answered: %.0f%%)" % (
        len(plants), right, unclear, wrong, 100 * right / max(1, right + wrong)))
    out = ROOT / "out" / "speaker-pass"
    out.mkdir(parents=True, exist_ok=True)
    rows, by = [], collections.Counter()
    for k, r in key.items():
        if r["kind"] != "run" or k not in got:
            continue
        sp = got[k].get("speaker")
        by[sp if sp in ("unclear", "GOD") else ("named" if sp in r["candidates"] else "off-list")] += 1
        if sp and sp != "unclear" and sp in r["candidates"]:
            rows.append({"key": k, "verses": r["verses"], "intro": r["intro"], "speaker": sp,
                         "name": r["candidates"][sp], "shown_by": got[k].get("shown_by")})
    (out / "candidates.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows),
                                          encoding="utf-8")
    print("runs: %s; %d candidates covering %d verses -> %s" % (
        dict(by), len(rows), sum(len(x["verses"]) for x in rows), out / "candidates.jsonl"))
    if wrong:
        print("wrong plants:", [(key[k]["verses"][0], key[k]["speaker"], got[k].get("speaker"))
                                for k in plants if got[k].get("speaker") not in (key[k]["speaker"], "unclear")][:12])


if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["count"])[0]
    if cmd == "export-sample":
        export(300)
    elif cmd == "report-sample":
        report(True)
    else:
        {"export": export, "count": count, "report": report}[cmd]()
