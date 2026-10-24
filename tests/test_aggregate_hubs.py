"""Every aggregate card is a hub, and every link on it rests on a verse (A.34).

2026-10-07, on the armor of God's collection card: nothing in the member
diagram was clickable, though it is meant to act as a hub for exploring the
concepts listed and even the moves; the card was labeled "aggregates", and the
fruit of the spirit had the same issue. The card showed taxonomy ids ("armor
of god", "sword of the spirit", "wisdom s") as plain chips. This checks
ontology/aggregate-hubs.json, which the card now reads instead:
  - every aggregate in the taxonomy has a hub entry with a label and ONE
    card in the graph (two cards for one list were confusing), and every
    member a node (a concept or image node for each member);
  - every member and move has a verse, and its words are in that verse's
    Berean text (a leading "the", "a" or "an" aside);
  - every member's card exists, and no member is wired by rule to a divine
    person (God, the Father, Jesus, the Holy Spirit change only by hand);
  - a member that is a figure opens the whole symbol ("the breastplate of
    righteousness"), and that image links to what it stands for (a gateway
    to righteousness), never a bare object image;
  - the labels keep the text's capitals: no "god", "spirit of", "lord" where
    the Berean capitalises;
  - the card draws members with a card as record links and every other member
    and move as a verse link, through the page's delegated listener, so a
    restored tab keeps working.
Run: python tests/test_aggregate_hubs.py"""
import glob
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
fails = []

V = {}
for line in (ROOT / "data" / "bible" / "verses.bsb.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        d = json.loads(line)
        if "b" in d:
            V[f"{d['b']} {d['c']}:{d['v']}"] = d["t"]
ENTS = {}
for f in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
    for line in open(f, encoding="utf-8"):
        if line.strip():
            e = json.loads(line)
            ENTS[e["id"]] = e
DIVINE = {"god", "the_father", "jesus", "holy_ghost"}
# an image with a link to what it stands for: its gloss (speaks_of) or the
# text's own key (signifies)
GATEWAY = set()
for f in glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl")):
    for line in open(f, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            if r["type"] in ("speaks_of", "signifies") and ENTS.get(r["dst"], {}).get("type") != "image":
                GATEWAY.add(r["src"])

hubs = json.loads((ROOT / "ontology" / "aggregate-hubs.json").read_text(encoding="utf-8"))
tax = json.loads((ROOT / "ontology" / "interest-taxonomy.json").read_text(encoding="utf-8"))
for a in tax["aggregates"]["items"]:
    if a["id"] not in hubs:
        fails.append(f"{a['id']}: no entry in ontology/aggregate-hubs.json")

flat = lambda s: re.sub(r"[‘’']", "'", re.sub(r"\s+", " ", s)).lower()
n_links = 0
for aid, h in hubs.items():
    if aid.startswith("_"):
        continue
    if not h.get("label"):
        fails.append(f"{aid}: no label")
    # one card per list (two cards for one list were confusing)
    if h.get("card") not in ENTS:
        fails.append(f"{aid}: card {h.get('card')} is not in the graph (run tools/aggregate_nodes.py)")
    for m in h.get("members") or []:
        if not m.get("card"):
            fails.append(f"{aid}: member '{m['label']}' has no node (Doug: \"concept or image nodes "
                         f"for all the members\")")
    for what, rows in (("member", h.get("members") or []), ("move", h.get("moves") or [])):
        for m in rows:
            words = m.get("label") if what == "member" else m.get("words")
            ref = m.get("ref")
            n_links += 1
            if ref not in V:
                fails.append(f"{aid} {what} '{words}': no Berean verse {ref}")
                continue
            w = re.sub(r"^(the|a|an) ", "", flat(words))
            if w not in flat(V[ref]):
                fails.append(f"{aid} {what} '{words}' is not in {ref}: {V[ref]}")
            card = m.get("card")
            if card and card not in ENTS:
                fails.append(f"{aid} {what} '{words}': card {card} is not in the graph")
            if card in DIVINE:
                fails.append(f"{aid} {what} '{words}' is wired to a divine person ({card}); by hand only")
            # a figure opens the whole symbol, and the symbol is the gateway to
            # what it stands for (2026-10-07: what matters most in the belt of
            # truth is not the belt but the truth; the breastplate of
            # righteousness is a gateway to righteousness)
            if what == "member" and ENTS.get(card, {}).get("type") == "image":
                sym = re.sub(r"^(the|a|an) ", "", flat(ENTS[card]["name"]))
                if not re.sub(r"s$", "", flat(words)).endswith(re.sub(r"s$", "", sym)):
                    fails.append(f"{aid} member '{words}' opens '{ENTS[card]['name']}' ({card}), "
                                 f"not the whole symbol")
                if card not in GATEWAY:
                    fails.append(f"{aid} member '{words}' opens an image ({card}) that leads to nothing it stands for")
    for s in [h.get("label", "")] + [m.get("label", "") for m in h.get("members") or []]:
        if re.search(r"\bgod\b|\bof the spirit\b|\blord\b", s):
            fails.append(f"{aid}: '{s}' loses the text's capitals")

# the page: members and moves are drawn as links the delegated listener serves
page = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
body = page.split("function hubBlock", 1)[1].split("\nasync function ", 1)[0]
if 'class="mem link" data-ent=' not in body:
    fails.append("index.html: a member with a card is not drawn as a record link (.link[data-ent])")
if not re.search(r'class="mem[^"]*" data-go=', body):
    fails.append("index.html: a member without a card is not drawn as a verse link (data-go)")
if not re.search(r'class="move[^"]*" data-go=', body):
    fails.append("index.html: a move is not drawn as a verse link (data-go)")
if "if(r.redirect){ openEntity(r.redirect); return; }" not in page:
    fails.append("index.html: a list's chip does not open the list's one card (r.redirect)")
if "'.link[data-ent],.entnode[data-ent]'" not in page:
    fails.append("index.html: the delegated listener does not serve a card diagram's nodes (.entnode)")

print(f"{len([k for k in hubs if not k.startswith('_')])} aggregate hubs, {n_links} member and move links "
      f"checked against the Berean, {len(fails)} failures")
for f in fails:
    print("FAIL", f)
sys.exit(1 if fails else 0)
