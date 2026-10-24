"""The deterministic face-lift, prototyped on one study: the fruit of the
Spirit (Gal 5:22-23), every card filled by rule into the hub's template.

2026-10-09: a level of continuity is wanted when viewing cards that do not make
the cut, like humility, so that there is a level of uniformity -- imagine a
Bible study on the fruit of the Spirit.

Per card, by rule only (nothing hand-picked): the opening (the card's own
description), the words with their part of speech and uses, the themes, the
texts' own words (the card's own key verses), a section per form the words
take -- noun, verb, adjective -- with three verses spread across the Bible
(the first in the Law and history, the first in the Gospels and Acts, the
first in the letters and Revelation, else the next), the cards that share a
word (its cluster), and the study bar (this card's place in the list).

    python tools/concepts/proto/facelift.py  -> fruit-study.json beside it
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

LIST = "fruit_of_the_spirit"
TIER = {"love": 1, "joy": 1, "peace": 1, "faith": 1, "patience": 2, "kindness": 2, "gentleness": 2,
        "goodness": 3, "temperance": 3}
TIER2 = {"patience": ["g3114"], "gentleness": ["g4239"], "temperance": ["g1468"]}
POS = {"N": "noun", "A": "adjective", "V": "verb"}
GOSPELS = {"Matt", "Mark", "Luke", "John", "Acts"}
LETTERS = {"Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim", "Titus",
           "Phlm", "Heb", "Jas", "1Pet", "2Pet", "1John", "2John", "3John", "Jude", "Rev"}


def main():
    d = S.load()
    vo = S._verses_of(d)
    hubs = json.loads((ROOT / "ontology" / "aggregate-hubs.json").read_text(encoding="utf-8"))
    hub = hubs[LIST] if LIST in hubs else next(v for v in hubs.values() if isinstance(v, dict) and v.get("card") == LIST)
    members = hub["members"]
    ranking = json.loads((ROOT / "out" / "concept-ranking.json").read_text(encoding="utf-8"))["concepts"]
    words_of = {r["id"]: set(r["words"]) for r in ranking}

    def verse(mref):
        b, c, v = S.bsb_ref(d, mref).split(".")
        b = S.MACULA_BACK.get(b, b)
        t = d["verses"].get((b, int(c), int(v)))
        return {"ref": f"{S.TITLE.get(b, b)} {c}:{v}", "text": t, "b": b} if t else None

    def spread(keys):
        vs = []
        for k in keys:
            vs += [verse(r) for r in sorted(vo.get(k, ()), key=lambda r: S._canon_key(r) if hasattr(S, "_canon_key") else r)]
        vs = [x for x in vs if x]
        picks = []
        for test in (lambda b: b not in GOSPELS and b not in LETTERS, lambda b: b in GOSPELS, lambda b: b in LETTERS):
            x = next((x for x in vs if test(x["b"]) and x not in picks), None)
            if x:
                picks.append(x)
        for x in vs:
            if len(picks) >= 3:
                break
            if x not in picks:
                picks.append(x)
        return picks[:3]

    out = []
    for i, m in enumerate(members):
        eid = m["card"]
        card = S.api_entity(d, {"id": [eid]})
        words, by_pos = [], {}
        for w in card.get("words") or []:
            sense = S.api_sense(d, {"key": [w["key"]]})
            p = sense.get("pos") or (d["lex"].get(w["key"]) or {}).get("pos") or ""
            pos = "verb" if sense.get("kind") == "verb" else POS.get(p.split(":")[-1][:1], "word")
            words.append({"lemma": w.get("lemma"), "translit": w.get("translit"), "gloss": w.get("gloss"),
                          "lang": w.get("lang"), "uses": w.get("uses"), "pos": pos})
            by_pos.setdefault(pos, []).append(w["key"])
        # TIER 2 (hand-chosen for the mockup, marked as such): the word family
        # the graph does not link yet -- the noun's verb or adjective
        for k in TIER2.get(eid, []):
            lx = d["lex"].get(k) or {}
            pos = POS.get((lx.get("pos") or "").split(":")[-1][:1], "word")
            words.append({"lemma": lx.get("word"), "translit": lx.get("translit"), "gloss": lx.get("gloss"),
                          "lang": "Greek" if k.startswith("g") else "Hebrew", "uses": len(vo.get(k, ())),
                          "pos": pos, "tier2": True})
            by_pos.setdefault(pos, []).append(k)
        forms = []
        for pos in ("verb", "noun", "adjective", "word"):
            if pos in by_pos:
                n = len(set().union(*(set(vo.get(k, ())) for k in by_pos[pos])))
                forms.append({"form": pos, "n": n, "eg": spread(by_pos[pos])})
        forms.sort(key=lambda f: -f["n"])                 # the text's own weight leads
        own = [verse(S._macula_ref(d, r)) for r in (card.get("refs") or [])[:4]]
        mine = words_of.get(eid, set())
        cluster = [{"id": r["id"], "name": r["name"]} for r in ranking
                   if r["id"] != eid and mine & set(r["words"])][:6]
        out.append({
            "id": eid, "label": m["label"], "name": card.get("name") or eid, "tier": TIER.get(eid, 3),
            "intro": [p for p in (card.get("desc") or "").split("\n\n") if p.strip()],
            "words": words, "forms": forms,
            "themes": [[t.get("title"), t.get("label") or ""] for t in card.get("mthemes") or []],
            "own_words": [x for x in own if x], "cluster": cluster,
            "study": {"list": hub.get("label"), "passage": hub.get("passage"), "n": i + 1, "of": len(members),
                      "prev": members[i - 1]["label"] if i else None,
                      "next": members[i + 1]["label"] if i + 1 < len(members) else None},
        })
        print(f"  {m['label']:14} words {len(words)}  forms {[(f['form'], f['n']) for f in forms]}  themes {len(out[-1]['themes'])}  "
              f"own {len(out[-1]['own_words'])}  cluster {[c['name'] for c in cluster][:4]}")
    Path(__file__).with_name("fruit-study.json").write_text(json.dumps(
        {"members": [m["label"] for m in members], "cards": out}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
