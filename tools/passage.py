"""A passage drawn at two levels, every mark typed by the ontology.

2026-09-24: the aim was the ontology page and the frog plague graph
leveraging the ontology; then, on the first attempt, the mermaid diagram may
take multiple graphs - a high level with lower-level node definition diagrams.

So there are two kinds of diagram:

    OVERVIEW   one node per GROUP of clauses the graph connects, in text
               order, with the relations BETWEEN groups — the ordered pairs
               that reach across verses, and the proposed links that would
               join groups the graph leaves apart.
    DETAIL     one diagram per group: its clauses and the relations INSIDE it.

A group is a connected set of clauses under the relations the graph HOLDS
(says, and, because, if, ...), and nothing else. No group is inferred. That is
the point: where the graph fails to connect a speech that runs on across
verses, the overview shows the speech in pieces, and the pieces are the gap.

Everything is classified through `ontology/kinds.json` (tools/ontology.py):

    clause colour      its force in the MEANING layer, mapped from the form
                       (directive / assertion / not finite / no verb)
    solid arrow        a relation the graph HOLDS
    dashed blue arrow  a relation a PROPOSED kind would add — a preview of a
                       queue item, computed here and not in the graph
    red dashed border  an orphan: no clause points at it

    python tools/passage.py Exo.7.26 Exo.8.11      # writes out/passage.html
    /passage?from=Exo.7.26&to=Exo.8.11             # in the reader
"""
from __future__ import annotations

import collections
import gzip
import html
import json
import pathlib
import re
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools"))
import ontology as O                                    # noqa: E402

# WHICH CLAUSE LINKS THE OVERVIEW DRAWS: every built relation the ontology
# files under `clause_link`, read from ontology/kinds.json. This was a
# hand-written set, and every link type added after it — result, fulfils,
# elaborates, though, sequence — was silently left off the overview. The
# view keeps up with the ontology by reading it, not by being remembered.
def _clause_links():
    rels = O.load()["relations"]
    return {r["id"] for r in rels
            if r.get("parent") == "clause_link" and r["status"] == "built"}


def _link_labels():
    return {r["id"]: r.get("label", r["id"]) for r in O.load()["relations"]
            if r.get("parent") == "clause_link"}


LINKS = _clause_links()
# the sequence link is emitted as `then`; `within` is drawn as "inside"
LINKS |= {"then"}
SAY = {**_link_labels(), "then": "and then", "within": "inside"}

# Meaning-layer force → fill. Muted, so the arrows carry the eye.
FILL = {"directive": ("#f6e3c4", "#9a6b2f"),
        "assertion": ("#dce8f4", "#2f5d8a"),
        "wish": ("#eadcf0", "#6b3f86"),
        "nonfinite": ("#eeeae4", "#8a8175"),
        "none": ("#f3f1ec", "#a89e90")}
ARROW_CSS = {"preview": "stroke:#2f7fd0,stroke-width:2px,stroke-dasharray:6 4",
             "group": "stroke:#9a6b2f,stroke-width:1.5px",
             "says": "stroke:#4a4038,stroke-width:2.5px"}
ORPHAN_CSS = "stroke:#c03a3a,stroke-width:2.5px,stroke-dasharray:5 3"


def _mid(s):
    return re.sub(r"[^A-Za-z0-9]", "_", s)


def _lbl(s):
    # Mermaid's own entity syntax, so the label survives the page's escaping
    # of the whole diagram without being escaped twice.
    return ((s or "").replace('"', "#quot;").replace("<", "#lt;")
            .replace(">", "#gt;"))


def _nfc(s):
    return unicodedata.normalize("NFC", s or "")


def _v(ref):
    return ref.split(".", 1)[1].replace(".", ":")


def load(a, b):
    """Nodes and edges for the verses from `a` to `b`, in file order."""
    refs, on = [], False
    nodes = {}
    for line in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        r = d.get("ref")
        if r == a:
            on = True
        if on and r and r not in refs:
            if refs and refs[-1] == b:
                break
            refs.append(r)
        if on and r:
            nodes[d["id"]] = d
    want = set(refs)
    edges = []
    for line in gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt",
                          encoding="utf-8"):
        e = json.loads(line)
        if e.get("ref") in want:
            edges.append(e)
    return refs, nodes, edges


def english(refs):
    try:
        moved = json.loads((OUT / "versemap.json").read_text(
            encoding="utf-8")).get("moved") or {}
    except (OSError, ValueError):
        moved = {}
    eref = {r: moved.get(r, r) for r in refs}
    back = {v: k for k, v in eref.items()}
    out = {}
    for line in gzip.open(OUT / "bsb-align.jsonl.gz", "rt", encoding="utf-8"):
        if not line.startswith('{"ref"'):
            continue
        d = json.loads(line)
        if d.get("ref") in back:
            out[back[d["ref"]]] = (d["ref"], d.get("text") or "")
    return out


_STOP = {"the", "a", "an", "of", "to", "and", "in", "on", "for", "with", "et",
          "he", "she", "it", "they", "i", "you", "we", "his", "her", "its",
          "their", "my", "your", "our", "is", "are", "was", "be", "from", "at",
          "by", "that", "this", "these", "dm", "not", "him", "them", "me"}
