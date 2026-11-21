"""Pack the pages tools/build_pages.py built for the server, and say exactly how to send them (plan A.49, step 3).

Runs after the build, before the push. The archive holds:
  - the pages that changed since the last upload (out/pages/changed.json);
  - every version's shell files, so a page cached from the version before still finds its script;
  - removed.txt, the pages no longer built, to delete there.

    python tools/upload_pages.py                 -> out/pages/upload-<stamp>.tar.gz, then the commands to run
    python tools/upload_pages.py --all           -> every page, not only the changed ones (the first upload)
    python tools/upload_pages.py --mark-uploaded -> after the commands succeed: this build becomes the last upload

On the server (Caddy reads them; deploy/Caddyfile, "THE LAST GOOD COPY" and "THE APP'S SHELL"):
  /var/cache/bibleontology/site/<path>.html     the pages: owned by the app's user, which refreshes them as it serves
  /var/cache/bibleontology/assets/app-<hash>.*  every version's shell: root's, never writable by the app
                                                (app2/page_copies.py says why)

    python tools/upload_pages.py --shell-only    -> just this version's two shell files: before any push that
                                                    changes the app's script or stylesheet, when no rebuild is due
"""
import argparse
import json
import shutil
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "pages"
HOST = "doug@<server>"
DEST = "/var/cache/bibleontology"
sys.path.insert(0, str(ROOT / "tools"))
from build_pages import file_for  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="send every page, not only the changed ones")
    ap.add_argument("--mark-uploaded", action="store_true", help="record this build as the last upload")
    ap.add_argument("--shell-only", action="store_true", help="only this version's shell files, no pages")
    a = ap.parse_args()
    if a.shell_only:
        return shell_only()
    man = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    if a.mark_uploaded:
        shutil.copyfile(OUT / "manifest.json", OUT / "uploaded.json")
        print(f"recorded: {len(man['pages']):,} pages and the shell {man['shell']} as the last upload")
        return
    ch = json.loads((OUT / "changed.json").read_text(encoding="utf-8"))
    pages = sorted(man["pages"]) if a.all else ch["changed"]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    tar_path = OUT / f"upload-{stamp}.tar.gz"
    removed = "\n".join(file_for(p) for p in ch["removed"])
    with tarfile.open(tar_path, "w:gz") as tar:
        for p in pages:
            f = OUT / "site" / file_for(p)
            tar.add(f, arcname="site/" + file_for(p))
        for f in sorted((OUT / "assets").glob("app-*")):
            tar.add(f, arcname="assets/" + f.name)
        data = (removed + "\n").encode() if removed else b""
        info = tarfile.TarInfo("removed.txt")
        info.size = len(data)
        import io
        tar.addfile(info, io.BytesIO(data))
    mb = tar_path.stat().st_size / 1e6
    print(f"{len(pages):,} pages, {len(list((OUT / 'assets').glob('app-*')))} shell files, "
          f"{len(ch['removed'])} to remove: {tar_path.name}, {mb:.1f} MB")
    win = str(tar_path).replace("/", "\\")
    print("\nThen, from PowerShell, in order (single quotes: PowerShell must not read the command):\n")
    print(f'scp "{win}" {HOST}:')
    # first, as root, nothing in site/ but plain files and folders: tar run as root would otherwise write through a
    # symlinked folder the app had planted (the security seat, 2026-11-12)
    print(f"ssh -t {HOST} 'sudo mkdir -p {DEST}/site {DEST}/assets "
          f"&& sudo find {DEST}/site -mindepth 1 -not -type f -not -type d -delete && sudo tar -xzf ~/{tar_path.name} -C {DEST} "
          f"&& cd {DEST} && sudo xargs -r -a removed.txt -I PAGE rm -f site/PAGE && sudo rm -f removed.txt "
          f"&& sudo chown -R bibleont:bibleont {DEST}/site && sudo chown -R root:root {DEST}/assets "
          f"&& sudo chmod -R a+rX,go-w {DEST} && rm ~/{tar_path.name} && sudo du -sh {DEST}/site {DEST}/assets'")
    print("\nWhen both succeed:\n")
    print("python tools/upload_pages.py --mark-uploaded")


def shell_only():
    """This version's two shell files, straight from app_shell(), with no page build: for a push that changes the
    app's script or stylesheet when no page rebuild is due (pages refreshed by the new app name the new files)."""
    sys.path.insert(0, str(ROOT / "app2"))
    import server as S  # noqa: E402
    sh = S.app_shell()
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    tar_path = OUT / f"shell-{stamp}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for kind in ("js", "css"):
            name = f"app-{sh[kind + '_hash']}.{kind}"
            (OUT / "assets" / name).write_bytes(sh[kind])
            tar.add(OUT / "assets" / name, arcname="assets/" + name)
    win = str(tar_path).replace("/", "\\")
    print(f"the shell {sh['js_hash']} / {sh['css_hash']}: {tar_path.name}")
    print("\nThen, from PowerShell:\n")
    print(f'scp "{win}" {HOST}:')
    print(f"ssh -t {HOST} 'sudo mkdir -p {DEST}/assets && sudo tar -xzf ~/{tar_path.name} -C {DEST} "
          f"&& sudo chown -R root:root {DEST}/assets && sudo chmod -R a+rX,go-w {DEST}/assets && rm ~/{tar_path.name} "
          f"&& ls {DEST}/assets'")


if __name__ == "__main__":
    main()
