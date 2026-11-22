// Asia/Jakarta has been UTC+7 with no DST since 1964, so a fixed offset is exact.
const WIB_OFFSET = '+07:00'

const dateParts = new Intl.DateTimeFormat('id-ID', {
  timeZone: 'Asia/Jakarta',
  weekday: 'long',
  day: 'numeric',
  month: 'short',
})
const timeParts = new Intl.DateTimeFormat('id-ID', {
  timeZone: 'Asia/Jakarta',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/** "Senin, 24 Nov · 19.00 WIB" */
export function formatWIB(iso: string): string {
  const d = new Date(iso)
  return `${dateParts.format(d)} · ${timeParts.format(d).replace(':', '.')} WIB`
}

/** Value for <input type="datetime-local"> showing `d` in WIB: "2026-11-24T19:00". */
export function toWibInput(d: Date): string {
  const wib = new Date(d.getTime() + 7 * 3600_000)
  return wib.toISOString().slice(0, 16)
}

/** Parses a datetime-local value as WIB and returns a UTC ISO string. */
export function fromWibInput(value: string): string {
  return new Date(`${value}:00${WIB_OFFSET}`).toISOString()
}

/** "0:42", "12:05" */
export function formatDuration(seconds: number): string {
  const s = Math.round(seconds)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}
