"""THE RULINGS AS CODE, AFTER THE VOTE (plan 1.34: "a ruling becomes a
builder rule stated generally").

Round 2 of the calibration (2026-10-15) left 12 gold rows that every judge
missed, and several were consequences of what the judges had already made:
they built the turn but not the `content` link R1 asks for. A consequence
needs no judgement, so it is derived here, not asked for again:

  D1  content    a turn's saying clause (its frame) is linked by `content`
                 to what is said: its first part, or the imperative group
                 that part belongs to (R1)
  D2  nesting    a turn whose frame is a part of another turn is a part of
                 that turn (R1, R2: speech nests)
  D3  one home   a clause that is a part of an inner turn is not also a
                 direct part of the turn around it, so its speaker is the
                 inner turn's sender, not the outer one's (R2)
  D4  commanded  a nested turn whose frame is a command to speak is spoken
                 by the one commanded: the outer turn's addressee (R2)

Applied to each verse's final state (the builder's, with the vote's answer
over it), and written out as an answer in the same form, so score.py reads
it like any run. Every derived link and group carries `derived` with the
rule that made it.

    python tools/sweep/derive.py <voted dir> <out dir>
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import score as S  # noqa: E402

CTX = ROOT / "out" / "sweep" / "context"


def derive(ctx, ans):
    v = S.Verse(ctx, ans)
    mood = {c["id"]: (c.get("mood") or "", c.get("force") or "") for c in ctx["clauses"]}
    order = {c["id"]: i for i, c in enumerate(ctx["clauses"])}
    groups = {gid: {"kind": g["kind"], "members": [(r, S.suffix(n)) for r, n in g["members"]]}
              for gid, g in v.groups.items()}
    links = set(v.links)
    made = []

    def turns():
        return {gid: g for gid, g in groups.items() if g["kind"] == "turn"}

    def frame_of(g):
        return next((n for r, n in g["members"] if r == "frame"), None)

    # D2 nesting
    for a_id, a in turns().items():
        for b_id, b in turns().items():
            if a_id == b_id:
                continue
            fb = frame_of(b)
            if fb and ("part", fb) in a["members"] and ("part", b_id) not in a["members"]:
                a["members"].append(("part", b_id))
                made.append(("D2", a_id, b_id))
    # D3 one home: a clause in an inner turn leaves the outer turn's direct parts
    for a_id, a in turns().items():
        inner = [groups[n] for r, n in a["members"] if r == "part" and n in groups and groups[n]["kind"] == "turn"]
        owned = {n for g in inner for r, n in g["members"] if r in ("part", "frame")}
        keep = [(r, n) for r, n in a["members"] if not (r == "part" and n in owned)]
        if len(keep) != len(a["members"]):
            made.append(("D3", a_id, sorted(owned)))
            a["members"] = keep
    # D4 commanded speech
    for a_id, a in turns().items():
        addressee = next((n for r, n in a["members"] if r == "addressee"), None)
        for r, b_id in list(a["members"]):
            b = groups.get(b_id)
            if r != "part" or not b or b["kind"] != "turn" or not addressee:
                continue
            fb = frame_of(b)
            if fb and (mood.get(fb, ("", ""))[0] == "imperative" or mood.get(fb, ("", ""))[1] == "directive"):
                b["members"] = [(rr, nn) for rr, nn in b["members"] if rr != "sender"] + [("sender", addressee)]
                made.append(("D4", b_id, addressee))
    def commands(gid):
        g = groups.get(gid) or {}
        return [n for r, n in g.get("members", []) if r == "command"] if g.get("kind") == "imperative" else []

    # D1a CONTENT POINTS AT A GROUP ONLY WHEN IT IS A COLLECTION. R1: "to the
    # imperative group when what is said is a collection of commands". The
    # judges also pointed it at a command-plus-aim group; such a link goes to
    # the command itself.
    for (a, t, b) in sorted(links):
        if t == "content" and b in groups and groups[b]["kind"] == "imperative" and len(commands(b)) < 2:
            if commands(b):
                links.discard((a, t, b))
                links.add((a, t, commands(b)[0]))
                made.append(("D1a", a, b, commands(b)[0]))
    # D5 A BARE PRESENTATIVE IS NOT THE CLAUSE IT PRESENTS. The clean builder
    # splits "here!" / "there!" (hinneh) off as a clause of its own, and a judge
    # then took it as a condition's consequence; the consequence is the clause
    # it introduces, the next one.
    bare = {c["id"] for c in ctx["clauses"]
            if not c.get("mood") and re.fullmatch(r"\W*(here|there|behold|see|look|lo)\W*", (c.get("gloss") or "").lower())}
    nxt = {c["id"]: ctx["clauses"][i + 1]["id"] for i, c in enumerate(ctx["clauses"][:-1])}
    for gid, g in groups.items():
        for i, (r, n) in enumerate(g["members"]):
            if n in bare and n in nxt and r not in ("part",):
                g["members"][i] = (r, nxt[n])
                made.append(("D5", gid, n, nxt[n]))
    for (a, t, b) in sorted(links):
        if b in bare and b in nxt and t != "and":
            links.discard((a, t, b))
            links.add((a, t, nxt[b]))
            made.append(("D5", a, t, b, nxt[b]))
    # D6 A RESULT IS NOT ALSO A PLAIN "AND" OR "THEN" (R4)
    for (a, t, b) in sorted(links):
        if t == "result":
            for plain in ("then", "and"):
                if (a, plain, b) in links:
                    links.discard((a, plain, b))
                    made.append(("D6", a, plain, b))
    # D1 content
    for t_id, t in turns().items():
        f = frame_of(t)
        if not f or not f.startswith("cl"):
            continue
        parts = [n for r, n in t["members"] if r == "part"]
        clauses = sorted((n for n in parts if n in order and order[n] > order.get(f, -1)), key=order.get)
        target = None
        if clauses:
            target = clauses[0]
            for gid, g in groups.items():
                if g["kind"] == "imperative" and ("command", target) in g["members"] and len(commands(gid)) >= 2:
                    target = gid
                    break
        elif any(r == "part" and n in groups and groups[n]["kind"] == "imperative" for r, n in t["members"]):
            # what is said is a group: its collection, or its one command
            g_id = next(n for r, n in t["members"] if r == "part" and n in groups and groups[n]["kind"] == "imperative")
            target = g_id if len(commands(g_id)) >= 2 else (commands(g_id) or [g_id])[0]
        elif parts:
            target = next((n for n in parts if n in groups), None)
        # a content link the judges already made from this frame is enough
        if any(a == f and tt == "content" for a, tt, b in links):
            target = None
        if target and (f, "content", target) not in links:
            links.add((f, "content", target))
            made.append(("D1", f, target))
    # back to an answer: every final group restated, the builder's that went removed
    # THE DIVINE FLAGS GO THROUGH. They route a decision to a hand ruling; the first
    # derive pass restated the answer without them (28 flags became 0).
    div_slots = {s for s, _c in v.divine if s in v.slots}
    div_groups = {S.suffix(g) for g, _k in v.divine if S.suffix(g) not in v.slots}
    # So do R8's rhetorical answers and R7's extended turns: the first bench2
    # derive restated both away (2026-10-15).
    rmeta = {r.get("slot"): {k: r[k] for k in ("rhetorical", "implied", "answered_by") if r.get(k)}
             for r in ans.get("referents") or []}
    extends = [g for g in ans.get("groups") or [] if g.get("action") == "extend"]
    out = {"ref": ctx["ref"], "referents": [{"slot": s, "choice": c or "none", "divine": s in div_slots,
                                             **rmeta.get(s, {})}
                                            for s, c in v.refs.items()],
           "links": [{"src": a, "type": t, "dst": b, "action": "add"} for a, t, b in sorted(links)]
                    + [{"src": a, "type": t, "dst": b, "action": "remove"} for a, t, b in sorted(Verse_base_links(ctx) - links)],
           "groups": [{"id": gid, "kind": g["kind"], "action": "change", "divine": gid in div_groups,
                       "members": [{"role": r, "node": n} for r, n in g["members"]]} for gid, g in groups.items()]
                     + [{"id": gid, "kind": g["kind"], "action": "remove", "members": []}
                        for gid, g in ctx["builder_groups"].items() if gid not in groups]
                     + extends,
           "derived": made}
    return out


def Verse_base_links(ctx):
    return set(S.Verse(ctx).links)


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.mkdir(parents=True, exist_ok=True)
    n, counts = 0, {}
    for p in sorted(src.glob("*.json")):
        if p.name.startswith(("held", "_", "score")):
            continue
        cp = CTX / p.name
        if not cp.exists():
            continue
        out = derive(json.loads(cp.read_text(encoding="utf-8")), json.loads(p.read_text(encoding="utf-8")))
        for d in out["derived"]:
            counts[d[0]] = counts.get(d[0], 0) + 1
        (dst / p.name).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        n += 1
    print(f"{n} verses; derived {counts} -> {dst}")


if __name__ == "__main__":
    main()
