"""Running the standing reviewer against an API.

Pass one, as described in `docs/REVIEWER.md`. This module builds the prompt,
sends it, and writes verdicts in the shape `bibleont.review score` reads.

## What it is careful about

**No key, no call.** The endpoint and key come from the environment, and
without them `--dry` is the only thing that runs. Nothing here can spend money
by accident.

**One relation per request.** Batching would be cheaper and it would also let
one bad judgement contaminate the next, because a model that has just flagged
three things is more likely to flag a fourth. The checks are independent and
the requests should be too.

**The verses go in full.** A reviewer asked whether a quote supports a claim,
without the verse in front of it, is being asked to recall rather than read --
which is the one thing it is worst at, and the failure would look exactly like
success.

**The scoring is disclosed, both halves of it.** Telling a reviewer it is
measured on catching problems produces a reviewer that flags everything; we
measured that and it scores 100% recall at 28.6% precision. So the prompt says
it is scored on precision as well, and that an unquoted flag is discarded
unread. Whether disclosure helps at all is an open question with a cheap
answer -- run the answer key with `--no-disclose` and compare.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from bibleont.paths import ROOT
from bibleont.review import load_cases, as_prompt

ENDPOINT = os.environ.get("BIBLEONT_REVIEW_URL", "https://api.deepseek.com/chat/completions")
# deepseek-flash (DeepSeek-V4.1-Flash) is the cheap tier as of the pricing page
# read 25 Sep 2026; "deepseek-v4-flash" is a legacy name it still serves. Use
# the documented one so the run log's model_returned means something.
MODEL = os.environ.get("BIBLEONT_REVIEW_MODEL", "deepseek-flash")
KEY = os.environ.get("BIBLEONT_REVIEW_KEY", "")

# Extended reasoning, off by default and deliberately so. Reasoning tokens
# bill as output, which is the dearest rate, and this task is a fixed
# checklist rather than a problem to work through. But "is this quote evidence
# or illustration" is the one check where thinking might genuinely help, and
# the answer key can settle it for a fraction of a cent -- so it is one
# variable away rather than a code change.
#
#   BIBLEONT_REVIEW_THINKING=high   (or low / medium)
THINKING = os.environ.get("BIBLEONT_REVIEW_THINKING", "").strip().lower()

CHECKS = """\
1. EVIDENCE OR ILLUSTRATION. Does the quoted verse support THIS claim -- that
   this source stands in this relation to this target -- or is it quoted to
   describe, illustrate, or add colour? Answer bad when the verse would be
   just as quotable on a dozen unrelated relations.

2. INTENT ASSERTED. Does the note say what a writer MEANT, INTENDED, or was
   TRYING TO DO, rather than reporting what the text says? Words like
   "deliberately", "in order to", "the point being", "clearly means".

3. NOT VERBATIM. Does the note put quotation marks around words the cited
   verses do not contain in that order? Compression counts: if the words are
   all present but separated by other words, the quotation marks are wrong.

5. CERTAINTY OVERSTATED. Is this marked "explicit" when the cited verses name
   only one of the two ends, or when the connection depends on a step the note
   has to explain?

6. ATTRIBUTE LEAK. When several verses are cited, does the claim hold in EACH
   of them, or only in one?
"""

SYSTEM = """\
You are the first-pass reviewer for a citation-backed Biblical knowledge graph.

Your job is NOT to decide what enters the graph. A person does that. Your job
is to flag the specific ways this graph has gone wrong before, so that person's
attention goes to the hard cases instead of the plainly broken ones.

Apply ONLY these checks:

{checks}
Answer with a single JSON object and nothing else:

  {{"verdict": "bad" | "good" | "unsure", "check": <number or null>,
    "why": "<one sentence>", "quote": "<the words from the note or verse that decide it>"}}

Rules that matter more than being helpful:

- If nothing on the list is wrong, answer "good". Most relations are sound.
- QUOTE THE WORDS THAT DECIDE IT. A flag with an empty quote is discarded
  unread, and counts against you exactly as a miss does.
