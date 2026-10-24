"""One verse's structure, for the reader's structure chip.

2026-09-25: the reader becomes BSB paragraphs, full width, and after
every verse two chips — the original language, and "the structure graph that
we are working on" (not on mobile) — each opening under its verse. Then,
because the verse diagrams are too wide to sit under a verse: the panel shows
the verse's CLAUSES compactly, one line each with its force and links, and a
click opens ONE clause's node diagram (versetree.mermaid_built(only=...)).

The reader speaks English verse numbers; the graph speaks MACULA's (Hebrew
numbering: BSB Exodus 8:16 is 8:12). The map is out/versemap.json, the one
/passage uses — per verse, so verses that move BETWEEN chapters (BSB Exodus
8:1-4 = Hebrew 7:26-29) map right, which a per-chapter offset cannot.

THE CHAPTER INDEX. Finding a chapter meant reading the graph files until it
turned up: about 6 s for John 3 once the graph held all three languages
(2026-09-27), and the first click looked broken. Now one pass splits both
files by chapter, each chapter's lines kept zlib-compressed in memory (about
the size of the .gz files), and a chapter is a decompress and a parse. The
server starts the pass in the background when it starts; the index is
rebuilt if the graph file changes (build.py --install).
"""
import collections
import gzip
import json
import re
import sys
import threading
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools"))
import ontology as O                                      # noqa: E402
import passage as P                                       # noqa: E402
import versetree as VT                                    # noqa: E402

_CACHE = collections.OrderedDict()          # chapter -> (nodes, edges, readings)
_CACHE_MAX = 12
_CACHE_LOCK = threading.Lock()


def _moved():
    try:
        return json.loads((OUT / "versemap.json").read_text(
            encoding="utf-8")).get("moved") or {}
    except (OSError, ValueError):
        return {}


def to_macula(book, ch, v):
    """English (BSB) reference -> MACULA's. `moved` maps MACULA -> English."""
    eng = f"{book}.{ch}.{v}"
    back = {e: m for m, e in _moved().items()}
    return back.get(eng, eng)


def to_english(ref):
    return _moved().get(ref, ref)


_STORE = None                               # the chapter blocks, once loaded
_LOCK = threading.Lock()
_REF = re.compile(r'"ref": "([^"]+)"')
FILES = (OUT / "placeholder-nodes.jsonl.gz", OUT / "placeholder-edges.jsonl.gz")
# S6's layer: the BSB's readings, kept apart from the structure and shown
# with it (edges marked reading: "BSB")
READINGS = OUT / "placeholder-readings.jsonl.gz"
# THE STRUCTURE SWEEP'S LAYER (plan 1.34, tools/sweep/import_layer.py): its
# readings ride in the same slot as the BSB's, kept apart from the structure
# and applied only where the panel draws it (_with_layer). 2026-10-17: the
# sweep layer output was approved for use.
SWEEP = OUT / "sweep-layer.jsonl.gz"
# THE ONE COPY OF THE CLAUSE STRUCTURE (2026-10-01, docs/LAUNCH.md). The server
# held every node and edge as a dict (1,353 MB) beside this module's
# compressed chapters, built from the same two files -- the structure twice.
# The aim: compact the clause structure while the app stays fully functional. Now
# every chapter is one compressed block per file, prebuilt here
# (python tools/structure.py --blocks), loaded as one bytes object, and the
# server reads its nodes and edges through chapter(); what it needed of the
# whole corpus at once (counts, which verses are parsed, a word's verses, ids
# filed under another chapter) is a summary written beside the blocks.
BLOCKS = OUT / "structure-chapters.bin"
LEVEL = 6


def _inputs():
    """{file: md5} of what the blocks are built from (file times are
    meaningless after a git checkout)."""
    import hashlib
    return {f.name: hashlib.md5(f.read_bytes()).hexdigest()
            for f in (*FILES, READINGS, SWEEP) if f.exists()}


