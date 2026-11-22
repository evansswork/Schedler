---
name: copy-id
description: Indonesian UI copywriting guide for Schedler (tone, terminology glossary, error and empty-state patterns, Telegram messages). Load whenever writing or changing any user-facing text in the frontend, error mapping (last_error_human) or notifications.
---

# Indonesian UI copy

## Tone

Casual-sopan, like a helpful friend who knows tech: short, direct, no slang overload. Use "kamu", never "Anda". Contractions OK ("nggak", "udah") in helper text and toasts; buttons and labels stay standard ("Tidak", "Sudah" are not needed: prefer verbs).

## Glossary (use these words consistently)

| Concept | Use | Don't use |
|---|---|---|
| Schedule (verb) | Jadwalkan | Schedule, Jadwalin |
| Scheduled | Terjadwal | Queued, Dalam antrean |
| Published | Tayang | Posted, Terbit |
| Failed | Gagal | Error |
| Waiting for Buffer slot | Menunggu slot | Pending |
| Processing / downloading | Diproses / Mengunduh | Loading |
| Retry | Coba lagi | Retry, Ulangi |
| Cancel a post | Batalkan | Hapus (unless deleting) |
| Account | Akun | Channel (except "channel YouTube") |
| Time slot | Slot | Jam tayang (ok in helper text) |
| Needs attention | Perlu perhatian | Notifikasi, Alert |
| Reconnect | Sambungkan ulang | Re-auth, Login ulang |
| Test mode (DRY_RUN) | Mode uji | Dry run |

Platform names stay as brands: Instagram, YouTube, TikTok, Reels, Shorts, Buffer.

## Patterns

- **Buttons:** verb first, ≤ 2 words: "Jadwalkan", "Coba lagi", "Sambungkan ulang", "Simpan draft".
- **Errors:** `[Apa yang gagal] + [kenapa, kalau tahu] + [apa yang bisa dilakukan]`.
  - ✅ "Gagal mengunduh video. Videonya private atau sudah dihapus. Cek link atau upload MP4-nya."
  - ❌ "Terjadi kesalahan. Silakan coba lagi."
- **Empty states:** one sentence + action. "Belum ada video terjadwal. Tempel link TikTok untuk mulai."
- **Confirmations:** name the object and consequence. "Batalkan 3 post di YT #1? Post yang sudah dikirim ke Buffer juga ikut dihapus."
- **Times:** always show WIB: "Senin, 24 Nov · 19.00 WIB". Use a period for hours (19.00), per Indonesian convention.
- **Counts:** "10 video", "3 akun" (no plural suffix).

## Error mapping starter (for last_error_human)

| Raw cause | Human copy |
|---|---|
| IG quota exhausted | "Kuota posting IG hari ini habis. Dijadwalkan ulang otomatis besok." |
| IG token expired | "Login Instagram kedaluwarsa. Sambungkan ulang akunnya." |
| IG container ERROR | "Instagram menolak videonya (format/durasi). Cek file atau coba upload ulang." |
| Buffer 429 | "Buffer lagi membatasi permintaan. Dicoba lagi otomatis." |
| Buffer channel disconnected | "Akun ini terputus dari Buffer. Sambungkan ulang di Buffer." |
| Media URL unreachable | "Platform nggak bisa mengambil file videonya. Cek storage." |
| yt-dlp private/removed | "Videonya private atau sudah dihapus dari TikTok." |
| yt-dlp extractor broken | "Pengunduh TikTok lagi bermasalah. Update pengunduh di Pengaturan atau upload MP4." |
| Overdue after downtime | "Terlewat karena server mati. Jadwalkan ulang?" |
