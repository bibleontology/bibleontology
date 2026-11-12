"""Which person or place card a name word names, where the rule could not tell (Doug, 2026-11-10, on Dothan: "Could
the Mac look for words disconnected from meanings and without a basic type definition clearly presented to the user?").

server.names_of_word links 1,472 of 2,892 name words by rule: the cards' own name words, or a card named as the word
is glossed whose verses hold it. Of the 1,420 left, 1,170 have no person or place card citing any of their verses
(minor names of genealogies and lists: nothing to link to). The other 250 have candidates: a card of the kind STEP's
tag gives that cites one of the word's verses (Azotus, Acts 8:40, is the Ashdod card's place under its Greek name, or
is not). One item per word: its lexicon line, its verses, and the candidates, each with its own disambiguation; the Mac
picks one, or none. Nothing is written by this pass; the apply step adds the picked links to the name index after a
look. The Mac alone (DeepSeek budget 0); a divine person is never a candidate (linked by hand only).

    python tools/meaning/name_links.py build   -> out/orchestra-intake/23-name-links/
"""
import collections
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))

NAME = "23-name-links"
OPTIONS = {"temperature": 0, "num_ctx": 4096}
SEED = 20261110
DIVINE = {"god", "jesus", "holy_spirit", "the_father", "yhwh", "the_lord"}
MAX_CANDS, MAX_VERSES = 8, 3

BRIEF = """You match a name in the Bible's original language to the person or place it names. You get the word, its
lexicon line, up to three verses where it stands (the Berean Standard Bible), and numbered candidate cards, each with
a name, a line saying who or what it is, and the verses it cites. Say which card the word names in these verses.

Answer with ONE line of JSON:
{"id": "...", "pick": N, "why": "..."}

pick: the number of the card the word names, or 0 if none of them is it (a different person or place who happens to
appear in the same verse is not it). Pick a card only if the verses show the word naming it: the same name, or the
same person or place under another spelling or language (a Greek form of a Hebrew name counts).
why: one short reason.

Worked examples (not from the items):
- WORD Ἄζωτος, "Azotus, a place". VERSE Acts 8:40 "Philip, however, appeared at Azotus..." CARDS 1 Philip (the
  evangelist), 2 Ashdod (Philistine city). -> pick 2: Azotus is the Greek name of Ashdod.
- WORD עֲזַרְיָה, "Azariah, a man's name". VERSE 2 Chr 26:17 "Azariah the priest went in after him..." CARDS 1 Uzziah
  (king of Judah), 2 Azariah (high priest under Uzziah). -> pick 2.
- WORD Ἀντιπᾶς, "Antipas, a man's name". VERSE Rev 2:13 "...Antipas, My faithful witness..." CARDS 1 Herod (Herod
  Antipas, tetrarch). -> pick 0: a martyr at Pergamum, not Herod.
"""


