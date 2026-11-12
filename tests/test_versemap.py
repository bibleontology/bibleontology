"""The verse map (out/versemap.json, tools/versify.py): MACULA's Hebrew-numbered verse -> the Berean verse with its
text. The reader places the Hebrew under the English by it, so a wrong entry shows one verse's original under
another's English.

  1. No psalm's verse maps into another psalm. Psalm 54:2, the second verse of its title (the Ziphites' words to
     Saul), was mapped to 53:6, so Psalm 53:6 showed Psalm 54's heading (found 2026-11-06 by tools/lrm_psalter.py,
     which refuses it). A chapter boundary that truly moves (1 Sam 21:1 is English 20:42) is outside the Psalter.
  2. The fixes stay fixed: Psalm 54:2 is 54:1 (a title folds into the Berean's verse 1); Psalm 13:1 is not 12:8 (the
     image audit, 2026-10-24); Hosea 14:8 is 14:7.
  3. Regenerating the map without STEP's tables (data/raw/stepbible, git-ignored) silently undoes 89 of its
     corrections, Psalm 13's among them: check 2 catches that, as it did on 2026-11-06.

Each check is proved by a planted fault. Run: python -X utf8 tests/test_versemap.py"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOVED = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8"))["moved"]
KEEP = {"Psa.54.2": "Psa.54.1", "Psa.13.1": "Psa.13.1", "Hos.14.8": "Hos.14.7",
        # a chapter's last verse the Berean folds into the one before (2026-11-07): Rev 12:18 had linked nowhere
        "Rev.12.18": "Rev.12.17", "3Jn.1.15": "3Jn.1.14"}


def faults(moved):
    out = []
    for k, v in moved.items():
        if k.startswith("Psa.") and k.split(".")[1] != v.split(".")[1]:
            out.append(f"{k} maps into another psalm: {v}")
    for k, want in KEEP.items():
        if moved.get(k, k) != want:
            out.append(f"{k} maps to {moved.get(k, k)}, not {want}")
    return out


fails = faults(MOVED)
for what, plant in (("a title verse sent into the psalm before", {"Psa.54.2": "Psa.53.6"}),
                    ("Psalm 13's title under 12:8 again", {"Psa.13.1": "Psa.12.8"}),
                    ("Hosea 14:8 left in place", {"Hos.14.8": "Hos.14.8"})):
    m = copy.deepcopy(MOVED)
    m.update(plant)
    if not faults(m):
        fails.append(f"planted: {what} was not caught")
for f in fails:
    print("FAIL", f)
print(f"verse map: {len(MOVED)} moved verses; {'ok' if not fails else f'{len(fails)} failures'}")
sys.exit(1 if fails else 0)
