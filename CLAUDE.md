# CLAUDE.md

This file is loaded automatically by Claude Code. Full rules live in AGENTS.md; this file adds Claude Code specifics.

@AGENTS.md

## Read before any task

1. `docs/PRD.md`: what we are building and why
2. `docs/ARCHITECTURE.md`: how it is built (data model, jobs, integrations)
3. `docs/DESIGN.md`: UI/UX spec. Read it before touching anything in `frontend/`.
4. `docs/ROADMAP.md`: current phase and acceptance criteria. Work only on the current phase unless told otherwise.
5. `docs/DECISIONS.md`: decisions already made. Do not reopen them without asking the owner.

## Skills in this repo (`.claude/skills/`)

| Skill | Load when |
|---|---|
| `no-ai-slop` | Always: before writing code, UI or docs, and before every commit |
| `backend` | Writing anything in `backend/` |
| `frontend` | Writing anything in `frontend/` |
| `ui-taste` | Creating or restyling any screen; run its checklist before UI work is done |
| `copy-id` | Writing any user-facing Indonesian text, error messages or notifications |
| `platform-apis` | Touching Instagram, Buffer, yt-dlp or Telegram code |
| `video-pipeline` | Touching download, probe, orientation or ffmpeg code |
| `testing` | Adding features, fixing bugs, or when tests fail |
| `debug` | A post fails, a job misbehaves, or the owner reports a problem |
| `release` | Work is done, or the owner says "push", "rilis", "production" or "deploy" |

## Working style for this repo

- The owner communicates in Indonesian (casual). Reply in Indonesian. Code, comments, commit messages and docs stay in English, except UI copy, which is Indonesian (see DESIGN.md).
- For each roadmap phase, start in plan mode: propose the plan, wait for approval, then implement.
- Never connect real social accounts, or post to real platforms, without the owner explicitly saying so in the current session. Use mocks and the `DRY_RUN=true` mode by default.
- When an external API behaves differently from what the docs here say, stop. Tell the owner, then update the relevant doc in the same commit as the fix.
- The owner is on macOS (Apple Silicon). Use Homebrew for system packages (`ffmpeg`, `python@3.12`, `node`).
