"""Every chapter of the canon, profiled, clustered, and laid out per scroll.

2026-09-03: every scroll has a time-base visualization -- so each book is a
strip read left to right, and a shift is something you see rather than
something you infer from a table.

And, on what the clusters are allowed to mean: a made-up word like 'alpha-b'
could be used, saying that the last part of Daniel and Revelation after the
seven-church section are both sending a lot of 'alpha-b' signals.

**The clusters are deliberately unnamed.** Naming them invites arguing about
whether Revelation is "really" apocalyptic instead of measuring whether the
same signature recurs. A cluster earns its keep by appearing in two books
written centuries apart in different languages, not by having a good label.

The prediction, recorded in `docs/GROUPING-TESTS.md` **before this ran**:
Daniel's latter chapters and Revelation from 4 onward should land in the same
cluster, and Genesis 1, Leviticus 1 and Romans 3 should not. That file is held
out -- it must never be used to choose features.

    python tools/signature_map.py          # writes out/signature-map.json
"""
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bibleont.genre import DIMS, GENRE_VERSION, profile      # noqa: E402

OT = ["Gen", "Exo", "Lev", "Num", "Deu", "Jos", "Jdg", "Rut", "1Sa", "2Sa",
      "1Ki", "2Ki", "1Ch", "2Ch", "Ezr", "Neh", "Est", "Job", "Psa", "Pro",
      "Ecc", "Sng", "Isa", "Jer", "Lam", "Ezk", "Dan", "Hos", "Jol", "Amo",
      "Oba", "Jon", "Mic", "Nam", "Hab", "Zep", "Hag", "Zec", "Mal"]
NT = ["Mat", "Mrk", "Luk", "Jhn", "Act", "Rom", "1Co", "2Co", "Gal", "Eph",
      "Php", "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm", "Heb", "Jas",
      "1Pe", "2Pe", "1Jn", "2Jn", "3Jn", "Jud", "Rev"]

NAMES = {"Gen": "Genesis", "Exo": "Exodus", "Lev": "Leviticus",
         "Num": "Numbers", "Deu": "Deuteronomy", "Jos": "Joshua",
         "Jdg": "Judges", "Rut": "Ruth", "1Sa": "1 Samuel", "2Sa": "2 Samuel",
         "1Ki": "1 Kings", "2Ki": "2 Kings", "1Ch": "1 Chronicles",
         "2Ch": "2 Chronicles", "Ezr": "Ezra", "Neh": "Nehemiah",
         "Est": "Esther", "Job": "Job", "Psa": "Psalms", "Pro": "Proverbs",
         "Ecc": "Ecclesiastes", "Sng": "Song of Songs", "Isa": "Isaiah",
         "Jer": "Jeremiah", "Lam": "Lamentations", "Ezk": "Ezekiel",
         "Dan": "Daniel", "Hos": "Hosea", "Jol": "Joel", "Amo": "Amos",
         "Oba": "Obadiah", "Jon": "Jonah", "Mic": "Micah", "Nam": "Nahum",
         "Hab": "Habakkuk", "Zep": "Zephaniah", "Hag": "Haggai",
         "Zec": "Zechariah", "Mal": "Malachi", "Mat": "Matthew",
         "Mrk": "Mark", "Luk": "Luke", "Jhn": "John", "Act": "Acts",
         "Rom": "Romans", "1Co": "1 Corinthians", "2Co": "2 Corinthians",
         "Gal": "Galatians", "Eph": "Ephesians", "Php": "Philippians",
         "Col": "Colossians", "1Th": "1 Thessalonians",
         "2Th": "2 Thessalonians", "1Ti": "1 Timothy", "2Ti": "2 Timothy",
         "Tit": "Titus", "Phm": "Philemon", "Heb": "Hebrews", "Jas": "James",
         "1Pe": "1 Peter", "2Pe": "2 Peter", "1Jn": "1 John", "2Jn": "2 John",
         "3Jn": "3 John", "Jud": "Jude", "Rev": "Revelation"}

K = 7            # clusters. Unnamed on purpose.
ITERS = 40


def kmeans(pts, k, seed=1729):
    """Plain Lloyd's algorithm. No dependency, and the data is tiny."""
    random.seed(seed)
    cent = [list(p) for p in random.sample(pts, k)]
    assign = [0] * len(pts)
    for _ in range(ITERS):
        moved = False
        for i, p in enumerate(pts):
            best = min(range(k), key=lambda c:
                       sum((p[d] - cent[c][d]) ** 2 for d in range(len(p))))
            if best != assign[i]:
                assign[i], moved = best, True
        for c in range(k):
            members = [pts[i] for i in range(len(pts)) if assign[i] == c]
            if members:
                cent[c] = [sum(m[d] for m in members) / len(members)
                           for d in range(len(members[0]))]
        if not moved:
            break
    return assign, cent


def main() -> int:
    rows = []
    for book in OT + NT:
        ch = 1
        while ch <= 160:
            p = profile(book, ch)
            if not p.words:
                break
            rows.append({"book": book, "name": NAMES.get(book, book),
                         "ch": ch, "words": p.words,
                         "testament": "OT" if book in OT else "NT",
                         **{d: p.scores[d] for d in DIMS}})
            ch += 1
        print(f"  {book:5} {ch - 1:>3} chapters", flush=True)

    pts = [[r[d] for d in DIMS] for r in rows]
    assign, cent = kmeans(pts, K)
    for r, a in zip(rows, assign):
        r["cluster"] = a

    # Label clusters by nothing but a letter. The point: the name is not the
    # finding, the recurrence is.
    letters = "ABCDEFGHIJ"
    summary = []
    for c in range(K):
        members = [r for r in rows if r["cluster"] == c]
        if not members:
            continue
        books = {}
        for m in members:
            books.setdefault(m["name"], []).append(m["ch"])
        summary.append({
            "id": letters[c], "n": len(members),
            "centroid": {d: round(cent[c][i]) for i, d in enumerate(DIMS)},
            "books": sorted(books.items(), key=lambda kv: -len(kv[1]))[:8],
        })
    for r in rows:
        r["cluster"] = letters[r["cluster"]]

    out = {"version": GENRE_VERSION, "dims": list(DIMS), "k": K,
           "chapters": rows, "clusters": summary}
    (ROOT / "out" / "signature-map.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")

    print(f"\n{len(rows)} chapters, {K} unnamed clusters, genre {GENRE_VERSION}\n")
    for s in summary:
        top = sorted(s["centroid"].items(), key=lambda kv: -kv[1])[:3]
        print(f"  cluster {s['id']}  n={s['n']:<4} "
              + ", ".join(f"{k[:4]} {v}" for k, v in top))
        print(f"     mostly: "
              + ", ".join(f"{b} ({len(c)})" for b, c in s["books"][:5]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
