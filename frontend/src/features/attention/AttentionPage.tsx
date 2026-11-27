import { CircleCheck, KeyRound } from 'lucide-react'

import { PlatformDot } from '@/components/PlatformDot'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { pageHref } from '@/app/route'
import { CancelButton, RetryButton } from '@/features/targets/actions'
import { formatWIB } from '@/lib/format'

import { useAttention, type TokenIssue } from './useAttention'

function tokenText({ account, daysLeft }: TokenIssue) {
  if (daysLeft <= 0) return `Login ${account.label} kedaluwarsa. Sambungkan ulang akunnya.`
  return `Login ${account.label} kedaluwarsa ${daysLeft} hari lagi. Sambungkan ulang sebelum itu.`
}

export function AttentionPage() {
  const { failed, accounts, tokens, count } = useAttention()
  const failedTargets = failed.data ?? []

  if (failed.isPending || accounts.isPending)
    return (
      <div aria-busy className="space-y-3">
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-20 w-full rounded-xl" />
      </div>
    )
  const error = failed.error ?? accounts.error
  if (error)
    return (
      <div className="bg-card flex items-center justify-between gap-3 rounded-xl border px-4 py-6">
        <p className="text-destructive">{error.message}</p>
        <Button
          variant="outline"
          size="lg"
          onClick={() => void Promise.all([failed.refetch(), accounts.refetch()])}
        >
          Coba lagi
        </Button>
      </div>
    )
  if (count === 0)
    return (
      <div className="bg-card flex items-center gap-3 rounded-xl border px-4 py-6">
        <CircleCheck aria-hidden className="text-status-published size-5" />
        <p>Semua aman. Nggak ada yang perlu kamu urus.</p>
      </div>
    )

  return (
    <div className="space-y-6">
      {tokens.length > 0 && (
        <section aria-labelledby="att-tokens" className="space-y-2">
          <h2 id="att-tokens" className="text-muted-foreground text-[11px] tracking-wide uppercase">
            Login akun
          </h2>
          <ul className="bg-card divide-y rounded-xl border">
            {tokens.map((issue) => (
              <li key={issue.account.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <KeyRound aria-hidden className="text-status-waiting size-4 shrink-0" />
                <p className="min-w-0 flex-1 basis-56">{tokenText(issue)}</p>
                <Button asChild variant="outline" size="lg">
                  <a href={pageHref('akun')}>Sambungkan ulang</a>
                </Button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {failedTargets.length > 0 && (
        <section aria-labelledby="att-failed" className="space-y-2">
          <h2 id="att-failed" className="text-muted-foreground text-[11px] tracking-wide uppercase">
            Gagal tayang <span className="tabular-nums">({failedTargets.length})</span>
          </h2>
          <ul className="bg-card divide-y rounded-xl border">
            {failedTargets.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center gap-3 px-4 py-3 md:flex-nowrap">
                <div className="min-w-0 flex-1 basis-full space-y-1 md:basis-auto">
                  <p className="text-status-failed">{t.last_error_human ?? 'Gagal tayang.'}</p>
                  <p className="text-muted-foreground flex flex-wrap items-center gap-x-3 text-[13px]">
                    <span className="inline-flex items-center gap-1.5">
                      <PlatformDot platform={t.account.platform} />
                      {t.account.label}
                    </span>
                    <span className="tabular-nums">{formatWIB(t.scheduled_at)}</span>
                    <span className="max-w-full truncate" title={t.caption}>
                      {t.caption || 'Tanpa caption'}
                    </span>
                  </p>
                </div>
                <div className="ml-auto flex items-center gap-1">
                  <RetryButton target={t} />
                  <CancelButton target={t} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
