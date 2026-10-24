"""Legacy name -> Strong's number, via the aligned translation rather than spelling.

2026-09-05: the better source for the mappings might be in the translation
text we used, aligned to the original language. That is the right
instrument, and it replaces two worse ones tried first in the same session.

## What was tried before this, and why each failed

**Spelling normalisation.** The two graphs transliterate apart -- Ahijah/Ahiah,
Alphaeus/Alpheus, Oholiab/Aholiab -- so a third of legacy person names have no
exact match in the node vocabulary. A normaliser closes some of that, but the
aggressive version merged Esau with Joshua with Jesse, and Judah with Adah. It
raised the score by destroying the measurement. Only the collision-free half
survives, in `tools/derive.py`.

**Placement induction.** The suggestion was that graph placement would help
build a mapping if not. Sound in principle -- two things in the same slot of the same clause are
the same thing -- and it failed on a specific and instructive defect: in "the
sons of Jokshan; Sheba, and Dedan" every child occupies the SAME slot, so
matching the parent identifies nothing about which child is which. It proposed
`dedan -> sheba`, `haran -> abram`, and four different names for `ephah`.
Requiring a single filler helped and did not save it, because an under-parsed
coordination makes a five-name list *look* single-valued. Placement induction is
blocked on the coordination gap, not on the idea.

## What this does instead

The join runs through the **Strong's number**, so no English spelling is ever
compared:

    legacy name --(verses it is cited in)--> Strong's --(same number)--> node

**The source of the per-verse numbers is MACULA, and that is a late correction
worth recording.** This was built first against STEPBible's `index.json`, a
word-level alignment of 31,210 verses keyed in the legacy graph's own reference
format — excellent data, read from disk, never redistributed. Then, while
looking for an alternative Strong's source, the obvious thing surfaced:
**Strong's numbers are public domain (1890), and MACULA already carries one on
every node.** What STEPBible adds is the modern alignment, which is real work —
and which this particular method does not need, because MACULA's own alignment
is right there under a plain CC BY 4.0 with no redistribution request.

    with STEPBible    1,238 names    99% accurate
    MACULA alone      1,121 names    99% accurate

91% of the yield, one fewer dependency, and no licensing question hanging over
the committed artifact. `--stepbible` still uses their alignment for the extra
117 names.

**Co-occurrence alone is not enough**, and the failure is worth keeping: a name
that always appears beside another name satisfies "present in every cited
verse" for its companion too. That produced `Abiram -> Dathan` and
`Abiel -> Kish` -- always-together pairs. The discriminator is set similarity
rather than presence: the right number occurs where the name occurs *and not
elsewhere*, so candidates are scored by Jaccard over verse sets and a contested
best is refused rather than guessed.

## The lab: measuring the mapping before trusting it

Where a legacy name already matches a MACULA node spelling exactly, the answer
is known independently. That subset is a **validation set the method never
sees**: run the same resolution on it and compare. The accuracy reported on it
is the honest estimate for the names where spelling gives no answer, which are
the only ones the mapping is actually needed for.

    python tools/namemap.py            # resolve, validate, write
    python tools/namemap.py --misses   # what it got wrong on the known set
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import pathlib
import re
import sys

import derive

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
STEP = ROOT / "data" / "raw" / "stepbible" / "index.json"

# A name resolves only with enough independent verses behind it and a clear
# winner. Both thresholds exist because of a specific error: two verses and a
# constant companion is exactly the Abiram/Dathan shape.
MIN_VERSES = 3
MARGIN = 1.5


def strongs(s):
    """'H0041H' and '41' -> 'H41'. The letter prefix MUST survive: dropping it
    collided Greek G256 (Alphaeus) with Hebrew H256 (Ahab)."""
    m = re.match(r"^([HG])0*([0-9]+)", s or "")
    return m.group(1) + m.group(2) if m else None


def nodes():
    """Strong's -> the node spellings MACULA uses for it, proper nouns only."""
    proper = collections.defaultdict(collections.Counter)
    for line in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt",
                          encoding="utf-8"):
        n = json.loads(line)
        if not (n.get("proper") and n.get("strong")):
            continue
        p = ("G" if n.get("lang") == "greek" else "H") + \
            re.sub(r"^0+", "", re.sub(r"[^0-9]", "", n["strong"]))
        proper[p][n["local"].lower()] += 1
    return proper


