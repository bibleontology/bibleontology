"""THE IMPORT, SHOWN BEFORE IT IS WIRED IN (feedback comes from
looking: a verse's structure as the builder has it, and with the sweep's
layer applied, side by side).

    python tools/sweep/import_preview.py [ref ...]   -> docs/review/sweep-import-preview.html

The layer is applied the way the site would apply it: the sweep's nodes and
edges added, the builder edges and groups it disputes taken away.
"""
import collections
import gzip
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import structure as S    # noqa: E402
import versetree as VT   # noqa: E402

LAYER = ROOT / "out" / "sweep-layer.jsonl.gz"
DEFAULT = ["Exo.8.13", "Gen.22.2", "Mrk.2.3", "Job.38.2", "Luk.22.8", "Rom.8.31", "Jhn.14.9"]
e = html.escape


def VT_clean(t):
    t = " ".join(str(t or "").replace(".", " ").split())
    return t if len(t) <= 70 else t[:67] + "…"


def load_layer(chapters):
    """The layer's records for these chapters, plus every generic (they are
    named from anywhere)."""
    out = collections.defaultdict(list)
    with gzip.open(LAYER, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            ch = d["ref"].rsplit(".", 1)[0]
            if ch in chapters or d.get("kind") == "generic":
                out[ch].append(d)
    return out


def applied(nodes, edges, layer):
    nodes = dict(nodes)
    gone_groups = {d["id"] for d in layer if d.get("action") == "remove" and "id" in d and "type" not in d}
    gone_edges = {(d["src"], d["type"], d["dst"]) for d in layer if d.get("action") == "remove" and "type" in d}
    for g in gone_groups:
        nodes.pop(g, None)
    keep = [x for x in edges if (x.get("src"), x.get("type"), x.get("dst")) not in gone_edges
            and x.get("src") not in gone_groups and x.get("dst") not in gone_groups]
    for d in layer:
        if d.get("action") == "remove":
            continue
        if d.get("node"):
            n = {k: v for k, v in d.items() if k != "node"}
            if d.get("kind") in ("generic", "together"):
                n["word"] = True
            nodes[d["id"]] = n
        elif "type" in d:
            keep.append(d)
    return nodes, keep


def main():
    refs = sys.argv[1:] or DEFAULT
    chapters = {r.rsplit(".", 1)[0] for r in refs}
    layer = load_layer(chapters)
    generics = [d for ds in layer.values() for d in ds if d.get("kind") == "generic"]
    parts = []
    for ref in refs:
        ch = ref.rsplit(".", 1)[0]
        nodes, edges, readings = S.chapter(ch)
        before = (nodes, edges + readings)
        mine = [d for d in layer.get(ch, []) if d.get("kind") != "generic"]
        an, ae = applied(nodes, edges + readings, mine + generics)
        here = [d for d in mine if d["ref"] == ref]
        # ONE CLAUSE AT A TIME, as the site draws them, and only the clauses
        # the layer changes: a whole verse in one drawing was unreadable
        # (Genesis 22:2, eleven clauses)
        clauses = sorted((n for n in nodes.values() if n.get("clause") and n.get("ref") == ref),
                         key=lambda n: n.get("order", 0))
        blocks = []
        for c in clauses:
            b_ = VT.mermaid_built(ref, graph=before, only=c["id"], show_ref=S.to_english)
            a_ = VT.mermaid_built(ref, graph=(an, ae), only=c["id"], show_ref=S.to_english)
            if a_ != b_:
                blocks.append((c, b_, a_))
        diag = {}
        for c, b_, a_ in blocks:
            diag[f"“{VT_clean(c.get('text'))}”: as the builder has it"] = b_
            diag[f"“{VT_clean(c.get('text'))}”: with the sweep's layer"] = a_
        eng = S.to_english(ref)
        summary = collections.Counter(
            ("dispute: " if d.get("action") == "remove" else "") + (d.get("type") or d.get("kind") or "group")
            for d in here)
        notes = "".join(
            f"<li>{e(d.get('type') or d.get('kind') or '')}: {e(d.get('src', d.get('id', '')).split('#')[-1])}"
            f" → {e(str(d.get('dst', '')).split('#')[-1] if d.get('dst') else '')}"
            f"{' <b>(disputes the builder)</b>' if d.get('action') == 'remove' else ''}"
            f" <span class=k>{e(d.get('by', ''))}</span></li>" for d in here[:40])
        parts.append(
            f"<section><h2>{e(eng)}{'' if eng == ref else f' <span class=k>(Hebrew {e(ref)})</span>'}</h2>"
            f"<p class=k>{e(', '.join(f'{v} {k}' for k, v in summary.most_common()))}</p>"
            + ("".join(f"<h3>{e(name)}</h3><pre class=mermaid>{e(m)}</pre>" for name, m in diag.items())
               or "<p class=k>The layer changes no clause's drawing here.</p>")
            + f"<details><summary>The layer's records for this verse</summary><ul>{notes}</ul></details></section>")
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Sweep import preview</title><style>
:root{{--paper:#F3F5F8;--surface:#fff;--ink:#141F2C;--muted:#5C6A7B;--rule:#BAC4D0}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#0F151D;--surface:#18202B;--ink:#E7ECF2;--muted:#93A2B3;--rule:#2C3A4A}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Georgia,serif}} main{{max-width:1100px;margin:0 auto;padding:16px}}
section{{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:8px 16px;margin:14px 0;overflow-x:auto}}
.k{{color:var(--muted);font-size:13px}} pre.mermaid{{background:#fff;border-radius:8px;padding:8px}}
</style></head><body><main><h1>The sweep, imported: a preview</h1>
<p class=k>Each verse twice: the structure as the builder has it, and with the sweep's layer applied (its readings added, the
builder links and groups it disputes taken away). A pronoun the sweep resolved is labelled "is · automated analysis".</p>
{''.join(parts)}</main>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad:true, securityLevel:'loose', theme:'neutral', flowchart:{{useMaxWidth:true}}}});
window.structWord=()=>{{}};</script></body></html>"""
    dest = ROOT / "docs" / "review" / "sweep-import-preview.html"
    dest.write_text(page, encoding="utf-8")
    print("->", dest.relative_to(ROOT))


if __name__ == "__main__":
    main()
