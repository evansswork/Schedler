import { useQuery } from '@tanstack/react-query'
import { ExternalLink, Film, Play, Search } from 'lucide-react'
import { useState } from 'react'

import { PlatformDot } from '@/components/PlatformDot'
import { StatusBadge } from '@/components/StatusBadge'
import { QUEUE_SEARCH_ID } from '@/app/shortcuts'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CancelButton, RetryButton } from '@/features/targets/actions'
import { CANCELLABLE } from '@/features/targets/status'
import { api, type Target, type TargetStatus } from '@/lib/api'
import { formatWIB } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'

type TabSpec = {
  label: string
  statuses: TargetStatus[]
  empty: string
  keep?: (t: Target) => boolean
}

const heldForBuffer = (t: Target) => t.status === 'queued_local' && t.account.route === 'buffer'

const TABS = {
  scheduled: {
    label: 'Terjadwal',
    statuses: ['queued_local', 'sent_to_buffer'],
    empty: 'Belum ada video terjadwal. Tempel link TikTok untuk mulai.',
    keep: (t) => !heldForBuffer(t),
  },
  waiting: {
    label: 'Menunggu slot',
    statuses: ['queued_local'],
    empty: 'Nggak ada yang menunggu slot Buffer.',
    keep: heldForBuffer,
  },
  processing: {
    label: 'Sedang diproses',
    statuses: ['waiting_media', 'publishing'],
    empty: 'Nggak ada video yang lagi diproses.',
  },
  published: {
    label: 'Tayang',
    statuses: ['published'],
    empty: 'Belum ada yang tayang.',
  },
  failed: {
    label: 'Gagal',
    statuses: ['failed'],
    empty: 'Nggak ada yang gagal. Semua aman.',
  },
  manual: {
    label: 'Manual',
    statuses: ['manual_required'],
    empty: 'Nggak ada yang perlu diupload manual.',
  },
} satisfies Record<string, TabSpec>
type Tab = keyof typeof TABS

function fetchTargets(statuses: readonly TargetStatus[]) {
  return api<Target[]>(`/targets?${new URLSearchParams(statuses.map((s) => ['status', s]))}`)
}

function TargetRow({ t }: { t: Target }) {
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

export function QueuePage({ onCreate }: { onCreate: () => void }) {
  const [tab, setTab] = useState<Tab>('scheduled')
  const [search, setSearch] = useState('')
  // Poll only while something is still being processed.
  const processing = useQuery({
    queryKey: queryKeys.targets(TABS.processing.statuses),
    queryFn: () => fetchTargets(TABS.processing.statuses),
    refetchInterval: (q) => (q.state.data?.length ? 4000 : false),
  })
  const busy = Boolean(processing.data?.length)
  const current = useQuery({
    queryKey: queryKeys.targets(TABS[tab].statuses),
    queryFn: () => fetchTargets(TABS[tab].statuses),
    refetchInterval: busy ? 4000 : false,
  })

  const spec: TabSpec = TABS[tab]
  const needle = search.trim().toLowerCase()
  const kept = (current.data ?? [])
    .filter(spec.keep ?? (() => true))
    .filter(
      (t) =>
        !needle ||
        t.caption.toLowerCase().includes(needle) ||
        t.account.label.toLowerCase().includes(needle),
    )
  const rows = tab === 'published' ? kept.toReversed() : kept

  return (
    <div className="space-y-4">
      <label className="relative block max-w-sm">
        <span className="sr-only">Cari caption atau akun</span>
        <Search
          aria-hidden
          className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2"
        />
        <Input
          id={QUEUE_SEARCH_ID}
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Cari caption atau akun  ( / )"
          className="h-9 pl-8"
        />
      </label>
      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList className="h-9 max-w-full justify-start overflow-x-auto">
          {(Object.keys(TABS) as Tab[]).map((key) => (
            <TabsTrigger key={key} value={key} className="px-3">
              {TABS[key].label}
              {key === 'processing' && busy && (
                <span className="text-muted-foreground tabular-nums">
                  {processing.data?.length}
                </span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div className="bg-card rounded-xl border">
        <div className="text-muted-foreground hidden grid-cols-[48px_1fr_140px_220px_110px_120px] gap-3 border-b px-4 py-2 text-[11px] tracking-wide uppercase md:grid">
          <span />
          <span>Caption</span>
          <span>Akun</span>
          <span>Waktu</span>
          <span>Status</span>
          <span />
        </div>
        {current.isPending ? (
          <ul aria-busy className="divide-y">
            {[0, 1, 2].map((i) => (
              <li key={i} className="flex items-center gap-3 px-4 py-3">
                <Skeleton className="h-16 w-12 rounded-md" />
                <Skeleton className="h-4 flex-1" />
              </li>
            ))}
          </ul>
        ) : current.isError ? (
          <div className="flex items-center justify-between gap-3 px-4 py-6">
            <p className="text-destructive">{current.error.message}</p>
            <Button variant="outline" size="lg" onClick={() => void current.refetch()}>
              Coba lagi
            </Button>
          </div>
        ) : rows.length === 0 && needle ? (
          <p className="text-muted-foreground px-4 py-6">
            Nggak ada post yang cocok dengan "{search.trim()}".
          </p>
        ) : rows.length === 0 ? (
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-6">
            <p className="text-muted-foreground">{TABS[tab].empty}</p>
            {tab === 'scheduled' && (
              <Button variant="outline" size="lg" onClick={onCreate}>
                Buat post
              </Button>
            )}
          </div>
        ) : (
          <ul className="divide-y">
            {rows.map((t) => (
              <TargetRow key={t.id} t={t} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
