"""About's "How to cite it" names the vocabularies' current release (2026-11-06).

It said version 1.2.1 through the whole of the 1.3.0 release: the comment beside it asked for the two to change
together, and nothing held them. The line in app2/static/index.html must name exactly the version in
ontology/ns-version.json, once; a planted fault (the line naming the previous version) must be caught.

Run: python -X utf8 tests/test_about_cite.py"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = json.loads((ROOT / "ontology" / "ns-version.json").read_text(encoding="utf-8"))["version"]
PAGE = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
CITE = re.compile(r"<i>Bible Ontology vocabularies</i>, version (\d+\.\d+\.\d+)\.")


def faults(page):
    got = CITE.findall(page)
    if len(got) != 1:
        return [f"About names the vocabularies' version {len(got)} times, not once"]
    if got[0] != VERSION:
        return [f"About cites the vocabularies as version {got[0]}; the release is {VERSION}"]
    return []


fails = faults(PAGE)
if not faults(CITE.sub("<i>Bible Ontology vocabularies</i>, version 1.0.0.", PAGE)):
    fails.append("planted: an old version in the citation was not caught")
for m in fails:
    print("FAIL", m)
print(f"About's citation names vocabulary version {VERSION}: {'ok' if not fails else f'{len(fails)} failures'}")
sys.exit(1 if fails else 0)
