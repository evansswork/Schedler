# DESIGN.md: UI/UX spec

Reference: Publer's UX patterns (calendar-first, side composer, per-network customization, AutoSchedule slots). We copy the **patterns**, not Publer's branding, colors, logo or layout pixel-for-pixel. Schedler has its own visual identity.

## 1. Principles

1. **Paste and go.** The fastest path is: paste links → Enter → done. Every other field has a smart default.
2. **Calm by default, loud on failure.** Healthy state is quiet. Failures go to "Perlu perhatian" and to Telegram.
3. **Show the system's state.** Slot usage, quotas, token expiry and processing status are always visible; nothing silently waits.
4. **Phone-friendly.** Every core action works on a 390 px wide screen.
5. **Indonesian, plain words.** No jargon in UI copy ("Terjadwal", not "Queued").

## 2. Layout

- **Desktop (≥ 1024 px):** left sidebar (240 px) + main area + right composer panel (480 px, slides over the main area).
- **Tablet/phone:** bottom tab bar (Kalender, Antrian, +Buat, Perhatian, Akun). The composer opens as a full-screen sheet.
- **Top bar:** page title, view toggles, global "+ Buat post" button (keyboard `N`), health pill (green / amber / red) that opens the health popover.

### Sidebar

```
Schedler
────────────
+ Buat post
Kalender
Antrian
Perlu perhatian (badge count)
Akun & slot
Pengaturan
────────────
AKUN
● IG #1      4/50
● IG #2      2/50
● YT #1      7/10
● YT #2      3/10
● TikTok     5/10
```
Each account row shows a platform color dot plus a usage meter (IG = today's quota; Buffer = queued slots). Click to filter the calendar.

## 3. Screens

### 3.1 Kalender (home)

- Week view (default) and Month view; "Hari ini" button; prev/next.
- Each post is a **chip**: platform dot(s), time, first 30 characters of caption, orientation icon. A chip with several targets at the same time shows stacked dots.
- Drag a chip to reschedule (confirm dialog if it was already sent to Buffer; the change syncs automatically).
- Empty slot cells (from AutoSchedule slots) show a dashed outline with "+". Clicking opens the composer prefilled with that slot.
- Filters: account multi-select, status (Terjadwal / Tayang / Gagal).

### 3.2 Composer (side panel), the most important screen

Sections, top to bottom:

1. **Sumber**: segmented control `Link TikTok | Upload MP4`.
   - Link mode: a multi-line textarea, "Tempel satu atau banyak link (satu per baris)". Each valid link becomes a row with thumbnail, duration, orientation badge and status (Mengunduh 42% → Siap).
   - Upload mode: drag-and-drop zone, multiple files.
2. **Akun tujuan**: checkbox chips per account (remember the last selection). Incompatible accounts show a warning tooltip.
3. **Caption**: a default caption (prefilled from TikTok) + tabs per platform (`Semua | Instagram | YouTube | TikTok`) to override. The YouTube tab has **Judul** (max 100 characters, counter) + **Deskripsi**. Hashtag counter for IG (max 30).
4. **Jadwal**: segmented `Slot berikutnya (otomatis) | Pilih waktu`. For a batch: "10 video akan disebar ke slot kosong mulai Senin 11:00" with a preview list.
5. **Preview**: platform-styled previews (phone frame) for the selected tab: IG Reel, YT Shorts or YT video, TikTok.
6. **Footer**: `Simpan draft` (secondary) · `Jadwalkan` (primary, Cmd/Ctrl+Enter).

Validation: inline, never blocking typing. Blocking errors only on submit (e.g. "Pilih minimal satu akun").

### 3.3 Antrian

- Tabs: `Terjadwal`, `Menunggu slot Buffer`, `Sedang diproses`, `Tayang`, `Gagal`, `Draft`, `Manual`.
- Table (desktop) or cards (phone): thumbnail, caption, account, time (WIB), status badge, actions (Edit, Batalkan, Coba lagi, Buka post).
- Bulk select → reschedule / cancel.

### 3.4 Perlu perhatian

- A list of problems, newest first, grouped by type: Gagal tayang, Token hampir kedaluwarsa, Kuota hampir habis, Downloader error, Manual required.
- Each item: human-readable reason, suggested fix, primary action (`Coba lagi`, `Hubungkan ulang`, `Unduh file + salin caption` for manual).
- Empty state: a green check, "Semua aman. Nggak ada yang perlu kamu urus."

### 3.5 Akun & slot

- Account cards: avatar, handle, route badge (`Langsung` / `via Buffer`), status (Terhubung / Perlu login ulang), usage meter.
- Slot editor per account: weekday toggles + time chips (add/remove), timezone select (default Asia/Jakarta). A preview shows "Slot kosong minggu ini: 12".
- Connect flows: IG (paste token or OAuth), Buffer (paste API key → pick channels).

### 3.6 Pengaturan

Groups: Telegram (bot token, chat id, "Kirim tes"), Storage (R2 / Lokal, usage), Keamanan (ganti password), Sistem (DRY_RUN toggle shown loudly, yt-dlp version + "Update sekarang", Buffer API usage today).

## 4. Visual system

- **Type:** Inter (UI) at 14 px base, 13 px meta, 20/16 px headings. Two weights: 400 and 500.
- **Radius:** 8 px controls, 12 px cards, full-round chips.
- **Spacing:** 4 px grid; 16 px card padding; 24 px section gap.
- **Neutral palette:** slate-based (Tailwind `slate`), light and dark.
- **Accent:** indigo-600 (light) / indigo-400 (dark) for primary actions only.
- **Platform colors** (dots and badges only, never large fills): IG `#E1306C`, YouTube `#FF0033`, TikTok `#25F4EE` + `#FE2C55` dual dot. Always pair color with an icon or label (accessibility).
- **Status colors:** Terjadwal = indigo, Tayang = green, Menunggu = amber, Gagal = red, Draft = slate, Manual = violet.
- **Icons:** lucide-react.
- **Motion:** 150 to 200 ms ease-out for panels; respect `prefers-reduced-motion`.
- **Dark mode:** follows the system, plus a manual toggle; every token defined for both.

## 5. Components (shadcn/ui based)

Button, Input, Textarea, Tabs, Segmented (ToggleGroup), Checkbox chips, Badge (status), Card, Sheet (composer on mobile), Dialog (confirm), Tooltip, Toast (sonner), Progress, Calendar (FullCalendar wrapped with our tokens), DataTable (TanStack Table), Skeleton loaders.

## 6. UI copy (Indonesian, casual-polite)

| Situation | Copy |
|---|---|
| Primary CTA | "Jadwalkan" |
| Batch summary | "10 video siap dijadwalkan ke 5 akun" |
| Downloading | "Mengunduh… 42%" |
| Success toast | "Beres! 10 video terjadwal." |
| IG quota | "Kuota IG #1 hari ini hampir habis (48/50). Sisanya digeser ke besok." |
| Buffer full | "Antrian YT #1 penuh (10/10). Sisanya nunggu otomatis." |
| Token expiring | "Login IG #2 kedaluwarsa 5 hari lagi. Klik untuk sambungkan ulang." |
| Failure (generic) | "Gagal tayang di YT #2: {alasan}. Sudah dicoba 3x." |
| DRY_RUN banner | "Mode uji aktif: nggak ada yang beneran diposting." |

## 7. Improvements over Publer (must-haves)

1. Multi-link paste → auto-download → auto-spread to slots (replaces CSV bulk).
2. Caption auto-filled from the TikTok source.
3. Orientation auto-detection + per-platform compatibility warnings.
4. Live health meters (IG quota, Buffer slots, tokens, storage) in the sidebar.
5. "Perlu perhatian" inbox with human-readable reasons + one-click fixes.
6. Telegram status loop, so the dashboard is optional day to day.
7. Keyboard-first: `N` new post, `Cmd+Enter` schedule, `/` search, `G then C` calendar.

## 8. Accessibility

WCAG AA contrast, focus rings visible, all actions reachable by keyboard, color never the only signal, `aria-live` for upload and download progress.
