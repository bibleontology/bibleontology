"""THE SWEEP, SETTLED (plan 8.2h, 2026-10-24): one placement per verse of the 42 swept image cards.

Every verse of each card was read once (the sweep). A blind second reader read every verse the sweep called a figure
and every 10th other; where the two placed it differently, a third blind reader settled it. So a verse is:
  agreed      sweep and confirmer place it alike
  two of three  the third reader sided with one of them
  three-way   all three differ: for Doug
  single      the sweep alone (a literal or unused verse outside the 10% sample); the sample's agreement rate is
              the measure of how far to trust these
Placement: literal -> the literal card; figure, figure_keyed -> the image card; both -> both; anything else -> neither.
Then compared with the candidate pass's settled placements (candidates/tier2-final.json) for the same verses.

    python tools/meaning/image_sweep_settle.py  -> out/meaning/image-audit/sweep/settled.json, a tally
"""
import collections
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
S = ROOT / "out" / "meaning" / "image-audit" / "sweep"
PLACE = {"literal": "literal", "figure": "figure", "figure_keyed": "figure", "both": "both"}


def place(s):
    return PLACE.get(s, "neither")


def thirds(prefix):
    t = {}
    for f in glob.glob(str(S / f"{prefix}-*.result.json")):
        for v in json.loads(Path(f).read_text(encoding="utf-8"))["verses"]:
            t[(v["image"], v["ref"])] = v
    return t


