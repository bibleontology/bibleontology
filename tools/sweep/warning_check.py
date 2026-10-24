"""THE SWEEP'S WARNINGS, JUDGED ONE BY ONE (2026-10-18, on the 1.2.0
inventory: the issue is accuracy, so a precision job was run to get it right).

The structure sweep linked 196 clauses to a command as its `warning`: what
follows if the command is refused ("Do not raise your voice against us, or
angry men will attack you", Judges 18:25). They were held out of the layer on
2026-10-18 (5 of 10 right on a sample: second commands, a time clause and a
self-link were among them). Each is read here against its verse by a focused
judge, which answers warning / second command / other. This measures
PRECISION only; warnings the sweep never proposed are not looked for.

The 196 come from the layer as it was before the hold (git: the parent of
the commit that held them).

    python tools/sweep/warning_check.py run     -> out/sweep/runs/warning-check/W-*.json
    python tools/sweep/warning_check.py merge   -> out/sweep/warning-check.jsonl, a tally
"""
import collections
import concurrent.futures as cf
import gzip
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(Path(__file__).parent))
import context as C  # noqa: E402
import headless as H  # noqa: E402

MODEL = "claude-haiku-5-5"
BEFORE_HOLD = "dee6aac2~1"          # the layer with the 196 still in it
CHUNK, WORKERS = 20, 6
LOCK = threading.Lock()
state = {"fails": 0, "lost": 0, "stop": None}
RUN = OUT / "sweep" / "runs" / "warning-check"
DEST = OUT / "sweep" / "warning-check.jsonl"

TASK = """You are checking one kind of link in a reading of the Bible: a clause marked as the WARNING attached to a
command. A warning says what will happen if the command is NOT obeyed, or the danger the command is given to avoid:
"Do not raise your voice against us, OR angry men will attack you" (Judges 18:25); "We must leave quickly, OR he will
overtake us" (2 Samuel 15:14); "Why should God be angry with your words?" after "Do not let your mouth cause you to
sin" (Ecclesiastes 5:6); "lest you die".

For each item you get the verse (the Berean Standard Bible, and the verses around it where the link crosses verses),
the command, and the clause marked as its warning (a word-by-word gloss of the original). Answer:
  "warning"         the marked clause says what follows if the command is refused, or the danger it averts
  "second_command"  the marked clause is another command (often a negative one: "do not light the fire")
  "other"           anything else: a time or a reason clause, a description, the same clause as the command, unclear

Rules:
- Read the verse, not only the gloss. A negative command ("do not ...") is a command, not a warning.
- A reason the command is right ("for the LORD has given you the city") is "other", not a warning; a warning is a
  consequence of disobeying, or the threat the command is meant to avoid.
- When it is truly unclear, answer "other" with confidence "low". Unresolved is better than wrong.
- Answer every item once, by its id. Keep each `why` to about a dozen words.

Answer with ONLY this JSON object:
{"answers": [{"id": "<item id>", "decision": "warning|second_command|other", "confidence": "high|medium|low", "why": "..."}]}

"""

# THE SECOND JUDGE (2026-10-18: a second judge, keep agreement). The first
# (Haiku) judged the verse, not the marked clause: Exodus 19:12's marked clause
# is "touch its base", part of the prohibition, and it was kept for the death
# penalty in the next clause; 1 Samuel 14:44's oath was kept as a warning. Read
# by Claude, its kept set was about 75-83% right. These rules are added for the
# second judge, and only what both call a warning is kept.
SECOND = {"model": "claude-sonnet-5-5", "run": "warning-check-2", "rules": """
Further rules, from errors found in an earlier pass:
- Judge ONLY the clause marked as the warning, read in its verse. If that clause is itself part of what is forbidden or
  commanded ("Be careful not to go up on the mountain or TOUCH ITS BASE"), it is "other", even when the verse goes
  on to name a penalty in a different clause.
- An oath or curse formula ("May God punish me, and ever so severely, if you do not surely die") is not a command
  with a warning: "other".
- "Or ...", "otherwise ...", "lest ...", "so that ... not ..." after a command usually introduce a warning, but only
  if the marked clause is what they introduce.
"""}


