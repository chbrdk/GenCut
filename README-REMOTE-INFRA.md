# Remote Server Infrastructure (plygrnd.tech)

This document summarizes the current infrastructure on the remote server hosting services under the `plygrnd.tech` domain.

## Host Overview
- **Hostname**: 93.93.115.29
- **OS**: Ubuntu 24.04.3 LTS (Noble)
- **Kernel**: Linux 6.8.x (generic)
- **CPU**: 4 vCPU (AMD EPYC-Milan), virtualization under Microsoft hypervisor
- **RAM**: 7.7 GiB (≈5.8 GiB available at last check)
- **Disk**: 232G (≈6% used)
- **SSH**: `ssh root@93.93.115.29`
- **Firewall (UFW)**: active; allows `22/tcp`, `80/tcp`, `443/tcp`

## Container Runtime
- **Docker Engine**: 28.3.3
- **Docker Compose**: v2.39.1
- **Networks**:
  - `n8n_default` (shared/external network used for reverse-proxied services)
  - `bridge`, `host`, `none`
- **Volumes**:
  - `n8n_postgres_data`, `n8n_n8n_data`
  - `n8n_caddy_data`, `n8n_caddy_config`

## Reverse Proxy and TLS
- **Proxy**: Caddy runs as a container in the `n8n` stack and exposes `80/443` on the host.
- **Config file**: `/opt/n8n/Caddyfile`
- **Domains and routes** (from Caddyfile):

```
n8n.plygrnd.tech, www.plygrnd.tech, plygrnd.tech -> n8n:5678
flowsight.plygrnd.tech -> flowsight-prod:3007
autopod.plygrnd.tech -> udg-autopod-app:3001
mcp.plygrnd.tech -> elevenlabs-http-mcp-server:3006
techlex.plygrnd.tech -> techlex-frontend:5173
```

- **Certificates**: Managed automatically by Caddy for the mapped domains.

## Deployed Stacks and Locations

### n8n stack (`/opt/n8n`)
- Services: `postgres`, `n8n`, `caddy`.
- Compose: `/opt/n8n/docker-compose.yml`.
- Volumes: `n8n_postgres_data`, `n8n_n8n_data`, `n8n_caddy_data`, `n8n_caddy_config`.
- Notes: Caddy in this stack reverse-proxies other services reachable on `n8n_default`.

### Flowsight (`/opt/flowsight`)
- Service: `flowsight-prod`.
- Compose: `/opt/flowsight/docker-compose.yml`.
- Network: attaches to `n8n_default` (declared as external).
- Domain: `flowsight.plygrnd.tech`.

### Techlex (`/opt/techlex`)
- Service: `techlex-frontend`.
- Compose: `/opt/techlex/docker-compose.yml`.
- Port: 5173 (published to loopback by docker-proxy).
- Network: attaches to the shared proxy network.
- Domain: `techlex.plygrnd.tech`.

### Autopod (`/opt/udg-autopod` and `/opt/autopod/podcast-generator-dmexco`)
- Service: `udg-autopod-app`.
- Compose indicates host networking and dev-style bind mounts.
- Domain: `autopod.plygrnd.tech`.
- Note: Two similar compose paths exist; the running image suggests the `podcast-generator-dmexco` variant is active. Consider consolidating to a single canonical location.

### ElevenLabs HTTP MCP
- Running container: `elevenlabs-http-mcp-server`.
- Port: 3006 (published to loopback).
- Domain: `mcp.plygrnd.tech`.
- Note: Two compose definitions exist (`/opt/elevenlabs-mcp` and `/opt/autopod/elevenlabs-mcp`), but the active container is the HTTP MCP server used by autopod. Recommend standardizing.

## Currently Running Containers (examples)
- `n8n-caddy-1` (Caddy) — 80/443 exposed.
- `n8n-n8n-1` (n8n).
- `n8n-postgres-1` (Postgres 15).
- `flowsight-prod` — 3007 (public).
- `techlex-frontend` — 5173 (loopback).
- `udg-autopod-app` — 3001 (loopback, host network).
- `elevenlabs-http-mcp-server` — 3006 (loopback).

