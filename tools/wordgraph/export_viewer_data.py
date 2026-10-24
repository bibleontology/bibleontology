# Written by DeepSeek-V4-Pro (.delegate\results\20260927-211013.md); reviewed by Claude before use.
# tools/wordgraph/export_viewer_data.py
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORDS_PATH = ROOT / "out" / "word-lexemes.jsonl.gz"
LAYERS_PATH = ROOT / "out" / "word-lexeme-layers.jsonl.gz"
# (Claude) written next to viewer.html: it fetches this file by relative
# path ('wordgraph-viewer-data.json'), same folder.
OUT_PATH = ROOT / "tools" / "wordgraph" / "wordgraph-viewer-data.json"
MAX_BYTES = 15 * 1024 * 1024


def unwrap(value):
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def item_count(item):
    if not isinstance(item, dict):
        return 0
    try:
        return float(item.get("count") or 0)
    except (TypeError, ValueError):
        return 0


def sort_by_count(items):
    if not isinstance(items, list):
        return items
    return sorted(items, key=item_count, reverse=True)


def build_records():
    layers = {}
    with gzip.open(LAYERS_PATH, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            lex_id = obj.get("id")
            if lex_id:
                layers[lex_id] = obj

    records = []
    with gzip.open(WORDS_PATH, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            lex_id = obj.get("id")
            layer = layers.get(lex_id, {})

            count_raw = unwrap(obj.get("count"))
            try:
                count = int(count_raw or 0)
            except (TypeError, ValueError):
                count = 0

            books = unwrap(obj.get("books"))
            if not isinstance(books, list):
                books = []

            record = {
                "id": lex_id,
                "lemma": unwrap(obj.get("lemma")),
                "language": unwrap(obj.get("lang")),
                "strong": unwrap(obj.get("strong")),
                "count": count,
                "books": books,
            }

            gloss_value = unwrap(layer.get("glosses")) or {}
            record["usual_gloss"] = gloss_value.get("usual")
            record["glosses"] = sort_by_count(gloss_value.get("counts")) or []

            stems_value = unwrap(layer.get("stems")) or {}
            record["stems"] = sort_by_count(stems_value.get("counts")) or []

            sept_value = unwrap(layer.get("septuagint")) or {}
            record["usual_greek"] = sept_value.get("usual_greek")
            record["septuagint"] = sort_by_count(sept_value.get("counts")) or []

            speech_value = unwrap(layer.get("speech_types")) or {}
            record["speech_types"] = sort_by_count(speech_value.get("raw_counts")) or []

            bsb_value = unwrap(layer.get("bsb_renderings")) or {}
            record["bsb_renderings"] = sort_by_count(bsb_value.get("counts")) or []

            records.append(record)

    return records


def encode(records):
    return json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def main():
    records = build_records()
    records.sort(key=lambda record: record.get("count") or 0, reverse=True)

    selected = records
    serialized = encode(selected)

    if len(serialized) > MAX_BYTES:
        selected = records[:3000]
        # Safety net: if 3000 records still exceed 15 MB, trim the tail.
        while selected and len(encode(selected)) > MAX_BYTES:
            selected = selected[:-100]
        print(f"Dropped {len(records) - len(selected)} lexemes because full output would exceed 15 MB")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = encode(selected)
    OUT_PATH.write_bytes(serialized)
    print(f"Wrote {len(selected)} lexemes to {OUT_PATH} ({len(serialized) / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
