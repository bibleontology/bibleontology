"""THE IMAGE AUDIT, step 1: a mechanical measurement, read-only (plan proposal
P-2026-10-23-4). Doug, 2026-10-23, after world and temple: "an audit starting with
all images to check that the graph is complete, tracing down to the structure
level, and then the cards - for each image if there is a corresponding object or
place card, it should be checked as well".

What the temple taught, one check each:
  - a card's verses over almost no relations (584 verses, 3 relations);
  - the clause layer naming another card where the card's word stands ("Solomon
    built household", 81 clauses; Revelation's Lamb read as "lambs");
  - a verse on both the figure's and the literal card's lists, or a verse the
    description says readers divide over sitting on either list (Haggai 2:9);
  - a description citing verses that no relation carries (the five figures of
    the temple, 2 relations).

The card's verses are asked of a running server (python app2/server.py --port
8012), so they are the site's own answer (tools/meaning/membership.py), not a
second definition. The server lists at most 300 verses a book, so a list can be
short of its total; the total is the server's.

    python tools/meaning/image_audit.py [--port 8012]
      -> out/meaning/image-audit/images.jsonl, summary.md

Nothing here judges meaning. It finds where to look, ranked; the judging comes
after, by verse, as for temple.
"""
import ast
import collections
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from bibleont.refs import parse_ref, RefError  # noqa: E402

OUT = ROOT / "out" / "meaning" / "image-audit"
PORT = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8012
LITERAL = {"object", "place", "creature", "observance", "person", "group", "event"}


def to_macula_map():
    """server.py's TO_MACULA (BSB book -> MACULA book), read without importing
    the server"""
    src = (ROOT / "app2" / "server.py").read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "TO_MACULA":
            return ast.literal_eval(node.value)
    raise SystemExit("TO_MACULA not found in app2/server.py")


TO_M = to_macula_map()


def verses_of_ref(text):
    """'1 Corinthians 6:19-20' -> {'1Co.6.19', '1Co.6.20'}; a chapter or book gives
    nothing (a description's citation is a verse or a range)"""
    try:
        r = parse_ref(text.strip())
    except RefError:
        return set()
    if r.granularity != "verse" or r.start_chapter != r.end_chapter:
        return set() if r.granularity != "verse" else {f"{TO_M.get(r.book, r.book)}.{r.start_chapter}.{r.start_verse}"}
    b = TO_M.get(r.book, r.book)
    return {f"{b}.{r.start_chapter}.{v}" for v in range(r.start_verse, min(r.end_verse, r.start_verse + 40) + 1)}


CITE = re.compile(r"\(([1-3]?\s?[A-Z][A-Za-z]+\.?\s+\d+:\d+(?:[-–]\d+)?)\)|\((\d+:\d+(?:[-–]\d+)?)\)")
BOOKREF = re.compile(r"([1-3]?\s?[A-Z][A-Za-z]+)\s+\d+:\d+")


def cited(desc):
    """verses a description cites in parentheses; '(7:23)' continues the last book"""
    out, last_book = set(), None
    for m in CITE.finditer(desc or ""):
        if m.group(1):
            last_book = BOOKREF.match(m.group(1)).group(1)
            out |= verses_of_ref(m.group(1).replace("–", "-"))
        elif last_book:
            out |= verses_of_ref(f"{last_book} {m.group(2)}".replace("–", "-"))
    return out


def differ_part(desc):
    """the 'Where readers differ' paragraph of a description, if any"""
    for para in re.split(r"\n\s*\n", desc or ""):
        if "readers differ" in para.lower():
            return para
    return ""


def differ_verses(para):
    """verses named in a readers-differ paragraph, with or without parentheses"""
    out, last_book = set(), None
    for m in re.finditer(r"([1-3]?\s?[A-Z][a-z]+)\s+(\d+):(\d+)(?:[-–](\d+))?|\((\d+):(\d+)\)", para):
        if m.group(1) and m.group(1) not in ("So", "The", "A", "And"):
            last_book = m.group(1)
            out |= verses_of_ref(f"{m.group(1)} {m.group(2)}:{m.group(3)}" + (f"-{m.group(4)}" if m.group(4) else ""))
        elif m.group(5) and last_book:
            out |= verses_of_ref(f"{last_book} {m.group(5)}:{m.group(6)}")
    return out


def card_verses(eid, cache={}):
    if eid not in cache:
        with urllib.request.urlopen(f"http://localhost:{PORT}/api/entity-verses?id={eid}", timeout=60) as r:
            d = json.load(r)
        cache[eid] = (d.get("total") or 0, {it["eref"] for b in d.get("books") or [] for it in b.get("items") or []},
                      [w.get("key") for w in d.get("words") or []])
    return cache[eid]


