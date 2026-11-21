"""The MCP server's core: acceptance tests (2026-11-03). Written before the code.

    python3 -X utf8 tests/test_mcp.py

A read-only Model Context Protocol server over the public graph: JSON-RPC 2.0, stateless Streamable HTTP. This module is
the whole protocol and every rule; the web server only hands it the parsed request body and a backend, and sends back
what it returns (HTTP 202 with no body when it returns None).

THE INTERFACE (app2/mcp.py, Python 3.9, standard library only):
  PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26")     newest first (2026-07-28 removed 2026-11-15:
                     the stateless revision, never implemented here; offering it broke Claude's directory check)
  TOOLS              the six tool names: "start", "search", "fetch", "get_relations", "get_verse", "get_word"
  NS = "https://bibleontology.org/ns/relation/"
  MAX_LINKS = 12; MAX_RELATIONS = 25; MAX_BYTES = 60000; MAX_QUERY = 200
  handle(msg, backend) -> dict | None
      msg is the parsed JSON body (any JSON value). A notification (an object with "method" and no "id") -> None.
      A batch (a list) -> {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, ...}} (not supported).
      Not an object, or no "method" string, or jsonrpc != "2.0" -> error -32600, id echoed when present.
      Unknown method -> -32601. Bad params -> -32602. Never raises: anything unexpected -> -32603, with no detail
      from the exception (no paths, no stack) in the message.
  Methods:
      initialize        result {"protocolVersion", "capabilities": {"tools": {}, "resources": {}}, "serverInfo":
                        {"name": "bible-ontology", "version": backend.data_version}, "instructions": INSTRUCTIONS}.
                        protocolVersion is the client's params.protocolVersion if it is in PROTOCOL_VERSIONS, else
                        PROTOCOL_VERSIONS[0].
      ping              result {}
      tools/list        result {"tools": [...]}: each {"name", "title", "description", "inputSchema" (a JSON Schema
                        object with "type": "object", "properties", "required", "additionalProperties": False),
                        "annotations": {"title", "readOnlyHint": True, "destructiveHint": False, "idempotentHint":
                        True, "openWorldHint": False}}. Exactly the six TOOLS.
      tools/call        params {"name", "arguments"}. Result {"content": [...], "structuredContent": {...},
                        "isError": False}. content[0] is {"type": "text", "text": <the structuredContent as JSON>},
                        then one {"type": "resource_link", "uri", "name", "description"} per link (see LINKS).
                        A bad argument or an unknown/hidden id -> a result with "isError": True and one text item
                        saying what was wrong (never which ids are held). An unknown tool name -> -32602.
      resources/list    result {"resources": [...]}: "about", "method", "licensing", "version", each {"uri":
                        "bibleontology://<name>", "name", "mimeType": "text/markdown"}.
      resources/read    params {"uri"} -> {"contents": [{"uri", "mimeType", "text": backend.resource(name)}]};
                        an unknown uri -> -32602.
  IDS (checked before any lookup): card:<a-z0-9_ 1-80>, theme:<same>, question:<same>, verse:<Book>.<c>.<v> with a
      book from the site's 66 codes (Gen ... Rev) and numbers 1-999, word:<H or G><1-4 digits><optional a-z>.
  TOOLS' ARGUMENTS:
      search {"query": 1-MAX_QUERY chars after stripping}     -> structuredContent {"results": [{"id", "title", "url",
                                                                 "links": first 3 LINKS}]}, at most 10
      fetch {"id"}                                             -> {"id", "title", "url", "text", "verses", "links",
                                                                 "sources", "credit", "data_version"}
      get_relations {"id", "kind"? , "cursor"?}                -> {"id", "relations": [...MAX_RELATIONS at most],
                                                                 "next_cursor": str | None, "sources", "credit",
                                                                 "data_version"}; strongest first; kind filters on the relation's type
      get_verse {"ref": "Matt.4.4" or "Matt 4:4"}              -> fetch of "verse:Matt.4.4"
      get_word {"strong": "H8322" or "G26"}                    -> fetch of "word:H8322"
  LINKS: from the item's relations, those whose target backend.shown(id) is true, strongest first, MAX_LINKS at most,
      each {"rel", "id", "title", "url", "because": {"ref", "url"}}; if more remain, then one {"rel": "more", "cursor"}
      that get_relations accepts. A relation's id is its target's id.
  EVERY tool answer carries "sources" (backend.sources, as given), "credit" (CREDIT) and "data_version".
  BYTES: a structuredContent whose JSON is over MAX_BYTES has its "text" cut (and "verses" trimmed) until it fits,
      with "truncated": True.

THE BACKEND (the tests' fake; the web server's adapter calls the site's own functions):
  data_version: str; sources: list of {"name", "licence", "url"}
  search(query, limit) -> [{"id", "title", "url"}]          the site's search, strongest first
  item(id) -> dict | None   {"id", "title", "url", "text", "verses": [{"ref", "text", "url"}], "shown": bool,
                             "relations": [{"rel", "id", "title", "url", "because": {"ref", "url"}, "strength": n}]}
  shown(id) -> bool         what the site shows; a held card is False
  resource(name) -> str
  start() -> {"text": str, "links": [{"rel", "id", "title", "url"}]}            the front door's entries
  item(id)["moves"] -> {"up": {"id","title","url"} | None, "down": [...], "prev": ..., "next": ..., "speaker": ...}
  each relation also has "type" (its vocabulary type), "certainty" ("stated" | "implied" | "reading"), "voice"

V1'S HYPERMEDIA (DESIGN: "Hypermedia in full"), added 2026-11-03:
  start {} (no arguments)  -> {"text", "links" (shown only), "sources", "credit", "data_version"}: the front door
  every link from a relation also carries "iri" (NS + type), "certainty" and "voice" (as given, None allowed)
  fetch also returns "moves": a list of {"rel": "up"|"down"|"prev"|"next"|"speaker", "id", "title", "url"} in that
      order, only well-formed ids the site shows, "down" at most MAX_LINKS; each is also a resource_link item
  fetch also returns "map": one entry per relation type among the shown relations, most first:
      {"type", "rel", "iri", "count", "readings": how many have certainty "reading",
       "get": {"tool": "get_relations", "arguments": {"id": <this id>, "kind": <type>}}}
  INSTRUCTIONS also says to begin with start when there is no query, and that each rel's iri defines it
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
try:
    import mcp as M  # noqa: E402
except ImportError as e:
    print("FAIL app2/mcp.py does not import:", e)
    sys.exit(1)

fails = []


def check(ok, what):
    if not ok:
        fails.append(what)


def rel(n, target, strength):
    return {"rel": "quotes" if n % 2 else "tempted by", "type": "quotes" if n % 2 else "tempted_by",
            "certainty": "reading" if n % 3 == 0 else "stated", "voice": "the words of Satan" if n == 2 else None, "id": target, "title": target.split(":")[1], "url": "https://x/e/" + target,
            "because": {"ref": "Matt 4:%d" % (n + 1), "url": "https://x/v/Matt.4.%d" % (n + 1)}, "strength": strength}


class Fake:
    data_version = "1.3.0+2026-11-03"
    sources = [{"name": "MACULA", "licence": "CC BY 4.0", "url": "https://github.com/Clear-Bible/macula-greek"}]

    def __init__(self):
        self.calls = []
        many = [rel(i, "card:c%d" % i, 100 - i) for i in range(30)]
        self.items = {
            "card:temptation": {"id": "card:temptation", "title": "The temptation", "url": "https://x/e/temptation",
                                "text": "Jesus in the wilderness.", "verses": [{"ref": "Matt 4:1", "text": "Then Jesus...", "url": "https://x/v/Matt.4.1"}],
                                "shown": True, "relations": many + [rel(99, "question:held_one", 1000)],
                                "moves": {"up": {"id": "card:ministry", "title": "The ministry", "url": "https://x/e/ministry"},
                                          "down": [{"id": "verse:Matt.4.4", "title": "Matthew 4:4", "url": "https://x/v/Matt.4.4"}],
                                          "prev": {"id": "card:baptism", "title": "The baptism", "url": "https://x/e/baptism"},
                                          "next": {"id": "question:held_one", "title": "held", "url": "u"},
                                          "speaker": None}},
            "verse:Matt.4.4": {"id": "verse:Matt.4.4", "title": "Matthew 4:4", "url": "https://x/v/Matt.4.4", "text": "It is written",
                               "verses": [], "shown": True, "relations": []},
            "word:H8322": {"id": "word:H8322", "title": "H8322", "url": "https://x/w/H8322", "text": "x", "verses": [], "shown": True, "relations": []},
            "question:held_one": {"id": "question:held_one", "title": "held", "url": "https://x/q/held_one", "text": "secret",
                                  "verses": [], "shown": False, "relations": []},
            "card:big": {"id": "card:big", "title": "big", "url": "https://x/e/big", "text": "w" * 200000,
                         "verses": [{"ref": "Gen 1:%d" % i, "text": "v" * 500, "url": "u"} for i in range(1, 60)], "shown": True, "relations": []},
        }
        for k in ("card:ministry", "card:baptism"):
            self.items[k] = {"id": k, "title": k, "url": "u", "text": "t", "verses": [], "shown": True, "relations": []}
        for i in range(30):
            self.items["card:c%d" % i] = {"id": "card:c%d" % i, "title": "c%d" % i, "url": "u", "text": "t", "verses": [], "shown": True, "relations": []}

    def search(self, query, limit):
        self.calls.append(("search", query))
        return [{"id": "card:temptation", "title": "The temptation", "url": "https://x/e/temptation"}] * 15

    def item(self, id):
        self.calls.append(("item", id))
        return self.items.get(id)

    def shown(self, id):
        it = self.items.get(id)
        return bool(it and it["shown"])

    def resource(self, name):
        return "# " + name

    def start(self):
        return {"text": "A graph of what the Bible says.", "links": [
            {"rel": "book", "id": "card:temptation", "title": "t", "url": "https://x/e/temptation"},
            {"rel": "theme", "id": "question:held_one", "title": "held", "url": "u"}]}


B = Fake()


def call(method, params=None, id=1):
    msg = {"jsonrpc": "2.0", "id": id, "method": method}
    if params is not None:
        msg["params"] = params
    return M.handle(msg, B)


def tool(name, args):
    return call("tools/call", {"name": name, "arguments": args})


# 1. the protocol
r = call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
res = r.get("result") or {}
check(r.get("jsonrpc") == "2.0" and r.get("id") == 1, "1: initialize envelope %r" % r)
check(res.get("protocolVersion") == "2025-06-18", "1: a supported client version was not echoed")
check(call("initialize", {"protocolVersion": "1999-01-01"})["result"]["protocolVersion"] == M.PROTOCOL_VERSIONS[0], "1: unknown version")
# CLAUDE'S DIRECTORY CHECK (2026-11-15): it asks for 2025-11-25 and must get 2025-11-25 back, never a revision this
# server does not implement; a stateless-revision request (server/discover, or _meta asking 2026-07-28) gets the
# protocol's own unsupported-version error listing what is spoken, so the client falls back to initialize
check(call("initialize", {"protocolVersion": "2025-11-25"})["result"]["protocolVersion"] == "2025-11-25",
      "1: Claude's 2025-11-25 was not echoed")
check("2026-07-28" not in M.PROTOCOL_VERSIONS, "1: the stateless revision is offered but not implemented")
r = call("server/discover", {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}})
check(r.get("error", {}).get("code") == -32022 and "2025-11-25" in r["error"].get("data", {}).get("supported", []),
      "1: server/discover is not answered with unsupported-version: %r" % r)
r = call("tools/list", {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}})
check(r.get("error", {}).get("code") == -32022, "1: a 2026-07-28 request was served as if understood: %r" % str(r)[:120])
check(call("resources/templates/list", {}).get("result") == {"resourceTemplates": []}, "1: resource templates")
check(set(res.get("capabilities", {})) == {"tools", "resources"}, "1: capabilities %r" % res.get("capabilities"))
check(res.get("serverInfo") == {"name": "bible-ontology", "version": B.data_version}, "1: serverInfo")
check(isinstance(res.get("instructions"), str) and "links" in res["instructions"] and "fetch" in res["instructions"]
      and "cite" in res["instructions"].lower(), "1: instructions do not explain following links and citing")
check(call("ping") == {"jsonrpc": "2.0", "id": 1, "result": {}}, "1: ping")
check(M.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, B) is None, "1: a notification was answered")
check(M.handle([{"jsonrpc": "2.0", "id": 1, "method": "ping"}], B)["error"]["code"] == -32600, "1: a batch was accepted")
for bad in ("x", 5, None, {"id": 3}, {"jsonrpc": "1.0", "id": 3, "method": "ping"}, {"jsonrpc": "2.0", "id": 3, "method": 7}):
    e = M.handle(bad, B)
    check(isinstance(e, dict) and e.get("error", {}).get("code") == -32600, "1: malformed %r gave %r" % (bad, e))
check(call("nope")["error"]["code"] == -32601, "1: unknown method")
check(call("tools/call", {"name": "write_card", "arguments": {}})["error"]["code"] == -32602, "1: unknown tool")


# 2. tools/list: exactly six, read-only, strict schemas
tl = call("tools/list")["result"]["tools"]
check(sorted(t["name"] for t in tl) == sorted(M.TOOLS) == sorted(["start", "search", "fetch", "get_relations", "get_verse", "get_word"]), "2: tools %r" % [t["name"] for t in tl])
for t in tl:
    a = t.get("annotations") or {}
    check(a.get("readOnlyHint") is True and a.get("destructiveHint") is False and a.get("idempotentHint") is True
          and a.get("openWorldHint") is False and a.get("title"), "2: %s annotations %r" % (t["name"], a))
    s = t.get("inputSchema") or {}
    check(s.get("type") == "object" and s.get("additionalProperties") is False and isinstance(s.get("required"), list)
          and (s["required"] or t["name"] == "start"), "2: %s schema" % t["name"])
    check(t.get("title") and len(t.get("description") or "") > 40, "2: %s needs a title and a real description" % t["name"])


# 3. search
r = tool("search", {"query": "  temptation  "})["result"]
sc = r["structuredContent"]
check(r["isError"] is False and 1 <= len(sc["results"]) <= 10, "3: search results %d" % len(sc.get("results", [])))
check(all(x["url"] and x["id"] and x["title"] for x in sc["results"]), "3: a result without id, title or url")
check(len(sc["results"][0]["links"]) == 3, "3: a search hit should carry its three strongest hops")
check(("search", "temptation") in B.calls, "3: the query was not stripped")
# (Claude's read of the worker's code, 2026-11-03) a held or malformed hit from the site's search is never listed
class LeakySearch(Fake):
    def search(self, query, limit):
        return [{"id": "question:held_one", "title": "held", "url": "u"}, {"id": "card:../x", "title": "x", "url": "u"},
                {"id": "card:temptation", "title": "The temptation", "url": "https://x/e/temptation"}]


ls = M.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
               "params": {"name": "search", "arguments": {"query": "x"}}}, LeakySearch())["result"]["structuredContent"]["results"]
check([x["id"] for x in ls] == ["card:temptation"], "3: search listed a held or malformed hit: %r" % [x["id"] for x in ls])
for bad in ("", "   ", "x" * 201, 5):
    rr = tool("search", {"query": bad})["result"]
    check(rr["isError"] is True, "3: query %r accepted" % (bad,))
check(tool("search", {"query": "a", "extra": 1})["result"]["isError"] is True, "3: an extra argument accepted")


# 4. fetch, its links and the held card
B.calls.clear()
r = tool("fetch", {"id": "card:temptation"})["result"]
sc = r["structuredContent"]
check(sc["id"] == "card:temptation" and sc["url"] == "https://x/e/temptation" and sc["text"], "4: fetch body")
check(sc["sources"] == B.sources and sc["credit"] == M.CREDIT and "CC BY 4.0" in M.CREDIT and "bibleontology.org" in M.CREDIT
      and sc["data_version"] == B.data_version, "4: sources, credit, data version")
links = sc["links"]
real = [x for x in links if x["rel"] != "more"]
check(len(real) == M.MAX_LINKS == 12, "4: %d links" % len(real))
check(all(x["id"] != "question:held_one" for x in links), "4: a link reached a held card")
check([x["id"] for x in real] == ["card:c%d" % i for i in range(12)], "4: links not strongest first: %r" % [x["id"] for x in real])
check(all(x["because"]["ref"] and x["because"]["url"] for x in real), "4: a link without its verse")
check(links[-1]["rel"] == "more" and links[-1].get("cursor"), "4: no 'more' link with a cursor")
rl = [c for c in r["content"] if c["type"] == "resource_link"]
check(r["content"][0]["type"] == "text" and json.loads(r["content"][0]["text"]) == sc, "4: content[0] is not the JSON")
check(len(rl) == 12 + len(sc.get("moves") or []) and all(c.get("uri") and c.get("name") for c in rl), "4: resource_link items %d" % len(rl))
# an error echoes the id it was given and searches its words (2026-11-12: errors that name the next call), so the
# comparison takes the id and its words out: what is left must not say "held", and must be the same for both
def _bare(rr, hidden):
    words = hidden.split(":", 1)[1].replace("_", " ")
    return json.dumps(rr).replace(hidden, "<id>").replace(words, "<words>")


for hidden in ("question:held_one", "card:nobody"):
    rr = tool("fetch", {"id": hidden})["result"]
    check(rr["isError"] is True and "held" not in _bare(rr, hidden).lower(), "4: %s: %r" % (hidden, rr))
    check(rr["structuredContent"]["error"] == "not_found" and rr["structuredContent"].get("try"),
          "4: %s: no error code or next call" % hidden)
    check(all(B.shown(s["id"]) for s in rr["structuredContent"].get("suggestions") or []),
          "4: %s: a suggestion the site does not show" % hidden)
check(_bare(tool("fetch", {"id": "question:held_one"})["result"], "question:held_one")
      == _bare(tool("fetch", {"id": "card:nobody"})["result"], "card:nobody"), "4: a held id answers unlike a missing one")
B.calls.clear()
check(M._valid_id("question:can-salvation-be-lost"), "4: a question id with hyphens was refused")
for bad in ("question:-x", "question:a--b", "card:a-b"):
    check(not M._valid_id(bad), "4: %r accepted" % bad)
for bad in ("card:../x", "card:Bad", "verse:Matt.4", "verse:Xyz.1.1", "verse:Matt.0.1", "word:H12345", "word:X1", "sql:1", "card:" + "a" * 81, 7):
    rr = tool("fetch", {"id": bad})["result"]
    check(rr["isError"] is True, "4: id %r accepted" % (bad,))
check(not [c for c in B.calls if c[0] == "item"], "4: a malformed id reached the backend %r" % B.calls)


# 5. get_relations: capped, paged, filtered
r = tool("get_relations", {"id": "card:temptation"})["result"]["structuredContent"]
check(len(r["relations"]) == 25 and r["next_cursor"], "5: first page %d, cursor %r" % (len(r["relations"]), r.get("next_cursor")))
r2 = tool("get_relations", {"id": "card:temptation", "cursor": r["next_cursor"]})["result"]["structuredContent"]
check(len(r2["relations"]) == 5 and r2["next_cursor"] is None, "5: second page %d" % len(r2["relations"]))
check(not ({x["id"] for x in r["relations"]} & {x["id"] for x in r2["relations"]}), "5: pages overlap")
check(all(x["id"] != "question:held_one" for x in r["relations"] + r2["relations"]), "5: a held card in relations")
k = tool("get_relations", {"id": "card:temptation", "kind": "quotes"})["result"]["structuredContent"]["relations"]
check(k and all(x["rel"] == "quotes" for x in k), "5: kind filter")
more = tool("fetch", {"id": "card:temptation"})["result"]["structuredContent"]["links"][-1]["cursor"]
check(tool("get_relations", {"id": "card:temptation", "cursor": more})["result"]["isError"] is False, "5: the more link's cursor")
check(tool("get_relations", {"id": "card:temptation", "cursor": "zz"})["result"]["isError"] is True, "5: a junk cursor accepted")


# 6. get_verse, get_word, the byte cap
check(tool("get_verse", {"ref": "Matt 4:4"})["result"]["structuredContent"]["id"] == "verse:Matt.4.4", "6: Matt 4:4")
check(tool("get_verse", {"ref": "Matt.4.4"})["result"]["structuredContent"]["id"] == "verse:Matt.4.4", "6: Matt.4.4")
check(tool("get_verse", {"ref": "Matthew 4:4; drop"})["result"]["isError"] is True, "6: a bad reference accepted")
check(tool("get_word", {"strong": "H8322"})["result"]["structuredContent"]["id"] == "word:H8322", "6: get_word")
big = tool("fetch", {"id": "card:big"})["result"]["structuredContent"]
check(len(json.dumps(big)) <= M.MAX_BYTES and big.get("truncated") is True and big["url"], "6: byte cap %d" % len(json.dumps(big)))


# 7. resources, and nothing raises
rs = call("resources/list")["result"]["resources"]
check(sorted(x["name"] for x in rs) == ["about", "licensing", "method", "version"]
      and all(x["uri"] == "bibleontology://" + x["name"] for x in rs), "7: resources %r" % rs)
rd = call("resources/read", {"uri": "bibleontology://about"})["result"]["contents"][0]
check(rd["text"] == "# about" and rd["mimeType"] == "text/markdown", "7: read about")
check(call("resources/read", {"uri": "file:///etc/passwd"})["error"]["code"] == -32602, "7: an unknown uri")


class Broken(Fake):
    def item(self, id):
        raise RuntimeError("C:\\secret\\path exploded")


e = M.handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "fetch", "arguments": {"id": "card:x"}}}, Broken())
txt = json.dumps(e)
check(("error" in e and e["error"]["code"] == -32603) or e.get("result", {}).get("isError") is True, "7: a backend failure: %r" % e)
check("secret" not in txt and "exploded" not in txt, "7: an exception's detail leaked: %s" % txt)

# 8. v1's hypermedia: the front door, self-defining relations, the grouping tree as moves, the map, trust on each hop
st = tool("start", {})["result"]
check(st["isError"] is False and st["structuredContent"]["text"] and [x["id"] for x in st["structuredContent"]["links"]] == ["card:temptation"],
      "8: the front door %r" % st.get("structuredContent"))
check(tool("start", {"x": 1})["result"]["isError"] is True, "8: start took an argument")
check("start" in M.INSTRUCTIONS and "iri" in M.INSTRUCTIONS.lower(), "8: the instructions do not mention start and the iri")
f = tool("fetch", {"id": "card:temptation"})["result"]
sc = f["structuredContent"]
l0 = [x for x in sc["links"] if x["rel"] != "more"]
check(all(x["iri"] == M.NS + ("quotes" if x["rel"] == "quotes" else "tempted_by") for x in l0), "8: a link's iri %r" % l0[:2])
check(M.NS == "https://bibleontology.org/ns/relation/", "8: NS")
check(all("certainty" in x and "voice" in x for x in l0) and any(x["voice"] == "the words of Satan" for x in l0),
      "8: trust fields missing on a hop")
mv = sc.get("moves") or []
check([(m["rel"], m["id"]) for m in mv] == [("up", "card:ministry"), ("down", "verse:Matt.4.4"), ("prev", "card:baptism")],
      "8: moves %r (the held 'next' must be dropped)" % [(m.get("rel"), m.get("id")) for m in mv])
check(sum(1 for c in f["content"] if c["type"] == "resource_link") == len(l0) + len(mv), "8: moves are not resource_link items")
mp = sc.get("map") or []
check([m["type"] for m in mp][:2] in (["quotes", "tempted_by"], ["tempted_by", "quotes"]) and sum(m["count"] for m in mp) == 30,
      "8: the map %r" % [(m.get("type"), m.get("count")) for m in mp])
check(all(m["iri"] == M.NS + m["type"] and m["get"] == {"tool": "get_relations", "arguments": {"id": "card:temptation", "kind": m["type"]}}
          for m in mp), "8: a map entry's iri or move")
check(sum(m["readings"] for m in mp) == sum(1 for i in range(30) if i % 3 == 0), "8: readings counted wrong")
g = tool(mp[0]["get"]["tool"], mp[0]["get"]["arguments"])["result"]["structuredContent"]["relations"]
check(g and all(x["iri"] == M.NS + mp[0]["type"] for x in g), "8: the map's move does not filter by type")

# 9. the schema as items (2026-11-03): relation and kind ids, a definition pointer on every hop and map entry
for good in ("relation:re_enacts", "kind:person"):
    check(M._valid_id(good), "9: %s refused" % good)
for bad in ("relation:Re", "relation:a-b", "kind:" + "a" * 41, "relation:"):
    check(not M._valid_id(bad), "9: %r accepted" % bad)
sc = tool("fetch", {"id": "card:temptation"})["result"]["structuredContent"]
check(all(x["definition"] == "relation:" + ("quotes" if x["rel"] == "quotes" else "tempted_by") for x in sc["links"] if x["rel"] != "more"),
      "9: a hop's definition pointer")
check(all(m["definition"] == "relation:" + m["type"] for m in sc["map"]), "9: a map entry's definition pointer")
B.items["relation:quotes"] = {"id": "relation:quotes", "title": "quotes", "url": "https://x/ns/relation/quotes", "text": "def",
                              "verses": [], "shown": True, "relations": [rel(1, "card:c1", 5)],
                              "schema": {"iri": M.NS + "quotes", "domain": ["kind:person"], "range": ["kind:text"]}}
r = tool("fetch", {"id": "relation:quotes"})["result"]["structuredContent"]
check(r["schema"]["domain"] == ["kind:person"] and r["links"][0]["id"] == "card:c1", "9: a relation's schema and instances %r" % r.get("schema"))
check(tool("fetch", {"id": "kind:nothing"})["result"]["isError"] is True, "9: an unknown kind opened")
# a typeless relation keeps its label but never gets an iri or a definition from it ("quotes" was a dead link)
B.items["card:typeless"] = {"id": "card:typeless", "title": "t", "url": "u", "text": "t", "verses": [], "shown": True,
                            "relations": [{"rel": "quotes", "type": None, "id": "card:c1", "title": "c1", "url": "u",
                                           "because": {"ref": "Matt 4:4", "url": "u"}, "strength": 1}]}
tl = tool("fetch", {"id": "card:typeless"})["result"]["structuredContent"]
check(tl["links"][0]["iri"] is None and tl["links"][0]["definition"] is None and tl["map"][0]["iri"] is None,
      "9: a label became an iri: %r" % tl["links"][0])

# 10. ERRORS THAT SAY WHAT WAS WRONG AND WHAT TO CALL (2026-11-12: both AI directories reject bare errors; "no such
# item" left an agent guessing). Every failing call answers with a code, a sentence of detail, and where one exists a
# ready call; references are taken by book name as agents write them.
LEGACY = {"invalid arguments", "invalid query", "invalid id", "no such item", "invalid kind", "invalid cursor",
          "invalid reference", "invalid strong's number"}


def error_faults(rr, what):
    f = []
    sc = rr.get("structuredContent") or {}
    text = (rr.get("content") or [{}])[0].get("text", "")
    if rr.get("isError") is not True:
        f.append(what + ": not an error")
    if text.strip().lower() in LEGACY or len(text) < 30:
        f.append(what + ": a bare error %r" % text)
    if not re.fullmatch(r"[a-z_]+", sc.get("error") or ""):
        f.append(what + ": no error code")
    for c in sc.get("try") or []:
        if c.get("tool") not in M.TOOLS or not isinstance(c.get("arguments"), dict):
            f.append(what + ": a 'try' that is not a call %r" % c)
    return f


import re  # noqa: E402
cases = [("search", {"query": ""}), ("search", {"query": 5}), ("search", {"q": "x"}), ("fetch", {"id": "card:Bad"}),
         ("fetch", {"id": "card:nobody"}), ("fetch", {"id": "verse:Matt.29.1"}), ("fetch", {}),
         ("get_relations", {"id": "card:temptation", "kind": 3}), ("get_relations", {"id": "card:temptation", "cursor": "zz"}),
         ("get_verse", {"ref": "Matthew 4:4; drop"}), ("get_verse", {"ref": "Hezekiah 1:1"}), ("get_verse", {"ref": 7}),
         ("get_word", {"strong": "X1"}), ("start", {"x": 1})]
for name, args in cases:
    for f in error_faults(tool(name, args)["result"], "%s %r" % (name, args)):
        check(False, "10: " + f)
check(tool("fetch", {"id": "card:Bad"})["result"]["structuredContent"]["try"][0]["arguments"]["query"] == "bad",
      "10: a malformed id does not offer a search on its words")
check("query (required)" in tool("search", {"q": "x"})["result"]["content"][0]["text"],
      "10: an argument error does not say what the tool takes")
e = call("tools/call", {"name": "write_card", "arguments": {}})["error"]
check(e["code"] == -32602 and "fetch" in (e.get("data") or {}).get("detail", ""), "10: an unknown tool's error names no tools")
check("bibleontology://about" in (call("resources/read", {"uri": "x"})["error"].get("data") or {}).get("detail", ""),
      "10: a bad resource uri names none")
# references as people write them, each the same verse the code gives
for ref in ("Matthew 4:4", "matt.4.4", "Matt 4:4", "MATTHEW 4 : 4"):
    rr = tool("get_verse", {"ref": ref})["result"]
    check(rr["isError"] is False and rr["structuredContent"]["id"] == "verse:Matt.4.4", "10: %r did not open Matt 4:4" % ref)
for ref, code in (("Isaiah 53:7", "Isa"), ("1 John 3:16", "1John"), ("I John 3:16", "1John"), ("III John 1:2", "3John"),
                  ("Song of Songs 2:4", "Song"), ("Psalm 23:1", "Ps"), ("Revelation 5:6", "Rev"), ("Philemon 1:6", "Phlm")):
    m = M._RE_ANY_REF.fullmatch(ref)
    check(m and M._book_code(m.group(1)) == code, "10: %r read as %r" % (ref, m and M._book_code(m.group(1))))
check(tool("get_word", {"strong": "h8322"})["result"]["isError"] is False, "10: a lower-case Strong's number refused")
# planted: a bare error is caught
check(error_faults({"isError": True, "content": [{"type": "text", "text": "no such item"}], "structuredContent": {}},
                   "plant"), "10: planted: a bare 'no such item' not caught")

for f in fails:
    print("FAIL", f)
print("mcp: 10 groups of checks; %d failures" % len(fails))
sys.exit(1 if fails else 0)
