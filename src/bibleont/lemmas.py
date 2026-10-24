"""Which original-language word a node is about, decided by several methods at once.

Replaces the single-signal assignment in `lemma.py`, which scored only WHERE a
lemma appears -- the intersection of a node's cited verses -- and never what it
means. That is sound with several citations and a coin flip with one, and most
nodes have one. The result was 4% coverage and wrong where it existed:

    barley, cockle, wheat   all H0890, glossed "foul weed"   (Job 31:40 only)
    ark, cubit              both H8392, glossed "ark"        (overlapping refs)
    afflicted, friend, pity all H4523                        (Job 6:14 only)

## Several methods, and the agreement is the confidence

2026-09-02: try a couple of deterministic approaches to find the candidates,
in case one algorithm misses some that really have the same meaning -- the
rule that several weak signals on one target are not
several weak signals, they are one strong one, and per-item ranking cannot see
it.

What matters is that they fail differently, or they corroborate nothing:

    gloss       the node's name against the word's English gloss.
                Fails on rendering differences -- `cockle` / "foul weed".
    stem        the same, on stems, so `afflicted` reaches "affliction".
                Fails on suppletion and on multi-word glosses.
    verse-fit   which lemma appears in exactly this node's cited verses,
                weighted by rarity elsewhere. Fails on single-citation nodes.
    eliminate   what is unclaimed in the verse once the confident matches are
                taken. Fails when the languages are not near one-to-one.

**Every vote is stored, not just the winner.** When an assignment turns out
wrong in three months the question is which signal misled us, and a bare lemma
field cannot answer it -- which is exactly why the existing 320 are
untrustworthy rather than merely wrong.

## Hebrew and Greek stay separate

The decision: use a mapping between Hebrew and Greek so that they are
different physical nodes mapped together. So H2617 and G1656 are two
nodes with an edge between them, never one node. Merging them would destroy a
distinction no later pass could recover -- the same reasoning that kept
`jesus` and `jesus_incarnate` apart -- and a mapping edge can carry its
evidence and be argued with, which a merge cannot.

## A test for the mapping layer, once it exists

2026-09-02: a test for later is that if two words are close to each other and
a third is close to one and was not measured against the other, take a look.

Note what it is and is not. **It does not assert the third edge.** A close to
B and C close to A says nothing about C and B -- that is the transitivity trap
`docs/PRINCIPLES.md` records for symbolic relations, where the seed and the
sword both signify the word of God and no passage relates them. What it does
is find a pair the comparison set never evaluated, and hand it to whatever
measures pairs.

So it is a coverage check on the candidate generator, not an inference rule,
and it is the same fixed-point shape as any iterative resolution: resolving one
pair changes which other pairs are visible, so the sweep has to be re-run
until it stops finding anything.

Two places it will apply:

    lemma assignment   two nodes resolving to one lemma are candidates for
                       the same node. A third close to one of them and never
                       compared to the other is a duplicate hiding behind a
                       gap in the comparison set.

    H-G mapping        if a Hebrew lemma maps to a Greek one on the evidence
                       of an NT quotation, and a second Greek word renders the
                       same Hebrew elsewhere, the two Greek words were
                       probably never compared to each other.

Not built. It needs the mapping layer first, and it needs every comparison
recorded rather than only the ones that scored -- an unmeasured pair and a
pair measured at zero look identical unless both are written down.

Mapping is NOT done here. It needs its own evidence, and the strongest is
where the New Testament quotes the Old: the Greek word chosen for that Hebrew
word is the text's own equivalence rather than ours.
"""

from __future__ import annotations

import collections
import json
import re
import sys
from dataclasses import dataclass, field

from .paths import ROOT

STEP = ROOT / "data" / "raw" / "stepbible"

# TAHOT/TAGNT book codes against this project's.
BOOKS = {
    "Gen": "Gen", "Exod": "Exo", "Lev": "Lev", "Num": "Num", "Deut": "Deu",
    "Josh": "Jos", "Judg": "Jdg", "Ruth": "Rut", "1Sam": "1Sa", "2Sam": "2Sa",
    "1Kgs": "1Ki", "2Kgs": "2Ki", "1Chr": "1Ch", "2Chr": "2Ch", "Ezra": "Ezr",
    "Neh": "Neh", "Esth": "Est", "Job": "Job", "Ps": "Psa", "Prov": "Pro",
    "Eccl": "Ecc", "Song": "Sng", "Isa": "Isa", "Jer": "Jer", "Lam": "Lam",
    "Ezek": "Ezk", "Dan": "Dan", "Hos": "Hos", "Joel": "Jol", "Amos": "Amo",
    "Obad": "Oba", "Jonah": "Jon", "Mic": "Mic", "Nah": "Nam", "Hab": "Hab",
    "Zeph": "Zep", "Hag": "Hag", "Zech": "Zec", "Mal": "Mal",
    "Matt": "Mat", "Mark": "Mrk", "Luke": "Luk", "John": "Jhn", "Acts": "Act",
    "Rom": "Rom", "1Cor": "1Co", "2Cor": "2Co", "Gal": "Gal", "Eph": "Eph",
    "Phil": "Php", "Col": "Col", "1Thess": "1Th", "2Thess": "2Th",
    "1Tim": "1Ti", "2Tim": "2Ti", "Titus": "Tit", "Phlm": "Phm", "Heb": "Heb",
    "Jas": "Jas", "1Pet": "1Pe", "2Pet": "2Pe", "1John": "1Jn", "2John": "2Jn",
    "3John": "3Jn", "Jude": "Jud", "Rev": "Rev",
}
INV = {v: k for k, v in BOOKS.items()}

