"""Read-only MCP server core for the Bible Ontology graph.

The web server parses a JSON-RPC body, calls ``handle(msg, backend)``, and
sends the returned object (or 202 with no body for a notification).
"""

import base64
import binascii
import json
import re

# THE VERSIONS SPOKEN, newest first (2026-11-15: Claude's directory could not connect). The list of 11-03 began with
# "2026-07-28", the stateless revision, which has no `initialize` at all (server/discover, `_meta` on every request,
# `resultType` on every result) and which this server never implemented; and it lacked 2025-11-25. Claude's checker
# sent `initialize` asking for 2025-11-25, was offered 2026-07-28, went on in it, and its next call (server/discover)
# got "method not found". This server speaks the handshake revisions only, until 2026-07-28 is built and tested.
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26")
# a request in the stateless revision is answered with its own "unsupported version" error, listing these, so the
# client falls back to `initialize` (2026-07-28, basic/versioning: -32022, data.supported and data.requested, HTTP 400)
UNSUPPORTED_VERSION = -32022
TOOLS = ("start", "search", "fetch", "get_relations", "get_verse", "get_word")
MAX_LINKS = 12
MAX_RELATIONS = 25
MAX_BYTES = 60000
MAX_QUERY = 200
CREDIT = "Bible Ontology (bibleontology.org), CC BY 4.0"
NS = "https://bibleontology.org/ns/relation/"

