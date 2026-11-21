"""THE THIN-BOOK PASS: verse-by-verse, for books the graph has almost no claims about (2026-11-13).

Found via /api/coverage: 2Thess and Obad have ZERO relations anywhere in the ontology despite full structural
parsing; 14 more small books sit under a 0.27 claims-per-verse ratio (Nah, 1Thess, Eccl, 1Tim, Zech, 2John, Song,
Zeph, Hab, 2Pet, Jude, Mic, Mal, 2Tim). One verse per call, Berean text only: "what does this verse state, as a
plain subject-does/is-X claim?" up to 3 per verse. The Mac only proposes; nothing reaches the graph untouched --
Claude judges every candidate against the verse before anything is added.

    python tools/meaning/book_claims_gap.py export
    python tools/grunt/grunt.py push out/grunt/jobs/30-thin-books.jsonl
    python tools/grunt/grunt.py pull
    python tools/meaning/book_claims_gap.py report
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

NAME = "30-thin-books"
JOBS = ROOT / "out" / "grunt" / "jobs"
DONE = ROOT / "out" / "grunt" / "done"
BOOKS = ["2Thess", "Obad", "Nah", "1Thess", "Eccl", "1Tim", "Zech", "2John", "Song",
         "Zeph", "Hab", "2Pet", "Jude", "Mic", "Mal", "2Tim"]
# job 31 (2026-11-13): the next tier, larger books also under about 0.35 claims a verse
if len(sys.argv) > 2 and sys.argv[1] == "export":
    NAME = sys.argv[2]
    BOOKS = sys.argv[3].split(",")
OPTIONS = {"temperature": 0, "num_ctx": 2048}

BRIEF = """You are given one verse of the Bible, in English. State what this verse itself claims, each as one short
plain sentence with its own subject ("Paul warns the Thessalonians about idleness"). Up to 3 claims. Only what the
text itself says -- no interpretation, no doctrine, no cross-reference. If the verse is a greeting, a transition, or
makes no standalone claim, return an empty list.

Answer with JSON only: {"claims": ["...", "..."]}"""


def export():
    d = S.load()
    its = []
    for (b, c, v) in sorted(d["verses"]):
        if b not in BOOKS:
            continue
        text = d["verses"][(b, c, v)]
        if not (text or "").strip():
            continue
        ref = f"{b} {c}:{v}"
        its.append({"key": f"t{len(its):04d}", "ref": ref,
                     "messages": [{"role": "system", "content": BRIEF},
                                  {"role": "user", "content": text}]})
    JOBS.mkdir(parents=True, exist_ok=True)
    with open(JOBS / f"{NAME}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "book_claims_gap"}}) + "\n")
        for it in its:
            f.write(json.dumps({"key": it["key"], "messages": it["messages"]}, ensure_ascii=False) + "\n")
    with open(JOBS / f"{NAME}.key.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in its:
            f.write(json.dumps({"key": it["key"], "ref": it["ref"]}, ensure_ascii=False) + "\n")
    print(f"{len(its)} verses across {len(BOOKS)} books -> {JOBS / (NAME + '.jsonl')}")


def report():
    key = {json.loads(l)["key"]: json.loads(l)["ref"] for l in open(JOBS / f"{NAME}.key.jsonl", encoding="utf-8")}
    rows = [json.loads(l) for l in open(DONE / f"{NAME}.jsonl", encoding="utf-8")]
    n = 0
    for d in rows:
        try:
            claims = json.loads(d["content"]).get("claims") or []
        except Exception:
            claims = []
        if claims:
            n += 1
            print(key.get(d["key"], d["key"]), "->", claims)
    print(f"\n{n} of {len(rows)} verses yielded a candidate claim")


if __name__ == "__main__":
    if sys.argv[1:2] == ["export"]:
        export()
    elif sys.argv[1:2] == ["report"]:
        report()
    else:
        print(__doc__)
