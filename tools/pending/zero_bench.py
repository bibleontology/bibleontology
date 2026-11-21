"""The Mac bench for P-2026-11-19-2, on the settled zero-relation answers of 2026-11-19 (Doug: "Yes, bench it").

    python -X utf8 tools/pending/zero_bench.py export      # one job per model -> out/grunt/jobs/
    python -X utf8 tools/pending/zero_bench.py score       # after grunt.py pull

The question is the one DeepSeek answered (zero_brief.py), one card a call, so a dense model's answer stays short
enough for the runner's 120 s watchdog. The key is Claude's final reading of DeepSeek's answers (zero_final.json):
the relations kept or corrected, card by card. Left out of the key: the itinerary camps Claude added by rule and the
14 releases, whose partner was never among the candidates. The key stays on this PC; the Mac sees only the questions.

A model's proposal runs the same mechanical check as DeepSeek's (zero_check.py's rules), then is matched to the key:
`exact` (same ends and type), `pair` (same two records, another type or direction), or `extra` (not in the key).
DeepSeek is scored the same way from its own answers, so the three sit side by side.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
S = Path(r"<local>")
JOBS, DONE = ROOT / "out" / "grunt" / "jobs", ROOT / "out" / "grunt" / "done"
MODELS = {"32-bench-zero-gemma26": "gemma4:26b", "33-bench-zero-gemma31": "gemma4:31b-it-qat"}
OPTIONS = {"gemma4:26b": {"temperature": 0, "num_ctx": 8192, "num_predict": 700},
           "gemma4:31b-it-qat": {"temperature": 0, "num_ctx": 8192, "num_predict": 450}}

types = yaml.safe_load(open(ROOT / "ontology/schema/relationship_types.yaml", encoding="utf-8"))["types"]
defs = json.load(open(ROOT / "ontology/schema/relation_definitions.json", encoding="utf-8"))["types"]
cards = json.load(open(S / "zero_cand.json", encoding="utf-8"))
SKIP = {"speaks_of", "in_theme", "instance_of", "spoken_in", "states"}
L = lambda v: v if isinstance(v, list) else [v]


def allowed(a, b):
    return [t for t, s in types.items() if t not in SKIP and t in defs and (
        (a in L(s.get("src_type")) and b in L(s.get("dst_type"))) or (b in L(s.get("src_type")) and a in L(s.get("dst_type"))))]


HEAD = open(S / "zero_brief.py", encoding="utf-8").read().split('HEAD = """', 1)[1].split('"""', 1)[0]


def brief(c):
    tys = set()
    for x in c["candidates"]:
        tys |= set(allowed(c["type"], x["type"]))
    tl = "\n".join(f"- {t}: {defs[t]['definition'].split('. ')[0][:220]} (reads: src {types[t].get('label', t)} dst; "
                   f"src {'/'.join(L(types[t].get('src_type')))}, dst {'/'.join(L(types[t].get('dst_type')))})"
                   for t in sorted(tys))
    cand = "\n".join(f"    - {x['id']} ({x['type']}): {x['name']}" for x in c["candidates"])
    vs = "\n".join("".join(f"    (before) {x['ref']}: {x['text']}\n" for x in v.get("before") or [])
                   + f"    {v['ref']}: {v['text']}" for v in c["verses"])
    return (HEAD + "\nTYPES:\n" + tl + f"\n\nCARD {c['id']} ({c['type']}): {c['name']}\n  verses:\n{vs}\n  candidates:\n{cand}\n")


def export():
    JOBS.mkdir(parents=True, exist_ok=True)
    pick = [c for c in cards if c["candidates"]]
    for name, model in MODELS.items():
        with open(JOBS / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as o:
            o.write(json.dumps({"_job": {"model": model, "options": OPTIONS[model], "recycle_every": 50}}) + "\n")
            for c in pick:
                o.write(json.dumps({"key": c["id"], "messages": [{"role": "user", "content": brief(c)}]},
                                   ensure_ascii=False) + "\n")
        print(name, model, len(pick), "calls")


PAIR_HEAD = """You read Bible verses (the Berean Standard Bible) and answer ONE narrow question about two named things.

Question: do the CARD'S verses state, in so many words, a relation between A and B, of one of the TYPES listed?
- Verses marked (before) are context only: use them to see who "he", "him" or "the king" is, never as the evidence.
- A list of names, a border route, or two names in one verse with no stated tie is "none".
- Answer "none" when unsure.

