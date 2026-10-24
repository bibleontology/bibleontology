"""Which API the workers talk to, and what differs between them.

The reviewer was written against DeepSeek and its endpoint, model and key were
already environment variables, so pointing it elsewhere was nearly possible
already. Three things stopped it being actually possible, and they are the
three things this module holds.

**Parameters one provider accepts and another rejects.** DeepSeek's extended
reasoning is asked for with `reasoning_effort` and `thinking`. Sending those to
an OpenAI-compatible endpoint that has never heard of them is a 400, not a
polite ignore.

**Rates.** DeepSeek's are per-million and asymmetric between a cached and an
uncached input token. A free tier's are zero, and a run against it should say
zero rather than quietly reporting DeepSeek's arithmetic over someone else's
tokens.

**How a cached token is reported.** DeepSeek returns
`prompt_cache_hit_tokens`; the OpenAI-compatible convention is
`prompt_tokens_details.cached_tokens`; a provider that does not cache reports
neither. This matters more than it sounds. The whole prompt design rests on a
15,000-token prefix being cached -- if it is not, the economics invert and the
right design is the per-verse lookup that was discarded for being worse. So
`cached_tokens()` reads both conventions and returns None when it cannot tell,
and None is a finding rather than a zero.

## What is deliberately not here

Model names for providers other than DeepSeek. A catalogue changes faster than
this file would be updated, and a wrong default that looks authoritative is
worse than no default -- it produces a 404 that reads like a broken key. Ask
the provider instead: `python -m bibleont.providers models`.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field


# urllib identifies itself as "Python-urllib/3.13" and Groq's endpoint sits
# behind a browser-integrity filter that answers that with HTTP 403, Cloudflare
# error 1010. Naming the client honestly is what every vendor SDK does and is
# what the filter is asking for; it is not a browser string and does not
# pretend to be one.
UA = "bibleont/1.0 (+https://bibleontology.org) python-urllib"

HEADERS = {"Content-Type": "application/json", "User-Agent": UA,
           "Accept": "application/json"}


def auth(provider: "Provider") -> dict:
    """Headers that will authenticate against this provider.

    Anthropic uses an `x-api-key` header and requires an API version, rather
    than the bearer token every other provider here takes. Kept in one place
    so `models`, `probe` and anything else added later get it right without
    each remembering.
    """
    if getattr(provider, "wire", "openai") == "anthropic":
        return dict(HEADERS, **{"x-api-key": provider.key,
                                "anthropic-version": "2023-06-01"})
    return dict(HEADERS, Authorization=f"Bearer {provider.key}")


# The OS keystore -- Credential Manager on Windows, Keychain on macOS, Secret
# Service on Linux -- reached through `keyring`, which is optional. Absent, the
# environment still works exactly as before.
KEYSTORE_SERVICE = "bibleont"


def from_keystore(provider_name: str) -> str:
    """The stored key for a provider, or "" for any reason at all.

    Deliberately silent. A missing keystore, an absent entry and a locked
    keychain are all "no key here", and the caller's job is to say which
    variable to set -- not to explain a dependency the user may never have
    wanted.
    """
    try:
        import keyring
    except ImportError:
        return ""
    try:
        return keyring.get_password(KEYSTORE_SERVICE, provider_name) or ""
    except Exception:                               # noqa: BLE001
        return ""


def to_keystore(provider_name: str, secret: str) -> None:
    import keyring
    keyring.set_password(KEYSTORE_SERVICE, provider_name, secret)


@dataclass(frozen=True)
class Provider:
    name: str
    base: str                      # up to and including /v1 or equivalent
    key_env: str
    model_env: str
    default_model: str = ""        # empty means: the user must name one
    thinking: bool = False         # accepts reasoning_effort / thinking
    # USD per million tokens, (off-peak, peak). None = free tier / unmetered.
    rates: dict | None = None
    notes: str = ""

    # Anthropic speaks its own shape rather than the OpenAI one every other
    # provider here happens to serve. Kept as a flag rather than a subclass
    # because exactly one thing branches on it and a subclass would hide that.
    wire: str = "openai"

    # A local server wants no auth. Everything else does, and the
    # check that enforces that has caught a missing key more than
    # once, so it is relaxed per provider rather than removed.
    needs_key: bool = True

    @property
    def chat_url(self) -> str:
        if self.wire == "anthropic":
            return self.base.rstrip("/") + "/messages"
        return self.base.rstrip("/") + "/chat/completions"

    @property
    def models_url(self) -> str:
        return self.base.rstrip("/") + "/models"

    @property
    def key(self) -> str:
        """The environment first, then the OS keystore.

        The environment wins so that a one-off run against a different key is
        still a one-liner, and so that CI or a container needs no keystore at
        all. The keystore is the convenience: set once, works in every future
        shell, and survives the terminal being closed.

        It is also the safer of the two persistent options. Making the
        variable permanent with `SetEnvironmentVariable(..., "User")` writes
        the key into the registry in plain text; the keystore holds it
        encrypted under DPAPI against this Windows account.

        Neither protects against a process already running as this user --
        that is not what either is for.
        """
        env = os.environ.get(self.key_env, "")
        if env:
            return env
        return from_keystore(self.name)

    @property
    def model(self) -> str:
        return os.environ.get(self.model_env, "") or self.default_model


LOCAL = Provider(
    name="local",
    # Ollama serves an OpenAI-shaped /v1/chat/completions, so nothing in
    # `reviewer.ask` has to change -- the wire is the same one every provider
    # here speaks except Anthropic.
    base="http://127.0.0.1:11434/v1",
    key_env="BIBLEONT_LOCAL_KEY",          # unused; Ollama wants no auth
    model_env="BIBLEONT_LOCAL_MODEL",
    default_model="qwen2.5:3b-instruct-q4_K_M",
    thinking=False,
    # RATES ARE ZERO AND THAT IS THE DANGEROUS PART.
    #
    # Every guard in the farm is a money guard -- per-run budget, the ceiling
    # that stopped Exodus, the pacing that widens review intervals when funds
    # run low. At zero cost every one of them becomes a no-op, and there is no
    # economic brake on producing five days of unusable output.
    #
    # So a local run needs the deterministic lints promoted from advice to a
    # hard gate. Nothing about that is optional: free extraction removes the
    # only thing that has ever stopped a bad run early.
    rates={"__free__": {"hit": (0.0, 0.0), "miss": (0.0, 0.0), "out": (0.0, 0.0)}},
    needs_key=False,
    notes="Ollama on this machine. Free, slow, and unguarded by cost.",
)


DEEPSEEK = Provider(
    name="deepseek",
    base="https://api.deepseek.com",
    key_env="BIBLEONT_REVIEW_KEY",
    model_env="BIBLEONT_REVIEW_MODEL",
    # `deepseek-flash` is DeepSeek-V4.1-Flash (pricing page, 25 Sep 2026);
    # `deepseek-v4-flash` is a legacy name still served by it at Flash price.
    # The two names this key can call: deepseek-flash, deepseek-v4-pro.
    default_model="deepseek-flash",
    thinking=True,
    rates={
        "deepseek-flash": {"hit": (0.003, 0.006), "miss": (0.15, 0.30),
                           "out": (0.60, 1.20)},
        "deepseek-v4-flash": {"hit": (0.003, 0.006), "miss": (0.15, 0.30),
                              "out": (0.60, 1.20)},
        "deepseek-v4-pro": {"hit": (0.022, 0.044), "miss": (0.66, 1.32),
                            "out": (1.98, 3.96)},
    },
    notes="metered; peak 01:00-04:00 and 06:00-10:00 UTC weekdays doubles it",
)

GROQ = Provider(
    name="groq",
    base="https://api.groq.com/openai/v1",
    key_env="BIBLEONT_GROQ_KEY",
    model_env="BIBLEONT_GROQ_MODEL",
    default_model="",              # deliberately none -- see module docstring
    thinking=False,
    rates=None,                    # free tier while no card is on file
    notes="free tier binds on requests per minute, not on price",
)


ANTHROPIC = Provider(
    name="anthropic",
    base="https://api.anthropic.com/v1",
    key_env="BIBLEONT_ANTHROPIC_KEY",
    model_env="BIBLEONT_ANTHROPIC_MODEL",
    default_model="claude-opus-5",
    thinking=True,
    wire="anthropic",
    # CONFIRMED against the published price list, 2026-08-30 (the page was pasted in).
    #
    # These drive the supervisor's ledger, and the grant has auto-reload off:
    # running out is a hard stop in the middle of a run, not an overdraft.
    #
    # The previous figures were guesses erring high on purpose, and were high
    # by 3x -- Opus 5 is $5/$25 per MTok, not $15/$75. That is the safe
    # direction to be wrong in (the ledger under-reports headroom and stops
    # early) but it is not free: every plan costed this session came out 3x
    # too expensive, and "Opus cannot afford the chapter layer" was a
    # conclusion drawn from the wrong number. An estimate that fails safe
    # still decides architecture.
    #
    # `write` is the cache-creation premium, charged ABOVE base input -- it
    # was previously billed at the base rate, a small but systematic
    # undercharge on every cold call.
    rates={
        "claude-opus-5": {"hit": (0.50, 0.50), "miss": (5.0, 5.0),
                          "write": (6.25, 6.25), "out": (25.0, 25.0)},
        "claude-fable-5": {"hit": (1.00, 1.00), "miss": (10.0, 10.0),
                           "write": (12.50, 12.50), "out": (50.0, 50.0)},
        "claude-sonnet-5": {"hit": (0.20, 0.20), "miss": (2.0, 2.0),
                            "write": (2.50, 2.50), "out": (10.0, 10.0)},
        "claude-haiku-4-5-20251001": {"hit": (0.10, 0.10), "miss": (1.0, 1.0),
                                      "write": (1.25, 1.25), "out": (5.0, 5.0)},
    },
    notes="supervisor and coach; metered API credit, separate from any "
          "Claude subscription and with auto-reload off",
)

PROVIDERS = {
p.name: p for p in (DEEPSEEK, GROQ, ANTHROPIC, LOCAL)}


def current() -> Provider:
    """The active provider. Unset means DeepSeek, so nothing existing moves."""
    return PROVIDERS.get(
        os.environ.get("BIBLEONT_PROVIDER", "deepseek").strip().lower(),
        DEEPSEEK)


def cached_tokens(usage: dict) -> int | None:
    """How many input tokens were served from cache, or None if unreported.

    None is not zero. A provider that does not tell us cannot be assumed to
    have cached nothing, and cannot be assumed to have cached everything --
    it means the prefix design is unverified against that provider.
    """
    if not usage:
        return None
    if "prompt_cache_hit_tokens" in usage:
        return usage.get("prompt_cache_hit_tokens") or 0
    details = usage.get("prompt_tokens_details") or {}
    if "cached_tokens" in details:
        return details.get("cached_tokens") or 0
    return None


def cost(usage: dict, provider: Provider | None = None,
         peak: bool = False) -> float:
    """What one call cost. Zero for an unmetered provider, and honestly zero
    rather than DeepSeek's arithmetic applied to someone else's tokens."""
    p = provider or current()
    if not p.rates:
        return 0.0
    table = p.rates.get(p.model) or next(iter(p.rates.values()))
    i = 1 if peak else 0
    hit = cached_tokens(usage) or 0
    total_in = usage.get("prompt_tokens") or 0
    miss = usage.get("prompt_cache_miss_tokens")
    if miss is None:
        miss = max(total_in - hit, 0)
    out = usage.get("completion_tokens") or 0
    return (hit * table["hit"][i] + miss * table["miss"][i]
            + out * table["out"][i]) / 1e6


def probe(prompt: str = "Reply with the JSON object {\"ok\": true} and "
                        "nothing else.") -> dict:
    """One minimal call, returning the raw usage block.

    This is how the caching question gets answered: not by reading a pricing
    page but by looking at what comes back.
    """
    p = current()
    if not p.key:
        raise RuntimeError(f"no {p.key_env} in the environment")
    if not p.model:
        raise RuntimeError(
            f"no model set. {p.model_env} must name one; "
            f"run `python -m bibleont.providers models` to see the choices")
    body = json.dumps({
        "model": p.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 64,
    }).encode()
    req = urllib.request.Request(p.chat_url, data=body, headers=auth(p))
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def models() -> list[str]:
    """Ask the provider what this key may actually call."""
    p = current()
    if not p.key:
        raise RuntimeError(f"no {p.key_env} in the environment")
    req = urllib.request.Request(p.models_url, headers=auth(p))
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.loads(r.read())
    rows = payload.get("data") or payload.get("models") or []
    return sorted(m.get("id", "") for m in rows if isinstance(m, dict))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "show"
    p = current()

    if cmd == "show":
        print(f"provider   {p.name}")
        print(f"endpoint   {p.chat_url}")
        env_set = bool(os.environ.get(p.key_env))
        stored = bool(from_keystore(p.name))
        where = ("environment" if env_set else
                 "OS keystore" if stored else "NOT SET")
        print(f"key        {where}"
              + (f" ({len(p.key)} chars)" if p.key else
                 f" -- set {p.key_env}, or `providers store`"))
        if env_set and stored:
            print("           (a stored key exists too; the environment wins)")
        print(f"model      {p.model or '(none set -- ' + p.model_env + ')'}")
        print(f"thinking   {'supported' if p.thinking else 'not supported'}")
        print(f"metered    {'yes' if p.rates else 'no (free tier)'}")
        print(f"note       {p.notes}")
        print()
        print("switch with:  BIBLEONT_PROVIDER=groq")
        return 0

    if cmd == "store":
        # getpass, so the key is never echoed to the terminal and never lands
        # in PowerShell history the way `$env:X = "sk-..."` does.
        import getpass
        try:
            import keyring                          # noqa: F401
        except ImportError:
            print("the `keyring` package is not installed:")
            print("    pip install keyring")
            print("without it, set the key per shell instead:")
            print(f"    $env:{p.key_env} = \"...\"")
            return 1
        secret = getpass.getpass(f"{p.name} API key (not echoed): ").strip()
        if not secret:
            print("nothing entered; nothing stored.")
            return 1
        to_keystore(p.name, secret)
        print(f"stored for {p.name} in the OS keystore under "
              f"'{KEYSTORE_SERVICE}'.")
        print(f"{p.key_env} still overrides it when set.")
        return 0

    if cmd == "forget":
        try:
            import keyring
            keyring.delete_password(KEYSTORE_SERVICE, p.name)
            print(f"removed the stored key for {p.name}.")
        except Exception as exc:                    # noqa: BLE001
            print(f"nothing removed: {type(exc).__name__}: {exc}")
            return 1
        return 0

    if cmd == "models":
        try:
            got = models()
        except urllib.error.HTTPError as exc:
            print(f"HTTP {exc.code}: {exc.read()[:200].decode(errors='replace')}")
            return 1
        except Exception as exc:                    # noqa: BLE001
            print(f"{type(exc).__name__}: {exc}")
            return 1
        print(f"{len(got)} model(s) available to this key on {p.name}:")
        for m in got:
            print(f"  {m}")
        return 0

    if cmd == "probe":
        try:
            payload = probe()
        except urllib.error.HTTPError as exc:
            print(f"HTTP {exc.code}: {exc.read()[:400].decode(errors='replace')}")
            return 1
        except Exception as exc:                    # noqa: BLE001
            print(f"{type(exc).__name__}: {exc}")
            return 1
        usage = payload.get("usage") or {}
        print(f"model returned  {payload.get('model')}")
        print(f"usage block     {json.dumps(usage, indent=2)}")
        hit = cached_tokens(usage)
        print()
        if hit is None:
            print("CACHING: not reported by this provider.")
            print("  The 15,000-token prefix design cannot be verified here.")
            print("  Treat prefix tokens as billed in full when planning a run.")
        else:
            print(f"CACHING: reported. {hit} of "
                  f"{usage.get('prompt_tokens', '?')} input tokens were cached.")
            print("  (One call cannot warm a cache; re-run to see a hit.)")
        return 0

    print("usage: python -m bibleont.providers "
          "[show|store|forget|models|probe]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
