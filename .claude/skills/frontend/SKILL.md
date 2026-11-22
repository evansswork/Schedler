---
name: frontend
description: Frontend conventions for Schedler (React + Vite + TypeScript strict + Tailwind + shadcn/ui + TanStack Query + FullCalendar). Folder structure, data fetching, forms, state, and component rules. Load before writing code in frontend/.
---

# Frontend conventions

Also load `ui-taste`, `copy-id` and `no-ai-slop` for any UI work.

## Stack

React 18+, Vite, TypeScript (`strict: true`, no `any`), Tailwind, shadcn/ui (copied components in `src/components/ui`), lucide-react icons, TanStack Query (server state), TanStack Table, react-hook-form + zod (forms), FullCalendar (calendar), sonner (toasts), date-fns + date-fns-tz (WIB display).

## Structure

```
frontend/src/
  app/            routes, layout, providers
  features/
    calendar/     CalendarView, PostChip, hooks
    composer/     ComposerPanel, SourceInput, AccountPicker, CaptionTabs, SchedulePicker, Preview
    queue/        QueueTable, filters
    attention/    AttentionInbox
    accounts/     AccountCard, SlotEditor
    settings/
  components/ui/  shadcn primitives (don't edit unless restyling the theme)
  components/     shared composites (StatusBadge, PlatformDot, UsageMeter, EmptyState)
  lib/            api client, query keys, formatters (formatWIB), zod schemas
  styles/         tailwind theme tokens
```

## Rules

- **API client:** one typed `api.ts` (fetch wrapper, credentials included, CSRF header, typed errors). Types come from the backend's OpenAPI (`openapi-typescript`), never hand-copied.
- **Server state only in TanStack Query.** Query keys in `lib/queryKeys.ts`. Mutations invalidate precise keys; drag-reschedule uses optimistic updates with rollback.
- **Local UI state** with `useState`/`useReducer`; no global store unless two distant features share state (then Zustand, justified in the commit).
- **Forms:** react-hook-form + zod; schema shared with the API types where possible.
- **Time:** the API sends UTC ISO strings; convert with `formatWIB()` at render. Never `new Date().toLocaleString()` ad hoc.
- **Polling:** media processing and queue status poll every 3 to 5 s only while something is in progress; otherwise stop.
- **Components:** function components, props typed, ≤ ~200 lines; split otherwise. No inline styles; Tailwind classes + `cn()`.
- **Theming:** colors via CSS variables in the Tailwind theme (light/dark). Platform and status colors are tokens (`--platform-ig`, `--status-failed`, ...).
- **Accessibility:** shadcn/Radix primitives for dialogs, menus, tabs; label every input; `aria-live` for progress.
- **No new UI library** (MUI, Chakra, Ant, etc.).

## Checks

`npm run lint && npm run typecheck && npm run build`, plus manual check per the ui-taste checklist.
