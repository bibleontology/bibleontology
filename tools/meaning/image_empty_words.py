"""THE EMPTY IMAGE CARDS (plan 8.2h, 2026-10-24): 98 image cards show no verses at all.

Not because nothing backs them: 92 cite verses in their own description and 94 have relations. They are empty
because no word is joined to the card, so the membership rules have nothing to gather verses with. A card that
says "'Seeing in the distance a fig tree in leaf ...' (Mark 11:13)" and then lists no verse is the failure the
graph-backs-the-card rule names.

The fix is mechanical and adds nothing the card does not already claim. For each empty card, the words of its
name; in each verse it cites (its refs, and the citations in its description), the Hebrew or Greek word the Berean
renders with one of those words (out/bsb-words.json, MACULA's Strong's numbers per verse). That word is NAMED to
exactly those cited verses. A cited verse where no word of the name is found is reported, not guessed.

    python tools/meaning/image_empty_words.py            dry run: what each card would show
    python tools/meaning/image_empty_words.py --write    add the repair rows, with a provenance record
"""
import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from export_claims import verses as vlist  # noqa: E402
from derive import BOOK  # noqa: E402

WRITE = "--write" in sys.argv
RULING = ("ontology/provenance/meaning/image-emptied-cards-2026-10-25.json"
          if any(not a.startswith("--") for a in sys.argv[1:])
          else "ontology/provenance/meaning/image-empty-cards-2026-10-24.json")
STOP = {"the", "a", "an", "of", "to", "and", "in", "on", "with", "his", "her", "my", "your", "their", "its", "for",
        "from", "by", "at", "is", "as", "be", "like", "who", "that", "which", "into", "out", "up", "o"}
CITE = re.compile(r"\(((?:[1-3] )?[A-Z][a-z]+\.? \d+:\d+(?:[-–]\d+)?)\)")


def mac(ref):
    try:
        return {BOOK.get(b, b) + "." + rest for b, rest in (v.split(".", 1) for v in vlist(ref))}
    except Exception:
        return set()


def forms(w):
    out = {w}
    for suf in ("es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            out.add(w[: -len(suf)])
    out |= {w + "s", w + "es"}
    return out


def main():
    rows = [json.loads(l) for l in open(ROOT / "out" / "meaning" / "image-audit" / "images.jsonl", encoding="utf-8")]
    ents = {}
    for ln in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        if ln.strip():
            e = json.loads(ln)
            ents[e["id"]] = e
    render = collections.defaultdict(set)  # key -> the English words the Berean uses for it
    for k, rs in json.loads((ROOT / "out" / "bsb-words.json").read_text(encoding="utf-8"))["words"].items():
        for word, _n in rs:
            render[k] |= set(re.findall(r"[a-z]+", word.lower()))
    # or the cards named on the command line: a card the image audit emptied (2026-10-25: "branch" held the
    # lampstand's branches, Exod 25, while its description is John 15:5's "you are the branches")
    named_cards = [a for a in sys.argv[1:] if not a.startswith("--")]
    empty = named_cards or [r["id"] for r in rows if r["verses"] == 0]
    # a card cites in the Berean's numbering; MACULA's Hebrew counts some verses differently (Joel 3:13 is its
    # 4:13, Ps 52:8 its 52:10), so a cited verse is turned into MACULA's before its words are looked up
    moved = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8"))["moved"]
    to_mac = {bsb: m for m, bsb in moved.items()}
    cited = {}
    for c in empty:
        e = ents.get(c) or {}
        refs = list(e.get("refs") or []) + CITE.findall(e.get("desc") or "")
        cited[c] = sorted({to_mac.get(v, v) for v in (set().union(*(mac(r) for r in refs)) if refs else set())})
    want = set().union(*cited.values())
    # each word's own English in this verse ("text": "harvest"), so a lexeme the renderings table does not carry is
    # still found (θερισμός, "harvest", John 4:35, is not among its ~4,000 lexemes)
    vkeys = collections.defaultdict(set)
    vtext = collections.defaultdict(lambda: collections.defaultdict(set))
    with gzip.open(ROOT / "out" / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for ln in f:
            n = json.loads(ln)
            if n.get("ref") in want and n.get("strong"):
                s = re.sub(r"\D", "", str(n["strong"])).lstrip("0")
                if s:
                    k = ("g" if n.get("lang") == "greek" else "h") + s
                    vkeys[n["ref"]].add(k)
                    vtext[n["ref"]][k] |= set(re.findall(r"[a-z]+", (n.get("text") or "").lower()))
    plan, out_rows = {}, []
    for c in empty:
        name = ((ents.get(c) or {}).get("name") or "").lower()
        toks = {t for w in re.findall(r"[a-z]+", name) if w not in STOP for t in forms(w)}
        named = collections.defaultdict(list)
        unmatched = []
        for v in cited[c]:
            ks = [k for k in vkeys.get(v, ()) if (vtext[v][k] | render[k]) & toks]
            for k in ks:
                named[k].append(v)
            if not ks:
                unmatched.append(v)
        plan[c] = {"name": name, "cited": len(cited[c]), "shown": len({v for vs in named.values() for v in vs}),
                   "words": {k: sorted(vs) for k, vs in named.items()}, "cited_but_no_word_of_the_name": unmatched}
        for k, vs in sorted(named.items()):
            out_rows.append({"card": c, "key": k, "action": "named", "verses": sorted(vs),
                             "decision": "plan 8.2h: an empty image card shows the verses it already cites",
                             "reader": "mechanical: the word of the card's name in each verse it cites (the "
                                       "Berean's rendering of MACULA's Strong's number), 2026-10-24",
                             "ruling": RULING})
    t = collections.Counter()
    for p in plan.values():
        t.update(cards=1, cited=p["cited"], shown=p["shown"], still_empty=p["shown"] == 0)
    print(dict(t))
    for c, p in list(plan.items())[:12]:
        print(f"  {c:32} cites {p['cited']:>2}, shows {p['shown']:>2}  {list(p['words'])}  "
              f"unmatched {p['cited_but_no_word_of_the_name'][:3]}")
    if WRITE:
        rp = ROOT / "ontology" / "card-repairs.jsonl"
        raw = rp.read_text(encoding="utf-8")
        nl = "\r\n" if "\r\n" in raw else "\n"
        have = {(json.loads(l)["card"], json.loads(l)["key"]) for l in raw.split(nl) if l.strip()}
        new = [r for r in out_rows if (r["card"], r["key"]) not in have]
        rp.write_text(raw.rstrip("\r\n") + nl + nl.join(json.dumps(r, ensure_ascii=False) for r in new) + nl,
                      encoding="utf-8", newline="")
        (ROOT / RULING).write_text(json.dumps({"what": __doc__.split("\n\n")[0], "date": "2026-10-24",
                                               "plan": plan}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"written: {len(new)} repair rows -> {RULING}")


if __name__ == "__main__":
    main()