def main():
    # fix-<n>: the 1,699 verses first shown with a neighbour's text (2026-10-25), read again with their own. Settled
    # LAST, so their readings replace the first ones, and with their own third readers (fixtb-<n>) only: a third
    # reading made against the wrong text never counts for them
    third_first, third_fix = thirds("tiebreak"), thirds("fixtb")
    out, basis = {}, collections.Counter()
    per = collections.defaultdict(lambda: collections.Counter())
    keyed = collections.defaultdict(list)
    files = sorted(glob.glob(str(S / "*.sweep.json")))
    files = [f for f in files if not Path(f).name.startswith("fix-")] + [f for f in files if Path(f).name.startswith("fix-")]
    for f in files:
        cid = Path(f).name[:-len(".sweep.json")]
        third = third_fix if cid.startswith("fix-") else third_first
        # a packed chunk (pack-<n>) holds several small cards, and each verse names its own
        img0 = json.loads((S / f"{cid}.json").read_text(encoding="utf-8")).get("image")
        sw = {(v.get("image") or img0, v["ref"]): v for v in json.loads(Path(f).read_text(encoding="utf-8"))["verses"]}
        cf = {}
        # confirm2: the rest of a small card's verses, confirmed too (2026-10-24: on the small cards 16 of 280
        # sampled non-figures were figures, 6%, against 1% on the large ones, so their single reads were not kept)
        for cp in (S / f"{cid}.confirm.json", S / f"{cid}.confirm2.json"):
            if cp.exists():
                cf.update({(v.get("image") or img0, v["ref"]): v
                           for v in json.loads(cp.read_text(encoding="utf-8"))["verses"]})
        for (img, ref), v in sw.items():
            a = place(v["sense"])
            c = cf.get((img, ref))
            if not c:
                p, how = a, "single"
            elif place(c["sense"]) == a:
                p, how = a, "agreed"
            else:
                t = third.get((img, ref))
                votes = [a, place(c["sense"])] + ([place(t["sense"])] if t else [])
                top, n = collections.Counter(votes).most_common(1)[0]
                p, how = (top, "two of three") if n >= 2 else (None, "three-way" if t else "split, no third")
            out[f"{img}|{ref}"] = {"place": p, "how": how + (" (read again)" if cid.startswith("fix-") else ""),
                                   "sweep": v["sense"],
                                   "confirm": c and c["sense"], "third": (third.get((img, ref)) or {}).get("sense"),
                                   "identifies_with": v.get("identifies_with"), "speaker": v.get("speaker")}
    # counted from the final placements, so a verse read again is counted once, as its second reading
    for k, o in out.items():
        img, ref = k.split("|")
        basis[o["how"]] += 1
        per[img][o["place"] or "for Doug"] += 1
        if o["place"] == "figure" and o["sweep"] == "figure_keyed" and o.get("identifies_with"):
            keyed[img].append([ref, o["identifies_with"], o.get("speaker")])
    cand = json.loads((ROOT / "out" / "meaning" / "image-audit" / "candidates" / "tier2-final.json")
                      .read_text(encoding="utf-8"))["final"]
    both = [k for k in out if k in cand]
    differ = [k for k in both if out[k]["place"] and out[k]["place"] != cand[k]]
    new_figs = [k for k, v in out.items() if v["place"] in ("figure", "both") and k not in cand]
    (S / "settled.json").write_text(json.dumps(
        {"final": out, "per": {k: dict(v) for k, v in per.items()}, "keyed": keyed,
         "vs_candidates": {"shared": len(both), "differ": differ, "new_figures": new_figs}},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} verses on {len(per)} images: " + ", ".join(f"{k} {v}" for k, v in basis.most_common()))
    tot = collections.Counter(v["place"] or "for Doug" for v in out.values())
    print("placed: " + ", ".join(f"{k} {v}" for k, v in tot.most_common()))
    print(f"vs the candidate pass: {len(both)} verses read by both, {len(differ)} placed differently; "
          f"{len(new_figs)} figures the sweep found that the candidates never had")


def tiebreak_inputs(prefix="tiebreak"):
    """the splits with no third reading yet, as <prefix>-<n>.json chunks of 50 for a third blind reader; with
    prefix "fixtb", only the fix-<n> chunks' splits (read again with their own text), which never use the first
    third readings"""
    third = set()
    for f in glob.glob(str(S / f"{prefix}-*.result.json")):
        third |= {(v["image"], v["ref"]) for v in json.loads(Path(f).read_text(encoding="utf-8"))["verses"]}
    asked = set()
    for f in glob.glob(str(S / f"{prefix}-*.json")):
        if not f.endswith(".result.json"):
            asked |= {(v["image"], v["ref"]) for v in json.loads(Path(f).read_text(encoding="utf-8"))["verses"]}
    items = []
    for f in sorted(glob.glob(str(S / "*.sweep.json"))):
        cid = Path(f).name[:-len(".sweep.json")]
        if cid.startswith("fix-") != (prefix == "fixtb"):
            continue
        cps = [p for p in (S / f"{cid}.confirm.json", S / f"{cid}.confirm2.json") if p.exists()]
        if not cps:
            continue
        inp = json.loads((S / f"{cid}.json").read_text(encoding="utf-8"))
        img0 = inp.get("image")
        vv = {(v.get("image") or img0, v["ref"]): v for v in inp["verses"]}
        sw = {(v.get("image") or img0, v["ref"]): v for v in json.loads(Path(f).read_text(encoding="utf-8"))["verses"]}
        for v in (x for cp in cps for x in json.loads(cp.read_text(encoding="utf-8"))["verses"]):
            k = (v.get("image") or img0, v["ref"])
            s = sw.get(k)
            if s and place(s["sense"]) != place(v["sense"]) and k in vv and k not in third and k not in asked:
                x = vv[k]
                items.append({"chunk": cid, "image": k[0], "name": x.get("name") or inp.get("name"),
                              "desc": x.get("desc") or inp.get("desc"),
                              "ref": x["ref"], "before": x["before"], "text": x["text"], "after": x["after"]})
    start = 1 + max([int(Path(f).name.split("-")[1].split(".")[0]) for f in glob.glob(str(S / f"{prefix}-*.json"))]
                    or [-1])
    ids = []
    for i in range(0, len(items), 50):
        n = start + i // 50
        (S / f"{prefix}-{n}.json").write_text(json.dumps({"chunk": f"{prefix}-{n}", "verses": items[i:i + 50]},
                                                          ensure_ascii=False, indent=1), encoding="utf-8")
        ids.append(n)
    print(f"{len(items)} splits without a third reading -> chunks {ids}")


def confirm_rest():
    """for the packed (small-card) chunks: every verse the first confirmer did not read, as <cid>.check2.json"""
    ids = []
    for f in sorted(glob.glob(str(S / "pack-*.sweep.json"))):
        cid = Path(f).name[:-len(".sweep.json")]
        seen = set()
        cp = S / f"{cid}.confirm.json"
        if cp.exists():
            seen = {f"{v.get('image')}|{v['ref']}" for v in json.loads(cp.read_text(encoding="utf-8"))["verses"]}
        rest = [f"{v['image']}|{v['ref']}" for v in json.loads(Path(f).read_text(encoding="utf-8"))["verses"]
                if f"{v['image']}|{v['ref']}" not in seen]
        if rest and not (S / f"{cid}.confirm2.json").exists():
            (S / f"{cid}.check2.json").write_text(json.dumps(rest), encoding="utf-8")
            ids.append(cid)
    print(f"{len(ids)} chunks to confirm in full: {json.dumps(ids)}")


if __name__ == "__main__":
    import sys
    if "--tiebreak-inputs" in sys.argv:
        tiebreak_inputs("fixtb" if "--fix" in sys.argv else "tiebreak")
    elif "--confirm-rest" in sys.argv:
        confirm_rest()
    else:
        main()
