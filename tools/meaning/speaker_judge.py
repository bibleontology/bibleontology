"""THE SPEAKER PASS, JUDGED (2026-11-16; the Mac's pass is tools/meaning/local_speaker_pass.py, job 36).

The Mac proposed a speaker for 3,910 runs of quoted words (out/speaker-pass/candidates.jsonl). Nothing reaches the
graph on its word alone, so a second reader answers the same question BLIND -- the same verses and candidates, never
the Mac's answer -- and a run is applied only where the two agree. The graph's own recorded speakers are planted among
the runs, keys opaque, to measure the judge.

NESTED SPEECH (Doug, 2026-11-16: "Both, inner first"): when the words are another's, relayed ("Thus says the LORD",
a messenger repeating the king, Jesus quoting Isaiah), the speaker is the inner voice -- whose words they are -- and
the one delivering them is recorded as `reported_by`. The MCP answers "God, through Jeremiah".

DIVINE PERSONS are Doug's, record by record. A run whose speaker is God or Jesus is applied only where the verse that
shows it is the run's first verse or the one beside it (2026-10-25: a "He" resolved by the verse beside counts as
resolved); the rest go to his sheet with both readings.

    python tools/meaning/speaker_judge.py batches [--size 60] [--plants 600]
        -> out/speaker-judge/in/bNNN.json (the judge's input) and out/speaker-judge/plan.json (which key is what)
    python tools/meaning/speaker_judge.py report
        -> reads out/speaker-judge/ans/bNNN.json; plants scored; agreement with the Mac; out/speaker-judge/result.json
    python tools/meaning/speaker_judge.py apply
        -> out/speaker-readings.jsonl.gz (one row per verse), out/speaker-judge/doug-sheet.md, and the trail under
           ontology/provenance/speaker-pass-2026-11-16.jsonl (shown and rejected alike)
"""
import collections
import gzip
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / "out" / "grunt" / "jobs" / "36-speaker-pass.jsonl"
KEY = ROOT / "out" / "grunt" / "jobs" / "36-speaker-pass.key.jsonl"
CANDS = ROOT / "out" / "speaker-pass" / "candidates.jsonl"
OUT = ROOT / "out" / "speaker-judge"
READINGS = ROOT / "out" / "speaker-readings.jsonl.gz"
TRAIL = ROOT / "ontology" / "provenance" / "speaker-pass-2026-11-16.jsonl"

# the book's own prophet, offered as the one who may be relaying the words (Ezekiel 15:1, "the word of the LORD came
# to me", names no one). Only cards that exist and are unambiguous; Obadiah, Zephaniah, Haggai and Zechariah have none
BOOK_PROPHET = {"Isa": ("isaiah", "Isaiah"), "Jer": ("jeremiah", "Jeremiah"), "Ezek": ("ezekiel", "Ezekiel"),
                "Dan": ("daniel_the_prophet", "Daniel"), "Hos": ("hosea", "Hosea"), "Joel": ("joel", "Joel"),
                "Amos": ("amos", "Amos"), "Jonah": ("jonah", "Jonah"), "Mic": ("micah", "Micah"),
                "Nah": ("nahum", "Nahum"), "Hab": ("habakkuk", "Habakkuk"), "Mal": ("malachi", "Malachi")}
DIVINE = {"GOD", "jesus"}


def _load_job():
    calls, keys = {}, {}
    for line in open(JOB, encoding="utf-8"):
        r = json.loads(line)
        if r.get("key"):
            calls[r["key"]] = json.loads(r["messages"][1]["content"])
    for line in open(KEY, encoding="utf-8"):
        r = json.loads(line)
        keys[r["key"]] = r
    return calls, keys


def _item(key, call):
    """What the judge sees: the verses and the candidates, nothing of either answer."""
    cands = dict(call["candidates"])
    book = call["start"].split()[0]
    if book in BOOK_PROPHET and BOOK_PROPHET[book][0] not in cands:
        cands[BOOK_PROPHET[book][0]] = BOOK_PROPHET[book][1]
    return {"key": key, "verses_before": call.get("verses_before") or [], "start": call["start"],
            "quoted_from_start": call.get("quoted_from_start") or [], "candidates": cands}


