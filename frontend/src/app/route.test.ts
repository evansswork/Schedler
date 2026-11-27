import { describe, expect, it } from 'vitest'

import { pageHref, parsePage } from './route'

describe('parsePage', () => {
  it('reads known pages from the hash', () => {
    expect(parsePage('#/antrian')).toBe('antrian')
    expect(parsePage('#perhatian')).toBe('perhatian')
    expect(parsePage(pageHref('akun'))).toBe('akun')
  })

  it('falls back to the calendar', () => {
    expect(parsePage('')).toBe('kalender')
    expect(parsePage('#/toString')).toBe('kalender')
    expect(parsePage('#/nope')).toBe('kalender')
  })
})
