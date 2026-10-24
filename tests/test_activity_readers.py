"""Readers on /ops are browsers that ran the page (2026-10-22).

From 21 October a farm of desktop "browsers" loaded one page each and never ran
its script, and /ops counted them as visitors. A reader is now a visitor whose
page sent /api/open; where readers came from rides on that same request, since
the page that carried the Referer header is mostly answered from Cloudflare's
cache. This checks, on the real counter with a scratch folder:
  - a page load with no /api/open is a visitor, never a reader;
  - /api/open makes a reader, counted once, and only readers' devices count;
  - the site a reader came from is counted; our own host and junk are not;
  - /ops shows readers first, and a dash for days before readers were counted.
Planted: a farm client that sends /api/open must be counted (the signal is
honoured, not guessed at), and a day with no reader count must not show 0.

    python tests/test_activity_readers.py
"""
import os
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


def main():
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["BIBLEONT_FEEDBACK"] = tmp
        import activity as A
        a = A.Activity()
        a.record("/", {}, 200, 5, "10.1.1.1", PHONE, "", HOST)
        a.record("/api/open", {"r": ["www.google.com"]}, 200, 1, "10.1.1.1", PHONE, "", HOST)
        a.record("/api/open", {"r": ["www.google.com"]}, 200, 1, "10.1.1.1", PHONE, "", HOST)
        for i in range(5):                               # the farm: one page each, no script
            a.record(f"/e/r{i}", {}, 200, 5, f"10.2.{i}.1", DESK, "", HOST)
        a.record("/api/open", {"r": ["www.bibleontology.org"]}, 200, 1, "10.3.1.1", PHONE, "", HOST)
        a.record("/api/open", {"r": ["<script>"]}, 200, 1, "10.4.1.1", DESK, "", HOST)
        c = a.c
        if c.get("readers") != 3:
            fails.append(f"readers {c.get('readers')}, not 3 (one reader twice, two more)")
        if c.get("visitors") != 8:
            fails.append(f"visitors {c.get('visitors')}, not 8")
        if c.get("devices", {}).get("desktop", 0) != 1:
            fails.append(f"desktop devices {c.get('devices')}: the farm's page loads were counted as readers")
        if c.get("referrers") != {"www.google.com": 1}:
            fails.append(f"referrers {c.get('referrers')}: want www.google.com once (once per reader a day), "
                         "never our own host or junk")
        # PLANTED: a client that does send /api/open is a reader, whatever it is
        a.record("/api/open", {}, 200, 1, "10.2.0.1", DESK, "", HOST)
        planted = int(a.c.get("readers") == 4)
        # A READER BACK FROM ANOTHER SITE LATER IN THE DAY is counted from it
        # (Doug, 2026-10-22: "I redirected from google and bing and neither
        # bumped the count" -- his phone was already a reader that day)
        a.record("/api/open", {"r": ["www.bing.com"]}, 200, 1, "10.3.1.1", PHONE, "", HOST)
        if a.c["referrers"].get("www.bing.com") != 1:
            fails.append(f"referrers {a.c['referrers']}: a reader returning from Bing was not counted")
        # PLANTED: one client repeating /api/open cannot write the referrer line
        # (the security seat, 2026-10-22): a site once per reader, at most three
        # sites per reader a day; nor can a port or non-ASCII digits
        for _ in range(50):
            a.record("/api/open", {"r": ["casino.example"]}, 200, 1, "10.1.1.1", PHONE, "", HOST)
        for i in range(10):
            a.record("/api/open", {"r": [f"spam{i}.example"]}, 200, 1, "10.1.1.1", PHONE, "", HOST)
        a.record("/api/open", {"r": ["x.example:١٢"]}, 200, 1, "10.5.1.1", PHONE, "", HOST)
        spam = sum(v for k, v in a.c["referrers"].items() if k.startswith("spam"))
        if a.c["referrers"].get("casino.example") != 1 or spam > 1 or any("١" in k for k in a.c["referrers"]):
            fails.append(f"referrers {a.c['referrers']}: one client wrote more than three sites, "
                         "a site more than once, or a malformed name")
        else:
            planted += 1
        if a._blank().get("readers") != 0:
            fails.append("a new day does not start at 0 readers (a farm-only day would show a dash)")
        # the report's alerts: a farm of browsers that never run the page
        sys.path.insert(0, str(ROOT / "tools"))
        import ops_report as R
        farm = {"day": "2026-10-22", "visitors": 8611, "readers": 12, "requests_people": 8709,
                "requests_bots": 2435, "status": {}, "referrers": {}}
        if not any("automated browsers" in x for x in R.attention({"days": [farm, {"day": "2026-10-21"}]})):
            fails.append("ops_report raises no alert for 8,599 browser-like visitors that never ran the page")
        # /ops: readers first, a dash before they were counted
        import server as S
        if not {"/api/open", "/api/seen"} <= S.NOT_KEPT:
            fails.append("the counting signals are kept in the answer cache")
        page = S.ops_page({"days": [{"day": "2026-10-22", **a.c}, {"day": "2026-10-20", "visitors": 207,
                                                                     "pages": 296, "requests_bots": 9}]})
        if f"{a.c['readers']} readers</b>" not in page:
            fails.append("/ops does not lead with the day's readers")
        row20 = page[page.find("<td>2026-10-20</td>"):][:120]
        if "<b>—</b>" not in row20:
            fails.append(f"a day before readers were counted does not show a dash: {row20!r}")
        else:
            planted += 1
    if planted != 3:
        fails.append(f"planted faults caught: {planted} of 3")
    print(f"readers on /ops: 3 readers among 8 visitors, the farm kept out of devices and referrers, "
          f"a site once per reader, three at most; planted faults caught: {planted} of 3; {len(fails)} failures")
    for f in fails:
        print("FAIL " + f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
