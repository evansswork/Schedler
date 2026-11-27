import type { TargetStatus } from '@/lib/api'

/** Mirrors CANCELLABLE in backend/app/services/posts.py. */
export const CANCELLABLE: readonly TargetStatus[] = [
  'waiting_media',
  'queued_local',
  'sent_to_buffer',
  'failed',
  'manual_required',
]
