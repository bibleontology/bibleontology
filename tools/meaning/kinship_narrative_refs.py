"""KINSHIP THE NARRATOR ALSO STATES: cite the narrative verse, release the hold
(the committee of 2026-10-21; the scholar: "where the narrator also states the
fact elsewhere (Num 1's fathers), cite that verse instead").

tools/meaning/hold_quoted_relations.py held the relations whose every verse is
speech. Some kinship among them is how a speaker names someone -- "Elishama
son of Ammihud" in God's census instructions (Num 1:10) -- and the narrator
says the same elsewhere (Num 7:48). This finds that verse and cites it, so the
fact rests on the narrator's words and is shown again.

A father_of row is released only when ONE narrative verse does all three:
  1. resolves both names to these two records (out/mentions.jsonl.gz), so no
     identity is assumed from a name alone (Matt 23:35's Zechariah is not
     taken to be the prophet's from "son of Berechiah");
  2. states the relation in words: "<son> son of <father>", "<father> fathered
     <son>", "<father> ... the father of <son>";
  3. says it outside the Berean's quotation marks.

Only the changed lines are rewritten, line endings kept.

    python tools/meaning/kinship_narrative_refs.py [--dry-run]
"""
import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
from derive import BOOK  # noqa: E402  (MACULA code -> the Berean's book name)
from hold_quoted_relations import REASON  # noqa: E402
from quoted import berean_quotes  # noqa: E402


def mentions_by_verse():
    out = collections.defaultdict(set)
    for line in gzip.open(ROOT / "out" / "mentions.jsonl.gz", "rt", encoding="utf-8"):
        if line.strip():
            m = json.loads(line)
            vid = m["occurrence"].split("#")[0]
            b, c, v = vid.split(".")
            out[f"{BOOK.get(b, b)} {c}:{v}"].add(m["record"])
    return out


def outside(text, start):
    """Whether position `start` in a verse stands outside its quotation marks
    (the state the verse opens in is taken as closed: a verse partly quoted
    has its own marks)."""
    state = False
    for ch in text[:start]:
        if ch == "“":
            state = True
        elif ch == "”":
            state = False
    return not state


def states(text, father, son):
    pats = [rf"\b{re.escape(son)},? (?:the )?son of {re.escape(father)}\b",
            rf"\b{re.escape(father)} fathered {re.escape(son)}\b",
            rf"\b{re.escape(father)}\b[^.;]{{0,40}}\bthe father of {re.escape(son)}\b"]
    for p in pats:
        for m in re.finditer(p, text):
            if outside(text, m.start()):
                return True
    return False


def main():
    dry = "--dry-run" in sys.argv
    names = {}
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        r = json.loads(line)
        names[r["id"]] = (r.get("name") or r["id"]).split(" (")[0]
    quotes, texts = berean_quotes()
    ment = mentions_by_verse()
    released = []
    for p in sorted((ROOT / "ontology" / "relations").glob("*.jsonl")):
        with open(p, encoding="utf-8", newline="") as f:
            lines = f.read().split("\n")
        changed = False
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("held") != REASON or r.get("type") != "father_of":
                continue
            father, son = names.get(r["src"], ""), names.get(r["dst"], "")
            found = [ref for ref, recs in ment.items()
                     if r["src"] in recs and r["dst"] in recs and quotes.get(ref) != "whole"
                     and ref in texts and states(texts[ref][0], father, son)]
            if not found:
                continue
            r["refs"] = r["refs"] + sorted(set(found) - set(r["refs"]))
            del r["held"]
            r["narrator_refs_from"] = "kinship_narrative_refs: the narrator states it in " + ", ".join(sorted(found))
            lines[i] = json.dumps(r, ensure_ascii=False) + ("\r" if line.endswith("\r") else "")
            changed = True
            released.append((r["src"], r["dst"], sorted(found)))
        if changed and not dry:
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write("\n".join(lines))
    print(f"{'would release' if dry else 'released'} {len(released)} father_of rows, each with a narrative verse:")
    for s, d, f in released:
        print(f"  {s} -> {d}: {', '.join(f)}")


if __name__ == "__main__":
    main()
