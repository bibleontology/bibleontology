"""A day of DeepSeek work for Claude to review (Doug, 2026-11-08: "get as much quality DeepSeek work completed … so
that I can really start pulling in aggressively in priority order starting tomorrow evening").

Three bounded tasks, blind (no file access), thinking on with room to finish, each carrying only public data: the
live site's cards and the public relation definitions (/ns). Results go to docs/review/deepseek-day-2026-11-08/.

    python tools/deepseek_day.py [verbs|mockups|beacon]
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "docs" / "review" / "deepseek-day-2026-11-08"
SCRATCH = Path(sys.argv[2]) if len(sys.argv) > 2 else None


def run(task, label):
    from bibleont import delegate as D
    import os
    r = D.run(task, level=3, label=label, blind=True, think=True, effort=os.environ.get("DS_EFFORT", "high"),
              timeout=1800)
    return r.get("answer") or "", r.get("cost")


def site(path):
    return subprocess.run(["curl", "-s", "https://bibleontology.org" + path], capture_output=True,
                          timeout=120).stdout.decode("utf-8")


def verbs():
    rows = json.loads(Path(SCRATCH).read_text(encoding="utf-8"))
    defs = json.loads((ROOT / "ontology" / "schema" / "relation_definitions.json").read_text(encoding="utf-8"))["types"]
    vocab = {k: v["definition"] for k, v in defs.items()}
    task = ("A Bible knowledge graph records relations between a doer (a person or group) and a THING (an object or "
            "creature) with a fixed vocabulary of relation types. Below are the vocabulary (type: definition) and the "
            "250 commonest verbs a parser found with a thing as their object (Hebrew or Greek lemma, its English gloss, "
            "how often). For each verb, give the ONE vocabulary type that records 'doer VERB thing' faithfully, or null "
            "when none fits without changing the meaning (eating, tearing, seeing usually fit none). Never invent a "
            "type. Answer with ONE JSON object {lemma: {\"type\": type or null, \"why\": \"a few words\"}} and nothing "
            "else.\n\nVOCABULARY:\n" + json.dumps(vocab, ensure_ascii=False) + "\n\nVERBS:\n"
            + json.dumps(rows, ensure_ascii=False))
    ans, cost = run(task, "deepseek-day verbs")
    (OUT / "verb-to-type.json").write_text(ans, encoding="utf-8")
    print("verbs", cost)


def mockups():
    stones = site("/api/entity?id=the_twelve_stones_from_the_jordan")
    kind = site("/api/entity?id=stones")
    for n, idea in enumerate((
            "a card that OPENS on its place in the graph: a small node-link picture at the top (the thing, its kind, "
            "who acted on it, where it is, the passage), each node a link, the card's text below it",
            "a side rail beside the card: 'where you are in the graph' as a short breadcrumb path (Bible > Joshua 4 > "
            "the twelve stones > its kind: stones) and three or four next steps, each one tap",
            "a full-screen explorer a reader enters from any card: the card's node in the centre, its relations around "
            "it, tap a neighbour to move there, a trail of where you have been along the bottom"), 1):
        task = ("Design one static mockup, as a single self-contained HTML file (inline CSS, no scripts from the web, "
                "no external fonts), for a free Bible-study website whose pages are cards about people, places, "
                "things and ideas in the Bible, built on a knowledge graph. The idea to show: " + idea + ". Use ONLY "
                "the real data below (two cards, as the site's API returns them); invent no relation, verse or name. "
                "Quiet, readable, works at phone width (375px) and desktop; warm paper background, dark ink, one "
                "accent color. Put a short note at the top saying it is mockup " + str(n) + " of 3. Answer with the "
                "HTML only.\n\nCARD (the twelve stones from the Jordan):\n" + stones[:12000]
                + "\n\nCARD (stones, its kind):\n" + kind[:8000])
        ans, cost = run(task, f"deepseek-day mockup {n}")
        html = ans[ans.find("<"):] if "<" in ans else ans
        import os
        tag = "-max" if os.environ.get("DS_EFFORT") == "max" else ""     # Doug: "give it plenty of think"
        (OUT / f"navigator-mockup-{n}{tag}.html").write_text(html, encoding="utf-8")
        print("mockup", n, cost)


def mockups2():
    """Round 2, Doug's direction (navigator-direction.md): a colored "Show in Navigator" button on the card that goes
    to the Navigator tab with the card's node centered, and plainly a change of view."""
    stones = site("/api/entity?id=the_twelve_stones_from_the_jordan")
    kind = site("/api/entity?id=stones")
    first = (OUT / "navigator-mockup-3.html").read_text(encoding="utf-8")[:9000]
    for n, idea in enumerate((
            "TWO SCREENS side by side in one page, labeled 'Screen A: the card' and 'Screen B: after the tap'. "
            "Screen A: the card for the twelve stones from the Jordan as a reader sees it (title, the line 'Carried by "
            "the sons of Israel (Joshua 4:8)', the first verses), with ONE colored button, 'Show in Navigator', near "
            "the top, styled unlike the card's text links (filled, the accent color, an icon suggesting a map or graph) "
            "so it reads as switching to another view. Screen B: the Navigator tab: a tab bar where 'Navigator' is now "
            "the active tab, the twelve stones' node centered, its neighbors around it (its kind 'stones', the sons of "
            "Israel, Gilgal, the passage Joshua 4), each a node you could tap, and a clear 'Back to the card' control",
            "the same two screens at PHONE width (375px), stacked: Screen A above Screen B, the button full-width "
            "under the card's title, and on Screen B the centered node with its neighbors fitting a phone"), 1):
        task = ("Design one static mockup, as a single self-contained HTML file (inline CSS and inline SVG only, no "
                "scripts or fonts from the web), for a free Bible-study website whose pages are cards about people, "
                "places, things and ideas in the Bible, built on a knowledge graph. Show: " + idea + ". Use ONLY the "
                "real data below; invent no relation, verse or name. Quiet and readable; warm paper background, dark "
                "ink, one accent color used for the button and the centered node. A short note at the top: 'Mockup "
                "round 2, " + str(n) + " of 2: the Show in Navigator button'. The earlier explorer mockup is given as "
                "a style reference only. Answer with the HTML only.\n\nCARD (the twelve stones from the Jordan):\n"
                + stones[:10000] + "\n\nCARD (stones, its kind):\n" + kind[:5000]
                + "\n\nEARLIER EXPLORER MOCKUP (style reference):\n" + first)
        ans, cost = run(task, f"deepseek-day mockup2 {n}")
        html = ans[ans.find("<"):] if "<" in ans else ans
        (OUT / f"navigator-round2-{n}.html").write_text(html, encoding="utf-8")
        print("mockup2", n, cost)


