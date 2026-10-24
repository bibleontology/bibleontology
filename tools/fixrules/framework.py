"""The plug-in framework for structure-graph rules.

2026-09-26: provide a python framework that the DeepSeek solution can plug
into, and put the framework in its cache along with some good examples that
have worked. This file and `rules/` are the ONLY
Python released to a worker. The builder that makes the graph is not; a
rule sees what the builder produced, never how.

THE GRAPH A RULE SEES
One language at a time, as two lists of plain dicts.

Nodes (`id` is "<ref>#<local>", e.g. "2Sa.17.14#cl2"):
  - a CLAUSE: `clause: True`, `order` (0.. within the verse), `text`,
    `rule` (MACULA's clause pattern, e.g. "S-V-PP-PP"), and for a clause with
    a verb: `verb_lemma`, `verb_mood` (qatal, yiqtol, wayyiqtol, weqatal,
    imperative, cohortative, jussive, participle, infinitive construct,
    infinitive absolute), `verb_stem` (qal, niphal, piel, hiphil ...),
    `verb_person`, `verb_gender`, `verb_number`; `upper_force` (assertion,
    question, command, nonfinite).
  - its CONTENT (what the clause says): `content: True`, id "<ref>#ct<n>"
    for clause "<ref>#cl<n>" (a causative's inner event is "#ct<n>c").
  - a WORD: `text` (English), `lemma` (Hebrew), `strong`, `pos` (noun,
    verb, adjective, pronoun, preposition, particle, conjunction, adverb),
    `class`, `type` (proper, common, personal ...), `gender`, `number`,
    `person`, `proper`, `usual` (the most frequent rendering). A pronoun the
    verb implies has `implicit: True`. NOTE: until plan item 2.5, a word is
    ONE node per word text per verse — two "Absalom"s in a verse share it.
  - a VERB: `verb: True`, `lemma`, `mood`, `stem`, `person`, `gender`,
    `number`.
  - a COMPOSITE (a coordination or a phrase): `composite: True`; its parts
    by `member` edges.
  - a GROUP (a speech turn, a command with its effect, acts of one agent
    ...): `pair: True` or a `kind`, with `head` and `part` / `frame` edges.

Edges `{ref, lang, type, src, dst, ...}`:
  - ROLES, `clause_role: True`, from a content to what fills it:
    `v` verb, `s` subject, `o` object, `p` predicate (a verbless clause),
    `pp` prepositional phrase (`prep`, `prep_gloss`), `neg`, `qualifier`
    (word -> word, `rel`: of / attribute / quantity / like / focus ...),
    `refers_to` (a pronoun -> who it is).
  - CLAUSE LINKS, `clause_link: True`, clause -> clause: and, because,
    if, then, purpose, result, content, within, when_if_though, contrast,
    but_rather, until_limit, conceded ... (the ontology's relations), and a
    group's `frame` / `part` / `sender`.
  - ORDER, `order_link: True`, `next`: clause -> the clause after it.
  - Others (no flag) are the older flat layer, named after verbs and
    glosses; a rule should not rely on them.
  - `inferred: "<why>"` marks an edge a rule supplied rather than the
    text; `reading: "BSB"` marks one taken from the English translation.

A RULE is a module in `rules/` with three passes (2026-09-26: the
framework supports a detection pass, a fix pass, and a validate
pass):
    NAME  = "short_name"
    BASIS = "original"        # or "translation" (the BSB fallback)
    TEST  = "the condition, in plain words, over general features"

    def detect(v):            # v is a Verse; yield one dict per place the
        ...                   #   rule applies: {"at": node id, "why": ...,
                              #   anything fix / validate need}
    def fix(v, f):            # f is one finding; yield Change objects
        ...
    def validate(v, f):       # run AFTER the fix is applied; return a list
        ...                   #   of problems (empty = the fix holds)

DETECT is measured on its own first: a sample of detections is judged
before any fix is written, so a rule that fires in the wrong places is
caught before it changes anything. VALIDATE states what must be true once
the fix is in, in terms of the graph, not of the rule's own steps (e.g.
"this clause now has exactly one verb, and it is a verb of an earlier
clause"). A fix whose validation fails is UNDONE and reported, never kept.

A rule needs nothing from outside this file. Each pass must be a pure
function of the Verse: no files, no network, no randomness, no globals
that carry state between verses.

THE GUARANTEES THE FRAMEWORK KEEPS (a rule cannot break them):
  - A change must name nodes that exist; an edge has at least one end in
    THIS verse (the other may be earlier: a turn framed before, a referent).
  - An edge type must already exist in the graph as a role or link, or be
    a relation of the ontology. A new kind is a GAP for the owner.
  - A "translation" rule never removes anything and never adds a second
    `refers_to` to a pronoun that has one: the original language first.
  - Every edge a rule adds carries `rule: NAME` and `inferred`; a
    translation rule's also carries `reading: "BSB"`.
"""
import collections
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


