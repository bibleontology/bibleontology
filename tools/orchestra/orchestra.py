"""The orchestrator: one cycle of the three tiers of checking.

The Mac's local model reads claims against Bible verses; DeepSeek reads the
claims it flagged, twice; disagreements are written for a human to read.  This
module only schedules.  It moves job files, calls the one proxy object it is
handed, and writes files under ``env.home``.  It never runs a command, never
imports subprocess/socket/urllib, and never opens a connection itself.

The interface and the rules are set out in tests/test_orchestrator.py.
Python 3.9, standard library only.
"""

import datetime as dt
import json
import random
import re
import shutil
from pathlib import Path

TARGET_QUEUE_HOURS = 12.0
MAX_QUEUE_HOURS = 24.0
CAP_MARGIN_USD = 0.05
MAX_FAILS = 2                     # failed calls on one batch run before it is filed as failed
LOCAL_MODEL = "gemma4:26b"      # the fast reader
CLOUD_MODEL = "qwen3.8:27b"     # the strong reader; local too, despite the name the worker gave it (kept: tests use it)
PEAK_WINDOWS = ((1, 4), (6, 10))
HOLDS = ("stated", "implied")
DEFAULT_FIELDS = ["id", "claim", "ref", "verse", "context"]


# ---------------------------------------------------------------- the world

class Env(object):
    """What the orchestrator is handed: folders, the clock, the proxy, rates."""

    def __init__(self, home=None, grunt=None, now=None, proxy=None, rates=None):
        self.home = Path(home) if home is not None else None
        self.grunt = Path(grunt) if grunt is not None else None
        self.now = now if now is not None else dt.datetime.now(dt.timezone.utc)
        self.proxy = proxy
        self.rates = dict(rates or {})


# --------------------------------------------------------------------- time

def _utc(t):
    """The moment as a UTC datetime; None means now."""
    if t is None:
        return dt.datetime.now(dt.timezone.utc)
    if getattr(t, "tzinfo", None) is None:
        return t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc)


def is_peak(t):
    """True inside a weekday peak window: 01:00-04:00 and 06:00-10:00 UTC."""
    t = _utc(t)
    if t.weekday() > 4:
        return False
    for start, end in PEAK_WINDOWS:
        if start <= t.hour < end:
            return True
    return False


def _window_of(t):
    for start, end in PEAK_WINDOWS:
        if start <= t.hour < end:
            return start, end
    return None


def _next_window_start(t):
    best = None
    for day in range(0, 8):
        when = (t + dt.timedelta(days=day)).date()
        if when.weekday() > 4:
            continue
        for start, _end in PEAK_WINDOWS:
            cand = dt.datetime.combine(when, dt.time(start, 0)).replace(tzinfo=dt.timezone.utc)
            if cand > t and (best is None or cand < best):
                best = cand
    return best


def _peak_need(now, margin=0.5, lookahead=2.0):
    """Hours that must be queued now to outlast the peak window.

    Inside a window: the hours left of it plus a margin.  Shortly before one
    begins: the whole window plus a margin.  Otherwise nothing extra.
    """
    t = _utc(now)
    window = _window_of(t)
    if window:
        end = t.replace(hour=window[1], minute=0, second=0, microsecond=0)
        return (end - t).total_seconds() / 3600.0 + margin
    nxt = _next_window_start(t)
    if nxt is None:
        return 0.0
    if (nxt - t).total_seconds() / 3600.0 > lookahead:
        return 0.0
    length = 3.0
    for start, end in PEAK_WINDOWS:
        if start == nxt.hour:
            length = float(end - start)
    return length + margin


# -------------------------------------------------------------------- paths