def _build():
    """(header, data): every chapter's nodes, edges and readings lines, each
    compressed, laid end to end; and the summary of the whole corpus.
    The first "ref" on a line is the record's own: ids come before it."""
    parts = collections.defaultdict(lambda: ([], [], []))
    for i, f in ((0, FILES[0]), (1, FILES[1]), (2, READINGS), (2, SWEEP)):
        if not f.exists():
            continue
        for line in gzip.open(f, "rt", encoding="utf-8"):
            m = _REF.search(line)
            if m:
                parts[m.group(1).rsplit(".", 1)[0]][i].append(line)
    # THE WHOLE-CORPUS SUMMARY, in the node file's own order: the server's
    # dict of nodes iterated that way (a repeated id kept its first place and
    # took its last value), and its word pages depend on the order -- the
    # first lemma seen for a word, each word's verses in sequence
    ordered, ids_away = {}, {}
    if FILES[0].exists():
        for line in gzip.open(FILES[0], "rt", encoding="utf-8"):
            d = json.loads(line)
            if "id" not in d:
                continue
            ordered[d["id"]] = (d.get("lang"), d.get("strong"), d.get("ref"),
                                d.get("text"), d.get("lemma"))
            m = _REF.search(line)
            key = m.group(1).rsplit(".", 1)[0] if m else None
            # an id whose own prefix names another chapter is filed under its
            # record's ref, which is where chapter() will find it
            if key and d["id"].split("#")[0].rsplit(".", 1)[0] != key:
                ids_away[d["id"]] = key
            else:
                ids_away.pop(d["id"], None)      # a repeated id: the last line decides
    refs = sorted({r for (_l, _s, r, _t, _m) in ordered.values() if r})
    # how many verses have edges -- the server's banner counted its dict of
    # them ("31,152 units")
    edge_refs = {m.group(1) for key, (_nl, el, _rl) in parts.items()
                 for line in el for m in (_REF.search(line),) if m}
    # [lang, strong, ref, text, lemma] for every node with a Strong's number
    words = [list(v) for v in ordered.values() if v[1] is not None]
    n_nodes, n_lemma = len(ordered), sum(1 for v in ordered.values() if v[4])
    chapters, chunks, pos = {}, [], 0
    for key in sorted(parts):
        spans = []
        for lines in parts[key]:
            z = zlib.compress("".join(lines).encode("utf-8"), LEVEL) if lines else b""
            spans += [pos, len(z)]
            chunks.append(z)
            pos += len(z)
        chapters[key] = spans
    # the word rows are large and wanted once, at start: a block of their own
    # (read by words()), so they never sit in the header kept in memory
    z = zlib.compress(json.dumps(words, ensure_ascii=False,
                                 separators=(",", ":")).encode("utf-8"), LEVEL)
    chunks.append(z)
    header = {"_inputs": _inputs(), "chapters": chapters,
              "summary": {"nodes": n_nodes, "with_lemma": n_lemma, "refs": refs,
                          "edge_refs": len(edge_refs),
                          "ids_away": ids_away, "words": [pos, len(z)]}}
    return header, b"".join(chunks)