_WORD = re.compile(r"[A-Za-z][A-Za-z’']*")


def _forms(node, bsbw):
    """English words that may render this Hebrew word in the Berean text, as
    (gloss forms, rendering forms). MACULA's gloss is trusted more: the
    renderings list is noisy — it has "said" among the renderings of עַם
    "people", and "may" among those of the LORD — so only a lexeme's FREQUENT
    renderings are kept (at least a tenth as common as its commonest)."""
    rend = set()
    s = re.sub(r"\D", "", node.get("strong") or "")
    lang = "g" if node.get("lang") == "greek" else "h"
    for key in (f"{lang}{s}", f"{lang}{s.lstrip('0')}"):
        rows = bsbw.get(key, [])
        top = max((n for _w, n in rows), default=0)
        for w, n in rows:
            if n >= max(2, top * 0.1):
                rend |= {t.lower() for t in _WORD.findall(w)}
    gloss = {t.lower() for t in _WORD.findall(node.get("text") or "")}
    keep = lambda xs: {f for f in xs if f not in _STOP and len(f) > 1}  # noqa
    return keep(gloss), keep(rend) - keep(gloss)


def _hit(tok, forms):
    for f in forms:
        if tok == f:
            return True
        k = min(len(tok), len(f))
        if k >= 4 and tok[:max(4, k - 2)] == f[:max(4, k - 2)]:
            return True
    return False


def bsb_spans(refs, nodes, edges, eng):
    """Where in the BEREAN text each node is, approximately.

    2026-09-25: clicking a node should pop up a box with the section of the
    verse in BSB that it describes. The Berean text tags
    only ~6 words a verse with Strong's numbers (BSB 8:2 has one), so there is
    no word-for-word alignment to read. Each Hebrew word is matched instead to
    the English the Berean uses for that lexeme elsewhere, and MACULA's gloss;
    a clause covers the stretch between its matched words, and a grouping the
    union of its members. Approximate, and labelled so on the page.
    """
    try:
        bsbw = json.loads((OUT / "bsb-words.json").read_text(
            encoding="utf-8")).get("words") or {}
    except (OSError, ValueError):
        bsbw = {}
    toks = {}
    for r in refs:
        e = eng.get(r)
        if e:
            toks[r] = [(m.start(), m.end(), m.group().lower())
                       for m in _WORD.finditer(e[1])]
    parts = collections.defaultdict(list)       # content -> word nodes
    ct_of = {}
    for e in edges:
        if e.get("type") == "asserts":
            ct_of[e["dst"]] = e["src"]
    members = collections.defaultdict(list)
    for e in edges:
        if e.get("type") == "member" and e.get("dst") in nodes:
            members[e["src"]].append(e["dst"])
    for e in edges:
        # an INFERRED participant is not in the clause's own words ("go to
        # Pharaoh" has no Moses in it), so it cannot anchor the clause's text
        if e.get("clause_role") and e.get("src") in ct_of and \
                e.get("dst") in nodes and e["type"] != "speaker" and \
                not e.get("inferred"):
            w = nodes[e["dst"]]
            parts[ct_of[e["src"]]] += [w] + [nodes[m] for m in
                                             members.get(w["id"], [])]
    spans = {}

    def hits_for(word, r):
        """[(token index, cost)]: 0 for a gloss match, 1 for a rendering."""
        gl, rd = _forms(word, bsbw)
        out = []
        for i, (_s, _e, t) in enumerate(toks.get(r, [])):
            if _hit(t, gl):
                out.append((i, 0))
            elif _hit(t, rd):
                out.append((i, 1))
        return out

    def grow(r, i, word):
        """Widen a matched token over the rest of a multi-word gloss —
        'there is no one' — allowing one small word between."""
        gl, rd = _forms(word, bsbw)
        ok = lambda t: _hit(t, gl | rd)                        # noqa: E731
        tk = toks[r]
        lo = hi = i
        while lo > 0 and (ok(tk[lo - 1][2]) or (
                tk[lo - 1][2] in _STOP and lo > 1 and ok(tk[lo - 2][2]))):
            lo -= 1
        while hi + 1 < len(tk) and (ok(tk[hi + 1][2]) or (
                tk[hi + 1][2] in _STOP and hi + 2 < len(tk)
                and ok(tk[hi + 2][2]))):
            hi += 1
        return lo, hi

    for c in (n for n in nodes.values() if n.get("clause")):
        r = c["ref"]
        if r not in toks:
            continue
        cand = [(w, hits_for(w, r)) for w in parts.get(c["id"], [])]
        cand = [(w, h) for w, h in cand if h]
        if not cand:
            continue
        # THE TIGHTEST CONSISTENT CHOICE: try each candidate as the centre,
        # give every other word its occurrence nearest it, and keep the
        # choice with the smallest stretch plus the fewest rendering-only
        # (untrusted) matches. Anchoring on the rarest word alone let a noisy
        # rendering win: "let my people go" became "said to Moses, 'Go'".
        best = None
        for _w0, h0 in cand:
            for centre, _c0 in h0:
                pick = [min(h, key=lambda x: (abs(x[0] - centre), x[1]))
                        for _w, h in cand]
                ps = [p for p, _q in pick]
                cost = (max(ps) - min(ps)) + 2 * sum(q for _p, q in pick)
                if best is None or cost < best[0]:
                    best = (cost, pick)
        pos = []
        for (w, _h), (p, _q) in zip(cand, best[1]):
            lo, hi = grow(r, p, w)
            pos += [lo, hi]
            spans.setdefault(w["id"], [(r, toks[r][lo][0], toks[r][hi][1])])
        lo, hi = min(pos), max(pos)
        spans[c["id"]] = [(r, toks[r][lo][0], toks[r][hi][1])]
        for e in edges:
            if e.get("type") == "asserts" and e.get("src") == c["id"]:
                spans[e["dst"]] = spans[c["id"]]
    kids = collections.defaultdict(list)
    for e in edges:
        if e.get("clause_link") and (nodes.get(e.get("src")) or {}) \
                .get("pair"):
            kids[e["src"]].append(e.get("dst"))

    def group(nid, depth=0):
        if nid in spans or depth > 5:
            return spans.get(nid, [])
        out = []
        for k in kids.get(nid, []):
            out += group(k, depth + 1)
        spans[nid] = out
        return out
    for n in nodes.values():
        if n.get("pair"):
            group(n["id"])
    return spans