def main():
    ents = {}
    for f in sorted((ROOT / "ontology" / "entities").glob("*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                e = json.loads(ln)
                ents.setdefault(e["id"], e)
    rels = []
    for f in sorted((ROOT / "ontology" / "relations").glob("*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                rels.append(json.loads(ln))
    by = collections.defaultdict(list)
    for r in rels:
        by[r["src"]].append(r)
        by[r["dst"]].append(r)

    # the clause layer: in which verses does a clause name a record, and which
    # records do the 'card' resolutions put in each verse
    names_in = collections.defaultdict(set)          # record -> verses where a clause names it
    card_res = collections.defaultdict(collections.Counter)  # verse -> records resolved via a card
    for ln in open(ROOT / "out" / "meaning" / "clause-records.jsonl", encoding="utf-8"):
        c = json.loads(ln)
        for role in ("subject", "object"):
            x = c.get(role) or {}
            if x.get("record"):
                names_in[x["record"]].add(c["ref"])
                if str(x.get("how", "")).startswith("card"):
                    card_res[c["ref"]][x["record"]] += 1

    def rel_verses(eid):
        vs = set()
        for r in by[eid]:
            for ref in r.get("refs") or []:
                vs |= verses_of_ref(ref)
        return vs

    def card_row(eid):
        e = ents.get(eid) or {}
        total, vs, words = card_verses(eid)
        out_t = collections.Counter(r["type"] for r in by[eid] if r["src"] == eid)
        in_t = collections.Counter(r["type"] for r in by[eid] if r["dst"] == eid)
        backed = len(vs & names_in[eid])
        others = collections.Counter()
        for v in vs:
            for rec, n in card_res[v].items():
                if rec != eid:
                    others[rec] += n
        cites = cited(e.get("desc"))
        unbacked = sorted(cites - rel_verses(eid))
        differ = differ_verses(differ_part(e.get("desc")))
        return {"id": eid, "name": e.get("name"), "type": e.get("type"), "verses": total, "words": words,
                "relations": sum(out_t.values()) + sum(in_t.values()), "out": dict(out_t), "in": dict(in_t),
                "clause_names_it_in": backed, "clause_other_cards": others.most_common(5),
                "desc_cites": len(cites), "desc_cites_unbacked": unbacked,
                "differ_named": sorted(differ), "differ_on_list": sorted(differ & vs), "_vs": vs}

    images = sorted(i for i, e in ents.items() if e.get("type") == "image")
    rows, seen_literal = [], {}
    for n, iid in enumerate(images, 1):
        row = card_row(iid)
        lit = [r["dst"] for r in by[iid] if r["src"] == iid and r["type"] == "drawn_from"
               and (ents.get(r["dst"]) or {}).get("type") in LITERAL]
        row["signifies"] = sorted({r["dst"] for r in by[iid] if r["src"] == iid and r["type"] == "signifies"})
        row["literal"] = []
        for lid in lit:
            if lid not in seen_literal:
                seen_literal[lid] = card_row(lid)
            L = seen_literal[lid]
            row["literal"].append({k: v for k, v in L.items() if k != "_vs"} |
                                  {"overlap": sorted(row["_vs"] & L["_vs"])[:40],
                                   "overlap_n": len(row["_vs"] & L["_vs"])})
        gaps = []
        if not lit:
            gaps.append("no literal card (drawn_from)")
        if not row["signifies"]:
            gaps.append("signifies nothing")
        if row["desc_cites_unbacked"]:
            gaps.append(f"{len(row['desc_cites_unbacked'])} cited verses no relation carries")
        if row["verses"] >= 5 and row["clause_names_it_in"] == 0:
            gaps.append(f"the clause layer never names it in its {row['verses']} verses")
        if row["differ_on_list"]:
            gaps.append(f"{len(row['differ_on_list'])} readers-differ verses on its list")
        for L in row["literal"]:
            if L["overlap_n"]:
                gaps.append(f"{L['overlap_n']} verses on both it and {L['id']}")
            if L["verses"] >= 20 and L["relations"] <= 3:
                gaps.append(f"{L['id']}: {L['verses']} verses over {L['relations']} relations")
            if L["differ_on_list"]:
                gaps.append(f"{L['id']}: {len(L['differ_on_list'])} readers-differ verses on its list")
            if L["desc_cites_unbacked"]:
                gaps.append(f"{L['id']}: {len(L['desc_cites_unbacked'])} cited verses no relation carries")
        row["gaps"] = gaps
        row.pop("_vs")
        rows.append(row)
        if n % 25 == 0:
            print(f"  {n} of {len(images)} images", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    rows.sort(key=lambda r: (-len(r["gaps"]), -r["verses"]))
    with open(OUT / "images.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    kinds = collections.Counter(re.sub(r"\d+", "N", g.split(": ", 1)[-1]) for r in rows for g in r["gaps"])
    lines = [f"# The image audit, step 1: the measurement ({len(rows)} images, {len(seen_literal)} literal cards)", "",
             "Read-only. Written by `tools/meaning/image_audit.py` against a local server. Nothing here is a",
             "finding about meaning: it says where to look. Plan proposal P-2026-10-23-4.", "",
             "## How often each gap occurs", "", "| gap | images |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in kinds.most_common()]
    lines += ["", "## The images, most gaps first (top 60)", "",
              "| image | verses | relations | signifies | literal card(s) | gaps |", "|---|---|---|---|---|---|"]
    for r in rows[:60]:
        lit = ", ".join(f"{L['id']} ({L['verses']} v, {L['relations']} rel)" for L in r["literal"]) or "none"
        lines.append(f"| {r['id']} | {r['verses']} | {r['relations']} | {len(r['signifies'])} | {lit} | "
                     f"{'; '.join(r['gaps'])} |")
    clean = sum(1 for r in rows if not r["gaps"])
    lines += ["", f"**Images with no gap found by these checks:** {clean} of {len(rows)}.", ""]
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"{len(rows)} images, {len(seen_literal)} literal cards; no gap: {clean}; -> {OUT}")


if __name__ == "__main__":
    main()
