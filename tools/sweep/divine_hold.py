"""PATTERN A, APPROVED, WITH PARABLES HELD (2026-10-17: approved,
parables held; the case was Luke 12:37, a parable's master resolved to Jesus).

A divine flag of pattern A (a pronoun pointing to a divine word, divine_sheet.py)
is HELD for the parable pass (plan 1.39) when either:
  1. its verse lies inside a parable the event list knows (its tellings'
     ranges, events-copilot.jsonl), or
  2. it is a third-person pronoun or unstated subject resolved to Jesus in a
     Gospel chapter whose Berean text mentions a parable: the parable's shape is
     Jesus speaking of a master, a son, a sower, and of himself he says "I".
     This catches parables the list does not have (Luke 12:37 is not on it).
     It holds narration too ("He replied"): held flags go to the parable pass,
     an automated check against the text's own explanation, so holding too
     many costs little and holding too few would let a parable through.
     WRONG TURN, KEPT: the first test held a third person "inside Jesus'
     speech" when the verse had a turn spoken by Jesus. At verse level it
     could not tell narration from speech: it held John 1:38's "He turned"
     and missed Luke 12:37, the case that started it.
Every other pattern A flag is approved. Writes the decisions with the reason.
Patterns B and C and the 130 one by one were approved afterwards (see REST).

    python tools/sweep/divine_hold.py   -> out/sweep/divine-decisions.json, counts
"""
import collections
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIRST = ROOT / "out" / "sweep" / "runs" / "sweep-1"
MERGED = ROOT / "out" / "sweep" / "runs" / "resolve-1" / "merged"
BOOK = {"Matthew": "Mat", "Mark": "Mrk", "Luke": "Luk", "John": "Jhn"}


def parable_verses():
    out = set()
    for line in open(ROOT / "ontology" / "entities" / "events-copilot.jsonl", encoding="utf-8"):
        d = json.loads(line)
        if "parable" not in (d.get("id", "") + d.get("name", "")).lower():
            continue
        for b, c, v1, v2 in re.findall(r"(Matthew|Mark|Luke|John) (\d+):(\d+)(?:[–-](\d+))?", d.get("desc") or ""):
            for v in range(int(v1), int(v2 or v1) + 1):
                out.add(f"{BOOK[b]}.{c}.{v}")
    return out


def main():
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from divine_sheet import group
    rows = json.loads((ROOT / "out" / "sweep" / "divine-flags.json").read_text(encoding="utf-8"))
    nodes = {}
    with gzip.open(ROOT / "out" / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("word") or d.get("local", "").startswith("cl"):
                nodes[d["id"]] = d
    pv = parable_verses()
    GOSPEL = {"Matt": "Mat", "Mark": "Mrk", "Luke": "Luk", "John": "Jhn"}
    pch = set()
    for line in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        d = json.loads(line)
        if d.get("b") in GOSPEL and "parable" in (d.get("t") or "").lower():
            pch.add(f"{GOSPEL[d['b']]}.{d['c']}")

    def third(r):
        s = r.get("slot") or ""
        n = nodes.get(f"{r['ref']}#{s[:-1] if s.endswith('s') and s.startswith('cl') else s}") or {}
        person = n.get("verb_person") if s.startswith("cl") else n.get("person")
        return (person or "").startswith("third")

    def jesus_speaks(ref):
        p = MERGED / f"{ref}.json"
        p = p if p.exists() else FIRST / f"{ref}.json"
        if not p.exists():
            return False
        a = json.loads(p.read_text(encoding="utf-8"))
        for g in a.get("groups") or []:
            if g.get("kind") == "turn":
                for m in g.get("members") or []:
                    node = m.get("node")
                    if m.get("role") == "sender" and isinstance(node, str):
                        full = node if "#" in node else f"{ref}#{node}"
                        if (nodes.get(full) or {}).get("text") == "Jesus":
                            return True
            # a speech carried on from an earlier verse whose speaker the
            # first pass named: the extend points at it
            if g.get("action") == "extend" and isinstance(g.get("id"), str) and "#" in g["id"]:
                return jesus_speaks_cached(g["id"].split("#")[0])
        return False

    cache = {}

    def jesus_speaks_cached(ref):
        if ref not in cache:
            cache[ref] = False          # guards a cycle of extends
            cache[ref] = jesus_speaks(ref)
        return cache[ref]

    out, why = [], collections.Counter()
    # THE REST OF THE SHEET (later 2026-10-17: that was all the
    # feedback from the sheet, everything else looked good). The four cases;
    # none of them is a wrong link. A "Peter and and" is the
    # builder's coordination fault (P-2026-10-17-4), and a generic the text names
    # is fixed at the import (P-2026-10-17-5). Both are noted on the decision,
    # so the import finds them.
    REST = {"B": "pattern B (Doug, 2026-10-17)", "C": "pattern C (Doug, 2026-10-17)",
            "several": "one by one, several together (Doug, 2026-10-17: everything else looks good)",
            "god": "one by one, lowercase god: the gloss of the word, not a judgement (Doug, 2026-10-17)"}
    # WRONG, on a reader's reading (2026-10-17): Luke
    # 22:8's "for us" and "we might eat" are Jesus with the disciples who eat
    # (22:11, 22:14), not only the two he sends; the pick's own note said "the
    # Twelve". Back to the resolver, not approved.
    WRONG = {("Luk.22.8", "w8"), ("Luk.22.8", "cl4s")}
    for r in rows:
        g = group(r)
        if (r["ref"], r.get("slot")) in WRONG:
            why[("rejected", "Doug, 2026-10-17")] += 1
            out.append({**r, "decision": "rejected", "reason": "narrower than the text: Jesus with the disciples who eat "
                        "(Luke 22:11, 22:14), not only Peter and John (Doug, 2026-10-17)"})
            continue
        if g in REST:
            notes = []
            if any(re.search(r"\b(\w+) \1$", n or "") for n in r["names"]):
                notes.append("coordination member fault, P-2026-10-17-4")
            if any("generic:" in (n or "") for n in r["names"]):
                notes.append("generic to check against the text's own word, P-2026-10-17-5")
            reason = REST[g] + ("; " + "; ".join(notes) if notes else "")
            why[("approved", REST[g])] += 1
            out.append({**r, "decision": "approved", "reason": reason})
            continue
        if g != "A":
            continue
        # THE HOLD, RELEASED (2026-10-17, released): the example it
        # was approved on was a misreading (Luke 12:37's flag is "Truly I tell
        # you", Jesus, right), and 16 of 16 held flags sampled were right. The
        # tests stay, to say which flags they were, for the parable pass (1.39).
        if r["ref"] in pv:
            dec, reason = "approved", "pattern A; inside a listed parable (hold released)"
        elif r["names"] == ["Jesus"] and third(r) and ".".join(r["ref"].split(".")[:2]) in pch:
            dec, reason = "approved", "pattern A; a third person to Jesus in a parable chapter (hold released)"
        else:
            dec, reason = "approved", "pattern A (Doug, 2026-10-17)"
        why[(dec, reason)] += 1
        out.append({**r, "decision": dec, "reason": reason})
    (ROOT / "out" / "sweep" / "divine-decisions.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    for (d, r), n in why.most_common():
        print(f"{n:6,}  {d:9s} {r}")
    held = [x for x in out if x["decision"] == "held"]
    print("Luke 12:37 held:", any(x["ref"] == "Luk.12.37" for x in held))
    print("sample held:", [(x["ref"], x["names"]) for x in held[:8]])


if __name__ == "__main__":
    main()
