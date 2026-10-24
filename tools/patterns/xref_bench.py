"""Benchmark: do the echoes find the quotations the BSB's own footnotes cite?

2026-09-28: as an audit/benchmark, go through whatever established list of
cross references exists (e.g. BSB footnotes) and make sure they are all
captured. The Berean Standard Bible (public domain)
footnotes a New Testament quotation with the verse it quotes: Rom 1:17
"Habakkuk 2:4", Rom 3:4 "Or when You are judged; Psalms 51:4 (see also LXX)".
Every scripture citation in an NT footnote is taken as a pair to find; a
range counts as found if any verse of it is linked.

For each pair: is the cited verse among the NT verse's echo links, and at
what band; the misses are listed so each can be read for why.

    python tools/patterns/xref_bench.py
        -> docs/review/XREF-BENCH.md
"""
import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
USFM = ROOT / "data" / "raw" / "usfm" / "engbsb"
sys.path.insert(0, str(ROOT / "tools"))
from acts import BOOK  # noqa: E402  MACULA code -> BSB code

BSB_TO_MACULA = {v: k for k, v in BOOK.items()}
USFM_ID = {"GEN": "Gen", "EXO": "Exo", "LEV": "Lev", "NUM": "Num", "DEU": "Deu",
           "JOS": "Jos", "JDG": "Jdg", "RUT": "Rut", "1SA": "1Sa", "2SA": "2Sa",
           "1KI": "1Ki", "2KI": "2Ki", "1CH": "1Ch", "2CH": "2Ch", "EZR": "Ezr",
           "NEH": "Neh", "EST": "Est", "JOB": "Job", "PSA": "Psa", "PRO": "Pro",
           "ECC": "Ecc", "SNG": "Sng", "ISA": "Isa", "JER": "Jer", "LAM": "Lam",
           "EZK": "Ezk", "DAN": "Dan", "HOS": "Hos", "JOL": "Jol", "AMO": "Amo",
           "OBA": "Oba", "JON": "Jon", "MIC": "Mic", "NAM": "Nam", "HAB": "Hab",
           "ZEP": "Zep", "HAG": "Hag", "ZEC": "Zec", "MAL": "Mal", "MAT": "Mat",
           "MRK": "Mrk", "LUK": "Luk", "JHN": "Jhn", "ACT": "Act", "ROM": "Rom",
           "1CO": "1Co", "2CO": "2Co", "GAL": "Gal", "EPH": "Eph", "PHP": "Php",
           "COL": "Col", "1TH": "1Th", "2TH": "2Th", "1TI": "1Ti", "2TI": "2Ti",
           "TIT": "Tit", "PHM": "Phm", "HEB": "Heb", "JAS": "Jas", "1PE": "1Pe",
           "2PE": "2Pe", "1JN": "1Jn", "2JN": "2Jn", "3JN": "3Jn", "JUD": "Jud",
           "REV": "Rev"}
# the book names the footnotes use -> MACULA codes
NAMES = {"Genesis": "Gen", "Exodus": "Exo", "Leviticus": "Lev",
         "Numbers": "Num", "Deuteronomy": "Deu", "Joshua": "Jos",
         "Judges": "Jdg", "Ruth": "Rut", "1 Samuel": "1Sa", "2 Samuel": "2Sa",
         "1 Kings": "1Ki", "2 Kings": "2Ki", "1 Chronicles": "1Ch",
         "2 Chronicles": "2Ch", "Ezra": "Ezr", "Nehemiah": "Neh",
         "Esther": "Est", "Job": "Job", "Psalms": "Psa", "Psalm": "Psa",
         "Proverbs": "Pro", "Ecclesiastes": "Ecc", "Song of Solomon": "Sng",
         "Isaiah": "Isa", "Jeremiah": "Jer", "Lamentations": "Lam",
         "Ezekiel": "Ezk", "Daniel": "Dan", "Hosea": "Hos", "Joel": "Jol",
         "Amos": "Amo", "Obadiah": "Oba", "Jonah": "Jon", "Micah": "Mic",
         "Nahum": "Nam", "Habakkuk": "Hab", "Zephaniah": "Zep",
         "Haggai": "Hag", "Zechariah": "Zec", "Malachi": "Mal"}
CITE = re.compile(r"(" + "|".join(sorted(map(re.escape, NAMES), key=len,
                                          reverse=True)) +
                  r")\s+(\d+):(\d+)(?:[–-](\d+))?")
FOOT = re.compile(r"\\f \+ \\fr (\d+):(\d+)\s*\\ft (.*?)\\f\*")
BANDS = [(13.3, "strong"), (11.4, "likely"), (9.5, "possible"), (0.0, "faint")]
NT_START = "MAT"


