"""EVIDENCE CARDS: what a local pass flagged, laid out so a judge only has to decide (plan 8.2j, 2026-10-24).

Doug: "maybe there is a way to lay out the evidence that makes Claude's life easy". The costly part of a review agent
is gathering context, not judging. Each card carries everything the decision needs, so a cheap judge (Haiku, in
batches, no tools) can pick an option:
  1. the verse, with the one before and after;
  2. the original-language clause (MACULA: each part's role, gloss and lemmas);
  3. what the graph holds now: the clause record, and the relations on this card that cite this verse;
  4. the pass's finding, its quoted words, and the pass's measured catch rate on planted faults;
  5. precedent: earlier verdicts on findings of the same kind (none until the first verdicts exist);
  6. a short menu, each option's edit written out in full, so a verdict is applied mechanically.

    python tools/meaning/evidence_cards.py CARD
      -> out/meaning/local-structure/<card>.cards.json and .cards.md
"""
import collections
import glob
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from export_claims import verses as vlist  # noqa: E402
from derive import BOOK  # noqa: E402

DIR = ROOT / "out" / "meaning" / "local-structure"
# clause verbs (the record's English) -> the relation type that already exists for them; anything else has no type
# yet and waits for the vocabulary release, which the card says rather than inventing one
TYPE = {"build": "built", "built": "built", "building": "built", "in building": "built", "finished": "built",
        "completed": "built", "laid the foundation": "built", "lay the foundation": "built",
        "repair": "repaired", "repaired": "repaired", "restore": "repaired", "restored": "repaired",
        "strengthened": "repaired", "destroyed": "destroyed", "destroying": "destroyed", "burned": "destroyed",
        "made": "made", "make": "made"}


def load_entities():
    ents, by_name = {}, collections.defaultdict(set)
    for f in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                e = json.loads(ln)
                ents.setdefault(e["id"], e)
                by_name[(e.get("name") or "").lower()].add(e["id"])
    return ents, by_name


def mac(ref):
    return {BOOK.get(b, b) + "." + rest for b, rest in (v.split(".", 1) for v in vlist(ref))}


