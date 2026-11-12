"""Fetch the UBS Hebrew and Greek dictionaries from UBS's own repository and
build data/raw/ubs/ubs-hebrew.jsonl and ubs-greek.jsonl, the senses on the
word and verse pages.

Why this exists (2026-11-04): the dictionaries are CC BY-SA 4.0 and the graph
is CC BY 4.0. They are shown on the site, credited, and never enter the
public copy (docs/review/permissions/sdbh-2026-11-02.md). A committed file the
server reads is published by tools/export_public.py (deploy/runtime-inputs.txt),
so they are not committed: the server fetches them into data/raw/, which git
ignores here and in the public copy, as tools/fetch_lexicon.py does for STEP.

Pinned: one commit of github.com/ubsicap/ubs-open-license, each file's SHA-256
as downloaded with the owner's yes on 2026-11-02, and each extract's SHA-256 as
tools/lexicon/ubs_extract.py builds it. A changed file fails here instead of
changing what the site shows; a new UBS version is a change to this file.

    python3 tools/fetch_ubs.py              # then restart the app
    python3 tools/fetch_ubs.py --local      # build and check from files already here, download nothing

Writes nothing unless every hash matches. Python 3.9, standard library only.
"""
import hashlib
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "raw" / "ubs"
COMMIT = "a15a96cfaa4ca18a6c0339016645ba1e534db3c8"      # main on 2026-11-04 (committed 2026-10-21)
BASE = f"https://raw.githubusercontent.com/ubsicap/ubs-open-license/{COMMIT}/"

# local name: (path in the repository, SHA-256)
SOURCES = {
    "UBSHebrewDic-v0.9.4-en.JSON": ("dictionaries/hebrew/JSON/UBSHebrewDic-v0.9.4-en.JSON",
                                    "28d0b53a17240b6225201c4cadcb82718c2761efab309d045018f764cf618217"),
    "UBSHebrewDicLexicalDomains-v0.9.4-en.JSON": (
        "dictionaries/hebrew/JSON/UBSHebrewDicLexicalDomains-v0.9.4-en.JSON",
        "b5b4eb96bb089fb1b98108e168e37297d0f63130940880e820acdb48f1c516e6"),
    "UBSHebrewDicContextualDomains-v0.9.4-en.JSON": (
        "dictionaries/hebrew/JSON/UBSHebrewDicContextualDomains-v0.9.4-en.JSON",
        "db82e313dc3d70bb7093068318d567a4d337e65d8711841f8a436f915c587ec7"),
    "UBSGreekNTDic-v1.1-en.JSON": ("dictionaries/greek/JSON/UBSGreekNTDic-v1.1-en.JSON",
                                   "d84bb9077a43fa4a4f7e571fe2ffa460fa655d7b78439b366281ce527fd56893"),
    "UBSGreekNTDicLexicalDomains-v1.1-en.JSON": (
        "dictionaries/greek/JSON/UBSGreekNTDicLexicalDomains-v1.1-en.JSON",
        "a816a6bb2bdbdd7df6f46f771b5ddb1b9c019d73c3f0147e5a5cead5cfef8b4b"),
    "LICENSE.md": ("ubs-bible-routes/LICENSE.md",
                   "7abe19ec9bb73b36141b999b861d24ad855e808bafe0f81e84cce28556f6c297"),
    "README-hebrew.md": ("dictionaries/hebrew/README.md",
                         "f18eab18a4bad4a83f45981064139f89a96cb4ae97e0e72833d709ae2fb52940"),
    "README-greek.md": ("dictionaries/greek/README.md",
                        "29ffe0e7c9bd51b312abac5d1f68af47604e9ec24580377777afe86d035d51ed"),
}

# extract: (language, dictionary, version, SHA-256)
EXTRACTS = {
    "ubs-hebrew.jsonl": ("hebrew", "UBSHebrewDic-v0.9.4-en.JSON", "v0.9.4",
                         "aee470b90f0208e4d0d07b262caf4cdefc6a1f340e87b1ae1c3feddff503b6d8"),
    "ubs-greek.jsonl": ("greek", "UBSGreekNTDic-v1.1-en.JSON", "v1.1",
                        "0e9aece24d3771ecb1ca5f04662d6165f70c897aeba0a2c992c5769f9f25545d"),
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main(argv):
    local = "--local" in argv
    got = {}
    for name, (path, want) in SOURCES.items():
        if local:
            if not (DEST / name).exists():
                raise SystemExit(f"{name}: not in data/raw/ubs/ -- run without --local to fetch it")
            body = (DEST / name).read_bytes()
        else:
            with urllib.request.urlopen(BASE + path, timeout=300) as r:
                body = r.read()
        if sha256(body) != want:
            raise SystemExit(f"{name}: SHA-256 {sha256(body)[:16]}..., pinned {want[:16]}... -- nothing written")
        got[name] = body
        print(f"  {len(body) // 1024:>6,} KB  {name}  ok")
    with tempfile.TemporaryDirectory() as tmp:
        built = {}
        for name, (lang, dic, version, want) in EXTRACTS.items():
            src, out = Path(tmp) / dic, Path(tmp) / name
            src.write_bytes(got[dic])
            subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools" / "lexicon" / "ubs_extract.py"),
                            lang, str(src), str(out), version], check=True)
            body = out.read_bytes()
            if sha256(body) != want:
                raise SystemExit(f"{name}: built {sha256(body)[:16]}..., pinned {want[:16]}... -- nothing written")
            built[name] = body
            keys = body.count(b"\n")
            print(f"  {keys:>6,} keys  {name}  ok")
    DEST.mkdir(parents=True, exist_ok=True)
    for name, body in list(got.items()) + list(built.items()):
        (DEST / name).write_bytes(body)
    print(f"wrote {len(got) + len(built)} files to {DEST}")
    print("Restart the app to load them: sudo systemctl restart bibleontology")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