# INFORMATION, NEVER INSTRUCTIONS (2026-11-12): both directories reject model-readable text that tells the model how to
# behave (Claude: "describe what the tool does, and don't tell Claude how to behave"; OpenAI: nothing that steers). Until
# then this said "Check certainty before you rely on a reading" and "Cite the url": true advice, phrased as orders.
# It now says what the server holds and what each field means; the license's own term is stated as a term.
# tests/test_mcp_backend.py refuses imperatives aimed at the model here and in the tool descriptions.
INSTRUCTIONS = (
    "This graph holds the people, events, places and ideas of the Bible, and "
    "every relation names the verse it rests on. The start tool gives an orientation "
    "and entry points; search finds items by name or words. Each answer ends with links "
    "and moves, each an id that fetch accepts, so the graph can be walked from any answer. A link's iri names "
    "its relation in the published vocabulary, and its certainty says how firmly the "
    "verse supports it: stated (the text says it), implied, a reading (someone's judgment), or a "
    "match (found by shared words in the original, with its measured grade). Its voice says whose "
    "words it rests on, when they are a speaker's and not the narrator's. A verse names its speaker "
    "where the graph records who speaks it: most of Job, and between a quarter and two fifths of the "
    "quoted speech in the Gospels and Acts. Where it does not, the answer says the words are spoken "
    "and that the speaker is not recorded. Each answer carries its "
    "page's url and its verses to cite; the graph's license, CC BY 4.0, asks for that attribution."
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

# BOOK NAMES AS PEOPLE AND AGENTS WRITE THEM (2026-11-12): get_verse("Isaiah 53:7") was refused, since only the codes
# above were taken. Keys are lower case with spaces and full stops removed; a leading I, II or III reads as 1, 2, 3.
_NAMES = {
    "genesis": "Gen", "exodus": "Exod", "leviticus": "Lev", "numbers": "Num", "deuteronomy": "Deut",
    "joshua": "Josh", "judges": "Judg", "ruth": "Ruth", "1samuel": "1Sam", "2samuel": "2Sam", "1kings": "1Kgs",
    "2kings": "2Kgs", "1chronicles": "1Chr", "2chronicles": "2Chr", "ezra": "Ezra", "nehemiah": "Neh",
    "esther": "Esth", "job": "Job", "psalm": "Ps", "psalms": "Ps", "proverbs": "Prov", "ecclesiastes": "Eccl",
    "songofsolomon": "Song", "songofsongs": "Song", "song": "Song", "isaiah": "Isa", "jeremiah": "Jer",
    "lamentations": "Lam", "ezekiel": "Ezek", "daniel": "Dan", "hosea": "Hos", "joel": "Joel", "amos": "Amos",
    "obadiah": "Obad", "jonah": "Jonah", "micah": "Mic", "nahum": "Nah", "habakkuk": "Hab", "zephaniah": "Zeph",
    "haggai": "Hag", "zechariah": "Zech", "malachi": "Mal", "matthew": "Matt", "mark": "Mark", "luke": "Luke",
    "john": "John", "acts": "Acts", "romans": "Rom", "1corinthians": "1Cor", "2corinthians": "2Cor",
    "galatians": "Gal", "ephesians": "Eph", "philippians": "Phil", "colossians": "Col", "1thessalonians": "1Thess",
    "2thessalonians": "2Thess", "1timothy": "1Tim", "2timothy": "2Tim", "titus": "Titus", "philemon": "Phlm",
    "hebrews": "Heb", "james": "Jas", "1peter": "1Pet", "2peter": "2Pet", "1john": "1John", "2john": "2John",
    "3john": "3John", "jude": "Jude", "revelation": "Rev", "revelations": "Rev",
}
_NAMES.update({b.lower(): b for b in _BOOKS})


def _book_code(name):
    """A book's code from its code or its name, any case ("Isaiah", "isa", "1 John", "I John", "Song of Songs")."""
    key = re.sub(r"[\s.]", "", name or "").lower()
    if key in _NAMES:
        return _NAMES[key]
    for roman, n in (("iii", "3"), ("ii", "2"), ("i", "1")):
        if key.startswith(roman) and n + key[len(roman):] in _NAMES:
            return _NAMES[n + key[len(roman):]]
    return None


_RE_ANY_REF = re.compile(r"\s*((?:[1-3]|I{1,3})?\s*[A-Za-z][A-Za-z .]{0,29}?)[\s.]*(\d{1,3})\s*[.:]\s*(\d{1,3})\s*")

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


def _error(rid, code, detail=None):
    # the standard message, and where it helps, what to send instead (2026-11-12: errors that name the next call)
    err = {"code": code, "message": _ERROR_MESSAGES[code]}
    if detail:
        err["data"] = {"detail": detail}
    return {"jsonrpc": "2.0", "id": rid, "error": err}


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
        return _args_error("start")
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


def _tool_error(text, code="invalid", try_calls=None, suggestions=None):
    """AN ERROR THAT SAYS WHAT WAS WRONG AND WHAT TO CALL INSTEAD (2026-11-12). Both directories reject bare errors
    (Claude: "generic errors ... with no detail fail review"; OpenAI: "clear messaging or fallback behaviors"), and an
    agent given "no such item" had to guess. `code` is stable for programs; `try` holds ready calls; `suggestions`
    holds items the site shows, from its own search, and never says whether an id is held."""
    structured = {"error": code, "message": text}
    if try_calls:
        structured["try"] = try_calls
        text += " Try " + "; or ".join("%s %s" % (c["tool"], json.dumps(c["arguments"])) for c in try_calls) + "."
    if suggestions:
        structured["suggestions"] = suggestions
        text += " Nearest: " + ", ".join("%s (%s)" % (s["id"], s.get("title") or "") for s in suggestions) + "."
    return {"content": [{"type": "text", "text": text}], "structuredContent": structured, "isError": True}


_ID_FORMS = ("card:david, verse:Matt.4.4, word:G26, theme:creation, question:<its address>, relation:quotes "
             "or kind:person")


def _args_error(tool):
    props = next((t["inputSchema"]["properties"] for t in _tool_defs() if t["name"] == tool), {})
    need = next((t["inputSchema"]["required"] for t in _tool_defs() if t["name"] == tool), [])
    takes = ", ".join(("%s (required)" % p) if p in need else p for p in props) or "no arguments"
    return _tool_error("%s takes %s, and nothing else." % (tool, takes), "invalid_arguments")


def _bad_id(value):
    rest = value.split(":", 1)[-1] if isinstance(value, str) else ""          # the words, not the kind before them
    words = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", rest.lower())).strip()[:MAX_QUERY]
    return _tool_error("That is not an id this server uses. Ids look like %s." % _ID_FORMS, "invalid_id",
                       [{"tool": "search", "arguments": {"query": words}}] if words else None)


def _not_found(backend, item_id):
    """Nothing is published under this id: the same words for an id that never existed and for one the site holds
    back (never-rule 1), with a search on the id's own words and its first three hits the site shows."""
    kind, _, rest = item_id.partition(":")
    if kind in ("verse", "word"):
        hint = ("verse:<Book>.<chapter>.<verse>, with a book code such as Matt or 1John"
                if kind == "verse" else "word:<H or G><number>, as in word:H157 or word:G26")
        return _tool_error("Nothing is published under %s. A %s id is %s." % (item_id, kind, hint), "not_found")
    words = re.sub(r"[_\-]+", " ", rest).strip()[:MAX_QUERY]
    hits = []
    for hit in backend.search(words, 20) or []:
        if isinstance(hit, dict) and _valid_id(hit.get("id")) and backend.shown(hit["id"]) \
                and hit["id"] not in [h["id"] for h in hits]:
            hits.append({"id": hit["id"], "title": hit.get("title"), "url": hit.get("url")})
        if len(hits) == 3:
            break
    return _tool_error("Nothing is published under %s." % item_id, "not_found",
                       [{"tool": "search", "arguments": {"query": words}}] if words else None, hits or None)


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
        return _args_error("search")
    query = args.get("query")
    if not isinstance(query, str):
        return _tool_error("search takes a query: text, a name or some words.", "invalid_query")
    query = query.strip()
    if not query or len(query) > MAX_QUERY:
        return _tool_error("A query is 1 to %d characters of text." % MAX_QUERY, "invalid_query")

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
        return _args_error("fetch")
    item_id = args.get("id")
    if not isinstance(item_id, str) or not _valid_id(item_id):
        return _bad_id(item_id)
    item = backend.item(item_id)
    if not item or item.get("shown") is False:
        return _not_found(backend, item_id)

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
        return _args_error("get_relations")
    item_id = args.get("id")
    if not isinstance(item_id, str) or not _valid_id(item_id):
        return _bad_id(item_id)
    item = backend.item(item_id)
    if not item or item.get("shown") is False:
        return _not_found(backend, item_id)

    kind = args.get("kind")
    if kind is not None and not isinstance(kind, str):
        return _tool_error("kind is a relation type, as text: the types an item holds are in its map.",
                           "invalid_kind", [{"tool": "fetch", "arguments": {"id": item_id}}])

    offset = 0
    cursor = args.get("cursor")
    if cursor is not None:
        payload = _read_cursor(cursor)
        if payload is None or payload["id"] != item_id:
            return _tool_error("That cursor is not one this item and kind gave out. A cursor comes from the "
                               "'more' link, or next_cursor, of the same item and kind.", "invalid_cursor",
                               [{"tool": "get_relations", "arguments": {"id": item_id}}])
        if kind is None and payload.get("kind"):
            kind = payload["kind"]
        if kind is not None and payload.get("kind") not in (None, kind):
            return _tool_error("That cursor is not one this item and kind gave out. A cursor comes from the "
                               "'more' link, or next_cursor, of the same item and kind.", "invalid_cursor",
                               [{"tool": "get_relations", "arguments": {"id": item_id}}])
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
        return _args_error("get_verse")
    ref = args.get("ref")
    bad = _tool_error("A reference is a book, a chapter and a verse, as in Matt 4:4, Matthew 4:4, Isa.53.7 or "
                      "1 John 3:16. One verse at a time.", "invalid_reference")
    if not isinstance(ref, str) or len(ref) > 60:
        return bad
    match = _RE_ANY_REF.fullmatch(ref)
    book = _book_code(match.group(1)) if match else None
    if not match:
        return bad
    if not book:
        return _tool_error("%r is not a book of the 66 this graph holds (Genesis to Revelation, by name or code)."
                           % match.group(1).strip(), "invalid_reference")
    chapter, verse = int(match.group(2)), int(match.group(3))
    if not (1 <= chapter <= 999 and 1 <= verse <= 999):
        return bad
    return _fetch(backend, {"id": "verse:%s.%d.%d" % (book, chapter, verse)})


def _get_word(backend, args):
    if not _args_ok(args, {"strong"}):
        return _args_error("get_word")
    strong = args.get("strong")
    if isinstance(strong, str):
        strong = strong.strip().upper()
        if re.fullmatch(r"[HG]\d{1,4}[A-Z]?", strong):
            strong = strong[:-1] + strong[-1].lower() if strong[-1].isalpha() else strong
    if not isinstance(strong, str) or not _RE_STRONG.fullmatch(strong):
        return _tool_error("A Strong's number is H (Hebrew and Aramaic) or G (Greek) and up to four digits, as in "
                           "H157 or G26.", "invalid_strongs")
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
            "For when there is no specific question yet: a short orientation to the "
            "graph and the entries most worth opening.",
            {},
            [],
        ),
        make(
            "search", "Search",
            # 2026-11-17 (P-2026-11-16-3 (3)): "each with its three strongest links" was untrue past the fifth hit, and
            # a model read Dan 9:27's empty list (eighth or so) as "no links"; it has Matt 24:15 and Mark 13:14
            "Use this when you have a question or a name. Search the Bible ontology for people, events, places and ideas; "
            "returns up to ten matching items. The first five carry their three strongest links; the rest carry none "
            "here, which does not mean they have none: fetch returns any item whole, with all its links.",
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
            "Return a Bible verse by reference, the book by name or code (for example Matthew 4:4, Matt 4:4, "
            "1 John 3:16 or Isa.53.7), with its links.",
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
        return _error(rid, -32602, "tools/call takes params {\"name\": <a tool>, \"arguments\": {...}}.")
    name = params.get("name")
    if not isinstance(name, str) or name not in _TOOL_FUNCTIONS:
        return _error(rid, -32602, "The tools are %s; tools/list describes each." % ", ".join(TOOLS))
    args = params.get("arguments")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return _ok(rid, _tool_error("arguments is an object of the tool's named arguments.", "invalid_arguments"))
    return _ok(rid, _TOOL_FUNCTIONS[name](backend, args))


def _resources_read(rid, params, backend):
    if not isinstance(params, dict):
        return _error(rid, -32602, "resources/read takes a uri from resources/list: %s." % ", ".join(
            "bibleontology://" + r for r in _RESOURCE_NAMES))
    uri = params.get("uri")
    prefix = "bibleontology://"
    if not isinstance(uri, str) or not uri.startswith(prefix):
        return _error(rid, -32602, "resources/read takes a uri from resources/list: %s." % ", ".join(
            "bibleontology://" + r for r in _RESOURCE_NAMES))
    name = uri[len(prefix):]
    if name not in _RESOURCE_NAMES:
        return _error(rid, -32602, "resources/read takes a uri from resources/list: %s." % ", ".join(
            "bibleontology://" + r for r in _RESOURCE_NAMES))
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
    meta = params.get("_meta") if isinstance(params, dict) else None
    asked = meta.get("io.modelcontextprotocol/protocolVersion") if isinstance(meta, dict) else None
    if method == "server/discover" or (asked and asked not in PROTOCOL_VERSIONS):
        return {"jsonrpc": "2.0", "id": rid, "error": {
            "code": UNSUPPORTED_VERSION, "message": "unsupported protocol version",
            "data": {"supported": list(PROTOCOL_VERSIONS), "requested": asked or "2026-07-28"}}}
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
    if method == "resources/templates/list":
        # resources are declared, so a client may ask for their templates: there are none, which is an answer
        return _ok(rid, {"resourceTemplates": []})
    return _error(rid, -32601)


def handle(msg, backend):
    try:
        return _handle(msg, backend)
    except Exception:
        rid = msg.get("id") if isinstance(msg, dict) else None
        return _error(rid, -32603)
