"""WHAT THE SWEEP SAYS ABOUT THE VOCABULARY (2026-10-16; asked whether anything
in the data influences the work towards finalizing the schemas).

Over a run's per-verse answers: how often each link type and group kind is
used, and how (added, kept, removed); member roles used that a kind does not
declare; terms used that are not in the lists at all; and what the judges
said had no term (none_fit) or could not decide (cant_tell).

    python tools/sweep/vocab_use.py <run dir>   -> <run dir>/vocab-use.json
"""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import context as C  # noqa: E402


def main():
    run = Path(sys.argv[1])
    ltypes = {l["type"] for l in C.vocabulary()}
    gkinds = {k: set(roles) for k, (_d, roles) in C.GROUP_KINDS.items()}
    links, groups, roles_off, unknown = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    none_fit, cant_tell, rhet = [], [], collections.Counter()
    verses = 0
    for p in sorted(run.glob("*.json")):
        # "1Sa", "2Ki", "3Jn" as well as "Gen": the first tally's pattern
        # missed every numbered book and counted 25,025 of 31,158 verses
        if not re.match(r"^[1-3]?[A-Z][a-z]{1,2}\.\d+\.\d+\.json$", p.name):
            continue
        a = json.loads(p.read_text(encoding="utf-8"))
        verses += 1
        for l in a.get("links") or []:
            t, act = l.get("type"), l.get("action")
            links[(t, act)] += 1
            if t not in ltypes:
                unknown[("link", t)] += 1
        for g in a.get("groups") or []:
            k, act = g.get("kind"), g.get("action")
            groups[(k, act)] += 1
            if k not in gkinds:
                unknown[("group", k)] += 1
            elif gkinds[k]:
                for m in g.get("members") or []:
                    if m.get("role") not in gkinds[k]:
                        roles_off[(k, m.get("role"))] += 1
        for r in a.get("referents") or []:
            if r.get("rhetorical"):
                rhet["rhetorical"] += 1
                rhet["implied" if r.get("implied") else "no implied"] += 1
                rhet["answered_by" if r.get("answered_by") else "no answered_by"] += 1
                rhet["a candidate" if r.get("choice") not in (None, "none", "cant_tell") else "none"] += 1
        for x in a.get("none_fit") or []:
            none_fit.append({"ref": a.get("ref"), **x})
        for x in a.get("cant_tell") or []:
            cant_tell.append({"ref": a.get("ref"), **x})
    out = {"verses": verses,
           "links": {f"{t}|{act}": n for (t, act), n in links.most_common()},
           "groups": {f"{k}|{act}": n for (k, act), n in groups.most_common()},
           "unused_link_types": sorted(ltypes - {t for t, _ in links}),
           "unused_group_kinds": sorted(set(gkinds) - {k for k, _ in groups}),
           "roles_not_declared": {f"{k}|{r}": n for (k, r), n in roles_off.most_common()},
           "terms_not_in_lists": {f"{w}|{t}": n for (w, t), n in unknown.most_common()},
           "rhetorical": dict(rhet), "none_fit": none_fit, "cant_tell": cant_tell}
    (run / "vocab-use.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{verses} verses; none_fit {len(none_fit)}; cant_tell {len(cant_tell)}")
    print("links:", dict(list(out["links"].items())[:30]))
    print("groups:", dict(list(out["groups"].items())[:30]))
    print("unused link types:", out["unused_link_types"])
    print("unused group kinds:", out["unused_group_kinds"])
    print("roles not declared:", dict(list(out["roles_not_declared"].items())[:15]))
    print("terms not in lists:", dict(list(out["terms_not_in_lists"].items())[:25]))
    print("rhetorical:", out["rhetorical"])


if __name__ == "__main__":
    main()
