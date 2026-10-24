#!/usr/bin/env bash
# First-run setup. RUNS ON THE SERVER, as root, once.
#
#   ssh root@<server> 'bash -s' < deploy/setup.sh
#
# From PowerShell, `<` is not a redirection operator. Use:
#
#   (Get-Content deploy/setup.sh -Raw).Replace("`r`n","`n") | ssh root@HOST 'bash -s'
#
# Everything here is idempotent: running it twice changes nothing the second
# time. That is deliberate, because the alternative is being afraid to run it
# when you cannot remember whether you already did.
set -euo pipefail

ADMIN_USER="${ADMIN_USER:-doug}"
APP_USER="bibleont"
APP_DIR="/srv/bibleontology"
DATA_DIR="/srv/bibleontology-data"

say() { printf '\n=== %s\n' "$1"; }

say "packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-yaml git ufw fail2ban \
	unattended-upgrades debian-keyring debian-archive-keyring \
	apt-transport-https curl gnupg

say "caddy"
if ! command -v caddy >/dev/null; then
	curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
		| gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
	curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
		| tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
	apt-get update -qq
	apt-get install -y -qq caddy
fi

say "somewhere for caddy to write its log"
# The package ships the directory on some releases and not others, and Caddy
# refuses a config it cannot open a log file for -- which surfaces as a reload
# that fails while the old config keeps serving, so the site looks fine and
# the new settings are simply not on.
install -d -o caddy -g caddy -m 750 /var/log/caddy

say "an admin account that is not root"
if ! id -u "$ADMIN_USER" >/dev/null 2>&1; then
	adduser --disabled-password --gecos "" "$ADMIN_USER"
	usermod -aG sudo "$ADMIN_USER"
fi
# The key that got you in becomes the key for the account you will actually
# use. Copied rather than moved, so the root session you are reading this in
# does not lose its own access halfway through.
if [ -f /root/.ssh/authorized_keys ]; then
	install -d -m 700 -o "$ADMIN_USER" -g "$ADMIN_USER" "/home/$ADMIN_USER/.ssh"
	install -m 600 -o "$ADMIN_USER" -g "$ADMIN_USER" \
		/root/.ssh/authorized_keys "/home/$ADMIN_USER/.ssh/authorized_keys"
fi

say "a service account that owns nothing and can log in nowhere"
id -u "$APP_USER" >/dev/null 2>&1 || \
	adduser --system --group --no-create-home --shell /usr/sbin/nologin "$APP_USER"

say "directories"
install -d -o "$ADMIN_USER" -g "$ADMIN_USER" "$APP_DIR"
install -d -o "$APP_USER" -g "$APP_USER" -m 750 "$DATA_DIR"
install -d -o "$APP_USER" -g "$APP_USER" -m 750 "$DATA_DIR/inbox"

say "firewall"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

say "automatic security updates"
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

say "fail2ban"
systemctl enable --now fail2ban

say "a bare repository to push into"
# Deploys are `git push`. No archive to upload, no build step, and the server
# keeps the history -- so what is running can always be identified exactly,
# which matters because every note a reader leaves is pinned to a build hash.
if [ ! -d "$APP_DIR.git" ]; then
	install -d -o "$ADMIN_USER" -g "$ADMIN_USER" "$APP_DIR.git"
	sudo -u "$ADMIN_USER" git init --bare -q "$APP_DIR.git"
fi
cat >"$APP_DIR.git/hooks/post-receive" <<EOF
#!/usr/bin/env bash
set -eu
# Check the pushed commit out into the working directory and restart. The
# service is down for about a second: the store loads in 0.2s.
git --work-tree="$APP_DIR" --git-dir="$APP_DIR.git" checkout -f
sudo /usr/bin/systemctl restart bibleontology
echo "deployed \$(git --git-dir="$APP_DIR.git" rev-parse --short HEAD)"
EOF
chmod +x "$APP_DIR.git/hooks/post-receive"
chown "$ADMIN_USER:$ADMIN_USER" "$APP_DIR.git/hooks/post-receive"

# The one thing the deploy user may do as root, and nothing else.
cat >/etc/sudoers.d/bibleontology <<EOF
$ADMIN_USER ALL=(root) NOPASSWD: /usr/bin/systemctl restart bibleontology
EOF
chmod 440 /etc/sudoers.d/bibleontology

say "done"
cat <<EOF

Next, from your laptop:

  git remote add live $ADMIN_USER@$(hostname -I | awk '{print $1}'):$APP_DIR.git
  git push live master

Then back here, install the service and Caddy config (they are in the repo
once you have pushed):

  cp $APP_DIR/deploy/bibleontology.service /etc/systemd/system/
  cp $APP_DIR/deploy/Caddyfile /etc/caddy/Caddyfile
  systemctl daemon-reload
  systemctl enable --now bibleontology
  systemctl reload caddy

Point DNS at this machine BEFORE reloading Caddy, or the certificate request
will fail and you will wait out a rate limit for no reason.
EOF
