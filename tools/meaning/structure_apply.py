"""THE APPLY STEP for the structure-relations passes (20s objects and creatures, 22 concepts and images), plan
P-2026-11-08-1 (approved 2026-11-08); written 2026-11-13.

The Mac read 15,697 clauses where a card's own word is the doer or the thing done to, and confirmed 5,963 as stated
by their verse. Nothing reached the graph: this step was never written, which is why object and creature pages still
showed 83% with two or fewer links to other cards (the per-kind audit, 2026-11-13).

For each confirmed reading:
  ROLE   the card is the subject ("the stones struck"): card -> act -> the other end (the thing, if named);
         the card is the object ("Cain worked the ground"): the doer -> act -> card.
  OTHER END  resolved by the site's own name index (alias_ix), preferring a candidate whose card already cites this
         verse; two candidates left, or none, and the row is HELD with its reason. Never a guess.
  ACT    mapped to a vocabulary type by DeepSeek (labels actmap-*, judged once per distinct act), then checked here
         against the live vocabulary (relationship_types.yaml); "none" or an unknown type is HELD.
  HELD BY RULE  a divine doer or end (Doug's, record by record); a speech verb (told, said, spoke: the graph's speech
         rule decides those, not this step); a reading whose verse is not the clause's own.

    python tools/meaning/structure_apply.py resolve   -> out/structure-apply/resolved.jsonl, and the tally
    python tools/meaning/structure_apply.py rows      -> out/structure-apply/rows.jsonl (with the act map)
    python tools/meaning/structure_apply.py sample N  -> out/structure-apply/sample.jsonl, for judging
Nothing here writes ontology/; the write is its own step, after the sample is judged.
"""
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
sys.stdout.reconfigure(encoding="utf-8")
OUT = ROOT / "out" / "structure-apply"
DONE = ROOT / "out" / "grunt" / "done"
INTAKE = ROOT / "out" / "orchestra-intake"
JOBS = [("20s-structure-relations", "20s-structure-relations"),
        ("22-structure-relations-concepts", "22-structure-relations-concepts")]
DIVINE_IDS = {"god", "the_father", "jesus", "holy_ghost", "spirit_of_the_lord_in_the_hebrew_bible", "spirit", "spirit_of_god", "holy_spirit"}
DIVINE_WORDS = re.compile(r"\b(lord|god|jesus|christ|holy spirit|spirit of god|the father|almighty|yahweh|"
                          r"son of man|lamb of god)\b", re.I)
SPEECH = re.compile(r"^(said|say|says|told|tell|spoke|speak|speaks|answered|asked|called|cried|declared|commanded|"
                    r"replied|proclaimed|preached|wrote|sang|prayed)\b", re.I)
ARTICLE = re.compile(r"^(the|a|an|his|her|their|its|my|your|our)\s+", re.I)
TITLE = re.compile(r"^(king|queen|prophet|priest|the prophet|the priest|pharaoh)\s+", re.I)


def readings():
    """(item, Mac answer) for every stated reading of both jobs."""
    for done, intake in JOBS:
        items = {}
        for l in open(INTAKE / intake / "items.jsonl", encoding="utf-8"):
            it = json.loads(l)
            items[it["key"]] = it
        for l in open(DONE / f"{done}.jsonl", encoding="utf-8"):
            d = json.loads(l)
            try:
                a = json.loads(d["content"])
            except (ValueError, KeyError, TypeError):
                continue
            if a.get("verdict") == "stated" and d["key"] in items:
                yield items[d["key"]], a


