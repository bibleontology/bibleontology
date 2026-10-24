"""Write the major-theme map into the ontology as nodes (the rule and
choices, 2026-09-29).

The rule: there can be nodes for concepts if the concept can be described by
scripture; if an existing node carries that concept, merge with it, but only
if it really has the same meaning. On the proposal
(docs/review/THEMES-NODES-PROPOSAL.md) the choice was: merge **the 6 plain ones**,
hold Creation and Judgment to discuss, keep Spirit separate; and create the
aspects and the new concepts, **both**.

Written to files of its own, so the shared store (entities.jsonl, 8,420
records) is never rewritten -- bibleont.schema.load_entities reads every
*.jsonl in ontology/entities, and relations likewise:

- ontology/entities/theme-map.jsonl: a `concept` node per theme that did not
  merge (`theme_<id>`) and per core concept that did not merge
  (`theme_<id>_c<n>`), its refs the passages the map gives (first verse of
  each, the Berean's numbering), credited to Microsoft Copilot
  (source "copilot-theme-map");
- ontology/relations/theme-map.jsonl: `specializes` ("is a narrower form
  of") -- the one type the vocabulary offers for this -- from each concept to
  its theme's node, and from each ASPECT ("Sin as Rebellion Against God") to
  the existing node it is a facet of; `implied` (the taxonomy is the map's,
  not the text's), cited to the concept's passages. "This concept names that
  node" is not an edge: the vocabulary has no catch-all relation and none is
  invented; it stays in the theme layer (out/theme-map.json);
- ontology/themes/theme-nodes.json: map key -> node id. A MERGE is exactly
  this: the theme concept IS the existing node. No existing record changes.
- Creation and Judgment keep theme nodes of their own (decided 2026-09-29):
  Judgment `aspect_of` the `judgment` node (one of its two senses);
  Creation broader than the word, with the reader's annotation
  (ontology/themes/theme-annotations.json) in its description.

Idempotent: every run rewrites these three files and nothing else.

    python tools/themes/theme_nodes.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENT = ROOT / "ontology" / "entities" / "theme-map.jsonl"
REL = ROOT / "ontology" / "relations" / "theme-map.jsonl"
MAP = ROOT / "ontology" / "themes" / "theme-nodes.json"
RETIRED = ROOT / "ontology" / "themes" / "retired-concept-nodes.json"
# cards whose name a redone sub-theme shares but whose sense it does not
NOT_THE_SAME = {"firstborn"}
SOURCE = "copilot-theme-map"
sys.path.insert(0, str(ROOT / "tools" / "themes"))
from node_proposal import head, norm  # noqa: E402
from theme_map import node_index  # noqa: E402

# The choice: "The 6 plain ones"
MERGE = {"theme:covenant": "covenant", "theme:kingdom": "kingdom",
         "theme:sacrifice": "sacrifice", "theme:image_of_god": "image_of_god",
         "sacrifice:9": "day_of_atonement", "mercy_restoration:3": "remission_of_sins",
         # A.34, 2026-10-07: two cards were confusing -- the
         # Spiritual Warfare concept "The full armor of God" is Ephesians
         # 6:10-18, which the graph already holds as the armor's card
         "spiritual_warfare:1": "the_full_armor_of_god"}
# 2026-09-29, on the two held: as themes both keep
# their own nodes, and linking Judgment as an aspect_of is approved. Judgment
# the theme (God's righteous response to sin) is one of the two senses the
# `judgment` node holds apart; Creation keeps its own node, broader than the
# word, with the reader's annotation (ontology/themes/theme-annotations.json).
THEME_ASPECT = {"theme:judgment": "judgment"}
ANNOT = ROOT / "ontology" / "themes" / "theme-annotations.json"
PICK = ["being", "concept", "observance", "covenant", "title", "image", "object", "place",
        "group", "person", "event", "creature"]


def ref_of(r):
    """the store's form: OSIS code, a space, chapter:verse ("Ps 51:17")"""
    return f"{r['book']} {r['start'][0]}:{r['start'][1]}" if r.get("start") else None


def title_of(t):
    return " ".join(w if w in ("&", "of") else w[:1].upper() + w[1:]
                    for w in t["title"].lower().split())


