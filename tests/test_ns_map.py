"""Every link in the schema map lands (plan 8.1e: the map at /ns/map with 1.2.0).

2026-10-20: not all deep links worked. Two causes, both found that day:
terms new in 1.2.0 were linked from a map drawn for 1.2.0 while the live pages
were still 1.1.0 (they land once 1.2.0 is published); and the vocabulary
pages gave an entry only to classes and properties, so a list's values
(claim:explicit), a voice (claim:narrator) and a metric (bom:cardWordShare)
had nothing to land on. This checks the map against the pages 1.2.0 will
publish, not the ones live now:

  - every link to /ns/<vocab>#term has an entry on that page as
    tools/ns_docs.py renders it from the vocabulary as generated now;
  - every link inside the map (#L-meaning, #std-dqv) has its target;
  - the committed map is what tools/ns_map.py draws now;
  - planted: a link to a term that does not exist is caught.

    python tests/test_ns_map.py          (preflight runs it so)
"""
import collections
import re
import sys
import tempfile
from pathlib import Path

import rdflib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ns_docs  # noqa: E402
import ns_map  # noqa: E402
import vocab_inventory as V  # noqa: E402

SITE = "https://bibleontology.org"
VOCABS = ("structure", "relation", "meaning", "claim")


def anchors(html):
    return set(re.findall(r'id="([^"]+)"', html)) | set(re.findall(r"id=([^\s\"'>]+)", html))


def broken(map_html, pages):
    bad = []
    for v in VOCABS + ("alignment",):
        for t in sorted(set(re.findall(rf'href="{SITE}/ns/{v}#([^"]+)"', map_html))):
            if t not in pages[v]:
                bad.append(f"/ns/{v}#{t}")
    own = anchors(map_html)
    for t in sorted(set(re.findall(r'href="#([^"]+)"', map_html))):
        if t not in own:
            bad.append(f"#{t} (in the map)")
    return bad


def main():
    fails = []
    gen, _ = V.generated()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pages = {}
        for v in VOCABS:
            ttl = tmp / f"{v}.ttl"
            ttl.write_bytes(gen[v])
            dest, _n = ns_docs.page(v, ttl, dest=tmp / f"{v}.html")
            pages[v] = anchors(dest.read_text(encoding="utf-8"))
        # the alignment page the release will publish (tools/ns_align.py)
        import ns_align
        ns_align.main({v: rdflib.Graph().parse(data=gen[v].decode("utf-8"), format="turtle") for v in VOCABS}, tmp)
        pages["alignment"] = anchors((tmp / "alignment.html").read_text(encoding="utf-8"))
        drawn = tmp / "schema-map.html"
        unreached = ns_map.main(drawn)
        now = drawn.read_text(encoding="utf-8")
    # THE STRUCTURE AND THE LINKS, NOT THE COUNTS (the committee's third
    # sitting, practitioner W3): the counts are dated on the page and move with
    # every data commit, so they are set aside here; what must not drift is
    # every box, label and link. From 1.2.0 the served copy is checked too (D8)
    def shape(s):
        return re.sub(r"\d[\d,.]*", "#", s)
    # the review copy lives in docs/, which a public copy does not carry
    copies = [p for p in (ROOT / "docs" / "review" / "schema-map.html",) if (ROOT / "docs" / "review").exists()]
    import ns_common
    if tuple(int(x) for x in ns_common.VERSION.split(".")) >= (1, 2, 0):
        copies.append(ROOT / "out" / "ns" / "map.html")
    for p in copies:
        if not p.exists() or shape(p.read_text(encoding="utf-8")) != shape(now):
            fails.append(f"{p.relative_to(ROOT)} is not what tools/ns_map.py draws now: python tools/ns_map.py")
    # EACH CLASS'S COUNT IS THE TYPED EXPORT'S (D4: PersonalBeing showed 11 for
    # ~1,674): the crosswalk the map counts by must give what the published
    # records are typed as
    import gzip
    import json
    typed = collections.Counter(re.findall(r"\ba bom:(\w+)", gzip.open(ROOT / "out" / "export" / "entities.ttl.gz", "rt",
                                                                      encoding="utf-8").read()))
    # every entity file, first record of an id wins, as the export reads them
    first, recs = ROOT / "ontology" / "entities" / "entities.jsonl", {}
    for p in [first] + sorted(q for q in first.parent.glob("*.jsonl") if q != first):
        for x in p.read_text(encoding="utf-8").splitlines():
            if x.strip():
                recs.setdefault(json.loads(x)["id"], json.loads(x).get("type"))
    kinds = collections.Counter(recs.values())
    gm = rdflib.Graph().parse(data=gen["meaning"].decode("utf-8"), format="turtle")
    FROM = rdflib.URIRef("https://bibleontology.org/ns/meaning#fromEntityType")
    for cls in set(gm.subjects(FROM, None)):
        name = str(cls).rsplit("#", 1)[1]
        n = sum(kinds.get(str(k), 0) for k in gm.objects(cls, FROM))
        if typed.get(name) and n != typed[name]:
            fails.append(f"the map counts {n:,} {name} records; the typed export has {typed[name]:,}")
    # a term in no picture must at least have its entry on the vocabulary page
    # the section's master link opens (the annotation terms: status, layer)
    left = {k: [t for t in v if t not in pages[k]] for k, v in unreached.items()}
    left = {k: v for k, v in left.items() if v}
    if left:
        fails.append(f"terms reached by no picture and no vocabulary page: {left}")
    bad = broken(now, pages)
    if bad:
        fails.append(f"{len(bad)} links land nowhere: {bad[:12]}")
    # PLANTED: a box linking a term that does not exist
    planted = now.replace("</main>", f'<a href="{SITE}/ns/claim#noSuchTerm">x</a><a href="#no-such-picture">y</a></main>')
    caught = broken(planted, pages)
    if not any("noSuchTerm" in b for b in caught) or not any("no-such-picture" in b for b in caught):
        fails.append("planted: a link to a missing term or picture was not caught")
    print(f"schema map: {len(set(re.findall(r'href=\"[^\"]+\"', now)))} distinct links; "
          f"{len(bad)} land nowhere; planted faults caught; {len(fails)} failures")
    for f in fails:
        print("FAIL " + f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
