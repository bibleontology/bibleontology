"""SCORE A SWEEP RUN AGAINST THE GOLD (plan 1.34).

The gold is tests/verses.json: hand rulings, verse by verse, in the old
builder's node names. This file is the only part of the sweep that reads it.

WHAT IS SCORED IS THE SWEEP'S JOB, not MACULA's. In scope: clause links,
groups and their members, referents (pronouns and implied subjects,
possessors, the people a "they" stands for), turn senders and speakers, and
the `absent` rows that pin wrong links and wrong referents. Out of scope,
because the deterministic builder owns them: clause text, verb nodes,
prepositions, content keys, roles inside a clause, and the psalm's voice
chain (voice, resolves_to), which no link or group kind yet covers.

REFERENTS ARE COMPARED BY WHO, not by node id. A gold name ("aaron") and a
model's choice ("Exo.8.12#w7") both reduce to a key: a word's Hebrew or Greek
lemma; a composite's set of member keys; "voice" for a psalm's voice. So a
pronoun resolved to Moses matches whichever verse's "Moses" node was chosen.

GROUPS ARE COMPARED BY KIND AND MEMBERS. A gold group's id (imp3, turn1)
only names the group within the verse; the final group of the same kind that
satisfies most of its rows is taken as its match.

    python tools/sweep/score.py baseline              the builder alone
    python tools/sweep/score.py <run dir>             out/sweep/runs/<run>/<ref>.json
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CTX = ROOT / "out" / "sweep" / "context"
GOLD = ROOT / "tests" / "verses.json"
GROUP_PREFIX = {"imp": "imperative", "turn": "turn", "conc": "concession", "acts": "acts",
                "cnd": "conditional", "pair": "action-state", "par": "parallel", "desc": "descriptions"}
OUT_OF_SCOPE_EDGES = {"voice", "resolves_to", "like"}


def norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower().replace("’s", "").replace("'s", ""))


def suffix(x):
    return x.split("#", 1)[1] if "#" in (x or "") else x


def group_kind_of(name):
    if name == "writing":
        return "writing"
    m = re.match(r"^([a-z]+?)\d", name or "")
    return GROUP_PREFIX.get(m.group(1)) if m else None


class Verse:
    """The final state of one verse: the builder's, with a run's choices applied."""

    def __init__(self, ctx, run=None):
        self.ctx = ctx
        self.cands = {c["id"]: c for c in ctx["candidates"]}
        # a judge may name an earlier verse's candidate by its local id
        # ("psalmist" for Psa.23.1#psalmist); found 2026-10-15, when seven right
        # answers were counted invalid. Only where the local id is unambiguous.
        locals_ = collections.Counter(suffix(i) for i in self.cands)
        for i, c in list(self.cands.items()):
            if "#" in i and locals_[suffix(i)] == 1 and suffix(i) not in self.cands:
                self.cands[suffix(i)] = c
        self.slots = {s["id"]: s for s in ctx["slots"]}
        self.links = set()
        for row in ctx["builder_links"]:
            a, rest = row.split(" -", 1)
            t, b = rest.split("-> ", 1)
            self.links.add((a, t, suffix(b)))
        self.groups = {}
        for gid, g in ctx["builder_groups"].items():
            self.groups[gid] = {"kind": g["kind"], "members": [tuple(m.split("=", 1)) for m in g["members"]]}
        self.refs = {sid: s.get("builder_says") for sid, s in self.slots.items()}
        self.rejected, self.invalid, self.divine = [], [], []
        if run:
            self.apply(run)

    def key(self, cid):
        """Who a candidate is: lemma, a composite's member set, or 'voice'."""
        if cid is None:
            return None
        c = self.cands.get(cid) or self.cands.get(suffix(cid))
        if not c:
            # the builder may point at a word that is no candidate ("rivers"):
            # known by its text, so an `absent` row can still catch it
            said = next((s.get("builder_says_text") for s in self.slots.values()
                         if s.get("builder_says") == cid), None)
            return ("text", norm(said)) if said else ("unknown", cid)
        if c.get("voice"):
            return "voice"
        if c.get("members"):
            return frozenset(c["members"])
        return c.get("lemma") or norm(c.get("text"))

    def apply(self, run):
        for r in run.get("referents") or []:
            sid, ch = r.get("slot"), r.get("choice")
            if sid not in self.slots:
                self.invalid.append(("slot", sid))
                continue
            if ch in ("none", "cant_tell", None):
                self.refs[sid] = None
                continue
            c = self.cands.get(ch) or self.cands.get(suffix(ch))
            if not c:
                self.invalid.append(("candidate", ch))
                self.refs[sid] = None
                continue
            # THE ORIGINAL ARBITRATES: a plural slot is never ONE PERSON (a
            # proper name), a singular slot never a composite.
            # WRONG TURN, KEPT (2026-10-15): the first rule rejected any plural
            # slot resolved to a singular noun, and threw out three right
            # answers. "They" -> "people" (עַם) is a collective, which Hebrew
            # takes with a plural verb; the judge said so in its reasons.
            num = self.slots[sid].get("morph", "")
            one_person = bool(c.get("proper"))
            if ("plural" in num and one_person and not c.get("members")) or ("singular" in num and c.get("members")):
                self.rejected.append((sid, ch, num, c.get("morph")))
                self.refs[sid] = None
                continue
            if r.get("divine"):
                self.divine.append((sid, ch))
            self.refs[sid] = c["id"]
        # A LINK'S SOURCE IN THIS VERSE, BY ITS LOCAL NAME. The target was
        # suffixed and the source was not, so "Exo.8.13#cl1 -fulfils->" never
        # met the gold's "cl1 -fulfils->", and a removal written that way left
        # the builder's link standing. The bench's judges wrote bare "cl1"; the
        # first headless run's 12-verse passages prefixed every id, and scored
        # 70.0% against the bench's 79-86% on the same 14 verses (2026-10-16)
        # until this was fixed.
        own = f"{self.ctx.get('ref')}#"
        for l in run.get("links") or []:
            src = l.get("src") or ""
            src = src[len(own):] if src.startswith(own) else src
            t = (src, l.get("type"), suffix(l.get("dst")))
            if l.get("action") == "remove":
                self.links.discard(t)
            elif l.get("action") == "add":
                self.links.add(t)
        for g in run.get("groups") or []:
            # a judge in a passage names its groups with the verse in front
            # ("Exo.7.26#g1"); members name them without. One name each.
            gid, act = suffix(g.get("id")), g.get("action")
            # but never a candidate's: "Exo.8.12#w4" (Moses, a verse back) is
            # not this verse's w4
            mem = [(m.get("role"), m.get("node") if m.get("node") in self.cands else suffix(m.get("node")))
                   for m in g.get("members") or []]
            if act == "remove":
                self.groups.pop(gid, None)
            elif act == "extend":
                # R7: this verse's clauses added to a turn an earlier verse
                # began; within this verse the turn is present, with them
                g0 = self.groups.setdefault(gid, {"kind": g.get("kind"), "members": []})
                g0["members"] += [m for m in mem if m not in g0["members"]]
            elif act in ("change", "add") or (act == "keep" and gid not in self.groups):
                self.groups[gid] = {"kind": g.get("kind"), "members": mem}
            if g.get("divine") and act != "remove":
                self.divine.append((gid, g.get("kind")))

    # ---- queries -----------------------------------------------------
    def node_is(self, node, gold_name):
        """Does a final member node stand for the gold node name?"""
        gk = group_kind_of(gold_name)
        if gk:
            n = suffix(node)
            return (n in self.groups and self.groups[n]["kind"] == gk) or group_kind_of(n) == gk
        return suffix(node) == gold_name

    def has_link(self, a, t, b):
        gk = group_kind_of(b)
        for (s, tt, d) in self.links:
            if s == a and tt == t and (d == b or (gk and self.node_is(d, b))):
                return True
        return False


