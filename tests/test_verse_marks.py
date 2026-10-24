"""The marks beside the Berean's words are where they should be (2026-10-08).

Of Mark 16:16 in a theme outline: mark the longer ending site-wide;
and of 1 Corinthians 13:8: keep the Berean's words, but mark the note clearly,
with an asterisk or equivalent right in the verse, for consistency in using a
translation while communicating our own findings. This
checks, without the server:
  - every verse of Mark 16:9-20 and John 7:53-8:11 carries the Berean's
    manuscript note (out/manuscript-notes.json, tools/manuscript_notes.py),
    and Luke 23:34 its own;
  - every finding in ontology/translation-findings.json names a verse that
    exists, its "word" is in that verse's Berean text exactly (so the asterisk
    lands at the word, not at the end), and it carries a lemma, a gloss and a
    note;
  - the client marks the reader, the verse peeks and the server-rendered /p/
    pages through vtext / _marked, and reads the field "vmarks" (the reader's
    rows already had a "marks" field, for the theme brackets: reusing the
    name broke the reader on 2026-10-08);
  - a planted fault is caught: a finding whose word is not in its verse.
Run: python tests/test_verse_marks.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V = {}
for line in (ROOT / "data" / "bible" / "verses.bsb.jsonl").read_text(encoding="utf-8").splitlines():
    d = json.loads(line)
    if "b" in d:
        V[f"{d['b']}.{d['c']}.{d['v']}"] = d["t"]
MS = json.loads((ROOT / "out" / "manuscript-notes.json").read_text(encoding="utf-8"))["notes"]
FIND = json.loads((ROOT / "ontology" / "translation-findings.json").read_text(encoding="utf-8"))["findings"]
HTML = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
SRV = (ROOT / "app2" / "server.py").read_text(encoding="utf-8")


def check(findings):
    bad = []
    for f in findings:
        t = V.get(f.get("ref"))
        if t is None:
            bad.append(f"finding at {f.get('ref')}: no such verse")
        elif f.get("word") not in t:
            bad.append(f"finding at {f['ref']}: {f.get('word')!r} is not in the Berean's text")
        for k in ("lemma", "gloss", "note"):
            if not f.get(k):
                bad.append(f"finding at {f.get('ref')}: no {k}")
    return bad


fails = []
for b, c, vs in (("Mark", 16, range(9, 21)), ("John", 7, [53]), ("John", 8, range(1, 12))):
    for v in vs:
        k = f"{b}.{c}.{v}"
        if k in V and not MS.get(k):
            fails.append(f"{k}: no manuscript note")
if not MS.get("Luke.23.34"):
    fails.append("Luke.23.34: no manuscript note")
fails += check(FIND)
for needle, where in (("function vtext(", HTML), ("vtext(v.text, v.vmarks", HTML), ("vtext(d.text, d.vmarks)", HTML),
                      ('"vmarks": verse_marks(', SRV), ("def _marked(", SRV), ("_marked(b, c, v, text)", SRV)):
    if needle not in where:
        fails.append(f"missing in the page code: {needle}")
# a planted fault must be caught
planted = check([{"ref": "1Cor.13.8", "word": "they will be stopped", "lemma": "x", "gloss": "x", "note": "x"}])
if not planted:
    fails.append("planted fault (a finding's word not in its verse) was not caught")

print(f"{len(MS)} verses with a manuscript note, {len(FIND)} findings; planted fault caught: {bool(planted)}; "
      f"{len(fails)} failures")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
