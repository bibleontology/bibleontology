"""The face of the I AM card: the verses, the speakers, the original words (2026-10-31).

render(data) builds one HTML fragment from the card's data and nothing else; bush_svg() draws Exodus 3:2.
"""

import html

CSS = """
.iam { color: var(--ink); font-family: var(--ff-text); line-height: 1.55; max-width: 100%; }
.iam p { margin: 0 0 .5rem; }
.iam a { color: var(--ochre-text); text-decoration: none; border-bottom: 1px solid var(--ochre-soft); }
.iam-name { font-family: var(--ff-text); font-size: 1.9rem; font-weight: 600; line-height: 1.15; color: var(--ink); margin: 0 0 .5rem; }
.iam-top { display: flex; flex-direction: column; gap: .75rem; margin-bottom: 1.25rem; }
.iam-sketch { max-width: 96px; color: var(--ochre-text); }
.iam-sketch svg { width: 96px; height: 96px; display: block; }
.iam-lede { font-size: 1.02rem; }
.iam-lede .iam-ref { display: block; font-family: var(--ff-data); font-size: .8rem; color: var(--muted); margin-bottom: .2rem; }
.iam-cap { font-size: .86rem; color: var(--muted); margin-top: .4rem; }
.iam-cap .iam-ref { font-family: var(--ff-data); color: var(--muted); }
.iam-group { border-top: 1px solid var(--rule); padding: .9rem 0 .4rem; }
.iam-group > h2, .iam-group > summary { font-size: 1rem; font-weight: 600; margin: 0 0 .2rem; color: var(--ink); }
.iam-group > summary { cursor: pointer; }
.iam-sub { font-size: .82rem; color: var(--muted); margin: 0 0 .6rem; }
.iam-count { font-family: var(--ff-data); font-size: .74rem; color: var(--muted); margin-left: .35rem; }
.iam-row { padding: .55rem 0 .6rem; border-top: 1px dotted var(--rule); }
.iam-row:first-of-type { border-top: 0; }
.iam-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: .4rem; margin-bottom: .2rem; }
.iam-ref { font-family: var(--ff-data); font-size: .8rem; }
.iam-who { font-size: .78rem; color: var(--muted); }
.iam-image { font-size: .74rem; color: var(--slate); background: var(--slate-soft); border-radius: 999px; padding: .05rem .45rem; }
.iam-words { display: flex; flex-wrap: wrap; gap: .3rem; margin: .3rem 0 .35rem; }
.iam-w { background: var(--ochre-soft); border-radius: .35rem; padding: .1rem .4rem; display: inline-flex; align-items: baseline; gap: .3rem; max-width: 100%; }
.iam-w .iam-t { font-family: var(--ff-data); font-size: .92rem; }
.iam-w .iam-x { font-family: var(--ff-data); font-size: .68rem; color: var(--muted); }
.iam-w .iam-g { font-size: .68rem; color: var(--ochre-text); }
.iam-verse { font-size: .95rem; }
.iam-after { font-size: .84rem; color: var(--muted); margin-top: .25rem; }
.iam-chips { display: flex; flex-wrap: wrap; gap: .3rem; margin: .2rem 0 .7rem; }
.iam-chip { font-size: .72rem; color: var(--ochre-text); background: var(--ochre-soft); border-radius: 999px; padding: .1rem .5rem; }
.iam-pair { border-top: 1px solid var(--rule-strong); padding: 1rem 0 .6rem; margin-top: .5rem; }
.iam-pair > h2 { font-size: .98rem; margin: 0 0 .5rem; }
.iam-sides { display: flex; flex-direction: column; gap: .7rem; }
.iam-side { background: var(--surface); border-radius: .4rem; padding: .55rem .6rem; }
.iam-side .iam-verse { margin-bottom: .3rem; }
.iam-side .iam-words { margin: .2rem 0 0; }
.iam-side .iam-w { background: var(--paper); }
@media (min-width: 640px) {
  .iam-top { flex-direction: row; align-items: flex-start; gap: 1rem; }
  .iam-sketch { flex: 0 0 96px; }
  .iam-sides { flex-direction: row; }
  .iam-side { flex: 1 1 0; min-width: 0; }
}
"""


def e(s):
    return html.escape("" if s is None else str(s), quote=True)


def bush_svg():
    """Exodus 3:2: a shrub alight but not consumed. Lines only; nothing in the fire but fire.
    Traced by Claude (2026-10-31) from a draft Doug made with Copilot: the canopy holding three flames."""
    return (
        '<svg viewBox="0 0 96 96" role="img" aria-label="The bush on fire, burning but not consumed" '
        'fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" '
        'width="96" height="96">'
        # the ground, the trunk, the two branches, the line the canopy rests on
        '<path d="M15 79H81"/>'
        '<path d="M46.5 79C47.3 72 47.3 63 47 57M49.5 79C48.7 72 48.7 63 49 57"/>'
        '<path d="M24 57.5L47 68"/>'
        '<path d="M72 57.5L49 68"/>'
        '<path d="M27 56H69"/>'
        # the canopy, scalloped
        '<path d="M27 56C19 56 15 50 16.5 44.5C14 40 17.5 33 23.5 33C25 26 33 22 40 24.5C42 19 46 16.5 50 17'
        'C54.5 17.5 57.5 21 58 24.5C64.5 22 71.5 26 72.5 33C78.5 33 82 40 79.5 44.5C81 50 77 56 69 56"/>'
        # the fire: a tall flame and one either side, rising from within it
        '<path d="M41 56C37 46 39.5 36 44 29.5C46 26.5 46.5 23.5 44.5 21.5C50 21 54.5 25.5 55.5 32'
        'C57 40 55.5 49 54.5 56Z" fill="var(--ochre-soft)"/>'
        '<path d="M30 56C27 49 29 42 33.5 37.5C34.5 36.3 34 34.5 32.5 34C35.5 33 38.5 34.6 39.2 37.4'
        'C40.2 43 39.3 50 38.5 56Z" fill="var(--ochre-soft)"/>'
        '<path d="M66 56C69 49 67 42 62.5 37.5C61.5 36.3 62 34.5 63.5 34C60.5 33 57.5 34.6 56.8 37.4'
        'C55.8 43 56.7 50 57.5 56Z" fill="var(--ochre-soft)"/>'
        "</svg>"
    )