def safe_path(base, *parts):
    """The path base/parts, resolved; ValueError if it leaves base."""
    base = Path(base).resolve()
    pieces = []
    for part in parts:
        s = str(part)
        if not s:
            continue
        if Path(s).is_absolute() or s.startswith("~"):
            raise ValueError("path %r is outside %s" % (s, base))
        pieces.append(s)
    target = base
    for s in pieces:
        target = target / s
    target = target.resolve()
    if target != base and base not in target.parents:
        raise ValueError("path %s leaves %s" % (target, base))
    return target


# ------------------------------------------------------------------- fields

def reduce_item(item, allowed):
    """Only the allowed fields of item; ValueError if it carries another."""
    allowed_set = set(allowed or [])
    extra = sorted(k for k in item if k not in allowed_set)
    if extra:
        raise ValueError("item carries fields not allowed in a message: %s"
                         % ", ".join(str(k) for k in extra))
    return dict((k, item[k]) for k in item if k in allowed_set)


# -------------------------------------------------------------------- model

def _accuracy(entry):
    if not isinstance(entry, dict):
        return None
    value = entry.get("hard_acc")
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def choose_model(pass_spec, models):
    """The model for a job, from measurements; always with a reason."""
    spec = pass_spec or {}
    models = models or {}
    if not spec.get("reasoning"):
        model = LOCAL_MODEL
        why = "a simple job: the local model reads it"
    else:
        kind = spec.get("kind")
        table = models.get(kind) if kind else None
        gemma = table.get(LOCAL_MODEL) if isinstance(table, dict) else None
        qwen = table.get(CLOUD_MODEL) if isinstance(table, dict) else None
        gemma_acc = _accuracy(gemma)
        qwen_acc = _accuracy(qwen)
        if gemma_acc is not None and qwen_acc is not None and (qwen_acc - gemma_acc) >= 0.10:
            model = CLOUD_MODEL
            why = "measured on %s: %.2f on hard items against %.2f for %s" % (
                kind, qwen_acc, gemma_acc, LOCAL_MODEL)
        else:
            model = LOCAL_MODEL
            if kind and not isinstance(table, dict):
                why = "no measurements for %s yet: the local model" % kind
            else:
                why = ("no measured advantage of 0.10 or more for %s: the local model"
                       % CLOUD_MODEL)
    planned = spec.get("planned")
    if planned is None or not str(planned).strip():
        return model, why
    if planned == model:
        return model, why + "; as planned"
    return model, "%s; planned %s overruled" % (why, planned)


# --------------------------------------------------------------- small files

def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return None


def _loads_loose(text):
    """JSON from a string, tolerating prose or fences around the object."""
    if not isinstance(text, str):
        return None
    s = text.strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except ValueError:
        pass
    i, j = s.find("{"), s.rfind("}")
    if 0 <= i < j:
        try:
            return json.loads(s[i:j + 1])
        except ValueError:
            return None
    k, n = s.find("["), s.rfind("]")
    if 0 <= k < n:
        try:
            return json.loads(s[k:n + 1])
        except ValueError:
            return None
    return None


