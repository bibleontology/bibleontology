"""THE NEXT 58 IMAGES: the sheet, and the build on Doug's word (plan 8.2h, 2026-10-24).

Each image card today lists every verse of its word ("the hand of God" lists every "hand"). After this it holds the
verses where the text uses the figure. Two passes read them:
  - the candidate pass (out/meaning/image-audit/candidates/tier2-final.json): figure-first candidates, a first and a
    blind second reader, a third for the splits;
  - the sweep (out/meaning/image-audit/sweep/settled.json): every verse of 54 cards, a blind confirmer on every
    figure and every 10th other, a third reader for the splits.
A verse both read and they differ: every reader's vote is pooled and the majority places it; a tie is HELD.
A three-way split is HELD. Held is on neither card and listed for Doug: unresolved is better than wrong.
Four cards are named sayings, not broad figures (the two houses, the sower, the good tree, the city on a hill): the
candidates are the figure, and the card's other thousand "house" verses go.

Placement: figure and both -> the image card. The literal cards are not touched here (their verses are already
theirs). Each word the image card carries is NAMED to the figure verses it occurs in, or DROPPED, so no unnamed word
pours its verses back. Keyed identifications (the text's own "X is Y") are listed, not built: they are relations,
and go to their own sheet.

    python tools/meaning/image_tier2_build.py            the sheet: docs/review/image-audit-58-2026-10-24/SHEET.md
    python tools/meaning/image_tier2_build.py --write    apply, on Doug's word
"""
import collections
import glob
import gzip
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "out" / "meaning" / "image-audit"
# --small: the 137 cards of 1-99 verses, swept in packed chunks and never in the candidate pass (2026-10-24)
SMALL = "--small" in sys.argv
SHEET = ROOT / "docs" / "review" / ("image-audit-137-2026-10-24" if SMALL else "image-audit-58-2026-10-24") / "SHEET.md"
RULING = ("ontology/provenance/meaning/image-audit-137-marks-2026-10-24.json" if SMALL
          else "ontology/provenance/meaning/image-audit-58-marks-2026-10-24.json")
DONE_BEFORE = {"image_wine", "image_lion", "image_vine", "image_candlestick", "image_lamb", "image_clothes", "image_ox",
               "image_bread", "image_temple"}
SAYINGS = {"image_two_houses", "image_city_on_a_hill", "image_sower", "image_good_tree"}
PLACE = {"literal": "literal", "figure": "figure", "figure_keyed": "figure", "both": "both"}
READER = ("the image audit's candidate pass (a first and a blind second Claude Sonnet reader, a third for the splits) "
          "and the sweep of every verse (a Claude Sonnet reader, a blind confirmer on every figure and every 10th "
          "other, a third for the splits), 2026-10-24; ties and three-way splits held; ruled by Doug")
WRITE = "--write" in sys.argv


def pl(s):
    return PLACE.get(s, "neither") if s else None


def votes_from_candidates():
    v = collections.defaultdict(list)
    for f in glob.glob(str(A / "candidates" / "*.pack.json")):
        p = json.loads(Path(f).read_text(encoding="utf-8"))
        for x in p["verses"]:
            v[f"{p['image']}|{x['ref']}"].append(pl(x["sense"]))
        b = Path(f.replace(".pack.", ".blind."))
        for x in json.loads(b.read_text(encoding="utf-8"))["verses"]:
            v[f"{p['image']}|{x['ref']}"].append(pl(x["sense"]))
    for f in glob.glob(str(A / "candidates" / "tiebreak-*.result.json")):
        for x in json.loads(Path(f).read_text(encoding="utf-8"))["verses"]:
            v[f"{x['image']}|{x['ref']}"].append(pl(x["sense"]))
    return v


