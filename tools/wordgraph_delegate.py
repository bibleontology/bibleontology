"""Have DeepSeek code the Step 2 word-graph builder (2026-09-27:
delegate coding the builder to DeepSeek, worst case throw it away; do not let
it produce nothing by accidentally running out of money).

Two independent calls, each saving its module the moment it returns, so a
stop after the first still leaves something that runs:
  1. core   -> tools/wordgraph/core.py    (occurrences, lexemes, manifest)
  2. layers -> tools/wordgraph/layers.py  (per-lexeme attributes)
Before each call the DeepSeek balance is checked against a floor; below it
the run stops cleanly and says so.

    python tools/wordgraph_delegate.py [core|layers|both]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from bibleont import delegate as D                        # noqa: E402

OUT = ROOT / "tools" / "wordgraph"
FLOOR = 0.20                          # dollars left before a call may start
SAMPLES = (ROOT / "out" / "wordgraph-samples.txt").read_text(encoding="utf-8")

COMMON = """You are writing Python 3 (standard library only) for a Hebrew Bible knowledge graph. You have NO tools: everything is in this message. Answer with the module in one ```python block, then nothing else but a short VERIFY list.

THE INPUTS (real samples below):
- MACULA Hebrew syntax trees: one XML file per chapter, data/raw/macula/hebrew/*.xml (sorted names give canonical order). Every <w> is one MORPHEME with a unique `xml:id` (read with the key "{{http://www.w3.org/XML/1998/namespace}}id"). `ref` is "BOOK C:V!n", where n is the whitespace-word number, not unique. Book codes map to ours as in: GEN->Gen, EXO->Exo, 1SA->1Sa, PSA->Psa, SNG->Sng, EZK->Ezk, JOL->Jol, NAM->Nam (first letter upper, the rest lower, digits kept). Our verse ids are "Book.C.V".
- READ ONLY THESE ATTRIBUTES: xml:id, ref, class, lemma, strongnumberx, stronglemma, type, stem, person, gender, number, state, english, gloss, greek, greekstrong, lang, transliteration, pos, and the element text. NEVER read or copy any other attribute. In particular never touch sdbh, lexdomain, coredomain, domain, contextualdomain, sensenumber or ln: they are licensed and must not enter the graph.
- out/structure-nodes.jsonl.gz: the structure graph, one JSON object per line. A clause node has "clause": true, "upper_force" (assertion, directive, question, nonfinite) and "src" (the xml:ids of its morphemes).
- out/bsb-align.jsonl.gz: the Berean Standard Bible, one verse per line, with "spans" [start, end, "h<strong>"] marking English the Berean editors tagged to a Hebrew Strong's number.

{samples}

RULES
- Deterministic: the same inputs give byte-identical outputs (sort keys, sort lists, no timestamps inside data files).
- Every attribute you write carries its source, e.g. {{"value": ..., "source": "MACULA", "licence": "CC BY 4.0"}} or {{"source": "BSB", "licence": "public domain"}}.
- Stream gzip JSONL; the corpus is ~475,000 morphemes, so keep memory reasonable.
- Fail loudly (raise) on anything unexpected rather than skipping silently. Print counts at the end.
- No one-offs, no hard-coded verse references.
"""

VIEWER = """You are writing a single static HTML file (inline CSS and JS, no build step, no external network requests except loading normal fonts is NOT needed) that lets someone BROWSE a word graph, for a non-technical reviewer.

DATA IT READS (already built, do not regenerate): out/word-lexemes.jsonl.gz and out/word-lexeme-layers.jsonl.gz are gzip JSONL — too big to embed. Their REAL shape, one line from each file:

{viewer_samples}

Instead, write TWO things:
1. tools/wordgraph/export_viewer_data.py: a small Python script (stdlib + gzip + json only) that reads out/word-lexemes.jsonl.gz and out/word-lexeme-layers.jsonl.gz, joins them by lexeme id, and writes out/wordgraph-viewer-data.json — a single JSON array, each element one lexeme: {id, lemma, language, strong, count, books, usual_gloss, glosses, stems, usual_greek, septuagint, speech_types, bsb_renderings}. Keep it under 15MB (if the full set is bigger, keep the 3000 most frequent lexemes and print how many were dropped).
2. tools/wordgraph/viewer.html: loads wordgraph-viewer-data.json via fetch('wordgraph-viewer-data.json') (relative path, same folder), and shows:
   - a search box filtering by lemma or gloss (client-side, case-insensitive substring)
   - a sortable table: lemma, language, usual gloss, occurrence count, top Septuagint equivalent
   - clicking a row expands a detail panel: full gloss frequency list, stem distribution, speech-type distribution (as a small bar or text breakdown), BSB rendering frequencies — each clearly labelled with its source (MACULA / BSB / Septuagint via MACULA)
   - a simple language filter (Hebrew / Greek / all)
Keep it plain, readable, no frameworks, works when opened via a local HTTP server (not file://, since fetch needs http). Comment the file with a one-line note on how to serve it: "python -m http.server, from the tools/wordgraph directory, or via app2/server.py if wired in."

RETURN both files, each in its own ```python or ```html block, filenames as comments on the first line. No prose beyond a short VERIFY list.
"""

TASKS = {
    "core": COMMON + """
WRITE tools/wordgraph/core.py, the word-graph FOUNDATION:
1. An OCCURRENCE node per MACULA morpheme: id = its xml:id; ref (our verse id), position in the verse (0-based, in document order), text, and the allowed attributes. Edge `next` from each occurrence to the following one in document order (across verses and chapters within a book; not across books).
2. A LEXEME node per (language, lemma, strongnumberx): id "lex:H<strong>:<lemma>"; count of occurrences; the set of books it occurs in. Edge `of_lexeme` from each occurrence to its lexeme.
3. out/word-occurrences.jsonl.gz, out/word-lexemes.jsonl.gz, out/word-edges.jsonl.gz, and out/word-manifest.json, holding: input file list with sizes and sha256, output sha256s, counts, the allowed attribute list, and a "frozen" version string passed on the command line (default "draft").
4. A check function `verify()` that re-reads the outputs and asserts: every morpheme is exactly one occurrence; every occurrence has exactly one lexeme; `next` forms one chain per book with no gaps; output hashes match the manifest. Run it at the end of main().
Command line: python tools/wordgraph/core.py [--version V]
""",
    "viewer": VIEWER,
    "layers": COMMON + """
WRITE tools/wordgraph/layers.py. It reads the outputs of tools/wordgraph/core.py (out/word-occurrences.jsonl.gz, out/word-lexemes.jsonl.gz: occurrence ids are MACULA xml:ids; each occurrence has "lexeme") and adds PER-LEXEME attributes, written to out/word-lexeme-layers.jsonl.gz (one object per lexeme id). Each layer is a separate function, and each value records its source:
1. glosses: the frequency of each MACULA `english` rendering, and the most frequent one as "usual" (source MACULA).
2. stems: for verbs, the frequency of each `stem` (qal, niphal, piel ...) (source MACULA).
3. septuagint: the frequency of each (greek, greekstrong) pair MACULA records on the lexeme's occurrences; the top one as "usual_greek" (source MACULA, which aligns the Septuagint).
4. speech_types: for each clause in out/structure-nodes.jsonl.gz with "upper_force", every occurrence in its "src" counts one for that force; the lexeme gets the normalized distribution over assertion / directive / question / nonfinite, with the raw counts (source: the structure graph).
5. bsb_renderings: for each BSB verse, each span's tagged English (text[start:end]) counts one for that Strong's number; attach to every lexeme with that strongnumberx (normalize both by stripping leading zeros and any trailing letter, and REPORT how many lexemes matched and how many Strong's numbers in the BSB matched no lexeme; do not guess across numbers) (source BSB).
Print per-layer coverage (how many lexemes got each layer). Command line: python tools/wordgraph/layers.py
""",
}


def run(name):
    bal = D.balance_usd()
    if bal is not None and bal < FLOOR:
        print(f"STOP before {name}: DeepSeek balance ${bal:.2f} is below "
              f"${FLOOR:.2f}; nothing sent (add funds, then rerun "
              f"'{name}')")
        return False
    task = TASKS[name]
    if "{samples}" in task:
        task = task.replace("{samples}", SAMPLES)
    if "{viewer_samples}" in task:
        vs_path = ROOT / "out" / "wordgraph-viewer-samples.txt"
        vs = vs_path.read_text(encoding="utf-8") if vs_path.exists() else ""
        task = task.replace("{viewer_samples}", vs)
    res = D.run(task, level=3, label=f"wordgraph-{name}", blind=True,
                effort="high")
    ans = res.get("answer") or ""
    tok = res.get("tokens") or {}
    blocks = re.findall(r"```(python|html)\n(.*?)```", ans, re.S)
    print(f"{name}: ${res.get('cost')} reasoning {tok.get('reasoning')} / "
          f"{tok.get('completion')} stopped={res.get('stopped') or res.get('refused')} "
          f"blocks={len(blocks)}")
    if not blocks:
        print(f"BREAKER: no module in the {name} answer; saved nothing")
        return False
    OUT.mkdir(exist_ok=True)
    note = f"Written by DeepSeek-V4-Pro ({res.get('result_file')}); " \
        f"reviewed by Claude before use."
    saved = []
    for kind, body in blocks:
        header = f"<!-- {note} -->" if kind == "html" else f"# {note}"
        first = body.strip().splitlines()[0] if body.strip() else ""
        m = re.search(r"([\w./]+\.(?:py|html))", first)
        fname = m.group(1).split("/")[-1] if m else \
            (f"{name}.py" if kind == "python" else f"{name}.html")
        p = OUT / fname
        p.write_text(header + "\n" + body, encoding="utf-8")
        saved.append(p)
        print(f"saved {p.relative_to(ROOT)}")
    return bool(saved)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    for n in (["core", "layers"] if which == "both" else [which]):
        if not run(n):
            break
