"""robots.txt and the sitemaps (plan A.21), written to deploy/www/ for Caddy to
serve from disk -- so they answer while the app restarts: Google pauses
crawling a whole site while its robots.txt answers 5xx (observed 2026-10-03).

What is listed, and why:
  - the front page, /about, /graph, the 20 major themes
  - every card, except sayings and passage units named only by where they
    are ("Satan at Job 2:2", passage records): the verse pages carry those,
    and a page per speech would be thin
  - not a major theme's card: it names /themes/<name> as the page to keep
  - every chapter
  - every verse with something of its own -- a card that cites it, or a
    quotation, echo, parallel or judged shared wording (ontology/
    allusions.jsonl); a verse page with only its text is thin,
    and a site with many thin pages is discounted
  - never /graph/<id>: those name the card as the page to keep (the graph
    view is not to be the dominant mode that search engines use)

robots.txt says the site's policy (P-77, approved): training crawlers
out; search engines and AI search and answer fetchers in. Since 2026-10-05 it
is the only place that says it -- Cloudflare's training block also blocked
Googlebot, and was set to Allow.

    python tools/sitemap.py          -> deploy/www/{robots.txt, sitemap*.xml}
"""
import datetime
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deploy" / "www"
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

SITE = S.SITE
# THE LINE IS ATTRIBUTION (2026-10-05: the concern with training is that
# there is no attribution): search engines and AI search and answer fetchers cite
# and link the page, and are welcome; crawlers that take the text into a
# model, where nothing points back, are not. Every name here is also refused
# with a 403 by the Caddyfile's @training (deploy/Caddyfile), except the two
# that are robots.txt tokens, not crawlers (TOKENS_ONLY); tests/test_crawlers.py
# keeps the two lists the same.
TRAINING = ["GPTBot", "ClaudeBot", "anthropic-ai", "CCBot", "Google-Extended",
            "Applebot-Extended", "meta-externalagent", "FacebookBot", "Bytespider",
            "cohere-training-data-crawler", "Diffbot", "Omgilibot", "PerplexityBot-Training",
            "Amazonbot", "Timpibot", "TikTokSpider"]
# Google's and Apple's training opt-outs: honoured only through robots.txt
# (their crawlers are Googlebot and Applebot, which search with the same visit)
TOKENS_ONLY = {"Google-Extended", "Applebot-Extended"}
SPEECH = re.compile(r"^.+ at (?:[1-3] ?)?[A-Z][a-z]+\.? \d+:\d+$")


def urlset(urls, today):
    # no per-page lastmod: stamping every page "today" on each build is the
    # kind of date Google learns to ignore
    rows = "".join(f"<url><loc>{escape(SITE + u)}</loc></url>\n" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + rows + "</urlset>\n")


