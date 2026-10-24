"""Prototype: love by who loves what, from the frames layer (agent, patient,
stance), every row a verse in the Berean's words. For the morning review
of the concept cards (2026-10-09); not wired into the site."""
import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(r"<local> Ontology")
OUT = Path(__file__).with_name("love-who.json")
LEM = {"ἀγαπάω", "φιλέω", "אָהֵב", "אהב"}
DIVINE = {"יהוה", "θεός", "πατήρ", "אֱלֹהִים", "κύριος", "אֲדֹנָי"}
JESUS = {"Ἰησοῦς", "Χριστός", "υἱός"}
FIRST = {"ἐγώ", "אֲנִי", "אָנֹכִי"}
# what is loved -> the row it opens (plain labels; the lemma decides, not a reading)
PATIENT_ROWS = [
    ("Love the LORD your God", {"יהוה", "θεός", "κύριος", "אֱלֹהִים", "שֵׁם", "πατήρ"}),
    ("Love one another", {"ἀλλήλων"}),
    ("Love your neighbor", {"πλησίον", "רֵעַ", "ἕτερος"}),
    ("Love your brother", {"ἀδελφός", "ἀδελφότης"}),
    ("Love your enemies", {"ἐχθρός"}),
    ("Husbands and wives", {"γυνή", "אִשָּׁה", "ἀνήρ", "אִישׁ"}),
    ("Love the foreigner", {"גֵּר", "ξένος"}),
    ("Love the law, wisdom and what is right", {"תּוֹרָה", "מִצְוָה", "מִשְׁפָּט", "חָכְמָה", "מוּסָר", "דַּעַת",
                                                 "צֶדֶק", "פִּקּוּד", "עֵדוּת", "חֹק", "אֱמֶת", "שָׁלוֹם",
                                                 "טוֹב", "חֶסֶד", "ἀλήθεια", "δικαιοσύνη", "φῶς", "ἐπιφάνεια"}),
    ("What the text warns against loving", {"κόσμος", "ἀργύριον", "כֶּסֶף", "שֹׁחַד", "שֵׁנָה", "יַיִן", "רַע",
                                            "שֶׁקֶר", "πρωτοκαθεδρία", "πρωτοκλισία", "ἀσπασμός", "δόξα",
                                            "σκότος", "ψυχή", "שִׁקּוּץ", "שַׁלְמֹנִים", "חָמָס", "κατάρα",
                                            "קְלָלָה", "מָוֶת", "θάνατος", "רָע", "פֶּשַׁע", "μισθός"}),
    ("Parents and children", {"בֵּן", "בַּת", "θυγάτηρ", "יוֹסֵף", "עֵשָׂו", "יַעֲקֹב"}),
]

V = {}
for line in (ROOT / "data/bible/verses.bsb.jsonl").read_text(encoding="utf-8").splitlines():
    d = json.loads(line)
    if "b" in d:
        V[(d["b"], d["c"], d["v"])] = d["t"]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402  (book ids only)
BACK = S.MACULA_BACK

speaker = {}
with gzip.open(ROOT / "out/speakers.jsonl.gz", "rt", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("ref"):
            speaker.setdefault(r["ref"], r.get("speaker"))


DATA = S.load()


def eng(ref):
    # the Berean's numbering, not the Hebrew's (Psalm titles shift a verse)
    b, c, v = S.bsb_ref(DATA, ref).split(".")
    return (BACK.get(b, b), int(c), int(v))


rows = collections.defaultdict(list)
unplaced = 0
with gzip.open(ROOT / "out/frames.jsonl.gz", "rt", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("lemma") not in LEM:
            continue
        key = eng(r["ref"])
        text = V.get(key, "")
        ag, pa = set(r.get("agent") or []), set(r.get("patient") or [])
        spk = speaker.get(r["ref"])
        if ag & FIRST and spk:
            ag |= {spk}
        if pa & FIRST and spk:
            pa |= {spk}
        stance = "forbidden" if r.get("prohibition") else (
            "commanded" if r.get("stance") == "command" or r.get("form") == "imperative" else "told")
        if r.get("polarity") == "negative" and stance == "told":
            stance = "not"
        item = {"ref": f"{S.TITLE.get(key[0], key[0])} {key[1]}:{key[2]}", "id": f"{key[0]}.{key[1]}.{key[2]}",
                "stance": stance, "agent": sorted(r.get("agent") or []), "patient": sorted(r.get("patient") or []),
                "text": text}
        placed = False
        if ag & (DIVINE | {"יהוה"}) and not pa & DIVINE:
            rows["The LORD loves"].append(item); placed = True
        elif ag & JESUS and not pa & DIVINE:
            rows["Jesus loves"].append(item); placed = True
        for name, lems in PATIENT_ROWS:
            if pa & lems and not placed:
                rows[name].append(item); placed = True
                break
        if not placed:
            rows["Other"].append(item); unplaced += 1

out = []
order = ["The LORD loves", "Jesus loves"] + [n for n, _ in PATIENT_ROWS] + ["Other"]
for name in order:
    xs = rows.get(name) or []
    seen, uniq = set(), []
    for x in xs:
        if x["id"] not in seen:
            seen.add(x["id"]); uniq.append(x)
    out.append({"row": name, "n": len(uniq),
                "by_stance": dict(collections.Counter(x["stance"] for x in uniq)), "verses": uniq})
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for r in out:
    print(f"{r['row']:42} {r['n']:4}  {r['by_stance']}  e.g. {', '.join(x['ref'] for x in r['verses'][:4])}")