def build(check=False):
    """check=True (24-name-links-check): the RULE's own links, a word with exactly one card, asked the same question
    with that one candidate; a "0" comes back to Claude. The rule linked 1,472 words with no model looking."""
    import server as S
    import structure as T
    from object_identity import verses
    text = verses()
    d = S.load()
    global NAME
    if check:
        NAME = "24-name-links-check"
    vo = S._verses_of(d)
    refs = {e: {S._macula_ref(d, r) for r in v.get("refs") or ()} for e, v in d["ents"].items()
            if v.get("type") in ("person", "place", "group") and e not in DIVINE}
    by_verse = collections.defaultdict(set)
    for e, rs in refs.items():
        for r in rs:
            by_verse[r].add(e)
    by_name = collections.defaultdict(set)
    for e in refs:
        for nm in [d["ents"][e].get("name")] + list(d["ents"][e].get("aka") or []):
            if S._slug(nm):
                by_name[S._slug(nm)].add(e)
    items = []
    judged = json.loads(LINKS.read_text(encoding="utf-8"))["links"] if LINKS.exists() else {}
    for k in sorted(d["lex"]):
        nk = S.name_kind(d, k)
        if not nk or not vo.get(k):
            continue
        have = S.names_of_word(d, k)
        if check:
            # one card, linked by the rule (not already judged), never a divine person
            if len(have) != 1 or k in judged or have[0]["id"] not in refs:
                continue
            cands = {have[0]["id"]}
        else:
            if have:
                continue
            # "a place, or the people of it" (Maacathite) may be either; a name may also be a card that cites none
            # of these verses (the Aramaic Cyrus of Ezra 5-6), so cards named as the word's gloss or definition too
            kinds = {"place", "group"} if (d["lex"][k].get("pos") or "").endswith("LG") else {nk[0]}
            fit = lambda e: nk[0] is None or d["ents"][e]["type"] in kinds  # noqa: E731
            cands = {e for r in vo[k] for e in by_verse.get(r, ()) if fit(e)}
            said = (d["lex"][k].get("gloss") or "") + "," + (d["lex"][k].get("definition") or "").split("·")[0]
            for part in re.split(r"\s+or\s+|[,;/(){}]", said):
                cands |= {e for e in by_name.get(S._slug(part.strip()), ()) if fit(e)}
        if not cands:
            continue
        cands = sorted(cands, key=lambda e: (-len(refs[e] & vo[k]), e))[:MAX_CANDS]
        vs = []
        for r in sorted(vo[k], key=lambda r: -sum(r in refs[e] for e in cands))[:MAX_VERSES]:
            eng = T.to_english(r)
            t = text.get(eng) or text.get(r)
            if t:
                vs.append(f"{eng}: {t}")
        if not vs:
            continue
        lx = d["lex"][k]
        cl = []
        for i, e in enumerate(cands, 1):
            ent = d["ents"][e]
            cl.append(f"{i} {ent.get('name')} ({S._who(ent) or ent['type']}); cites "
                      + ", ".join(sorted(ent.get("refs") or [])[:4]))
        items.append({"key": k, "id": f"n{len(items) + 1}", "word": lx.get("word"), "kind": nk[1],
                      "lexicon": (lx.get("definition") or lx.get("gloss") or "")[:200], "cands": cands,
                      "claim": f"WORD {lx.get('word')}, \"{(lx.get('gloss') or '').strip()}\", {nk[1]}. "
                               f"LEXICON: {(lx.get('definition') or '')[:200]}",
                      "verse": "\n".join(vs), "context": cl})
    random.Random(SEED).shuffle(items)
    out = ROOT / "out" / "orchestra-intake" / NAME
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{NAME}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "name_links"}}) + "\n")
        for it in items:
            f.write(json.dumps({"key": it["key"], "messages": messages(it)}, ensure_ascii=False) + "\n")
    spec = {"pass": NAME, "mac_job": f"{NAME}.jsonl", "priority": 30, "flag": {"verdict_in": []},
            "deepseek": {"budget_usd": 0}, "allowed_fields": ["id", "claim", "verse", "context"]}
    (out / f"{NAME}.pass.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out / "brief.md").write_text(BRIEF, encoding="utf-8", newline="\n")
    with open(out / "items.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"{len(items)} name words with candidate cards -> {out}")


# THE JUDGMENT (Claude, 2026-11-10, every one of the Mac's 206 picks read): rejected, by word, with why. Most are a
# relative taken for the man (the verses name both), or one bearer of a name several share
REJECT = {
    "g2331": "Thessalonians are the city's people, not the church", "g2541": "Caesar is several emperors",
    "g4549": "Σαούλ is mostly Paul (Acts 9, 22, 26), once the king", "g896": "Baal in Rom 11:4 is the god",
    "g923": "Barsabbas is Joseph (Acts 1:23) as well as Judas", "h1424": "Gadi is Menahem's father",
    "h1689": "Diblah as Riblah is a conjecture", "h1712": "Dagon is the god, not his temple",
    "h206": "Aven is also On (Ezek 30:17) and a valley (Amos 1:5)", "h2383": "Hezion is Ben-hadad's grandfather",
    "h2577": "the Hamathites are one Canaanite clan, not the Canaanite", "h2886": "Tabrimmon is Ben-hadad's father",
    "h3479": "the Aramaic Israel names the nation (Ezra)", "h3779": "the Aramaic Chaldean is a class, not one group",
    "h3810": "Lo-debar as Debir is a guess", "h4176": "Moreh is also the hill (Judg 7:1)",
    "h4322": "Micaiah is mostly the prophet", "h5028": "Nebat is Jeroboam's father",
    "h5316": "a height of Dor, not Dor", "h5512": "Sin is also Pelusium (Ezek 30:15)", "h5611": "Sephar is no dwelling",
    "h6164": "the Arbathite is of Beth-arabah, not the Arabah", "h6326": "this Puah is the midwife, the card two men",
    "h683": "Azaliah is Shaphan's father", "h7145": "the Korahites are more than the gatekeepers",
    "h721": "the Arvadites are one Canaanite clan", "h7747": "the Shuhite is Bildad, not the three",
    "h7774": "this Shua is a woman (1 Chr 7:32), the card Judah's father-in-law",
    "h7793": "Shur is the region, not the land between", "h8152": "Shinar is the plain, not the city",
    "h8515": "Telassar is not Eden",
}
LINKS = ROOT / "ontology" / "word-name-links.json"


def apply():
    """The Mac's picks less the rejected, to ontology/word-name-links.json ({key: [card]}), read by
    server.names_of_word; every item's trail, shown and rejected, to ontology/provenance/ (provenance against slop)."""
    items = {json.loads(x)["key"]: json.loads(x) for x in open(ROOT / "out" / "orchestra-intake" / NAME / "items.jsonl",
                                                                 encoding="utf-8")}
    links, trail = {}, []
    for line in open(ROOT / "out" / "grunt" / "done" / f"{NAME}.jsonl", encoding="utf-8"):
        r = json.loads(line)
        it = items.get(r["key"])
        m = re.search(r"\{.*\}", r.get("content") or "", re.S)
        try:
            a = json.loads(m.group(0)) if m else {}
        except ValueError:
            a = {}
        p = a.get("pick")
        card = it["cands"][p - 1] if it and isinstance(p, int) and 1 <= p <= len(it["cands"]) else None
        verdict = "none" if not card else ("rejected" if r["key"] in REJECT else "linked")
        if verdict == "linked":
            links[r["key"]] = [card]
        trail.append({"key": r["key"], "word": it and it["word"], "cands": it and it["cands"], "mac_pick": card,
                      "mac_why": a.get("why"), "verdict": verdict, "why": REJECT.get(r["key"]),
                      "judge": "claude-opus, every pick read, 2026-11-10"})
    LINKS.write_text(json.dumps({"_source": f"{NAME}: the Mac's pick, each read by Claude; see "
                                            f"ontology/provenance/{NAME}-2026-11-10.jsonl",
                                 "links": dict(sorted(links.items()))}, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8", newline="\n")
    prov = ROOT / "ontology" / "provenance" / f"{NAME}-2026-11-10.jsonl"
    with open(prov, "w", encoding="utf-8", newline="\n") as f:
        for t in trail:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    c = collections.Counter(t["verdict"] for t in trail)
    print(f"{dict(c)} -> {LINKS.name}, {prov.name}")


def messages(it):
    return [{"role": "system", "content": BRIEF},
            {"role": "user", "content": f"id: {it['id']}\n{it['claim']}\nVERSES:\n{it['verse']}\nCARDS:\n"
                                        + "\n".join(it["context"])}]


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        build(check="--check" in sys.argv)
    elif sys.argv[1:2] == ["apply"]:
        apply()
    else:
        print(__doc__)
