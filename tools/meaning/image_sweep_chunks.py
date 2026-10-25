"""THE SWEEP'S INPUTS (plan 8.2h, 2026-10-24): every verse on an image card, in chunks of 100, each verse with the
one before and after, for a reader who must use no shell.

The candidate pass found a figure only where something already marked one (a simile, a metaphor, a citation), and
on the 42 swept cards the full sweep then found 2,855 figures it never had: "the hand of the LORD" is a figure in the
word itself. So a card is swept whole before it is built.

    python tools/meaning/image_sweep_chunks.py IMAGE [IMAGE ...] [--port 8012]
      -> out/meaning/image-audit/sweep/<image>-<n>.json, and the ids appended to chunks.json
    python tools/meaning/image_sweep_chunks.py --rest [--port 8012]
      every image not yet audited with 1-99 verses, several small cards PACKED into one chunk of ~100 verses
      (pack-<n>.json; each verse carries its own image, name and desc), so 137 small cards take ~40 readers, not 137
"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from derive import BOOK  # noqa: E402

S = ROOT / "out" / "meaning" / "image-audit" / "sweep"
PORT = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8012


def card_verses(img, ctx):
    with urllib.request.urlopen(f"http://localhost:{PORT}/api/entity-verses?id={img}", timeout=120) as r:
        d = json.load(r)
    refs = [it["eref"] for b in d.get("books") or [] for it in b.get("items") or []]
    return [v for v in (ctx(ref) for ref in refs) if v], d.get("total")


def rest():
    A = ROOT / "out" / "meaning" / "image-audit"
    audited = {x["image"] for x in json.loads((A / "candidates" / "index.json").read_text(encoding="utf-8"))}
    audited |= {"image_wine", "image_lion", "image_vine", "image_candlestick", "image_lamb", "image_clothes",
                "image_ox", "image_bread", "image_temple"}
    todo = [r["id"] for r in (json.loads(l) for l in open(A / "images.jsonl", encoding="utf-8"))
            if r["id"] not in audited and 0 < r["verses"] < 100]
    ctx, ents = context()
    chunks = json.loads((S / "chunks.json").read_text(encoding="utf-8"))
    pack, n, made = [], 0, []

    def flush():
        nonlocal pack, n
        if pack:
            cid = f"pack-{n}"
            (S / f"{cid}.json").write_text(json.dumps({"chunk": cid, "packed": True, "verses": pack},
                                                      ensure_ascii=False, indent=1), encoding="utf-8")
            made.append(cid)
            if cid not in chunks:
                chunks.append(cid)
            pack, n = [], n + 1
    for img in todo:
        vs, _ = card_verses(img, ctx)
        e = ents.get(img) or {}
        if pack and len(pack) + len(vs) > 100:
            flush()
        pack += [{"image": img, "name": e.get("name"), "desc": e.get("desc"), **v} for v in vs]
    flush()
    (S / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    print(f"{len(todo)} cards in {len(made)} packed chunks: {json.dumps(made)}")


def fix():
    """the verses the first cut showed with a neighbour's text (their Berean and MACULA numbers differ), packed into
    fix-<n>.json with their own text, to be read again; settle lets these readings replace the first ones"""
    moved = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8"))["moved"]
    to_mac = {b: m for m, b in moved.items()}
    settled = json.loads((S / "settled.json").read_text(encoding="utf-8"))["final"]
    keys = sorted(k for k in settled if to_mac.get(k.split("|")[1], k.split("|")[1]) != k.split("|")[1])
    ctx, ents = context()
    chunks = json.loads((S / "chunks.json").read_text(encoding="utf-8"))
    made = []
    for n in range(0, len(keys), 100):
        vs = []
        for k in keys[n:n + 100]:
            img, ref = k.split("|")
            v = ctx(ref)
            if v:
                e = ents.get(img) or {}
                vs.append({"image": img, "name": e.get("name"), "desc": e.get("desc"), **v})
        cid = f"fix-{n // 100}"
        (S / f"{cid}.json").write_text(json.dumps({"chunk": cid, "packed": True, "verses": vs}, ensure_ascii=False,
                                                  indent=1), encoding="utf-8")
        made.append(cid)
        if cid not in chunks:
            chunks.append(cid)
    (S / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    print(f"{len(keys)} verses to read again in {len(made)} chunks: {json.dumps(made)}")


def context():
    order, text = [], {}
    for ln in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        if "b" in d:
            k = f"{BOOK.get(d['b'], d['b'])}.{d['c']}.{d['v']}"
            order.append(k)
            text[k] = d["t"]
    pos = {k: i for i, k in enumerate(order)}
    moved = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8"))["moved"]
    ents = {}
    for ln in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        if ln.strip():
            e = json.loads(ln)
            ents[e["id"]] = e

    # A CARD'S VERSES ARE IN THE BEREAN'S NUMBERING (2026-10-25): the server shows Malachi 4, which MACULA's Hebrew
    # does not have. The first cut ran them through versemap's MACULA->Berean map as if they were MACULA, so where the
    # two count differently (psalm titles, Joel, Malachi: 1,699 of 27,614 swept verses) the reader got the
    # NEIGHBOURING verse's text under the right reference: "Psa.34.15" showed "Turn away from evil", and the readers
    # found "the eyes of the LORD" in the verse after. Look the verse up by its own number.
    def ctx(ref):
        k = ref
        i = pos.get(k)
        if i is None:
            return None
        return {"ref": ref, "before": text[order[i - 1]] if i else None, "text": text[k],
                "after": text[order[i + 1]] if i + 1 < len(order) else None}
    return ctx, ents


def main(images):
    order, text = [], {}
    for ln in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        if "b" in d:
            k = f"{BOOK.get(d['b'], d['b'])}.{d['c']}.{d['v']}"
            order.append(k)
            text[k] = d["t"]
    pos = {k: i for i, k in enumerate(order)}
    moved = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8"))["moved"]
    ents = {}
    for ln in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        if ln.strip():
            e = json.loads(ln)
            ents[e["id"]] = e
    chunks = json.loads((S / "chunks.json").read_text(encoding="utf-8"))
    for img in images:
        with urllib.request.urlopen(f"http://localhost:{PORT}/api/entity-verses?id={img}", timeout=120) as r:
            d = json.load(r)
        refs = [it["eref"] for b in d.get("books") or [] for it in b.get("items") or []]
        verses = []
        for ref in refs:
            k = ref  # the card's own (Berean) number; see ctx() in context()
            i = pos.get(k)
            if i is None:
                continue
            verses.append({"ref": ref, "before": text[order[i - 1]] if i else None, "text": text[k],
                           "after": text[order[i + 1]] if i + 1 < len(order) else None})
        e = ents.get(img) or {}
        for n in range(0, len(verses), 100):
            cid = f"{img}-{n // 100}"
            (S / f"{cid}.json").write_text(json.dumps(
                {"chunk": cid, "image": img, "name": e.get("name"), "desc": e.get("desc"),
                 "verses": verses[n:n + 100]}, ensure_ascii=False, indent=1), encoding="utf-8")
            if cid not in chunks:
                chunks.append(cid)
        print(f"{img}: {len(verses)} of {d.get('total')} verses, {(len(verses) + 99) // 100} chunks")
    (S / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    if "--rest" in sys.argv:
        rest()
    elif "--fix" in sys.argv:
        fix()
    else:
        main([a for a in sys.argv[1:] if not a.startswith("--") and not a.isdigit()])
