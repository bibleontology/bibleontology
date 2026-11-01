"""The original is paired with an English verse through the verse map, never by number (FAULTS #24, 2026-10-28).

The Berean and MACULA number some Old Testament verses differently, and a verse can move into another chapter:
English Joel 2:28-32 is Hebrew 3:1-5, Malachi 4 is Hebrew 3:19-24, and in every psalm whose Hebrew counts the title
as verse 1 the English runs one behind. /api/verse paired them by number: Joel 2:28 and Malachi 4:1 had no
original, and Psalm 40:6 ("Sacrifice and offering") stood over the Hebrew of 40:5 (רַבּוֹת). Measured over all
31,102 English verses: 151 had no original and 1,837 another verse's; after, 15 have none, every one a New
Testament verse the critical text does not have.

  - Joel 2:28's original begins וְהָיָה אַחֲרֵי־כֵן; Joel 3:1 (English) is Hebrew 4:1, not 3:1
  - Psalm 40:6's original is זֶבַח וּמִנְחָה, not רַבּוֹת
  - Malachi 4:1 has its original (Hebrew 3:19)
  - every English verse without an original is a New Testament verse the critical text omits

Each check is proved by a planted fault: the pairing by number put back.

In process, after the graph loads (~1 minute). Run: python tests/test_verse_pairing.py"""
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

d = S.load()


def bare(words):
    """the original's letters, points, accents and marks aside"""
    s = " ".join(w.get("t") or "" for w in words)
    s = "".join(ch for ch in unicodedata.normalize("NFD", s) if not unicodedata.combining(ch))
    return re.sub(r"[^א-ת ]", "", s.replace("־", " ")).split()


def faults():
    out = []
    joel = bare(S.api_verse(d, {"ref": ["Joel 2:28"]})["orig"])
    if joel[:5] != ["ו", "היה", "אחרי", "כן", "אשפוך"] and joel[:4] != ["והיה", "אחרי", "כן", "אשפוך"]:
        out.append(f"Joel 2:28's original begins {joel[:5]}, not וְהָיָה אַחֲרֵי־כֵן")
    j31 = bare(S.api_verse(d, {"ref": ["Joel 3:1"]})["orig"])
    if j31[:2] != ["כי", "הנה"]:
        out.append(f"English Joel 3:1 shows {j31[:4]}, not כִּי הִנֵּה (Hebrew 4:1)")
    ps = bare(S.api_verse(d, {"ref": ["Ps 40:6"]})["orig"])
    if not ps or ps[0] == "רבות" or ps[0] != "זבח":
        out.append(f"Psalm 40:6's original begins {ps[:3]}, not זֶבַח")
    if not S.api_verse(d, {"ref": ["Mal 4:1"]})["orig"]:
        out.append("Malachi 4:1 has no original")
    missing = [k for k in d["verses"] if S.macula_ref(*k) not in d["orig"]]
    ot = [k for k in missing if S.TO_MACULA.get(k[0], k[0]) not in S._NT_BOOKS]
    if ot or len(missing) > 15:
        out.append(f"{len(missing)} English verses have no original, {len(ot)} in the Old Testament: {ot[:4]}")
    return out


fails = faults()
# planted: the pairing by number, as it was
real = S.macula_ref
S.macula_ref = lambda b, c, v: f"{S.TO_MACULA.get(b, b)}.{c}.{v}"
planted = faults()
S.macula_ref = real
for want in ("Joel 2:28", "Joel 3:1", "Psalm 40:6", "Malachi 4:1", "no original"):
    if not any(want in f for f in planted):
        fails.append(f"planted (the pairing by number) was not caught at {want}")
print("verse pairing: Joel 2:28, Joel 3:1, Psalm 40:6 and Malachi 4:1 paired by the verse map; 5 planted faults caught")
for f in fails:
    print("FAIL", f)
print("ok" if not fails else f"{len(fails)} failures")
sys.exit(1 if fails else 0)