def combine():
    idx = json.loads((A / "candidates" / "index.json").read_text(encoding="utf-8"))
    cand = json.loads((A / "candidates" / "tier2-final.json").read_text(encoding="utf-8"))
    sw = json.loads((A / "sweep" / "settled.json").read_text(encoding="utf-8"))
    # THE NUMBERING (2026-10-25): the sweep read cards' verses as the server lists them, in the Berean's numbering;
    # the candidate pass, the word data and the rulings file are MACULA's (the temple's ruling "Psa.84.5" shows as
    # Ps 84:4, "How blessed are those who dwell in Your house"). So the sweep's refs are turned into MACULA's here,
    # before the two passes are compared and before any ruling is written. The first build did not, and Ps 34:15,
    # "The eyes of the LORD are on the righteous", fell off its own card.
    moved = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8"))["moved"]
    to_mac = {b: m for m, b in moved.items()}
    sw["final"] = {f"{k.split('|')[0]}|{to_mac.get(k.split('|')[1], k.split('|')[1])}": v
                   for k, v in sw["final"].items()}
    swept = {k.split("|")[0] for k in sw["final"]}
    if SMALL:
        tier2 = {x["image"] for x in idx}
        small = sorted(swept - tier2 - DONE_BEFORE)
        idx = [{"image": i, "verses_on_card": None} for i in small]
    images = [x["image"] for x in idx]
    cv = votes_from_candidates()
    final, how = {}, {}
    for k in set(cand["final"]) | set(sw["final"]):
        img = k.split("|")[0]
        if img not in images:
            continue
        c, s = cand["final"].get(k), sw["final"].get(k)
        if s and c:
            if s["place"] == c:
                final[k], how[k] = c, "both passes"
            else:
                vs = [x for x in (pl(s["sweep"]), pl(s["confirm"]), pl(s["third"])) if x] + cv.get(k, [])
                top = collections.Counter(vs).most_common(2)
                if len(top) > 1 and top[0][1] == top[1][1]:
                    final[k], how[k] = None, "held: the readers of both passes tie"
                else:
                    final[k], how[k] = top[0][0], "pooled votes"
        elif s:
            final[k], how[k] = s["place"], ("held: three-way" if s["place"] is None else "sweep, " + s["how"])
        else:
            if img in swept and c is None:
                continue
            final[k], how[k] = c, "candidate pass"
    return idx, images, swept, final, how, cand, sw


