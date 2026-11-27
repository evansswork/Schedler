import { ExternalLink, Film, Play } from 'lucide-react'

import { PlatformDot } from '@/components/PlatformDot'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { CancelButton, RetryButton } from '@/features/targets/actions'
import { CANCELLABLE } from '@/features/targets/status'
import type { Target } from '@/lib/api'
import { formatWIB } from '@/lib/format'

/** One post in Antrian: a table row on desktop, a card on phones. */
export function TargetRow({ t }: { t: Target }) {
  return (
    <li className="grid grid-cols-[48px_1fr_auto] gap-3 px-4 py-3 md:grid-cols-[48px_1fr_140px_220px_110px_120px] md:items-center">
      {t.media.public_url ? (
        <video
          src={t.media.public_url}
          preload="metadata"
          muted
          className="bg-muted h-16 w-12 rounded-md object-cover"
          aria-hidden
        />
      ) : t.media.status === 'deleted' ? (
        <span
          className="bg-muted text-muted-foreground flex h-16 w-12 items-center justify-center rounded-md"
          title="File videonya sudah dihapus otomatis"
        >
          <Film aria-hidden className="size-4" />
        </span>
      ) : (
        <Skeleton className="h-16 w-12 rounded-md" />
      )}
      <div className="min-w-0 space-y-1">
        <p className="truncate" title={t.caption}>
          {t.caption || <span className="text-muted-foreground">Tanpa caption</span>}
        </p>
        {t.last_error_human && <p className="text-destructive text-[13px]">{t.last_error_human}</p>}
        <p className="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] md:hidden">
          <span className="inline-flex items-center gap-1.5">
            <PlatformDot platform={t.account.platform} />
            {t.account.label}
          </span>
          <span className="tabular-nums">{formatWIB(t.scheduled_at)}</span>
          <StatusBadge status={t.status} route={t.account.route} />
        </p>
      </div>
      <span className="hidden items-center gap-1.5 md:inline-flex">
        <PlatformDot platform={t.account.platform} />
        {t.account.label}
      </span>
      <span className="hidden tabular-nums md:block">{formatWIB(t.scheduled_at)}</span>
      <span className="hidden md:block">
        <StatusBadge status={t.status} route={t.account.route} />
      </span>
      <div className="flex items-center justify-end gap-1">
        {t.status === 'failed' && <RetryButton target={t} compact />}
        {t.published_url ? (
          <Button asChild variant="ghost" size="icon-lg">
            <a href={t.published_url} target="_blank" rel="noreferrer" aria-label="Buka post">
              <ExternalLink aria-hidden />
            </a>
          </Button>
        ) : (
          t.media.public_url && (
            <Button asChild variant="ghost" size="icon-lg">
              <a
                href={t.media.public_url}
                target="_blank"
                rel="noreferrer"
                aria-label="Putar video"
              >
                <Play aria-hidden />
              </a>
            </Button>
          )
        )}
        {CANCELLABLE.includes(t.status) && <CancelButton target={t} />}
      </div>
    </li>
  )
}
