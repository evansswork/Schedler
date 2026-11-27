import type { Orientation, Platform, Target, TargetStatus } from '@/lib/api'
import { fromWibInput, toWibInput } from '@/lib/format'

/** One calendar chip = one post at one time, across all of its accounts. */
export type Chip = {
  key: string
  start: string // WIB wall time "YYYY-MM-DDTHH:mm"; the calendar runs in UTC to show it as is
  ids: string[]
  platforms: Platform[]
  labels: string[]
  caption: string
  orientation: Orientation | null
  status: TargetStatus
  movable: boolean
}

const MOVABLE: readonly TargetStatus[] = ['waiting_media', 'queued_local']
// The chip shows its most urgent status.
const URGENCY: readonly TargetStatus[] = [
  'failed',
  'manual_required',
  'publishing',
  'waiting_media',
  'queued_local',
  'sent_to_buffer',
  'draft',
  'published',
]

export function toChips(targets: Target[]): Chip[] {
  const groups = new Map<string, Target[]>()
  for (const t of targets) {
    if (t.status === 'cancelled') continue
    const key = `${t.post_id}|${t.scheduled_at}`
    groups.set(key, [...(groups.get(key) ?? []), t])
  }
  return [...groups].map(([key, group]) => {
    const first = group[0]
    return {
      key,
      start: toWibInput(new Date(first.scheduled_at)),
      ids: group.map((t) => t.id),
      platforms: [...new Set(group.map((t) => t.account.platform))],
      labels: group.map((t) => t.account.label),
      caption: first.caption,
      orientation: first.media.orientation ?? null,
      status: URGENCY.find((s) => group.some((t) => t.status === s)) ?? first.status,
      movable: group.every((t) => MOVABLE.includes(t.status)),
    }
  })
}

/** Calendar dates are WIB wall time on a UTC calendar; this gives the real UTC ISO string. */
export function wallToUtcIso(d: Date): string {
  return fromWibInput(d.toISOString().slice(0, 16))
}
