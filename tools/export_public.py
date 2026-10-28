"""Build the public repository from this one: tracked files on an allow-list,
cleaned and scanned, into a directory with no shared history (plan 8.3b).

## Why a copy, never a fork

Git keeps history, so a clone with private files deleted still carries every
one of them in earlier commits. The public repository is cut from a snapshot
into a fresh directory, and this repository's visibility never changes
(P-2026-10-19-10; the security seat, 2026-10-21).

## What goes in (decided 2026-10-21, docs/review/public-repo-8.3a.md)

The code, under Apache-2.0: app2/, src/, tools/, tests/ and deploy/. The graph,
under CC BY 4.0: ontology/ core and ontology/provenance/ (after its scan), the
published vocabularies and exports (out/ns/, out/export/), and the built files
the site reads at run time. The texts the site reads: MACULA's (CC BY 4.0) and
the Berean, ASV, WEB and YLT (public domain). Of the written record,
docs/PRINCIPLES.md only. The extraction prompt goes too (P2: "publish code incl.
prompt").

Never: the KJV and the pre-A.22 backups, the journal and the other private
documents, reader notes and feedback, the agent's instructions, the retired,
proposed and staged working files, the first app.

## Built from tracked files only

`git ls-files`, filtered by the allow-list: an ignored file inside a public
folder (data/raw/ holds the KJV) never travels (the security seat, finding 1).

## Cleaned on the way

  - every *_kjv field is removed from every JSON and JSONL record, compressed
    or not: the quotations, and the old names and addresses too, since on a
    phrase card the name is itself a KJV verse (the live site keeps them, to
    redirect old addresses);
  - local paths (C:\\Users\\..., the session scratchpad) become <local>;
  - the server's address becomes <server>.

## Scanned before anything is written (each scan proven by a planted fault)

  KJV         a six-word run found in the KJV and in none of the Berean, ASV,
              WEB or YLT; the KJV files by name
  secrets     private keys, tokens and keys of the usual formats
  personal    the owner's personal mail domain and local user name; any
              email but the project's and the crawler contacts the tests quote
  readers     every note id and reader name in the private notes backlog
  private     the names of private documents (the journal, the discipline...)
  family      family lines in comments ("my wife", "my daughter"...)

    python tools/export_public.py --check            scan, write nothing
    python tools/export_public.py --to ../bible-ontology-public
    python tools/export_public.py --selftest         plant each fault, expect each caught
"""
from __future__ import annotations

import argparse
import fnmatch
import gzip
import io
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PUBLIC: tuple[str, ...] = (
    "app2/*", "src/*", "tools/*", "tests/*", "deploy/*", "pyproject.toml",
    "ontology/entities/*", "ontology/relations/*", "ontology/schema/*", "ontology/meaning/*",
    "ontology/claim/*", "ontology/align/*", "ontology/themes/*", "ontology/concept-hubs/*",
    # the question cards and the traditions' own words (2026-10-26), each only once shown: see unshown()
    "ontology/questions/*", "ontology/traditions/*",
    "ontology/numbers/*", "ontology/versions/*", "ontology/events/*.json", "ontology/provenance/*",
    "ontology/*.json", "ontology/*.jsonl", "ontology/*.yaml", "ontology/EXTRACTION_GUIDE.md",
    "out/ns/*", "out/export/*",
    # who says a speaker's line, credited by the sweep: the claims export and
    # the quoted-speech test read it, and without it those rows look like the
    # narrator's (the exported tree's gate, 2026-10-21)
    "out/sweep/speaker-credits.jsonl", "out/sweep/speaker-credits-stats.json",
    "data/macula-clauses.jsonl.gz", "data/macula-manifest.json", "data/translation-manifest.json",
    "data/bible/verses.bsb.jsonl", "data/bible/verses.asv.jsonl", "data/bible/verses.web.jsonl",
    "data/bible/verses.ylt.jsonl",
    "docs/PRINCIPLES.md", "docs/rdf-1.2-in-practice.md",
    "README.md", "LICENSE", "LICENSE-DATA", "LICENSING.md", "NOTICE", "SOURCES.md", "CITATION.cff",
    "CONTRIBUTING.md", "CHANGELOG.md", "SECURITY.md", ".github/ISSUE_TEMPLATE/*",
    # line endings and binaries: without it a Windows clone's git add corrupts
    # out/structure-chapters.bin and gives the deploy scripts CRLF (the
    # correctness review, 2026-10-22)
    ".gitattributes",
)

