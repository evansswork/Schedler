---
name: debug
description: Systematic debugging for Schedler, especially failed posts and external API errors (Instagram, Buffer, yt-dlp, ffmpeg, Telegram). Use when a post fails, a job misbehaves, the owner reports "nggak ke-upload", or any error appears.
---

# Debug

## Order of operations

1. **Reproduce and scope.** Which target/media/account? Since when? One account or all? Check `EventLog` for the entity and the job run summaries.
2. **Classify the failure:**
   - Input: link private/removed, unsupported file → user-facing message, no retry.
   - Pipeline: yt-dlp or ffmpeg error → check versions (`yt-dlp --version`), rerun the single step manually on the file.
   - Auth: IG token expired/revoked, Buffer key invalid → "Sambungkan ulang" flow.
   - Quota/limits: IG `content_publishing_limit`, Buffer 10-slot cap or request budget, HTTP 429.
   - Media fetch: platform can't fetch `public_url` → `curl -I <public_url>` from outside; check Caddy/R2 and that media wasn't cleaned early.
   - Platform-side rejection: IG container `ERROR`, Buffer post error → read the raw error body in EventLog.
   - Our bug: wrong state transition, timezone, double run.
3. **Isolate with a minimal call.** Reproduce the single API call with `httpx` in a scratch script or `curl`, using the owner's real credentials **only with their permission** and never posting publicly (use a private/test account or `DRY_RUN`).
4. **Fix with a test first** (see the testing skill), then fix, then verify the failing target can be retried from the UI.
5. **Update knowledge.** If the cause was an undocumented API behavior, add it to `platform-apis/SKILL.md` and the error mapping in `copy-id/SKILL.md`.

## Rules

- Don't "fix" by adding blanket retries or broader `except` blocks.
- Don't delete or rewrite DB rows by hand without telling the owner; prefer a migration or a service function.
- Report to the owner in Indonesian: what happened, root cause, what changed, whether they must do anything.
