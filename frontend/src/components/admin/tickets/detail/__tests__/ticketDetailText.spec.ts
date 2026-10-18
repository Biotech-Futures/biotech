import { afterEach, describe, expect, it, vi } from 'vitest'

import { registerProfileTimeZone } from '@/utils/date'
import { when, whenDate } from '../ticketDetailText'

// The panel's times follow the reader's set zone: their Profile timezone, or
// their computer's when the profile names none. Kolkata is half an hour off
// every whole-hour zone, so the computer's zone (UTC in CI, Sydney on a
// laptop here) cannot produce these by luck.
const KOLKATA = 'Asia/Kolkata'

afterEach(() => {
  vi.unstubAllEnvs()
  registerProfileTimeZone(() => undefined)
})

describe('when', () => {
  it('prints the reader’s Profile timezone, and names it', () => {
    registerProfileTimeZone(() => KOLKATA)

    const printed = when('2026-08-04T03:00:00Z')
    expect(printed).toBe(
      new Date('2026-08-04T03:00:00Z').toLocaleString('en-AU', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: KOLKATA,
        timeZoneName: 'short'
      })
    )
    expect(printed).toContain(':30')
  })
})

describe('whenDate', () => {
  it('puts Member since on the Profile timezone’s day', () => {
    // 20:00 UTC on 25 August is already the 26th in Kolkata (01:30), and
    // still the 25th on a computer in Sao Paulo (17:00). Pinned there, since
    // a computer in Sydney is on the 26th as well and would pass by luck.
    vi.stubEnv('TZ', 'America/Sao_Paulo')
    registerProfileTimeZone(() => KOLKATA)

    expect(whenDate('2026-08-25T20:00:00Z')).toBe('26 Aug 2026')
  })
})