Worked examples (not from today's cards):
- 1Sam 25:3 "His name was Nabal, and his wife's name was Abigail": A = Abigail, B = Nabal -> spouse_of, "his wife's
  name was Abigail" ("His" is Nabal, named in the same verse).
- Josh 15:21 "These were the southernmost cities of the tribe of Judah ...: Kabzeel, Eder, Jagur,": A = Eder,
  B = Jagur -> none (a list).

Return ONLY one JSON object: {"type": one TYPE or "none", "src": id, "dst": id, "ref": "Book 1:2", "why": "the exact
words of the verse"}. Direction: src does the relation to dst as the type reads.
"""


def pair_export():
    JOBS.mkdir(parents=True, exist_ok=True)
    name, model, n = "34-bench-zero-pairs-gemma26", "gemma4:26b", 0
    with open(JOBS / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as o:
        o.write(json.dumps({"_job": {"model": model, "options": {"temperature": 0, "num_ctx": 6144, "num_predict": 220},
                                     "recycle_every": 100}}) + "\n")
        for c in cards:
            vs = "\n".join("".join(f"    (before) {x['ref']}: {x['text']}\n" for x in v.get("before") or [])
                           + f"    {v['ref']}: {v['text']}" for v in c["verses"])
            for x in c["candidates"]:
                tys = allowed(c["type"], x["type"])
                if not tys:
                    continue
                tl = "\n".join(f"- {t}: {defs[t]['definition'].split('. ')[0][:200]} (src {types[t].get('label', t)} dst)"
                               for t in sorted(tys))
                q = (PAIR_HEAD + f"\nTYPES:\n{tl}\n\nA = {c['id']} ({c['type']}): {c['name']}\nB = {x['id']} ({x['type']}): "
                     f"{x['name']}\nTHE CARD'S VERSES:\n{vs}\n")
                o.write(json.dumps({"key": f"{c['id']}|{x['id']}", "messages": [{"role": "user", "content": q}]},
                                   ensure_ascii=False) + "\n")
                n += 1
    print(name, n, "calls")


def parse_obj(text):
    for b in reversed(re.findall(r"\{[^{}]*\}", text or "", re.S)):
        try:
            return json.loads(b)
        except ValueError:
            continue
    return None


def parse(text):
    """the last JSON array in the answer: gemma4:26b answered "none" in one block, then "Correction/Refinement" and a
    second block, on 25 of 290 cards (the bench, 2026-11-19), and a greedy match read the two as one broken array"""
    text = text or ""
    blocks = re.findall(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.S)
    if not blocks:
        whole = re.search(r"\[.*\]", text, re.S)
        blocks = [whole.group(0)] if whole else []
    for b in reversed(blocks):
        try:
            v = json.loads(b)
            if isinstance(v, list):
                return v
        except ValueError:
            continue
    return None


def score():
    sys.path.insert(0, str(S))
    import zero_verdicts as V
    final = json.load(open(S / "zero_final.json", encoding="utf-8"))
    chk = json.load(open(S / "zero_checked.json", encoding="utf-8"))
    by_rule = {(r["src"], r["type"], r["dst"]) for r in final["relations"]
               if r["type"] == "camped_at" and r["src"] in ("children_of_israel", "ezra")
               and not any((p["src"], p["type"], p["dst"]) == (r["src"], r["type"], r["dst"]) for p in chk["pass"])}
    ids = {c["id"] for c in cards if c["candidates"]}
    key = defaultdict(set)
    for r in final["relations"]:
        t = (r["src"], r["type"], r["dst"])
        if t in by_rule:
            continue
        for end in (r["src"], r["dst"], r.get("card")):
            if end in ids:
                key[end].add(t)
    # the mechanical check, as zero_check.py runs it
    kind, have = {}, set()
    for ef in (ROOT / "ontology/entities").glob("*.jsonl"):
        for ln in open(ef, encoding="utf-8"):
            if ln.strip():
                e = json.loads(ln)
                if "id" in e and e.get("type"):
                    kind.setdefault(e["id"], e["type"])
    for f in (ROOT / "ontology/relations").glob("*.jsonl"):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                r = json.loads(ln); have.add((r.get("src"), r.get("type"), r.get("dst")))
    cmap = {c["id"]: c for c in cards}
    norm = lambda s: re.sub(r"[^a-z0-9 ]", "", re.sub(r"[\u2018\u2019']", "", str(s).lower())).split()

    def ok(it, card):
        c = cmap[card]; s, d, ty = it.get("src"), it.get("dst"), it.get("type")
        if s not in kind or d not in kind or card not in (s, d) or ty not in types:
            return False
        sp = types[ty]
        if kind[s] not in L(sp.get("src_type")) or kind[d] not in L(sp.get("dst_type")):
            return False
        v = next((x for x in c["verses"] if x["ref"] == it.get("ref")), None)
        if not v:
            return False
        q = [w for w in norm(it.get("why", "")) if len(w) > 2]
        vt = set(norm(v["text"]))
        if q and sum(w not in vt for w in q) > len(q) * 0.25:
            return False
        return (s, ty, d) not in have

    def tally(answers):
        t = Counter()
        for card in ids:
            items = answers.get(card)
            if items is None:
                t["no answer"] += 1; continue
            props = [it for it in items if isinstance(it, dict) and not it.get("none")]
            gold = key.get(card, set())
            if not gold:
                t["none cards"] += 1
            passed = [it for it in props if ok(it, card)]
            t["proposed"] += len(props); t["passed check"] += len(passed)
            if not gold and not passed:
                t["none agreed"] += 1
            pairs = {frozenset((g[0], g[2])) for g in gold}
            got = set()
            for it in passed:
                tt = (it["src"], it["type"], it["dst"])
                if V.SPEAKER.get(it["dst"]) and it["type"] == "asserted_by":
                    tt = (it["src"], "asserted_by", V.SPEAKER[it["dst"]])
                if tt in gold:
                    t["exact"] += 1; got.add(tt)
                elif frozenset((tt[0], tt[2])) in pairs:
                    t["pair"] += 1
                else:
                    t["extra"] += 1
            t["key relations"] += len(gold); t["key found exact"] += len(got)
        return t

    rows = {}
    ds = defaultdict(list)
    for f in sorted((S / "zero_all").glob("batch-*.answer.txt")):
        for it in parse(f.read_text(encoding="utf-8")) or []:
            if isinstance(it, dict) and it.get("card") in ids:
                ds[it["card"]].append(it)
    rows["DeepSeek V4 Pro (5 a brief)"] = tally({c: ds.get(c, []) for c in ids})
    for name, model in MODELS.items():
        p = DONE / f"{name}.jsonl"
        if not p.exists():
            continue
        ans, secs = {}, []
        for ln in open(p, encoding="utf-8"):
            r = json.loads(ln)
            if "content" in r:
                ans[r["key"]] = parse(r["content"]) or []
                secs.append(r.get("secs") or 0)
        t = tally(ans); t["calls"] = len(secs); t["median secs"] = round(sorted(secs)[len(secs) // 2], 1) if secs else 0
        rows[model] = t
    p = DONE / "34-bench-zero-pairs-gemma26.jsonl"
    if p.exists():
        ans, secs = defaultdict(list), []
        for ln in open(p, encoding="utf-8"):
            r = json.loads(ln)
            if "content" not in r:
                continue
            card = r["key"].split("|")[0]
            o = parse_obj(r["content"]) or {}
            if o.get("type") and o["type"] != "none":
                ans[card].append(o)
            ans.setdefault(card, [])
            secs.append(r.get("secs") or 0)
        t = tally(dict(ans)); t["calls"] = len(secs)
        t["median secs"] = round(sorted(secs)[len(secs) // 2], 1) if secs else 0
        rows["gemma4:26b, one pair a call"] = t
    out = {}
    for m, t in rows.items():
        prec = t["exact"] / t["passed check"] if t["passed check"] else 0
        rec = t["key found exact"] / t["key relations"] if t["key relations"] else 0
        out[m] = {**t, "precision exact": round(prec, 3), "recall exact": round(rec, 3),
                  "none agreed of none cards": f"{t['none agreed']}/{t['none cards']}"}
        print(f"{m}: {dict(out[m])}")
    (ROOT / "out" / "zero-bench-score.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    {"export": export, "pairs": pair_export, "score": score}[sys.argv[1]]()
