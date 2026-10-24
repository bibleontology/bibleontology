"""THE TRAIL OF THE CONCEPT AUDITS AND THE LIFTED RELATIONS, ARCHIVED
(2026-10-19; memory: provenance against slop -- every judged pass's per-item
trail, kept and rejected, goes to ontology/provenance/ before scratch is lost).

One gzipped JSONL per pass family, one record per item, every judge's answer
side by side:

  concept-audit-2026-10-18.jsonl.gz   per concept card: phase 1 (Sonnet), and
                                      each verse with its verdict in every pass
  sense-flags-2026-10-19.jsonl.gz     per flagged word: its 20 verses, Sonnet's
                                      and Haiku's verdict on each
  card-audit-2026-10-19.jsonl.gz      the same audit over objects, images, titles...
  lifted-relations-2026-10-19.jsonl.gz  per candidate clause: both judges'
                                      decision and why; the family candidates

    python tools/meaning/archive_audit.py
"""
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
M = ROOT / "out" / "meaning"
DEST = ROOT / "ontology" / "provenance" / "meaning"


def files(d, prefix):
    for p in sorted(d.glob(f"{prefix}-*.json")):
        yield p, json.loads(p.read_text(encoding="utf-8"))


def write(name, rows):
    DEST.mkdir(parents=True, exist_ok=True)
    with gzip.open(DEST / name, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{name}: {len(rows):,} records, {(DEST / name).stat().st_size:,} bytes")


def audit(base, phase1, passes, extra_passes=(), rejudge=None):
    # items.json now holds the corrected "uncovered" lists; what the first judge
    # was SHOWN is items-before-bookfix.json (the Matt/Mat bug, 2026-10-19)
    shown = base / "items-before-bookfix.json"
    items = {i["id"]: i for i in json.loads((shown if shown.exists() else base / "items.json").read_text(encoding="utf-8"))}
    fixed = {i["id"]: i for i in json.loads((base / "items.json").read_text(encoding="utf-8"))}
    p1, p2 = {}, {}
    for _, a in files(base / phase1, "A"):
        for c in a.get("cards") or []:
            p1[c.get("id")] = c
    if rejudge and (base / rejudge).exists():
        for _, a in files(base / rejudge, "A"):
            for c in a.get("cards") or []:
                p2[c.get("id")] = c
    verdicts = {}
    for run in list(passes) + list(extra_passes):
        if not (base / run).exists():
            continue
        for p, a in files(base / run, "V"):
            for ref, v in (a.get("verses") or {}).items():
                verdicts.setdefault(p.stem[2:], {}).setdefault(ref, {})[run] = v
    rows = []
    for cid, it in items.items():
        rows.append({"card": cid, "name": it["name"], "candidates_shown": it["candidates"],
                     "anchors_shown": it["anchors"], "uncovered_shown": it["uncovered"],
                     "phase1": {"by": f"Claude Sonnet ({phase1})", "answer": p1.get(cid)},
                     **({"rejudge_after_book_fix": {"by": f"Claude Sonnet ({rejudge})", "uncovered_shown":
                                                    fixed[cid]["uncovered"], "answer": p2[cid]}} if cid in p2 else {}),
                     "verses": {"by": "Claude Sonnet, each pass independent", "verdicts": verdicts.get(cid, {})}})
    return rows


def main():
    write("concept-audit-2026-10-18.jsonl.gz",
          audit(M / "concept-audit", "sonnet-1", ["verses-1", "verses-2"], ["verses-3", "verses-4"], "sonnet-2"))
    write("card-audit-2026-10-19.jsonl.gz", audit(M / "card-audit", "card-1", ["verses-1", "verses-2"], (), "card-2"))

    ca = M / "concept-audit"
    its = json.loads((ca / "senses-1" / "items.json").read_text(encoding="utf-8"))
    runs = {r: {p.stem[2:].replace("__", "~"): a.get("verses") for p, a in files(ca / r, "S")}
            for r in ("senses-1", "senses-2")}
    write("sense-flags-2026-10-19.jsonl.gz",
          [{**{k: x[k] for k in ("flag", "card", "name", "key", "lemma", "uses", "pool")},
            "sonnet": runs["senses-1"].get(x["flag"]), "haiku": runs["senses-2"].get(x["flag"])} for x in its])

    lift = M / "lift"
    rows = []
    # the ends check (2026-10-19): per card or image end, both judges' verdicts
    endv = {}
    for run in ("ends-sonnet", "ends-haiku"):
        if not (lift / run).exists():
            continue
        eits = {x["id"]: x for x in json.loads((lift / run / "items.json").read_text(encoding="utf-8"))}
        for _, x in files(lift / run, "E"):
            for y in x.get("answers") or []:
                it = eits.get(y.get("id"))
                if it:
                    endv.setdefault(tuple(it["rel"]), {}).setdefault(it["side"], {})[run] = \
                        {"card": it["card"], "decision": y.get("decision"), "why": y.get("why")}
    for a, b in (("love-sonnet", "love-haiku"), ("all-sonnet", "all-haiku"), ("delta-sonnet", "delta-haiku")):
        if not (lift / a).exists():
            continue
        its = json.loads((lift / a / "items.json").read_text(encoding="utf-8"))
        ans = {}
        for run in (a, b):
            for _, x in files(lift / run, "L"):
                for y in x.get("answers") or []:
                    ans.setdefault(y.get("id"), {})[run] = {"decision": y.get("decision"), "why": y.get("why")}
        fam = {}
        if a == "all-sonnet" and (lift / "families-1").exists():
            for _, x in files(lift / "families-1", "F"):
                for y in x.get("answers") or []:
                    fam[y.get("id")] = {"sense": y.get("sense"), "family": y.get("family")}
        for x in its:
            j = ans.get(x["id"], {})
            kept = all((j.get(r) or {}).get("decision") == "yes" for r in (a, b))
            k = (x["id"], x["subject"], x["object"])
            rows.append({"pass": a.split("-")[0], **x, "judges": j, "kept": kept,
                         **({"ends_check": endv[k]} if k in endv else {}),
                         **({"family_candidate": fam[x["id"]]} if x["id"] in fam else {})})
    write("lifted-relations-2026-10-19.jsonl.gz", rows)


if __name__ == "__main__":
    main()
