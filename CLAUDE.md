# CLAUDE.md

This file is loaded automatically by Claude Code. Full rules live in AGENTS.md; this file adds Claude Code specifics.

@AGENTS.md

## Read before any task

1. `docs/PRD.md`: what we are building and why
2. `docs/ARCHITECTURE.md`: how it is built (data model, jobs, integrations)
3. `docs/DESIGN.md`: UI/UX spec. Read it before touching anything in `frontend/`.
4. `docs/ROADMAP.md`: current phase and acceptance criteria. Work only on the current phase unless told otherwise.
5. `docs/DECISIONS.md`: decisions already made. Do not reopen them without asking the owner.

## Skills in this repo

- `.claude/skills/platform-apis`: Instagram, Buffer, yt-dlp and Telegram integration rules and gotchas. Load it before writing any integration code.
- `.claude/skills/video-pipeline`: download, probe, orientation routing and ffmpeg normalization
- `.claude/skills/release`: the test, commit, push and tag flow. Load it whenever work is "done" or the owner says "push" or "production".

## Working style for this repo

- The owner communicates in Indonesian (casual). Reply in Indonesian. Code, comments, commit messages and docs stay in English, except UI copy, which is Indonesian (see DESIGN.md).
- For each roadmap phase, start in plan mode: propose the plan, wait for approval, then implement.
- Never connect real social accounts, or post to real platforms, without the owner explicitly saying so in the current session. Use mocks and the `DRY_RUN=true` mode by default.
- When an external API behaves differently from what the docs here say, stop. Tell the owner, then update the relevant doc in the same commit as the fix.
- The owner is on macOS (Apple Silicon). Use Homebrew for system packages (`ffmpeg`, `python@3.12`, `node`).
