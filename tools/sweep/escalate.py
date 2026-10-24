"""THE SONNET PROMPTS: a verse whose two Haiku runs disagreed (plan 1.34).

Sonnet reads the same task and verse as Haiku did, plus the list of decisions
the two blind runs made differently or could not make. It answers the whole
verse in the same form, deciding the disputed points itself; it is told the
earlier readings may both be wrong. Nothing from the gold is in it.

    python tools/sweep/escalate.py <run a> <run b>   -> out/sweep/prompts-sonnet/<ref>.txt

Then the combined answer per verse (tools/sweep/combine.py): Sonnet's for an
escalated verse, the agreed Haiku answer for the rest.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "out" / "sweep" / "prompts"
DST = ROOT / "out" / "sweep" / "prompts-sonnet"


def main():
    a = Path(sys.argv[1])
    esc = json.loads((a / "escalate.json").read_text(encoding="utf-8"))
    DST.mkdir(parents=True, exist_ok=True)
    for ref, v in esc.items():
        lines = []
        for d in v["disagree"]:
            if "referent" in d:
                lines.append(f"- slot {d['referent']}: one reader chose {d['a']}, the other {d['b']}")
            elif "link" in d:
                lines.append(f"- link {d['link']}: one reader said {d['a'] or 'nothing'}, the other {d['b'] or 'nothing'}")
            else:
                lines.append(f"- a {d['group']} group with members {d['members']}: proposed by one reader only")
        for c in v["cant_tell"]:
            lines.append(f"- left undecided by a reader: {c.get('what')} ({c.get('why')})")
        extra = ("\n\n## Two earlier readers disagreed\n\nTwo earlier readings of this verse differed on the points "
                 "below, or left them undecided. Decide each yourself from the evidence; either earlier reading, "
                 "or both, may be wrong. Answer the WHOLE verse in the same JSON form as asked above.\n\n"
                 + "\n".join(lines) + "\n")
        (DST / f"{ref}.txt").write_text((SRC / f"{ref}.txt").read_text(encoding="utf-8") + extra, encoding="utf-8")
    print(f"{len(esc)} escalation prompts -> {DST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
