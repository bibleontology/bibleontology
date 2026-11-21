"""/llms.txt's MCP section and the /mcp page say only what the live server does (2026-11-12).

Doug, 2026-11-12: "communicate clearly to the AI providers ... I want Claude to see the value". /llms.txt never
mentioned the MCP, /mcp was not in the sitemap, and the /mcp page said "only counts of calls" when nothing was
counted. A model that reads a claim here and finds the server does otherwise has no reason to trust the rest, so
each claim is checked against the server's own answer:

  1. the section names every tool the server lists, and no other
  2. its worked example (Isa 53:7) is what get_verse answers: each hop's verse, term and certainty
  3. the certainties it names are the ones the server sends
  4. /mcp is in the sitemap; the /mcp page names "match" and promises no counting

Planted faults prove 1 and 2. In process, after the graph loads. Run: python tests/test_llms_mcp.py"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402
import mcp  # noqa: E402

fails, plants = [], 0


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print("FAIL", msg)


S.load()
text = S.llms_txt()
sec = text.split("## Ask the graph over MCP", 1)[1] if "## Ask the graph over MCP" in text else ""
check(sec, "/llms.txt has no MCP section")
check(f"{S.SITE}/mcp" in sec, "the section does not give the server's address")


# ---- 1. the tools
def tool_faults(s):
    m = re.search(r"Tools: (.*?)\. Every answer", s, flags=re.S)
    named = set(re.findall(r"\b([a-z_]+) \(", m.group(1))) | set(re.findall(r", ([a-z_]+)[,.]", m.group(1))) \
        if m else set()
    named = {n for n in named if "_" in n or n in mcp.TOOLS}
    return sorted(set(mcp.TOOLS) ^ named)


check(not tool_faults(sec), f"the tools named and the tools listed differ: {tool_faults(sec)}")
plants += 1
check(tool_faults(sec.replace("get_word (by Strong's number)", "get_word (by Strong's number), get_claims (by "
                                                                 "passage)")),
      "planted: a tool the server lacks not caught")

# ---- 2. the worked example, against the server's own answer
backend = S.mcp_backend()
out = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "get_verse", "arguments": {"ref": "Isa 53:7"}}}, backend)
links = out["result"]["structuredContent"]["links"]


def example_faults(s):
    m = re.search(r'get_verse\("Isa 53:7"\) answers .*?links: (.*?)\n', s)
    if not m:
        return ["no worked example"]
    f = []
    # each clause: "<words> in|to in <Book ch:v>, ... (<certainty>)" -> that verse, that certainty, a hop of that term
    # a quotation of a range is titled as the range ("Acts 8:32–33", 2026-11-15)
    for words, ref, cert in re.findall(r"(quoted|echoed|alluded to)[^;]*? in ((?:\d )?[A-Z][a-z]+ \d+:\d+(?:–\d+)?)"
                                       r"[^;]*?\((a reading|stated|a word match[^)]*)\)", m.group(1)):
        term = {"quoted": "quotes", "echoed": "echoes", "alluded to": "alludes_to"}[words]
        short = ref.replace("Revelation", "Rev")
        hop = [li for li in links if li.get("title") == short and (li.get("iri") or "").endswith("/" + term)]
        if not hop:
            f.append(f"no {term} hop to {ref}")
            continue
        want = {"stated": "stated", "a reading": "reading"}.get(cert, "match")
        if hop[0].get("certainty") != want:
            f.append(f"{ref}: says {cert}, the server says {hop[0].get('certainty')}")
        if want == "match" and cert.split(", ", 1)[-1] not in hop[0].get("rel", ""):
            f.append(f"{ref}: the grade '{cert}' is not the server's '{hop[0].get('rel')}'")
    if len(f) == 0 and len(re.findall(r"\((?:a reading|stated|a word match[^)]*)\)", m.group(1))) != 3:
        f.append("the example's three hops not all read")
    return f


check(not example_faults(sec), f"the worked example: {example_faults(sec)}")
plants += 1
check(example_faults(sec.replace("alluded to in Revelation 5:6, as a reader judged (a reading)",
                                 "alluded to in Revelation 5:6, as a reader judged (stated)")),
      "planted: a reading called stated not caught")
plants += 1
check(example_faults(sec.replace("quoted in Acts 8:32–33", "quoted in Acts 8:34")),
      "planted: a wrong verse not caught")

# ---- 3. the certainties
sent = set()
for ref in ("Isa 53:7", "Matt 4:4", "Deut 8:3"):
    o = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "get_verse", "arguments": {"ref": ref}}}, backend)
    sent |= {li.get("certainty") for li in o["result"]["structuredContent"]["links"] if li.get("certainty")}
for word in ("stated", "implied", "a reading", "a match"):
    check(word in sec, f"the section does not name the certainty '{word}'")
check(sent <= {"stated", "implied", "reading", "match"}, f"the server sends a certainty the section does not name: "
                                                         f"{sent - {'stated', 'implied', 'reading', 'match'}}")

# ---- 3b. INFORMATION, NEVER INSTRUCTIONS (2026-11-12): what a model reads from the server says what things are and
# when a tool fits, and never tells the model how to behave (Claude's review: "don't tell Claude how to behave";
# OpenAI's: nothing that steers). Saying when to call a tool ("Use this when ...") is what both ask for.
import mcp_backend as MB  # noqa: E402
STEER = re.compile(r"\b(?:you must|you should|be sure to|make sure|remember to|before you rely|do not|don't|"
                   r"ignore|only cite|please)\b|(?:^|[.!?]\s+)(?:cite|check|follow|always|never|rely|trust|prefer|"
                   r"begin|start with)\b", re.I)


def steer_faults(texts):
    return [f"{name}: '{m.group(0).strip()}'" for name, t in texts for m in [STEER.search(t or "")] if m]


readable = [("instructions", mcp.INSTRUCTIONS), ("start", MB.START_TEXT)] \
    + [(f"tool {t['name']}", t["description"]) for t in mcp._tool_defs()] \
    + [(f"resource {k}", v) for k, v in MB.RESOURCES.items()]
check(not steer_faults(readable), f"model-readable text that steers: {steer_faults(readable)}")
plants += 1
check(steer_faults([("plant", mcp.INSTRUCTIONS + " Check certainty before you rely on a reading.")]),
      "planted: the old 'Check certainty' instruction not caught")

# ---- 4. the sitemap and the /mcp page
pages = (ROOT / "deploy" / "www" / "sitemap-pages.xml").read_text(encoding="utf-8")
check(f"<loc>{S.SITE}/mcp</loc>" in pages, "/mcp is not in sitemap-pages.xml (python tools/sitemap.py --lastmod ...)")
check("match of words" in S.MCP_PAGE, "the /mcp page's certainties leave out the match")
# from 2026-11-12 (plan 8.7d) the server counts, so the page must say what it keeps, and what app2/mcp_usage.py keeps
check("daily totals" in S.MCP_PAGE and "90 days" in S.MCP_PAGE, "the /mcp page does not say what the server counts")
import mcp_usage  # noqa: E402
check(mcp_usage.NO_RESULTS_DAYS == 90, "the /mcp page says 90 days and the counter keeps searches otherwise")

print(f"llms.txt and /mcp against the server: 4 classes checked; {plants} planted faults; {len(fails)} failures")
sys.exit(1 if fails else 0)