def gold_key(v, name, composites):
    if name in composites:
        return frozenset(gold_key(v, m, composites) for m in composites[name])
    if name in ("psalmist",):
        return "voice"
    n = norm(name[:-1] if name.endswith("S") else name)
    pool = sorted(v.cands.values(), key=lambda c: c.get("where") != "this verse")
    for c in pool:
        if norm(c.get("text")) == n and not c.get("members"):
            return c.get("lemma") or norm(c.get("text"))
    return ("unmapped", name)


def gold_slots(v, name):
    m = re.match(r"^(he|she|it|they|you|we|i)(\d+)$", name)
    if m:
        return [f"cl{m.group(2)}s"] if f"cl{m.group(2)}s" in v.slots else []
    n = norm(name)
    return [s for s, d in v.slots.items() if norm(d.get("text")) == n]


_OLD = None


def old_clause_map(ref, v):
    """{old clause number: new clause number}, by the clause's text.

    THE GOLD NUMBERS CLAUSES AS THE OLD BUILDER DID (2026-10-15). In three
    gold verses the clean builder splits off a clause the old one did not
    ("here!" in Exo 7:27, "there!" in 8:16, "your rod and your staff" in
    Psa 23:4), so the gold's cl4 is the new cl5, and scoring by number
    compared the ruling with the wrong clause in every run alike."""
    global _OLD
    if _OLD is None:
        p = ROOT / "out" / "sweep" / "old-clauses.json"
        if p.exists():
            _OLD = json.loads(p.read_text(encoding="utf-8"))
        else:
            import gzip
            gold = json.loads(GOLD.read_text(encoding="utf-8"))
            refs = {r for r in gold if not r.startswith("_")}
            _OLD = {}
            for line in gzip.open(ROOT / "out" / "placeholder-nodes.old.jsonl.gz", "rt", encoding="utf-8"):
                n = json.loads(line)
                if n.get("ref") in refs and n.get("clause"):
                    _OLD.setdefault(n["ref"], {})[str(n.get("order"))] = n.get("text") or ""
            p.write_text(json.dumps(_OLD, ensure_ascii=False), encoding="utf-8")

    def key(t):
        return re.sub(r"[^a-z]", "", (t or "").lower())[:40]
    # ALIGNED IN ORDER, not looked up by text: two clauses can read the same
    # ("he said ... he said", Exo 8:6), and a lookup by text mapped both to one
    new = [(int(c["id"][2:]), key(c["gloss"])) for c in v.ctx["clauses"]]
    out, j = {}, 0
    for o, t in sorted(((int(o), t) for o, t in (_OLD.get(ref) or {}).items())):
        k = j
        while k < len(new) and new[k][1] != key(t):
            k += 1
        if k < len(new):
            out[o] = new[k][0]
            j = k + 1
    return out


