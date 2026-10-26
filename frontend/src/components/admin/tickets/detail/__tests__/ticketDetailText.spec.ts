import { afterEach, describe, expect, it, vi } from 'vitest'

import { registerProfileTimeZone } from '@/utils/date'
import { when, whenDate } from '../ticketDetailText'

// The panel's times follow the reader's own zone: their Profile timezone, or
// their computer's when the profile names none or still says UTC. Kolkata is half an hour off
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

describe('a reader whose Profile still says UTC', () => {
  // C-37, C-38, C-40: the client's admin account never chose a zone, so the
  // platform's rule read every time on this panel in UTC. The computer is
  // pinned to Kolkata, so the half hour can only come from the computer.
  it('reads the panel’s times in the computer’s zone, and names that zone', () => {
    vi.stubEnv('TZ', KOLKATA)
    registerProfileTimeZone(() => 'UTC')

    const printed = when('2026-08-04T03:00:00Z')
    expect(printed).toContain(':30')
    expect(printed).not.toContain('UTC')
  })

  it('puts Member since on the computer’s day', () => {
    // 20:00 UTC on 25 August is already the 26th in Kolkata.
    vi.stubEnv('TZ', KOLKATA)
    registerProfileTimeZone(() => 'UTC')

    expect(whenDate('2026-08-25T20:00:00Z')).toBe('26 Aug 2026')
  })
})
