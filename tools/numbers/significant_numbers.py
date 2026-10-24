"""Significant numbers (plan 6.16): a number the text returns to as a span,
built as a pattern whose instances are OCCASIONS, not verses.

2026-10-03: 40 deserves its own significant-number card because it also ties
to the flood; the question of what the card really is; and P-102 approved
("Significant number" as the card's label).

Input: ontology/numbers/<name>.json, written by hand from the original --
the occasions (each a span the text counts), the phrases it repeats, the
places the text itself joins one occasion to another, and what is set aside
(ages, larger numbers, verses where the witnesses differ).

Checked here, so the file cannot drift from the text:
  - every verse cited contains the number in the Berean text;
  - every quotation is the Berean's own words (each '...'-separated piece);
  - every verse where the ORIGINAL counts the number as days, nights or
    years (out/interlinear.jsonl.gz) is on an occasion or set aside, with
    its reason -- nothing is dropped silently;
  - each phrase's verses are found by its pattern, not listed by hand.
Any failure stops the build and writes nothing.

Output:
  out/significant-numbers.json                     the cards' view
  ontology/entities/significant-numbers.jsonl      one pattern node per number
  ontology/relations/significant-numbers.jsonl     event -occasion_of-> number,
                                                   for occasions inside an event's tellings

    python tools/numbers/significant_numbers.py
"""
from __future__ import annotations

import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
SRC = ROOT / "ontology" / "numbers"
ENT = ROOT / "ontology" / "entities" / "significant-numbers.jsonl"
REL = ROOT / "ontology" / "relations" / "significant-numbers.jsonl"
VIEW = OUT / "significant-numbers.json"
SOURCE = "significant-numbers"
sys.path.insert(0, str(ROOT / "tools" / "events"))
from event_nodes import FROM_MACULA, TO_MACULA  # noqa: E402

SPAN_UNITS = ("day", "night", "year")


