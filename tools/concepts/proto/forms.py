"""Prototype for the concept hubs (2026-10-09): love and righteousness
by the forms the text uses -- the verb (who acts on whom, from the frames),
the noun (what the text says it is or does, and whose it is, from the
clauses), the adjective (who is called it). Every item a verse in the
Berean's words. Not wired into the site: a measurement for the morning."""
import collections
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(r"<local> Ontology")
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402
D = S.load()

CONCEPTS = {
    "love": {"verb": {"ἀγαπάω", "φιλέω", "אָהֵב", "אהב"}, "noun": {"ἀγάπη", "אַהֲבָה", "φιλία"},
             "adj": {"ἀγαπητός"}},
    "righteousness": {"verb": {"δικαιόω", "צָדַק"}, "noun": {"δικαιοσύνη", "צְדָקָה", "צֶדֶק", "δικαίωσις", "δικαίωμα"},
                      "adj": {"δίκαιος", "צַדִּיק"}},
}
V = {}
for line in (ROOT / "data/bible/verses.bsb.jsonl").read_text(encoding="utf-8").splitlines():
    d = json.loads(line)
    if "b" in d:
        V[(d["b"], d["c"], d["v"])] = d["t"]


def eng(ref):
    b, c, v = S.bsb_ref(D, ref).split(".")
    b = S.MACULA_BACK.get(b, b)
    return (b, int(c), int(v)), f"{S.TITLE.get(b, b)} {c}:{v}"


report = {}
for cid, forms in CONCEPTS.items():
    out = {"verb": collections.defaultdict(list), "noun_role": collections.defaultdict(list),
           "noun_of": collections.Counter(), "adj_role": collections.defaultdict(list)}
    # the verb: agent and patient from the frames
    with gzip.open(ROOT / "out/frames.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("lemma") in forms["verb"]:
                key, lab = eng(r["ref"])
                out["verb"][(" ".join(r.get("agent") or ["-"]), " ".join(r.get("patient") or ["-"]))].append(lab)
    # the noun and the adjective: the role their phrase plays in the clause
    with gzip.open(ROOT / "data/macula-clauses.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            for p in r.get("parts") or []:
                lem = set(p.get("lemmas") or [])
                if lem & forms["noun"]:
                    key, lab = eng(r["ref"])
                    out["noun_role"][p["role"]].append(lab)
                    # "the love of God": the other nouns in the same phrase
                    for x in p.get("lemmas") or []:
                        if x not in forms["noun"] and len(x) > 2 and x not in ("ὁ", "הַ", "καί", "וְ", "לְ", "בְּ", "ἐν"):
                            out["noun_of"][x] += 1
                if lem & forms["adj"]:
                    key, lab = eng(r["ref"])
                    out["adj_role"][p["role"]].append(lab)
    report[cid] = {
        "verb_frames": sum(len(v) for v in out["verb"].values()),
        "verb_top": [(f"{a} -> {p}", len(v), v[:3]) for (a, p), v in
                     sorted(out["verb"].items(), key=lambda x: -len(x[1]))[:10]],
        "noun_roles": {k: len(v) for k, v in out["noun_role"].items()},
        "noun_as_subject_eg": out["noun_role"].get("s", [])[:8],
        "noun_with": out["noun_of"].most_common(15),
        "adj_roles": {k: len(v) for k, v in out["adj_role"].items()},
        "adj_eg": out["adj_role"].get("s", [])[:6] + out["adj_role"].get("p", [])[:6],
    }
Path(__file__).with_name("forms.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
for cid, r in report.items():
    print("=" * 10, cid)
    for k, v in r.items():
        print(f"{k}: {v}")
