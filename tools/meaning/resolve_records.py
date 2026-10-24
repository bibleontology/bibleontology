"""THE RESOLUTION LAYER: each clause's subject and object to a record (plan
2.17, step 1; approved 2026-10-18).

A clause whose verb has a subject and an object that both name records is a
candidate relation between them. Each end is resolved, in order, by:
  named      a word the mentions layer names (a person, a place)
  referent   a pronoun or unstated subject followed through the sweep's
             refers_to (the builder's where the sweep said nothing)
  divine     the ruling of 2026-10-18 ("names only, rest held"): יהוה and
             singular θεός are God; אֱלֹהִים only with a singular verb;
             κύριος, πατήρ and plural אֱלֹהִים are HELD, never guessed
  card       a concept word, to the card NAMED by that word (ruled: "the card
             named by the word"): κόσμος -> world; a phrase card ("the light
             of the world") never takes a single word
Unresolved is recorded as such, with why.

    python tools/meaning/resolve_records.py   -> out/meaning/clause-records.jsonl, a tally
"""
import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "meaning" / "clause-records.jsonl"
GOD = "god"
LORD_NAMES = {"יְהוָה", "יהוה"}
THEOS = {"θεός"}
ELOHIM = {"אֱלֹהִים"}
HELD_DIVINE = {"κύριος", "πατήρ", "אֲדֹנָי"}
# by Strong's number: the first try by lemma missed כֹּל (Gen 25:5), MACULA
# ordering its marks differently from the typed word
QUANT = {"h3605", "g3956", "g537"}
# divine persons, and the cards that mix them with others: never reached by a
# pointer chain or a card rule, only by a ruling made by hand, record by record.
# God by the names rule above is the ruling of 2026-10-18
DIVINE_HOLD = {"god", "holy_ghost", "the_father", "jesus", "spirit", "spirit_of_god"}


