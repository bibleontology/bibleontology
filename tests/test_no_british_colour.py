"""No British "colour" in what the server shows (pilot task 3, 2026-10-31; the walkthrough found "Colours" on /graph).
Checks the string literals of app2/server.py, not its comments or names: the American-spelling map's own key
("colour": "color") is the one string allowed to hold the British form.

    python -X utf8 tests/test_no_british_colour.py
"""
import io
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "app2" / "server.py").read_text(encoding="utf-8")

bad = []
prev = None
for tok in tokenize.generate_tokens(io.StringIO(SRC).readline):
    is_doc = tok.type == tokenize.STRING and (prev is None or prev.type in (tokenize.INDENT, tokenize.NEWLINE, tokenize.DEDENT))
    if tok.type not in (tokenize.NL, tokenize.COMMENT):
        prev = tok
    if tok.type != tokenize.STRING or is_doc:            # a docstring documents the code; the site never shows it
        continue
    if not re.search(r"colour", tok.string, re.I):
        continue
    if re.fullmatch(r"""[rbuf]*["']colours?["']""", tok.string, re.I):    # the spelling map's keys
        continue
    bad.append("line %d: %s" % (tok.start[0], tok.string[:80]))

ok_phrase = "Colors mark the kind of tie" in SRC
for b in bad:
    print("FAIL British spelling in a shown string:", b)
if not ok_phrase:
    print("FAIL the /graph legend does not say 'Colors mark the kind of tie'")
print("no British colour: %d shown string(s) with it, legend %s" % (len(bad), "ok" if ok_phrase else "missing"))
sys.exit(1 if bad or not ok_phrase else 0)