- Do not flag a relation for being uninteresting, incomplete, or for a reading
  you would have made differently. Only the checks above.
{scoring}"""

DISCLOSURE = """
You are scored against cases whose correct answers are already known, on BOTH
recall (of the known-bad, how many you caught) and precision (of what you
flagged, how much deserved it). Flagging everything scores 100% recall and is
worthless -- it has been measured, at 28.6% precision. Passing everything
scores zero. Neither is reading.
"""


def build(case: dict, disclose: bool = True) -> tuple[str, str]:
    system = SYSTEM.format(checks=CHECKS,
                           scoring=DISCLOSURE if disclose else "")
    return system, as_prompt(case)


class ReplyError(RuntimeError):
    """A reply that could not be parsed, carrying the envelope that explains why.

    Discarding the envelope on failure throws away the diagnosis: an empty
    content field with finish_reason "length" and a large reasoning_len says
    the budget was spent thinking, which reads identically to "the model
    returned nothing" if only the exception text survives.
    """

    def __init__(self, message: str, raw: dict | None = None):
        super().__init__(message)
        self.raw = raw or {}


def quote_is_real(case: dict, quote: str) -> bool | None:
    """Did the reviewer quote something it was actually shown?

    The strongest signal available about whether a verdict was read or
    invented, and it costs nothing. A reviewer is given exactly two bodies of
    text -- the note and the cited verses -- so a quotation from neither was
    produced rather than found.

    Returns None when there is no quote to check, which is its own finding and
    is counted separately.
    """
    q = _flat(quote)
    if len(q) < 8:
        return None
    hay = _flat(case.get("note", "") + " " + " ".join(case.get("verses", {}).values()))
    return q in hay


def _flat(text: str) -> str:
    import re
    text = str(text).lower().replace("æ", "ae").replace("œ", "oe")
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text).split())


def ask(system: str, user: str, timeout: int = 60,
        max_tokens: int | None = None) -> dict:
    # Resolved per call rather than at import, so BIBLEONT_PROVIDER can be set
    # in the same shell that runs the command. With it unset this is DeepSeek
    # and every value below is what it always was.
    from bibleont.providers import current as _provider

    prov = _provider()
    endpoint = os.environ.get("BIBLEONT_REVIEW_URL") or prov.chat_url
    model = prov.model
    key = prov.key
    if not key and getattr(prov, "needs_key", True):
        raise RuntimeError(f"no {prov.key_env} in the environment")
    key = key or "local"
    if not model:
        raise RuntimeError(
            f"no model set for {prov.name}: {prov.model_env} must name one "
            f"(python -m bibleont.providers models)")
    payload_out = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0,
        # Room for the JSON reply, and for reasoning tokens when thinking is
        # on -- those count against this limit, and a truncated reply is
        # reported by `review diagnose` as finish_reason rather than passing
        # silently as a malformed verdict.
        # The v4 models spend tokens reasoning before they emit content, and
        # that spending counts against this limit whether or not thinking is
        # asked for. At 400 the budget was gone before a reply began: eleven
        # of fifteen came back with content empty or cut mid-string.
        "max_tokens": max_tokens or (12000 if THINKING else 8000),
        # It produced '"quote": "one" "two"' -- two adjacent JSON strings,
        # which is invalid and which instructions do not reliably prevent.
        # Constrained decoding does.
        "response_format": {"type": "json_object"},
    }
    # Only where the provider has the parameters. An endpoint that has never
    # heard of `reasoning_effort` answers 400, not a polite ignore.
    if THINKING and prov.thinking:
        payload_out["reasoning_effort"] = THINKING
        payload_out["thinking"] = {"type": "enabled"}
    from bibleont.providers import HEADERS as _H

    # Anthropic's Messages API is a different shape from the OpenAI one every
    # other provider here serves, and the differences are not cosmetic:
    #
    #   auth      x-api-key, not Authorization: Bearer
    #   version   an anthropic-version header, required
    #   system    a TOP-LEVEL parameter -- there is no "system" role
    #   json      no response_format; the fence-stripping below handles it
    #   sampling  temperature/top_p are deprecated, and conflict with thinking
    #
    # Sent as a TextBlockParam with cache_control so the supervisor's rubric
    # -- which is identical on every review -- is cached rather than re-read
    # at full price each time. The one-hour TTL outlives a night's run.
    if getattr(prov, "wire", "openai") == "anthropic":
        payload_out = {
            "model": model,
            "max_tokens": max_tokens or (12000 if THINKING else 8000),
            "system": [{"type": "text", "text": system,
                        "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
            "messages": [{"role": "user", "content": user}],
        }
        if THINKING and prov.thinking:
            payload_out["thinking"] = {"type": "adaptive"}
        headers = dict(_H)
        headers.pop("Authorization", None)
        headers["x-api-key"] = key
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers = dict(_H, Authorization=f"Bearer {key}")

    body = json.dumps(payload_out).encode()
    req = urllib.request.Request(endpoint, data=body, headers=headers)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload = json.loads(r.read())
    elapsed = round(time.time() - t0, 2)

    if getattr(prov, "wire", "openai") == "anthropic":
        # `content` is a list of blocks and the first is not necessarily the
        # answer: with thinking on, a thinking block comes first. Taking
        # content[0] would hand back reasoning as though it were the reply.
        blocks = payload.get("content") or []
        text = "".join(b.get("text", "") for b in blocks
                       if b.get("type") == "text").strip()
        finish = payload.get("stop_reason")
    else:
        text = payload["choices"][0]["message"]["content"].strip()
        finish = (payload.get("choices") or [{}])[0].get("finish_reason")

    raw = {
        "latency_s": elapsed,
        "model_returned": payload.get("model"),
        "usage": payload.get("usage"),
        "finish_reason": finish,
        "thinking": THINKING or None,
        "content": text,
    }
    # Models wrap JSON in fences no matter how firmly asked not to.
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ReplyError(f"no JSON object in reply: {text[:120]}", raw)
    try:
        return json.loads(text[start:end + 1]), raw
    except json.JSONDecodeError as exc:
        raise ReplyError(f"malformed JSON: {exc}", raw) from exc


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dry = "--dry" in argv
    disclose = "--no-disclose" not in argv
    out = Path("verdicts.jsonl")
    for a in argv:
        if a.startswith("--out="):
            out = Path(a.split("=", 1)[1])

    cases = load_cases()
    if not cases:
        print("no answer key; build it first")
        return 1

    if dry:
        system, user = build(cases[0], disclose)
        print("=" * 72)
        print("SYSTEM")
        print("=" * 72)
        print(system)
        print("=" * 72)
        print(f"USER  (1 of {len(cases)})")
        print("=" * 72)
        print(user)
        print()
        print(f"disclosure: {'on' if disclose else 'off'}   "
              f"model: {MODEL}   thinking: {THINKING or 'off'}   "
              f"key: {'set' if KEY else 'NOT SET'}")
        return 0

    if not KEY:
        print("BIBLEONT_REVIEW_KEY is not set. Nothing was sent.")
        print("Run with --dry to see exactly what would be.")
        return 1

    results, failed, log = [], 0, []
    for i, c in enumerate(cases, 1):
        system, user = build(c, disclose)
        try:
            v, raw = ask(system, user)
        except Exception as exc:
            raw = getattr(exc, "raw", {}) or {}
            print(f"  {i:3}/{len(cases)}  {c['id'][:44]:46} ERROR {str(exc)[:44]}"
                  f"  [{raw.get('finish_reason')}, "
                  f"reasoning {raw.get('reasoning_tokens', '?')} tok]")
            log.append({"id": c["id"], "expected": c.get("expected"),
                        "error": str(exc)[:300], **raw})
            failed += 1
            continue
        v["id"] = c["id"]
        results.append(v)

        # Everything needed to judge the reviewer rather than its verdict.
        log.append({
            "id": c["id"],
            "expected": c.get("expected"),
            "expected_check": c.get("check"),
            "verdict": v.get("verdict"),
            "check": v.get("check"),
            "why": v.get("why"),
            "quote": v.get("quote"),
            "quote_is_real": quote_is_real(c, v.get("quote", "")),
            "disclosed": disclose,
            **raw,
        })

        mark = v.get("verdict", "?")
        fab = "" if quote_is_real(c, v.get("quote", "")) is not False else "  QUOTE NOT IN SOURCE"
        print(f"  {i:3}/{len(cases)}  {c['id'][:44]:46} {mark:6} "
              f"check {str(v.get('check')):4} {raw['latency_s']:5.2f}s{fab}")
        time.sleep(0.2)

    with out.open("w", encoding="utf-8", newline="") as fh:
        for v in results:
            fh.write(json.dumps(v, ensure_ascii=False) + "\n")

    # Every call, including the ones that failed to parse. This is the half
    # that says whether the reviewer is reading rather than whether it was
    # right, and a failed call is the most informative row in it.
    runs = ROOT / "ontology" / "proposals" / ".runs"
    runs.mkdir(parents=True, exist_ok=True)
    logpath = runs / f"{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    with logpath.open("w", encoding="utf-8", newline="") as fh:
        for row in log:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\n{len(results)} verdicts -> {out}"
          + (f"   ({failed} failed)" if failed else ""))
    print(f"run log      -> {logpath.relative_to(ROOT)}")
    print(f"score with:  python -m bibleont.review score {out}")
    print(f"diagnose:    python -m bibleont.review diagnose "
          f"{logpath.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
