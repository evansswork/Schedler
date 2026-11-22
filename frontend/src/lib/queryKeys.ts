import type { TargetStatus } from './api'

export const queryKeys = {
  me: ['me'] as const,
  accounts: ['accounts'] as const,
  media: (ids: string[]) => ['media', ids] as const,
  targets: (statuses: readonly TargetStatus[]) => ['targets', statuses] as const,
  allTargets: ['targets'] as const,
}
