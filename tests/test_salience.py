"""The filter policy is the one source (plan 8.1f, ontology/schema/salience.json).

Holds: the card-word cut membership.py uses is the policy's; the server serves
the navigator's rule from the policy; the page's fallback numbers (used only
should a server send none) equal the policy's; and a planted change to the
policy is seen by every reader of it.

    python tests/test_salience.py          (preflight runs it so)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
import salience  # noqa: E402
import membership  # noqa: E402


def test_card_cut_is_the_policys():
    assert membership.SHOWN_SHARE == salience.cut("card_word_share")


def test_tiers():
    assert salience.tier("card_word_share", 0.15) == "default"
    assert salience.tier("card_word_share", 0.149) == "on_request", "planted: a word just under the cut"
    assert salience.tier("claim_certainty", None) == "default", "certainty hides nothing"


def test_server_serves_the_navigator_rule():
    src = (ROOT / "app2" / "server.py").read_text(encoding="utf-8")
    assert 'salience.entry("navigator_tie_strength")' in src and '"policy":' in src


def test_page_fallbacks_equal_the_policy():
    page = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
    p = salience.entry("navigator_tie_strength")["parameters"]
    r = salience.entry("navigator_tie_strength")["rank"]
    for name in ("chapter_weight", "certainty_factor_default", "weight_default", "weight_coefficient",
                 "shared_coefficient"):
        m = re.search(rf"p\.{name} \?\? ([0-9.]+)", page)
        assert m and float(m.group(1)) == p[name], f"the page's fallback for {name} differs from the policy"
    m = re.search(r"KGN\.pol\.rank\.desktop\) : (\d+)", page)
    assert m and int(m.group(1)) == r["desktop"], "the page's fallback ceiling differs from the policy"


def test_planted_policy_change_is_seen():
    saved = salience._P
    try:
        salience._P = json.loads(salience.POLICY.read_text(encoding="utf-8"))
        salience._P["measures"]["card_word_share"]["cut"] = 0.5
        assert salience.tier("card_word_share", 0.3) == "on_request", "a reader kept its own cut"
    finally:
        salience._P = saved


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = []
    for n, f in tests:
        try:
            f()
        except AssertionError as ex:
            failed.append(f"FAIL {n}: {ex}")
    print(f"filter policy: {len(tests)} checks, {len(tests) - len(failed)} passed, planted faults among them")
    for x in failed:
        print(x)
    sys.exit(1 if failed else 0)
