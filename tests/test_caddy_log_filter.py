"""The access log's filter can match what it means to delete (2026-11-12).

Caddy logs each request header under Go's canonical name ("Cf-Connecting-Ip", "Cf-Ipcountry"), and a log filter
field matches that name exactly. The filter was written "CF-Connecting-IP" and "CF-IPCountry" and so never matched:
every reader's full address and country went into the log, while About and /privacy said addresses were cut short.
Found by reading the log itself, not by any test. This is that test:

  1. every `request>headers>NAME delete` in both Caddyfiles names NAME in canonical form
  2. the headers that carry a reader's address or identity are all deleted: Cf-Connecting-Ip, X-Forwarded-For,
     True-Client-Ip, Cf-Ipcountry, Cookie, Set-Cookie
  3. the two address fields Caddy keeps are masked (remote_ip and client_ip)

A planted old spelling proves 1. No server needed. Run: python tests/test_caddy_log_filter.py"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
fails, plants = [], 0
MUST = {"Cf-Connecting-Ip", "X-Forwarded-For", "True-Client-Ip", "Cf-Ipcountry", "Cookie", "Set-Cookie"}


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print("FAIL", msg)


def canonical(name):
    """Go's textproto.CanonicalMIMEHeaderKey: each hyphen-separated part, first letter upper, the rest lower."""
    return "-".join(p[:1].upper() + p[1:].lower() for p in name.split("-"))


def filter_faults(text, label):
    f = []
    names = re.findall(r"request>headers>([A-Za-z0-9-]+)\s+delete", text)
    for n in names:
        if n != canonical(n):
            f.append(f"{label}: '{n}' never matches; Caddy logs it as '{canonical(n)}'")
    missing = MUST - set(names)
    if missing:
        f.append(f"{label}: not deleted: {sorted(missing)}")
    for field in ("remote_ip", "client_ip"):
        if not re.search(r"request>" + field + r"\s+ip_mask", text):
            f.append(f"{label}: {field} is not masked")
    return f


for name in ("Caddyfile", "Caddyfile.origin-pulls"):
    p = ROOT / "deploy" / name
    if p.exists():
        for f in filter_faults(p.read_text(encoding="utf-8"), name):
            check(False, f)

plants += 1
old = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8").replace(
    "request>headers>Cf-Connecting-Ip delete", "request>headers>CF-Connecting-IP delete")
check(filter_faults(old, "plant"), "planted: the old 'CF-Connecting-IP' spelling not caught")

print(f"Caddy log filter: 3 classes checked; {plants} planted fault; {len(fails)} failures")
sys.exit(1 if fails else 0)
