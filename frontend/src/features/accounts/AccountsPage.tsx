import { useQuery } from '@tanstack/react-query'

import { PlatformDot } from '@/components/PlatformDot'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { tokenIssues } from '@/features/attention/useAttention'
import { api, type Account } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

import { SlotEditor } from './SlotEditor'
import { TokenDialog } from './TokenDialog'

function connection(account: Account, now: Date): { text: string; tone: string } {
  if (!account.connected) return { text: 'Belum terhubung', tone: 'text-muted-foreground' }
  const issue = tokenIssues([account], now)[0]
  if (!issue) return { text: 'Terhubung', tone: 'text-status-published' }
  if (issue.daysLeft <= 0) return { text: 'Perlu sambungkan ulang', tone: 'text-status-failed' }
  return { text: `Login kedaluwarsa ${issue.daysLeft} hari lagi`, tone: 'text-status-waiting' }
}

function AccountCard({ account }: { account: Account }) {
  const status = connection(account, new Date())
  const ig = account.route === 'ig_direct'
  return (
    <li className="bg-card space-y-4 rounded-xl border p-4">
      <div className="flex flex-wrap items-center gap-3">
        <PlatformDot platform={account.platform} />
        <div className="min-w-0 flex-1">
          <p className="font-medium">
            {account.label}
            {account.handle && (
              <span className="text-muted-foreground font-normal"> @{account.handle}</span>
            )}
          </p>
          <p className="text-[13px]">
            <span className="text-muted-foreground">{ig ? 'Langsung' : 'via Buffer'} · </span>
            <span className={status.tone}>{status.text}</span>
          </p>
        </div>
        {ig && <TokenDialog account={account} reconnect={account.connected} />}
      </div>
      <SlotEditor account={account} />
    </li>
  )
}

export function AccountsPage() {
  const accounts = useQuery({
    queryKey: queryKeys.accounts,
    queryFn: () => api<Account[]>('/accounts'),
  })
  if (accounts.isPending)
    return (
      <div aria-busy className="grid gap-4 xl:grid-cols-2">
        <Skeleton className="h-44 rounded-xl" />
        <Skeleton className="h-44 rounded-xl" />
      </div>
    )
  if (accounts.isError)
    return (
      <div className="bg-card flex items-center justify-between gap-3 rounded-xl border px-4 py-6">
        <p className="text-destructive">{accounts.error.message}</p>
        <Button variant="outline" size="lg" onClick={() => void accounts.refetch()}>
          Coba lagi
        </Button>
      </div>
    )
  if (accounts.data.length === 0)
    return (
      <p className="bg-card text-muted-foreground rounded-xl border px-4 py-6">
        Belum ada akun. Jalankan <code>python -m app.cli seed-accounts</code> di folder backend.
      </p>
    )
  return (
    <ul className="grid gap-4 xl:grid-cols-2">
      {accounts.data.map((a) => (
        <AccountCard key={a.id} account={a} />
      ))}
    </ul>
  )
}