def bsb():
    v = {}
    for line in (ROOT / "data" / "bible" / "verses.bsb.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            if "b" in d:
                v[f"{d['b']} {d['c']}:{d['v']}"] = d["t"]
    return v


def to_bsb(mref, moved):
    """'Deu.29.4' (MACULA) -> 'Deut 29:5' (Berean)"""
    mref = moved.get(mref, mref)
    b, c, v = mref.split(".")
    return f"{FROM_MACULA[b]} {c}:{v}"


def vkey(ref):
    b, cv = ref.rsplit(" ", 1)
    c, v = cv.split(":")
    order = list(TO_MACULA)
    return (order.index(b), int(c), int(v))


def norm(s):
    return re.sub(r"\s+", " ", s.replace("—", "-").replace("–", "-").replace("’", "'")
                  .replace("‘", "'").replace("“", '"').replace("”", '"')).strip().lower()


def original_spans(words, moved):
    """Berean ref -> True for every verse where the original counts the
    number as days, nights or years (the gloss of a nearby word)."""
    found = {}
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt", encoding="utf-8"):
        d = json.loads(line)
        ws = d.get("words") or []
        for i, w in enumerate(ws):
            g = (w.get("g") or "").lower()
            if not any(re.search(rf"\b{re.escape(x)}\b", g) for x in words):
                continue
            near = " ".join((x.get("g") or "").lower() for x in ws[max(0, i - 3):i + 4])
            if any(u in near for u in SPAN_UNITS):
                found[to_bsb(d["ref"], moved)] = True
    return found


def events_at():
    """Berean ref -> [(event id, title)] whose tellings hold it."""
    ev = json.loads((OUT / "event-nodes.json").read_text(encoding="utf-8"))["events"]
    spans = []
    for eid, e in ev.items():
        for t in e["tellings"]:
            a, z = t["first"].split("."), t["last"].split(".")
            spans.append((a[0], (int(a[1]), int(a[2])), (int(z[1]), int(z[2])), eid, e["title"]))

    def at(ref):
        b, cv = ref.rsplit(" ", 1)
        c, v = (int(x) for x in cv.split(":"))
        return [(eid, title) for bk, lo, hi, eid, title in spans
                if bk == b and lo <= (c, v) <= hi]
    return at


def build(spec, V, moved, at, errors):
    words = spec["words"]
    has = re.compile("|".join(rf"\b{re.escape(w)}\b" for w in words), re.I)

    def check_ref(ref, where):
        if ref not in V:
            errors.append(f"{spec['id']}: {where}: {ref} is not a Berean verse")
            return False
        if not has.search(V[ref]):
            errors.append(f"{spec['id']}: {where}: {ref} does not contain {words[0]!r} in the "
                          f"Berean: {V[ref][:90]}")
            return False
        return True

    def check_quote(ref, words_quoted, where):
        if ref not in V:
            errors.append(f"{spec['id']}: {where}: {ref} is not a Berean verse")
            return
        for piece in re.split(r"\.\.\.|…", words_quoted):
            p = norm(piece).strip(" '\":,")
            if p and p not in norm(V[ref]):
                errors.append(f"{spec['id']}: {where}: {ref} has no {piece.strip()!r}")

    placed = collections.defaultdict(list)
    occ_out = []
    for o in spec["occasions"]:
        for r in o["verses"]:
            check_ref(r, o["id"])
            placed[r].append(o["id"])
        # ONLY THE EVENTS NAMED. A verse inside an event's passages does not
        # make the event an occasion: Stephen's speech recounts the wilderness
        # years (Acts 7:36) and a forty-year reign is not the coronation
        # (2 Sam 5:4 sits inside "David made king"). Each named event must
        # hold one of the occasion's verses in its own tellings.
        evs = {}
        for r in o["verses"]:
            for eid, title in at(r):
                if eid in o.get("events", ()):
                    evs.setdefault(eid, {"id": eid, "title": title, "refs": []})["refs"].append(r)
        for eid in o.get("events", ()):
            if eid not in evs:
                errors.append(f"{spec['id']}: occasion {o['id']} names {eid}, whose tellings "
                              f"hold none of its verses")
        occ_out.append(dict(o, verses=sorted(o["verses"], key=vkey),
                            events=list(evs.values()),
                            quotes={r: V.get(r) for r in o["verses"]}))
    aside = {}
    for k, s in spec.get("set_aside", {}).items():
        for r in s["verses"]:
            # the number as written in the Berean: only where the set-aside
            # reason is not itself that the Berean writes it differently
            if r in V and not has.search(V[r]) and k in ("ages",):
                errors.append(f"{spec['id']}: set_aside {k}: {r} has no {words[0]!r}")
            aside[r] = k
    # nothing the original counts as a span is dropped silently
    spans = original_spans(words, moved)
    missing = sorted((r for r in spans if r not in placed and r not in aside), key=vkey)
    for r in missing:
        errors.append(f"{spec['id']}: the original counts {words[0]} as days/nights/years at "
                      f"{r} ({(V.get(r) or '')[:80]}) -- place it on an occasion or set it aside")
    phrases = []
    for p in spec.get("phrases", []):
        rx = re.compile(p["match"], re.I)
        hits = sorted((r for r, t in V.items() if rx.search(t)), key=vkey)
        order = [o["id"] for o in spec["occasions"]]          # the file's order, the text's
        occ = sorted({o for r in hits for o in placed.get(r, [])}, key=order.index)
        phrases.append(dict(p, verses=hits, occasions=occ))
    joins = []
    for j in spec.get("joins", []):
        for side in ("a", "b", "c"):
            if j.get(side):
                check_quote(j[side][0], j[side][1], f"join {j['title']!r}")
        for o in j.get("occasions", []):
            if o not in {x["id"] for x in spec["occasions"]}:
                errors.append(f"{spec['id']}: join {j['title']!r} names unknown occasion {o}")
        joins.append(j)
    with_n = {r for r, t in V.items() if has.search(t)}
    n_all = len(with_n)
    quoted = {s[0] for j in spec.get("joins", []) for s in (j.get("a"), j.get("b"), j.get("c")) if s}
    # "complete": "berean" -- a number that counts SETS (twelve) is held to
    # more than the original's spans: every Berean verse with it is placed,
    # quoted in a tie, or set aside with its reason
    if spec.get("complete") == "berean":
        for r in sorted(with_n - set(placed) - set(aside) - quoted, key=vkey):
            errors.append(f"{spec['id']}: {r} has {words[0]} and is on no occasion and not set "
                          f"aside: {V[r][:90]}")
    # every other verse with the number: counts of things (armies, measures,
    # gifts), counted so the card says how many it leaves out (the eight-reader
    # review: "the set-aside list is incomplete")
    n_other = len(with_n - set(placed) - set(aside) - quoted)
    view = {"id": spec["id"], "name": spec["name"], "number": spec["number"], "lead": spec["lead"],
            "groups": spec["groups"], "occasions": occ_out, "phrases": phrases, "joins": joins,
            "set_aside": {k: dict(s, verses=sorted(s["verses"], key=vkey))
                          for k, s in spec.get("set_aside", {}).items()},
            "counts": {"verses_with_the_number": n_all, "other_counts": n_other,
                       "occasions": len(occ_out),
                       "verses_on_occasions": len(placed)}}
    first = sorted(placed, key=vkey)[:3]
    node = {"attrs": {"kind": "significant_number", "number": spec["number"]},
            "desc": spec["lead"], "gender": "unknown", "id": spec["id"],
            "disambiguation": spec.get("disambiguation")
                              or f"the significant number: the times the text counts {spec['name']} "
                                 f"as a span, not any one verse's {spec['name']}",
            "name": spec["name"], "refs": first, "source": SOURCE, "type": "pattern"}
    rels = []
    for o in occ_out:
        for e in o["events"]:
            rels.append({"certainty": "explicit", "dst": spec["id"],
                         "note": f"'{e['title']}' counts {spec['name']}: {o['title']} "
                                 f"({', '.join(e['refs'])})",
                         "refs": e["refs"][:4], "source": SOURCE, "src": e["id"],
                         "type": "occasion_of"})
    return view, node, rels


def main():
    V = bsb()
    moved = json.loads((OUT / "versemap.json").read_text(encoding="utf-8"))["moved"]
    at = events_at()
    errors, views, nodes, rels = [], {}, [], []
    for f in sorted(SRC.glob("*.json")):
        spec = json.loads(f.read_text(encoding="utf-8"))
        view, node, rr = build(spec, V, moved, at, errors)
        views[spec["id"]] = view
        nodes.append(node)
        rels += rr
    if errors:
        print("\n".join(errors))
        raise SystemExit(f"{len(errors)} problem(s); nothing written")
    # one edge per event and number; two occasions in one event (Moses' two
    # forties, both in "Israel receives the law") join their notes
    seen, uniq = {}, []
    for r in rels:
        k = (r["src"], r["dst"])
        if k in seen:
            prev = seen[k]
            prev["note"] += "; " + r["note"].split(": ", 1)[1]
            prev["refs"] = (prev["refs"] + [x for x in r["refs"] if x not in prev["refs"]])[:6]
        else:
            seen[k] = r
            uniq.append(r)
    VIEW.write_text(json.dumps({"_source": "tools/numbers/significant_numbers.py from "
                                "ontology/numbers/", "numbers": views},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    for path, rows in ((ENT, nodes), (REL, uniq)):
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    for v in views.values():
        c = v["counts"]
        print(f"{v['name']}: {c['occasions']} occasions over {c['verses_on_occasions']} verses "
              f"(of {c['verses_with_the_number']} with the number); "
              f"{len(v['phrases'])} phrases; {len(v['joins'])} joins; "
              f"{sum(1 for r in uniq if r['dst'] == v['id'])} event links")


if __name__ == "__main__":
    main()
