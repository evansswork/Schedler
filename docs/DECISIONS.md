# Decisions (ADR log)

Short records of decisions already made with the owner. Do not reopen them without asking.

## ADR-001: Rp0 hybrid routing (2026-11-22)
**Decision:** IG publishes directly via Instagram API (no App Review needed for owned accounts). YouTube ×2 and TikTok ×1 go through the Buffer free plan (3 channels).
**Why:** The owner requires Rp0 posting APIs. The direct YouTube and TikTok APIs lock unaudited uploads to private; Buffer already has approved integrations.
**Rejected:** Upload-Post paid ($16 to $24/mo), Buffer paid, Postiz/Mixpost self-host (still needs platform audits), browser bots (ToS risk), multiple free Buffer accounts (plan circumvention).

## ADR-002: Self-hosted single process + SQLite (2026-11-22)
**Decision:** FastAPI + APScheduler in one process; SQLite in WAL mode via SQLModel.
**Why:** Single user, ~25 posts/day; simplest to run and back up. SQLModel keeps a path to PostgreSQL if this ever becomes multi-user.

## ADR-003: React SPA instead of server-rendered HTMX (2026-11-22)
**Decision:** React + Vite + TS + Tailwind + shadcn/ui + FullCalendar.
**Why:** The owner wants Publer-level UX (drag-and-drop calendar, side composer, live previews), which is impractical with HTMX.

## ADR-004: Local Mac first, VPS later (2026-11-22)
**Decision:** Build and test on macOS in VS Code with Claude Code; move to a VPS for production (Phase 5).
**Why:** Faster iteration; the VPS is needed only for 24/7 IG publishing and Buffer refills.

## ADR-005: Free subdomain (2026-11-22)
**Decision:** DuckDNS (or Dynu) subdomain + Caddy auto-HTTPS. Buy a `.my.id` domain only if TikTok/Buffer requires domain verification.

## ADR-006: Instagram account type = Creator (2026-11-22)
**Decision:** Convert both IG accounts to Creator (not Business).
**Why:** API publishing requires a Professional account; Business accounts have a restricted music library, which risks muted audio on TikTok-sourced videos. TikTok stays a personal, public account; YouTube channels need phone verification only.

## ADR-007: Git flow (2026-11-22)
**Decision:** `main` = production. Branch per task, Conventional Commits, and every production-ready change is merged, pushed and tagged.
