"""The blog as published is the blog as written: every post in docs/blog/posts
has its page in app2/static/blog, built from its current text by
tools/blog_build.py, and the list names every post. An edited post not rebuilt
(or a page left behind by a deleted post) fails, so what goes live is what
the author wrote. Also: every page carries the reply box, posting to
/api/feedback.

Run: python tests/test_blog.py"""
import re
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import blog_build as B  # noqa: E402

# The posts' sources sit in docs/blog/, which the public repository does not
# carry (2026-10-21, plan 8.3a: of docs/, PRINCIPLES.md only); the built pages
# in app2/static/blog/ do travel. A copy without the sources skips, saying so.
if not B.SRC.exists():
    print("skipped: the posts' sources (docs/blog/posts) are not in this copy; the built pages are")
    raise SystemExit(0)

fails = []
live = B.OUT
with tempfile.TemporaryDirectory() as tmp:
    B.OUT = Path(tmp)
    B.main()
    built = {p.name: p.read_text(encoding="utf-8") for p in Path(tmp).glob("*.html")}
B.OUT = live
have = {p.name: p.read_text(encoding="utf-8") for p in live.glob("*.html")} if live.exists() else {}
for name, text in built.items():
    if name not in have:
        fails.append(f"{name}: not built (python tools/blog_build.py)")
    elif have[name] != text:
        fails.append(f"{name}: out of date with its post (python tools/blog_build.py)")
    if name != "index.html" and "fetch('/api/feedback'" not in text:
        fails.append(f"{name}: no reply box")
for name in set(have) - set(built):
    fails.append(f"{name}: a page with no post")
print(f"{len(built) - 1} post(s), {len(fails)} failures")
for f in fails:
    print("FAIL", f)
sys.exit(1 if fails else 0)