def a51_akas():
    """A.51's alias map (out/structure-apply/a51-akas.json): name -> {card, reason, refs?}. Used only after the name
    index fails; the entity records' aka are untouched (an ontology decision Doug reviews). A name with refs maps
    only in those books/chapters."""
    p = OUT / "a51-akas.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def resolve():
    import server as S
    d = S.load()
    ents, aix = d["ents"], d["alias_ix"]
    akas = a51_akas()

    def cites(eid, ref):
        """Whether the card already cites this verse (any relation of it, either end)."""
        for r in d["rels"].get(eid, []):
            if any(str(x).replace(" ", "").startswith(ref.split(".")[0]) and x.endswith(ref.split(".", 1)[1].replace(".", ":"))
                   for x in r.get("refs", [])):
                return True
        return False

    def find(name, ref):
        if not name:
            return None, "no other end named"
        if DIVINE_WORDS.search(name):
            return None, "divine (Doug's)"
        n = ARTICLE.sub("", name.strip())
        # the name as written ("the Levites" is a card's own name), without its article, without a title ("King
        # Hezekiah": 7 readings, all held as "no card" until 2026-11-13), and singular
        cands = []
        for v in (name.strip(), n, TITLE.sub("", n), n[:-1] if n.endswith("s") else ""):
            if v and not cands:
                cands = [x for x in aix.get(S._slug(v), ()) if x in ents]
        cands = sorted(set(cands))
        if not cands:
            for v in (name.strip().lower(), n.lower(), TITLE.sub("", n).lower()):
                m = akas.get(v)
                if m and m["card"] in ents and (not m.get("refs") or any(ref.startswith(x) for x in m["refs"])):
                    return m["card"], "A.51 alias: " + m["reason"]
            return None, "no card by that name"
        if any(c in DIVINE_IDS for c in cands):
            return None, "divine (Doug's)"
        if len(cands) == 1:
            return cands[0], "one card by that name"
        here = [c for c in cands if cites(c, ref)]
        if len(here) == 1:
            return here[0], "the one of its namesakes this verse already names"
        return None, f"{len(cands)} cards by that name"

    OUT.mkdir(parents=True, exist_ok=True)
    tally, rows = collections.Counter(), []
    for it, a in readings():
        card = it["card"]
        act = (a.get("act") or it.get("verb_text") or "").strip()
        rec = {"key": it["key"], "card": card, "role": it["role"], "ref": it["ref"], "act": act,
               "words": a.get("words"), "verse": it.get("verse"), "who": a.get("who")}
        if card in DIVINE_IDS:
            rec["held"] = "divine (Doug's)"
        elif SPEECH.match(act):
            rec["held"] = "speech (the graph's speech rule)"
        elif it["role"] == "o":
            other, why = find(a.get("who") or it.get("doer"), it["ref"])
            rec.update(src=other, dst=card, resolved_by=why)
            if not other:
                rec["held"] = why
        else:
            m = re.search(r"THING\s+(.+)$", it.get("claim") or "")
            thing = m.group(1).strip() if m else ""
            if thing in ("(none)", ""):
                rec.update(src=card, dst=None, resolved_by="no thing: an act of the card alone")
                rec["held"] = "no other end (an act of the card alone)"
            else:
                other, why = find(thing, it["ref"])
                rec.update(src=card, dst=other, resolved_by=why)
                if not other:
                    rec["held"] = why
        tally[rec.get("held") or "resolved"] += 1
        rows.append(rec)
    with open(OUT / "resolved.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows)} stated readings")
    for k, n in tally.most_common():
        print(f"  {n:5}  {k}")


PRONOUN = {"he", "she", "they", "you", "we", "i", "it", "him", "them", "man", "a man", "anyone", "people", "woman",
           "someone", "one", "each", "everyone", "whoever", "those", "the one", "each man", "the speaker"}
NEG = re.compile(r"\b(not|never|no|nor|neither|if)\b", re.I)


def act_map():
    """act -> type, from DeepSeek's actmap answers (.delegate/results in the main checkout), the later answer winning."""
    res = ROOT.parents[2] / ".delegate" / "results" if (ROOT.parents[2] / ".delegate").exists() else ROOT / ".delegate" / "results"
    m = {}
    for p in sorted(res.glob("*.md")):
        t = p.read_text(encoding="utf-8", errors="replace")
        if "You map verbs from Bible verses" not in t or "## Answer" not in t:
            continue
        ans = t.split("## Answer", 1)[1].split("\n## Tool calls", 1)[0]
        s, e = ans.find("["), ans.rfind("]")
        try:
            for x in json.loads(ans[s:e + 1]):
                m[(x.get("act") or "").lower().strip()] = (x.get("type") or "none").strip()
        except ValueError:
            continue
    return m


