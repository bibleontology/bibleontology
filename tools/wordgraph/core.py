# Written by DeepSeek-V4-Pro (.delegate\results\20260927-201602.md); reviewed by Claude before use.
#!/usr/bin/env python3
"""Word-graph foundation for the Hebrew Bible knowledge graph.

Builds:
- out/word-occurrences.jsonl.gz  (one node per MACULA <w> morpheme)
- out/word-lexemes.jsonl.gz      (one node per lang/lemma/strongnumberx)
- out/word-edges.jsonl.gz        (next and of_lexeme edges)
- out/word-manifest.json         (inputs, outputs, counts, version)
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# Constants and paths

ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "data" / "raw" / "macula" / "hebrew"
GREEK_DIR = ROOT / "data" / "raw" / "macula" / "greek"


def input_paths() -> list:
    """Hebrew chapter files, then the 27 numbered Greek book files. (Claude,
    2026-09-27: the question whether it works for Greek.) The Greek folder also holds
    two WHOLE-NT files (commonformat.xml, nestle1904lowfat.xml); reading
    them too would count every Greek word three times."""
    heb = sorted(INPUT_DIR.glob("*.xml"), key=lambda p: p.name)
    grk = sorted((p for p in GREEK_DIR.glob("*.xml") if p.name[:2].isdigit()),
                 key=lambda p: p.name)
    return heb + grk
OUT_DIR = ROOT / "out"

OCCURRENCES_FILE = OUT_DIR / "word-occurrences.jsonl.gz"
LEXEMES_FILE = OUT_DIR / "word-lexemes.jsonl.gz"
EDGES_FILE = OUT_DIR / "word-edges.jsonl.gz"
MANIFEST_FILE = OUT_DIR / "word-manifest.json"

XML_ID_KEY = "{http://www.w3.org/XML/1998/namespace}id"
MACULA_SOURCE = "MACULA"
MACULA_LICENCE = "CC BY 4.0"

# The only MACULA <w> attributes this module is allowed to read, apart from
# xml:id and ref and the element text.  The graph must never contain the
# separately licensed fields named sdbh, lexdomain, coredomain, domain,
# contextualdomain, sensenumber, or ln.
READ_ATTRS = [
    "class",
    "lemma",
    "strongnumberx",
    "stronglemma",
    "type",
    "stem",
    "person",
    "gender",
    "number",
    "state",
    "english",
    "gloss",
    "greek",
    "greekstrong",
    "lang",
    "transliteration",
    "pos",
    # Greek (MACULA Greek names Strong's `strong`, and has no `english`)
    "strong",
    "normalized",
    "mood",
    "tense",
    "voice",
    "case",
]

REF_RE = re.compile(r"^(\S+)\s+(\d+):(\d+)!(\d+)$")


# ---------------------------------------------------------------------------
# Small helpers


def consonants(s: str) -> str:
    """Hebrew consonants only: points, accents and marks removed."""
    return "".join(ch for ch in (s or "") if "א" <= ch <= "ת") \
        or (s or "")


def src(value: object, source: str = MACULA_SOURCE, licence: str = MACULA_LICENCE) -> dict:
    """Wrap a source-derived value with its source and licence."""
    return {"value": value, "source": source, "licence": licence}


def map_book_code(code: str) -> str:
    """Map a MACULA book code like GEN, 1SA, SNG to Gen, 1Sa, Sng."""
    first_alpha = next((i for i, ch in enumerate(code) if ch.isalpha()), None)
    if first_alpha is None:
        raise ValueError(f"MACULA book code has no alphabetic character: {code!r}")

    out: list[str] = []
    for i, ch in enumerate(code):
        if ch.isalpha():
            out.append(ch.upper() if i == first_alpha else ch.lower())
        else:
            out.append(ch)
    return "".join(out)


def parse_ref(ref_raw: str) -> tuple[str, str]:
    """Return our verse id and book name from a MACULA ref like 'PSA 23:1!1'."""
    match = REF_RE.fullmatch(ref_raw.strip())
    if not match:
        raise ValueError(f"Unexpected MACULA ref: {ref_raw!r}")

    book_code, chapter, verse, _word_no = match.groups()
    book = map_book_code(book_code)
    verse_id = f"{book}.{int(chapter)}.{int(verse)}"
    return verse_id, book


def is_w_tag(tag: str) -> bool:
    """Local tag name check, so namespaced XML still works."""
    return tag.rsplit("}", 1)[-1] == "w"


def hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def iter_w_elements(root: ET.Element):
    """Yield all MACULA <w> elements in document order."""
    for elem in root.iter():
        if is_w_tag(elem.tag):
            yield elem


class GzipJsonlWriter:
    """Write one JSON object per line to a deterministic gzip-compressed file."""

    def __init__(self, path: Path):
        self.path = path
        self.count = 0
        self._closed = False
        path.parent.mkdir(parents=True, exist_ok=True)
        self._raw = open(path, "wb")
        # mtime=0 keeps the gzip output deterministic.
        self._gz = gzip.GzipFile(fileobj=self._raw, mode="wb", compresslevel=9, mtime=0)

    def write(self, obj: dict) -> None:
        if self._closed:
            raise IOError(f"writer already closed: {self.path}")
        line = json.dumps(
            obj,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self._gz.write((line + "\n").encode("utf-8"))
        self.count += 1

    def close(self) -> None:
        if not self._closed:
            self._gz.close()
            self._raw.close()
            self._closed = True

    def __enter__(self) -> "GzipJsonlWriter":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.close()
        return False


# ---------------------------------------------------------------------------
# Build


def build(version: str) -> dict:
    """Build the occurrence, lexeme and edge outputs, then the manifest."""
    if not INPUT_DIR.is_dir():
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    chapter_paths = input_paths()
    if not chapter_paths:
        raise FileNotFoundError(f"No MACULA XML files found in {INPUT_DIR}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    input_files: list[dict] = []
    lexeme_info: dict[str, dict] = {}
    seen_xml_ids: set[str] = set()
    prev_by_book: dict[str, str] = {}
    verse_position: dict[str, int] = {}
    book_occurrence_counts: dict[str, int] = {}

    occ_writer = GzipJsonlWriter(OCCURRENCES_FILE)
    edge_writer: GzipJsonlWriter | None = None

    try:
        edge_writer = GzipJsonlWriter(EDGES_FILE)

        for path in chapter_paths:
            data = path.read_bytes()
            input_files.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )

            root = ET.fromstring(data)

            for w in iter_w_elements(root):
                xml_id = w.attrib.get(XML_ID_KEY)
                if xml_id is None:
                    raise ValueError(
                        f"Missing namespaced xml:id on a <w> in {path.relative_to(ROOT)}"
                    )
                if xml_id in seen_xml_ids:
                    raise ValueError(f"Duplicate MACULA xml:id across corpus: {xml_id!r}")
                seen_xml_ids.add(xml_id)

                ref_raw = w.attrib.get("ref")
                if ref_raw is None:
                    raise ValueError(f"Missing ref on morpheme {xml_id!r}")
                verse_id, book = parse_ref(ref_raw)

                # 0-based position in document order within the verse.
                position = verse_position.get(verse_id, 0)
                verse_position[verse_id] = position + 1

                # Some MACULA morphemes are empty elements (structural
                # markers with no text) — treated as "" rather than an
                # error, matching tools/builder/source.py's `w.text or ""`.
                text = w.text or ""

                occ_node: dict = {
                    "id": xml_id,
                    "kind": "occurrence",
                    "ref": src(verse_id),
                    "position": src(position),
                    "text": src(text),
                }

                for attr in READ_ATTRS:
                    if attr in w.attrib:
                        occ_node[attr] = src(w.attrib[attr])

                occ_writer.write(occ_node)

                # Lexeme.
                # MACULA Greek has no `lang` and names Strong's `strong`
                lang = w.attrib.get("lang") or                     ("G" if path.parent == GREEK_DIR else None)
                lemma = w.attrib.get("lemma")
                strong = w.attrib.get("strongnumberx") or w.attrib.get("strong")
                if lang is None or lemma is None:
                    raise ValueError(
                        f"Missing lang/lemma on morpheme {xml_id!r}; "
                        "cannot build lexeme node"
                    )
                # A small number of morphemes (rare proper names such as
                # Tubal-Cain, Gen 4:22) carry no Strong's number in MACULA.
                # The lexeme is then keyed by lemma alone rather than
                # dropped or treated as an error.
                strong_key = strong if strong is not None else "-"
                # (Claude, 2026-09-27) ONE LEXEME PER WORD, NOT PER SPELLING.
                # MACULA points some lemmas two ways (עָוֹן / עָוֺן, both
                # Strong's 5771): 233 Strong's numbers were split into two
                # lexemes by pointing alone. With a Strong's number the key
                # is its CONSONANTS; the label is the commonest spelling.
                lemma_key = consonants(lemma) if strong is not None else lemma

                lexeme_id = f"lex:{lang}:{strong_key}:{lemma_key}"
                edge_writer.write(
                    {
                        "edge": "of_lexeme",
                        "from": xml_id,
                        "to": lexeme_id,
                        "source": MACULA_SOURCE,
                        "licence": MACULA_LICENCE,
                    }
                )

                info = lexeme_info.get(lexeme_id)
                if info is None:
                    info = {
                        "lang": lang,
                        "lemma": lemma,
                        "spellings": {},
                        "strong": strong,
                        "count": 0,
                        "books": set(),
                    }
                    lexeme_info[lexeme_id] = info
                info["count"] += 1
                info["books"].add(book)
                info["spellings"][lemma] = info["spellings"].get(lemma, 0) + 1
                # the label is the commonest spelling (ties: alphabetical)
                info["lemma"] = min(info["spellings"],
                                    key=lambda s: (-info["spellings"][s], s))

                # next edge within one book, across chapters.
                previous_id = prev_by_book.get(book)
                if previous_id is not None:
                    edge_writer.write(
                        {
                            "edge": "next",
                            "from": previous_id,
                            "to": xml_id,
                            "source": MACULA_SOURCE,
                            "licence": MACULA_LICENCE,
                        }
                    )

                prev_by_book[book] = xml_id
                book_occurrence_counts[book] = book_occurrence_counts.get(book, 0) + 1

    finally:
        if edge_writer is not None:
            edge_writer.close()
        occ_writer.close()

    # Lexeme nodes are deterministic: sorted by lexeme id.
    with GzipJsonlWriter(LEXEMES_FILE) as lex_writer:
        for lexeme_id in sorted(lexeme_info):
            info = lexeme_info[lexeme_id]
            lex_writer.write(
                {
                    "id": lexeme_id,
                    "kind": "lexeme",
                    "lang": src(info["lang"]),
                    "lemma": src(info["lemma"]),
                    "spellings": src(dict(sorted(info["spellings"].items()))),
                    "strong": src(info["strong"]),
                    "count": src(info["count"]),
                    "books": src(sorted(info["books"])),
                }
            )

    # Output hashes and manifest.
    outputs: dict[str, dict] = {}
    for output_path in (OCCURRENCES_FILE, LEXEMES_FILE, EDGES_FILE):
        rel = str(output_path.relative_to(ROOT))
        outputs[rel] = {
            "size": os.path.getsize(output_path),
            "sha256": hash_file(output_path),
        }

    occurrence_count = occ_writer.count
    lexeme_count = len(lexeme_info)
    next_edge_count = occurrence_count - len(book_occurrence_counts)
    of_lexeme_edge_count = occurrence_count
    edge_count = next_edge_count + of_lexeme_edge_count

    counts = {
        "occurrences": occurrence_count,
        "lexemes": lexeme_count,
        "next_edges": next_edge_count,
        "of_lexeme_edges": of_lexeme_edge_count,
        "edges": edge_count,
        "books": len(book_occurrence_counts),
        "input_files": len(input_files),
    }

    allowed_attributes = sorted(["xml:id", "ref", "text"] + READ_ATTRS)

    manifest = {
        "version": version,
        "inputs": input_files,
        "outputs": outputs,
        "counts": counts,
        "allowed_attributes": allowed_attributes,
        "schema": {
            "occurrence": (
                "One node per MACULA <w> morpheme. id is the MACULA xml:id. "
                "Source-derived fields are wrapped as {value, source, licence}."
            ),
            "lexeme": (
                "One node per (lang, lemma, strongnumberx). "
                "id is lex:<lang>:<strongnumberx>:<lemma>."
            ),
            "edge": (
                "One record per edge. edge is 'next' or 'of_lexeme'; "
                "from and to are node ids."
            ),
        },
    }

    with open(MANIFEST_FILE, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        fh.write("\n")

    return counts


# ---------------------------------------------------------------------------
# Verify


def verify(expected_version: str) -> None:
    """Re-read outputs and assert the graph invariants.

    Specifically:
    - every morpheme is exactly one occurrence
    - every occurrence has exactly one of_lexeme edge
    - next edges form one chain per book with no gaps
    - output hashes match the manifest
    - input files match the manifest
    """
    manifest_text = MANIFEST_FILE.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    assert manifest["version"] == expected_version, "manifest version mismatch"

    expected_allowed = sorted(["xml:id", "ref", "text"] + READ_ATTRS)
    assert manifest["allowed_attributes"] == expected_allowed, "allowed attribute list mismatch"

    # --- Inputs and morpheme ids -------------------------------------------
    chapter_paths = input_paths()
    expected_inputs: list[dict] = []
    input_ids: list[str] = []
    input_id_set: set[str] = set()

    for path in chapter_paths:
        data = path.read_bytes()
        expected_inputs.append(
            {
                "path": str(path.relative_to(ROOT)),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )

        root = ET.fromstring(data)
        for w in iter_w_elements(root):
            xml_id = w.attrib.get(XML_ID_KEY)
            if xml_id is None:
                raise AssertionError(f"Missing xml:id in {path}")
            if xml_id in input_id_set:
                raise AssertionError(f"Duplicate input xml:id: {xml_id!r}")
            input_id_set.add(xml_id)
            input_ids.append(xml_id)

    assert manifest["inputs"] == expected_inputs, "input file list/hash mismatch"

    # --- Output hashes ------------------------------------------------------
    for rel, meta in manifest["outputs"].items():
        p = ROOT / rel
        assert p.exists(), f"missing output: {rel}"
        assert os.path.getsize(p) == meta["size"], f"output size mismatch: {rel}"
        assert hash_file(p) == meta["sha256"], f"output hash mismatch: {rel}"

    # --- Occurrences --------------------------------------------------------
    occ_ids: list[str] = []
    occ_seen: set[str] = set()
    occ_book: dict[str, str] = {}

    with gzip.open(OCCURRENCES_FILE, "rt", encoding="utf-8") as fh:
        for line in fh:
            node = json.loads(line)
            oid = node["id"]
            if oid in occ_seen:
                raise AssertionError(f"duplicate occurrence id: {oid!r}")
            occ_seen.add(oid)
            occ_ids.append(oid)

            verse_id = node["ref"]["value"]
            book = verse_id.split(".", 1)[0]
            occ_book[oid] = book

    assert len(occ_ids) == manifest["counts"]["occurrences"], "occurrence count mismatch"
    assert occ_seen == input_id_set, "morpheme/occurrence mismatch"
    assert len(input_ids) == len(input_id_set), "input corpus must have unique xml:ids"

    # --- Lexemes ------------------------------------------------------------
    lexeme_ids: set[str] = set()

    with gzip.open(LEXEMES_FILE, "rt", encoding="utf-8") as fh:
        for line in fh:
            node = json.loads(line)
            lid = node["id"]
            if lid in lexeme_ids:
                raise AssertionError(f"duplicate lexeme id: {lid!r}")
            lexeme_ids.add(lid)

    assert len(lexeme_ids) == manifest["counts"]["lexemes"], "lexeme count mismatch"

    # --- Edges --------------------------------------------------------------
    next_out: dict[str, str] = {}
    next_in: dict[str, int] = defaultdict(int)
    of_lexeme_count: dict[str, int] = defaultdict(int)
    edge_total = 0
    next_edge_count = 0
    of_lexeme_edge_count = 0

    with gzip.open(EDGES_FILE, "rt", encoding="utf-8") as fh:
        for line in fh:
            edge = json.loads(line)
            edge_type = edge["edge"]
            from_id = edge["from"]
            to_id = edge["to"]
            edge_total += 1

            if edge_type == "next":
                if from_id not in occ_seen or to_id not in occ_seen:
                    raise AssertionError(f"next edge references unknown occurrence: {edge}")
                if occ_book[from_id] != occ_book[to_id]:
                    raise AssertionError(f"next edge crosses books: {edge}")
                if from_id == to_id:
                    raise AssertionError(f"next edge self-loop: {edge}")
                if from_id in next_out:
                    raise AssertionError(f"occurrence has more than one outgoing next edge: {from_id}")
                next_out[from_id] = to_id
                next_in[to_id] += 1
                next_edge_count += 1

            elif edge_type == "of_lexeme":
                if from_id not in occ_seen or to_id not in lexeme_ids:
                    raise AssertionError(f"of_lexeme edge references unknown node: {edge}")
                of_lexeme_count[from_id] += 1
                of_lexeme_edge_count += 1

            else:
                raise AssertionError(f"unknown edge type: {edge_type!r}")

    assert edge_total == manifest["counts"]["edges"], "edge count mismatch"
    assert next_edge_count == manifest["counts"]["next_edges"], "next edge count mismatch"
    assert (
        of_lexeme_edge_count == manifest["counts"]["of_lexeme_edges"]
    ), "of_lexeme edge count mismatch"

    # Every occurrence has exactly one of_lexeme edge.
    for oid in occ_seen:
        if of_lexeme_count[oid] != 1:
            raise AssertionError(
                f"occurrence {oid} has {of_lexeme_count[oid]} of_lexeme edges, expected 1"
            )

    # next edges form one chain per book with no gaps.
    book_occurrences: dict[str, set[str]] = defaultdict(set)
    for oid, book in occ_book.items():
        book_occurrences[book].add(oid)

    for book, occurrences in book_occurrences.items():
        heads = [oid for oid in occurrences if next_in.get(oid, 0) == 0]
        tails = [oid for oid in occurrences if oid not in next_out]

        if len(heads) != 1:
            raise AssertionError(f"book {book} has {len(heads)} next-chain heads, expected 1")
        if len(tails) != 1:
            raise AssertionError(f"book {book} has {len(tails)} next-chain tails, expected 1")

        head = heads[0]
        tail = tails[0]

        for oid in occurrences:
            in_count = next_in.get(oid, 0)
            if oid == head:
                assert in_count == 0, f"head {oid} unexpectedly has an incoming next edge"
            else:
                assert in_count == 1, f"occurrence {oid} does not have exactly one incoming next edge"

            if oid == tail:
                assert oid not in next_out, f"tail {oid} unexpectedly has an outgoing next edge"
            else:
                assert oid in next_out, f"occurrence {oid} has no outgoing next edge"

        visited: list[str] = []
        current: str | None = head
        while current is not None:
            if current in visited:
                raise AssertionError(f"cycle in next chain for book {book}")
            if current not in occurrences:
                raise AssertionError(
                    f"next chain for book {book} visits non-book occurrence {current}"
                )
            visited.append(current)
            current = next_out.get(current)

        if set(visited) != occurrences:
            raise AssertionError(f"next chain for book {book} has gaps or extra visits")
        if visited[-1] != tail:
            raise AssertionError(f"next chain for book {book} does not end at tail")


# ---------------------------------------------------------------------------
# Main


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build the word-graph foundation from MACULA Hebrew XML."
    )
    parser.add_argument(
        "--version",
        default="draft",
        help="frozen version string for the manifest (default: draft)",
    )
    args = parser.parse_args(argv)

    counts = build(args.version)
    verify(args.version)

    print("wordgraph verified ok")
    print(json.dumps(counts, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
