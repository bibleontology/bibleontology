"""HOLD THE NARRATOR'S RELATIONS THAT ARE SPEECH (the committee of 2026-10-21,
the scholar's first finding; the extension of D1, which was ruled "all as
recommended" for the verb statements on 2026-10-20).

D1 held the verb statements whose clause the Berean prints inside quotation
marks. The relation files had the same fault: 250 relations in the narrator's
voice whose every verse is speech in the Berean -- 2 Sam 12:9 "David killed
Uriah" (Nathan's charge), Gen 20:5 (Abimelech on his own integrity), Job 23:16
(Job), Gen 49:5 (Jacob's blessing) -- were stated as the text's own fact.

A relation is held when, with no speaker on record:
  - every verse it rests on is printed wholly inside quotation marks
    (tools/meaning/quoted.py), and
  - it is a claim about the world, not about the speech itself. Relations of
    the language, meaning, imagery, story and numbers categories, and those
    that record a speech act (told, quoted, asserted_by, explained,
    signifies, warned, besought, titled, self_designated_as,
    distinguished_from, contrary_to, specializes), are true wherever they sit:
    that a saying draws on an image, that one statement grounds another, that
    a speaker quotes someone.

Held is reversible: the row stays in the store with its reason, the server and
the exports skip it, and a later pass may credit the speaker or cite a
narrative verse that says the same (kinship read from how a speaker names
someone, "Elishama son of Ammihud" in Num 1:10, is the first such pass).

Only the held lines are rewritten; every other line of every file is left as
it was, byte for byte.

    python tools/meaning/hold_quoted_relations.py [--dry-run]
"""
import collections
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
from quoted import berean_quotes  # noqa: E402

REASON = "inside quoted speech (the Berean's quotation marks), speaker not on record"
EXEMPT_CATEGORIES = {"language", "meaning", "imagery", "story", "numbers"}
EXEMPT_TYPES = {"told", "quoted", "specializes", "explained", "signifies", "self_designated_as",
                "distinguished_from", "contrary_to", "besought", "warned", "titled", "asserted_by", "states"}


def categories():
    spec = yaml.safe_load((ROOT / "ontology" / "schema" / "relationship_types.yaml").read_text(encoding="utf-8"))
    return {k: (v or {}).get("category") for k, v in (spec.get("types") or {}).items()}


def about_the_world(r, cat):
    """A claim about the world, which the narrator states or does not --
    not a fact about the speech itself."""
    return r.get("type") not in EXEMPT_TYPES and cat.get(r.get("type")) not in EXEMPT_CATEGORIES


def credited():
    """The relations the structure sweep credits to their speaker at export
    (out/sweep/speaker-credits.jsonl, plan 8.1c): already never the narrator's,
    and a speaker on record is better than a hold. The first run held 39 of
    them; the sweep's credits fell from 69 to 30 until this was added."""
    p = ROOT / "out" / "sweep" / "speaker-credits.jsonl"
    if not p.exists():
        return set()
    return {(c["src"], c["type"], c["dst"]) for c in (json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
                                                     if x.strip())}


_CREDITED = None


def to_hold(r, cat, quotes):
    global _CREDITED
    if _CREDITED is None:
        _CREDITED = credited()
    if r.get("held") or r.get("described") or r.get("claimed_by") or not about_the_world(r, cat):
        return False
    if (r.get("src"), r.get("type"), r.get("dst")) in _CREDITED:
        return False
    refs = r.get("refs") or []
    return bool(refs) and all(quotes.get(x) == "whole" for x in refs)


def main():
    dry = "--dry-run" in sys.argv
    cat, (quotes, _t) = categories(), berean_quotes()
    by_type, by_file = collections.Counter(), collections.Counter()
    for p in sorted((ROOT / "ontology" / "relations").glob("*.jsonl")):
        # line endings kept as they are (newline=""): a file stored with
        # \r\n stays so, and only the held lines differ
        with open(p, encoding="utf-8", newline="") as f:
            raw = f.read()
        lines = raw.split("\n")
        changed = False
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            r = json.loads(line)
            # released: a row this pass held that the sweep now credits to
            # its speaker
            if r.get("held") == REASON and (r.get("src"), r.get("type"), r.get("dst")) in credited():
                del r["held"]
                lines[i] = json.dumps(r, ensure_ascii=False) + ("\r" if line.endswith("\r") else "")
                changed = True
                by_type["released (speaker credited): " + r["type"]] += 1
                continue
            if r.get("type") == "states" or not to_hold(r, cat, quotes):
                continue
            r["held"] = REASON
            lines[i] = json.dumps(r, ensure_ascii=False) + ("\r" if line.endswith("\r") else "")
            changed = True
            by_type[r["type"]] += 1
            by_file[p.name] += 1
        if changed and not dry:
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write("\n".join(lines))
    print(f"{'would hold' if dry else 'held'} {sum(by_type.values())} relations in {len(by_file)} files")
    print("by type:", dict(by_type.most_common()))


if __name__ == "__main__":
    main()
