"""Public addresses for cards whose id misleads (plan A.21; P-99 retires the old).

A card's address was its id, and an id is made once, from whatever the record
was first called. 758 ids share no word with the card's name or other names --
mostly the KJV's rendering, kept after the name was corrected: /e/the_proud is
Rahab the sea monster (Job 26:12), /e/pureness is cleanness, /e/provender is
feed. 2026-10-03: a misleading site map is not good for search engines either; new
addresses were chosen for those 758 only, with the old links to be retired
eventually.

The ids do not change -- they run through every relation and derived file.
Each of the 758 gets an ADDRESS made from its name; the server answers it,
sends the old one there permanently, and names it in the canonical tag and
the sitemap. An id with a verse reference in it (gen_22_5_abraham_speech) is
not misleading and keeps its address.

Rule: the name, lower-cased, letters and digits only, words joined by "_",
"the" dropped at the front, cut at a word within 60 characters. Where that is
taken -- by any id, or by an address already given -- the card's first verse
is added (rahab_job_26_12), then its id.

    python tools/card_slugs.py   -> out/card-slugs.json  {id: address}
"""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOP = set("the a an of and in to for his her their my your our on at by with from as is "
           "be that this it s".split())
MAXLEN = 60


def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if w not in STOP}


def stem(w):
    for suf in ("ies", "es", "s", "ing", "ed"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[:-len(suf)]
    return w


_DELTA = None


def kjv_delta():
    """Words the KJV uses and neither the Berean nor the WEB does ("ghost",
    "brethren", "begat") -- tools/kjv_audit.py's DELTA, from data/raw/kjv/
    (gitignored, local). Empty where the KJV is not on disk."""
    global _DELTA
    if _DELTA is None:
        try:
            import sys
            import collections
            sys.path.insert(0, str(ROOT / "tools"))
            import kjv_audit as K
            kjv, bsb, web = K.verses_k(K.KJV), K.verses_k(K.BSB), K.verses_k(K.WEB)
            books = {b for b, _c, _v in bsb}
            kv = collections.Counter(w for k, t in kjv.items() if k[0] in books
                                     for w in K.WORD.findall(K.plain(t)))
            bv = {w for t in bsb.values() for w in K.WORD.findall(K.plain(t))}
            wv = {w for t in web.values() for w in K.WORD.findall(K.plain(t))}
            _DELTA = {w for w in kv if w not in bv and w not in wv and w not in K.NOT_OLD and len(w) > 2}
        except Exception:  # noqa: BLE001 -- no KJV on disk: the old rule only
            _DELTA = set()
    return _DELTA


def misleading(e):
    """The id shares no word with the card's names, and is not a reference.
    Or (2026-10-11: /e/holy_ghost becomes a redirect to
    /e/holy_spirit, and other urls with words in the delta
    between KJV and Berean are looked for) the id keeps a KJV-only word its name no longer
    has: holy_ghost is named "Holy Spirit". A word the name still carries
    (a card actually named "Epicureans") is the name, not old wording."""
    idw = set(e["id"].split("_"))
    nmw = {w for n in [e["name"]] + (e.get("aka") or []) for w in re.findall(r"[a-z]+", (n or "").lower())}
    if (idw & kjv_delta()) - nmw:
        return True
    if re.search(r"\d", e["id"]):
        return False
    idt = {stem(w) for w in toks(e["id"].replace("_", " "))}
    nm = {stem(w) for n in [e["name"]] + (e.get("aka") or []) for w in toks(n)}
    return bool(idt) and not (idt & nm)


def slugify(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    words = re.findall(r"[a-z0-9]+", s)
    if words[:1] == ["the"]:
        words = words[1:]
    out = ""
    for w in words:
        if len(out) + len(w) + 1 > MAXLEN and out:
            break
        out = f"{out}_{w}" if out else w
    return out


def ref_slug(r):
    return slugify(r)


def main():
    ents = [json.loads(ln) for ln in open(ROOT / "ontology" / "entities" / "entities.jsonl",
                                          encoding="utf-8")]
    taken = {e["id"] for e in ents}
    # AN ADDRESS GIVEN IS KEPT. Once published, an address is in search
    # indexes and in links people have shared; re-deriving it after a name
    # changes would move it again. So every address already in the file
    # stays, and only cards newly misleading get one.
    p = ROOT / "out" / "card-slugs.json"
    out = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    ids = {e["id"] for e in ents}
    out = {k: v for k, v in out.items() if k in ids}
    taken |= set(out.values())
    # BY HAND, where the rule cannot see it (2026-10-11): "ghost" is in
    # the Berean too ("It's a ghost!", Matt 14:26), so it is not in the delta
    HAND = {"holy_ghost": "holy_spirit"}
    for i, s in HAND.items():
        if i in ids and i not in out and s not in taken:
            out[i] = s
            taken.add(s)
    for e in ents:
        if e["id"] in out or not misleading(e):
            continue
        s = slugify(e["name"])
        # a one-word name ("Mary", for Mary the wife of Clopas) is not an
        # address for one card among several: its first verse is added
        if s and "_" not in s and s not in ids:
            s = f"{s}_{ref_slug((e.get('refs') or [''])[0])}".strip("_")
        if not s or s in taken:
            s2 = f"{s}_{ref_slug((e.get('refs') or [''])[0])}".strip("_") if s else ""
            s = s2 if s2 and s2 not in taken else f"{s or 'card'}_{e['id']}"
        out[e["id"]] = s
        taken.add(s)
    (ROOT / "out" / "card-slugs.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    moved = sum(1 for k, v in out.items() if v != k)
    print(f"{len(out):,} cards given an address from their name ({moved:,} differ from the id)")


if __name__ == "__main__":
    main()
