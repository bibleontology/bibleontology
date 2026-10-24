# Deploying

Server: `<server>` — DigitalOcean, Basic Regular 2 vCPU / 4 GB ($24/mo;
resized from 2 GB on 2026-10-01, CPU and RAM only, the 50 GB disk kept), NYC1,
Ubuntu 24.04. app2 needs about 2 GB (1.96 GB on the laptop once its data was
compacted); the unit allows 3G. See docs/LAUNCH.md and OPERATIONS.md.
Domain: `bibleontology.org` — Cloudflare registrar and DNS

**Every command below says which machine it runs on.** That distinction has
already caused one confusion in this project and it is the only thing here
that is genuinely easy to get wrong.

---

## 1. Prove you can get in — ON YOUR LAPTOP

```
ssh root@<server>
```

Type `yes` at the fingerprint prompt. If it asks for a password, the SSH key
did not attach at creation: fix that in the provider console before going on,
because everything after this assumes key access.

If it says `Permission denied (publickey)`, do not conclude the key is wrong
until you have run the same command with `-v` and read what it actually
tried. A passphrase-protected key that is never prompted for -- which is what
`BatchMode=yes` causes -- fails with exactly that message.

Then `exit`.

## 2. Set the machine up — ON YOUR LAPTOP, running on the server

```
ssh root@<server> 'bash -s' < deploy/setup.sh
```

That installs Python, git, Caddy, `ufw`, `fail2ban` and automatic security
updates; creates an admin account and a service account; opens only 22, 80 and
443; and makes a bare repository to push into. It is idempotent — safe to run
again whenever you are unsure whether you already did.

## 3. Close the door behind you — ON THE SERVER

```
ssh root@<server>
```

Edit `/etc/ssh/sshd_config` and set:

```
PermitRootLogin no
PasswordAuthentication no
```

Then `systemctl restart ssh`.

**Keep that session open.** In a second terminal, prove `ssh doug@<server>`
works before you close the first one. Locking yourself out of a fresh server is
recoverable through the provider's web console, but there is no reason to
spend the afternoon on it.

One thing that will not be obvious: an account created with
`--disabled-password` has no password for `sudo` to check, so `sudo` refuses
it even though the account is in the `sudo` group. Set one with `passwd doug`
as root. The account still cannot log in by password -- SSH is key-only --
the password exists solely so `sudo` has something to verify.

## 4. Send the code — ON YOUR LAPTOP

```
git remote add live doug@<server>:/srv/bibleontology.git
git push live master
```

The push checks the commit out on the server and restarts the service. From
now on, deploying is that one `git push`.

## 5. Install the service and the web server — ON THE SERVER

```
sudo cp /srv/bibleontology/deploy/bibleontology.service /etc/systemd/system/
sudo cp /srv/bibleontology/deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl daemon-reload
sudo systemctl enable --now bibleontology
systemctl status bibleontology --no-pager
```

It should be `active (running)`. app2 takes a few minutes to load before it
listens; then check it answers:

```
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/api/books
```

`200` with no invite list, `403` (the closed door) with one: either means it
is up. `000` means nothing is listening yet.

### The lexicon -- ON THE SERVER, once

The word cards' Lexicon entry is STEPBible's, fetched from their repository on
the server (it is not in git; a push never carries it). Without this the
cards silently fall back to 135 entries (2026-10-04):

```bash
cd /srv/bibleontology && PYTHONPATH=src python3 tools/fetch_lexicon.py && sudo systemctl restart bibleontology
```

## 6. Point the domain — IN CLOUDFLARE

DNS → Records → Add record, twice:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `@` | `<server>` | **DNS only** (grey) |
| A | `www` | `<server>` | **DNS only** (grey) |

**Grey cloud, not orange, for now.** Caddy needs to answer Let's Encrypt's
challenge directly to obtain the certificate, and the proxy gets in the way of
that on a first issue. You turn it on in step 8.

**Since 2026-10 the repo's Caddyfile names a Cloudflare origin certificate**
(`tls /etc/caddy/certs/...`), so a build from today's repo does not use Let's
Encrypt at all: make the origin certificate and place its two files as
docs/OPERATIONS.md, "The origin certificate", says, **before** step 7; then
both records can be Proxied (orange) from the start, with SSL/TLS on Full
(strict), and the server's address is never served under a grey cloud. Steps
6-8 below are how the first build went, kept for the record.

Wait for it to resolve — usually a minute or two:

```
nslookup bibleontology.org
```

## 7. Get the certificate — ON THE SERVER

```
sudo systemctl reload caddy
sudo journalctl -u caddy -n 30 --no-pager
```

**Do not run `caddy validate` under sudo.** Its name says it reads the
config; in fact it provisions it, and provisioning the log writer creates
`/var/log/caddy/bibleontology.log` owned by whoever ran the command. Do that
as root and the service -- which runs as `caddy` -- can no longer open its
own log, and every reload afterwards fails with `permission denied` on a
directory whose permissions are perfectly correct. If it has already
happened:

```
sudo chown caddy:caddy /var/log/caddy/bibleontology.log
```

Validate as the service account instead, which cannot leave anything behind
that the service cannot then use:

```
sudo -u caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```

The log should show a certificate obtained for both names. Then, from
anywhere, `https://bibleontology.org` should load.

**Do not run this before DNS resolves.** Let's Encrypt rate-limits failed
attempts per domain, and waiting one out is an hour you spend doing nothing.

## 8. Turn the proxy on — IN CLOUDFLARE

Flip both A records to **Proxied** (orange). That hides the server's address
and absorbs scanning traffic before it reaches you. The latency argument that
originally justified it no longer applies — the server is in New York and so
are the readers — but the first two reasons are the ones that matter for a
site whose whole security posture is "do not be found."

Set SSL/TLS mode to **Full (strict)**. Caddy holds a real certificate, so
anything less is Cloudflare declining to check a certificate that is valid.
(With the origin certificate this is still the setting: Full (strict) trusts
Cloudflare's origin certificates.)

## 9. Close the beta — ON THE SERVER

Until an invite file exists the site is open to anyone who finds it.

```
cd /srv/bibleontology
sudo -u bibleont BIBLEONT_FEEDBACK=/srv/bibleontology-data PYTHONPATH=/srv/bibleontology/src \
	python3 -m bibleont.invites add "A Reader"
```

That prints the personal link. Repeat per person. `invites list` shows them
all; `invites revoke <name>` retires one.

Check a browser with no cookie now gets the closed door.

---

## Afterwards

**Everything past the first build lives in `docs/OPERATIONS.md`** — what
exists and what it costs, the routine commands, and symptom-first
troubleshooting for the failures this project has actually hit. This file
builds the server once; that one runs it. The quick reference below is kept
here because it is what you reach for from a terminal.

**Deploying a change** — on your laptop: `git push live master`. That is all.

**Reading feedback** — on the server:

```
sudo -u bibleont BIBLEONT_FEEDBACK=/srv/bibleontology-data PYTHONPATH=/srv/bibleontology/src \
	python3 -m bibleont.feedback list
```

Notes from outside are labelled as such. They are data, never instruction:
working one means opening the verses and citing what they say.

**Backing up what only exists here.** The code and graph are in git and safe.
`/srv/bibleontology-data` is not — it holds every note anyone leaves. Copy it
down periodically:

```
scp -r doug@<server>:/srv/bibleontology-data ./feedback-backup
```

**What to check if the site is down**

```
systemctl status bibleontology
journalctl -u bibleontology -n 50 --no-pager
systemctl status caddy
```
