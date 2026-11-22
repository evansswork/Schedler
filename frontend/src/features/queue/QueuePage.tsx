import { useQuery } from '@tanstack/react-query'
import { Play } from 'lucide-react'
import { useState } from 'react'

import { PlatformDot } from '@/components/PlatformDot'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, type Target, type TargetStatus } from '@/lib/api'
import { formatWIB } from '@/lib/format'
import { queryKeys } from '@/lib/queryKeys'

const TABS = {
  scheduled: {
    label: 'Terjadwal',
    statuses: ['queued_local', 'sent_to_buffer'],
    empty: 'Belum ada video terjadwal. Tempel link TikTok untuk mulai.',
  },
  processing: {
    label: 'Sedang diproses',
    statuses: ['waiting_media', 'publishing'],
    empty: 'Nggak ada video yang lagi diproses.',
  },
  failed: {
    label: 'Gagal',
    statuses: ['failed'],
    empty: 'Nggak ada yang gagal. Semua aman.',
  },
} satisfies Record<string, { label: string; statuses: TargetStatus[]; empty: string }>
type Tab = keyof typeof TABS

function fetchTargets(statuses: readonly TargetStatus[]) {
  return api<Target[]>(`/targets?${new URLSearchParams(statuses.map((s) => ['status', s]))}`)
}

function TargetRow({ t }: { t: Target }) {
  return (
    <li className="grid grid-cols-[48px_1fr_auto] gap-3 px-4 py-3 md:grid-cols-[48px_1fr_140px_220px_110px_44px] md:items-center">
      {t.media.public_url ? (
        <video
          src={t.media.public_url}
          preload="metadata"
          muted
          className="bg-muted h-16 w-12 rounded-md object-cover"
          aria-hidden
        />
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
          <StatusBadge status={t.status} />
        </p>
      </div>
      <span className="hidden items-center gap-1.5 md:inline-flex">
        <PlatformDot platform={t.account.platform} />
        {t.account.label}
      </span>
      <span className="hidden tabular-nums md:block">{formatWIB(t.scheduled_at)}</span>
      <span className="hidden md:block">
        <StatusBadge status={t.status} />
      </span>
      {t.media.public_url ? (
        <Button asChild variant="ghost" size="icon-lg">
          <a href={t.media.public_url} target="_blank" rel="noreferrer" aria-label="Putar video">
            <Play aria-hidden />
          </a>
        </Button>
      ) : (
        <span className="hidden md:block" />
      )}
    </li>
  )
}

export function QueuePage({ onCreate }: { onCreate: () => void }) {
  const [tab, setTab] = useState<Tab>('scheduled')
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

  return (
    <div className="space-y-4">
      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList className="h-9">
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
        <div className="text-muted-foreground hidden grid-cols-[48px_1fr_140px_220px_110px_44px] gap-3 border-b px-4 py-2 text-[11px] tracking-wide uppercase md:grid">
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
        ) : current.data.length === 0 ? (
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
            {current.data.map((t) => (
              <TargetRow key={t.id} t={t} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
