"""A push never shows crawlers "back in a moment" (plan A.49, steps 2-4; 2026-11-12): the pieces agree.

tools/build_pages.py writes each sitemap page to a file, tools/upload_pages.py sends them, and Caddy serves them while
the app restarts. Each piece names files its own way, and a disagreement fails silently (Caddy finds nothing and shows
the splash), so the names are checked against each other:

  1. the builder's file for a path is one Caddy's try_files will find ({path}.html, or {path}index.html for "/" and
     a trailing slash); a path that is not a plain page path is refused (a planted "/../server" is caught)
  2. Caddy: the copy is tried inside handle_errors before the splash, from /var/cache/bibleontology/site, with 200
     and no-store; the shell is served from /var/cache/bibleontology/assets only where the file is there (else the
     app); the two Caddyfiles differ only in TLS
  3. a built page is the server's own answer plus one <meta> carrying its content-security policy (without
     frame-ancestors), and a card that does not exist is not built
  4. the upload tool deletes only paths the builder could have written

Run: python tests/test_deploy_fallback.py (the graph loads for part 3)"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_pages as B  # noqa: E402

fails, plants = [], 0


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print("FAIL", msg)


# ---- 1. names
def caddy_finds(path, file):
    return "/" + file in (path + ".html", path + "index.html")


for p in ("/", "/e/david", "/p/Job.4.7", "/word/G26", "/blog/", "/themes/covenant/side-by-side", "/about"):
    check(caddy_finds(p, B.file_for(p)), f"{p}: the builder writes {B.file_for(p)}, which Caddy's try_files misses")
plants += 1
try:
    B.file_for("/../server")
    check(False, "planted: a path climbing out of the folder was not refused")
except ValueError:
    pass

# ---- 2. Caddy
cf = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")
errors = cf[cf.index("handle_errors {"):]
check(errors.index("@copy") < errors.index("handle @down"), "the copy is not tried before the splash")
copy = errors[errors.index("@copy {"):errors.index("handle @down")]
for want in ("root /var/cache/bibleontology/site", "try_files {path}.html {path}index.html", "status 200",
             'Cache-Control "no-store"', "rewrite * {file_match.relative}"):
    check(want in copy, f"the copy's handler lacks: {want}")
check(re.search(r"@shell_disk \{\s*path_regexp \^/app-\[0-9a-f\]\{12\}\\\.\(js\|css\)\$\s*file \{\s*root "
                r"/var/cache/bibleontology/assets", cf), "the shell is not served from the asset folder, only where it is")
check(cf.index("handle @shell_disk") < cf.index("reverse_proxy 127.0.0.1:8000"), "the shell handler comes after the app's")


def bare(t):
    t = re.sub(r"(?m)^\s*#.*\n", "", t)
    t = re.sub(r"tls (\S+) (\S+) \{\s*client_auth \{[^}]*\}\s*\}", r"tls \1 \2", t)
    return re.sub(r"\s+", " ", t)


op = (ROOT / "deploy" / "Caddyfile.origin-pulls").read_text(encoding="utf-8")
check(bare(cf) == bare(op), "the two Caddyfiles differ beyond TLS")

# ---- 3. built pages
S = B._server()
for p in ("/e/david", "/p/Job.4.7", "/word/G26", "/"):
    code, body, ctype = B.render(p)
    check(code == 200 and ctype.startswith("text/html") and len(body) < 150_000, f"{p}: {code} {ctype} {len(body):,} B")
code, _, _ = B.render("/e/no_such_card_anywhere")
check(code != 200, "a card that does not exist would be built")
out = B.OUT
B.OUT = Path(__import__("tempfile").mkdtemp())
try:
    done, f, _ = B._work((["/e/david"], str(B.OUT)))
    built = (B.OUT / "site" / "e" / "david.html").read_bytes()
    _, served, _ = B.render("/e/david")
    meta = re.search(rb'\n<meta http-equiv="Content-Security-Policy" content="([^"]+)">', built)
    check(meta and built.replace(meta.group(0), b"", 1) == served, "a built page is not the server's answer plus one <meta>")
    pol = meta.group(1).decode() if meta else ""
    want = "; ".join(d for d in S.csp_for(served).split("; ") if not d.startswith("frame-ancestors"))
    check(pol.replace("&quot;", '"') == want, "the built page's policy is not the server's")
finally:
    B.OUT = out

# ---- 4. removals
up = (ROOT / "tools" / "upload_pages.py").read_text(encoding="utf-8")
check("file_for(p) for p in ch[\"removed\"]" in up and "rm -f site/PAGE" in up,
      "the upload deletes something other than builder-made files under site/")

print(f"deploy fallback: 4 classes checked; {plants} planted fault; {len(fails)} failures")
sys.exit(1 if fails else 0)