def _read_jsonl(path):
    rows = []
    try:
        f = open(path, "r", encoding="utf-8")
    except (IOError, OSError):
        return rows
    with f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = _loads_loose(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _call_count(path):
    """The calls a job makes: its lines after the header."""
    try:
        f = open(path, "r", encoding="utf-8")
    except (IOError, OSError):
        return 0
    n = 0
    with f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            if i == 0:
                head = _loads_loose(line)
                if isinstance(head, dict) and "_job" in head:
                    continue
            n += 1
    return n


def _job_model(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            first = f.readline()
    except (IOError, OSError):
        return None
    row = _loads_loose(first)
    if not isinstance(row, dict):
        return None
    head = row.get("_job")
    if isinstance(head, dict) and head.get("model"):
        return head.get("model")
    return row.get("model")


def _rate(env, model):
    rates = getattr(env, "rates", None) or {}
    try:
        rate = float(rates.get(model))
        if rate > 0:
            return rate
    except (TypeError, ValueError):
        pass
    known = []
    for value in rates.values():
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if value > 0:
            known.append(value)
    return min(known) if known else 20.0


def _done_marker(env, name):
    """grunt/done/<name>.complete (or <stem>.complete if that is what is there)."""
    base = str(name)
    stem = base[:-len(".jsonl")] if base.endswith(".jsonl") else base
    for cand in (stem + ".complete", base + ".complete"):
        try:
            path = safe_path(env.grunt, "done", cand)
        except ValueError:
            continue
        if path.exists():
            return path
    return safe_path(env.grunt, "done", stem + ".complete")


# -------------------------------------------------------------------- queue

def queue_hours(env):
    """Estimated hours of work in grunt/queue that is not yet done."""
    try:
        qdir = safe_path(env.grunt, "queue")
    except ValueError:
        return 0.0
    if not qdir.exists():
        return 0.0
    total = 0.0
    for path in sorted(qdir.glob("*.jsonl")):
        if _done_marker(env, path.name).exists():
            continue
        calls = _call_count(path)
        total += (calls / _rate(env, _job_model(path))) / 60.0
    return total


def _intake_candidates(env):
    try:
        idir = safe_path(env.home, "intake")
    except ValueError:
        return []
    if not idir.exists():
        return []
    out = []
    for path in sorted(idir.glob("*.pass.json")):
        name = path.name[:-len(".pass.json")]
        job = name + ".jsonl"
        try:
            job_path = safe_path(env.home, "intake", job)
        except ValueError:
            continue
        if not job_path.exists():
            continue
        spec = _load_json(path)
        if not isinstance(spec, dict):
            spec = {}
        try:
            priority = float(spec.get("priority") or 0)
        except (TypeError, ValueError):
            priority = 0.0
        out.append({
            "name": name,
            "job": job,
            "priority": priority,
            "spec": spec,
            "pass": spec.get("pass") or name,
        })
    return out


def fill_queue(env, target=None):
    """Move intake jobs into grunt/queue, highest priority first."""
    # below the target, top up to a day (MAX), as the design says; at or above it, leave the queue alone
    trigger = min(TARGET_QUEUE_HOURS if target is None else float(target), MAX_QUEUE_HOURS)
    moved = []
    if queue_hours(env) >= trigger:
        return moved
    limit = max(trigger, MAX_QUEUE_HOURS)
    while queue_hours(env) < limit:
        cands = _intake_candidates(env)
        if not cands:
            break
        cands.sort(key=lambda c: (-c["priority"], c["name"]))
        cand = cands[0]
        src = safe_path(env.home, "intake", cand["job"])
        qdir = safe_path(env.grunt, "queue")
        qdir.mkdir(parents=True, exist_ok=True)
        dst = safe_path(env.grunt, "queue", cand["job"])
        shutil.move(str(src), str(dst))
        spec = dict(cand["spec"])
        spec.setdefault("pass", cand["pass"])
        if not spec.get("mac_job"):
            spec["mac_job"] = cand["job"]
        pdir = safe_path(env.home, "passes", cand["pass"])
        pdir.mkdir(parents=True, exist_ok=True)
        safe_path(env.home, "passes", cand["pass"], "pass.json").write_text(
            json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        moved.append(cand["job"])
    return moved


# ------------------------------------------------------------------ answers

def _norm(value):
    if value is None:
        return None
    s = str(value).strip().lower()
    return s or None


def _content_dict(content):
    if isinstance(content, dict):
        return content
    if isinstance(content, list):
        for row in content:
            if isinstance(row, dict):
                return row
        return None
    if not isinstance(content, str):
        return None
    row = _loads_loose(content)
    return row if isinstance(row, dict) else None


def _mac_verdicts(env, mac_job):
    """key -> the Mac's verdict, from grunt/done/<mac_job>."""
    out = {}
    if not mac_job:
        return out
    try:
        path = safe_path(env.grunt, "done", mac_job)
    except ValueError:
        return out
    for row in _read_jsonl(path):
        key = row.get("key")
        if key is None:
            key = row.get("id")
        content = row.get("content")
        verdict = None
        parsed = _content_dict(content)
        if isinstance(parsed, dict):
            verdict = parsed.get("verdict")
        if verdict is None and isinstance(content, str):
            verdict = content
        out[str(key)] = _norm(verdict)
    return out


def _verdict_rows(content):
    """The id/verdict objects in one answer, tolerating junk lines."""
    if content is None:
        return []
    if isinstance(content, dict):
        inner = content.get("results")
        if isinstance(inner, list):
            return _verdict_rows(inner)
        return [content] if content.get("id") is not None else []
    if isinstance(content, (list, tuple)):
        return [row for row in content
                if isinstance(row, dict) and row.get("id") is not None]
    text = str(content)
    whole = _loads_loose(text)
    if isinstance(whole, (dict, list)):
        return _verdict_rows(whole)
    rows = []
    for line in text.splitlines():
        line = line.strip().strip(",")
        if not line:
            continue
        row = _loads_loose(line)
        if isinstance(row, dict) and row.get("id") is not None:
            rows.append(row)
    return rows


def _run_answers(env, name):
    """run index -> {id: verdict}, from results/<pass>/<batch>-run<N>.json."""
    answers = {}
    try:
        rdir = safe_path(env.home, "results", name)
    except ValueError:
        return answers
    if not rdir.exists():
        return answers
    for path in sorted(rdir.iterdir()):
        found = re.match(r"^(\d+)-run(\d+)\.json$", path.name)
        if not found:
            continue
        run = int(found.group(2))
        result = _load_json(path)
        if not isinstance(result, dict):
            continue
        table = answers.setdefault(run, {})
        for row in _verdict_rows(result.get("content")):
            table[str(row.get("id"))] = _norm(row.get("verdict"))
    return answers


def _holds(verdict):
    if verdict is None:
        return None
    return _norm(verdict) in HOLDS


def _category(mac_verdict, run_verdicts):
    mac = _holds(mac_verdict)
    runs = [_holds(v) for v in run_verdicts]
    if mac is True and runs and all(r is True for r in runs):
        return "agree-holds"
    if mac is False and runs and all(r is False for r in runs):
        return "agree-wrong"
    if len(runs) >= 2 and runs[0] is not runs[1]:
        return "unsettled"
    return "disagree"


# ------------------------------------------------------------------- passes

def _pass_spec(env, name):
    for rel in (("results", name, "meta.json"), ("passes", name, "pass.json")):
        try:
            path = safe_path(env.home, *rel)
        except ValueError:
            continue
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        inner = data.get("spec")
        spec = dict(inner) if isinstance(inner, dict) else dict(data)
        spec.setdefault("pass", name)
        return spec
    return {"pass": name}


def _pass_names(env):
    try:
        pdir = safe_path(env.home, "passes")
    except ValueError:
        return []
    if not pdir.exists():
        return []
    return sorted(p.name for p in pdir.iterdir() if p.is_dir())


def _brief(env, name, deep):
    try:
        path = safe_path(env.home, "passes", name, deep.get("brief") or "brief.md")
        return path.read_text(encoding="utf-8")
    except (IOError, OSError, ValueError):
        return ""


def _item_line(item):
    return "[%s] CLAIM: %s VERSE (%s): %s" % (
        item.get("id", ""), item.get("claim", ""),
        item.get("ref", ""), item.get("verse", ""))


def _spent(env, name):
    """What the pass has spent, from the costs its result files recorded."""
    total = 0.0
    try:
        rdir = safe_path(env.home, "results", name)
    except ValueError:
        return total
    if not rdir.exists():
        return total
    for path in sorted(rdir.glob("*.json")):
        result = _load_json(path)
        if not isinstance(result, dict) or "cost" not in result:
            continue
        try:
            total += float(result.get("cost") or 0.0)
        except (TypeError, ValueError):
            continue
    return total


def _budget_ok(env, spec, name):
    """True while the pass and the week both have room for one more call."""
    deep = spec.get("deepseek") or {}
    try:
        health = env.proxy.health()
    except Exception:
        return False
    if isinstance(health, dict):
        try:
            week = float(health.get("week_usd"))
        except (TypeError, ValueError):
            return False               # a spend it cannot read is not zero
        # a health answer without a readable cap stops it: the cap is never skipped (Claude's read, 2026-11-02)
        try:
            if float(health.get("cap")) - week <= CAP_MARGIN_USD:
                return False
        except (TypeError, ValueError):
            return False
    else:
        return False
    budget = deep.get("budget_usd")
    if budget is not None:
        try:
            if _spent(env, name) >= float(budget):
                return False
        except (TypeError, ValueError):
            pass
    return True


def _spread(items, plants, seed):
    """The plants spread through the items, one in each equal stretch at a seeded place. Appended after the items
    (to 2026-11-04) they filled the last batch: 10 of the 16-psalm-headings pass's 12 plants were in one batch, which
    a reader could tell from the rest and which scored nothing about the batches the real items were in. Seeded by
    the pass's name, so every cycle sends the same order and a pass resumed part-way keeps its batches."""
    if not plants or not items:
        return list(items) + list(plants)
    rng = random.Random(seed)
    stride = float(len(items) + len(plants)) / len(plants)
    slots = set()
    for i in range(len(plants)):
        slots.add(min(int(i * stride + rng.random() * stride), len(items) + len(plants) - 1))
    while len(slots) < len(plants):                      # a collision at a stretch's edge: the next free place
        slots.add(min(set(range(len(items) + len(plants))) - slots))
    out, it, pl = [], iter(items), iter(plants)
    for pos in range(len(items) + len(plants)):
        out.append(next(pl) if pos in slots else next(it))
    return out


def _payload(env, name, spec, deep, allowed):
    """The items to send: those the Mac flagged, with the plants spread among them."""
    mac = _mac_verdicts(env, spec.get("mac_job") or (name + ".jsonl"))
    flag_in = set((spec.get("flag") or {}).get("verdict_in") or [])
    out = []
    items = _read_jsonl(safe_path(env.home, "passes", name, "items.jsonl"))
    for item in items:
        key = item.get("key")
        if key is None:
            key = item.get("id")
        if str(key) not in mac or mac[str(key)] not in flag_in:
            continue
        row = dict(item)
        row.pop("key", None)
        out.append(reduce_item(row, allowed))
    plants = _read_jsonl(safe_path(env.home, "passes", name,
                                   deep.get("planted") or "planted.jsonl"))
    sent = []
    for plant in plants:
        row = dict(plant)
        row.pop("expect", None)
        row.pop("key", None)
        sent.append(reduce_item(row, allowed))
    return _spread(out, sent, name)


def second_pass(env, pass_spec):
    """Let DeepSeek read the flagged items and the plants, twice."""
    spec = dict(pass_spec or {})
    name = spec.get("pass") or spec.get("name") or "pass"
    deep = spec.get("deepseek") or {}

    if deep.get("thinking") and not deep.get("thinking_approved"):
        return "refused: thinking without Doug's approval"
    if is_peak(env.now) and not spec.get("urgent"):
        return "held: peak"

    allowed = spec.get("allowed_fields") or DEFAULT_FIELDS
    try:
        payload = _payload(env, name, spec, deep, allowed)
    except ValueError as exc:
        return "refused: %s" % exc

    runs = int(deep.get("runs") or 2)
    if runs < 1:
        runs = 1
    size = int(deep.get("batch") or 36)
    if size < 1:
        size = 36
    brief = _brief(env, name, deep)

    rdir = safe_path(env.home, "results", name)
    rdir.mkdir(parents=True, exist_ok=True)
    safe_path(env.home, "results", name, "meta.json").write_text(
        json.dumps({"pass": name, "spec": spec}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")

    batches = [payload[i:i + size] for i in range(0, len(payload), size)]
    for index, batch in enumerate(batches):
        body = "\n".join(_item_line(item) for item in batch)
        for run in range(runs):
            out = safe_path(env.home, "results", name,
                            "%d-run%d.json" % (index, run))
            if out.exists():
                continue
            if not _budget_ok(env, spec, name):
                return "waiting for budget"
            messages = [
                {"role": "system", "content": brief},
                {"role": "user", "content": body},
            ]
            # one proxy job per batch run, so the proxy's per-job caps bind each call, not the whole pass
            # A failed call may already be billed (the security seat, 2026-11-03): it is counted in <out>.fail, and
            # after MAX_FAILS the batch run is filed empty and marked failed, so it is never retried without end.
            fail = safe_path(env.home, "results", name, "%d-run%d.fail" % (index, run))
            try:
                answer = env.proxy.chat(job="orch-%s-%d-run%d" % (name, index, run), messages=messages,
                                        thinking=False)
            except Exception as exc:                      # noqa: BLE001
                try:
                    count = int(fail.read_text(encoding="utf-8").split()[0]) + 1
                except (OSError, ValueError, IndexError):
                    count = 1
                fail.write_text("%d %s\n" % (count, type(exc).__name__), encoding="utf-8")
                if count < MAX_FAILS:
                    return "call failed (%d of %d): %s" % (count, MAX_FAILS, type(exc).__name__)
                out.write_text(json.dumps({"batch": index, "run": run, "pass": name, "content": "",
                                           "cost": 0.0, "failed": True}) + "\n", encoding="utf-8")
                continue
            content = ""
            cost = 0.0
            if isinstance(answer, dict):
                content = answer.get("content") or ""
                try:
                    cost = float(answer.get("cost") or 0.0)
                except (TypeError, ValueError):
                    cost = 0.0
            elif answer is not None:
                content = str(answer)
            out.write_text(json.dumps({"batch": index, "run": run, "pass": name,
                                       "content": content, "cost": cost}) + "\n",
                           encoding="utf-8")
    return "done"


def agreement(env, pass_name):
    """Write what the three readings agreed on; score the plants."""
    name = pass_name
    spec = _pass_spec(env, name)
    deep = spec.get("deepseek") or {}
    runs = int(deep.get("runs") or 2)
    if runs < 1:
        runs = 1
    mac = _mac_verdicts(env, spec.get("mac_job") or (name + ".jsonl"))
    answers = _run_answers(env, name)

    counts = {"agree-holds": 0, "agree-wrong": 0, "disagree": 0, "unsettled": 0}
    rows = []
    items = _read_jsonl(safe_path(env.home, "passes", name, "items.jsonl"))
    for item in items:
        key = item.get("key")
        if key is None:
            key = item.get("id")
        ident = item.get("id")
        mac_verdict = mac.get(str(key)) if key is not None else None
        seen = [answers.get(run, {}).get(str(ident)) for run in range(runs)]
        # an item the Mac passed was never sent: it is the Mac's reading alone, not a disagreement (Claude's read,
        # 2026-11-02: unflagged items had filled "disagree", thousands on a full sweep)
        if all(v is None for v in seen):
            category = "mac-only"
            counts["mac-only"] = counts.get("mac-only", 0)
        else:
            category = _category(mac_verdict, seen)
        counts[category] += 1
        rows.append({"key": key, "id": ident, "mac": mac_verdict,
                     "runs": seen, "category": category})

    rdir = safe_path(env.home, "results", name)
    rdir.mkdir(parents=True, exist_ok=True)
    with open(safe_path(env.home, "results", name, "agreement.jsonl"),
              "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    plants = _read_jsonl(safe_path(env.home, "passes", name,
                                   deep.get("planted") or "planted.jsonl"))
    answered = 0
    right = 0
    for plant in plants:
        ident = str(plant.get("id"))
        expect = _norm(plant.get("expect"))
        seen = [answers.get(run, {}).get(ident) for run in range(runs)]
        seen = [v for v in seen if v is not None]
        if not seen:
            continue
        answered += 1
        if len(seen) == runs and all(v == expect for v in seen):
            right += 1

    try:
        floor = float(deep.get("planted_floor"))
    except (TypeError, ValueError):
        floor = 0.85
    share = (float(right) / answered) if answered else 0.0

    out = dict(counts)
    out.update({
        "items": len(rows),
        "plants": len(plants),
        "plants_answered": answered,
        "plants_right": right,
        "planted_share": round(share, 4),
        "trusted": bool(answered and share >= floor),
    })
    return out


# -------------------------------------------------------------------- cycle

def _write_today(env, status):
    now = _utc(env.now).strftime("%Y-%m-%d %H:%M")
    lines = ["# Today, orchestra", "",
             "- Now: %s UTC" % now,
             "- Peak: %s" % ("yes" if status.get("peak") else "no"),
             "- Queued: %.1f h" % status.get("queue_hours", 0.0),
             "- Cost this cycle: $%.4f" % status.get("cost_usd", 0.0),
             "", "## Ran"]
    if status.get("ran"):
        for item in status["ran"]:
            lines.append("- " + item)
    else:
        lines.append("- nothing")
    lines.append("")
    lines.append("## Waiting")
    if status.get("waiting"):
        for item in status["waiting"]:
            lines.append("- " + item)
    else:
        lines.append("- nothing")
    safe_path(env.home, "today.md").write_text("\n".join(lines) + "\n",
                                              encoding="utf-8")


def cycle(env):
    """One full cycle: keep the queue ready, run what may run, report."""
    ran = []
    waiting = []
    cost = 0.0

    need = _peak_need(env.now)
    target = need if need > TARGET_QUEUE_HOURS else TARGET_QUEUE_HOURS
    try:
        moved = fill_queue(env, target)
    except ValueError:
        moved = []
    if moved:
        ran.append("queued " + ", ".join(moved))

    at_peak = is_peak(env.now)
    for name in _pass_names(env):
        spec = _pass_spec(env, name)
        mac_job = spec.get("mac_job") or (name + ".jsonl")
        try:
            done = _done_marker(env, mac_job).exists()
        except ValueError:
            done = False
        if not done:
            continue
        # finished before peak: a finished pass was listed as "held: peak" (16-psalm-headings, 2026-11-04)
        try:
            finished = safe_path(env.home, "results", name, "agreement.jsonl").exists()
        except ValueError:
            finished = False
        if finished:
            continue
        if at_peak:
            if not spec.get("urgent"):
                waiting.append("%s: held: peak" % name)
            continue
        before = _spent(env, name)
        # one bad pass never stops the others (the security seat, 2026-11-03)
        try:
            result = second_pass(env, spec)
        except Exception as exc:                          # noqa: BLE001
            waiting.append("%s: error %s" % (name, type(exc).__name__))
            continue
        cost += max(0.0, _spent(env, name) - before)
        if result == "done":
            counts = agreement(env, name)
            ran.append("second pass %s: %d items, %d plants, trusted=%s"
                       % (name, counts.get("items", 0), counts.get("plants", 0),
                          counts.get("trusted")))
        else:
            waiting.append("%s: %s" % (name, result))

    status = {
        "ran": ran,
        "cost_usd": round(cost, 6),
        "waiting": waiting,
        "now": _utc(env.now).isoformat(),
        "queue_hours": round(queue_hours(env), 2),
        "peak": at_peak,
    }
    safe_path(env.home, "status.json").write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_today(env, status)
