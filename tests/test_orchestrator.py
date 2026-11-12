"""The orchestrator's acceptance tests (plan A.41; the design approved by Doug, 2026-11-02).

    python -X utf8 tests/test_orchestrator.py

Written before the code, by Claude; the coding worker writes tools/orchestra/orchestra.py to pass them. All offline:
fake folders, a fake proxy, a fixed clock. Each "never" rule is tested by feeding it the fault and expecting refusal.

THE INTERFACE the module provides (Python 3.9, standard library only):
  is_peak(t: datetime) -> bool                       UTC; 01:00-04:00 and 06:00-10:00, Monday-Friday
  safe_path(base: Path, *parts) -> Path              raises ValueError if the result leaves base
  reduce_item(item: dict, allowed: list) -> dict     raises ValueError if item has a key not in allowed
  choose_model(pass_spec: dict, models: dict) -> (model: str, reason: str)
  class Env: home, grunt, now (datetime UTC), proxy (an object with .health() -> dict and
             .chat(job: str, messages: list, thinking: bool) -> {"content": str, "cost": float}),
             rates (dict model -> checks per minute)
  queue_hours(env) -> float                          estimated hours of work in grunt/queue (not yet in done)
  fill_queue(env) -> list[str]                       moves intake jobs into grunt/queue; returns names moved
  second_pass(env, pass_spec: dict) -> str           "done" | "waiting for budget" | "held: peak" | "refused: <why>"
  agreement(env, pass_name: str) -> dict             writes results/<pass>/agreement.jsonl; returns counts
  cycle(env) -> None                                 one full cycle; writes status.json and today.md
"""
import datetime as dt
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "orchestra"))
try:
    import orchestra as O  # noqa: E402
except ImportError:
    print("FAIL tools/orchestra/orchestra.py does not exist yet")
    sys.exit(1)

fails = []


def check(ok, what):
    if not ok:
        fails.append(what)


def t(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)


class FakeProxy:
    def __init__(self, week=0.10, cap=5.0, answer=None):
        self.week, self.cap, self.calls, self.answer = week, cap, [], answer

    def health(self):
        return {"ok": True, "week_usd": self.week, "cap": self.cap}

    def chat(self, job, messages, thinking):
        self.calls.append({"job": job, "messages": messages, "thinking": thinking})
        self.week += 0.002
        return {"content": self.answer(messages) if self.answer else "", "cost": 0.002}


def world(now="2026-11-03T14:00:00", proxy=None):
    tmp = Path(tempfile.mkdtemp())
    home, grunt = tmp / "orchestra", tmp / "grunt"
    for d in (home / "intake", home / "results", grunt / "queue", grunt / "done"):
        d.mkdir(parents=True)
    env = O.Env(home=home, grunt=grunt, now=t(now), proxy=proxy or FakeProxy(), rates={"gemma4:26b": 60.0, "qwen3.8:27b": 20.0})
    return tmp, env


def job(path, model, n, kind="relation_sweep"):
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"_job": {"model": model, "options": {}, "pass": kind}}) + "\n")
        for i in range(n):
            f.write(json.dumps({"key": f"k{i}", "messages": [{"role": "user", "content": "x"}]}) + "\n")


def intake(env, name, n, priority, model="gemma4:26b", reasoning=False):
    job(env.home / "intake" / f"{name}.jsonl", model, n)
    (env.home / "intake" / f"{name}.pass.json").write_text(json.dumps(
        {"pass": name, "priority": priority, "mac_job": f"{name}.jsonl", "reasoning": reasoning}), encoding="utf-8")


# 1. the queue fills to its target from the intake, highest priority first, and not past it
tmp, env = world()
intake(env, "low", 60 * 60 * 10, 1)            # 10 hours at 60 a minute
intake(env, "high", 60 * 60 * 10, 9)
intake(env, "mid", 60 * 60 * 10, 5)
moved = O.fill_queue(env)
check(moved[:1] == ["high.jsonl"], f"1: highest priority first, got {moved}")
check(24 <= O.queue_hours(env) <= 34, f"1: queue {O.queue_hours(env):.1f} h, not topped up to a day")
check(len(moved) == 3, f"1: three 10-hour jobs make a day, moved {moved}")
O.fill_queue(env)
check(len(list((env.grunt / "queue").glob("*.jsonl"))) == 3, "1: a full queue was filled again")
shutil.rmtree(tmp)

