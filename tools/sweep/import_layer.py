"""THE SWEEP, IMPORTED AS A LAYER OF READINGS (plan 1.34, step 4;
2026-10-17: import the sweep results).

The sweep's answers are edits to the builder's structure: a referent chosen
for a pronoun or an unstated subject, clause links added or removed, groups
(speech turns, command groups, parallels ...) added, restated, removed or
extended across verses. Model output is a credited reading until a ruling
makes it a builder rule (plan 1.34), so the answers are NOT merged into the
builder's files. They are written as their own layer, the way the Berean's
readings are (out/placeholder-readings.jsonl.gz, S6): every record carries
`reading: "sweep"` and the pass that made it.

    python tools/sweep/import_layer.py   -> out/sweep-layer.jsonl.gz
                                          out/sweep/import-stats.json

What is applied on the way in, each counted:
  - THE DIVINE RULINGS (out/sweep/divine-decisions.json): a rejected flag
    is not imported (Luke 22:8's "for us" and "we", 2026-10-17); an approved
    one is, marked `divine`.
  - THE GRAPH ARBITRATES: an id that names no node in the graph is dropped,
    as is a link type the vocabulary does not have.
  - AN EARLIER VERSE'S NODE IS ACCEPTED, offered as a candidate or not
    (journal 2026-10-17: the first pass answered Genesis 22:2's "I" with
    God from 22:1, an id it had not been offered), when its number agrees
    with the slot's or either is unknown. Where the numbers differ the
    choice is held, not imported, and counted.
  - Where the builder already resolved a slot the same way, nothing is
    written (the agreement is counted). Where it resolved it differently,
    the sweep's choice is written with a record disputing the builder's.

Record shapes (one JSON object per line, each with "ref" and "reading"):
  edge     {"type", "src", "dst", ...}                    refers_to, a clause
           link (clause_link: true), or a group member (group_member: true)
  dispute  {"type", "src", "dst", "action": "remove"}     a builder edge the
           sweep says is wrong; or {"id", "action": "remove"} for a group
  node     {"id", "kind", "text", "node": true}           a group the sweep
           made, a list of referents taken together, or a generic entity
"""
import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
FIRST = OUT / "sweep" / "runs" / "sweep-1"
MERGED = OUT / "sweep" / "runs" / "resolve-1" / "merged"
GENERICS = OUT / "sweep" / "runs" / "resolve-1" / "generics.json"
DEST = OUT / "sweep-layer.jsonl.gz"
GENERIC_LINKS = OUT / "sweep" / "generic-links.jsonl"
# God, LORD, Lord (H430 H433 H410 H3068 H3069 H136 H3050, Aramaic H426; G2316
# G2962), Jesus G2424, Christ G5547, Spirit G4151 H7307, Father G3962, Son G5207
DIVINE_PERSONS = {"H430", "H433", "H410", "H3068", "H3069", "H136", "H3050", "H426", "H7307",
                  "G2316", "G2962", "G2424", "G5547", "G4151", "G3962", "G5207"}
VERSE = re.compile(r"^[1-3]?[A-Z][a-z]{1,2}\.\d+\.\d+\.json$")
# who read it, as the data keeps it (the site rewrites tool names, About names them)
READER = {"first pass": "sweep, first pass (Claude Haiku 5.5)",
          "resolution pass": "sweep, resolution pass (Claude Sonnet 5.5)"}
GROUP_KIND = {"turn": "turn", "imperative": "imperative", "acts": "agent_acts",
              "conditional": "conditional", "parallel": "parallel", "descriptions": "descriptions",
              "writing": "writing", "concession": "concession", "action-state": "action_state"}


def load_graph():
    """Every node id with its number, and the builder's refers_to and group
    member edges by verse."""
    num, kind, person, strong = {}, {}, {}, {}
    with gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            i = d.get("id")
            if not i:
                continue
            if d.get("word") and d.get("strong"):
                s = re.sub(r"\D", "", str(d["strong"])).lstrip("0")
                strong[i] = ("G" if d.get("lang") == "greek" else "H") + s
            num[i] = d.get("number") or d.get("verb_number")
            person[i] = d.get("person") or d.get("verb_person")
            kind[i] = d.get("kind") if d.get("pair") else ("composite" if d.get("composite") else
                                                           "clause" if d.get("clause") else
                                                           "word" if d.get("word") else "other")
    refers, members = {}, collections.defaultdict(set)
    links = set()
    with gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            t = e.get("type")
            if t == "refers_to":
                refers[e["src"]] = e["dst"]
            elif e.get("clause_link"):
                if kind.get(e["src"]) not in (None, "clause", "word", "composite", "other"):
                    members[e["src"]].add((t, e["dst"]))
                else:
                    links.add((e["src"], t, e["dst"]))
    return num, kind, person, refers, members, links, strong


