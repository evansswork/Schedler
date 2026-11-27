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

- API: Instagram API with Instagram Login. Host `https://graph.instagram.com/<version>`; version from `IG_GRAPH_VERSION` (v27.0 as of 2026-11; check https://developers.facebook.com/docs/graph-api/changelog).
- Auth: `Authorization: Bearer <token>` header. Account id: `GET /me?fields=user_id,username` → `{"data": [{"user_id", "username"}]}` (Meta documents the `data` wrapper; the client accepts a flat object too). Use `user_id`, not `id` (app-scoped).
- Scopes: `instagram_business_basic`, `instagram_business_content_publish`.
- Access: Standard Access, no App Review, because the app only serves accounts the owner owns. Tokens for own accounts: App Dashboard → Instagram → API setup with Instagram business login → Generate token. These are long-lived (60 days).
- Account must be Professional (we use Creator).
- Publish a Reel:
  1. `POST /{ig-user-id}/media` with `media_type=REELS`, `video_url=<public https url>`, `caption=<text>` → `{id: container_id}`
  2. Poll `GET /{container_id}?fields=status_code,status` once per minute (Meta recommends ≤ 5 min; Schedler waits up to 15 min). Values: `IN_PROGRESS` → wait; `FINISHED` → publish; `PUBLISHED` → already done (use for crash recovery); `ERROR` (`status` holds the subcode) or `EXPIRED` → fail.
  3. `POST /{ig-user-id}/media_publish?creation_id={container_id}` → `{id: media_id}`
  4. Optional: `GET /{media_id}?fields=permalink` for `published_url`.
- Quota: `GET /{ig-user-id}/content_publishing_limit?fields=quota_usage,config` before step 3 → `{"data": [{"quota_usage": 2, "config": {"quota_total": 50, "quota_duration": 86400}}]}`. Meta docs say both 50 and 100 per 24 h, so trust the API's `config.quota_total`. The reference example uses graph.facebook.com; we call graph.instagram.com (per its requirements table). Verify on the first live run.
- Containers expire after 24 h; max 400 containers per 24 h. Create the container close to publish time (≤ 10 min before).
- Tokens: long-lived 60 days. Refresh with unversioned `GET https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=…` → `access_token`, `token_type`, `expires_in` (token must be ≥ 24 h old and not expired; an expired token cannot be refreshed).
- Caption: ≤ 2,200 characters, ≤ 30 hashtags, ≤ 20 @ tags.
- Reels file: MP4/MOV, H.264/HEVC, AAC ≤ 48 kHz, moov atom first, 3 s to 15 min, ≤ 300 MB, ≤ 1920 px wide.
- Resumable upload (`rupload.facebook.com`) is documented for the Facebook Login variant only; with Instagram Login use `video_url`.
- Errors (`error.code` / `error.error_subcode`), mapped in `publishers/ig_client.py`:
  - 190 (any subcode): token invalid/expired → reconnect, no retry. Not on Meta's IG error page, but standard Graph OAuth.
  - 9 / 2207042: publishing limit reached → retry later without counting an attempt.
  - 9004 / 2207052: media could not be fetched from the URL → retry (check storage).
  - 352 / 2207026: unsupported video format; 36004 / 2207010: caption too long; 25 / 2207050: account restricted; 4 / 2207051: spam restriction → no retry.
  - 4, 9, 17, 32, 613 (other subcodes) and HTTP 429/5xx → rate limit or outage → retry.

## Buffer (YouTube + TikTok)

Source: https://developers.buffer.com (read 2026-11-27); checked live on 2026-11-27 where marked **verified live**. Items marked **verify live** must be checked on the first real run; fix code and this file in the same commit if they differ.

- Endpoint `POST https://api.buffer.com`, `Authorization: Bearer <key>`. Key: publish.buffer.com/settings/api. Free plan: 1 key, API included.
- Limits (free): 150 / 15 min, 600 / 24 h, 1,000 per unlocked channel per 30 days (max 3,000), shared by all keys of the account. Every response carries `RateLimit: "<name>"; r=<left>; t=<reset s>` and `RateLimit-Policy: "<name>"; q=<quota>; w=<window s>` (match windows by `w`: 900, 86400, 2592000; **verified live**: 150/15 min, 600/24 h, 1,000/30 days on a 1-channel free account). 429 → `Retry-After` seconds, body `extensions.code = RATE_LIMIT_EXCEEDED`; a 429 costs nothing.
- Budget guard (`buffer_client.budget_ok`): stored headers per key; no new posts when < 20% of the day or < 10% of the month is left. Queue size per channel is counted locally (our `sent_to_buffer` targets), not queried.
- Free plan: **10 scheduled posts per channel at a time** (Buffer roadmap; user-reported via support, **verify live**). Never send an 11th; hold it locally.
- Channels: `account { organizations { id name } }`, then `channels(input: {organizationId}) { id name displayName service isDisconnected }`. `service` values lowercase: `youtube` **verified live**, `tiktok` still to verify. The organizations and channels queries work as written (**verified live**).
- Create: `createPost(input: CreatePostInput!)` with `channelId`, `text`, `schedulingType: automatic`, `mode: customScheduled`, `dueAt` (ISO UTC, future), `assets: [{video: {url}}]` (`thumbnailUrl` is rejected), `metadata`. Result union: `... on PostActionSuccess { post { id } }`, `... on MutationError { message }`.
  - YouTube: `metadata.youtube { title (required), type: short | regularVideo, categoryId (required), privacy, madeForKids, notifySubscribers }`. Categories: 1, 2, 10, 15, 17, 19, 20, 22–29 (see `services/accounts.YT_CATEGORIES`).
  - TikTok: `metadata.tiktok { title }` is for photo posts only; we send no metadata. No privacy field.
- Read: `post(input: {id}) { id status externalLink }`. Status values `buffer` (scheduled), `sending`, `sent`, `error`, `draft`: **verify live** (docs examples also use `scheduled`).
- Edit: `editPost(input: {id, dueAt})`; delete: `deletePost(input: {id})` (`PostNotDeletableError` when already sent).
- Media: public, direct, stable HTTPS URL reachable until Buffer publishes (R2 public URL works). Do not clean it up early.
- TikTok risk: URL-pulled TikTok video may require a verified domain (user report on Buffer's roadmap, **verify live**). If `createPost` for TikTok fails that way, the target becomes `manual_required` (owner downloads the file + copies the caption).

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
