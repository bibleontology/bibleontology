"""Canonical filesystem layout for the project."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
RAW = DATA / "raw"
BIBLE = DATA / "bible"
VERSES_JSONL = BIBLE / "verses.jsonl"
BSB_JSONL = BIBLE / "verses.bsb.jsonl"   # the Berean: what the site shows, and all a public copy has
BOOK_TEXT = BIBLE / "text"  # one plain-text file per book, verse-prefixed


def text_path() -> Path:
    """The verse file to read: the KJV where this checkout has it, else the
    Berean, which has the same 31,102 verse ids and record shape (as
    Corpus.load does). The public repository carries no KJV, and eight modules
    that opened verses.jsonl directly died there (the code review,
    2026-10-22). A reader of wording should know the Berean words differ."""
    return VERSES_JSONL if VERSES_JSONL.exists() or not BSB_JSONL.exists() else BSB_JSONL

ONTOLOGY = ROOT / "ontology"
SCHEMA_DIR = ONTOLOGY / "schema"
RELATION_TYPES = SCHEMA_DIR / "relationship_types.yaml"
ENTITIES_DIR = ONTOLOGY / "entities"
PERSONS_DIR = ONTOLOGY / "persons"   # pre-generalization layout, still read
RELATIONS_DIR = ONTOLOGY / "relations"

BUILD = ROOT / "build"
GRAPH_JSON = BUILD / "graph.json"
