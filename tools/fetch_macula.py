"""Fetch the MACULA datasets to disk, pinned and checksummed.

The decision: local and scripted, with the risk that the source goes away in
mind.

Local and scripted, matching how STEPBible is handled. On the risk, three, and
the one people worry about is not the one that bites.

**Content drift is the real risk.** Both repositories have moved past their
last tagged release -- macula-hebrew main was 2026-04-24 against release
26.04.13, macula-greek main 2026-07-07 against 24.06.17. Fetching `main` means
a rebuild months later can silently produce different data, and nothing in the
output would say so. So this pins a RELEASE TAG and records a SHA-256 for every
file. A changed file is an error, not a warning.

**The repository going away** is a lesser risk -- Clear Bible is Biblica-backed
and active -- and it is the one we are actually insured against, because
**MACULA is CC BY 4.0 and may be redistributed.** If it vanished we could
legally mirror our copy. That is precisely what STEPBible's terms forbid
("please do not redistribute it yourself"), so the two dependencies carry
different risk even though both are read from disk.

**Rate limiting** is the third and is why this fetches only what is asked for.

## Moving forward is a decision, not a side effect

The requirement: pin to versions and have a process to move forward.
Pinning without an upgrade path just means going stale on purpose, so:

    --check           which releases are newer than the pin
    --upgrade TAG     fetch TAG to a STAGING directory, check the checksums,
                      and report which files differ. The pin is untouched and
                      nothing downstream sees the new data.
    --adopt TAG       after reviewing the diff, move staging into place and
                      bump the pin. This is the only step that changes what
                      the pipeline reads.

The staging step is the point. A dataset upgrade that lands directly in
`data/raw/` cannot be evaluated, only discovered -- and the difference between
"the numbers moved because we improved" and "the numbers moved because the
source changed underneath us" is the whole value of the audit.

    python tools/fetch_macula.py              # the stress-test chapters
    python tools/fetch_macula.py --verify     # check what is on disk
    python tools/fetch_macula.py --check      # is there a newer release?
    python tools/fetch_macula.py --upgrade 26.09.01
    python tools/fetch_macula.py --adopt 26.09.01

Nothing here is committed to the repository. `data/raw/macula/` is ignored, the
same as the STEPBible data beside it. `data/macula-manifest.json` IS committed:
it is the record of what we are pinned to and what those files hashed to.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "raw" / "macula"
MANIFEST = ROOT / "data" / "macula-manifest.json"

# Pinned. Bump deliberately, re-run, and let the checksum diff tell you what
# actually changed -- that is the whole point of recording them.
PIN = {"macula-hebrew": "26.04.13", "macula-greek": "24.06.17"}
RAW = "https://raw.githubusercontent.com/Clear-Bible/{repo}/{tag}/{path}"

# The chapters behind the stress set, plus the worked cases.
HEBREW = ["01-Gen-001", "32-Jon-001", "19-Psa-023", "17-Est-008",
          "17-Est-003", "24-Jer-034", "13-1Ch-022", "06-Jos-008"]
GREEK = ["02-mark", "03-luke", "04-john", "27-revelation"]


TARBALL = "https://codeload.github.com/Clear-Bible/{repo}/tar.gz/refs/tags/{tag}"
INNER = {"macula-hebrew": ("WLC/lowfat/", "hebrew"),
         "macula-greek": ("Nestle1904/lowfat/", "greek")}


def fetch_all():
    """The whole corpus, by tag tarball rather than 969 separate requests.

    The combined `macula-hebrew-lowfat.xml` in the repository is 43 KB of
    XInclude pointers, not data, so there is no single-file shortcut. The
    chapter files are 423 MB across 929 requests for Hebrew and 110 MB across
    40 for Greek; the tag tarballs are two requests and about 70 seconds.

    The tarball's own SHA-256 goes in the manifest, which is a stronger pin
    than per-file hashes: one number covers the entire release.
    """
    import io
    import tarfile
    man = json.loads(MANIFEST.read_text(encoding="utf-8")) \
        if MANIFEST.exists() else {"pin": PIN, "files": {}}
    man.setdefault("tarballs", {})
    for repo, tag in PIN.items():
        prefix, sub = INNER[repo]
        url = TARBALL.format(repo=repo, tag=tag)
        print(f"  {repo} {tag} …", flush=True)
        with urllib.request.urlopen(url, timeout=600) as r:
            blob = r.read()
        digest = hashlib.sha256(blob).hexdigest()
        old = man["tarballs"].get(repo, {}).get("sha256")
        if old and old != digest:
            # an error, not a warning (the module's own rule; the code review,
            # 2026-10-22, found it extracted and re-pinned anyway, so a second
            # run reported clean): nothing extracted, the manifest untouched
            print(f"    ! tarball for {tag} CHANGED since it was recorded. "
                  f"A pinned tag should never move. Nothing extracted; the manifest keeps the old checksum. "
                  f"Investigate.")
            return 1
        man["tarballs"][repo] = {"sha256": digest, "bytes": len(blob),
                                 "tag": tag}
        dest = DEST / sub
        dest.mkdir(parents=True, exist_ok=True)
        n = 0
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
            for m in tf:
                if not m.isfile() or prefix not in m.name:
                    continue
                if not m.name.endswith(".xml"):
                    continue
                name = m.name.rsplit("/", 1)[-1]
                f = tf.extractfile(m)
                if f is None:
                    continue
                (dest / name).write_bytes(f.read())
                n += 1
        print(f"    extracted {n:,} files to {dest}")
    MANIFEST.write_text(json.dumps(man, indent=2), encoding="utf-8")
    print(f"\nmanifest: {MANIFEST}")
    print("MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0")
    return 0


def _targets(all_books=False):
    out = []
    for stem in HEBREW:
        out.append(("macula-hebrew", f"WLC/lowfat/{stem}-lowfat.xml",
                    DEST / "hebrew" / f"{stem}-lowfat.xml"))
    for stem in GREEK:
        out.append(("macula-greek", f"Nestle1904/lowfat/{stem}.xml",
                    DEST / "greek" / f"{stem}.xml"))
    # (the whole corpus is fetched by fetch_all(), by tag tarball: `--all`)
    return out


def _sha(p):
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch():
    man = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() \
        else {"pin": PIN, "files": {}}
    changed, fresh, same = [], 0, 0
    for repo, path, dest in _targets():
        url = RAW.format(repo=repo, tag=PIN[repo], path=path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                body = r.read()
        except urllib.error.HTTPError as e:
            print(f"  FAILED {dest.name}: HTTP {e.code} — is the tag "
                  f"{PIN[repo]} still present in {repo}?")
            continue
        key = f"{repo}/{path}"
        digest = hashlib.sha256(body).hexdigest()
        old = man["files"].get(key, {}).get("sha256")
        if old and old != digest:
            # kept out: neither the file nor its recorded checksum is replaced,
            # so the change is still there to investigate on the next run
            changed.append(key)
            continue
        elif old:
            same += 1
        else:
            fresh += 1
        dest.write_bytes(body)
        man["files"][key] = {"sha256": digest, "bytes": len(body),
                             "tag": PIN[repo]}
    man["pin"] = PIN
    MANIFEST.write_text(json.dumps(man, indent=2), encoding="utf-8")
    print(f"fetched {len(man['files'])} files at pinned tags "
          f"{PIN['macula-hebrew']} / {PIN['macula-greek']}")
    print(f"  new {fresh}   unchanged {same}   CHANGED {len(changed)}")
    for k in changed:
        print(f"    ! {k} differs from the recorded checksum")
    if changed:
        print("  A pinned tag should never change content. Investigate before "
              "rebuilding anything downstream.")
    print(f"\nmanifest: {MANIFEST}")
    print("MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0")
    return 1 if changed else 0


def verify():
    if not MANIFEST.exists():
        print("no manifest — run without --verify first")
        return 1
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bad = missing = ok = 0
    for repo, path, dest in _targets():
        key = f"{repo}/{path}"
        rec = man["files"].get(key)
        if not dest.exists():
            print(f"  MISSING {dest.name}")
            missing += 1
        elif rec and _sha(dest) != rec["sha256"]:
            print(f"  ALTERED {dest.name}")
            bad += 1
        else:
            ok += 1
    print(f"verified: {ok} ok, {bad} altered, {missing} missing")
    return 1 if (bad or missing) else 0


STAGE = ROOT / "data" / "raw" / "macula-staging"


def _releases(repo):
    url = f"https://api.github.com/repos/Clear-Bible/{repo}/releases"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return [(x["tag_name"], x["published_at"][:10])
                    for x in json.loads(r.read())]
    except Exception as e:                                # noqa: BLE001
        print(f"  could not list releases for {repo}: {e}")
        return []


def check():
    """What is newer than the pin. Reports; changes nothing."""
    stale = False
    for repo, pinned in PIN.items():
        rel = _releases(repo)
        newer = [t for t, d in rel if t > pinned]
        print(f"{repo}: pinned at {pinned}")
        if not rel:
            continue
        for t, d in rel[:5]:
            flag = "  <-- NEWER" if t > pinned else ("  <-- pinned"
                                                     if t == pinned else "")
            print(f"    {t:12}{d}{flag}")
        if newer:
            stale = True
            print(f"    {len(newer)} release(s) newer than the pin. "
                  f"Review with --upgrade {newer[0]} before adopting.")
    if not stale:
        print("\nup to date with the latest release in both repositories.")
    return 0


def upgrade(tag):
    """Fetch a candidate release to staging and report what differs.

    Nothing downstream reads staging, so this is safe to run at any time and
    the pin is unchanged until --adopt.
    """
    man = json.loads(MANIFEST.read_text(encoding="utf-8")) \
        if MANIFEST.exists() else {"files": {}}
    diff, same, new = [], 0, 0
    for repo, path, dest in _targets():
        url = RAW.format(repo=repo, tag=tag, path=path)
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                body = r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue          # tag belongs to the other repository
            print(f"  FAILED {path}: HTTP {e.code}")
            continue
        out = STAGE / dest.relative_to(DEST)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(body)
        key = f"{repo}/{path}"
        old = man["files"].get(key, {}).get("sha256")
        d = hashlib.sha256(body).hexdigest()
        if old is None:
            new += 1
        elif old != d:
            diff.append((key, man["files"][key]["bytes"], len(body)))
        else:
            same += 1
    print(f"staged release {tag} in {STAGE}")
    print(f"  unchanged {same}   CHANGED {len(diff)}   new {new}")
    for k, a, b in diff:
        print(f"    ~ {k}   {a:,} -> {b:,} bytes ({b-a:+,})")
    if diff:
        print("\n  Before adopting, re-run the stress set against staging and")
        print("  compare: tools/macula.py --compare reads data/raw/macula, so")
        print("  a number that moves after --adopt and not before is the")
        print("  source changing rather than our rules improving.")
    print(f"\n  adopt with:  python tools/fetch_macula.py --adopt {tag}")
    return 0


def adopt(tag):
    """Move staging into place and bump the pin. The only step that changes
    what the pipeline reads."""
    if not STAGE.exists():
        print(f"nothing staged — run --upgrade {tag} first")
        return 1
    man = json.loads(MANIFEST.read_text(encoding="utf-8")) \
        if MANIFEST.exists() else {"files": {}}
    moved = 0
    for src in STAGE.rglob("*.xml"):
        dst = DEST / src.relative_to(STAGE)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        moved += 1
    for repo in PIN:
        if any(_releases(repo) and t == tag for t, _ in _releases(repo)):
            PIN[repo] = tag
    man["pin"] = PIN
    for repo, path, dest in _targets():
        if dest.exists():
            man["files"][f"{repo}/{path}"] = {
                "sha256": _sha(dest), "bytes": dest.stat().st_size,
                "tag": PIN[repo]}
    MANIFEST.write_text(json.dumps(man, indent=2), encoding="utf-8")
    print(f"adopted {tag}: {moved} files moved into data/raw/macula")
    print(f"pin is now {PIN}")
    print("Commit data/macula-manifest.json so the pin is recorded in git.")
    return 0


def main() -> int:
    if "--all" in sys.argv:
        return fetch_all()
    if "--verify" in sys.argv:
        return verify()
    if "--check" in sys.argv:
        return check()
    for flag, fn in (("--upgrade", upgrade), ("--adopt", adopt)):
        if flag in sys.argv:
            i = sys.argv.index(flag)
            if i + 1 >= len(sys.argv):
                print(f"{flag} needs a release tag; see --check")
                return 1
            return fn(sys.argv[i + 1])
    return fetch()


if __name__ == "__main__":
    raise SystemExit(main())
