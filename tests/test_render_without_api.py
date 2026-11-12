"""A card's page does not depend on /api/ (2026-10-29: Search Console's URL Inspection showed every card page EMPTY).

The cause. From 2026-10-03 (commits 8dd0e783 and 67079487) the first script in app2/static/index.html added a `js`
class and `.js .ssr{display:none}` hid the server's copy of the card at once; the app then fetched the card from
/api/, which robots.txt disallows for every crawler. Google rendered the page, the copy vanished, the API was
refused, and what it kept was an empty frame.

The rule now. The server's copy (class `ssr`) is hidden only by `.drawn .ssr`, and `drawn` is added by markDrawn()
alone, which only arrived() calls, which only openTab (after the tab is on screen) and setExplore (after Explore
is built) call -- so a request that failed, or never answered, leaves the copy as the page. A failed request draws
nothing over it: no "site is restarting" notice while a server copy shows, no error text in the pane, no removal of
the copy.

This checks, from the page as served (with_card puts the copy into index.html as the server does) and from
index.html's script:
  1. the only rule that hides `.ssr` is `.drawn .ssr`; nothing adds a `js` class; the page arrives without `drawn`
  2. the app's frame waits invisibly while the copy shows, and only a rule keyed on `drawn` lifts it
  3. every server copy in server.py carries the class the rule names
  4. `drawn` is added in one place (markDrawn), reached only through arrived(), called only after a draw
     (openTab after selectTab, setExplore after the pane is filled) and never from the boot script or the first
     script, so never before a fetch
  5. the failure path leaves the copy: api() draws and catches nothing, the restart notice yields to a server copy,
     no code removes or hides `.ssr`, no global error handler writes to the page
  6. the success path still exists (a copy nothing ever hides would sit over a working app)

Every check is proved by a planted fault: the old rule restored, `drawn` added before the fetch (in the first
script and in the boot script), an error notice drawn over a server copy (two ways), the copy removed on failure,
the success calls removed, a server copy without the class, `drawn` in the served HTML.

No graph is loaded (the copy is stood in for): seconds. Run: python tests/test_render_without_api.py"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

SRC = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8").replace("\r\n", "\n")
SERVER = (ROOT / "app2" / "server.py").read_text(encoding="utf-8")
COPY = '<article id="ssr" class="ssr"><h1>Abraham</h1><p>the server\'s copy</p></article>'


def served(src):
    """The page as the server sends a card: the copy goes first in <body>."""
    return S.with_card(src.encode("utf-8"), "<title>Abraham</title>\n", COPY).decode("utf-8")


def span(text, start_pat, end_pat):
    """The text from start_pat to the next end_pat (a function from its head to its closing line), or ''."""
    m = re.search(start_pat, text)
    if not m:
        return ""
    e = re.compile(end_pat, re.M).search(text, m.end())
    return text[m.start():e.end() if e else len(text)]


def scripts(html):
    return re.findall(r"<script>(.*?)</script>", html, re.S)


def code(js):
    """The script without its comments (a comment may say 'arrived()' or 'ssr' without calling or touching either)."""
    return re.sub(r"(?m)^\s*//.*$", "", re.sub(r"/\*.*?\*/", "", js, flags=re.S))


def faults(src, server_src):
    out = []
    page = served(src)
    css = "".join(re.findall(r"<style>(.*?)</style>", src, re.S))
    js = code("\n".join(scripts(src)))

    # 1. the one rule that hides the server's copy
    hiders = [m.group(1).strip() for m in re.finditer(r"([^{}]*\.ssr[^{}]*)\{[^}]*display\s*:\s*none", css)
              if "~" not in m.group(1) and " .ssr-" not in m.group(1)]
    if hiders != [".drawn .ssr", "html.human .ssr"]:
        out.append(f"the rule(s) hiding .ssr are {hiders}; only '.drawn .ssr' and the reader's 'html.human .ssr' are "
                   "allowed (the old '.js .ssr' hid the copy the moment the script ran, crawler or not)")
    # 1b. A READER, NEVER A CRAWLER (2026-11-09, Doug: "visible to Google but not to me"): `reader` is added only when
    # the user agent fails the crawler test, by the first script, and taken off again if nothing draws in 4 s
    first = scripts(page)[0] if scripts(page) else ""
    cm = re.search(r"var C=/(.*?)/i;", first)
    if not cm or "if(!C.test(navigator.userAgent" not in first or "classList.add('human')" not in first:
        out.append("`reader` is not added by the first script, behind the crawler test")
    else:
        names = cm.group(1).lower()
        for need in ("googlebot", "google-inspectiontool", "applebot", "claude", "oai-searchbot", "perplexity",
                     "petalbot", "baiduspider", "bytespider", "ccbot", "bot"):
            if need not in names:
                out.append(f"the crawler test does not name {need!r}")
        if re.search(r"(^|\|)(apple|google)(\||$)", names):
            out.append("the crawler test matches a bare 'apple' or 'google' (every browser says AppleWebKit)")
    if "setTimeout(function(){if(!H.classList.contains('drawn'))H.classList.remove('human')},4000)" not in first:
        out.append("nothing gives the copy back to a reader when no draw comes within 4 s")
    # 1c. THE ROOT'S CLASS STYLES NOTHING ELSE (2026-11-11, Doug: "on my desktop the content does not extend to the
    # bottom of the page"): the first version added `reader`, the card pane's own class, so <html> took the pane's
    # padding and the app stopped 120 px short of the window. A class the first script puts on the root must not be a
    # bare selector of the stylesheet (a rule that would style any element carrying it)
    for cls in re.findall(r"H\.classList\.add\('([\w-]+)'\)", first):
        if re.search(r"(^|[\s,}])\." + re.escape(cls) + r"(?![\w-])", css):
            out.append(f"the root's class '{cls}' is also a bare selector in the stylesheet, so <html> takes that style")
    if re.search(r"classList\.add\(\s*['\"]js['\"]", src) or re.search(r"\.js\s+\.", css):
        out.append("a `js` class is added or styled: it says the script ran, not that the card was drawn")
    html_tag = re.search(r"<html[^>]*>", page).group(0)
    body_tag = re.search(r"<body[^>]*>", page).group(0)
    if "drawn" in html_tag or "drawn" in body_tag:
        out.append("the page arrives with `drawn` already on it: the copy would be hidden before anything was drawn")
    for s in scripts(page.split('class="app"', 1)[0]):
        if "drawn" in s.replace("contains('drawn')", ""):     # the reader's 4 s check only asks
            out.append("a script that runs before the app draws mentions `drawn`")

    # 2. the app's frame waits invisibly, lifted only by `drawn`
    waits = re.findall(r"([^{}\n]*\.ssr\s*~\s*\.app[^{}]*)\{([^}]*)\}", css)
    if len(waits) != 1 or not waits[0][0].strip().startswith("html:not(.drawn):not(.human)") or "visibility:hidden" not in \
            waits[0][1].replace(" ", ""):
        out.append(f"the app's frame is not held invisible by a rule keyed on `drawn` alone: {waits}")
    if waits and "position:absolute" not in waits[0][1].replace(" ", ""):
        out.append("the waiting frame is left in the flow: it would push the server's copy about when it is lifted")
    a, b = page.find('id="ssr"'), page.find('class="app"')
    if not (0 <= a < b):
        out.append("the server's copy does not come before the app's frame in the served page")

    # 3. every server copy carries the class the rule names
    sites = re.findall(r'<article id=\\?"ssr\\?"[^>]*>', server_src)
    bad = [s for s in sites if s != '<article id="ssr" class="ssr">']
    n_ids = server_src.count('id="ssr"')
    if len(sites) < 13 or bad or n_ids != len(sites):
        out.append(f"{len(sites)} server copies of {n_ids} ids; not of class `ssr` exactly: {bad}")

    # 4. `drawn` is added in one place, reached only after a draw
    adds = re.findall(r"classList\.add\(\s*['\"]drawn['\"]\s*\)", js)
    mark = span(js, r"const markDrawn\s*=", r"\n")
    if len(adds) != 1 or "classList.add('drawn')" not in mark:
        out.append(f"`drawn` is added {len(adds)} times; once, in markDrawn, is the rule")
    calls_mark = [m.start() for m in re.finditer(r"\bmarkDrawn\(", js)]
    arrived_def = span(js, r"const arrived\s*=", r"\n")
    if len(calls_mark) != 1 or "markDrawn()" not in arrived_def:
        out.append("markDrawn() is called from somewhere other than arrived()")
    boot = span(js, r"\(async function\(\)\{\n", r"^\}\)\(\);")
    first = scripts(src)[0]
    for what, text in (("the boot script", boot), ("the first script", first)):
        if re.search(r"\b(markDrawn|arrived)\(|classList\.add\(\s*['\"]drawn", text):
            out.append(f"{what} adds `drawn` or calls arrived(): that is before any fetch has answered")
    opentab = span(js, r"function openTab\(", r"^\}")
    setex = span(js, r"function setExplore\(", r"^\}")
    if not re.search(r"selectTab\(id\);\s*(//[^\n]*\n\s*)*arrived\(", opentab):
        out.append("openTab does not call arrived() after selectTab(id): the success path is gone (or runs early)")
    if opentab.count("arrived(") != 2 or "return arrived(" not in opentab:
        out.append("openTab calls arrived() other than once after each of its two ways of showing a tab")
    if not re.search(r"innerHTML = html;\s*if\(wire\) wire\(\);\s*\}\s*arrived\('explore'\)", setex):
        out.append("setExplore does not call arrived('explore') after the pane is filled")
    allowed = {"openTab": opentab.count("arrived("), "setExplore": setex.count("arrived(")}
    if js.count("arrived(") != sum(allowed.values()):
        out.append("arrived() is called outside openTab and setExplore")

    # 5. the failure path
    # the request path is api() and the loop it calls (_apiGet, 2026-11-10: split off when api() began to set the
    # loading bar's class); both are read, or a fault planted in the loop goes unseen
    api = span(js, r"const api = async", r"^\};") + span(js, r"const _apiGet = async", r"^\};")
    if re.search(r"\bcatch\b|innerHTML|textContent|appendChild|\.append\(|\.remove\(", api):
        out.append("api() catches or draws something: a failed request would cover the server's copy")
    note = span(js, r"const _restartNote\s*=", r"^\};")
    guard = re.search(r"if\(n \|\| _serverCopyShows\(\)\) return;", note)
    if not guard or note.index("_serverCopyShows") > note.index("createElement"):
        out.append("the restart notice is drawn over a server copy: it must yield to _serverCopyShows() first")
    shows = span(js, r"const _serverCopyShows\s*=", r";\n")
    if "'.ssr'" not in shows or "contains('drawn')" not in shows:
        out.append("_serverCopyShows() does not mean 'a server copy is on the page and nothing has been drawn'")
    outside = re.sub(re.escape(shows), "", js)
    for m in re.finditer(r"[^\n]*(['\"`#.]ssr\b|id=.ssr)[^\n]*", outside):
        line = m.group(0)
        if not line.lstrip().startswith(("/*", "//", "*")) and "ssr-" not in line:
            out.append(f"script touches the server's copy outside _serverCopyShows: {line.strip()[:90]}")
    if re.search(r"addEventListener\(\s*['\"](unhandledrejection|error)['\"]|window\.onerror", js):
        out.append("a global error handler: an unanswered request must leave the page as the server sent it")

    # 6. the success path exists and is what lifts the copy
    if "ARRIVAL" not in boot or "ARRIVAL = ['chapter']" not in boot:
        out.append("the boot script does not say what each address waits for (ARRIVAL)")
    if not re.search(r"ARRIVAL\s*=\s*exploreId", boot):
        out.append("the boot script does not set ARRIVAL for a card's address")

    # 7. the fallback card's page (2026-10-31) is part of the one server copy, built from the same answer as the app
    if 'fbp["sections"] if fbp else ""' not in server_src or "fbp = _fallback_page(d, eid, c)" not in server_src:
        out.append("the fallback card's page is not part of the server's copy")
    return out


fails = []


# --- the real files hold ---
real = faults(SRC, SERVER)
for f in real:
    fails.append(f)

# --- each fault planted and caught ---
PLANTS = []


def plant(name, src=None, server_src=None, expect=None):
    PLANTS.append((name, src, server_src, expect))


def replaced(text, old, new, count=1):
    assert old in text, f"plant anchor missing: {old!r}"
    return text.replace(old, new, count)


plant("the old rule restored (`.js .ssr`, class added by the first script)",
      src=replaced(replaced(SRC, ".drawn .ssr{display:none}", ".js .ssr{display:none}"),
                   "<script>\n/* a theme", "<script>document.documentElement.classList.add('js')\n/* a theme"),
      expect="only '.drawn .ssr'")

plant("hidden by the script having run: `drawn` added in the first script",
      src=replaced(SRC, "<script>\n/* a theme", "<script>document.documentElement.classList.add('drawn')\n/* a theme"),
      expect='first script')

plant("`drawn` added before the fetch, at the head of the boot script",
      src=replaced(SRC, "(async function(){\n", "(async function(){\n  markDrawn();\n"),
      expect='the boot script adds')

plant("`drawn` added before the fetch, straight after /api/books is asked for",
      src=replaced(SRC, "  const b = await api('/api/books', {});", "  document.documentElement.classList.add('drawn');\n  const b = await api('/api/books', {});"),
      expect='`drawn` is added 2 times')

plant("arrived() called at boot, before any address is drawn",
      src=replaced(SRC, "(async function(){\n", "(async function(){\n  arrived('card');\n"),
      expect='the boot script adds')

plant("an error notice drawn over a server copy: the restart notice no longer yields",
      src=replaced(SRC, "if(n || _serverCopyShows()) return;", "if(n) return;"),
      expect='restart notice')

plant("an error notice drawn over a server copy: api() writes one into the pane when a request fails",
      src=replaced(SRC, "    const r = await fetch(url);",
                   "    let r; try{ r = await fetch(url); }catch(e){ $('#paneinner').innerHTML = '<p>Could not load.</p>'; throw e; }"),
      expect='api() catches')

plant("the copy removed on failure (api() takes the copy off the page)",
      src=replaced(SRC, "    const r = await fetch(url);",
                   "    let r; try{ r = await fetch(url); }catch(e){ document.querySelector('.ssr').remove(); throw e; }"),
      expect='api() catches')

plant("a global error handler that writes a notice",
      src=replaced(SRC, "let ARRIVAL = null;",
                   "let ARRIVAL = null;\nwindow.addEventListener('unhandledrejection', () => { document.body.append('error'); });"),
      expect='global error handler')

plant("the success path removed from openTab (the copy would sit over a working app)",
      src=replaced(SRC, "  arrived(kind === 'ch' ? 'chapter' : 'card');\n}", "}"),
      expect='openTab does not call arrived')

plant("the success path removed from setExplore",
      src=replaced(SRC, "  arrived('explore');\n}", "}"),
      expect='setExplore does not call')

plant("openTab marks the page drawn before the tab is shown",
      src=replaced(SRC, "  selectTab(id);\n  // the page is on screen", "  arrived('card');\n  selectTab(id);\n  // the page is on screen"),
      expect='openTab calls arrived() other than once')

plant("the app's frame left in the flow while the copy shows",
      src=replaced(SRC, "html:not(.drawn):not(.human) .ssr ~ .app{position:absolute;",
                   "html:not(.drawn):not(.human) .ssr ~ .app{"),
      expect='left in the flow')

plant("the app's frame hidden by a rule that does not wait for `drawn`",
      src=replaced(SRC, "html:not(.drawn):not(.human) .ssr ~ .app{", "html .ssr ~ .app{"),
      expect='not held invisible')

plant("the copy hidden for crawlers too (the reader class added without the crawler test)",
      src=replaced(SRC, "if(!C.test(navigator.userAgent||'')){var H", "if(true){var H"),
      expect="behind the crawler test")
plant("Googlebot left off the crawler test",
      src=replaced(SRC, "googlebot|google-inspectiontool|", ""),
      expect="does not name 'googlebot'")
plant("no 4-second return for a reader",
      src=replaced(SRC, "setTimeout(function(){if(!H.classList.contains('drawn'))H.classList.remove('human')},4000)",
                   "0"),
      expect="within 4 s")

plant("the page served already `drawn`",
      src=replaced(SRC, '<html lang="en">', '<html lang="en" class="drawn">'),
      expect='already on it')

plant("the fallback card's sections left out of the server's copy",
      server_src=replaced(SERVER, '            + (fbp["sections"] if fbp else "")\n', ''),
      expect="fallback card's page")

plant("the root's class named as the card pane's (`reader`, the 120 px gap at the bottom of the window)",
      src=replaced(replaced(SRC, "H.classList.add('human')", "H.classList.add('reader')"),
                   "H.classList.remove('human')", "H.classList.remove('reader')"),
      expect="also a bare selector")
plant("a server copy without the class the rule names",
      server_src=replaced(SERVER, '<article id="ssr" class="ssr"><h1>{_esc(name)}</h1>',
                          '<article id="ssr" class="ssr-card"><h1>{_esc(name)}</h1>'),
      expect='server copies')


for name, src, server_src, expect in PLANTS:
    got = faults(src if src is not None else SRC, server_src if server_src is not None else SERVER)
    if not any(expect in f for f in got):
        fails.append(f"PLANT NOT CAUGHT (expected a fault saying {expect!r}): {name}; got {got}")

print(f"{len(PLANTS)} planted faults, each caught; {len(real)} faults in the real files")
for f in fails:
    print("FAIL", f)
sys.exit(1 if fails else 0)
