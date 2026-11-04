"""The MCP server's backend: the site's own answers, gathered into what app2/mcp.py serves (2026-11-03).

app2/mcp.py is the protocol and every rule (tests/test_mcp.py, a fake backend). This module is the one place that
knows the site: it calls the same functions the API calls (one source of truth, no second copy of the graph), and
turns a card's answer into items whose relations each carry the verse that makes them.

THE HOP RULES (Doug, 2026-11-03: "build the adapter with the hop rules as discussed"):
  - a hop names a relation and hands over a verse that makes it; a relation with no verse is not a hop
  - the card's relation groups, in the order the card shows them; kin, events and the event's cast among them
  - quotations and echoes are hops; readings are marked "reading" (the story echoes, anything conjectured, a judged
    parallel no editor made)
  - the original-language words: two at most
  - themes go in the body, never as hops; mined patterns ("Role pattern") are left out: patterns, not instances
  - divine persons exactly as the site shows them: nothing here adds, merges or relabels a relation
  - "shown" means the site's own API finds it: a held card or question answers {"found": False} there
"""
import collections
import json
import re
import threading
from pathlib import Path

SITE = "https://bibleontology.org"
ROOT = Path(__file__).resolve().parents[1]

CERTAINTY = {"explicit": "stated", "implied": "implied", "conjectured": "reading", "disputed": "reading"}
READING_CATEGORIES = {"Story echoes", "Story told this way"}      # readings by the story-echo standard
SKIP_CATEGORIES = {"Role pattern"}                                # patterns, not instances
THEME_TYPES = {"in_theme"}                                        # a card's major themes: in the body, not hops
LANGUAGE_CATEGORY, LANGUAGE_CAP = "Language", 2
VERSES_IN_BODY = 6
# the security seat, 2026-11-03: built items are cached (the data does not change between deploys), bounded, and the
# shown answers too, so attacker-chosen ids cannot grow memory without end
ITEM_CACHE = 512
SHOWN_CACHE = 50000
REF = re.compile(r"^\s*(\d?[A-Za-z]+)\s+(\d+):(\d+)")
SLUG = re.compile(r"^[a-z0-9_]{1,80}$")

# the order of strength: what the text states, then quotations and parallels, then readings, then words
TIER_STATED, TIER_QUOTE, TIER_READING, TIER_WORD = 3, 2, 1, 0

SOURCES = [
    {"name": "MACULA Hebrew and Greek Linguistic Datasets",
     "licence": "(c) 2022-2024 Biblica, Inc. Licensed under CC BY 4.0",
     "url": "https://github.com/Clear-Bible/macula-hebrew/ and https://github.com/Clear-Bible/macula-greek/"},
    {"name": "The Holy Bible, Berean Standard Bible, BSB",
     "licence": "This text of God's Word has been dedicated to the public domain.", "url": "https://bereanbible.com"},
    {"name": "STEP Bible's Translators Brief lexicons (Tyndale House, Cambridge)",
     "licence": "CC BY 4.0; the Greek based on Abbott-Smith's Manual Greek Lexicon of the New Testament (1922)",
     "url": "https://github.com/STEPBible/STEPBible-Data"},
]

START_TEXT = (
    "Bible Ontology is a graph of what the Bible's text says: who did what to whom, who said it, which passages "
    "quote or echo which, and the Hebrew and Greek words beneath, every relation tied to the verse that makes it. "
    "It takes no doctrinal side; where a link is a reading rather than a statement of the text, it says so. Open "
    "one of these, or search for a name, an event, a theme or a reference.")
START_LINKS = [("event", "card:event_jesus_temptation"), ("person", "card:david"), ("person", "card:moses"),
               ("event", "card:event_creation_of_heavens_and_earth"), ("theme", "theme:creation"),
               ("question", "question:baptism"), ("verse", "verse:John.1.1")]

