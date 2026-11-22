---
name: platform-apis
description: Rules, endpoints and gotchas for Schedler's external integrations (Instagram API with Instagram Login, Buffer GraphQL API, yt-dlp, Telegram Bot API). Load before writing or changing any code in backend/app/publishers, pipeline/download.py or notify/.
---

# Platform APIs

## General rules

- Use official APIs only. No browser automation for posting.
- Every integration has a fake for tests and `DRY_RUN`. Tests never hit the real network (use `respx`).
- Wrap calls with `httpx.AsyncClient(timeout=30)`, 3 retries with exponential backoff on 5xx and timeouts. Do not retry 4xx except 429 (honor `Retry-After`).
- Map every known error to an Indonesian `last_error_human` string; keep the raw body in `EventLog`.
- If the live API differs from this file, update this file in the same commit.

## Instagram (direct)

- API: Instagram API with Instagram Login. Host `https://graph.instagram.com/<version>`.
- Scopes: `instagram_business_basic`, `instagram_business_content_publish`.
- Access: Standard Access, no App Review, because the app only serves accounts the owner owns. Tokens for own accounts can be generated in the Meta App Dashboard.
- Account must be Professional (we use Creator).
- Publish a Reel:
  1. `POST /{ig-user-id}/media` with `media_type=REELS`, `video_url=<public https url>`, `caption=<text>` → `{id: container_id}`
  2. Poll `GET /{container_id}?fields=status_code` once per minute, ≤ 5 tries: `IN_PROGRESS` → wait; `FINISHED` → publish; `ERROR` or `EXPIRED` → fail.
  3. `POST /{ig-user-id}/media_publish?creation_id={container_id}` → `{id: media_id}`
  4. Optional: `GET /{media_id}?fields=permalink` for `published_url`.
- Quota: `GET /{ig-user-id}/content_publishing_limit?fields=quota_usage,config` before step 3. Meta docs say both 50 and 100 per 24 h, so trust the API's `config.quota_total`.
- Containers expire after 24 h; max 400 containers per 24 h. Create the container close to publish time (≤ 10 min before).
- Tokens: long-lived ~60 days. Refresh with `GET /refresh_access_token?grant_type=ig_refresh_token&access_token=…` (token must be ≥ 24 h old and not expired).
- Caption: ≤ 2,200 characters, ≤ 30 hashtags.
- Fallback when the URL fetch is flaky: resumable upload to `https://rupload.facebook.com/ig-api-upload/{container_id}`.

## Buffer (YouTube + TikTok)

- API: GraphQL at the endpoint listed on https://developers.buffer.com (personal API key, `Authorization: Bearer <key>`). The free plan allows 1 key and ~3,000 requests per 30 days (~250 per 24 h).
- Free plan: 3 channels, **10 scheduled posts per channel at a time**. Never send an 11th; hold it locally.
- Scheduled post: `createPost` mutation with `mode: customScheduled`, `dueAt: <ISO-8601 UTC>`, `channelId`, `text`, `assets: { videos: [{ url }] }`.
- Media must be a public URL that stays reachable until the post publishes. Do not clean it up early.
- Per-platform metadata (YouTube title, Short vs. video; TikTok title/privacy): **TO VERIFY in Phase 3** using the API Explorer. Write the confirmed field names here:
  - YouTube: `TBD`
  - TikTok: `TBD`
- TikTok risk: the Buffer roadmap mentions URL-pulled TikTok video may require a verified domain. If `createPost` fails for that reason, set the target to `manual_required`.
- Budget guard: count requests per day in `EventLog`; pause refills at 80% of the daily budget.

## yt-dlp (TikTok download)

- Only for the owner's own videos.
- Format: `-f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b" --merge-output-format mp4 --write-info-json --no-playlist`.
- Caption source: `description` in the info JSON; strip trailing tracking text.
- Errors to map: private/removed video, region block, rate limit (429), extractor broken. For "extractor broken", suggest the update action plus MP4 upload.
- Keep yt-dlp updated (daily job). Pin the minimum version in `pyproject.toml`, not the maximum.

## Telegram

- `POST https://api.telegram.org/bot<token>/sendMessage` with `chat_id`, `text`, `parse_mode=HTML`, `disable_web_page_preview=true`.
- ≤ 1 message per second; batch when > 5 events per minute.
- Message templates (Indonesian):
  - Success: `✅ <b>{akun}</b> tayang {jam} WIB\n{caption_30}\n{url}`
  - Failure: `❌ <b>{akun}</b> gagal: {alasan}\nSudah dicoba {n}x. Buka: {link_dashboard}`
