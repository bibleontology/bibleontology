"""THE VERSE RE-READ: the Mac's confirmed findings, each read again against its own verse (2026-11-01).

Doug, 2026-11-01: "Have it take a pass reading against the verse and then have DeepSeek take a pass." The Mac's audit
(jobs 3 to 7) flagged; DeepSeek judged each flag twice (tools/meaning/deepseek_judge.py, 2026-10-31). What both runs
confirmed still has to be read against the verse before anything reaches a card: the judge confirmed "Boaz covered
Ruth with his garment" (Ruth 3:9), where Ruth ASKS him to. This pass puts one claim and its verse in front of the
model and asks one question: does the verse say this, or something close but different?

    python tools/meaning/verse_reread.py build     -> out/grunt/jobs/9-verse-reread.jsonl (+ .key.jsonl)
    python tools/grunt/grunt.py out/grunt/jobs/9-verse-reread.jsonl
    python tools/grunt/grunt.py pull
    python tools/meaning/verse_reread.py report    the Mac's verdicts, its score on the planted claims

WHAT IS CONFIRMED (both DeepSeek runs agree, planted items left out):
  gap     real_gap   a statement the card lacks, with the verse that says it
  doer    yes        who did the action in a clause whose doer the graph had left blank
  err     no         a relation the judge says its own verse does not support (expected: not_said)
  flag    no         a shown statement the judge says its verse does not support (expected: not_said)
Divine persons were never in these batches (the judge's build left them out); nothing here touches their records.

PLANTED CLAIMS (accuracy, about one in six): a TRUE claim (a gap or doer claim paired with its own verse, read as
stated by both runs of the judge; not checked by hand, so a few may truly be "partly", like 2 Sam 23:17's "he refused
to drink it", and the score on them is a lower bound), and two kinds of FALSE claim: another item's claim
under this item's verse (not_said), and a doer claim with doer and receiver swapped ("David intends to kill Saul";
partly or not_said). The key holds which is which; the job does not.
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "out" / "grunt" / "deepseek-judge"
JOBS, DONE = ROOT / "out" / "grunt" / "jobs", ROOT / "out" / "grunt" / "done"
NAME = "9-verse-reread"
OPTIONS = {"temperature": 0, "num_ctx": 4096}
SEED = 20261101
CONFIRM = {"gap": "real_gap", "doer": "yes", "err": "no", "flag": "no"}

BRIEF = """You read Bible verses (the Berean Standard Bible) and say whether they state a claim.

You get a CLAIM and the VERSE (sometimes with the verses just before it, for context). Answer with ONE line of JSON:
{"verdict": "...", "words": "...", "fix": "..."}

verdict:
- "stated": the verse says the claim, in these or other words.
- "implied": the claim follows plainly from the verse without adding anything the verse does not give.
- "partly": the verse says something close, but a detail differs: who did it, to whom, or whether it happened at all
  (asked, intended, promised or threatened is not done).
- "not_said": the verse does not say it.
words: the deciding words, copied exactly from the verse.
fix: only when "partly": the claim corrected to what the verse says, in the verse's own words. Otherwise "".

Judge from the verse shown, not from what you remember of the story.

Examples:
CLAIM: Cain killed his brother Abel. VERSE (Gen 4:8): "...And while they were in the field, Cain rose up against his
brother Abel and killed him."
{"verdict": "stated", "words": "Cain rose up against his brother Abel and killed him", "fix": ""}

CLAIM: Abraham sacrificed Isaac. VERSE (Gen 22:10): "Then Abraham reached out his hand and took the knife to slaughter
his son."
{"verdict": "partly", "words": "took the knife to slaughter his son", "fix": "Abraham took the knife to slaughter his son"}