# 2-4. the second pass: flagged items and plants only; two runs; agreement; a pass below its planted floor
tmp, env = world(proxy=FakeProxy(answer=lambda m: "\n".join(
    json.dumps({"id": l.split("]")[0].strip("["), "verdict": "not_said"}) for l in m[-1]["content"].splitlines()
    if l.startswith("["))))
name = "sweep"
pdir = env.home / "passes" / name
pdir.mkdir(parents=True)
(pdir / "brief.md").write_text("Say whether the verse says the claim.", encoding="utf-8")
with open(pdir / "planted.jsonl", "w", encoding="utf-8") as f:
    for i in range(4):
        f.write(json.dumps({"id": f"p{i}", "claim": "c", "ref": "Gen 1:1", "verse": "v", "context": [], "expect": "not_said"}) + "\n")
with open(env.grunt / "done" / "sweep.jsonl", "w", encoding="utf-8") as f:
    for i, v in enumerate(["stated", "not_said", "partly", "stated"]):
        f.write(json.dumps({"key": f"k{i}", "content": json.dumps({"verdict": v})}) + "\n")
(env.grunt / "done" / "sweep.complete").write_text("")
with open(pdir / "items.jsonl", "w", encoding="utf-8") as f:
    for i in range(4):
        f.write(json.dumps({"key": f"k{i}", "id": f"k{i}", "claim": f"claim {i}", "ref": "Gen 1:1", "verse": "v", "context": []}) + "\n")
spec = {"pass": name, "mac_job": "sweep.jsonl", "flag": {"verdict_in": ["not_said", "partly"]},
        "deepseek": {"brief": "brief.md", "batch": 36, "runs": 2, "budget_usd": 0.5, "planted": "planted.jsonl",
                     "planted_floor": 0.85, "thinking": False},
        "allowed_fields": ["id", "claim", "ref", "verse", "context"]}
check(O.second_pass(env, spec) == "done", "2: the second pass did not run")
sent = " ".join(c["messages"][-1]["content"] for c in env.proxy.calls)
check("claim 1" in sent and "claim 2" in sent, "2: a flagged item was not sent")
check("claim 0" not in sent and "claim 3" not in sent, "2: an item the Mac passed was sent")
check(len(env.proxy.calls) == 2, f"3: two runs expected, {len(env.proxy.calls)} calls")
counts = O.agreement(env, name)
rows = [json.loads(l) for l in open(env.home / "results" / name / "agreement.jsonl", encoding="utf-8")]
check({r["category"] for r in rows} <= {"agree-holds", "agree-wrong", "disagree", "unsettled", "mac-only"}, "3: unknown category")
check(any(r["category"] == "agree-wrong" for r in rows), "3: the Mac and both runs said not_said: agree-wrong")
check(counts.get("trusted") is True, "4: plants all right, the pass should be trusted")
shutil.rmtree(tmp)

tmp, env = world(proxy=FakeProxy(answer=lambda m: ""))           # answers nothing: every plant missed
pdir = env.home / "passes" / "sweep"
pdir.mkdir(parents=True)
(pdir / "brief.md").write_text("b", encoding="utf-8")
(pdir / "planted.jsonl").write_text(json.dumps({"id": "p0", "claim": "c", "ref": "Gen 1:1", "verse": "v", "context": [], "expect": "not_said"}) + "\n", encoding="utf-8")
(pdir / "items.jsonl").write_text(json.dumps({"key": "k0", "id": "k0", "claim": "c", "ref": "Gen 1:1", "verse": "v", "context": []}) + "\n", encoding="utf-8")
(env.grunt / "done" / "sweep.jsonl").write_text(json.dumps({"key": "k0", "content": json.dumps({"verdict": "not_said"})}) + "\n", encoding="utf-8")
(env.grunt / "done" / "sweep.complete").write_text("")
O.second_pass(env, spec)
check(O.agreement(env, "sweep").get("trusted") is False, "4: a pass below its planted floor was trusted")
shutil.rmtree(tmp)

