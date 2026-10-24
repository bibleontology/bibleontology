"""IndexNow: tell Bing (and the other IndexNow engines) which addresses are new or changed.

2026-10-07, after verifying the site in Bing Webmaster Tools: Bing's own
URL Submission takes about 100 addresses a day by hand; IndexNow takes up to
10,000 in one call. The key is public by design: Bing confirms a submission
comes from the site's owner by fetching https://bibleontology.org/<key>.txt,
served by the Caddyfile from deploy/www/ (tests/test_crawlers.py keeps the two
in step). Google does not use IndexNow.

    python tools/indexnow.py --check           the key answers on the live site?
    python tools/indexnow.py --new --dry-run   what would be sent
    python tools/indexnow.py --new             every sitemap address not yet sent
    python tools/indexnow.py --urls a b c      these, changed (e.g. a theme's page)

Nothing is sent unless the live key file answers with the key. What was sent,
and when, is kept in out/indexnow-sent.json, so --new sends only what is new.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / "deploy" / "www"
SENT = ROOT / "out" / "indexnow-sent.json"
HOST = "bibleontology.org"
ENDPOINT = "https://api.indexnow.org/indexnow"
BATCH = 10000


def key():
    ks = [p for p in WWW.glob("*.txt") if p.name != "robots.txt"]
    assert len(ks) == 1, f"one key file expected in deploy/www, found {len(ks)}"
    k = ks[0].read_text(encoding="utf-8").strip()
    assert k == ks[0].stem, "the key file does not contain its own key"
    return k


def live_ok(k):
    """the key file as the world sees it: Bing answers 403 to every call otherwise"""
    url = f"https://{HOST}/{k}.txt"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "indexnow-check"}),
                                    timeout=20) as r:
            body = r.read().decode("utf-8").strip()
            return r.status == 200 and body == k, f"{r.status} {body[:40]!r}"
    except urllib.error.HTTPError as e:
        return False, f"{e.code}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def sitemap_urls():
    out = []
    # the site's own pages first, then chapters, verses and cards
    for name in ("pages", "chapters", "verses", "cards"):
        f = WWW / f"sitemap-{name}.xml"
        if f.exists():
            out += re.findall(r"<loc>([^<]+)</loc>", f.read_text(encoding="utf-8"))
    return list(dict.fromkeys(u for u in out if u.startswith(f"https://{HOST}/")))


def send(k, urls):
    body = json.dumps({"host": HOST, "key": k, "keyLocation": f"https://{HOST}/{k}.txt",
                       "urlList": urls}).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--new", action="store_true")
    g.add_argument("--urls", nargs="+")
    # a list too long for a command line (2026-10-11: every card, after the
    # week's site-wide card changes): one address per line
    g.add_argument("--file")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.file:
        a.urls = [l.strip() for l in Path(a.file).read_text(encoding="utf-8").splitlines() if l.strip()]
    k = key()
    ok, why = live_ok(k)
    print(f"key file live: {'yes' if ok else 'NO'} ({why})")
    if a.check:
        sys.exit(0 if ok else 1)
    sent = json.loads(SENT.read_text(encoding="utf-8")) if SENT.exists() else {}
    if a.new:
        urls = [u for u in sitemap_urls() if u not in sent]
    else:
        urls = [u for u in a.urls if u.startswith(f"https://{HOST}/")]
        assert len(urls) == len(a.urls), "every address must be on " + HOST
    print(f"{len(urls)} addresses to send")
    if a.dry_run or not urls:
        print("\n".join(urls[:10]) + ("\n..." if len(urls) > 10 else ""))
        return
    if not ok:
        sys.exit("not sending: the key file is not live with the key (push, then reload Caddy)")
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    for i in range(0, len(urls), BATCH):
        part = urls[i:i + BATCH]
        st = send(k, part)
        print(f"batch {i // BATCH + 1}: {len(part)} addresses -> {st}")
        if st not in (200, 202):
            sys.exit(f"stopped at HTTP {st} (403: key not found; 422: address not on the host; "
                     f"429: too many)")
        for u in part:
            sent[u] = stamp
        SENT.write_text(json.dumps(sent, indent=0, sort_keys=True), encoding="utf-8")
    print(f"sent {len(urls)}; {len(sent)} recorded in {SENT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
