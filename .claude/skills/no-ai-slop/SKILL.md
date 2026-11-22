---
name: no-ai-slop
description: Banned patterns that make code, UI and copy look AI-generated or fake-finished in Schedler. Load before writing any code, UI or docs, and re-check before every commit.
---

# No AI slop

If something below shows up, remove it before committing. "It works on the happy path" is not done.

## Code

- **Fake success.** Never return mocked data, `pass`, `return True` or a hard-coded response from real code paths to make something "work". Fakes live only in `FakePublisher`/test fixtures, behind `DRY_RUN`.
- **Swallowed errors.** No bare `except:` / `except Exception: pass` / `.catch(() => {})`. Handle, log to EventLog, or re-raise.
- **Speculative abstraction.** No base classes, factories, plugin systems or config options without two real users of them today. (The Publisher adapter interface is justified; most others aren't.)
- **Comment noise.** No comments that restate code (`# increment i`), no changelog-style comments, no "This function does X" on obvious functions. Comment *why*, not *what*.
- **Leftovers.** No `TODO` without an issue/ROADMAP reference, no commented-out code, no `print`/`console.log` debugging, no unused imports, files or dependencies.
- **Dependency bloat.** Don't add a library for something the stdlib or an existing dep does in < 20 lines. Every new dependency is justified in the commit message.
- **Invented APIs.** Never guess an endpoint, field or SDK method. Check the docs or the live schema; if you can't, stop and say so. Mark unverified things `TBD` in docs.
- **Over-defensive code.** No null checks for values the type system guarantees; no try/except around code that can't raise.
- **Giant files.** Split modules > ~400 lines; functions > ~50 lines need a reason.
- **Tests that test nothing.** No tests that only assert mocks were called, or that assert `True`. Test behavior and outcomes.

## UI

- No lorem ipsum, "John Doe", stock avatars, or fake metrics in shipped screens.
- No marketing hero, "Welcome to Schedler 🚀" banner, or feature tiles inside the app.
- No emoji as UI decoration (Telegram messages may use ✅ ❌ only).
- No purple-blue gradients, glowing cards, glass blur, or every-card-has-a-shadow looks.
- No generic icon-in-a-colored-circle repeated on every card.
- No "Coming soon" buttons; don't render features that don't work.
- No centered-everything layouts; app UIs are left-aligned and scannable.

## Copy (UI and docs)

- No filler: "seamlessly", "effortlessly", "powerful", "robust", "leverage", "elevate", "unlock", "dive in", "dengan mudah dan cepat".
- No exclamation overload; at most one "!" per success toast.
- No vague errors ("Terjadi kesalahan"). Say what failed and what to do.
- Docs: no repetition of the same point in three sections, no generic "Best practices" lists that aren't specific to this repo.

## Before-commit self-check

Run `git diff --staged` and scan for: `TODO`, `console.log`, `print(`, `except:`, `pass`, `lorem`, `Lorem`, `John`, `🚀`, `gradient`, `any` (TS). Justify or remove every hit.
