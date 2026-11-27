import { useMutation, useQueryClient } from '@tanstack/react-query'
import { LogOut, Plus, Settings } from 'lucide-react'
import { useCallback, useState } from 'react'

import { PlatformDot } from '@/components/PlatformDot'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { AccountsPage } from '@/features/accounts/AccountsPage'
import { AttentionPage } from '@/features/attention/AttentionPage'
import { useAttention } from '@/features/attention/useAttention'
import { CalendarPage } from '@/features/calendar/CalendarPage'
import { ComposerPanel } from '@/features/composer/ComposerPanel'
import { HealthPill } from '@/features/health/HealthPill'
import { useHealth } from '@/features/health/useHealth'
import { QueuePage } from '@/features/queue/QueuePage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { api, type Me } from '@/lib/api'
import { cn } from '@/lib/utils'

import { Count, TabBar } from './Navigation'
import { ICONS, PAGES, pageHref, usePage, type Page } from './route'
import { useShortcuts } from './shortcuts'

export function AppShell({ me }: { me: Me }) {
  const queryClient = useQueryClient()
  const page = usePage()
  const [composerOpen, setComposerOpen] = useState(false)
  const attention = useAttention()
  const accounts = attention.accounts
  const logout = useMutation({
    mutationFn: () => api<undefined>('/auth/logout', { method: 'POST' }),
    onSuccess: () => queryClient.clear(),
  })
  const openComposer = useCallback(() => setComposerOpen(true), [])
  const health = useHealth()
  const meters = new Map(health.data?.accounts.map((a) => [a.id, a]))

  useShortcuts(openComposer)

  const pages = Object.keys(PAGES) as Page[]

  return (
    <div className="flex min-h-svh flex-col">
      {me.dry_run && (
        <p
          role="status"
          className="border-status-waiting/30 bg-status-waiting/10 text-status-waiting border-b px-4 py-1.5 text-[13px]"
        >
          Mode uji aktif: nggak ada yang beneran diposting.
        </p>
      )}
      <div className="flex flex-1">
        <aside className="bg-sidebar hidden w-60 shrink-0 flex-col border-r lg:flex">
          <div className="px-4 py-4 font-medium">Schedler</div>
          <div className="px-3">
            <Button size="lg" className="w-full justify-start" onClick={openComposer}>
              <Plus aria-hidden /> Buat post
              <kbd className="ml-auto text-[11px] opacity-70">N</kbd>
            </Button>
          </div>
          <nav aria-label="Menu utama" className="mt-3 space-y-0.5 px-3">
            {pages.map((p) => {
              const Icon = ICONS[p]
              return (
                <a
                  key={p}
                  href={pageHref(p)}
                  aria-current={page === p ? 'page' : undefined}
                  className={cn(
                    'hover:bg-accent flex h-9 items-center gap-2 rounded-md px-2.5',
                    page === p && 'bg-accent font-medium',
                  )}
                >
                  <Icon aria-hidden className="size-4" /> {PAGES[p]}
                  {p === 'perhatian' && <Count n={attention.count} className="ml-auto" />}
                </a>
              )
            })}
          </nav>
          <div className="mt-6 border-t px-4 pt-4">
            <p className="text-muted-foreground mb-2 text-[11px] tracking-wide uppercase">Akun</p>
            {accounts.isPending ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-20" />
              </div>
            ) : (
              <ul className="space-y-1">
                {accounts.data?.map((a) => {
                  const m = meters.get(a.id)
                  return (
                    <li key={a.id} className="flex h-7 items-center gap-2">
                      <PlatformDot platform={a.platform} /> {a.label}
                      <span
                        className={cn(
                          'text-muted-foreground ml-auto text-[12px] tabular-nums',
                          m && m.connected && m.used >= m.limit * 0.8 && 'text-status-waiting',
                        )}
                        title={
                          m?.connected
                            ? a.route === 'ig_direct'
                              ? 'Post 24 jam terakhir / kuota IG'
                              : 'Post di antrian Buffer / batas'
                            : undefined
                        }
                      >
                        {!a.connected ? 'belum terhubung' : m ? `${m.used}/${m.limit}` : ''}
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}
            {accounts.isError && (
              <p className="text-destructive text-[13px]">{accounts.error.message}</p>
            )}
          </div>
          <div className="mt-auto p-3">
            <Button
              variant="ghost"
              size="lg"
              className="text-muted-foreground w-full justify-start"
              onClick={() => logout.mutate()}
            >
              <LogOut aria-hidden /> Keluar
            </Button>
          </div>
        </aside>

        <div className="min-w-0 flex-1 pb-16 lg:pb-0">
          <header className="flex h-14 items-center justify-between gap-3 border-b px-4 lg:px-6">
            <h1 className="text-xl font-medium">{PAGES[page]}</h1>
            <div className="flex items-center gap-1">
              <HealthPill />
              <Button asChild variant="ghost" size="icon-lg" className="size-11 lg:hidden">
                <a href={pageHref('pengaturan')} aria-label="Pengaturan">
                  <Settings aria-hidden />
                </a>
              </Button>
            </div>
          </header>
          <main className="p-4 lg:p-6">
            {page === 'kalender' && <CalendarPage />}
            {page === 'antrian' && <QueuePage onCreate={openComposer} />}
            {page === 'perhatian' && <AttentionPage />}
            {page === 'akun' && <AccountsPage />}
            {page === 'pengaturan' && <SettingsPage onLogout={() => logout.mutate()} />}
          </main>
        </div>
      </div>

      <TabBar page={page} attention={attention.count} onCreate={openComposer} />

      <ComposerPanel
        open={composerOpen}
        onOpenChange={setComposerOpen}
        accounts={accounts.data ?? []}
      />
    </div>
  )
}
