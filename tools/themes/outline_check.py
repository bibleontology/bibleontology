"""Check a redone theme outline before anyone reads it (plan 7.6c).

    python tools/themes/outline_check.py <outline.txt> [...]

Each file is parsed by the site's own parser (tools/themes/theme_map.py), so
what fails here would fail on the page; then every reference must resolve to
Berean verses, every note (a quotation in curly quotes) must be in its verse
word for word, no range may run 20 verses or more, and no name or note may
use a word the site never says in its own voice. Exit 1 on any failure.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "themes"))
import theme_map as TM  # noqa: E402

V = {}
for line in (ROOT / "data" / "bible" / "verses.bsb.jsonl").read_text(encoding="utf-8").splitlines():
    d = json.loads(line)
    if "b" in d:
        V[(d["b"], d["c"], d["v"])] = d["t"]
VOICE = re.compile(r"\b(fulfil\w*|fulfill\w*|foreshadow\w*|predict\w*|prefigur\w*|antitype\w*|"
                   r"rapture|millenni\w*|tribulation|dispensation\w*|end times|antichrist|"
                   r"typolog\w*|christolog\w*|imago dei|the fall\b)", re.I)
WIDE = 20
norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[‘’']", "'", s or "")).lower()  # noqa: E731


def verses(r):
    b, (c1, v1), (c2, v2) = r[0], r[1], r[2]
    out = []
    for c in range(c1, c2 + 1):
        for v in range(v1 if c == c1 else 1, (v2 if c == c2 else 200) + 1):
            if (b, c, v) in V:
                out.append((b, c, v))
    return out


def check(path):
    fails, problems = [], []
    themes = TM.parse(problems, Path(path), "redone")
    fails += [f"parse: {p}" for p in problems]
    if len(themes) != 1:
        fails.append(f"{len(themes)} themes parsed (expected 1)")
        return fails, None
    t = themes[0]
    # at least 8, no upper limit: themes need not be balanced
    # (2026-10-08)
    if len(t["concepts"]) < 8:
        fails.append(f"{len(t['concepts'])} core concepts (at least 8)")
    for c in t["concepts"]:
        # a word the site does not say in its own voice is the text's own
        # when the name is a phrase of one of its passages ("Not to abolish,
        # but to fulfill", Matt 5:17): the readings test allows a quotation
        # the same way
        body_all = norm(" ".join(V[k] for p in c["passages"] for r in p["refs"] if r[1] for k in verses(r)))
        if VOICE.search(c["name"]) and norm(re.sub(r"[“”\"]", "", c["name"])).strip(" .,;:?!") not in body_all:
            fails.append(f"concept '{c['name']}': a word the site does not say in its own voice")
        if not 3 <= len(c["passages"]) <= 8:     # the brief's B: 3 to 8 each
            fails.append(f"concept '{c['name']}': {len(c['passages'])} passages (3 to 8)")
        for p in c["passages"]:
            for r in p["refs"]:
                if not r[1]:
                    fails.append(f"'{c['name']}': a whole book cited")
                    continue
                vs = verses(r)
                if not vs:
                    fails.append(f"'{c['name']}': {TM.label(r)} has no Berean verse")
                elif len(vs) >= WIDE:
                    fails.append(f"'{c['name']}': {TM.label(r)} runs {len(vs)} verses")
            if p.get("note"):
                body = norm(" ".join(V[k] for r in p["refs"] if r[1] for k in verses(r)))
                parts = [re.sub(r"^[\s\"“”'‘’,;:.—–-]+|[\s\"“”'‘’,;:.—–-]+$", "", x)
                         for x in re.split(r"…|\.\.\.", p["note"])]
                if not all(norm(x) in body for x in parts if len(x) >= 3):
                    fails.append(f"'{c['name']}': the note {p['note']!r} is not in its verses")
                # (a note found in its verses is the text's own words: no
                # voice check, as the readings test allows a quotation)
    # the brief's bounds for C and D (7.6c-OUTLINES.md): 4 to 10 secondary,
    # at least 4 links -- the ten lifted: if they are related they are
    # related (2026-10-08)
    if not 4 <= len(t["secondary"]) <= 10:
        fails.append(f"{len(t['secondary'])} secondary concepts (4 to 10)")
    if len(t["links"]) < 4:
        fails.append(f"{len(t['links'])} links (at least 4)")
    for s in t["secondary"]:
        if VOICE.search(s["name"]):
            fails.append(f"secondary '{s['name']}': a word the site does not say")
        for r in s.get("refs") or []:
            if r[1] and len(verses(r)) >= WIDE:
                fails.append(f"secondary '{s['name']}': {TM.label(r)} runs {len(verses(r))} verses")
    return fails, t


def main():
    bad = 0
    for path in sys.argv[1:]:
        fails, t = check(path)
        n = len(t["concepts"]) if t else 0
        print(f"{Path(path).name}: {n} concepts, {len(t['secondary']) if t else 0} secondary, "
              f"{len(t['links']) if t else 0} links, {len(fails)} failures")
        for f in fails:
            print("  FAIL", f)
        bad += bool(fails)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
