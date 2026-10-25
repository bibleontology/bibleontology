"""THE IMAGE AUDIT, the next tier: figure-first candidates (plan 8.2h, 2026-10-24).

The 58 images with 100 verses or more carry 26,761 verses, nearly all plain uses
of a common word ("a city on a hill" lists every verse with "city"). Reading them
all would be the eight's method sixteen times over. A figure card should hold the
verses where the text uses the figure, so start from what already marks a figure:
  - a simile whose vehicle is the card's word (out/comparisons.jsonl.gz, figurative);
  - a metaphor whose vehicle is the card's word (out/metaphor.jsonl.gz);
  - the verses the card cites, and the verses its relations cite.
Each candidate keeps why it is one. Read-only; the reading comes after, by verse.

    python tools/meaning/image_candidates.py [--port 8012] [--min 100]
      -> out/meaning/image-audit/candidates/<image>.json, index.json
"""
import collections
import glob
import gzip
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from export_claims import verses as vlist  # noqa: E402
from derive import BOOK  # noqa: E402

PORT = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8012
MIN = int(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 100
OUT = ROOT / "out" / "meaning" / "image-audit" / "candidates"
DONE = {"image_wine", "image_lion", "image_vine", "image_candlestick", "image_lamb", "image_clothes", "image_ox",
        "image_bread", "image_temple"}


def rows(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            if "ref" in d:
                yield d


def mac(ref):
    out = set()
    for v in vlist(ref):
        b, rest = v.split(".", 1)
        out.add(BOOK.get(b, b) + "." + rest)
    return out


def main():
    audit = [json.loads(l) for l in open(ROOT / "out" / "meaning" / "image-audit" / "images.jsonl", encoding="utf-8")]
    todo = [r for r in audit if r["verses"] >= MIN and r["id"] not in DONE]
    ents = {}
    for f in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                e = json.loads(ln)
                ents.setdefault(e["id"], e)
    by = collections.defaultdict(list)
    for f in glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                r = json.loads(ln)
                by[r["src"]].append(r)
                by[r["dst"]].append(r)
    sim = list(rows(ROOT / "out" / "comparisons.jsonl.gz"))
    met = list(rows(ROOT / "out" / "metaphor.jsonl.gz"))
    text = {}
    for ln in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        if "b" in d:
            text[f"{BOOK.get(d['b'], d['b'])}.{d['c']}.{d['v']}"] = d["t"]
    moved = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8"))["moved"]
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for r in todo:
        iid = r["id"]
        with urllib.request.urlopen(f"http://localhost:{PORT}/api/entity-verses?id={iid}", timeout=60) as resp:
            d = json.load(resp)
        lemmas = {w.get("lemma") for w in d.get("words") or [] if w.get("lemma")}
        cand = collections.defaultdict(set)
        for s in sim:
            if s.get("figurative") and lemmas & set(s.get("vehicle") or []):
                cand[s["ref"]].add("a simile whose vehicle is the card's word")
        for m in met:
            if lemmas & set(m.get("vehicle") or []):
                cand[m["ref"]].add("a metaphor whose vehicle is the card's word")
        e = ents.get(iid) or {}
        for ref in e.get("refs") or []:
            for v in mac(ref):
                cand[v].add("the card cites it")
        for rel in by[iid]:
            for ref in rel.get("refs") or []:
                for v in mac(ref):
                    cand[v].add(f"its relation cites it ({rel['src']} {rel['type']} {rel['dst']})")
        items = [{"ref": v, "why": sorted(w), "text": text.get(moved.get(v, v))} for v, w in sorted(cand.items())]
        out = {"image": iid, "name": e.get("name"), "desc": e.get("desc"), "verses_on_card": d.get("total"),
               "words": [{"key": w.get("key"), "lemma": w.get("lemma")} for w in d.get("words") or []],
               "relations": [{k: x.get(k) for k in ("src", "type", "dst", "refs")} for x in by[iid]],
               "candidates": items}
        (OUT / f"{iid}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        index.append({"image": iid, "verses_on_card": d.get("total"), "candidates": len(items)})
    index.sort(key=lambda x: -x["verses_on_card"])
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(index)} images: {sum(x['verses_on_card'] for x in index)} card verses, "
          f"{sum(x['candidates'] for x in index)} candidates")
    for x in index[:10]:
        print(f"  {x['image']:28} {x['verses_on_card']:>5} on card -> {x['candidates']:>4} candidates")


if __name__ == "__main__":
    main()