def _link(go, text):
    return '<a href="/p/%s">%s</a>' % (e(go), e(text))


def _ref(go, ref):
    return '<span class="iam-ref">%s</span>' % _link(go, ref)


def _word(w):
    lang = w.get("lang", "")
    if lang == "he":
        mark = ' lang="he" dir="rtl"'
    elif lang == "grc":
        mark = ' lang="grc"'
    else:
        mark = ""
    out = ['<span class="iam-w">']
    out.append('<span class="iam-t"%s>%s</span>' % (mark, e(w.get("t"))))
    if w.get("x"):
        out.append('<span class="iam-x">%s</span>' % e(w["x"]))
    if w.get("g"):
        out.append('<span class="iam-g">%s</span>' % e(w["g"]))
    out.append("</span>")
    return "".join(out)


def _words(words):
    if not words:
        return ""
    return '<div class="iam-words">%s</div>' % "".join(_word(w) for w in words)


def _after(after):
    if not after:
        return ""
    return '<p class="iam-after">%s%s</p>' % (_ref(after.get("go"), after.get("ref")), " " + e(after.get("text")))


def _row(item):
    out = ['<div class="iam-row">']
    head = [_ref(item.get("go"), item.get("ref"))]
    if item.get("who"):
        head.append('<span class="iam-who">%s</span>' % e(item["who"]))
    if item.get("image"):
        head.append('<span class="iam-image">%s</span>' % e(item["image"]))
    out.append('<div class="iam-head">%s</div>' % "".join(head))
    out.append(_words(item.get("words")))
    out.append('<p class="iam-verse">%s</p>' % e(item.get("text")))
    out.append(_after(item.get("after")))
    out.append("</div>")
    return "".join(out)


def _group(g):
    shown = bool(g.get("shown"))
    tag = "section" if shown else "details"
    n = len(g.get("items", []))
    out = ['<%s class="iam-group" data-group="%s" data-count="%d">' % (tag, e(g.get("id")), n)]
    if shown:
        out.append("<h2>%s<span class=\"iam-count\">%d</span></h2>" % (e(g.get("title")), n))
    else:
        out.append('<summary>%s<span class="iam-count">%d</span></summary>' % (e(g.get("title")), n))
    if g.get("sub"):
        out.append('<p class="iam-sub">%s</p>' % e(g["sub"]))
    if g.get("id") == "images":
        seen = []
        for i in g.get("items", []):
            img = i.get("image")
            if img and img not in seen:
                seen.append(img)
        if seen:
            out.append('<div class="iam-chips">%s</div>' % "".join(
                '<span class="iam-chip">%s</span>' % e(s) for s in seen))
    for i in g.get("items", []):
        out.append(_row(i))
    out.append("</%s>" % tag)
    return "".join(out)


def _pair_word(w, lang_default):
    lang = w.get("lang", lang_default)
    if lang == "he":
        mark = ' lang="he" dir="rtl"'
    elif lang == "grc":
        mark = ' lang="grc"'
    else:
        mark = ""
    return '<span class="iam-w"><a href="%s"%s>%s</a><span class="iam-g">%s</span></span>' % (
        e(w.get("addr")), mark, e(w.get("lemma")), e(w.get("gloss")))


def _side(s):
    out = ['<div class="iam-side">']
    out.append('<div class="iam-head">%s</div>' % _ref(s.get("go"), s.get("ref")))
    out.append('<p class="iam-verse">%s</p>' % e(s.get("text")))
    ws = s.get("words") or []
    if ws:
        out.append('<div class="iam-words">%s</div>' % "".join(_pair_word(w, "") for w in ws))
    out.append("</div>")
    return "".join(out)


def _pair(p):
    return ('<div class="iam-pair" data-pair><h2>%s</h2><div class="iam-sides">%s%s</div></div>'
            % (e(p.get("words")), _side(p.get("a", {})), _side(p.get("b", {}))))


def render(data):
    parts = ['<div class="iam">']
    parts.append('<h1 class="iam-name">%s</h1>' % e(data.get("name")))
    lede = data.get("lede") or {}
    parts.append('<div class="iam-top">')
    parts.append('<div class="iam-sketch">%s</div>' % bush_svg())
    sketch = data.get("sketch") or {}
    if sketch:
        parts.append('<p class="iam-cap">%s%s</p>' % (_ref(sketch.get("go"), sketch.get("ref")),
                                                      " " + e(sketch.get("text"))))
    parts.append("</div>")
    if lede:
        parts.append('<div class="iam-lede">')
        parts.append(_ref(lede.get("go"), lede.get("ref")))
        parts.append('<p class="iam-verse">%s</p>' % e(lede.get("text")))
        parts.append("</div>")
    for g in data.get("groups", []):
        parts.append(_group(g))
    for p in data.get("pairs", []):
        parts.append(_pair(p))
    parts.append("</div>")
    return "".join(parts)
