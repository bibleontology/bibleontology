"""Microsoft Copilot's event lists, parsed and checked against the text.

2026-09-29, five lists pasted in: to be merged into what exists, with a better
job of cross references; and of what existed, the event section was completely
tag based, and disappointing when one actually reached the events, as they were
not really nodes. Source: ontology/events/copilot-events.md, Copilot's text verbatim.

The five lists, each parsed to one shape:

- **canonical** (events 1-150): title, themes, primary narrative, secondary
  references with Copilot's bracketed note on each.
- **gospel** (151-205): a table, one column per Gospel. Rows 169, 170, 203,
  204 are Copilot's own placeholders ("already mapped as ...") and are
  dropped (decision card, 2026-09-29).
- **ot_parallel** (its own 1-49): Samuel / Kings / Chronicles / other
  columns. Numbered in its own series, so its ids are `ot1`..`ot49`, never
  the canonical 1-49 they would collide with.
- **ot_clusters**: prose clusters, kept as text only (they are not events).
- **additional**: ~110 events by book, title and reference(s).

Every reference is resolved against the Berean text (tools/themes/theme_map
spans_in / check). A reference that names a chapter or verse the Berean does
not have is reported, never dropped silently.

HELD, not events (decision card): the letters (146-148), the summary
rows (174, 205, "Many unrecorded signs in John") and the genealogies. They
are parsed and marked `held` with the reason.

    python tools/events/copilot_events.py   -> out/copilot-events.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "ontology" / "events" / "copilot-events.md"
OUT = ROOT / "out" / "copilot-events.json"
sys.path.insert(0, str(ROOT / "tools" / "themes"))
from theme_map import BOOKS, check, label, spans_in  # noqa: E402

DROP = {"gospel": {169, 170, 203, 204}}
HELD = {("canonical", 146): "a set of letters, not an event",
        ("canonical", 147): "a set of letters, not an event",
        ("canonical", 148): "a set of letters, not an event",
        ("gospel", 174): "a summary of many healings, not one event",
        ("gospel", 205): "a summary of unrecorded signs, not one event"}
HELD_TITLE = {"many unrecorded signs in john": "a summary of unrecorded signs, not one event",
              "genealogies of adam → noah": "a genealogy, not an event",
              "jesus’ genealogy (matthew & luke)": "a genealogy, not an event"}
GOSPEL_COLS = ["Matthew", "Mark", "Luke", "John"]
OT_COLS = ["Samuel", "Kings", "Chronicles", "Other"]
STOP_SEC = re.compile(r"^(Notes:|If you say|EVENT SET|Event \d+ —|You now have|You’ve reached|"
                      r"Here is Event)")


def span_rec(s):
    code, a, b = s
    rec = {"book": code, "label": label(s)}
    if a is not None:
        rec.update(start=list(a), end=list(b))
    return rec


def refs(text, problems, where, book=None):
    """a line of references -> [span records]; `book` prefixes a table cell"""
    t = text.strip()
    if not t or t in ("—", "-"):
        return []
    if book:
        t = f"{book} {t}"
    # a one-chapter book is cited by verse: "Jude 11" is Jude 1:11
    t = re.sub(r"\b(Jude|Obadiah|Philemon|2 John|3 John) (\d+)(?![:\d])", r"\1 1:\2", t)
    out = []
    for s in spans_in(t, problems):
        if check(s, problems, where):
            out.append(span_rec(s))
    if not out:
        problems.append(f"{where}: no reference read from '{text.strip()}'")
    return out


def note_of(line):
    m = re.search(r"\((.*)\)\s*$", line.strip())
    return m.group(1).strip() if m else None


def parse_canonical(text, problems):
    out = []
    blocks = re.split(r"\n(?=Event \d+ — )", text)
    for blk in blocks:
        m = re.match(r"Event (\d+) — (.+)", blk)
        if not m:
            continue
        n, title = int(m.group(1)), m.group(2).strip()
        lines = [ln.strip() for ln in blk.split("\n")[1:]]
        ev = {"list": "canonical", "n": n, "id": f"c{n}", "title": title, "themes": [],
              "primary": [], "secondary": []}
        mode = None
        for i, ln in enumerate(lines):
            if not ln:
                continue
            if STOP_SEC.match(ln):
                if ln.startswith("Notes:"):
                    mode = "notes"
                    continue
                break
            if ln.startswith("Themes:"):
                rest = ln[len("Themes:"):].strip()
                if not rest:
                    rest = next((x for x in lines[i + 1:] if x), "")
                ev["themes"] = [t.strip() for t in rest.split(";") if t.strip()]
                mode = "themes"
                continue
            if ln.startswith("Primary narrative"):
                mode = "primary"
                continue
            if ln.startswith("Secondary references"):
                mode = "secondary"
                continue
            if mode == "primary":
                got = refs(re.sub(r"\(.*?\)", "", ln), problems, f"event {n} primary")
                for r in got:
                    r["note"] = note_of(ln)
                ev["primary"] += got
            elif mode == "secondary":
                for r in refs(re.sub(r"\(.*?\)", "", ln), problems, f"event {n} secondary"):
                    r["note"] = note_of(ln)
                    r["line"] = ln
                    ev["secondary"].append(r)
            elif mode == "notes":
                ev["notes"] = (ev.get("notes", "") + " " + ln).strip()
        out.append(ev)
    return out


def table_rows(text, header_re):
    i = text.find(header_re)
    rows = []
    for ln in text[i:].split("\n")[1:]:
        if not ln.strip():
            continue
        cells = ln.split("\t")
        if not re.match(r"^\d+$", cells[0].strip()):
            if rows:
                break
            continue
        rows.append([c.strip() for c in cells])
    return rows


def parse_gospel(text, problems):
    out = []
    for cells in table_rows(text, "Event index 151+"):
        n = int(cells[0])
        if n in DROP["gospel"]:
            continue
        ev = {"list": "gospel", "n": n, "id": f"g{n}", "title": cells[1], "themes": [],
              "primary": [], "secondary": []}
        for col, cell in zip(GOSPEL_COLS, cells[2:6]):
            for r in refs(re.sub(r"\(.*?\)", "", cell), problems, f"gospel {n} {col}", col):
                r["note"] = note_of(cell)
                ev["primary"].append(r)
        out.append(ev)
    return out


def parse_ot(text, problems):
    out = []
    for cells in table_rows(text, "OT parallel event index"):
        n = int(cells[0])
        ev = {"list": "ot_parallel", "n": n, "id": f"ot{n}", "title": cells[1], "themes": [],
              "primary": [], "secondary": [], "columns": {}}
        for col, cell in zip(OT_COLS, cells[2:6]):
            ev["columns"][col] = cell
            got = refs(re.sub(r"\((?:context|oracles|prophetic backdrop)\)", "", cell),
                       problems, f"OT table {n} {col}")
            for r in got:
                r["column"] = col
                r["note"] = note_of(cell)
                # a Kings column holding 1 Chr 10, a Samuel column holding
                # 1 Kgs 1-2: Copilot's slips, reported (the reference itself
                # is still a real passage)
                want = {"Samuel": ("1Sam", "2Sam"), "Kings": ("1Kgs", "2Kgs"),
                        "Chronicles": ("1Chr", "2Chr")}.get(col)
                if want and r["book"] not in want:
                    problems.append(f"OT table {n} ({cells[1]}): {r['label']} is under "
                                    f"{col}")
                    r["misfiled"] = True
            ev["primary"] += got
        # the same passage in two columns is one telling
        seen, uniq = set(), []
        for r in ev["primary"]:
            k = (r["book"], tuple(r.get("start") or ()), tuple(r.get("end") or ()))
            if k not in seen:
                seen.add(k)
                uniq.append(r)
        ev["primary"] = uniq
        out.append(ev)
    return out


def parse_additional(text, problems):
    i = text.find("ADDITIONAL SIGNIFICANT BIBLICAL EVENTS")
    out, section, title = [], None, None
    for ln in text[i:].split("\n")[1:]:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("* "):
            if title is None:
                continue
            got = refs(s[2:], problems, f"additional '{title}'")
            out[-1]["primary"] += got
            continue
        head = re.sub(r"\s*\(.*\)", "", s).strip()
        if head.upper() == head and re.search(r"[A-Z]{3}", head):
            section = head        # "GENESIS (not previously listed)"
            continue
        title = s
        out.append({"list": "additional", "n": len(out) + 1, "id": f"a{len(out) + 1}",
                    "title": s, "section": section, "themes": [], "primary": [],
                    "secondary": []})
    return out


def main():
    text = SRC.read_text(encoding="utf-8")
    problems = []
    cut = text.find("now for events 150+")
    events = (parse_canonical(text[:cut], problems) + parse_gospel(text, problems)
              + parse_ot(text, problems) + parse_additional(text, problems))
    for ev in events:
        why = HELD.get((ev["list"], ev["n"])) or HELD_TITLE.get(ev["title"].lower())
        if why:
            ev["held"] = why
        elif not ev["primary"]:
            ev["held"] = "no primary passage given"
    OUT.write_text(json.dumps({"_source": "Microsoft Copilot, five event lists harvested by "
                               "Doug Egge 2026-09-29 (ontology/events/copilot-events.md)",
                               "events": events, "problems": problems},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    by = {}
    for ev in events:
        by.setdefault(ev["list"], []).append(ev)
    for k, v in by.items():
        print(f"{k}: {len(v)} ({sum(1 for e in v if e.get('held'))} held), "
              f"{sum(len(e['primary']) for e in v)} primary, "
              f"{sum(len(e['secondary']) for e in v)} secondary")
    print(f"problems: {len(problems)}")
    for p in problems:
        print("  ", p)


if __name__ == "__main__":
    main()