def main():
    idx, images, swept, final, how, cand, sw = combine()
    unswept = [i for i in images if i not in swept and i not in SAYINGS]
    if unswept:
        print("NOT SWEPT and not a named saying, so not buildable yet:", unswept)
    names, words = {}, {}
    for i in images:
        cj = A / "candidates" / f"{i}.json"
        if cj.exists():
            d = json.loads(cj.read_text(encoding="utf-8"))
        else:  # a small card the candidate pass never read: its words and count from the server
            import urllib.request
            with urllib.request.urlopen(f"http://localhost:8012/api/entity-verses?id={i}", timeout=120) as r:
                d = json.load(r)
            d["name"] = (json.loads(next(l for l in open(ROOT / "ontology" / "entities" / "entities.jsonl",
                                                          encoding="utf-8") if f'"id": "{i}"' in l)) or {}).get("name")
            for x in idx:
                if x["image"] == i:
                    x["verses_on_card"] = d.get("total")
        names[i] = d.get("name") or i
        words[i] = {w["key"] for w in d.get("words") or [] if w.get("key")}
    text = {}
    sys.path.insert(0, str(ROOT / "tools"))
    from derive import BOOK
    for ln in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        if "b" in d:
            text[f"{BOOK.get(d['b'], d['b'])}.{d['c']}.{d['v']}"] = d["t"]
    moved = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8"))["moved"]
    want = {k.split("|")[1] for k in final}
    vkeys = collections.defaultdict(set)
    with gzip.open(ROOT / "out" / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for ln in f:
            n = json.loads(ln)
            if n.get("ref") in want and n.get("strong"):
                s = re.sub(r"\D", "", str(n["strong"])).lstrip("0")
                if s:
                    vkeys[n["ref"]].add(("g" if n.get("lang") == "greek" else "h") + s)

    plan, rows = {}, []
    for i in [x for x in images if x not in unswept]:
        mine = {k.split("|")[1]: p for k, p in final.items() if k.startswith(i + "|")}
        figs = sorted(r for r, p in mine.items() if p in ("figure", "both"))
        named = collections.defaultdict(list)
        for r in figs:
            for k in vkeys.get(r, set()) & words[i]:
                named[k].append(r)
        dropped = sorted(words[i] - set(named))
        held = sorted(r for r, p in mine.items() if p is None)
        on = len({r for vs in named.values() for r in vs})
        # how far to trust the verses only the sweep read: the confirmer's 10% sample of the sweep's non-figures
        smp = [v for k, v in sw["final"].items() if k.startswith(i + "|") and v["confirm"]
               and pl(v["sweep"]) in ("literal", "neither")]
        miss = [v for v in smp if pl(v["confirm"]) in ("figure", "both") and v["place"] in ("figure", "both")]
        single = sum(1 for k, v in sw["final"].items() if k.startswith(i + "|") and v["how"] == "single")
        plan[i] = {"before": next(x["verses_on_card"] for x in idx if x["image"] == i), "after": on,
                   "sample": len(smp), "sample_missed": len(miss), "single": single,
                   "figures": len(figs), "unplaced_figures": sorted(set(figs) - {r for vs in named.values() for r in vs}),
                   "literal": sum(p == "literal" for p in mine.values()), "neither": sum(p == "neither" for p in mine.values()),
                   "held": held, "named": {k: len(v) for k, v in named.items()}, "dropped": dropped}
        for k, vs in sorted(named.items()):
            rows.append({"card": i, "key": k, "action": "named", "verses": sorted(vs),
                         "decision": "plan 8.2h: the image audit, the next 58", "reader": READER, "ruling": RULING})
        for k in dropped:
            rows.append({"card": i, "key": k, "action": "drop",
                         "decision": "plan 8.2h: this word gives the card none of its figure verses", "reader": READER,
                         "ruling": RULING})

    keyed = collections.defaultdict(list)
    for i, L in (cand.get("per") or {}).items():
        for x in L.get("keyed") or []:
            keyed[i].append(x)
    mv = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8"))["moved"]
    to_mac = {b: m for m, b in mv.items()}
    for i, L in (sw.get("keyed") or {}).items():
        for x in L:  # the sweep's keyed refs are in the Berean's numbering; final is MACULA's
            if final.get(f"{i}|{to_mac.get(x[0], x[0])}") in ("figure", "both"):
                keyed[i].append(x)

    if WRITE:
        # the per-verse trail, so it outlives out/ (memory: provenance against slop): place, how, and each
        # reader's sense where the sweep read it
        trail = {}
        for k, p in final.items():
            if k.split("|")[0] in plan:
                s = sw["final"].get(k) or {}
                trail[k] = [p, how[k], s.get("sweep"), s.get("confirm"), s.get("third"), cand["final"].get(k)]
        apply(rows, plan, trail)
        return
    write_sheet(plan, names, final, how, keyed, text, moved, unswept)


def write_sheet(plan, names, final, how, keyed, text, moved, unswept):
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(58)
    tot = collections.Counter()
    for p in plan.values():
        tot.update(before=p["before"], after=p["after"], held=len(p["held"]))
    hows = collections.Counter(h for k, h in how.items() if k.split("|")[0] in plan)
    title = "the 137 smaller images" if SMALL else "the next 58 images"
    L = [f"# The image audit: {title} — one sheet", "",
         "Plan 8.2h. **Every item is \"as recommended\" unless you override it by number.** Reply \"all as recommended\", "
         "or name the items you would change.", "",
         "## What this decides", "",
         "Each image card today lists every verse of its word: \"the hand of God\" lists every \"hand\", 2,000 of "
         "them. After this, it lists the verses where the text uses the figure. **The literal cards are not touched.** "
         "The keyed identifications (the text's own \"X is Y\") are counted below but **not built**: they become "
         "relations, and get a sheet of their own.", "",
         f"**{tot['before']:,} card verses become {tot['after']:,}** across {len(plan)} cards. "
         f"**{tot['held']} are held:** on neither card, because the readers tied or split three ways. Unresolved is "
         "better than wrong.", "",
         "## How each verse was placed", "",
         "| basis | verses |", "|---|---|"]
    for h, n in hows.most_common():
        L.append(f"| {h} | {n:,} |")
    L.append("")
    if SMALL:
        L += ["- **Each card was swept whole and every verse confirmed:** a reader on every verse, a blind confirmer "
              "on every verse too, and a third reader where the two split. Several small cards shared one reader's "
              "file, each verse naming its own card, so 137 cards took 51 sweep readers and 77 confirmers.",
              f"- **Why every verse, not a 10% sample as on the larger cards:** on these cards the sample found 6% of "
              f"the sweep's non-figures were figures, against 1% on the larger ones. Confirming the rest found "
              f"{sum(p['sample_missed'] for p in plan.values())} such figures in all, now on their cards.",
              "- **These cards had no candidate pass.** The 58 larger cards showed why: the sweep found thousands of "
              "figures that starting from similes and metaphors had missed."]
    else:
        L += ["- **Two passes read these cards.** The candidate pass started from what already marked a figure (a "
              "simile, a metaphor, a citation). The sweep then read every verse of the card.",
              "- **The sweep found 3,092 figures on these cards that the candidate pass never had.** \"The hand of "
              "the LORD\" is a figure in the word itself; nothing marks it.",
              "- **Where the two passes read a verse and differ,** every reader's vote is pooled. A tie is held."]
    L += [] if SMALL else [
          "- **\"Sweep, single\"** is a verse only the sweep read: a literal or unused verse outside the blind "
          "confirmer's 10% sample. The sample measures what those hide. Across all cards, "
          f"{sum(p['sample_missed'] for p in plan.values())} of the {sum(p['sample'] for p in plan.values())} sampled "
          "non-figures turned out, after a third reader, to be figures. At that rate the "
          f"{sum(p['single'] for p in plan.values()):,} single-read verses hide about "
          f"{round(sum(p['single'] for p in plan.values()) * sum(p['sample_missed'] for p in plan.values()) / max(1, sum(p['sample'] for p in plan.values())))} "
          "figures, which the card would miss. The column \"missed in sample\" gives each card's count; the Mac's later "
          "passes are where they get found."]
    if not SMALL:
        L.append("- **Four cards are named sayings, not broad figures:** the two houses, the sower, the good tree, the "
                 "city on a hill. Their candidates are the figure, and their other \"house\", \"seed\" or \"city\" "
                 "verses go.")
    L.append("")
    if unswept:
        L += [f"**Not on this sheet, still being swept:** {', '.join(unswept)}.", ""]
    L += ["## The cards", "", "| # | card | verses now | after | held | missed in sample | words named / dropped |",
          "|---|---|---|---|---|---|---|"]
    order = sorted(plan, key=lambda i: -plan[i]["before"])
    for n, i in enumerate(order, 1):
        p = plan[i]
        L.append(f"| {n} | {names[i]} (`{i}`) | {p['before']:,} | {p['after']:,} | {len(p['held'])} | "
                 + (f"{p['sample_missed']} of {p['sample']}" if p["sample"] else "—")
                 + f" | {len(p['named'])} / {len(p['dropped'])} |")
    L += ["", "## Each card, with a spot-check", "",
          "Three verses the card keeps and two it lets go, chosen at random, so you can see the reading is right "
          "without reading thousands. If a spot-check looks wrong, override the item and the card waits.", ""]
    for n, i in enumerate(order, 1):
        p = plan[i]
        mine = {k.split("|")[1]: v for k, v in final.items() if k.startswith(i + "|")}
        keep = sorted(r for r, v in mine.items() if v in ("figure", "both"))
        go = sorted(r for r, v in mine.items() if v in ("literal", "neither"))
        unread = p["before"] - p["after"] - p["literal"] - p["neither"] - len(p["held"])
        L += [f"### {n}. {names[i]} — {p['before']:,} → {p['after']:,}", "",
              f"**Recommended:** the card keeps the {p['after']:,} verses where the figure is used. "
              f"{p['literal']:,} literal and {p['neither']:,} other verses go"
              + (f", as do {unread:,} verses of the word that are not this saying" if i in SAYINGS and unread > 0 else "")
              + (f"; {len(p['held'])} held ({', '.join(moved.get(h, h) for h in p['held'][:12])}"
                 f"{' …' if len(p['held']) > 12 else ''})" if p['held'] else "")
              + ".", ""]
        if keyed.get(i):
            L.append(f"*Keyed identifications, for their own sheet: {len(keyed[i])}.*")
            L.append("")
        for label, pool in (("keeps", keep), ("lets go", go)):
            for r in rnd.sample(pool, min(3 if label == "keeps" else 2, len(pool))):
                t = text.get(moved.get(r, r), "")
                L.append(f"- *{label}* **{moved.get(r, r)}**: {t}")  # shown in the Berean's number
        L.append("")
    SHEET.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{len(plan)} cards: {tot['before']:,} -> {tot['after']:,} verses, {tot['held']} held -> {SHEET}")
    print(dict(hows.most_common()))


def apply(rows, plan, trail):
    rp = ROOT / "ontology" / "card-repairs.jsonl"
    raw = rp.read_text(encoding="utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    cards = set(plan)
    kept, replaced = [], []
    for ln in raw.split(nl):
        if not ln.strip():
            continue
        (replaced if json.loads(ln)["card"] in cards else kept).append(ln)
    rp.write_text(nl.join(kept + [json.dumps(r, ensure_ascii=False) for r in rows]) + nl, encoding="utf-8", newline="")
    (ROOT / RULING).write_text(json.dumps({
        "sheet": str(SHEET.relative_to(ROOT)).replace("\\", "/"), "ruled_by": "Doug", "date": "2026-10-24",
        "answer": ("go ahead and start on the cut but provide the page for me with a guide with what changes as I "
                   "want to do side by sides with the current deployed site as you prepare (2026-10-25)" if SMALL
                   else "as recommended on the sheet"), "placement": plan,
        "verses_key": ["placement (None = held)", "how", "sweep reader", "blind confirmer", "third reader",
                       "candidate pass's settled placement"],
        "verses": trail, "repairs_replaced": [json.loads(x) for x in replaced]},
        ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"written: {len(rows)} repair rows on {len(cards)} cards (replacing {len(replaced)}) -> {RULING}")


if __name__ == "__main__":
    main()
