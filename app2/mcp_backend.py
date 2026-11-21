"""The MCP server's backend: the site's own answers, gathered into what app2/mcp.py serves (2026-11-03).

app2/mcp.py is the protocol and every rule (tests/test_mcp.py, a fake backend). This module is the one place that
knows the site: it calls the same functions the API calls (one source of truth, no second copy of the graph), and
turns a card's answer into items whose relations each carry the verse that makes them.

THE HOP RULES (Doug, 2026-11-03: "build the adapter with the hop rules as discussed"):
  - a hop names a relation and hands over a verse that makes it; a relation with no verse is not a hop
  - the card's relation groups, in the order the card shows them; kin, events and the event's cast among them
  - quotations and echoes are hops; readings are marked "reading" (the story echoes, anything conjectured, a judged
    parallel no editor made); a word match is marked "match" and carries its grade (plan 8.7c)
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
WORD_VERSE_LINKS = 60      # a word's verses offered as hops (12 in the answer, the rest by get_relations; 2026-11-12)
# the security seat, 2026-11-03: built items are cached (the data does not change between deploys), bounded, and the
# shown answers too, so attacker-chosen ids cannot grow memory without end
ITEM_CACHE = 512
SHOWN_CACHE = 50000
UBS_SENSES = 8                     # a word answer's UBS senses; the page has every one
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
    "It takes no doctrinal side; where a link is a reading rather than a statement of the text, it says so. Each "
    "entry below opens with fetch, and search finds a name, an event, a theme or a reference.")
START_LINKS = [("event", "card:event_jesus_temptation"), ("person", "card:david"), ("person", "card:moses"),
               ("event", "card:event_creation_of_heavens_and_earth"), ("theme", "theme:creation"),
               ("question", "question:baptism"), ("verse", "verse:John.1.1")]

RESOURCES = {
    "about": (
        "# Bible Ontology\n\nA knowledge graph of the Bible's text: people, events, places, ideas and words, and "
        "the relations between them, each citing its verse. Built on the original languages (MACULA) and read in "
        "the Berean Standard Bible. Read-only. It states what the text says and marks readings as readings; it "
        "takes no doctrinal position.\n\nEvery answer ends with links and moves, each an id `fetch` accepts. Each "
        "link's `iri` is its relation's definition in the published vocabulary; its `certainty` says how firmly "
        "the verse supports it (stated, implied, a reading, or a match of shared words with its measured grade); "
        "`voice` says whose words it rests on. Every answer carries its page's `url` and its verses, the "
        "attribution the graph's license (CC BY 4.0) asks for.\n"),
    "method": (
        "# How the graph is built\n\n- Relations are lifted from the clauses of the original-language text "
        "(MACULA) and read against the verse; where translations differ, the original decides.\n- Each relation "
        "keeps its certainty (stated, implied, a reading, or a match of shared words) and its voice: the narrator, or the speaker whose words "
        "it rests on (\"the words of Eliphaz\").\n- Readings (story echoes, judged parallels) are marked as "
        "readings and never presented as the text's own statement.\n- Machine readings are checked twice and "
        "against planted faults before they are kept; the method is described at " + SITE + "/about.\n"),
    "licensing": (
        "# Licensing\n\nThe graph: Bible Ontology (bibleontology.org), CC BY 4.0. Its sources keep their own "
        "terms, credited in their own words in every answer's `sources`: MACULA (c) Biblica, Inc., CC BY 4.0; "
        "the Berean Standard Bible, public domain; STEP Bible's lexicons, CC BY 4.0. A word's senses from the UBS "
        "dictionaries of Biblical Hebrew and New Testament Greek (United Bible Societies) are CC BY-SA 4.0, not the "
        "graph's license: an answer that carries them says so in its text and credits them in its `sources`.\n"),
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
    STOP = {"the", "a", "an", "of", "and", "or", "is", "are", "does", "do", "what", "about", "say", "bible", "in",
            "to", "on", "for", "without", "with", "by", "be", "can", "how", "why", "who"}

    def _question_hits(self, query):
        """The shown questions a query names: every content word of the query in the question's id, title or short
        name ("faith without works" -> faith-and-works; "free will" -> free-will). The site's own search has no
        question rows, so this is the MCP's door to them."""
        words = [w for w in re.findall(r"[a-z]+", query.lower()) if w not in self.STOP]
        if not words:
            return []
        out = []
        stem = lambda w: w[:-1] if w.endswith("s") and len(w) > 3 else w  # noqa: E731
        for qid, q in self.S._questions().items():
            hay = " ".join((qid.replace("-", " "), q.get("question") or "", q.get("short") or "")).lower()
            own = [w for w in qid.split("-") if w not in self.STOP]
            # every word of the query in the question, or every word of the question's own name in the query
            # ("is baptism necessary for salvation" -> baptism)
            if all(re.search(r"\b" + re.escape(stem(w)), hay) for w in words) or \
                    (own and all(re.search(r"\b" + re.escape(stem(w)), query.lower()) for w in own)):
                out.append({"id": "question:" + qid, "title": q.get("question") or qid,
                            "url": _url("/questions/" + qid)})
        return out

    def search(self, query, limit):
        out = self._question_hits(query)[:limit]
        for r in (self.S.api_search(self.d, {"q": [query]}).get("results") or []):
            if len(out) >= limit:
                break
            kind, rid, title = r.get("kind"), r.get("id"), r.get("title")
            # A WORD HIT PASSES THROUGH (P-2026-11-12-3 (2); the probe: "faith without works" gave 0 through the MCP
            # while the site found faith G4102 and works G2041): the site's word rows open as word: items
            if kind == "sense" and re.match(r"^[hg]\d+$", rid or ""):
                out.append({"id": "word:%s%s" % (rid[0].upper(), rid[1:]),
                            "title": "%s (%s%s%s)" % (title or rid, (r["lang"] + " ") if r.get("lang") else "",
                                                       rid[0].upper(), rid[1:]),
                            "url": _url("/word/%s%s" % (rid[0].upper(), rid[1:]))})
                continue
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
        # NO CARD FOR THE PHRASE, SO THE CARDS FOR ITS WORDS (P-2026-11-16-3 (1); Doug's shared conversation, Claude:
        # "'temple end times' returned only Greek word entries ... the useful temple card only turned up by chance, and
        # 'temple of God church body' returned nothing"). The site's search reads a query as one phrase; when that finds
        # no card or theme, each content word is searched alone, in the query's order, and its best cards added -- so
        # the temple theme and card come back, and church and body after them. Word entries already found stay first.
        if len(out) < limit and not any(o["id"].startswith(("card:", "theme:")) for o in out):
            words = [w for w in re.findall(r"[A-Za-z]+", query) if w.lower() not in self.STOP and len(w) >= 3]
            # a name first ("who killed Goliath": Goliath's cards before "killing" and "die"), else the query's order
            words.sort(key=lambda w: not w[0].isupper())
            if len(words) >= 2:
                seen = {o["id"] for o in out}
                for w in words:
                    took = 0
                    for r in (self.S.api_search(self.d, {"q": [w]}).get("results") or []):
                        kind, rid, title = r.get("kind"), r.get("id"), r.get("title")
                        if kind == "entity" and SLUG.match(rid or ""):
                            item = {"id": "card:" + rid, "title": title, "url": self._card_url(rid)}
                        elif kind == "mtheme" and SLUG.match(rid or ""):
                            item = {"id": "theme:" + rid, "title": title, "url": _url("/themes/" + rid)}
                        else:
                            continue
                        if item["id"] in seen:
                            continue
                        item["title"] = "%s (for “%s”)" % (item["title"], w)
                        out.append(item)
                        seen.add(item["id"])
                        took += 1
                        if took >= 3 or len(out) >= limit:
                            break
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
                # A SAYING'S LINK RESTS ON THE SAYING'S OWN VERSE (Doug's self-test, 2026-11-15: Eliphaz's sayings from
                # Job 15:25 on cited 15:1). Such a relation cites the speech's introduction ("Then Eliphaz the Temanite
                # replied", 15:1) and the saying (15:25), both rightly; the hop takes the one the other end's own
                # record cites, else the first
                refs = it.get("refs") or [None]
                own = set((self.d["ents"].get(other) or {}).get("refs") or []) if other else set()
                because = self._because(next((r for r in refs if r in own), refs[0]))
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
        speakers = self._passage_speakers(eid) if (self.d["ents"].get(eid) or {}).get("type") == "passage" else []
        for i, (sid, name, first_v, cnt) in enumerate(speakers):
            # A SPEECH LINKS TO ITS SPEAKER (P-2026-11-12-3 (1); the probe: "First speech of Eliphaz" had no link to
            # Eliphaz). Who speaks the sayings inside it, as their own relations say, each with its first verse
            rels.append({"rel": "is spoken by (%d of its sayings)" % cnt, "type": self._vt("asserted_by"),
                         "id": "card:" + sid, "title": name, "url": self._card_url(sid), "because": first_v,
                         "certainty": "stated", "voice": None, "strength": TIER_STATED * 100000 + 90000 - i})
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
        if speakers:
            moves["speaker"] = {"id": "card:" + speakers[0][0], "title": speakers[0][1],
                                "url": self._card_url(speakers[0][0])}
            text += "\nSpoken by " + " and ".join(s[1] for s in speakers) + "."
        return {"id": "card:" + eid, "title": e.get("name") or eid, "url": self._card_url(eid), "text": text,
                "verses": verses, "relations": rels, "moves": moves, "shown": True}

    # --------------------------------------------------------------------- verses
    # THE VERSE-TO-VERSE TERMS (plan 8.7c, vocabulary 1.5.0; Doug, 2026-11-12: "Six, as recommended"). Each hop
    # names a published type, split by who makes the link. Before, "earlier" went out as "quotes or echoes", stated:
    # it is the word match, about 4 in 8 real at "likely", so it is now `echoes` with its grade and certainty "match".
    # The editors' notes were one "cross-reference" for five kinds; each is now its own term, and its inverse where
    # the note runs the other way. Their section headings' lists ("parallel" in the data) point, from the section:
    # the first run called them parallel accounts, which made Isa 53:7 a parallel account of 1 Pet 2:21. `allusions` is a dict of readings by kind, which the old loop iterated as keys and
    # so never sent one; the told-again stories are left out (their term joins events, not verses).
    EDITOR_KINDS = {"quotes": ("quotes", "quotes"), "quoted by": ("quotes", "is quoted in"),
                    "points to": ("points_to", "points to"), "pointed to by": ("points_to", "is pointed to by"),
                    # the section heading's list of passages (out/xrefs.jsonl.gz, keyed to the section start): not a
                    # claim that the two tell one event -- Isa 53:7's lists 1 Pet 2:21 -- so it points, from the section
                    "parallel": ("points_to", "its section points to")}
    ALLUSION_KINDS = ("words", "images", "letters", "revelation", "history")

    def _verse_hops(self, ec, here_ref):
        """-> [(item, type, label, certainty, tier)] the verse's links to other verses, each under its term."""
        out = []
        for it in ec.get("editors") or []:
            k = self.EDITOR_KINDS.get(it.get("kind"))
            if k:
                how = "in the Berean editors' section heading" if it.get("kind") == "parallel" else "as the Berean editors note"
                out.append((it, k[0], "%s, %s" % (k[1], how), "stated", TIER_QUOTE))
        for bucket, label in (("earlier", "echoes"), ("later", "is echoed in")):
            for it in ec.get(bucket) or []:
                grade = "%s: %s" % (it.get("band") or "", it.get("band_note") or "")
                out.append((it, "echoes", "%s (a word match, %s)" % (label, grade), "match", TIER_READING))
        for it in ec.get("aligned") or []:
            if it.get("judged"):                             # an unjudged alignment is a similarity score
                # the pair judgment asks whether two verses SAY THE SAME THING (tools/meaning/pair_judge.py):
                # a parallel account, one promise said twice, or a prophecy and its quotation, so not "parallel"
                out.append((it, "says_the_same_as", "says the same as, as DeepSeek Flash judged the pair",
                            "reading", TIER_READING))
        al = ec.get("allusions") or {}
        canon = getattr(self.S, "_MCANON", {})

        def pos(ref):
            p = str(ref or "").split(".")
            try:
                return (canon.get(p[0], 99), int(p[1]), int(p[2]))
            except (IndexError, ValueError):
                return None
        mine = pos(here_ref)
        for kind in self.ALLUSION_KINDS:
            for it in (al.get(kind) or []) if isinstance(al, dict) else []:
                theirs = pos(it.get("ref"))
                if not isinstance(it, dict) or not mine or not theirs or theirs == mine:
                    continue
                label = "alludes to" if theirs < mine else "is alluded to in"
                out.append((it, "alludes_to", "%s, as %s judged" % (label, it.get("reader") or "a reader"),
                            "reading", TIER_READING))
        return out

    # A VERSE NAMES ITS SPEAKER (P-2026-11-12-3 (1); the probe of 2026-11-12: 0 of 15 speech verses named one, and
    # "who says it" is the listing's headline). Three sources, the firmest first:
    #   1. the relations that cite the verse, as the site's verse card gathers them (server.verse_card): "Eliphaz told
    #      'Eliphaz at Job 4:7'", "the serpent told 'You will not surely die'" -- a card, resolved by the graph;
    #   2. the speech the verse sits in (its passage's part_of chain): the move up, and the speech named in words;
    #   3. MACULA's own speaker annotation (out/speakers.jsonl.gz, the server's "speaks" layer): a person the verse
    #      names is matched to the card the verse page links; anyone else is named in words only, as the text names
    #      them. A divine name is ALWAYS words only ("the LORD", "God"): the speaker as the Hebrew or Greek names him,
    #      never a link this module chose (divine persons are the owner's, record by record).
    DIVINE_WORDS = {"YHWH": "the LORD", "Adonai": "the Lord", "Elohim": "God", "Theos": "God", "El": "God",
                    "Kyrios": "the Lord (God or Jesus: the Greek does not settle which)"}
    SPEAKER_TYPES = ("person", "being", "creature", "group", "people")
    PRONOUNS = {"i", "me", "you", "he", "him", "she", "her", "it", "we", "us", "they", "them", "this", "that",
                "these", "those", "who", "one", "-", "", "the", "a", "an", "the the"}   # ὁ δὲ εἶπεν: the article as "he"

    def _in_quotation(self, mref):
        """Whether the verse sits inside quotation marks (the Berean's punctuation, out/speech-depth.jsonl.gz)."""
        if getattr(self, "_depth", None) is None:
            dep = {}
            try:
                import gzip
                with gzip.open(ROOT / "out" / "speech-depth.jsonl.gz", "rt", encoding="utf-8") as f:
                    for line in f:
                        r = json.loads(line)
                        if r.get("ref"):
                            try:
                                dep[r["ref"]] = int(r.get("depth") or 0)
                            except ValueError:
                                pass
            except OSError:
                pass
            self._depth = dep
        return self._depth.get(mref, 0) >= 1

    def _passage_speakers(self, eid):
        """[(speaker id, name, first verse as a because, sayings)] for a passage card: the sayings (text records) cited
        inside its span, by their own told / asserted_by relations; most sayings first."""
        refs = self.d["ents"].get(eid, {}).get("refs") or []
        spans = [s for s in (self.S._site_span(self.d, r) for r in refs) if s]
        if not spans:
            return []
        b0 = spans[0][0]
        lo = min((s[1], s[2]) for s in spans if s[0] == b0)
        hi = max((s[3], s[4]) for s in spans if s[0] == b0)
        at, ents, rels = self.S._cards_at(), self.d["ents"], self.d["rels"]
        found = collections.OrderedDict()
        for (bb, cc, vv) in sorted(k for k in self.d["verses"] if k[0] == b0 and lo <= (k[1], k[2]) <= hi):
            for tid in at.get((bb, cc, vv), []):
                if (ents.get(tid) or {}).get("type") != "text":
                    continue
                for r in rels.get(tid, []):
                    if (r["type"] == "told" and r["dir"] == "in") or (r["type"] == "asserted_by" and r["dir"] == "out"):
                        o = ents.get(r["other"]) or {}
                        if o.get("type") in self.SPEAKER_TYPES and SLUG.match(r["other"]):
                            x = found.setdefault(r["other"], [r["other"], o.get("name") or r["other"],
                                                              {"ref": "%s %d:%d" % (bb, cc, vv),
                                                               "url": _url("/p/%s.%d.%d" % (bb, cc, vv))}, set()])
                            x[3].add(tid)
        out = [(x[0], x[1], x[2], len(x[3])) for x in found.values()]
        return sorted(out, key=lambda x: -x[3])[:4]

    def _gloss_of_lemma(self, lemma):
        if getattr(self, "_lg", None) is None:
            lg = {}
            for k, lem in (self.d.get("lemmas") or {}).items():
                g = (self.d["lex"].get(k) or {}).get("gloss")
                if lem and g and lem not in lg:
                    lg[lem] = g
            self._lg = lg
        return self._lg.get(lemma)

    def _voice(self, vc, b, c, v):
        """-> (speakers [{id or None, name, by}], speech [passage rows, smallest first], text_speakers {text id: name})"""
        speakers, text_sp = [], {}
        for r in vc.get("rels") or []:
            # a sign is told by the hand, not the mouth (2026-11-16: "Spoken by Aaron" at Exod 7:19, the LORD's words
            # to Moses, from "Aaron told the plagues of Egypt", the plagues being a sign worked by Aaron's staff)
            if r["type"] == "told" and ((self.d["ents"].get(r["b"]) or {}).get("attrs") or {}).get("kind") == "sign":
                continue
            if r["type"] == "told" and r["text_b"] and not r["text_a"] and r["ta"] in self.SPEAKER_TYPES:
                sid, name, tid = r["a"], r["an"], r["b"]
            elif r["type"] in ("asserted_by", "claimed_by") and r["text_a"] and not r["text_b"] \
                    and r["tb"] in self.SPEAKER_TYPES:
                sid, name, tid = r["b"], r["bn"], r["a"]
            else:
                continue
            text_sp.setdefault(tid, name)
            if sid not in [s["id"] for s in speakers]:
                speakers.append({"id": sid, "name": name, "by": "relation", "certainty": r.get("certainty")})
        # the speech: passages the verse's text sits in, the smallest (a part of another) first
        # a role pattern's cells and rows are passages too (rcell_, rrow_): patterns, not the speech
        # and so are a story template's stages and arcs (stage_, arc_: "Faithfulness (Tested and found faithful)"):
        # a reading of the story's shape, not the passage the words sit in
        role = lambda x: x.startswith(("stage_", "arc_")) or str(  # noqa: E731
            ((self.d["ents"].get(x) or {}).get("attrs") or {}).get("kind") or "").startswith("role")
        parts = [r for r in vc.get("rels") or [] if r["type"] == "part_of" and r["ta"] == "passage"
                 and r["tb"] in ("passage", "event") and not role(r["a"]) and not role(r["b"])]
        inner = [r["a"] for r in parts if r["a"] not in {x["b"] for x in parts}]
        outer = [r["b"] for r in parts if r["b"] not in {x["a"] for x in parts}]
        speech = list(dict.fromkeys(inner + outer))
        if not speakers:
            mref = self.S._vc_mref(self.d, b, c, v)
            names = {(n.get("at") or "").lower(): n for n in vc.get("names") or []}
            glosses = {w.get("lemma"): (w.get("g") or "") for w in vc.get("words") or []}
            # PRECISION FIRST (a sample of 1,500 verses, 2026-11-15, read by hand): the annotation's speaker is kept
            # only where this verse names him ("stated"), the verse has one speaker row, and the word is a name or a
            # divine name. Carried in from a quotation's head ("span") it credited Agrippa with Paul's words (Acts
            # 26:8) and the LORD with Abigail's (1 Sam 25:31); several rows in one verse credited "the scribe" and
            # "Pharisee" beside Jesus (John 8:7); common nouns came out as "the each man", "the some"
            rows = [r for r in ((self.d.get("layers") or {}).get(mref) or {}).get("speaks") or []
                    if r.get("by") == "stated"]
            for row in rows if len({r.get("who") for r in rows}) == 1 else []:
                who = row.get("who") or ""
                if row.get("divine"):
                    name, sid = self.DIVINE_WORDS.get(row["divine"], "God"), None
                else:
                    g = (glosses.get(who) or self._gloss_of_lemma(who) or "").split("/")[-1].strip()
                    n = names.get(g.lower())
                    if not n and not re.fullmatch(r"[A-Z][a-z]+(?: [A-Z][a-z]+)?", g):
                        continue                             # not a name: a pronoun, an article, a common noun
                    sid, name = (n["id"], n["name"]) if n else (None, g)
                if name and name not in [s["name"] for s in speakers]:
                    speakers.append({"id": sid, "name": name, "by": "stated", "certainty": "explicit"})
        # A READING, LAST (the speaker pass, 2026-11-16): only where neither a relation nor MACULA's stated speaker
        # names anyone. Two independent readers, the Mac and a blind Claude judge, named the same speaker; the
        # inner voice first, and the one relaying it as `through` (Doug's ruling on nested speech)
        if not speakers:
            mref = self.S._vc_mref(self.d, b, c, v)
            for row in ((self.d.get("layers") or {}).get(mref) or {}).get("speaker_reading") or []:
                if row.get("name") and row["name"] not in [s["name"] for s in speakers]:
                    speakers.append({"id": row.get("who"), "name": row["name"], "by": "reading",
                                     "certainty": "reading", "through": row.get("rep_name"),
                                     "through_id": row.get("rep")})
        return speakers, speech, text_sp

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
        seen = set()
        for it, rtype, label, certainty, tier in self._verse_hops(ec, ec.get("ref")):
            n += 1
            # `ref` is MACULA's numbering and `eref` already the Berean's: converting `eref` again moved every
            # quotation into a chapter the Hebrew numbers differently by one (Matt 4:15 "quotes Isa 9:3", for 9:2;
            # found 2026-11-15 beside the self-test's ranges)
            t = self._from_macula(it.get("ref") or "") if it.get("ref") else None
            if not t or t == (b, c, v) or (t, rtype) in seen:
                continue
            seen.add((t, rtype))
            tid = "%s.%d.%d" % t
            # a quotation of a range is titled as the range ("Isa 53:7-8"), the hop going to its first verse
            e = self._from_macula(it.get("end") or "") if it.get("end") else None
            title = "%s %d:%d" % t
            if e and e[0] == t[0] and (e[1], e[2]) > (t[1], t[2]):
                title += ("–%d" % e[2]) if e[1] == t[1] else ("–%d:%d" % (e[1], e[2]))
            rels.append({"rel": label, "type": self._vt(rtype), "id": "verse:" + tid, "title": title,
                         "url": _url("/p/" + tid), "because": here, "certainty": certainty, "voice": None,
                         "strength": tier * 100000 - n})
        # THE VERSE'S OWN RELATIONS (P-2026-11-12-3 (1) and (3); the probe: 143 of 300 verses answered with no link):
        # every relation that cites this verse, as the site's verse card shows them, each a hop with this verse as its
        # because. A saying's words carry their speaker's voice.
        try:
            vc = self.S.verse_card(self.d, b, c, v)
        except Exception:                                    # noqa: BLE001
            vc = {}
        speakers, speech, text_sp = self._voice(vc, b, c, v)
        # INSIDE A QUOTATION, SPEAKER UNKNOWN (Doug, 2026-11-15: "as long as the MCP clearly states what it supports
        # and then supports those things without overclaiming"): an empty voice means the narrator's words, so on
        # Matt 5:44 it would have told the agent the narrator says "love your enemies". Where the verse sits inside
        # quotation marks (out/speech-depth.jsonl.gz) and no speaker is known, its hops say a speaker the graph does
        # not name, and the answer says so in words. Measured that day: 23-41% of speech verses in the Gospels and
        # Acts name their speaker, 81% in Job.
        unnamed = not speakers and self._in_quotation(self.S._vc_mref(self.d, b, c, v))
        if unnamed:
            text_sp = collections.defaultdict(lambda: "a speaker the graph does not name")
        ents, seen_c = self.d["ents"], set()
        for s in speakers:
            if s["id"] and SLUG.match(s["id"]) and s["id"] in ents:
                seen_c.add((s["id"], "speaker"))
                rels.append({"rel": "its words are spoken by", "type": self._vt("asserted_by"), "id": "card:" + s["id"],
                             "title": s["name"], "url": self._card_url(s["id"]), "because": here,
                             "certainty": CERTAINTY.get(s["certainty"], "implied"), "voice": None,
                             "strength": TIER_STATED * 100000 + 90000})
        for r in vc.get("rels") or []:
            n += 1
            t = r["type"]
            if t in THEME_TYPES or t in ("told", "asserted_by", "claimed_by") or (r["text_a"] and r["text_b"]):
                continue
            # only what THIS verse says (the first-impression walk, 2026-11-15): a relation cited to a range that
            # merely covers the verse is the passage's, not the verse's ("Nicodemus conversation is part of Story arc"
            # on John 3:16); and patterns are not instances ("Speech act: Intercession" on Matt 5:44)
            if not any(x.get("k") == key and "–" not in (x.get("l") or "") for x in r.get("refs") or []):
                continue
            if "pattern" in (r["ta"], r["tb"]) or t in ("spoken_in", "instance_of", "recounts", "part_of"):
                continue                                     # part_of is structure: the moves carry it
            if any(x.startswith(("arc_", "stage_", "rcell_", "rrow_")) for x in (r["a"], r["b"])):
                continue                                     # a story template's arc or a role pattern: a reading of shape
            if t == "part_of" and r["ta"] == "passage":
                continue                                     # the speech: a move, below
            certainty = CERTAINTY.get(r.get("certainty"), "implied")
            tier = TIER_READING if certainty == "reading" else TIER_STATED
            if r["text_a"]:                                  # a saying's words speak of something: its voice
                ends = [(r["b"], r["bn"], r["label"], text_sp.get(r["a"]))]
            elif r["text_b"]:
                ends = [(r["a"], r["an"], "%s %s" % (r["label"], r["bn"]), text_sp.get(r["b"]))]
            else:                                            # who did what to whom: the clause, from either end
                clause = "%s %s %s" % (r["an"], r["label"], r["bn"])
                ends = [(r["a"], r["an"], clause, None), (r["b"], r["bn"], clause, None)]
            for oid, name, label, sp in ends:
                if not SLUG.match(oid or "") or oid not in ents or (oid, label) in seen_c:
                    continue
                seen_c.add((oid, label))
                rels.append({"rel": label, "type": self._vt(t), "id": "card:" + oid, "title": name,
                             "url": self._card_url(oid), "because": here, "certainty": certainty,
                             "voice": ("the words of " + sp) if sp else None,
                             "strength": tier * 100000 + 40000 - n})
        _diversify(rels)
        moves = {}
        for rel, cand in (("prev", (b, c, v - 1)), ("next", (b, c, v + 1)), ("next", (b, c + 1, 1))):
            if rel not in moves and cand in self.d["verses"]:
                moves[rel] = {"id": "verse:%s.%d.%d" % cand, "title": "%s %d:%d" % cand,
                              "url": _url("/p/%s.%d.%d" % cand)}
        # up: the smallest passage the verse's words sit in, else the event it is told in
        ev = (vc.get("setting") or {}).get("event") or {}
        if speech and speech[0] in ents:
            moves["up"] = {"id": "card:" + speech[0], "title": ents[speech[0]].get("name") or speech[0],
                           "url": self._card_url(speech[0])}
        elif SLUG.match(ev.get("id") or "") and ev["id"] in ents:
            moves["up"] = {"id": "card:" + ev["id"], "title": ev.get("title") or ev["id"], "url": self._card_url(ev["id"])}
        first = next((s for s in speakers if s["id"] and s["id"] in ents), None)
        if first:
            moves["speaker"] = {"id": "card:" + first["id"], "title": first["name"], "url": self._card_url(first["id"])}
        # the speaker and the setting in words, in the answer itself
        said = []
        if speakers:
            # the graph's own relations say whose words the verse is; MACULA's annotation says who speaks IN the
            # verse, which may be a command the narrator reports ("everything the LORD had commanded", Lev 8:36), so
            # each is worded as what it is
            rel_sp = [s["name"] for s in speakers if s["by"] == "relation"]
            ann_sp = [s["name"] for s in speakers if s["by"] == "stated"]
            read_sp = [s["name"] + (", through " + s["through"] if s.get("through") else "")
                       for s in speakers if s["by"] == "reading"]
            if rel_sp:
                said.append("Spoken by " + " and ".join(rel_sp) + ".")
            if ann_sp:
                said.append("Speaking in this verse, as the original-language annotation (MACULA) marks it: "
                            + " and ".join(ann_sp) + ".")
            if read_sp:
                said.append("Whose words these are, as a reading (an automated pass and a blind check named the "
                            "same speaker; not a stated relation): " + " and ".join(read_sp) + ".")
        elif unnamed:
            said.append("These are words spoken within the passage (inside quotation marks); the graph does not "
                        "record who speaks them, so no link here is the narrator's.")
        if speech:
            sp_names = ["“%s”" % (ents.get(p, {}).get("name") or p) for p in speech if p in ents]
            if sp_names:
                said.append("Part of " + ", within ".join(sp_names) + ".")
        hd = (vc.get("setting") or {}).get("heading") or {}
        if hd.get("title"):
            said.append("Under the Berean editors' heading “%s” (%s)." % (hd["title"], hd.get("label") or ""))
        if ev.get("title"):
            said.append("Told in the event “%s” (%s)." % (ev["title"], ev.get("telling") or ""))
        body = (text or "") + ("\n" + " ".join(said) if said else "")
        return {"id": "verse:" + key, "title": "%s %d:%d" % (b, c, v), "url": here["url"], "text": body,
                "verses": [dict(here, text=text)], "relations": rels, "moves": moves, "shown": True,
                "speakers": [dict({"name": s["name"], "id": ("card:" + s["id"]) if s["id"] else None, "by": s["by"]},
                                  **({"through": s["through"]} if s.get("through") else {}))
                             for s in speakers]}

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
        if "verse" in (t.get("src_type") or []):
            return self._verse_relation(key, t, dfn)
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

    # A verse-to-verse term's examples come from verses, since no record carries it: these verses are known to hold
    # quotations, parallels, echoes and allusions, spread across both testaments (plan 8.7c)
    VERSE_EXAMPLES = ("Matt.4.4", "Matt.14.17", "Isa.53.7", "Rev.5.6", "Rom.3.10", "Heb.1.5", "Acts.2.25", "Matt.1.23",
                      "Mark.1.2", "John.19.36", "Matt.21.42", "1Pet.2.6", "Ps.22.1", "Luke.4.18", "Gal.3.16",
                      "Rom.9.33", "Mark.6.38", "Ps.2.7", "Deut.8.3", "Isa.40.3")

    def _verse_relation(self, key, t, dfn):
        rels = []
        for vk in self.VERSE_EXAMPLES:
            got = self._verse(vk) or {}
            for r in got.get("relations") or []:
                if r.get("type") == key and len(rels) < 12:
                    rels.append(dict(r, rel="%s %s %s" % (got.get("title"), r.get("rel"), r.get("title")),
                                     strength=1000 - len(rels)))
        schema = {"iri": SITE + "/ns/relation/" + key, "label": t.get("label"), "inverse": t.get("inverse"),
                  "definition": dfn, "category": t.get("category"), "group": t.get("group"),
                  "domain": ["kind:verse"], "range": ["kind:verse"], "class": "https://bibleontology.org/ns/biblio#Segment",
                  "instances": None, "vocabulary_version": self.data_version}
        text = ("%s (%s). %s\nInverse: %s. Joins one verse to another (a biblio:Segment); derived for each verse, not "
                "counted as records. Examples follow as links, each from its verse." % (
                    t.get("label") or key, key, dfn, t.get("inverse") or "none"))
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
        # UBS's senses (CC BY-SA, not the graph's CC BY): marked in the text, and its credit added to this answer's
        # sources only (app2/ubs.py)
        u, extra = s.get("ubs"), []
        if u and u.get("senses"):
            text += "\nIts senses in the UBS dictionary (%s, not the graph's license):" % u["licence"]
            for x in u["senses"][:UBS_SENSES]:
                text += "\n- %s: %s [%s; %d verses]" % ("; ".join(x["glosses"]) or "", x["short"],
                                                       ", ".join(dm["label"] for dm in x["domains"]), len(x["refs"]))
            if len(u["senses"]) > UBS_SENSES:
                text += "\n- and %d more senses on the page" % (len(u["senses"]) - UBS_SENSES)
            extra = [{"name": u["credit"], "licence": u["licence"] + " (" + u["licence_url"] + "). " + u["edited"],
                      "url": u["url"]}]
        if s.get("definition"):
            text += "\n" + s["definition"] + ("\n(" + s["definition_credit"] + ")" if s.get("definition_credit") else "")
        # THE WORD'S WHOLE COUNT, IN WORDS (Doug's self-test in Claude, 2026-11-15: "the graph's own verse links for G26
        # number only 60, not 106 ... some may not be yet linked"). 60 is a page of links, not a count; say both
        occ = s.get("occurrences") or {}
        if occ.get("total"):
            text += "\nUsed in %d verses%s. Its links list the first %d of them in the site's order; the page lists every one." % (
                occ["total"], " across %d books" % occ["books"] if occ.get("books") else "",
                min(WORD_VERSE_LINKS, occ["total"]))
        # A WORD'S NEXT HOPS (2026-11-12: get_word("G26") answered with 0 links, a dead end for an agent; found preparing
        # the directories' example prompts). First the cards that gather the word, then the verses that use it, each
        # with a verse. Neither is a typed relation in the vocabulary, so each goes with its label and no iri: a card
        # gathering its words is the graph's grouping (certainty None, never "stated"); a verse using the word is what
        # the text holds. The Septuagint equivalents and the lexicon's "compare" carry no verse, so they stay out
        # (nothing without scripture).
        first = self._because("%s %d:%d" % vs[0]) if vs else None
        rels, cards = [], set()
        for n, c in enumerate(s.get("concepts") or []):
            # an old id names its card once, by the card's own id (G26 listed "charity" and "love", one card)
            cid = (self.d.get("renamed") or {}).get(c.get("id"), c.get("id"))
            if first and SLUG.match(cid or "") and cid not in cards:
                cards.add(cid)
                rels.append({"rel": "is one of the words the card for %s gathers" % (c.get("name") or cid),
                             "type": None, "id": "card:" + cid, "title": c.get("name"), "url": self._card_url(cid),
                             "because": first, "certainty": None, "voice": None, "strength": 2000 - n})
        used = []                                      # the word's verses, in the site's order, 60 at most to page through
        for r in rows[:WORD_VERSE_LINKS]:
            t = self._from_macula(r.get("ref") or "")
            if t and t not in used:
                used.append(t)
        for n, t in enumerate(used):
            b = {"ref": "%s %d:%d" % t, "url": _url("/p/%s.%d.%d" % t)}
            rels.append({"rel": "is used in", "type": None, "id": "verse:%s.%d.%d" % t, "title": b["ref"],
                         "url": b["url"], "because": b, "certainty": "stated", "voice": None, "strength": 1000 - n})
        return {"id": "word:" + key, "title": "%s %s" % (key, s.get("lemma") or ""), "url": _url("/word/" + key),
                "text": text, "verses": [{"ref": "%s %d:%d" % t, "text": self._verse_text(*t), "url": _url("/p/%s.%d.%d" % t)}
                                         for t in vs], "relations": rels, "moves": {}, "shown": True,
                "sources_extra": extra}

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
