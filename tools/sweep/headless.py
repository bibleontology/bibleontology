"""THE SWEEP, UNATTENDED (plan 1.34; 2026-10-15: use the session and ideally
the next fully, checking in and stopping it if it goes awry).

Each passage goes to Haiku through the Claude Code CLI in print mode, with no
tools, no MCP servers and a one-line system prompt, so a call carries the
passage and nothing of an agent's overhead. Answers land in the run directory
as P-<name>.json, exactly as the bench's did, so passages.py split, vote.py,
derive.py and score.py read them unchanged. Nothing here writes to the graph.

Books are cut by chapter into passages of at most 12 verses, evenly.

Circuit breakers, each of which stops the run and says why in _log.txt:
  a STOP file in the run directory     (how a person or a check-in stops it)
  the deadline                         (no call starts after it)
  3 failures in a row                  (not counting the usage limit)
  4 of the last 20 passages unusable   (bad JSON, or verses missing, after a
                                        retry; an unusable passage is split in
                                        half and the halves judged)
  a call above 60,000 tokens a verse   (the bench averaged ~14,500)
At the usage limit it waits 10 minutes and tries again, until the deadline.

    python tools/sweep/headless.py <run name> <deadline UTC, e.g. 2026-10-15T17:20> <book> <book> ...
"""
import collections
import concurrent.futures as cf
import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import context as C  # noqa: E402
import passages as P  # noqa: E402

# The desktop app is a packaged (MSIX) app: its Roaming folder is virtualised,
# and Store Python sees the real one under Packages, not %APPDATA%.
CLI = next(p for p in (
    Path(os.environ["LOCALAPPDATA"]) / "Packages" / "Claude_pzs8sxrjxfjjc" / "LocalCache" / "Roaming",
    Path(os.environ["APPDATA"])) if (p / "Claude" / "claude-code" / "2.1.295").exists()) \
    / "Claude" / "claude-code" / "2.1.295" / "d2e29494ec83" / "claude.exe"
MODEL = "claude-haiku-5-5"
# 4 at a time judged ~860 verses an hour; the whole Bible overnight needs
# ~4x that (2026-10-16: the whole Bible done
# overnight). The meter was never the limit: 2,113 verses took 11%
# of a 5-hour window.
WORKERS = int(os.environ.get("SWEEP_WORKERS", "4"))
MAX_PER_VERSE = 60_000
CHUNK = 12

lock = threading.Lock()
recent = collections.deque(maxlen=20)   # 16 at a time: 10 was less than one wave
state = {"fails_in_row": 0, "stop": None}


def now():
    return dt.datetime.now(dt.timezone.utc)


