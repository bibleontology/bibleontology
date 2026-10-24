"""The rest of each theme's page, measured (plan 7.6c proposal, 2026-10-08).

The request: check the integrity of the front pages (Event relationships,
secondary concepts, and the rest) rather than treat them as an afterthought if
they are solid material; if the core concepts are leftovers from Copilot and
not what the text is saying, rename them. This is the machine pass that comes first: for every shown
theme, every section below the front page as the page serves it
(api_majortheme), with what fails mechanically. Nothing is changed.

    python tools/themes/frontpage_audit.py      -> out/frontpage-audit.json
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

# the site's own voice must not say these (tests/test_readings_text.py VOICE)
VOICE = re.compile(r"\b(fulfil\w*|fulfill\w*|foreshadow\w*|predict\w*|prefigur\w*|antitype\w*|"
                   r"rapture|millenni\w*|tribulation|dispensation\w*|end times|antichrist|type of|"
                   r"typolog\w*|christolog\w*)\b", re.I)
WIDE = 20


def flat(s):
    return re.sub(r"\s+", " ", re.sub(r"[‘’]", "'", re.sub(r"[“”]", '"', s or ""))).strip().lower()


def span(d, r):
    (c1, v1), (c2, v2) = r["start"], r.get("end") or r["start"]
    n = 0
    for c in range(c1, c2 + 1):
        top = max((v for (b, cc, v) in d["_vix"].get((r["book"], c), [])), default=0)
        n += (v2 if c == c2 else top) - (v1 if c == c1 else 1) + 1
    return n


def main():
    d = S.load()
    vix = collections.defaultdict(list)
    for k in d["verses"]:
        vix[(k[0], k[1])].append(k)
    d["_vix"] = vix
    text = lambda r: " ".join(d["verses"].get((r["book"], c, v), "")  # noqa: E731
                              for c in range(r["start"][0], (r.get("end") or r["start"])[0] + 1)
                              for v in range(1, 200) if (r["book"], c, v) in d["verses"]
                              and (r["start"][0], r["start"][1]) <= (c, v) <= tuple(r.get("end") or r["start"]))
    out, totals = [], collections.Counter()
    for t in S._theme_map()["themes"]:
        page = S.api_majortheme(d, {"id": [t["id"]]})
        if not page.get("found"):
            continue
        th = {"id": t["id"], "title": S._title(t["title"]), "source": page.get("source"), "sections": {}}
        for part, blk in [("outline", page)] + ([("synthesis", page["synthesis"])] if page.get("synthesis") else []):
            cons = []
            for con in blk.get("concepts") or []:
                refs = [r for p in con.get("passages") or [] for r in p.get("refs") or [] if r.get("start")]
                notes = [p["note"] for p in con.get("passages") or [] if p.get("note")]
                flags = []
                if VOICE.search(con.get("name") or ""):
                    flags.append("site-voice word in the name")
                wide = [r["label"] for r in refs if span(d, r) >= WIDE]
                if wide:
                    flags.append(f"{len(wide)} references of {WIDE}+ verses: {', '.join(wide[:3])}")
                bad_notes = []
                for p in con.get("passages") or []:
                    if p.get("note"):
                        q = re.sub(r"^[\"“']|[\"”']$", "", p["note"].strip())
                        body = " ".join(text(r) for r in p.get("refs") or [] if r.get("start"))
                        if flat(q) and flat(q).strip(" .,;:") not in flat(body):
                            bad_notes.append(p["note"])
                if bad_notes:
                    flags.append(f"{len(bad_notes)} notes not found in their verses")
                cons.append({"n": con["n"], "name": con["name"], "refs": len(refs), "notes": len(notes),
                             "flags": flags, "node": con.get("node")})
                totals["concepts"] += 1
                totals["flagged concepts"] += bool(flags)
            secs = []
            for sec in blk.get("secondary") or []:
                refs = [r for r in sec.get("refs") or [] if r.get("start")]
                flags = []
                if VOICE.search(sec.get("name") or ""):
                    flags.append("site-voice word in the name")
                wide = [r["label"] for r in refs if span(d, r) >= WIDE]
                if wide:
                    flags.append(f"{len(wide)} references of {WIDE}+ verses: {', '.join(wide[:3])}")
                if not refs:
                    flags.append("no reference")
                secs.append({"name": sec["name"], "refs": len(refs), "flags": flags})
                totals["secondary"] += 1
                totals["flagged secondary"] += bool(flags)
            th["sections"][part] = {"concepts": cons, "secondary": secs}
        if page.get("synthesis"):
            a = {flat(c["name"]) for c in page.get("concepts") or []}
            b = {flat(c["name"]) for c in page["synthesis"].get("concepts") or []}
            th["outline_synthesis_same_names"] = sorted(a & b)
        th["events"] = len(page.get("events") or [])
        th["links"] = len(page.get("links") or [])
        th["messages"] = len(page.get("messages") or [])
        th["acts"] = len(page.get("acts") or [])
        th["go_deeper"] = [s.get("id") for s in page.get("stamps") or []]
        for k in ("events", "links", "messages", "acts"):
            totals[k] += th[k]
        out.append(th)
    res = {"themes": out, "totals": dict(totals)}
    (ROOT / "out" / "frontpage-audit.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(dict(totals)))
    for th in out:
        o = th["sections"]["outline"]
        fl = sum(1 for c in o["concepts"] if c["flags"])
        print(f"{th['id']:20} {th['source'] or 'copilot':8} concepts {len(o['concepts']):3} flagged {fl:3}"
              f" | secondary {len(o['secondary']):3} | synthesis {'yes' if 'synthesis' in th['sections'] else '-':3}"
              f" | events {th['events']:3} links {th['links']:3} msgs {th['messages']:3} acts {th['acts']:3}")


if __name__ == "__main__":
    main()
