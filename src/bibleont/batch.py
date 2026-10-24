"""Anthropic's Message Batches API: half price, for work nobody is waiting on.

2026-09-01: batch submission was asked for -- and the word `batch` was
already taken in this project. Everywhere else it means a proposal directory:
one book's extraction, staged and awaiting merge. This is the other thing, and
the collision is worth naming once so nobody reads `bibleont.batch` expecting
`ontology/proposals/`.

**Half price, and that is the whole argument.** Every rate halves -- input,
output, cache write and cache read alike -- in exchange for giving up latency.
A batch is accepted immediately and returns whenever it returns; the
documented ceiling is 24 hours and the observed reality is usually minutes.

So the rule for when to use it is simple and it is about the caller, not the
job: **if something in this session is blocked on the answer, do not batch
it.** A supervisor deciding whether to stop a running farm is blocked. A
review of a document, a second opinion, a re-scoring of finished work and the
per-book grouping passes are not -- nobody is watching those, and paying twice
the price to have them sooner buys nothing.

## What this does not do

No cache control, no tools, no streaming, no partial retrieval. One system
prompt and one user message per request, a model per request, and the results
as text. That is what the two callers here need, and everything absent is
absent because guessing at it now would be designing for a caller that does
not exist.

**Requests in one batch may name different models**, which is the feature that
made this worth building today rather than later: two reviewers, blind to each
other, for less than one of them costs unbatched.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .providers import PROVIDERS, auth

# The batch endpoints, which are not under /messages despite what the shape of
# the API suggests.
_URL = "https://api.anthropic.com/v1/messages/batches"


@dataclass
class Result:
    custom_id: str
    kind: str                    # succeeded | errored | canceled | expired
    text: str
    usage: dict
    model: str

    @property
    def cost(self) -> float:
        """What this result cost, at the batch rate.

        `supervisor.price` prices a normal call. Batch halves every rate, so
        the discount is applied here rather than in the price table -- the
        table is shared with the interactive path, and a rate that is
        sometimes half is a rate nobody can reason about.
        """
        from .supervisor import price
        return price(self.usage, model=self.model) / 2


def _post(url: str, body: dict | None = None, method: str = "POST") -> dict:
    prov = PROVIDERS["anthropic"]
    if not prov.key:
        raise RuntimeError(f"no {prov.key_env} in the environment")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=auth(prov),
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as exc:
        # The body carries the reason and the status alone does not. An empty
        # Anthropic balance arrives as a 400 saying so in the body, and this
        # project has already lost an evening to reading the status only.
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from None


def model_family(model: str) -> str:
    """Which thinking dialect a model speaks.

    Not a version check. The 5-series takes adaptive thinking with an effort
    control; Haiku 4.5 takes an explicit token budget and refuses adaptive.
    Both refusals are hard 400s, so guessing costs a whole request.
    """
    return "adaptive" if re.search(r"(opus|sonnet|fable)-5", model) else "budget"


def submit(requests: list[dict], max_tokens: int = 8000) -> str:
    """Send a batch. Each request is {id, model, system, user}.

    Returns the batch id. Nothing is charged until results are produced, and a
    batch that is never fetched still ran -- so the id is the only thing worth
    keeping and it is printed as well as returned.

    THINKING IS ON UNLESS YOU TURN IT OFF, AND IT SPENDS `max_tokens`.

    The first batch this project ever sent asked three models for a report,
    gave each 10,000 tokens, and got three empty strings back for $0.4934.
    Every one of them reported `thinking_tokens: 10000` and
    `stop_reason: max_tokens`: the budget was gone before a single character
    of the answer was written.

    So a request carries an explicit `thinking`, and `max_tokens` is sized as
    **budget plus room for the answer**, never as the answer alone. Pass
    `{"type": "disabled"}` for work that does not need reasoning, or
    `{"type": "enabled", "budget_tokens": N}` with `max_tokens` comfortably
    above N.

    This failure was already written down. `reviewer.py` carries it in a
    comment -- *"the v4 models spend tokens reasoning before they emit
    content, and that spending counts against this limit"* -- and this module
    reproduced it at 10,000 tokens instead of 400, because a new path does not
    inherit the guards of the one it sits beside. That is the general lesson
    and it is worth more than the fix.
    """
    out = []
    for r in requests:
        params = {"model": r["model"],
                  "max_tokens": r.get("max_tokens", max_tokens),
                  "system": r["system"],
                  "messages": [{"role": "user", "content": r["user"]}]}
        think = r.get("thinking")
        if think is None:
            raise ValueError(
                f"request {r['id']!r}: `thinking` must be set explicitly. "
                "Left to the default it consumed every token of the first "
                "batch this project sent and returned nothing.")
        # THINKING IS CONFIGURED PER MODEL AND THE SHAPES ARE NOT INTERCHANGEABLE.
        #
        # The 5-series models take `{"type": "adaptive"}` and refuse
        # `enabled` with a budget -- "use thinking.type.adaptive and
        # output_config.effort". Haiku 4.5 is the mirror image: it refuses
        # adaptive outright with "adaptive thinking is not supported on this
        # model" and takes a budget. One benchmark request was lost to sending
        # every model the same block.
        #
        # So `thinking: "auto"` asks for whatever this model accepts, and a
        # caller comparing models across one batch does not have to know which
        # family each belongs to. An explicit dict is still passed straight
        # through for a caller that does.
        if think == "auto":
            if model_family(r["model"]) == "adaptive":
                params["thinking"] = {"type": "adaptive"}
                params.setdefault("output_config",
                                  {"effort": r.get("effort", "medium")})
            else:
                budget = min(4096, max(1024, params["max_tokens"] // 4))
                params["thinking"] = {"type": "enabled", "budget_tokens": budget}
        else:
            params["thinking"] = think
        # How much of the ceiling adaptive thinking is allowed to spend. The
        # 5-series models refuse `{"type": "enabled", "budget_tokens": N}`
        # outright -- "not supported for this model, use thinking.type.adaptive
        # and output_config.effort" -- so the budget is steered here or not at
        # all.
        if r.get("output_config"):
            params["output_config"] = r["output_config"]
        # Read the budget off what was RESOLVED, not off what was asked for.
        # `thinking: "auto"` is a string and the first version of this check
        # called .get on it.
        budget = (params.get("thinking") or {}).get("budget_tokens")
        if budget and params["max_tokens"] <= budget:
            raise ValueError(
                f"request {r['id']!r}: max_tokens {params['max_tokens']} "
                f"leaves nothing after a thinking budget of {budget}")
        out.append({"custom_id": r["id"], "params": params})
    return _post(_URL, {"requests": out})["id"]


def status(batch_id: str) -> dict:
    return _post(f"{_URL}/{batch_id}", method="GET")


def done(batch_id: str) -> bool:
    return status(batch_id).get("processing_status") == "ended"


def results(batch_id: str) -> list[Result]:
    """Fetch a finished batch. Results arrive as JSONL, one object per line."""
    info = status(batch_id)
    url = info.get("results_url")
    if not url:
        raise RuntimeError(
            f"batch {batch_id} is {info.get('processing_status')}, no results yet")
    prov = PROVIDERS["anthropic"]
    req = urllib.request.Request(url, headers=auth(prov))
    with urllib.request.urlopen(req, timeout=300) as r:
        body = r.read().decode("utf-8")

    out = []
    for line in body.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        res = row.get("result") or {}
        kind = res.get("type", "?")
        msg = res.get("message") or {}
        text = "".join(b.get("text", "") for b in (msg.get("content") or [])
                       if b.get("type") == "text")

        # A SUCCEEDED RESULT WITH NO TEXT IS A FAILURE, AND IT ARRIVES SILENTLY.
        #
        # The API is right to call it succeeded -- the model ran, the tokens
        # were spent, nothing errored. But it is not an answer, and the caller
        # that files it as one has paid full price for an empty file that
        # looks like a model with nothing to say. Zero is indistinguishable
        # from thrift, again, one layer up.
        stop = msg.get("stop_reason")
        if kind == "succeeded" and not text.strip():
            think = ((msg.get("usage") or {}).get("output_tokens_details")
                     or {}).get("thinking_tokens")
            kind = "empty"
            text = (f"NO TEXT RETURNED. stop_reason={stop}, "
                    f"thinking_tokens={think}, "
                    f"output_tokens={(msg.get('usage') or {}).get('output_tokens')}. "
                    "If thinking consumed the budget, raise max_tokens above "
                    "the thinking budget rather than raising the budget.")
        if kind not in ("succeeded", "empty"):
            # Say what went wrong in the text, so a caller that only reads
            # `text` cannot mistake a failure for an empty answer. Zero is
            # indistinguishable from thrift, and an empty string is
            # indistinguishable from a model with nothing to say.
            text = text or json.dumps(res.get("error") or res)[:500]
        out.append(Result(custom_id=row.get("custom_id", "?"), kind=kind,
                          text=text, usage=msg.get("usage") or {},
                          model=msg.get("model") or "?"))
    return out


def record(batch_id: str, rows: list[Result], note: str = "") -> float:
    """Write a finished batch's cost into the supervisor ledger.

    **A spending path the governor cannot see is not guarded.** The ledger
    tracked farm runs only, so an evening of batch work -- $3.26 across seven
    batches -- left no trace, and the guard that stops a run when the balance
    is low was reading a number that had not moved since yesterday. That is
    the same shape as the misrouted windows priced at $0.00: not an overspend,
    an unobserved spend, which is worse because nothing reports it.

    Called by the collectors rather than by `results`, so fetching a batch
    twice to re-read it does not double-count.
    """
    import json as _json
    from .paths import ROOT as _ROOT

    total = round(sum(r.cost for r in rows), 6)
    path = _ROOT / "ontology" / "proposals" / ".supervisor" / "ledger.json"
    if not path.exists():
        return total
    d = _json.loads(path.read_text(encoding="utf-8"))
    if any(r.get("batch") == batch_id for r in d.get("runs", [])):
        return total                                   # already recorded
    d["spent"] = round(d.get("spent", 0.0) + total, 6)
    d.setdefault("runs", []).append({
        "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "batch": batch_id, "requests": len(rows),
        "models": sorted({r.model for r in rows}),
        "spent": total, "note": note or "batch"})
    path.write_text(_json.dumps(d, indent=1), encoding="utf-8")
    return total


def wait(batch_id: str, every: int = 30, limit: int = 3600) -> list[Result]:
    """Poll until the batch ends, then fetch.

    `limit` is a wall-clock ceiling in seconds and defaults to an hour, which
    is well inside the documented 24 and well outside anything observed. It
    exists so an unattended caller stops rather than polls forever; the batch
    is unaffected and can still be fetched later by id.
    """
    deadline = time.time() + limit
    while time.time() < deadline:
        info = status(batch_id)
        if info.get("processing_status") == "ended":
            return results(batch_id)
        counts = info.get("request_counts") or {}
        print(f"  {info.get('processing_status')}  {counts}", flush=True)
        time.sleep(every)
    raise TimeoutError(f"batch {batch_id} still running after {limit}s; "
                       f"fetch it later with `python -m bibleont.batch fetch {batch_id}`")


def main(argv: list[str] | None = None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m bibleont.batch status|fetch|wait <id>")
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "status":
        print(json.dumps(status(rest[0]), indent=1))
        return 0
    if cmd in ("fetch", "wait"):
        rows = wait(rest[0]) if cmd == "wait" else results(rest[0])
        total = 0.0
        for r in rows:
            total += r.cost
            print(f"\n=== {r.custom_id}  [{r.kind}]  {r.model}  "
                  f"${r.cost:.4f}\n")
            print(r.text)
        print(f"\ntotal ${total:.4f} at the batch rate")
        return 0
    print(f"unknown command {cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
