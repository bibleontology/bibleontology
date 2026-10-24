"""Fetch STEP Bible's TIPNR (Translators Individualised Proper Names with all
References) into data/raw/stepbible/ -- what tools/meaning/mentions.py reads
to tell which James, Simon or John a verse means (tools/meaning/tipnr.py).

Why a fetch and not a commit (2026-10-04): STEP Bible asks that their data be
distributed from github.com/STEPBible, not from ours, so the file is
gitignored like the lexicons (tools/fetch_lexicon.py). Only a machine that
rebuilds out/mentions.jsonl.gz needs it; the live server reads the committed
mentions and does not.

    python tools/fetch_tipnr.py

Refuses a short download: a truncated file would quietly drop people from the
resolver and send their names back to the chapter and book guesses.
"""
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "TIPNR - Translators Individualised Proper Names with all References - STEPBible.org CC BY.txt"
URL = ("https://raw.githubusercontent.com/STEPBible/STEPBible-Data/master/Proper%20Nouns/"
       + urllib.parse.quote(NAME))
MIN_BYTES = 7_000_000        # the 2026-10 file is 7,967,205

with urllib.request.urlopen(URL, timeout=120) as r:
    body = r.read()
if len(body) < MIN_BYTES:
    raise SystemExit(f"TIPNR: only {len(body):,} bytes -- not written")
out = ROOT / "data" / "raw" / "stepbible" / NAME
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(body)
print(f"wrote {out.relative_to(ROOT)} ({len(body):,} bytes)")