def log(run, msg):
    line = f"{now():%Y-%m-%dT%H:%M:%SZ} {msg}"
    print(line, flush=True)
    with lock, open(run / "_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def stop(run, why):
    with lock:
        if not state["stop"]:
            state["stop"] = why
    log(run, f"STOPPING: {why}")


def passages_of(book):
    refs = collections.defaultdict(set)
    import gzip
    for line in gzip.open(C.OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(line).get("ref") or ""
        if r.startswith(book + "."):
            b, c, v = r.split(".")
            refs[int(c)].add(int(v))
    out = []
    for c in sorted(refs):
        vs = sorted(refs[c])
        n = -(-len(vs) // CHUNK)
        size = -(-len(vs) // n)
        for i in range(0, len(vs), size):
            part = vs[i:i + size]
            out.append((f"{book}{c}-{part[0]}", [f"{book}.{c}.{v}" for v in part]))
    return out


# THE LEVERS (2026-10-15: pull the levers now, after the projection
# came to about twice the four sessions). Measured on Ruth 1 and Genesis 1:
# an 8-verse prompt is ~37-59k characters, of which the task and vocabulary
# are ~23k paid once per passage, and the candidates the largest per-verse
# part, repeated verse after verse. So:
#   passages of up to 12 verses, not 8         (fixed part paid less often)
#   a candidate already given earlier in the passage appears by id alone
#   each `why` in a dozen words                 (output is the dear part)
# The third lever proposed, skipping verses with nothing to decide, found 1
# such verse in 40 and was dropped: not worth what it could miss.
LEVERS = """A candidate whose full id (with "#") was already listed for an earlier verse of this passage is listed again only
as {"id": ...}: it is the same candidate as before. Keep each `why` to about a dozen words, naming the evidence.

"""


def prompt(name, refs, ctxs):
    task = (Path(__file__).with_name("task.md")).read_text(encoding="utf-8")
    first = ctxs[refs[0]]
    shared = {"link_types": first["link_types"], "group_kinds": first["group_kinds"]}
    verses, seen = [], set()
    for i, ref in enumerate(refs):
        c = {k: v for k, v in ctxs[ref].items() if k not in ("link_types", "group_kinds")}
        if i:
            c["before"] = [b for b in c["before"] if not any(b["ref"] == ctxs[r]["verse"] for r in refs[:i])]
        cands = []
        for k in c.get("candidates") or []:
            full = "#" in (k.get("id") or "")
            cands.append({"id": k["id"]} if full and k["id"] in seen else k)
            if full:
                seen.add(k["id"])
        c["candidates"] = cands
        verses.append(c)
    return P.PREFACE + LEVERS + task.replace("## The verse", "## The passage") + "\n" + json.dumps(
        {"passage": name, **shared, "verses": verses}, ensure_ascii=False, separators=(",", ":")) + "\n"


def call(text, model=None):
    r = subprocess.run(
        [str(CLI), "-p", "--model", model or MODEL, "--tools", "", "--strict-mcp-config",
         "--no-session-persistence", "--output-format", "json",
         "--system-prompt", "You judge sentence structure and answer with ONLY a JSON object."],
        input=text, capture_output=True, text=True, encoding="utf-8", timeout=1800, cwd=str(ROOT / "out"))
    try:
        return json.loads(r.stdout), r.stderr
    except json.JSONDecodeError:
        return None, (r.stdout[-500:] + r.stderr[-500:])


def parse(res):
    """The passage object; or, when the judge wrote its verse objects one after
    another without the wrapper (Genesis 24:61, 2026-10-15, which tripped the
    breaker), those objects wrapped."""
    t = (res or {}).get("result") or ""
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        return json.loads(t[a:b + 1])
    except json.JSONDecodeError:
        dec, i, objs = json.JSONDecoder(), a, []
        try:
            while i <= b:
                o, i = dec.raw_decode(t, i)
                objs.append(o)
                while i <= b and t[i] in " \t\r\n,":
                    i += 1
        except json.JSONDecodeError:
            # broken JSON is an unusable answer, never a crash: an uncaught
            # error here stopped the whole resolution pass at 14:30Z
            # (2026-10-16), 368 chapters in
            return None
        return {"verses": objs} if objs and all(isinstance(o, dict) and o.get("ref") for o in objs) else None


def done(run, name, depth=0):
    """Judged whole, or as halves that are each done (John 1:34-44 came out as
    aa, ab and b)."""
    return (run / f"P-{name}.json").exists() or (
        depth < 4 and done(run, name + "a", depth + 1) and done(run, name + "b", depth + 1))


def judge(run, deadline, name, refs, text, ctxs_for_split=None):
    out = run / f"P-{name}.json"
    if done(run, name):
        return
    tries = 0
    while not state["stop"]:
        if (run / "STOP").exists():
            return stop(run, "STOP file")
        if now() >= deadline:
            return stop(run, "deadline")
        t0 = time.time()
        res, err = call(text)
        blob = json.dumps(res or {}) + (err or "")
        if res is None or res.get("is_error"):
            if "limit" in blob.lower():
                log(run, f"{name}: usage limit; waiting 10 minutes ({blob[:160]!r})")
                time.sleep(600)
                continue
            tries += 1
            with lock:
                state["fails_in_row"] += 1
                bad = state["fails_in_row"]
            log(run, f"{name}: call failed ({blob[:300]!r})")
            if bad >= 3:
                return stop(run, "3 failures in a row")
            if tries >= 2:
                return
            continue
        with lock:
            state["fails_in_row"] = 0
        u = res.get("usage") or {}
        toks = sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens",
                                             "cache_read_input_tokens", "cache_creation_input_tokens"))
        with lock, open(run / "_ledger.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"passage": name, "verses": len(refs), "tokens": toks, "usage": u,
                                "cost_usd_equiv": res.get("total_cost_usd"), "seconds": round(time.time() - t0),
                                "at": f"{now():%Y-%m-%dT%H:%M:%SZ}"}) + "\n")
        if toks > MAX_PER_VERSE * len(refs):
            return stop(run, f"{name}: {toks:,} tokens for {len(refs)} verses, above the {MAX_PER_VERSE:,}/verse breaker")
        try:
            ans = parse(res)
            got = {v.get("ref") for v in (ans or {}).get("verses") or []}
            ok = ans is not None and all(any(g == r or (g or "").endswith(r) for g in got) for r in refs)
        except json.JSONDecodeError:
            ans, ok = None, False
        if not ok and tries == 0:
            # one more try before it counts: Genesis 25:13 came back with one
            # verse of its passage, a short answer, not a wrong one
            tries += 1
            (run / f"bad-{name}-try1.txt").write_text((res or {}).get("result") or "", encoding="utf-8")
            log(run, f"{name}: answer incomplete; one retry")
            continue
        # THE BREAKER COUNTS WHAT IS LOST, not what is split. A passage that
        # fails whole and succeeds in halves loses nothing; counting it, three
        # recovered splits in Acts 18-19 took the breaker to one short of
        # stopping the night (2026-10-16). Only a passage that cannot be split
        # further and still fails is a loss.
        splits = not ok and len(refs) > 2 and ctxs_for_split is not None
        with lock:
            if not splits:
                recent.append(ok)
            unusable = recent.count(False)
        if ok:
            out.write_text(json.dumps(ans, ensure_ascii=False, indent=1), encoding="utf-8")
            log(run, f"{name}: {len(refs)} verses, {toks:,} tokens")
            return
        (run / f"bad-{name}.txt").write_text((res or {}).get("result") or "", encoding="utf-8")
        log(run, f"{name}: answer unusable (bad JSON or verses missing){'; splitting' if splits else '; LOST'}")
        if unusable >= 4:
            return stop(run, "4 of the last 20 passages lost")
        # SPLIT, DON'T SKIP. Mark 12:34-44 and John 1:34-51 came back twice
        # each as their first verse alone (2026-10-16); halves are judged as
        # passages of their own, so the night leaves no hole
        if splits:
            half = len(refs) // 2
            for tag, part in (("a", refs[:half]), ("b", refs[half:])):
                judge(run, deadline, f"{name}{tag}", part, prompt(f"{name}{tag}", part, ctxs_for_split), ctxs_for_split)
        return