def renumber(name, cmap):
    """A gold node name with its clause number moved to the new numbering:
    cl4 -> cl5, ct4 -> ct5, he4 -> he5 (an implied subject is its clause's)."""
    m = re.match(r"^(cl|ct|he|she|it|they|you|we|i)(\d+)$", name)
    if m and int(m.group(2)) in cmap:
        return f"{m.group(1)}{cmap[int(m.group(2))]}"
    return name


def score(ref, want, v):
    """[(row, in_scope, ok)] for one verse."""
    cmap = old_clause_map(ref, v)
    if any(a != b for a, b in cmap.items()):
        def fix(row):
            if " -" in row and "-> " in row:
                a, rest = row.split(" -", 1)
                t, b = rest.split("-> ", 1)
                return f"{renumber(a.strip(), cmap)} -{t}-> {renumber(b.strip(), cmap)}"
            return re.sub(r"\b(cl|ct)(\d+)\b", lambda m: renumber(m.group(0), cmap), row)
        want = {k: ([fix(r) for r in x] if isinstance(x, list) else x) for k, x in want.items()}
    out = []
    composites = collections.defaultdict(list)
    for row in want.get("edges") or []:
        a, rest = row.split(" -", 1)
        t, b = rest.split("-> ", 1)
        if t.strip() == "member":
            composites[a.strip()].append(b.strip())

    def resolved_text(s):
        x = v.refs.get(s)
        c = v.cands.get(x) or v.cands.get(suffix(x or ""))
        return norm(c.get("text")) if c else norm(v.slots[s].get("builder_says_text")) if x else None

    def referent_ok(slot_name, target):
        sl = gold_slots(v, slot_name)
        if not sl:
            return None
        k = gold_key(v, target, composites)
        if isinstance(k, tuple):
            # not a candidate: only checkable by its text (an `absent` row
            # catching the builder's pick of a word no candidate list offers)
            n = norm(target[:-1] if target.endswith("S") else target)
            return all(resolved_text(s) == n for s in sl)
        return all(v.key(v.refs.get(s)) == k for s in sl)

    turns = {gid: g for gid, g in v.groups.items() if g["kind"] == "turn"}
    parent = {}
    for gid, g in turns.items():
        for r, n in g["members"]:
            if r == "part" and suffix(n) in turns:
                parent[suffix(n)] = gid

    def depth(gid):
        d, seen = 0, set()
        while gid in parent and gid not in seen:
            seen.add(gid)
            gid, d = parent[gid], d + 1
        return d

    def turn_sender_of_clause(cl):
        """The speaker of a clause: the sender of the turn it is a part of;
        and for the frame of a NESTED turn ("you shall say to him", inside
        another's speech), that turn's own sender (spoken by the one
        commanded). An outermost turn's frame is the narrator's: no speaker."""
        return {v.key(n) for gid, g in turns.items()
                if any((r == "part" or (r == "frame" and gid in parent)) and suffix(x) == cl
                       for r, x in g["members"])
                for r, n in g["members"] if r == "sender"}

    def gold_turn(name):
        """The gold's turn0 / turn1 / turn2 name the outer, the nested and the
        innermost speech of a verse: matched by nesting depth, so a sender
        row about turn1 is not satisfied (or violated) by turn2's sender."""
        m = re.match(r"^turn(\d+)$", name)
        if not m or not turns:
            return None
        want = int(m.group(1))
        return [g for gid, g in turns.items() if depth(gid) == want] or None

    def row_ok(kind, a, t, b):
        if kind == "edges" or kind == "absent_edge":
            if t in OUT_OF_SCOPE_EDGES:
                return None
            if t == "refers_to":
                return referent_ok(a, b)
            if t == "possessor":
                ga = norm(a[:-1] if a.endswith("S") else a)
                sl = [s for s, d in v.slots.items() if norm(d.get("in_text")) == ga]
                k = gold_key(v, b, composites)
                if not sl or isinstance(k, tuple):
                    return None
                return all(v.key(v.refs.get(s)) == k for s in sl)
            if t == "member":
                # A COMPOSITE IS THE SWEEP'S ONLY WHEN SOMETHING REFERS TO IT
                # ("they" -> Moses and Aaron). A coordination the text spells
                # out ("goodness and mercy", Psa 23:6) is the builder's, and its
                # member rows are not scored (found 2026-10-15: all three runs
                # "missed" them, because no slot points there)
                if not any(r.split(" -", 1)[1].startswith("refers_to-> " + a)
                           for r in (want.get("edges") or []) if " -" in r):
                    return None
                k = gold_key(v, b, composites)
                return any(isinstance(v.key(x), frozenset) and k in v.key(x) for x in v.refs.values() if x)
            if t == "speaker":
                k = gold_key(v, b, composites)
                return None if isinstance(k, tuple) else k in turn_sender_of_clause(a)
            if t == "sender":
                k = gold_key(v, b, composites)
                gk = group_kind_of(a)
                if isinstance(k, tuple) or not gk:
                    return None
                pool = gold_turn(a) if gk == "turn" else None
                pool = pool if pool is not None else [g for g in v.groups.values() if g["kind"] == gk]
                return any(any(r == "sender" and v.key(n) == k for r, n in g["members"]) for g in pool)
            return None
        # links
        if a.startswith("ct"):
            return None                            # a role inside a clause: the builder's
        gk = group_kind_of(a)
        if gk:
            return any(g["kind"] == gk and any(r == t and v.node_is(n, b) for r, n in g["members"])
                       for g in v.groups.values())
        if not a.startswith("cl"):
            return None
        return v.has_link(a, t, b)

    for kind in ("links", "edges", "absent"):
        for row in want.get(kind) or []:
            a, rest = row.split(" -", 1)
            t, b = rest.split("-> ", 1)
            a, t, b = a.strip(), t.strip(), b.strip()
            if kind == "absent":
                k2 = "absent_edge" if t in ("refers_to", "possessor", "speaker", "sender", "member") else "links"
                ok = row_ok(k2, a, t, b)
                if ok is not None and t == "refers_to":
                    # absent referent: true when the slot is NOT resolved to it
                    ok = not ok
                elif ok is not None:
                    ok = not ok
            else:
                ok = row_ok(kind, a, t, b)
            out.append((f"{kind}: {row}", ok is not None, bool(ok)))
    for row in want.get("groups") or []:
        bits = [x.strip() for x in row.split("|")]
        kind, members = bits[0], [m.split("=", 1)[1] for m in bits[2:]]
        ok = any(g["kind"] == kind and all(any(v.node_is(n, m) for _, n in g["members"]) for m in members)
                 for g in v.groups.values())
        out.append((f"groups: {row}", True, ok))
    for row in want.get("pairs") or []:
        bits = [x.strip() for x in row.split("|")]
        kind, mem = bits[0], [tuple(m.split("=", 1)) for m in bits[2:]]
        ok = any(g["kind"] == kind and all(any(r == role and suffix(n) == x for r, n in g["members"]) for role, x in mem)
                 for g in v.groups.values())
        out.append((f"pairs: {row}", True, ok))
    for row in want.get("speakers") or []:
        cl, who = [x.strip() for x in row.split("|")]
        got = turn_sender_of_clause(cl)
        if who == "-":
            ok = not got
        else:
            k = gold_key(v, who, composites)
            ok = None if isinstance(k, tuple) else k in got
        out.append((f"speakers: {row}", ok is not None, bool(ok)))
    for kind in want.get("absent_pairs") or []:
        ok = not any(g["kind"] == kind for g in v.groups.values())
        out.append((f"absent_pairs: {kind}", True, ok))
    return out


