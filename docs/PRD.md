# PRD: Schedler

Owner: Evans · Status: Draft v1 · Last updated: 2026-11-22

## 1. Problem

The owner runs several short-video accounts and posts the same video (originally published on TikTok) to Instagram, YouTube and TikTok every day. Scheduling each video by hand, in each app, for each account, takes too long. Paid schedulers (Publer, Buffer paid, Upload-Post) solve this but cost money per account. Building directly on each platform's API runs into audits (YouTube and TikTok lock unaudited uploads to private).

## 2. Goal

One self-hosted dashboard where the owner pastes a TikTok link or drops an MP4, picks accounts and time slots once, and **never has to open any app again** until something fails.

### Success metrics

| Metric | Target |
|---|---|
| Owner time per video (input to scheduled) | ≤ 30 seconds; ≤ 2 minutes for a batch of 10 links |
| Publish success rate (no manual intervention) | ≥ 98% |
| Posts going live within 5 minutes of scheduled time | ≥ 95% (IG direct); Buffer timing is Buffer's |
| Monthly cost of posting APIs | Rp0 |
| Days the owner needs to open the dashboard per week | ≤ 1 (plus on failure alerts) |

## 3. Users

A single user: the owner. Technical enough to run VS Code and a VPS with guidance. Uses the dashboard from a MacBook and from a phone.

## 4. Scope

### Target accounts (v1)

- Instagram: 2 accounts (Creator type), direct via Instagram API
- YouTube: 2 channels, via Buffer free plan
- TikTok: 1 account (personal, public), via Buffer free plan (feasibility verified in Phase 3)
- Volume: ~4 to 5 videos per day per account

### In scope (v1)

**Input**
- FR-1 Paste one or many TikTok links (one per line). Each becomes a media item.
- FR-2 Upload one or many MP4 files (drag and drop).
- FR-3 Auto-fill caption and hashtags from the TikTok source caption (editable).

**Processing**
- FR-4 Download the HD, watermark-free file via `yt-dlp`. Show progress and status.
- FR-5 Probe width, height and duration. Classify as `vertical`, `horizontal` or `square`.
- FR-6 Route by orientation: vertical ≤ 3 min becomes YouTube Shorts; anything else becomes a regular YouTube video. IG always publishes as Reels. Warn when a platform would reject or crop the video.
- FR-7 Normalize to platform-safe MP4 (H.264/AAC, yuv420p, faststart), re-encoding only when needed.

**Scheduling**
- FR-8 Per-account caption overrides: YouTube title + description, IG caption, TikTok caption.
- FR-9 Schedule modes: exact date/time, or "next free slot" using per-account time slots (AutoSchedule).
- FR-10 Bulk: N pasted links are spread across the next N free slots per selected account.
- FR-11 Calendar view (week and month) with drag-and-drop rescheduling.
- FR-12 Edit or cancel any scheduled post. Changes propagate to Buffer when the post was already sent.

**Publishing**
- FR-13 IG direct: the worker publishes at the scheduled time (container → poll status → publish). It checks the account's publishing quota first.
- FR-14 Buffer: keep each Buffer channel topped up to ≤ 10 queued posts, earliest first. The rest is held locally and sent when slots free up.
- FR-15 Automatic retry up to 3 times with backoff. After that, mark as failed with a human-readable reason.
- FR-16 Sync published status and post URLs back into Schedler.

**Feedback**
- FR-17 Telegram notification on each publish success and failure, plus a daily summary (optional).
- FR-18 "Perlu perhatian" inbox: all failures and warnings in one place, with a one-click "Coba lagi".
- FR-19 Health indicators: Buffer slot usage per channel, IG daily quota per account, token expiry, storage usage, Telegram bot status.

**Admin**
- FR-20 Connect and manage accounts; per-account time slots and timezone (default Asia/Jakarta).
- FR-21 Settings: API keys, Telegram, storage backend, dashboard password.
- FR-22 Single-user login (password), session cookie.

### Non-functional

- NFR-1 Runs on a 1 to 2 vCPU / 1 to 4 GB RAM VPS. Single Docker Compose stack.
- NFR-2 Survives restarts: all schedules and job state live in SQLite. Nothing important lives in memory only.
- NFR-3 Times stored in UTC; UI in Asia/Jakarta.
- NFR-4 UI in Indonesian; responsive (desktop + phone); light and dark mode.
- NFR-5 Media files are deleted after all targets are published, plus a 24-hour grace period.
- NFR-6 Secrets in `.env`; platform tokens encrypted at rest.
- NFR-7 `DRY_RUN` mode: the whole pipeline runs with fake publishers.

### Out of scope (v1)

- Multi-user, teams, approvals, client workspaces
- Analytics or insights dashboards
- Posting photos, carousels or stories
- AI caption generation (possible v2)
- Platforms other than IG, YouTube and TikTok
- Any paid posting API as a requirement

## 5. Constraints and known limits

| Item | Limit | Source / note |
|---|---|---|
| Buffer free plan | 3 channels, 10 scheduled posts per channel at a time (refillable) | buffer.com/pricing |
| Buffer API (free) | 150 / 15 min, 600 / 24 h, 1,000 per channel / 30 days (max 3,000) | developers.buffer.com (2026-11) |
| Buffer media | Must be a public URL, reachable until the post publishes | Buffer API docs |
| IG publishing | 50 to 100 API posts per account per 24 h (docs inconsistent). Read the real value from `content_publishing_limit`. | Meta docs |
| IG account type | Professional (Creator recommended, for the music library) | Meta docs |
| IG app review | Not required for accounts the owner owns or manages (Standard Access) | Meta docs |
| TikTok via Buffer API | May require verified domain for URL-pulled video. **Unverified; test in Phase 3.** | Buffer API roadmap |
| YouTube direct API | Uploads from unaudited projects are locked private. Not used in v1. | YouTube API docs |

## 6. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Buffer changes the free plan or API | YT + TikTok stop | Adapter design. Fallbacks: YouTube direct after audit, or an optional paid adapter. |
| TikTok via Buffer API fails | 1 account manual | Detect in Phase 3; mark TikTok targets as "siap upload manual" with file + caption |
| yt-dlp breaks after TikTok changes | Link input fails | Daily auto-update; clear error; MP4 input always available |
| IG token expiry (60 days) | IG stops | Auto-refresh job + Telegram warning 7 days before expiry |
| VPS down | IG posts miss their time | Docker restart policy; on startup, publish overdue IG posts (if < 6 h late) and notify |

## 7. Release plan

See `docs/ROADMAP.md`. Phases 1 to 4 run locally on macOS; Phase 5 moves to a VPS (production).
