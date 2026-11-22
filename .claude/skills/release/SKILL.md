---
name: release
description: Schedler's ship flow. Run checks, commit with Conventional Commits, merge to main, push and tag a semver release with a CHANGELOG entry. Use whenever a task or roadmap phase is done, or the owner says "push", "rilis", "production" or "deploy".
---

# Release flow

`main` is production. Every production-ready change ends up merged, pushed and tagged.

## 1. Pre-flight (all must pass; stop and report if any fails)

```bash
cd backend && ruff check . && ruff format --check . && pytest -q
cd ../frontend && npm run lint && npm run typecheck && npm run build
git status   # no .env, data/, media/, *.db staged
```

Also confirm:
- Acceptance criteria for the task or phase in `docs/ROADMAP.md` are met. Tick the boxes.
- Docs and `.env.example` are updated if config or behavior changed.

## 2. Commit on the task branch

- Branch name: `feat/…`, `fix/…`, `docs/…`, `chore/…`
- Message: Conventional Commits, e.g. `feat(buffer): refill queue up to 10 per channel`
- Small, logical commits. No "wip" commits on `main`.

## 3. Version + changelog

- SemVer: phase completion = minor bump (`v0.2.0`); fixes = patch (`v0.2.1`); `v1.0.0` = Phase 5 production.
- Add a section to `CHANGELOG.md`: `## vX.Y.Z - YYYY-MM-DD` with Added / Changed / Fixed.

## 4. Merge, push, tag

```bash
git checkout main && git pull --ff-only
git merge --no-ff <branch> -m "merge: <branch>"
git push origin main
git tag -a vX.Y.Z -m "vX.Y.Z: <summary>"
git push origin vX.Y.Z
git branch -d <branch>
```

- If `main` moved, rebase the branch onto `main` first and re-run pre-flight.
- Never `git push --force` to `main`.

## 5. Report to the owner (in Indonesian)

One short message: version, what changed (≤ 5 bullets), and whether anything needs their action (e.g. "isi BUFFER_API_KEY di .env").

## 6. Production deploy (Phase 5+ only, when the owner asks)

On the VPS: `git pull && docker compose -f deploy/docker-compose.yml up -d --build`, then check `/api/health` and the Telegram test message.
