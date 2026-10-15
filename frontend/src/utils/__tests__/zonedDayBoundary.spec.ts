import { afterEach, describe, expect, it } from 'vitest'

import { registerProfileTimeZone, zonedDayBoundary } from '@/utils/date'

const SYDNEY = 'Australia/Sydney'

afterEach(() => {
  registerProfileTimeZone(() => undefined)
})

describe('zonedDayBoundary', () => {
  it('gives the first and last millisecond of a Sydney day with its offset', () => {
    expect(zonedDayBoundary('2026-10-15', 'start', SYDNEY)).toBe('2026-10-15T00:00:00.000+11:00')
    expect(zonedDayBoundary('2026-10-15', 'end', SYDNEY)).toBe('2026-10-15T23:59:59.999+11:00')
  })

  it('uses each day its own offset either side of the 4 October daylight-saving change', () => {
    // Before the change Sydney is +10:00 (AEST), after it +11:00 (AEDT).
    expect(zonedDayBoundary('2026-10-01', 'start', SYDNEY)).toBe('2026-10-01T00:00:00.000+10:00')
    expect(zonedDayBoundary('2026-10-15', 'end', SYDNEY)).toBe('2026-10-15T23:59:59.999+11:00')
    // On the day itself the clocks go forward at 2am: the day starts on
    // +10:00 and ends on +11:00.
    expect(zonedDayBoundary('2026-10-04', 'start', SYDNEY)).toBe('2026-10-04T00:00:00.000+10:00')
    expect(zonedDayBoundary('2026-10-04', 'end', SYDNEY)).toBe('2026-10-04T23:59:59.999+11:00')
  })

  it('names the right instants in UTC', () => {
    const start = zonedDayBoundary('2026-10-01', 'start', SYDNEY)!
    const end = zonedDayBoundary('2026-10-15', 'end', SYDNEY)!
    expect(new Date(start).toISOString()).toBe('2026-09-30T14:00:00.000Z')
    expect(new Date(end).toISOString()).toBe('2026-10-15T12:59:59.999Z')
  })

  it('handles zones behind UTC, half-hour offsets and UTC itself', () => {
    expect(zonedDayBoundary('2026-10-15', 'start', 'America/New_York')).toBe('2026-10-15T00:00:00.000-04:00')
    expect(zonedDayBoundary('2026-10-15', 'start', 'Asia/Kolkata')).toBe('2026-10-15T00:00:00.000+05:30')
    expect(zonedDayBoundary('2026-10-15', 'end', 'UTC')).toBe('2026-10-15T23:59:59.999+00:00')
  })

  it('uses the admin’s Profile timezone when none is passed', () => {
    registerProfileTimeZone(() => SYDNEY)
    expect(zonedDayBoundary('2026-10-15', 'start')).toBe('2026-10-15T00:00:00.000+11:00')
  })

  it('reads every year as written, not 0-99 as 1900-1999', () => {
    // Year 0 is a leap year, 1900 isn't: read as 1900, 29 February would be refused.
    expect(zonedDayBoundary('0000-02-29', 'start', 'UTC')).toBe('0000-02-29T00:00:00.000+00:00')
    // Sydney had no daylight saving in 1950.
    expect(zonedDayBoundary('1950-01-15', 'start', SYDNEY)).toBe('1950-01-15T00:00:00.000+10:00')
  })

  it('refuses anything that is not a real calendar day', () => {
    expect(zonedDayBoundary('', 'start', SYDNEY)).toBeNull()
    expect(zonedDayBoundary('15/10/2026', 'start', SYDNEY)).toBeNull()
    expect(zonedDayBoundary('2026-02-31', 'end', SYDNEY)).toBeNull()
  })
})
