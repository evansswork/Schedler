import { X } from 'lucide-react'

import { OrientationBadge } from '@/components/OrientationBadge'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import type { Media, Platform } from '@/lib/api'
import { formatDuration } from '@/lib/format'

import { CaptionTabs } from './CaptionTabs'
import type { Override, Row } from './logic'

type Props = {
  index: number
  media: Media | undefined
  row: Row
  platforms: Platform[]
  time: string | null // null: the time comes from the account slots
  onCaption: (value: string) => void
  onOverride: (platform: Platform, patch: Override) => void
  onTime: (value: string) => void
  onRemove: () => void
}

function StatusLine({ media }: { media: Media | undefined }) {
  if (!media || media.status === 'pending') return <span>Menunggu antrean unduh…</span>
  if (media.status === 'downloading')
    return (
      <span className="flex w-full items-center gap-2">
        <span className="tabular-nums">Mengunduh… {media.progress_pct}%</span>
        <Progress value={media.progress_pct} className="h-1 flex-1" aria-hidden />
      </span>
    )
  if (media.status === 'processing') return <span>Diproses…</span>
  if (media.status === 'failed') return <span className="text-destructive">{media.error}</span>
  return (
    <span className="flex items-center gap-2">
      <span className="text-status-published">Siap</span>
      {media.duration_s != null && (
        <span className="tabular-nums">{formatDuration(media.duration_s)}</span>
      )}
      {media.orientation && <OrientationBadge orientation={media.orientation} />}
    </span>
  )
}

export function VideoRow(props: Props) {
  const { index, media, row, platforms, time, onCaption, onOverride, onTime, onRemove } = props
  const n = index + 1
  return (
    <li className="flex gap-3 rounded-xl border p-3">
      {media?.public_url ? (
        <video
          src={media.public_url}
          preload="metadata"
          muted
          className="bg-muted h-24 w-14 shrink-0 rounded-md object-cover"
          aria-label={`Pratinjau video ${n}`}
        />
      ) : (
        <Skeleton className="h-24 w-14 shrink-0 rounded-md" />
      )}
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div
            className="text-muted-foreground min-h-6 flex-1 text-[13px]"
            aria-live="polite"
            aria-label={`Status video ${n}`}
          >
            <StatusLine media={media} />
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={onRemove}
            aria-label={`Hapus video ${n} dari daftar`}
          >
            <X aria-hidden />
          </Button>
        </div>
        <CaptionTabs
          n={n}
          row={row}
          platforms={platforms}
          videoUrl={media?.public_url ?? null}
          placeholder={
            media?.status === 'ready' ? 'Caption' : 'Caption (diisi otomatis dari TikTok)'
          }
          onCaption={onCaption}
          onOverride={onOverride}
        />
        {time !== null && (
          <label className="flex flex-col gap-1 text-[13px] sm:flex-row sm:items-center sm:gap-2">
            <span className="text-muted-foreground shrink-0">Waktu tayang (WIB)</span>
            <Input
              type="datetime-local"
              value={time}
              onChange={(e) => onTime(e.target.value)}
              className="h-9 tabular-nums"
            />
          </label>
        )}
      </div>
    </li>
  )
}
