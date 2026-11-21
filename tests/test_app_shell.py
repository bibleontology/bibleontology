"""The app's shell is served as two files of its own, and nothing is lost in the split (2026-11-12).

Plan P-2026-11-12-4, step 1: every page carried the same 810 KB script and 157 KB stylesheet inline, about 1 MB a
page. app_shell() serves index.html with the stylesheet as /app-<hash>.css and the app as /app-<hash>.js. Checked:

  1. THE SPLIT LOSES NOTHING: the served page, with the two files put back where their tags stand, is index.html
     exactly (a planted lost character is caught)
  2. each file's name is its content's hash, so a year's caching cannot serve a stale one
  3. order is kept: the stylesheet's link sits in <head>, the script's tag at the end of <body>, neither async nor
     deferred; the small inline script in <head> stays inline
  4. the content-security policy still allows them: it names 'self' for scripts, and hashes only the inline script left
  5. a page is small: David's card page under 100 KB (it was about 1 MB)
  6. only the current pair is served: the route answers another hash with a 404 that is not cached

No server needed (the card page builds in process, after the graph loads). Run: python tests/test_app_shell.py"""
import hashlib
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

fails, plants = [], 0


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print("FAIL", msg)


src = (S.STATIC / "index.html").read_text(encoding="utf-8")
sh = S.app_shell()
page = sh["page"].decode("utf-8")
js, css = sh["js"].decode("utf-8"), sh["css"].decode("utf-8")


# ---- 1. nothing lost
def rebuild(pg, js_text, css_text):
    pg = pg.replace(f'<link rel="stylesheet" href="/app-{sh["css_hash"]}.css">', "<style>" + css_text + "</style>", 1)
    return pg.replace(f'<script src="/app-{sh["js_hash"]}.js"></script>', "<script>" + js_text + "</script>", 1)


check(rebuild(page, js, css) == src, "the served page and its two files do not put back together as index.html")
plants += 1
check(rebuild(page, js[:-1], css) != src, "planted: a character lost from the script not caught")

# ---- 2. names are content hashes
check(sh["js_hash"] == hashlib.sha256(sh["js"]).hexdigest()[:12], "the script's name is not its content's hash")
check(sh["css_hash"] == hashlib.sha256(sh["css"]).hexdigest()[:12], "the stylesheet's name is not its content's hash")

# ---- 3. order
head, body = page.split("</head>", 1)
check(f'href="/app-{sh["css_hash"]}.css"' in head, "the stylesheet's link is not in <head>")
tag = f'<script src="/app-{sh["js_hash"]}.js"></script>'
check(tag in body and body.rstrip().endswith("</html>") and body.index(tag) > body.rindex("<body"),
      "the script's tag is not in <body>")
check(re.search(r"<script>.*?</script>", head, flags=re.S), "the small inline script left <head>")
check(len(js) > 500_000 and len(css) > 100_000, "the split took the wrong blocks")

# ---- 4. the policy
csp = S.csp_for(sh["page"])
check(re.search(r"script-src 'self'", csp), f"the policy does not allow the app's own script file: {csp[:120]}")
inline = re.findall(r"<script>(.*?)</script>", page, flags=re.S)
check(len(inline) == csp.count("'sha256-"), "the policy hashes something other than the inline scripts left")

# ---- 5. size
S.load()
pg = S.card_page("david")
david = S.with_card(sh["page"], pg[0], pg[1]) if pg else b""
check(0 < len(david) < 100_000, f"David's card page is {len(david):,} bytes")

# ---- 6. the route
srv = (ROOT / "app2" / "server.py").read_text(encoding="utf-8")
check(re.search(r'm_app\.group\(1\) != sh\[kind \+ "_hash"\]:\s*\n\s*return self\._send\(404.*no-store', srv),
      "the shell route does not refuse another hash with an uncached 404")

print(f"app shell: 6 classes checked; {plants} planted fault; David's page {len(david):,} bytes; {len(fails)} failures")
sys.exit(1 if fails else 0)