## Managing Stacks

Bring up/down and inspect a stack:

```bash
cd /opt/<stack>
docker compose pull
docker compose up -d
docker compose ps
docker compose logs -f
```

Common stack dirs: `n8n`, `flowsight`, `techlex`, `udg-autopod`, `autopod/podcast-generator-dmexco`, `elevenlabs-mcp`.

## Logs and Troubleshooting

```bash
# Containers
docker ps
docker logs -f <container>

# System services
journalctl -u docker -f

# Ports
ss -tulpn | grep -E ':(80|443|3001|3006|3007|5173)\b'
```

## Data and Backups
- n8n Postgres data: `n8n_postgres_data`.
- n8n app data/uploads: `n8n_n8n_data` (Caddy exposes `/n8n_data` for static files).

Ad-hoc snapshot example:

```bash
docker run --rm --volumes-from n8n-postgres-1 \
  -v $(pwd):/backup busybox \
  tar czf /backup/n8n_postgres_data_$(date +%F).tar.gz /var/lib/postgresql/data
```

Consider scheduled backups via cron + object storage.


## Security Notes and Recommendations
- Keep only `22/80/443` open; current UFW rules are good.
- Consider fail2ban for SSH.
- Unattended upgrades are enabled; keep Docker images up to date.
- Move secrets (e.g., provider API keys) into `.env` or Docker secrets, not inline in compose files.
- Standardize service locations to a single compose per service to reduce drift.

## Quick Reference
- Proxy config: `/opt/n8n/Caddyfile`.
- n8n stack: `/opt/n8n/docker-compose.yml`.
- Flowsight: `/opt/flowsight/docker-compose.yml`.
- Techlex: `/opt/techlex/docker-compose.yml`.
- Autopod (current): `/opt/autopod/podcast-generator-dmexco/docker-compose.yml`.
- ElevenLabs MCP (variant in use): alongside autopod; container `elevenlabs-http-mcp-server`.

---
_Last verified against the live host on:_ 2025-09-02

## Native Mail Server (Postfix + Dovecot + OpenDKIM)
- Hostname: `mail.plygrnd.tech`
- Services and ports:
  - SMTP: 25 (server-to-server), 587 (submission, STARTTLS)
  - IMAP: 993 (IMAPS)
  - OpenDKIM milter: 127.0.0.1:12301
- Firewall (UFW): 25/tcp, 587/tcp, 993/tcp allowed

### Account(s)
- Mailbox: `hello@plygrnd.tech`
- Password: `SnojEN2DapCCGPbLY3e/fhh4`

### Client settings
- Incoming (IMAP):
  - Host: `mail.plygrnd.tech`
  - Port: 993
  - Security: TLS/SSL
  - User: `hello@plygrnd.tech`
  - Pass: as above
- Outgoing (SMTP):
  - Option A (Submission): Host `mail.plygrnd.tech`, Port 587, Security STARTTLS, Auth ja
  - Option B (Implicit TLS): Host `mail.plygrnd.tech`, Port 465, Security SSL/TLS, Auth ja

### DNS records (add at your DNS provider)
- A: `mail.plygrnd.tech. 300 IN A 93.93.115.29`
- MX: `plygrnd.tech. 300 IN MX 10 mail.plygrnd.tech.`
- SPF (TXT on `plygrnd.tech.`): `v=spf1 a mx ~all`
- DKIM (TXT on `default._domainkey.plygrnd.tech.`):
```txt
default._domainkey      IN      TXT     ( "v=DKIM1; h=sha256; k=rsa; "
          "p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA5Xw0tmbek1qttN882zCiIlQlwH32LPVaHYpewMq3Gz8lVYTNNG2
QqySTzvyPNDhWB1h5tCYH9GoNhKbRneXU70XOxQrwYvxf/v09duwHQiLdXg/z61+O28/Sy14xwCjh93CQFJYlfwE9/XN2zaKQIcvd3Jh7gKG
NzZ/yvgmtyqyLfBFOFwK0d/trfW1p6VeF7J5O8f+06iq7Fi"

          "zTcznuQS4wpIjS358f8xo4uTcAOblXhEBItS340ShYwRUikpdGPLvLGEW17i7F0SishOOcO+Y65jWyc/RkFKNNO0wDyqa9TC4
y1+vjSoR0TGsRSXWBwsgUqpVka95bLbMMVE+bBQIDAQAB" )  ; DKIM key default for plygrnd.tech
```
- DMARC (TXT on `_dmarc.plygrnd.tech.`): `v=DMARC1; p=none; rua=mailto:hello@plygrnd.tech; fo=1`
- PTR (Reverse DNS): Set the IP `93.93.115.29` PTR to `mail.plygrnd.tech` at your provider (improves reputation)

