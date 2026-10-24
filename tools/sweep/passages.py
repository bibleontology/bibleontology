"""ONE PROMPT PER PASSAGE (plan 1.34; 2026-10-15: measure batching).

A judge call cost about 73,000 tokens in the calibration, about 6,000 of
them the verse: the rest is a general-purpose agent's fixed overhead. So a
passage is judged in one call. The vocabulary is given once, the verses in
order, and a verse's earlier neighbours in the same passage are the judge's
OWN decisions, not the builder's: a verse-by-verse judge could not see that
its answer for the verse before had merged two command groups.

    python tools/sweep/passages.py build <name> <ref> <ref> ...  -> out/sweep/prompts-passage/<name>.txt
    python tools/sweep/passages.py split <run dir>                -> <run dir>/<ref>.json from <name>.json

The judge answers {"passage": name, "verses": [one object per verse, in the
verse form of task.md]}; `split` writes each verse's object to its own file,
so tools/sweep/score.py and vote.py read passages and verses alike.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import context as C  # noqa: E402

DST = ROOT / "out" / "sweep" / "prompts-passage"

PREFACE = """You are judging a PASSAGE of several verses, one after another. Judge each verse exactly as the
instructions below describe, in order. When you judge a later verse, your own decisions for the verses before it
in this passage are part of its context: a fulfilment, a "likewise" or a referent may point back into them, by
full id (for example `Exo.8.12#cl3` or `Exo.8.12#g1`). Ids you mint for new groups must be unique in the passage:
prefix them with the verse ref (`Exo.8.12#g1`).

The vocabulary (`link_types`, `group_kinds`) is given once, at the start of the JSON; each verse's own JSON has the
rest.

Answer with ONLY this JSON object: {"passage": "<name>", "verses": [ <one answer per verse, in order, each in the
form given under "Answer" below> ]}

"""


def build(name, refs):
    ctxs = C.build(refs)
    task = (Path(__file__).with_name("task.md")).read_text(encoding="utf-8")
    first = ctxs[refs[0]]
    shared = {"link_types": first["link_types"], "group_kinds": first["group_kinds"]}
    verses = []
    for i, ref in enumerate(refs):
        c = {k: v for k, v in ctxs[ref].items() if k not in ("link_types", "group_kinds")}
        if i:
            # its neighbours are in the passage: keep the text of the verses
            # before the passage, drop the repetition of the passage itself
            c["before"] = [b for b in c["before"] if not any(b["ref"] == ctxs[r]["verse"] for r in refs[:i])]
        verses.append(c)
    DST.mkdir(parents=True, exist_ok=True)
    body = PREFACE + task.replace("## The verse", "## The passage") + "\n" + json.dumps(
        {"passage": name, **shared, "verses": verses}, ensure_ascii=False, separators=(",", ":")) + "\n"
    (DST / f"{name}.txt").write_text(body, encoding="utf-8")
    print(f"{name}: {len(refs)} verses, {len(body):,} characters -> {DST.relative_to(ROOT)}")


def split(run):
    run = Path(run)
    n = 0
    for p in sorted(run.glob("P-*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for v in d.get("verses") or []:
            if v.get("ref"):
                (run / f"{v['ref']}.json").write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
                n += 1
    print(f"{n} verses split out in {run}")


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(sys.argv[2], sys.argv[3:])
    else:
        split(sys.argv[2])
