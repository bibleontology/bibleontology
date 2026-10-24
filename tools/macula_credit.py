"""MACULA'S CREDIT IN ITS OWN WORDS, in every derived file's header (the
committee of 2026-10-21, item 7: "MACULA's credit in the derived files' first
lines"; and the rule that a licence's credit is given in the licence's words).

The derived files said "MACULA Hebrew/Greek Linguistic Datasets, Clear Bible,
CC BY 4.0". MACULA asks for "MACULA Hebrew Linguistic Datasets, available at
https://github.com/Clear-Bible/macula-hebrew/" and the Greek likewise, and the
data is (c) Biblica, Inc. (Clear Bible is Biblica's). This rewrites the header
of each built file that carries the old form, once each, every other byte
kept; the tools that write those headers take CREDIT from here.

    python tools/macula_credit.py [--dry-run]
"""
import gzip
import io
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = "MACULA Hebrew/Greek Linguistic Datasets, Clear Bible, CC BY 4.0"
CREDIT = ("MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; "
          "MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; "
          "© Biblica, Inc., CC BY 4.0")


def main():
    dry = "--dry-run" in sys.argv
    files = subprocess.run(["git", "ls-files", "data", "out", "ontology"], cwd=ROOT, capture_output=True,
                           text=True, check=True).stdout.split("\n")
    done = 0
    for f in files:
        if not f.endswith((".json", ".jsonl", ".json.gz", ".jsonl.gz")):
            continue
        p = ROOT / f
        raw = p.read_bytes()
        gz = f.endswith(".gz")
        try:
            text = (gzip.decompress(raw) if gz else raw).decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # the header: a JSONL file's first line, a JSON file's first 4,000
        # characters (its "_source" key comes first)
        head = text.split("\n", 1)[0] if ".jsonl" in f else text[:4000]
        if OLD not in head:
            continue
        if head.count(OLD) != 1:
            sys.exit(f"{f}: the old credit appears {head.count(OLD)} times in the header; nothing written")
        i = text.index(OLD)
        text = text[:i] + CREDIT + text[i + len(OLD):]
        done += 1
        print(("would rewrite " if dry else "rewrote ") + f)
        if dry:
            continue
        data = text.encode("utf-8")
        if gz:
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as g:
                g.write(data)
            data = buf.getvalue()
        p.write_bytes(data)
    print(f"{done} files")


if __name__ == "__main__":
    main()