### Server paths and config
- Postfix:
  - Main: `/etc/postfix/main.cf`
  - Master: `/etc/postfix/master.cf`
  - Virtual map: `/etc/postfix/vmailbox` (+ `postmap`)
- Dovecot:
  - Auth/passwd: `/etc/dovecot/passwd` (SHA512-CRYPT)
  - Overrides: `/etc/dovecot/conf.d/99-local-*.conf`
  - Maildir storage: `/var/vmail/<domain>/<user>/Maildir`
- OpenDKIM:
  - Config: `/etc/opendkim.conf`
  - Keys: `/etc/opendkim/keys/plygrnd.tech/`
  - Socket: `inet:12301@localhost`
  - PID dir: `/run/opendkim/`

### Operations
- Restart services:
```bash
systemctl restart postfix dovecot opendkim
```
- Check ports/services:
```bash
ss -tulpn | grep -E ':(25|587|993|12301)\b'
```
- Rotate password for an account (example for hello@plygrnd.tech):
```bash
USER=hello@plygrnd.tech; PASS=$(openssl rand -base64 18); HASH=$(openssl passwd -6 "$PASS"); \
  sed -i "s#^$USER:.*#$USER:$HASH:5000:8::/var/vmail/plygrnd.tech/hello::#" /etc/dovecot/passwd; \
  systemctl restart dovecot postfix; echo "$USER $PASS"
```
- Add another mailbox:
```bash
USER_LOCAL=newuser; USER="$USER_LOCAL@plygrnd.tech"; \
  mkdir -p /var/vmail/plygrnd.tech/$USER_LOCAL/Maildir/{cur,new,tmp}; chown -R vmail:mail /var/vmail/plygrnd.tech/$USER_LOCAL; \
  PASS=$(openssl rand -base64 18); HASH=$(openssl passwd -6 "$PASS"); \
  echo "$USER:$HASH:5000:8::/var/vmail/plygrnd.tech/$USER_LOCAL::" >> /etc/dovecot/passwd; \
  echo "$USER plygrnd.tech/$USER_LOCAL/" >> /etc/postfix/vmailbox; postmap /etc/postfix/vmailbox; \
  systemctl restart postfix dovecot; echo "$USER $PASS"
```

### Notes
- After DNS propagation (A/MX/SPF/DKIM/DMARC/PTR), test sending and IMAP login from an external client.
- For best deliverability, keep PTR aligned and consider moving DMARC policy from `p=none` to `p=quarantine`/`reject` after observation.

### Changes
- 2025-09-01: MailHog test SMTP removed (stack at `/opt/mailhog` torn down, Caddy route `mail.plygrnd.tech` removed). Native Postfix/Dovecot/OpenDKIM is now authoritative for mail on `plygrnd.tech`.

### Postfix transport configuration
- inet_protocols: ipv4
- smtp_address_preference: ipv4
- SMTPS 465 and Submission 587 enabled
- Dovecot LMTP enabled (socket: `/var/spool/postfix/private/dovecot-lmtp`)

### Current status
- Outbound delivery to Gmail verified (status=sent) over IPv4
- Queue: empty (DSN re-delivered via LMTP)

