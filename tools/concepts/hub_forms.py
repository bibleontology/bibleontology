"""The raw material for the concept hubs, by form, for the top fifteen and
righteousness -- grammar only, no model (2026-10-09).

The aim was to hit the top 15 concepts while moderating token consumption
for the rest of the week. So this is a script, not a review: for each concept's words (the card's own, by rule,
part of speech from the lexicon), the verb's commonest agents and patients
(the frames), the noun's commonest companion words in its phrase (MACULA's
clauses: "of God", "and justice", "do"), and the adjective's verses -- each
with counts and example verses, Hebrew normalized (typed and stored vowel
order differ). A hub's rows are drawn from this and checked before showing.

    python tools/concepts/hub_forms.py   -> out/hub-forms.json, out/hub-forms.md
"""
from __future__ import annotations

import collections
import gzip
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

HUBS = ["truth", "love", "righteousness", "faith", "grace", "mercy", "hope", "holiness", "glory",
        "peace", "joy", "forgiveness", "repentance", "prayer", "praise"]
NF = lambda x: unicodedata.normalize("NFC", x or "")  # noqa: E731
STOP = {NF(x) for x in ("ὁ", "καί", "ἐν", "εἰς", "δέ", "γάρ", "αὐτός", "ἐγώ", "σύ", "ὅς", "οὗτος", "πᾶς", "εἰμί",
                        "הַ", "וְ", "לְ", "בְּ", "כְּ", "מִן", "אֵת", "הוּא", "אֲשֶׁר", "כִּי", "עַל", "אֶל", "לֹא", "כֹּל")}


def main():
    d = S.load()
    vo = S._verses_of(d)

    def lab(mref):
        b, c, v = S.bsb_ref(d, mref).split(".")
        b = S.MACULA_BACK.get(b, b)
        return f"{S.TITLE.get(b, b)} {c}:{v}"

    def gloss(lemma):
        k = d.get("lemma_key", {}).get(lemma) if isinstance(d.get("lemma_key"), dict) else None
        return (d["lex"].get(k) or {}).get("gloss") if k else None

    plan = {}
    for cid in HUBS:
        card = S.api_entity(d, {"id": [cid]})
        if not card.get("found"):
            plan[cid] = None
            continue
        forms = collections.defaultdict(set)
        for w in card.get("words") or []:
            lx = d["lex"].get(w["key"]) or {}
            pos = (lx.get("pos") or "").split(":")[-1][:1]
            sense_kind = None if pos else (S.api_sense(d, {"key": [w["key"]]}).get("kind"))
            form = {"V": "verb", "N": "noun", "A": "adjective"}.get(pos) or ("verb" if sense_kind == "verb" else "noun")
            forms[form].add(NF(w.get("lemma")))
        plan[cid] = {"name": card.get("name"), "forms": {k: sorted(v) for k, v in forms.items()},
                     "verses": len(set().union(*(set(vo.get(w["key"], ())) for w in card.get("words") or [])))
                     if card.get("words") else 0}
    # one pass over each source for all concepts
    verb = {cid: collections.defaultdict(list) for cid in plan if plan[cid]}
    with gzip.open(ROOT / "out/frames.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            lem = NF(r.get("lemma"))
            for cid, p in plan.items():
                if p and lem in set(p["forms"].get("verb", [])):
                    key = (" ".join(r.get("agent") or ["-"]), " ".join(r.get("patient") or ["-"]))
                    verb[cid][key].append(r["ref"])
    noun = {cid: collections.defaultdict(list) for cid in plan if plan[cid]}
    adj = {cid: [] for cid in plan if plan[cid]}
    with gzip.open(ROOT / "data/macula-clauses.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            for part in r.get("parts") or []:
                lems = [NF(x) for x in part.get("lemmas") or []]
                ls = set(lems)
                for cid, p in plan.items():
                    if not p:
                        continue
                    if ls & set(p["forms"].get("noun", [])):
                        for x in ls - set(p["forms"]["noun"]) - STOP:
                            if len(x) > 1 and r["ref"] not in noun[cid][x]:
                                noun[cid][x].append(r["ref"])
                    if ls & set(p["forms"].get("adjective", [])) and part["role"] in ("p", "s", "o"):
                        if r["ref"] not in adj[cid]:
                            adj[cid].append(r["ref"])
    out, md = {}, ["# The concept hubs' raw material, by form (grammar only)", ""]
    for cid, p in plan.items():
        if not p:
            md += [f"## {cid}: no card", ""]
            continue
        vt = sorted(verb[cid].items(), key=lambda x: -len(x[1]))[:12]
        nt = sorted(noun[cid].items(), key=lambda x: -len(x[1]))[:12]
        out[cid] = {**p, "verb": [{"agent": a, "patient": b, "n": len(v), "eg": [lab(x) for x in v[:3]]} for (a, b), v in vt],
                    "verb_total": sum(len(v) for v in verb[cid].values()),
                    "noun_with": [{"word": w, "n": len(v), "eg": [lab(x) for x in v[:3]]} for w, v in nt],
                    "noun_total": len({x for v in noun[cid].values() for x in v}),
                    "adjective": {"n": len(adj[cid]), "eg": [lab(x) for x in adj[cid][:4]]}}
        o = out[cid]
        lead = max((("verb", o["verb_total"]), ("noun", o["noun_total"]), ("adjective", o["adjective"]["n"])), key=lambda x: x[1])
        o["leads"] = lead[0]
        md += [f"## {p['name']} -- {p['verses']} verses; leads with the {lead[0]}",
               f"- words: " + "; ".join(f"{k}: {' '.join(v)}" for k, v in p["forms"].items()),
               f"- verb ({o['verb_total']}): " + "; ".join(f"{x['agent']} -> {x['patient']} {x['n']}" for x in o["verb"][:6]),
               f"- noun ({o['noun_total']}) beside: " + "; ".join(f"{x['word']} {x['n']}" for x in o["noun_with"][:8]),
               f"- adjective ({o['adjective']['n']}): " + ", ".join(o["adjective"]["eg"]), ""]
    (ROOT / "out" / "hub-forms.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "out" / "hub-forms.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:60]))


if __name__ == "__main__":
    main()
