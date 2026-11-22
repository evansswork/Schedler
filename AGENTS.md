# AGENTS.md

Instructions for any AI coding agent (Claude Code, Codex, Cursor, etc.) working in this repo.

## Project in one paragraph

Schedler is a self-hosted, single-user video scheduler. The owner pastes a TikTok link (of their **own** video) or uploads an MP4, picks target accounts and a time, and Schedler does the rest: downloads the HD file, detects orientation, normalizes it, schedules it, publishes it to Instagram, YouTube and TikTok, and reports results over Telegram. The UX goal is "better than Publer" for this specific workflow. The cost goal is **Rp0 for all posting APIs**. The only paid items are a VPS and, optionally, a domain.

## Hard constraints (never violate)

1. **Rp0 posting.** Never add a paid API or service as a requirement. Paid options may exist only as optional adapters that are disabled by default.
2. **Official APIs only.** No browser automation, headless-browser bots or unofficial private APIs for *posting* to any platform. Downloading the owner's own TikTok videos with `yt-dlp` is allowed.
3. **Own content only.** The product is for mirroring the owner's own videos. Do not add features aimed at re-uploading other people's content (e.g. bulk-scraping someone else's profile).
4. **No plan-limit circumvention.** Do not build features to get around third-party plan limits, such as rotating multiple free Buffer accounts to dodge the 3-channel cap. Multiple Buffer API keys are allowed only as separate, legitimately owned organizations.
5. **Secrets never in git.** API keys, tokens and passwords live in `.env` (gitignored). Platform tokens stored in the DB are encrypted (Fernet, key from `.env`).
6. **Respect platform quotas.** Check the IG publishing limit before publishing. Never exceed 10 queued posts per Buffer channel on the free plan.

## Routing (current target setup)

| Account | Route | Who triggers publish at the scheduled time |
|---|---|---|
| IG #1, IG #2 (Creator accounts) | Instagram API with Instagram Login (direct) | Schedler worker |
| YouTube #1, YouTube #2 | Buffer GraphQL API (free plan) | Buffer |
| TikTok (personal, public) | Buffer GraphQL API (free plan, 3rd channel) | Buffer (verify in Phase 3) |

Publishing goes through **adapters** (`backend/app/publishers/`). A new route means a new adapter, never special-case code scattered around.

## Repo layout (target)

```
backend/            FastAPI app, worker jobs, adapters
  app/
    api/            HTTP routes (JSON) used by the frontend
    core/           config, security, db session, logging
    models/         SQLModel tables
    services/       business logic (scheduling, slots, routing)
    publishers/     ig_direct.py, buffer.py, base.py (adapter interface)
    pipeline/       download.py (yt-dlp), probe.py, normalize.py (ffmpeg)
    storage/        base.py, r2.py, local_public.py
    jobs/           APScheduler job functions
    notify/         telegram.py
  tests/
frontend/           React + Vite + TypeScript + Tailwind + shadcn/ui
docs/               PRD, ARCHITECTURE, DESIGN, ROADMAP, DECISIONS
deploy/             docker-compose.yml, Caddyfile, Dockerfile
.claude/skills/     agent skills for this repo
```

## Commands (set up in Phase 1; keep this section accurate)

```bash
# backend
cd backend && python3.14 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head                     # apply migrations
python -m app.cli seed-accounts          # create the 5 target accounts (once)
uvicorn app.main:app --reload            # API + worker on :8000
pytest                                   # tests
ruff check . && ruff format --check .    # lint + format

# frontend
cd frontend && npm install
npm run dev                              # :5173, proxies /api and /m to :8000
npm run build && npm run lint && npm run typecheck && npm test
npm run gen:api                          # regenerate src/lib/api-types.ts (backend running)

# full stack via docker (Phase 5)
docker compose -f deploy/docker-compose.yml up --build
```

## Code standards

- **Python 3.14**, type hints everywhere, `ruff` for lint and format, `pytest` + `pytest-asyncio` + `respx` (HTTP mocking).
- **TypeScript strict**, ESLint + Prettier, React function components, TanStack Query for server state.
- All times are stored in **UTC** in the DB. Convert to `Asia/Jakarta` only at the UI and notification edges.
- External HTTP calls go through `httpx` with timeouts and retries (exponential backoff, max 3). No bare `requests` calls.
- Every external integration has a **fake** implementation used in tests and when `DRY_RUN=true`.
- Errors shown to the user are human-readable Indonesian sentences. The raw error goes to the event log.
- Keep functions small. Business logic lives in `services/`, not in route handlers or jobs.

## Testing rules

- Tests must never hit real Instagram, Buffer, TikTok, YouTube or Telegram. Mock with `respx` or use the fake adapters.
- Each adapter has contract tests built from recorded or sample payloads stored in `backend/tests/fixtures/`.
- Each scheduling rule (slot filling, Buffer refill, quota checks, retries) needs unit tests.
- A phase is not done until its acceptance criteria in `docs/ROADMAP.md` pass.

## Git workflow (owner requirement: every production-ready change is pushed)

- `main` = production. It must always be deployable.
- Work on a branch per task: `feat/<short-name>`, `fix/<short-name>`, `docs/<short-name>`, `chore/<short-name>`.
- Use Conventional Commits: `feat(publisher): add IG resumable upload`.
- When a task passes tests, lint and its acceptance criteria: merge to `main`, push, and tag a release (`vMAJOR.MINOR.PATCH`). Follow `.claude/skills/release/SKILL.md`.
- Never force-push `main`. Never commit `.env`, `data/` or `media/`.
- Update `CHANGELOG.md` with each release.

## Definition of done

- [ ] Acceptance criteria for the task or phase met
- [ ] Tests added or updated and passing; lint clean
- [ ] Docs updated if behavior, config or architecture changed
- [ ] `.env.example` updated if new config was added
- [ ] Committed on a branch, merged to `main`, pushed, tagged (release skill)
