"""CASES LIKE "WORLD": cards much thinner than the original words behind them,
or of the wrong kind (proposed plan 8.2c, P-2026-10-18-4; 2026-10-18:
"world" is worth fixing, and a scan for similar cases was to follow, then
approved).

The case: /e/world was a place on one verse (Job 18:18), while κόσμος has 57
uses in John alone. Measured, nothing changed:

  - THE WORDS BEHIND A CARD'S NAME, found two ways: the words the card's own
    references and mentions point at, AND every Hebrew or Greek word whose
    gloss is the card's name in at least 30% of its uses (at least 3). The
    second way is what finds κόσμος for "world": the record's one reference
    is the Hebrew תֵּבֵל.
  - WHAT THE CARD CARRIES: its verses (its references and its mentions).
  - THE GAP: the verses those words are in that the card does not carry.
  - THE KIND: the share of the words' uses MACULA marks as a proper noun. A
    place, people or group whose words are almost never proper nouns (a
    concept filed as a place, as "world" was) is flagged.

People are not ranked: names shared by several people (the Johns, the
Jameses) make a gap meaningless, and TIPNR already tells them apart.

    python tools/meaning/thin_cards.py   -> out/thin-cards.json,
                                            docs/review/thin-cards-2026-10-18.html
"""
import ast
import collections
import gzip
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import structure as S  # noqa: E402

OUT = ROOT / "out"
# not "title": the divine titles are ruled by hand, record by record (memory:
# divine persons by hand), never by a scan
RANKED = {"place", "concept", "group", "object", "creature"}
# THE DIVINE WORDS are left out of the scan for the same reason: "gods" matched
# θεός, God (fifth run). God, the LORD, El, Elohim, Adonai, the Lord: ruled by
# hand, record by record
DIVINE = {"G2316", "H430", "H433", "H410", "H3068", "H3069", "H136", "G2962", "H3050", "H426"}
STOP = {"the", "a", "an", "of", "from", "to", "in", "on", "into", "for", "with", "by", "and", "his", "her",
        "their", "your", "my", "our", "its", "all", "this", "that", "these", "those", "o"}
e = html.escape


