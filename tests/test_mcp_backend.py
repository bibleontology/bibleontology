"""The MCP server over the real graph (2026-11-03): the adapter keeps the hop rules, and the site's own limits hold.

    python -X utf8 tests/test_mcp_backend.py

tests/test_mcp.py proves the protocol and its rules against a fake. This proves the adapter (app2/mcp_backend.py)
against the real answers, with the hop rules Doug set on 2026-11-03:
  1. every hop carries a verse, and its target opens (no dead links)
  2. themes are never hops (in_theme), and mined patterns ("Role pattern") never appear
  3. a held question answers like a missing one; the six held questions never open
  4. divine persons exactly as the site shows them: every hop on the God card is one of the card's own relations
  5. Matt 4:4 hops to its quotation of Deut 8:3 and to Luke 4:4, the parallel marked a reading
  6. the temptation: its cast and its quotations are hops, its story echoes are readings, its tellings are moves
  7. /mcp over HTTP: POST answers, a notification is 202, GET is 405, a foreign Origin is 403
Planted: themes let back in as hops must be caught (2), and a hop with no verse must be caught (1).
"""
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402
import mcp as M  # noqa: E402
import mcp_backend as MB  # noqa: E402

S.load()
B = S.mcp_backend()
HELD = ["after-death", "end-times", "hell", "millennium", "rapture", "tithing"]
fails = []


def check(ok, what):
    if not ok:
        fails.append(what)


def fetch(iid, backend=None):
    r = M.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "fetch", "arguments": {"id": iid}}}, backend or B)
    return r["result"]


def hop_faults(sc):
    f = []
    for l in sc.get("links") or []:
        if l["rel"] == "more":
            continue
        if not (l.get("because") or {}).get("ref") or not (l.get("because") or {}).get("url"):
            f.append("no verse: %s -> %s" % (l["rel"], l["id"]))
        if not B.shown(l["id"]):
            f.append("dead: %s" % l["id"])
        if l.get("iri") and "in_theme" in l["iri"]:
            f.append("a theme as a hop: %s" % l["id"])
    return f


CARDS = ["card:event_jesus_temptation", "card:david", "card:moses", "card:god", "card:jesus", "card:the_father",
         "card:holy_ghost", "card:abraham", "verse:Matt.4.4", "verse:John.1.1", "verse:Gen.1.1"]

# 1, 2: every hop has its verse and opens; no theme hop; no pattern
for iid in CARDS:
    res = fetch(iid)
    check(not res.get("isError"), "1: %s did not open" % iid)
    sc = res.get("structuredContent") or {}
    for f in hop_faults(sc):
        check(False, "1/2: %s: %s" % (iid, f))
    check(not any(m["type"] in MB.THEME_TYPES for m in sc.get("map") or []), "2: %s maps a theme relation" % iid)
    it = B.item(iid)
    check(all(r.get("because") for r in it["relations"]), "1: %s keeps a relation with no verse" % iid)

# 3: held questions
for q in HELD:
    res = fetch("question:" + q)
    check(res.get("isError") and res["content"][0]["text"] == fetch("question:no-such-thing")["content"][0]["text"],
          "3: held question %s answered unlike a missing one" % q)
check(not fetch("question:baptism").get("isError"), "3: a shown question did not open")

# 4: the God card's hops are its own relations, as the site shows them
e = S.api_entity(S.load(), {"id": ["god"]})
own = {("card:" + it["other"], it["label"]) for g in e["groups"] for it in g["items"]}
sc = fetch("card:god")["structuredContent"]
extra = [(l["id"], l["rel"]) for l in sc["links"] if l["rel"] != "more" and (l["id"], l["rel"]) not in own]
check(not extra, "4: hops on the God card the site does not show: %r" % extra[:3])

# 5: Matt 4:4
sc = fetch("verse:Matt.4.4")["structuredContent"]
got = {(l["id"], l["certainty"]) for l in sc["links"] if l["rel"] != "more"}
check(("verse:Deut.8.3", "stated") in got, "5: Matt 4:4 does not hop to Deut 8:3: %r" % got)
check(("verse:Luke.4.4", "reading") in got, "5: Matt 4:4's parallel in Luke is not a marked reading: %r" % got)
check([m["rel"] for m in sc["moves"]] == ["prev", "next"], "5: Matt 4:4's moves %r" % sc["moves"])

# 6: the temptation
it = B.item("card:event_jesus_temptation")
ids = {r["id"] for r in it["relations"]}
check("card:the_angels" in ids and "verse:Deut.8.3" in ids, "6: the cast or the quotations are missing")
check(all(r["certainty"] == "reading" for r in it["relations"] if r.get("type") == "re_enacts")
      and any(r.get("type") == "re_enacts" for r in it["relations"]), "6: the story echoes are not marked readings")
check({m["id"] for m in it["moves"]["down"]} >= {"card:tell_matt_4_1_4_11", "card:tell_luke_4_1_4_13"},
      "6: the tellings are not moves down: %r" % it["moves"]["down"])

# 8: the schema as items: every definition a hop points to opens; a relation's domain and range kinds open; no
# invented type ("quotes") reaches an iri; a relation's instances each carry their verse
defs = set()
for iid in CARDS:
    sc = fetch(iid)["structuredContent"]
    for l in sc["links"] + sc["map"]:
        if l.get("definition"):
            defs.add(l["definition"])
            check(l.get("iri") == M.NS + l["definition"].split(":", 1)[1] if "iri" in l else True, "8: iri and definition disagree %r" % l)
        elif l.get("iri"):
            check(False, "8: an iri with no definition: %r" % l)
