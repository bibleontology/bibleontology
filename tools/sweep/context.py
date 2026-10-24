"""THE SWEEP'S INPUT: one verse, as candidates (plan 1.34).

2026-10-15: put Haiku 5.5 to work on a low-level structure sweep of every
sentence, aligning with the work done on the gnat plague: filling in pronouns,
linking with transition words, and so on.

The model never invents a referent or a link. This file gives it the verse as
the clean builder read it, and the closed lists to choose from:

  clauses      each with its original text, gloss, mood, person/gender/number
               and the connective that opens it
  slots        every pronoun and implicit subject, with its morphology and
               the builder's current referent (to confirm, correct or leave)
  candidates   who a slot may refer to: the nouns of this verse, the people
               and groups of the verses before it in the chapter, the
               speakers and addressees of the enclosing turns, and the
               writing's own voice
  links        the builder's clause-to-clause links and groups, to keep or
               remove
  vocabulary   the declared link and group kinds, with their definitions

No ruling comes from tests/verses.json: the calibration is blind, and the
gold is read only by tools/sweep/score.py. This file reads the gold's LIST
OF VERSES only, to take out of the definitions shown to a judge any sentence
that cites one of them (`blind`).

    python tools/sweep/context.py Exo.8.12 [more refs]   -> out/sweep/context/<ref>.json
"""
from __future__ import annotations

import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
WINDOW = 5                     # verses of the same chapter shown before this one

# The definitions accepted on the structure sheet (accepted 2026-10-15
# with no change), for the relations kinds.json does not yet define;
# they move into kinds.json with release 1.2.0
SHEET_DEFS = json.loads((Path(__file__).with_name("sheet_definitions.json"))
                        .read_text(encoding="utf-8"))

GROUP_KINDS = {
    "writing": ("A book, psalm or letter as a unit, from its writer to its readers: its heading "
                "(frame), what it says (part), the writer where the text names one (sender).",
                ["frame", "part", "sender", "addressee"]),
    "turn": ("Someone communicating: the saying clause (frame), what is said (part), "
             "who (sender), to whom (addressee). Turns nest: a command to say "
             "something holds the inner turn as a part.", ["frame", "part", "sender", "addressee"]),
    "imperative": ("A command as a unit: its command(s), and what qualifies it.",
                   ["command", "aim", "basis", "effect", "warning"]),
    "conditional": ("An 'if' clause and the clause it conditions.", ["condition", "consequence"]),
    "action-state": ("A command, then the same act reported as having happened.", ["action", "state"]),
    "parallel": ("Two lines where the second restates the first's roles without the subject, "
                 "because the subject is the same.", ["line", "group_subject"]),
    "acts": ("Clauses in a row that are the acts of one agent, each stating its subject only "
             "in its verb, all the same referent.", ["agent_act", "group_subject"]),
    "concession": ("'Even though': the obstacle, the claim that holds anyway, and its ground.",
                   ["conceded", "holds_anyway", "its_ground"]),
    "descriptions": ("Consecutive 'the one who' clauses describing one referent.",
                     ["described_as", "group_subject"]),
}


def _kinds():
    return json.loads((ROOT / "ontology" / "kinds.json").read_text(encoding="utf-8"))


