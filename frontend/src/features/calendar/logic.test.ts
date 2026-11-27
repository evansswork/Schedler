import { describe, expect, it } from 'vitest'

import type { Target } from '@/lib/api'

import { toChips, wallToUtcIso } from './logic'

function target(over: Partial<Target> & { platform?: 'ig' | 'youtube' }): Target {
  const { platform = 'ig', ...rest } = over
  return {
    id: 't1',
    post_id: 'p1',
    status: 'queued_local',
    scheduled_at: '2026-11-24T12:30:00Z',
    caption: 'Halo',
    title: null,
    yt_kind: null,
    published_url: null,
    last_error_human: null,
    account: { label: platform === 'ig' ? 'IG #1' : 'YT #1', platform } as Target['account'],
    media: { orientation: 'vertical' } as Target['media'],
    ...rest,
  }
}

describe('toChips', () => {
  it('groups the accounts of one post at one time into one chip in WIB', () => {
    const chips = toChips([
      target({ id: 'a' }),
      target({ id: 'b', platform: 'youtube' }),
      target({ id: 'c', scheduled_at: '2026-11-24T13:30:00Z' }),
    ])
    expect(chips).toHaveLength(2)
    expect(chips[0]).toMatchObject({
      start: '2026-11-24T19:30',
      ids: ['a', 'b'],
      platforms: ['ig', 'youtube'],
      labels: ['IG #1', 'YT #1'],
      movable: true,
    })
  })

  it('shows the most urgent status and locks chips that are already moving', () => {
    const [chip] = toChips([
      target({ id: 'a', status: 'published' }),
      target({ id: 'b', status: 'failed', platform: 'youtube' }),
    ])
    expect(chip.status).toBe('failed')
    expect(chip.movable).toBe(false)
  })

  it('leaves cancelled posts out', () => {
    expect(toChips([target({ status: 'cancelled' })])).toEqual([])
  })
})

describe('wallToUtcIso', () => {
  it('turns a WIB wall time on the UTC calendar into real UTC', () => {
    expect(wallToUtcIso(new Date('2026-11-24T20:30:00Z'))).toBe('2026-11-24T13:30:00.000Z')
  })
})