class Diagram:
    """One mermaid graph, keeping arrow indices so styles land on the right
    arrow — `linkStyle` addresses arrows by their position in the source."""

    def __init__(self, direction):
        self.lines = [f"graph {direction}"]
        self.styles = []
        self.idx = 0
        self.classes = []

    def node(self, line):
        self.lines.append("  " + line)

    def arrow(self, src, dst, label=None, kind="held"):
        a = {"says": "==>", "held": "-->", "group": "-->", "preview": "-.->",
             "order": "~~~"}[kind]
        mid = f'|"{_lbl(label)}"|' if label and kind != "order" else ""
        self.lines.append(f"  {src} {a}{mid} {dst}")
        if kind in ARROW_CSS:
            self.styles.append((self.idx, ARROW_CSS[kind]))
        self.idx += 1

    def text(self):
        out = self.lines + self.classes
        for k, (fill, stroke) in FILL.items():
            out.append(f"  classDef f_{k} fill:{fill},stroke:{stroke},"
                       f"color:#241f1a")
        out.append("  classDef grp fill:#fff4e0,stroke:#9a6b2f,color:#241f1a")
        out.append("  classDef unit fill:#f1ece2,stroke:#6b6257,color:#241f1a")
        out.append("  classDef verse fill:#241f1a,stroke:#241f1a,"
                   "color:#fbfaf7,font-weight:600")
        for i, css in self.styles:
            out.append(f"  linkStyle {i} {css}")
        return "\n".join(out)


