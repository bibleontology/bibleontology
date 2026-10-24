"""The crawler line holds in both places that draw it (2026-10-05).

The concern with training crawlers is that they give no attribution. robots.txt
(tools/sitemap.py's TRAINING) asks training crawlers to stay out; the
Caddyfile's @training refuses them with a 403. This checks:
  - every TRAINING crawler (not the robots-only tokens) is in the Caddy rule,
    and the rule names nothing that is not in TRAINING;
  - deploy/www/robots.txt was rebuilt from that list;
  - the rule does NOT match the crawlers that attribute: Googlebot, Bingbot,
    Applebot, the AI search and answer fetchers, link previews;
  - it DOES match a real string from each refused crawler.
Proven by planting faults (journal 2026-10-05). Run: python tests/test_crawlers.py"""
import ast
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
fails = []

# the list, read from the source without importing it (sitemap.py loads the graph)
src = (ROOT / "tools" / "sitemap.py").read_text(encoding="utf-8")
lit = lambda name: ast.literal_eval(re.search(rf"^{name} = (\[.*?\]|\{{.*?\}})", src, re.S | re.M).group(1))
TRAINING, TOKENS = lit("TRAINING"), set(lit("TOKENS_ONLY"))
crawlers = [n for n in TRAINING if n not in TOKENS]

caddy = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")
m = re.search(r"@training \{\s*header_regexp User-Agent \(\?i\)\(([^)]*)\)", caddy)
if not m:
    fails.append("Caddyfile: no @training rule")
    rule = []
else:
    rule = m.group(1).split("|")
for n in crawlers:
    if n not in rule:
        fails.append(f"Caddyfile @training is missing {n} (in tools/sitemap.py TRAINING)")
for n in rule:
    if n not in crawlers:
        fails.append(f"Caddyfile @training refuses {n}, which TRAINING does not name")
if "not path /robots.txt" not in caddy.split("@training", 1)[-1].split("}", 1)[0]:
    fails.append("Caddyfile @training does not leave /robots.txt readable")

robots = (ROOT / "deploy" / "www" / "robots.txt").read_text(encoding="utf-8")
for n in TRAINING:
    if f"User-agent: {n}\n" not in robots:
        fails.append(f"robots.txt does not name {n}: run python tools/sitemap.py")

rx = re.compile("(?i)(" + "|".join(rule) + ")") if rule else None
WELCOME = {  # real user-agent strings of crawlers that attribute
    "Googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Googlebot smartphone": "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.8010.52 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Google-InspectionTool": "Mozilla/5.0 (compatible; Google-InspectionTool/1.0;)",
    "Bingbot": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Applebot": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)",
    "OAI-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot",
    "ChatGPT-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot",
    "Claude-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-SearchBot/1.0; +Claude-SearchBot@anthropic.com)",
    "Claude-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0; +Claude-User@anthropic.com)",
    "PerplexityBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
    "DuckAssistBot": "DuckAssistBot/1.2; (+http://duckduckgo.com/duckassistbot.html)",
    "facebookexternalhit (link previews)": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Meta-ExternalFetcher": "meta-externalfetcher/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)",
    "an iPhone": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
}
REFUSED = {
    "GPTBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.1; +https://openai.com/gptbot",
    "ClaudeBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "CCBot": "CCBot/2.0 (https://commoncrawl.org/faq/)",
    "Bytespider": "Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; Bytespider; spider-feedback@bytedance.com)",
    "Meta-ExternalAgent": "meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)",
    "Amazonbot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot) Chrome/119.0.6045.214 Safari/537.36",
}
if rx:
    for who, ua in WELCOME.items():
        if rx.search(ua):
            fails.append(f"the training rule would refuse {who}, which attributes")
    for who, ua in REFUSED.items():
        if not rx.search(ua):
            fails.append(f"the training rule would let {who} through")
# THE INDEXNOW KEY (2026-10-07): exactly one key file in deploy/www/, its name
# its own content, served by the Caddyfile by that exact name and no pattern;
# without it Bing answers every submission 403
_root = Path(__file__).resolve().parents[1]
_keys = [p for p in (_root / "deploy" / "www").glob("*.txt") if p.name != "robots.txt"]
_caddy = (_root / "deploy" / "Caddyfile").read_text(encoding="utf-8")
if len(_keys) != 1:
    fails.append(f"IndexNow: {len(_keys)} key files in deploy/www (one expected)")
else:
    k = _keys[0]
    if k.read_text(encoding="utf-8").strip() != k.stem:
        fails.append(f"IndexNow: {k.name} does not contain its own key")
    if f"/{k.name}" not in _caddy:
        fails.append(f"IndexNow: the Caddyfile does not serve /{k.name}")
print(f"{len(crawlers)} training crawlers refused, {len(WELCOME)} that attribute let through, {len(fails)} failures")
for f in fails:
    print("FAIL", f)
sys.exit(1 if fails else 0)
