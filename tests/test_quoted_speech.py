"""No character's words are stated as the text's own (the committee's third
sitting, D1; approved 2026-10-20).

The rule the site, the map, claim.ttl and the blog all state -- only the
narrator is asserted -- failed in at least 47 statements of speech that had no
speaker on record: Job 23:16 "God terrified Job" (Job speaking), Isa 38:12
(Hezekiah's writing), Jer 20:7 (Jeremiah's complaint), John 3:16 (inside
Jesus's words to Nicodemus as the Berean marks them). So, of the statements
shown in the narrator's voice:

  - none sits in a verse the Berean prints wholly inside quotation marks;
  - none in a partly quoted verse has its verb inside the quotation;
  - none is in Psalms (a psalm's voice is its heading's, or nobody's; never
    the narrator's -- the psalm ruling);
  - none has a second-person verb outside the letters and memoirs;
  - planted: a quoted, a psalm and a second-person statement released are
    each caught.

    python tests/test_quoted_speech.py          (preflight runs it so)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
from quoted import berean_quotes, verb_side  # noqa: E402

# the letters and memoirs, where the writer is the narrator's "I" and "you"
# (tools/meaning/write_statements.py I_NARRATOR, in the Berean's book names)
LETTERS = {"Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim", "Titus", "Phlm",
           "Heb", "Jas", "1Pet", "2Pet", "1John", "2John", "3John", "Jude", "Neh", "Ezra", "Eccl"}
DIVINE = {"god", "jesus", "holy_ghost", "the_father", "spirit", "spirit_of_god"}


def shown_narrator(rows):
    return [r for r in rows if not r.get("held") and not r.get("described") and not r.get("claimed_by")]


def faults(rows, quotes, texts):
    out = []
    for r in shown_narrator(rows):
        refs = r.get("refs") or []
        books = {x.split()[0] for x in refs}
        if all(quotes.get(x) == "whole" for x in refs):
            out.append(f"{refs[0]}: '{r.get('label_plain')}' ({r['src']} -> {r['dst']}) is wholly inside the Berean's "
                       "quotation marks")
        elif any(quotes.get(x) == "part" for x in refs) and not any(quotes.get(x) is None for x in refs) and \
                verb_side(r.get("label_plain") or "", [texts[x] for x in refs if quotes.get(x) == "part"]) == "inside":
            out.append(f"{refs[0]}: '{r.get('label_plain')}' stands inside a quotation")
        if books == {"Ps"}:
            out.append(f"{refs[0]}: a psalm statement in the narrator's voice")
        if str(r.get("person") or "").startswith("second") and not (books & LETTERS and r["src"] not in DIVINE):
            out.append(f"{refs[0]}: '{r.get('label_plain')}' is second person, addressed, not narrated")
    return out


def relation_faults(quotes):
    """THE RELATIONS TOO (the committee of 2026-10-21, the scholar's first
    finding): a claim about the world in the narrator's voice whose every
    verse the Berean prints as speech (tools/meaning/hold_quoted_relations.py
    holds them; this fails if one is shown)."""
    from hold_quoted_relations import categories, to_hold
    cat, out = categories(), []
    for p in sorted((ROOT / "ontology" / "relations").glob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("type") != "states" and to_hold(r, cat, quotes):
                    out.append(f"{p.name}: {r['refs'][0]} {r['src']} {r['type']} {r['dst']} is speech, "
                               "stated as the narrator's")
    return out


def main():
    rows = [json.loads(x) for x in (ROOT / "ontology" / "relations" / "verb-statements.jsonl").read_text(
        encoding="utf-8").splitlines() if x.strip()]
    quotes, texts = berean_quotes()
    fails = faults(rows, quotes, texts)
    rel = relation_faults(quotes)
    fails += rel
    # PLANTED: a held relation released must be caught
    from hold_quoted_relations import categories, to_hold
    cat = categories()
    held = next((json.loads(x) for p in sorted((ROOT / "ontology" / "relations").glob("*.jsonl"))
                 for x in p.read_text(encoding="utf-8").splitlines()
                 if x.strip() and "Berean's quotation marks" in (json.loads(x).get("held") or "")
                 and json.loads(x).get("type") != "states"), None)
    if held is None or not to_hold(dict(held, held=None), cat, quotes):
        fails.append("planted: a held quoted relation released was not caught")
    # PLANTED: three held rows released, one of each kind, must be caught
    def first(test):
        return next((r for r in rows if r.get("held") and test(r)), None)
    plants = [first(lambda r: all(quotes.get(x) == "whole" for x in r["refs"])),
              first(lambda r: {x.split()[0] for x in r["refs"]} == {"Ps"}),
              first(lambda r: str(r.get("person") or "").startswith("second")
                    and not {x.split()[0] for x in r["refs"]} & LETTERS)]
    for p in plants:
        if p is None:
            fails.append("planted: no held row of a kind to plant")
            continue
        released = [dict(r, held=None) if r is p else r for r in rows]
        if not faults(released, quotes, texts):
            fails.append(f"planted: {p['refs'][0]} released and not caught")
    n = len(shown_narrator(rows))
    print(f"quoted speech: {n} statements shown in the narrator's voice, none inside the Berean's quotation marks, "
          f"in Psalms or addressed in the second person; no relation about the world stated from speech "
          f"({len(rel)} found); 4 planted releases; {len(fails)} failures")
    for f in fails[:20]:
        print("FAIL " + f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
