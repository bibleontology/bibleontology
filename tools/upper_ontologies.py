"""The upper ontologies, gathered into one file for the reader's Explore tab.

2026-09-28: make the ontologies visible somewhere, as a fourth section under
Explore, called Upper Ontologies to avoid confusion (kinds.json already names its meaning
layer "upper"). Four parts, each saying what it is:

    the meaning classes      ontology/meaning/meaning.ttl (the upper ontology proper)
    the structure kinds      ontology/kinds.json (full page: /ontology)
    the relation vocabulary  ontology/schema/relationship_types.yaml
    the tag taxonomy         ontology/interest-taxonomy.json

Built here, not in the server: the server runs without rdflib and yaml, and a
reader layer should be a file it reads, like every other (first version
parsed in the server and two of the four parts failed there).

    python tools/upper_ontologies.py    -> out/upper-ontologies.json
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

import rdflib
import yaml
from rdflib.namespace import OWL, RDF, RDFS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"


def meaning():
    g = rdflib.Graph()
    g.parse(ROOT / "ontology" / "meaning" / "meaning.ttl")
    classes = set(g.subjects(RDF.type, OWL.Class)) | set(g.subjects(RDF.type, RDFS.Class))
    kids = collections.defaultdict(list)
    for s, o in g.subject_objects(RDFS.subClassOf):
        kids[o].append(s)

    def lab(c):
        return str(g.value(c, RDFS.label) or str(c).split("#")[-1])

    def node(c, seen=()):
        return {"label": lab(c), "comment": str(g.value(c, RDFS.comment) or ""),
                "children": [node(k, seen + (c,)) for k in sorted(kids.get(c, ()), key=lab)
                             if k not in seen]}
    roots = sorted((c for c in classes if not list(g.objects(c, RDFS.subClassOf))), key=lab)
    return {"id": "meaning", "name": "The meaning classes", "count": len(classes),
            # PROPOSED, and said so: meaning.ttl's own header reads "Nothing here
            # is built". This note called it "the upper ontology proper" until
            # the 2026-10-02 evaluation; do not describe things that
            # do not exist yet.
            "note": "A proposal, not yet applied: what every node in the meaning layer would "
                    "be a kind of — a being, a thing, a setting, an occurrence, an abstraction "
                    "— and the kinds of saying and figurative use the text would be read into. "
                    "Language-independent, so a Hebrew and a Greek passage could be compared. "
                    "Nothing in the graph is stated in these classes yet. "
                    "(ontology/meaning/meaning.ttl)",
            "tree": [node(r) for r in roots]}


def structure():
    k = json.loads((ROOT / "ontology" / "kinds.json").read_text(encoding="utf-8"))
    layers = []
    for ly in k.get("layers", []):
        cls = [c for c in k.get("classes", []) if c.get("layer") == ly["id"]]
        rel = [r for r in k.get("relations", []) if r.get("layer") == ly["id"]]
        layers.append({"label": ly.get("label"), "what": ly.get("what"),
                       "classes": [{"label": c.get("label"), "status": c.get("status"),
                                    "definition": c.get("definition")} for c in cls],
                       "relations": [{"label": r.get("label"), "status": r.get("status"),
                                      "definition": r.get("definition")} for r in rel]})
    return {"id": "structure", "name": "The structure kinds",
            "count": len(k.get("classes", [])) + len(k.get("relations", [])),
            # no link to /ontology: that page is a working page (WORKING_PAGES),
            # served only with --dev, so on the public site the link was a 404
            "note": "What the structure graph holds: clauses, contents, turns, groups, and the "
                    "links between them, each with its status. (ontology/kinds.json)",
            "layers": layers}


def relations():
    y = yaml.safe_load((ROOT / "ontology" / "schema" / "relationship_types.yaml")
                       .read_text(encoding="utf-8"))
    types = y.get("types") or {}
    if isinstance(types, list):
        types = {t.get("id"): t for t in types}
    cats = collections.defaultdict(list)
    for tid, t in types.items():
        if isinstance(t, dict):
            # a type with a second label for non-image targets shows both,
            # as the cards use both (draws_on, 2026-10-02)
            lab = t.get("label") or tid
            if t.get("plain_label"):
                lab = f"{lab} (an image) · {t['plain_label']} (anything else)"
            cats[t.get("category") or "other"].append(
                {"id": tid, "label": lab,
                 "notes": (t.get("notes") or "").strip().split("\n")[0][:220]})
    # each category under the heading a card shows ("Story echoes", not
    # "story"), in the schema's own slot order; an undeclared one keeps its id
    declared = y.get("categories") or {}

    def heading(c):
        # undeclared: as the cards show it (the server capitalises the id),
        # and said to be undeclared -- `language` holds 11 types (backlog)
        return ((declared.get(c) or {}).get("label")
                or c.replace("_", " ").capitalize() + " (not yet declared in the schema)")

    def slot(c):
        return ((declared.get(c) or {}).get("slot") or 99, heading(c))
    return {"id": "relations", "name": "The relation vocabulary",
            "count": sum(len(v) for v in cats.values()),
            "note": "Every kind of link the graph may assert between people, places, things "
                    "and ideas, by category. A relation not on this list cannot be recorded. "
                    "(ontology/schema/relationship_types.yaml)",
            "groups": [{"label": heading(c), "items": sorted(v, key=lambda x: x["id"])}
                       for c, v in sorted(cats.items(), key=lambda kv: slot(kv[0]))]}


def tags(only_used=True):
    """The tag taxonomy. ONLY WHAT A READING HAS USED (2026-09-30:
    everything on the taxonomy is handled in some way; what is not a tag is
    eliminated from that section). ontology/tag-crosswalk.json
    accounts for every entry of interest-taxonomy.json: a tag (pinned to a
    clause or stamped on a section) stays; one a node now holds, or that no
    reading ever used, leaves this section and is listed in the crosswalk
    with its home. only_used=False gives every entry (the crosswalk's input)."""
    t = json.loads((ROOT / "ontology" / "interest-taxonomy.json").read_text(encoding="utf-8"))
    xw_path = ROOT / "ontology" / "tag-crosswalk.json"
    xw = json.loads(xw_path.read_text(encoding="utf-8"))["entries"] if xw_path.exists() else {}
    keep = (lambda i: xw.get(i["id"], {}).get("status", "tag") == "tag") if only_used and xw \
        else (lambda i: True)

    def item(x):
        if isinstance(x, dict):
            return {"id": x.get("id"), "label": x.get("label") or x.get("id"),
                    "gloss": x.get("gloss") or ""}
        if isinstance(x, list):
            return {"id": x[0], "label": x[0], "gloss": x[1] if len(x) > 1 else ""}
        return {"id": x, "label": str(x).replace("_", " "), "gloss": ""}
    groups, n, moved = [], 0, collections.Counter()
    for cat, v in t.items():
        if cat.startswith("_") or not isinstance(v, dict):
            continue
        sub = []
        if "items" in v:
            sub.append({"label": "", "items": [item(x) for x in v["items"]]})
        for gk, gv in v.items():
            if gk.startswith("_") or gk == "items" or not isinstance(gv, list):
                continue
            sub.append({"label": gk.replace("_", " "), "items": [item(x) for x in gv]})
        for s in sub:
            for i in s["items"]:
                if not keep(i):
                    moved[xw.get(i["id"], {}).get("status", "held")] += 1
            s["items"] = [i for i in s["items"] if keep(i)]
        sub = [s for s in sub if s["items"]]
        if not sub:
            continue
        n += sum(len(s["items"]) for s in sub)
        groups.append({"label": cat.replace("_", " "), "note": v.get("_note") or "", "sub": sub})
    if only_used and xw:
        # REGROUPED BY WHAT KIND OF PASSAGE (2026-09-30: kept, regrouped):
        # a tag here says what sort of stretch of text this is; the old
        # categories become sub-groups, so no group stands with a single tag
        order = ["Genre", "Story shape", "Literary device", "Crisis", "Roles a figure plays",
                 "No card yet"]
        notes = {"Genre": "What kind of speech or vision a passage is: a parable, a dream, an "
                          "oracle of judgment.",
                 "Story shape": "A shape an event takes, wherever it recurs: a sea crossing, a "
                                "theophany, the younger over the elder.",
                 "Literary device": "How a passage is made: parallelism, chiasm, inclusio; and "
                                    "the collections the text lists (the beatitudes, the armour "
                                    "of God).",
                 "Crisis": "The undoing the apocalyptic passages describe.",
                 "No card yet": "Themes and events a reading tags that no node holds yet; "
                                "each is a candidate for one."}
        regroup = collections.OrderedDict((k, collections.OrderedDict()) for k in order)
        seen = set()
        for g in groups:
            for s in g["sub"]:
                for i in s["items"]:
                    # once, under the category the crosswalk records ("symbolic
                    # action" is in two of the draft's categories)
                    if i["id"] in seen or xw.get(i["id"], {}).get("category") not in (None, g["label"]):
                        continue
                    seen.add(i["id"])
                    grp = xw.get(i["id"], {}).get("group") or "No card yet"
                    regroup.setdefault(grp, collections.OrderedDict()) \
                           .setdefault(g["label"], []).append(i)
        groups = [{"label": k, "note": notes.get(k, ""),
                   "sub": [{"label": c, "items": its} for c, its in v.items()]}
                  for k, v in regroup.items() if v]
        # counted AFTER an entry in two draft categories is kept once: the
        # header said 134 over groups adding to 133 (UI committee, 2026-09-30).
        # The note's figures are the crosswalk's, one per entry, for the same
        # reason: per-category counting gave 1,063 entries where there are 1,043
        n = sum(len(s["items"]) for g in groups for s in g["sub"])
        moved = collections.Counter(v.get("status") for v in xw.values())
        n_draft = sum(moved.values())
    note = ("The kinds of passage a reading tags — a model's reading of each clause, and "
            "September's stamps on sections: what SORT of passage this is (a parable, a vision, "
            "a reversal, a chiasm), which no node says. A reading, never a finding. "
            "(ontology/interest-taxonomy.json)")
    if moved:
        note += (f" Of the draft vocabulary's {n_draft:,} entries, "
                 f"{moved['folded']:,} name a thing a node holds and are folded into it (its "
                 f"card links the reading's clauses); {moved['home']:,} no reading used and a "
                 f"node holds; {moved['held']:,} neither; {moved['dropped']:,} were used but "
                 f"connected to nothing else and were dropped. Each is listed in "
                 f"ontology/tag-crosswalk.json.")
    return {"id": "tags", "name": "Passage kinds a reading tags", "count": n, "note": note,
            "groups": groups}


# NO ONE NAMED OR QUOTED, outside About. 2026-10-01: no one is
# personally named or quoted in the app outside the About page. The
# ontology files keep who said what (kinds.json's definitions cite the reading
# that made each kind necessary); the copy the Explore tab shows says what the
# kind is. Ordered: the specific shapes first, then the possessive.
UNNAME = [
    (re.compile(r"\s*\(Doug(?:, \d{4}-\d{2}-\d{2})?(?:, [^:()]*)?: '[^']*'\)"), ""),
    (re.compile(r";\s*Doug(?:, \d{4}-\d{2}-\d{2})?: (?:'[^']*'|[^)]*)(?=\))"), ""),
    (re.compile(r"\. He weighed the pray-er as a second referent and set it"),
     ". The one who prays the psalm was weighed as a second referent and set"),
    (re.compile(r"Doug: (\S+) '([^']*)'"), r"\1 \2"),
    (re.compile(r"\s*[:—-]?\s*Doug(?:, \d{4}-\d{2}-\d{2})?(?:, on [^,]+)?,? '[^']*'?"), ""),
    (re.compile(r"\s*Doug: '[^']*'?"), ""),
    (re.compile(r", all from Doug"), ""),
    (re.compile(r"Doug's"), "a reader's"),
]


def unname(x):
    if isinstance(x, dict):
        return {k: unname(v) for k, v in x.items()}
    if isinstance(x, list):
        return [unname(v) for v in x]
    if isinstance(x, str) and "Doug" in x:
        for pat, plain in UNNAME:
            x = pat.sub(plain, x)
    return x


def main():
    parts = unname([meaning(), structure(), relations(), tags()])
    (OUT / "upper-ontologies.json").write_text(
        json.dumps({"_note": "Built by tools/upper_ontologies.py from the ontology files.",
                    "parts": parts}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("; ".join(f"{p['name']} {p['count']}" for p in parts))


if __name__ == "__main__":
    main()
