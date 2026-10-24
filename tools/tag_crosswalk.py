"""Every entry of the tag taxonomy, accounted for (2026-09-30).

The brief: everything in the Tag Taxonomy on the Explore page is handled in
some way, and what is not a tag is eliminated from that section. ontology/interest-taxonomy.json (1,063 entries, mostly a Copilot
draft from September) was written as the vocabulary a reading may stamp on
a section or pin to a clause. Since then much of it has become nodes of its
own: messages, speech acts, images, events, role and story patterns. Each
entry gets one status:

    tag    a reading has used it (pinned to a clause, or stamped on a section);
           it stays in the tag taxonomy
    home   never used as a tag, but a node or pattern now holds it; it leaves
           the tag section and the crosswalk says where it lives
    held   never used and no home; it leaves the section, kept here so
           nothing is lost

Stage 1 (this file, `candidates`): usage counts and candidate homes by name.
Stage 2 (judged): which candidate, if any, is the entry's home.
Stage 3 (`merge`): ontology/tag-crosswalk.json, read by
tools/upper_ontologies.py.

    python tools/tag_crosswalk.py candidates
    python tools/tag_crosswalk.py merge <dir with J_NN.json>
"""
import collections
import glob
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
STRIP = re.compile(r"_(obj|assess|feast|practice|beings|collective|place|affect|ev)$")
PREFIX = re.compile(r"^(Story pattern|Role pattern|Speech act|Message|Message group|"
                    r"Speech-act group|Story arc|Story stage): ")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


def toks(s):
    return {t for t in slug(s).split("_") if len(t) > 1 and t not in
            {"the", "and", "of", "god", "lord", "his", "who"}}


def entries():
    # every entry of the draft vocabulary, not the filtered section the page shows
    sys.path.insert(0, str(ROOT / "tools"))
    import upper_ontologies
    tags = upper_ontologies.tags(only_used=False)
    for g in tags["groups"]:
        for s in g.get("sub", []):
            for it in s.get("items", []):
                tid = it.get("id") or slug(it.get("label"))
                yield {"tag": tid, "category": g["label"], "group": s.get("label") or "",
                       "label": it.get("label") or tid, "gloss": it.get("gloss") or ""}


