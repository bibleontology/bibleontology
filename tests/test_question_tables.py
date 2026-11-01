"""Every question card's comparison rests on the card's own words and verses (plan 8.4h, 2026-10-28).

A question card opens with its readings side by side (`compare` in ontology/questions/<id>.json, the design
panel's mockup in docs/review/card-panel-2026-10-28/). A cell there is short, and short is where a reading gets
misstated, so each cell names the field it condenses and a snippet of the reading's own text that must be found
there, and every verse it cites must be one the card gives that reading (a passage, or a verse its own text
names). The designer's build checked this for the mockup and caught a stray reference; this holds it for the site.

Also checked:
- every reading has exactly one plain name, and every cell names a reading that exists;
- "in their own words" uses only terms the card defines;
- a tradition marked "in part" for a reading is one the graph says states it (ontology/traditions/, the
  `states_reading` edges, or the card's own held_by), and the qualifier's words are in that reading's summary;
- each "one verse" take rests on its reading's text, and the two pulls cite verses the card holds.

Reported, not failed: cell verses that no relation in the traditions layer carries (the reading node's verses),
which is the graph backing still to build.

Planted: an altered snippet, a verse from another reading, an "in part" tradition that states nothing, an
unknown term, and a term glossed in words that are not the card's note on it. Each must fail.

Run: python tests/test_question_tables.py"""
import copy
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
QDIR = ROOT / "ontology" / "questions"
TRAD = ROOT / "ontology" / "traditions"

REF = re.compile(r"((?:[1-3] )?[A-Z][a-z]+(?: of [A-Z][a-z]+)?) (\d+):(\d+)(?:[-–](\d+))?|(?<![\d:])(\d+):(\d+)(?:[-–](\d+))?")


def verses_in(text):
    """every (book, chapter, verse) a text names, ranges spread, a bare "6:65" taking the last book named"""
    out, book = set(), None
    for m in REF.finditer(text or ""):
        if m.group(1):
            book, c, v, w = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        elif book:
            c, v, w = int(m.group(5)), int(m.group(6)), m.group(7)
        else:
            continue
        for x in range(v, int(w or v) + 1):
            out.add((book, c, x))
    return out