NEVER: tuple[str, ...] = (
    "data/bible/verses.jsonl", "data/bible/text/*", "data/raw/*", "backups/*",
    "ontology/retired/*", "ontology/proposals/*", "ontology/staging/*", "ontology/candidates/*",
    "ontology/readings-held.jsonl", "ontology/events/*.md",
    # lists of the KJV addresses themselves (A.22b's measure, the renames)
    "ontology/provenance/kjv-addresses-*", "ontology/provenance/kjv-phrase-renames-*",
    # the KJV-removal tools read data/raw/kjv/, which never travels, and quote
    # what they removed; the one-off migrations and an unused bench likewise
    "tools/kjv_*", "tools/rename_kjv_addresses.py", "tools/local_bench.py",
    # read and write the private rulings, journal and roadmap by name
    "tools/casebook.py", "tools/rulings.py",
    # unused (imported nowhere); its one pattern is a KJV phrase
    "src/bibleont/keys.py",
    # the theme working notes (the site reads only the .json beside them), one
    # of them a brainstorming conversation kept as input, not as our text
    "ontology/themes/*.md",
    # its keys are those notes' sentences verbatim (tools/themes/theme_map.py
    # matches them exactly); with the notes out, nothing in the copy reads it
    "ontology/themes/theme-notes-requoted.json",
    "CLAUDE.md", ".claude/*", "feedback-backup/*", "app/*", "out/clause-stamping/*", "out/pin-pilot/*",
    # they test the retired app/, which never travels (the code review,
    # 2026-10-22: both died on import in a clean checkout)
    "tests/test_panes.py", "tests/test_ui_contract.py",
    # the DeepSeek worker: it reads the private briefing files and names the
    # private ones it must never send (the code review, 2026-10-22, B6; Doug
    # approved leaving it out). The tools that called it record how a pass
    # was run, and need a key a contributor would not have in any case
    "src/bibleont/delegate.py",
)

LOCAL_PATH = re.compile(r"(?:[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s\"'`]+|/c/Users/[^/\s\"'`]+)[^\s\"'`)]*")
def _server_address() -> str | None:
    """The origin's address, from this machine's git config (bibleont.server),
    never from this file: the cut publishes this file, and a pattern naming the
    address's first octets narrowed it to one /16 (the security seat's review
    of the cut, 2026-10-21, finding 4)."""
    r = subprocess.run(["git", "config", "--get", "bibleont.server"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() or None


_ADDR = _server_address()
SERVER = re.compile(r"\b" + re.escape(_ADDR) + r"\b") if _ADDR else None
DATETIME = re.compile(r"\b(20\d\d-\d\d-\d\d)[T ]\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:?\d\d)?\b")
# Any public IPv4 address left after the scrub refuses the cut: a new server
# address after a move is caught without this file knowing it.
IPV4 = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.])")
SECRET = [(re.compile(p), why) for p, why in (
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "a private key"),
    (r"\bAKIA[0-9A-Z]{16}\b", "an AWS key"),
    (r"\bgh[pousr]_[A-Za-z0-9]{30,}\b", "a GitHub token"),
    (r"\bgithub_pat_[A-Za-z0-9_]{40,}\b", "a GitHub token"),
    (r"\bsk-[A-Za-z0-9_-]{20,}\b", "an API key"),
    (r"\bxox[abps]-[A-Za-z0-9-]{10,}\b", "a Slack token"),
    (r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b", "a JWT"),
    (r"\bdop_v1_[a-f0-9]{64}\b", "a DigitalOcean token"),
    (r"\bAIza[0-9A-Za-z_-]{35}\b", "a Google API key"),
)]
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
EMAIL_OK = {"bible.ontology@gmail.com"}
PERSONAL = re.compile(r"hotmail|\bdouge\b", re.I)
FAMILY = re.compile(r"\bmy (?:wife|daughters?|kids|dad|mom|family)\b|\bkids-in-law\b", re.I)
PRIVATE_DOCS = ("JOURNAL.md", "DISCIPLINE.md", "RULINGS.md", "ROADMAP.md", "CLAUDE.md", "NOTES-BACKLOG",
                "FOUNDER-NOTES", "IP-CONSULT", "IP-INTAKE", "PROJECT-IDEAS", "COPYRIGHT-APPLICATION",
                "AUTHORSHIP-INVENTORY", "POLICY-GRAPH-DEMO")
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".ttl", ".trig", ".html", ".js",
                 ".css", ".sh", ".toml", ".cff", ".service", ".rq", ".csv", ".tsv", ".xml", ".svg", ".java", ""}


