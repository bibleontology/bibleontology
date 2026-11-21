"""Hold the "Who did what" rows four reads agree the passage does not say (tools/meaning/cast_judge.py tally ->
out/structure-apply/cast-hold.json). Written 2026-11-13.

A cast row is one or more relations (its subjects) of one type to one object, cited inside the event's telling. Each
relation behind a held row gets `held` with its reason: the server and the exports skip it, the row stays in the
store, and it is reversible like every hold. A relation that is also cited OUTSIDE this event is not held (its other
citation may stand); it is listed for a reader instead. Only held lines are rewritten.

    python tools/meaning/cast_hold.py [--dry-run]
"""
import io
import contextlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
sys.stdout.reconfigure(encoding="utf-8")
REASON = "the passage does not say it: four reads agree (the Mac twice, DeepSeek twice; cast check, 2026-11-13)"


def norm(ref):
    """'1 Samuel 17:4' and '1Sam 17:4' -> ('1sa', '17:4'): a book's first three letters and its first verse."""
    m = re.match(r"^\s*([1-3]?\s*[A-Za-z]+)\.?\s+(\d+[:.]\d+)", str(ref))
    if not m:
        return None
    return re.sub(r"\s", "", m.group(1)).lower()[:3], m.group(2).replace(".", ":")


def main(dry):
    with contextlib.redirect_stdout(io.StringIO()):
        import server as S
        d = S.load()
    hold = json.load(open(ROOT / "out" / "structure-apply" / "cast-hold.json", encoding="utf-8"))
    targets, kinds = [], {}
    for h in hold:
        if h["event"] not in kinds:
            with contextlib.redirect_stdout(io.StringIO()):
                c = S.api_entity(d, {"id": [h["event"]]})
            kinds[h["event"]] = (c.get("evcard") or {}).get("cast") or []
        row = next((r for r in kinds[h["event"]] if r["verb"] == h["verb"] and r["object"]["id"] == h["object"]
                    and sorted(s["id"] for s in r["subjects"]) == sorted(h["subjects"])), None)
        if not row:
            print("no longer on the card:", h["claim"])
            continue
        cited = {norm(c["ref"]) for c in row["cites"]}
        targets.append((set(h["subjects"]), row["kind"], h["object"], cited, h))
    held, skipped, n_lines = [], [], 0
    for path in sorted((ROOT / "ontology" / "relations").glob("*.jsonl")):
        # read as bytes: read_text turns CRLF into LF, and the relation files are stored -text, most with CRLF -- the
        # first run rewrote 4,475 lines of 17 files to change 39 (2026-11-13). Each line keeps its own ending.
        lines = path.read_bytes().decode("utf-8").split("\n")
        changed = False
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("held"):
                continue
            for subs, kind, obj, cited, h in targets:
                if r.get("src") in subs and r.get("type") == kind and r.get("dst") == obj:
                    refs = {norm(x) for x in r.get("refs") or []}
                    if not refs & cited:
                        continue
                    if refs - cited:
                        skipped.append((h["claim"], path.name, sorted(map(str, refs - cited))))
                        continue
                    r["held"] = REASON
                    lines[i] = json.dumps(r, ensure_ascii=False) + ("\r" if line.endswith("\r") else "")
                    changed = True
                    held.append((h["claim"], path.name))
                    n_lines += 1
        if changed and not dry:
            path.write_bytes("\n".join(lines).encode("utf-8"))
    print(f"{len(targets)} rows; {n_lines} relations held; {len(skipped)} cited elsewhere too, left for a reader")
    for s in skipped:
        print("  cited elsewhere:", s)
    (ROOT / "ontology" / "provenance" / "meaning" / "cast-hold-2026-11-13.json").write_text(
        json.dumps({"reason": REASON, "held": held, "cited_elsewhere": skipped, "rows": hold}, ensure_ascii=False,
                   indent=1), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
