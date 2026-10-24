"""WHERE TWO BLIND RUNS DISAGREE: what goes up to Sonnet (plan 1.34).

Each verse is judged twice by Haiku, blind. A decision both runs make the
same way stands. A decision they make differently, or one either run says it
cannot make, is escalated. Compared at the level of the decision, not the
wording:

  referents   slot -> the candidate chosen ("none" and "cant_tell" included)
  links       (src, type, dst) -> keep, remove or add
  groups      each run's groups as (kind, its members' set)

    python tools/sweep/agree.py <run a> <run b>     -> escalate.json beside run a
"""
import json
import sys
from pathlib import Path


def suffix(x):
    return x.split("#", 1)[1] if "#" in (x or "") else (x or "")


def decisions(d):
    refs = {r.get("slot"): suffix(r.get("choice")) for r in d.get("referents") or []}
    links = {(l.get("src"), l.get("type"), suffix(l.get("dst"))): l.get("action") for l in d.get("links") or []}
    groups = {(g.get("kind"), frozenset((m.get("role"), suffix(m.get("node"))) for m in g.get("members") or []))
              for g in d.get("groups") or [] if g.get("action") != "remove"}
    return refs, links, groups


def main():
    a, b = Path(sys.argv[1]), Path(sys.argv[2])
    out, n_dec, n_dis = {}, 0, 0
    for pa in sorted(a.glob("*.json")):
        if pa.name.startswith("score") or pa.name == "escalate.json":
            continue
        pb = b / pa.name
        if not pb.exists():
            continue
        da, db = json.loads(pa.read_text(encoding="utf-8")), json.loads(pb.read_text(encoding="utf-8"))
        ra, la, ga = decisions(da)
        rb, lb, gb = decisions(db)
        dis = []
        for s in sorted(set(ra) | set(rb)):
            n_dec += 1
            if ra.get(s) != rb.get(s) or "cant_tell" in (ra.get(s), rb.get(s)):
                dis.append({"referent": s, "a": ra.get(s), "b": rb.get(s)})
        for k in sorted(set(la) | set(lb), key=str):
            n_dec += 1
            if la.get(k, "absent") != lb.get(k, "absent"):
                dis.append({"link": " ".join(k), "a": la.get(k), "b": lb.get(k)})
        for g in ga ^ gb:
            dis.append({"group": g[0], "members": sorted(map(list, g[1])), "only_in": "a" if g in ga else "b"})
        n_dec += len(ga | gb)
        ct = (da.get("cant_tell") or []) + (db.get("cant_tell") or [])
        n_dis += len(dis)
        if dis or ct:
            out[pa.stem] = {"disagree": dis, "cant_tell": ct}
    (a / "escalate.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{n_dis} of {n_dec} decisions differ; {len(out)} verses to escalate -> {a / 'escalate.json'}")


if __name__ == "__main__":
    main()