def matches(path: str, pats) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in pats)


def runtime_inputs() -> set[str]:
    """The built files the site reads at run time (deploy/runtime-inputs.txt,
    measured by tools/runtime_inputs.py): published so a clone runs the site.
    NEVER still outranks the list (it names the KJV verse file, which the
    server reads only if present)."""
    p = ROOT / "deploy" / "runtime-inputs.txt"
    if not p.exists():
        return set()
    return {x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")}


def unshown(root: Path = ROOT) -> set[str]:
    """WHAT THE SITE DOES NOT YET SHOW, NEVER PUBLISHED IN THE DATA (2026-10-26). A concept hub or a question card
    with "shown": false is a draft the owner has not read; so are its panel trails (they quote it nearly whole) and
    the traditions layer derived from the cards. The copy carries only what a reader of the site can already open:
    a hub's spec and build, a card, the hub trails named for it, and the question-card trails only once every card
    is shown (each trail file covers several cards). The traditions layer is published while cards are held, but
    rebuilt from the shown cards alone (shown_layer, 2026-10-27: three end-times cards held from the release)."""
    out, hubs = set(), set()
    for spec in sorted((root / "ontology" / "concept-hubs").glob("*.json")):
        if not json.loads(spec.read_text(encoding="utf-8")).get("shown"):
            hubs.add(spec.stem)
            out |= {f"ontology/concept-hubs/{spec.name}", f"out/concept-hubs/{spec.name}"}
    prov = root / "ontology" / "provenance" / "concept-hubs"
    for f in sorted(prov.glob("*")) if prov.exists() else []:
        if any(f.name.startswith(h + "-") for h in hubs):
            out.add(f.relative_to(root).as_posix())
    cards = sorted((root / "ontology" / "questions").glob("*.json"))
    hidden = [c for c in cards if not json.loads(c.read_text(encoding="utf-8")).get("shown")]
    out |= {c.relative_to(root).as_posix() for c in hidden}
    if hidden:
        for d in sorted((root / "ontology" / "provenance").glob("question-cards-*")):
            out |= {f.relative_to(root).as_posix() for f in d.rglob("*") if f.is_file()}
        # the earlier panel trails (2026-10-25), one pair per card, and a cross-check over every card: a trail goes
        # out only when it is named for a shown card (2026-10-27: end-times, hell and tithing trails were in the cut)
        shown = [c.stem for c in cards if c not in hidden]
        pq = root / "ontology" / "provenance" / "questions"
        for f in sorted(pq.rglob("*")) if pq.exists() else []:
            if f.is_file() and not any(f.name.startswith(s + "-") for s in shown):
                out.add(f.relative_to(root).as_posix())
    return out


def shown_layer(root: Path = ROOT) -> dict[str, bytes]:
    """The traditions layer as the public copy carries it: built from the shown cards only, so a held card's
    readings, documents and edges stay out. Empty when every card is shown (the committed layer is then exact)."""
    qdir = root / "ontology" / "questions"
    if all(json.loads(c.read_text(encoding="utf-8")).get("shown") for c in qdir.glob("*.json")):
        return {}
    sys.path.insert(0, str(ROOT / "tools" / "traditions"))
    import build as tb
    nodes, edges, problems = tb.build(qdir, shown_only=True)
    if problems:
        raise SystemExit("the traditions layer cannot be built from the shown cards: " + "; ".join(problems))
    return {"ontology/traditions/nodes.jsonl": tb.lines(nodes).encode("utf-8"),
            "ontology/traditions/edges.jsonl": tb.lines(edges).encode("utf-8")}


def selected() -> list[str]:
    files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    run = runtime_inputs()
    hide = unshown()
    out = []
    for f in files.decode("utf-8").split("\0"):
        if f and (matches(f, PUBLIC) or f in run) and not matches(f, NEVER) and "__pycache__" not in f \
                and f not in hide:
            out.append(f)
    return sorted(out)


# ---------------------------------------------------------------- cleaning
def strip_kjv(obj):
    """Every *_kjv field goes (the legal seat), and every field named plain
    "kjv" (the translation labels, ontology/versions/labels.jsonl). The live
    site keeps them to redirect old addresses and to find old wording; a public
    clone needs neither, and on a phrase card the old name field IS a KJV verse:
    642 of 779 hits in the entity file, 2026-10-21. The server reads them with
    .get, so absence is safe."""
    if isinstance(obj, dict):
        return {k: strip_kjv(v) for k, v in obj.items() if not (k.endswith("_kjv") or k == "kjv")}
    if isinstance(obj, list):
        return [strip_kjv(v) for v in obj]
    return obj


def clean_text(name: str, text: str) -> str:
    if name.endswith(".jsonl"):
        lines = []
        for line in text.split("\n"):
            body = line.rstrip("\r")
            if body.strip() and body.lstrip().startswith("{"):
                try:
                    obj = json.loads(body)
                    if isinstance(obj, (dict, list)) and ('_kjv"' in body or '"kjv"' in body):
                        body = json.dumps(strip_kjv(obj), ensure_ascii=False)
                except json.JSONDecodeError:
                    pass
            lines.append(body + ("\r" if line.endswith("\r") else ""))
        text = "\n".join(lines)
    elif name.endswith(".json"):
        try:
            obj = json.loads(text)
            if '_kjv"' in text or '"kjv"' in text:
                text = json.dumps(strip_kjv(obj), ensure_ascii=False, indent=1)
        except json.JSONDecodeError:
            pass
    text = LOCAL_PATH.sub("<local>", text)
    # DATES, NEVER TIMES OF DAY, IN THE PUBLISHED DATA (2026-10-22: a personal
    # privacy line; nothing public says when the work was done within a day).
    # The data's build stamps ("_built": "2026-09-12T08:10:16+00:00") keep their
    # date; code is left alone, where a time is an example or a test fixture.
    # (not RDF: a typed xsd:dateTime cut to a date would be an invalid literal;
    # the exports carry xsd:date only, checked 2026-10-22)
    if name.endswith((".json", ".jsonl", ".yaml", ".yml", ".csv", ".tsv")):
        text = DATETIME.sub(r"\1", text)
    return SERVER.sub("<server>", text) if SERVER else text


def read_clean(f: str) -> tuple[bytes, str | None]:
    """The file's published bytes, and its text (None for binary)."""
    raw = (ROOT / f).read_bytes()
    inner = f[:-3] if f.endswith(".gz") else f
    if Path(inner).suffix not in TEXT_SUFFIXES:
        return raw, None
    try:
        text = (gzip.decompress(raw) if f.endswith(".gz") else raw).decode("utf-8")
    except (UnicodeDecodeError, OSError):
        return raw, None
    # the scanner's own files are published as written: cleaning them rewrote
    # the scanner's patterns into a syntax error (the security seat, 2026-10-21)
    new = text if f in SCANNER else clean_text(inner, text)
    if new == text:
        return raw, text
    data = new.encode("utf-8")
    if f.endswith(".gz"):
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as g:
            g.write(data)
        data = buf.getvalue()
    return data, new


# ---------------------------------------------------------------- scanning
WORD = re.compile(r"[a-z]+")


def words(s: str) -> list[str]:
    return WORD.findall(s.lower().replace("\u2019", "'"))


ARCHAIC = {"thee", "thou", "thy", "thine", "ye", "unto", "shalt", "hast", "hath", "doth", "dost", "saith",
           "wherefore", "whither", "thence", "hither", "begat", "spake", "art", "wilt", "canst", "shouldest",
           "wouldest", "didst", "hadst", "mayest", "verily", "lo", "behold", "nigh", "yea", "nay", "brethren"}


def archaic(run: tuple) -> bool:
    return any(w in ARCHAIC or (len(w) > 4 and w.endswith(("eth", "est"))) for w in run)


# Former addresses that still redirect (a record's merged_from, the identity
# merge map) and happen to be KJV phrases. They are identifiers, never shown;
# the live site needs them so an old link lands. Each is named here so the
# exemption is visible, and only the identifier is exempt, not its words as text.
EXEMPT_IDS = ("shewing_all_meekness_unto_all_men",)


def kjv_hits(w: list[str], runs6: set, runs8: set) -> int:
    """KJV wording: a six-word KJV-only run that carries an archaic word, or an
    eight-word KJV-only run of any words. A six-word run of plain words alone
    ("and on either side of the") is common English, not the KJV (measured
    2026-10-21: 157 files flagged before this rule, many of them so)."""
    n = 0
    for i in range(len(w) - 5):
        r6 = tuple(w[i:i + 6])
        if r6 in runs6 and (archaic(r6) or tuple(w[i:i + 8]) in runs8):
            n += 1
    return n


def kjv_only_runs(n: int = 6) -> set[tuple]:
    """Runs of n words in the KJV and in none of the texts published beside it."""
    kjv_dir = ROOT / "data" / "raw" / "kjv"
    if not kjv_dir.exists():
        raise SystemExit("data/raw/kjv/ missing: the KJV is the detector (A.22) and must be on this machine")
    tags = re.compile(r"\\[a-z0-9]+\*?|\|[^\\]*?(?=\\w\*)|strong=\"[^\"]*\"")
    kjv = set()
    for p in sorted(kjv_dir.glob("*.usfm")):
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("\\v "):
                w = words(tags.sub(" ", line[3:]))
                kjv.update(tuple(w[i:i + n]) for i in range(len(w) - n + 1))
    other = set()

    def add(text):
        w = words(text)
        other.update(tuple(w[i:i + n]) for i in range(len(w) - n + 1))
    for t in ("bsb", "asv", "web", "ylt"):
        for line in open(ROOT / "data" / "bible" / f"verses.{t}.jsonl", encoding="utf-8"):
            r = json.loads(line)
            if "t" in r:
                add(r["t"])
    # MACULA's English glosses, word by word in the original's order (the Berean
    # Interlinear's and Cherith's): a literal gloss often matches the KJV's word
    # order ("they came all the elders of Israel to the king to Hebron") without
    # being the KJV. Measured 2026-10-21: 4,000+ such runs in the structure and
    # clause files, every one a gloss.
    # The structure nodes' text is the same glosses joined across clause
    # boundaries; the Berean's text as aligned from its USFM edition differs from
    # verses.bsb.jsonl in places; and the Berean's own footnotes quote other
    # manuscript traditions. None of them is the KJV.
    for name, field in (("data/macula-clauses.jsonl.gz", "gloss"), ("out/interlinear.jsonl.gz", None),
                        ("out/placeholder-nodes.jsonl.gz", "text"), ("out/bsb-align.jsonl.gz", "text"),
                        ("out/quotenotes.jsonl.gz", "source")):
        p = ROOT / name
        if not p.exists():
            continue
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            for line in fh:
                if not line.lstrip().startswith("{"):
                    continue
                r = json.loads(line)
                if field:
                    v = r.get(field)
                    add(v if isinstance(v, str) else "")
                elif r.get("words"):
                    add(" ".join(x.get("g") or "" for x in r["words"]))
    return kjv - other


def private_readers() -> tuple[set[str], set[str]]:
    """Note ids and reader names, read from the private backlog at scan time
    (never written into this tool)."""
    p = ROOT / "docs" / "NOTES-BACKLOG.md"
    if not p.exists():
        return set(), set()
    t = p.read_text(encoding="utf-8")
    ids = set(re.findall(r"`([0-9a-f]{10})`", t))
    names = set(re.findall(r"\(([A-Z][a-z]+)\)", t)) | set(re.findall(r"one from ([A-Z][a-z]+)", t))
    names -= {"Doug", "BSB", "KJV", "Abba", "Rom", "Gen", "Mark", "Matt", "John", "Luke", "Acts"}
    return ids, names


SCANNER = ("tools/export_public.py", "tests/test_export_public.py")   # name the patterns they look for
# Files that must name a private document to keep it private: the worker's
# floor of never-readable files (src/bibleont/delegate.py's DENY). Only these
# names, and only in these files; any other private name there still refuses.
PRIVATE_NAMES_OK = {
    "src/bibleont/delegate.py": {"NOTES-BACKLOG", "IP-CONSULT", "IP-INTAKE", "FOUNDER-NOTES",
                                 "DISCIPLINE.md", "CLAUDE.md"},
    # asserts the server never serves these (server.PUBLIC_FILES)
    "tests/test_extraction_contract.py": {"JOURNAL.md", "DISCIPLINE.md", "ROADMAP.md", "NOTES-BACKLOG",
                                          "FOUNDER-NOTES"},
}
CODE = (".py", ".js", ".html", ".sh", ".css", ".service")
FULL = False
REHEARSAL = False
COMMENT = re.compile(r"(?:#|//|/\*|<!--|\*)(.*)$", re.M)


def scan(texts: dict[str, str], kjv_runs, ids: set, names: set, emails_ok=EMAIL_OK) -> dict[str, list]:
    runs6, runs8 = kjv_runs
    found = defaultdict(list)
    names_re = re.compile(r"\b(" + "|".join(map(re.escape, sorted(names))) + r")\b") if names else None
    for f, t in texts.items():
        if f.startswith(("data/bible/verses.", "data/macula-")) or f in SCANNER:
            continue                     # the published texts themselves; the scanner's own patterns
        bare = t
        for x in EXEMPT_IDS:
            bare = re.sub(r"(?<![A-Za-z0-9_])" + re.escape(x) + r"(?![A-Za-z0-9_])", " ", bare)
        hits = kjv_hits(words(bare), runs6, runs8)
        if hits:
            found["KJV text"].append(f"{f} ({hits} runs)")
        for rx, why in SECRET:
            if rx.search(t):
                found["secret: " + why].append(f)
        for m in EMAIL.finditer(t):
            e = m.group(0).lower()
            if e not in emails_ok and not f.startswith("tests/test_crawlers.py"):
                found["email"].append(f"{f}: {e}")
        if PERSONAL.search(t):
            found["personal"].append(f)
        if any(i in t for i in ids):
            found["reader note id"].append(f)
        if names_re and names_re.search(t):
            found["reader name"].append(f)
        # family lines in the code's comments only: the text itself says "my
        # father" and "my son" on every page
        if f.endswith(CODE) and any(FAMILY.search(m.group(1)) for m in COMMENT.finditer(t)):
            found["family line"].append(f)
        for d in PRIVATE_DOCS:
            if d in t and d not in PRIVATE_NAMES_OK.get(f, ()):
                found["private document named"].append(f"{f}: {d}")
        for m in IPV4.finditer(t):
            if public_ipv4(*map(int, m.groups())):
                found["public IP address"].append(f"{f}: {m.group(0)}")
                break
    return found


def public_ipv4(a: int, b: int, c: int, d: int) -> bool:
    """An address on the open internet: not private, loopback, link-local,
    documentation or multicast, and every part a real octet."""
    if max(a, b, c, d) > 255 or a in (0, 10, 127) or a >= 224:
        return False
    if (a, b) in ((169, 254), (192, 168)) or (a == 172 and 16 <= b <= 31):
        return False
    if (a, b, c) in ((192, 0, 2), (198, 51, 100), (203, 0, 113)):     # RFC 5737
        return False
    return True


def build(check_only: bool, dest: Path | None) -> int:
    files = selected()
    tops = Counter(f.split("/")[0] if f.count("/") else f for f in files)
    print(f"{len(files)} tracked files on the allow-list: " + ", ".join(f"{k} {n}" for k, n in sorted(tops.items())))
    # THE COMMITTED BYTES, NOT THE WORKING TREE'S (the correctness review,
    # 2026-10-22): the copy is read from disk, so an uncommitted edit to an
    # allow-listed file would be published unreviewed. A copy for the push
    # refuses; a rehearsal says so and goes on
    # the whole status, filtered here: 1,900 paths as arguments are longer
    # than a Windows command line may be ("[WinError 206]", 2026-10-22)
    status = subprocess.run(["git", "status", "--porcelain", "-z", "--untracked-files=no"], cwd=ROOT,
                            capture_output=True, check=True).stdout.decode("utf-8").split("\0")
    wanted = set(files)
    dirty = sorted(x[3:] for x in status if x.strip() and x[3:] in wanted)
    if dirty:
        print(f"{'NOTE' if REHEARSAL or check_only else 'REFUSING'}: {len(dirty)} allow-listed files differ "
              f"from the last commit, e.g. {', '.join(dirty[:4])}")
        if not (REHEARSAL or check_only):
            print("Commit or restore them first. Nothing was written.")
            return 1
    out, texts = {}, {}
    for f in files:
        data, text = read_clean(f)
        out[f] = data
        if text is not None:
            texts[f] = text
    for f, data in shown_layer().items():          # a held card's part of the layer stays out
        out[f] = data
        texts[f] = data.decode("utf-8")
    ids, names = private_readers()
    found = scan(texts, (kjv_only_runs(6), kjv_only_runs(8)), ids, names)
    if found:
        print(f"REFUSING: {sum(len(v) for v in found.values())} findings")
        for k, v in sorted(found.items()):
            print(f"  {k}: {len(v)}")
            for x in (v if FULL else v[:6]):
                print(f"    {x}")
        print("Nothing was written.")
        return 1
    print("scans clean: KJV, secrets, personal, readers, private documents, family, public IP addresses")
    if check_only:
        return 0
    # NO PUBLIC COPY UNTIL THE GRAPH'S LICENCE IS GRANTED (the simulated
    # maintainer's catch, 2026-10-22): the exports' headers say "all rights
    # reserved" until ontology/ns-version.json's graph_license is granted, and
    # LICENSE-DATA says CC BY. A test only checked that the two agree, never that
    # the switch was on. A rehearsal copy (a simulation, a gate run) may pass
    # --rehearsal; the copy that is pushed may not.
    if not REHEARSAL:
        gl = (json.loads((ROOT / "ontology" / "ns-version.json").read_text(encoding="utf-8"))
              .get("graph_license") or {})
        if not gl.get("granted"):
            print("REFUSING: graph_license.granted is false in ontology/ns-version.json, so the exports say 'all "
                  "rights reserved' beside LICENSE-DATA's CC BY. Grant it and rebuild the exports (docs/CUT-DAY.md "
                  "step 2), or pass --rehearsal for a copy that will not be published.")
            return 1
    dest.mkdir(parents=True, exist_ok=True)
    # A SECOND CUT INTO THE SAME FOLDER REMOVES WHAT LEFT THE LIST (the security
    # seat, 2026-10-21, finding 3): a file moved to NEVER after an earlier cut
    # would otherwise stay in the working tree and be committed again. The
    # repository's own .git and .gitignore are left alone.
    stale = [p for p in dest.rglob("*") if p.is_file() and ".git" not in p.relative_to(dest).parts[:1]
             and p.relative_to(dest).as_posix() not in out and p.name != ".gitignore"]
    for p in stale:
        p.unlink()
    for f, data in out.items():
        (dest / f).parent.mkdir(parents=True, exist_ok=True)
        (dest / f).write_bytes(data)
    # its own .gitignore (finding 2): the ops token, local secrets, readers'
    # notes and raw downloads must never be one `git add -A` from published
    (dest / ".gitignore").write_bytes((ROOT / "deploy" / "public.gitignore").read_bytes())
    print(f"wrote {len(out)} files and .gitignore to {dest}"
          + (f"; removed {len(stale)} left from an earlier cut" if stale else "")
          + ". First export: git init there, with a noreply user.email.")
    return 0


def selftest() -> int:
    """Each scan must catch a planted fault, and each clean must clean."""
    runs = (kjv_only_runs(6), kjv_only_runs(8))
    kjv_sample = " ".join(next(r for r in runs[0] if archaic(r)))
    plants = {
        "KJV text": {"a.md": f"as it is written, {kjv_sample}."},
        "secret: a private key": {"c.txt": "-----BEGIN OPENSSH PRIVATE KEY-----"},
        "email": {"d.md": "write to someone@example.org"},
        "personal": {"e.py": "# by douge"},
        "reader note id": {"f.json": "see 0123456789"},
        "reader name": {"g.md": "Zebedina said"},
        "family line": {"h.js": "// my daughter didn't see them"},
        "private document named": {"i.py": "# see docs/JOURNAL.md"},
        "public IP address": {"j.md": "ssh to 93.184.216.34 (192.168.1.1 and 127.0.0.1 are fine)"},
        "secret: a DigitalOcean token": {"k.env": "DO=dop_v1_" + "ab" * 32},
    }
    fails = []
    for kind, files in plants.items():
        got = scan(files, runs, {"0123456789"}, {"Zebedina"})
        if kind not in got:
            fails.append(f"planted {kind} not caught")
    row = json.dumps({"id": "x", "note": "n", "note_kjv": "unto thee", "name_kjv": "Elias", "kjv": "thy own soul"})
    cleaned = json.loads(clean_text("r.jsonl", row))
    if any(k.endswith("_kjv") or k == "kjv" for k in cleaned) or cleaned.get("note") != "n":
        fails.append("a *_kjv or kjv field was not stripped, or another field was touched")
    if "<local>" not in clean_text("x.md", r"see C:\Users\someone\repo\file.txt"):
        fails.append("a local path was not scrubbed")
    got = clean_text("b.jsonl", '{"_built": "2026-09-12T08:10:16+00:00", "on": "2026-09-12"}')
    if "08:10" in got or '"2026-09-12"' not in got:
        fails.append(f"a time of day survived in the data, or its date was lost: {got}")
    # an unshown hub, an unshown card and their trails stay out (2026-10-26)
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        r = Path(tmp)
        for sub in ("ontology/concept-hubs", "ontology/questions", "ontology/provenance/concept-hubs",
                    "ontology/provenance/question-cards-x", "ontology/traditions", "ontology/provenance/questions"):
            (r / sub).mkdir(parents=True, exist_ok=True)
        (r / "ontology/concept-hubs/seen.json").write_text('{"shown": true}', encoding="utf-8")
        (r / "ontology/concept-hubs/draft.json").write_text('{"shown": false}', encoding="utf-8")
        (r / "ontology/provenance/concept-hubs/draft-panel.json").write_text("{}", encoding="utf-8")
        (r / "ontology/questions/q.json").write_text('{"shown": false}', encoding="utf-8")
        (r / "ontology/provenance/question-cards-x/scholar.json").write_text("{}", encoding="utf-8")
        (r / "ontology/traditions/nodes.jsonl").write_text("{}", encoding="utf-8")
        (r / "ontology/questions/seen.json").write_text('{"shown": true}', encoding="utf-8")
        for n in ("q-panel-a.json", "seen-panel-a.json", "cross-check.json"):
            (r / "ontology/provenance/questions" / n).write_text("{}", encoding="utf-8")
        hid = unshown(r)
        want = {"ontology/concept-hubs/draft.json", "out/concept-hubs/draft.json",
                "ontology/provenance/concept-hubs/draft-panel.json", "ontology/questions/q.json",
                "ontology/provenance/question-cards-x/scholar.json", "ontology/provenance/questions/q-panel-a.json",
                "ontology/provenance/questions/cross-check.json"}
        keep = {"ontology/concept-hubs/seen.json", "ontology/questions/seen.json",
                "ontology/provenance/questions/seen-panel-a.json"}
        if not want <= hid or keep & hid:
            fails.append(f"unshown work would be published, or shown work withheld: {sorted(want - hid)}, "
                         f"{sorted(keep & hid)}")
        # the layer goes out rebuilt from the shown cards: a held card's question and readings are not in it
        (r / "ontology/questions/seen.json").write_text(json.dumps(
            {"id": "seen-q", "shown": True, "question": "Seen?", "readings": [{"label": "A"}]}), encoding="utf-8")
        (r / "ontology/questions/q.json").write_text(json.dumps(
            {"id": "held-q", "shown": False, "question": "Held?", "readings": [{"label": "B"}]}), encoding="utf-8")
        layer = b"".join(shown_layer(r).values()).decode("utf-8")
        if "held-q" in layer or "held_q" in layer or "seen_q" not in layer:
            fails.append("the public traditions layer carries a held card, or lost a shown one")
    if not _ADDR:
        fails.append("the server's address is unknown here: git config --local bibleont.server <address>")
    elif "<server>" not in clean_text("x.md", f"ssh admin@{_ADDR}"):
        fails.append("the server address was not scrubbed")
    print(f"selftest: {len(plants)} planted faults, 4 cleanings; {len(fails)} failures")
    for f in fails:
        print("FAIL " + f)
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--full", action="store_true", help="list every finding, not the first six of each")
    ap.add_argument("--rehearsal", action="store_true",
                    help="write a copy even though the graph's licence is not yet granted (never for the push)")
    a = ap.parse_args()
    global FULL, REHEARSAL
    FULL, REHEARSAL = a.full, a.rehearsal
    if a.selftest:
        return selftest()
    if not a.check and not a.to:
        ap.error("--check, --selftest or --to DEST")
    return build(a.check, Path(a.to).resolve() if a.to else None)


if __name__ == "__main__":
    sys.exit(main())