CLAIM: Jacob deceived Laban. VERSE (Rom 4:21): "being fully persuaded that God was able to do what He had promised."
{"verdict": "not_said", "words": "", "fix": ""}"""


def confirmed():
    """the real items both judge runs agree on, as {id, type, claim, ref, verse, context, expect}"""
    out = []
    for t, files in (("gap", ["gap"]), ("doer", ["doer"]), ("err", ["err", "errrest"]), ("flag", ["flag"])):
        items = {}
        for f in files:
            for line in open(WORK / f"batches-{f}.jsonl", encoding="utf-8"):
                b = json.loads(line)
                for it in b["items"]:
                    if it.get("planted") is None:
                        items[(b["batch"], it["id"])] = it
        verdict = {}
        for run in ("results", "results2"):
            for p in (WORK / run).glob("*.json"):
                r = json.loads(p.read_text(encoding="utf-8"))
                for i, v in (r.get("got") or {}).items():
                    verdict.setdefault((r["batch"], i), []).append(v.get("verdict"))
        for k, it in items.items():
            vs = verdict.get(k, [])
            if len(vs) == 2 and vs[0] == vs[1] == CONFIRM[t]:
                out.append(as_claim(t, it, f"{k[0]}:{k[1]}"))
    return [c for c in out if c]


def as_claim(t, it, key):
    if t == "gap":
        return {"key": key, "type": t, "claim": f"About {it['name']}: {it['what']}", "ref": it["ref"],
                "verse": it.get("verse") or "", "context": [], "expect": "stated", "card": it["card"]}
    if t == "doer":
        return {"key": key, "type": t, "claim": f"{it['cand']} is the one who did this: {it['action']} ({it['receiver']})",
                "ref": it["ref"], "verse": it["text"], "context": it.get("before") or [], "expect": "stated",
                "card": it["rec"], "doer": it["cand"], "receiver": it["receiver"], "action": it["action"],
                "clause": it["clause"]}
    if t == "err":
        vs = it.get("verses") or []
        return {"key": key, "type": t, "claim": it["text"].replace(" — ", " "), "ref": ", ".join(v["ref"] for v in vs),
                "verse": " ".join(v["text"] for v in vs), "context": [], "expect": "not_said", "card": it["src"],
                "rel": [it["src"], it["rtype"], it["dst"]], "keyid": it.get("keyid")}
    if t == "flag":
        return {"key": key, "type": t, "claim": it["record"].replace("~", "").replace("->", "").replace("-", " "),
                "ref": it["ref"], "verse": it["text"], "context": it.get("before") or [], "expect": "not_said",
                "card": None, "clause": it["clause"]}


def plants(real, rnd):
    true_ = [c for c in real if c["type"] in ("gap", "doer")]
    rnd.shuffle(true_)
    n = max(6, len(real) // 18)
    out = []
    for i, c in enumerate(true_[:n]):                    # a true claim with its own verse
        out.append(dict(c, key=f"P-true-{i}", planted="stated"))
    for i, (a, b) in enumerate(zip(true_[n:2 * n], true_[2 * n:3 * n])):   # a claim under another item's verse
        out.append(dict(a, key=f"P-moved-{i}", claim=b["claim"], planted="not_said"))
    swaps = [c for c in true_[3 * n:] if c["type"] == "doer" and c["receiver"] and c["receiver"] != c["doer"]]
    for i, c in enumerate(swaps[:n]):                    # doer and receiver swapped
        out.append(dict(c, key=f"P-swap-{i}", claim=f"{c['receiver']} is the one who did this: {c['action']} ({c['doer']})",
                        planted="partly|not_said"))
    return out


def messages(c):
    ctx = "".join(f"(before) {x}\n" for x in c["context"][-2:])
    return [{"role": "system", "content": BRIEF},
            {"role": "user", "content": f"CLAIM: {c['claim']}\n{ctx}VERSE ({c['ref']}): \"{c['verse']}\""}]


def build():
    rnd = random.Random(SEED)
    real = confirmed()
    items = real + plants(real, rnd)
    rnd.shuffle(items)
    JOBS.mkdir(parents=True, exist_ok=True)
    with open(JOBS / f"{NAME}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "qwen3.8:27b", "options": OPTIONS, "pass": "verse_reread"}}) + "\n")
        for c in items:
            f.write(json.dumps({"key": c["key"], "messages": messages(c)}, ensure_ascii=False) + "\n")
    with open(JOBS / f"{NAME}.key.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for c in items:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    by = {}
    for c in real:
        by[c["type"]] = by.get(c["type"], 0) + 1
    print(f"{len(real)} confirmed findings {by}; {len(items) - len(real)} planted; {len(items)} calls -> {JOBS / NAME}.jsonl")


def parse(content):
    s = (content or "").strip()
    a, b = s.find("{"), s.rfind("}")
    try:
        return json.loads(s[a:b + 1]) if a >= 0 else None
    except ValueError:
        return None


def report():
    key = {json.loads(l)["key"]: json.loads(l) for l in open(JOBS / f"{NAME}.key.jsonl", encoding="utf-8")}
    rows = [json.loads(l) for l in open(DONE / f"{NAME}.jsonl", encoding="utf-8")]
    got = {r["key"]: parse(r.get("content")) for r in rows}
    caught = total = 0
    counts = {}
    for k, c in key.items():
        v = (got.get(k) or {}).get("verdict")
        if "planted" in c:
            total += 1
            ok = v in c["planted"].split("|") or (c["planted"] == "stated" and v == "implied")
            caught += ok
            if not ok:
                print(f"  missed plant {k}: expected {c['planted']}, said {v}")
        else:
            counts.setdefault(c["type"], {}).setdefault(v, 0)
            counts[c["type"]][v] += 1
    print(f"{len(rows)} answers of {len(key)}; planted right {caught} of {total}")
    for t, cs in counts.items():
        print(f"  {t}: {cs}")


# ---- DeepSeek's pass on the same claims -------------------------------------------------------------------------
# Blind to the Mac's verdict, so the two readings are independent: each claim with its verse, the same question. Where
# the Mac answered "partly", its corrected claim is asked too, as an item of its own: does the verse state the fix?
# Runs twice (DSJ_RUN=2 for the second), as every judgment that matters does; only what both runs agree on counts.
# DeepSeek sees verse text, names and the claim only (the owner's rule); divine persons were never in these items.
#
#     python tools/meaning/verse_reread.py ds-build        -> out/grunt/deepseek-judge/batches-reread.jsonl
#     python tools/meaning/deepseek_judge.py run reread    (then DSJ_RUN=2 ... run reread)
#     python tools/meaning/verse_reread.py ds-report       the Mac against DeepSeek, item by item -> out/grunt/reread.jsonl

DS_BRIEF = BRIEF.replace("Answer with ONE line of JSON:\n{\"verdict\": \"...\", \"words\": \"...\", \"fix\": \"...\"}",
                         "Answer each item with ONE line of JSON:\n{\"id\": \"...\", \"verdict\": \"...\", \"words\": \"...\", "
                         "\"why\": \"...\"}") \
    .replace("fix: only when \"partly\": the claim corrected to what the verse says, in the verse's own words. Otherwise \"\".",
             "why: only when \"partly\": the claim corrected to what the verse says, in the verse's own words.") \
    .replace("{\"verdict\": \"stated\", \"words\": \"Cain rose up against his brother Abel and killed him\", \"fix\": \"\"}",
             "{\"id\": \"r1\", \"verdict\": \"stated\", \"words\": \"Cain rose up against his brother Abel and killed him\", \"why\": \"\"}") \
    .replace("{\"verdict\": \"partly\", \"words\": \"took the knife to slaughter his son\", \"fix\": \"Abraham took the knife to slaughter his son\"}",
             "{\"id\": \"r2\", \"verdict\": \"partly\", \"words\": \"took the knife to slaughter his son\", \"why\": \"Abraham took the knife to slaughter his son\"}") \
    .replace("{\"verdict\": \"not_said\", \"words\": \"\", \"fix\": \"\"}",
             "{\"id\": \"r3\", \"verdict\": \"not_said\", \"words\": \"\", \"why\": \"\"}")


# a .replace() that misses is silent: every one must have landed (the brief keeps no "fix" and has all three ids)
assert '"fix"' not in DS_BRIEF and "fix:" not in DS_BRIEF and all(f'"id": "r{i}"' in DS_BRIEF for i in (1, 2, 3)) \
    and '"id": "...", "verdict"' in DS_BRIEF, "DS_BRIEF: a replacement did not apply"


def ds_text(c):
    ctx = "".join(f"  (before) {x}\n" for x in c["context"][-2:])
    return f"[{c['id']}] CLAIM: {c['claim']}\n{ctx}  VERSE ({c['ref']}): \"{c['verse']}\""


def ds_build():
    sys.path.insert(0, str(ROOT / "tools" / "meaning"))
    import deepseek_judge as dj
    key = [json.loads(l) for l in open(JOBS / f"{NAME}.key.jsonl", encoding="utf-8")]
    rows = {json.loads(l)["key"]: parse(json.loads(l).get("content")) for l in open(DONE / f"{NAME}.jsonl", encoding="utf-8")}
    items = []
    for c in key:
        items.append(dict(c, ask="claim"))
        mac = rows.get(c["key"]) or {}
        if mac.get("verdict") == "partly" and (mac.get("fix") or "").strip() and "planted" not in c:
            items.append(dict(c, ask="fix", claim=mac["fix"].strip()))
    rnd = random.Random(SEED + 1)
    rnd.shuffle(items)
    batches = []
    for bi in range(0, len(items), dj.BATCH):
        part = items[bi:bi + dj.BATCH]
        for n, it in enumerate(part, 1):
            it["id"] = f"r{n}"
        batches.append({"batch": f"R-{bi // dj.BATCH + 1:02d}", "items": part,
                        "task": DS_BRIEF + "\n\nITEMS (" + str(len(part)) + "):\n\n" + "\n\n".join(ds_text(x) for x in part) + "\n"})
    dj.write_batches("reread", batches)
    print(f"{len(items)} items ({sum(1 for x in items if x['ask'] == 'fix')} of them the Mac's corrections) in {len(batches)} batches")


def ds_report():
    rows = {json.loads(l)["key"]: parse(json.loads(l).get("content")) for l in open(DONE / f"{NAME}.jsonl", encoding="utf-8")}
    runs = []
    for run in ("results", "results2"):
        got = {}
        for p in (WORK / run).glob("R-*.json"):
            r = json.loads(p.read_text(encoding="utf-8"))
            got[r["batch"]] = r["got"]
        runs.append(got)
    out, plant_ok, plant_n, tally = [], 0, 0, {}
    for line in open(WORK / "batches-reread.jsonl", encoding="utf-8"):
        b = json.loads(line)
        for it in b["items"]:
            ds = [(g.get(b["batch"]) or {}).get(it["id"]) or {} for g in runs]
            v = [x.get("verdict") for x in ds]
            mac = rows.get(it["key"]) or {}
            settled = v[0] if len(v) == 2 and v[0] == v[1] else None
            if "planted" in it and it["ask"] == "claim":
                plant_n += 1
                plant_ok += settled in it["planted"].split("|") or (it["planted"] == "stated" and settled == "implied")
                continue
            row = {**{k: it[k] for k in ("key", "type", "ask", "claim", "ref", "verse", "expect") if k in it},
                   "mac": mac.get("verdict"), "mac_fix": mac.get("fix"), "ds": settled, "ds_runs": v,
                   "ds_words": (ds[0] or {}).get("words"), "ds_fix": (ds[0] or {}).get("why")}
            row["agree"] = settled is not None and (row["mac"] == settled or {row["mac"], settled} <= {"stated", "implied"})
            out.append(row)
            t = (it["type"], it["ask"], "agree" if row["agree"] else "differ")
            tally[t] = tally.get(t, 0) + 1
    with open(ROOT / "out" / "grunt" / "reread.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"DeepSeek on the planted claims (settled, both runs): {plant_ok} of {plant_n}")
    for k in sorted(tally):
        print(f"  {k}: {tally[k]}")




# THE OBJECT AUDIT, RE-READ ON THE MAC (2026-11-02): every candidate DeepSeek gave in docs/review/object-audit-2026-11-01/
# (a use, or a sign or wonder) as one claim beside its verse, the same question as above. A second reader before
# Claude's check; the Mac's own blind spot (who did what) is why the uses keep their "who" in the claim.
#     python tools/meaning/verse_reread.py objects   -> out/grunt/jobs/11-object-reread.jsonl, then grunt.py push
def objects():
    import re
    verses, books = {}, {}
    for l in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if "t" in r:
            verses[(r["b"], r["c"], r["v"])] = r["t"]
            books.setdefault(r["b"].lower().replace(" ", ""), r["b"])
    alias = {"genesis": "Gen", "exodus": "Exod", "leviticus": "Lev", "numbers": "Num", "deuteronomy": "Deut",
             "joshua": "Josh", "judges": "Judg", "1samuel": "1Sam", "2samuel": "2Sam", "1kings": "1Kgs", "2kings": "2Kgs",
             "matthew": "Matt", "revelation": "Rev", "hebrews": "Heb", "john": "John"}

    def find(ref):
        m = re.match(r"\s*(\d?\s?[A-Za-z]+)\.?\s+(\d+):(\d+)", ref or "")
        if not m:
            return None, None
        b = m.group(1).replace(" ", "")
        b = books.get(b.lower()) or alias.get(b.lower()) or b
        k = (b, int(m.group(2)), int(m.group(3)))
        return (f"{b} {k[1]}:{k[2]}", verses[k]) if k in verses else (None, None)
    items = []
    for f in sorted((ROOT / "docs" / "review" / "object-audit-2026-11-01").glob("*.md")):
        obj = f.stem.replace("-signs", "")
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip().strip(",")
            if not line.startswith("{"):
                continue
            try:
                j = json.loads(line)
            except ValueError:
                continue
            ref, text = find(j.get("ref"))
            if not text:
                continue
            if f.stem.endswith("-signs"):
                claim = f"{obj.replace('_', ' ')}: {j.get('means') or ''}"
            else:
                claim = " ".join(x for x in (j.get("who"), j.get("act"), j.get("which"), ("on " + j["on"]) if j.get("on") else "") if x)
            items.append({"key": f"{f.stem}:{len(items)}", "claim": claim, "ref": ref, "verse": text, "context": []})
    with open(JOBS / "11-object-reread.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"_job": {"model": "qwen3.8:27b", "options": OPTIONS, "pass": "object_reread"}}) + "\n")
        for c in items:
            fh.write(json.dumps({"key": c["key"], "messages": messages(c)}, ensure_ascii=False) + "\n")
    with open(JOBS / "11-object-reread.key.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for c in items:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{len(items)} candidates -> 11-object-reread.jsonl")



# THE STANDING SWEEP, FIRST STAGE (2026-11-02; P-2026-11-02-1, trust first): every concrete relation read against its
# own verse on the Mac, read-only. Doug: "make sure that the Mac will be productive all day". Order: the cards Bing's
# AI already cites (Webmaster Tools' grounding pages, 2026-11-02), then every other card, most-connected first.
# Structural kinds (a verse wired to an idea) are left out: they have no doer to misread. Nothing reaches the graph.
#     python tools/meaning/verse_reread.py relations  -> out/grunt/jobs/12a-sweep-cited.jsonl, 12b-sweep-rest.jsonl
CITED = """the_father jesus god holy_ghost theme_trinity the_full_armor_of_god accuser servant_of_abraham
the_name_of_the_lord event_heavenly_council_scenes anna sarah event_woman_with_issue_of_blood david judgment silas love
folly the_altar_of_incense pleasure anathoth event_joseph_interprets_dreams_in_prison rain""".split()
SKIP = {"speaks_of", "in_theme", "asserted_by", "part_of", "instance_of", "draws_on", "recounts", "spoken_in",
        "specializes", "same_steps_as", "states", "described_as", "likened_to", "signifies", "composed_of", "named_with",
        "occasion_of", "aspect_of", "titled", "spoken_of_as", "distinguished_from", "possibly_same_as", "member_of",
        "located_in", "conditional_on", "grounds", "token_of", "drawn_from", "answered_in", "assessed_as"}


KINDS2 = {"described_as", "likened_to", "signifies", "titled", "spoken_of_as", "assessed_as", "states",
          "member_of", "located_in", "token_of", "conditional_on", "grounds"}


def relations():
    import glob
    import re
    import collections
    import yaml
    verses = {}
    for l in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if "t" in r:
            verses[(r["b"], r["c"], r["v"])] = r["t"]
    ents = {}
    for p in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
        for l in open(p, encoding="utf-8"):
            if l.strip():
                e = json.loads(l)
                ents.setdefault(e["id"], e.get("name") or e["id"])
    labels = {k: v.get("label") or k for k, v in
              yaml.safe_load(open(ROOT / "ontology" / "schema" / "relationship_types.yaml", encoding="utf-8"))["types"].items()}
    rels, degree = [], collections.Counter()
    for p in sorted(glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl"))):
        for i, l in enumerate(open(p, encoding="utf-8")):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            # "kinds": the second stage, the claim kinds the first left out (descriptions, likenings, titles, signs)
            if ((r.get("type") not in KINDS2) if "kinds" in sys.argv[2:] else (r.get("type") in SKIP)) or not r.get("refs") or r.get("src") not in ents or r.get("dst") not in ents:
                continue
            rels.append((Path(p).stem, i, r))
            degree[r["src"]] += 1
            degree[r["dst"]] += 1

    def verse_of(ref):
        m = re.match(r"\s*(\S+)\s+(\d+):(\d+)", ref)
        return (f"{m.group(1)} {m.group(2)}:{m.group(3)}", verses.get((m.group(1), int(m.group(2)), int(m.group(3))))) if m else (None, None)
    cited, rest = [], []
    for f, i, r in rels:
        got = [verse_of(x) for x in r["refs"][:2]]
        got = [(a, t) for a, t in got if t]
        if not got:
            continue
        claim = f"{ents[r['src']]} {labels.get(r['type'], r['type'])} {ents[r['dst']]}"
        if r.get("claimed_by"):
            claim += f" (in the words of {ents.get(r['claimed_by'], r['claimed_by'])})"
        c = {"key": f"{f}:{i}", "claim": claim, "ref": ", ".join(a for a, _ in got), "verse": " ".join(t for _, t in got),
             "context": [], "rel": [r["src"], r["type"], r["dst"]], "file": f, "line": i}
        (cited if r["src"] in CITED or r["dst"] in CITED else rest).append((degree[r["src"]] + degree[r["dst"]], c))
    sfx = "-kinds" if "kinds" in sys.argv[2:] else ""
    for name, part in ((f"12a-sweep-cited{sfx}", cited), (f"12b-sweep-rest{sfx}", rest)):
        part.sort(key=lambda x: -x[0])
        with open(JOBS / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"_job": {"model": "qwen3.8:27b", "options": OPTIONS, "pass": "relation_sweep"}}) + "\n")
            for _, c in part:
                fh.write(json.dumps({"key": c["key"], "messages": messages(c)}, ensure_ascii=False) + "\n")
        with open(JOBS / f"{name}.key.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for _, c in part:
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")
        print(f"{name}: {len(part)} relations")


if __name__ == "__main__":
    {"build": build, "report": report, "ds-build": ds_build, "ds-report": ds_report, "objects": objects, "relations": relations}[sys.argv[1]]()
