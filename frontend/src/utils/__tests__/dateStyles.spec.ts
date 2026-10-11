import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  formatDayMonth,
  formatDayMonthTime,
  formatEventCalendarDay,
  formatEventDay,
  formatExactTime,
  formatOrdinalDate,
  formatShortDate,
  formatShortDateTime,
  formatStatementTime,
  formatSydneySlot,
  getSetTimeZone,
  ordinal,
  registerProfileTimeZone,
} from '@/utils/date'

// Fri 9 Oct 2026, 4:12:01 pm in Sydney (AEDT, UTC+11).
const AT = '2026-10-09T05:12:01Z'
const SYDNEY = 'Australia/Sydney'

afterEach(() => {
  registerProfileTimeZone(() => undefined)
  vi.useRealTimers()
})

describe('the date styles', () => {
  it('formats each style in the given zone', () => {
    expect(formatShortDate(AT, SYDNEY)).toBe('09/10/26')
    expect(formatShortDateTime(AT, SYDNEY)).toBe('09/10/26 16:12')
    expect(formatExactTime(AT, SYDNEY)).toBe('09/10/26 16:12:01')
    expect(formatStatementTime(AT, SYDNEY)).toBe('09/10/2026 at 16:12')
    expect(formatEventDay(AT, SYDNEY)).toBe('Friday, 9th October 2026')
    expect(formatOrdinalDate(AT, SYDNEY)).toBe('9th October 2026')
  })

  it('leaves the year off this year and adds it for another year', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-12T00:00:00Z'))
    expect(formatDayMonth(AT, SYDNEY)).toBe('9 Oct')
    expect(formatDayMonthTime(AT, SYDNEY)).toBe('9 Oct, 4:12 pm')
    expect(formatDayMonthTime('2025-10-08T23:05:00Z', SYDNEY)).toBe('9 Oct 2025, 10:05 am')
  })

  it('shows midnight and midday as 12', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-12T00:00:00Z'))
    expect(formatDayMonthTime('2026-10-09T00:00:00Z', 'UTC')).toBe('9 Oct, 12:00 am')
    expect(formatDayMonthTime('2026-10-09T12:30:00Z', 'UTC')).toBe('9 Oct, 12:30 pm')
  })

  it('turns the day over in the zone, not in UTC', () => {
    expect(formatShortDateTime('2026-10-09T14:30:00Z', SYDNEY)).toBe('10/10/26 01:30')
    expect(formatShortDateTime('2026-10-09T14:30:00Z', 'UTC')).toBe('09/10/26 14:30')
  })

  it('formats a calendar day without shifting it', () => {
    expect(formatEventCalendarDay('2026-10-09')).toBe('Friday, 9th October 2026')
    expect(formatEventCalendarDay('')).toBe('')
  })

  it('returns an empty string for a missing or broken value', () => {
    expect(formatShortDate(null)).toBe('')
    expect(formatShortDateTime('not a date')).toBe('')
    expect(formatDayMonthTime(undefined)).toBe('')
  })

  it('writes a Sydney slot with its clock name', () => {
    expect(formatSydneySlot('9:30', '10:00', '2026-10-09')).toBe('09:30 - 10:00 AEDT')
    expect(formatSydneySlot('13:00:00', '13:30:00', '2026-06-09')).toBe('13:00 - 13:30 AEST')
    expect(formatSydneySlot('9:30', '10:00', null)).toBe('09:30 - 10:00')
  })

  it('writes ordinals', () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 31].map(ordinal)).toEqual([
      '1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd', '23rd', '31st',
    ])
  })
})

describe('the set time', () => {
  it('uses the Profile timezone', () => {
    registerProfileTimeZone(() => SYDNEY)
    expect(getSetTimeZone()).toBe(SYDNEY)
    expect(formatShortDateTime(AT)).toBe('09/10/26 16:12')
  })

  it("falls back to the computer's timezone when none is set or it's broken", () => {
    const computer = Intl.DateTimeFormat().resolvedOptions().timeZone
    registerProfileTimeZone(() => undefined)
    expect(getSetTimeZone()).toBe(computer)
    registerProfileTimeZone(() => 'Not/AZone')
    expect(getSetTimeZone()).toBe(computer)
    registerProfileTimeZone(() => {
      throw new Error('no store')
    })
    expect(getSetTimeZone()).toBe(computer)
  })
})
