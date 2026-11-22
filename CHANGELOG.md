# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com), versioning: SemVer.

## Unreleased

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
