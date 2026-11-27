import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { components } from '@/lib/api-types'
import { queryKeys } from '@/lib/queryKeys'

export type Health = components['schemas']['HealthSummary']

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => api<Health>('/health/summary'),
    refetchInterval: 60_000,
  })
}