def main():
    tm = json.loads((ROOT / "out" / "theme-map.json").read_text(encoding="utf-8"))
    ix, ents = node_index()
    # a merge target may be any record (the armor's card is a saying, which
    # node_index leaves out of name matching), so the whole store is checked
    store = {json.loads(x)["id"] for x in (ROOT / "ontology" / "entities" / "entities.jsonl")
             .read_text(encoding="utf-8").splitlines() if x.strip()}
    for eid in MERGE.values():
        if eid not in store:
            raise SystemExit(f"merge target {eid} is not in the store")
    new, rels, key2node, seen = [], [], {}, {}
    # the concept ids a redone outline retired, kept for good (a rebuilt map
    # no longer holds them, and their redirects must not lapse)
    old_map = json.loads(MAP.read_text(encoding="utf-8")) if MAP.exists() else {}
    # A REDONE SUB-THEME NAMED AS A CARD IS THAT CARD (plan 7.6c: the drafters
    # named a sub-theme as the site's card is named, "so the page can link
    # straight to it"; the concept
    # nodes/cards already held are not to be lost). Exact name or alternative name, a
    # saying or a concept (the kinds a theme may hold); "firstborn" is the
    # birth-order card, not Romans 8:29's "the firstborn among many brothers"
    by_name = collections.defaultdict(list)
    for line in (ROOT / "ontology" / "entities" / "entities.jsonl").read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if e.get("type") in ("concept", "text", "observance") and e["id"] not in NOT_THE_SAME:
            for n in [e.get("name")] + list(e.get("aka") or []):
                by_name[re.sub(r"^the ", "", (n or "").lower().strip())].append(e["id"])
    retired = json.loads(RETIRED.read_text(encoding="utf-8")) if RETIRED.exists() else {}
    annots = {k: v for k, v in json.loads(ANNOT.read_text(encoding="utf-8")).items()
              if not k.startswith("_")} if ANNOT.exists() else {}
    # a theme of the site's own gets its cards only once its owner has seen
    # it (theme-homes.json "site_shown"; the server hides it until then too)
    shown = set(json.loads((ROOT / "ontology" / "themes" / "theme-homes.json")
                           .read_text(encoding="utf-8")).get("site_shown") or [])
    for t in tm["themes"]:
        if t.get("source") == "site" and t["id"] not in shown:
            continue
        tkey, title = "theme:" + t["id"], title_of(t)
        # WHOSE OUTLINE (plan 7.6b, 2026-10-07): Copilot's twenty, or the site's
        # own four (ontology/themes/site-themes.md), each credited as its own
        site = t.get("source") == "site"
        # A REDONE OUTLINE (plan 7.6c): the theme is Copilot's, its concepts
        # now the site's, in the texts' words -- credited to the site, given
        # new ids (`_r<n>`: a number is not the same concept as Copilot's at
        # that number), no name-matched facet links, and Copilot's old concept
        # cards redirected to the theme (they are in search indexes)
        redone = t.get("outline") == "redone"
        own = site or redone
        reader = "the site" if site else "Microsoft Copilot"
        source = "site-theme-map" if site else SOURCE
        creader = "the site" if own else reader
        csource = "site-theme-map" if own else source
        mapname = ("the site's own theme outline" if site else
                   "the theme's outline, redone in the texts' words" if redone else
                   "Microsoft Copilot's theme map")
        holder = None                  # the record that keeps Copilot's old concept ids
        if tkey in MERGE:
            tnode = MERGE[tkey]
        else:
            tnode = "theme_" + t["id"]
            refs = [x for c in t["concepts"] for p in c["passages"] for x in map(ref_of, p["refs"]) if x]
            rec = {"attrs": {"kind": "major_theme", "theme": t["id"], "reader": reader},
                   # said about the text; the tools that drafted the map are
                   # named in About (2026-09-30: About is the
                   # place for all AI credits); `reader` keeps the provenance
                   # "resolved", not "checked": only that each reference
                   # opens a real verse is verified (the 2026-10-02
                   # evaluation; About was corrected the same day)
                   "desc": f"The major theme {title}: {t.get('subtitle') or ''}. A reading: "
                           f"every passage it names resolves to a verse in the Berean text.",
                   "gender": "unknown", "id": tnode, "name": f"{title} (major theme)",
                   # every passage the theme cites, uncapped (of Creation:
                   # this can be a large theme)
                   "refs": list(dict.fromkeys(refs)), "source": source, "type": "concept"}
            note = annots.get(t["id"])
            if note:
                rec["desc"] += f"\n\n**{note['reader']}'s note.** {note['text']}"
                rec["attrs"]["annotated_by"] = note["reader"]
                # the note's passages are the node's scripture too (the reader
                # asked for that reference in the graph as well), after
                # the theme's own, which stay first: the theme is still
                # Creation
                rec["refs"] = list(dict.fromkeys(rec["refs"] + list(note.get("refs", []))))
            new.append(rec)
            holder = rec
            if tkey in THEME_ASPECT:
                eid = THEME_ASPECT[tkey]
                rels.append({"certainty": "implied", "dst": eid,
                             "note": f"the major theme {title} is one sense of "
                                     f"{ents[eid]['name']}: God's righteous response to sin "
                                     f"(2026-09-29: aspect_of approved)",
                             "refs": list(dict.fromkeys(refs))[:3], "source": SOURCE,
                             "src": tnode, "type": "aspect_of"})
        key2node[tkey] = tnode
        for c in t["concepts"]:
            ckey = f"{t['id']}:{c['n']}"
            refs = [x for p in c["passages"] for x in map(ref_of, p["refs"]) if x]
            same = seen.get(norm(c["name"]))
            if ckey in MERGE:
                cn = MERGE[ckey]
            elif redone and len(set(by_name.get(re.sub(r"^the ", "", c["name"].lower().strip()), []))) == 1:
                cn = by_name[re.sub(r"^the ", "", c["name"].lower().strip())][0]
            elif same:
                # THE SAME CONCEPT UNDER TWO THEMES is one node in both ("Church
                # as Royal Priesthood" under Priesthood and under Church): the
                # validator flagged the four pairs as one name on two nodes
                cn = same
            else:
                cn = f"theme_{t['id']}_{'r' if redone else 'c'}{c['n']}"
                new.append({"attrs": {"kind": "theme_concept", "theme": t["id"], "n": c["n"],
                                      "reader": creader},
                            "desc": (f"A sub-theme of the major theme {title}, named in the texts' "
                                     f"own words and described by the passages it cites."
                                     if redone else
                                     f"A core concept of the major theme {title}, a reading "
                                     f"described by the passages it cites."),
                            "gender": "unknown", "id": cn, "name": c["name"][:100],
                            "refs": list(dict.fromkeys(refs)), "source": csource,
                            "type": "concept"})
                if holder is None:
                    holder = new[-1]
            key2node[ckey] = cn
            seen.setdefault(norm(c["name"]), cn)
            if cn != tnode:
                rels.append({"certainty": "implied", "dst": tnode,
                             "note": f"a core concept of the major theme {title} ({mapname})",
                             "refs": list(dict.fromkeys(refs))[:3], "source": csource,
                             "src": cn, "type": "in_theme"})
            # an ASPECT of an existing node: "X as Y", X the node
            whole = norm(re.sub(r"\(.*?\)", "", c["name"]))
            h = norm(head(c["name"]))
            # the site's own concepts are named in the texts' words, never "X as
            # Y", and get no facet link by rule: the Trinity theme's concepts
            # name the Father, the Son and the Spirit, and a divine person is
            # changed only by the owner's hand
            if ckey not in MERGE and not same and h != whole and not own:
                # when a name fits several nodes, the being or concept it is,
                # not a title or a word-sense: "God as Creator" is a facet of
                # God (being), not of the title Elohim or of 'gods' (idols)
                for eid in sorted(ix.get(h, ()), key=lambda x: (PICK.index(ents[x]["type"])
                                  if ents[x]["type"] in PICK else 99, x))[:1]:
                    rels.append({"certainty": "implied", "dst": eid,
                                 "note": f"'{c['name']}' is a facet of {ents[eid]['name']} "
                                         f"(Microsoft Copilot's theme map)",
                                 "refs": list(dict.fromkeys(refs))[:3], "source": SOURCE,
                                 "src": cn, "type": "aspect_of"})
        # Copilot's old concept cards of a redone theme open its card (the
        # theme's own, or its first sub-theme where the theme is an existing
        # node): their addresses are in search indexes
        if redone and holder is not None:
            olds = sorted({v for k, v in old_map.items()
                           if k.startswith(t["id"] + ":") and v.startswith(f"theme_{t['id']}_c")}
                          | set(retired.get(t["id"], [])))
            if olds:
                retired[t["id"]] = olds
                holder["merged_from"] = sorted(set(holder.get("merged_from", [])) | set(olds))
    clash = [r["id"] for r in new if r["id"] in ents]
    if clash:
        raise SystemExit(f"ids already in the store: {clash[:5]}")
    for path, rows in ((ENT, new), (REL, rels)):
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    MAP.write_text(json.dumps(key2node, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    RETIRED.write_text(json.dumps(retired, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                       encoding="utf-8")
    aspects = sum(1 for r in rels if "facet" in r["note"])
    print(f"nodes {len(new)} ({sum(1 for r in new if r['attrs']['kind'] == 'major_theme')} themes, "
          f"{sum(1 for r in new if r['attrs']['kind'] == 'theme_concept')} concepts); merges "
          f"{len(MERGE)}; relations {len(rels)} ({aspects} aspect edges)")


if __name__ == "__main__":
    main()
