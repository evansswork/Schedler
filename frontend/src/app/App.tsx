import { useQuery } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { LoginPage } from '@/features/auth/LoginPage'
import { api, ApiError, setCsrfToken, type Me } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

import { AppShell } from './AppShell'

async function fetchMe() {
  const me = await api<Me>('/auth/me')
  setCsrfToken(me.csrf_token)
  return me
}

export function App() {
  const me = useQuery({ queryKey: queryKeys.me, queryFn: fetchMe, retry: false })

  if (me.isPending)
    return (
      <div className="flex min-h-svh">
        <Skeleton className="hidden w-60 rounded-none lg:block" />
        <div className="flex-1 space-y-4 p-6">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    )
  if (me.isError) {
    if (me.error instanceof ApiError && me.error.status === 401) return <LoginPage />
    return (
      <main className="flex min-h-svh items-center justify-center gap-3 p-4">
        <p className="text-destructive">{me.error.message}</p>
        <Button variant="outline" size="lg" onClick={() => void me.refetch()}>
          Coba lagi
        </Button>
      </main>
    )
  }
  return <AppShell me={me.data} />
}
