"""The privacy page says what the code keeps, and nothing else (2026-11-12).

/privacy is the address the AI directories' forms take, and both reject a missing or incomplete policy. A policy that
drifts from the code is worse than none: it is the site's claim about its readers. Each number and promise on the page
is checked against the code that makes it true:

  1. the MCP's searches with no results: the days the page says == app2/mcp_usage.NO_RESULTS_DAYS
  2. the MCP's rate window: "a minute" == MCP_WINDOW; notes: "up to a day" == the longest FEEDBACK_PER_ADDR span
  3. no outside scripts, fonts or images: the page and the app's index.html load nothing from another host
  4. the access log is "a few files of fixed size": deploy/Caddyfile rolls it by size and keeps a fixed number
  5. the session key "held only in memory": app2/mcp_usage.py writes no key, and its test proves the file holds none
  6. it is served at /privacy, in the sitemap, and linked from About and /mcp
  7. it names what the directories ask for: categories, purposes, recipients, retention, contact, children

Planted faults prove 1 and 3. In process, no graph needed. Run: python tests/test_privacy_page.py"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402
import mcp_usage  # noqa: E402

fails, plants = [], 0


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print("FAIL", msg)


P = S.PRIVACY_PAGE
text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", P))


# ---- 1. the 90 days
def days_faults(t, days):
    m = re.search(r"for (\d+) days, and then removed", t)
    return [] if m and int(m.group(1)) == days else [f"the page says {m.group(1) if m else 'no'} days, the code {days}"]


check(not days_faults(text, mcp_usage.NO_RESULTS_DAYS), f"searches kept: {days_faults(text, mcp_usage.NO_RESULTS_DAYS)}")
plants += 1
check(days_faults(text, 30), "planted: the counter keeping 30 days not caught")

# ---- 2. the windows
check(S.MCP_WINDOW == 60 and "counted in memory for a minute" in text, "the MCP's rate window is not the page's minute")
check(max(span for span, _ in S.FEEDBACK_PER_ADDR) <= 86400 and "for up to a day" in text,
      "the notes' rate window is longer than the page's day")


# ---- 3. nothing from another host
def outside(html):
    return re.findall(r"""<(?:script|link|img|iframe)\b[^>]*\b(?:src|href)=["']?(https?:)?//(?!bibleontology\.org)""",
                      html, flags=re.I)


index = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
check(not outside(P) and not outside(index), f"something loads from another host: {outside(P) + outside(index)}")
plants += 1
check(outside(index + '<script src="https://cdn.example.com/x.js"></script>'), "planted: an outside script not caught")

# ---- 4. the log
caddy = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")
check(re.search(r"roll_size\s+\d+MiB", caddy) and re.search(r"roll_keep\s+\d+", caddy),
      "the access log is not rolled by size to a fixed number of files, as the page says")

# ---- 5. the key
src = (ROOT / "app2" / "mcp_usage.py").read_text(encoding="utf-8")
check("self.key" in src and not re.search(r"write_bytes\(self\.key|self\.key\.hex\(\)", src),
      "app2/mcp_usage.py may write its session key, which the page says is held only in memory")

# ---- 6. where it is
check('if u.path == "/privacy"' in (ROOT / "app2" / "server.py").read_text(encoding="utf-8"), "/privacy is not served")
check("/privacy" in (ROOT / "tools" / "sitemap.py").read_text(encoding="utf-8"), "/privacy is not in the sitemap's pages")
check('href="/privacy"' in index, "About does not link /privacy")
check('href="/privacy"' in S.MCP_PAGE, "/mcp does not link /privacy")
check('<link rel=canonical href="https://bibleontology.org/privacy">' in P, "the page's canonical is not /privacy")

# ---- 7. what the directories ask a policy to say
for need, words in (("what is kept", "Daily totals"), ("why", "kept to"), ("recipients", "Cloudflare"),
                    ("retention", "90 days"), ("contact", "bible.ontology@gmail.com"), ("children", "under 13"),
                    ("no selling", "sells or shares nothing")):
    check(words in text, f"the policy does not say {need} ('{words}')")
check(not re.search(r"\b(?:favour|honour|colour|behaviour|centre|organis|recognis)", text, re.I),
      "British spelling on the privacy page")

# ---- 8. THE TERMS OF USE (approved by Doug as written, 2026-11-12): served, listed, linked, and in step with the
# license file and the code: the rate it states is MCP_RATE, the license it names is the repository's
T = S.TERMS_PAGE
ttext = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", T))
server_src = (ROOT / "app2" / "server.py").read_text(encoding="utf-8")
check('if u.path == "/terms"' in server_src, "/terms is not served")
check("/terms" in (ROOT / "tools" / "sitemap.py").read_text(encoding="utf-8"), "/terms is not in the sitemap's pages")
check('href="/terms"' in P and 'href="/terms"' in S.MCP_PAGE, "/privacy or /mcp does not link /terms")
check(f"{S.MCP_RATE} calls a minute" in ttext, f"the terms' rate is not MCP_RATE ({S.MCP_RATE})")
lic = (ROOT / "LICENSE-DATA").read_text(encoding="utf-8")
check("CC BY 4.0" in ttext and "CC BY 4.0" in lic, "the terms and LICENSE-DATA name different licenses")
check("Apache License 2.0" in ttext and "Apache" in (ROOT / "LICENSE").read_text(encoding="utf-8"),
      "the terms name a code license the repository does not have")
check(not outside(T), "the terms page loads something from another host")
check(not re.search(r"\b(?:favour|honour|colour|behaviour|centre|organis|recognis|licence)", ttext, re.I),
      "British spelling on the terms page")

# ---- 9. THE ICON (Doug's, 2026-11-12: the r/BibleOntology icon at 512; the two words at 48; a book at 32 and 16):
# every file the head and the routes name exists, is the kind it says, and is the size it claims; the static rule
# serves only icons/ PNGs and the ICO, nothing else new
icons = ROOT / "app2" / "static" / "icons"
for name, size in (("icon-16.png", 16), ("icon-32.png", 32), ("icon-48.png", 48), ("icon-512.png", 512)):
    b = (icons / name).read_bytes() if (icons / name).exists() else b""
    w = int.from_bytes(b[16:20], "big") if b[:8] == b"\x89PNG\r\n\x1a\n" else 0
    check(w == size, f"{name}: {'missing or not a PNG' if not w else f'{w} px wide, not {size}'}")
ico = (icons / "favicon.ico").read_bytes() if (icons / "favicon.ico").exists() else b""
check(ico[:4] == b"\x00\x00\x01\x00" and int.from_bytes(ico[4:6], "little") == 3, "favicon.ico is not an ICO of three")
check(not (icons / "icon-192.png").exists(), "icon-192.png (icon C, replaced) is still there")
for href in ("/favicon.ico", "/icons/icon-512.png", "/apple-touch-icon.png"):
    check(f'href="{href}"' in index, f"the app's head does not link {href}")
check('"/favicon.ico", "/apple-touch-icon.png"' in server_src, "the root icon addresses are not routed")
check(r'icons/[\w.-]+\.(?:png|ico)' in server_src, "the static rule for icons is not the narrow one")

print(f"privacy, terms and icon against the code: 9 classes checked; {plants} planted faults; {len(fails)} failures")
sys.exit(1 if fails else 0)
