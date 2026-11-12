"""Engaged readers, and bots by name, on /ops (2026-11-03). Written before the code.

From November a farm of desktop "Chrome" clients runs the page's script, so it sends /api/open and is counted as a
reader: on 3 November, 226 "readers" were desktops and 1 a phone. A person does something on the page; the farm
loads and leaves. And the bot requests were one number, with the AI fetchers (the ones that cite the site) hidden in
it. This checks, on the real counter with a scratch folder:

THE INTERFACE (app2/activity.py; change nothing else in its behavior):
  /api/engaged     sent by the page once, on the reader's first real tap, key or scroll. Counted only for a browser
                   whose hash is already a reader today (sent /api/open first); counted once per reader a day:
                   c["engaged"] (a number, starting at 0 on a new day), and c["engaged_devices"] {"phone"|"tablet"|
                   "desktop": n} by the same DEVICE rules. It is not a page and bumps nothing else. The day's
                   engaged hashes are kept in <dir>/.<day>.engaged as the readers are in .<day>.readers (8 bytes
                   each), reloaded on a restart within the day, and earlier days' files deleted.
  BOT_NAMES        an ordered tuple of (name, compiled regex). Every bot request is counted under the first name
                   whose regex matches its browser string, else "other": c["bots_named"] {name: n}. The names, in
                   order:
                     "ChatGPT, for a user"    ChatGPT-User          "OpenAI search"       OAI-SearchBot
                     "OpenAI training"        GPTBot                "Claude, for a user"  Claude-User
                     "Claude search"          Claude-SearchBot      "Anthropic training"  ClaudeBot
                     "Perplexity, for a user" Perplexity-User       "Perplexity search"   PerplexityBot
                     "Google"                 Googlebot|Google-InspectionTool|GoogleOther|Google-Extended
                     "Bing"                   bingbot|BingPreview|msnbot
                     "DuckDuckGo"             DuckDuckBot|DuckAssistBot
                     "Apple"                  Applebot
                     "Meta"                   meta-externalagent|facebookexternalhit
                     "Amazon"                 Amazonbot
                     "Common Crawl"           CCBot
                     "ByteDance"              Bytespider
                   matched case-insensitively. Our own checks ("bibleont-check/...") stay counted as checks only.

    python tests/test_activity_engaged.py
"""

import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))

PHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
         "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
DESK = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/141.0 Safari/537.36")
HOST = "bibleontology.org"
UAS = {
    "ChatGPT, for a user": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot",
    "OpenAI search": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot",
    "OpenAI training": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.2; +https://openai.com/gptbot",
    "Claude, for a user": "Claude-User/1.0 (+https://www.anthropic.com)",
    "Claude search": "Claude-SearchBot/1.0 (+https://www.anthropic.com)",
    "Anthropic training": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +https://www.anthropic.com)",
    "Perplexity, for a user": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)",
    "Perplexity search": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
    "Google": "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Bing": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm) Chrome/116.0 Safari/537.36",
    "DuckDuckGo": "DuckDuckBot/1.1; (+http://duckduckgo.com/duckduckbot.html)",
    "Apple": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)",
    "Meta": "meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)",
    "Amazon": "Mozilla/5.0 (compatible; Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot)",
    "Common Crawl": "CCBot/2.0 (https://commoncrawl.org/faq/)",
    "ByteDance": "Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; Bytespider)",
    "other": "python-requests/2.32",
}


