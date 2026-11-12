"""Read-only MCP server core for the Bible Ontology graph.

The web server parses a JSON-RPC body, calls ``handle(msg, backend)``, and
sends the returned object (or 202 with no body for a notification).
"""

import base64
import binascii
import json
import re

PROTOCOL_VERSIONS = ("2026-07-28", "2025-06-18", "2025-03-26")
TOOLS = ("start", "search", "fetch", "get_relations", "get_verse", "get_word")
MAX_LINKS = 12
MAX_RELATIONS = 25
MAX_BYTES = 60000
MAX_QUERY = 200
CREDIT = "Bible Ontology (bibleontology.org), CC BY 4.0"
NS = "https://bibleontology.org/ns/relation/"

INSTRUCTIONS = (
    "This graph holds the people, events, places and ideas of the Bible, and "
    "every relation cites the verse it rests on. Start with the start tool when "
    "you have no query yet; otherwise use search. Each answer ends with links "
    "and moves: follow them with fetch to walk the graph. A link's iri names its "
    "relation in our published vocabulary, and its certainty says how firmly the "
    "verse supports it: stated, implied, a reading (someone's judgment), or a "
    "match (found by shared words, with its grade). Check certainty before you "
    "rely on a reading or a match. Cite the "
    "url and the verses of whatever you use."
)

# The site's 66 book codes, longest first so prefixed codes match before short ones.
_BOOKS = (
    "Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth",
    "1Sam", "2Sam", "1Kgs", "2Kgs", "1Chr", "2Chr", "Ezra", "Neh",
    "Esth", "Job", "Ps", "Prov", "Eccl", "Song", "Isa", "Jer", "Lam",
    "Ezek", "Dan", "Hos", "Joel", "Amos", "Obad", "Jonah", "Mic", "Nah",
    "Hab", "Zeph", "Hag", "Zech", "Mal", "Matt", "Mark", "Luke", "John",
    "Acts", "Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col", "1Thess",
    "2Thess", "1Tim", "2Tim", "Titus", "Phlm", "Heb", "Jas", "1Pet",
    "2Pet", "1John", "2John", "3John", "Jude", "Rev",
)
_BOOK_PAT = "|".join(sorted(_BOOKS, key=len, reverse=True))

_SLUG = r"[a-z0-9_]{1,80}"
_RE_CARD = re.compile(r"card:" + _SLUG)
_RE_THEME = re.compile(r"theme:" + _SLUG)
# question ids are the site's addresses, with hyphens ("can-salvation-be-lost"); never a leading one, never "--"
_RE_QUESTION = re.compile(r"question:[a-z0-9](?:[a-z0-9_]|-(?!-)){0,79}")
_RE_VERSE = re.compile(r"verse:(?:%s)\.(\d{1,3})\.(\d{1,3})" % _BOOK_PAT)
_RE_WORD = re.compile(r"word:[HG]\d{1,4}[a-z]?")
# the schema as items (2026-11-03): a relation type and an entity kind, each fetched like a card
_RE_RELATION = re.compile(r"relation:[a-z0-9_]{1,80}")
_RE_KIND = re.compile(r"kind:[a-z0-9_]{1,40}")
_RE_REF = re.compile(r"(%s)\s*[.: ]\s*(\d{1,3})\s*[.:]\s*(\d{1,3})" % _BOOK_PAT)
_RE_STRONG = re.compile(r"[HG]\d{1,4}[a-z]?")

_RESOURCE_NAMES = ("about", "method", "licensing", "version")

_ERROR_MESSAGES = {
    -32600: "invalid request",
    -32601: "method not found",
    -32602: "invalid params",
    -32603: "internal error",
}


def _valid_id(value):
    if not isinstance(value, str):
        return False
    if (_RE_CARD.fullmatch(value) or _RE_THEME.fullmatch(value)
            or _RE_QUESTION.fullmatch(value) or _RE_WORD.fullmatch(value)
            or _RE_RELATION.fullmatch(value) or _RE_KIND.fullmatch(value)):
        return True
    match = _RE_VERSE.fullmatch(value)
    if not match:
        return False
    return all(1 <= int(number) <= 999 for number in match.groups())


