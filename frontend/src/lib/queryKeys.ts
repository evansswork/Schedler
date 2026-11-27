import type { TargetStatus } from './api'

// Every target list starts with 'targets', so invalidating allTargets refreshes them all.
export const queryKeys = {
  me: ['me'] as const,
  accounts: ['accounts'] as const,
  media: (ids: string[]) => ['media', ids] as const,
  targets: (statuses: readonly TargetStatus[]) => ['targets', statuses] as const,
  targetsRange: (start: string, end: string) => ['targets', 'range', start, end] as const,
  allTargets: ['targets'] as const,
  health: ['health'] as const,
  bufferChannels: ['buffer-channels'] as const,
  ytCategories: ['yt-categories'] as const,
  slotsPreview: (accountIds: string[], count: number) =>
    ['slots-preview', accountIds, count] as const,
}
