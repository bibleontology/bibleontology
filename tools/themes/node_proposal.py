"""Which theme-map concepts merge with an existing node, and which become new
concept nodes: a PROPOSAL, nothing written to the ontology.

2026-09-29: there can be nodes for concepts if the concept can be described
by scripture; if an existing node carries that concept, merge with it, but
only if it really has the same meaning.

Every theme and core concept of the map is described by scripture (its
passages, all resolved against the Berean text), so each may be a node. A
MERGE is proposed only where the concept's own head phrase -- its name up to
" as ", "(", ":" -- IS an existing node's name or alternative name, exactly;
anything else is proposed NEW, related to the nodes its name speaks of
(tools/themes/theme_map.py's name matches), never merged with them. Each
merge candidate is then READ (Claude's reading, below) for whether the two
really mean the same thing; the merge is decided by hand.

    python tools/themes/node_proposal.py  -> docs/review/THEMES-NODES-PROPOSAL.md
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "themes"))
from theme_map import node_index  # noqa: E402

# Claude's reading of each merge candidate, 2026-09-29: does the existing
# node carry the SAME meaning as the theme or concept? Keyed "theme:<id>" or
# "<theme id>:<concept n>" -> (verdict, node id or None, why). Candidates not
# read here are reported as unread.
READ = {
    "theme:creation": ("same, but filed as an image", "image_creation",
                       "the creation as a whole; the existing node is typed 'image' and named for "
                       "'creature/created' — the meaning matches, the node's type is a question"),
    "theme:covenant": ("same", "covenant",
                       "covenant as such (4 refs); NOT 'league' (a pact between people, 1 ref)"),
    "theme:kingdom": ("same", "kingdom", "God's kingdom / reign"),
    "theme:sacrifice": ("same", "sacrifice",
                        "the concept (its card already cites Hos 6:6, Ps 51:17); NOT the 'sacrifices' "
                        "object"),
    "theme:judgment": ("same, one of two senses", "judgment",
                       "the node carries two senses (deciding justly; condemnation) and says so; the "
                       "theme is God's judgment, which spans both"),
    "theme:spirit": ("different", None,
                     "the theme is God's Spirit at work; 'spirit' is the word in every sense (breath, "
                     "wind, a person's spirit), and 'the Holy Spirit' is a person-node — a theme about "
                     "Him, related to that node, not merged into it"),
    "theme:image_of_god": ("same", "image_of_god",
                           "the image of God in humanity; NOT the title 'the image of God', which is "
                           "Christ (2 Cor 4:4) — that one relates to concept 9"),
    "sacrifice:9": ("same", "day_of_atonement", "the Day of Atonement, the observance (Lev 23:27)"),
    "mercy_restoration:3": ("same", "remission_of_sins",
                            "forgiveness of sins = remission of sins; the node has one ref (Mark 1:4) "
                            "and would gain the concept's passages"),
}


def head(name):
    h = re.split(r" as | \(|:| through | in | over | under ", name, maxsplit=1)[0]
    h = re.sub(r"[^a-z' ]", " ", h.lower().replace("’", "'"))
    return re.sub(r"\s+", " ", h).strip()


def norm(s):
    s = re.sub(r"[^a-z' ]", " ", s.lower().replace("’", "'"))
    return re.sub(r"^the ", "", re.sub(r"\s+", " ", s).strip())


def main():
    tm = json.loads((ROOT / "out" / "theme-map.json").read_text(encoding="utf-8"))
    ix, ents = node_index()
    rows = []
    for t in tm["themes"]:
        items = [("theme:" + t["id"], t["title"].title(), None)] + \
                [(f"{t['id']}:{c['n']}", c["name"], c) for c in t["concepts"]]
        for key, name, c in items:
            # SAME: the whole name, its bracketed gloss set aside, is a node
            # ("Day of Atonement (Annual National Cleansing)"). A theme of one
            # part counts; a compound theme ("Sin / Exile / Death") is not any
            # one of its parts.
            whole = norm(re.sub(r"\(.*?\)", "", name))
            parts = [p for p in re.split(r"[/&]", re.sub(r"\(.*?\)", "", name)) if p.strip()]
            same = sorted(ix.get(whole, ())) if len(parts) == 1 else []
            # ASPECT: "X as Y", "X in Y" where X is a node -- a facet of X,
            # a new node related to it, never X itself
            h = norm(head(name))
            aspect = sorted(ix.get(h, ())) if not same and h != whole else []
            kind = "same" if same else "aspect" if aspect else "new"
            related = [n for n in (c["nodes"] if c else t["nodes"])
                       if n["id"] not in same + aspect]
            rows.append({"key": key, "theme": t["title"].title(), "name": name, "kind": kind,
                         "cands": same or aspect, "read": READ.get(key), "related": related})
    merge = [r for r in rows if r["kind"] == "same"]
    aspects = [r for r in rows if r["kind"] == "aspect"]
    new = [r for r in rows if r["kind"] == "new"]
    L = ["# Theme-map concepts as nodes — a proposal (nothing written yet)", "",
         "Made by `tools/themes/node_proposal.py`. 2026-09-29: concepts may be nodes if the concept can be described by scripture; "
         "an existing node that carries the concept is merged with only if it really has the same "
         "meaning.", "",
         f"**{len(rows)} items** (20 themes, {len(rows) - 20} core concepts), every one described "
         f"by its passages. **{len(merge)} could MERGE** (the whole name is an existing node — "
         f"to be read for whether it truly means the same); **{len(aspects)} are ASPECTS** of an "
         f"existing node (\"Sin as Rebellion Against God\" is a facet of sin: a new node related "
         f"to it, never merged); **{len(new)} are NEW** (no existing node), each related to the "
         "nodes its name speaks of.", "",
         "## Merge candidates — does the existing node really mean the same?", "",
         "| item | theme | existing node(s) | reading | why |", "|---|---|---|---|---|"]
    for r in merge:
        nodes = "; ".join(f"{ents[e]['name']} ({ents[e]['type']}, `{e}`)" for e in r["cands"])
        v, pick, why = r["read"] or ("unread", None, "")
        L.append(f"| {r['name']} | {r['theme']} | {nodes} | **{v}**"
                 f"{f' → `{pick}`' if pick else ''} | {why} |")
    L += ["", "## Aspects — a new node for each, related to the existing node it is a facet of",
          ""]
    for r in aspects:
        L.append(f"- **{r['name']}** ({r['theme']}) — an aspect of "
                 + ", ".join(f"{ents[e]['name']} ({ents[e]['type']})" for e in r["cands"]))
    L += ["", "## New concept nodes — described by their passages, related to what they name",
          ""]
    for r in new:
        rel = ", ".join(f"{n['name']}" for n in r["related"][:5])
        L.append(f"- **{r['name']}** ({r['theme']}){f' — relates to: {rel}' if rel else ''}")
    (ROOT / "docs" / "review" / "THEMES-NODES-PROPOSAL.md").write_text("\n".join(L) + "\n",
                                                                       encoding="utf-8")
    print(f"{len(rows)} items: {len(merge)} merge candidates "
          f"({sum(1 for r in merge if r['read'])} read), {len(aspects)} aspects, {len(new)} new")
    for r in merge:
        print(" ", r["key"], "|", r["name"], "->", [f"{e}:{ents[e]['type']}" for e in r["cands"]],
              "| read:", r["read"][0] if r["read"] else "-")


if __name__ == "__main__":
    main()
