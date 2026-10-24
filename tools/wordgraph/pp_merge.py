"""THE PREPOSITIONAL PHRASES, RULE AND JUDGE TOGETHER (plan 2.13).

Joins out/wordgraph/prep-phrases.jsonl.gz (each phrase, with a relation where
a certain rule named one) to the judged pass's answers (out/sweep/runs/<run>/
J-*.json, pp_judge.py). A rule's relation is kept as `by: rule`; a judged one
is a reading, `by: judged`, with its confidence. "none" stays none. Writes the
joined file and prints what was decided, overall and per preposition.

    python tools/wordgraph/pp_merge.py <run>   -> out/wordgraph/prep-phrases-judged.jsonl.gz
"""
import collections
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from pp_judge import RELATIONS  # noqa: E402

from pp_judge import SCHEMA  # noqa: E402

SRC = ROOT / "out" / "wordgraph" / "prep-phrases.jsonl.gz"
# the two-level re-judge (PP_SCHEMA=2) writes beside the first, never over it
DST = ROOT / "out" / "wordgraph" / ("prep-phrases-judged-2.jsonl.gz" if SCHEMA == "2"
                                    else "prep-phrases-judged.jsonl.gz")
FAMILY = {}
if SCHEMA == "2":
    _pr = json.loads((ROOT / "ontology" / "schema" / "prep_relations.json").read_text(encoding="utf-8"))
    for _f, _v in _pr["families"].items():
        FAMILY[_f] = _f
        for _t in _v["types"]:
            FAMILY[_t] = _f


# THE FILE THE RE-JUDGE READ, KEPT: its ids are numbered within the verse a
# phrase was filed under, so refiling (2026-10-18: each word's verse now read
# from MACULA, not guessed) renumbers them. Its answers are translated to the
# phrase's old_id, which is numbered by sentence and never moves.
JUDGED_2_INPUT = ROOT / "out" / "wordgraph" / "prep-phrases.judged-2-input.jsonl.gz"


def answers(run):
    out = {}
    for p in (ROOT / "out" / "sweep" / "runs" / run).glob("J-*.json"):
        for a in json.loads(p.read_text(encoding="utf-8")).get("answers") or []:
            out.setdefault(a.get("id"), a)
    return out


def id_to_old(path):
    to_old = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            for p in json.loads(line)["pp"]:
                to_old[p["id"]] = p["old_id"]
    return to_old


def main():
    """pp_merge.py <run> [<later run> ...]: a later run's answers replace an
    earlier run's for the phrases it judged (the re-judge of the phrases
    first judged under the wrong verse, 2026-10-18). A later run was made on
    the current file, so its ids are the current ids."""
    judged = answers(sys.argv[1])
    if SCHEMA == "2":
        if not JUDGED_2_INPUT.exists():
            raise SystemExit(f"{JUDGED_2_INPUT.relative_to(ROOT)} missing: the re-judge's answers cannot be joined")
        to_old = id_to_old(JUDGED_2_INPUT)
        judged = {to_old[k]: a for k, a in judged.items() if k in to_old}
    if sys.argv[2:]:
        now_old = id_to_old(SRC)
        for later in sys.argv[2:]:
            got = answers(later)
            # an id the judge made up is skipped and counted; many of them mean
            # the run was made on another file, and the merge stops
            missing = [k for k in got if k not in now_old]
            if len(missing) > 0.01 * len(got):
                raise SystemExit(f"{later}: {len(missing)} answers name no current phrase (e.g. {missing[0]})")
            if missing:
                print(f"{later}: {len(missing)} answers name no phrase, skipped")
            for k, a in got.items():
                if k in now_old:
                    judged[now_old[k]] = {**a, "run": later}
            print(f"{later}: {len(got):,} answers laid over the first run's")
    rel, conf, per_prep, unanswered = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter), 0
    with gzip.open(SRC, "rt", encoding="utf-8") as f, gzip.open(DST, "wt", encoding="utf-8") as g:
        g.write(next(f))
        for line in f:
            d = json.loads(line)
            for p in d["pp"]:
                if p["relation"]:
                    p["kind"] = "rule"
                else:
                    # both judged passes are joined by old_id (filed under the
                    # first verse of its sentence, numbered there), which no
                    # refiling changes
                    a = judged.get(p.get("old_id") or p["id"])
                    if not a:
                        unanswered += 1
                        p["kind"] = "unanswered"
                    else:
                        # a name off the closed list ("agency", 6 times in the
                        # first run) is not a choice: it counts as none
                        r = a.get("relation")
                        p["relation"] = r if r in RELATIONS and r != "none" else None
                        # LOW COUNTS AS NONE (2026-10-17, "Low
                        # counts as none" chosen: unresolved beats wrong). The guess is
                        # kept beside it, for whoever confirms it later.
                        if a.get("confidence") == "low" and p["relation"]:
                            p["low_guess"], p["relation"] = p["relation"], None
                        p["kind"] = "judged"
                        p["confidence"] = a.get("confidence")
                        p["by"] = a.get("why")
                        if a.get("run"):
                            p["run"] = a["run"]
                        conf[a.get("confidence")] += 1
                if SCHEMA == "2" and p["relation"]:
                    # which level was named: a type, or only its family
                    p["family"] = FAMILY.get(p["relation"])
                    p["level"] = "family" if p["relation"] == p["family"] else "type"
                key = p["relation"] or ("none" if p["kind"] == "judged" else p["kind"])
                rel[(p["kind"], key)] += 1
                per_prep[f"{p['prep']['l']} {p['prep']['s']}"][key] += 1
            g.write(json.dumps(d, ensure_ascii=False) + "\n")
    total = sum(rel.values())
    named = sum(v for (k, r), v in rel.items() if r not in ("none", "unanswered"))
    print(f"{total:,} phrases; relation named {named:,} ({100 * named / total:.1f}%); "
          f"judged none {rel[('judged', 'none')]:,}; unanswered {unanswered:,}")
    print("by rule:  ", {r: v for (k, r), v in rel.most_common() if k == "rule"})
    print("judged:   ", {r: v for (k, r), v in rel.most_common() if k == "judged"})
    print("confidence of judged:", dict(conf))
    for prep, c in sorted(per_prep.items(), key=lambda x: -sum(x[1].values()))[:8]:
        n = sum(c.values())
        print(f"  {prep:14s} {n:6,}: " + ", ".join(f"{r} {100 * v / n:.0f}%" for r, v in c.most_common(5)))
    print("->", DST.relative_to(ROOT))


if __name__ == "__main__":
    main()
