# Written by DeepSeek-V4-Pro (.delegate\results\20260927-205454.md); reviewed by Claude before use.
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

OCCURRENCES = str(BASE / "out" / "word-occurrences.jsonl.gz")
LEXEMES = str(BASE / "out" / "word-lexemes.jsonl.gz")
EDGES = str(BASE / "out" / "word-edges.jsonl.gz")
STRUCTURE = str(BASE / "out" / "structure-nodes.jsonl.gz")
BSB = str(BASE / "out" / "bsb-align.jsonl.gz")
OUT = str(BASE / "out" / "word-lexeme-layers.jsonl.gz")

MACULA_SOURCE = "MACULA"
MACULA_LICENCE = "CC BY 4.0"
STRUCTURE_SOURCE = "structure graph"
STRUCTURE_LICENCE = "CC BY 4.0"
BSB_SOURCE = "BSB"
BSB_LICENCE = "public domain"

CANONICAL_FORCES = ("assertion", "directive", "question", "nonfinite")
TRAILING_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def sourced(value, source, licence):
    return {"value": value, "source": source, "licence": licence}


def normalize_strong(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # BSB tags are h<strong>; MACULA strongnumberx has no h prefix.
    if text[0].lower() == "h":
        text = text[1:]
    text = text.lstrip("0") or "0"
    text = text.rstrip(TRAILING_LETTERS)
    if not text:
        return None
    return text


def unwrap_record(obj):
    """(Claude, integrating two independently-written modules.) core.py
    wraps every source-derived attribute as {"value", "source", "licence"};
    this module was written expecting flat values. Unwrap one level on
    every top-level field whose value has exactly that shape. Edge records
    and structure-graph records are already flat, so this is a no-op there."""
    if not isinstance(obj, dict):
        return obj
    out = {}
    for k, v in obj.items():
        if isinstance(v, dict) and set(v.keys()) == {"value", "source", "licence"}:
            out[k] = v["value"]
        else:
            out[k] = v
    return out


def read_jsonl_gz(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="\n") as fh:
        for line_number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                yield unwrap_record(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc


def read_of_lexeme_edges(path):
    """occurrence id -> lexeme id, from core.py's word-edges.jsonl.gz."""
    occ_to_lexeme = {}
    for line_number, obj in enumerate(read_jsonl_gz(path), 1):
        if obj.get("edge") != "of_lexeme":
            continue
        occ_id, lid = obj.get("from"), obj.get("to")
        if not isinstance(occ_id, str) or not isinstance(lid, str):
            raise ValueError(f"{path}:{line_number}: of_lexeme edge missing from/to")
        occ_to_lexeme[occ_id] = lid
    return occ_to_lexeme


def read_lexemes(path):
    lexemes = {}
    for line_number, obj in enumerate(read_jsonl_gz(path), 1):
        lid = obj.get("id")
        if lid is None:
            lid = obj.get("lexeme")
        if not isinstance(lid, str) or not lid:
            raise ValueError(f"{path}:{line_number}: lexeme object missing string id")
        if lid in lexemes:
            raise ValueError(f"{path}:{line_number}: duplicate lexeme id {lid!r}")
        lexemes[lid] = obj
    return lexemes


def initialize_agg(lexemes):
    agg = {}
    for lid, lexeme in lexemes.items():
        agg[lid] = {
            "glosses": Counter(),
            "stems": Counter(),
            "greek": Counter(),
            "strongs": set(),
        }
        for key in ("strongnumberx", "strong"):
            raw = lexeme.get(key)
            if raw is not None and str(raw).strip():
                normalized = normalize_strong(raw)
                if normalized is not None:
                    agg[lid]["strongs"].add(normalized)
    return agg


def read_occurrences(path, lexemes, agg, id_to_lexeme, occ_to_lexeme):
    for line_number, obj in enumerate(read_jsonl_gz(path), 1):
        occ_id = obj.get("id")
        if occ_id is None:
            occ_id = obj.get("xml:id")
        if not isinstance(occ_id, str) or not occ_id:
            raise ValueError(f"{path}:{line_number}: occurrence missing string xml:id")
        # (Claude) the lexeme link is a separate of_lexeme edge in core.py's
        # output, not a field on the occurrence record.
        lid = occ_to_lexeme.get(occ_id)
        if not isinstance(lid, str) or not lid:
            raise ValueError(f"{path}:{line_number}: occurrence {occ_id!r} missing lexeme id")
        if lid not in lexemes:
            raise ValueError(f"{path}:{line_number}: occurrence {occ_id!r} references unknown lexeme {lid!r}")
        if occ_id in id_to_lexeme:
            raise ValueError(f"{path}:{line_number}: duplicate occurrence id {occ_id!r}")
        id_to_lexeme[occ_id] = lid

        entry = agg[lid]

        english = obj.get("english")
        if not english and obj.get("gloss") and obj.get("lang") in (None, "G"):
            # (Claude) MACULA Greek has no `english`; its gloss marks
            # supplied words in brackets ("[The] book"), which are dropped
            import re as _re
            english = " ".join(_re.sub(r"\[[^\]]*\]", " ",
                                       obj["gloss"]).replace(".", " ").split())
        if english is not None and english != "":
            entry["glosses"][english] += 1

        if obj.get("class") == "verb":
            stem = obj.get("stem")
            if stem is not None and stem != "":
                entry["stems"][stem] += 1

        greek = obj.get("greek")
        greekstrong = obj.get("greekstrong")
        if greek is not None and greek != "" and greekstrong is not None and greekstrong != "":
            entry["greek"][(greek, greekstrong)] += 1

        strongnumberx = obj.get("strongnumberx")
        normalized = normalize_strong(strongnumberx)
        if normalized is not None:
            entry["strongs"].add(normalized)


def build_strong_to_lexemes(agg, lexemes):
    """(Claude) keyed by language family AND number: Hebrew and Greek
    Strong's numbers overlap (H1656 is not G1656)."""
    strong_to_lexemes = defaultdict(set)
    for lid, entry in agg.items():
        fam = "g" if (lexemes.get(lid) or {}).get("lang") == "G" else "h"
        for strong in entry["strongs"]:
            strong_to_lexemes[fam + strong].add(lid)
    return strong_to_lexemes


def read_structure(path, id_to_lexeme, speech_counts):
    for line_number, obj in enumerate(read_jsonl_gz(path), 1):
        if obj.get("clause") is True and "upper_force" in obj:
            force = obj["upper_force"]
            if force not in CANONICAL_FORCES:
                raise ValueError(f"{path}:{line_number}: unknown upper_force {force!r}")
            src = obj.get("src")
            if not isinstance(src, list):
                raise ValueError(f"{path}:{line_number}: clause src is not a list")
            for occ_id in src:
                if not isinstance(occ_id, str):
                    raise ValueError(f"{path}:{line_number}: clause src id is not a string")
                lid = id_to_lexeme.get(occ_id)
                if lid is None:
                    raise ValueError(f"{path}:{line_number}: clause src {occ_id!r} not in word-occurrences")
                speech_counts[lid][force] += 1


def read_bsb(path, strong_to_lexemes):
    renderings = defaultdict(Counter)
    bsb_strongs = set()
    matched_bsb_strongs = set()
    unmatched_bsb_strongs = set()

    for line_number, obj in enumerate(read_jsonl_gz(path), 1):
        if "_source" in obj or "_note" in obj:
            # (Claude) this project's jsonl.gz files carry a leading
            # metadata record (a project-wide convention, not a verse).
            continue
        text = obj.get("text")
        spans = obj.get("spans")
        if not isinstance(text, str):
            raise ValueError(f"{path}:{line_number}: BSB text is not a string")
        if not isinstance(spans, list):
            raise ValueError(f"{path}:{line_number}: BSB spans is not a list")

        for span_index, span in enumerate(spans):
            if not isinstance(span, list) or len(span) != 3:
                raise ValueError(f"{path}:{line_number}: span {span_index} is not [start, end, tag]")
            start, end, tag = span
            if not isinstance(start, int) or not isinstance(end, int) or not isinstance(tag, str):
                raise ValueError(f"{path}:{line_number}: span {span_index} has wrong types")
            if start < 0 or end > len(text) or start > end:
                raise ValueError(f"{path}:{line_number}: span {span_index} out of range")
            fam = tag[:1].lower()
            if fam not in ("h", "g"):
                continue
            # (Claude) Hebrew tags h<n>, Greek g<n>: matched within family
            strong = normalize_strong(tag[1:])
            if strong is None:
                raise ValueError(f"{path}:{line_number}: BSB Strong tag has no number: {tag!r}")

            english = text[start:end]
            if not english:
                raise ValueError(f"{path}:{line_number}: empty BSB span {span!r}")

            strong = fam + strong
            bsb_strongs.add(strong)
            lids = strong_to_lexemes.get(strong, set())
            if not lids:
                unmatched_bsb_strongs.add(strong)
                continue

            matched_bsb_strongs.add(strong)
            for lid in lids:
                renderings[lid][english] += 1

    return renderings, bsb_strongs, matched_bsb_strongs, unmatched_bsb_strongs


def sorted_counter_items(counter, sort_key=None):
    if sort_key is None:
        return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return sorted(counter.items(), key=sort_key)


def build_glosses(entry):
    counts = sorted_counter_items(entry["glosses"])
    count_list = [{"english": english, "count": count} for english, count in counts]
    usual = count_list[0]["english"] if count_list else None
    return sourced({"counts": count_list, "usual": usual}, MACULA_SOURCE, MACULA_LICENCE)


def build_stems(entry):
    counts = sorted_counter_items(entry["stems"])
    count_list = [{"stem": stem, "count": count} for stem, count in counts]
    return sourced({"counts": count_list}, MACULA_SOURCE, MACULA_LICENCE)


def build_septuagint(entry):
    counts = sorted(entry["greek"].items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))
    count_list = [
        {"greek": greek, "greekstrong": greekstrong, "count": count}
        for (greek, greekstrong), count in counts
    ]
    usual_greek = count_list[0] if count_list else None
    return sourced(
        {"counts": count_list, "usual_greek": usual_greek},
        MACULA_SOURCE,
        MACULA_LICENCE,
    )


def build_speech_types(speech_counter):
    raw_counts = [
        {"force": force, "count": speech_counter.get(force, 0)}
        for force in CANONICAL_FORCES
    ]
    total = sum(item["count"] for item in raw_counts)
    normalized = [
        {
            "force": item["force"],
            "normalized": (item["count"] / total if total else 0.0),
        }
        for item in raw_counts
    ]
    return sourced(
        {"raw_counts": raw_counts, "normalized": normalized},
        STRUCTURE_SOURCE,
        STRUCTURE_LICENCE,
    )


def build_bsb_renderings(counter):
    counts = sorted_counter_items(counter)
    count_list = [{"english": english, "count": count} for english, count in counts]
    return sourced({"counts": count_list}, BSB_SOURCE, BSB_LICENCE)


def main():
    lexemes = read_lexemes(LEXEMES)
    agg = initialize_agg(lexemes)

    occ_to_lexeme = read_of_lexeme_edges(EDGES)
    id_to_lexeme = {}
    read_occurrences(OCCURRENCES, lexemes, agg, id_to_lexeme, occ_to_lexeme)

    strong_to_lexemes = build_strong_to_lexemes(agg, lexemes)

    speech_counts = defaultdict(Counter)
    read_structure(STRUCTURE, id_to_lexeme, speech_counts)

    bsb_renderings, bsb_strongs, matched_bsb_strongs, unmatched_bsb_strongs = read_bsb(
        BSB, strong_to_lexemes
    )

    coverage = Counter()
    total_lexemes = len(lexemes)

    with gzip.open(OUT, "wt", encoding="utf-8", newline="\n") as out_fh:
        for lid in sorted(lexemes):
            entry = agg[lid]
            glosses = build_glosses(entry)
            stems = build_stems(entry)
            septuagint = build_septuagint(entry)
            speech_types = build_speech_types(speech_counts.get(lid, Counter()))
            bsb = build_bsb_renderings(bsb_renderings.get(lid, Counter()))

            obj = {
                "id": lid,
                "glosses": glosses,
                "stems": stems,
                "septuagint": septuagint,
                "speech_types": speech_types,
                "bsb_renderings": bsb,
            }

            if glosses["value"]["counts"]:
                coverage["glosses"] += 1
            if stems["value"]["counts"]:
                coverage["stems"] += 1
            if septuagint["value"]["counts"]:
                coverage["septuagint"] += 1
            if any(item["count"] for item in speech_types["value"]["raw_counts"]):
                coverage["speech_types"] += 1
            if bsb["value"]["counts"]:
                coverage["bsb_renderings"] += 1

            out_fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")

    print(f"Lexemes: {total_lexemes}")
    for layer in ("glosses", "stems", "septuagint", "speech_types", "bsb_renderings"):
        print(f"{layer}: {coverage[layer]} of {total_lexemes} lexemes")
    print(f"BSB unique Strong numbers: {len(bsb_strongs)}")
    print(f"BSB unique Strong numbers matched to at least one lexeme: {len(matched_bsb_strongs)}")
    print(f"BSB unique Strong numbers matched to no lexeme: {len(unmatched_bsb_strongs)}")
    print(f"BSB lexemes with renderings: {coverage['bsb_renderings']} of {total_lexemes}")


if __name__ == "__main__":
    main()
