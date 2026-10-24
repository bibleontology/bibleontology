"""THE EXPORTED TREE MUST RUN (plan 8.3b; the committee of 2026-10-21, item
2: "a gate that runs in the exported tree: the tests pass and the server
answers").

Run against a tree written by tools/export_public.py, never this repository:
it starts the server there, asks it the routes a first visitor would, then
runs the tests deploy/preflight.sh runs, each inside the copy. A test that
needs what the copy does not carry (the KJV, MACULA's raw files, the private
docs) says "skipped" and exits 0; anything else that fails, fails the gate.

    python tools/export_gate.py ../bible-ontology-public
"""
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PORT = 8793
ROUTES = ["/healthz", "/", "/api/about", "/api/books", "/api/chapter?book=Gen&c=1", "/api/verse?ref=Gen%201:1",
          "/e/david", "/api/entity?id=david", "/api/search?q=love", "/ns/meaning", "/ns/map"]
# (robots.txt and the sitemaps are Caddy's to serve, from deploy/www/, not the server's)


def tests_in(tree: Path) -> list[str]:
    """The test files deploy/preflight.sh runs, as named there."""
    pre = (tree / "deploy" / "preflight.sh").read_text(encoding="utf-8")
    return sorted(set(re.findall(r"tests/(test_[\w]+\.py)", pre)))


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    tree = Path(sys.argv[1]).resolve()
    if tree == Path(__file__).resolve().parents[1]:
        sys.exit("that is this repository, not an exported copy")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
               BIBLEONT_FEEDBACK=str(tree.parent / (tree.name + "-gate-feedback")))
    fails = []
    srv = subprocess.Popen([sys.executable, "app2/server.py", "--port", str(PORT)], cwd=tree, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    try:
        up = False
        for _ in range(900):
            if srv.poll() is not None:
                break
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/healthz", timeout=5).read()
                up = True
                break
            except OSError:
                time.sleep(1)
        if not up:
            out = srv.stdout.read() if srv.poll() is not None else ""
            fails.append("the server never answered /healthz" + (f":\n{out[-1500:]}" if out else ""))
        else:
            for r in ROUTES:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{r}", timeout=120) as resp:
                        if resp.status != 200:
                            fails.append(f"{r}: {resp.status}")
                except OSError as ex:
                    fails.append(f"{r}: {ex}")
            print(f"server: {len(ROUTES)} routes asked, {sum(f.startswith('/') for f in fails)} failed")
    finally:
        srv.kill()
    # a third-party secret scanner over the whole copy, when installed (the
    # security seat, 2026-10-21; deploy/gitleaks.toml names the one allowance)
    gl = shutil.which("gitleaks") or next((str(p) for p in Path(os.environ.get("LOCALAPPDATA", "")).glob(
        "Microsoft/WinGet/Links/gitleaks.exe")), None)
    if gl:
        p = subprocess.run([gl, "dir", str(tree), "--config", str(tree / "deploy" / "gitleaks.toml"),
                            "--no-banner", "--redact"], capture_output=True, text=True, encoding="utf-8")
        print(f"  {'ok  ' if p.returncode == 0 else 'FAIL'} gitleaks: "
              f"{(p.stderr.strip().splitlines() or [''])[-1][-80:]}")
        if p.returncode:
            fails.append("gitleaks found something: run it with --report-path to see where")
    else:
        print("  note gitleaks is not installed here; its scan was skipped")
    for t in tests_in(tree):
        p = subprocess.run([sys.executable, f"tests/{t}"], cwd=tree, env=env, capture_output=True, text=True,
                           encoding="utf-8", timeout=1800)
        last = (p.stdout.strip().splitlines() or [""])[-1][:150]
        print(f"  {'ok  ' if p.returncode == 0 else 'FAIL'} {t}: {last}")
        if p.returncode:
            fails.append(f"tests/{t}: {(p.stdout + p.stderr)[-800:]}")
    print(f"gate: {len(fails)} failures")
    for f in fails:
        print("FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