def batches(size=60, n_plants=600):
    calls, keys = _load_job()
    runs = [json.loads(l)["key"] for l in open(CANDS, encoding="utf-8")]
    plants = sorted(k for k, v in keys.items() if v["kind"] == "plant" and k in calls)
    random.seed(20261116)
    plants = random.sample(plants, min(n_plants, len(plants)))
    todo = runs + plants
    random.shuffle(todo)
    (OUT / "in").mkdir(parents=True, exist_ok=True)
    (OUT / "ans").mkdir(parents=True, exist_ok=True)
    plan = {"runs": runs, "plants": plants, "batches": []}
    for i in range(0, len(todo), size):
        name = "b%03d" % (i // size)
        items = [_item(k, calls[k]) for k in todo[i:i + size]]
        (OUT / "in" / f"{name}.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        plan["batches"].append(name)
    (OUT / "plan.json").write_text(json.dumps(plan, indent=0), encoding="utf-8")
    print(f"{len(runs)} runs + {len(plants)} plants in {len(plan['batches'])} batches of {size} -> {OUT / 'in'}")


def _answers():
    got = {}
    for f in sorted((OUT / "ans").glob("b*.json")):
        try:
            for a in json.loads(f.read_text(encoding="utf-8")):
                if isinstance(a, dict) and a.get("key"):
                    got[a["key"]] = a
        except json.JSONDecodeError as e:
            print("unreadable:", f.name, e)
    return got


def _ref_key(ref):
    m = re.match(r"(\S+) (\d+):(\d+)", ref or "")
    return (m.group(1), int(m.group(2)), int(m.group(3))) if m else None


def _near(run_first, shown):
    """The verse that shows the speaker is the run's first verse or the one before or after it."""
    b, c, v = run_first.split(".")
    s = _ref_key(shown)
    return bool(s) and s[1] == int(c) and abs(s[2] - int(v)) <= 1


def report():
    calls, keys = _load_job()
    plan = json.loads((OUT / "plan.json").read_text(encoding="utf-8"))
    mac = {json.loads(l)["key"]: json.loads(l) for l in open(CANDS, encoding="utf-8")}
    got = _answers()
    # plants: the graph's own speaker, hidden from the judge
    p = collections.Counter()
    for k in plan["plants"]:
        a = got.get(k)
        if not a:
            p["unanswered"] += 1
            continue
        sp = a.get("speaker") or "unclear"
        truth = keys[k].get("speaker")
        cands = calls[k]["candidates"]
        # the same person under two keys is no error of the judge's (found in the first five batches: "elihu" for
        # elihu_son_of_barachel, both named Elihu; "GOD", the candidates' key, for the graph's god)
        same = sp == truth or (sp == "GOD" and truth == "god") or \
            (sp in cands and cands.get(sp) == cands.get(truth))
        p["unclear" if sp == "unclear" else ("right" if same else "wrong")] += 1
    ans = p["right"] + p["wrong"]
    print(f"plants: {dict(p)}; precision on answered {p['right'] / ans:.1%}" if ans else f"plants: {dict(p)}")
    # runs: agreement with the Mac
    out = collections.Counter()
    rows = []
    for k in plan["runs"]:
        a, m = got.get(k), dict(mac[k])
        if not a:
            out["unanswered"] += 1
            continue
        # one key for God: some candidate lists hold both the graph's "god" and the pass's "GOD" (Gen 9:17)
        a = dict(a, speaker="GOD" if a.get("speaker") == "god" else a.get("speaker"),
                 reported_by="GOD" if a.get("reported_by") == "god" else a.get("reported_by"))
        m["speaker"] = "GOD" if m["speaker"] == "god" else m["speaker"]
        sp = a.get("speaker") or "unclear"
        if sp == "unclear":
            verdict = "judge unclear"
        elif sp != m["speaker"] and a.get("reported_by") != m["speaker"]:
            verdict = "disagree"
        # THE NESTED CASE AGREES TOO (the bench, b000): the Mac named who speaks in the scene (Moses, Lev 10:3;
        # Jeremiah, Jer 21:3) and the judge, by Doug's ruling, the inner voice with that same person relaying it
        elif sp != m["speaker"] and sp in DIVINE and not _near(m["verses"][0], a.get("shown_by")):
            verdict = "agree, divine beyond the verse beside: Doug's sheet"
        elif sp in DIVINE and not (_near(m["verses"][0], m.get("shown_by")) or _near(m["verses"][0], a.get("shown_by"))):
            verdict = "agree, divine beyond the verse beside: Doug's sheet"
        else:
            verdict = "agree"
        out[verdict] += 1
        rows.append({"key": k, "verses": m["verses"], "mac": m["speaker"], "mac_name": m["name"],
                     "mac_shown_by": m.get("shown_by"), "judge": sp, "reported_by": a.get("reported_by"),
                     "judge_shown_by": a.get("shown_by"), "why": a.get("why"),
                     "candidates": _item(k, calls[k])["candidates"], "verdict": verdict})
    print("runs:", dict(out))
    print("verses applied if agreed:", sum(len(r["verses"]) for r in rows if r["verdict"] == "agree"))
    (OUT / "result.json").write_text(json.dumps({"plants": dict(p), "runs": dict(out), "rows": rows},
                                                ensure_ascii=False, indent=0), encoding="utf-8")


def apply():
    res = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "app2"))
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        import server as S
        S.load()
        d = S.mcp_backend().d                     # as tools/meaning/local_speaker_pass.py loads it

    def mref(site_ref):
        # the layers are keyed by MACULA's reference; the runs carry the Berean's (site) verse keys
        b, c, v = site_ref.split(".")
        return S._vc_mref(d, b, int(c), int(v))
    lines, trail, sheet = [], [], []
    for r in res["rows"]:
        cands = r["candidates"]
        rep = r.get("reported_by")
        rep = rep if rep in cands and rep != r["judge"] else None
        # Doug reviewed the whole divine sheet, 2026-11-16: "I looked through the divine sheet and it looks right"
        approved = r["verdict"].startswith("agree, divine") and "--sheet-approved" in sys.argv
        trail.append(dict(r, applied=r["verdict"] == "agree" or approved,
                          approved_by="Doug, the whole divine sheet, 2026-11-16" if approved else None,
                          source="speaker pass 2026-11-16: the Mac (gemma4:26b) and a blind Claude judge agreeing"))
        if r["verdict"] == "agree" or approved:
            for ref in r["verses"]:
                lines.append({"ref": mref(ref), "site_ref": ref, "speaker": None if r["judge"] == "GOD" else r["judge"],
                              "name": cands.get(r["judge"]), "divine": "GOD" if r["judge"] == "GOD" else None,
                              "reported_by": rep, "reported_by_name": cands.get(rep) if rep else None,
                              "by": "reading", "shown_by": r.get("mac_shown_by") or r.get("judge_shown_by"),
                              "run": r["key"]})
        elif r["verdict"].startswith("agree, divine"):
            sheet.append(r)
    with gzip.open(READINGS, "wt", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_source": "The speaker pass, 2026-11-16: runs of quoted words whose speaker the graph "
                            "did not record, proposed by the Mac (gemma4:26b) and judged blind by Claude; a row only "
                            "where both named the same speaker. A reading, not a stated relation. Nested speech: "
                            "the inner voice is the speaker, the one relaying it `reported_by` (Doug, 2026-11-16)."})
                + "\n")
        for x in lines:
            f.write(json.dumps({k: v for k, v in x.items() if v is not None}, ensure_ascii=False) + "\n")
    TRAIL.parent.mkdir(parents=True, exist_ok=True)
    TRAIL.write_text("".join(json.dumps(t, ensure_ascii=False) + "\n" for t in trail), encoding="utf-8",
                     newline="\n")
    md = ["# The speaker pass: divine speakers beyond the verse beside (Doug's sheet)", "",
          "Both readers, the Mac and a blind Claude judge, named the same divine speaker, but the verse that shows "
          "it is not the run's first verse or the one beside it. Divine persons are yours, record by record. "
          "Mark each line **yes** (apply), **no**, or **held**.", ""]
    for r in sheet:
        md.append(f"- [ ] `{r['key']}` **{', '.join(r['verses'][:1])}{'–' + r['verses'][-1] if len(r['verses']) > 1 else ''}**"
                  f" → {r['mac_name']}{' (reported by ' + r['candidates'].get(r['reported_by'], '') + ')' if r.get('reported_by') in r['candidates'] else ''}."
                  f" Shown by {r.get('mac_shown_by')} / {r.get('judge_shown_by')}. {r.get('why') or ''}")
    (OUT / "doug-sheet.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{len(lines)} verse rows -> {READINGS}; {len(trail)} runs in the trail; {len(sheet)} on Doug's sheet")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "batches":
        a = sys.argv[2:]
        size = int(a[a.index("--size") + 1]) if "--size" in a else 60
        n = int(a[a.index("--plants") + 1]) if "--plants" in a else 600
        batches(size, n)
    elif cmd == "report":
        report()
    elif cmd == "apply":
        apply()
    else:
        print(__doc__)