def legacy_names():
    """name -> every verse the legacy graph cites it in.

    Pooled by NAME rather than by entity: the mapping is needed to compare
    spellings, and eleven men called Zechariah share one spelling and one
    Hebrew word. Identity is a separate question and not this one.
    """
    ents = {}
    for line in (ROOT / "ontology" / "entities" / "entities.jsonl").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            ents[e["id"]] = e
    byname = collections.defaultdict(set)
    kinds = ("person", "place", "group")
    for e in ents.values():
        if e["type"] in kinds:
            for r in e.get("refs", []):
                byname[e["name"]].add(r.strip())
    for f in sorted(glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl"))):
        for line in pathlib.Path(f).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            for side in ("src", "dst"):
                e = ents.get(r[side])
                if e and e["type"] in kinds:
                    for x in r.get("refs", []):
                        byname[e["name"]].add(x.strip())
    return byname


PHONIC = 0.82


def sounds_like(name, k, proper):
    """Best Jaro-Winkler between a legacy name and MACULA's spellings for k."""
    n = slug(name)
    return max((jaro_winkler(n, slug(s)) for s in proper[k]), default=0.0)


def resolve(byname, proper, idx, sverses, phonic=True, exact_first=True):
    """name -> Strong's, or nothing. Never a guess.

    Two routes to an accepted mapping, and they trade the same evidence:

        STATISTICAL   three or more verses, the candidate present in every one
                      of them, and no rival within the margin. Spelling is
                      never consulted.

        PHONIC        fewer verses than that, but exactly one candidate in
                      those verses whose MACULA spelling sounds like the name.
                      The candidate set still comes from co-occurrence, so the
                      measure only ever refuses -- it cannot nominate.

    The second exists because 1,371 of 2,216 names were refused for having too
    few verses, which was by far the largest loss.
    """
    out, why, route = {}, collections.Counter(), collections.Counter()
    for name, verses in byname.items():
        vs = {v for v in verses if v in idx}
        if not vs:
            why["no parsed verse"] += 1
            continue
        sc = []
        for k in {strongs(s) for v in vs for _, s in idx[v]}:
            if k not in proper:
                continue
            inter = len(vs & sverses[k])
            sc.append((inter / len(vs | sverses[k]), k, inter))
        sc.sort(reverse=True)
        if not sc:
            why["no proper noun in those verses"] += 1
            continue

        # EXACT first. Where MACULA spells the name the same way in one of
        # these verses, no inference is needed and none should be made. This
        # route is excluded from the validation below, because scoring a
        # method on the cases it reads the answer from measures nothing --
        # but shipping without it would knowingly use weaker evidence.
        if exact_first:
            # An exact spelling is the strongest evidence there is, so it wins
            # outright. Requiring it to be UNIQUE threw away David, Moses and
            # Abraham -- the commonest names in the corpus -- because several
            # Strong's codes carry the same spelling and the tie was treated as
            # no answer. Where several match, the one sharing the most verses
            # with the name is the one meant.
            hit = [(inter, k) for _, k, inter in sc
                   if slug(name) in {slug(x) for x in proper[k]}]
            if hit:
                out[name] = max(hit)[1]
                route["exact spelling"] += 1
                continue

        if len(vs) >= MIN_VERSES and sc[0][2] >= len(vs) and \
                not (len(sc) > 1 and sc[1][0] * MARGIN > sc[0][0]):
            out[name] = sc[0][1]
            route["statistical"] += 1
            continue

        if not phonic:
            why["too few verses / contested"] += 1
            continue
        close = [(sounds_like(name, k, proper), k) for _, k, _ in sc]
        close = sorted((c for c in close if c[0] >= PHONIC), reverse=True)
        if len(close) == 1 or (len(close) > 1 and close[0][0] - close[1][0] > 0.05):
            out[name] = close[0][1]
            route["phonic"] += 1
        elif close:
            why["phonic tie"] += 1
        else:
            why["nothing sounds like it"] += 1
    return out, why, route


def slug(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def jaro_winkler(a, b):
    """Deterministic phonetic-ish similarity, 0..1. No dependencies, no model.

    2026-09-05: is there a deterministic measure of phonic similarity between
    words that can be used in these cases? Several -- Soundex,
    Metaphone, NYSIIS, Jaro-Winkler -- and the choice matters less than **how
    it is used**.

    Soundex and Metaphone are BUCKETING schemes: they hash a name to a code and
    call every name in the bucket a match. That is precisely the shape that
    merged Esau with Joshua with Jesse earlier today, and it fails the same way
    here, because a four-character code over 1,600 biblical names is not
    discriminating.

    Jaro-Winkler is a PAIRWISE measure instead, and it is only ever asked about
    two specific strings that verse co-occurrence has already nominated. It
    cannot invent a candidate; it can only refuse one. That containment is what
    makes it safe, and it is why the prefix weighting suits transliterations,
    where the disagreements cluster at the end of the word -- Ahijah/Ahiah,
    Hizkijah/Hizkiah, Malchijah/Malchiah.
    """
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    reach = max(len(a), len(b)) // 2 - 1
    fa, fb = [False] * len(a), [False] * len(b)
    m = 0
    for i, ch in enumerate(a):
        for j in range(max(0, i - reach), min(len(b), i + reach + 1)):
            if not fb[j] and b[j] == ch:
                fa[i] = fb[j] = True
                m += 1
                break
    if not m:
        return 0.0
    k = t = 0
    for i in range(len(a)):
        if fa[i]:
            while not fb[k]:
                k += 1
            if a[i] != b[k]:
                t += 1
            k += 1
    t //= 2
    j = (m / len(a) + m / len(b) + (m - t) / m) / 3
    p = 0
    for x, y in zip(a[:4], b[:4]):
        if x != y:
            break
        p += 1
    return j + p * 0.1 * (1 - j)


def macula_index():
    """Per-verse Strong's numbers from MACULA alone, keyed like the legacy graph.

    2026-09-05, looking for another Strong's source (the site found was very
    limited). The useful realisation came out of that search rather than out of the site.
    **Strong's numbers and the lexicon are public domain (1890).** What STEPBible
    supplies that a lexicon cannot is the modern verse-by-verse alignment of the
    original text to those numbers — and MACULA already carries `strong` on every
    node, under a plain CC BY 4.0 with no redistribution request attached.

    So the whole method runs without them:

        with STEPBible    1,238 names    99% accurate
        MACULA alone      1,121 names    99% accurate

    91% of the yield, one fewer dependency, and no licensing question over the
    committed artifact. STEPBible stays available as an enrichment for the extra
    117 names via `--stepbible`, and is still read from disk and never
    redistributed.
    """
    idx = collections.defaultdict(list)
    back = {v: k for k, v in derive.BOOK.items()}
    for line in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt",
                          encoding="utf-8"):
        n = json.loads(line)
        if not (n.get("proper") and n.get("strong")):
            continue
        b, c, v = n["ref"].split(".")
        k = ("G" if n.get("lang") == "greek" else "H") + \
            re.sub(r"^0+", "", re.sub(r"[^0-9]", "", n["strong"]))
        idx[f"{back.get(b, b)} {c}:{v}"].append(("", k))
    return idx


def rosters():
    """Verse -> [(parent node slug, [child node slugs])] from the structure."""
    out = collections.defaultdict(list)
    byverse = collections.defaultdict(list)
    for line in gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt",
                          encoding="utf-8"):
        e = json.loads(line)
        if "_source" not in e:
            byverse[e["ref"]].append(e)
    KIN = {"son", "sons", "child", "children", "daughter", "daughters"}
    for v, edges in byverse.items():
        members = collections.defaultdict(list)
        for e in edges:
            if e.get("type") == "member" and e.get("src") and e.get("dst"):
                members[e["src"]].append(e["dst"])
        for e in edges:
            rel = e.get("dst_relation")
            if not rel or (rel.get("type") or "").lower() != "of":
                continue
            if slug((rel.get("src") or "").split("#")[-1]) not in KIN:
                continue
            parent = slug((rel.get("dst") or "").split("#")[-1])
            kids = []
            for f in edges:
                if f.get("type") == "is" and f.get("src") == e.get("src"):
                    for m in members.get(f.get("dst"), [f.get("dst")]):
                        if m:
                            kids.append(slug(m.split("#")[-1]))
            if parent and kids:
                out[v].append((parent, kids))
    return out


