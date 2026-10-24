"""The full verse lists behind four DeepSeek event stamps (14 Sep 2026 run)."""
import glob, html, json, re
ROOT = "<local> Ontology/"
OSIS = ("Gen Exod Lev Num Deut Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr 2Chr Ezra Neh Esth Job Ps Prov Eccl Song "
        "Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal Matt Mark Luke John Acts Rom "
        "1Cor 2Cor Gal Eph Phil Col 1Thess 2Thess 1Tim 2Tim Titus Phlm Heb Jas 1Pet 2Pet 1John 2John 3John Jude Rev").split()
USFM = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA JER LAM EZK "
        "DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH "
        "2TH 1TI 2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV").split()
CODE = dict(zip(OSIS, USFM))
ORDER = {b: i for i, b in enumerate(OSIS)}
_cache = {}


def verses(osis):
    if osis in _cache:
        return _cache[osis]
    f = glob.glob(ROOT + f"data/raw/usfm/engbsb/*{CODE[osis]}engbsb.usfm")[0]
    out, ch, cur = {}, 0, None
    for line in open(f, encoding="utf-8"):
        m = re.match(r"\\c (\d+)", line)
        if m:
            ch = int(m.group(1)); continue
        if re.match(r"\\(s\d?|r|d|mt\d?|h|toc\d?|id|ms\d?|mr)\b", line):
            continue
        text = re.sub(r"\\f .*?\\f\*", "", line)
        text = re.sub(r"\\w ([^|]*)\|[^\\]*\\w\*", r"\1", text)
        for piece in re.split(r"(\\v \d+)", text):
            m = re.match(r"\\v (\d+)", piece)
            if m:
                cur = (ch, int(m.group(1))); out[cur] = ""; continue
            if cur:
                out[cur] += " " + re.sub(r"\\\S+\*?", "", piece).strip()
    _cache[osis] = {k: re.sub(r"\s+", " ", v).strip() for k, v in out.items()}
    return _cache[osis]


IDS = [("crucifixion", "Crucifixion"), ("resurrection", "Resurrection"),
       ("incarnation", "Incarnation"), ("ascension", "Ascension")]
rows = {k: [] for k, _ in IDS}
for f in glob.glob(ROOT + "out/stamps-*-deepseek-ref.jsonl"):
    for l in open(f, encoding="utf-8"):
        r = json.loads(l)
        if r.get("id") in rows:
            rows[r["id"]].append(r)
body = []
nav = []
for k, name in IDS:
    rs = rows[k]

    def key(r):
        m = re.match(r"(\w+) (\d+):(\d+)", r.get("cites") or "")
        b, c, v = (m.group(1), int(m.group(2)), int(m.group(3))) if m else (r["ref"].split(".")[0], 0, 0)
        return (ORDER.get(b, 99), c, v)
    rs.sort(key=key)
    gos = sum(1 for r in rs if r["ref"].split(".")[0] in ("Matt", "Mark", "Luke", "John"))
    nav.append(f'<a href="#{k}">{name} ({len(rs)})</a>')
    body.append(f'<h2 id="{k}">{name} <span class=n>{len(rs)} stamps · {gos} in the gospels, '
                f'{len(rs) - gos} elsewhere</span></h2><div class=wrap><table><tr><th>#</th>'
                f'<th>cites</th><th>verse (BSB)</th><th>section stamped</th></tr>')
    for i, r in enumerate(rs, 1):
        m = re.match(r"(\w+) (\d+):(\d+)", r.get("cites") or "")
        text = ""
        if m and m.group(1) in CODE:
            text = verses(m.group(1)).get((int(m.group(2)), int(m.group(3))), "")
        sec = r["ref"].split(".")
        body.append(f'<tr><td class=i>{i}</td><td class=c>{html.escape(r.get("cites") or "")}</td>'
                    f'<td>{html.escape(text)}</td><td class=s>{html.escape(r.get("title") or "")}'
                    f' <span class=n>({sec[0]} {sec[1]}:{sec[2]})</span></td></tr>')
    body.append("</table></div>")
page = f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Event Stamp Lists</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1b18;--mut:#6b655c;--line:#e4dfd6;--hd:#f1ede5}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#181715;--fg:#ece8e1;--mut:#a39c90;--line:#34312c;--hd:#23211e}}}}
:root[data-theme=dark]{{--bg:#181715;--fg:#ece8e1;--mut:#a39c90;--line:#34312c;--hd:#23211e}}
body{{background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif;margin:0;padding:16px;max-width:1100px}}
h1{{font-size:20px;margin:0 0 4px}}h2{{font-size:17px;margin:26px 0 6px}}p{{color:var(--mut);margin:4px 0 10px}}
nav a{{margin-right:14px}}.n{{color:var(--mut);font-weight:400;font-size:13px}}
.wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;min-width:640px}}
th,td{{border-bottom:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}}th{{background:var(--hd)}}
td.i{{color:var(--mut);width:2em}}td.c{{white-space:nowrap;font-weight:600}}td.s{{color:var(--mut);width:28%}}
</style></head><body><h1>Four event stamps — every verse</h1>
<p>DeepSeek's reference stamps from the 14 September 2026 corpus run: each stamp sits on a BSB section and cites
one verse as its evidence. Shown in canon order of the cited verse, with that verse's text. Not yet read or
measured; this is the list as the model left it.</p><nav>{' '.join(nav)}</nav>{''.join(body)}</body></html>"""
open(ROOT + "docs/review/event-stamp-lists.html", "w", encoding="utf-8").write(page)
print({k: len(v) for k, v in rows.items()})
