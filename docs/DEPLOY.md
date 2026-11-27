# Deploy: Schedler on a VPS

Production runs the same app as the Mac, in Docker, behind Caddy (automatic HTTPS). Video files are served from the VPS itself (`/m/...`), so R2 is no longer needed for new videos.

**Before you start:** stop the backend on the Mac when the VPS takes over (step 6). Two running copies would both publish the same posts.

## 1. VPS

- Ubuntu 24.04, 1–2 vCPU, 2 GB RAM or more, 25 GB disk or more (videos are deleted 24 h after they are posted).
- Log in as a normal user with `sudo` (the first user created on Ubuntu has uid 1000, which the app container also uses).

```bash
sudo apt update && sudo apt upgrade -y
sudo ufw allow OpenSSH && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw enable
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"    # log out and back in afterwards
```

## 2. Domain (DuckDNS, free)

1. Sign in at https://www.duckdns.org, add a subdomain (for example `schedler-evans`) and set its IP to the VPS IP.
2. Keep the IP current (every 5 minutes):

```bash
mkdir -p ~/duckdns
echo 'echo url="https://www.duckdns.org/update?domains=SUBDOMAIN&token=TOKEN&ip=" | curl -k -o ~/duckdns/duck.log -K -' > ~/duckdns/duck.sh
chmod 700 ~/duckdns/duck.sh
(crontab -l 2>/dev/null; echo "*/5 * * * * ~/duckdns/duck.sh >/dev/null 2>&1") | crontab -
```

Replace `SUBDOMAIN` and `TOKEN` with yours. The domain is `SUBDOMAIN.duckdns.org`.

## 3. Code and folders

```bash
git clone <your repo URL> schedler && cd schedler
mkdir -p data media/public
```

## 4. `.env`

Copy `.env` from the Mac (for example `scp .env user@VPS:~/schedler/.env`), then change these lines:

```bash
APP_ENV=production
DOMAIN=SUBDOMAIN.duckdns.org
APP_BASE_URL=https://SUBDOMAIN.duckdns.org
STORAGE_BACKEND=local_public
PUBLIC_MEDIA_BASE_URL=https://SUBDOMAIN.duckdns.org/m
DRY_RUN=false                      # only when you want real posting
```

Keep `SECRET_KEY`, `ADMIN_PASSWORD_HASH`, `BUFFER_API_KEYS`, `TELEGRAM_*` and **`FERNET_KEY`** unchanged: the Instagram tokens in the database can only be read with the same `FERNET_KEY`. Keep the `R2_*` lines too (see step 6).

## 5. First start (empty database)

```bash
docker compose -f deploy/docker-compose.yml up -d --build
docker compose -f deploy/docker-compose.yml logs -f app     # Ctrl+C to stop following
docker compose -f deploy/docker-compose.yml exec app python -m app.cli seed-accounts
```

Open `https://SUBDOMAIN.duckdns.org` on your phone, log in, then **Pengaturan → Kirim tes**.

## 6. Moving from the Mac (instead of step 5's seed)

1. On the Mac, **stop the backend** (Ctrl+C in its terminal) and keep it stopped.
2. Make a consistent copy of the database and send it:

```bash
cd ~/path/to/Schedler
sqlite3 data/schedler.db ".backup data/move.db"
scp data/move.db user@VPS:~/schedler/data/schedler.db
```

3. On the VPS: `docker compose -f deploy/docker-compose.yml up -d --build`.

Posts scheduled on the Mac keep their R2 video links, so keep the R2 bucket until the last of them has been posted (YouTube and TikTok fetch the file from Buffer at publish time). New videos are stored on the VPS.

Instagram, Buffer and Telegram keep working without reconnecting, because the tokens moved with the database and `FERNET_KEY` is the same.

## 7. Updating

```bash
cd ~/schedler && git pull
docker compose -f deploy/docker-compose.yml up -d --build
```

Database migrations run automatically when the app starts. Posts due during the restart are handled when it is back (Instagram posts more than 6 hours late are not published; they show in Perlu perhatian).

## 8. Backups

Every night at 03.00 WIB the app copies the database to `data/backups/` and keeps 7 days. Copy one off the server now and then:

```bash
scp user@VPS:~/schedler/data/backups/schedler-*.db ~/Backups/
```

To restore: stop the stack (`docker compose -f deploy/docker-compose.yml down`), copy the backup to `data/schedler.db`, start it again.

## Troubleshooting

- **The site has no HTTPS / Caddy errors:** check that the domain points to the VPS (`ping SUBDOMAIN.duckdns.org`) and ports 80 and 443 are open; then `docker compose -f deploy/docker-compose.yml logs caddy`.
- **`Missing required settings in .env`:** fill in the listed values and run `up -d` again.
- **Permission denied on `data/` or `media/`:** `sudo chown -R 1000:1000 data media`.
- **The app restarted by itself around 04.00 WIB:** expected after a yt-dlp update; Docker starts it again with the new version.
