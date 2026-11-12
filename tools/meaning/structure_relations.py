"""Every word-verse of a card's own words, its relation from the structure layer (P-2026-11-08-1, approved by Doug
2026-11-08: "I approve the structure layer step").

Measured 2026-11-08: of about 255,000 verses where thing and idea cards' own words occur, relations cite 1 to 6%.
The Mac's reading of 852 verses (20o) yielded 12 relations because the doer was "you" or "they". The structure layer
already holds each clause's verb (`v`), subject (`s`, or an implicit subject the verb's person states) and object
(`o`), and the resolution pass links a pronoun or implicit subject to the word it means (`refers_to`): in Joshua 4:8
"they took up twelve stones" is the twelve men of 4:2, and "them" is the stones.

So for each object or creature card, each clause where one of its words (or a word resolved to one) is the object or
the subject, the candidate is built by rule: the doer, the verb, the thing. One narrow question goes to the Mac: does
the verse say this? It also names the doer as the verse does and the act in a plain verb. Nothing is written to the
graph by this pass; the apply step maps doers to cards and verbs to the vocabulary, holds speech by the graph's rule,
and keeps divine persons by hand. The Mac alone (DeepSeek budget 0: these clauses name the LORD often).

    python tools/meaning/structure_relations.py build   -> out/orchestra-intake/20s-structure-relations/
"""
import collections
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))

NAME = "20s-structure-relations"     # below 21-renderings-check: the Mac's runner takes names in order, so this runs first
OPTIONS = {"temperature": 0, "num_ctx": 4096}
SEED = 20261108
PER_CARD = 40
KINDS = {"object", "creature"}
if "--concepts" in sys.argv:          # the second pass (2026-11-10): ideas and images, fewer verses each
    NAME, KINDS, PER_CARD = "22-structure-relations-concepts", {"concept", "image"}, 12

BRIEF = """You check one reading of a Bible verse (the Berean Standard Bible). A parser read the verse's clause as:
DOER - ACT - THING. Say whether the verse says that.

Answer each with ONE line of JSON:
{"id": "...", "verdict": "...", "who": "...", "act": "...", "words": "...", "why": "..."}

verdict:
- "stated": the verse says the doer does this act to the thing (or the thing does it, when the thing is the doer).
  A command or a promise counts only if the verse reports it as done; "you shall bring" is "commanded".
- "commanded": the verse commands or permits it, but does not report it done.
- "not_said": the verse does not say this (wrong doer, wrong thing, or the act is denied).
- "unclear": you cannot tell.

who: the doer as the verse or its story names them, a name or a plain noun ("the twelve men", "the priests",
"the Philistines", "David"); never a pronoun.
act: the act in one plain past-tense verb ("carried", "set up", "offered", "captured", "worshiped", "broke").
words: the verse's words that say it, copied exactly.
why: one short reason.

Worked examples (not from the items):
- DOER the men (resolved from "they") - ACT took up - THING stones. VERSE: "...they took up twelve stones from the
  middle of the Jordan..." -> stated, who "the twelve men", act "took up".
- DOER you - ACT bring - THING grain offering. VERSE: "When anyone brings a grain offering to the LORD..." ->
  commanded, who "anyone", act "brings".
- DOER Israel - ACT served - THING other gods. VERSE: "...they did not serve other gods." -> not_said (denied).
"""


def build():
    import server as S
    import structure as T
    from object_identity import verses
    text = verses()
    d = S.load()
    cards = {}
    for eid, e in d["ents"].items():
        if e.get("type") in KINDS:
            try:
                keys = {w["key"] for w in S.api_entity_verses(d, {"id": [eid]}).get("words") or [] if w.get("key")}
            except Exception:
                keys = set()
            if keys:
                cards[eid] = (e.get("name") or eid, keys)
    by_key = collections.defaultdict(set)
    for eid, (_n, keys) in cards.items():
        for k in keys:
            by_key[k].add(eid)
    # the chapters any card's word is in
    chapters = set()
    for k in by_key:
        for ref in S._verses_of(d).get(k, ()):
            chapters.add(ref.rsplit(".", 1)[0])
    items, per = [], collections.Counter()
    for chap in sorted(chapters):
        try:
            nodes, edges = T._chapter(chap + ".1")
        except Exception:
            continue
        refer = {}
        for e in edges:
            if e.get("type") == "refers_to":
                refer.setdefault(e["src"], e["dst"])
        roles = collections.defaultdict(dict)
        for e in edges:
            if e.get("clause_role") and e.get("type") in ("v", "s", "o"):
                roles[e["src"]].setdefault(e["type"], e["dst"])

        def key_of(nid, hops=0):
            n = nodes.get(nid) or {}
            if n.get("strong"):
                lang = n.get("lang") or "hebrew"
                return S.sense_key(lang, n["strong"]), nid
            if nid in refer and hops < 3:
                return key_of(refer[nid], hops + 1)
            return None, nid

        def name_of(nid, hops=0):
            n = nodes.get(nid) or {}
            if nid in refer and hops < 3 and not n.get("proper"):
                tgt = refer[nid]
                got = name_of(tgt, hops + 1)
                if got:
                    return got
            return (n.get("text") or "").replace(".", " ") or None

        for ct, r in roles.items():
            if "v" not in r:
                continue
            verb = nodes.get(r["v"]) or {}
            for role in ("o", "s"):
                if role not in r:
                    continue
                k, _w = key_of(r[role])
                for eid in by_key.get(k, ()):
                    if per[eid] >= PER_CARD:
                        continue
                    ref = (nodes.get(r[role]) or {}).get("ref") or ct.split("#")[0]
                    eng = T.to_english(ref)
                    vtext = text.get(eng) or text.get(ref)
                    if not vtext:
                        continue
                    doer = name_of(r["s"]) if role == "o" and "s" in r else None
                    thing = cards[eid][0]
                    claim = (f"DOER {doer or '(not given)'} - ACT {verb.get('text', '').replace('.', ' ')} - THING {thing}"
                             if role == "o" else f"DOER {thing} - ACT {verb.get('text', '').replace('.', ' ')} - THING "
                             f"{name_of(r['o']) if 'o' in r else '(none)'}")
                    per[eid] += 1
                    items.append({"key": f"{eid}:{eng}:{ct.split('#')[1]}:{role}", "id": f"s{len(items) + 1}",
                                  "card": eid, "role": role, "ref": eng, "verb_lemma": verb.get("lemma"),
                                  "verb_text": verb.get("text"), "doer": doer, "claim": claim, "verse": vtext,
                                  "context": [f"THING: {thing}"]})
    random.Random(SEED).shuffle(items)
    out = ROOT / "out" / "orchestra-intake" / NAME
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{NAME}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "structure_relations"}}) + "\n")
        for it in items:
            f.write(json.dumps({"key": it["key"], "messages": messages(it)}, ensure_ascii=False) + "\n")
    spec = {"pass": NAME, "mac_job": f"{NAME}.jsonl", "priority": 30, "flag": {"verdict_in": []},
            "deepseek": {"budget_usd": 0}, "allowed_fields": ["id", "claim", "ref", "verse", "context"]}
    (out / f"{NAME}.pass.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out / "brief.md").write_text(BRIEF, encoding="utf-8", newline="\n")
    with open(out / "items.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"{len(cards)} cards with words; {len(items)} clause readings from {len(per)} cards -> {out}")


def messages(it):
    return [{"role": "system", "content": BRIEF},
            {"role": "user", "content": f"id: {it['id']}\n{it['claim']}\nVERSE ({it['ref']}): {it['verse']}"}]


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        build()
    else:
        print(__doc__)