# H9xxx and G9xxx are grammatical particles -- prefixes, suffixes, punctuation
# -- not words. `friend` came back as H9006H7453H9023, which is "from" + friend
# + "his" concatenated, because nothing was stripping them.
PARTICLE = re.compile(r"^[HG]9\d{3}")
STOP = {"the", "of", "a", "an", "and", "to", "in", "for", "s", "his", "her",
        "their", "its", "it", "he", "she", "they", "them", "him", "from",
        "with", "is", "are", "was", "were", "be", "unto", "upon"}


@dataclass
class Word:
    ref: str            # "Gen 6:14"
    lemma: str          # "H8392"
    gloss: str          # "an ark of"


@dataclass
class Vote:
    method: str
    lemma: str
    score: float
    why: str = ""


@dataclass
class Result:
    node: str
    lemma: str = ""
    confidence: float = 0.0
    votes: list = field(default_factory=list)
    state: str = "unresolved"       # agreed | split | unresolved | untagged
    candidates: list = field(default_factory=list)


def _stem(w: str) -> str:
    """Crude and deliberate: enough to join afflicted/affliction, no more."""
    for suf in ("edness", "ations", "ation", "ings", "ing", "eth", "ies",
                "ied", "es", "ed", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if w not in STOP}


def load_tagged(books: set | None = None) -> dict:
    """Every tagged word, keyed by this project's verse reference.

    Reads the STEPBible amalgamated texts. Not redistributed -- the licence
    asks that people be pointed at github.com/STEPBible instead -- so this
    reads what is already on disk and writes only derived assignments.
    """
    out: dict = collections.defaultdict(list)
    want = {BOOKS[b] for b in books} if books else None
    for f in sorted(STEP.glob("TA*.txt")):
        greek = f.name.startswith("TAGNT")
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "#" not in line[:24] or "\t" not in line:
                    continue
                cols = line.split("\t")
                head = cols[0].split("#")[0]
                bits = head.split(".")
                if len(bits) != 3 or (want and bits[0] not in want):
                    continue
                book = INV.get(bits[0])
                if not book or not bits[1].isdigit() or not bits[2].isdigit():
                    continue
                # THE TWO TEXTS ARE LAID OUT DIFFERENTLY and reading both
                # with one column map silently dropped the entire New
                # Testament -- 21,178 verses looked like the whole Bible and
                # was the Old alone.
                #
                #   TAHOT  [1] ref  [2] Hebrew  [3] translit  [4] gloss  [5] {lemma}
                #   TAGNT  [1] ref  [2] Greek   [3] gloss     [4] G0976=N-NSF
                if greek:
                    gloss = (cols[2] if len(cols) > 2 else "").strip()
                    raw = (cols[3] if len(cols) > 3 else "")
                else:
                    gloss = (cols[3] if len(cols) > 3 else "").strip()
                    raw = (cols[4] if len(cols) > 4 else "")
                for lem in re.findall(r"[HG]\d{4}[A-Z]?", raw):
                    if PARTICLE.match(lem):
                        continue
                    out[f"{book} {bits[1]}:{bits[2]}"].append(
                        Word(f"{book} {bits[1]}:{bits[2]}", lem, gloss))
                    break            # the first real lemma is the word's own
    return out