RESOURCES = {
    "about": (
        "# Bible Ontology\n\nA knowledge graph of the Bible's text: people, events, places, ideas and words, and "
        "the relations between them, each citing its verse. Built on the original languages (MACULA) and read in "
        "the Berean Standard Bible. Read-only. It states what the text says and marks readings as readings; it "
        "takes no doctrinal position.\n\nEvery answer ends with links and moves: follow them with `fetch`. Each "
        "link's `iri` is its relation's definition in the published vocabulary; its `certainty` says how firmly "
        "the verse supports it; `voice` says whose words it rests on. Cite the `url` and the verses you use.\n"),
    "method": (
        "# How the graph is built\n\n- Relations are lifted from the clauses of the original-language text "
        "(MACULA) and read against the verse; where translations differ, the original decides.\n- Each relation "
        "keeps its certainty (stated, implied, a reading) and its voice: the narrator, or the speaker whose words "
        "it rests on (\"the words of Eliphaz\").\n- Readings (story echoes, judged parallels) are marked as "
        "readings and never presented as the text's own statement.\n- Machine readings are checked twice and "
        "against planted faults before they are kept; the method is described at " + SITE + "/about.\n"),
    "licensing": (
        "# Licensing\n\nThe graph: Bible Ontology (bibleontology.org), CC BY 4.0. Its sources keep their own "
        "terms, credited in their own words in every answer's `sources`: MACULA (c) Biblica, Inc., CC BY 4.0; "
        "the Berean Standard Bible, public domain; STEP Bible's lexicons, CC BY 4.0.\n"),
}


def _url(path):
    return SITE + path


def _verse_id(ref):
    """'2Sam 23:23' or 'Luke 3:31-32' -> ('2Sam', 23, 23), the first verse of a range; None if it is not one."""
    m = REF.match(ref or "")
    return (m.group(1), int(m.group(2)), int(m.group(3))) if m else None


def _diversify(rels):
    """A target's second relation ranks after every target's first, its third after every second: the top links go to
    as many different places as there are, and get_relations still lists every relation (Jesus took four of the
    temptation's twelve links before this)."""
    count = {}
    for r in sorted(rels, key=lambda r: -r["strength"]):
        k = count.get(r["id"], 0)
        count[r["id"]] = k + 1
        r["strength"] -= k * 10000000


