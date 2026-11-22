---
name: testing
description: How to test Schedler (pytest, respx, fakes, fixtures, time control, frontend tests) without touching real platforms. Load when adding features, fixing bugs, or when tests fail.
---

# Testing

## Principles

- No test touches the real network. `respx` blocks unmocked HTTP calls (configure `assert_all_mocked=True`).
- Test behavior, not implementation: given DB state + mocked API responses → assert resulting statuses, scheduled times, events, notifications.
- Every bug fix starts with a failing test that reproduces it.

## Backend

- `pytest`, `pytest-asyncio`, `respx`, `time-machine` (freeze/advance time for scheduling logic).
- Fixtures (`tests/conftest.py`): temp SQLite DB per test (migrated), settings override with `DRY_RUN=true`, factory helpers (`make_account`, `make_media`, `make_target`).
- Sample API payloads in `tests/fixtures/<platform>/*.json` (IG container statuses, Buffer createPost responses, errors). Use real-shaped payloads from docs or recordings with secrets stripped.
- Tiny generated videos for pipeline tests: `ffmpeg -f lavfi -i testsrc=size=1080x1920:rate=30:duration=2 -f lavfi -i sine=duration=2 -shortest v.mp4` (also 1920x1080, 1080x1080). Never commit real user videos.
- Must-have test suites:
  - orientation classify + YouTube short/video routing
  - slot filling and batch spreading across accounts/timezones
  - Buffer refill never exceeds 10 per channel, earliest first; budget guard
  - IG publish: quota exhausted → rescheduled; container ERROR → retry → failed after 3
  - idempotency: two concurrent job runs don't double-publish
  - startup catch-up (≤ 6 h publish, > 6 h fail + notify)
  - error mapping → Indonesian human messages

## Frontend

- Vitest + Testing Library for logic-heavy components (composer validation, batch preview, formatWIB). MSW for API mocking.
- No snapshot tests of whole pages.

## Commands

`cd backend && pytest -q` · `cd frontend && npm test`
