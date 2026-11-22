import type { Account, Media, Platform } from '@/lib/api'
import { fromWibInput, toWibInput } from '@/lib/format'

export type Row = { mediaId: string; caption: string; time: string; captionTouched: boolean }
export type ComposerValues = { rows: Row[]; accountIds: string[] }

const HOUR = 3600_000
const TIKTOK_HOSTS = new Set([
  'tiktok.com',
  'www.tiktok.com',
  'm.tiktok.com',
  'vm.tiktok.com',
  'vt.tiktok.com',
])

/** Splits pasted text into links; returns the ones that aren't TikTok URLs separately. */
export function parseLinks(text: string): { valid: string[]; invalid: string[] } {
  const lines = [...new Set(text.split(/\s+/).map((l) => l.trim()))].filter(Boolean)
  const valid: string[] = []
  const invalid: string[] = []
  for (const line of lines) {
    let ok: boolean
    try {
      const url = new URL(line)
      ok = /^https?:$/.test(url.protocol) && TIKTOK_HOSTS.has(url.hostname)
    } catch {
      ok = false
    }
    ;(ok ? valid : invalid).push(line)
  }
  return { valid, invalid }
}

/** Next `count` default times: one hour apart, starting an hour after `after`
 * (the last row's time) or at the first full hour at least an hour from now. */
export function nextTimes(count: number, now: Date, after?: string): string[] {
  const start = after
    ? new Date(fromWibInput(after)).getTime() + HOUR
    : Math.ceil((now.getTime() + HOUR) / HOUR) * HOUR
  return Array.from({ length: count }, (_, i) => toWibInput(new Date(start + i * HOUR)))
}

/** Blocking problems shown on submit only (inline hints are rendered elsewhere). */
export function submitError(
  values: ComposerValues,
  media: Map<string, Media>,
  now: Date,
): string | null {
  if (values.rows.length === 0) return 'Tambahkan minimal satu video.'
  if (values.accountIds.length === 0) return 'Pilih minimal satu akun.'
  if (values.rows.some((r) => media.get(r.mediaId)?.status === 'failed'))
    return 'Ada video yang gagal diproses. Hapus dari daftar dulu.'
  if (values.rows.some((r) => !r.time)) return 'Isi waktu tayang untuk setiap video.'
  if (values.rows.some((r) => new Date(fromWibInput(r.time)) < now))
    return 'Ada waktu tayang yang sudah lewat. Pilih waktu yang akan datang.'
  return null
}

/** "IG #1: Video horizontal akan tampil…" for each selected account with a warning. */
export function accountWarnings(accounts: Account[], selected: string[], media: Media[]): string[] {
  const out = new Set<string>()
  for (const account of accounts.filter((a) => selected.includes(a.id))) {
    for (const m of media) {
      for (const w of m.warnings?.[account.platform as Platform] ?? []) {
        out.add(`${account.label}: ${w}`)
      }
    }
  }
  return [...out]
}