def write_blocks():
    """python tools/structure.py --blocks: out/structure-chapters.bin, a JSON
    header line then the blocks. Rebuild whenever the graph files change."""
    header, data = _build()
    with open(BLOCKS, "wb") as f:
        f.write(json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
        f.write(data)
    print(f"wrote {BLOCKS.relative_to(ROOT)}: {len(header['chapters']):,} chapters, "
          f"{len(data) / 1e6:.1f} MB of blocks")


def store():
    """(header, data), from the prebuilt file when it was built from these
    inputs, else built here (and said so: the build holds the whole graph as
    text for a moment, which a small server can ill afford)."""
    global _STORE
    with _LOCK:
        if _STORE is not None:
            return _STORE
        if BLOCKS.exists():
            with open(BLOCKS, "rb") as f:
                header = json.loads(f.readline())
                data = f.read()
            if header.get("_inputs") == _inputs():
                _STORE = (header, data)
                return _STORE
            print("  structure-chapters.bin was built from other graph files: building "
                  "in memory (run python tools/structure.py --blocks)", flush=True)
        _STORE = _build()
        return _STORE


def index():
    """{chapter: spans} -- which chapters exist (kept for callers that ask)."""
    return store()[0]["chapters"]


def summary():
    """What the server needs of the whole corpus at once (see BLOCKS)."""
    return store()[0]["summary"]


def words():
    """[lang, strong, ref, text, lemma] for every node with a Strong's
    number, in the node file's order -- unpacked on each call, not kept."""
    header, data = store()
    a, n = header["summary"]["words"]
    return json.loads(zlib.decompress(data[a:a + n]))


def chapter(key):
    """(nodes {id: record}, edges [records], readings [records]) of one
    chapter ("Psa.23"), every field as written; the last 12 stay parsed."""
    with _CACHE_LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    header, data = store()
    spans = header["chapters"].get(key)
    texts = []
    for i in range(3):
        if spans and spans[2 * i + 1]:
            a, n = spans[2 * i], spans[2 * i + 1]
            texts.append(zlib.decompress(data[a:a + n]).decode("utf-8"))
        else:
            texts.append("")
    nodes = {}
    for line in texts[0].splitlines():
        d = json.loads(line)
        if d.get("id"):
            nodes[d["id"]] = d
    edges = [json.loads(line) for line in texts[1].splitlines()]
    readings = [json.loads(line) for line in texts[2].splitlines()]
    with _CACHE_LOCK:
        _CACHE[key] = (nodes, edges, readings)
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    return nodes, edges, readings


def _chapter(ref):
    """(nodes, edges and readings together) of the chapter holding a verse --
    the structure panel's view, with the sweep's layer applied."""
    book, ch, _v = ref.split(".")
    nodes, edges, readings = chapter(f"{book}.{ch}")
    return _with_layer(nodes, edges, readings)


def _with_layer(nodes, edges, readings):
    """The readings applied for drawing: the BSB's and the sweep's edges
    added, the sweep's nodes (its groups, a generic entity, referents taken
    together) added, and the builder edges and groups it disputes taken
    away. A referent in another chapter (an earlier verse's word, a generic
    named elsewhere) is fetched so it can be drawn by its words. Nothing here
    is written back: the builder's files stay as they are."""
    nodes = dict(nodes)
    gone_groups = {d["id"] for d in readings
                   if d.get("action") == "remove" and "type" not in d and d.get("id")}
    gone = {(d["src"], d["type"], d["dst"]) for d in readings
            if d.get("action") == "remove" and "type" in d}
    out = [e for e in edges
           if (e.get("src"), e.get("type"), e.get("dst")) not in gone
           and e.get("src") not in gone_groups and e.get("dst") not in gone_groups]
    for g in gone_groups:
        nodes.pop(g, None)
    for d in readings:
        if d.get("action") == "remove":
            continue
        if d.get("node"):
            n = {k: v for k, v in d.items() if k != "node"}
            if d.get("kind") in ("generic", "together"):
                n["word"] = True        # drawn as a referent, by its words
            nodes[d["id"]] = n
        else:
            out.append(d)
    # referents named in another chapter, fetched once each
    for e in out:
        x = e.get("dst")
        if e.get("type") in ("refers_to", "member", "partitive") and isinstance(x, str) and x not in nodes:
            key = x.split("#")[0]
            key = key if key.count(".") == 1 else key.rsplit(".", 1)[0]
            try:
                n2, _e2, r2 = chapter(key)
            except Exception:
                continue
            if x in n2:
                nodes[x] = n2[x]
            else:
                found = next((r for r in r2 if r.get("id") == x and r.get("node")), None)
                if found:
                    nodes[x] = {**{k: v for k, v in found.items() if k != "node"}, "word": True}
    return nodes, out


def _clean(t):
    return " ".join(str(t or "").replace(".", " ").split())


def verse(book, ch, v):
    ref = to_macula(book, ch, v)
    nodes, edges = _chapter(ref)
    onto = O.load()
    label = {r["id"]: r.get("label", r["id"]) for r in onto["relations"]}
    clauses = sorted((n for n in nodes.values()
                      if n.get("clause") and n.get("ref") == ref),
                     key=lambda n: n.get("order", 0))
    force = {n["id"]: n.get("upper_force") for n in clauses}

    def cv(r):
        return r.split(".", 1)[-1].replace(".", ":")

    def other(nid):
        n = nodes.get(nid) or {}
        r = n.get("ref") or nid.split("#")[0]
        e_ = to_english(r)
        # the Berean number, and the Hebrew beside it where they differ
        both = {"ref": cv(e_), **({"heb": cv(r)} if e_ != r else {})}
        if n.get("pair"):
            return {**both, "kind": n.get("kind"),
                    "text": _clean(n.get("text"))[:90], "group": True}
        return {**both, "text": _clean(n.get("text"))[:90],
                "here": r == ref}

    out = []
    for n in clauses:
        cid = n["id"]
        links = []
        for e in edges:
            if not e.get("clause_link"):
                continue
            # the sweep's readings are marked as automated analysis on the page
            auto = {"auto": True} if e.get("reading") == "sweep" else {}
            if e.get("src") == cid:
                links.append({"dir": "out", "type": e["type"],
                              "label": label.get(e["type"], e["type"]),
                              **other(e["dst"]), **auto})
            elif e.get("dst") == cid:
                src = nodes.get(e["src"]) or {}
                if src.get("pair"):
                    # a group this clause is a member of, and its role there
                    links.append({"dir": "member", "type": e["type"],
                                  "label": label.get(e["type"], e["type"]),
                                  **other(e["src"]), **auto})
                else:
                    links.append({"dir": "in", "type": e["type"],
                                  "label": label.get(e["type"], e["type"]),
                                  **other(e["src"]), **auto})
        out.append({
            "id": cid, "order": n.get("order", 0),
            "text": _clean(n.get("text")),
            "force": n.get("upper_force"),
            "mood": VT.gloss_mood(n.get("verb_mood")) or None,
            "orphan": bool(n.get("orphan")),
            "links": links,
            "diagram": VT.mermaid_built(ref, graph=(nodes, edges),
                                        force=force, only=cid,
                                        show_ref=to_english,
                                        click="structWord"),
        })
    # A DIAGRAM'S WORDS OPEN THEIR WORD CARD. 2026-09-26: making the simple
    # concepts in the graph linkable to the root words, as in the
    # original-language expansion, would be really helpful. Each drawn
    # word calls structWord(<graph id>); this maps the id to the card's key,
    # the one the original-language strip uses: h/g + Strong's digits.
    keys = {}
    for c in out:
        for gid in re.findall(r'call structWord\("([^"]+)"\)', c["diagram"]):
            n = nodes.get(gid) or {}
            s = re.sub(r"\D", "", str(n.get("strong") or "")).lstrip("0")
            if s:
                keys[gid] = ("h" if n.get("lang") == "hebrew" else "g") + s
    # how far this stretch has been vetted, from the passages log
    worked = None
    for w in (onto.get("passages") or {}).get("worked") or []:
        a, b = w.get("from", ""), w.get("to", "")
        key = [int(x) if x.isdigit() else 0 for x in ref.split(".")[1:]]
        if ref.split(".")[0] == a.split(".")[0] and \
                [int(x) for x in a.split(".")[1:]] <= key <= \
                [int(x) for x in b.split(".")[1:]]:
            worked = {"name": w.get("name"), "status": w.get("status", "")
                      .split(".")[0][:120]}
    return {"ref": ref, "english": f"{book} {ch}:{v}", "clauses": out,
            "worked": worked, "keys": keys,
            "note": ("A working reading of the Hebrew and Greek structure, "
                     "built by rule from MACULA and checked against the "
                     "project's ontology. Most passages have not been vetted "
                     "by hand; treat it as a draft.")}


if __name__ == "__main__":
    if sys.argv[1:] == ["--blocks"]:
        write_blocks()
        sys.exit(0)
    b, c, v = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    r = verse(b, c, v)
    print(json.dumps({k: v for k, v in r.items() if k != "clauses"},
                     indent=1, ensure_ascii=False))
    for cl in r["clauses"]:
        print(cl["order"], cl["force"], cl["text"][:60],
              [(x["dir"], x["label"], x["ref"]) for x in cl["links"]],
              len(cl["diagram"]), "chars")
