import { afterEach, describe, expect, it, vi } from 'vitest'

import { registerProfileTimeZone } from '@/utils/date'
import { formatCalendarDate, relativeDays } from '@/utils/mentorFormat'

afterEach(() => {
  registerProfileTimeZone(() => undefined)
  vi.useRealTimers()
})

describe('relativeDays', () => {
  it('counts whole days, like the inactive highlight', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-09T22:00:00Z'))

    expect(relativeDays('2026-10-09T02:00:00Z')).toBe('Today')
    expect(relativeDays('2026-10-08T20:00:00Z')).toBe('1 day ago')
    expect(relativeDays('2026-09-27T21:00:00Z')).toBe('12 days ago')
  })

  it('says nothing for a broken date', () => {
    expect(relativeDays('not a date')).toBe('')
  })
})

describe('formatCalendarDate', () => {
  it('writes a calendar date without moving it a day', () => {
    registerProfileTimeZone(() => 'America/Los_Angeles')
    expect(formatCalendarDate('2026-10-09')).toBe('09/10/26')
  })

  it('passes anything else through', () => {
    expect(formatCalendarDate('')).toBe('')
    expect(formatCalendarDate(null)).toBe('')
    expect(formatCalendarDate('Oct 2026')).toBe('Oct 2026')
  })
})
