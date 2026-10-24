"""The reader's theme tags are what the themes' own pages point to (2026-10-08).

With the Themes redefined and some added, the existing tags were no longer
trusted; the decision was to tag the verses from what the theme itself
references, taking the tables as the source and retiring from view DeepSeek's
September theme stamps. Then, since verses on the front pages of the themes
(the Core Concepts references, the verses highlighted as "in the text's own
words", the chapters singled out) would otherwise be left out, they were
included too. This checks:
  - every non-aside cell of a shown theme's table is tagged as its row, and
    no verse is tagged as a row that only an aside holds -- read from the
    table files, not from the server's index;
  - every passage of the front page (its quotations, core concepts, "also in
    this theme", chapters singled out), as the page itself serves it, is
    tagged for that theme -- and no verse is tagged that none of these holds;
  - a bracket opens the row, else the concept's card, else the theme;
  - no clause tag the reader shows is a retired theme stamp;
  - the page draws brackets and the verse panel from these.
After the graph loads (~1 minute). Run: python tests/test_theme_tags.py"""
import collections
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

d = S.load()
fails = []
ix = S._theme_tags()
maxv = collections.defaultdict(int)
for (b, c, v) in d["verses"]:
    maxv[(b, c)] = max(maxv[(b, c)], v)
got = collections.defaultdict(lambda: collections.defaultdict(set))   # theme -> kind -> verses
for key, xs in ix.items():
    for x in xs:
        got[x["theme"]][x["kind"]].add(key)
hubs = json.loads((ROOT / "ontology/themes/theme-hubs.json").read_text(encoding="utf-8"))


def verses_of(b, c1, v1, c2, v2):
    out = set()
    for c in range(c1, c2 + 1):
        for v in range(v1 if c == c1 else 1, (v2 if c == c2 else maxv[(b, c)]) + 1):
            if (b, c, v) in d["verses"]:
                out.add((b, c, v))
    return out


n_themes = 0
for t in S._theme_map()["themes"]:
    tid = t["id"]
    page = S.api_majortheme(d, {"id": [tid]})
    if not page.get("found"):
        continue
    n_themes += 1
    # the table, from its file
    want_row, aside = set(), set()
    h = hubs.get(tid) or {}
    tab = S._imagery(tid)
    for row in (tab or {}).get("rows") or []:
        for cells in row["cells"].values():
            for cell in cells:
                m = re.match(r"^(.+?) (\d+):(\d+)(?:[-–](\d+))?$", cell[0])
                nr = S._named_ref(cell[0]) if m else None
                if not nr:
                    fails.append(f"{tid}: a cell's reference does not read: {cell[0]!r}")
                    continue
                vs = verses_of(nr[0], nr[1], int(m.group(3)), nr[1], int(m.group(4) or m.group(3)))
                (aside if len(cell) > 2 and cell[2] == "aside" else want_row).update(vs)
    for x in sorted(want_row - got[tid]["row"])[:3]:
        fails.append(f"{tid}: {x} is in its table but not tagged as a row")
    for x in sorted(got[tid]["row"] - want_row)[:3]:
        fails.append(f"{tid}: {x} is tagged as a row but not in its table" + (" (an aside)" if x in aside else ""))
    # the front page, as it is served
    hub = page.get("hub") or {}
    want = {"quote": set(), "concept": set(), "also": set(), "chapter": set()}
    for o in hub.get("opening") or []:
        nr = S._named_ref(o["ref"] if isinstance(o, dict) else o[0])
        if nr and nr[2]:
            want["quote"].add(nr)
    for blk in [page] + ([page["synthesis"]] if page.get("synthesis") else []):
        for con in blk.get("concepts") or []:
            for p in con.get("passages") or []:
                for r in p.get("refs") or []:
                    if r.get("start"):
                        want["concept"] |= verses_of(r["book"], *r["start"], *(r.get("end") or r["start"]))
        for sec in blk.get("secondary") or []:
            for r in sec.get("refs") or []:
                if r.get("start"):
                    want["also"] |= verses_of(r["book"], *r["start"], *(r.get("end") or r["start"]))
    for ch in hub.get("visions") or []:
        want["chapter"] |= verses_of(ch["b"], ch["c"], 1, ch["c"], maxv[(ch["b"], ch["c"])])
    # the events on the page that its passages cite, every verse of each
    # telling (2026-10-08: "the full theme pages in their current states");
    # one joined only by Copilot's list or a retired stamp is not tagged
    want["event"] = set()
    evs = S._events(d)["events"]
    for x in page.get("events") or []:
        if not x.get("n_cited"):
            continue
        for tl in (evs.get(x["id"]) or {}).get("tellings") or []:
            fb, fc, fv = S.bsb_ref(d, tl["first"]).split(".")
            _lb, lc, lv = S.bsb_ref(d, tl["last"]).split(".")
            want["event"] |= verses_of(S.MACULA_BACK.get(fb, fb), int(fc), int(fv), int(lc), int(lv))
    # "Panel only" (decided 2026-10-08): an event is named only on a verse the
    # theme tags by its own pages, so it never adds a verse or a bracket
    own = set().union(*(vs for k, vs in got[tid].items() if k != "event"))
    want["event"] &= own
    if got[tid]["event"] - own:
        fails.append(f"{tid}: an event tags a verse the theme's own pages do not")
    checked = page.get("source") == "site" or page.get("outline") == "redone"
    for k, vs in want.items():
        if k not in S.THEME_TAG_KINDS and k != "event" and not (checked and k in ("concept", "also")):
            # an outline not yet through the readers waits (7.6c)
            if got[tid][k]:
                fails.append(f"{tid}: tagged as {k}, which is not switched on")
            continue
        for x in sorted(vs - got[tid][k])[:3]:
            fails.append(f"{tid}: {x} is on its front page ({k}) but not tagged")
        for x in sorted(got[tid][k] - vs)[:3]:
            fails.append(f"{tid}: {x} is tagged as {k} but its front page does not hold it")
    if not any(got[tid].values()):
        fails.append(f"{tid}: tags no verse")
