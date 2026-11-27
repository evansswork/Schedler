# ROADMAP

Current phase: **Phase 1**

Each phase ends with: acceptance criteria pass → merge to `main` → push → tag (see the release skill).

## Phase 1: Foundation (local, DRY_RUN) → `v0.1.0`

- [x] Backend skeleton: FastAPI, config (pydantic-settings), SQLModel + SQLite (WAL), Alembic migrations
- [x] Models from ARCHITECTURE §3; ULID ids; UTC handling
- [x] Auth: single-user password login, session cookie
- [x] Pipeline: yt-dlp download, ffprobe probe, orientation classify, ffmpeg normalize (only when needed)
- [x] Storage: `LocalPublicStorage` + `R2Storage` behind one interface
- [x] `FakePublisher` + `DRY_RUN=true` end-to-end
- [x] APScheduler wired with `process_media` job
- [x] Frontend skeleton: Vite + React + TS + Tailwind + shadcn/ui, layout (sidebar/top bar), login, composer (link + MP4 input, accounts, caption, schedule), Antrian list
- [x] Tooling: ruff, pytest, eslint, prettier, `.env.example`, README setup for macOS

**Acceptance:** paste 3 TikTok links of the owner's own videos → all download, get the correct orientation badge, appear in Antrian as "Terjadwal" (DRY_RUN), and the files are playable.

## Phase 2: Instagram direct → `v0.2.0`

- [x] Meta app setup guide in README (Instagram API with Instagram Login, Standard Access)
- [x] Account connect (paste a long-lived token first; OAuth optional)
- [x] `IgDirectPublisher`: quota check → REELS container → poll → publish; retries; human error messages
- [x] `publish_ig_due` job + startup catch-up rule (≤ 6 h)
- [x] `refresh_ig_tokens` job
- [x] Slots + "next free slot" scheduling + batch spreading
- [x] Calendar view (week/month) with drag-to-reschedule

**Acceptance:** with `DRY_RUN=false` and one IG account, a scheduled Reel goes live within 5 minutes of its time, and a forced failure retries 3x and then shows in "Perlu perhatian".

## Phase 3: Buffer (YouTube + TikTok) → `v0.3.0`

- [x] Buffer key + channel picker; map channels to accounts
- [ ] Verify the live GraphQL schema for video posts + YouTube/TikTok metadata. Record field names in the platform-apis skill. (Fields from the docs are recorded; live check pending a key.)
- [x] `BufferPublisher`: schedule, cancel, sync
- [x] `buffer_refill` (≤ 10 per channel) + `buffer_sync` jobs + API budget guard
- [ ] TikTok feasibility test. If it fails, `manual_required` flow (download file + copy caption). (Manual flow built; live test pending.)
- [x] Edit/cancel propagation to Buffer

**Acceptance:** 15 videos queued for YT #1 → 10 go to Buffer, 5 wait, and the refill sends more as posts publish; Shorts vs. video are routed correctly; TikTok is either posting or cleanly `manual_required`.

## Phase 4: Feedback and polish → `v0.4.0`

- [x] Telegram notifications + daily summary + "Kirim tes"
- [x] "Perlu perhatian" inbox with one-click fixes
- [x] Health meters in the sidebar + health pill
- [x] Per-platform previews in the composer; keyboard shortcuts; dark mode; mobile layout
- [x] `cleanup_media`, `update_ytdlp` jobs

**Acceptance:** a full week of posts runs on the Mac without opening the dashboard, and every publish and failure arrives on Telegram.

## Phase 5: Production on VPS → `v1.0.0`

- [ ] Dockerfile (multi-stage), docker-compose, Caddyfile
- [ ] VPS setup guide (Ubuntu, Docker, firewall), DuckDNS, HTTPS
- [ ] Switch storage to `LocalPublicStorage`; migrate the DB from the Mac
- [ ] Nightly SQLite backup; restart policy; health endpoint
- [ ] Optional: GitHub Actions CI (lint + tests)

**Acceptance:** the dashboard is reachable over HTTPS from a phone; scheduled posts on all 5 accounts publish for 7 days straight with ≥ 98% success.

## Later (v1.x+)

- YouTube direct adapter after a successful YouTube API audit (frees 2 Buffer slots)
- AI caption suggestions
- Recurring / evergreen posts
- Simple analytics (views per post, via platform APIs)
