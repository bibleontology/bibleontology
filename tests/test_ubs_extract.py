"""The UBS lexicon extractor's acceptance tests (2026-11-03): the UBS Hebrew and Greek dictionaries to per-word senses.

    python -X utf8 tests/test_ubs_extract.py

Written before the code. The fixture is invented (no dictionary text): it has the dictionaries' shape only.

THE INTERFACE (tools/lexicon/ubs_extract.py, Python 3.9, standard library only):
  BOOKS                                  the 66 book codes the site uses, Genesis to Revelation, in canon order
  ref_of(code: str) -> str | None        "00100202400012" -> "Gen.2.24" (BBB CCC VVV, then word digits ignored);
                                         None for a code that is malformed or names no book 1-66
  keys_of(entry: dict, lang: str) -> list  from entry["StrongCodes"]: "H0001"/"A0004" -> "h1", "h4"; "G0026" -> "g26";
                                         a bare "2062" takes the language's letter; "H1234a" -> "h1234"; "" ignored;
                                         sorted, no duplicates
  extract(entries: list, lang: str, version: str) -> dict
        key -> {"key", "lemma", "source": "ubs-<lang>", "version", "senses": [...]}; a sense is
        {"domains": [{"code", "label"}], "short", "long", "glosses": [...], "refs": [...]} from each
        BaseForms[].LEXMeanings[] with its English LEXSenses (LanguageCode "en"). A sense with AIGenerated or
        HumanCheckRecommended true is left out. refs are ref_of() of LEXReferences, malformed ones dropped. An entry
        with several keys appears under each; two entries with one key have their senses joined, in input order.
  domain_index(extracted: dict) -> dict  domain code -> {"label", "words": sorted keys whose senses carry it}
  main(argv) CLI: ubs_extract.py hebrew|greek IN.json OUT.jsonl -> one JSON object per key, sorted by key
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "lexicon"))
try:
    import ubs_extract as U  # noqa: E402
except ImportError:
    print("FAIL tools/lexicon/ubs_extract.py does not exist yet")
    sys.exit(1)

fails = []


def check(ok, what):
    if not ok:
        fails.append(what)


def sense(short, refs, domains, ai=False, human=False, lang="en"):
    return {"LanguageCode": lang, "DefinitionShort": short, "DefinitionLong": short + " (long)", "Glosses": [short + "-g"],
            "AIGenerated": ai, "HumanCheckRecommended": human}


def meaning(code, label, refs, senses):
    return {"LEXDomains": [{"DomainCode": code, "Domain": label}], "LEXReferences": refs, "LEXSenses": senses}


def entry(lemma, codes, meanings):
    return {"Lemma": lemma, "StrongCodes": codes, "BaseForms": [{"LEXMeanings": meanings}]}


HEB = [
    entry("alpha", ["H0001"], [meaning("001", "Relatives", ["00100202400012", "bad", "06700100100002"],
                                       [sense("one", [], []), sense("un", [], [], lang="fr")]),
                               meaning("002", "Plants", ["00200300400006"], [sense("two", [], [], ai=True)])]),
    entry("beta", ["H0002", "A0002", ""], [meaning("001", "Relatives", ["01900100100004"], [sense("three", [], [])])]),
    entry("gamma", ["2062"], [meaning("003", "Time", ["00100100100002"], [sense("four", [], [], human=True)])]),
    entry("alpha-2", ["H0001a"], [meaning("004", "Motion", ["00100100200008"], [sense("five", [], [])])]),
]
GRK = [entry("delta", ["G0026"], [meaning("025", "Attitudes", ["04300301600016"], [sense("love", [], [])]),
                                  meaning("023", "Meals", ["06500101200012"], [sense("feast", [], [])])])]

# 1. BOOKS and references
check(len(U.BOOKS) == 66 and U.BOOKS[0] == "Gen" and U.BOOKS[-1] == "Rev", "1: BOOKS is not the 66 books, Gen to Rev")
site = ("Gen Exod Lev Num Deut Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr 2Chr Ezra Neh Esth Job Ps Prov Eccl Song Isa Jer "
        "Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal Matt Mark Luke John Acts Rom 1Cor 2Cor Gal Eph "
        "Phil Col 1Thess 2Thess 1Tim 2Tim Titus Phlm Heb Jas 1Pet 2Pet 1John 2John 3John Jude Rev").split()
check(list(U.BOOKS) == site, "1: BOOKS differ from the site's own book codes")
check(U.ref_of("00100202400012") == "Gen.2.24", f"1: Gen 2:24 read as {U.ref_of('00100202400012')}")
check(U.ref_of("06500101200012") == "Jude.1.12", f"1: Jude 1:12 read as {U.ref_of('06500101200012')}")
for bad in ("bad", "06700100100002", "", "0010020"):
    check(U.ref_of(bad) is None, f"1: malformed {bad!r} gave {U.ref_of(bad)}")

# 2. keys
check(U.keys_of(HEB[1], "hebrew") == ["h2"], f"2: H0002 + A0002 + '' gave {U.keys_of(HEB[1], 'hebrew')}")
check(U.keys_of(HEB[2], "hebrew") == ["h2062"], "2: a bare number did not take the language's letter")
check(U.keys_of(HEB[3], "hebrew") == ["h1"], "2: H0001a is not h1")
check(U.keys_of(GRK[0], "greek") == ["g26"], "2: G0026 is not g26")

# 3. extract: English only, AI-generated and human-check senses left out, refs converted, entries joined
h = U.extract(HEB, "hebrew", "v0.9.4")
check(set(h) == {"h1", "h2", "h2062"}, f"3: keys {sorted(h)}")
s1 = [s["short"] for s in h["h1"]["senses"]]
check(s1 == ["one", "five"], f"3: h1's senses {s1} (English only, the AI-generated one out, alpha-2 joined after)")
check(h["h1"]["senses"][0]["refs"] == ["Gen.2.24"], f"3: refs {h['h1']['senses'][0]['refs']}")
check(h["h1"]["senses"][0]["domains"] == [{"code": "001", "label": "Relatives"}], "3: domains")
check(h["h2062"]["senses"] == [], "3: a human-check sense was kept")
check(h["h1"]["source"] == "ubs-hebrew" and h["h1"]["version"] == "v0.9.4" and h["h1"]["lemma"] == "alpha", "3: header")
g = U.extract(GRK, "greek", "v1.1")
check([s["short"] for s in g["g26"]["senses"]] == ["love", "feast"] and g["g26"]["senses"][1]["refs"] == ["Jude.1.12"],
      "3: agape's two senses, the feast at Jude 1:12")

# 4. the domain index: other words in the domain
idx = U.domain_index(h)
check(idx["001"]["words"] == ["h1", "h2"] and idx["001"]["label"] == "Relatives", f"4: domain 001 {idx.get('001')}")
check("002" not in idx, "4: a domain only an AI-generated sense carried was indexed")

# 5. the command line writes one sorted object per key
tmp = Path(tempfile.mkdtemp())
(tmp / "in.json").write_text(json.dumps(HEB), encoding="utf-8")
U.main(["hebrew", str(tmp / "in.json"), str(tmp / "out.jsonl")])
rows = [json.loads(l) for l in open(tmp / "out.jsonl", encoding="utf-8")]
check([r["key"] for r in rows] == ["h1", "h2", "h2062"], f"5: written keys {[r['key'] for r in rows]}")

for f in fails:
    print("FAIL", f)
print(f"ubs extract: 5 groups of checks; {len(fails)} failures")
sys.exit(1 if fails else 0)