# 5. budget: it stops at the pass budget and before the weekly cap
for week, label in ((4.99, "the weekly cap"),):
    tmp, env = world(proxy=FakeProxy(week=week))
    pdir = env.home / "passes" / "sweep"
    pdir.mkdir(parents=True)
    (pdir / "brief.md").write_text("b", encoding="utf-8")
    (pdir / "planted.jsonl").write_text("", encoding="utf-8")
    (pdir / "items.jsonl").write_text(json.dumps({"key": "k0", "id": "k0", "claim": "c", "ref": "Gen 1:1", "verse": "v", "context": []}) + "\n", encoding="utf-8")
    (env.grunt / "done" / "sweep.jsonl").write_text(json.dumps({"key": "k0", "content": json.dumps({"verdict": "not_said"})}) + "\n", encoding="utf-8")
    (env.grunt / "done" / "sweep.complete").write_text("")
    r = O.second_pass(env, spec)
    check(r == "waiting for budget" and not env.proxy.calls, f"5: at {label} it called anyway ({r})")
    shutil.rmtree(tmp)

# 6. thinking without Doug's recorded approval is refused
tmp, env = world()
think = json.loads(json.dumps(spec))
think["deepseek"]["thinking"] = True
r = O.second_pass(env, think)
check(r.startswith("refused") and not env.proxy.calls, f"6: thinking without approval ran ({r})")
shutil.rmtree(tmp)

# 7. an item with a forbidden field is refused, and nothing is sent
try:
    O.reduce_item({"id": "k0", "claim": "c", "note": "a reader's words"}, spec["allowed_fields"])
    fails.append("7: an item carrying 'note' was not refused")
except ValueError:
    pass
check(O.reduce_item({"id": "k0", "claim": "c"}, spec["allowed_fields"]) == {"id": "k0", "claim": "c"}, "7: an allowed item changed")

# 8. a path outside its folders is refused
base = Path(tempfile.mkdtemp())
for bad in ("../x", "/etc/passwd", "a/../../b"):
    try:
        O.safe_path(base, bad)
        fails.append(f"8: {bad!r} was not refused")
    except ValueError:
        pass
shutil.rmtree(base)

# 9. peak hours hold the DeepSeek stage; "urgent" with Doug's words releases it
check(O.is_peak(t("2026-11-03T07:30:00")) and O.is_peak(t("2026-11-03T02:00:00")), "9: weekday peak not seen")
check(not O.is_peak(t("2026-11-03T14:00:00")) and not O.is_peak(t("2026-11-07T07:30:00")), "9: off-peak or Saturday seen as peak")
tmp, env = world(now="2026-11-03T07:30:00")
r = O.second_pass(env, spec)
check(r == "held: peak" and not env.proxy.calls, f"9: called at peak ({r})")
shutil.rmtree(tmp)

# 10. after a crash nothing is called twice; 11. done/ is never written
tmp, env = world(proxy=FakeProxy(answer=lambda m: ""))
pdir = env.home / "passes" / "sweep"
pdir.mkdir(parents=True)
(pdir / "brief.md").write_text("b", encoding="utf-8")
(pdir / "planted.jsonl").write_text("", encoding="utf-8")
(pdir / "items.jsonl").write_text(json.dumps({"key": "k0", "id": "k0", "claim": "c", "ref": "Gen 1:1", "verse": "v", "context": []}) + "\n", encoding="utf-8")
(env.grunt / "done" / "sweep.jsonl").write_text(json.dumps({"key": "k0", "content": json.dumps({"verdict": "not_said"})}) + "\n", encoding="utf-8")
(env.grunt / "done" / "sweep.complete").write_text("")
before = {p.name: p.read_bytes() for p in (env.grunt / "done").iterdir()}
O.second_pass(env, spec)
n1 = len(env.proxy.calls)
O.second_pass(env, spec)
check(len(env.proxy.calls) == n1, "10: a finished batch was called again")
check({p.name: p.read_bytes() for p in (env.grunt / "done").iterdir()} == before, "11: done/ was written")
shutil.rmtree(tmp)

# 12. status.json and today.md say what ran, what it cost, what waits
tmp, env = world()
O.cycle(env)
st = json.loads((env.home / "status.json").read_text(encoding="utf-8"))
check({"ran", "cost_usd", "waiting"} <= set(st), f"12: status.json lacks keys: {sorted(st)}")
check((env.home / "today.md").exists(), "12: no today.md")
shutil.rmtree(tmp)

