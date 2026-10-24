"""Build the blog: docs/blog/posts/<date>-<slug>.md -> app2/static/blog/<slug>.html,
and app2/static/blog/index.html listing the posts, newest first.

The posts are written by hand; this only turns them into pages. A deliberately small
markdown reader -- headings, paragraphs, lists, block quotes, a rule, **bold**,
*italics* and [links](url) -- because a post is prose, and nothing outside the
standard library is installed on the server. Everything is HTML-escaped before
any markup is added, so a post cannot inject a script. The site's own links
(https://bibleontology.org/...) are written relative, so a page works on a
laptop as it does live.

Each post ends with a reply box (one fixed inline script, which the server's
content security policy hashes); the site's typefaces and colours, light and
dark.

    python tools/blog_build.py
"""
from __future__ import annotations

import datetime as dt
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "blog" / "posts"
OUT = ROOT / "app2" / "static" / "blog"
SITE = "https://bibleontology.org"


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
               lambda m: f'<a href="{html.escape(m.group(2).replace(SITE, "") or "/", quote=True)}">{m.group(1)}</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<i>\1</i>", s)
    # A BARE DOMAIN IS A LINK, as a markdown viewer makes it (2026-10-05:
    # a bare BibleProject.com is meant to be a hyperlink): only in text, never
    # inside a tag or an existing link
    parts = re.split(r"(<a\b.*?</a>|<[^>]+>)", s, flags=re.S)
    for k in range(0, len(parts), 2):
        parts[k] = re.sub(r"(?<![\w./@-])((?:www\.)?[A-Za-z0-9][A-Za-z0-9-]*\.(?:com|org|net))(?![\w/-])",
                          lambda m: f'<a href="https://{m.group(1).lower()}">{m.group(1)}</a>', parts[k])
    return "".join(parts)


def render(md: str) -> tuple[str, str]:
    """(title, body html)"""
    lines = md.replace("\r\n", "\n").split("\n")
    title, out, para, items, quote = "", [], [], [], []

    def flush():
        nonlocal para, items, quote
        if para:
            out.append(f"<p>{inline(' '.join(x.strip() for x in para))}</p>")
        if items:
            out.append("<ul>" + "".join(f"<li>{inline(' '.join(i))}</li>" for i in items) + "</ul>")
        if quote:
            ps, cur = [], []
            for q in quote + [""]:
                if q.strip():
                    cur.append(q.strip())
                elif cur:
                    ps.append(f"<p>{inline(' '.join(cur))}</p>")
                    cur = []
            out.append("<blockquote>" + "".join(ps) + "</blockquote>")
        para, items, quote = [], [], []

    for ln in lines:
        if ln.startswith("# ") and not title:
            title = ln[2:].strip()
            continue
        if ln.strip() == "---":
            flush()
            continue
        if ln.startswith("## "):
            flush()
            out.append(f"<h2>{inline(ln[3:].strip())}</h2>")
            continue
        if ln.startswith(">"):
            if para or items:
                flush()
            quote.append(ln[1:].lstrip() if ln[1:].strip() else "")
            continue
        if ln.startswith("- "):
            if para or quote:
                flush()
            items.append([ln[2:]])
            continue
        if items and ln.startswith("  ") and ln.strip():
            items[-1].append(ln.strip())
            continue
        if not ln.strip():
            flush()
            continue
        if items or quote:
            flush()
        para.append(ln)
    flush()
    return title, "\n".join(out)


STYLE = """
:root{--paper:#F3F5F8;--surface:#FFFFFF;--ink:#141F2C;--muted:#5C6A7B;--rule:#D9E0E8;--ochre:#A96A1E;--slate:#356A8C}
@media (prefers-color-scheme: dark){:root{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2A3542;--ochre:#DFA759;--slate:#79AECD}}
html{background:var(--paper)}
body{margin:0;background:var(--paper);color:var(--ink);font-family:Spectral,Georgia,serif;font-size:18px;line-height:1.7}
header{border-bottom:1px solid var(--rule);background:var(--surface)}
header .in{max-width:44rem;margin:0 auto;padding:12px 16px;display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.brand{font-weight:600;color:var(--ink);text-decoration:none}.brand span{color:var(--ochre)}
nav a{color:var(--slate);font-size:15px;margin-left:14px}
main{max-width:44rem;margin:0 auto;padding:24px 16px 64px}
h1{font-size:2rem;line-height:1.2;margin:.4em 0 .1em}
.date{color:var(--muted);font-family:'IBM Plex Mono',monospace;font-size:13px;margin:0 0 1.6em}
h2{font-size:1.3rem;margin:1.8em 0 .4em}
a{color:var(--slate)}
blockquote{margin:1.2em 0;padding:.2em 1.2em;border-left:3px solid var(--ochre);color:var(--ink);font-style:italic}
blockquote b{font-style:italic}
ul{padding-left:1.3em}li{margin:.3em 0}
.posts{list-style:none;padding:0}.posts li{margin:1.4em 0}.posts a{font-size:1.25rem;font-weight:600}
footer{max-width:44rem;margin:0 auto;padding:0 16px 40px;color:var(--muted);font-size:14px}
.reply{margin-top:3em;padding:1em 1.2em;background:var(--surface);border:1px solid var(--rule);border-radius:8px}
.reply h2{margin-top:0}.reply p{font-size:16px;color:var(--muted);margin:.3em 0 .8em}
.reply textarea{width:100%;box-sizing:border-box;min-height:8em;font:inherit;font-size:16px;padding:.6em;
  border:1px solid var(--rule);border-radius:6px;background:var(--paper);color:var(--ink)}
.reply button{margin-top:.6em;font:600 15px system-ui,sans-serif;padding:.5em 1.2em;border:0;border-radius:999px;
  background:var(--slate);color:var(--surface);cursor:pointer}
.reply .hp{position:absolute;left:-9999px}
#rmsg{font:14px system-ui,sans-serif;color:var(--muted);margin-left:.8em}
"""