def usage():
    pinned, stamped = collections.Counter(), collections.Counter()
    for ln in gzip.open(OUT / "clause-tags.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if "tag" in r:
            pinned[r["tag"].removesuffix("_ev")] += 1
    for ln in open(OUT / "stamps-leveled.jsonl", encoding="utf-8"):
        if ln.strip():
            stamped[json.loads(ln)["id"].removesuffix("_ev")] += 1
    return pinned, stamped


def nodes():
    """Every node a tag could have become: id, shown name, type, a few refs."""
    out = []
    for f in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            d = json.loads(ln)
            if d.get("type") in ("passage",) or d["id"].startswith(("stage_", "tplstage_", "clause")):
                continue
            nm = PREFIX.sub("", d.get("name") or d["id"])
            out.append({"id": d["id"], "name": nm, "type": d.get("type"),
                        "aka": (d.get("aka") or [])[:4], "desc": (d.get("desc") or "")[:120],
                        "t": toks(nm) | {t for a in (d.get("aka") or []) for t in toks(a)}
                        | toks(d["id"])})
    return out


def candidates():
    pinned, stamped = usage()
    ns = nodes()
    by_tok = collections.defaultdict(list)
    for n in ns:
        for t in n["t"]:
            by_tok[t].append(n)
    rows = []
    for e in entries():
        base = STRIP.sub("", e["tag"].removesuffix("_ev"))
        e["pinned"], e["stamped"] = pinned[e["tag"].removesuffix("_ev")], stamped[e["tag"].removesuffix("_ev")]
        et = toks(base) | toks(e["label"])
        score = collections.Counter()
        for t in et:
            for n in by_tok.get(t, []):
                score[n["id"]] += 1
        byid = {n["id"]: n for n in ns}
        # a chain ("shepherd > sheep > pasture") is headed by its first link
        head = toks(e["label"].split(">")[0]) if ">" in e["label"] else set()
        for t in head:
            for n in by_tok.get(t, []):
                score[n["id"]] += 2
        # the same letters, split differently: "cornerstone" is image_corner_stone
        flat = base.replace("_", "")
        lab = slug(e["label"])
        for n in ns:
            if len(flat) > 4 and flat in n["id"].replace("_", ""):
                score[n["id"]] += 3
            # the very name: "jerusalem", "ur", the message "Go" (first cut
            # ranked "church at Jerusalem" above Jerusalem, and dropped names of
            # two letters altogether)
            if slug(n["name"]) in (base, lab) or n["id"] in (base, "msg_" + lab, "sact_" + base):
                score[n["id"]] += 6
            # a chain ("king > kingdom > law") is a pattern's shape: every role
            # and story pattern sharing a link is a candidate (forty Canaanite
            # kings crowded rolepat_king out of the top eight)
            if ">" in e["label"] and n["id"].startswith(("rolepat_", "tpl_")) and \
                    n["t"] & toks(e["label"].replace(">", " ")):
                score[n["id"]] += 4
        best = sorted(score, key=lambda k: (-score[k] / max(1, len(byid[k]["t"]) ** 0.5), k))[:8]
        e["candidates"] = [{k: byid[i][k] for k in ("id", "name", "type", "aka", "desc")}
                           for i in best]
        rows.append(e)
    (OUT / "tag-crosswalk-candidates.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    c = collections.Counter("tag" if r["pinned"] or r["stamped"] else "to judge" for r in rows)
    print(len(rows), dict(c))


# THING TAGS FOLD INTO THEIR NODE (2026-09-30, card: fold into the
# node). A used tag naming a thing a node holds is off the tag list;
# the node keeps the reading's clauses as weak evidence. Found by the very name,
# by the theme map for the major themes, and by hand for these, each read:
FOLD = {"jonathan_and_david": "covenant_of_jonathan_and_david",
        "covenant_at_shechem": "event_covenant_renewal_at_shechem",
        "annunciation": "event_annunciation_to_mary",
        "shipwreck": "event_shipwreck_on_malta",
        # "the covenant of circumcision" (Acts 7:8) is the covenant with Abraham
        "covenant_of_circumcision": "covenant_with_abraham",
        # a role with a role pattern of its own folds into the pattern
        "shepherd": "rolepat_shepherd", "king": "rolepat_king", "prophet": "rolepat_prophet",
        "priest": "rolepat_priest", "bridegroom": "rolepat_bridegroom",
        "father": "rolepat_father", "servant": "rolepat_servant"}
# what a passage-kind tag is, in the regrouped section ("Keep, regrouped")
REGROUP = {"parables": "Genre", "dreams": "Genre", "prophetic categories": "Genre",
           "reversals": "Story shape", "event images": "Story shape",
           "devices": "Literary device", "aggregates": "Literary device",
           "apocalyptic crisis": "Crisis",
           "character roles": "Roles a figure plays"}


# DISCONNECTED TAGS THAT GO (2026-09-30: not every disconnected tag
# has to stay). Measured: 38 tags in use that no other section draws on.
# Dropped: the roles a figure plays (24 -- bride, watchman, "new Moses": the
# eight real roles are role patterns now, and the "new X" readings are
# typology the graph does not hold as tags), and the covenants with no card
# (5). Kept: the 8 devices (parallelism is the backbone of Hebrew poetry) and
# "symbolic action", each the same kind as the connected tags beside it.
DROP_GROUPS = {"Roles a figure plays"}
DROP_TAGS = {"covenant_with_phinehas", "covenant_of_salt", "oath_to_the_fathers",
             "marriage_covenant", "covenant_with_creation",
             # NOT A THING THE TEXT NAMES. The question was whether "suffering servant" is even a thing
             # in the Bible. No: the text says "My Servant" (Isa 52:13), "a man
             # of sorrows" (53:3); "suffering servant" is scholars' name for the
             # Servant Songs, and the reading used it as a lens -- 806 clauses,
             # 15 in Isaiah 52-53, the rest Psalms, Gospels, Acts, Job, Genesis.
             # Folded, the Servant card would have linked them as evidence; the
             # role pattern's own row "The servant in Isaiah" is the text's
             "suffering_servant",
             # 2026-09-30, after seeing what each removes (card): messianic
             # prophecy -- 374 loose section stamps, most not prophecy at all
             # ("Hosea Redeems His Wife", "The Feeding of the Five Thousand");
             # the NT's own fulfilment formulas are held in Patterns. Union with
             # Christ -- 413 verses, about half on topic ("abide in Him") and half
             # not (a greeting, "humble like a child"). Kept: dying and rising
             # with Christ, 17 verses nearly all the text's own "died / buried /
             # raised / crucified with Christ"
             "messianic_prophecy", "union_with_christ"}


def merge(dj):
    rows = json.loads((OUT / "tag-crosswalk-candidates.json").read_text(encoding="utf-8"))
    theme_node =json.loads((ROOT / "ontology" / "themes" / "theme-nodes.json")
                            .read_text(encoding="utf-8"))
    allnodes = {n["id"]: n["name"] for n in nodes()}

    def thing_home(r):
        b = r["tag"].removesuffix("_ev")
        if r["tag"] in FOLD:
            return FOLD[r["tag"]]
        if r["category"] == "themes" and ("theme:" + b) in theme_node:
            return theme_node["theme:" + b]
        if r["category"] in REGROUP and r["category"] not in ("character roles", "event images"):
            return None      # a kind of passage, never a thing
        return next((c["id"] for c in r["candidates"]
                     if slug(c["name"]) == slug(b) or c["id"] in (b, "image_" + b)), None)
    judged = {}
    for f in sorted(glob.glob(str(Path(dj) / "J_*.json"))):
        if re.fullmatch(r"J_\d\d\.json", Path(f).name):
            for x in json.load(open(f, encoding="utf-8")):
                judged[x["tag"]] = x
    out, tally = {}, collections.Counter()
    for r in rows:
        j = judged.get(r["tag"], {})
        home = j.get("home") if j.get("home") in {c["id"] for c in r["candidates"]} else None
        group = None
        if r["pinned"] or r["stamped"]:
            th = thing_home(r)
            if th:
                st, home = "folded", th
            else:
                st = "tag"
                group = REGROUP.get(r["category"], "No card yet")
                if group in DROP_GROUPS or r["tag"] in DROP_TAGS:
                    st = "dropped"
        elif home:
            st = "home"
        else:
            st = "held"
        tally[st] += 1
        out[r["tag"]] = {"status": st, "category": r["category"], "label": r["label"],
                         "pinned": r["pinned"], "stamped": r["stamped"],
                         **({"group": group} if group else {}),
                         **({"home": home, "home_name": allnodes.get(home, home)} if home else {}),
                         **({"why": j.get("why")} if j.get("why") else {})}
    (ROOT / "ontology" / "tag-crosswalk.json").write_text(
        json.dumps({"_note": "Every tag-taxonomy entry, accounted for (tools/tag_crosswalk.py). "
                             "tag: a reading used it; home: a node holds it; held: neither.",
                    "entries": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for t, v in out.items():
        by[v["status"]][v["category"]].append((t, v))
    L = ["# The tag taxonomy, accounted for", "",
         "Made by `tools/tag_crosswalk.py`. 2026-09-30: everything on the Tag Taxonomy is handled in "
         "some way, and what is not a tag is eliminated from that section. "
         f"Every entry of ontology/interest-taxonomy.json: **{tally['tag']} tags** a reading has "
         f"used stay in the Explore section; **{tally['home']}** never used as a tag are held by a "
         f"node of their own and leave it; **{tally['held']}** neither used nor held stay listed "
         "here, so nothing is lost -- each is a candidate for a node once the text grounds it.",
         "", "## Held by a node of their own", ""]
    for cat, xs in sorted(by["home"].items()):
        L.append(f"- **{cat}** ({len(xs)}): " + "; ".join(f"{v['label']} → `{v['home']}`"
                                                          for _t, v in xs))
    L += ["", "## Not used, no node (held)", ""]
    for cat, xs in sorted(by["held"].items()):
        L.append(f"- **{cat}** ({len(xs)}): " + ", ".join(v["label"] for _t, v in xs))
    L += ["", "## Used, naming a thing: folded into its node", "",
          "2026-09-30: fold into the node. The card links the "
          "reading's clauses as candidates.", ""]
    for cat, xs in sorted(by["folded"].items()):
        L.append(f"- **{cat}** ({len(xs)}): " + "; ".join(f"{v['label']} → `{v['home']}`"
                                                          for _t, v in xs))
    L += ["", "## Used, connected to nothing else: dropped", "",
          "2026-09-30: not every disconnected tag has to stay.", ""]
    for cat, xs in sorted(by["dropped"].items()):
        L.append(f"- **{cat}** ({len(xs)}): " + ", ".join(v["label"] for _t, v in xs))
    (ROOT / "docs" / "review" / "TAG-CROSSWALK.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(dict(tally))


if __name__ == "__main__":
    if sys.argv[1] == "candidates":
        candidates()
    else:
        merge(sys.argv[2])