# 13. at peak a long job is running or placed to outlast the window
tmp, env = world(now="2026-11-03T05:50:00")                 # ten minutes before the 06:00-10:00 window
intake(env, "long", 60 * 60 * 6, 5)
O.cycle(env)
check(O.queue_hours(env) >= 4.2, f"13: only {O.queue_hours(env):.1f} h queued before a four-hour peak")
shutil.rmtree(tmp)

# 14-15. the model is chosen for the job, from measurements; a plan beyond them is overruled
simple = {"pass": "s", "reasoning": False}
hard = {"pass": "h", "reasoning": True, "kind": "who_did_what"}
m, _ = O.choose_model(simple, {})
check(m == "gemma4:26b", f"14: a simple job ran on {m}")
m, _ = O.choose_model(hard, {})
check(m == "gemma4:26b", f"14: a reasoning job with no measurements ran on {m}")
table = {"who_did_what": {"gemma4:26b": {"hard_acc": 0.37, "per_min": 58}, "qwen3.8:27b": {"hard_acc": 0.59, "per_min": 20}}}
m, why = O.choose_model(hard, table)
check(m == "qwen3.8:27b" and why, f"14: qwen's measured advantage not used ({m}, {why!r})")
m, why = O.choose_model(dict(hard, planned="qwen3.8:27b", kind="no_such_kind"), table)
check(m == "gemma4:26b" and "overrul" in why.lower(), f"15: a plan beyond the table was followed ({m}, {why!r})")

# FROM CLAUDE'S READ OF THE WORKER'S CODE (2026-11-02), each a fault the first tests missed
def sweep_world(proxy, verdicts):
    tmp, env = world(proxy=proxy)
    pdir = env.home / "passes" / "sweep"
    pdir.mkdir(parents=True)
    (pdir / "brief.md").write_text("b", encoding="utf-8")
    (pdir / "planted.jsonl").write_text("", encoding="utf-8")
    with open(pdir / "items.jsonl", "w", encoding="utf-8") as f, open(env.grunt / "done" / "sweep.jsonl", "w", encoding="utf-8") as g:
        for i, v in enumerate(verdicts):
            f.write(json.dumps({"key": f"k{i}", "id": f"k{i}", "claim": f"c{i}", "ref": "Gen 1:1", "verse": "v", "context": []}) + "\n")
            g.write(json.dumps({"key": f"k{i}", "content": json.dumps({"verdict": v})}) + "\n")
    (env.grunt / "done" / "sweep.complete").write_text("")
    return tmp, env


# 17. an item the Mac passed (never sent) is the Mac's alone, never "disagree"
tmp, env = sweep_world(FakeProxy(answer=lambda m: ""), ["stated", "stated", "not_said"])
O.second_pass(env, spec)
counts = O.agreement(env, "sweep")
check(counts.get("disagree", 0) == 0 or counts.get("mac-only", 0) >= 2,
      f"17: items the Mac passed were filed as disagreements: {counts}")
shutil.rmtree(tmp)


# 18. a health answer without a cap, or with an unreadable spend, stops the calls
class NoCap(FakeProxy):
    def health(self):
        return {"ok": True, "week_usd": 0.1}


class BadWeek(FakeProxy):
    def health(self):
        return {"ok": True, "week_usd": "?", "cap": 5.0}


for P, label in ((NoCap, "no cap"), (BadWeek, "an unreadable spend")):
    tmp, env = sweep_world(P(), ["not_said"])
    r = O.second_pass(env, spec)
    check(r == "waiting for budget" and not env.proxy.calls, f"18: called with {label} ({r})")
    shutil.rmtree(tmp)

# 19. each batch run is its own proxy job, so the proxy's per-job caps bind each call
tmp, env = sweep_world(FakeProxy(answer=lambda m: ""), ["not_said"])
O.second_pass(env, spec)
jobs = [c["job"] for c in env.proxy.calls]
check(len(set(jobs)) == len(jobs) == 2 and all(j.startswith("orch-sweep-") for j in jobs), f"19: proxy job names {jobs}")
shutil.rmtree(tmp)