def build(a, b):
    onto = O.load()
    nm, em = O._node_matchers(onto), O._edge_matchers(onto)
    refs, nodes, edges = load(a, b)
    forces = onto["forces"]
    eng = english(refs)

    kinds = collections.Counter()
    for n in nodes.values():
        k = O.classify_node(n, nm)
        if k:
            kinds[k] += 1
    rels = collections.Counter()
    for e in edges:
        k = O.classify_edge(e, em)
        if k:
            rels[k] += 1

    clauses = [n for n in nodes.values() if n.get("clause")]
    order = {r: i for i, r in enumerate(refs)}
    clauses.sort(key=lambda n: (order[n["ref"]], n["order"]))
    pos = {n["id"]: i for i, n in enumerate(clauses)}
    byid = {n["id"]: n for n in clauses}
    force_of, ct_of = {}, {}
    for e in edges:
        if e.get("type") == "asserts":
            force_of[e["src"]] = e.get("force") or "-"
            ct_of[e["dst"]] = e["src"]
    subj = {}
    for e in edges:
        if e.get("type") == "s" and e.get("clause_role") and \
                e["src"] in ct_of and e.get("dst") in nodes:
            subj[ct_of[e["src"]]] = (nodes[e["dst"]].get("text"),
                                     e.get("inferred"))
    speaker = {e["src"]: nodes.get(e["dst"], {}).get("text")
               for e in edges if e.get("type") == "speaker"}

    def upper(n):
        form = force_of.get(n["id"], "-")
        spec = (forces.get(n.get("lang")) or {}).get(form) or {}
        return spec.get("upper", "none"), form

    # What the graph HOLDS between clauses.
    held = [(e["src"], e["dst"], e["type"]) for e in edges
            if e.get("clause_link") and e.get("type") in LINKS
            and e["src"] in byid and e.get("dst") in byid]

    # PREVIEWS of proposed kinds — the rules written in kinds.json and
    # docs/BACKLOG.md, computed here, drawn dashed, NOT in the graph.
    # PREVIEWS of proposed kinds: (src, dst, label, kind id). Purpose, "and
    # then", the forward `if` and the speech turn all started here as dashed
    # previews and were built (2026-09-24/25); none is proposed now. A new
    # proposed kind gets its draft rule here first, so it can be seen on a
    # real passage before it is written into the build.
    previews = []
    # refers_to WAS previewed here — a nearest-subject walk, drawn dashed as
    # "he = LORD? (proposed)". It is built now, by the stricter rule (one
    # agreeing candidate or none), and versetree draws the built edge off the
    # pronoun. The preview outlived the build and kept telling the reader a
    # resolved "he" was only proposed (Psalm 23:2, 2026-09-25); removed.
    # PROPOSED: ImperativeWarning. 2026-09-25, on BSB 8:2: a
    # continuation of the Lord's speech, but also a motivation/consequence of
    # not following the imperative. A held `if` whose condition refuses or
    # negates the verb of an earlier command in view; drawn from the command
    # to the consequence. Here as a preview until it is built.
    refuse = {_nfc("מָאֵן")}
    for s, d, t in held:
        if t != "if":
            continue
        p = byid[d]
        i = pos[d]
        lem = {_nfc(p.get("verb_lemma"))}
        for m in clauses[i + 1:]:
            if m["ref"] != p["ref"] or not (m.get("verb_mood") or "") \
                    .startswith("infinitive"):
                break
            lem.add(_nfc(m.get("verb_lemma")))
        neg = _nfc(p.get("verb_lemma")) in refuse or \
            " not " in f" {p.get('text', '')} "
        cmd = next((c for c in reversed(clauses[:i])
                    if c.get("verb_mood") in ("imperative", "jussive",
                                              "cohortative")
                    and _nfc(c.get("verb_lemma")) in lem), None)
        if neg and cmd:
            # to the if/then as a whole, where it is a node: the warning is
            # the conditional, not its consequence alone
            cnd = next((e["src"] for e in edges
                        if e.get("type") == "consequence"
                        and e.get("dst") == s), s)
            # from the Imperative group where the command has one: the
            # warning is a qualifier OF the command, alongside its aim
            imp = next((e["src"] for e in edges
                        if e.get("type") == "command"
                        and e.get("dst") == cmd["id"]), cmd["id"])
            previews.append((imp, cnd, "warning: if refused, then",
                             "warning"))

    # GROUPS: connected components of the held relations. Nothing else joins
    # clauses — not position, not a preview, not a guess.
    root = {c: c for c in byid}

    def find(x):
        while root[x] != x:
            root[x] = root[root[x]]
            x = root[x]
        return x
    for s, d, _t in held:
        root[find(s)] = find(d)
    comp = collections.defaultdict(list)
    for n in clauses:
        comp[find(n["id"])].append(n)
    units = sorted(comp.values(), key=lambda m: pos[m[0]["id"]])
    unit_of = {n["id"]: i for i, u in enumerate(units) for n in u}
    incoming = {d for _s, d, _t in held}

    def head(u):
        return next((n for n in u if n["id"] not in incoming), u[0])

    pairs = []
    for n in nodes.values():
        if not n.get("pair"):
            continue
        # a member may be a clause OR another grouping — a speech turn's part
        # is the if/then node where the verse has one
        members = sorted(((e.get("order"), e["type"], e["dst"]) for e in edges
                          if e.get("src") == n["id"] and e.get("clause_link")
                          and (e.get("dst") in byid
                               or (nodes.get(e.get("dst")) or {}).get("pair"))))
        pairs.append({"id": n["id"], "kind": n.get("kind"),
                      "lemma": n.get("lemma"), "members": members})

    def clause_label(n):
        up, form = upper(n)
        who = ""
        if n["id"] in speaker:
            who = f"<br/><i>speaker: {speaker[n['id']]} (inferred)</i>"
        elif n["id"] in subj and subj[n["id"]][1]:
            who = f"<br/><i>subject: {subj[n['id']][0]} (inferred)</i>"
        return (f'"{_lbl(n["text"][:60])}<br/><small>{up} · {_lbl(form)}'
                f'</small>{who}"')

    def paint(d, n, nid):
        up, _ = upper(n)
        d.classes.append(f"  class {nid} f_{up}")
        if n.get("orphan"):
            d.classes.append(f"  style {nid} {ORPHAN_CSS}")

    # ---- OVERVIEW: a node diagram one level up ---------------------------
    # 2026-09-24: the overview diagram should be a node diagram as well, and
    # its lower-level nodes should reference/link to the nodes in the
    # lower-level diagrams.
    #
    # So the overview's nodes are the CLAUSES — the level the verse diagrams
    # expand — with the nodes ABOVE them: a group node over each group of
    # two or more, joined to the clause it hangs from, and the ordered pairs.
    # Clause links are drawn between clauses; the content, verb and
    # participants are left to the verse diagram. Click a clause to go to the
    # same node in its verse diagram, highlighted; click a clause there to
    # come back.
    ov = Diagram("TB")
    spine = []
    last_ref = None
    for n in clauses:
        if n["ref"] != last_ref:
            e = (eng.get(n["ref"]) or (n["ref"], ""))[0]
            mark = _mid("V" + n["ref"])
            ov.node(f'{mark}(["{_v(n["ref"])}'
                    + (f" · BSB {_v(e)}" if e != n["ref"] else "") + '"])')
            ov.node(f'click {mark} call goVerse("{n["ref"]}")')
            ov.classes.append(f"  class {mark} verse")
            spine.append(mark)
            last_ref = n["ref"]
        nid = _mid(n["id"])
        ov.node(f"{nid}({clause_label(n)})")
        ov.node(f'click {nid} call showNode("{n["id"]}")')
        paint(ov, n, nid)
        spine.append(nid)
    for x, y in zip(spine, spine[1:]):
        ov.arrow(x, y, kind="order")
    for i, u in enumerate(units):
        if len(u) < 2:
            continue      # a lone clause is its own node; no group above it
        h = head(u)
        says = collections.Counter(SAY.get(t, t) for s, d, t in held
                                   if unit_of.get(s) == i)
        gid = f"G{i}"
        ov.node(f'{gid}[["group · {len(u)} clauses<br/><small>'
                + ", ".join(f"{t} {c}" for t, c in says.most_common())
                + '</small>"]]')
        ov.classes.append(f"  class {gid} unit")
        ov.arrow(gid, _mid(h["id"]), "head", "group")
    for s, d, typ in held:
        ov.arrow(_mid(s), _mid(d), SAY.get(typ, typ),
                 "says" if typ == "content" else "held")
    for p in pairs:
        pid = _mid(p["id"])
        lab = {"action-state": "action, then state",
               "imperative": "imperative + qualifiers",
               "parallel": "parallel lines",
               "turn": "speech turn",
               "writing": "writing",
               "conditional": "if … then"}.get(p["kind"], p["kind"])
        ov.node(f'{pid}{{{{"{lab}' + (f"<br/>{_lbl(p['lemma'])}"
                                     if p["lemma"] else "") + '"}}')
        ov.classes.append(f"  class {pid} grp")
        for o, t, m in p["members"]:
            ov.arrow(pid, _mid(m), f"{o} {t}", "group")
    for s, d, lab, q in previews:
        ov.arrow(_mid(s), _mid(d), f"{lab} (proposed)", "preview")

    # ---- DETAIL: the node diagram of each verse -------------------------
    # 2026-09-24: node diagrams were expected for the frog plague, as shown
    # before. The first version drew each group as clause boxes only,
    # which is the overview again at a larger size. The detail level is the
    # NODE structure — clause, content with its key, verb, participants,
    # pairs — and it is drawn by the same function as /tree and /suite, so a
    # verse cannot look one way in the suite and another here.
    sys.path.insert(0, str(ROOT / "tools"))
    import versetree                                    # noqa: PLC0415
    force_up = {n["id"]: upper(n)[0] for n in clauses}
    details = []
    for r in refs:
        if not any(n["ref"] == r for n in clauses):
            continue
        details.append({"ref": r,
                        "groups": sorted({unit_of[n["id"]] for n in clauses
                                          if n["ref"] == r}),
                        "mermaid": versetree.mermaid_built(
                            r, graph=(nodes, edges), force=force_up,
                            click="showNode",
                            # a pronoun's reference is drawn where the
                            # PRONOUN is, not in its antecedent's verse — four
                            # "he = LORD?" arrows back into 23:1 was context
                            # that does not bear on 23:1
                            extra=[(s, d, lab) for s, d, lab, k_ in previews
                                   if r == s.split("#")[0]
                                   or (k_ != "refers_to"
                                       and r == d.split("#")[0])])})

    # WHAT A CLICK SHOWS: the node's own words in the HEBREW — exact, by
    # position — and the Berean text as far as it can be matched.
    # 2026-09-25: using the Hebrew in the popup and adding the BSB to the extent
    # it fits was approved.
    spans = bsb_spans(refs, nodes, edges, eng)
    heb = {}
    want = set(refs)
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if d.get("ref") in want:
            heb[d["ref"]] = [[w.get("t") or "", w.get("g") or "",
                              w.get("l") or ""] for w in d.get("words", [])]
            if len(heb) == len(want):
                break
    wpos = {}                                   # node id -> {ref: [pos]}
    for c in clauses:
        if c.get("w"):
            wpos[c["id"]] = {c["ref"]: list(c["w"])}
    for e in edges:
        if e.get("type") == "asserts" and e["src"] in wpos:
            wpos[e["dst"]] = wpos[e["src"]]
    for n in nodes.values():
        if n.get("verb") and n.get("w"):
            wpos[n["id"]] = {n["ref"]: list(n["w"])}
    # a participant word: the positions in ITS clause carrying its lemma
    for e in edges:
        if e.get("clause_role") and e.get("src") in ct_of and \
                e.get("dst") in nodes and e["dst"] not in wpos:
            c = byid.get(ct_of[e["src"]])
            w = nodes[e["dst"]]
            if not c or not w.get("lemma") or c["ref"] not in heb:
                continue
            hit = [i for i in c.get("w", [])
                   if i < len(heb[c["ref"]])
                   and _nfc(heb[c["ref"]][i][2]) == _nfc(w["lemma"])]
            if hit:
                wpos[w["id"]] = {c["ref"]: hit}
    kids_ = collections.defaultdict(list)
    for e in edges:
        if e.get("clause_link") and (nodes.get(e.get("src")) or {}) \
                .get("pair"):
            kids_[e["src"]].append(e.get("dst"))

    def gpos(nid, depth=0):
        if nid in wpos or depth > 5:
            return wpos.get(nid, {})
        out = collections.defaultdict(set)
        for k in kids_.get(nid, []):
            for r, ps in gpos(k, depth + 1).items():
                out[r] |= set(ps)
        wpos[nid] = {r: sorted(ps) for r, ps in out.items()}
        return wpos[nid]
    for n in nodes.values():
        if n.get("pair"):
            gpos(n["id"])
    popup = {"text": {r: list(eng[r]) for r in refs if r in eng},
             "heb": {r: [[t, g] for t, g, _l in ws] for r, ws in heb.items()},
             "nodes": {}}
    for nid, n in nodes.items():
        if not (n.get("clause") or n.get("pair") or n.get("content")
                or n.get("class") or n.get("verb") or n.get("composite")):
            continue
        what = n.get("text") or n.get("key") or nid.split("#")[-1]
        if n.get("pair"):
            what = f'{n.get("kind")}: {what}'
        popup["nodes"][nid] = {
            "label": what[:120], "ref": n.get("ref"),
            "w": wpos.get(nid, {}),
            "spans": [list(s) for s in spans.get(nid, [])]}

    return {"refs": refs, "overview": ov.text(), "details": details,
            "popup": popup,
            "kinds": kinds, "rels": rels, "clauses": clauses,
            "previews": collections.Counter(q for *_x, q in previews),
            "units": units, "english": eng, "onto": onto}