def main():
    fails = []

    def check(ok, what):
        if not ok:
            fails.append(what)

    with tempfile.TemporaryDirectory() as tmp:
        import activity as A
        A.store_dir = lambda: Path(tmp)
        a = A.Activity()
        # 1. a reader who taps is engaged, once
        a.record("/api/open", {}, 200, 1, "10.1.1.1", PHONE, "", HOST)
        a.record("/api/engaged", {}, 200, 1, "10.1.1.1", PHONE, "", HOST)
        a.record("/api/engaged", {}, 200, 1, "10.1.1.1", PHONE, "", HOST)
        check(a.c.get("engaged") == 1, f"1: engaged {a.c.get('engaged')}, not 1 (one reader, twice)")
        check(a.c.get("engaged_devices") == {"phone": 1}, f"1: engaged devices {a.c.get('engaged_devices')}")
        # 2. the farm: opens and leaves; engaged without opening is not counted; a bot's engaged is not
        for i in range(5):
            a.record("/api/open", {}, 200, 1, f"10.2.{i}.1", DESK, "", HOST)
        a.record("/api/engaged", {}, 200, 1, "10.9.9.1", DESK, "", HOST)
        a.record("/api/engaged", {}, 200, 1, "10.9.9.2", UAS["Google"], "", HOST)
        check(a.c.get("readers") == 6, f"2: readers {a.c.get('readers')}, not 6 (the farm still opens)")
        check(a.c.get("engaged") == 1, f"2: engaged {a.c.get('engaged')}: counted without /api/open, or a bot")
        pages = a.c.get("pages")
        a.record("/api/open", {}, 200, 1, "10.3.1.1", DESK, "", HOST)
        a.record("/api/engaged", {}, 200, 1, "10.3.1.1", DESK, "", HOST)
        check(a.c.get("engaged") == 2 and a.c.get("engaged_devices") == {"phone": 1, "desktop": 1},
              f"2: a desktop reader who taps: {a.c.get('engaged')} {a.c.get('engaged_devices')}")
        check(a.c.get("pages") == pages, "2: /api/engaged was counted as a page")
        # 3. bots by name
        for name, ua in UAS.items():
            a.record("/e/jesus", {}, 200, 5, "10.5.5.5", ua, "", HOST)
        named = a.c.get("bots_named") or {}
        for name in UAS:
            check(named.get(name) == 1, f"3: {name!r} counted {named.get(name)}")
        check([n for n, _ in A.BOT_NAMES] == [n for n in UAS if n != "other"], "3: BOT_NAMES not in the stated order")
        a.record("/e/jesus", {}, 200, 5, "10.5.5.5", "bibleont-check/1.0", "", HOST)
        check(sum((a.c.get("bots_named") or {}).values()) == len(UAS), "3: our own check was counted as a bot")
        check(a.c.get("readers") == 7, "3: a bot became a reader")
        # 4. kept across a restart within the day; a new day starts at 0
        a._flush_locked()
        b = A.Activity()
        b.record("/api/engaged", {}, 200, 1, "10.1.1.1", PHONE, "", HOST)
        check(b.c.get("engaged") == 2, f"4: after a restart, engaged {b.c.get('engaged')} (the same reader again)")
        check(any(p.name.endswith(".engaged") for p in Path(tmp, "activity").glob(".*")), "4: no .engaged file")
        day = b.day
        b._roll("2099-01-01")
        check(b.c.get("engaged") == 0 and not b.engaged, "4: a new day did not start at 0")
        check(not Path(tmp, "activity", f".{day}.engaged").exists(), "4: the old day's engaged file was kept")
        # 5. what readers did, counted for readers only (2026-11-03: the farm's Gen 1 119 times and 576 "1chr.1.27"
        # searches had filled the lists): a farm client's card, chapter and search are not counted; a reader's
        # actions before their first tap count when they tap; after it, at once
        c5 = A.Activity()
        c5._roll("2099-02-02")
        for i in range(3):                                   # the farm: runs the page, calls the API, never taps
            ip = f"10.7.{i}.1"
            c5.record("/api/open", {}, 200, 1, ip, DESK, "", HOST)
            c5.record("/api/chapter", {"b": ["Gen"], "c": ["1"]}, 200, 5, ip, DESK, "", HOST)
            c5.record("/api/search", {"q": ["1chr.1.27"]}, 200, 5, ip, DESK, "", HOST)
        check(not c5.c.get("chapters") and not c5.c.get("searches"), f"5: the farm's actions counted: {c5.c.get('chapters')} {c5.c.get('searches')}")
        c5.record("/api/open", {}, 200, 1, "10.8.1.1", PHONE, "", HOST)
        c5.record("/api/entity", {"id": ["david"]}, 200, 5, "10.8.1.1", PHONE, "", HOST)   # the card they landed on
        check(not c5.c.get("cards"), "5: a card counted before its reader engaged")
        c5.record("/api/engaged", {}, 200, 1, "10.8.1.1", PHONE, "", HOST)
        check(c5.c.get("cards") == {"david": 1}, f"5: the landing card did not count on the first tap: {c5.c.get('cards')}")
        c5.record("/api/chapter", {"b": ["Ruth"], "c": ["1"]}, 200, 5, "10.8.1.1", PHONE, "", HOST)
        check(c5.c.get("chapters") == {"Ruth 1": 1}, f"5: an engaged reader's chapter: {c5.c.get('chapters')}")
        # the Navigator, its own tab from 2026-11-08: a reader's centring counts, the farm's does not
        c5.record("/api/graph", {"id": ["stones"]}, 200, 5, "10.8.1.1", PHONE, "", HOST)
        c5.record("/api/graph", {"id": ["jacob"]}, 200, 5, "10.7.0.1", DESK, "", HOST)
        check(c5.c.get("navigator") == {"stones": 1}, f"5: the Navigator's views: {c5.c.get('navigator')}")
        for i in range(30):
            c5.record("/api/search", {"q": [f"x{i}"]}, 200, 5, "10.9.9.9", DESK, "", HOST)
        check(len(c5.pending.get(c5._hash("10.9.9.9", DESK), [])) <= A.PENDING_PER, "5: pending grew past its cap")
        # 6. the page counts real input only: a tap, click, key or wheel, never "scroll", which the browser fires as
        # trusted when the page scrolls itself (63 desktop "readers" and no phone on the first night)
        html = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
        m = re.search(r"const evs = \[([^\]]*)\];", html)
        check(m and "'scroll'" not in m.group(1) and "'wheel'" in m.group(1), f"6: the engagement events {m and m.group(1)}")
    for f in fails:
        print("FAIL", f)
    print(f"activity engaged: 6 groups of checks; {len(fails)} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