# ----------------------------------------------------------------- changes
class Change:
    """What a rule proposes. Build them with the functions below."""

    def __init__(self, op, **kw):
        self.op, self.kw = op, kw

    def __repr__(self):
        return f"Change({self.op}, {self.kw})"


def add_edge(src, type, dst, why, **attrs):             # noqa: A002
    """A new edge; `why` becomes its `inferred` note."""
    return Change("add_edge", src=src, type=type, dst=dst, why=why,
                  attrs=attrs)


def drop_edge(src, type, dst):                          # noqa: A002
    return Change("drop_edge", src=src, type=type, dst=dst)


def set_attr(node, key, value):
    return Change("set_attr", node=node, key=key, value=value)


def add_node(local, why, **fields):
    """A new node "<ref>#<local>" (e.g. a subject the text implies). A
    field named after a Python keyword goes in as **{"class": "noun"}."""
    return Change("add_node", local=local, why=why, fields=fields)


# ------------------------------------------------------------------- views
def _key(ref):
    b, c, v = ref.split(".")
    return (b, int(c), int(v))


class Graph:
    """Indexes over one language's nodes and edges."""

    def __init__(self, nodes, edges, lang="hebrew", bsb=None, words=None):
        self.lang = lang
        self.nodes = {n["id"]: n for n in nodes if n.get("id")}
        self.edges = edges
        self.by_ref_n = collections.defaultdict(list)
        self.by_ref_e = collections.defaultdict(list)
        for n in nodes:
            if n.get("ref"):
                self.by_ref_n[n["ref"]].append(n)
        for e in edges:
            if e.get("ref"):
                self.by_ref_e[e["ref"]].append(e)
        self.refs = sorted(self.by_ref_n, key=_key)
        self._pos = {r: i for i, r in enumerate(self.refs)}
        self.bsb = bsb or {}            # ref -> (text, [[start, end, "h####"]])
        self.words = words or {}        # ref -> [{t, l, s, p, g}]  in order

    def verse(self, ref):
        return Verse(self, ref)

    def before(self, ref, n=1):
        """The n verses before `ref` in the same chapter, nearest first."""
        i, chap, out = self._pos.get(ref, 0), ref.rsplit(".", 1)[0], []
        for j in range(i - 1, max(-1, i - 1 - n), -1):
            r = self.refs[j]
            if r.rsplit(".", 1)[0] != chap:
                break
            out.append(Verse(self, r))
        return out


class Verse:
    """One verse: its clauses in order, their roles and links."""

    def __init__(self, g, ref):
        self.g, self.ref = g, ref
        self.nodes = {n["id"]: n for n in g.by_ref_n.get(ref, [])}
        self.edges = g.by_ref_e.get(ref, [])

    # -- what is here
    def node(self, nid):
        return self.g.nodes.get(nid)

    def clauses(self):
        return sorted((n for n in self.nodes.values() if n.get("clause")),
                      key=lambda n: n.get("order", 0))

    @staticmethod
    def content(clause):
        """The content id of a clause ("#cl3" -> "#ct3")."""
        return clause["id"].replace("#cl", "#ct")

    def roles(self, clause_or_content):
        """{role type: [node ids]} filling a clause's content."""
        cid = clause_or_content if isinstance(clause_or_content, str) \
            else self.content(clause_or_content)
        r = collections.defaultdict(list)
        for e in self.edges:
            if e.get("clause_role") and e.get("src") == cid:
                r[e["type"]].append(e["dst"])
        return r

    def out(self, nid, type=None):                      # noqa: A002
        return [e for e in self.edges if e.get("src") == nid
                and (type is None or e.get("type") == type)]

    def into(self, nid, type=None):                     # noqa: A002
        return [e for e in self.edges if e.get("dst") == nid
                and (type is None or e.get("type") == type)]

    def links(self):
        """Clause links in this verse (not roles, not order)."""
        return [e for e in self.edges if e.get("clause_link")]

    def refers(self, nid):
        """Who a pronoun is, if resolved."""
        return next((e["dst"] for e in self.edges
                     if e.get("type") == "refers_to" and e.get("src") == nid),
                    None)

    # -- the text
    def words(self):
        """The original-language words in order: t (text), l (lemma),
        s (Strong's), p (part of speech), g (usual gloss)."""
        return self.g.words.get(self.ref, [])

    def bsb(self):
        """(English text, spans): each span [start, end, "h####"] is English
        the Berean editors tagged to that Hebrew word; English in no span
        was supplied by the translators or left untagged."""
        return self.g.bsb.get(self.ref, ("", []))

    def before(self, n=1):
        return self.g.before(self.ref, n)