def _gold_refs():
    """Every verse the gold rules on, as a pattern over citations in either
    numbering (MACULA 'Exo 8:12', the Berean's 'Exod 8:16')."""
    spec = json.loads((ROOT / "tests" / "verses.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "app2"))
    import server as S                                       # noqa: E402  (constants only)
    moved = json.loads((OUT / "versemap.json").read_text(encoding="utf-8")).get("moved") or {}
    pats = set()
    for ref in spec:
        if ref.startswith("_"):
            continue
        for r in (ref, moved.get(ref, ref)):
            b, c, v = r.split(".")
            for name in {b, S.MACULA_BACK.get(b, b), S.TITLE.get(S.MACULA_BACK.get(b, b), b)}:
                pats.add(rf"{re.escape(name)}\.? ?{c}[:.]{v}\b")
    return re.compile("|".join(sorted(pats)))


_GOLD_WORDS = None


def _gold_words():
    """3-word runs of every gold verse's Berean text and word-by-word gloss,
    and the gold verses' chapter:verse in both numberings."""
    global _GOLD_WORDS
    if _GOLD_WORDS is None:
        spec = json.loads((ROOT / "tests" / "verses.json").read_text(encoding="utf-8"))
        refs = [r for r in spec if not r.startswith("_")]
        of = _bsb()
        moved = json.loads((OUT / "versemap.json").read_text(encoding="utf-8")).get("moved") or {}
        grams, cvs = set(), set()
        nodes, _ = load(refs)
        for r in refs:
            texts = [of(r)[1]] + [n.get("text") or "" for n in nodes[r].values() if n.get("clause")]
            for t in texts:
                w = re.findall(r"[a-z]+", t.lower().replace(".", " "))
                grams |= {" ".join(w[i:i + 3]) for i in range(len(w) - 2)}
            for x in (r, moved.get(r, r)):
                cvs.add(":".join(x.split(".")[1:]))
        _GOLD_WORDS = (grams, cvs)
    return _GOLD_WORDS


def _quotes_gold(q, grams):
    w = re.findall(r"[a-z]+", q.lower())
    return any(" ".join(w[i:i + 3]) in grams for i in range(len(w) - 2))


def blind(text, gold):
    """A definition with every sentence that cites a gold verse taken out.

    FOUND IN THE FIRST CALIBRATION RUN (2026-10-15): seven definitions
    quoted the gnat plague itself, which is the passage being scored
    ('fulfils' cited 'Exo 8:13 they did so -> Moses and Aaron'). The
    definitions are not changed; only what a judge is shown. The verse a
    judge is scored on must not be in its instructions."""
    # first the citation itself, a parenthesis naming a gold verse (with the
    # words it quotes), so the rule in the same sentence survives: "an
    # imperative, then waw + a third-person weqatal (Exo 8:12, '...')"
    grams, cvs = _gold_words()
    bare = re.compile(r"\b(" + "|".join(re.escape(c) for c in sorted(cvs)) + r")\b")
    text = re.sub(r"\s*\([^()]*\)", lambda m: "" if gold.search(m.group(0)) or bare.search(m.group(0))
                  else m.group(0), text or "")
    # SECOND PASS, after the first still leaked (2026-10-15): the gold's own
    # words quoted with no citation at all ("Aaron stretched out ... struck",
    # "just as the LORD had said"). A quotation sharing three words in a row
    # with a gold verse goes, and the rule around it stays.
    text = re.sub(r"[‘'“\"][^‘’'“”\"]{4,}[’'”\"]", lambda m: "'…'" if _quotes_gold(m.group(0), grams) else m.group(0), text)
    # then any sentence that still cites one: it is an example, not a rule
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z'(])", text)
    return " ".join(p for p in parts if not gold.search(p) and not bare.search(p)).strip()


def vocabulary():
    """The clause links, by the edge name the graph uses, with definitions
    in full (cutting them at 300 characters hid half of 'fulfils') and
    blind to the gold."""
    gold = _gold_refs()
    # where a definition was written from the gold passages, the judge reads
    # a general restatement instead (judge_definitions.json, and why there)
    neutral = json.loads(Path(__file__).with_name("judge_definitions.json").read_text(encoding="utf-8"))
    k = _kinds()
    kids = collections.defaultdict(list)
    for r in k["relations"]:
        kids[r.get("parent")].append(r)
    out = []
    for r in kids["clause_link"]:
        if r.get("status") in ("withdrawn", "superseded"):
            continue
        name = ((r.get("match") or {}).get("type") or [r["id"]])[0]
        d = neutral.get(r["id"]) or blind(r.get("definition") or SHEET_DEFS.get(r["id"], ""), gold)
        out.append({"type": name, "label": r.get("label"), "reads": r.get("reads"), "means": d})
    for r in kids["result"]:
        out.append({"type": r["id"], "label": r.get("label"), "reads": r.get("reads"),
                    "means": neutral.get(r["id"]) or blind(r.get("definition") or SHEET_DEFS.get(r["id"], ""), gold)})
    return out


def _bsb():
    sys.path.insert(0, str(ROOT / "app2"))
    import server as S                                       # noqa: E402  (constants only)
    moved = json.loads((OUT / "versemap.json").read_text(encoding="utf-8")).get("moved") or {}
    text = {}
    for line in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        d = json.loads(line)
        if "b" in d:
            text[(d["b"], d["c"], d["v"])] = d["t"]

    def of(mref):
        b, c, v = moved.get(mref, mref).split(".")
        bb = S.MACULA_BACK.get(b, b)
        return f"{S.TITLE.get(bb, bb)} {c}:{v}", text.get((bb, int(c), int(v)), "")
    return of


def load(refs):
    want = set(refs)
    nodes, edges = collections.defaultdict(dict), collections.defaultdict(list)
    for line in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8"):
        d = json.loads(line)
        if d.get("ref") in want:
            nodes[d["ref"]][d["id"]] = d
    for line in gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt", encoding="utf-8"):
        e = json.loads(line)
        if e.get("ref") in want:
            edges[e["ref"]].append(e)
    return nodes, edges


def window(ref):
    """The verses shown before this one, as text and clauses."""
    b, c, v = ref.split(".")
    return [f"{b}.{c}.{x}" for x in range(max(1, int(v) - WINDOW), int(v))]


def cand_window(ref):
    """The verses whose people and voices are candidates. In a psalm, the
    whole psalm so far: its voice and its 'LORD' are at its head, and the
    first calibration offered Psalm 119:105 neither (2026-10-15)."""
    b, c, v = ref.split(".")
    if b == "Psa":
        return [f"{b}.{c}.{x}" for x in range(1, int(v))]
    return window(ref)


def _loc(i):
    return i.split("#", 1)[1] if "#" in i else i


def build(refs):
    allrefs = sorted({r for ref in refs for r in [ref] + window(ref) + cand_window(ref)})
    nodes, edges = load(allrefs)
    bsb = _bsb()
    vocab = vocabulary()
    # a composite's members, so "they" can be checked against who they are
    members = collections.defaultdict(list)
    for r in allrefs:
        for e in edges[r]:
            if e["type"] == "member":
                m = nodes[r].get(e["dst"]) or {}
                members[e["src"]].append(m.get("lemma") or m.get("text"))
    out = {}
    for ref in refs:
        N, E = nodes[ref], edges[ref]
        pretty, text = bsb(ref)
        connective = {}
        for e in E:
            if e.get("clause_link") and e.get("connective"):
                connective.setdefault(_loc(e["dst"]), e["connective"])
        clauses = []
        for n in sorted((n for n in N.values() if n.get("clause")), key=lambda n: n["order"]):
            clauses.append({"id": n["local"], "gloss": n.get("text"), "mood": n.get("verb_mood"),
                            "verb": "/".join(x for x in (n.get("verb_person"), n.get("verb_gender"),
                                                         n.get("verb_number")) if x),
                            "force": n.get("upper_force"), "opens_with": connective.get(n["local"])})
        # the builder's current referents, to confirm or correct
        current = {_loc(e["src"]): _loc(e["dst"]) for e in E if e["type"] == "refers_to"}
        in_clause = {}
        for e in E:
            if e.get("clause_role"):
                in_clause.setdefault(_loc(e["dst"]), _loc(e["src"]).replace("ct", "cl"))
        slots = []
        for n in N.values():
            if n.get("implicit") or n.get("class") == "pron":
                inside = in_clause.get(n["local"]) or (n["local"][:-1] if n["local"].endswith("s") else None)
                said = current.get(n["local"])
                slots.append({"id": n["local"], "text": n.get("text"), "original": n.get("original"),
                              "morph": "/".join(x for x in (n.get("person"), n.get("gender"), n.get("number")) if x),
                              "in": inside,
                              # the words, not only the ids: "my" is in "shepherd", which
                              # is no candidate; the builder may point at one that is not
                              "in_text": (N.get(f"{ref}#{inside}") or {}).get("text") if inside else None,
                              "builder_says": said,
                              "builder_says_text": (N.get(f"{ref}#{said}") or {}).get("text") if said else None})
        # candidates: this verse's nouns, the chapter's people before it, turn ends, voices
        cands = []
        for n in N.values():
            # `voice is True` is a psalm's voice node; a Greek verb's `voice`
            # is "active" or "passive", and is not a candidate
            if n.get("word") and n.get("class") == "noun" or n.get("composite") or n.get("voice") is True \
                    or n.get("kind") == "writing":
                cands.append({"id": n["local"], "text": n.get("text"), "lemma": n.get("lemma"),
                              "morph": "/".join(x for x in (n.get("gender"), n.get("number")) if x),
                              "where": "this verse", **({"proper": True} if n.get("proper") else {}),
                              **({"members": members[n["id"]]} if members.get(n["id"]) else {}),
                              **({"voice": n.get("author_kind") or "voice"} if n.get("voice") is True else {})})
        seen = set()
        near = set(window(ref))
        for pref in reversed(cand_window(ref)):
            for n in nodes[pref].values():
                # beyond the near window, only names and voices: a whole
                # psalm's coordinations ("gold and silver pieces") are noise
                if n.get("word") and n.get("proper") or n.get("voice") is True \
                        or (n.get("composite") and pref in near):
                    key = n.get("lemma") or n.get("text")
                    if key in seen:
                        continue
                    seen.add(key)
                    cands.append({"id": n["id"], "text": n.get("text"), "lemma": n.get("lemma"),
                                  "morph": "/".join(x for x in (n.get("gender"), n.get("number")) if x),
                                  "where": pref, **({"proper": True} if n.get("proper") else {}),
                                  **({"members": members[n["id"]]} if members.get(n["id"]) else {}),
                                  **({"voice": n.get("author_kind") or "voice"} if n.get("voice") is True else {})})
        links, groups = [], collections.defaultdict(list)
        for e in E:
            s, d = _loc(e["src"]), _loc(e["dst"])
            if e.get("clause_link") and s.startswith("cl") and d.startswith("cl"):
                links.append(f"{s} -{e['type']}-> {d}")
            src_n = N.get(e["src"]) or {}
            if src_n.get("pair"):
                groups[s].append(f"{e['type']}={d}")
        # the verses before, as text AND as clause ids: a fulfilment ("this
        # they did", Exod 8:17) links to a command a verse or more back
        context = []
        for p in window(ref):
            pn = nodes[p]
            context.append({"ref": bsb(p)[0], "text": bsb(p)[1],
                            "clauses": [f'{n["id"]} [{n.get("verb_mood")}] {n.get("text")}'
                                        for n in sorted((n for n in pn.values() if n.get("clause")),
                                                        key=lambda n: n["order"])],
                            "groups": [f'{n["id"]} ({n.get("kind")})' for n in pn.values() if n.get("pair")]})
        out[ref] = {"ref": ref, "verse": pretty, "text": text, "lang": next(iter(N.values()), {}).get("lang"),
                    "before": context, "clauses": clauses, "slots": slots, "candidates": cands,
                    "builder_links": links,
                    "builder_groups": {g: {"kind": (N.get(f"{ref}#{g}") or {}).get("kind"), "members": m}
                                       for g, m in groups.items()},
                    "link_types": vocab,
                    "group_kinds": {k: {"means": v[0], "members": v[1]} for k, v in GROUP_KINDS.items()}}
    return out


def main():
    refs = sys.argv[1:]
    d = OUT / "sweep" / "context"
    d.mkdir(parents=True, exist_ok=True)
    for ref, c in build(refs).items():
        (d / f"{ref}.json").write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{ref}: {len(c['clauses'])} clauses, {len(c['slots'])} slots, "
              f"{len(c['candidates'])} candidates, {len(c['builder_links'])} links, "
              f"{len(c['builder_groups'])} groups")


if __name__ == "__main__":
    main()