def jl(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def key_of(n):
    s = re.sub(r"\D", "", str(n.get("strong") or "")).lstrip("0")
    return (("g" if n.get("lang") == "greek" else "h") + s) if s else None


PAST_OR_PRESENT = "past or present (by form)"


def time_of(mood, tense):
    """WHETHER THE VERB'S FORM SAYS A THING HAPPENED (1.2.0 step 5, 2026-10-20).
    Step 5's command example found 217 of 1,098 live verb statements whose form
    does not say so, every one shown in the past tense as a fact: "God put
    enmity" for Gen 3:15's "I will put", "Jesus saved the world" for John
    12:47's "that I might save". The Greek future and the subjunctive and
    optative say it did not (yet); the Hebrew yiqtol and weqatal leave it to
    the context: future, command, habit ("He tests the righteous", Ps 11:5) or,
    in poetry, past ("You kept me", 2 Sam 22:44). The form decides only where
    it can; the rest waits for a reading of its time."""
    mood, tense = (mood or "").lower(), (tense or "").lower()
    if tense == "future":
        return "future (by form)"
    # THE COMMITTEE'S SCHOLAR, second sitting (2026-10-20): a participle has no
    # time of its own and an infinitive takes its time from the verb that
    # governs it, so neither says the thing happened. "God sent Elijah" (Mal
    # 4:5, a participle: "I am sending") and "God destroyed Israel" (Deut 28:48,
    # an infinitive in a curse) were shown as past facts
    if mood.startswith("participle"):
        return "participle: no time of its own"
    if mood.startswith("infinitive"):
        return "infinitive: its time is its governing verb's"
    if mood in ("subjunctive", "optative"):
        return f"{mood}: not said to have happened (by form)"
    if mood in ("yiqtol", "weqatal"):
        return f"{mood}: not decided by form"
    return PAST_OR_PRESENT


def main():
    nodes, edges = {}, collections.defaultdict(list)
    for d in jl(ROOT / "out" / "placeholder-nodes.jsonl.gz"):
        nodes[d["id"]] = d
    refers, possessed_pairs, pointed = {}, set(), set()
    possessed = possessed_pairs
    for e in jl(ROOT / "out" / "placeholder-edges.jsonl.gz"):
        edges[e["src"]].append(e)
        if e["type"] == "refers_to":
            refers[e["src"]] = e["dst"]
        elif e["type"] == "possessor" or (e["type"] == "qualifier" and e.get("rel") in ("whose", "of")):
            # "their father" (Gen 37:4): the builder stores the suffix as its own
            # node, joined by a qualifier "of"; "the gates of Zion" (Ps 87:2) the
            # same way. Kept as candidates here; only an "of" a pronoun or a
            # name makes the noun a particular one (checked below)
            possessed.add((e["src"], e["dst"]))
        if e["type"] == "qualifier" and e.get("rel") == "demonstrative":
            pointed.add(e["src"])
    for d in jl(ROOT / "out" / "sweep-layer.jsonl.gz"):
        if d.get("type") == "refers_to":
            if d.get("action") == "remove":
                refers.pop(d["src"], None)
            else:
                refers[d["src"]] = d["dst"]
    # a noun is a particular one when it is "of" a pronoun or a name
    # (nouns only: a pronoun with an "of" is unresolved for its own reason)
    of_any = {s for s, d in possessed_pairs}
    possessed = {s for s, d in possessed_pairs
                 if (nodes.get(s) or {}).get("class") == "noun"
                 and ((nodes.get(d) or {}).get("class") in ("pron", "pronoun") or (nodes.get(d) or {}).get("proper")
                      or (nodes.get(d) or {}).get("type") == "proper" or (nodes.get(d) or {}).get("implicit"))}
    mention = {d["occurrence"]: d["record"] for d in jl(ROOT / "out" / "mentions.jsonl.gz")
               if "occurrence" in d and not str(d.get("how", "")).startswith("refers_to")}
    ents = {}
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        e = json.loads(line)
        ents[e["id"]] = e
    # a concept word -> the card NAMED by it (one word, the word's own gloss)
    named_card = {}
    # A NAME TWO CARDS SHARE NAMES NEITHER (the scholar, 2026-10-19): built by
    # overwriting, "faith" went to `fidelity` (one citation) over `faith` (16),
    # "covenant" to `league`, "people" to `souls`; 47 such names
    by_name = collections.defaultdict(list)
    for eid, e in ents.items():
        if e.get("type") == "concept" and re.fullmatch(r"[A-Za-z]+", e["name"].strip()):
            by_name[e["name"].strip().lower()].append(eid)
    one_word = {nm: ids[0] for nm, ids in by_name.items() if len(ids) == 1}
    # A CARD'S WORDS ARE THE ONES A READER IS SHOWN (tools/meaning/membership.py,
    # plan 4.8 step 0(a)): before, every anchor, 3,114 of them hidden from
    # readers on 1,107 cards, and none of the root or family words readers see
    sys.path.insert(0, str(ROOT / "tools" / "meaning"))
    import membership as M
    lemmas = {}
    for d in nodes.values():
        if d.get("word"):
            k = key_of(d)
            if k and k not in lemmas:
                lemmas[k] = d.get("lemma")
    fp = ROOT / "out" / "word-families.json"
    families = (json.loads(fp.read_text(encoding="utf-8")).get("families") or {}) if fp.exists() else {}
    rix = M.root_index(lemmas)
    shown = M.anchors(jl(ROOT / "out" / "concept-anchors.jsonl.gz"))
    # a word a ruled repair limits to named verses is not the card's word
    # everywhere it occurs, so it never resolves to the card here (2026-10-20)
    card_words = {eid: {k for k, w in M.words(base, lemmas, families, rix, card=eid).items()
                        if not str(w.get("only") or "").startswith("named")}
                  for eid, base in shown.items() if eid in ents}
    for eid, ks in card_words.items():
        nm = ents[eid]["name"].strip().lower()
        if one_word.get(nm) != eid:
            continue                                 # a phrase card never takes a single word
        for k in ks:
            named_card.setdefault(k, set()).add(eid)

    # IMAGE CARDS FIRST (2026-10-19: the image handling must be respected. The
    # house in Matthew 7:24-25 is different from a random house):
    # a word in a verse an image card cites, or in the three verses after it in
    # the same chapter (the image's telling runs on: "that house", 7:25), that
    # is among the image card's own words, is the image, ahead of every
    # "particular one" test below. "His house" in 7:24 is possessed, and still
    # the parable's house.
    sys.path.insert(0, str(ROOT / "tools"))
    from derive import BOOK
    from export_claims import verses as vlist
    image_at = collections.defaultdict(set)              # (verse, key) -> image ids
    img_words = {eid: ks for eid, ks in card_words.items() if ents[eid].get("type") == "image"}
    for iid, keys in img_words.items():
        for ref in ents[iid].get("refs") or []:
            for v in vlist(ref):
                b, c, n = v.rsplit(".", 2)
                b = BOOK.get(b, b)
                for k in keys:
                    for d in range(4):
                        image_at[(f"{b}.{c}.{int(n) + d}", k)].add(iid)

    # THE RELEASE (2026-10-19): words that reach God or Jesus through a
    # pointer chain, released as a class where no seat of the panel of eleven
    # objected in two passes (ontology/provenance/sweep/divine-releases-*.json)
    released = set()
    for p_ in sorted((ROOT / "ontology" / "provenance" / "sweep").glob("divine-releases-*.json")):
        released |= {x["word"] for x in json.loads(p_.read_text(encoding="utf-8"))["released"]}

    def resolve(x, verb, depth=0, rel=None):
        if not x or depth > 6:
            return None, "none"
        if rel is None:
            rel = x in released
        n = nodes.get(x) or {}
        # (checked before the mentions too, which could name "our god" God)
        if n.get("lemma") in (THEOS | ELOHIM) and x in of_any:
            return None, "held: a god of someone or something"
        if x in mention:
            return mention[x], "named"
        for i in n.get("w") or []:
            m = mention.get(f"{n.get('ref')}#w{i}")
            if m:
                return m, "named"
        lem = n.get("lemma")
        # A DIVINE WORD WITH AN "OF" IS HELD, before the names rule (the
        # committee's scholar, 2026-10-19): "our god has given Samson" (Judg
        # 16:23) is Dagon, and "the god of this age" (2 Cor 4:4) is disputed;
        # both had resolved to God. "The God of Israel" is held with them:
        # unresolved is better than wrong, and the divine records are decided by hand
        if (lem in LORD_NAMES or lem in THEOS or lem in ELOHIM) and x in of_any and lem not in LORD_NAMES:
            return None, "held: a god of someone or something"
        if lem in LORD_NAMES or (lem in THEOS and n.get("number") != "plural"):
            return GOD, "divine"
        if lem in ELOHIM:
            return (GOD, "divine") if (verb or {}).get("number") == "singular" else (None, "held: אֱלֹהִים, plural verb")
        if lem in HELD_DIVINE:
            return None, f"held: {lem}"
        if x in refers:
            r, how = resolve(refers[x], verb, depth + 1, rel)
            # NO DIVINE PERSON THROUGH A POINTER CHAIN (the scholar, 2026-10-19:
            # 1 John 5:16 "He will give life" -- God, or the one who prays? --
            # had been settled by the chain). Held for a ruling, per record, unless
            # a ruling released the word
            if r in DIVINE_HOLD and r in ("god", "jesus") and rel:
                return r, "referent (released by Doug's ruling)"
            if r in DIVINE_HOLD:
                return None, f"held: {r} through a referent"
            # the end is labelled by what it reached, so the ends check sees a
            # card however it was reached (295 had skipped it as "referent")
            if r and how in ("card", "image"):
                return r, how + " via referent"
            return r, ("referent" if r and how == "named" else how)
        k = key_of(n) if n.get("word") else None
        imgs = image_at.get((n.get("ref"), k)) or set()
        if len(imgs) == 1:
            return next(iter(imgs)), "image"
        if len(imgs) > 1:
            return None, "several images"
        # A POSSESSED NOUN IS A PARTICULAR PERSON OR THING, not the concept:
        # "their father loved Joseph" (Gen 37:4) is Jacob, and resolved to the
        # card "father" in the first love pilot (2026-10-19)
        if x in possessed:
            return None, "possessed: a particular one, not the concept"
        # so is a noun with a demonstrative ("that house", "these words")
        if x in pointed:
            return None, "demonstrative: a particular one, not the concept"
        # "all" is a quantity, not a concept ("Abraham gave all", Gen 25:5)
        if k in QUANT:
            return None, "quantifier"
        cards = named_card.get(k) or set()
        if len(cards) == 1:
            c = next(iter(cards))
            # the "spirit" card held demons and the Holy Spirit together (Mark
            # 1:24, John 16:14); every spirit card end is held for a ruling
            if c in DIVINE_HOLD:
                return None, f"held: the {c} card"
            return c, "card"
        return None, "unnamed" if not cards else "several cards"

    def chain(x):
        """The pointer chain from a word to where it ends: the evidence a reader
        needs for a held divine end (B4, 2026-10-19: run them by the
        committee of 11)."""
        out = [x]
        while out[-1] in refers and len(out) < 8 and refers[out[-1]] not in out:
            out.append(refers[out[-1]])
        return out

    def end(x, r, how):
        d = {"node": x, "record": r, "how": how}
        if how.startswith("held:") and "through a referent" in how:
            d["chain"] = [{"node": c, "ref": (nodes.get(c) or {}).get("ref"), "text": (nodes.get(c) or {}).get("text"),
                           "lemma": (nodes.get(c) or {}).get("lemma")} for c in chain(x)]
        return d

    # THE GATE (plan 2.18, approved 2026-10-19): what the clause's own grammar
    # already says is not judge work. 291 of 378 command-form candidates had
    # been rejected by judges at a cost, and Gen 12:2 "be a blessing" passed
    # four judgments. The modality is RECORDED, from the form, and a gated
    # candidate is kept with its reason, never deleted. Where the form does
    # not mark it (Hebrew legal yiqtol, the Greek future as command) the form
    # says "stated" and only a reading can say otherwise.
    negated = {e["src"] for es in edges.values() for e in es if e["type"] == "neg"}
    PASSIVE_STEMS = {"niphal", "pual", "hophal", "hothpaal"}

    def modality(c, ctid):
        f, mood, person = c.get("upper_force"), c.get("verb_mood"), str(c.get("verb_person") or "")
        if f == "question":
            m = "asked"
        elif f == "directive":
            if mood == "cohortative" or (mood == "subjunctive" and person.startswith("first")):
                m = "promised" if mood == "cohortative" else "urged"
            elif mood == "optative":
                m = "wished"
            elif mood == "jussive":
                m = "commanded or wished"
            else:
                m = "commanded"
        elif f == "nonfinite":
            m = "nonfinite"
        else:
            m = "stated"
        passive = (c.get("verb_voice") or "").startswith("passive") or (c.get("verb_stem") or "") in PASSIVE_STEMS
        neg = ctid in negated
        gate = None
        # NOT "nonfinite": "when Ahab saw Elijah" (1 Kgs 18:17, an infinitive)
        # reports a real event, and the judges were right to keep 48 of the 62
        # (the first version of the gate held them all, 2026-10-19)
        if m not in ("stated", "nonfinite"):
            gate = f"{m}: not a statement (by its form)"
        elif neg:
            gate = "negated"
        elif passive:
            gate = "passive: the subject is the one acted on"
        return {"modality": m, "modality_from": "form", "negated": neg, "passive": passive,
                "mood": mood, "stem": c.get("verb_stem"), "person": c.get("verb_person"),
                "voice": c.get("verb_voice"), "gate": gate}

    st, rows = collections.Counter(), []
    for nid, n in nodes.items():
        if not n.get("content"):
            continue
        es = edges.get(nid, [])
        verb = next((nodes.get(e["dst"]) for e in es if e["type"] == "v"), None)
        o = next((e["dst"] for e in es if e["type"] == "o"), None)
        if not verb or not o:
            continue
        s = next((e["dst"] for e in es if e["type"] == "s"), None) or nid.replace("#ct", "#cl") + "s"
        rs, hs = resolve(s, verb)
        ro, ho = resolve(o, verb)
        md = modality(nodes.get(nid.replace("#ct", "#cl")) or {}, nid)
        st["clauses with a verb and an object"] += 1
        st[f"time: {time_of(md['mood'], verb.get('tense'))}"] += 1
        st["both resolved"] += bool(rs and ro)
        if rs and ro:
            st[f"both resolved, gate: {(md['gate'] or 'open').split(':')[0]}"] += 1
        st[f"subject: {hs.split(':')[0]}"] += 1
        st[f"object: {ho.split(':')[0]}"] += 1
        rows.append({"ref": n["ref"], "clause": nid.replace("#ct", "#cl"), "verb": verb.get("lemma"),
                     "verb_key": key_of(verb), "verb_text": verb.get("text"),
                     # the full number, its homonym letter kept (2050c), beside
                     # the key the word pages use (h2050): the committee's
                     # scholar, both sittings
                     "verb_strong": verb.get("strong"),
                     "subject": end(s, rs, hs), "object": end(o, ro, ho), **md,
                     "tense": verb.get("tense"), "time": time_of(md["mood"], verb.get("tense"))})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps(dict(st.most_common()), ensure_ascii=False, indent=1))
    for r in rows:
        if r["ref"] == "Jhn.3.16":
            print("John 3:16:", r["subject"]["record"], r["verb"], r["object"]["record"], r["subject"]["how"], r["object"]["how"])


if __name__ == "__main__":
    main()
