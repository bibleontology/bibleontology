"""The themes against Torrey's New Topical Textbook (1897, public domain), by
the verses (P-2026-10-08-3).

2026-10-08: check this overall set of subthemes against external
benchmarks, not for contents but for completeness; filter the topics by
substance directly from the Bible, without losing sight of the concept
nodes/cards already held; test each Torrey verse reference, which has to fit
within the overall theme as well as the topic; and flag the Torrey pages that
fit nowhere, as a list.

Each Torrey topic's verses (its page at CCEL, fetched once into a folder) are
compared with every theme's verses -- the table, front page, chapters singled
out and outline, as the site (or with --preview, the preview) has them: how
many of the topic's verses each theme holds. The site's cards for the topic
(by name) are listed beside it. The judgment whether a topic belongs to a
theme's subject is made after this, by a reader; this measures.

    python tools/themes/torrey_bench.py <folder of Torrey pages> [--preview]
        -> out/torrey-bench.json
"""
from __future__ import annotations

import collections
import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if "--preview" in sys.argv:
    os.environ["BIBLEONT_SHOW_UNREVIEWED"] = "1"
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

BOOK = {"Ge": "Gen", "Ex": "Exod", "Le": "Lev", "Nu": "Num", "De": "Deut", "Jos": "Josh", "Jdj": "Judg",
        "Ru": "Ruth", "1Sa": "1Sam", "2Sa": "2Sam", "1Ki": "1Kgs", "2Ki": "2Kgs", "1Ch": "1Chr",
        "2Ch": "2Chr", "Ezr": "Ezra", "Ne": "Neh", "Neh": "Neh", "Es": "Esth", "Job": "Job", "Ps": "Ps",
        "Pr": "Prov", "Ec": "Eccl", "Song": "Song", "Isa": "Isa", "Jer": "Jer", "La": "Lam", "Eze": "Ezek",
        "Da": "Dan", "Ho": "Hos", "Joe": "Joel", "Am": "Amos", "Ob": "Obad", "Jon": "Jonah", "Mic": "Mic",
        "Na": "Nah", "Hab": "Hab", "Zep": "Zeph", "Hag": "Hag", "Zec": "Zech", "Mal": "Mal", "Mt": "Matt",
        "Mr": "Mark", "Lu": "Luke", "Joh": "John", "Ac": "Acts", "Ro": "Rom", "1Co": "1Cor", "2Co": "2Cor",
        "Ga": "Gal", "Eph": "Eph", "Php": "Phil", "Col": "Col", "1Th": "1Thess", "2Th": "2Thess",
        "1Ti": "1Tim", "2Ti": "2Tim", "Tit": "Titus", "Phm": "Phlm", "Heb": "Heb", "Jas": "Jas",
        "1Pe": "1Pet", "2Pe": "2Pet", "1Jo": "1John", "2Jo": "2John", "3Jo": "3John", "Jude": "Jude",
        "Re": "Rev"}
TOK = re.compile(r"\b([1-3]?[A-Z][a-z]{0,3})\s+(?=\d+\s*:)|(\d+)\s*:\s*(\d+)(?:\s*-\s*(\d+))?|,\s*(\d+)(?:\s*-\s*(\d+))?(?!\s*:)|(;)")


def topic_verses(seg, d):
    out, book, ch = [], None, None
    for m in TOK.finditer(seg):
        if m.group(1):
            book = BOOK.get(m.group(1))
        elif m.group(2) and book:
            ch, v1 = int(m.group(2)), int(m.group(3))
            for v in range(v1, int(m.group(4) or v1) + 1):
                out.append((book, ch, v))
        elif m.group(5) and book and ch:
            v1 = int(m.group(5))
            for v in range(v1, int(m.group(6) or v1) + 1):
                out.append((book, ch, v))
    return [x for x in dict.fromkeys(out) if x in d["verses"]]


def main():
    folder = Path(sys.argv[1])
    d = S.load()
    S.THEME_TAG_KINDS = {"row", "quote", "chapter", "concept", "also"}
    S._THEME_TAGS = None
    ix = S._theme_tags()
    theme_v = collections.defaultdict(set)
    for k, xs in ix.items():
        for x in xs:
            theme_v[x["theme"]].add(k)
    titles = {t["id"]: S._title(t["title"]) for t in S._theme_map()["themes"]}
    names = collections.defaultdict(list)
    for e in d["ents"].values():
        if e["type"] in ("concept", "observance", "assessment", "image", "covenant", "title") \
                and not str(e["id"]).startswith("theme_"):
            names[re.sub(r"^the ", "", (e.get("name") or "").lower())].append(e["id"])
    # the list of headings sits beside the folder of pages
    tl = next(p for p in (folder.parent / "torrey_topics.json", folder.parent.parent / "torrey_topics.json")
              if p.exists())
    topics = json.loads(tl.read_text(encoding="utf-8"))
    res = []
    for t in topics:
        fn = folder / (re.sub(r"[^A-Za-z0-9]+", "_", t) + ".html")
        if not fn.exists():
            continue
        s = fn.read_text(encoding="utf-8", errors="replace")
        txt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(
            r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S))))
        i = txt.find(t, txt.find(t) + len(t))
        j = txt.find("Prev", i)
        vs = topic_verses(txt[i:j if j > i else None], d)
        over = sorted(((len(set(vs) & theme_v[tid]), tid) for tid in theme_v), reverse=True)
        head = re.sub(r",.*$|\s*\(.*?\)", "", t).strip().lower()
        res.append({"topic": t, "verses": len(vs),
                    "themes": [{"theme": tid, "title": titles.get(tid, tid), "shared": n,
                                "share": round(n / len(vs), 2) if vs else 0} for n, tid in over[:4] if n],
                    "cards": names.get(re.sub(r"^the ", "", head), [])[:3]})
    out = ROOT / "out" / "torrey-bench.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    best = [r["themes"][0]["share"] if r["themes"] else 0 for r in res]
    print(f"{len(res)} topics, {sum(r['verses'] for r in res)} verses; best theme share: "
          f">=50% {sum(b >= .5 for b in best)}, 20-50% {sum(.2 <= b < .5 for b in best)}, "
          f"<20% {sum(0 < b < .2 for b in best)}, none {sum(b == 0 for b in best)}")


if __name__ == "__main__":
    main()
