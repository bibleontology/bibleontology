"""Convert overlay entity names from KJV wording to BSB, verifiably.

2026-09-12: the overlay needed converting to BSB words. The reader now
sees BSB -- `verses.bsb.jsonl` loads second and overwrites the KJV -- while the
overlay names and quotes are KJV throughout. Searching *"armor of god"* returned
nothing while the overlay held `the_whole_armour_of_god`, which is the failure
inverted: it looked empty exactly where it was thorough.

## Why this is safe to automate

**The conversion is mechanically verifiable.** A correct BSB name appears
verbatim in the BSB text of a verse the entity already cites. Nothing is
trusted; every proposal is checked by substring before it is written, and a
failure queues for review rather than landing. That property is what makes a
model pass acceptable here and would not make one acceptable for a claim.

## What it refuses to touch

**IDS NEVER CHANGE.** Measured 2026-09-12: 5,191 of 8,416 ids are tied to the
name, and 15,030 relations carry 30,060 endpoints pointing at them. Regenerating
ids from converted names would rewrite every one of those across 196 files for a
cosmetic gain. The id stays an opaque key -- which is what an id should have
been -- and only `name` changes, with the original kept as `name_kjv`.

## The four outcomes, measured before building

    verbatim in BOTH translations       3,265   38.8%   nothing to do
    not a verbatim quote                2,632   31.3%   editorial labels
    in KJV but NOT in BSB               2,469   29.3%   the work
    BSB only                               50    0.6%   already fine

Of the 2,469, a word map alone settles 67. A fuzzy-window pass looked like it
settled 998 more and **is not used**: at any threshold loose enough to catch
*colours -> colors* (0.86) it also accepted *"a dead man" -> "a dream and"*
(0.76). Character similarity matches incidental letter overlap, so the residue
goes to a model whose output is then verified, not to a similarity score.

    python tools/bsbconvert.py                 # report what needs doing
    python tools/bsbconvert.py --apply-map     # write only the deterministic wins
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENT = ROOT / "ontology/entities/entities.jsonl"

# Archaisms and spellings that are safe because they are exact word swaps.
# Deliberately NOT morphological: a rule broad enough to catch `baptise` also
# turns `praise` into `praize`, which is how the search normaliser broke first.
WORD_MAP = {
    "thy": "your", "thee": "you", "thou": "you", "ye": "you", "thine": "your",
    "unto": "to", "hath": "has", "doth": "does", "hast": "have",
    "saith": "says", "colours": "colors", "colour": "color",
    "armour": "armor", "honour": "honor", "honours": "honors",
    "saviour": "savior", "labour": "labor", "favour": "favor",
    "neighbour": "neighbor", "valour": "valor", "vigour": "vigor",
    "charity": "love", "ghost": "Spirit", "shew": "show", "shewed": "showed",
    "sheweth": "shows", "behold": "behold", "raiment": "clothing",
    "wroth": "angry", "hearken": "listen", "beseech": "urge",
}
VERSE_RX = re.compile(r"^([\w\d]+)\s+(\d+):(\d+)")


def verses(name):
    out = {}
    for line in (ROOT / "data/bible" / name).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if "b" in d:
            out[(d["b"], d["c"], d["v"])] = d["t"]
    return out


def vkey(ref):
    m = VERSE_RX.match(ref or "")
    return (m.group(1), int(m.group(2)), int(m.group(3))) if m else None


def norm(s):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split())


def modernise(s):
    return " ".join(WORD_MAP.get(w, w) for w in (s or "").split())


def classify(ents, kjv, bsb):
    """-> {bucket: [(entity, refs)]}. The buckets are the four outcomes."""
    out = collections.defaultdict(list)
    for e in ents:
        nm = norm(e.get("name"))
        refs = [vkey(r) for r in (e.get("refs") or [])]
        refs = [r for r in refs if r and r in kjv and r in bsb]
        if not nm or not refs:
            out["unresolvable"].append((e, refs))
            continue
        ink = any(nm in norm(kjv[r]) for r in refs)
        inb = any(nm in norm(bsb[r]) for r in refs)
        if ink and inb:
            out["both"].append((e, refs))
        elif ink:
            out["needs"].append((e, refs))
        elif inb:
            out["bsb_only"].append((e, refs))
        else:
            out["not_a_quote"].append((e, refs))
    return out


def try_map(e, refs, bsb):
    """Deterministic conversion. Returns the new name, or None if unverified."""
    cand = modernise(e["name"])
    if cand == e["name"]:
        return None
    if any(norm(cand) in norm(bsb[r]) for r in refs):
        return cand
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply-map", action="store_true",
                    help="write the deterministic conversions only")
    a = ap.parse_args()

    kjv, bsb = verses("verses.jsonl"), verses("verses.bsb.jsonl")
    ents = [json.loads(l) for l in ENT.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    ents = [e for e in ents if isinstance(e, dict) and e.get("name")]
    buckets = classify(ents, kjv, bsb)
    n = len(ents)
    print(f"overlay entities {n:,}\n")
    for k in ("both", "not_a_quote", "needs", "bsb_only", "unresolvable"):
        v = len(buckets[k])
        print(f"  {k:<16}{v:>6,}  {100*v/n:5.1f}%")

    wins = []
    for e, refs in buckets["needs"]:
        new = try_map(e, refs, bsb)
        if new:
            wins.append((e, new))
    print(f"\n  deterministic conversions available: {len(wins):,}")
    for e, new in wins[:8]:
        print(f"     {e['name'][:40]:<42} -> {new[:40]}")
    print(f"\n  left for a verified model pass: "
          f"{len(buckets['needs']) - len(wins):,}")

    if not a.apply_map:
        print("\nnot written -- pass --apply-map for the deterministic wins only")
        return 0

    by_id = {id(e): new for e, new in wins}
    out, changed = [], 0
    for line in ENT.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        new = None
        for e, nm in wins:
            if e.get("id") == d.get("id"):
                new = nm
                break
        if new:
            d["name_kjv"] = d["name"]        # the original is kept, never lost
            d["name"] = new
            changed += 1
        out.append(json.dumps(d, ensure_ascii=False))
    ENT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\nwrote {ENT.relative_to(ROOT)}  ({changed:,} names converted, "
          f"ids untouched, originals kept as name_kjv)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