def mockups3():
    """Round 3: the on-ramp from a word card (Doug: "navigation from words where there is a very quick on ramp to
    connected meaning layer cards"), drawn on אֶבֶן "stone" (H68), the word behind the Jordan stones."""
    word = site("/api/sense?key=h68")
    stones = site("/api/entity?id=stones")
    jordan = site("/api/entity?id=the_twelve_stones_from_the_jordan")
    style = (OUT / "navigator-round2-1.html").read_text(encoding="utf-8")[:8000]
    task = ("Design one static mockup, as a single self-contained HTML file (inline CSS and inline SVG only, no scripts "
            "or fonts from the web), for a free Bible-study website. Show the TOP of the word card for the Hebrew word "
            "אֶבֶן 'stone' (Strong's H68) as a reader sees it on arrival (headword, transliteration, gloss, how often it "
            "is used), and directly under the headword, before anything else, a short row: 'In the meaning layer' "
            "with the cards this word leads to as tappable chips (the general card 'stones', and particular things the "
            "text follows, such as 'the twelve stones from the Jordan' and 'the stones at the cave of Makkedah'), and "
            "the same colored 'Show in Navigator' button as the card mockup, which opens the Navigator centered on "
            "the word's meaning-layer card. Make plain the chips go to other cards and the button to another view. "
            "Desktop and, below it, the same at phone width (375px). Use ONLY the real data below; invent no card, "
            "verse or count. A short note at the top: 'Mockup round 3: from a word to the meaning layer'. Keep the "
            "style of the round 2 mockup given. Answer with the HTML only.\n\nWORD CARD (H68):\n" + word[:9000]
            + "\n\nCARD (stones):\n" + stones[:5000] + "\n\nCARD (the twelve stones from the Jordan):\n"
            + jordan[:4000] + "\n\nROUND 2 MOCKUP (style):\n" + style)
    ans, cost = run(task, "deepseek-day mockup3")
    html = ans[ans.find("<"):] if "<" in ans else ans
    (OUT / "navigator-round3-word.html").write_text(html, encoding="utf-8")
    print("mockup3", cost)


