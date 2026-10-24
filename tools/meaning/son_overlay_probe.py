"""Which of the grammar's unresolved NT 'Son's does the old graph's overlay cover?"""
import collections, glob, gzip, json, re, sys, unicodedata
ROOT = "<local> Ontology/"
S = "<local>"
sys.path.insert(0, ROOT + "tools/patterns")
from mine import FAM, NTFAM  # noqa
TITLES = {"the_son_of_god", "the_son_of_man"}
NAME = {"Matt": "Mat", "Mark": "Mrk", "Luke": "Luk", "John": "Jhn", "Acts": "Act", "Rom": "Rom",
        "1Cor": "1Co", "2Cor": "2Co", "Gal": "Gal", "Eph": "Eph", "Phil": "Php", "Col": "Col",
        "1Thess": "1Th", "2Thess": "2Th", "1Tim": "1Ti", "2Tim": "2Ti", "Titus": "Tit", "Phlm": "Phm",
        "Heb": "Heb", "Jas": "Jas", "1Pet": "1Pe", "2Pet": "2Pe", "1John": "1Jn", "2John": "2Jn",
        "3John": "3Jn", "Jude": "Jud", "Rev": "Rev"}


def mref(r):
    m = re.match(r"(\w+) (\d+):(\d+)", r or "")
    return f"{NAME.get(m.group(1), m.group(1))}.{m.group(2)}.{m.group(3)}" if m else None


# verses where the overlay says the title is used of Jesus, or Jesus as the Son
cover = collections.defaultdict(set)
for l in open(ROOT + "ontology/entities/entities.jsonl", encoding="utf-8"):
    d = json.loads(l)
    if d["id"] in TITLES:
        for r in d.get("refs") or []:
            if mref(r):
                cover[mref(r)].add(f"{d['id']} record")
for f in glob.glob(ROOT + "ontology/relations/*.jsonl"):
    for l in open(f, encoding="utf-8"):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r.get("dst") in TITLES or (r.get("src") == "jesus" and "son" in (r.get("note") or "").lower()):
            for x in r.get("refs") or []:
                if mref(x):
                    cover[mref(x)].add(f"{r.get('src')} {r.get('type')} {r.get('dst')}")


def plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if not unicodedata.combining(c)).lower()


resolved = {s for s, _ in json.load(open(S + "son_hits.json"))}
sons = []
for l in gzip.open(ROOT + "out/structure-nodes.jsonl.gz", "rt", encoding="utf-8"):
    if l.startswith('{"_') or '"word": true' not in l:
        continue
    n = json.loads(l)
    if FAM.get(n["id"].split(".")[0], 0) >= NTFAM and plain(n.get("lemma")) == "υιος" and n.get("number") != "plural":
        sons.append(n["id"])
left = [s for s in sons if s not in resolved]
hit = [(s, sorted(cover[s.split("#")[0]])) for s in left if s.split("#")[0] in cover]
also = [s for s in resolved if s.split("#")[0] in cover]
print(f"{len(sons)} singular υἱός; grammar resolved {len(resolved)}; left {len(left)}")
print(f"overlay covers {len(hit)} of the {len(left)} left; and confirms {len(also)} the grammar already had")
for s, why in hit:
    print("  ", s, why[:2])
print("overlay verses with a Son claim:", len(cover))