def _error(rid, code):
    return {
        "jsonrpc": "2.0",
        "id": rid,
        "error": {"code": code, "message": _ERROR_MESSAGES[code]},
    }


def _ok(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _args_ok(args, allowed):
    return isinstance(args, dict) and set(args) <= set(allowed)


def _relation_type(relation):
    # The vocabulary type defines the relation; the label is only for people.
    rtype = relation.get("type")
    if isinstance(rtype, str) and rtype:
        return rtype
    label = relation.get("rel")
    return label if isinstance(label, str) and label else None


def _vocab_type(relation):
    """The relation's published type, or None: the iri and the definition come only from a real type, never from the
    label a typeless relation falls back to ("quotes" would pass the pattern and name a term that does not exist)."""
    rtype = relation.get("type")
    return rtype if isinstance(rtype, str) and re.fullmatch(r"[a-z0-9_]+", rtype) else None


def _relation_view(relation):
    vtype = _vocab_type(relation)
    return {
        "rel": relation.get("rel"),
        "id": relation.get("id"),
        "title": relation.get("title"),
        "url": relation.get("url"),
        "because": relation.get("because") or {},
        "iri": NS + vtype if vtype else None,
        "certainty": relation.get("certainty"),
        "voice": relation.get("voice"),
        # the relation's own item, so an agent can read what the link claims before relying on it
        "definition": "relation:" + vtype if vtype else None,
    }


def _make_cursor(item_id, offset, kind=None):
    payload = {"id": item_id, "offset": offset}
    if kind:
        payload["kind"] = kind
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _read_cursor(cursor):
    if not isinstance(cursor, str):
        return None
    try:
        raw = base64.b64decode(cursor.encode("ascii"), altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, binascii.Error, UnicodeError):
        return None
    if not isinstance(payload, dict):
        return None
    item_id = payload.get("id")
    offset = payload.get("offset")
    kind = payload.get("kind")
    if not isinstance(item_id, str) or not _valid_id(item_id):
        return None
    if not isinstance(offset, int) or isinstance(offset, bool) or not 0 <= offset <= 100000:
        return None
    if kind is not None and not isinstance(kind, str):
        return None
    return payload


def _shown_relations(backend, item, kind=None):
    relations = sorted(
        item.get("relations") or [],
        key=lambda relation: relation.get("strength", 0),
        reverse=True,
    )
    shown = []
    for relation in relations:
        if kind is not None and _relation_type(relation) != kind:
            continue
        target = relation.get("id")
        if not isinstance(target, str) or not target:
            continue
        if backend.shown(target):
            shown.append(relation)
    return shown


def _links(backend, item, limit, with_more=True):
    if not item:
        return []
    shown = _shown_relations(backend, item)
    links = [_relation_view(relation) for relation in shown[:limit]]
    if with_more and len(shown) > limit:
        # "more" carries an id key like the others so callers can walk links uniformly.
        links.append({
            "rel": "more",
            "id": None,
            "cursor": _make_cursor(item.get("id"), limit),
        })
    return links


_MOVE_ORDER = ("up", "down", "prev", "next", "speaker")


def _moves(backend, item):
    # Moves get the same checks as links: well-formed, shown, and "down" capped.
    moves = item.get("moves") or {}
    if not isinstance(moves, dict):
        return []
    out = []
    for rel in _MOVE_ORDER:
        value = moves.get(rel)
        if rel == "down":
            targets = value if isinstance(value, list) else []
            targets = targets[:MAX_LINKS]
        elif isinstance(value, dict):
            targets = [value]
        else:
            targets = []
        for target in targets:
            target_id = target.get("id")
            if not isinstance(target_id, str) or not _valid_id(target_id):
                continue
            if not backend.shown(target_id):
                continue
            out.append({
                "rel": rel,
                "id": target_id,
                "title": target.get("title"),
                "url": target.get("url"),
            })
    return out


def _map(backend, item):
    # The neighborhood at a glance: one entry per relation type whose target is shown.
    groups = {}
    for relation in _shown_relations(backend, item):
        rtype = _relation_type(relation)
        if rtype is None:
            continue
        group = groups.get(rtype)
        if group is None:
            group = groups[rtype] = {
                "type": rtype,
                "rel": relation.get("rel"),
                "iri": NS + _vocab_type(relation) if _vocab_type(relation) else None,
                "count": 0,
                "readings": 0,
                "definition": "relation:" + _vocab_type(relation) if _vocab_type(relation) else None,
            }
        group["count"] += 1
        if relation.get("certainty") == "reading":
            group["readings"] += 1
    entries = sorted(groups.values(), key=lambda entry: entry["count"], reverse=True)
    for entry in entries:
        entry["get"] = {
            "tool": "get_relations",
            "arguments": {"id": item.get("id"), "kind": entry["type"]},
        }
    return entries


def _start(backend, args):
    if not _args_ok(args, set()):
        return _tool_error("invalid arguments")
    entry = backend.start() or {}
    links = []
    for link in entry.get("links") or []:
        if not isinstance(link, dict):
            continue
        link_id = link.get("id")
        if not isinstance(link_id, str) or not _valid_id(link_id) or not backend.shown(link_id):
            continue
        links.append({
            "rel": link.get("rel"),
            "id": link_id,
            "title": link.get("title"),
            "url": link.get("url"),
        })
    structured = {
        "text": entry.get("text", ""),
        "links": links,
        "sources": backend.sources,
        "credit": CREDIT,
        "data_version": backend.data_version,
    }
    return _tool_result(structured)


def _tool_result(structured, links=None):
    content = [{"type": "text", "text": json.dumps(structured)}]
    for link in (structured.get("links", []) if links is None else links):
        if link.get("rel") == "more":
            continue
        content.append({
            "type": "resource_link",
            "uri": link.get("url", ""),
            "name": link.get("title", ""),
            "description": link.get("rel", ""),
        })
    return {"content": content, "structuredContent": structured, "isError": False}


def _tool_error(text):
    return {"content": [{"type": "text", "text": text}], "isError": True}


def _fit(structured):
    if len(json.dumps(structured)) <= MAX_BYTES:
        return
    structured["truncated"] = True
    while len(json.dumps(structured)) > MAX_BYTES:
        if structured.get("text") and (len(structured["text"]) > 2000 or not structured.get("verses")):
            structured["text"] = structured["text"][: len(structured["text"]) // 2]
        elif structured.get("verses"):
            structured["verses"].pop()
        elif structured.get("text"):
            structured["text"] = structured["text"][: len(structured["text"]) // 2]
        else:
            break
    while len(json.dumps(structured)) > MAX_BYTES and structured.get("links"):
        structured["links"].pop()


def _search(backend, args):
    if not _args_ok(args, {"query"}):
        return _tool_error("invalid arguments")
    query = args.get("query")
    if not isinstance(query, str):
        return _tool_error("invalid query")
    query = query.strip()
    if not query or len(query) > MAX_QUERY:
        return _tool_error("invalid query")

    results = []
    all_links = []
    hits = []
    for hit in backend.search(query, 20) or []:
        # a hit is listed only if fetch would answer it: a well-formed id the site shows (Claude's read, 2026-11-03:
        # links and fetch checked shown, search did not, so a held card the site's search returned would be listed)
        if isinstance(hit, dict) and _valid_id(hit.get("id")) and backend.shown(hit["id"]):
            hits.append(hit)
    for n, hit in enumerate(hits[:10]):
        # the first five hits carry their three strongest hops; the rest only their title and url, since each hop
        # list costs a whole item build (the security seat, 2026-11-03)
        item = backend.item(hit.get("id")) if n < 5 else None
        links = _links(backend, item, 3, with_more=False) if item else []
        all_links.extend(links)
        results.append({
            "id": hit.get("id"),
            "title": hit.get("title"),
            "url": hit.get("url"),
            "links": links,
        })
    structured = {
        "results": results,
        "sources": backend.sources,
        "credit": CREDIT,
        "data_version": backend.data_version,
    }
    return _tool_result(structured, links=all_links)


def _fetch(backend, args):
    if not _args_ok(args, {"id"}):
        return _tool_error("invalid arguments")
    item_id = args.get("id")
    if not isinstance(item_id, str) or not _valid_id(item_id):
        return _tool_error("invalid id")
    item = backend.item(item_id)
    if not item or item.get("shown") is False:
        return _tool_error("no such item")

    structured = {
        "id": item.get("id", item_id),
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "text": item.get("text", ""),
        "verses": list(item.get("verses") or []),
        "links": _links(backend, item, MAX_LINKS, with_more=True),
        "moves": _moves(backend, item),
        "map": _map(backend, item),
        "schema": item.get("schema"),
        # a source only some answers carry (the UBS senses, CC BY-SA) is credited on those answers
        "sources": list(backend.sources) + list(item.get("sources_extra") or []),
        "credit": CREDIT,
        "data_version": backend.data_version,
    }
    _fit(structured)
    # The content lists the item's links and its moves, each one a thing an agent can fetch or read
    # next; _tool_result skips the "more" link, a cursor for get_relations rather than a target.
    content_links = structured["links"] + structured["moves"]
    return _tool_result(structured, links=content_links)


def _get_relations(backend, args):
    if not _args_ok(args, {"id", "kind", "cursor"}):
        return _tool_error("invalid arguments")
    item_id = args.get("id")
    if not isinstance(item_id, str) or not _valid_id(item_id):
        return _tool_error("invalid id")
    item = backend.item(item_id)
    if not item or item.get("shown") is False:
        return _tool_error("no such item")

    kind = args.get("kind")
    if kind is not None and not isinstance(kind, str):
        return _tool_error("invalid kind")

    offset = 0
    cursor = args.get("cursor")
    if cursor is not None:
        payload = _read_cursor(cursor)
        if payload is None or payload["id"] != item_id:
            return _tool_error("invalid cursor")
        if kind is None and payload.get("kind"):
            kind = payload["kind"]
        if kind is not None and payload.get("kind") not in (None, kind):
            return _tool_error("invalid cursor")
        offset = payload["offset"]

    shown = _shown_relations(backend, item, kind)
    page = shown[offset:offset + MAX_RELATIONS]
    next_offset = offset + len(page)
    next_cursor = _make_cursor(item_id, next_offset, kind) if next_offset < len(shown) else None
    relations = [_relation_view(relation) for relation in page]
    structured = {
        "id": item_id,
        "relations": relations,
        "next_cursor": next_cursor,
        "sources": backend.sources,
        "credit": CREDIT,
        "data_version": backend.data_version,
    }
    return _tool_result(structured, links=relations)


def _get_verse(backend, args):
    if not _args_ok(args, {"ref"}):
        return _tool_error("invalid arguments")
    ref = args.get("ref")
    if not isinstance(ref, str):
        return _tool_error("invalid reference")
    match = _RE_REF.fullmatch(ref.strip())
    if not match:
        return _tool_error("invalid reference")
    book, chapter, verse = match.group(1), int(match.group(2)), int(match.group(3))
    if not (1 <= chapter <= 999 and 1 <= verse <= 999):
        return _tool_error("invalid reference")
    return _fetch(backend, {"id": "verse:%s.%d.%d" % (book, chapter, verse)})


def _get_word(backend, args):
    if not _args_ok(args, {"strong"}):
        return _tool_error("invalid arguments")
    strong = args.get("strong")
    if not isinstance(strong, str) or not _RE_STRONG.fullmatch(strong):
        return _tool_error("invalid strong's number")
    return _fetch(backend, {"id": "word:" + strong})


_TOOL_FUNCTIONS = {
    "start": _start,
    "search": _search,
    "fetch": _fetch,
    "get_relations": _get_relations,
    "get_verse": _get_verse,
    "get_word": _get_word,
}


def _tool_defs():
    def make(name, title, description, properties, required):
        return {
            "name": name,
            "title": title,
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
            "annotations": {
                "title": title,
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        }

    return [
        make(
            "start", "Start here",
            "Begin here when you have no specific question yet: a short orientation to the "
            "graph and the entries most worth opening.",
            {},
            [],
        ),
        make(
            "search", "Search",
            "Use this when you have a question or a name. Search the Bible ontology for people, events, places and ideas; "
            "returns up to ten matching items, each with its three strongest links.",
            {"query": {"type": "string", "minLength": 1, "maxLength": MAX_QUERY}},
            ["query"],
        ),
        make(
            "fetch", "Fetch an item",
            "Return one item whole, with its text, verses, sources and links. "
            "Use it to read a search hit or to follow a link from another answer.",
            {"id": {"type": "string"}},
            ["id"],
        ),
        make(
            "get_relations", "Get relations",
            "Page through an item's relations, strongest first, optionally filtered by relation kind. "
            "Use the cursor from a 'more' link to see the next page.",
            {
                "id": {"type": "string"},
                "kind": {"type": "string"},
                "cursor": {"type": "string"},
            },
            ["id"],
        ),
        make(
            "get_verse", "Get a verse",
            "Return a Bible verse by reference (for example Matt 4:4 or Matt.4.4), with its links.",
            {"ref": {"type": "string"}},
            ["ref"],
        ),
        make(
            "get_word", "Get a word",
            "Return a Strong's word entry by number (for example H8322 or G26), with its links.",
            {"strong": {"type": "string"}},
            ["strong"],
        ),
    ]


def _resources_list():
    return [
        {"uri": "bibleontology://" + name, "name": name, "mimeType": "text/markdown"}
        for name in _RESOURCE_NAMES
    ]


def _initialize(params, backend):
    requested = params.get("protocolVersion") if isinstance(params, dict) else None
    version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
    return {
        "protocolVersion": version,
        "capabilities": {"tools": {}, "resources": {}},
        "serverInfo": {"name": "bible-ontology", "version": backend.data_version},
        "instructions": INSTRUCTIONS,
    }


def _tools_call(rid, params, backend):
    if not isinstance(params, dict):
        return _error(rid, -32602)
    name = params.get("name")
    if not isinstance(name, str) or name not in _TOOL_FUNCTIONS:
        return _error(rid, -32602)
    args = params.get("arguments")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return _ok(rid, _tool_error("invalid arguments"))
    return _ok(rid, _TOOL_FUNCTIONS[name](backend, args))


def _resources_read(rid, params, backend):
    if not isinstance(params, dict):
        return _error(rid, -32602)
    uri = params.get("uri")
    prefix = "bibleontology://"
    if not isinstance(uri, str) or not uri.startswith(prefix):
        return _error(rid, -32602)
    name = uri[len(prefix):]
    if name not in _RESOURCE_NAMES:
        return _error(rid, -32602)
    return _ok(rid, {
        "contents": [{
            "uri": uri,
            "mimeType": "text/markdown",
            "text": backend.resource(name),
        }]
    })


def _handle(msg, backend):
    if isinstance(msg, list):
        return _error(None, -32600)
    if not isinstance(msg, dict):
        return _error(None, -32600)
    if msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _error(msg.get("id"), -32600)
    if "id" not in msg:
        return None

    rid = msg["id"]
    method = msg["method"]
    params = msg.get("params")
    if method == "initialize":
        return _ok(rid, _initialize(params, backend))
    if method == "ping":
        return _ok(rid, {})
    if method == "tools/list":
        return _ok(rid, {"tools": _tool_defs()})
    if method == "tools/call":
        return _tools_call(rid, params, backend)
    if method == "resources/list":
        return _ok(rid, {"resources": _resources_list()})
    if method == "resources/read":
        return _resources_read(rid, params, backend)
    return _error(rid, -32601)


def handle(msg, backend):
    try:
        return _handle(msg, backend)
    except Exception:
        rid = msg.get("id") if isinstance(msg, dict) else None
        return _error(rid, -32603)
