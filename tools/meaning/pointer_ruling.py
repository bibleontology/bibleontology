"""THE RULING ON THE HELD DIVINE ENDS, WRITTEN AS FILES THE PIPELINE READS
(2026-10-19; docs/review/divine-ends-2026-10-19.html, all three decisions "as
recommended").

  1. release   the 5,606 words no seat of the panel of eleven objected to, in
               two passes -> ontology/provenance/sweep/divine-releases-2026-10-19.json,
               read by tools/meaning/resolve_records.py
  2. correct   the 154 objected pointers: each wrong link is removed; where two
               judges named the same true referent AND those words are found
               among the nearby words, the corrected link is written
               -> ontology/provenance/sweep/pointer-corrections-2026-10-19.json,
               read by tools/sweep/import_layer.py
  3. open      the 163 held open stay held (no file changes them); docs/HELD.md
               records them as a class

    python tools/meaning/pointer_ruling.py
"""
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "out" / "meaning" / "divine-panel"
DEST = ROOT / "ontology" / "provenance" / "sweep"
RULING = ("Doug, 2026-10-19, on docs/review/divine-ends-2026-10-19.html: all three decisions marked as "
          "recommended (release the words no seat objected to in two passes; correct the objected pointers "
          "in the sweep; the open ones stay held)")
STOP = {"the", "a", "an", "of", "son", "daughter", "who", "one", "that", "his", "her", "their", "to", "in", "and"}
import sys  # noqa: E402
sys.path.insert(0, str(ROOT / "tools" / "sweep"))
from import_layer import DIVINE_PERSONS  # noqa: E402


def divine(d):
    s = re.sub(r"\D", "", str(d.get("strong") or "")).lstrip("0")
    return bool(s) and (("G" if d.get("lang") == "greek" else "H") + s) in DIVINE_PERSONS


def main():
    rows = [json.loads(x) for x in (PANEL / "verdicts.jsonl").read_text(encoding="utf-8").splitlines()]
    corr = {json.loads(x)["id"]: json.loads(x) for x in (PANEL / "corrections.jsonl").read_text(encoding="utf-8").splitlines()}
    released = [{"word": r["id"], "ref": r["ref"], "person": r["person"], "via": r["chain"][1]["node"]}
                for r in rows if r["verdict"].startswith("candidate")]
    objected = [r for r in rows if r["verdict"] == "objected"]

    # the words near each objected word, to find the judges' referent among them
    want = set()
    for r in objected:
        b, c, v = r["ref"].rsplit(".", 2)
        want |= {f"{b}.{c}.{int(v) - k}" for k in range(0, 4) if int(v) - k > 0}
    near = {}
    with gzip.open(ROOT / "out" / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("ref") in want and d.get("word") and d.get("class") in ("noun", "pron") and d.get("text"):
                near.setdefault(d["ref"], []).append(d)

    fixes, st = [], {"removed only": 0, "removed and relinked": 0}
    for r in objected:
        c = corr.get(r["id"]) or {}
        new, how = None, "no agreed referent"
        if c.get("agree"):
            ref_text = (c.get("sonnet") or {}).get("referent") or ""
            keys = [w.lower() for w in re.findall(r"[A-Za-z]+", ref_text) if w.lower() not in STOP]
            b, ch, v = r["ref"].rsplit(".", 2)
            for k in range(0, 4):                      # the word's own verse first, then back
                vv = f"{b}.{ch}.{int(v) - k}"
                hits = [d for d in near.get(vv, []) if d["id"] != r["id"]
                        and any(w.lower() in keys for w in re.findall(r"[A-Za-z]+", d["text"]))]
                if len(hits) == 1 and divine(hits[0]):
                    # a relink TO a word for God, the Father, Jesus or the Spirit
                    # is itself a divine identity made by rule: removed only,
                    # held for a ruling by hand (John 5:22 -> "Father", Ps 32:10 -> "LORD")
                    how = f"two judges named \"{ref_text}\"; it is a divine person's word, so held for Doug"
                    break
                if len(hits) == 1:
                    new, how = hits[0]["id"], f"two judges named \"{ref_text}\"; found as \"{hits[0]['text']}\" in {vv}"
                    break
                if len(hits) > 1:
                    how = f"two judges named \"{ref_text}\"; {len(hits)} words could be it in {vv}, none chosen"
                    break
            else:
                how = f"two judges named \"{ref_text}\"; not found among the nearby words"
        st["removed and relinked" if new else "removed only"] += 1
        fixes.append({"src": r["id"], "ref": r["ref"], "wrong": r["chain"][1]["node"], "dst": new, "how": how,
                      "objections": sorted({o.get("why") for o in (r["pass1"] or []) + (r["pass2"] or [])})[:3]})

    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "divine-releases-2026-10-19.json").write_text(json.dumps(
        {"ruling": RULING, "what": "words that reach God or Jesus only through a pointer chain, released as a class: "
                                   "no seat of the panel of eleven objected in either of two passes "
                                   "(ontology/provenance/meaning/divine-panel-2026-10-19.jsonl.gz)",
         "released": released}, ensure_ascii=False, indent=1), encoding="utf-8")
    (DEST / "pointer-corrections-2026-10-19.json").write_text(json.dumps(
        {"ruling": RULING, "what": "pointers the panel of eleven objected to: the wrong link is removed; a corrected "
                                   "link only where two judges named the same referent and it was found nearby "
                                   "(ontology/provenance/meaning/pointer-corrections-2026-10-19.jsonl.gz)",
         "corrections": fixes}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"released {len(released)}; corrections {len(fixes)}: {st}")
    for x in fixes[:10]:
        print(" ", x["ref"], x["src"].split("#")[1], "->", x["dst"], "|", x["how"][:90])


if __name__ == "__main__":
    main()
