"""Jesus' life as a series of events: each event once, with its tellings.

2026-09-28: the aim was to map the Gospels completely, Jesus' life as a
series of events, after the person profile was stopped (the narratives come
first, then the mapping to them). And the reason it comes first: John 3:16
is dialogue within the Nicodemus event, which foreshadows the events to
come — an event holds speech, and
speech points at other events. Nothing can point at an event that has no
node.

## What an event is here

A TELLING is a stretch of one gospel. An EVENT is one or more tellings, at
most one per gospel, that tell the same thing. Where the gospels differ the
tellings are laid side by side and never reconciled (PRINCIPLES: read the
corpus without harmonising). The row order on the page is a reading aid —
each gospel's own order is kept, merged where they agree — and is NOT a
claim about chronology.

## The three voices, and what each is trusted for

- **The BSB editors** (`\\s1` headings and `\\r` parallel notes, Public
  Domain): where each section starts, what it is called, and which sections
  of the other gospels it parallels. Benchmark-only until 2026-09-28; the
  seam scorer agrees with them 27-45% exactly, so they enter as a credited
  reading (measured that date). Every row says which voice made it.
- **Wording** (`out/allusions.jsonl.gz`, shared rare Greek lemmas): which
  verses of two gospels say the same words. It links tellings on its own
  and it SPLITS an editor's section when its verses align, in order, with
  two sections of another gospel (Mark 1:1-11 is Matthew's "John prepares
  the way" and "the baptism of Jesus").
- **Binding** (`out/structure-edges.jsonl.gz`): a clause that runs across a
  verse line (0 of 345 such lines carry a heading) forbids a split there.

    python tools/gospel_events.py   -> out/gospel-events.jsonl.gz
                                       docs/review/gospel-events.html
"""
from __future__ import annotations

import collections
import gzip
import html
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
USFM = ROOT / "data" / "raw" / "usfm" / "engbsb"
GOSPELS = {"MAT": "Mat", "MRK": "Mrk", "LUK": "Luk", "JHN": "Jhn"}
NAMES = {"Matthew": "Mat", "Mark": "Mrk", "Luke": "Luk", "John": "Jhn"}
SPINE = ("Mrk", "Mat", "Luk", "Jhn")   # merge order for the page only
WORD_MIN = 2        # aligned verse pairs for wording alone to link tellings
PAIR_SHARED = 4     # shared lemmas for a verse pair to count as aligned
DENSITY = 0.5       # wording alone joins only if this share of EACH side aligns
PROTAGONIST = 0.05  # a record in more than this share of verses binds no scene


