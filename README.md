# Schedler

Self-hosted video scheduler: paste a TikTok link (of your own video) or drop an MP4, and Schedler downloads it in HD, detects orientation and publishes on schedule to Instagram, YouTube and TikTok, with Telegram notifications. Rp0 posting APIs; only a VPS is paid.

- Product: [docs/PRD.md](docs/PRD.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- UI/UX: [docs/DESIGN.md](docs/DESIGN.md)
- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)
- Decisions: [docs/DECISIONS.md](docs/DECISIONS.md)
- Agent rules: [AGENTS.md](AGENTS.md) · [CLAUDE.md](CLAUDE.md)

## Status

Phase 2 (Instagram direct): Instagram Reels publish on schedule once an account is connected and `DRY_RUN=false`. YouTube and TikTok (via Buffer) arrive in Phase 3; until then their posts stay in the queue. With `DRY_RUN=true` (the default) nothing is posted and posts turn "Tayang" at their time.

## Setup on macOS (Apple Silicon)

### 1. System packages

```bash
brew install python@3.14 node ffmpeg
```

`yt-dlp` is installed into the backend's virtualenv, not through Homebrew.

### 2. Cloudflare R2 (public video URLs)

Instagram and Buffer fetch videos from a public URL, so local development stores processed videos in an R2 bucket (free tier). Menu names in the Cloudflare dashboard may differ slightly.

1. Cloudflare dashboard → **R2** → create a bucket named `schedler-media`.
2. Bucket → **Settings** → **Public access** → enable the **r2.dev** public development URL. Copy it (`https://pub-….r2.dev`).
3. R2 → **Manage API tokens** → create a token with **Object Read & Write**, scoped to `schedler-media`. Copy the Access Key ID and Secret Access Key.
4. Copy your **Account ID** from the R2 overview page.

The r2.dev URL is rate-limited and meant for development; production (Phase 5) serves videos from the VPS instead.

### 3. Configure `.env`

```bash
cp .env.example .env
python3.14 -c "import secrets;print(secrets.token_urlsafe(48))"   # -> SECRET_KEY
python3.14 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"   # -> FERNET_KEY (after step 4's pip install)
```

Fill in `SECRET_KEY`, `FERNET_KEY` and the `R2_*` values. Keep `DRY_RUN=true`. `FERNET_KEY` encrypts the Instagram tokens in the database: keep it, because changing it makes stored tokens unreadable (reconnect the accounts if that happens).

### 4. Backend

```bash
cd backend
python3.14 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m app.cli hash-password      # paste the printed ADMIN_PASSWORD_HASH='…' line into .env
alembic upgrade head                 # creates data/schedler.db
python -m app.cli seed-accounts      # IG #1, IG #2, YT #1, YT #2, TikTok (no tokens yet)
uvicorn app.main:app --reload        # API + background jobs on :8000
```

### 5. Frontend (second terminal)

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173 (proxies /api to :8000)
```

Open http://localhost:5173, log in with the password from step 4, press `N` (or **Buat post**), paste TikTok links of your own videos, pick accounts and press **Jadwalkan**.

### 6. Connect Instagram (Phase 2)

Schedler posts Reels through Meta's *Instagram API with Instagram Login*, for accounts you own (no App Review needed). Menu names in the Meta dashboard can change slightly.

1. In the Instagram app, switch each account to a **Creator** account (Settings → Account type and tools) and make sure it is **public**.
2. Go to https://developers.facebook.com → **My Apps** → **Create app**. Pick the use case **Other**, then app type **Business**, and give it a name (for example "Schedler").
3. In the app, add the **Instagram** product and click **Set up**. This opens **API setup with Instagram business login**.
4. Under **Generate access tokens**, click **Add account** and log in with IG #1. If Instagram asks you to accept a tester invite, accept it in the Instagram app and refresh the page.
5. Click **Generate token** next to the account, approve the permissions (`instagram_business_basic`, `instagram_business_content_publish`) and copy the token. Dashboard tokens are valid for 60 days; Schedler refreshes them automatically.
6. In Schedler, open **Akun & slot**, click **Tempel token** on IG #1 and paste it. The card shows `@username` and "Terhubung" when it works.
7. Repeat steps 4 to 6 for IG #2.

Posting for real: set `DRY_RUN=false` in `.env` and restart the backend. Each Reel's container is created 5 minutes before its time and published on the minute. A failed post is retried after 2 and 5 minutes; after the 3rd failure it shows in **Perlu perhatian**. Keep the Mac awake and the backend running: posts missed by more than 6 hours (server off) are not published late.

**Slots:** every account starts with 19.30, 20.30, 21.30, 22.30 and 23.30 WIB, every day. Change them in **Akun & slot**. "Slot berikutnya (otomatis)" in the composer spreads the videos over each account's next free slots.

### Checks

```bash
cd backend && ruff check . && ruff format --check . && pytest -q
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

After changing backend API schemas, regenerate the frontend types with `npm run gen:api` (backend must be running).

### Troubleshooting

- **App exits with `Missing required settings in .env: …`**: fill in the listed values.
- **Login says the password is not set**: run `python -m app.cli hash-password` and paste the whole printed line, including the single quotes.
- **A TikTok link fails with "Pengunduh TikTok lagi bermasalah"**: update the downloader with `pip install -U yt-dlp` inside `backend/.venv`, or upload the MP4 instead.
- **Videos don't play in the dashboard, and opening the `pub-….r2.dev` link shows a Telkomsel "internetbaik" page**: your ISP's DNS blocks `*.r2.dev`. Uploads and Instagram still work, since only your Mac is affected. Set the Mac's DNS to `1.1.1.1` and `8.8.8.8` (System Settings → Network → your connection → Details → DNS).
- **"Token ditolak Instagram"**: the token was not copied whole, or it expired. Generate a new one (section 6, step 5).