def triage():
    """Round 4's "wrong" findings, each rechecked by DeepSeek against the card as it stands now (Doug, 2026-11-09:
    "always look to leverage DeepSeek"): real, mistaken, by design, or already fixed. Claude reads only the real ones."""
    src = sys.argv[2] if len(sys.argv) > 2 else "round3-deepseek-2026-11-08.jsonl"
    rows = [json.loads(l) for l in open(ROOT / "docs" / "review" / "word-audit" / src, encoding="utf-8")]
    rows = rows[-int(sys.argv[3]):] if len(sys.argv) > 3 else rows
    found = [(r["key"], f) for r in rows for f in ((r.get("answer") or {}).get("findings") or [])
             if f.get("level") == "WRONG"]
    out = []
    for key, f in found:
        card = subprocess.run(["curl", "-s", f"http://localhost:8022/api/sense?key={key.lower()}"], capture_output=True,
                              timeout=120).stdout.decode("utf-8")[:14000]
        task = ("A reviewer reported this fault on a Bible word card. Recheck it against the card's CURRENT data below "
                "and your own knowledge of Greek and Hebrew. Classify it as one of: REAL (the fault is there now and is "
                "a factual error), MISTAKEN (the reviewer is wrong: say why), BY_DESIGN (the card deliberately does "
                "this: Greek cards have no Septuagint rows; UBS senses are the UBS dictionary's own analysis; a dagesh "
                "lene in an initial begadkefat is correct), or FIXED (the current data no longer shows it). Answer with "
                "ONE JSON object: {\"verdict\": \"...\", \"why\": \"one or two sentences\", \"fix\": \"what to change, "
                "if REAL\"}.\n\nWORD: " + key + "\nREPORTED FAULT: " + json.dumps(f, ensure_ascii=False)
                + "\n\nCURRENT CARD DATA:\n" + card)
        ans, cost = run(task, f"triage {key}")
        m = re.search(r"\{.*\}", ans, re.S)
        try:
            v = json.loads(m.group(0)) if m else {"verdict": "?", "why": ans[:300]}
        except ValueError:
            v = {"verdict": "?", "why": ans[:300]}
        out.append({"key": key, "finding": f, **v, "cost": cost})
        print(key, v.get("verdict"), cost, flush=True)
    (OUT.parent / "word-audit" / (sys.argv[4] if len(sys.argv) > 4 else "round4-triage-2026-11-09.json")).write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def beacon():
    task = ("A website counts readers with three signals sent from the page's script: /api/open when the page's "
            "script runs, and /api/engaged on the first trusted pointerdown, keydown, wheel or touchstart. A farm of "
            "automated browsers runs the script and leaves at once, so /api/open over-counts; /api/engaged misses a "
            "person who reads the first screen and leaves without touching anything. Write a third signal, /api/stayed: "
            "sent once when the page has been VISIBLE (document.visibilityState) for 15 seconds in total, pausing the "
            "clock while hidden, never sent by a page that is prerendered or hidden the whole time, carrying no data, "
            "fetch with keepalive and cache no-store, every failure ignored, in plain browser JavaScript of the same "
            "style as this:\n\n  try{\n    const evs = ['pointerdown', 'keydown', 'wheel', 'touchstart'];\n    const "
            "once = ev => {\n      if(!ev.isTrusted) return;\n      evs.forEach(t => removeEventListener(t, once, "
            "true));\n      fetch('/api/engaged', {cache: 'no-store', keepalive: true}).catch(() => {});\n    };\n"
            "    evs.forEach(t => addEventListener(t, once, {capture: true, passive: true}));\n  }catch(e){}\n\n"
            "Then list, in a short numbered list, the ways a bot could still trigger it and what each would cost the "
            "bot. Answer with the code block first, then the list.")
    ans, cost = run(task, "deepseek-day beacon")
    (OUT / "stayed-beacon.md").write_text(ans, encoding="utf-8")
    print("beacon", cost)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    {"verbs": verbs, "mockups": mockups, "mockups2": mockups2, "mockups3": mockups3, "triage": triage, "beacon": beacon}[sys.argv[1]]()