def kind_of(text):
    """What the footnote says the citation is. 2026-09-28: a lot of BSB
    footnotes are not cross references.
      quotation   the footnote is the source and nothing else, perhaps after
                  an alternative rendering: "Psalms 110:4", "Or when You are
                  judged; Psalms 51:4 (see also LXX)"
      see         a pointer: "See Deuteronomy 29:4 and Isaiah 29:10."
      background  anything else that happens to cite (Acts 20:16, the feast
                  of Shavuot, "Exodus 23:16")"""
    if re.search(r"\b[Ss]ee\b(?! also LXX)|\bcited\b|\bcf\b", text):
        return "see"
    tail = re.split(r"[;”]", text)[-1]
    rest = CITE.sub("", tail)
    rest = re.sub(r"\(see also LXX\)|LXX|\band\b|[,.;()\s]", "", rest)
    return "quotation" if not rest else "background"


def key():
    """(NT verse, [OT verses]) from every NT footnote citing the OT, in the
    graph's (MACULA) numbering."""
    moved = json.loads((OUT / "versemap.json").read_text(
        encoding="utf-8")).get("moved") or {}
    to_macula = {e: m for m, e in moved.items()}   # English -> MACULA
    pairs = []
    files = sorted(USFM.glob("*.usfm"))
    nt = False
    for p in files:
        s = p.read_text(encoding="utf-8")
        bid = re.search(r"\\id (\w+)", s).group(1)
        if bid == NT_START:
            nt = True
        if not nt or bid not in USFM_ID:
            continue
        book = USFM_ID[bid]
        for m in FOOT.finditer(s):
            c, v, text = m.group(1), m.group(2), m.group(3)
            for cm in CITE.finditer(text):
                ob, oc, ov, ov2 = NAMES[cm.group(1)], int(cm.group(2)), \
                    int(cm.group(3)), cm.group(4)
                rng = range(ov, int(ov2) + 1) if ov2 else [ov]
                ots = [to_macula.get(f"{ob}.{oc}.{x}", f"{ob}.{oc}.{x}")
                       for x in rng]
                pairs.append((f"{book}.{c}.{v}", ots, cm.group(0), text,
                              kind_of(text)))
    return pairs


def main():
    links = collections.defaultdict(dict)
    for line in gzip.open(OUT / "echoes.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(line)
        if r["kind"] == "NT->OT":
            links[r["from"]][r["to"]] = max(r["score"],
                                            links[r["from"]].get(r["to"], 0))
    pairs = key()
    found = collections.Counter()
    by_kind = collections.defaultdict(collections.Counter)
    misses = []
    for nt, ots, cite, text, kind in pairs:
        # the NT verse or its neighbour (a footnote sits on the verse where
        # the quotation ends; the quotation may start one verse before)
        best = 0.0
        for v in (nt, _step(nt, -1), _step(nt, 1)):
            for o in ots:
                for oo in (o, _step(o, -1), _step(o, 1)):
                    best = max(best, links.get(v, {}).get(oo, 0.0))
        band = next(n for lo, n in BANDS if best >= lo) if best else "missed"
        found[band] += 1
        by_kind[kind][band] += 1
        if band in ("missed", "faint"):
            misses.append((kind, nt, cite, best, text))
    n = len(pairs)
    BL = ("strong", "likely", "possible", "faint", "missed")
    lines = []
    for kind in ("quotation", "see", "background"):
        c = by_kind[kind]
        t = sum(c.values()) or 1
        cum = 0
        cells = []
        for b in BL[:-1]:
            cum += c[b]
            cells.append(f"{100 * cum / t:.0f}%")
        lines.append(f"| {kind} | {t} | " + " | ".join(cells) +
                     f" | {c['missed']} |")
    rep = ["# Cross-reference benchmark — the BSB's quotation footnotes", "",
           "Made by `tools/patterns/xref_bench.py` (Doug, 2026-09-28: *\"go "
           "through whatever established list of cross references we have "
           "(e.g. BSB footnotes) and make sure that we have captured "
           "them\"*). Every Old Testament citation in a New Testament "
           "footnote of the Berean Standard Bible is a pair to find; found "
           "if `out/echoes.jsonl.gz` links the NT verse (or a neighbour) to "
           "the cited verse (or a neighbour), graded by the band of the "
           "link.", "",
           f"**{n} cited pairs**, split by what the footnote says the "
           "citation is (`kind_of`): a *quotation* source, a *see* pointer, "
           "or *background* that happens to cite.", "",
           "Share found at each band or better (cumulative):", "",
           "| footnote kind | pairs | strong | +likely | +possible | +faint "
           "| missed |", "|---|---|---|---|---|---|---|",
           *lines, "",
           "## Missed or faint", "",
           "| kind | NT verse | footnote cites | best score | footnote |",
           "|---|---|---|---|---|"]
    for kind, nt, cite, best, text in sorted(misses):
        rep.append(f"| {kind} | {nt} | {cite} | {best or '-'} | "
                   f"{text.replace('|', '/')[:90]} |")
    (ROOT / "docs" / "review" / "XREF-BENCH.md").write_text(
        "\n".join(rep) + "\n", encoding="utf-8")
    print(f"{n} pairs: " + ", ".join(f"{b} {found[b]}" for b in BL))
    for line in lines:
        print(line)


def _step(v, d):
    b, c, x = v.rsplit(".", 2)
    return f"{b}.{c}.{int(x) + d}"


if __name__ == "__main__":
    main()