def graph():
    nodes = {}
    for line in (TRAD / "nodes.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            n = json.loads(line)
            nodes[n["id"]] = n
    states = {}
    for line in (TRAD / "edges.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            if e.get("type") == "states_reading":
                doc = nodes.get(e["src"]) or {}
                t = nodes.get((doc.get("attrs") or {}).get("tradition") or "") or {}
                if t.get("name"):
                    states.setdefault(e["dst"], set()).add(t["name"])
    return nodes, states


def field_text(card, ri, fld):
    r = card["readings"][ri - 1]
    if fld.startswith("fr:"):
        return card["further_reading"][int(fld[3:])].get("says") or ""
    if fld == "note":
        return " ".join((p.get("note") or "") for p in r.get("passages") or [])
    return r.get(fld) or ""


def own_verses(card, ri):
    r = card["readings"][ri - 1]
    vs = set()
    for p in r.get("passages") or []:
        vs |= verses_in(p.get("ref"))
    for fld in ("summary", "answers", "label"):
        vs |= verses_in(r.get(fld))
    vs |= verses_in(field_text(card, ri, "note"))
    for p in (card.get("agreed") or {}).get("passages") or []:
        vs |= verses_in(p.get("ref"))
    return vs


def card_verses(card):
    vs = set()
    for i in range(1, len(card.get("readings") or []) + 1):
        vs |= own_verses(card, i)
    return vs


def problems(qid, card, nodes, states):
    c = card.get("compare")
    if not c:
        return [], []
    bad, unbacked = [], []
    n = len(card.get("readings") or [])
    if not isinstance(c.get("reviewed"), bool):
        bad.append(f"{qid}: compare.reviewed must be true or false")
    names = [x.get("reading") for x in c.get("names") or []]
    if sorted(names) != list(range(1, n + 1)):
        bad.append(f"{qid}: plain names cover readings {names}, not 1..{n}")
    gid = "reading_" + qid.replace("-", "_") + "_"
    for row in c.get("rows") or []:
        seen = set()
        for cell in row.get("cells") or []:
            ri = cell.get("reading")
            where = f"{qid}: '{row.get('q')}' reading {ri}"
            if not isinstance(ri, int) or not 1 <= ri <= n or ri in seen:
                bad.append(f"{where}: no such reading, or two cells for it")
                continue
            seen.add(ri)
            if not cell.get("src"):
                bad.append(f"{where}: names no source text")
            for fld, snip in cell.get("src") or []:
                if snip not in field_text(card, ri, fld):
                    bad.append(f"{where}: '{snip}' is not in its {fld}")
            mine = own_verses(card, ri)
            node_vs = set()
            for r_ in (nodes.get(gid + str(ri)) or {}).get("refs") or []:
                node_vs |= verses_in(r_)
            for ref in cell.get("refs") or []:
                vs = verses_in(ref)
                if not vs or not vs <= mine:
                    bad.append(f"{where}: cites {ref}, which the card does not give this reading")
                elif not vs <= node_vs:
                    unbacked.append(f"{where}: {ref}")
    # a term may carry its gloss, "term (gloss)", where the gloss is the card's own note on the term (the young
    # believer's seat, 2026-10-28: "bondage of the will" heard first as slavery, "federal headship" as the marriage debate)
    terms = {t.get("term"): (t.get("note") or "") for t in card.get("terms") or []}
    for ri, ts in (c.get("own_words") or {}).items():
        for t in ts:
            m = re.fullmatch(r"(.+?) \((.+)\)", t)
            if t in terms:
                continue
            if m and m.group(1) in terms:
                if m.group(2).lower() not in terms[m.group(1)].lower():
                    bad.append(f"{qid}: own words of reading {ri}: the gloss of '{m.group(1)}' is not the card's "
                               f"note on it")
                continue
            bad.append(f"{qid}: own words of reading {ri}: '{t}' is not a term the card defines")
    for ri, parts in (c.get("in_part") or {}).items():
        ri = int(ri)
        stated = states.get(gid + str(ri), set()) | set(card["readings"][ri - 1].get("held_by") or [])
        for t, note in parts.items():
            if t not in stated:
                bad.append(f"{qid}: reading {ri} marks {t} 'in part', but no {t} document states it")
            if note not in field_text(card, ri, "summary"):
                bad.append(f"{qid}: reading {ri}, {t} 'in part': '{note}' is not in its summary")
    for ov in c.get("one_verse") or []:
        for ri, fld, snip in ov.get("src") or []:
            if snip not in field_text(card, ri, fld):
                bad.append(f"{qid}: one verse {ov.get('ref')}, reading {ri}: '{snip}' is not in its {fld}")
        for ri, take in (ov.get("takes") or {}).items():
            if take and not any(s[0] == int(ri) for s in ov.get("src") or []):
                bad.append(f"{qid}: one verse {ov.get('ref')}: reading {ri}'s take rests on nothing")
    allv = card_verses(card)
    for p in c.get("pulls") or []:
        for ref in p.get("refs") or []:
            if not verses_in(ref) or not verses_in(ref) <= allv:
                bad.append(f"{qid}: the pull '{p.get('label')}' cites {ref}, which the card does not hold")
    return bad, unbacked


def check_all(cards, nodes, states):
    bad, unbacked = [], []
    for qid, card in cards.items():
        b, u = problems(qid, card, nodes, states)
        bad += b
        unbacked += u
    return bad, unbacked


def main():
    cards = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(QDIR.glob("*.json"))}
    nodes, states = graph()
    bad, unbacked = check_all(cards, nodes, states)
    for x in bad:
        print("FAIL", x)
    with_table = [q for q, c in cards.items() if c.get("compare")]
    # planted faults, each on a copy of the first card with a table
    planted_ok = 0
    if with_table:
        q = with_table[0]
        plants = []
        a = copy.deepcopy(cards[q])
        a["compare"]["rows"][0]["cells"][0]["src"][0][1] += " (planted)"
        plants.append(("altered snippet", a))
        b = copy.deepcopy(cards[q])
        b["compare"]["rows"][0]["cells"][0]["refs"].append("Obadiah 1:21")
        plants.append(("verse from nowhere", b))
        c = copy.deepcopy(cards[q])
        c["compare"].setdefault("in_part", {}).setdefault("1", {})["Planted Church"] = "planted"
        plants.append(("in part, stating nothing", c))
        d = copy.deepcopy(cards[q])
        d["compare"].setdefault("own_words", {}).setdefault("1", []).append("planted term")
        plants.append(("unknown term", d))
        e = copy.deepcopy(cards[q])
        t0 = next(t for t in e.get("terms") or [] if t.get("term"))["term"]
        e["compare"].setdefault("own_words", {}).setdefault("1", []).append(f"{t0} (a gloss the card never gives)")
        plants.append(("a gloss not the card's", e))
        for name, card in plants:
            if problems(q, card, nodes, states)[0]:
                planted_ok += 1
            else:
                print(f"FAIL planted ({name}) was not caught")
                bad.append(name)
    print(f"question tables: {len(with_table)} of {len(cards)} cards have one, "
          f"{sum(len(r.get('cells') or []) for q in with_table for r in cards[q]['compare'].get('rows') or [])} cells "
          f"checked, {planted_ok} of 5 planted faults caught; {len(unbacked)} cell verses no relation carries yet")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