def page(a, b):
    sys.path.insert(0, str(ROOT / "tools"))
    import versetree                                    # noqa: PLC0415
    g = build(a, b)
    onto = g["onto"]
    label = {x["id"]: x for x in onto["classes"] + onto["relations"]}
    n_orph = sum(1 for n in g["clauses"] if n.get("orphan"))
    singles = sum(1 for u in g["units"] if len(u) == 1)

    def chip(k, n):
        x = label.get(k, {"label": k, "status": "built"})
        return (f'<a class="chip {x["status"]}" href="/ontology#{k}">'
                f'{html.escape(x["label"])} <b>{n:,}</b></a>')

    held = "".join(chip(k, n) for k, n in g["kinds"].most_common()) + \
        "".join(chip(k, n) for k, n in g["rels"].most_common()
                if k != "flat")
    faults = "".join(
        f'<li><a href="/ontology#{k}">{html.escape(label[k]["label"])}</a>: '
        f'{html.escape(label[k]["known_fault"])}</li>'
        for k in ("ActionState", "if", "and")
        if label.get(k, {}).get("known_fault"))
    prev_txt = ", ".join(
        f'{n} × <a href="/ontology#{k}">{html.escape(label[k]["label"])}</a>'
        for k, n in g["previews"].items())
    swatches = "".join(
        f'<span class="sw" style="background:{f};border-color:{s}"></span>'
        f'{html.escape(k if k != "nonfinite" else "not finite")} '
        for k, (f, s) in FILL.items())
    verses = "".join(
        f'<tr><td class="r">{html.escape(_v(r))}</td>'
        f'<td class="r muted">{html.escape(_v(e[0]))}</td>'
        f'<td>{html.escape(e[1])}</td></tr>'
        for r in g["refs"] for e in [g["english"].get(r, (r, ""))])
    blocks = []
    for d in g["details"]:
        r = d["ref"]
        e = g["english"].get(r, (r, ""))
        ng = len(d["groups"])
        blocks.append(
            f'<section class="unit" id="v-{_mid(r)}"><h3><span class="vref">'
            f'{html.escape(_v(r))}</span>'
            + (f'<span class="muted">BSB {html.escape(_v(e[0]))}</span>'
               if e[0] != r else "")
            + f'<span class="sz">{ng} group{"s" if ng > 1 else ""}</span>'
            f'</h3><p class="eng">{html.escape(e[1])}</p>'
            f'<div class="wrap"><pre class="mermaid">'
            f'{html.escape(d["mermaid"])}</pre></div>'
            f'<a class="up" href="#overview">↑ overview</a></section>')
    first, last = g["refs"][0], g["refs"][-1]
    # the passage's name if it is in the log of passages worked
    name = next((w.get("name", "") + " as built"
                 for w in (onto.get("passages") or {}).get("worked", [])
                 if w.get("from") == first and w.get("to") == last),
                "as built")
    # inside <script type="application/json">, so "</" must not appear raw
    popjson = json.dumps(g["popup"], ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Passage graph</title>
<style>{versetree._CSS}
.chips{{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 4px}}
.chip{{border:1px solid var(--line);border-radius:999px;padding:1px 10px;
font-size:13px;color:var(--ink);text-decoration:none;background:var(--card)}}
.chip.proposed{{border-style:dashed}}
.chip b{{font-weight:600;color:var(--muted);margin-left:3px}}
.legend{{font-size:13px;color:var(--muted);max-width:80ch;margin:10px 0 14px}}
.sw{{display:inline-block;width:12px;height:12px;border:1.5px solid;
border-radius:3px;vertical-align:-1px;margin:0 4px 0 10px}}
.sw:first-child{{margin-left:0}}
.faults{{color:var(--red);font-size:13px;max-width:84ch}}
.faults a{{color:var(--red)}}
.unit{{margin:26px 0 0;padding-top:14px;border-top:1px solid var(--line)}}
.unit h3{{margin:0 0 4px;font-size:15px;display:flex;gap:10px;
align-items:baseline;flex-wrap:wrap}}
.vref{{background:var(--ink);color:var(--bg);border-radius:999px;
padding:0 9px;font-size:12px}}
.sz{{margin-left:auto;font-weight:400;color:var(--faint);font-size:12px}}
.unit .eng{{color:var(--muted);font-size:14px;margin:0 0 8px}}
.up{{font-size:12px}}
g.node{{cursor:pointer}}
@keyframes hit{{0%,60%{{filter:drop-shadow(0 0 6px #e0a100)
drop-shadow(0 0 2px #e0a100)}}100%{{filter:none}}}}
g.node.hit{{animation:hit 2.4s ease-out}}
#pop{{position:fixed;right:16px;bottom:16px;max-width:min(520px,calc(100vw - 32px));
max-height:60vh;overflow:auto;background:var(--card);color:var(--ink);
border:1px solid var(--line);border-radius:10px;padding:12px 14px 10px;
box-shadow:0 8px 28px rgba(0,0,0,.18);font-size:15px;line-height:1.55;
display:none;z-index:10}}
#pop.on{{display:block}}
#pop .lab{{font-size:12px;color:var(--muted);margin:0 22px 6px 0}}
#pop .vr{{font-size:12px;font-weight:600;color:var(--muted);margin-top:6px}}
#pop mark{{background:#f6d77a;color:#241f1a;border-radius:2px;padding:0 1px}}
#pop .note{{font-size:11px;color:var(--faint);margin-top:8px}}
#pop .heb{{font-size:21px;line-height:1.7;margin:2px 0}}
#pop .heb .dim{{opacity:.38}}
#pop .gl{{font-size:13px;color:var(--muted);margin-bottom:6px}}
#pop .x{{position:absolute;top:6px;right:10px;border:0;background:none;
font-size:18px;color:var(--muted);cursor:pointer}}
table{{border-collapse:collapse;font-size:14px;max-width:100ch}}
td{{border-bottom:1px solid var(--line);padding:4px 10px;vertical-align:top}}
.r{{text-align:right;white-space:nowrap}} .muted{{color:var(--faint)}}
nav.top{{font-size:13px;margin:0 0 12px}} nav.top a{{margin-right:14px}}
</style>
<nav class="top"><a href="/ontology">ontology</a><a href="/suite">verse suite</a>
<a href="/tree?ref={html.escape(first)}">verse tree</a></nav>
<h1>{html.escape(first)} – {html.escape(last)} · {html.escape(name)}</h1>
<p class="h">{len(g["clauses"])} clauses in {len(g["units"])} groups across
{len(g["refs"])} verses · <b style="color:var(--red)">{n_orph} orphaned</b> ·
{singles} groups are a single clause the graph connects to nothing.
MACULA verse numbers, with the Berean alongside.</p>

<h2>What the ontology finds here</h2>
<div class="chips">{held}</div>
<p class="legend">{swatches}<br>
Clauses are coloured by their <b>force in the meaning layer</b>, mapped from
the Hebrew form through the ontology; the form is on the second line.
<b>Thick arrows</b> are <i>says</i>; thin ones are clause links the graph
holds; brown ones come from an ordered pair.
<b style="color:#2f7fd0">Dashed blue arrows are not in the graph</b>: they are
what the proposed kinds would add — {prev_txt or "none here"}.
<b style="color:var(--red)">A red dashed border is an orphan.</b></p>
<ul class="faults">{faults}</ul>

<h2>Verse by verse · the node structure</h2>
<p class="legend">Each verse as built: clause, the content it asserts (shown
by its key), the verb and each participant by role, and the groupings. The
same drawing as <code>/tree</code> and <code>/suite</code>, with the
meaning-layer force added in bold. <b>Click any node to see the stretch of the
Berean text it describes.</b><br>
<b>Dotted boxes are context, not this verse's own:</b> a grouping introduced
in an earlier verse (a speech still going), or a member described in another
verse. A grouping is solid only in the verse that introduces it — verses are a
reference layer over the graph, not where its nodes live.</p>
{"".join(blocks)}

<h2 id="overview">Overview · the passage one level up</h2>
<p class="legend">The clauses in text order with the groups and pairs above
them. Click a clause for its Berean text.</p>
<div class="wrap" id="overview-box"><pre class="mermaid">{html.escape(g["overview"])}</pre></div>

<h2>The text</h2>
<div class="tw"><table><tbody>{verses}</tbody></table></div>

<div id="pop" role="dialog" aria-live="polite"><button class="x" type="button"
aria-label="close">×</button><div id="popbody"></div></div>
<script type="application/json" id="popdata">{popjson}</script>

<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
// NODE FOR NODE between the overview and the verse diagrams. Mermaid gives a
// node the element id "<diagram>-flowchart-<nodeId>-<n>", so a node is found
// by its own id inside the right diagram and flashed.
const mid = s => s.replace(/[^A-Za-z0-9]/g, '_');
function find(box, nodeId) {{
  return box && box.querySelector(`g.node[id*="flowchart-${{nodeId}}-"]`);
}}
function flash(el) {{
  if (!el) return;
  el.scrollIntoView({{block:'center', inline:'center'}});
  el.classList.remove('hit'); void el.getBBox(); el.classList.add('hit');
}}
window.goVerse = ref => document.getElementById('v-' + mid(ref))
  ?.scrollIntoView({{block:'start'}});
window.goClause = (ref, order) =>
  flash(find(document.getElementById('v-' + mid(ref)), 'c' + order));
window.goOver = (ref, order) =>
  flash(find(document.getElementById('overview-box'),
             mid(ref + '#cl' + order)));
// THE BEREAN TEXT A NODE DESCRIBES. 2026-09-25: clicking a node pops up a
// box with the section of the verse in BSB that it describes. Every verse the node covers is shown, its stretch highlighted.
const POP = JSON.parse(document.getElementById('popdata').textContent);
const esc = s => s.replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}})[c]);
const pop = document.getElementById('pop'), body = document.getElementById('popbody');
pop.querySelector('.x').onclick = () => pop.classList.remove('on');
document.addEventListener('keydown', e => {{ if (e.key === 'Escape') pop.classList.remove('on'); }});
window.showNode = id => {{
  const n = POP.nodes[id];
  if (!n) return;
  const by = {{}};
  for (const [r, s, e] of n.spans) (by[r] = by[r] || []).push([s, e]);
  const wrefs = Object.keys(n.w || {{}});
  const refs = [...new Set([...wrefs, ...Object.keys(by)])];
  if (!refs.length) refs.push(n.ref);
  let h = `<div class="lab">${{esc(n.label)}}</div>`;
  // THE HEBREW FIRST, AND EXACT: the node's own words, marked in the verse,
  // then their glosses in order
  for (const r of refs) {{
    const ws = POP.heb[r], mine = new Set((n.w || {{}})[r] || []);
    if (!ws) continue;
    const v = r.split('.').slice(1).join(':');
    const line = ws.map(([t, g], i) => mine.has(i)
      ? `<mark>${{esc(t)}}</mark>` : `<span class="dim">${{esc(t)}}</span>`)
      .join(' ');
    const gl = ws.filter((_, i) => mine.has(i)).map(([t, g]) => esc(g))
      .join(' · ');
    const greek = /[Ͱ-Ͽἀ-῿]/.test((ws[0] || [''])[0]);
    h += `<div class="vr">${{greek ? 'Greek' : 'Hebrew'}} ${{v}}</div>`
      + `<div class="heb" dir="${{greek ? 'ltr' : 'rtl'}}">${{line}}</div>`
      + (gl ? `<div class="gl">${{gl}}</div>` : '');
  }}
  for (const r of refs) {{
    const t = POP.text[r]; if (!t) continue;
    const [bref, text] = t;
    const rs = (by[r] || []).sort((a, b) => a[0] - b[0]);
    let out = '', at = 0;
    for (const [s, e] of rs) {{
      if (s < at) continue;
      out += esc(text.slice(at, s)) + '<mark>' + esc(text.slice(s, e)) + '</mark>';
      at = e;
    }}
    out += esc(text.slice(at));
    h += `<div class="vr">Berean · BSB ${{bref.split('.').slice(1).join(':')}}</div><div>${{out}}</div>`;
  }}
  h += n.spans.length
    ? '<div class="note">The Hebrew is exact. The Berean highlight is approximate: matched through the words the Berean uses for these lexemes.</div>'
    : '<div class="note">The Hebrew is exact. No word of this node was matched in the Berean text, so the whole verse is shown.</div>';
  body.innerHTML = h;
  pop.classList.add('on');
}};
mermaid.initialize({{startOnLoad:true, theme:'neutral', securityLevel:'loose',
  maxTextSize:200000,
  flowchart:{{curve:'basis', nodeSpacing:26, rankSpacing:46, htmlLabels:true}}}});
</script>
</html>
"""


def main():
    a, b = (sys.argv[1], sys.argv[2]) if len(sys.argv) >= 3 \
        else ("Exo.7.26", "Exo.8.11")
    (OUT / "passage.html").write_text(page(a, b), encoding="utf-8")
    g = build(a, b)
    print(f"{len(g['clauses'])} clauses in {len(g['units'])} groups, "
          f"previews {dict(g['previews'])}")
    print(f"wrote {OUT / 'passage.html'}")


if __name__ == "__main__":
    main()