# 20. below its target the queue is topped up to a day, not to the target
tmp, env = world()
for k in range(5):
    intake(env, f"j{k}", 60 * 60 * 5, 5 - k)                       # five 5-hour jobs
O.fill_queue(env)
check(O.queue_hours(env) >= 24, f"20: topped up to {O.queue_hours(env):.1f} h, not a day")
shutil.rmtree(tmp)

# FROM THE SECURITY SEAT (2026-11-03)
# 21. a failing call (perhaps billed) is retried at most MAX_FAILS times, then filed as failed; never without end
class Failing(FakeProxy):
    def chat(self, job, messages, thinking):
        self.calls.append({"job": job})
        raise RuntimeError("timed out")


tmp, env = sweep_world(Failing(), ["not_said"])
r1 = O.second_pass(env, spec)
for _ in range(4):
    r2 = O.second_pass(env, spec)
failed = [json.loads(p.read_text(encoding="utf-8")).get("failed") for p in (env.home / "results" / "sweep").glob("*-run*.json")]
check(r1.startswith("call failed (1") and r2 == "done" and len(env.proxy.calls) == 2 * O.MAX_FAILS and failed == [True, True],
      f"21: {r1!r}, then {r2!r}; {len(env.proxy.calls)} calls, filed {failed} (want two runs, each tried {O.MAX_FAILS} times)")
shutil.rmtree(tmp)

# 22. one pass that raises never stops the cycle or the passes after it
tmp, env = sweep_world(FakeProxy(answer=lambda m: ""), ["not_said"])
real = O.second_pass
O.second_pass = lambda env, spec: (_ for _ in ()).throw(ValueError("bad spec"))
try:
    O.cycle(env)
    st = json.loads((env.home / "status.json").read_text(encoding="utf-8"))
    check(any("error ValueError" in w for w in st.get("waiting", [])), f"22: the failed pass is not reported: {st}")
except Exception as exc:                                         # noqa: BLE001
    check(False, f"22: one pass's error stopped the cycle ({type(exc).__name__})")
finally:
    O.second_pass = real
shutil.rmtree(tmp)

# 23. the plants are spread through the batches (2026-11-04: appended last, 10 of 12 filled the final batch). The
# 16-psalm-headings shape: 286 flagged items, 12 plants, batches of 36
items_ = [{"id": "i%d" % i} for i in range(286)]
plants_ = [{"id": "p%d" % i} for i in range(12)]
order = O._spread(items_, plants_, "16-psalm-headings")
batches_ = [order[i:i + 36] for i in range(0, len(order), 36)]
per = [sum(1 for x in b if x["id"].startswith("p")) for b in batches_]
check(len(order) == 298 and sorted(x["id"] for x in order) == sorted(x["id"] for x in items_ + plants_),
      "23: the spread lost or repeated an item")
check(max(per) <= 3 and min(per) >= 1, f"23: plants per batch {per} (want every batch some, none more than 3)")
check(order == O._spread(items_, plants_, "16-psalm-headings"), "23: the order is not the same on every cycle")
few = O._spread(items_[:5], plants_[:2], "small")
check([x["id"] for x in few if x["id"].startswith("i")] == ["i0", "i1", "i2", "i3", "i4"],
      "23: the spread reordered the real items")

# 24. a finished pass is not listed as held at peak (2026-11-04: "16-psalm-headings: held: peak" after it finished)
tmp, env = sweep_world(FakeProxy(answer=lambda m: ""), ["not_said"])
(env.home / "results" / "sweep").mkdir(parents=True, exist_ok=True)
(env.home / "results" / "sweep" / "agreement.jsonl").write_text("", encoding="utf-8")
env.now = t("2026-11-04T02:00:00")                       # a weekday peak
O.cycle(env)
st = json.loads((env.home / "status.json").read_text(encoding="utf-8"))
check(st.get("peak") and not any(w.startswith("sweep") for w in st.get("waiting", [])),
      f"24: a finished pass is reported as waiting at peak: {st.get('waiting')}")
shutil.rmtree(tmp)

for f in fails:
    print("FAIL", f)
print(f"orchestrator: 24 acceptance tests; {len(fails)} failures")
sys.exit(1 if fails else 0)
