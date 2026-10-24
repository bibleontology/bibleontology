"""Discrete events: what the graph can pull out now, measured.

2026-09-28: is there enough here to pull out discrete events? Events will
later form the building blocks for more coarse-grained events, and will also
matter greatly in pattern mining; event and narrative patterns will be among
the most significant, so events should be built up from discrete to
significant. The recording of the actual event and the later reference to that
same event are two different things: John 3:14 is a reference and not a new
event description.

A DISCRETE EVENT is one clause that says something happened. From the
structure graph and the layers on it:
    what        the verb, and its situation type (WordNet verb file via
                the word graph's categories: motion, contact, communication …)
    who / what  the clause's roles (s, o, io), joined to records by
                out/mentions.jsonl.gz
    where       a prepositional role
    whether     REALIS by the form: an assertion, not negated, not inside a
                condition, not a question, in a narrative or past form
    who says    the NARRATOR, or someone REPORTING it inside a speech turn
    order       the narrative's `then` chain

and every clause falls in one of:
    narrated    realis, told by the narrator — an event RECORDED
    reported    realis, inside someone's speech — a report, OR a reference
                back to an event recorded elsewhere (Jhn 3:14) — to be told
                apart, never counted as a new event
    projected   future or prophetic form (weqatal, yiqtol, Greek future)
    other       commands, questions, conditions, negations, states

    python tools/meaning/events.py
"""
import collections
import gzip
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "builder"))
from source import norm  # noqa: E402

PAST_HE = {"wayyiqtol", "qatal"}
FUTURE_HE = {"weqatal", "yiqtol"}


def rows(p):
    for line in gzip.open(p, "rt", encoding="utf-8"):
        yield json.loads(line)


def main():
    nodes = {n["id"]: n for n in rows(OUT / "structure-nodes.jsonl.gz")}
    edges = list(rows(OUT / "structure-edges.jsonl.gz"))
    mention = {m["occurrence"]: m["record"]
               for m in rows(OUT / "mentions.jsonl.gz")}
    sit, cat = {}, {}
    for r in rows(OUT / "meaning-categories.jsonl.gz"):
        if r.get("verdict") not in ("decided", "leaning"):
            continue
        if r.get("pos") == "verb":
            sit[(r["lang"], r["lemma"])] = r["class"]
        elif r.get("pos") == "noun":
            cat[(r["lang"], r["lemma"])] = r["class"]
    ents = {}
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl",
                     encoding="utf-8"):
        e = json.loads(line)
        ents[e["id"]] = e["name"]
    roles = collections.defaultdict(lambda: collections.defaultdict(list))
    neg, in_turn, in_cond, then_next = set(), set(), set(), {}
    for e in edges:
        if e.get("clause_role") and e["src"].split("#")[-1].startswith("ct"):
            roles[e["src"]][e["type"]].append(e)
        if e["type"] == "neg":
            neg.add(e["src"].replace("#ct", "#cl"))
        if e["type"] == "part" and "#turn" in e["src"]:
            in_turn.add(e["dst"])
        if e["type"] in ("condition", "consequence"):
            in_cond.add(e["dst"])
        if e["type"] in ("then", "sequence"):
            then_next[e["src"]] = e["dst"]
    # a clause nested in a reported part is reported too
    def reported(cid):
        seen = 0
        while cid and seen < 8:
            if cid in in_turn:
                return True
            cid = (nodes.get(cid) or {}).get("nested_in")
            seen += 1
        return False

    def who(nid):
        return mention.get(nid)

    stats = collections.Counter()
    fill = collections.Counter()
    samples = collections.defaultdict(list)
    for cid, c in nodes.items():
        if not c.get("clause") or not c.get("verb_lemma"):
            continue
        lang, mood = c.get("lang"), c.get("verb_mood")
        tense = c.get("verb_tense")
        force = c.get("upper_force")
        if force != "assertion" or cid in neg or cid in in_cond:
            kind = "other"
        elif (lang == "hebrew" and mood in FUTURE_HE) or tense == "future":
            kind = "projected"
        elif (lang == "hebrew" and mood in PAST_HE) or (
                lang == "greek" and mood == "indicative" and
                tense in ("aorist", "imperfect", "pluperfect")):
            kind = "reported" if reported(cid) else "narrated"
        else:
            kind = "other"
        stats[(lang, kind)] += 1
        if kind != "narrated":
            continue
        ct = cid.replace("#cl", "#ct")
        r = roles[ct]
        agent = next((who(x["dst"]) for x in r.get("s", [])), None)
        patient = next((who(x["dst"]) for x in r.get("o", []) +
                        r.get("io", [])), None)
        place = next((x for x in r.get("pp", [])), None)
        st = sit.get((lang, norm(c.get("verb_lemma"))))
        # the KIND of each participant, where its identity is unknown: the
        # head word's category (a noun's WordNet class via its glosses), or
        # the record's type when it is joined — what a pattern matches on
        def kind(es):
            for x in es:
                w = nodes.get(x["dst"]) or {}
                if who(x["dst"]):
                    return "record"
                k = cat.get((lang, norm(w.get("lemma") or "")))
                if k:
                    return k
            return None
        ak = kind(r.get("s", []))
        pk = kind(r.get("o", []) + r.get("io", []))
        has_o = bool(r.get("o") or r.get("io"))
        fill["narrated"] += 1
        fill["agent: a record, or at least its kind"] += bool(ak)
        fill["object (where there is one): a record or its kind"] += \
            bool(pk) if has_o else 0
        fill["_with object"] += has_o
        fill["agent joined to a record"] += bool(agent)
        fill["patient/recipient joined"] += bool(patient)
        fill["has a prepositional role (place, direction …)"] += bool(place)
        fill["situation type known"] += bool(st)
        fill["in the then-chain"] += cid in then_next or cid in \
            then_next.values()
        if len(samples[lang]) < 400:
            samples[lang].append((cid, c, agent, patient, st))

    print("EVERY CLAUSE WITH A VERB, by what it is:")
    for lang in ("hebrew", "greek"):
        tot = sum(v for (l, _), v in stats.items() if l == lang)
        print(f"  {lang}: " + ", ".join(
            f"{k} {stats[(lang, k)]:,} ({stats[(lang, k)] / tot:.0%})"
            for k in ("narrated", "reported", "projected", "other")))
    n = fill["narrated"]
    print(f"\nNARRATED EVENTS ({n:,}) — how complete:")
    for k, v in fill.items():
        if k in ("narrated", "_with object"):
            continue
        d = fill["_with object"] if k.startswith("object") else n
        print(f"  {k:52} {v / d:5.0%}")
    rng = random.Random(9)
    print("\nSAMPLE narrated events:")
    for lang in ("hebrew", "greek"):
        for cid, c, agent, patient, st in rng.sample(samples[lang], 6):
            print(f"  {cid.split('#')[0]:10} {c['text'][:48]:48} "
                  f"| {ents.get(agent, '-') if agent else '-'} "
                  f"-> {ents.get(patient, '-') if patient else '-'} "
                  f"| {st or '?'}")


if __name__ == "__main__":
    main()
