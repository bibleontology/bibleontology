"""The ontology as an in-memory graph.

At the sizes this project will reach (thousands of people, tens of thousands of
edges) an adjacency dict is faster to load and simpler to reason about than a
graph database, so the whole thing is built at startup from the JSONL files.
The Store deliberately keeps no state beyond what those files contain, so
reloading after an edit is just `Store.load()` again.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field

from .books import BOOK_ORDER
from .corpus import Corpus, get_corpus
from .refs import RefError, parse_ref
from .schema import (
    Person,
    name_variants,
    Relation,
    Vocabulary,
    load_persons,
    load_relations,
    load_vocabulary,
)


@dataclass
class Edge:
    """A relation as traversed, remembering which way it was crossed."""

    relation: Relation
    other: str
    outgoing: bool

    @property
    def type(self) -> str:
        return self.relation.type


@dataclass
class Store:
    people: dict[str, Person] = field(default_factory=dict)
    relations: list[Relation] = field(default_factory=list)
    vocab: Vocabulary = None  # type: ignore[assignment]
    corpus: Corpus = None  # type: ignore[assignment]
    _out: dict[str, list[Relation]] = field(default_factory=lambda: defaultdict(list))
    _in: dict[str, list[Relation]] = field(default_factory=lambda: defaultdict(list))
    _parent_index: dict | None = None

    # -- construction ----------------------------------------------------
    @classmethod
    def load(cls) -> "Store":
        store = cls(
            people=load_persons(),
            relations=load_relations(),
            vocab=load_vocabulary(),
            corpus=get_corpus(),
        )
        store.reindex()
        return store

    def reindex(self) -> None:
        self._out = defaultdict(list)
        self._in = defaultdict(list)
        self._parent_index = None
        # Built on first use and reused: the word index costs one pass over the
        # corpus, and each entity's verse set costs one regex over a short
        # candidate list.
        self._words = None
        self._texts = {}
        self._verses_cache = {}
        for rel in self.relations:
            self._out[rel.src].append(rel)
            self._in[rel.dst].append(rel)

    # -- traversal -------------------------------------------------------
    def edges(self, pid: str) -> list[Edge]:
        """Every relation touching a person, from that person's point of view."""
        out = [Edge(r, r.dst, True) for r in self._out.get(pid, [])]
        out += [Edge(r, r.src, False) for r in self._in.get(pid, [])]
        return out

    def neighbors(self, pid: str, types: set[str] | None = None) -> set[str]:
        return {
            e.other
            for e in self.edges(pid)
            if types is None or e.type in types
        }

    def ego(self, pid: str, depth: int = 1, types: set[str] | None = None) -> set[str]:
        """Person ids within `depth` hops, including the centre."""
        seen = {pid}
        frontier = {pid}
        for _ in range(max(0, depth)):
            nxt: set[str] = set()
            for node in frontier:
                nxt |= self.neighbors(node, types) - seen
            if not nxt:
                break
            seen |= nxt
            frontier = nxt
        return seen

    def path(self, a: str, b: str) -> list[str]:
        """Shortest relation path between two people, ignoring direction."""
        if a not in self.people or b not in self.people:
            return []
        if a == b:
            return [a]
        prev: dict[str, str] = {a: ""}
        queue = deque([a])
        while queue:
            node = queue.popleft()
            for other in self.neighbors(node):
                if other in prev:
                    continue
                prev[other] = node
                if other == b:
                    chain = [b]
                    while chain[-1] != a:
                        chain.append(prev[chain[-1]])
                    return list(reversed(chain))
                queue.append(other)
        return []

    def subgraph(self, ids: set[str]) -> list[Relation]:
        return [r for r in self.relations if r.src in ids and r.dst in ids]

    def degree(self, pid: str) -> int:
        return len(self._out.get(pid, [])) + len(self._in.get(pid, []))

    # -- inference -------------------------------------------------------
    def _parents(self) -> dict[str, dict[str, set]]:
        """child -> {"f": {fathers}, "m": {mothers}}.

        Sets, not single values: scripture gives some people two fathers and the
        ontology preserves that disagreement rather than resolving it (Kish;
        Joseph the husband of Mary). Collapsing to one would silently pick a
        side and, worse, make shared-parent inference miss real siblings.
        """
        if getattr(self, "_parent_index", None) is None:
            idx: dict[str, dict[str, set]] = defaultdict(lambda: {"f": set(), "m": set()})
            for rel in self.relations:
                if rel.type == "father_of":
                    idx[rel.dst]["f"].add(rel.src)
                elif rel.type == "mother_of":
                    idx[rel.dst]["m"].add(rel.src)
            self._parent_index = idx
        return self._parent_index

    def derived_siblings(self, pid: str) -> list[Relation]:
        """Siblinghood implied by shared parentage, computed rather than stored.

        Two people who are both children of one parent are siblings whether or
        not any verse says so. Recording that would add roughly a thousand edges
        derived entirely from ones already present -- eleven times the number the
        text states outright -- so it is inferred on demand instead. These
        relations are never written to disk; `source` is "derived" and the
        citations are the parentage verses the inference rests on.

        Everything inferred here is `sibling_of`, never `half_sibling_of`.
        Scripture states plain siblinghood 89 times and half-siblinghood 3, and
        calls all of Jacob's sons brethren without pressing which mother; the
        distinction is one it makes only when something turns on it. Splitting
        inferred siblings into two types therefore invented a difference the
        text does not draw, and made Judah look like a different kind of brother
        to Joseph than Levi purely because one bond happens to be stated. What
        is actually shared still goes in the note, so the detail is available
        without being structural.
        """
        parents = self._parents()
        mine = parents.get(pid) or {}
        if not mine:
            return []

        explicit = {
            frozenset((r.src, r.dst))
            for r in self.relations
            if r.type in ("sibling_of", "half_sibling_of")
        }

        # everyone sharing at least one recorded parent with this person
        candidates: set[str] = set()
        for slot, parents_in_slot in mine.items():
            rel_type = "father_of" if slot == "f" else "mother_of"
            for parent in parents_in_slot:
                for rel in self._out.get(parent, []):
                    if rel.type == rel_type and rel.dst != pid:
                        candidates.add(rel.dst)

        def cite(child: str) -> list[str]:
            refs: list[str] = []
            for rel in self._in.get(child, []):
                if rel.type in ("father_of", "mother_of"):
                    for ref in rel.refs[:1]:
                        if ref not in refs:
                            refs.append(ref)
            return refs

        out: list[Relation] = []
        for other in sorted(candidates):
            if frozenset((pid, other)) in explicit:
                continue  # the text says it; the stated edge stands on its own
            theirs = parents.get(other) or {"f": set(), "m": set()}
            shared = {s: mine[s] & theirs[s] for s in ("f", "m") if mine[s] & theirs[s]}
            if not shared:
                continue  # only reachable through inconsistent data; say nothing
            differs = [
                s for s in ("f", "m")
                if s not in shared and mine[s] and theirs[s]
            ]

            def name(pid_: str) -> str:
                return self.people[pid_].name if pid_ in self.people else pid_

            def named(slot: str) -> str:
                return " / ".join(sorted(name(p) for p in shared[slot]))

            # Always sibling_of. What is actually shared goes in the note, so
            # the detail survives without becoming a second relationship type.
            rtype = "sibling_of"
            if len(shared) == 2:
                note = f"Inferred: both are children of {named('f')} and {named('m')}."
            elif differs:
                slot = next(iter(shared))
                note = (
                    f"Inferred: both are children of {named(slot)}, by different "
                    f"{'mothers' if slot == 'f' else 'fathers'}."
                )
            else:
                slot = next(iter(shared))
                note = (
                    f"Inferred: both are children of {named(slot)}. The other "
                    "parent is not recorded for at least one of them."
                )
            a, b = sorted((pid, other))
            out.append(
                Relation(
                    src=a,
                    type=rtype,
                    dst=b,
                    refs=cite(pid) + [r for r in cite(other) if r not in cite(pid)],
                    certainty="implied",
                    note=note,
                    source="derived",
                )
            )
        return out

    def _needles(self, pid: str) -> set[str]:
        entity = self.people.get(pid)
        if entity is None:
            return set()
        return {
            v.lower() for n in entity.names() for v in name_variants(n) if len(v) > 2
        }

    def _name_matcher(self, needles: set[str]) -> re.Pattern[str] | None:
        """Whole-name matching, so Sheba does not match Beer-sheba.

        A plain `in` test made every Sheba a match for Beer-sheba, Bath-sheba,
        Elisheba and Jehosheba, and `\\b` alone does not help because a hyphen
        is a word boundary. The lookarounds reject an adjacent letter *or*
        hyphen, which is what distinguishes a name from a name it is buried in.
        """
        if not needles:
            return None
        alts = "|".join(
            re.escape(n) for n in sorted(needles, key=len, reverse=True)
        )
        return re.compile(rf"(?<![A-Za-z-])({alts})(?![A-Za-z-])", re.I)

    def _cited_verses(self, pid: str) -> set[str]:
        """Verses the graph cites for a relation involving this entity."""
        out: set[str] = set()
        for rel in self.relations:
            if rel.src != pid and rel.dst != pid:
                continue
            for ref in rel.refs:
                try:
                    out.update(str(v) for v in self.corpus.expand(parse_ref(ref)))
                except RefError:
                    continue
        return out

    # -- textual interaction ---------------------------------------------
    #
    # How much of the text two people actually share, which is not what their
    # citations record. Citations are *evidence*: extraction stores the minimum
    # needed to establish a relation, so a pair who dominate a book carry no
    # more references than a pair named once. Jesus/Peter and Jesus/Philip both
    # cite four verses. The text does not treat them alike, and neither should
    # the diagram.

    def _word_index(self) -> dict[str, set[str]]:
        """word -> verses containing it, built once.

        Running each entity's name pattern over 31,000 verses would be 51M
        regex applications. Looking up the name's words first narrows that to a
        handful of candidate verses, which the pattern then confirms.
        """
        if self._words is None:
            index: dict[str, set[str]] = defaultdict(set)
            texts: dict[str, str] = {}
            for verse in self.corpus.iter_verses():
                ref = str(verse.id)
                texts[ref] = verse.text
                for word in re.findall(r"[a-z]+", verse.text.lower()):
                    index[word].add(ref)
            self._words = index
            # Corpus.text() is keyed by VerseId, and these candidates are plain
            # refs, so the text is kept here rather than parsed back each time.
            self._texts = texts
        return self._words

    def entity_verses(self, pid: str) -> set[str]:
        """Verses naming this entity, with the same disambiguation as mentions."""
        if pid in self._verses_cache:
            return self._verses_cache[pid]

        needles = self._needles(pid)
        matcher = self._name_matcher(needles)
        if matcher is None:
            self._verses_cache[pid] = set()
            return self._verses_cache[pid]

        index = self._word_index()
        candidates: set[str] = set()
        for needle in needles:
            words = re.findall(r"[a-z]+", needle)
            if not words:
                continue
            hit = index.get(words[0], set())
            for word in words[1:]:
                hit = hit & index.get(word, set())
            candidates |= hit

        namesakes = self.namesakes(pid)
        mine = self._cited_verses(pid)
        theirs: set[str] = set()
        for other in namesakes:
            theirs |= self._cited_verses(other)
        theirs -= mine

        found = {
            ref
            for ref in candidates
            if ref not in theirs and matcher.search(self._texts.get(ref, ""))
        }

        if namesakes:
            # For a shared name, a bare match is not evidence about *which* one.
            # Counting them made Simon the brother of Jesus look like a constant
            # companion by absorbing Simon Peter -- John 13:36, 18:15, 21:7 all
            # landed on him. So keep only what the graph can place: verses cited
            # for this entity, or verses in a chapter where it is cited and no
            # namesake is. Same three tiers as `mentions`, applied to counting.
            def chapters(refs: set[str]) -> set[str]:
                return {r.rsplit(":", 1)[0] for r in refs}

            placed = chapters(mine) - chapters(theirs)
            found = {
                ref
                for ref in found
                if ref in mine or ref.rsplit(":", 1)[0] in placed
            }

        self._verses_cache[pid] = found
        return found

    def interaction(self, a: str, b: str) -> tuple[int, int]:
        """(verses naming both, chapters naming both but no shared verse).

        Chapter overlap is counted separately and weighted lower by callers:
        appearing in one scene is weaker evidence than appearing in one
        sentence, but it is not nothing — Jesus and his brothers share three
        chapters and no verse at all.
        """
        va, vb = self.entity_verses(a), self.entity_verses(b)
        shared = va & vb
        chapter = lambda refs: {r.rsplit(":", 1)[0] for r in refs}  # noqa: E731
        both_ch = chapter(va) & chapter(vb)
        return len(shared), len(both_ch - chapter(shared))

    def namesakes(self, pid: str) -> list[str]:
        """Other entities sharing a surface name with this one."""
        mine = self._needles(pid)
        if not mine:
            return []
        return [
            other
            for other in self.people
            if other != pid and self._needles(other) & mine
        ]

    def mentions(self, pid: str, limit: int = 400) -> list[dict]:
        """Every verse naming this entity, in canonical order.

        A concordance, computed rather than stored: it is derivable from the
        corpus and the entity's names, and storing thirty thousand of these
        would bury the relations that carry actual claims. This is what answers
        "show me a place and let me read its history" — Marah matters because of
        Exod 15:23, whether or not any named person attaches to it.

        **Disambiguation is applied.** Matching is still by name, so on its own
        it cannot tell four Shebas apart -- and it used to hand all of them the
        same 86 verses, including Abraham's Beer-sheba. What the graph does know
        is which verses it cites for whom, so each mention is classified:

        - `attested`     -- a relation of *this* entity cites the verse
        - `same_chapter` -- this entity is attested in that chapter and no
                            namesake is
        - `name_only`    -- the name matches and nothing more is known

        A verse attested to a *namesake* is dropped, because the graph has
        positively placed it with someone else. Everything else is kept and
        marked, since an uncited verse may still be this entity and saying so
        would be a guess. That means the list sharpens on its own as coverage
        improves: once Sheba the kingdom exists and Ps 72:10 is cited to it,
        that verse leaves the rebel's list without anyone revisiting this code.

        The middle tier exists because the strict split was accurate and
        useless: only 2 Sam 20:1-2 are cited for Sheba son of Bichri, so the
        rest of his own revolt landed in the same bucket as the queen of Sheba.
        "In a chapter where this entity is attested and no namesake is" is a
        fact about the graph, not a judgment about the text, which is why it is
        allowed to be its own tier rather than folded into `attested`.
        """
        matcher = self._name_matcher(self._needles(pid))
        if matcher is None:
            return []

        mine = self._cited_verses(pid)
        theirs: set[str] = set()
        for other in self.namesakes(pid):
            theirs |= self._cited_verses(other)
        theirs -= mine  # a shared citation is not evidence against this entity

        def chapters(refs: set[str]) -> set[tuple[str, int]]:
            out = set()
            for r in refs:
                try:
                    vid = self.corpus.expand(parse_ref(r))[0]
                except (RefError, IndexError):
                    continue
                out.add((vid.book, vid.chapter))
            return out

        my_chapters = chapters(mine) - chapters(theirs)

        out = []
        for verse in self.corpus.iter_verses():
            ref = str(verse.id)
            if ref in theirs or not matcher.search(verse.text):
                continue
            if ref in mine:
                attribution = "attested"
            elif (verse.id.book, verse.id.chapter) in my_chapters:
                attribution = "same_chapter"
            else:
                attribution = "name_only"
            out.append(
                {
                    "ref": ref,
                    "pretty": verse.id.pretty(),
                    "text": verse.text,
                    "attribution": attribution,
                }
            )
            if len(out) >= limit:
                break
        return out

    # -- presentation ----------------------------------------------------
    def describe(self, rel: Relation, of: str | None = None) -> str:
        """Render a relation as a sentence, from `of`'s point of view if given."""
        rtype = self.vocab.types.get(rel.type)
        label = rtype.label if rtype else rel.type.replace("_", " ")
        src = self.people[rel.src].name if rel.src in self.people else rel.src
        dst = self.people[rel.dst].name if rel.dst in self.people else rel.dst

        # Symmetric relations read the same either way, so always lead with the
        # person being viewed rather than whichever id sorted first on disk.
        if rtype and rtype.symmetric:
            if of == rel.dst:
                src, dst = dst, src
            return f"{src} {label} {dst}"

        if of == rel.dst and rtype and rtype.inverse:
            return f"{dst} {self._inverse_label(rtype, rel.dst)} {src}"
        return f"{src} {label} {dst}"

    def _inverse_label(self, rtype, subject_id: str) -> str:
        """Resolve gendered alternatives like 'is the son/daughter of'."""
        label = rtype.inverse
        if "/" not in label:
            return label
        person = self.people.get(subject_id)
        gender = person.gender if person else "unknown"
        # "is the son/daughter of" -> pick the matching half of the slashed pair
        def choose(match: str) -> str:
            male, female = match.split("/", 1)
            if gender == "m":
                return male
            if gender == "f":
                return female
            return match

        return re.sub(r"\S+/\S+", lambda m: choose(m.group(0)), label)

    def evidence(self, rel: Relation) -> list[dict]:
        """The cited verses, with their text, for display."""
        out = []
        for ref in rel.refs:
            try:
                parsed = parse_ref(ref)
            except RefError:
                out.append({"ref": ref, "error": "unparseable reference"})
                continue
            verses = [
                {"id": str(v.id), "pretty": v.id.pretty(), "text": v.text}
                for v in (self.corpus.verses_for(ref) or [])
            ]
            out.append({"ref": str(parsed), "verses": verses})
        return out

    def first_ref_sort_key(self, person: Person) -> tuple:
        best = None
        for ref in person.refs:
            try:
                p = parse_ref(ref)
            except RefError:
                continue
            key = (BOOK_ORDER.get(p.book, 999), p.start_chapter, p.start_verse)
            if best is None or key < best:
                best = key
        return best or (999, 999, 999)

    # -- serialization for the web app -----------------------------------
    def to_cytoscape(self, ids: set[str] | None = None) -> dict:
        ids = ids if ids is not None else set(self.people)
        nodes = [
            {
                "data": {
                    "id": pid,
                    "label": self.people[pid].name,
                    "etype": self.people[pid].type,
                    "gender": self.people[pid].gender,
                    "roles": self.people[pid].roles,
                    "era": self.people[pid].era,
                    "degree": self.degree(pid),
                }
            }
            for pid in sorted(ids)
            if pid in self.people
        ]
        edges = []
        for i, rel in enumerate(self.subgraph(ids)):
            rtype = self.vocab.types.get(rel.type)
            shared, chapters = self.interaction(rel.src, rel.dst)
            edges.append(
                {
                    "data": {
                        "id": f"e{i}",
                        "source": rel.src,
                        "target": rel.dst,
                        "type": rel.type,
                        "label": rtype.label if rtype else rel.type,
                        "category": rtype.category if rtype else "other",
                        "certainty": rel.certainty,
                        "refs": rel.refs,
                        "note": rel.note,
                        # How much text the pair actually share, which the
                        # citations do not measure. Drives tie strength.
                        "shared_verses": shared,
                        "shared_chapters": chapters,
                    }
                }
            )
        return {"nodes": nodes, "edges": edges}

    def stats(self) -> dict:
        by_type: dict[str, int] = defaultdict(int)
        by_cat: dict[str, int] = defaultdict(int)
        for rel in self.relations:
            by_type[rel.type] += 1
            rtype = self.vocab.types.get(rel.type)
            by_cat[rtype.category if rtype else "other"] += 1
        by_entity_type: dict[str, int] = defaultdict(int)
        for entity in self.people.values():
            by_entity_type[entity.type] += 1
        return {
            "people": len(self.people),  # kept for callers that predate places
            "entities": len(self.people),
            "by_entity_type": dict(sorted(by_entity_type.items(), key=lambda kv: -kv[1])),
            "relations": len(self.relations),
            "types_used": len(by_type),
            "types_available": len(self.vocab.types),
            "by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
            "by_category": dict(sorted(by_cat.items(), key=lambda kv: -kv[1])),
        }
