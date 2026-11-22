import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ListVideo, LogOut, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'

import { PlatformDot } from '@/components/PlatformDot'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ComposerPanel } from '@/features/composer/ComposerPanel'
import { QueuePage } from '@/features/queue/QueuePage'
import { api, type Account, type Me } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

function isTyping(el: EventTarget | null) {
  return (
    el instanceof HTMLElement &&
    (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName))
  )
}

export function AppShell({ me }: { me: Me }) {
  const queryClient = useQueryClient()
  const [composerOpen, setComposerOpen] = useState(false)
  const accounts = useQuery({
    queryKey: queryKeys.accounts,
    queryFn: () => api<Account[]>('/accounts'),
  })
  const logout = useMutation({
    mutationFn: () => api<undefined>('/auth/logout', { method: 'POST' }),
    onSuccess: () => queryClient.clear(),
  })

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.key.toLowerCase() === 'n' &&
        !e.metaKey &&
        !e.ctrlKey &&
        !e.altKey &&
        !isTyping(e.target)
      ) {
        e.preventDefault()
        setComposerOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

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
            <Button
              size="lg"
              className="w-full justify-start"
              onClick={() => setComposerOpen(true)}
            >
              <Plus aria-hidden /> Buat post
              <kbd className="ml-auto text-[11px] opacity-70">N</kbd>
            </Button>
          </div>
          <nav aria-label="Menu utama" className="mt-3 px-3">
            <a
              href="#antrian"
              aria-current="page"
              className="bg-accent flex h-9 items-center gap-2 rounded-md px-2.5"
            >
              <ListVideo aria-hidden className="size-4" /> Antrian
            </a>
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
                {accounts.data?.map((a) => (
                  <li key={a.id} className="flex h-7 items-center gap-2">
                    <PlatformDot platform={a.platform} /> {a.label}
                  </li>
                ))}
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

        <div className="min-w-0 flex-1">
          <header className="flex h-14 items-center justify-between gap-3 border-b px-4 lg:px-6">
            <h1 id="antrian" className="text-xl font-medium">
              Antrian
            </h1>
            <Button size="lg" className="h-11 lg:hidden" onClick={() => setComposerOpen(true)}>
              <Plus aria-hidden /> Buat post
            </Button>
          </header>
          <main className="p-4 lg:p-6">
            <QueuePage onCreate={() => setComposerOpen(true)} />
          </main>
        </div>
      </div>
      <ComposerPanel
        open={composerOpen}
        onOpenChange={setComposerOpen}
        accounts={accounts.data ?? []}
      />
    </div>
  )
}
