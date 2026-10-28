"""The traditions layer: what each tradition, church body and school of reading has itself written, and which
reading of which question it states (2026-10-26).

Derived from the question cards by tools/traditions/build.py into ontology/traditions/nodes.jsonl and edges.jsonl;
declared in ontology/schema/traditions.json. This module reads the layer and checks it, so `python -m
bibleont.validate` fails on a node or edge that carries no Bible verse, names a record that does not exist, or uses
a kind or relation the schema does not declare. It does not compare the layer with the cards: that is
tests/test_traditions.py, so a card edited under review does not turn the validator red.

Standing rule (the owner's): no node, edge or shown link without Biblical backup. A document edge points at the
verses of the readings it supports."""

from __future__ import annotations

import json
from pathlib import Path

from .paths import ONTOLOGY
from .refs import RefError, parse_ref

LAYER = ONTOLOGY / "traditions"
SCHEMA = ONTOLOGY / "schema" / "traditions.json"
CERTAINTY = {"explicit"}


def load_schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_layer(layer: Path | None = None) -> tuple[list[dict], list[dict]]:
    layer = layer or LAYER
    return _rows(layer / "nodes.jsonl"), _rows(layer / "edges.jsonl")


def problems(corpus=None, nodes=None, edges=None, schema=None) -> list[tuple[str, str, str, str]]:
    """(level, code, message, subject) for everything wrong with the layer; empty when it is sound"""
    if nodes is None or edges is None:
        n, e = load_layer()
        nodes = n if nodes is None else nodes
        edges = e if edges is None else edges
    schema = schema or load_schema()
    out: list[tuple[str, str, str, str]] = []
    add = lambda code, msg, subj="": out.append(("error", code, msg, subj))        # noqa: E731
    kinds, rtypes = schema["node_kinds"], schema["relation_types"]

    def refs_ok(refs, subj, what):
        if not refs:
            add(f"tradition.{what}_no_refs", f"{what} cites no verse", subj)
            return
        for ref in refs:
            try:
                parsed = parse_ref(ref)
            except RefError as exc:
                add(f"tradition.{what}_bad_ref", str(exc), subj)
                continue
            if corpus is not None and not corpus.ref_exists(parsed):
                add(f"tradition.{what}_dead_ref", f"{ref} resolves to no verse", subj)

    by_id: dict[str, dict] = {}
    for nd in nodes:
        nid = nd.get("id")
        if nid in by_id:
            add("tradition.duplicate_id", "defined twice", nid)
        by_id[nid] = nd
        if nd.get("type") not in kinds:
            add("tradition.unknown_kind", f"{nd.get('type')!r} is not a kind traditions.json declares", nid)
        if not nd.get("name"):
            add("tradition.node_no_name", "node has no name", nid)
        refs_ok(nd.get("refs"), nid, "node")

    seen: set[tuple] = set()
    for ed in edges:
        subj = f"{ed.get('src')} -{ed.get('type')}-> {ed.get('dst')}"
        spec = rtypes.get(ed.get("type"))
        if spec is None:
            add("tradition.unknown_type", f"{ed.get('type')!r} is not a relation traditions.json declares", subj)
        key = (ed.get("src"), ed.get("type"), ed.get("dst"))
        if key in seen:
            add("tradition.duplicate_edge", "the same edge twice; merge their verses", subj)
        seen.add(key)
        for side in ("src", "dst"):
            nd = by_id.get(ed.get(side))
            if nd is None:
                add("tradition.unknown_node", f"{side} {ed.get(side)!r} is not a node", subj)
            elif spec and nd.get("type") not in spec[side]:
                add("tradition.wrong_kind", f"{side} {ed.get(side)!r} is a {nd.get('type')}, but "
                    f"{ed.get('type')} takes {' or '.join(spec[side])} there", subj)
        if ed.get("src") == ed.get("dst"):
            add("tradition.self_loop", "edge points at itself", subj)
        if ed.get("certainty") not in CERTAINTY:
            add("tradition.certainty", f"unknown certainty {ed.get('certainty')!r}", subj)
        refs_ok(ed.get("refs"), subj, "edge")

    # a document belongs to someone and speaks on something; a body sits inside one tradition
    issued, spoke = {}, set()
    for ed in edges:
        if ed.get("type") == "issued_by":
            issued.setdefault(ed["src"], []).append(ed["dst"])
        elif ed.get("type") == "speaks_on":
            spoke.add(ed["src"])
    for nd in nodes:
        if nd.get("type") != "document":
            continue
        dsts = [by_id[x] for x in issued.get(nd["id"], []) if x in by_id]
        tops = [x for x in dsts if (x.get("attrs") or {}).get("level") in ("tradition", "school")]
        if len(tops) != 1:
            add("tradition.document_owner", f"has {len(tops)} traditions or schools, wants exactly one", nd["id"])
        for b in (x for x in dsts if (x.get("attrs") or {}).get("level") == "body"):
            if tops and (b.get("attrs") or {}).get("tradition") != tops[0]["id"]:
                add("tradition.body_elsewhere", f"body {b['id']} belongs to another tradition", nd["id"])
        if nd["id"] not in spoke:
            add("tradition.document_silent", "speaks on no question", nd["id"])
    return out
