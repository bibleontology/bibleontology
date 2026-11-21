#!/bin/bash
# DeepSeek draws each card-layout proposal's first phone screen as an HTML mockup (Doug, 2026-11-21: "they are not
# rendering as pictures"), then the gallery is assembled: out/layouts/gallery2.html. Resumable; off-peak only.
cd "$(dirname "$0")/../.."
export PYTHONPATH=src PYTHONIOENCODING=utf-8
D=out/layouts
offpeak() { python -X utf8 -c "import sys,datetime as t; n=t.datetime.now(t.timezone.utc); sys.exit(0 if (n.weekday()>=5 or not (1<=n.hour<4 or 6<=n.hour<10)) else 1)"; }
for ty in person place concept group object image saying message; do
  out="$D/$ty.mockup2.html"; [ -s "$out" ] && continue
  offpeak || { echo "peak: stopping"; exit 2; }
  { cat <<'EOF'
Draw the FIRST PHONE SCREEN of the card layout below as one self-contained HTML fragment.
- One <div class="phone"> 375px wide, about 700px tall, inline styles only, no <script>, no external files, no images.
- The site's look: page #F3F5F8, card #FFFFFF, ink #141F2C, muted #5C6A7B, rules #D9E0E8, accent ochre #A96A1E
  (soft #F5EADB), links slate #356A8C (soft #E6EEF4). Headings in Georgia, serif; small labels and verse references in
  "IBM Plex Mono", monospace, uppercase for labels; body in system-ui, sans-serif, 15px.
- Use the REAL content of the layout's mockup (names, verses, references). Show "more" controls as ▾ and links as
  slate text. Mark a reading with a small ochre tag. Keep it to what the layout puts on the first screen.
- After the phone, one <p> of at most two lines saying what sits below the first screen.
Return ONLY the HTML fragment, starting with <div class="phone" and nothing before or after it.

THE LAYOUT:
EOF
  sed -e 's/^{.*//' "$D/$ty.layout2.txt"; } > "$D/$ty.mockup2.brief.txt"
  for i in 1 2 3; do
    timeout 1200 python -X utf8 -m bibleont.delegate run --level 2 --blind --label "mockup $ty" --task "@$D/$ty.mockup2.brief.txt" > "$out.raw" 2>&1
    grep -q '<div class="phone"' "$out.raw" && break; echo "retry $ty $i"
  done
  python -X utf8 - "$out.raw" "$out" <<'EOF'
import sys, re
t = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r'<div class="phone".*</div>\s*(<p>.*?</p>)?', t, re.S)
if m:
    h = re.sub(r"<script.*?</script>", "", m.group(0), flags=re.S | re.I)
    open(sys.argv[2], "w", encoding="utf-8").write(h)
EOF
  [ -s "$out" ] && echo "$ty drawn" || echo "$ty: no mockup"
done
python -X utf8 - <<'EOF'
from pathlib import Path
D = Path("out/layouts")
cells = []
for ty in ["person", "place", "concept", "group", "object", "image", "saying", "message"]:
    f = D / f"{ty}.mockup2.html"
    body = f.read_text(encoding="utf-8") if f.exists() else "<p>(not drawn)</p>"
    cells.append(f'<section><h2>{ty.title()} card</h2>{body}</section>')
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Card layout proposals</title><style>
body{{background:#e9edf2;margin:0;padding:16px;font:15px system-ui,sans-serif;color:#141F2C}}
h1{{font:600 22px Georgia,serif;margin:0 0 4px}} .note{{color:#5C6A7B;margin:0 0 16px}}
.grid{{display:flex;flex-wrap:wrap;gap:28px}} section{{width:375px}} h2{{font:600 16px Georgia,serif;margin:0 0 8px}}
.phone{{box-shadow:0 2px 14px rgba(0,0,0,.18);border-radius:22px;overflow:hidden;border:8px solid #141F2C;max-width:375px;box-sizing:border-box}}
section p{{color:#5C6A7B;font-size:13px}}
</style></head><body><h1>Card layout proposals: the first phone screen (round 2: nothing distinct dropped, Navigator and the original language kept)</h1>
<p class="note">Drawn by DeepSeek from its own reconciled layouts (four personas each), 2026-11-21, round 2. Proposals only; nothing is built. The full text of each layout is in all-layouts.md.</p>
<div class="grid">{''.join(cells)}</div></body></html>"""
(D / "gallery2.html").write_text(page, encoding="utf-8")
print("gallery -> out/layouts/gallery2.html")
EOF