def macula(refs):
    out = collections.defaultdict(list)
    with gzip.open(ROOT / "data" / "macula-clauses.jsonl.gz", "rt", encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            if d.get("ref") in refs:
                out[d["ref"]].append(d)
    return out


def main(card):
    rows = [json.loads(l) for l in open(DIR / f"{card}.jsonl", encoding="utf-8")]
    ok = [r for r in rows if "answer" in r]
    fake = [r for r in ok if r["planted"]]
    caught = sum(r["answer"] != "yes" for r in fake)
    rate = f"caught {caught} of {len(fake)} planted faults" if fake else "no planted faults run"
    ents, by_name = load_entities()
    records = {}
    for ln in open(ROOT / "out" / "meaning" / "clause-records.jsonl", encoding="utf-8"):
        r = json.loads(ln)
        records[r["clause"]] = r
    rels = []
    for f in glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                x = json.loads(ln)
                if card in (x["src"], x["dst"]):
                    rels.append({**x, "_verses": set().union(*(mac(v) for v in x.get("refs") or [])) or set()})
    cites = set().union(*(mac(v) for v in ents.get(card, {}).get("refs") or [])) if ents.get(card) else set()

    flagged = [r for r in ok if not r["planted"] and (
        r["answer"] != "yes" or (r["doer"] == "unnamed" and r["doer_found"] not in ("", "not stated")))]
    mc = macula({r["ref"] for r in flagged})
    cards = []
    for r in sorted(flagged, key=lambda r: r["ref"]):
        rec = records[r["key"]]
        clause = next((c for c in mc.get(r["ref"], []) for p in c["parts"]
                       if p["role"] == "v" and rec["verb"] in p.get("lemmas", [])), None)
        on_verse = [x for x in rels if r["ref"] in x["_verses"]]
        verb = r["action"].split(" (")[0]
        menu = []
        if r["answer"] == "yes":
            kind = "doer named by the text"
            ids = sorted(by_name.get(r["doer_found"].lower().removeprefix("the "), set())
                         | by_name.get(r["doer_found"].lower(), set()))
            rtype = TYPE.get(verb)
            mode = rec.get("modality") or "stated"
            if mode not in ("stated", "promised"):
                # 27 of the 28 doers the first judges refused sat on commanded or "to build" records (2026-10-24):
                # a relation says it happened, so only stated and promised records may offer one
                menu.append(f"(a) None: the record is {mode}, so no relation. Name the doer on the record only.")
            elif rtype and len(ids) == 1:
                same = next((x for x in rels if (x["src"], x["type"], x["dst"]) == (ids[0], rtype, card)), None)
                if same:
                    menu.append(f"(a) Add {r['ref']} to the existing relation `{ids[0]} {rtype} {card}` "
                                f"(it cites {', '.join(same.get('refs') or [])}).")
                else:
                    menu.append(f"(a) Add the relation `{ids[0]} {rtype} {card}`, refs [{r['ref']}].")
            elif rtype:
                menu.append(f"(a) Add `<doer> {rtype} {card}`, refs [{r['ref']}] — the doer's card is "
                            + (f"one of {ids}" if ids else f"not found by the name \"{r['doer_found']}\"")
                            + ": say which.")
            else:
                menu.append(f"(a) No relation type for \"{verb}\" yet: queue it for the vocabulary release "
                            f"(event and action types, 1.3.0) with this verse.")
            menu.append(f"(b) Name the doer on the clause record only (\"{r['doer_found']}\"), no relation.")
            menu.append("(c) The pass is wrong: the verse does not name this doer. Change nothing.")
        else:
            kind = "record not supported by the verse" if r["answer"] == "no" else "wrong doer or receiver"
            menu.append("(a) The record is wrong: correct it (say which end, and to what) or drop it.")
            menu.append("(b) The record is right; the pass misread the verse. Change nothing.")
        menu.append("(d) Hold for Doug.")
        cards.append({
            "id": r["key"], "kind": kind, "ref": r["ref"],
            "verse": {"before": r["before"], "text": r["text"], "after": r["after"]},
            "original": [{"role": p["role"], "gloss": p["gloss"], "lemmas": p.get("lemmas")}
                         for p in (clause or {}).get("parts", [])],
            "graph_now": {"record": f"{r['doer']} -{r['action']}-> {r['receiver']} [{rec.get('modality')}]",
                          "record_how": {"doer": (rec.get("subject") or {}).get("how"),
                                         "receiver": (rec.get("object") or {}).get("how")},
                          "relations_citing_this_verse": [f"{x['src']} {x['type']} {x['dst']}" for x in on_verse],
                          "card_cites_this_verse": r["ref"] in cites},
            "finding": {"answer": r["answer"], "doer": r["doer_found"], "reason": r["reason"],
                        "model": r["model"], "pass_record": rate, "askings": "one model, one asking"},
            "precedent": [],
            "menu": menu})
    (DIR / f"{card}.cards.json").write_text(json.dumps(cards, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(DIR / f"{card}.cards.md", "w", encoding="utf-8") as f:
        for c in cards:
            v = c["verse"]
            f.write(f"## {c['ref']} — {c['kind']}\n\n")
            f.write(f"**The verse** (with its neighbours):\n\n> *{v['before']}*\n>\n> **{v['text']}**\n>\n> *{v['after']}*\n\n")
            f.write("**The original** (MACULA): " + ("; ".join(
                f"{p['role']}: {p['gloss']} [{' '.join(p['lemmas'] or [])}]" for p in c["original"]) or "not found") + "\n\n")
            g = c["graph_now"]
            f.write(f"**The graph now:** record `{g['record']}` (doer {g['record_how']['doer']}, receiver "
                    f"{g['record_how']['receiver']}); relations citing this verse: "
                    f"{', '.join(g['relations_citing_this_verse']) or 'none'}; the card cites it: "
                    f"{'yes' if g['card_cites_this_verse'] else 'no'}\n\n")
            fd = c["finding"]
            f.write(f"**The finding** ({fd['model']}; {fd['pass_record']}; {fd['askings']}): **{fd['answer']}**"
                    + (f", doer **{fd['doer']}**" if fd["doer"] else "") + f" — {fd['reason']}\n\n")
            f.write("**Precedent:** " + ("; ".join(c["precedent"]) or "none yet (the first verdicts make it)") + "\n\n")
            f.write("**Decide:**\n" + "\n".join(f"- {m}" for m in c["menu"]) + "\n\n---\n\n")
    print(f"{len(cards)} cards -> {DIR / (card + '.cards.md')}  ({rate})")
    print(collections.Counter(c["kind"] for c in cards))


if __name__ == "__main__":
    main(sys.argv[1])
