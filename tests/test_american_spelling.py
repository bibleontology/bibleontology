"""The site writes in American spelling, as the Berean does (Doug, 2026-10-27: "I don't spell favor with a u").

Held by machine for the question cards and the traditions layer built from them: every field a reader sees, in the
site's own voice. Left alone, because they are someone else's words: verse quotes (`quote`), a document's title
(`title`), addresses (`url`), and the editors' trails (keys beginning with `_`). A source's `says` is the site's
account of the document, not a quote, so it is checked (it becomes the traditions edges' `note`). The rest of the app still has British spellings in places (mostly code comments); widening this test
to it is a pass of its own.

Proven 2026-10-27 by planting "favour" in a card's summary and in a traditions node in-process (below): both named.

In process, no server. Run: python tests/test_american_spelling.py"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]

BRITISH = re.compile(
    r"\b(?:\w*(?:favour|honour|colour|behaviour|neighbour|labour|saviour|harbour|rumour|vapour|splendour)\w*"
    r"|centre[sd]?|centring|judgement\w*|defence|offence\w*|licence[sd]?|catalogue[sd]?|programme[sd]?"
    r"|practis(?:e|es|ed|ing)|fulfil|fulfils|fulfilment|whilst|travell\w+|counsell\w+|sceptic\w*|analys(?:e|ed|ing)"
    r"|(?:recogni|organi|reali|emphasi|bapti|summari|characteri|harmoni|critici|apologi|catechi|evangeli|symboli"
    r"|authori|legitimi|scrutini|memori|idoli|spirituali|literali)s(?:e|es|ed|ing|ation))\b",
    re.I)
OTHERS_WORDS = {"quote", "title", "url"}


def hits(obj, where):
    """(path, word) for every British spelling in a field the site speaks in."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.startswith("_") or k in OTHERS_WORDS:
                continue
            found += hits(v, f"{where}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found += hits(v, f"{where}[{i}]")
    elif isinstance(obj, str):
        found += [(where, m.group(0)) for m in BRITISH.finditer(obj)]
    return found


def cards():
    for f in sorted((ROOT / "ontology" / "questions").glob("*.json")):
        yield f.stem, json.loads(f.read_text(encoding="utf-8"))


def layer():
    for name in ("nodes.jsonl", "edges.jsonl"):
        for n, line in enumerate((ROOT / "ontology" / "traditions" / name).read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                rec = json.loads(line)
                if (rec.get("attrs") or {}).get("title"):
                    rec.pop("name", None)           # a document's name is its title, in its publisher's words
                yield f"traditions/{name}:{n}", rec


def check(items):
    return [h for where, obj in items for h in hits(obj, where)]


def main():
    fails = []
    for where, word in check(cards()) + check(layer()):
        fails.append(f"FAIL {where}: '{word}' (American spelling, please)")

    # Planted faults: the check must still catch a British word in a card and in the layer.
    planted_card = [("planted", {"readings": [{"summary": "and to favour none"}]})]
    planted_node = [("planted-node", {"name": "whatever is practised is tested"})]
    planted_quote = [("planted-quote", {"passages": [{"quote": "the favour of the LORD"}]})]
    if not check(planted_card):
        fails.append("FAIL planted: 'favour' in a card's summary was not caught")
    if not check(planted_node):
        fails.append("FAIL planted: 'practised' in a traditions node was not caught")
    if check(planted_quote):
        fails.append("FAIL planted: a verse quote was checked (quotes are the translation's words, not the site's)")

    for f in fails:
        print(f)
    if fails:
        sys.exit(1)
    n = sum(1 for _ in cards())
    print(f"American spelling: {n} question cards and the traditions layer clean; 3 planted checks held")


if __name__ == "__main__":
    main()
