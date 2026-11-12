"""What does each verse state about the thing? For the weakest object cards (weak_cards.py, 2026-11-07).

The offerings, the ark and the other gods are named in 60 to 120 verses each and their cards cite one to eight. Each
verse that names one is read with a single question: does it state something about this thing beyond naming it, and
if so who does what with it (brings, burns, carries, serves, makes, sets up, puts away) and to what end. The answers
are candidates; Claude turns the stated ones into relations, each with its verse, and validates to 0.

The Mac reads every verse. Nothing goes to DeepSeek: the verses about other gods and the offerings name the LORD in
almost every line, and DeepSeek gets no divine-person rows.

    python tools/meaning/object_relations.py build   -> out/orchestra-intake/20o-object-relations/
"""
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))

NAME = "20o-object-relations"   # below 21-renderings-check: the Mac's runner takes names in order, so this runs first
OPTIONS = {"temperature": 0, "num_ctx": 4096}
SEED = 20261108
# card -> the phrases that name it in the Berean (singular and plural both match)
CARDS = {
    "other_gods": ["other gods", "foreign gods", "strange gods"],
    "strange_gods": ["foreign gods", "foreign god"],
    "grain_offering": ["grain offering"],
    "sin_offering": ["sin offering"],
    "burnt_offerings": ["burnt offering"],
    "peace_offering": ["peace offering"],
    "drink_offering": ["drink offering"],
    "ark_of_the_covenant": ["ark of the covenant", "ark of god", "ark of the lord", "ark of the testimony"],
}

BRIEF = """You read Bible verses (the Berean Standard Bible) and say what each verse states about one THING, marked
«like this».

Answer each with ONE line of JSON:
{"id": "...", "verdict": "...", "who": "...", "act": "...", "purpose": "...", "words": "...", "why": "..."}

verdict:
- "stated": the verse says something happens to the thing or is done with it, or what it is for: someone brings,
  offers, burns, carries, makes, sets up, serves, worships, puts away, captures or returns it; or it is for
  atonement, for a pleasing aroma, for a sin.
- "not_said": the verse only names it (a list of offerings, a heading, a count) and states nothing done with it.
- "unclear": you cannot tell.

who: the doer, as the verse names them ("the priest", "Israel", "the Philistines", "Solomon"; "" if none).
act: the verb, plain ("offers", "burns", "carries", "serves", "puts away", "captures").
purpose: what it is for, in the verse's words ("" if none).
words: the verse's words that say it, copied exactly.
why: one short reason.

Worked examples (not from the items):
- "The priest is to burn the «grain offering» on the altar" -> stated, who "the priest", act "burns".
- "You shall have no «other gods» before Me" -> stated, who "you" (Israel), act "is not to have".
- "one male goat for a «sin offering», to make atonement for you" -> stated, act "is offered", purpose "to make
  atonement for you".
- "This is the law of the «grain offering»" -> not_said.
"""


