"""MAJORITY OF THREE BLIND RUNS (plan 1.34; 2026-10-15: a third Haiku
vote, after Sonnet as tie-breaker scored no better than one Haiku run).

Per verse, each decision stands on a majority of the runs:
  referents   a slot's choice that at least two runs made
  links       a (src, type, dst) whose action at least two runs gave
              ("absent" counts: two runs not adding a link outvote one that did)
  groups      a group (kind + members) at least two runs proposed
A decision with no majority is HELD: written to held.json for a hand ruling, and
left as the builder had it.

    python tools/sweep/vote.py <out dir> <run dir> <run dir> <run dir>
"""
import collections
import json
import sys
from pathlib import Path


def suffix(x):
    return x.split("#", 1)[1] if "#" in (x or "") else (x or "")


def main():
    out, runs = Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]]
    out.mkdir(parents=True, exist_ok=True)
    need = len(runs) // 2 + 1
    held, n_dec, n_held = {}, 0, 0
    refs = sorted({p.stem for r in runs for p in r.glob("*.json") if not p.name.startswith(("P-", "_", "score", "escalate", "held"))})
    for ref in refs:
        ans = [json.loads((r / f"{ref}.json").read_text(encoding="utf-8")) for r in runs if (r / f"{ref}.json").exists()]
        if len(ans) < need:
            continue
        v = {"ref": ref, "referents": [], "links": [], "groups": [], "none_fit": [], "cant_tell": [], "voted": len(ans)}
        h = []
        # referents
        slots = collections.defaultdict(list)
        for a in ans:
            for r in a.get("referents") or []:
                slots[r.get("slot")].append(r)
        for s, rs in slots.items():
            n_dec += 1
            c = collections.Counter(suffix(r.get("choice")) for r in rs)
            choice, k = c.most_common(1)[0]
            if k >= need:
                pick = next(r for r in rs if suffix(r.get("choice")) == choice)
                v["referents"].append({**pick, "votes": k})
            else:
                h.append({"referent": s, "choices": dict(c)})
        # links: every key any run mentioned; a run that did not mention it said "absent"
        keys = collections.defaultdict(lambda: [None] * len(ans))
        own = f"{ref}#"
        for i, a in enumerate(ans):
            for l in a.get("links") or []:
                # a source in this verse by its local name, however the judge
                # wrote it ("Exo.8.13#cl1" or "cl1"), so one run's prefix does
                # not split the vote (score.py, 2026-10-16)
                src = l.get("src") or ""
                src = src[len(own):] if src.startswith(own) else src
                keys[(src, l.get("type"), suffix(l.get("dst")))][i] = l
        for k, ls in keys.items():
            n_dec += 1
            acts = collections.Counter((l or {}).get("action", "absent") for l in ls)
            act, cnt = acts.most_common(1)[0]
            if cnt >= need:
                if act != "absent":
                    pick = next(l for l in ls if l and l.get("action") == act)
                    v["links"].append({**pick, "votes": cnt})
            else:
                h.append({"link": " ".join(k), "actions": dict(acts)})
        # groups: by kind and member set
        gs = collections.defaultdict(list)
        for a in ans:
            for g in a.get("groups") or []:
                sig = (g.get("kind"), frozenset((m.get("role"), suffix(m.get("node"))) for m in g.get("members") or []))
                gs[(sig, g.get("action") == "remove")].append(g)
        for (sig, removed), lst in gs.items():
            n_dec += 1
            if len(lst) >= need:
                v["groups"].append({**lst[0], "votes": len(lst)})
            elif not removed:
                h.append({"group": sig[0], "members": sorted(map(list, sig[1])), "votes": len(lst)})
        for a in ans:
            v["none_fit"] += a.get("none_fit") or []
            v["cant_tell"] += a.get("cant_tell") or []
        (out / f"{ref}.json").write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
        if h:
            held[ref] = h
            n_held += len(h)
    (out / "held.json").write_text(json.dumps(held, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(refs)} verses; {n_dec} decisions; {n_held} held without a majority -> {out}")


if __name__ == "__main__":
    main()