# a chapter's brackets: a row opens the table, else a concept its card
for b, c in (("Isa", 53), ("Eph", 6), ("Ps", 23), ("Gen", 1), ("Ps", 2)):
    for s in S.theme_spans(b, c, list(range(1, 200))):
        if s["row"] is not None and not s["rows"]:
            fails.append(f"{b} {c}:{s['from']}: a bracket with a row and no row title")
# the retired theme stamps reach no clause
retired = S._theme_stamp_ids()
if len(retired) < 20:
    fails.append(f"only {len(retired)} theme stamp ids found in the taxonomy")
bad = sum(1 for ts in S._clause_tags().values() for t in ts if t["kind"] == "stamp" and t["tag"] in retired)
if bad:
    fails.append(f"{bad} clause tags are retired theme stamps")
# the page
page_html = (ROOT / "app2/static/index.html").read_text(encoding="utf-8")
if 's.concepts.join' in page_html or "x.concept)}</span>`).join(' · ')" in page_html:
    fails.append("index.html: the reader still names the outline's concepts the old way")
if 'const brAttr = s => s.row != null ? `data-imagery="${esc(s.theme)}" data-row="${s.row}"`' not in page_html:
    fails.append("index.html: a bracket does not open the table at its row")
if ': s.node ? `data-ent="${esc(s.node)}"`' not in page_html:
    fails.append("index.html: a concept's bracket does not open the concept's card")
if "if(d.theme){ openMajorTheme(d.theme); return; }" not in page_html:
    fails.append("index.html: a retired theme tag does not open its theme")
kinds = collections.Counter(x["kind"] for xs in ix.values() for x in xs)
print(f"{n_themes} themes, {len(ix)} verses tagged from their own pages "
      f"({', '.join(f'{k} {n}' for k, n in kinds.most_common())}), {len(fails)} failures")
for f in fails[:12]:
    print("FAIL", f)
sys.exit(1 if fails else 0)