# ------------------------------------------------------------------- rules
def load(names=None, folder=HERE / "rules"):
    """The rule modules in `rules/` (or just `names`), in name order."""
    out = []
    for p in sorted(folder.glob("*.py")):
        if p.stem.startswith("_") or (names is not None and
                                      p.stem not in names):
            continue
        spec = importlib.util.spec_from_file_location(f"fixrule_{p.stem}", p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        for a in ("NAME", "BASIS", "TEST", "detect", "fix", "validate"):
            if not hasattr(m, a):
                raise ValueError(f"rule {p.name} lacks {a}")
        if m.BASIS not in ("original", "translation"):
            raise ValueError(f"rule {p.name}: BASIS must be original or "
                             f"translation")
        out.append(m)
    return out


def allowed_types(edges, kinds_path=HERE.parent.parent / "ontology" /
                  "kinds.json"):
    t = {e["type"] for e in edges
         if e.get("clause_role") or e.get("clause_link") or
         e.get("order_link") or e.get("type") in ("refers_to", "member")}
    try:
        k = json.load(open(kinds_path, encoding="utf-8"))
        t |= {r["id"] for r in k.get("relations", []) if isinstance(r, dict)}
    except FileNotFoundError:
        pass
    return t


def run(rules, nodes, edges, lang="hebrew", bsb=None, words=None,
        refs=None, detect_only=False):
    """Run each rule's three passes over every verse, changing `nodes` and
    `edges` IN PLACE (the caller decides whether to write them).

    Returns {rule NAME: {"detected": [(ref, finding)],
                         "fixed":    [(ref, finding, [changes])],
                         "invalid":  [(ref, finding, [problems])],  undone
                         "rejected": [(ref, finding, [reasons])]}}  never applied
    """
    g = Graph(nodes, edges, lang, bsb, words)
    types = allowed_types(edges)
    flags = {}
    for e in edges:
        for f in ("clause_role", "clause_link", "order_link"):
            if e.get(f):
                flags.setdefault(e["type"], f)
    report = {}
    for m in rules:
        r = report[m.NAME] = collections.defaultdict(list)
        for ref in (refs or g.refs):
            v = g.verse(ref)
            try:
                found = list(m.detect(v) or [])
            except Exception as x:                       # noqa: BLE001
                r["rejected"].append((ref, None, [f"detect crashed: {x!r}"]))
                continue
            for f in found:
                r["detected"].append((ref, f))
                if detect_only:
                    continue
                try:
                    props = list(m.fix(v, f) or [])
                except Exception as x:                   # noqa: BLE001
                    r["rejected"].append((ref, f, [f"fix crashed: {x!r}"]))
                    continue
                ok, bad = _check(m, v, props, types)
                if bad:
                    # a fix is whole or nothing: one bad change rejects it
                    r["rejected"].append((ref, f, bad))
                    continue
                undo = _apply(m, v, ok, nodes, edges, g, flags, lang)
                try:
                    problems = list(m.validate(g.verse(ref), f) or [])
                except Exception as x:                   # noqa: BLE001
                    problems = [f"validate crashed: {x!r}"]
                if problems:
                    _undo(undo, nodes, edges, g, v)
                    r["invalid"].append((ref, f, problems))
                else:
                    r["fixed"].append((ref, f, ok))
    return report


def _check(m, v, props, types):
    ok, bad = [], []
    new = {f"{v.ref}#{c.kw['local']}" for c in props if isinstance(c, Change)
           and c.op == "add_node"}
    here = set(v.nodes) | new
    for c in props:
        if not isinstance(c, Change):
            bad.append(f"not a Change: {c!r}")
            continue
        k = c.kw
        if m.BASIS == "translation" and c.op in ("drop_edge",):
            bad.append(f"{c}: a translation rule never removes")
        elif c.op in ("add_edge", "drop_edge") and not (
                (k["src"] in here or k["dst"] in here) and
                all(x is None or x in here or x in v.g.nodes
                    for x in (k["src"], k["dst"]))):
            # one end in this verse; the other may be earlier (a speech turn
            # framed in the verse before, a referent named before)
            bad.append(f"{c}: names a node not in this verse")
        elif c.op == "add_edge" and k["type"] not in types:
            bad.append(f"{c}: '{k['type']}' is not a kind (a GAP)")
        elif c.op == "add_edge" and m.BASIS == "translation" and \
                k["type"] == "refers_to" and v.refers(k["src"]):
            bad.append(f"{c}: already resolved — the original language first")
        elif c.op == "set_attr" and k["node"] not in here:
            bad.append(f"{c}: names a node not in this verse")
        elif c.op == "set_attr" and m.BASIS == "translation" and \
                v.nodes.get(k["node"], {}).get(k["key"]) is not None:
            bad.append(f"{c}: a translation rule never overwrites")
        elif c.op == "add_node" and f"{v.ref}#{k['local']}" in v.nodes:
            bad.append(f"{c}: node exists")
        elif c.op == "drop_edge" and not any(
                e.get("src") == k["src"] and e.get("type") == k["type"] and
                e.get("dst") == k["dst"] for e in v.edges):
            bad.append(f"{c}: no such edge")
        else:
            ok.append(c)
    return ok, bad


def _same(e, ref, k):
    return e.get("ref") == ref and e.get("src") == k["src"] and \
        e.get("type") == k["type"] and e.get("dst") == k["dst"]


def _apply(m, v, changes, nodes, edges, g, flags, lang):
    """Apply one fix's changes; return what undoes them."""
    undo = []
    for c in changes:
        k = c.kw
        if c.op == "add_node":
            n = {"id": f"{v.ref}#{k['local']}", "ref": v.ref,
                 "local": k["local"], "lang": lang, **k["fields"],
                 "rule": m.NAME, "minted_for": k["why"]}
            nodes.append(n)
            g.nodes[n["id"]] = n
            g.by_ref_n[v.ref].append(n)
            v.nodes[n["id"]] = n
            undo.append(("node", n))
        elif c.op == "add_edge":
            e = {"ref": v.ref, "lang": lang, "type": k["type"],
                 "src": k["src"], "dst": k["dst"], **k["attrs"],
                 "rule": m.NAME, "inferred": k["why"]}
            f = flags.get(k["type"])
            if f:
                e[f] = True
            if m.BASIS == "translation":
                e["reading"] = "BSB"
            edges.append(e)
            g.by_ref_e[v.ref].append(e)
            undo.append(("edge", e))
        elif c.op == "drop_edge":
            gone = [e for e in g.by_ref_e[v.ref] if _same(e, v.ref, k)]
            ids = {id(e) for e in gone}
            edges[:] = [e for e in edges if id(e) not in ids]
            g.by_ref_e[v.ref] = [e for e in g.by_ref_e[v.ref]
                                 if id(e) not in ids]
            v.edges = g.by_ref_e[v.ref]
            undo.append(("dropped", gone))
        elif c.op == "set_attr":
            n = g.nodes[k["node"]]
            undo.append(("attr", (n, k["key"], k["key"] in n,
                                  n.get(k["key"]))))
            n[k["key"]] = k["value"]
    return undo


def _undo(undo, nodes, edges, g, v):
    for kind, x in reversed(undo):
        if kind == "node":
            nodes.remove(x)
            g.nodes.pop(x["id"], None)
            g.by_ref_n[v.ref].remove(x)
            v.nodes.pop(x["id"], None)
        elif kind == "edge":
            edges.remove(x)
            g.by_ref_e[v.ref].remove(x)
        elif kind == "dropped":
            edges.extend(x)
            g.by_ref_e[v.ref].extend(x)
        elif kind == "attr":
            n, key, had, old = x
            if had:
                n[key] = old
            else:
                n.pop(key, None)
    v.edges = g.by_ref_e[v.ref]
