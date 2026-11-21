"""The conservation check catches a dropped fact and honors a ruled removal (P-2026-11-18-8).

    python -X utf8 tests/test_card_conservation.py

Doug, 2026-11-19: "we just need to be certain that we are not removing completely meaningful information that belongs
on any of the card types." `tools/card_conservation.py check` renders every card of a kind and compares it with its
snapshot; this proves the comparison itself, with planted faults, without rendering: a fact dropped from one card is
caught and named; the same fact on the removals list is not; a card that stops rendering is caught; a new fact is
counted, not failed; and the committed event snapshot is well formed (every card rendered, facts present).
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import card_conservation as C  # noqa: E402

fails = []
base = {"ev_a": {"cards": {"moses": True, "aaron": False}, "verses": {"exod 3:1": True}},
        "ev_b": {"cards": {"david": True}, "verses": {"1sam 17:4": False, "hos 6:6": False}}}

same, new = C.compare(base, copy.deepcopy(base), set())
if same or new:
    fails.append(f"an unchanged card reports a change: {same}, {new} new")

dropped = copy.deepcopy(base); del dropped["ev_a"]["cards"]["aaron"]
lost, _ = C.compare(base, dropped, set())
planted = {"a dropped card link is caught": any("ev_a" in x and "aaron" in x for x in lost)}

hid = copy.deepcopy(base); del hid["ev_b"]["verses"]["hos 6:6"]
lost, _ = C.compare(base, hid, {("ev_b", "hos 6:6")})
planted["a ruled removal is honored"] = not lost
lost, _ = C.compare(base, hid, {("*", "hos 6:6")})
planted["a ruled removal for every card is honored"] = not lost
lost, _ = C.compare(base, hid, {("ev_a", "hos 6:6")})
planted["a removal ruled for another card does not excuse this one"] = bool(lost)

gone = copy.deepcopy(base); gone["ev_b"] = {"error": "no page (0 bytes)"}
lost, _ = C.compare(base, gone, set())
planted["a card that stops rendering is caught"] = any("no longer renders" in x for x in lost)

more = copy.deepcopy(base); more["ev_a"]["verses"]["exod 3:2"] = False
lost, new = C.compare(base, more, set())
planted["a new fact is counted, not failed"] = not lost and new == 1

# the controls (2026-11-21): the Navigator button, a word card, a sketch
ctl = copy.deepcopy(base); ctl["ev_a"]["controls"] = {"navigator button": True, "word card H2617": True, "sketch": True}
for name in ("navigator button", "word card H2617", "sketch"):
    after = copy.deepcopy(ctl); del after["ev_a"]["controls"][name]
    lost, _ = C.compare(ctl, after, set())
    planted[f"a lost control is caught: {name}"] = any(name in x for x in lost)
C.controls  # the extractor exists
html = ('<button class="nav-btn" data-navgo="ruth">Show in Navigator</button><span data-key="H2617">x</span>'
        '<svg><use href="#sk-lamp"></use></svg>')
planted["the extractor reads all three"] = C.controls(html) == {"navigator button", "word card H2617", "sketch"}
planted["the extractor reads none on a bare page"] = C.controls("<p>Ruth</p>") == set()

for k, v in planted.items():
    if not v:
        fails.append(f"planted fault not caught: {k}")

snap = C.OUT / "event-snapshot.json"
if snap.exists():
    s = json.loads(snap.read_text(encoding="utf-8"))
    bad = [k for k, v in s.items() if "error" in v]
    if bad:
        fails.append(f"{len(bad)} event cards did not render in the snapshot, e.g. {bad[:3]}")
    if sum(len(v.get("cards", {})) + len(v.get("verses", {})) for v in s.values()) < len(s):
        fails.append("the event snapshot holds fewer facts than cards: an empty render was recorded as a card")
elif (ROOT / "docs" / "review").exists():
    fails.append("no event snapshot (python -X utf8 tools/card_conservation.py snapshot event, from PowerShell)")
else:
    # the public copy carries no docs/review, where the snapshots live; the planted faults above still ran (the export
    # gate, 2026-11-21)
    print("event snapshot: not in the public copy, skipped")

for f in fails:
    print("FAIL", f)
print(f"card conservation: planted faults caught: {sum(planted.values())} of {len(planted)}; {len(fails)} failures")
sys.exit(1 if fails else 0)