class Backend(object):
    def __init__(self, server, d):
        self.S, self.d = server, d
        try:
            v = json.loads((ROOT / "ontology" / "ns-version.json").read_text(encoding="utf-8"))
            self.data_version = "%s+%s" % (v.get("version"), v.get("date"))
        except (OSError, ValueError):
            self.data_version = "unknown"
        self.sources = SOURCES
        self._shown = {}
        self._items = collections.OrderedDict()
        self._lock = threading.Lock()                    # first-use builds and the caches, shared by many threads

    # ------------------------------------------------------------------ helpers
    def _because(self, ref):
        v = _verse_id(ref)
        if not v or v not in self.d["verses"]:
            return None
        return {"ref": "%s %d:%d" % v, "url": _url("/p/%s.%d.%d" % v)}

    def _verse_text(self, b, c, v):
        try:
            out = self.S.api_verse(self.d, {"ref": ["%s %d:%d" % (b, c, v)]})
        except Exception:                                    # noqa: BLE001
            return None
        if not (self.d["verses"].get((b, c, v)) or "").strip():
            return self._later_manuscripts(b, c, v)      # the API calls an empty verse not found; the key is there
        return out.get("text") if out.get("found") else None

    def _later_manuscripts(self, b, c, v):
        """A verse the Berean leaves empty (the earliest manuscripts lack it): the note, then the later manuscripts'
        reading in Young's Literal Translation, marked so. Never the text as if it were the Berean's, and never empty,
        which an agent may fill from memory, perhaps in the KJV's words (Doug, 2026-11-03: "note plus Young's Literal")."""
        if getattr(self, "_ylt", None) is None:
            try:
                self._ylt = json.loads((ROOT / "data" / "bible" / "later-manuscripts.ylt.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._ylt = {"note": "Not in the Berean text: the earliest manuscripts lack this verse.", "verses": {}}
        note = self._ylt.get("note") or ""
        ylt = (self._ylt.get("verses") or {}).get("%s.%d.%d" % (b, c, v))
        return note + (" Later manuscripts read (Young's Literal Translation, 1898): \"%s\"" % ylt if ylt else "")

    def _card_url(self, eid):
        return _url("/e/" + self.S.quote(self.S._addr(eid)))

    def _from_macula(self, ref):
        """'Mat.4.4' -> ('Matt', 4, 4), the Berean verse it names, or None."""
        try:
            got = self.S.bsb_ref(self.d, ref)
        except Exception:                                    # noqa: BLE001
            return None
        m = re.match(r"^(\w+)\.(\d+)\.(\d+)$", got or "")
        if not m:
            return None
        # bsb_ref answers in MACULA's book codes ("Luk"); the site's are the Berean's ("Luke"), as tools/sitemap.py does
        v = (self.S.MACULA_BACK.get(m.group(1), m.group(1)), int(m.group(2)), int(m.group(3)))
        return v if v in self.d["verses"] else None

    # ------------------------------------------------------------------- search
    def search(self, query, limit):
        out = []
        for r in (self.S.api_search(self.d, {"q": [query]}).get("results") or []):
            kind, rid, title = r.get("kind"), r.get("id"), r.get("title")
            if kind == "entity" and SLUG.match(rid or ""):
                out.append({"id": "card:" + rid, "title": title, "url": self._card_url(rid)})
            elif kind == "mtheme" and SLUG.match(rid or ""):
                out.append({"id": "theme:" + rid, "title": title, "url": _url("/themes/" + rid)})
            elif kind == "passage":
                v = _verse_id(title or "")                   # the title is the full name; the id, the book's code
                full = r.get("id")
                if v and full and (full, v[1], v[2]) in self.d["verses"]:
                    out.append({"id": "verse:%s.%d.%d" % (full, v[1], v[2]), "title": title,
                                "url": _url("/p/%s.%d.%d" % (full, v[1], v[2]))})
            if len(out) >= limit:
                break
        return out

    # --------------------------------------------------------------------- items
    def item(self, iid):
        with self._lock:
            if iid in self._items:
                self._items.move_to_end(iid)
                return self._items[iid]
        kind, _, key = iid.partition(":")
        try:
            got = {"card": self._card, "verse": self._verse, "word": self._word, "theme": self._theme,
                   "question": self._question, "relation": self._relation, "kind": self._kind}[kind](key)
        except KeyError:
            return None
        with self._lock:
            if got is not None:                          # only what exists is kept: a miss costs a lookup, not memory
                self._items[iid] = got
                if len(self._items) > ITEM_CACHE:
                    self._items.popitem(last=False)
            self._remember(iid, got is not None)
        return got

    def _remember(self, iid, got):
        """Called with the lock held. Positives only, and the map cleared when full (the security seat)."""
        if got:
            if len(self._shown) >= SHOWN_CACHE:
                self._shown.clear()
            self._shown[iid] = True

    def shown(self, iid):
        """What the site's own API would find, without building the item: a card's record, a question the site
        shows, a verse in the text. (Building each target cost the God card 70 s for its thousand relations.)"""
        if self._shown.get(iid):
            return True
        kind, _, key = iid.partition(":")
        if kind == "card":
            got = key in self.d["ents"]                      # api_entity's own test; an alias opens its event's card
        elif kind == "question":
            got = key in self.S._questions()                 # only the shown questions, as the sitemap relies on
        elif kind == "verse":
            m = re.match(r"^(\w+)\.(\d+)\.(\d+)$", key)
            got = bool(m) and (m.group(1), int(m.group(2)), int(m.group(3))) in self.d["verses"]
        elif kind == "relation":
            got = key in self._vocab()["types"]
        elif kind == "kind":
            got = key in self._kinds()
        else:
            got = self.item(iid) is not None
        with self._lock:
            self._remember(iid, got)
        return got

    def start(self):
        links = []
        for rel, iid in START_LINKS:
            kind, _, key = iid.partition(":")
            if not self.shown(iid):                          # each entry as the site has it, or left out
                continue
            if kind == "card":
                title, url = self.d["ents"][key].get("name") or key, self._card_url(key)
            elif kind == "verse":
                title, url = key.replace(".", " ", 1).replace(".", ":"), _url("/p/" + key)
            elif kind == "question":
                title, url = key.replace("-", " "), _url("/questions/" + key)
            else:
                title, url = key.replace("_", " ").title(), _url("/themes/" + key)
            links.append({"rel": rel, "id": iid, "title": title, "url": url})
        return {"text": START_TEXT, "links": links}

    def resource(self, name):
        if name == "version":
            return "# Version\n\nData and vocabulary: %s\n" % self.data_version
        return RESOURCES.get(name, "")

    # ---------------------------------------------------------------------- cards
    def _card(self, key):
        e = self.S.api_entity(self.d, {"id": [key]})
        if not e.get("found"):
            return None
        eid = e.get("id") or key
        rels, n = [], 0
        for g in e.get("groups") or []:
            cat = g.get("category")
            if cat in SKIP_CATEGORIES:
                continue
            taken = 0
            for it in g.get("items") or []:
                n += 1
                if cat == LANGUAGE_CATEGORY and taken >= LANGUAGE_CAP:
                    continue
                other = it.get("other")
                if it.get("type") in THEME_TYPES:
                    continue                                 # themes go in the body, never as hops
                because = self._because((it.get("refs") or [None])[0])
                if not SLUG.match(other or "") or not because:
                    continue                                 # no verse, no hop
                certainty = CERTAINTY.get(it.get("certainty"), "implied")
                if cat in READING_CATEGORIES:
                    certainty = "reading"
                tier = (TIER_WORD if cat == LANGUAGE_CATEGORY else
                        TIER_READING if certainty == "reading" else TIER_STATED)
                rels.append({"rel": it.get("label"), "type": self._vt(it.get("type")), "id": "card:" + other,
                             "title": it.get("name"), "url": self._card_url(other), "because": because,
                             "certainty": certainty,
                             "voice": ("the words of " + it["claimed_by_name"]) if it.get("claimed_by_name") else None,
                             "strength": tier * 100000 - n})
                taken += 1
        ev = e.get("evcard") or {}
        seen = {(r["id"], r["rel"]) for r in rels}
        for c in ev.get("cast") or []:                       # who did what in the scene, each with its clause's verse
            n += 1
            go = re.match(r"^(\w+)\.(\d+)\.(\d+)$", str(((c.get("cites") or [{}])[0]).get("go") or ""))
            because = self._because("%s %s:%s" % go.groups()) if go else None
            obj = c.get("object") or {}
            subs = [s for s in c.get("subjects") or [] if isinstance(s, dict)]
            if not because:
                continue
            certainty = CERTAINTY.get(c.get("certainty"), "implied")
            voice = ("the words of " + c["claimed_by"]["name"]) if isinstance(c.get("claimed_by"), dict) else None
            # the label is the clause itself, which reads the same from either end
            clause = " ".join(x for x in (" and ".join(s.get("name") or "" for s in subs), c.get("verb"), obj.get("name")) if x)
            ends = [(s.get("id"), s.get("name"), clause) for s in subs] + [(obj.get("id"), obj.get("name"), clause)]
            for oid, name, rel in ends:
                if not SLUG.match(oid or "") or oid == eid or (oid, rel) in seen:
                    continue
                seen.add((oid, rel))
                rels.append({"rel": rel, "type": self._vt(c.get("kind")), "id": "card:" + oid, "title": name,
                             "url": self._card_url(oid), "because": because, "certainty": certainty, "voice": voice,
                             # on an event, who did what leads its tier, ahead of the structural "contains"
                             "strength": TIER_STATED * 100000 + 50000 - n})
        for q in ev.get("quotes") or []:                     # the event's quotations: verse to verse
            n += 1
            # a quotation's ends come as one address or several ("Matt.4.6" or a list); the first of each is the hop.
            # The references are full names ("Deuteronomy 8:3"); the go fields are the addresses.
            first = lambda x: (x[0] if x else "") if isinstance(x, list) else (x or "")  # noqa: E731
            frm_go = re.match(r"^(\w+)\.(\d+)\.(\d+)$", str(first(q.get("from_go"))))
            m = re.match(r"^(\w+)\.(\d+)\.(\d+)$", str(first(q.get("to_go"))))
            frm = self._because("%s %s:%s" % frm_go.groups()) if frm_go else None
            if m and frm:
                tid = "%s.%s.%s" % m.groups()
                rels.append({"rel": q.get("verb") or "quotes", "type": None, "id": "verse:" + tid,
                             "title": str(first(q.get("to_ref"))) or tid, "url": _url("/p/" + tid), "because": frm,
                             "certainty": "stated", "voice": q.get("speaker"), "strength": TIER_QUOTE * 100000 - n})
        _diversify(rels)
        refs = [v for v in (_verse_id(r) for r in (e.get("refs") or [])) if v and v in self.d["verses"]]
        verses = [{"ref": "%s %d:%d" % v, "text": self._verse_text(*v), "url": _url("/p/%s.%d.%d" % v)}
                  for v in refs[:VERSES_IN_BODY]]
        themes = [t.get("title") or t.get("theme") for t in (e.get("mthemes") or [])]
        text = (e.get("name") or eid) + (". " + e["desc"] if e.get("desc") else "")
        if themes:
            text += "\nThemes: " + ", ".join(t for t in themes if t)
        moves = {}
        evd = (ev and e.get("event")) or {}
        within = evd.get("within")
        within = within if isinstance(within, list) else [within] if within else []
        # an event inside larger ones: the first is the move up (mcp.py takes one "up")
        ups = [w for w in within if isinstance(w, str) and SLUG.match(w) and w in self.d["ents"]]
        if ups:
            moves["up"] = {"id": "card:" + ups[0], "title": self.d["ents"][ups[0]].get("name") or ups[0],
                           "url": self._card_url(ups[0])}
        moves["down"] = [{"id": "card:" + t["id"], "title": t.get("label"), "url": self._card_url(t["id"])}
                         for t in (evd.get("tellings") or []) if SLUG.match(t.get("id") or "")]
        return {"id": "card:" + eid, "title": e.get("name") or eid, "url": self._card_url(eid), "text": text,
                "verses": verses, "relations": rels, "moves": moves, "shown": True}

    # --------------------------------------------------------------------- verses
    ECHO_BUCKETS = (("earlier", "quotes or echoes", "echoes_earlier", "stated", TIER_QUOTE),
                    ("editors", "the Berean editors' cross-reference", "cross_reference", "stated", TIER_QUOTE),
                    ("aligned", "a parallel account", "parallel_to", "reading", TIER_READING),
                    ("allusions", "alludes to", "alludes_to", "reading", TIER_READING))

    def _verse(self, key):
        m = re.match(r"^(\w+)\.(\d+)\.(\d+)$", key)
        if not m:
            return None
        b, c, v = m.group(1), int(m.group(2)), int(m.group(3))
        if (b, c, v) not in self.d["verses"]:
            return None
        text = self._verse_text(b, c, v)
        here = {"ref": "%s %d:%d" % (b, c, v), "url": _url("/p/%s.%d.%d" % (b, c, v))}
        rels, n = [], 0
        try:
            ec = self.S.api_echoes(self.d, {"ref": ["%s %d:%d" % (b, c, v)]})
        except Exception:                                    # noqa: BLE001
            ec = {}
        for bucket, label, rtype, certainty, tier in self.ECHO_BUCKETS:
            for it in ec.get(bucket) or []:
                n += 1
                if not isinstance(it, dict):
                    continue
                if bucket == "aligned" and not it.get("judged"):
                    continue                                 # an unjudged alignment is a similarity score, not a parallel
                t = self._from_macula(it.get("eref") or it.get("ref") or "")
                if not t or t == (b, c, v):
                    continue
                tid = "%s.%d.%d" % t
                rels.append({"rel": label, "type": self._vt(rtype), "id": "verse:" + tid, "title": "%s %d:%d" % t,
                             "url": _url("/p/" + tid), "because": here, "certainty": certainty, "voice": None,
                             "strength": tier * 100000 - n})
        _diversify(rels)
        moves = {}
        for rel, cand in (("prev", (b, c, v - 1)), ("next", (b, c, v + 1)), ("next", (b, c + 1, 1))):
            if rel not in moves and cand in self.d["verses"]:
                moves[rel] = {"id": "verse:%s.%d.%d" % cand, "title": "%s %d:%d" % cand,
                              "url": _url("/p/%s.%d.%d" % cand)}
        return {"id": "verse:" + key, "title": "%s %d:%d" % (b, c, v), "url": here["url"], "text": text or "",
                "verses": [dict(here, text=text)], "relations": rels, "moves": moves, "shown": True}

    # ---------------------------------------------------------------------- the schema
    # THE SCHEMA AS ITEMS (Doug, 2026-11-03: "add schema navigation to v1 ... with instances as links"). A link's
    # relation opens as an item: its public definition, its inverse, its domain and range as kinds, and a dozen real
    # instances, each a hop with its verse. A kind opens with the relations that start or end at it and example cards.
    # The vocabulary is the link-relation registry: the schema and the data are one walk.
    def _vocab(self):
        if getattr(self, "_v", None) is None:
            with self._lock:
                if getattr(self, "_v", None) is None:
                    self._v = self._load_vocab()
        return self._v

    def _load_vocab(self):
        if True:
            import yaml
            types = yaml.safe_load((ROOT / "ontology" / "schema" / "relationship_types.yaml").read_text(encoding="utf-8"))["types"]
            defs = json.loads((ROOT / "ontology" / "schema" / "relation_definitions.json").read_text(encoding="utf-8"))["types"]
            return {"types": types, "defs": defs}

    def _instances(self, rtype):
        """Every shown relation of a type, once, from its source's side (held rows are kept apart in held_ix)."""
        if rtype in THEME_TYPES:
            return []                                    # themes are never hops, here as on a card (the security seat)
        if getattr(self, "_inst", None) is None:
            with self._lock:
                if getattr(self, "_inst", None) is None:
                    ix = {}
                    for src, rows in self.d["rels"].items():
                        for r in rows:
                            if r.get("dir") == "out" and r.get("refs"):
                                ix.setdefault(r.get("type"), []).append((src, r))
                    self._inst = ix
        return self._inst.get(rtype, [])

    def _kinds(self):
        """The graph's entity kinds: every type a relation's domain or range names, and every card's type."""
        if getattr(self, "_k", None) is None:
            self._k = self._load_kinds()
        return self._k

    def _load_kinds(self):
        if True:
            ks = set()
            for t in self._vocab()["types"].values():
                ks.update(t.get("src_type") or [])
                ks.update(t.get("dst_type") or [])
            ks.update(e.get("type") for e in self.d["ents"].values() if e.get("type"))
            return {k for k in ks if isinstance(k, str) and SLUG.match(k)}

    def _vt(self, rtype):
        """A relation's type only if the published vocabulary has it; otherwise None, so the hop carries its label
        but no iri and no definition pointer. The verse-to-verse links (quotations, the editors' references,
        parallels, allusions) are not published terms yet: a made-up iri would be a claim about a vocabulary that
        does not say it (Claude's check, 2026-11-03: relation:quotes was a dead link)."""
        return rtype if rtype in self._vocab()["types"] else None

    def _spread(self, rows, n=12):
        """n rows evenly across the list, so the examples are not all from one book or one name."""
        if len(rows) <= n:
            return list(rows)
        step = len(rows) / float(n)
        return [rows[int(i * step)] for i in range(n)]

    def _relation(self, key):
        v = self._vocab()
        t = v["types"].get(key)
        if not t:
            return None
        dfn = (v["defs"].get(key) or {}).get("definition") or ""
        rows = self._instances(key)
        rels, n = [], 0
        for src, r in self._spread([x for x in rows if x[0] in self.d["ents"]], 12):
            n += 1
            because = self._because(r["refs"][0])
            dst = r.get("other")
            if not because or not SLUG.match(src):
                continue
            names = (self.d["ents"][src].get("name") or src, (self.d["ents"].get(dst) or {}).get("name") or dst)
            rels.append({"rel": "%s %s %s" % (names[0], t.get("label") or key, names[1]), "type": key, "id": "card:" + src,
                         "title": names[0], "url": self._card_url(src), "because": because,
                         "certainty": CERTAINTY.get(r.get("certainty"), "implied"),
                         "voice": ("the words of " + (self.d["ents"].get(r["claimed_by"]) or {}).get("name", r["claimed_by"]))
                         if r.get("claimed_by") else None, "strength": 1000 - n})
        schema = {"iri": SITE + "/ns/relation/" + key, "label": t.get("label"), "inverse": t.get("inverse"),
                  "definition": dfn, "category": t.get("category"), "group": t.get("group"),
                  "domain": ["kind:" + k for k in (t.get("src_type") or []) if SLUG.match(k)],
                  "range": ["kind:" + k for k in (t.get("dst_type") or []) if SLUG.match(k)],
                  "instances": len(rows), "vocabulary_version": self.data_version}
        text = "%s (%s). %s\nInverse: %s. %d instances in the graph; examples follow as links, each with its verse." % (
            t.get("label") or key, key, dfn, t.get("inverse") or "none", len(rows))
        return {"id": "relation:" + key, "title": t.get("label") or key, "url": SITE + "/ns/relation/" + key,
                "text": text, "verses": [], "relations": rels, "moves": {}, "shown": True, "schema": schema}

    # the closest published class for an entity kind, where the meaning vocabulary's own comments name it; the
    # others carry none rather than a guess (object, group, image, covenant, observance)
    KIND_CLASS = {"person": "PersonalBeing", "being": "PersonalBeing", "creature": "Being", "place": "Place",
                  "concept": "Concept", "title": "Title", "event": "Event", "text": "Saying"}

    def _kind(self, key):
        if key not in self._kinds():
            return None
        v = self._vocab()["types"]
        cls = self.KIND_CLASS.get(key)
        klass = None
        if cls:
            ttl = (ROOT / "out" / "ns" / "meaning.ttl")
            body = ""
            try:
                m = re.search(r"^bom:%s a rdfs:Class,(.*?)(?=^bom:|\Z)" % cls, ttl.read_text(encoding="utf-8"), re.S | re.M)
                body = m.group(1) if m else ""
            except OSError:
                pass
            com = re.search(r'rdfs:comment "([^"]*)"', body)
            klass = {"iri": SITE + "/ns/meaning#" + cls, "label": cls, "comment": com.group(1) if com else None}
        cards = sorted((eid for eid, e in self.d["ents"].items() if e.get("type") == key and e.get("refs")
                        and SLUG.match(eid) and not e.get("alias_of")))
        rels, n = [], 0
        for eid in self._spread(cards, 12):
            n += 1
            because = self._because((self.d["ents"][eid].get("refs") or [None])[0])
            if because:
                rels.append({"rel": "an example", "type": None, "id": "card:" + eid,
                             "title": self.d["ents"][eid].get("name") or eid, "url": self._card_url(eid),
                             "because": because, "certainty": None, "voice": None, "strength": 1000 - n})
        schema = {"kind": key, "class": klass,
                  "relations_from": ["relation:" + k for k, t in sorted(v.items()) if key in (t.get("src_type") or [])],
                  "relations_to": ["relation:" + k for k, t in sorted(v.items()) if key in (t.get("dst_type") or [])],
                  "cards": len(cards)}
        text = "The graph's %s cards: %d. %s" % (key, len(cards), ("Closest published class: %s. %s" % (cls, klass["comment"] or ""))
                                                 if klass else "No published class is named for this kind yet.")
        return {"id": "kind:" + key, "title": key, "url": SITE + "/ns/meaning", "text": text, "verses": [],
                "relations": rels, "moves": {}, "shown": True, "schema": schema}

    # ---------------------------------------------------------------------- words
    def _word(self, key):
        lang = {"H": "hebrew", "G": "greek"}[key[0]]
        s = self.S.api_sense(self.d, {"strong": [key[1:].lstrip("0") or "0"], "lang": [lang]})
        if not s.get("found"):
            return None
        rows = ((s.get("occurrences") or {}).get("rows") or [])
        vs = [t for t in (self._from_macula(r.get("ref") or "") for r in rows[:VERSES_IN_BODY]) if t]
        text = "%s (%s), %s: %s" % (s.get("lemma"), s.get("translit") or "", s.get("lang"), s.get("short") or s.get("gloss") or "")
        if s.get("definition"):
            text += "\n" + s["definition"] + ("\n(" + s["definition_credit"] + ")" if s.get("definition_credit") else "")
        return {"id": "word:" + key, "title": "%s %s" % (key, s.get("lemma") or ""), "url": _url("/word/" + key),
                "text": text, "verses": [{"ref": "%s %d:%d" % t, "text": self._verse_text(*t), "url": _url("/p/%s.%d.%d" % t)}
                                         for t in vs], "relations": [], "moves": {}, "shown": True}

    # --------------------------------------------------------------------- themes
    def _theme(self, key):
        t = self.S.api_majortheme(self.d, {"id": [key]})
        if not t.get("found"):
            return None
        events = [x.get("title") for x in (t.get("events") or []) if x.get("listed")]
        text = (t.get("title") or key) + (": " + t["subtitle"] if t.get("subtitle") else "")
        if events:
            text += "\nEvents: " + ", ".join(e for e in events if e)
        return {"id": "theme:" + key, "title": t.get("title") or key, "url": _url(t.get("path") or "/themes/" + key),
                "text": text, "verses": [], "relations": [], "moves": {}, "shown": True}

    # ------------------------------------------------------------------ questions
    def _question(self, key):
        q = self.S.api_question(self.d, {"id": [key]})
        if not q.get("found") or q.get("shown") is False:
            return None
        parts = [q.get("question") or key, q.get("intro") or ""]
        for r in q.get("readings") or []:
            parts.append("A reading: %s. %s" % (r.get("label") or "", r.get("summary") or ""))
        return {"id": "question:" + key, "title": q.get("question") or key, "url": _url(q.get("path") or "/questions/" + key),
                "text": "\n".join(p for p in parts if p), "verses": [], "relations": [], "moves": {}, "shown": True}