def stay_awake():
    """Hold off idle sleep while this process runs, as a media player does; it
    lapses when the process ends and changes no setting. The first run's stop
    went unseen for 12 hours because the machine slept (2026-10-15)."""
    # THE DISPLAY TOO. The host PC has only Modern Standby (powercfg /a: "S0 Low
    # Power Idle", no S3): once the screen goes off -- soon after a lock --
    # Windows pauses desktop programs whatever "sleep after" says, and a run
    # holding only ES_SYSTEM_REQUIRED was paused 04:06-09:22Z (2026-10-16).
    # Holding the display on is what a video player does; no setting changes.
    if sys.platform == "win32":
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)


def main():
    stay_awake()
    name, deadline, books = sys.argv[1], sys.argv[2], sys.argv[3:]
    deadline = dt.datetime.fromisoformat(deadline).replace(tzinfo=dt.timezone.utc)
    run = ROOT / "out" / "sweep" / "runs" / name
    run.mkdir(parents=True, exist_ok=True)
    log(run, f"start: {MODEL}, books {books}, deadline {deadline:%Y-%m-%dT%H:%MZ}, {WORKERS} at a time")
    # ONE POOL ACROSS BOOKS: the next book's context is built while this
    # book's last passages are still out, so the workers never wait at a book's
    # end (each book's build reads the clause files, about a minute). The queue
    # is kept short so memory holds a few books' prompts, not the Bible's.
    futs = []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for book in books:
            if state["stop"]:
                break
            ps = [(n, r) for n, r in passages_of(book) if not done(run, n)]
            if not ps:
                continue
            ctxs = C.build([r for _, rs in ps for r in rs])
            log(run, f"{book}: {len(ps)} passages to judge")
            for n, rs in ps:
                while sum(not f.done() for f in futs) > 3 * WORKERS and not state["stop"]:
                    time.sleep(5)
                futs.append(ex.submit(judge, run, deadline, n, rs, prompt(n, rs, ctxs), ctxs))
        for f in futs:
            f.result()
    log(run, f"end: {state['stop'] or 'all books done'}")


if __name__ == "__main__":
    main()
