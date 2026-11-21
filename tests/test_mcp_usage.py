"""The MCP's use counter (app2/mcp_usage.py; plan 8.7d, 2026-11-12): it counts what it says, and keeps no person.

Against a temporary folder, with made-up calls, no graph needed:
  1. initialize counts the client's own name and protocol; the User-Agent counts only its product name
  2. THE FOLLOW RATE: a fetch for an id an earlier answer in the session offered is followed, and a walk lengthens;
     one for an id never offered is fresh; a cursor page is followed; another client's offer does not count
  3. a search with no results keeps its text (cut to 100); a missing id is kept; an error by kind
  4. NO PERSON: the day's file holds no address, no full User-Agent, no session hash and no key (a planted address
     caught)
  5. searches with no results go after 90 days, and a day inside 90 keeps them (planted)
  6. a session back after the idle gap is a new one; counting never raises on junk
  7. /ops renders the section with an assistant's search text escaped

Run: python tests/test_mcp_usage.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import mcp_usage as U  # noqa: E402

fails, plants = [], 0


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print("FAIL", msg)


IP, IP2 = "203.0.113.77", "198.51.100.9"
UA = "claude-user/1.0 (secret-machine-42)"
UA2 = "openai-mcp/2.1"


def call(tool, args, structured=None, error=None):
    msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": args}}
    if error:     # the server's own error shape (app2/mcp.py _tool_error): a code, and a sentence
        res = {"content": [{"type": "text", "text": "Nothing is published under that id."}],
               "structuredContent": {"error": error, "message": "..."}, "isError": True}
    else:
        res = {"content": [], "structuredContent": structured or {}, "isError": False}
    return msg, {"jsonrpc": "2.0", "id": 1, "result": res}


tmp = Path(tempfile.mkdtemp())
u = U.Usage(tmp, flusher=False)
now = [1_000_000.0]


def rec(msg, out, ip=IP, ua=UA, ms=12.0, size=900):
    with u.lock:
        u._record(msg, out, ip, ua, ms, size, now[0])


# ---- 1. clients
rec({"jsonrpc": "2.0", "id": 0, "method": "initialize",
     "params": {"protocolVersion": "2026-07-28", "clientInfo": {"name": "Claude Desktop", "version": "9"}}},
    {"jsonrpc": "2.0", "id": 0, "result": {}})
rec({"jsonrpc": "2.0", "method": "notifications/initialized"}, None)
c = u.c
check(c["init_clients"] == {"Claude": 1}, f"clientInfo counted as {c['init_clients']}")
check(c["protocols"] == {"2026-07-28": 1}, f"protocol counted as {c['protocols']}")
check(c["clients"] == {"claude-user": 1}, f"the User-Agent counted as {c['clients']}")
check(c["calls"] == 1, f"a notification counted as a call ({c['calls']})")

# ---- 2. the follow rate
rec(*call("search", {"query": "temptation"}, {"results": [{"id": "card:event_jesus_temptation",
                                                           "links": [{"id": "verse:Matt.4.1"}]}]}))
rec(*call("fetch", {"id": "card:event_jesus_temptation"},
          {"links": [{"id": "verse:Matt.4.4"}], "moves": [{"id": "verse:Matt.4.2"}],
           "map": [{"get": {"tool": "get_relations", "arguments": {"id": "card:event_jesus_temptation",
                                                                    "kind": "quotes"}}}]}))
rec(*call("get_verse", {"ref": "Matt 4:4"}, {"links": [{"id": "verse:Deut.8.3"}]}))
rec(*call("get_relations", {"id": "card:event_jesus_temptation", "kind": "quotes"}, {"relations": []}))
rec(*call("get_relations", {"id": "card:x", "cursor": "abc"}, {"relations": []}))
rec(*call("fetch", {"id": "card:david"}, {"links": []}))
rec(*call("fetch", {"id": "verse:Deut.8.3"}, {}), ip=IP2, ua=UA2)       # offered to the other session only
check(c["followed"] == 4, f"followed {c['followed']}, wanted 4 (search hit, verse link, map call, cursor)")
check(c["fresh"] == 2, f"fresh {c['fresh']}, wanted 2 (card:david, and another client's offer)")
check(c["chain_max"] == 4, f"longest walk {c['chain_max']}, wanted 4")
check(c["sessions"] == 2, f"sessions {c['sessions']}, wanted 2")
check(c["args"].get("get_relations.kind") == 1 and c["args"].get("get_relations.cursor") == 1,
      f"arguments by name: {c['args']}")

# ---- 3. what was not found
rec(*call("search", {"query": "x" * 300}, {"results": []}))
rec(*call("search", {"query": "Melchizedek's bread"}, {"results": []}))
rec(*call("fetch", {"id": "card:eliphaz"}, error="not_found"))
rec(*call("get_verse", {"ref": "Zzz 1:1"}, error="invalid_reference"))
check(c["no_results"].get("x" * 100) == 1 and c["no_results"].get("Melchizedek's bread") == 1,
      f"searches with no results: {list(c['no_results'])}")
check(c["missing_ids"] == {"card:eliphaz": 1}, f"missing ids: {c['missing_ids']}")
check(c["errors"].get("invalid_reference") == 1, f"errors: {c['errors']}")

# ---- 4. no person
with u.lock:
    u._flush_locked()
text = (tmp / f"{u.day}.json").read_text(encoding="utf-8")


def person_faults(t):
    f = [w for w in (IP, IP2, "203.0.113", "secret-machine-42", "claude-user/1.0", UA2) if w in t]
    f += ["the day's key"] * (u.key.hex() in t)
    f += ["a session hash" for h in u.sessions if h.hex() in t]
    return f


check(not person_faults(text), f"the day's file keeps a person: {person_faults(text)}")
check(not list(tmp.glob(".*")), f"files beside the day's: {[p.name for p in tmp.glob('.*')]}")
plants += 1
check(person_faults(text.replace('"calls"', f'"{IP}": 1, "calls"')), "planted: an address in the file not caught")

# ---- 5. 90 days
old = tmp / "2026-01-01.json"
old.write_text(json.dumps({"calls": 3, "no_results": {"a question": 1}}), encoding="utf-8")
recent = tmp / f"{u.day[:8]}01.json"
if recent.name != f"{u.day}.json":
    recent.write_text(json.dumps({"calls": 1, "no_results": {"kept": 1}}), encoding="utf-8")
u._prune_no_results(u.day)
check(json.loads(old.read_text(encoding="utf-8")).get("no_results") == {}, "a search older than 90 days kept")
check(json.loads(old.read_text(encoding="utf-8")).get("calls") == 3, "the old day's counts lost with its searches")
plants += 1
if recent.name != f"{u.day}.json":
    check(json.loads(recent.read_text(encoding="utf-8")).get("no_results") == {"kept": 1},
          "planted: a search inside 90 days removed")

# ---- 6. idle, and junk
before = c["sessions"]
now[0] += U.IDLE + 1
rec(*call("fetch", {"id": "verse:Matt.4.4"}, {}))
check(c["sessions"] == before + 1, "a session back after the idle gap counted as the same")
check(c["fresh"] == 3, "an id offered before the idle gap counted as followed")
for junk in (None, [], "x", {"method": 5}, {"method": "tools/call", "params": "x"}):
    try:
        u.record(junk, {"nonsense": True}, IP, UA, 1, 1)
    except Exception as ex:  # noqa: BLE001
        check(False, f"record raised on {junk!r}: {ex}")
hist = u._hist_now()
check(sum(hist.values()) == c["sessions"], f"sessions {c['sessions']} but the histogram holds {sum(hist.values())}")

# ---- 7. /ops
import server as S  # noqa: E402
u.c["no_results"]["<script>alert(1)</script>"] = 1
html = S.ops_mcp_section(u.report(3), lambda counter, n=15: "".join(
    f"<tr><td>{S._esc(str(k))}</td><td>{v}</td></tr>" for k, v in (counter or {}).items()))
check("<script>alert" not in html and "&lt;script&gt;" in html, "an assistant's search text not escaped on /ops")
check("followed a link" in html and "%" in html, "/ops does not show the follow rate")

print(f"MCP use counter: 7 classes checked; {plants} planted faults; {len(fails)} failures")
sys.exit(1 if fails else 0)