def assign(node_id: str, name: str, refs: list, tagged: dict,
           freq: collections.Counter, claimed: dict | None = None) -> Result:
    """Score one node against every lemma appearing in its cited verses."""
    res = Result(node=node_id)
    here: dict = {}
    for r in refs or []:
        for w in tagged.get(r, []):
            here.setdefault(w.lemma, []).append(w)
    if not here:
        res.state = "untagged"
        return res

    label = _words(name.replace("_", " "))
    stems = {_stem(w) for w in label}
    n_refs = len({r for r in (refs or []) if r in tagged})

    for lem, ws in here.items():
        gl = _words(" ".join(w.gloss for w in ws))
        # 1. gloss overlap
        if label and gl:
            j = len(label & gl) / len(label | gl)
            if j:
                res.votes.append(Vote("gloss", lem, j, ws[0].gloss[:40]))
        # 2. stem overlap, which reaches inflections gloss overlap cannot
        gs = {_stem(w) for w in gl}
        if stems and gs and (stems & gs) and not (label & gl):
            res.votes.append(Vote("stem", lem, len(stems & gs) / len(stems | gs),
                                  ws[0].gloss[:40]))
        # 3. verse fit: in all of this node's verses, and rare elsewhere
        cover = len({w.ref for w in ws}) / max(n_refs, 1)
        if cover == 1.0 and n_refs > 1:
            rarity = 1.0 / (1 + (freq[lem] / 500))
            res.votes.append(Vote("verse-fit", lem, 0.5 + 0.5 * rarity,
                                  f"in all {n_refs} refs, {freq[lem]} verses"))
        # 4. elimination: unclaimed in a verse where everything else is taken
        if claimed is not None and n_refs == 1:
            others = {w.lemma for w in tagged.get(refs[0], [])}
            free = {o for o in others if o not in claimed}
            if free == {lem}:
                res.votes.append(Vote("eliminate", lem, 0.7,
                                      "only lemma unclaimed in the verse"))

    # CANDIDATES ARE EMITTED EVEN WHEN NOTHING VOTES, because they are the
    # screener's input. 2026-09-02: if it is a plausible candidate, a cheap
    # model screens it for the scorer. A node with no vote is
    # precisely the one a model must look at, and dropping it from the output
    # would leave the screener with nothing to screen -- `cockle` has four
    # plausible lemmas in Job 31:40 and scored zero against all of them,
    # because the KJV word and the gloss are different English.
    res.candidates = [{"lemma": lem,
                       "gloss": ws[0].gloss[:60],
                       "verses": sorted({w.ref for w in ws})[:4],
                       "elsewhere": freq[lem]}
                      for lem, ws in sorted(here.items(),
                                            key=lambda kv: freq[kv[0]])][:8]
    if not res.votes:
        return res
    by = collections.defaultdict(list)
    for v in res.votes:
        by[v.lemma].append(v)
    best = max(by.items(), key=lambda kv: (len(kv[1]), sum(x.score for x in kv[1])))
    res.lemma = best[0]
    methods = {v.method for v in best[1]}
    rivals = [k for k in by if k != best[0]]
    res.confidence = min(1.0, sum(v.score for v in best[1]) / max(len(methods), 1))
    # Agreement between INDEPENDENT methods is the thing worth trusting; one
    # method scoring high is not the same fact.
    res.state = ("agreed" if len(methods) > 1 else
                 "split" if rivals else "single")
    return res


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    from .schema import load_entities

    ents = load_entities()
    subset = [a for a in argv if not a.startswith("--")]
    print("reading STEPBible tagged texts ...", flush=True)
    tagged = load_tagged()
    freq = collections.Counter()
    for ws in tagged.values():
        for lem in {w.lemma for w in ws}:
            freq[lem] += 1
    print(f"  {len(tagged):,} tagged verses, {len(freq):,} distinct lemmas\n")

    # Two passes: confident assignments first, then elimination sees what is
    # already claimed. Same fixed-point shape as deduplication.
    rows = [(i, e) for i, e in ents.items() if e.refs]
    if subset:
        rows = [(i, e) for i, e in rows if i in subset]
    first = {i: assign(i, e.name or i, e.refs, tagged, freq) for i, e in rows}
    claimed = {r.lemma for r in first.values() if r.state == "agreed"}
    claimed = {c: True for c in claimed}
    final = {i: assign(i, e.name or i, e.refs, tagged, freq, claimed)
             for i, e in rows}

    state = collections.Counter(r.state for r in final.values())
    print(f"{'state':14}{'nodes':>8}   what it means")
    for s, msg in (("agreed", "two or more independent methods concur"),
                   ("single", "one method, no rival lemma"),
                   ("split", "methods disagree -- review"),
                   ("unresolved", "candidates exist, nothing matched"),
                   ("untagged", "no tagged verse among its citations")):
        print(f"{s:14}{state[s]:>8}   {msg}")
    print(f"{'':14}{'-'*8}")
    print(f"{'total':14}{sum(state.values()):>8}")

    out = ROOT / "out" / "lemma-assignments.json"
    out.write_text(json.dumps(
        {i: {"lemma": r.lemma, "state": r.state,
             "confidence": round(r.confidence, 3),
             "candidates": r.candidates,
             "votes": [{"method": v.method, "lemma": v.lemma,
                        "score": round(v.score, 3), "why": v.why}
                       for v in r.votes]}
         for i, r in final.items() if r.votes or r.candidates}, indent=1),
        encoding="utf-8")
    print(f"\nwrote {out}  (votes kept, not just winners)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
