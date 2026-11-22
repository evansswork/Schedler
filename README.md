# Schedler

Self-hosted video scheduler: paste a TikTok link (of your own video) or drop an MP4, and Schedler downloads it in HD, detects orientation and publishes on schedule to Instagram, YouTube and TikTok, with Telegram notifications. Rp0 posting APIs; only a VPS is paid.

- Product: [docs/PRD.md](docs/PRD.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- UI/UX: [docs/DESIGN.md](docs/DESIGN.md)
- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)
- Decisions: [docs/DECISIONS.md](docs/DECISIONS.md)
- Agent rules: [AGENTS.md](AGENTS.md) · [CLAUDE.md](CLAUDE.md)

## Status

Phase 1 (foundation): runs locally in test mode (`DRY_RUN=true`). Nothing is posted to any platform yet; Instagram arrives in Phase 2, Buffer (YouTube + TikTok) in Phase 3.

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
```

Fill in `SECRET_KEY` and the `R2_*` values. Keep `DRY_RUN=true`.

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
