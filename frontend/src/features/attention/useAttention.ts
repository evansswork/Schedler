import { useQuery } from '@tanstack/react-query'

import { api, type Account, type Target } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

const DAY = 86_400_000
export const TOKEN_WARN_DAYS = 15

export type TokenIssue = { account: Account; daysLeft: number }

/** Connected IG accounts whose login expires within 15 days (or already has). */
export function tokenIssues(accounts: Account[], now: Date): TokenIssue[] {
  return accounts.flatMap((account) => {
    if (account.route !== 'ig_direct' || !account.connected || !account.token_expires_at) return []
    const daysLeft = Math.ceil((new Date(account.token_expires_at).getTime() - now.getTime()) / DAY)
    return daysLeft <= TOKEN_WARN_DAYS ? [{ account, daysLeft }] : []
  })
}

export function useAttention() {
  const failed = useQuery({
    queryKey: queryKeys.targets(['failed']),
    queryFn: () => api<Target[]>('/targets?status=failed'),
    refetchInterval: 60_000, // failures arrive from the publish job, not from this tab
  })
  const manual = useQuery({
    queryKey: queryKeys.targets(['manual_required']),
    queryFn: () => api<Target[]>('/targets?status=manual_required'),
    refetchInterval: 60_000,
  })
  const accounts = useQuery({
    queryKey: queryKeys.accounts,
    queryFn: () => api<Account[]>('/accounts'),
  })
  const tokens = tokenIssues(accounts.data ?? [], new Date())
  return {
    failed,
    manual,
    accounts,
    tokens,
    count: (failed.data?.length ?? 0) + (manual.data?.length ?? 0) + tokens.length,
  }
}
