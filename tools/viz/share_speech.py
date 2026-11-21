"""THE SPEECH DIAGRAM'S SHARE IMAGE (2026-11-16; Doug posted it to r/dataisbeautiful as "a classification of text", not a
religious post). The draft was a screenshot of the live page: zoom buttons, "Hover a speaker" and "Who the voices are"
in a still picture, link underlines on every kind, and counts colliding with their names. This is the same drawing,
from the same function the page uses, with none of the page's controls.

Drawn only from out/viz/speech.json (tools/viz/build.py speech), so every number on it is the view's own.
Rendered to PNG by the installed Edge or Chrome, headless, at twice the pixels; nothing is installed.

    python tools/viz/share_speech.py        -> out/viz/share-speech.html and out/viz/share-speech.png
"""
import html
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "viz"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import _speech_svg  # noqa: E402
from share_ideas import BROWSERS  # noqa: E402

W, H = 1400, 1290


def main():
    d = json.loads((OUT / "speech.json").read_text(encoding="utf-8"))
    svg = _speech_svg(d, 1100, 230, 820, "share")
    # a still picture: no links, no underlines, no hover hooks
    svg = re.sub(r'<a href="[^"]*" target="_blank">|</a>', "", svg)
    svg = svg.replace("text-decoration:underline;text-decoration-color:var(--rule)", "")
    svg = svg.replace('class="hit band"', 'class="band"')
    # the kinds' counts are the drawn ones (a named voice); the layer's whole count is the definition's own number
    total = int(re.search(r"\(([\d,]+)\)", d["definition"]).group(1).replace(",", ""))
    drawn = sum(f["n"] for f in d["flows"])
    key = "".join(f'<span><i style="background:{g["color"]}"></i>{html.escape(g["name"])}</span>' for g in d["groups"])
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
:root{{--ink:#1d1b17;--mute:#6b645a;--rule:#d8d0c2}}
html,body{{margin:0;background:#fbf8f2;color:var(--ink)}}
.wrap{{width:{W - 120}px;padding:46px 60px 0}}
.k{{font:600 15px system-ui,sans-serif;letter-spacing:.14em;color:var(--mute)}}
h1{{font:700 44px/1.15 Georgia,serif;margin:12px 0 10px}}
.s{{font:19px/1.45 Georgia,serif;color:var(--mute);margin:0 0 16px;max-width:1150px}}
.key{{font:15px system-ui,sans-serif;color:var(--mute);display:flex;gap:22px;flex-wrap:wrap;margin-bottom:6px}}
.key i{{display:inline-block;width:20px;height:5px;border-radius:2px;margin-right:7px;vertical-align:middle}}
svg{{width:100%;height:auto;display:block}}
.f{{font:15px/1.5 system-ui,sans-serif;color:var(--mute);margin-top:6px}}
</style></head><body><div class="wrap">
<div class="k">BIBLE ONTOLOGY · A CLASSIFICATION OF SPEECH IN THE BIBLE</div>
<h1>{html.escape(d["question"])}</h1>
<p class="s">{total:,} instances sorted into {len(d["acts"])} kinds of speech in five groups. Each band runs from a
voice to a kind of speech; its width is how many times. Drawn here: the {drawn:,} whose voice the text names.</p>
<div class="key">{key}</div>
{svg}
<div class="f">Speakers from the original-language annotation (MACULA,
© Biblica, CC BY 4.0); kinds from the graph's speech-act layer. Explore every band and its verses:
bibleontology.org/visual/speech</div>
</div></body></html>"""
    (OUT / "share-speech.html").write_text(page, encoding="utf-8")
    exe = next((b for b in BROWSERS if Path(b).exists()), None)
    if not exe:
        sys.exit("no Edge or Chrome to render the PNG; the HTML is at " + str(OUT / "share-speech.html"))
    png = OUT / "share-speech.png"
    png.unlink(missing_ok=True)
    # A FRESH THROWAWAY PROFILE PER ATTEMPT (2026-11-16): with the shared out/viz/.share-browser-profile the browser
    # exited 0 and wrote nothing, three runs in four -- an instance still holding that profile took the request over
    for _ in range(3):
        with tempfile.TemporaryDirectory(prefix="share-speech-", ignore_cleanup_errors=True) as prof:
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                            f"--window-size={W},{H}", f"--user-data-dir={prof}", f"--screenshot={png}",
                            (OUT / "share-speech.html").as_uri()], check=False, timeout=120, capture_output=True)
            for _ in range(20):                       # the file may land a moment after the process returns
                if png.exists():
                    break
                time.sleep(0.5)
        if png.exists():
            break
    print("instances", total, "drawn", drawn, "->", png if png.exists() else "(no PNG written)")


if __name__ == "__main__":
    main()