def jl_bytes(b):
    for line in gzip.decompress(b).decode("utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def items():
    """The 196, each with its command's words and the marked clause's words."""
    raw = subprocess.run(["git", "show", f"{BEFORE_HOLD}:out/sweep-layer.jsonl.gz"], capture_output=True, cwd=ROOT).stdout
    layer = list(jl_bytes(raw))
    warns = [d for d in layer if d.get("type") == "warning" and d.get("action") != "remove"]
    # the command a group holds: the builder's head, or the sweep's `command` member
    commands = collections.defaultdict(list)
    for d in layer:
        if d.get("type") == "command" and d.get("action") != "remove":
            commands[d["src"]].append(d["dst"])
    want = {w["src"] for w in warns} | {w["dst"] for w in warns} | {x for v in commands.values() for x in v}
    nodes = {}
    with gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["id"] in want:
                nodes[d["id"]] = d
    heads = {nid: n.get("head") for nid, n in nodes.items() if n.get("head")}
    for h in list(heads.values()):
        want.add(h)
    out = []
    for i, w in enumerate(sorted(warns, key=lambda d: (d["ref"], d["src"], d["dst"]))):
        g = w["src"]
        cmd_ids = commands.get(g) or ([heads[g]] if heads.get(g) else [])
        cmd = " / ".join((nodes.get(c) or {}).get("text") or "" for c in cmd_ids) or (nodes.get(g) or {}).get("text") or ""
        out.append({"id": f"w{i + 1:03d}", "group": g, "clause": w["dst"], "ref": w["ref"],
                    "command": cmd, "marked": (nodes.get(w["dst"]) or {}).get("text") or "",
                    "refs": sorted({g.split("#")[0], w["dst"].split("#")[0]})})
    return out


def prompt(batch, bsb, extra=""):
    verses = {}
    for it in batch:
        for r in it["refs"]:
            verses.setdefault(r, bsb(r)[1])
    return TASK + extra + json.dumps({"verses": [{"ref": r, "text": t} for r, t in verses.items()],
                              "items": [{"id": it["id"], "verse": it["ref"], "command": it["command"],
                                         "marked_as_warning": it["marked"]} for it in batch]},
                             ensure_ascii=False, separators=(",", ":")) + "\n"


def log(msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    print(line, flush=True)
    with LOCK, open(RUN / "_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def judge(name, batch, text):
    out = RUN / f"W-{name}.json"
    if out.exists() or state["stop"]:
        return
    ids = {it["id"] for it in batch}
    for attempt in range(3):
        if (RUN / "STOP").exists():
            state["stop"] = "STOP file"
            return
        res, err = H.call(text, MODEL)
        blob = json.dumps(res or {}) + (err or "")
        if (res is None or res.get("is_error")) and "limit" in blob.lower():
            log(f"{name}: usage limit; waiting 10 minutes")
            time.sleep(600)
            continue
        if res is None or res.get("is_error"):
            with LOCK:
                state["fails"] += 1
                if state["fails"] >= 5:
                    state["stop"] = "5 failed calls in a row"
            log(f"{name}: call failed")
            if state["stop"]:
                return
            continue
        with LOCK:
            state["fails"] = 0
        u = res.get("usage") or {}
        toks = sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                             "cache_creation_input_tokens"))
        with LOCK, open(RUN / "_ledger.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"batch": name, "items": len(batch), "tokens": toks}) + "\n")
        ans = H.parse(res)
        got = {a.get("id") for a in (ans or {}).get("answers") or []
               if a.get("decision") in ("warning", "second_command", "other")}
        if ans and len(got & ids) >= 0.9 * len(ids):
            out.write_text(json.dumps(ans, ensure_ascii=False, indent=1), encoding="utf-8")
            log(f"{name}: {len(batch)} items, {len(got & ids)} answered, {toks:,} tokens")
            return
        log(f"{name}: answer incomplete ({len(got & ids)} of {len(ids)}), attempt {attempt + 1}")
    state["lost"] += 1
    log(f"{name}: LOST after 3 attempts")


def run(second=False):
    global RUN, MODEL
    H.stay_awake()
    first_items = RUN / "items.json"
    if second:
        RUN, MODEL = OUT / "sweep" / "runs" / SECOND["run"], SECOND["model"]
    RUN.mkdir(parents=True, exist_ok=True)
    # the second judge reads exactly the items the first did
    its = json.loads(first_items.read_text(encoding="utf-8")) if second else items()
    (RUN / "items.json").write_text(json.dumps(its, ensure_ascii=False, indent=1), encoding="utf-8")
    bsb = C._bsb()
    batches = [(f"B{i // CHUNK + 1:02d}", its[i:i + CHUNK]) for i in range(0, len(its), CHUNK)]
    log(f"start: {len(its)} warnings, {len(batches)} batches, {WORKERS} at a time, {MODEL}")
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for f in [ex.submit(judge, nm, b, prompt(b, bsb, SECOND["rules"] if second else "")) for nm, b in batches]:
            f.result()
    log(f"end: {state['stop'] or 'all batches done'}")


def answers(run_dir):
    ans = {}
    for p in sorted(run_dir.glob("W-*.json")):
        for a in json.loads(p.read_text(encoding="utf-8")).get("answers") or []:
            ans[a.get("id")] = a
    return ans


def merge():
    """Kept only where BOTH judges say warning, at high or medium confidence
    (low counts as not: unresolved beats wrong). Without the second run, the
    first judge alone."""
    its = {it["id"]: it for it in json.loads((RUN / "items.json").read_text(encoding="utf-8"))}
    run2 = OUT / "sweep" / "runs" / SECOND["run"]
    a1, a2 = answers(RUN), (answers(run2) if run2.exists() else None)
    tally = collections.Counter()
    rows = []

    def sure(a):
        return (a or {}).get("decision") == "warning" and (a or {}).get("confidence") in ("high", "medium")
    for i, it in its.items():
        x, y = a1.get(i) or {}, (a2 or {}).get(i) or {}
        keep = sure(x) and (a2 is None or sure(y))
        tally[f"{x.get('decision')}" + (f" / {y.get('decision')}" if a2 is not None else "")] += 1
        rows.append({**it, "decision": "warning" if keep else (y or x).get("decision"), "keep": keep,
                     "first": {k: x.get(k) for k in ("decision", "confidence", "why")},
                     **({"second": {k: y.get(k) for k in ("decision", "confidence", "why")}} if a2 is not None else {}),
                     "reading": "warning check",
                     "by": "warning check (Claude Haiku 5.5" + (" and Claude Sonnet 5.5, both agreeing)" if a2 is not None else ")")})
    DEST.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    tok = 0
    for d in (RUN, run2):
        if (d / "_ledger.jsonl").exists():
            tok += sum(json.loads(x)["tokens"] for x in (d / "_ledger.jsonl").read_text(encoding="utf-8").splitlines())
    print(f"{len(rows)} warnings, first / second: {dict(tally.most_common())}; kept {sum(r['keep'] for r in rows)}; "
          f"{tok:,} tokens in all -> {DEST.relative_to(ROOT)}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    run(second=True) if cmd == "run2" else {"run": run, "merge": merge}[cmd]()
