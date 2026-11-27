# Architecture: Schedler

## 1. Overview

```
                ┌──────────────────────── Schedler (one Docker stack) ───────────────────────┐
 Owner ──HTTPS──▶ Caddy ──▶ FastAPI app ──┬── REST API (/api/*) ◀── React SPA (static, /)    │
 (Mac/phone)    │  (TLS)     (uvicorn,    ├── APScheduler worker (same process)              │
                │            1 process)   ├── SQLite (data/schedler.db, WAL)                 │
                │                         └── Media dir (media/)  ◀── served at /m/<token>   │
                └────────────────────────────────────────────────────────────────────────────┘
                         │                    │                      │
                 yt-dlp + ffmpeg      Instagram Graph API      Buffer GraphQL API ──▶ YouTube, TikTok
                                       (graph.instagram.com)   Telegram Bot API
```

- **One process** runs the API and the scheduler (APScheduler `AsyncIOScheduler`) to keep SQLite single-writer friendly. Run uvicorn with `--workers 1`.
- The **React SPA** is built into static files and served by FastAPI (prod) or by Vite with `/api` proxied (dev).
- **Caddy** terminates TLS (Let's Encrypt) for the DuckDNS or own domain and also serves `/m/*` media (or proxies to FastAPI).

## 2. Environments

| | Local (Phases 1 to 4) | Production (Phase 5) |
|---|---|---|
| Host | macOS, VS Code | VPS (Ubuntu 24.04, Docker) |
| URL | http://localhost:5173 (dev) / :8000 | https://<name>.duckdns.org (or own domain) |
| Public media URLs (for Buffer and IG) | Cloudflare R2 public bucket (free tier) | Local `media/` dir served by Caddy |
| Publishing | `DRY_RUN=true` by default | `DRY_RUN=false` |

## 3. Data model (SQLModel / SQLite)

All timestamps are UTC (`datetime` with tz). IDs are ULIDs (sortable strings).

```
Account
  id, platform: ig|youtube|tiktok, label ("IG #1"), handle
  route: ig_direct|buffer
  ig_user_id?, buffer_channel_id?, buffer_key_ref?   # which Buffer API key (supports >1 org)
  yt_category_id?                                    # YouTube category for Buffer posts
  token_enc?, token_expires_at?                      # IG long-lived token (Fernet-encrypted)
  timezone (default Asia/Jakarta), slots: JSON ["11:00","19:00"], weekdays: JSON [1..7]
  active: bool, created_at, updated_at

MediaAsset
  id, source: tiktok_link|upload, source_url?, source_caption?
  status: pending|downloading|processing|ready|failed|deleted, progress_pct (0-100, download progress)
  file_path?, public_url?, public_token (random 32 bytes, url-safe)
  width?, height?, duration_s?, orientation: vertical|horizontal|square?
  size_bytes?, sha256?, error?, created_at, updated_at

Post                         # one logical post = one media + shared defaults
  id, media_id → MediaAsset, default_caption, created_at

PostTarget                   # one per account; the unit that gets scheduled and published
  id, post_id → Post, account_id → Account
  title?, caption, yt_kind?: short|video
  scheduled_at (UTC), schedule_mode: exact|slot
  status: draft|waiting_media|queued_local|sent_to_buffer|publishing|published|failed|cancelled|manual_required
  provider_ref?   # Buffer post id or IG container/media id
  published_url?, attempts: int, next_attempt_at?, last_error?, last_error_human?
  created_at, updated_at

EventLog
  id, at, level: info|warn|error, entity_type, entity_id, message, payload JSON

Setting
  key, value_enc?, value?    # runtime settings editable in UI (non-secret or encrypted)

Notification                 # Telegram outbox
  id, text, created_at, sent_at?
```

Indexes: `PostTarget(status, scheduled_at)`, `PostTarget(account_id, scheduled_at)`, `MediaAsset(status)`.

## 4. State machine (PostTarget)

```
draft ──save──▶ waiting_media ──media ready──▶ queued_local
queued_local ──(route=buffer, slot free)──▶ sent_to_buffer ──buffer published──▶ published
queued_local ──(route=ig_direct, ≤ 5 min before due: container created)──▶ publishing ──container FINISHED and due──▶ published
publishing / sent_to_buffer ──retryable error──▶ (attempts<3) queued_local with next_attempt_at (+2 min, +5 min)
                                      (attempts=3) failed
publishing ──IG quota used up──▶ publishing, next_attempt_at +1 h (not counted as an attempt)
any IG step ──token invalid / account not connected / video rejected──▶ failed (no retry)
TikTok route unsupported ──▶ manual_required
waiting_media / queued_local / failed ──user cancel──▶ cancelled  (publishing cannot be cancelled; Buffer posts: Phase 3)
```

## 5. Background jobs (APScheduler, persisted state in DB; jobs are idempotent)

| Job | Every | What it does |
|---|---|---|
| `process_media` | 30 s | Picks `pending` media: download (yt-dlp), probe, normalize, store, set `public_url`, mark `ready`; moves its targets to `queued_local` |
| `publish_ig_due` | 1 min | One step per IG target with `scheduled_at <= now + 5 min` (and `next_attempt_at` passed): `submit` creates the REELS container (`provider_ref`); `sync` polls `status_code` and, once `FINISHED` and due, checks quota → `media_publish` → permalink. A container already `PUBLISHED` (crash recovery) is just marked published |
| `buffer_refill` | 2 min | Per Buffer account: count our own `sent_to_buffer` targets (no API call). If < 10, send the earliest `queued_local` targets with `dueAt = scheduled_at` (now + 2 min if already past). Skipped while the API budget is low |
| `buffer_sync` | 5 min | Only `sent_to_buffer` targets 2 min past due: `post(id)` → `sent` = `published` (+ URL); still waiting = look again in 10 min; `error` = delete the Buffer post, then retry/failed like IG |
| `cleanup_media` | 1 h | Delete files whose targets are all published/failed/cancelled for 24 h (never while a target waits, is in Buffer or is `manual_required`; unscheduled uploads after 3 days); mark `deleted` |
| `refresh_ig_tokens` | daily | Refresh IG long-lived tokens expiring in < 15 days; warn on Telegram if refresh fails |
| `update_ytdlp` | daily 04:00 WIB | `pip install -U yt-dlp`. The running process keeps the old version, so in production the app exits cleanly and Docker restarts it; locally it reports that a restart is needed |
| `daily_summary` | daily 23:59 WIB | Telegram summary: published / failed today, scheduled tomorrow (after the owner's last slot) |
| `send_notifications` | 15 s | Sends the Telegram outbox (see §6.4) |

Startup: run `publish_ig_due` immediately. IG posts overdue by > 6 h are **not** auto-published. Mark them `failed` with the reason "Terlewat karena server mati", and notify.

**Buffer API budget (free):** 600 requests / 24 h and 1,000 per channel / 30 days (≈ 100 a day for 3 channels). Queue counts are local; status is read once per post after its due time. The `RateLimit` headers of every response are stored per key, and refills stop when < 20% of the day or < 10% of the month is left.

## 6. Publisher adapters

```python
class Publisher(Protocol):
    route: str                                   # "ig_direct" | "buffer"
    async def validate(self, target, media) -> list[Warning]
    async def submit(self, target, media) -> SubmitResult      # IG: publish now; Buffer: schedule
    async def sync(self, target) -> SyncResult                 # status/URL refresh
    async def cancel(self, target) -> None
```

Implementations: `IgDirectPublisher`, `BufferPublisher`, `FakePublisher` (tests, `DRY_RUN`). Selection by `Account.route`.

### 6.1 IG direct (Instagram API with Instagram Login)

- Host `graph.instagram.com`, scopes `instagram_business_basic`, `instagram_business_content_publish`.
- Owner-owned accounts → Standard Access, **no App Review**. Tokens can be generated in the Meta App Dashboard for the owner's own accounts (simplest for v1); an OAuth flow is optional.
- Flow: `POST /{ig-user-id}/media` with `media_type=REELS`, `video_url=<public_url>`, `caption` → poll `GET /{container-id}?fields=status_code` once per minute, up to 5 min (`FINISHED` → publish; `ERROR`/`EXPIRED` → fail) → `POST /{ig-user-id}/media_publish?creation_id=…`.
- Before publishing: `GET /{ig-user-id}/content_publishing_limit` and skip with retry-later if quota is used up.
- Long-lived tokens last ~60 days; refresh via `GET /refresh_access_token?grant_type=ig_refresh_token`.

### 6.2 Buffer (GraphQL API, personal API key)

- Docs: https://developers.buffer.com. Personal API key (Settings → API). The free plan allows 1 key.
- Create a scheduled post with the `createPost` mutation (`schedulingType: automatic`, `mode: customScheduled`, `dueAt`), the video as `assets: [{video: {url}}]` (public URL).
- YouTube needs `metadata.youtube.title` and `categoryId` (per account, `Account.yt_category_id`); `type` is `short` or `regularVideo` from `PostTarget.yt_kind`. Exact fields and the items still to verify live: `.claude/skills/platform-apis/SKILL.md`.
- Rescheduling or cancelling a `sent_to_buffer` target calls `editPost` / `deletePost` first; if Buffer refuses, the local post is left unchanged.
- The media URL must stay reachable until the post publishes, so do not delete media while any Buffer target is pending.
- TikTok risk: URL-pulled TikTok video may require a verified domain. If `createPost` for TikTok fails for that reason, set the target to `manual_required` and notify.

### 6.3 Downloader (yt-dlp)

- Download the best MP4 (`-f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b"`), merge with ffmpeg, write info JSON for the caption (`description`) and metadata.
- Verify the result has no TikTok watermark (yt-dlp normally selects the non-watermarked play URL). Record it in the event log if unsure.
- Only for the owner's own videos (see AGENTS.md).

### 6.4 Telegram

- Bot API `sendMessage` (HTML) to `TELEGRAM_CHAT_ID`. Messages in Indonesian.
- Outbox: a `Notification` row is written in the same transaction as the change it describes (post live, final failure, manual upload, missed during downtime, video download failed, IG login dead or < 7 days). `send_notifications` sends them ≤ 1 per second; more than 5 waiting become one combined message. Without Telegram settings the rows just wait.

## 7. Storage

`StorageBackend` interface: `put(local_path, key) -> public_url` (takes ownership of the file), `delete(key)`.

- `R2Storage` (dev): S3-compatible (`boto3`), public bucket or public dev URL, key = `public_token.mp4`.
- `LocalPublicStorage` (prod): moves the file to `media/public/<public_token>.mp4`, served at `https://<host>/m/<public_token>.mp4`. Only `media/public/` is served (work files in `media/incoming/` never are). Tokens are unguessable; directory listing is disabled.

## 8. Security

- Single-user password (argon2 hash in `.env` or DB) → HTTP-only, secure, SameSite=Lax session cookie. CSRF token on mutating requests.
- `.env` holds: `SECRET_KEY`, `FERNET_KEY`, `BUFFER_API_KEY(S)`, `META_APP_ID/SECRET`, `TELEGRAM_BOT_TOKEN/CHAT_ID`, R2 creds, `ADMIN_PASSWORD_HASH`.
- `/m/*` media is public by design (Buffer and IG must fetch it). Everything else requires auth.
- Rate-limit the login endpoint.

## 9. Deployment (Phase 5)

- `deploy/Dockerfile`: multi-stage (node build → python:3.14-slim + ffmpeg).
- `deploy/docker-compose.yml`: `app` (restart: unless-stopped, volumes `./data`, `./media`), `caddy` (ports 80/443, volume for certs).
- `deploy/Caddyfile`: `<host> { handle_path /m/* { root * /srv/media/public … file_server } reverse_proxy app:8000 }`.
- DNS: DuckDNS (or own domain) A record → VPS IP.
- Backups: nightly `sqlite3 .backup` of `data/schedler.db` (keep 7).
- CI (optional): GitHub Actions runs lint + tests on PRs to `main`.
