"""Who is making the judgement, where the text says so.

The question was what would be regretted for not being addressed early. The answer was the
assessor on an assessment -- and the write-up overstated it. **The field already
exists.** `claimed_by` is on every relation, `prefix.py` teaches it with a
worked example, and 2,294 relations carry it.

What is actually true, measured:

    assessed_as relations                463
      with an assessor                   142    30%
      Job (much quoted speech)            55%
      Genesis                             16%
      Kings, Judges, Numbers               0%

## The real defect is one line of the prompt

`prefix.py` says *"Leave `claimed_by` empty when the NARRATOR states
something."* That is right for a narrated fact -- "In all this Job sinned not"
is the scroll speaking. It collapses three different cases into one empty
field, and the middle one is a genuine loss:

    the narrator states a FACT            empty is correct
    the text NAMES the assessor           empty is WRONG
    a character assesses inside speech    claimed_by works today

The regnal formula is the second case, in bulk. **"Ahab did evil in the sight
of the LORD" does not lack an assessor -- it names one.** The narrator is
reporting God's judgement, and "in the sight of" / "in the eyes of" says so
explicitly. Reading it as narrator voice loses the one thing the formula exists
to state.

That is a closed formula, so it needs no model. This pass recovers the assessor
wherever the text names it, over the graph as it already stands, for nothing.

## It writes a sidecar, not the graph

Per the backlog's own guardrail: a device proves itself in `out/` where it costs
nothing and can be deleted. And the old graph is held as an independent witness
-- adding derived fields to it in place is the edit that quietly destroys that.
`out/assessors.jsonl` is a proposal to fold in or discard.

    python tools/assessors.py            # what it finds, and the headroom
    python tools/assessors.py --json     # writes out/assessors.jsonl
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bibleont.schema import load_entities, load_relations         # noqa: E402
from bibleont.decompose import _load                              # noqa: E402

# Formulae that name the assessor inside the assessment itself. Each is a fixed
# string in the translations, which is what makes this deterministic rather
# than a judgement about who probably meant it.
NAMES_ASSESSOR = [
    (re.compile(r"in the (?:sight|eyes) of the LORD", re.I), "god"),
    (re.compile(r"in the (?:sight|eyes) of God", re.I), "god"),
    (re.compile(r"before the LORD", re.I), "god"),
    (re.compile(r"in (?:his|His) (?:sight|eyes)", re.I), "god"),
    (re.compile(r"in the (?:sight|eyes) of (?:the )?men", re.I), "people"),
]


def find(text: str):
    for pat, who in NAMES_ASSESSOR:
        if pat.search(text or ""):
            return who, pat.pattern
    return None, None


def _quoted():
    """Verses inside a quotation span, so the rule can refuse to fire there.

    Job 15:15 -- "the heavens are not clean in his sight" -- matched the
    formula and was assigned to God. But **Eliphaz is speaking.** The formula
    names whose SIGHT it is; the CLAIM belongs to the speaker, and the E3
    ruling is exactly this distinction: Jesus "asserted that Pilate said it",
    not the content. Inside quoted speech `claimed_by` is the speaker and the
    prompt already handles it, so this pass has no business there.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    from acts import quoted_verses                             # noqa: E402
    return quoted_verses()


def main() -> int:
    ents = load_entities()
    rels = load_relations()
    bsb = _load("verses.bsb.jsonl")
    assessed = [r for r in rels if r.type == "assessed_as"]
    have = [r for r in assessed if r.claimed_by]

    print("THE FIELD ALREADY EXISTS -- claimed_by, taught in prefix.py.")
    print(f"  assessed_as relations      {len(assessed):>5}")
    print(f"  already carry an assessor  {len(have):>5}   "
          f"{100*len(have)//max(len(assessed),1)}%")
    print(f"  missing one                {len(assessed)-len(have):>5}")
    print()

    inside = _quoted()
    out = []
    skipped = 0
    by_src = collections.Counter()
    for r in assessed:
        if r.claimed_by:
            continue
        if any(ref in inside for ref in (r.refs or [])):
            skipped += 1
            continue                  # a speaker owns this claim, not the
        dst = ents.get(r.dst)          # one whose "sight" the formula names
        # The assessment's own name carries the formula; the verse is the
        # fallback, because a node named "evil" may sit in a verse that says
        # "in the sight of the LORD".
        who, pat = find(dst.name if dst else "")
        src_of = "assessment name"
        if not who:
            for ref in (r.refs or []):
                who, pat = find(bsb.get(ref, ""))
                if who:
                    src_of = "verse text"
                    break
        if not who:
            continue
        by_src[src_of] += 1
        out.append({"src": r.src, "type": r.type, "dst": r.dst,
                    "refs": r.refs, "assessor": who,
                    "evidence": pat, "found_in": src_of,
                    "note": "derived deterministically; not applied to the "
                            "graph"})

    print(f"  inside quoted speech, left to the speaker: {skipped}")
    print()
    print(f"ASSESSOR RECOVERABLE WITHOUT A MODEL: {len(out)}")
    print(f"  from the assessment's own name  {by_src['assessment name']:>5}")
    print(f"  from the verse text             {by_src['verse text']:>5}")
    covered = len(have) + len(out)
    print(f"  coverage would go {100*len(have)//max(len(assessed),1)}% -> "
          f"{100*covered//max(len(assessed),1)}%")
    print()
    print("samples:")
    for o in out[:10]:
        s = ents.get(o["src"])
        d = ents.get(o["dst"])
        print(f"  {(o['refs'] or ['?'])[0]:12} "
              f"{(s.name if s else o['src'])[:18]:20} -> "
              f"{(d.name if d else o['dst'])[:32]:34} assessor={o['assessor']}")

    print()
    left = len(assessed) - covered
    print(f"STILL WITHOUT AN ASSESSOR: {left} "
          f"({100*left//max(len(assessed),1)}%)")
    print("  These are genuinely the narrator's own judgement, or a speaker")
    print("  the formula does not name. The first group is not a gap -- the")
    print("  narrator IS the assessor and the prompt should say so rather")
    print("  than leave the field empty and lose the distinction between")
    print("  'nobody assessed this' and 'the scroll assessed this'.")

    if "--json" in sys.argv:
        p = ROOT / "out" / "assessors.jsonl"
        with p.open("w", encoding="utf-8") as fh:
            for o in out:
                fh.write(json.dumps(o, ensure_ascii=False) + "\n")
        print(f"\nwrote {p}  ({len(out)} proposals, graph untouched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
