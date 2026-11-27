# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com), versioning: SemVer.

## Unreleased

### Added
- Instagram direct publishing (Phase 2): connect IG accounts by pasting a dashboard token (encrypted with Fernet), Reels published on schedule with quota check, retries (2 and 5 min, then failed), crash-safe publish, and daily token refresh
- Startup rule: IG posts missed by more than 6 h are failed instead of published late
- Posting slots per account (default 19.30 to 23.30 WIB) and "Slot berikutnya (otomatis)" scheduling that spreads a batch over each account's free slots
- Kalender (week/month, drag to reschedule), Akun & slot, Perlu perhatian (failed posts, expiring logins), Tayang tab, Coba lagi and Batalkan
- README: Instagram setup guide and DNS troubleshooting
- YouTube and TikTok through Buffer (Phase 3): channel picker per account, YouTube category per account (YT #1 Science & Technology, YT #2 People & Blogs), at most 10 queued posts per channel refilled automatically, status read back after the due time, retries, and API budget guard from Buffer's rate-limit headers
- TikTok posts Buffer cannot pull become "Upload manual" items (download file, copy caption, mark as posted)
- Rescheduling or cancelling a post already in Buffer updates Buffer too

### Changed
- `FERNET_KEY` is now required; `IG_GRAPH_VERSION` defaults to v27.0
- `BUFFER_DAILY_REQUEST_BUDGET` removed: the budget now comes from Buffer's own rate-limit headers
- Validation errors use the same `{error: {code, message}}` shape as other API errors

## 0.1.0 (pending acceptance)

### Added
- Backend: FastAPI + SQLite (WAL) + Alembic, models with ULID ids and UTC timestamps
- Single-user login with session cookie, CSRF protection and login rate limit
- Video pipeline: yt-dlp download with progress, ffprobe orientation detection, ffmpeg normalize only when needed
- Storage on Cloudflare R2 or a local public folder
- Background `process_media` job; scheduling posts per video and account (test mode only)
- Frontend: login, composer (TikTok links or MP4 upload, per-video time, account picker with compatibility warnings) and Antrian
- macOS setup guide in README
- Project context docs: PRD, ARCHITECTURE, DESIGN, ROADMAP, DECISIONS, AGENTS.md, CLAUDE.md
- Claude Code skills: no-ai-slop, backend, frontend, ui-taste, copy-id, platform-apis, video-pipeline, testing, debug, release

### Changed
- Python target is 3.14 (ADR-008)
