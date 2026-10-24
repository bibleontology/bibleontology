"""What a Gemini run actually cost, counted rather than estimated.

2026-09-13, looking at $4.49 against a $10 cap after jobs I had costed at
about a dollar, the question was what explained the $4 spend.

I had three theories and no data, which is the wrong way round for this project.
Every response carries `usage_metadata` with exact counts, including the
**thinking tokens** that bill at the OUTPUT rate and that I had left out of every
estimate entirely. A model that deliberates for three hundred tokens before
emitting a twenty-token answer costs an order of magnitude more than the visible
answer suggests.

So a run now reports what it spent, and says which model actually served it --
`gemini-flash-latest` is an alias and the resolved version is the thing worth
recording.

## Thinking is off by default here

For an extraction task -- *copy the span of this verse that renders this
phrase* -- deliberation buys nothing and is billed at the output rate. `--think`
turns it back on for tasks where judgment genuinely helps, which is the stamping
job rather than these.
"""
from __future__ import annotations

import collections
import threading

# Published rates per 1M tokens, standard (not batch). Thinking bills as output.
# Used only to ESTIMATE from measured counts; the counts are the real output.
RATES = {
    "gemini-3.8-flash": (0.75, 3.75), "gemini-3.7-flash": (0.75, 3.75),
    "gemini-3.6-flash": (0.75, 3.75), "gemini-3.5-flash": (1.50, 9.00),
    "gemini-2.5-flash": (0.30, 2.50), "gemini-2.5-pro": (1.25, 10.00),
    "gemini-3.1-pro": (2.00, 12.00),
}
_DEFAULT = (0.75, 3.75)


class Usage:
    """Thread-safe accumulator. Feed it every response; ask it at the end."""

    def __init__(self):
        self.lock = threading.Lock()
        self.calls = 0
        self.prompt = 0
        self.output = 0
        self.thoughts = 0
        self.models = collections.Counter()

    def add(self, resp):
        m = getattr(resp, "usage_metadata", None)
        if m is None:
            return
        with self.lock:
            self.calls += 1
            self.prompt += getattr(m, "prompt_token_count", 0) or 0
            self.output += getattr(m, "candidates_token_count", 0) or 0
            self.thoughts += getattr(m, "thoughts_token_count", 0) or 0
            v = getattr(resp, "model_version", None)
            if v:
                self.models[v] += 1

    def rate(self):
        for name in self.models:
            for k, v in RATES.items():
                if k in (name or ""):
                    return v, k
        return _DEFAULT, "assumed 3.8-flash"

    def report(self):
        (pin, pout), which = self.rate()
        billed_out = self.output + self.thoughts
        cost = self.prompt / 1e6 * pin + billed_out / 1e6 * pout
        L = [f"\nUSAGE  {self.calls:,} calls"]
        if self.models:
            L.append("  served by: " + ", ".join(
                f"{k} x{v:,}" for k, v in self.models.most_common(3)))
        L.append(f"  prompt   {self.prompt:>10,}")
        L.append(f"  output   {self.output:>10,}")
        L.append(f"  thinking {self.thoughts:>10,}"
                 + ("   <- billed as output" if self.thoughts else "   (off)"))
        if self.calls:
            L.append(f"  per call: {self.prompt//self.calls:,} in, "
                     f"{billed_out//self.calls:,} billed out")
        L.append(f"  ESTIMATED ${cost:.2f}   at {which} standard rates")
        return "\n".join(L)


def config(think=False):
    """Request config with thinking OFF unless asked for. None if unsupported."""
    try:
        from google.genai import types
        if think:
            return None
        return types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0))
    except Exception:                                          # noqa: BLE001
        return None
