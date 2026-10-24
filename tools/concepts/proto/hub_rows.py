"""Rows for the two concept-hub mockups (love, righteousness), each row a
plain label the grammar decides and up to four verses in the Berean's words.
Noun rows come from the words standing in the same phrase as the noun (the
"of God", "and justice", "do"); adjective rows from the role the word plays
(said of someone, or the one acting); verb rows from the frames. Prototype."""
import collections
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(r"<local> Ontology")
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402
D = S.load()
V = {}
for line in (ROOT / "data/bible/verses.bsb.jsonl").read_text(encoding="utf-8").splitlines():
    d = json.loads(line)
    if "b" in d:
        V[(d["b"], d["c"], d["v"])] = d["t"]


def eng(ref):
    b, c, v = S.bsb_ref(D, ref).split(".")
    b = S.MACULA_BACK.get(b, b)
    return (b, int(c), int(v))


def lab(k):
    return f"{S.TITLE.get(k[0], k[0])} {k[1]}:{k[2]}"


DIV = {"יהוה", "θεός", "אֱלֹהִים", "κύριος", "πατήρ", "אֲדֹנָי"}
CHRIST = {"Χριστός", "Ἰησοῦς", "υἱός"}
SPEC = {
 "love": {
  "noun": {"ἀγάπη", "אַהֲבָה"}, "adj": {"ἀγαπητός"},
  "noun_rows": [("The love of God", DIV), ("The love of Christ", CHRIST),
                ("Faith, hope and love", {"πίστις", "ἐλπίς"}), ("Love and truth", {"ἀλήθεια"}),
                ("Walk in love, put on love", {"περιπατέω", "ἐνδύω", "διώκω", "ζηλόω"})],
 },
 "righteousness": {
  "noun": {"δικαιοσύνη", "צְדָקָה", "צֶדֶק"}, "adj": {"δίκαιος", "צַדִּיק"},
  "noun_rows": [("Justice and righteousness", {"מִשְׁפָּט", "κρίσις", "κρίμα"}),
                ("Do righteousness", {"עָשָׂה", "ποιέω", "ἐργάζομαι"}),
                ("The righteousness of the LORD, of God", DIV),
                ("Righteousness by faith", {"πίστις", "πιστεύω"}),
                ("Righteousness and the law", {"νόμος", "תּוֹרָה"}),
                ("Seek, pursue, hunger for righteousness", {"ζητέω", "διώκω", "πεινάω", "רָדַף", "בִּקֵּשׁ"})],
 },
}
import unicodedata
NF = lambda x: unicodedata.normalize("NFC", x)  # noqa: E731  Hebrew vowel order: the typed and the data differ
for sp in SPEC.values():
    sp["noun"] = {NF(x) for x in sp["noun"]}; sp["adj"] = {NF(x) for x in sp["adj"]}
    sp["noun_rows"] = [(n, {NF(x) for x in ks}) for n, ks in sp["noun_rows"]]
out = {}
with gzip.open(ROOT / "data/macula-clauses.jsonl.gz", "rt", encoding="utf-8") as f:
    clauses = [json.loads(line) for line in f]
for r in clauses:
    for p in r.get("parts") or []:
        p["lemmas"] = [NF(x) for x in (p.get("lemmas") or [])]
for cid, sp in SPEC.items():
    rows = {name: [] for name, _ in sp["noun_rows"]}
    is_said, said_of = [], []
    for r in clauses:
        parts = r.get("parts") or []
        if not parts:
            continue
        clause_lems = {x for p in parts for x in (p.get("lemmas") or [])}
        for p in parts:
            lem = set(p.get("lemmas") or [])
            if lem & sp["noun"]:
                k = eng(r["ref"])
                for name, keys in sp["noun_rows"]:
                    if (lem | clause_lems) & keys and k not in rows[name]:
                        rows[name].append(k)
                        break
                if p["role"] == "s" and any(q["role"] in ("p", "v") for q in parts) and k not in is_said:
                    is_said.append(k)
            if lem & sp["adj"] and p["role"] in ("p", "s", "o") and eng(r["ref"]) not in said_of:
                said_of.append(eng(r["ref"]))
    out[cid] = {
        "noun_rows": [{"row": n, "n": len(ks), "eg": [{"ref": lab(k), "text": V.get(k, "")} for k in ks[:4]]}
                      for n, ks in rows.items()],
        "noun_is": {"n": len(is_said), "eg": [{"ref": lab(k), "text": V.get(k, "")} for k in is_said[:6]]},
        "adj": {"n": len(said_of), "eg": [{"ref": lab(k), "text": V.get(k, "")} for k in said_of[:6]]},
    }
Path(__file__).with_name("hub-rows.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for cid, o in out.items():
    print("==", cid)
    for r in o["noun_rows"]:
        print(f"  {r['row']:42} {r['n']:4}  {' | '.join(e['ref'] for e in r['eg'])}")
    print(f"  noun as subject: {o['noun_is']['n']}  {' | '.join(e['ref'] for e in o['noun_is']['eg'])}")
    print(f"  adjective said of: {o['adj']['n']}  {' | '.join(e['ref'] for e in o['adj']['eg'])}")