def run_dir(arg):
    return None if arg == "baseline" else Path(arg)


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    rd = run_dir(arg)
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    tot_in = tot_ok = 0
    per = {}
    notes = collections.Counter()
    for ref, want in gold.items():
        if ref.startswith("_"):
            continue
        p = CTX / f"{ref}.json"
        if not p.exists():
            continue
        ctx = json.loads(p.read_text(encoding="utf-8"))
        run = None
        if rd:
            rp = rd / f"{ref}.json"
            if not rp.exists():
                continue
            run = json.loads(rp.read_text(encoding="utf-8"))
        v = Verse(ctx, run)
        rows = score(ref, want, v)
        n_in = sum(1 for _, s, _ in rows if s)
        n_ok = sum(1 for _, s, ok in rows if s and ok)
        tot_in += n_in
        tot_ok += n_ok
        per[ref] = {"in_scope": n_in, "ok": n_ok, "out_of_scope": sum(1 for _, s, _ in rows if not s),
                    "missed": [r for r, s, ok in rows if s and not ok],
                    "rejected_by_morphology": v.rejected, "invalid": v.invalid, "divine": v.divine}
        notes["rejected"] += len(v.rejected)
        notes["invalid"] += len(v.invalid)
        notes["divine"] += len(v.divine)
    for ref, r in per.items():
        print(f"{ref:12s} {r['ok']:3d}/{r['in_scope']:3d}" + (f"   rejected {len(r['rejected_by_morphology'])}" if r['rejected_by_morphology'] else ""))
    pct = 100 * tot_ok / tot_in if tot_in else 0
    print(f"TOTAL {tot_ok}/{tot_in} = {pct:.1f}%  ({dict(notes)})")
    dest = (rd.resolve() if rd else ROOT / "out" / "sweep") / f"score-{'baseline' if not rd else 'run'}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"total": [tot_ok, tot_in], "per": per}, ensure_ascii=False, indent=1, default=list),
                    encoding="utf-8")
    print("->", dest)


if __name__ == "__main__":
    main()
