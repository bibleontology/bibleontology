"""Each concept card's words, in the order its card shows them, for the same-word line (P-2026-11-18-3).

    python -X utf8 tools/concept_lead_words.py            # against the local server on :8002

The early extraction made a concept card for each English word, so one Hebrew or Greek word often leads several
concept cards (עֶבֶד leads slaves, manservant, menservants, servant and servants) that a visitor never learns about.
They are not merged: concepts keep their own cards (Doug, 2026-10-04). The card shows, under each of its words, the
other concept cards that word leads. A card's words come from a long derivation in the entity handler, too costly to
run for every concept on every request, so they are read here from the server's own answers and written to
ontology/concept-lead-words.json, which the server loads. tests/test_concept_lead_words.py checks a sample against
the live answers, so the file cannot drift unseen: rerun this after any change to the words layer or the hubs.
"""
import json
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ontology" / "concept-lead-words.json"
BASE = "http://localhost:8002"


def concept_ids():
    # A card merged through ontology/aliases.jsonl is retired: its address answers 301 to the card it joined, so
    # listing it would put "sons" on son's own line (31 such after option C, 2026-11-19, before this check).
    retired = {json.loads(x)["id"] for x in (ROOT / "ontology" / "aliases.jsonl").read_text(encoding="utf-8").splitlines()
               if x.strip()}
    ids = set()
    for f in sorted((ROOT / "ontology" / "entities").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("type") == "concept" and r.get("id") and not r.get("alias_of") and r["id"] not in retired:
                ids.add(r["id"])
    return sorted(ids)


def card_words(j):
    """the keys the card shows, in its order: the concept card's own list, else the face's"""
    cc = j.get("ccard") or {}
    return [w.get("key") for w in (cc.get("words") or j.get("words") or []) if w.get("key")]


def fetch(eid):
    url = f"{BASE}/api/entity?" + urllib.parse.urlencode({"id": eid})
    for _ in range(3):
        try:
            j = json.load(urllib.request.urlopen(url, timeout=120))
            return eid, (card_words(j) if j.get("found") and j.get("id") == eid else None)
        except Exception:  # noqa: BLE001 -- a slow answer is retried, then reported
            continue
    return eid, "error"


def main():
    ids = concept_ids()
    cards, errors = {}, []
    with ThreadPoolExecutor(4) as ex:
        for i, (eid, ws) in enumerate(ex.map(fetch, ids)):
            if ws == "error":
                errors.append(eid)
            elif ws:
                cards[eid] = ws
            if i % 200 == 0:
                print(i, len(ids), flush=True)
    if errors:
        sys.exit(f"{len(errors)} cards did not answer, nothing written: {errors[:10]}")
    OUT.write_text(json.dumps({"_note": "Each concept card's words in its card's order (tools/concept_lead_words.py); "
                                        "the same-word line, P-2026-11-18-3. Regenerate after the words layer changes.",
                               "cards": cards}, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    lead = {}
    for eid, ws in cards.items():
        lead.setdefault(ws[0], []).append(eid)
    shared = {k: v for k, v in lead.items() if len(v) > 1}
    print(f"{len(cards)} concept cards with words; {len(shared)} words lead {sum(len(v) for v in shared.values())} cards")


if __name__ == "__main__":
    main()