## Autopod Uploader API and Landing Page Generator
- Host: `autopod.plygrnd.tech`
- Endpoints:
  - POST `/api/upload` → stores image/audio files and generates dedicated landing page
  - Static files served at: `https://autopod.plygrnd.tech/static/*`
  - Podcast assets served at: `https://autopod.plygrnd.tech/podcasts/<podcast>/assets/<filename>`
  - Landing pages served at: `https://autopod.plygrnd.tech/podcasts/<podcast>/<imageName>-landing.html`
- Backing service: `autopod-uploader` (Flask) in `/opt/autopod/uploader`, mounts `n8n_n8n_data` at `/data`
- Main app: `udg-autopod-app` (Flask) in `/opt/autopod/podcast-generator-dmexco`, bridge networking
- Reverse proxy (Caddyfile `autopod.plygrnd.tech` block):
  - `/static/*` → `root * /n8n_data/static` + `file_server browse`
  - `/api/upload*` → `reverse_proxy autopod-uploader:5001`
  - `/podcasts/*` → `root * /n8n_data` + `file_server browse`
  - `/audio/*` → `root * /n8n_data` + `file_server browse`
  - Main app → `reverse_proxy udg-autopod-app:3001`

### Enhanced Upload Request
- URL: `https://autopod.plygrnd.tech/api/upload`
- Method: POST
- Headers: `Content-Type: application/json`
- Body example:
```json
{
  "podcast": "myshow",
  "filename": "cover.png",
  "base64": "<BASE64_DATA>",
  "podcast_audio_base64": "<AUDIO_BASE64_DATA>",
  "podcast_audio_filename": "episode1.mp3"
}
```
- Alternative with URL:
```json
{
  "podcast": "myshow",
  "filename": "cover.png",
  "base64": "<BASE64_DATA>",
  "podcast_url": "https://example.com/podcast.mp3"
}
```
- Response example:
```json
{
  "url": "https://autopod.plygrnd.tech/podcasts/myshow/assets/cover.png",
  "path": "/podcasts/myshow/assets/cover.png",
  "audio_url": "https://autopod.plygrnd.tech/podcasts/myshow/assets/episode1.mp3",
  "audio_path": "/podcasts/myshow/assets/episode1.mp3",
  "landing_url": "https://autopod.plygrnd.tech/podcasts/myshow/cover-landing.html",
  "landing_path": "/podcasts/myshow/cover-landing.html"
}
```

### Landing Page Features
- **Design**: Based on general Autopod design (similar to `index-polling.html`)
- **Layout**: Uploaded image prominently displayed in center
- **Audio Player**: Glassmorph-styled player below the image for podcast playback
- **Self-contained**: All assets embedded, no external dependencies
- **Responsive**: Works on desktop and mobile devices

### Data layout
- Stored under volume: `n8n_n8n_data`
- Path scheme: 
  - Images: `/podcasts/<podcast>/assets/<filename>`
  - Audio: `/podcasts/<podcast>/assets/<audio_filename>`
  - Landing pages: `/podcasts/<podcast>/<imageName>-landing.html`
  - Static assets: `/static/*`

### Notes
- Public fetch: `GET https://autopod.plygrnd.tech/podcasts/<podcast>/assets/<filename>`
- Landing page: `GET https://autopod.plygrnd.tech/podcasts/<podcast>/<imageName>-landing.html`
- Ensure `base64` payload is raw base64 (no data URL prefix)
- Audio can be provided via `podcast_audio_base64` or downloaded from `podcast_url`
- All static assets (CSS, images, animations) served from `/static/*`

## Backups
- Location: `/var/backups/server/YYYY-MM-DD_HHMMSS/`
- What: Docker volumes (tar.gz), configs (`/etc`, `/root`, `/opt`), package list
- Scripts:
  - `/opt/backup/backup_volumes.sh`
  - `/opt/backup/backup_all.sh`
- Schedule: daily at 03:15 via `/etc/cron.d/server_backup` (7-day retention)
- Manual run:
```bash
/opt/backup/backup_all.sh
```
- Restore notes (high-level):
  - Stop services → extract desired tarballs to target paths
  - For volumes: `docker run --rm -v <volume>:/v -v $(pwd):/backup busybox sh -c "cd /v && tar xzf /backup/vol_<volume>.tar.gz"`
  - Recreate containers and verify
