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
# From 2026-11-12 an error echoes its id and searches the id's words (errors that name the next call), so two
# different ids answer differently by their words alone. The test is sharper for it: a held question and an id that
# never existed WITH THE SAME WORDS (a theme of that name) must answer identically, apart from the id itself, so
# nothing in the answer depends on the question being held; and no suggestion is anything the site holds back.
compared = 0
for q in HELD:
    res = fetch("question:" + q)
    twin_id = "theme:" + q.replace("-", "_")
    twin = fetch(twin_id)
    if not twin.get("isError"):
        continue                                     # a real theme of that name: no twin to compare with
    compared += 1
    same = json.dumps(res).replace("question:" + q, "<id>") == json.dumps(twin).replace(twin_id, "<id>")
    check(res.get("isError") and same, "3: held question %s answered unlike a missing one with its words" % q)
    for s_ in (res.get("structuredContent") or {}).get("suggestions") or []:
        check(B.shown(s_["id"]), "3: held question %s suggests %s, which the site holds back" % (q, s_["id"]))
check(compared >= len(HELD) // 2, "3: only %d of %d held questions had a twin to compare: the check proves nothing"
      % (compared, len(HELD)))
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
# from 2026-11-15 (P-2026-11-12-3) a verse moves up to the passage or event its words sit in, and to its speaker:
# Jesus answers the devil, told in the event of the temptation; never into a story template's stage
mv = {m["rel"]: m for m in sc["moves"]}
# prev and next are there; a speaker move may follow them (the MCP's own order), and does from 2026-11-16, when the
# speaker pass gave Matt 4:4's run its speaker
check({"prev", "next"} <= {m["rel"] for m in sc["moves"]}, "5: Matt 4:4's moves %r" % sc["moves"])
check(mv.get("up", {}).get("id") == "card:event_jesus_temptation", "5: Matt 4:4 does not move up to the temptation: %r"
      % mv.get("up"))
check(not any("stage_" in m["id"] or "rcell_" in m["id"] for m in sc["moves"]), "5: a move into a pattern: %r" % sc["moves"])

# 5b: a verse names its speaker (P-2026-11-12-3; the probe of 2026-11-12: 0 of 15), and a speech its speaker
sc = fetch("verse:Job.4.7")["structuredContent"]
check("Spoken by Eliphaz" in sc.get("text", ""), "5b: Job 4:7 does not name Eliphaz: %r" % sc.get("text", "")[-200:])
check(any(m["rel"] == "speaker" and m["id"] == "card:eliphaz_the_temanite" for m in sc["moves"]),
      "5b: Job 4:7 has no speaker move: %r" % sc["moves"])
check(any(l.get("voice") == "the words of Eliphaz" for l in sc["links"]), "5b: Job 4:7's links carry no voice")
sc = fetch("card:job_4_2_21")["structuredContent"]
check(any(m["rel"] == "speaker" and m["id"] == "card:eliphaz_the_temanite" for m in sc["moves"]),
      "5b: the first speech of Eliphaz does not lead to Eliphaz: %r" % sc["moves"])
sc = fetch("verse:Job.42.7")["structuredContent"]
check("Spoken by" in sc.get("text", "") or "Speaking in this verse" in sc.get("text", ""), "5b: Job 42:7 names no speaker")
# a speech whose speaker is not recorded says so, never reads as the narrator's (Doug, 2026-11-15: no overclaiming)
sc = fetch("verse:Matt.5.44")["structuredContent"]
# since the divine sheet (2026-11-16) it is named as a reading, marked as one: either is no narrator
check("the graph does not record who speaks them" in sc.get("text", "") or "as a reading" in sc.get("text", ""),
      "5b: Matt 5:44 reads as the narrator's: %r" % sc.get("text", "")[-200:])
# a sign is told by the hand, not the mouth: never "Spoken by Aaron" at Exod 7:19, the LORD's words to Moses
check("Spoken by Aaron" not in fetch("verse:Exod.7.19")["structuredContent"].get("text", ""),
      "5b: Exod 7:19 credits Aaron with the LORD's words")
# never a speaker the annotation carried in from a quotation's head: Paul speaks Acts 26:8, not Agrippa
sc = fetch("verse:Acts.26.8")["structuredContent"]
said_ = " ".join(s for s in sc.get("text", "").split("\n")[-1].split(". ") if s.startswith(("Spoken by", "Speaking in")))
check("Agrippa" not in said_, "5b: Acts 26:8 credits Agrippa: %r" % said_)

# 5d: the faults Doug's self-test in Claude showed (2026-11-15). A quotation is a span at both ends (Acts 8:32-33 quotes
# Isa 53:7-8, not "Acts 8:33 quotes 53:7"); a quotation into a chapter numbered differently is not moved by one (Matt
# 4:15-16 quotes Isa 9:1-2, never 9:3); a word states its whole count; a saying rests on its own verse (Job 15:25, not
# the speech's introduction at 15:1)
qt = lambda iid: [l["title"] for l in fetch(iid)["structuredContent"]["links"]  # noqa: E731
                  if (l.get("iri") or "").endswith("/quotes")]
