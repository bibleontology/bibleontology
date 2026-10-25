"""Speech is found in every book, not only where two book codes happen to agree
(the speech-claims diagnosis, 2026-10-23; fixed 2026-10-24).

tools/sweep/speaker_credit.py looks a claim's verses up in the sweep's speech
turns. The claim's verses come in the site's book codes (Exod, 1Sam, Matt), the
sweep's in MACULA's (Exo, 1Sa, Mat). Unmapped, no verse outside the books whose
codes coincide (Gen, Job, Isa ...) ever held speech: every one of the 68 credits
was in Genesis, Job, Jeremiah, Isaiah or Daniel, and 43% of the narrator's claims
could not be credited at all. The test reads the credits the export uses:
- some credit lies in a book whose two codes differ;
- every credit's verses are written in the site's codes, which is what the claim
  export matches on (a MACULA code there would quietly match nothing).

Planted: the credits of before the fix (none in a book whose codes differ), and a
credit written in MACULA's code.

    python tests/test_speaker_credit_codes.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from derive import BOOK  # noqa: E402  (the site's code -> MACULA's)

DIFFER = {site for site, mac in BOOK.items() if site != mac}
MACULA_ONLY = {mac for site, mac in BOOK.items() if site != mac} - set(BOOK)


def faults(rows: list[dict]) -> list[str]:
    bad = []
    books = [r["refs"][0].split(".")[0] for r in rows if r.get("refs")]
    if not any(b in DIFFER for b in books):
        bad.append(f"no credit in a book whose site and MACULA codes differ ({len(rows)} credits, books "
                   f"{sorted(set(books))}): the verse lookup is unmapped again")
    for r in rows:
        for v in r.get("refs") or []:
            if v.split(".")[0] in MACULA_ONLY:
                bad.append(f"{r['src']} {r['type']} {r['dst']}: verse {v} is in MACULA's code; the export "
                           f"matches the site's")
    return bad


def main() -> int:
    rows = [json.loads(ln) for ln in open(ROOT / "out" / "sweep" / "speaker-credits.jsonl", encoding="utf-8")]
    found = faults(rows)
    planted = 0
    before = [r for r in rows if r["refs"][0].split(".")[0] not in DIFFER]
    planted += bool(faults(before))
    mac = [dict(rows[0], refs=["1Sa.21.9"])]
    planted += any("MACULA's code" in f for f in faults(rows + mac))
    in_differ = sum(1 for r in rows if r["refs"][0].split(".")[0] in DIFFER)
    print(f"speaker credits: {len(rows)}, {in_differ} in books whose codes differ; planted faults caught: "
          f"{planted} of 2; {len(found)} failures")
    for f in found:
        print("  FAIL", f)
    return 1 if found or planted != 2 else 0


if __name__ == "__main__":
    raise SystemExit(main())