def build(write=False):
    """The gates of object_relations.apply over the resolved rows, with DeepSeek's act map checked in code against
    the vocabulary's own src/dst kinds. Every row's fate goes to the trail."""
    import yaml
    types = yaml.safe_load((ROOT / "ontology" / "schema" / "relationship_types.yaml").read_text(encoding="utf-8"))
    types = types.get("types", types)
    ents = {}
    for path in sorted((ROOT / "ontology" / "entities").glob("*.jsonl")):
        for line in open(path, encoding="utf-8"):
            e = json.loads(line)
            if e.get("id"):
                ents.setdefault(e["id"], e)
    amap = act_map()
    rels, trail = [], []
    for line in open(OUT / "resolved.jsonl", encoding="utf-8"):
        r = json.loads(line)
        plain = (r.get("verse") or "").replace("«", "").replace("»", "")
        words = (r.get("words") or "").replace("«", "").replace("»", "")
        typ = amap.get(r["act"].lower())
        other = r.get("src") if r["role"] == "o" else r.get("dst")
        named = (r.get("who") if r["role"] == "o" else None)
        fate = r.get("held")
        if fate:
            pass
        elif typ is None:
            fate = "act not yet mapped"
        elif typ == "none" or typ not in types:
            fate = "no type for the act"
        elif named is not None and re.sub(r"^the ", "", named.lower().strip()) in PRONOUN:
            fate = "doer is a pronoun or unnamed"
        elif words and words not in plain:
            fate = "quoted words not in the verse"
        elif NEG.search(words):
            fate = "negated"
        elif ents.get(other, {}).get("type") in ("person", "group") and \
                (ents[other].get("name") or "").lower().split()[0] not in plain.lower():
            fate = "the other end is not named in the verse"
        else:
            spec = types[typ] or {}
            st, dt = ents.get(r["src"], {}).get("type"), ents.get(r["dst"], {}).get("type")
            if st not in (spec.get("src_type") or [st]) or dt not in (spec.get("dst_type") or [dt]):
                fate = f"{typ} does not take {st} -> {dt}"
            else:
                b, c, v = r["ref"].split(".")
                rels.append({"certainty": "explicit", "dst": r["dst"], "note": words, "refs": [f"{b} {c}:{v}"],
                             "source": "structure-relations-2026-11-13", "src": r["src"], "type": typ})
                fate = "applied"
        trail.append({"key": r["key"], "row": r, "type": typ, "fate": fate})
    have = set()
    for path in (ROOT / "ontology" / "relations").glob("*.jsonl"):
        if path.name.startswith("structure-relations-"):
            continue
        for line in open(path, encoding="utf-8"):
            if line.strip():
                x = json.loads(line)
                have.add((x.get("src"), x.get("type"), x.get("dst")))
    merged = {}
    for x in rels:
        k = (x["src"], x["type"], x["dst"])
        if k in have:
            continue
        if k in merged:
            merged[k]["refs"] += [q for q in x["refs"] if q not in merged[k]["refs"]]
        else:
            merged[k] = dict(x)
    sys.path.insert(0, str(ROOT / "tools" / "meaning"))
    from hold_quoted_relations import categories, to_hold
    from quoted import berean_quotes
    cat, (quotes, _texts) = categories(), berean_quotes()
    out = [x for x in merged.values() if not to_hold(x, cat, quotes)]
    print(len(rels), "passed the gates;", len(merged), "new after merging and the graph's own;",
          len(out), "after the speech rule")
    print(collections.Counter(t["fate"].split(" does not")[0] if "does not take" not in t["fate"] else "type's kinds do not fit"
                              for t in trail).most_common(16))
    (OUT / "rows.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out), encoding="utf-8")
    (OUT / "trail.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in trail), encoding="utf-8")
    if write:
        (ROOT / "ontology" / "relations" / "structure-relations-2026-11-13.jsonl").write_text(
            "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out), encoding="utf-8", newline="\n")
        (ROOT / "ontology" / "provenance" / "meaning" / "structure-relations-2026-11-13.jsonl").write_text(
            "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in trail), encoding="utf-8", newline="\n")
        print("written")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "resolve":
        resolve()
    elif cmd == "rows":
        build()
    elif cmd == "write":
        # ONLY THE ROWS BOTH BLIND RUNS JUDGED RIGHT (tools/meaning/structure_judge.py tally), with every judged row's
        # two verdicts kept in provenance beside the gates' trail
        kept = []
        for f in ("kept.jsonl", "kept-set2.jsonl"):
            kept += [json.loads(l) for l in open(OUT / f, encoding="utf-8")]
        # WHAT THE VALIDATOR REFUSED of the judged rows (2026-11-13), dropped here, never forced: a self loop ("the
        # thin cows ate the fat cows", one card for both); a parent relation from a word card ("wife", "concubine":
        # both judges called "his wife bore a son" right, the exact error the brief's worked example names); a group
        # that requires its scope (the Jews); and two book codes MACULA spells otherwise
        books = {"Amo": "Amos", "Ecc": "Eccl"}
        ents = {}
        for path in sorted((ROOT / "ontology" / "entities").glob("*.jsonl")):
            for line in open(path, encoding="utf-8"):
                e = json.loads(line)
                ents.setdefault(e.get("id"), e)
        out = []
        for x in kept:
            if x["src"] == x["dst"] or "jews" in (x["src"], x["dst"]):
                continue
            if x["type"] in ("mother_of", "father_of") and any(ents.get(e, {}).get("type") != "person"
                                                                for e in (x["src"], x["dst"])):
                continue
            x["refs"] = [books.get(r.split()[0], r.split()[0]) + " " + r.split(" ", 1)[1] for r in x["refs"]]
            out.append(x)
        print(len(kept) - len(out), "dropped by the validator's rules")
        kept = out
        (ROOT / "ontology" / "relations" / "structure-relations-2026-11-13.jsonl").write_text(
            "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in kept), encoding="utf-8", newline="\n")
        prov = {"gates": [json.loads(l) for l in open(OUT / "trail.jsonl", encoding="utf-8")]}
        for tag in ("", "-set2"):
            rows = [json.loads(l) for l in open(OUT / f"rows{tag or '-set1'}.jsonl", encoding="utf-8")]
            j = json.load(open(OUT / f"judged{tag}.json", encoding="utf-8"))
            prov[f"judged{tag or '-set1'}"] = [{"row": r, "A": j["A"].get(str(i)), "B": j["B"].get(str(i))}
                                               for i, r in enumerate(rows)]
        (ROOT / "ontology" / "provenance" / "meaning" / "structure-relations-2026-11-13.json").write_text(
            json.dumps(prov, ensure_ascii=False), encoding="utf-8", newline="\n")
        print(len(kept), "relations written")
    else:
        print(__doc__)