# A PLACE TO ANSWER THE AUTHOR (2026-10-05: give the reader a place to
# respond directly to the author). The site's reader-feedback path, unchanged:
# POST /api/feedback from this site's own pages, at most 1,000 characters, a
# hidden field a person never fills, rate limited; stored where nothing serves
# it and read on /ops/feedback with the page it came from. Nothing a reader
# writes is published or echoed back. The script is inline and fixed, so the
# server's content security policy hashes it like the app's own.
REPLY = """
<section class="reply"><h2>Reply to the author</h2>
<p>This goes to Doug alone. Nothing you write here is published. If you would like an answer, say how to reach you.</p>
<textarea id="rtext" maxlength="1000" aria-label="Your reply"></textarea>
<input class="hp" id="rweb" tabindex="-1" autocomplete="off" aria-hidden="true">
<button id="rsend" type="button">Send</button><span id="rmsg"></span></section>
<script>
(function(){
  var b=document.getElementById('rsend'),m=document.getElementById('rmsg'),t=document.getElementById('rtext');
  b.addEventListener('click',function(){
    var text=t.value.trim(); if(!text){m.textContent='Write something first.';return;}
    b.disabled=true; m.textContent='Sending…';
    fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text:text,page:location.pathname,title:'Reply to the author: '+document.title,
        website:document.getElementById('rweb').value,
        device:matchMedia('(max-width: 767px)').matches?'mobile':'desktop'})})
    .then(function(r){ if(r.ok){m.textContent='Thank you, sent.';t.value='';return;}
      return r.json().then(function(j){m.textContent=j.error?j.error.charAt(0).toUpperCase()+j.error.slice(1)+'.':'It could not be sent; try again later.';b.disabled=false;}); })
    .catch(function(){m.textContent='It could not be sent; try again later.';b.disabled=false;});
  });
})();
</script>
"""


def page(title: str, body: str, desc: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · Bible Ontology</title>
<meta name="description" content="{html.escape(desc, quote=True)}">
<link rel="stylesheet" href="/vendor/fonts-2026-10-01/fonts.css">
<style>{STYLE}</style></head><body>
<header><div class="in"><a class="brand" href="/">Bible <span>Ontology</span></a>
<nav><a href="/blog/">Blog</a><a href="/faq">FAQ</a><a href="/about">About</a></nav></div></header>
<main>{body}</main>
<footer>Bible Ontology · <a href="/">Open the site</a></footer>
</body></html>
"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    posts = []
    for f in sorted(SRC.glob("*.md"), reverse=True):
        m = re.match(r"(\d{4}-\d{2}-\d{2})-(.+)\.md$", f.name)
        if not m:
            continue
        date, slug = dt.date.fromisoformat(m.group(1)), m.group(2)
        title, body = render(f.read_text(encoding="utf-8"))
        first = re.search(r"<p>(.*?)</p>", body)
        desc = re.sub(r"<[^>]+>", "", first.group(1)) if first else title
        when = f"{date:%B} {date.day}, {date.year}"
        (OUT / f"{slug}.html").write_text(
            page(title, f"<article><h1>{html.escape(title)}</h1><p class='date'>{when}</p>{body}</article>"
                        + REPLY, desc),
            encoding="utf-8")
        posts.append((when, slug, title, desc))
    items = "".join(f"<li><a href='/blog/{s}'>{html.escape(t)}</a><div class='date'>{w}</div>"
                    f"<div>{html.escape(d)}</div></li>" for w, s, t, d in posts)
    (OUT / "index.html").write_text(page("Blog", f"<h1>Blog</h1><ul class='posts'>{items}</ul>",
                                         "Posts about building Bible Ontology."), encoding="utf-8")
    print(len(posts), "post(s) built into", OUT)
    # THE FAQ (2026-10-12: a faq page for confused people to
    # complement the about; simple, straightforward but grounded answers):
    # docs/faq.md, rendered the same way, served at /faq
    faq = ROOT / "docs" / "faq.md"
    if faq.exists():
        title, body = render(faq.read_text(encoding="utf-8"))
        (OUT.parent / "faq.html").write_text(
            page(title, f"<article><h1>{html.escape(title)}</h1>{body}</article>",
                 "Short answers about Bible Ontology: the name, what it is, whether to trust it, "
                 "which Bible and books it uses, its principles and what is planned."),
            encoding="utf-8")
        print("faq built into", OUT.parent / "faq.html")


if __name__ == "__main__":
    main()
