"""Run the tests, in this checkout, with no deploy remote (2026-10-22).

deploy/preflight.sh is the check before a deploy: it compares this checkout
with the live server's remote and prints the push command, so in a clone that
has no such remote it is the wrong tool (the simulated maintainer, 2026-10-22:
"a test runner that needs no deploy remote"). This runs the same test files
preflight names, one by one, and says which passed.

    python tools/run_tests.py            # the tests that do not load the whole site
    python tools/run_tests.py --all      # and those that do (minutes each, about 2 GB)
    python tools/run_tests.py test_claims test_assertion_policy

A test that needs what a public clone does not carry (the KJV, MACULA's raw
files) says "skipped" and passes. tests/test_verse_structure.py is not run:
it is known red (144 checks, since the October rebuilds) and under diagnosis.
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# the tests that start the server or load the whole site (about 2 GB, minutes)
HEAVY = {"test_card_links.py", "test_no_ai_names.py", "test_theme_tags.py", "test_word_addresses.py",
         "test_filter_exports.py", "test_ontology_closed_world.py"}


def named_in_preflight() -> list[str]:
    pre = (ROOT / "deploy" / "preflight.sh").read_text(encoding="utf-8")
    return sorted(set(re.findall(r"tests/(test_[\w]+\.py)", pre)))


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    every = "--all" in sys.argv
    tests = [a if a.endswith(".py") else a + ".py" for a in args] or named_in_preflight()
    if not args and not every:
        skipped = [t for t in tests if t in HEAVY]
        tests = [t for t in tests if t not in HEAVY]
        if skipped:
            print(f"not run (they load the whole site; --all runs them): {', '.join(skipped)}")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    fails = []
    for t in tests:
        t0 = time.time()
        p = subprocess.run([sys.executable, str(ROOT / "tests" / t)], cwd=ROOT, env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        last = (p.stdout.strip().splitlines() or [""])[-1][:120]
        print(f"  {'ok  ' if p.returncode == 0 else 'FAIL'} {t} ({time.time() - t0:.0f}s): {last}")
        if p.returncode:
            fails.append(t)
    print(f"{len(tests) - len(fails)} of {len(tests)} passed" + (f"; failed: {', '.join(fails)}" if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