def main():
    d = S.load()
    today = datetime.date.today().isoformat()
    pages = ["/", "/about", "/faq", "/graph"] + [S.theme_path(t["id"]) for t in S._theme_map().get("themes", [])] \
        + [S._side_path(t) for t in S._theme_hubs() if S._imagery(t)] \
        + [f"/explore/{g}" for g in (*S.EXPLORE_PAGES, *S.EXPLORE_GROUPS, *S.EXPLORE_SECTIONS)] \
        + ["/ns/meaning", "/ns/structure", "/ns/relation",    # the published ontology (2026-10-11)
           "/ns/claim"]                                       # the claim vocabulary (1.1.0, plan 8.1a)
    # the alignment file and the map (1.2.0, plan 8.1e): listed once released
    pages += [p for p, f in (("/ns/alignment", "alignment.ttl"), ("/ns/map", "map.html"))
              if (S.OUT / "ns" / f).exists()]
    # (a theme's imagery side by side, plan 7.6b: its own page, shown once
    # the site's owner has seen it)
    # the blog (2026-10-05: included in the sitemap as well): its list and
    # every post built by tools/blog_build.py
    blog = ROOT / "app2" / "static" / "blog"
    if (blog / "index.html").exists():
        pages += ["/blog/"] + [f"/blog/{p.stem}" for p in sorted(blog.glob("*.html")) if p.stem != "index"]
    cards, skipped = [], 0
    for eid, e in sorted(d["ents"].items()):
        attrs = e.get("attrs") or {}
        # a record consolidated into an event (ontology/aliases.jsonl) answers
        # 301 to the event's card: a sitemap lists only addresses that answer
        if e["type"] == "passage" or (e["type"] == "text" and SPEECH.match(e["name"])) \
                or attrs.get("kind") == "major_theme" or e.get("alias_of"):
            skipped += 1
            continue
        # the card's own address: a name-made one where the id misleads
        # (tools/card_slugs.py), never an address that only redirects
        cards.append(f"/e/{S.quote(S._addr(eid))}")
    chapters, verses = [], []
    cited = set(k for k, ids in S._cards_at().items()
                if any((d["ents"].get(i) or {}).get("type") not in ("text", "passage") for i in ids))
    echoed = set()
    for ref, got in (d.get("echoes") or {}).items():
        if any(got.get(k) for k in ("earlier", "later", "parallel", "refers_to")):
            m = re.match(r"^(\w+)\.(\d+)\.(\d+)$", S.bsb_ref(d, ref) or "")
            if m:
                echoed.add((S.MACULA_BACK.get(m.group(1), m.group(1)), int(m.group(2)), int(m.group(3))))
    # what two verses share (plan 6.17): both verses of every judged link have
    # something of their own -- 49 had nothing else when it landed (2026-10-04)
    for r in S._rows(ROOT / "ontology" / "allusions.jsonl"):
        for ref in (r["nt"], r["ot"]):
            b, cv = ref.rsplit(" ", 1)
            c, v = cv.split(":")
            echoed.add((b, int(c), int(v)))
    # and every verse carrying a step of a story told again (plan 6.18)
    for r in S._rows(ROOT / "ontology" / "told-again.jsonl"):
        for pair in r["beats"]:
            for ref, _w in pair:
                b, cv = ref.rsplit(" ", 1)
                c, v = cv.split(":")
                echoed.add((b, int(c), int(v)))
    # and both verses of every shown reference from a letter, a poem or a
    # prophet (plans 6.21, 6.19, 6.20): its first verse and the account's
    for refs in S._letter_refs().values():
        for r in refs:
            for k in (r["letter"][0], re.sub(r"\s*[-–]\s*\d+$", "", r["account_verse"])):
                m = re.match(r"^(\w+)\.(\d+)\.(\d+)$", S.bsb_ref(d, S._macula_ref(d, k)) or "")
                if m:
                    echoed.add((S.MACULA_BACK.get(m.group(1), m.group(1)), int(m.group(2)), int(m.group(3))))
    # and both verses of every shown link from Revelation (plan 6.22)
    for r in S._rows(ROOT / "ontology" / "revelation-links.jsonl"):
        if not r.get("reviewed_by_owner"):
            continue
        for k in (r["rev"][0], r["other"][0]):
            m = re.match(r"^(\w+)\.(\d+)\.(\d+)$", S.bsb_ref(d, S._macula_ref(d, k)) or "")
            if m:
                echoed.add((S.MACULA_BACK.get(m.group(1), m.group(1)), int(m.group(2)), int(m.group(3))))
    # and of every shown link between the history books (plan 6.23) -- not a
    # nearby link standing alone: it is shown quietly ("don't overemphasize
    # isolated close references"), and a verse with only that is thin
    for r in S._rows(ROOT / "ontology" / "history-links.jsonl"):
        if not r.get("reviewed_by_owner") or r.get("quiet"):
            continue
        for k in (r["later"][0], r["earlier"][0]):
            m = re.match(r"^(\w+)\.(\d+)\.(\d+)$", S.bsb_ref(d, S._macula_ref(d, k)) or "")
            if m:
                echoed.add((S.MACULA_BACK.get(m.group(1), m.group(1)), int(m.group(2)), int(m.group(3))))
    for (b, c, v) in sorted(d["verses"], key=lambda k: (S.ORDER.index(k[0]) if k[0] in S.ORDER else 99, k[1], k[2])):
        if v == 1:
            chapters.append(f"/p/{b}.{c}")
        if (b, c, v) in cited or (b, c, v) in echoed:
            verses.append(f"/p/{b}.{c}.{v}")
    OUT.mkdir(parents=True, exist_ok=True)
    files = {"sitemap-pages.xml": pages, "sitemap-cards.xml": cards,
             "sitemap-chapters.xml": chapters, "sitemap-verses.xml": verses}
    for name, urls in files.items():
        assert len(urls) <= 50000, name          # the protocol's limit per file
        (OUT / name).write_text(urlset(urls, today), encoding="utf-8", newline="\n")
    index = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
             + "".join(f"<sitemap><loc>{SITE}/{n}</loc><lastmod>{today}</lastmod></sitemap>\n"
                       for n in files)
             + "</sitemapindex>\n")
    (OUT / "sitemap.xml").write_text(index, encoding="utf-8", newline="\n")
    # NOT ENFORCED AT THE EDGE ANY MORE (2026-10-05). Cloudflare's "training
    # blocked" policy also blocked Googlebot and Bingbot from every page, and
    # the free plan allows no per-crawler exception; training was set to
    # Allow there, so this file is the training opt-out, honoured by the
    # crawlers named (docs/OPERATIONS.md, the Cloudflare table)
    robots = ("# Bible Ontology. Search engines and AI search and answer fetchers are\n"
              "# welcome; crawlers that copy for model training are asked not to.\n\n"
              + "".join(f"User-agent: {b}\n" for b in TRAINING) + "Disallow: /\n\n"
              "User-agent: *\nDisallow: /api/\nDisallow: /ops\nAllow: /\n\n"
              f"Sitemap: {SITE}/sitemap.xml\n")
    (OUT / "robots.txt").write_text(robots, encoding="utf-8", newline="\n")
    n_verses = len(d["verses"])
    print(f"pages {len(pages)}, cards {len(cards)} (left out {skipped}), chapters {len(chapters)}, "
          f"verses {len(verses)} of {n_verses} ({len(cited)} cited by a card, {len(echoed)} with "
          f"quotation, echo or parallel) -> {OUT}")


if __name__ == "__main__":
    main()