def member_roles():
    """The group member roles the vocabulary lets the readings show: a kind
    built, or deferred with its reason saying the sweep supplies it (1.42's
    wording). A role still proposed or withdrawn is held. Until 2026-10-18 the
    roles were never checked, and `warning`, still proposed, came in 196
    times, half of a sample of 10 wrong (they were held out)."""
    k = json.loads((ROOT / "ontology" / "kinds.json").read_text(encoding="utf-8"))
    ok = set()
    for r in k["relations"]:
        if r["status"] == "built" or (r["status"] == "deferred" and "sweep" in (r.get("deferred") or "")):
            ok.add(r["id"])
            ok.update((r.get("match") or {}).get("type") or [])
    return ok


def link_types():
    k = json.loads((ROOT / "ontology" / "kinds.json").read_text(encoding="utf-8"))
    ok = set()
    for r in k["relations"]:
        if r.get("parent") == "clause_link" or r["id"] in ("conceded", "failed_result"):
            ok.add(r["id"])
            ok.update((r.get("match") or {}).get("type") or [])
    return ok


def main():
    num, kind, person, refers, members, blinks, strong = load_graph()
    # a builder link by its type and target, to find the one a removal meant
    # when the model named its source by a local id from another verse
    by_td = collections.defaultdict(list)
    for s_, t_, d_ in blinks:
        by_td[(t_, d_)].append(s_)
    added_groups, pending = set(), []
    generics = {g["id"]: g for g in json.loads(GENERICS.read_text(encoding="utf-8"))}
    ltypes = link_types()
    mroles = member_roles()
    # WARNINGS ONLY WHERE TWO JUDGES AGREE (2026-10-18: included;
    # tools/sweep/warning_check.py): the sweep's 196, of which 86
    # kept. Any other warning the sweep proposed stays held
    wpath = OUT / "sweep" / "warning-check.jsonl"
    if not wpath.exists():
        raise SystemExit(f"{wpath.relative_to(ROOT)} missing -- python tools/sweep/warning_check.py merge")
    warn_ok = {(w["group"], w["clause"]) for w in map(json.loads, wpath.read_text(encoding="utf-8").splitlines())
               if w.get("keep")}
    decisions = {}
    for d in json.loads((OUT / "sweep" / "divine-decisions.json").read_text(encoding="utf-8")):
        decisions[(d["ref"], d.get("slot") or d["kind"])] = d["decision"]
    st = collections.Counter()
    held = collections.defaultdict(list)
    out = []

    def full(ref, x):
        return x if "#" in str(x) else f"{ref}#{x}"

    def exists(x):
        return x in num or x in generics

    # POINTER CORRECTIONS BY HAND (2026-10-19, ontology/provenance/sweep/
    # pointer-corrections-*.json): pointers the panel of eleven objected to,
    # all three decisions of docs/review/divine-ends-2026-10-19.html "as
    # recommended". A wrong link is never written (the structure view applies
    # a removal only to the builder's own links, so a sweep link must not be
    # written at all), a builder link is disputed, and a corrected link is
    # written where two judges agreed and the words were found
    corrections = []
    for p_ in sorted((ROOT / "ontology" / "provenance" / "sweep").glob("pointer-corrections-*.json")):
        corrections += json.loads(p_.read_text(encoding="utf-8"))["corrections"]
    wrong = {(c["src"], c["wrong"]) for c in corrections}

    with gzip.open(DEST, "wt", encoding="utf-8") as fh:
        def put(rec):
            if rec.get("type") == "refers_to" and not rec.get("action") and (rec.get("src"), rec.get("dst")) in wrong:
                st["referent: a pointer Doug's ruling corrects (not written)"] += 1
                return
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

        for g in generics.values():
            put({"ref": g["first"], "id": g["id"], "node": True, "kind": "generic", "text": g["label"],
                 "reading": "sweep", "by": READER["resolution pass"]})
            st["node:generic"] += 1
        # THE GENERICS CHECKED AGAINST THE TEXT'S OWN WORDS (plan 1.41;
        # out/sweep/generic-links.jsonl, tools/sweep/generic_check.py; the hand-checked
        # sample, 30 of 32 right, 2026-10-18). "Same": the generic is the group
        # the text names there, so it refers to that word ("the twelve",
        # Matthew 20:17, for 20:18's "we"). "Part of" is one of, or some of,
        # that group: `partitive` ("a priest" of "the priests", Lev 21:1).
        # A word for God, the LORD, Jesus, Christ, the Spirit, the Father or the
        # Son is never linked by this: those identities are set by hand.
        if not GENERIC_LINKS.exists():
            raise SystemExit(f"{GENERIC_LINKS.relative_to(ROOT)} missing -- python tools/sweep/generic_check.py merge")
        # Releases of held links by hand, one by one (never by rule)
        released = set()
        for p_ in sorted((ROOT / "ontology" / "provenance" / "sweep").glob("generic-releases-*.json")):
            for x in json.loads(p_.read_text(encoding="utf-8"))["released"]:
                released.add((x["generic"], x["word"]))
        if True:
            for r in (json.loads(x) for x in GENERIC_LINKS.read_text(encoding="utf-8").splitlines() if x.strip()):
                # "part of" is `partitive`: one of, or some of, the group the
                # text names (2026-10-18: partitive chosen; the same
                # term as the prepositional type)
                link = {"same": "refers_to", "part_of": "partitive"}.get(r.get("decision"))
                if not link:
                    st[f"generic check: {r.get('decision')} (not written)"] += 1
                    continue
                c_ = r.get("candidate")
                if r.get("generic") not in generics or c_ not in num:
                    st["generic check: unknown id (dropped)"] += 1
                    continue
                if strong.get(c_) in DIVINE_PERSONS and (r["generic"], c_) not in released:
                    st["generic check: a divine person's word (held for Doug)"] += 1
                    held["generic check: a divine person's word"].append((r["generic"], c_))
                    continue
                put({"ref": generics[r["generic"]]["first"], "reading": "sweep", "by": r.get("by"),
                     "confidence": r.get("confidence"), "type": link, "src": r["generic"], "dst": c_,
                     "generic_check": True})
                st[f"generic check: {r['decision']}, written"] += 1
                if (r["generic"], c_) in released:
                    st["generic check: a divine person's word, released by Doug"] += 1
        for p in sorted(FIRST.glob("*.json")):
            if not VERSE.match(p.name):
                continue
            ref = p.stem
            src = MERGED / p.name if (MERGED / p.name).exists() else p
            a = json.loads(src.read_text(encoding="utf-8"))
            st["verses"] += 1
            # REFERENTS
            for r in a.get("referents") or []:
                slot, ch = r.get("slot"), r.get("choice")
                by = r.get("resolved_by") or "first pass"
                base = {"ref": ref, "reading": "sweep", "by": READER.get(by, by),
                        "confidence": r.get("confidence")}
                for k_ in ("rhetorical", "implied", "answered_by"):
                    if r.get(k_):
                        base[k_] = r[k_]
                if ch in (None, "", "none"):
                    st["referent:none"] += 1
                    continue
                if ch == "cant_tell":
                    st["referent:can't tell"] += 1
                    continue
                if decisions.get((ref, slot)) == "rejected":
                    st["referent:rejected by Doug"] += 1
                    continue
                if r.get("divine"):
                    base["divine"] = True
                s = full(ref, slot)
                if s not in num:
                    st["referent:slot not in graph"] += 1
                    held["slot not in graph"].append((ref, slot))
                    continue
                if isinstance(ch, list):
                    ids = [full(ref, x) for x in ch if isinstance(x, str)]
                    if not ids or not all(exists(x) for x in ids):
                        st["referent:list with an unknown id"] += 1
                        held["list with an unknown id"].append((ref, slot, ch))
                        continue
                    cid = f"{s}~together"
                    put({**base, "id": cid, "node": True, "kind": "together",
                         "text": " and ".join(x.split("#")[-1] for x in ids)})
                    for x in ids:
                        put({**base, "type": "member", "src": cid, "dst": x})
                    dst = cid
                    st["referent:together"] += 1
                else:
                    dst = full(ref, ch) if isinstance(ch, str) else None
                    if not dst or not exists(dst):
                        st["referent:unknown id"] += 1
                        held["unknown id"].append((ref, slot, ch))
                        continue
                    # AN EARLIER VERSE'S NODE, offered or not. Number disagreement
                    # alone is no reason to refuse it: a plural "they" for "the
                    # Gadites", "the assembly", "the church" is a collective, and
                    # right. What it does catch is a "we" or "us" narrowed to the
                    # speaker alone ("let us bring back the ark" -> David), the
                    # Luke 22:8 fault marked wrong by hand: held.
                    if dst.split("#")[0] != ref and dst in num:
                        a_, b_ = num.get(s), num.get(dst)
                        if a_ and b_ and a_ != b_:
                            if (person.get(s) or "").startswith("first") and a_ == "plural" and b_ == "singular":
                                st["referent:earlier verse, 'we' narrowed to one (held)"] += 1
                                held["'we' narrowed to one"].append((ref, slot, dst))
                                continue
                            st["referent:earlier verse, number differs (a collective, accepted)"] += 1
                        st["referent:earlier verse"] += 1
                    if dst in generics:
                        st["referent:generic"] += 1
                if refers.get(s) == dst:
                    st["referent:agrees with builder"] += 1
                    continue
                if s in refers:
                    put({"ref": ref, "reading": "sweep", "by": base["by"], "type": "refers_to",
                         "src": s, "dst": refers[s], "action": "remove"})
                    st["referent:replaces builder"] += 1
                else:
                    st["referent:fills a blank"] += 1
                put({**base, "type": "refers_to", "src": s, "dst": dst})
            # LINKS
            for l in a.get("links") or []:
                act, t = l.get("action"), l.get("type")
                if act == "keep":
                    st["link:kept"] += 1
                    continue
                if act not in ("add", "remove"):
                    st[f"link:action {act} (dropped)"] += 1
                    continue
                if t not in ltypes:
                    st[f"link:type not in the vocabulary (dropped)"] += 1
                    held["link type not in the vocabulary"].append((ref, t))
                    continue
                s_, d_ = full(ref, l.get("src")), full(ref, l.get("dst"))
                if act == "remove" and (s_, t, d_) not in blinks:
                    # NOT RECOVERED, ON PURPOSE. A removal naming a link the
                    # builder does not have is mostly the sweep's context at
                    # fault: it showed a link from the previous verse's cl0 to
                    # this verse's cl0 as "cl0 -> cl0", and the judge removed it
                    # as a "self-link", or judged another clause of the same
                    # local name. Matching such a removal to the cross-verse link
                    # (tried 2026-10-17: 14,433 "recovered") would act on a
                    # judgement made about a different link. Only ~8% of a
                    # 3,000-verse sample showed the judge saw the link cross
                    # verses. Unresolved is better than wrong.
                    kind_ = ("written backwards" if (d_, t, s_) in blinks else
                             "across verses, seen as local" if any(
                                 x.split("#")[-1] == s_.split("#")[-1] for x in by_td.get((t, d_), ()))
                             else "naming no builder link")
                    st[f"link:remove not imported ({kind_})"] += 1
                    continue
                unknown = [x for x in (s_, d_) if x not in num]
                if unknown:
                    # a link to a group the sweep itself made: written once
                    # that group is known, at the end
                    if act == "add" and all(re.search(r"#g\d+$", x) for x in unknown):
                        pending.append(({"ref": ref, "reading": "sweep", "by": READER["first pass"], "type": t,
                                         "src": s_, "dst": d_, "clause_link": True,
                                         "confidence": l.get("confidence")}, unknown))
                        continue
                    st["link:unknown id (dropped)"] += 1
                    continue
                if act == "remove":
                    put({"ref": ref, "reading": "sweep", "by": READER["first pass"], "type": t,
                         "src": s_, "dst": d_, "action": "remove", "clause_link": True})
                    st["link:removed"] += 1
                else:
                    if (s_, t, d_) in blinks:
                        st["link:add of a link the builder has"] += 1
                        continue
                    put({"ref": ref, "reading": "sweep", "by": READER["first pass"], "type": t,
                         "src": s_, "dst": d_, "clause_link": True, "confidence": l.get("confidence")})
                    st["link:added"] += 1
            # GROUPS
            for g in a.get("groups") or []:
                act, gk = g.get("action"), GROUP_KIND.get(g.get("kind"))
                gid = g.get("id")
                if act == "keep":
                    st["group:kept"] += 1
                    continue
                if not gk or not isinstance(gid, str) or act not in ("add", "change", "remove", "extend"):
                    st["group:malformed (dropped)"] += 1
                    continue
                gid = full(ref, gid)
                by = READER["first pass"]
                if act == "remove":
                    if kind.get(gid) is None:
                        st["group:remove of a group the builder does not have"] += 1
                        continue
                    put({"ref": ref, "reading": "sweep", "by": by, "id": gid, "action": "remove"})
                    st["group:removed"] += 1
                    continue
                if act == "extend":
                    if gid.split("#")[0] == ref:
                        st["group:extend of its own verse (dropped)"] += 1
                        continue
                    st["group:extended"] += 1
                elif act == "add":
                    put({"ref": ref, "reading": "sweep", "by": by, "id": gid, "node": True, "kind": gk,
                         "pair": True, "confidence": g.get("confidence")})
                    added_groups.add(gid)
                    st["group:added"] += 1
                else:
                    if kind.get(gid) is None:
                        added_groups.add(gid)
                        # restating a group the builder never made: it is new
                        put({"ref": ref, "reading": "sweep", "by": by, "id": gid, "node": True, "kind": gk,
                             "pair": True, "confidence": g.get("confidence")})
                        st["group:changed, new to the builder"] += 1
                    else:
                        st["group:changed"] += 1
                new = set()
                for m in g.get("members") or []:
                    role, node = m.get("role"), m.get("node")
                    if role not in mroles:
                        st[f"member:role '{role}' not shown by the vocabulary (held)"] += 1
                        held["member role not shown by the vocabulary"].append((ref, gid, role))
                        continue
                    if role in ("sender", "addressee") and decisions.get((ref, role)) == "rejected":
                        st["member:rejected by Doug"] += 1
                        continue
                    if isinstance(node, list):
                        ids = [full(ref, x) for x in node if isinstance(x, str)]
                        if not ids or not all(exists(x) for x in ids):
                            st["member:list with an unknown id (dropped)"] += 1
                            continue
                        cid = f"{gid}~{role}"
                        put({"ref": ref, "reading": "sweep", "by": by, "id": cid, "node": True,
                             "kind": "together", "text": " and ".join(x.split("#")[-1] for x in ids)})
                        for x in ids:
                            put({"ref": ref, "reading": "sweep", "by": by, "type": "member", "src": cid, "dst": x})
                        node = cid
                    elif isinstance(node, str):
                        node = full(ref, node)
                        if not exists(node) and not node.startswith(ref + "#g"):
                            st["member:unknown id (dropped)"] += 1
                            continue
                    else:
                        st["member:no node (dropped)"] += 1
                        continue
                    if role == "warning" and (gid, node) not in warn_ok:
                        st["member:warning the two judges did not both keep (held)"] += 1
                        held["warning not kept by the warning check"].append((ref, gid, node))
                        continue
                    new.add((role, node))
                    by_m = READER.get(m.get("resolved_by"), by)
                    put({"ref": ref, "reading": "sweep", "by": by_m, "type": role, "src": gid, "dst": node,
                         "clause_link": True, "group_member": True,
                         **({"divine": True} if g.get("divine") and role in ("sender", "addressee") else {})})
                    st["member:written"] += 1
                if act == "change":
                    for role, node in members.get(gid, ()):
                        if (role, node) not in new:
                            put({"ref": ref, "reading": "sweep", "by": by, "type": role, "src": gid, "dst": node,
                                 "action": "remove", "clause_link": True, "group_member": True})
                            st["member:builder's disputed"] += 1
        for rec, unknown in pending:
            if all(x in added_groups for x in unknown):
                put(rec)
                st["link:added, to a group the sweep made"] += 1
            else:
                st["link:to a group the sweep did not make (dropped)"] += 1
        for c in corrections:
            if refers.get(c["src"]) == c["wrong"]:
                put({"ref": c["ref"], "reading": "sweep", "by": "Doug's ruling, 2026-10-19", "type": "refers_to",
                     "src": c["src"], "dst": c["wrong"], "action": "remove"})
                st["correction: the builder's pointer disputed"] += 1
            if c.get("dst") and exists(c["dst"]):
                put({"ref": c["ref"], "reading": "sweep", "type": "refers_to", "src": c["src"], "dst": c["dst"],
                     "by": "the panel of eleven, two passes, then two judges; Doug's ruling, 2026-10-19",
                     "correction": True})
                st["correction: the corrected pointer written"] += 1
    stats = {"_what": "tools/sweep/import_layer.py: what the import wrote, kept and held",
             "counts": dict(sorted(st.items())),
             "held_examples": {k: v[:25] for k, v in held.items()},
             "held_counts": {k: len(v) for k, v in held.items()}}
    (OUT / "sweep" / "import-stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in sorted(st.items()):
        print(f"{v:9,}  {k}")


if __name__ == "__main__":
    main()
