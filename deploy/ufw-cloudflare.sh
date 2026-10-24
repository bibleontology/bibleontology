#!/usr/bin/env bash
# Admit web traffic (80, 443) only from Cloudflare. RUNS ON THE SERVER.
#
#   sudo bash /srv/bibleontology/deploy/ufw-cloudflare.sh           # show the plan, change nothing
#   sudo bash /srv/bibleontology/deploy/ufw-cloudflare.sh --apply   # do it
#
# Why (docs/OPERATIONS.md, "The proxy hides the origin from discovery, not
# from someone who knows it"): treat the server's address as discoverable, as
# any origin's is once it has ever been served directly. Anyone who knows it
# can talk to Caddy directly and skip Cloudflare's rate
# limit, bot rules and caching. With 80 and 443 open only to Cloudflare's
# published ranges, the only way in is through Cloudflare. SSH (22) is not
# touched: it stays open, by key only, with fail2ban.
#
# It was held back until the origin certificate was in use (2026-10-01): the
# Let's Encrypt certificate it replaced renewed by Let's Encrypt reaching this
# machine directly, which this rule would have blocked.
#
# Re-run it to refresh: Cloudflare's ranges change rarely, but they do. New
# ranges are added before stale ones are removed, so the site is never shut
# out between the two. Every rule it manages carries the comment
# "cloudflare"; nothing else is touched except the two broad rules
# "allow 80/tcp" and "allow 443/tcp", which it removes.
#
# ROLLBACK, if the site stops answering through Cloudflare:
#   sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
set -euo pipefail

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

[ "$(id -u)" = "0" ] || { echo "run with sudo"; exit 1; }

# Read ufw's state once and test the saved text: `ufw status | grep -q` under
# pipefail can read as "no match" when grep exits early (the preflight bug of
# 2026-10-01, deploy/preflight.sh).
status="$(ufw status)"

# SSH must already be allowed, or this is not the server we think it is
if ! grep -qE '^(OpenSSH|22/tcp)\s+ALLOW' <<<"$status"; then
	echo "REFUSING: no SSH allow rule in ufw -- changing the firewall now could lock you out"
	exit 1
fi

v4="$(curl -fsS --max-time 20 https://www.cloudflare.com/ips-v4)" || { echo "could not fetch ips-v4"; exit 1; }
v6="$(curl -fsS --max-time 20 https://www.cloudflare.com/ips-v6)" || { echo "could not fetch ips-v6"; exit 1; }

# a list that is not a list of address ranges is not applied
cidr4='^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$'
cidr6='^[0-9a-fA-F:]+/[0-9]{1,3}$'
ranges=()
while read -r r; do [ -z "$r" ] && continue
	[[ "$r" =~ $cidr4 ]] || { echo "REFUSING: unexpected line in ips-v4: $r"; exit 1; }
	ranges+=("$r"); done <<<"$v4"
n4=${#ranges[@]}
while read -r r; do [ -z "$r" ] && continue
	[[ "$r" =~ $cidr6 ]] || { echo "REFUSING: unexpected line in ips-v6: $r"; exit 1; }
	ranges+=("$r"); done <<<"$v6"
n6=$(( ${#ranges[@]} - n4 ))
if [ "$n4" -lt 10 ] || [ "$n6" -lt 5 ]; then
	echo "REFUSING: only $n4 IPv4 and $n6 IPv6 ranges -- Cloudflare publishes about 15 and 7"
	exit 1
fi
echo "Cloudflare publishes $n4 IPv4 and $n6 IPv6 ranges."

# the ranges ufw already has from an earlier run (comment "cloudflare"); the
# range is whichever field holds a "/" other than the port spec -- an IPv6
# line has an extra "(v6)" column, so a fixed column would read it wrong
have="$(awk '/# cloudflare/ {for (i = 1; i <= NF; i++) if ($i ~ /\// && $i !~ /tcp/) print $i}' <<<"$status" | sort -u)"
want="$(printf '%s\n' "${ranges[@]}" | sort -u)"
add="$(comm -13 <(printf '%s\n' "$have") <(printf '%s\n' "$want") | sed '/^$/d')"
drop="$(comm -23 <(printf '%s\n' "$have") <(printf '%s\n' "$want") | sed '/^$/d')"
broad=0
grep -qE '^(80|443)/tcp(\s+\(v6\))?\s+ALLOW\s+Anywhere' <<<"$status" && broad=1

count() { [ -z "$1" ] && echo 0 || wc -l <<<"$1"; }
echo "To add:    $(count "$add") range(s)"
echo "To remove: $(count "$drop") stale range(s)"
[ "$broad" = 1 ] && echo "And remove: allow 80/tcp and allow 443/tcp from anywhere"

if [ "$APPLY" = 0 ]; then
	echo
	echo "Nothing changed. Run again with --apply to do it."
	exit 0
fi

# add first, so there is never a moment with no way in
while read -r r; do [ -z "$r" ] && continue
	ufw allow proto tcp from "$r" to any port 80,443 comment cloudflare >/dev/null
done <<<"$add"
while read -r r; do [ -z "$r" ] && continue
	ufw delete allow proto tcp from "$r" to any port 80,443 >/dev/null || true
done <<<"$drop"
if [ "$broad" = 1 ]; then
	ufw delete allow 80/tcp >/dev/null || true
	ufw delete allow 443/tcp >/dev/null || true
fi

after="$(ufw status)"
echo "Done. Web ports now admit only Cloudflare; SSH unchanged:"
grep -E 'OpenSSH|22/tcp' <<<"$after" || true
echo "$(grep -c cloudflare <<<"$after" || true) cloudflare rules (IPv4 and IPv6)"
grep -qE '^(80|443)/tcp(\s+\(v6\))?\s+ALLOW\s+Anywhere' <<<"$after" \
	&& echo "WARNING: a broad 80/443 rule is still present" || echo "No broad 80/443 rule remains."