def build():
    import server as S
    d = S.load()
    items, n = [], 0
    for card, phrases in CARDS.items():
        pat = re.compile(r"\b(" + "|".join(re.escape(p) for p in phrases) + r")(?:s|es)?\b", re.I)
        for (b, c, v), text in d["verses"].items():
            m = pat.search(text or "")
            if not m:
                continue
            n += 1
            ref = f"{b}.{c}.{v}"
            items.append({"key": f"{card}:{ref}", "id": f"o{n}", "card": card, "ref": ref,
                          "claim": f"What this verse states about the {phrases[0]}.",
                          "verse": text[:m.start()] + "«" + m.group(0) + "»" + text[m.end():],
                          "context": [f"THING: the {phrases[0]} (also: {', '.join(phrases[1:]) or 'none'})"]})
    random.Random(SEED).shuffle(items)
    out = ROOT / "out" / "orchestra-intake" / NAME
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{NAME}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "object_relations"}}) + "\n")
        for it in items:
            f.write(json.dumps({"key": it["key"], "messages": messages(it)}, ensure_ascii=False) + "\n")
    spec = {"pass": NAME, "mac_job": f"{NAME}.jsonl", "priority": 30,
            "flag": {"verdict_in": []},             # the Mac alone: no divine-person rows to DeepSeek
            "deepseek": {"budget_usd": 0},          # and the budget check refuses every call, whatever is flagged
            "allowed_fields": ["id", "claim", "ref", "verse", "context"]}
    (out / f"{NAME}.pass.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out / "brief.md").write_text(BRIEF, encoding="utf-8", newline="\n")
    with open(out / "items.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"{len(items)} verses across {len(CARDS)} cards -> {out}")


# the Mac's act -> a type the vocabulary already holds (ontology/schema/relationship_types.yaml); nothing new coined
ACTS = {"offered": ("offer", "offered", "offers", "offering", "present", "presented", "presents", "presenting",
                    "sacrifice", "sacrificed", "sacrificing", "sacrifices"),
        "carried": ("carry", "carried", "carrying", "carries"),
        "took": ("captured", "capture", "seized"),   # not "took": the priests took up the ark (Josh 6:12), they lifted it
        "put_away": ("put away", "get rid of", "removed", "remove", "put aside", "threw away"),
        # approved 2026-11-08 (P-2026-11-07-3)
        "served": ("serve", "served", "serves", "serving", "serve and worship", "served and worshiped"),
        "worshiped": ("worship", "worshiped", "worshipped", "worships", "worshiping", "bowed down to", "bow down to")}
# not "made": "having made the sin offering" (Lev 9:22) is performing it, and `made` is making a thing


def apply():
    """The stated rows whose doer the verse itself names and the graph holds once, whose act is a vocabulary type,
    and whose quoted words are the verse's: relations, each with its verse. The rest stay candidates (a pronoun's
    doer needs its antecedent read; "serve" and "worship" have no type yet). Every row's fate goes to provenance."""
    import yaml
    sys.path.insert(0, str(ROOT / "src"))
    types = yaml.safe_load((ROOT / "ontology" / "schema" / "relationship_types.yaml").read_text(encoding="utf-8"))
    types = types.get("types", types)
    ents = {}
    for path in sorted((ROOT / "ontology" / "entities").glob("*.jsonl")):    # the offerings are aggregate hubs
        for line in open(path, encoding="utf-8"):
            e = json.loads(line)
            if e.get("id"):
                ents.setdefault(e["id"], e)
    by_name = {}
    for e in ents.values():
        for n in [e.get("name")] + list(e.get("aka") or []):
            if n:
                by_name.setdefault(re.sub(r"^the ", "", n.lower().strip()), set()).add(e["id"])
    items = {json.loads(l)["key"]: json.loads(l) for l in open(ROOT / "out" / "orchestra-intake" / NAME / "items.jsonl",
                                                               encoding="utf-8")}
    rels, trail = [], []
    for line in open(ROOT / "out" / "orchestra-results" / f"{NAME}.jsonl", encoding="utf-8"):
        r = json.loads(line)
        a = json.loads(r["content"])
        it = items[r["key"]]
        plain = it["verse"].replace("«", "").replace("»", "")
        fate = None
        act = (a.get("act") or "").lower().strip()
        typ = next((t for t, words in ACTS.items() if act in words), None)
        who = re.sub(r"^the ", "", (a.get("who") or "").lower().strip())
        ids = by_name.get(who, set())
        if a.get("verdict") != "stated":
            fate = "not stated"
        elif not typ:
            fate = f"no type for '{act}'"
        elif not who or who in ("he", "she", "they", "you", "we", "i", "it", "him", "them", "man", "a man", "anyone",
                                "people", "woman", "someone", "one", "each", "everyone", "whoever"):
            fate = "doer is a pronoun or unnamed"       # "a man" (Lev 22:21) matched the man who wrestled with Jacob
        elif who not in plain.lower():
            fate = "doer not named in the verse"
        elif len(ids) != 1:
            fate = f"doer '{who}' matches {len(ids)} entities"
        elif (a.get("words") or "").replace("«", "").replace("»", "") not in plain:
            fate = "quoted words not in the verse"
        elif re.search(r"\b(not|never|no|nor|neither|if)\b", a.get("words") or "", re.I):    # and "if you prepare"
            fate = "negated"                   # Naaman's "will never again make a burnt offering" (2 Kgs 5:17)
        else:
            src = next(iter(ids))
            spec = types.get(typ) or {}
            if ents[src].get("type") not in (spec.get("src_type") or [ents[src].get("type")]) or \
                    (ents.get(it["card"]) or {}).get("type") not in (spec.get("dst_type") or ["?"]):
                fate = f"{typ} does not take {ents[src].get('type')} -> {(ents.get(it['card']) or {}).get('type')}"
            else:
                b, c, v = it["ref"].split(".")
                rels.append({"certainty": "explicit", "dst": it["card"], "note": a["words"].replace("«", "").replace("»", ""),
                             "refs": [f"{b} {c}:{v}"], "source": "object-relations-2026-11-07", "src": src, "type": typ})
                fate = "applied"
        trail.append({"key": r["key"], "answer": a, "fate": fate})
    # ONE RELATION A DOER, ACT AND THING, its verses merged (the validator's rel.duplicate: the Levites carried the
    # ark six times over); and none the graph already holds in another file, whose citation stands
    have = set()
    for path in (ROOT / "ontology" / "relations").glob("*.jsonl"):
        if path.name.startswith("object-relations-"):
            continue
        for line in open(path, encoding="utf-8"):
            if line.strip():
                x = json.loads(line)
                have.add((x.get("src"), x.get("type"), x.get("dst")))
    merged = {}
    for x in rels:
        k = (x["src"], x["type"], x["dst"])
        if k in have:
            continue
        if k in merged:
            merged[k]["refs"] += [r for r in x["refs"] if r not in merged[k]["refs"]]
        else:
            merged[k] = dict(x)
    # AND NONE THAT IS A CHARACTER'S WORDS: "Aaron's sons shall present it" (Lev 6:14) is the LORD's instruction, not
    # the narrator's report; the graph's own rule holds them (preflight's quoted-speech test found four)
    sys.path.insert(0, str(ROOT / "tools" / "meaning"))
    from hold_quoted_relations import categories, to_hold
    from quoted import berean_quotes
    cat, (quotes, _texts) = categories(), berean_quotes()
    out = [x for x in merged.values() if not to_hold(x, cat, quotes)]
    held = [x for x in merged.values() if x not in out]
    for t in trail:
        if t["fate"] == "applied" and any(x["dst"] == t["key"].split(":")[0] and x["src"] in json.dumps(t["answer"]).lower()
                                          for x in held):
            t["fate"] = "applied, then held: speech"
    (ROOT / "ontology" / "relations" / "object-relations-2026-11-07.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out), encoding="utf-8", newline="\n")
    prov = ROOT / "ontology" / "provenance" / "meaning" / "object-relations-2026-11-07.jsonl"
    prov.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in trail), encoding="utf-8", newline="\n")
    import collections
    print(len(out), "relations;", collections.Counter(t["fate"].split(" '")[0] for t in trail).most_common(12))


def messages(it):
    return [{"role": "system", "content": BRIEF},
            {"role": "user", "content": f"id: {it['id']}\n{it['context'][0]}\nVERSE ({it['ref']}): {it['verse']}"}]


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        build()
    elif sys.argv[1:2] == ["apply"]:
        apply()
    else:
        print(__doc__)
