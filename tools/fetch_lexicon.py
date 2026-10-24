"""Fetch STEPBible's two brief lexicons from STEPBible's own repository and
build data/raw/stepbible/lexicon.json -- the lexicon entry at the top of
every word card.

Why this exists (2026-10-04): the full lexicon is gitignored, because
STEPBible asks that their data be distributed from github.com/STEPBible rather
than from ours (src/bibleont/lemma.py). The live server gets its files by git,
so it had only the committed extract, ontology/lexicon.json: 135 entries
against 20,192. A reader on a phone reported that the lexicon entries seemed to be missing,
and that they are really important. So the server fetches them from STEPBible, as
they ask, and builds the file itself.

    PYTHONPATH=src python3 tools/fetch_lexicon.py      # then restart the app

Refuses to replace a lexicon with a smaller one: a short or failed download
must not leave the site with fewer entries than it had.
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bibleont import lemma  # noqa: E402

BASE = "https://raw.githubusercontent.com/STEPBible/STEPBible-Data/master/Lexicons/"
FILES = ["TBESG - Translators Brief lexicon of Extended Strongs for Greek - STEPBible.org CC BY.txt",
         "TBESH - Translators Brief lexicon of Extended Strongs for Hebrew - STEPBible.org CC BY.txt"]
MIN_ENTRIES = 15000          # the 2026-10 lexicon has 20,192; far fewer means a bad download

lemma.RAW.mkdir(parents=True, exist_ok=True)
for name in FILES:
    url = BASE + urllib.parse.quote(name)
    with urllib.request.urlopen(url, timeout=120) as r:
        body = r.read()
    if len(body) < 1_000_000:
        raise SystemExit(f"{name}: only {len(body):,} bytes -- not written")
    (lemma.RAW / name).write_bytes(body)
    print(f"  {len(body) // 1024:>6,} KB  {name[:60]}")

before = json.loads(lemma.LEXICON.read_text(encoding="utf-8")) if lemma.LEXICON.exists() else {}
keep = lemma.LEXICON.read_bytes() if lemma.LEXICON.exists() else None
out = lemma.build_lexicon(verbose=True)
with_def = sum(1 for v in out.values() if len(v) > 4 and v[4])
if len(out) < max(MIN_ENTRIES, len(before)):
    if keep is not None:
        lemma.LEXICON.write_bytes(keep)
    raise SystemExit(f"only {len(out):,} entries (had {len(before):,}) -- the previous lexicon is kept")
print(f"{len(out):,} entries, {with_def:,} with a definition -> {lemma.LEXICON.relative_to(ROOT)}")
print("Restart the app to load it: sudo systemctl restart bibleontology")