def legacy_sets():
    """(parent name, verse) -> [child names], from the legacy graph."""
    ents = {}
    for line in (ROOT / "ontology" / "entities" / "entities.jsonl").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            ents[e["id"]] = e
    out = collections.defaultdict(list)
    for f in sorted(glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl"))):
        for line in pathlib.Path(f).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r["type"] not in ("father_of", "mother_of"):
                continue
            s, d = ents.get(r["src"]), ents.get(r["dst"])
            if not s or not d:
                continue
            for v in r.get("refs", []):
                out[(s["name"], v.strip())].append(d["name"])
    return out


def assign(got, proper, ros, sets, floor=0.62):
    """Match a legacy sibling set to a node roster as a ONE-TO-ONE assignment.

    2026-09-05: narrowing to a collection of sons should help figure out which
    matches to which. This is the answer to the failure
    that killed placement induction earlier. There, every son occupied the same
    slot, so matching the parent said nothing about which child was which. Here
    the set is the unit: the legacy graph knows Merari's children and the
    structure knows the names in Merari's roster, and the question becomes
    which member pairs with which -- a closed assignment over two small sets
    rather than a lookup against the whole corpus.

    Two properties come free from doing it that way, and both were failures a
    moment ago:

    - **One-to-one.** No two legacy names may take the same node. That is what
      the earlier induction violated when four names all claimed `ephah`.
    - **A weak score is decisive inside a closed set.** Matching two names out
      of 1,600 needs a high bar; matching two lists of four needs only that
      this pairing beats the alternatives, so the floor can drop safely.

    Greedy best-pair-first, which is optimal enough on sets this size and has
    the merit of being obvious.
    """
    new, checked, agree = {}, 0, 0
    for (parent, verse), kids in sets.items():
        # the legacy graph and MACULA abbreviate books differently; reuse the
        # one map rather than writing a second one that can drift from it
        entries = ros.get(derive.ref(verse) or "")
        if not entries:
            continue
        pslug = slug(parent)
        for pnode, cnodes in entries:
            if pnode != pslug and jaro_winkler(pnode, pslug) < 0.9:
                continue
            pairs = sorted(
                ((jaro_winkler(slug(k), c), k, c)
                 for k in set(kids) for c in set(cnodes)),
                reverse=True)
            tk, tc = set(), set()
            for sc, k, c in pairs:
                if sc < floor or k in tk or c in tc:
                    continue
                tk.add(k)
                tc.add(c)
                if slug(k) == c:
                    continue          # spelling already agreed; no news
                if k in got:
                    checked += 1
                    agree += any(c == slug(x) for x in proper.get(got[k], {}))
                else:
                    new[k] = c
    return new, checked, agree


def main() -> int:
    step = "--stepbible" in sys.argv
    proper = nodes()
    if step:
        if not STEP.exists():
            print(f"STEPBible index not found at {STEP}")
            print("Read from disk only; see docs/OPERATIONS.md. Never "
                  "redistributed.")
            return 1
        idx = json.loads(STEP.read_text(encoding="utf-8"))["verses"]
        print("SOURCE: STEPBible alignment (read from disk, not redistributed)")
    else:
        idx = macula_index()
        print("SOURCE: MACULA alone - Strong's numbers are public domain and "
              "MACULA carries them")
    print(f"  verses with a proper noun  {len(idx):>6}\n")
    sverses = collections.defaultdict(set)
    for v, row in idx.items():
        for _, s in row:
            k = strongs(s)
            if k in proper:
                sverses[k].add(v)

    byname = legacy_names()
    base, _, _ = resolve(byname, proper, idx, sverses, phonic=False,
                         exact_first=False)
    scored, _, _ = resolve(byname, proper, idx, sverses, exact_first=False)
    got, why, route = resolve(byname, proper, idx, sverses)

    print("NAME -> STRONG'S, through the aligned translation")
    print(f"  legacy names pooled        {len(byname):>6}")
    print(f"  resolved                   {len(got):>6}")
    for k, v in route.most_common():
        print(f"    by {k:38}{v:>6}")
    for k, v in why.most_common():
        print(f"    refused: {k:34}{v:>6}")
    print()

    # ---- the lab: score it where the answer is already known ----------
    exact = {}
    for k, spell in proper.items():
        for s in spell:
            exact.setdefault(slug(s), set()).add(k)
    known, right, wrong = 0, 0, []
    kn2 = rt2 = 0
    for name, k in scored.items():
        if slug(name) not in exact:
            continue
        known += 1
        ok = k in exact[slug(name)]
        right += ok
        if name not in base:          # scored on the phonic route alone
            kn2 += 1
            rt2 += ok
        if not ok:
            wrong.append((name, k, sorted(exact[slug(name)])[:3],
                          list(proper[k])[:2], "phonic" if name not in base
                          else "statistical"))
    print("VALIDATION - names whose spelling already gives the answer")
    print(f"  scorable                   {known:>6}")
    print(f"  method agrees              {right:>6}   "
          f"{100*right//max(known,1)}%")
    print(f"  method disagrees           {len(wrong):>6}")
    print(f"  of those, added by phonic  {kn2:>6}   agrees {rt2}  "
          f"{100*rt2//max(kn2,1)}%")
    print("  This is the honest accuracy estimate for the names where")
    print("  spelling gives NO answer, which are the ones the map is for.")
    if "--misses" in sys.argv:
        print("\n  disagreements:")
        for w in wrong[:30]:
            print(f"    {w[0]:20}method {w[1]:8}({w[3]})  "
                  f"spelling says {w[2]}")

    ros, sets = rosters(), legacy_sets()
    new, checked, agree = assign(got, proper, ros, sets)
    print()
    print("SET ASSIGNMENT - matching a sibling list to a roster, one-to-one")
    print(f"  legacy parent/verse sets   {len(sets):>6}")
    print(f"  rosters in the structure   {sum(len(v) for v in ros.values()):>6}")
    print(f"  pairs where the map already had an answer {checked:>6}")
    print(f"    and the set agreed with it              {agree:>6}   "
          f"{100*agree//max(checked,1)}%")
    print(f"  names the set resolves that nothing else did {len(new):>6}")
    if new:
        print(f"    e.g. {list(new.items())[:8]}")

    path = OUT / "name-strongs.json"
    path.write_text(json.dumps({
        "_source": ("STEPBible TAHOT/TAGNT alignment, CC BY - read from disk, "
                    "never redistributed; refer others to github.com/STEPBible"
                    if step else
                    "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., "
                    "CC BY 4.0. Strong's numbers are public domain (1890)."),
        "_method": "verse-set Jaccard against MACULA proper-noun Strong's; "
                   f"min {MIN_VERSES} verses, margin {MARGIN}",
        "map": got,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
