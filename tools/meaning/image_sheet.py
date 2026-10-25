"""THE ONE SHEET for the image audit's eight (plan 8.2h): every decision "as
recommended" unless Doug overrides it by number, as for temple.

Reads the eight evidence packs, the blind second readings, the third reader's
tie-break, and writes docs/review/image-audit-2026-10-24/SHEET.md.

    python tools/meaning/image_sheet.py
"""
import collections
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKS = ROOT / "out" / "meaning" / "image-audit" / "packs"
OUT = ROOT / "docs" / "review" / "image-audit-2026-10-24" / "SHEET.md"
ORDER = ["image_wine", "image_lion", "image_vine", "image_candlestick", "image_lamb", "image_clothes", "image_ox",
         "image_bread"]
PLACE = {"literal": "the literal card", "figure": "the image card", "figure_keyed": "the image card",
         "both": "both cards"}

# where the sheet recommends otherwise than the gatherer, and why (Claude, 2026-10-24)
OVERRIDE = {
    ("image_lion", "signifies", "judah"): ("drop", "Gen 49:9 is a likening, and `judah likened_to image_lion` already "
                                          "exists; the post says the same of this verse"),
    ("image_lion", "signifies", "dan"): ("likened_to", "Deut 33:22 'Dan is a lion's cub' is a likening, as Judah's is: "
                                         "dan likened_to image_lion"),
    ("image_lamb", "signifies", "jesus"): ("hold", "for the Lamb talk-through, as Doug asked"),
}
BLOCKED = {("image_clothes", "signifies")}         # targets the schema does not allow yet


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main():
    tb = load(PACKS / "tiebreak-result.json")
    tb_by = collections.defaultdict(list)
    for t in tb:
        tb_by[t["image"]].append(t)
    agree = {a["image"]: a for a in map(load, glob.glob(str(PACKS / "*.agreement.json")))}
    n = 0
    lines = []
    W = lines.append

    def num():
        nonlocal n
        n += 1
        return n

    tot_asked = sum(a["asked"] for a in agree.values())
    tot_on = sum(a["agree_on_card"] for a in agree.values())
    three = [t for t in tb if t["status"] != "settled"]
    W("# The image audit, the first eight: your one sheet (plan 8.2h, 2026-10-24)")
    W("")
    W("**How to answer:** everything below is \"as recommended\" unless you say otherwise. Reply \"all as "
      "recommended\", or with the numbers you want to change.")
    W("")
    W("**What was done to get here:**")
    W("- **Eight evidence packs**, one per image: every verse on the image card and its literal card, read in "
      "context and sorted literal, figure, figure with a stated key, both, readers differ, or another sense "
      "(`out/meaning/image-audit/packs/`).")
    W(f"- **A blind second reader** for every non-literal verse and 40 literal ones: they agree on the card for "
      f"**{tot_on} of {tot_asked}**.")
    W(f"- **A third blind reader** for the {len(tb)} splits: two of three settled {len(tb) - len(three)}; "
      f"{len(three)} split three ways and are yours (item 1).")
    W("- **Not on this sheet:** the cards' descriptions. They are rewritten after this, from what you rule, and go "
      "to the eleven-reader panel as all site voice does.")
    W("")

    W("## The decisions that are really yours")
    W("")
    k = num()
    W(f"**{k}. The five three-way splits.** Recommended: **neither card** for now, each named for the description "
      "to mention if the panel wants it.")
    W("")
    W("| verse | image | first reader | second | third |")
    W("|---|---|---|---|---|")
    for t in three:
        W(f"| {t['ref']} | {t['image'].replace('image_', '')} | {t['first']} | {t['blind']} | {t['third']} |")
    W("")
    W(f"**{num()}. The Lamb in Revelation.** All 27 uses of ἀρνίον are figures (both readers), so the 2026-10-20 "
      "ruling that put them on the creature card is contradicted. Recommended: **off the creature card, onto the "
      "image card**; John 21:15 (\"Feed My lambs\", Peter's flock) onto the image card as a figure of its own. "
      "Which person the Lamb of Revelation is, is **not** decided here: the existing `image_lamb signifies jesus` "
      "(Rev 5:6, 5:12, implied) stays as it is, for our talk-through.")
    W("")
    W(f"**{num()}. \"The Lamb of God\" (John 1:29, 1:36).** John the Baptist names Jesus outright. The pack proposes "
      "`image_lamb signifies jesus`, explicit, claimed by John the Baptist. Recommended: **hold for the Lamb "
      "talk-through**, with item 2.")
    W("")
    W(f"**{num()}. Manna and the bread of life.** The existing `manna signifies the_bread_of_life` is contradicted "
      "by John 6:32 (\"it was not Moses who gave you the bread from heaven\") and 6:49 (\"Your fathers ate the "
      "manna in the wilderness, yet they died\"): the text contrasts them. Recommended: **retire it**, and add "
      "`image_bread signifies jesus` (John 6:35, \"I am the bread of life\", Jesus).")
    W("")
    W(f"**{num()}. Wine and vine have no Greek.** Both cards carry only the Hebrew word, so \"I am the true vine\" "
      "(John 15) and every New Testament wine verse are on no card, though the wine description quotes John 2:9. "
      "Recommended: **add οἶνος and ἄμπελος to the cards, verse by verse**, as the packs sorted them.")
    W("")
    W(f"**{num()}. Clothes and garment** share 224 of 260 verses: one thing recorded twice, by the look of it. "
      "Recommended: **not merged here**; it goes with the twin-cards question (P-2026-10-24-1), two judges and "
      "then you.")
    W("")
    W(f"**{num()}. Three links the schema cannot hold yet:** `image_clothes signifies` strength and honor (Prov "
      "31:25) and iniquity (Zech 3:4): `signifies` may not point at a concept or an assessment. Recommended: **wait "
      "for the vocabulary release after the post**, with the Lamb's and the events'.")
    W("")
    W(f"**{num()}. Records the packs say are missing** (the king of Assyria in Jer 50:17, Ezekiel's Pharaoh, the "
      "earth beast, the seven spirits, and others: listed per image below). Recommended: **not created now**; a "
      "relation that needs one waits.")
    W("")

    W("## Each image")
    W("")
    for img in ORDER:
        p = load(PACKS / f"{img}.json")
        a = agree.get(img, {})
        c = p.get("counts") or {}
        lit = ", ".join(p.get("literal") or []) or "none"
        W(f"### {img.replace('image_', '').capitalize()} (`{img}`; literal: {lit})")
        W("")
        W("- **The verses:** " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in c.items() if v) + ".")
        W(f"- **Readers:** {a.get('agree_on_card')} of {a.get('asked')} agree on the card; "
          f"{len(tb_by[img])} split, settled by the third reader"
          + (f" except {sum(1 for t in tb_by[img] if t['status'] != 'settled')} (item 1)." if any(
              t['status'] != 'settled' for t in tb_by[img]) else "."))
        k = num()
        W(f"- **{k}. Placement:** literal verses on the literal card, figures on the image card, `both` on both, "
          "readers-differ and other senses on neither; the splits as the third reader settled them.")
        rd = (p.get("proposed") or {}).get("readers_differ") or []
        if rd:
            W(f"- **{num()}. Readers differ, on neither card and named in the descriptions:** "
              + "; ".join(f"{r['ref']} ({' / '.join(r.get('readings') or [])})" for r in rd) + ".")
        rels = (p.get("proposed") or {}).get("relations") or []
        if rels:
            W("- **Relations proposed**, each with its verse:")
            for r in rels:
                key = (r["src"], r["type"], r["dst"])
                ov = OVERRIDE.get(key)
                blocked = (r["src"], r["type"]) in BLOCKED
                by = f", by {r['claimed_by']}" if r.get("claimed_by") else ""
                base = f"`{r['src']} {r['type']} {r['dst']}` ({', '.join(r.get('refs') or [])}{by})"
                if blocked:
                    W(f"  - **{num()}.** {base}: **waits** for the vocabulary release (item 7).")
                elif ov and ov[0] == "drop":
                    W(f"  - **{num()}.** {base}: **recommended not to add**: {ov[1]}.")
                elif ov and ov[0] == "hold":
                    W(f"  - **{num()}.** {base}: **held** {ov[1]}.")
                elif ov:
                    W(f"  - **{num()}.** {base}: **recommended as `{r['src'].replace('image_lion', r['dst'])} "
                      f"{ov[0]} image_lion` instead**: {ov[1]}.")
                else:
                    W(f"  - **{num()}.** {base}: add.")
        need = (p.get("proposed") or {}).get("needs_record") or []
        if need:
            W("- **Records it would need** (item 8, not now): " + "; ".join(x["what"] for x in need) + ".")
        W(f"- **Its pack:** `out/meaning/image-audit/packs/{img}.md`.")
        W("")

    W("## How it gets built")
    W("")
    W("- **Placement:** named-verse rulings in `ontology/card-repairs.jsonl`, as for temple; words that never carry "
      "the figure dropped from the image card, words that never carry the thing dropped from the literal card.")
    W("- **Relations:** one file per image in `ontology/relations/`, every note quoting its verse.")
    W("- **Measured before and after:** each card's verses and relations, and the image audit rerun "
      "(`tools/meaning/image_audit.py`).")
    W("- **Then the descriptions**, through the eleven-reader panel, and the next round of images.")
    W("")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"{n} numbered items -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
