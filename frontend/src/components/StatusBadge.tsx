import type { TargetStatus } from '@/lib/api'
import { cn } from '@/lib/utils'

const statusMeta: Record<TargetStatus, { label: string; color: string }> = {
  draft: { label: 'Draft', color: 'text-status-draft' },
  waiting_media: { label: 'Diproses', color: 'text-status-waiting' },
  queued_local: { label: 'Terjadwal', color: 'text-status-scheduled' },
  sent_to_buffer: { label: 'Terjadwal', color: 'text-status-scheduled' },
  publishing: { label: 'Diproses', color: 'text-status-waiting' },
  published: { label: 'Tayang', color: 'text-status-published' },
  failed: { label: 'Gagal', color: 'text-status-failed' },
  cancelled: { label: 'Dibatalkan', color: 'text-status-draft' },
  manual_required: { label: 'Manual', color: 'text-status-manual' },
}

export function StatusBadge({ status }: { status: TargetStatus }) {
  const meta = statusMeta[status]
  return (
    <span
      className={cn(
        'inline-flex h-6 items-center gap-1.5 rounded-full border px-2 text-[13px] font-medium',
        meta.color,
      )}
    >
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {meta.label}
    </span>
  )
}
