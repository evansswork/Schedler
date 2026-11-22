---
name: ui-taste
description: Visual quality bar for Schedler's frontend (layout, hierarchy, spacing, color, motion, states) so the UI feels like a polished product on par with or better than Publer, not a generic template. Load before creating or restyling any screen or component in frontend/, and run its checklist before calling UI work done.
---

# UI taste

DESIGN.md says *what* to build. This skill says *how good* it must look and feel.

## North star

A calm, dense, fast tool for someone who schedules 25 videos a day. Think Linear / Things / Publer's composer, not a marketing landing page. Every pixel either shows information or helps an action.

## Rules

**Hierarchy**
- One primary action per view (indigo button). Everything else is secondary/ghost.
- Max 3 text levels per card: title (14/500), body (14/400), meta (13/400 muted).
- Numbers that matter (quota, slots, counts) use `tabular-nums`.

**Density and spacing**
- 4 px grid only. Card padding 16, section gap 24, inline gap 8.
- Table rows 44 px; calendar chips 24 to 28 px tall. No oversized "hero" padding inside the app.
- Align everything to a few vertical lines; no ragged left edges.

**Color**
- Neutral UI (slate). Color is reserved for meaning: primary action, status, platform dots.
- Never fill large areas with platform brand colors. Dots, small badges and thin left borders only.
- No gradients, glows, glassmorphism or drop shadows heavier than `shadow-sm`. Borders > shadows.
- Both themes are designed, not inverted: check dark mode on every screen.

**Typography**
- Inter, two weights (400/500). No all-caps except tiny section labels (11 px, tracking-wide, muted).
- Sentence case for everything. Truncate with ellipsis + tooltip; never wrap chips.

**States (every component has all of them)**
- Loading: skeletons shaped like the real content (not spinners in the middle of the page).
- Empty: one sentence + one action ("Belum ada video terjadwal. Tempel link TikTok untuk mulai.").
- Error: inline, specific, with a fix action.
- Disabled: explain why on hover.
- Optimistic updates for drag-reschedule and cancel, with rollback toast on failure.

**Motion**
- 150 to 200 ms, ease-out, only for: panel slide, toast, chip drop, progress. Nothing bounces. Respect `prefers-reduced-motion`.

**Interaction**
- Keyboard: everything reachable; shortcuts from DESIGN.md §7; visible focus ring.
- Hit targets ≥ 36 px desktop, ≥ 44 px mobile.
- Destructive actions: confirm dialog naming the object ("Batalkan 3 post YT #1?").
- Never lose user input: the composer autosaves a draft locally.

## Done checklist (paste into the PR/commit description)

- [ ] Screenshot checked in light AND dark, at 1440 px and 390 px
- [ ] Loading, empty, error, disabled states exist and look intentional
- [ ] Only one primary button visible per view
- [ ] No hard-coded colors outside the Tailwind theme tokens
- [ ] Text never overflows or overlaps at 390 px
- [ ] Keyboard-only walk-through works (Tab, Enter, Esc, shortcuts)
- [ ] Copy follows the copy-id skill
- [ ] Nothing from the no-ai-slop skill's UI list is present
