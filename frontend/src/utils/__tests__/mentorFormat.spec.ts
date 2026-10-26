import { afterEach, describe, expect, it, vi } from 'vitest'

import { registerProfileTimeZone } from '@/utils/date'
import { formatCalendarDate, mentorConcern, relativeDays } from '@/utils/mentorFormat'

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

describe('mentorConcern', () => {
  // Fixed clock: these are all day counts against "now".
  const freeze = () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-27T12:00:00Z'))
  }
  const daysAgo = (days: number) =>
    new Date(Date.UTC(2026, 9, 27, 12) - days * 86_400_000).toISOString()

  it('reports a disabled account as inactive, however recently they spoke', () => {
    freeze()
    expect(
      mentorConcern({ isActive: false, lastMessageAt: daysAgo(0), dateJoined: daysAgo(400) })
    ).toBe('inactive')
  })

  it('reports an enabled account that has gone quiet as idle, not inactive', () => {
    freeze()
    // The two are different facts: a working login is never "inactive".
    expect(
      mentorConcern(
        { isActive: true, lastMessageAt: daysAgo(56), dateJoined: daysAgo(86), currentAssignedCount: 1 },
        30
      )
    ).toBe('idle')
  })

  it('excuses a mentor who spoke inside the window', () => {
    freeze()
    expect(
      mentorConcern(
        { isActive: true, lastMessageAt: daysAgo(3), dateJoined: daysAgo(400), currentAssignedCount: 1 },
        30
      )
    ).toBeNull()
  })

  it('excuses a mentor who joined inside the window and has not posted', () => {
    freeze()
    // The grace the matcher gives, now read the same way here: they have a
    // group, they have simply not had the time to use it.
    expect(
      mentorConcern(
        { isActive: true, lastMessageAt: null, dateJoined: daysAgo(14), currentAssignedCount: 1 },
        30
      )
    ).toBeNull()
  })

  it('stops excusing them once the window passes', () => {
    freeze()
    expect(
      mentorConcern(
        { isActive: true, lastMessageAt: null, dateJoined: daysAgo(31), currentAssignedCount: 1 },
        30
      )
    ).toBe('idle')
  })

  it('excuses a mentor with no group however long they are quiet', () => {
    freeze()
    // Nowhere to post, so silence says nothing. Marking them idle would lock
    // them out of ever being given a group.
    expect(
      mentorConcern(
        { isActive: true, lastMessageAt: null, dateJoined: daysAgo(400), currentAssignedCount: 0 },
        30
      )
    ).toBeNull()
  })

  it('takes the stricter reading when the join date is unknown', () => {
    freeze()
    expect(mentorConcern({ isActive: true, lastMessageAt: null }, 30)).toBe('idle')
  })
})
