import { formatDuration, formatWIB, fromWibInput, toWibInput } from './format'

test('formatWIB shows Jakarta time with a period separator', () => {
  expect(formatWIB('2026-11-24T12:00:00Z')).toBe('Selasa, 24 Nov · 19.00 WIB')
  expect(formatWIB('2026-11-24T17:30:00Z')).toBe('Rabu, 25 Nov · 00.30 WIB')
})

test('WIB input round-trips through UTC', () => {
  const d = new Date('2026-11-24T12:05:00Z')
  expect(toWibInput(d)).toBe('2026-11-24T19:05')
  expect(fromWibInput('2026-11-24T19:05')).toBe('2026-11-24T12:05:00.000Z')
})

test('formatDuration', () => {
  expect(formatDuration(42.4)).toBe('0:42')
  expect(formatDuration(725)).toBe('12:05')
})