for dfn in sorted(defs):
    r = fetch(dfn)
    check(not r.get("isError"), "8: %s does not open" % dfn)
    if not r.get("isError"):
        sch = r["structuredContent"]["schema"]
        for k in sch["domain"] + sch["range"]:
            check(B.shown(k), "8: %s's kind %s does not open" % (dfn, k))
        check(all(l["because"].get("ref") for l in r["structuredContent"]["links"] if l["rel"] != "more"),
              "8: %s has an instance with no verse" % dfn)
check(fetch("relation:quotes").get("isError"), "8: an invented relation opened")
check(not fetch("kind:person").get("isError") and not fetch("relation:re_enacts").get("isError"), "8: kind:person or relation:re_enacts")
print("schema items checked:", len(defs))

# 9: the 16 verses the Berean leaves empty: the note, then Young's Literal marked as the later manuscripts' reading;
# never empty, never as the Berean's (Doug, 2026-11-03: "note plus Young's Literal"); and no KJV is loaded at all
for ref in ("Matt.17.21", "Acts.8.37", "Rom.16.24"):
    t = fetch("verse:" + ref)["structuredContent"]["text"]
    check(t.startswith("Not in the Berean text") and "Young's Literal Translation, 1898" in t and len(t) > 120,
          "9: %s answered %r" % (ref, t[:120]))
check("Not in the Berean" not in fetch("verse:Matt.17.20")["structuredContent"]["text"], "9: a full verse got the note")
check(S.load().get("translation", "Berean Standard Bible") != "King James Version (1769)", "9: the KJV is the loaded translation")
kjv_only = "Howbeit this kind goeth not out but by prayer and fasting"
check(all(kjv_only not in t for t in S.load()["verses"].values()), "9: KJV wording is in the loaded verses")

# 9b: the site says the same (Doug, 2026-11-03: "so the site and the MCP say the same thing")
dd = S.load()
lv = S.api_verse(dd, {"ref": ["Matt 17:21"]}).get("later") or {}
check(lv.get("note", "").startswith("Not in the Berean") and "prayer and fasting" in lv.get("text", ""), "9b: api_verse's later %r" % lv)
check(S.api_verse(dd, {"ref": ["Matt 17:20"]}).get("later") is None, "9b: a full verse carries later")
rows = S.api_chapter(dd, {"b": ["Matt"], "c": ["17"]}).get("verses") or S.api_chapter(dd, {"b": ["Matt"], "c": ["17"]}).get("rows") or []
r21 = [r for r in rows if r.get("v") == 21]
check(r21 and (r21[0].get("later") or {}).get("text"), "9b: the chapter's verse 21 carries no later")
page = S.passage_page("Matt.17.21")
html = "".join(x for x in page if isinstance(x, str)) if isinstance(page, tuple) else str(page)
check("Not in the Berean text" in html and "Young&#x27;s Literal" in html or "Young's Literal" in html, "9b: the /p/ page lacks the note")
check(S._marked("Matt", 17, 20, dd["verses"][("Matt", 17, 20)]).find("Not in the Berean") < 0, "9b: a full verse got the note on /p/")
check(not dd["verses"][("Matt", 17, 21)].strip(), "9b: Young's text leaked into the verse text the graph is built from")

# planted: themes let back in as hops, and a hop with no verse
saved = MB.THEME_TYPES
MB.THEME_TYPES = set()
B2 = MB.Backend(S, S.load())
leaked = [l for l in fetch("card:event_jesus_temptation", B2)["structuredContent"]["links"] if "in_theme" in (l.get("iri") or "")]
MB.THEME_TYPES = saved
planted_theme = bool(leaked) or any(r.get("type") == "in_theme" for r in B2.item("card:event_jesus_temptation")["relations"])
planted_verse = bool(hop_faults({"links": [{"rel": "x", "id": "card:david", "because": {}}]}))

# 7: over HTTP
srv = S.ThreadingHTTPServer(("127.0.0.1", 0), S.Handler) if hasattr(S, "ThreadingHTTPServer") else None
if srv is None:
    import http.server
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), S.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = "http://127.0.0.1:%d/mcp" % srv.server_address[1]


def post(body, headers=None):
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


code, raw = post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
check(code == 200 and json.loads(raw)["result"]["protocolVersion"] == "2025-06-18", "7: initialize over HTTP %s" % code)
check(post({"jsonrpc": "2.0", "method": "notifications/initialized"})[0] == 202, "7: a notification is not 202")
check(post({"jsonrpc": "2.0", "id": 1, "method": "ping"}, {"Origin": "https://evil.example"})[0] == 403, "7: a foreign Origin passed")
try:
    urllib.request.urlopen(url, timeout=30)
    check(False, "7: GET /mcp answered")
except urllib.error.HTTPError as e:
    check(e.code == 405, "7: GET /mcp gave %s, not 405" % e.code)
# a person's browser gets the how-to page the flagship article promised; an event-stream probe still gets 405
with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "text/html,application/xhtml+xml"}), timeout=30) as r:
    page = r.read().decode("utf-8")
    check(r.status == 200 and "https://bibleontology.org/mcp" in page and "custom connector" in page, "7: no how-to page at /mcp")
try:
    urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "text/event-stream"}), timeout=30)
    check(False, "7: an event-stream GET was answered")
except urllib.error.HTTPError as e:
    check(e.code == 405, "7: an event-stream GET gave %s" % e.code)
srv.shutdown()

for f in fails:
    print("FAIL", f)
print("mcp over the graph: 9 groups; planted faults caught: %d of 2; %d failures"
      % (int(planted_theme) + int(planted_verse), len(fails)))
sys.exit(1 if fails or not (planted_theme and planted_verse) else 0)