def to_macula_book():
    """app2/server.py's TO_MACULA, read from its source: one map, never two."""
    src = (ROOT / "app2" / "server.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "TO_MACULA" for t in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit("TO_MACULA not found in app2/server.py")


def head(text):
    ws = [w for w in re.findall(r"[a-z]+", (text or "").lower()) if w not in STOP]
    return ws[-1] if ws else ""


def singular(w):
    return w[:-1] if w.endswith("s") and not w.endswith("ss") and len(w) > 3 else w


def main():
    tm = to_macula_book()
    words = {}                                   # id -> (ref, key, proper, head)
    by_ref = collections.defaultdict(list)
    occ = collections.defaultdict(set)           # (lang, strong) -> verses
    proper = collections.Counter()
    total = collections.Counter()
    heads = collections.defaultdict(collections.Counter)
    sample_word = {}
    with gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            # NOUNS ONLY: a card stands for a thing, and its words are nouns.
            # The first run let pronouns and the "and" prefix in (H2050, 7,283
            # uses), so "those who curse you" matched every "you" and "world"
            # ranked 871st under them (2026-10-18)
            if not d.get("word") or not d.get("strong") or d.get("class") != "noun":
                continue
            s = re.sub(r"\D", "", str(d["strong"])).lstrip("0")
            if not s:
                continue
            key = (d.get("lang"), s)
            h = singular(head(d.get("text")))
            words[d["id"]] = (d["ref"], key, d.get("type") == "proper", h)
            by_ref[d["ref"]].append(d["id"])
            occ[key].add(d["ref"])
            total[key] += 1
            proper[key] += d.get("type") == "proper"
            heads[key][h] += 1
            sample_word.setdefault(key, d.get("original") or d.get("hebrew"))
    # name -> the words whose gloss is that name in >= 30% of their uses (>= 3)
    by_name = collections.defaultdict(list)
    for key, hc in heads.items():
        for h, n in hc.items():
            if h and n >= 3 and n / total[key] >= 0.3:
                by_name[h].append(key)
    mentions = collections.defaultdict(set)
    with gzip.open(OUT / "mentions.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            m = json.loads(line)
            mentions[m["record"]].add(m["occurrence"])
    # A CONCEPT CARD CARRIES ITS ANCHOR WORDS' VERSES (out/concept-anchors):
    # /e/love is anchored to אָהַב, חֶסֶד, ἀγαπάω and ἀγάπη and shows their
    # verses. Without this the scan read "love" as 10 verses and listed ḥesed
    # as carried by no card (fourth run). Only a card of one word: a phrase's
    # parts ("many" in "a robe of many colors") are not what it carries.
    anchored = collections.defaultdict(set)
    with gzip.open(OUT / "concept-anchors.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            a = json.loads(line)
            if a.get("kind") != "word":
                continue
            for p in a.get("parts") or []:
                for strong, _n, _share in p.get("anchors") or []:
                    lang = "hebrew" if strong[0] in "hH" else "greek"
                    anchored[a["id"]].add((lang, strong[1:].lstrip("0")))

    def mref(r):
        m = re.match(r"^([1-3]?[A-Za-z]+)\s+(\d+):(\d+)", r or "")
        if not m or m.group(1) not in tm:
            return None
        return S.to_macula(tm[m.group(1)], int(m.group(2)), int(m.group(3)))

    rows = []
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        rec = json.loads(line)
        if rec.get("type") not in RANKED:
            continue
        # BY NAME ONLY FOR A ONE-WORD NAME ("world", "earth", "Sheol"): a
        # phrase ("the hand of the Lord", "Aaron's sons") was matched by its
        # last word and inherited every "Lord" and every "son" (second run)
        content = [w for w in re.findall(r"[a-z]+", (rec.get("name") or "").lower()) if w not in STOP]
        name = singular(content[0]) if len(content) == 1 else ""
        refs = {x for x in (mref(r) for r in rec.get("refs") or []) if x}
        mocc = [o for o in mentions.get(rec["id"], ()) if o in words]
        carried = refs | {words[o][0] for o in mocc}
        for k in anchored.get(rec["id"], ()):
            carried |= occ.get(k, set())
        keys = collections.Counter(words[o][1] for o in mocc)
        for r in refs:                            # the card's word in its own verses
            for w in by_ref.get(r, ()):
                if name and words[w][3] == name:
                    keys[words[w][1]] += 1
        for k in by_name.get(name, ()):           # every word glossed by its name
            keys[k] += 1
        if not keys:
            continue
        verses = set().union(*(occ[k] for k in keys))
        gap = verses - carried
        n_all = sum(total[k] for k in keys)
        share_proper = sum(proper[k] for k in keys) / n_all if n_all else 0
        misfit = rec["type"] in ("place", "group") and share_proper < 0.2 and len(verses) >= 10
        rows.append({"id": rec["id"], "name": rec.get("name"), "type": rec["type"],
                     "carried": len(carried), "word_verses": len(verses), "gap": len(gap),
                     "covered": round(len(carried & verses) / len(verses), 3) if verses else 0,
                     "proper_share": round(share_proper, 2), "kind_misfit": misfit,
                     "words": [{"lang": k[0], "strong": ("H" if k[0] == "hebrew" else "G") + k[1],
                                "word": sample_word.get(k), "uses": total[k], "verses": len(occ[k])}
                               for k, _ in keys.most_common(6)],
                     "gap_sample": sorted(gap)[:8], "_carried": sorted(carried)})
    rows.sort(key=lambda r: (-r["gap"], r["covered"]))
    rank = {r["id"]: i + 1 for i, r in enumerate(rows)}
    # BY WORD, NOT BY CARD (third run): ranked card by card, the most frequent
    # words floated up (son, man, day). What the cards share is the finding:
    # one original word split over several thin cards (אֶרֶץ over "earth",
    # "the earth", "land", "lands", "my land", "country"), and "world" one card
    # on κόσμος's 150 verses. A word is listed when no card carries a quarter
    # of its verses.
    cluster = collections.defaultdict(list)
    card_keys = {}
    for r in rows:
        for w in r["words"]:
            cluster[(w["lang"], w["strong"])].append(r)
    groups = []
    for (lang, strong), cards in cluster.items():
        key = (lang, strong[1:])
        wv = occ.get(key, set())
        if len(wv) < 20 or strong in DIVINE:
            continue
        # a proper name's verses are its people's, whom the scan leaves out
        # (Judah, Ephraim, Moab): not a case like "world" (fifth run)
        if total[key] and proper[key] / total[key] >= 0.5:
            continue
        best = max(len(set(c["_carried"]) & wv) / len(wv) for c in cards) if wv else 0
        if best >= 0.25:
            continue
        groups.append({"strong": strong, "word": sample_word.get(key), "verses": len(wv),
                       "proper_share": round(proper[key] / total[key], 2) if total[key] else 0,
                       "best_covered": round(best, 3),
                       "cards": [{"id": c["id"], "name": c["name"], "type": c["type"],
                                  "carried_here": len(set(c["_carried"]) & wv), "kind_misfit": c["kind_misfit"]}
                                 for c in sorted(cards, key=lambda c: -len(set(c["_carried"]) & wv))]})
    groups.sort(key=lambda g: -g["verses"])
    for r in rows:
        r.pop("_carried", None)
    sheet(groups)
    print(f"{len(groups)} original words that no card carries a quarter of;",
          "κόσμος:", next((f"rank {i + 1}, {g['verses']} verses, cards "
                           + ", ".join(f"{c['name']} ({c['carried_here']})" for c in g["cards"])
                           for i, g in enumerate(groups) if g["strong"] == "G2889"), "absent"))
    (OUT / "thin-cards.json").write_text(json.dumps({"_what": __doc__.split("\n\n")[0], "rows": rows},
                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    world = next((r for r in rows if r["id"] == "world"), None)
    print(f"{len(rows):,} cards measured; 'world' ranks {rank.get('world')}:",
          json.dumps(world, ensure_ascii=False)[:400] if world else "absent")
    print("kind misfits:", sum(r["kind_misfit"] for r in rows))
    for r in rows[:25]:
        print(f"  {r['gap']:>5} gap  {r['carried']:>4}/{r['word_verses']:<5} {r['type']:<8} {r['name']:<24} "
              f"{' '.join(w['strong'] + ':' + str(w['verses']) for w in r['words'][:4])}"
              f"{'  KIND?' if r['kind_misfit'] else ''}")
    return rows, rank


def sheet(groups):
    """The scan sheet: one row per original word, its cards beneath it."""
    rows = []
    for g in groups:
        cards = "".join(
            f"<li><a href='https://bibleontology.org/e/{e(c['id'])}' target=_blank>{e(c['name'])}</a> "
            f"<span class=k>{e(c['type'])} · carries {c['carried_here']} of these verses</span>"
            f"{' <span class=q>kind?</span>' if c['kind_misfit'] else ''}</li>" for c in g["cards"][:8])
        more = f"<li class=k>… and {len(g['cards']) - 8} more</li>" if len(g["cards"]) > 8 else ""
        rows.append(f"<tr><td><b>{e(g['word'] or '')}</b><br><span class=k>{e(g['strong'])}</span></td>"
                    f"<td>{g['verses']:,}</td><td>{g['best_covered']:.0%}</td>"
                    f"<td>{g['proper_share']:.0%}</td><td><ul>{cards}{more}</ul></td></tr>")
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Cards like world</title><style>
:root{{--paper:#F3F5F8;--surface:#fff;--ink:#141F2C;--muted:#5C6A7B;--rule:#BAC4D0;--warn:#9a6b2f}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2C3A4A;--warn:#d9a35b}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Georgia,serif}} main{{max-width:1000px;margin:0 auto;padding:16px}}
table{{border-collapse:collapse;width:100%;background:var(--surface)}} td,th{{border:1px solid var(--rule);padding:6px 8px;vertical-align:top;font-size:14px}}
th{{text-align:left}} ul{{margin:0;padding-left:16px}} .k{{color:var(--muted);font-size:13px}} .q{{color:var(--warn);font-size:13px}} a{{color:inherit}}
</style></head><body><main><h1>Cards like "world": a first scan</h1>
<p class=k>Proposed plan 8.2c, measured only; nothing has been changed. One row per original word that no card carries
a quarter of (words with 20 or more verses), most frequent first. Under it, the cards that point at it, with how many
of the word's verses each carries. <i>kind?</i> marks a place or group whose words are almost never proper nouns, as
"world" was. Found by each card's own references and mentions, and, for a card named by one word, every word glossed
by that name.</p>
<p class=k>What it is for: to see whether the method finds real cases before any are ruled on. Many rows will be
ordinary words (son, day) whose thin card may be right as it is.</p>
<table><tr><th>Word</th><th>Verses</th><th>Best card carries</th><th>Proper noun</th><th>Cards</th></tr>{''.join(rows)}</table>
</main></body></html>"""
    dest = ROOT / "docs" / "review" / "thin-cards-2026-10-18.html"
    dest.write_text(page, encoding="utf-8")
    print("->", dest.relative_to(ROOT))


if __name__ == "__main__":
    main()
