import type { Account, Media } from '@/lib/api'

import {
  accountWarnings,
  apiOverrides,
  captionFor,
  defaultTitle,
  hashtagCount,
  nextTimes,
  parseLinks,
  submitError,
  type ComposerValues,
} from './logic'

const now = new Date('2026-11-24T05:20:00Z') // 12.20 WIB

test('parseLinks keeps TikTok URLs, dedupes and flags the rest', () => {
  const text = `https://www.tiktok.com/@me/video/1
  https://vm.tiktok.com/ZS1/   https://www.tiktok.com/@me/video/1
  https://youtu.be/x
  tiktok.com/@me/video/2`
  expect(parseLinks(text)).toEqual({
    valid: ['https://www.tiktok.com/@me/video/1', 'https://vm.tiktok.com/ZS1/'],
    invalid: ['https://youtu.be/x', 'tiktok.com/@me/video/2'],
  })
})

test('nextTimes starts at the next full hour an hour out, then follows the last row', () => {
  expect(nextTimes(3, now)).toEqual(['2026-11-24T14:00', '2026-11-24T15:00', '2026-11-24T16:00'])
  expect(nextTimes(1, now, '2026-11-24T23:30')).toEqual(['2026-11-25T00:30'])
})

const ready = { id: 'm1', status: 'ready' } as Media
const failed = { id: 'm2', status: 'failed' } as Media
const row = (mediaId: string, time = '2026-11-24T14:00') => ({
  mediaId,
  caption: '',
  time,
  captionTouched: false,
})

test.each<[ComposerValues, string | null]>([
  [{ rows: [], accountIds: ['a'], mode: 'exact' }, 'Tambahkan minimal satu video.'],
  [{ rows: [row('m1')], accountIds: [], mode: 'exact' }, 'Pilih minimal satu akun.'],
  [
    { rows: [row('m2')], accountIds: ['a'], mode: 'exact' },
    'Ada video yang gagal diproses. Hapus dari daftar dulu.',
  ],
  [
    { rows: [row('m1', '')], accountIds: ['a'], mode: 'exact' },
    'Isi waktu tayang untuk setiap video.',
  ],
  [
    { rows: [row('m1', '2026-11-24T12:00')], accountIds: ['a'], mode: 'exact' },
    'Ada waktu tayang yang sudah lewat. Pilih waktu yang akan datang.',
  ],
  [{ rows: [row('m1')], accountIds: ['a'], mode: 'exact' }, null],
  [{ rows: [row('m1', '')], accountIds: ['a'], mode: 'slot' }, null],
])('submitError %#', (values, expected) => {
  const media = new Map([
    ['m1', ready],
    ['m2', failed],
  ])
  expect(submitError(values, media, now)).toBe(expected)
})

test('accountWarnings names the account and only covers selected ones', () => {
  const accounts = [
    { id: 'a', label: 'IG #1', platform: 'ig' },
    { id: 'b', label: 'IG #2', platform: 'ig' },
    { id: 'c', label: 'YT #1', platform: 'youtube' },
  ] as Account[]
  const media = [
    { warnings: { ig: ['Video horizontal akan tampil dengan bar hitam di Reels.'] } },
  ] as unknown as Media[]
  expect(accountWarnings(accounts, ['a', 'c'], media)).toEqual([
    'IG #1: Video horizontal akan tampil dengan bar hitam di Reels.',
  ])
})

describe('per-platform captions', () => {
  const base = { mediaId: 'm', caption: 'Halo dunia\nbaris dua', time: '', captionTouched: true }

  it('falls back to the shared caption and title from its first line', () => {
    expect(captionFor(base, 'ig')).toBe('Halo dunia\nbaris dua')
    expect(defaultTitle(base)).toBe('Halo dunia')
  })

  it('uses overrides and sends only non-empty ones', () => {
    const row = { ...base, overrides: { youtube: { title: ' Judul ', caption: '' }, ig: {} } }
    expect(captionFor(row, 'youtube')).toBe('Halo dunia\nbaris dua')
    expect(apiOverrides(row)).toEqual({ youtube: { title: 'Judul' } })
  })

  it('counts hashtags', () => {
    expect(hashtagCount('#a #b c#d #e_f')).toBe(3)
  })
})
