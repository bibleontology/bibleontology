"""The words MACULA marks as proper names, by Strong's key.

A record's name has one word behind it on its card, and the server finds it by
name -- which cannot tell apart three records that share one (N-D3 / C-D11,
the 2026-10-02 evaluation: the monster Rahab of Job 26:12 showed רָחָב, the
woman of Jericho's name; Matt 1:5's Rahab showed Ῥαάβ, where the verse reads
Ῥαχάβ). The fix looks in the record's own verses for the word standing there,
and needs to know which words are names: MACULA says so on every word
(type "proper"). The lexicon says so too, but it may not be shipped
(docs/OPERATIONS.md, "External datasets"); MACULA may, so the list is drawn
from it.

    python tools/proper_names.py   -> out/proper-names.json
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "builder"))
import source as S  # noqa: E402


def main():
    seen = collections.defaultdict(collections.Counter)
    for lang in ("hebrew", "greek"):
        for p in S.files(lang):
            _root, ws = S.load(p, lang)
            for w in ws.values():
                st = "".join(ch for ch in (w.get("strongnumberx") or w.get("strong") or "")
                             if ch.isdigit())
                if st:
                    k = ("g" if lang == "greek" else "h") + str(int(st))
                    seen[k][w.get("type") == "proper"] += 1
    # a name in most of its uses: a few Strong's numbers cover a name and a
    # common word together
    keys = sorted(k for k, c in seen.items() if c[True] > c[False])
    (ROOT / "out" / "proper-names.json").write_text(json.dumps({
        "_note": "Strong's keys MACULA marks as proper names (type 'proper') in most of "
                 "their uses. Made by tools/proper_names.py.",
        "keys": keys}, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"{len(keys):,} proper-name keys of {len(seen):,}")


if __name__ == "__main__":
    main()