check("Isa 53:7–8" in qt("verse:Acts.8.32"), "5d: Acts 8:32 does not quote Isa 53:7-8: %r" % qt("verse:Acts.8.32"))
check("Isa 9:3" not in qt("verse:Matt.4.15") and "Isa 9:1–2" in qt("verse:Matt.4.15"),
      "5d: Matt 4:15's quotation: %r" % qt("verse:Matt.4.15"))
check("Used in 106 verses" in fetch("word:G26")["structuredContent"].get("text", ""), "5d: G26 states no whole count")
el = B.item("card:eliphaz_the_temanite")
check(not [r for r in el["relations"] if r["rel"] == "told" and r["because"]["ref"] == "Job 15:1"],
      "5d: a saying of Eliphaz rests on Job 15:1")

# 5c: search passes word and question hits through (the probe: "faith without works" gave 0)
got = [h["id"] for h in B.search("faith without works", 5)]
check("question:faith-and-works" in got and "word:G4102" in got, "5c: faith without works: %r" % got)
# a transliteration needs the full STEP lexicon, which the public copy lacks until `tools/fetch_lexicon.py` adds it
# (the export gate, 2026-11-21: "agape" found nothing there, as the runbook says of the lexicon's other tests)
if (ROOT / "docs" / "review").exists():    # not the public copy (a worktree finds the lexicon in the main checkout)
    check([h["id"] for h in B.search("agape", 5)] == ["word:G26"], "5c: agape: %r" % B.search("agape", 5))
else:
    print("5c: agape skipped: no full STEP lexicon (python tools/fetch_lexicon.py)")
# 5c': no card for the phrase, so the cards for its words (P-2026-11-16-3 (1): "temple end times" gave only Greek word
# entries, "temple of God church body" nothing at all); a name searched first
got = [h["id"] for h in B.search("temple end times", 10)]
check("card:temple" in got and "theme:temple_presence" in got, "5c': temple end times: %r" % got)
got = [h["id"] for h in B.search("temple of God church body", 10)]
check("card:temple" in got and "theme:church" in got, "5c': temple of God church body: %r" % got)
got = [h["id"] for h in B.search("who killed Goliath", 10)]
check("card:goliath" in got and got.index("card:goliath") < min([got.index(i) for i in ("card:die", "card:killing") if i in got]
                                                               or [99]), "5c': who killed Goliath: %r" % got)

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
# relation:quotes was the invented one until 1.5.0 published it (plan 8.7c); parallel_to stays invented
check(fetch("relation:parallel_to").get("isError"), "8: an invented relation opened")
# THE VERSE HOPS NAME PUBLISHED TERMS (plan 8.7c): each of the five opens with examples, and a word match is never
# sent as stated -- the old "quotes or echoes" hop was the match, about 4 in 8 real, marked stated
VERSE_TERMS = ("quotes", "points_to", "says_the_same_as", "alludes_to", "echoes")
for k in VERSE_TERMS:
    r = fetch("relation:" + k)
    check(not r.get("isError") and r["structuredContent"]["links"], "8: relation:%s does not open with examples" % k)


def verse_faults(item):
    f = []
    for l in item.get("relations") or []:
        if l["id"].startswith("verse:") and l.get("type") not in VERSE_TERMS:
            f.append("a verse hop with no published term: %r" % l["rel"])
        if l.get("type") == "echoes" and (l.get("certainty") != "match" or "real" not in l["rel"]):
            f.append("a word match without its grade or marked %s" % l.get("certainty"))
    return f


for vk in ("Matt.4.4", "Isa.53.7", "Deut.8.3"):
    check(not verse_faults(B._verse(vk)), "8: %s: %s" % (vk, verse_faults(B._verse(vk))))
bad = B._verse("Matt.4.4")
bad["relations"] = [dict(l, certainty="stated") if l.get("type") == "echoes" else l for l in bad["relations"]]
planted_match = bool(verse_faults(bad))
check(planted_match, "planted: a word match marked stated not caught")
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
# a crawler's GET ("*/*", as Google's inspection tool sends) gets the page, never cached (Cloudflare ignores Accept)
with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "*/*"}), timeout=30) as r:
    check(r.status == 200 and r.headers.get("Cache-Control") == "no-store", "7: a */* GET got %s, %s" % (r.status, r.headers.get("Cache-Control")))
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
print("mcp over the graph: 9 groups; planted faults caught: %d of 3; %d failures"
      % (int(planted_theme) + int(planted_verse) + int(planted_match), len(fails)))
sys.exit(1 if fails or not (planted_theme and planted_verse and planted_match) else 0)
