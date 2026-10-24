"""Role patterns as nodes (plan A.10).

2026-09-30: P-61 approved, with the recommendations on
folding in patterns. A role pattern is a ROLE FRAME -- a role and what it
stands in relation to (shepherd: sheep, pasture, protection, provision) --
so its columns are SLOTS, not steps: Saul's "law" is a violation and Josiah
dies after his. A row per figure, a cell per slot, each cell a verse range.

Built from tools/themes/role_patterns.py's graded citations
(out/role-patterns.json), with its corrections applied: Copilot's list is the
draft and the evidence overrides it (Copilot is the draft; the
evidence overrides it, decided 2026-09-30).

  Enemy          folded into Story pattern: Cry and rescue
                 (tools/events/template_nodes.py), not built here
  Servant        its own pattern, a narrower form of Brought low, raised up
  Prophet        its own pattern, a narrower form of Sin, judgment and mercy
  Warfare        its own pattern, SUBMISSION first (Jas 4:6-10; 1 Pet 5:5-10)

Graph shape (no new relation types):
  pattern   type pattern   rolepat_<id>     "Role pattern: Shepherd"
  row       type passage   rrow_<id>_<row>  "David (Role pattern: Shepherd)"
            -instance_of-> the pattern; its figure in attrs, linked live
  cell      type passage   rcell_<id>_<row>_<slot>, -part_of-> the row
  pattern  -specializes-> story pattern      (Servant, Prophet)
A cell whose verses carry the slot's own word is `implied`; one resting on
reading is `conjectured` and shows as a reading. A citation over 40 verses is
not a cell (it is listed in the report to be narrowed).

    python tools/themes/role_nodes.py
      -> ontology/entities/role-patterns.jsonl
         ontology/relations/role-patterns.jsonl
         out/role-pattern-view.json
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "themes"))
sys.path.insert(0, str(ROOT / "tools" / "events"))
from theme_map import check, spans_in  # noqa: E402
from event_nodes import label_of, verses, vkey  # noqa: E402
import role_patterns as RP  # noqa: E402

ENT = ROOT / "ontology" / "entities" / "role-patterns.jsonl"
REL = ROOT / "ontology" / "relations" / "role-patterns.jsonl"
VIEW = OUT / "role-pattern-view.json"
SOURCE = "role-patterns"

BUILD = ["shepherd", "king", "priest", "bridegroom", "father", "servant", "prophet", "warfare"]
NOTE = {
    "shepherd": "A shepherd, the flock, its pasture, its protection and its provision.",
    "king": "A king, his kingdom, the law, judgment, and peace.",
    "priest": "A priest, sacrifice, cleansing, access, and presence.",
    "bridegroom": "A bridegroom, the bride, the covenant, faithfulness, and the wedding.",
    "father": "A father, a son, the inheritance, obedience, and blessing.",
    "servant": "A servant, suffering, vindication, and glory — a narrower form of the story "
               "pattern Brought low, raised up.",
    "prophet": "A prophet, the word, confrontation, repentance, and restoration — a narrower "
               "form of the story pattern Sin, judgment and mercy.",
    "warfare": "Submission to God, the powers, opposition, resistance, God's help, and "
               "standing. Submission comes first in the text (James 4:6–10; 1 Peter 5:5–10).",
}
SPECIALIZES = {"servant": "tpl_descent_return", "prophet": "tpl_judgment_mercy"}
SEQUENCES = {"servant", "prophet", "warfare"}      # the others are frames
ADDED_SLOTS = {("warfare", "Submission")}

# ---- which row a citation belongs to: first match wins, per pattern, over
# the figure (vertical) or the grouping and claim (horizontal)
ROWS = {
    "shepherd": [("prodigal|luke 15", "The lost sheep (Luke 15)"),
                 ("patriarch|jacob", "Jacob and the patriarchs"), ("moses|wilderness", "Moses"),
                 ("david", "David"), ("prophetic shepherd|scattered", "The shepherds the prophets condemn"),
                 ("ezekiel’s provision|god|lord|yhwh|israel", "The LORD"),
                 ("jesus|messiah|messianic|disciples|wolves", "Jesus"),
                 ("apostol|elders", "The apostles and elders"), ("new creation", "New creation")],
    "king": [("saul", "Saul"), ("solomon", "Solomon"), ("hezekiah", "Hezekiah"),
             ("josiah", "Josiah"), ("david", "David"),
             ("jesus|messiah|messianic|christ|son of man", "Jesus"),
             ("apostolic", "The apostles' preaching"), ("new creation", "New creation"),
             ("god|lord|yhwh|judge-king", "The LORD")],
    "priest": [("melchizedek", "Melchizedek"), ("david", "David"),
               ("jesus|christ", "Jesus"), ("believer|church|spirit", "The church"),
               ("new creation", "New creation"),
               ("patriarch|adam|noah|abraham|jacob", "The patriarchs"),
               ("aaron|levitical|high priest|tabernacle|temple|veil|passover|priestly|water",
                "Aaron and the priests")],
    "bridegroom": [("hosea|gomer", "Hosea and Gomer"),
                   ("lamb|new jerusalem|eternal|nt consummation|eschatological", "The Lamb and the bride"),
                   ("apostolic", "The apostles' church"),
                   ("jesus|christ|church|new covenant", "Jesus and the church"),
                   ("yhwh|god|israel|sinai|marriage|ot anticipation|bride’s", "The LORD and Israel")],
    "father": [("prodigal", "The prodigal son (Luke 15)"),
               ("david|king", "David and his sons"), ("jesus", "Jesus"),
               ("believer", "Believers"), ("new creation", "New creation"), ("israel", "Israel"),
               ("patriarch|abraham|isaac|jacob|human fathers", "The patriarchs")],
    "servant": [("john 13", "Jesus washing feet (John 13)"), ("isaiah", "The servant in Isaiah"),
                ("joseph", "Joseph"), ("moses", "Moses"), ("david", "David"),
                ("jesus|christ", "Jesus"), ("apostl|paul", "The apostles"),
                ("church|believer", "The church"), ("new creation", "New creation")],
    "prophet": [("huldah", "Huldah"), ("jonah|nineveh", "Jonah"),
                ("john the baptist", "John the Baptist"), ("samuel", "Samuel"),
                ("elijah", "Elijah"), ("elisha", "Elisha"), ("isaiah", "Isaiah"),
                ("jeremiah", "Jeremiah"), ("ezekiel", "Ezekiel"), ("moses", "Moses"),
                ("peter|apostl", "The apostles"), ("final prophetic|revelation", "Revelation"),
                ("jesus|messiah|christ", "Jesus")],
}
# warfare rows go by where the verses are
WARFARE = [("Jas.", "James 4:6–10"), ("1Pet.", "1 Peter 5:5–10"), ("Eph.", "Ephesians 6:10–18"),
           ("Matt.4.", "Jesus tempted (Matt 4:1–11)")]
# rows that are one person, for the live link to the person's card
PERSON = {"David": ["david"], "Moses": ["moses"], "Saul": ["saul"], "Solomon": ["solomon"],
          "Hezekiah": ["hezekiah"], "Josiah": ["josiah"], "Jesus": ["jesus"],
          "Melchizedek": ["melchizedek"], "Joseph": ["joseph"], "Samuel": ["samuel"],
          "Elijah": ["elijah"], "Elisha": ["elisha"], "Isaiah": ["isaiah"],
          "Jeremiah": ["jeremiah"], "Ezekiel": ["ezekiel"], "John the Baptist": ["john_the_baptist"],
          "Hosea and Gomer": ["hosea"], "The LORD": ["god"], "Jacob and the patriarchs": ["jacob"],
          "The patriarchs": ["abraham", "isaac", "jacob"], "Aaron and the priests": ["aaron"],
          "The LORD and Israel": ["god"], "Jesus and the church": ["jesus"],
          "David and his sons": ["david"], "Jesus washing feet (John 13)": ["jesus"],
          "Jesus tempted (Matt 4:1–11)": ["jesus"], "The Lamb and the bride": ["jesus"],
          "Jonah": ["jonah"], "Huldah": ["huldah"]}

# ---- corrections that add or remove a cell (the rest are in role_patterns'
# OVERRIDES and READINGS). (pattern, row, slot, reference, note)
EXTRA = [
    ("shepherd", "The lost sheep (Luke 15)", "Shepherd", "Luke 15:4",
     "“What man among you, if he has a hundred sheep and loses one of them …”"),
    ("shepherd", "The lost sheep (Luke 15)", "Sheep", "Luke 15:4–6", "the lost sheep, found"),
    ("shepherd", "The lost sheep (Luke 15)", "Pasture", "Luke 15:4", "the ninety-nine left in the pasture"),
    ("shepherd", "The lost sheep (Luke 15)", "Protection", "Luke 15:5",
     "he joyfully puts it on his shoulders"),
    ("shepherd", "Moses", "Shepherd", "Psalm 77:20",
     "“You led Your people like a flock by the hand of Moses and Aaron”"),
    ("shepherd", "Moses", "Shepherd", "Isaiah 63:11",
     "“the days of Moses … the shepherds of His flock”"),
    ("servant", "Joseph", "Servant", "Psalm 105:17", "“Joseph, sold as a slave”"),
    ("servant", "Moses", "Glory", "2 Corinthians 3:7", "“the glory of his face”"),
    ("priest", "Jesus", "Priest", "Psalm 110:4; Hebrews 5:6",
     "“You are a priest forever in the order of Melchizedek”, said to “my Lord” (110:1), "
     "and given to Jesus by Hebrews"),
    ("priest", "Melchizedek", "Priest", "Psalm 110:4", "“in the order of Melchizedek”"),
    ("shepherd", "The LORD", "Shepherd", "Genesis 48:15",
     "Jacob: “the God who has been my shepherd all my life to this day”"),
    # the role in the text's own words, where the draft's verse did not say it
    ("prophet", "Elijah", "Prophet", "1 Kings 18:36", "“Elijah the prophet approached the altar”"),
    ("prophet", "Isaiah", "Prophet", "2 Kings 19:2", "“the prophet Isaiah son of Amoz”"),
    ("prophet", "Huldah", "Prophet", "2 Kings 22:14", "“Huldah the prophetess”"),
    ("prophet", "Jonah", "Prophet", "2 Kings 14:25", "“His servant Jonah son of Amittai, the prophet”"),
    ("prophet", "Revelation", "Prophet", "Revelation 22:9",
     "“a fellow servant with you and your brothers the prophets”"),
    ("priest", "New creation", "Priest", "Revelation 20:6",
     "“they will be priests of God and of Christ”"),
    ("priest", "The church", "Priest", "Revelation 1:6", "“a kingdom, priests to His God and Father”"),
    ("bridegroom", "Hosea and Gomer", "Bridegroom", "Hosea 3:1",
     "“Love her as the LORD loves the Israelites” — the text makes the likeness itself"),
    # Psalm 2 does not name Jesus; Acts and Hebrews give it to him, so the cell
    # cites them (approved, 2026-10-02 evaluation). Same shape as the
    # priest row's Psalm 110:4 above.
    ("king", "Jesus", "King", "Psalm 2:6–7; Acts 13:33; Hebrews 1:5",
     "“I have installed My King on Zion … You are My Son” (Ps 2:6–7), given to Jesus "
     "by Acts 13:33 and Hebrews 1:5"),
]
# (pattern, row, reference) the evidence moves out
DROP = [("priest", "David", "Psalm 110:4"),
        # replaced by the cited cell above
        ("king", "Jesus", "Psalm 2:6–9"),
        # routed into Jesus's row by the word "Christ": Paul calling himself
        # a servant, and the apostles flogged (2026-10-02 evaluation)
        ("servant", "Jesus", "Romans 1:1"),
        ("servant", "Jesus", "Acts 5:40–41")]


# A QUOTE IN THE TEXT'S WORDS. Copilot's role-pattern notes quote verses in
# their own or the KJV's wording ("Purge me ... and I shall be clean", Ps
# 51:7). A.22 (P-90, 2026-10-02): a quoted span found in neither the Berean
# nor the WEB for the cell's verses becomes the run of Berean clauses that
# shares the most words with it -- when it shares at least half of them;
# otherwise it is left and listed (the build prints how many).
_BSB = None
_STOP = {"the", "and", "of", "to", "a", "in", "is", "his", "he", "i", "my", "for", "that",
         "you", "your", "it", "be", "will", "shall", "with", "on", "as", "who", "me", "them"}


def _bsb():
    global _BSB
    if _BSB is None:
        _BSB = {}
        for f, name in ((ROOT / "data" / "bible" / "verses.bsb.jsonl", "bsb"),
                        (ROOT / "data" / "bible" / "verses.web.jsonl", "web")):
            for line in f.open(encoding="utf-8"):
                d = json.loads(line)
                if "b" in d:
                    _BSB[(name, f"{d['b']}.{d['c']}.{d['v']}")] = d["t"]
    return _BSB


def _words(s):
    return re.findall(r"[a-z']+", s.lower().replace("’", "'"))


REQUOTED = collections.Counter()


def berean_quote(note, vs):
    def fix(m):
        q = m.group(1)
        texts = {n: " ".join(_bsb().get((n, v), "") for v in vs) for n in ("bsb", "web")}
        parts = [p for p in re.split(r"\s*(?:…|\.\.\.)\s*", q) if p.strip()]
        if any(all(" ".join(_words(p)) in " ".join(_words(texts[n])) for p in parts)
               for n in ("bsb", "web")):
            REQUOTED["kept"] += 1
            return m.group(0)
        want = {w for w in _words(q) if w not in _STOP}
        # a clause ends at punctuation, or at punctuation and a closing quote
        # mark (Rev 19:8 'bright and pure.” For the fine linen ...')
        clauses = [c.strip() for c in re.split(r"(?<=[,;:.?!])\s+|(?<=[,;:.?!][”’])\s+", texts["bsb"])
                   if c.strip()]
        best = (0.0, None)
        for i in range(len(clauses)):
            for j in range(i, min(i + 3, len(clauses))):
                run = " ".join(clauses[i:j + 1])
                have = {w for w in _words(run) if w not in _STOP}
                score = len(want & have) / len(want) if want else 0
                if score > best[0] + 1e-9 or (abs(score - best[0]) < 1e-9 and best[1] and len(run) < len(best[1])):
                    best = (score, run)
        if best[1] and best[0] >= 0.5:
            REQUOTED["requoted"] += 1
            return "“" + re.sub(r"[“”\"]", "", best[1]).strip(" ,;:‘’") + "”"
        REQUOTED["left"] += 1
        return m.group(0)
    return re.sub(r"“([^”]{3,})”", fix, note) if body_ok(note) else note


def body_ok(note):
    return "“" in note


def slug(t):
    t = re.sub(r"\(.*?\)", "", t.lower().replace("’", "").replace("'", ""))
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")[:40]


def row_of(pid, r):
    if pid == "warfare":
        if r["mode"] == "reading":
            return r["figure"]
        vs = r.get("verses") or []
        for pre, name in WARFARE:
            if vs and vs[0].startswith(pre):
                return name
        return "Other examples"
    if r["mode"] in ("vertical", "reading") and r["figure"]:
        text = r["figure"].lower()
    else:
        text = f"{r.get('group') or ''} {r['claim']}".lower()
    for keys, name in ROWS[pid]:
        if re.search(keys, text):
            return name
    return "Other examples"


def resolve(ref):
    probs = []
    sp = [s for s in spans_in(ref, probs) if s[1] is not None and check(s, probs, ref)]
    if probs or not sp:
        raise SystemExit(f"{ref}: {probs or 'no span'}")
    vs = []
    for c, a, b in sp:
        vs += verses({"book": c, "start": list(a), "end": list(b)})
    return vs


def label(vs):
    runs = []
    for b in dict.fromkeys(v.split(".")[0] for v in vs):
        runs.append(label_of(sorted([v for v in vs if v.split(".")[0] == b], key=vkey)))
    return "; ".join(runs)


def store(v):
    b, c, n = v.split(".")
    return f"{b} {c}:{n}"


def main():
    data = json.loads((OUT / "role-patterns.json").read_text(encoding="utf-8"))
    hand = {(p, f) for p, f, *_ in RP.READINGS}
    drop = {(p, r, ref) for p, r, ref in DROP}
    cells = collections.defaultdict(list)       # (pid, row, slot) -> [cell]
    held = []
    for r in data["rows"]:
        pid = r["pattern"]
        if pid not in BUILD:
            continue
        # The three added patterns are read by hand; Copilot's cells for them go
        if r["mode"] != "reading" and (pid, r["figure"]) in hand:
            continue
        if r["grade"] in ("broad", "unresolved"):
            held.append((pid, r["figure"] or r.get("group"), r["movement"], r["ref"], r["grade"]))
            continue
        row = row_of(pid, r)
        if (pid, row, r["ref"]) in drop:
            continue
        cells[(pid, row, r["movement"])].append(
            {"verses": r["verses"], "grade": r["grade"], "note": r["claim"],
             "hand": r["mode"] == "reading",
             "reading": r["grade"] not in ("word",)})
    for pid, row, slot, ref, note in EXTRA:
        cells[(pid, row, slot)].append({"verses": resolve(ref), "grade": "word",
                                        "note": note, "reading": False, "added": True})

    nodes, rels, view = [], [], {"patterns": {}, "by_node": {}, "by_figure": collections.defaultdict(list)}
    for pid in BUILD:
        _p, role, slots, _w, _rk = RP.PAT[pid]
        pat_id = "rolepat_" + pid
        prow = collections.OrderedDict()
        for (p, row, slot), cs in cells.items():
            if p == pid:
                prow.setdefault(row, {})[slot] = cs
        order = [n for _k, n in ROWS.get(pid, [])] + [n for _k, n in WARFARE] + ["Other examples"]
        rows_out, pat_refs = [], []
        for row in sorted(prow, key=lambda n: order.index(n) if n in order else 99):
            rid = f"rrow_{pid}_{slug(row)}"
            row_cells, row_refs = {}, []
            for si, slot in enumerate(slots):
                seen = set()
                out = []
                for c in prow[row].get(slot, []):
                    vs = sorted(set(c["verses"]), key=vkey)
                    key = tuple(vs)
                    if not vs or key in seen:
                        continue
                    seen.add(key)
                    cid = f"rcell_{pid}_{slug(row)}_{slug(slot)}_{len(out) + 1}"
                    lab = label(vs)
                    # NOT THE DRAFT'S VOICE. 2026-09-30, the question being whether the site still
                    # avoids being opinionated as this structure is built. The cell said the draft's own sentence
                    # ("Jesus fulfills and surpasses all previous shepherds")
                    # as its description, on 553 cards. A description says
                    # where the cell is; only words quoted from the text
                    # (hand readings, corrections) are added to it.
                    quoted = c.get("added") or c.get("hand") or c["note"].startswith("“")
                    nodes.append({"attrs": {"kind": "role_cell", "pattern": pid, "slot": slot},
                                  "desc": (f"{slot} — in {row}, a row of the role pattern "
                                           f"“{role}”: {lab}."
                                           + (f" {berean_quote(c['note'], vs)}" if quoted else ""))[:600],
                                  "gender": "unknown", "id": cid,
                                  "name": f"{slot} (Role pattern: {role}): {row} — {lab}",
                                  "refs": [store(vs[0])] + ([store(vs[-1])] if len(vs) > 1 else []),
                                  "source": SOURCE, "type": "passage"})
                    rels.append({"certainty": "conjectured" if c["reading"] else "implied",
                                 "dst": rid, "note": f"the {slot.lower()} of {row}, in “{role}”",
                                 "refs": [store(vs[0])], "source": SOURCE, "src": cid,
                                 "type": "part_of"})
                    # contiguous runs, for the reader's chips (as a story
                    # stage carries them)
                    runs, cur = [], []
                    for v in vs:
                        if cur and v.split(".")[:2] == cur[-1].split(".")[:2] and \
                                int(v.split(".")[2]) == int(cur[-1].split(".")[2]) + 1:
                            cur.append(v)
                        else:
                            if cur:
                                runs.append([cur[0], cur[-1]])
                            cur = [v]
                    if cur:
                        runs.append([cur[0], cur[-1]])
                    out.append({"id": cid, "kind": slot, "label": lab, "first": vs[0], "runs": runs,
                                "reading": c["reading"], "added": bool(c.get("added")),
                                "note": c["note"]})
                    view["by_node"][cid] = {"pattern": pid, "row": rid, "slot": slot}
                    row_refs.append(store(vs[0]))
                if out:
                    row_cells[slot] = out
            if not row_cells:
                continue
            first = slots[0]
            gives = [c for c in row_cells.get(first, []) if not c["reading"]]
            declared = pid not in SEQUENCES or pid in ("servant", "prophet")
            given = [c["label"] for c in gives] if declared else []
            figs = PERSON.get(row, [])
            nodes.append({"attrs": {"kind": "role_row", "pattern": pid, "figure": figs,
                                    "given_by_text": given},
                          "desc": f"{row} in the role pattern “{role}”"
                                  + (f"; the text gives the role: {'; '.join(given)}" if given
                                     else ("; the role is given by analogy — a reading"
                                           if declared and pid not in ("warfare",) else ""))
                                  + ".",
                          "gender": "unknown", "id": rid, "name": f"{row} (Role pattern: {role})",
                          "refs": list(dict.fromkeys(row_refs))[:12], "source": SOURCE,
                          "type": "passage"})
            reading_row = declared and not given and pid != "warfare"
            rels.append({"certainty": "conjectured" if reading_row else "implied",
                         "dst": pat_id, "note": f"{row}, an instance of the role pattern “{role}”",
                         "refs": list(dict.fromkeys(row_refs))[:4], "source": SOURCE, "src": rid,
                         "type": "instance_of"})
            rows_out.append({"id": rid, "name": row, "figure": figs, "given": given,
                             "reading": reading_row, "cells": row_cells})
            view["by_node"][rid] = {"pattern": pid, "row": rid}
            for f in figs:
                view["by_figure"][f].append({"pattern": pid, "row": rid})
            pat_refs += row_refs[:2]
        nodes.append({"attrs": {"kind": "role_pattern", "slots": slots,
                                "frame": pid not in SEQUENCES},
                      "desc": f"A role pattern: {NOTE[pid]}", "gender": "unknown",
                      "id": pat_id, "name": f"Role pattern: {role}",
                      "refs": list(dict.fromkeys(pat_refs))[:40], "source": SOURCE,
                      "type": "pattern"})
        if pid in SPECIALIZES:
            rels.append({"certainty": "conjectured", "dst": SPECIALIZES[pid],
                         "note": NOTE[pid], "refs": list(dict.fromkeys(pat_refs))[:2],
                         "source": SOURCE, "src": pat_id, "type": "specializes"})
        view["patterns"][pid] = {"id": pat_id, "name": role, "note": NOTE[pid],
                                 "frame": pid not in SEQUENCES,
                                 "slots": [{"stage": s, "name": s, "optional": False,
                                            "added": (pid, s) in ADDED_SLOTS} for s in slots],
                                 "rows": rows_out}
    for path, rs in ((ENT, nodes), (REL, rels)):
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for r in rs:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    VIEW.write_text(json.dumps({**view, "held": held}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    nrows = sum(len(p["rows"]) for p in view["patterns"].values())
    ncells = sum(1 for n in nodes if n["attrs"]["kind"] == "role_cell")
    nread = sum(1 for p in view["patterns"].values() for r in p["rows"]
                for cs in r["cells"].values() for c in cs if c["reading"])
    print(f"patterns {len(BUILD)}; rows {nrows}; cells {ncells} ({nread} readings); "
          f"held (too broad) {len(held)}; nodes {len(nodes)}; relations {len(rels)}")
    print(f"quotes: {REQUOTED['kept']} already the Berean's or WEB's, {REQUOTED['requoted']} put in "
          f"the Berean's words, {REQUOTED['left']} left (no clause shared half their words)")
    for pid, p in view["patterns"].items():
        print(f"  {pid}: " + ", ".join(
            f"{r['name']}{'' if not r['reading'] else '~'}" for r in p["rows"]))


if __name__ == "__main__":
    main()
