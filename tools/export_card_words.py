"""A CARD'S WORDS, PUBLISHED WITH THEIR STRENGTH (plan 8.1f; 2026-10-19:
card words + navigator).

Every word a card holds, shown or not (keep much, show little): its anchored
words with their share, the word a verse it cites uses, and the same-root and
derived words a reader is shown. Each is a bom:CardWord carrying its strength
as a W3C Data Quality Vocabulary measurement (dqv:QualityMeasurement) against
the metric the policy declares (bom:cardWordShare), and its tier (bom:tier
bom:default | bom:onRequest) under that policy (ontology/schema/salience.json).

TriG: the default graph holds every card word; the named graph
<https://bibleontology.org/graph/shown-card-words> holds exactly the shown ones,
a void:subset made by the published CONSTRUCT in out/export/shown-card-words.rq.

    python tools/export_card_words.py   -> out/export/card-words.trig.gz, out/export/shown-card-words.rq
"""
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
sys.path.insert(0, str(ROOT / "tools"))
from ns_common import export_rights, gz_text  # noqa: E402
import membership as M  # noqa: E402
import salience  # noqa: E402

SITE = "https://bibleontology.org"
OUT = ROOT / "out" / "export"
SHOWN = f"{SITE}/graph/shown-card-words"
CONSTRUCT = f"""PREFIX bom: <{SITE}/ns/meaning#>
PREFIX dqv: <http://www.w3.org/ns/dqv#>
# The card words a reader is shown by default: the policy's tier, nothing else.
# Run over out/export/card-words.trig's default graph, it gives exactly the
# named graph <{SHOWN}>, each word's strength measurement with it.
CONSTRUCT {{ ?cw ?p ?o . ?m ?mp ?mo }}
WHERE {{
  ?cw a bom:CardWord ; bom:tier bom:default ; ?p ?o .
  OPTIONAL {{ ?cw dqv:hasQualityMeasurement ?m . ?m ?mp ?mo }}
}}
"""


def lit(v):
    return json.dumps(v, ensure_ascii=False)


def main():
    rows = [json.loads(x) for x in gzip.open(ROOT / "out" / "concept-anchors.jsonl.gz", "rt", encoding="utf-8") if x.strip()]
    ents = {}
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        e = json.loads(line)
        ents[e["id"]] = e
    lemmas = {}
    with gzip.open(ROOT / "out" / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("word"):
                s = re.sub(r"\D", "", str(d.get("strong") or "")).lstrip("0")
                if s:
                    lemmas.setdefault(("g" if d.get("lang") == "greek" else "h") + s, d.get("lemma"))
    fp = ROOT / "out" / "word-families.json"
    families = (json.loads(fp.read_text(encoding="utf-8")).get("families") or {}) if fp.exists() else {}
    rix = M.root_index(lemmas)
    every = M.all_words(rows)
    shown = M.anchors(rows)
    cut = salience.cut("card_word_share")
    default, shown_n, total = [], 0, 0
    lines = [f"@prefix bom: <{SITE}/ns/meaning#> .", "@prefix dqv: <http://www.w3.org/ns/dqv#> .",
             "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .", ""]
    named = []
    rep = M.repairs()
    for cid in sorted(set(every) | {c for c, r in rep.items() if r["named"]}):
        ws = every.get(cid, [])
        if cid not in ents:
            continue
        seen = {}
        for k, share, basis in ws:
            tier = ("default" if basis == "cited verse" else "on_request" if basis == "anchored (phrase card)"
                    else salience.tier("card_word_share", share))
            seen[k] = (share, basis, tier)
        # the same-root and derived words a reader is shown with the shown
        # anchors, and a ruled repair's named-verse words (shown: their verses
        # are on the card, each marked a reading)
        for k, w in M.words(shown.get(cid, []), lemmas, families, rix, card=cid).items():
            if w["family"] and k not in seen:
                seen[k] = (None, "same root or derived", "default")
            elif str(w.get("only") or "").startswith("named"):
                seen[k] = (None, "named verses (a reading)", "default")
        for k, (share, basis, tier) in sorted(seen.items()):
            iri = f"<{SITE}/e/{cid}#word-{k}>"
            body = [f"{iri} a bom:CardWord ; bom:card <{SITE}/e/{cid}> ; bom:word <{SITE}/word/{k}> ;",
                    f"    bom:wordBasis {lit(basis)} ; bom:tier bom:{'default' if tier == 'default' else 'onRequest'}"]
            if share is not None:
                body[-1] += " ;"
                body.append(f"    dqv:hasQualityMeasurement [ a dqv:QualityMeasurement ; "
                            f"dqv:isMeasurementOf bom:cardWordShare ; dqv:value \"{share}\"^^xsd:decimal ]")
            body[-1] += " ."
            lines += body
            total += 1
            if tier == "default":
                named += body
                shown_n += 1
    trig = "\n".join(lines) + f"\n\n<{SHOWN}> {{\n" + "\n".join("    " + x for x in named) + "\n}\n"
    OUT.mkdir(parents=True, exist_ok=True)
    with gz_text(OUT / "card-words.trig.gz") as f:
        f.write(f"# A card's words with their strength, under the declared filter policy (cut {cut}).\n"
                + "\n".join(export_rights()) + "\n" + trig)
    (OUT / "shown-card-words.rq").write_text(CONSTRUCT, encoding="utf-8")
    print(f"{total:,} card words on {len(every):,} cards; shown by default {shown_n:,}, on request {total - shown_n:,} "
          f"-> {(OUT / 'card-words.trig.gz').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
