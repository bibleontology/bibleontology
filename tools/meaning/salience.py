"""THE DECLARED FILTER POLICY, READ ONE WAY (plan 8.1f; ontology/schema/salience.json).

Every tool that decides what is shown by default reads its cut or rank here,
never a constant of its own: the server's card words and the navigator, the
resolution layer, the concept audit, and the export that publishes each
measure and the policy itself.

    cut(name)            the measure's cut (card_word_share -> 0.15)
    tier(name, value)    "default" or "on_request" for a measured value
    entry(name)          the declared entry, for the export and the docs
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "ontology" / "schema" / "salience.json"
_P = None


def policy():
    global _P
    if _P is None:
        _P = json.loads(POLICY.read_text(encoding="utf-8"))
    return _P


def entry(name):
    return policy()["measures"][name]


def cut(name):
    c = entry(name).get("cut")
    if c is None:
        raise KeyError(f"{name} declares no cut")
    return c


def tier(name, value):
    c = entry(name).get("cut")
    if c is None:
        return "default"
    return "default" if value is not None and value >= c else "on_request"
