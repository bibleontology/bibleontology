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


# THE PARABLES (the parable card, 2026-10-29): one card, one address per parable, and the address is the event's
# id without "event_" -- "/e/parable_of_the_sower" -- whatever the older node was called. Exceptions are in
# ontology/parables.json: the pearl (the Berean's heading at Matt 13:44 is "The Parables of the Treasure and the
# Pearl", ruling PB-A, so the KJV's "of Great Price" is not in the address) and the two whose event id does not
# start with parable_of. The older record of each parable is folded into its event by ontology/aliases.jsonl and
# sends the reader on.
PARABLES = json.loads((ROOT / "ontology" / "parables.json").read_text(encoding="utf-8"))["events"]
PARABLE_EVENTS = [p["id"] for p in PARABLES]
PARABLE_ADDRESS = {p["id"]: p["address"] for p in PARABLES if p.get("address")}
# A folded record has no address of its own: the weeds' node had one, taken from its KJV name's neighbor, and two
# ids on one address leave the reverse map to dict order
FOLDED_NO_ADDRESS = {"parable_of_the_tares"}


def parable_address(eid):
    return PARABLE_ADDRESS.get(eid) or eid[len("event_"):]


def all_ids():
    """Every id in every entity file. The tool read entities.jsonl only, so the next run would have pruned every
    address given to a record that lives in another file -- all 22 parable events are in events-copilot.jsonl."""
    ids = set()
    for f in sorted((ROOT / "ontology" / "entities").glob("*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                ids.add(json.loads(ln)["id"])
    return ids


def main():
    ents = [json.loads(ln) for ln in open(ROOT / "ontology" / "entities" / "entities.jsonl",
                                          encoding="utf-8")]
    ids_all = all_ids()
    taken = {e["id"] for e in ents}
    # AN ADDRESS GIVEN IS KEPT. Once published, an address is in search
    # indexes and in links people have shared; re-deriving it after a name
    # changes would move it again. So every address already in the file
    # stays, and only cards newly misleading get one.
    p = ROOT / "out" / "card-slugs.json"
    out = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    ids = {e["id"] for e in ents}
    out = {k: v for k, v in out.items() if k in ids_all and k not in FOLDED_NO_ADDRESS}
    taken |= set(out.values())
    for eid in PARABLE_EVENTS:
        assert eid in ids_all, eid
        out[eid] = parable_address(eid)
        taken.add(out[eid])
    # BY HAND, where the rule cannot see it (2026-10-11): "ghost" is in
    # the Berean too ("It's a ghost!", Matt 14:26), so it is not in the delta
    HAND = {"holy_ghost": "holy_spirit",
            # THE IMAGE CARDS' KJV-WORDED ADDRESSES (2026-10-30, ruling IM-C; A.22: no visible trace of King James
            # wording in any href): each id kept the KJV's words after its name was corrected to the Berean's, so
            # the id showed in every link and in the JSON-LD. The old address answers 301 to the new one.
            "dream_of_the_butler": "chief_cupbearer_s_dream",
            "he_shall_shake_off_his_unripe_grape_as_the_vine": "he_will_be_like_a_vine_stripped_of_its_unripe_grapes",
            "the_branch_cannot_bear_fruit_of_itself": "no_branch_can_bear_fruit_by_itself_unless_it_remains_in_the_vine",
            # THE OBJECT CARDS' KJV-SPELLED ADDRESSES (2026-10-30, rulings OB-A and OB-F; A.22): "Cesar" and "unto" in five
            # ids, the KJV's "laver", "fowl", "favoured" and "bow" in the rest. The Berean's words; the old address
            # answers 301 to the new one.
            "cesar": "caesar", "cesar_augustus": "caesar_augustus", "tiberius_cesar": "tiberius_caesar",
            "i_appeal_unto_cesar": "i_appeal_to_caesar",
            "render_unto_cesar_the_things_which_are_cesars": "give_to_caesar_what_is_caesar_s",
            "sure_covenant_under_nehemiah": "binding_agreement_under_nehemiah",
            "the_laver": "basin", "fowl": "birds_gen_1_20", "fowl_of_the_air": "birds_of_the_air_gen_1_26",
            "seven_ill_favored_cows": "seven_sickly_and_thin_cows", "seven_well_favored_cows": "seven_cows_sleek_and_well_fed",
            "bow_in_the_cloud": "rainbow_in_the_clouds", "clean_fowl": "clean_bird"}
    for i, s in HAND.items():
        if i in ids and i not in out and s not in taken:
            out[i] = s
            taken.add(s)
    # a record folded into another (ontology/aliases.jsonl) answers 301 to its survivor: no address of its own
    folded = {json.loads(ln)["id"] for ln in open(ROOT / "ontology" / "aliases.jsonl", encoding="utf-8")
              if ln.strip()}
    for e in ents:
        if e["id"] in out or e["id"] in folded or not misleading(e):
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
