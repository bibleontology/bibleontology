"""The page's stylesheet has no line a stray quote has broken.

The card-sections review (2026-10-13) found five CSS lines in
app2/static/index.html that began with a `"` -- `"".qrow{`, `".identbox{`,
`".subbody{`, `".sheetbox svg{`, `".sheetbox.wide{`. A browser reads the quote
as an unterminated string, drops the rule, and often the rule after it: the
identity box's border, a whole min-width:1100px block and `.graphnote` had
never rendered, and nothing said so. This fails on any line inside a <style>
block that starts with a quote, and proves itself on a planted one.

    python tests/test_css.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "app2" / "static" / "index.html"


def stray(html):
    bad = []
    for m in re.finditer(r"<style[^>]*>(.*?)</style>", html, re.S):
        start = html.count("\n", 0, m.start(1)) + 1
        # comments out, their line breaks kept: a comment line may quote a reader
        css = re.sub(r"/\*.*?\*/", lambda c: "\n" * c.group(0).count("\n"), m.group(1), flags=re.S)
        for i, line in enumerate(css.split("\n")):
            if re.match(r"\s*[\"']", line):
                bad.append((start + i, line.strip()[:60]))
    return bad


def main():
    html = PAGE.read_text(encoding="utf-8")
    planted = stray("<style>\n.a{color:red}\n\".b{color:blue}\n</style>")
    if len(planted) != 1:
        print("FAIL the planted stray quote was not caught")
        return 1
    bad = stray(html)
    for n, line in bad:
        print(f"FAIL index.html:{n} a style line starts with a quote: {line}")
    print(f"{len(re.findall(r'<style', html))} style block(s); planted fault caught: True; {len(bad)} failures")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