def rows(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith('{"_'):
                yield json.loads(line)


def read_bsb():
    """Verse order, and the editors' sections with their parallel notes."""
    seq, sections = [], []
    for code, bk in GOSPELS.items():
        f = next(USFM.glob(f"*{code}*.usfm"))
        ch, pend = 0, None
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\\c (\d+)", line)
            if m:
                ch = int(m.group(1))
            m = re.match(r"\\s1 (.*)", line)
            if m:
                pend = {"title": m.group(1).strip(), "r": ""}
            m = re.match(r"\\r (.*)", line)
            if m and pend is not None:
                pend["r"] = m.group(1).strip()
            for v in re.findall(r"\\v (\d+)", line):
                ref = f"{bk}.{ch}.{v}"
                seq.append(ref)
                if pend is not None:
                    pend["start"] = ref
                    sections.append(pend)
                    pend = None
    return seq, sections


def parse_r(note):
    """'(Matthew 3:1–17; Luke 3:1–22)' -> [(book, (c, v), (c, v))]."""
    out = []
    for part in note.strip("() ").split(";"):
        m = re.match(r"\s*(Matthew|Mark|Luke|John)\s+(.*)", part)
        if not m:
            continue
        bk, rest = NAMES[m.group(1)], m.group(2)
        ch = None
        for piece in rest.split(","):
            piece = piece.strip().replace("–", "-")
            m2 = re.match(r"(?:(\d+):)?(\d+)(?:-(?:(\d+):)?(\d+))?$", piece)
            if not m2:
                continue
            if m2.group(1):
                ch = int(m2.group(1))
            if ch is None:
                continue
            a = (ch, int(m2.group(2)))
            ech = int(m2.group(3)) if m2.group(3) else ch
            b = (ech, int(m2.group(4))) if m2.group(4) else a
            out.append((bk, a, b))
            ch = ech
    return out


def cv(ref):
    _b, c, v = ref.split(".")
    return int(c), int(v)


def main():
    seq, sections = read_bsb()
    pos = {v: i for i, v in enumerate(seq)}
    book = lambda r: r.split(".")[0]  # noqa: E731
    # a clause running across a line forbids a split there
    bound = set()
    for e in rows(OUT / "structure-edges.jsonl.gz"):
        if not (e.get("clause_role") or e["type"] in
                ("within", "part", "qualifier", "member")):
            continue
        a, b = e["src"].split("#")[0], e["dst"].split("#")[0]
        if a in pos and b in pos and a != b and book(a) == book(b):
            lo, hi = sorted((pos[a], pos[b]))
            bound.update(range(lo + 1, hi + 1))
    # THE SETUP'S CAST binds a scene; the protagonist binds none (measured
    # 2026-09-28: a non-protagonist reference crossing a line 0.42x, the
    # same named cast within 2 verses on both sides 0.46x; of 57 references
    # crossing a heading, 39 are to Jesus). Protagonist = a record in more
    # than PROTAGONIST of the gospels' verses — computed, not named.
    rec, cast = {}, collections.defaultdict(set)
    for m in rows(OUT / "mentions.jsonl.gz"):
        rec[m["occurrence"]] = m["record"]
        v = m["occurrence"].split("#")[0]
        if v in pos:
            cast[pos[v]].add(m["record"])
    cover = collections.Counter(r for s in cast.values() for r in s)
    prot = {r for r, k in cover.items() if k / len(seq) > PROTAGONIST}
    cast_bound = set()
    for e in rows(OUT / "structure-edges.jsonl.gz"):
        if e["type"] != "refers_to":
            continue
        a, b = e["src"].split("#")[0], e["dst"].split("#")[0]
        if a in pos and b in pos and a != b and book(a) == book(b) and \
                (rec.get(e["dst"]) or rec.get(e["src"])) not in prot:
            lo, hi = sorted((pos[a], pos[b]))
            cast_bound.update(range(lo + 1, hi + 1))
    for i in range(1, len(seq)):
        left = set().union(*(cast[j] for j in range(max(0, i - 2), i)
                             if book(seq[j]) == book(seq[i])))
        right = set().union(*(cast[j] for j in range(i, min(len(seq), i + 2))
                              if book(seq[j]) == book(seq[i])))
        if (left & right) - prot:
            cast_bound.add(i)
    # wording: each verse's aligned verses in the other gospels
    align = collections.defaultdict(dict)       # verse -> {other verse: idf}
    for r in rows(OUT / "allusions.jsonl.gz"):
        a = r["ref"]
        if a not in pos:
            continue
        for l in r["links"]:
            b = l["ref"]
            if b in pos and book(b) != book(a) and l["shared"] >= PAIR_SHARED:
                align[a][b] = max(align[a].get(b, 0), l["idf"])
                align[b][a] = max(align[b].get(a, 0), l["idf"])
    # tellings: the editors' sections as spans of verse positions
    tell = []
    for i, s in enumerate(sections):
        lo = pos[s["start"]]
        nxt = [pos[t["start"]] for t in sections[i + 1:i + 2]
               if book(t["start"]) == book(s["start"])]
        hi = (nxt[0] if nxt else max(j for j, v in enumerate(seq)
                                     if book(v) == book(s["start"])) + 1)
        tell.append({"book": book(s["start"]), "lo": lo, "hi": hi,
                     "title": s["title"], "r": s["r"], "why": ["editors"]})

    def owner(p):
        for k, t in enumerate(tell):
            if t["lo"] <= p < t["hi"]:
                return k
        return None
    # SPLIT where a section's verses align, in order, with two sections of
    # another gospel and no clause runs across the split line
    splits = 0
    changed = True
    while changed:
        changed = False
        for k, t in enumerate(tell):
            for other in GOSPELS.values():
                if other == t["book"]:
                    continue
                marks = []                    # (my position, their section)
                for p in range(t["lo"], t["hi"]):
                    best = max(((idf, b) for b, idf in align[seq[p]].items()
                                if book(b) == other), default=None)
                    if best:
                        marks.append((p, owner(pos[best[1]])))
                # a stray single alignment elsewhere (Mark 1:2's Malachi
                # quotation -> Matt 11:10) is not a section it tells
                cnt = collections.Counter(o for _p, o in marks)
                marks = [(p, o) for p, o in marks if cnt[o] >= 2]
                owners = [o for _p, o in marks]
                runs = [o for j, o in enumerate(owners)
                        if j == 0 or o != owners[j - 1]]
                if len(runs) != 2 or len(set(runs)) != 2:
                    continue
                if min(owners.count(runs[0]), owners.count(runs[1])) < 2:
                    continue
                # the other gospel tells them as consecutive sections
                if runs[1] != runs[0] + 1:
                    continue
                cut = next(p for p, o in marks if o == runs[1])
                last = max(p for p, o in marks if o == runs[0])
                # a clause across the line forbids it; the cast only prefers
                # (John the Baptist is in both Mark 1:8 and 1:9, and 1:9 is
                # a new scene: the same cast continuing is not the same one)
                cands = [c for c in range(last + 1, cut + 1) if c not in bound]
                if not cands:
                    continue
                free = [c for c in cands if c not in cast_bound]
                c = free[-1] if free else cands[-1]
                tell[k:k + 1] = [dict(t, hi=c),
                                 dict(t, lo=c, title=(t["title"] or "")
                                      .removesuffix(" (cont.)") + " (cont.)",
                                      why=[f"split: wording aligns with two "
                                           f"sections of {other}"])]
                splits += 1
                changed = True
                break
            if changed:
                break
    # links between tellings: the editors' note, and wording
    link = collections.defaultdict(lambda: {"words": 0, "editors": False,
                                            "side": {}})
    for k, t in enumerate(tell):
        for p in range(t["lo"], t["hi"]):
            per = {}
            for b, idf in align[seq[p]].items():
                o = owner(pos[b])
                if o is not None and idf > per.get(o, 0):
                    per[o] = idf
            for o in per:
                key = tuple(sorted((k, o)))
                link[key]["words"] += 1
                link[key]["side"][k] = link[key]["side"].get(k, 0) + 1
        for bk, a, b in parse_r(t["r"]):
            for o, u in enumerate(tell):
                if u["book"] != bk:
                    continue
                s, e = cv(seq[u["lo"]]), cv(seq[u["hi"] - 1])
                if not (e < a or s > b):
                    link[tuple(sorted((k, o)))]["editors"] = True

    def density(a, b):
        """The share of EACH telling's verses that align with the other."""
        s = link[(a, b)]["side"]
        return min(s.get(a, 0) / (tell[a]["hi"] - tell[a]["lo"]),
                   s.get(b, 0) / (tell[b]["hi"] - tell[b]["lo"]))
    # EVENTS: strongest links first, at most one telling per gospel
    ev = {k: {k} for k in range(len(tell))}
    order = sorted(link.items(), key=lambda kv: (-kv[1]["editors"] -
                                                 (kv[1]["words"] >= WORD_MIN),
                                                 -kv[1]["words"]))
    # SAYINGS TRAVEL BY WORDING, EVENTS BY NARRATIVE. Wording alone never
    # merges two events: at DENSITY it records that they share a saying
    # (Matt 10:26 / Luke 12:1 "nothing hidden", in different settings).
    # Measured 2026-09-28: the editors' links spread over every density
    # (317; 17 below 0.1), wording-only links pile at the bottom (3,835;
    # 12 at 0.5 or more), and those 12 are sayings, doublets, or the two
    # annunciations (Matt 1:18 / Luke 1:26) — different scenes.
    sayings = collections.defaultdict(list)
    for (a, b), w in order:
        if os.environ.get("GE_DEBUG") and w["words"] >= WORD_MIN:
            print("DENS", w["editors"], round(density(a, b), 2),
                  seq[tell[a]["lo"]], seq[tell[b]["lo"]])
        if not w["editors"]:
            if w["words"] >= WORD_MIN and density(a, b) >= DENSITY:
                sayings[a].append(b)
                sayings[b].append(a)
            continue
        if ev[a] is ev[b]:
            continue
        books = [tell[x]["book"] for x in ev[a] | ev[b]]
        if len(books) != len(set(books)):
            continue
        merged = ev[a] | ev[b]
        for x in merged:
            ev[x] = merged
    groups = []
    seen = set()
    for k in range(len(tell)):
        g = ev[k]
        if id(g) in seen:
            continue
        seen.add(id(g))
        groups.append(sorted(g, key=lambda x: SPINE.index(tell[x]["book"])))
    # page order: each gospel's own sequence, merged in SPINE order
    placed = []
    where = {}
    for bk in SPINE:
        prev = -1
        for k in [k for k, t in enumerate(tell) if t["book"] == bk]:
            g = next(i for i, gg in enumerate(groups) if k in gg)
            if g in where:
                prev = max(prev, placed.index(g))
                continue
            placed.insert(prev + 1, g)
            prev += 1
            where[g] = True
    out = []
    for n, g in enumerate(placed):
        ts = groups[g]
        title = next((tell[k]["title"] for k in ts if tell[k]["title"] and
                      not tell[k]["title"].endswith("(cont.)")),
                     tell[ts[0]]["title"])
        rec = {"id": f"gev{n:04d}", "title": title, "tellings": []}
        for k in ts:
            t = tell[k]
            rec["tellings"].append({
                "book": t["book"], "start": seq[t["lo"]], "end": seq[t["hi"] - 1],
                "why": t["why"]})
        pairs = [(a, b) for a in ts for b in ts if a < b]
        rec["joined_by"] = [{"a": seq[tell[a]["lo"]], "b": seq[tell[b]["lo"]],
                             "editors": link[(a, b)]["editors"],
                             "verses_aligned": link[(a, b)]["words"]}
                            for a, b in pairs if (a, b) in link]
        rec["shares_wording"] = sorted({
            f"{seq[tell[o]['lo']]}-{seq[tell[o]['hi'] - 1]}"
            for k in ts for o in sayings.get(k, ()) if o not in ts})
        out.append(rec)
    with gzip.open(OUT / "gospel-events.jsonl.gz", "wt", encoding="utf-8") as f:
        f.write(json.dumps({"_source": "BSB section headings and \\r notes "
                            "(ebible.org, Public Domain) as the editors' "
                            "credited reading; MACULA Greek (CC BY 4.0) for "
                            "wording and binding.",
                            "_note": "Each event once with its tellings; page "
                            "order is a reading aid, not a chronology."}) + "\n")
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    wit = collections.Counter(len(r["tellings"]) for r in out)
    ed_only = sum(1 for r in out for j in r["joined_by"]
                  if j["editors"] and j["verses_aligned"] < WORD_MIN)
    both = sum(1 for r in out for j in r["joined_by"]
               if j["editors"] and j["verses_aligned"] >= WORD_MIN)
    shared = sum(len(v) for v in sayings.values()) // 2
    print(f"{len(tell)} tellings ({splits} split by wording), {len(out)} events;"
          f" by witnesses {dict(sorted(wit.items()))}; joins: editors and "
          f"wording {both}, editors only {ed_only}; shared sayings {shared}")
    page(out)


def page(evs):
    col = {b: i for i, b in enumerate(("Mat", "Mrk", "Luk", "Jhn"))}
    body = []
    for r in evs:
        cells = [""] * 4
        for t in r["tellings"]:
            a, b = t["start"].split("."), t["end"].split(".")
            span = (f"{a[1]}:{a[2]}–{b[2]}" if a[1] == b[1]
                    else f"{a[1]}:{a[2]}–{b[1]}:{b[2]}")
            mark = " ✂" if any(w.startswith("split") for w in t["why"]) else ""
            cells[col[t["book"]]] = f"{span}{mark}"
        how = []
        for j in r["joined_by"]:
            if j["editors"] and j["verses_aligned"] >= WORD_MIN:
                how.append("editors + wording")
            else:
                how.append("editors only")
        how = sorted(set(how))
        if r["shares_wording"]:
            how.append("shares a saying with " + ", ".join(
                s.split("-")[0].replace(".", " ", 1).replace(".", ":")
                for s in r["shares_wording"]))
        body.append("<tr><td class=t>" + html.escape(r["title"] or "—") +
                    "</td>" + "".join(f"<td>{html.escape(c)}</td>" for c in cells)
                    + f"<td class=h>{html.escape(', '.join(how))}</td></tr>")
    doc = PAGE.replace("{{ROWS}}", "\n".join(body)).replace(
        "{{N}}", str(len(evs)))
    (ROOT / "docs" / "review" / "gospel-events.html").write_text(
        doc, encoding="utf-8")


PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Gospel Events</title><style>
:root{--bg:#fbfaf7;--fg:#1d1b18;--mut:#6b655c;--line:#e4dfd6;--hd:#f1ede5}
@media (prefers-color-scheme:dark){:root{--bg:#181715;--fg:#ece8e1;
--mut:#a39c90;--line:#34312c;--hd:#23211e}}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;
margin:0;padding:16px}h1{font-size:20px;margin:0 0 4px}
p{color:var(--mut);max-width:70em;margin:4px 0 12px}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:720px}
th,td{border-bottom:1px solid var(--line);padding:4px 8px;text-align:left;
vertical-align:top}th{background:var(--hd);position:sticky;top:0}
td.t{font-weight:600}td.h{color:var(--mut);font-size:12px}
</style></head><body>
<h1>Jesus' life as events — first cut</h1>
<p>{{N}} events. Each row is one event with its tellings; a blank cell means
that gospel does not tell it. Titles and starting points are the BSB
editors' (a credited reading); ✂ marks a section split because its wording
aligns, in order, with two sections of another gospel. The last column says
what joined the tellings: the editors' parallel note, the wording (verses
aligned), or both. Row order keeps each gospel's own order and is not a
chronology.</p>
<div class=wrap><table><thead><tr><th>Event</th><th>Matthew</th><th>Mark</th>
<th>Luke</th><th>John</th><th>joined by</th></tr></thead><tbody>
{{ROWS}}
</tbody></table></div></body></html>"""


if __name__ == "__main__":
    main()
