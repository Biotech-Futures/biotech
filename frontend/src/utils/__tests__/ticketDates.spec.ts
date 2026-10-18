import { afterEach, describe, expect, it, vi } from 'vitest'
import { registerProfileTimeZone } from '@/utils/date'
import { formatDateAU, formatDateTimeAU, formatLongDateTimeAU } from '@/utils/ticketDates'

/**
 * The stamp on every line of a ticket conversation.
 *
 * Client item C-06: a date on its own could not tell a student whether the
 * reply under their message came five minutes or eight hours later. The stamp
 * now carries the time as well, read in the reader's set zone: their Profile
 * timezone, or their computer's when the profile names none (the platform's
 * rule, utils/date.getSetTimeZone).
 *
 * The computer's zone is pinned per test through TZ rather than left to the
 * machine, so the expected strings can be written out in full. Node picks a change to TZ
 * up on the spot; the suite passes started under TZ=UTC, which is what CI runs
 * in, and that is the check that the pin is really doing the work.
 */

// What the backend sends: an instant in UTC. 05:37 UTC on 24 September is
// 3:37 pm in Sydney (AEST, daylight saving starts on 4 October).
const REPLY_AT = '2026-09-24T05:37:00Z'

afterEach(() => {
  vi.unstubAllEnvs()
  // As this file starts: no profile is signed in, so none names a zone.
  registerProfileTimeZone(() => undefined)
})

describe('formatLongDateTimeAU', () => {
  it('shows the date and the time of day, the way an Australian reads them', () => {
    vi.stubEnv('TZ', 'Australia/Sydney')

    expect(formatLongDateTimeAU(REPLY_AT)).toBe('24 September 2026, 3:37 pm')
  })

  it('reads the time in the reader’s own zone, not in UTC', () => {
    // The same instant for a student on exchange in Sao Paulo. A formatter
    // that pinned a zone would print one of these two strings for both.
    vi.stubEnv('TZ', 'America/Sao_Paulo')

    expect(formatLongDateTimeAU(REPLY_AT)).toBe('24 September 2026, 2:37 am')
  })

  it('moves the date with the zone, not only the hour', () => {
    // Late evening on the West Coast is already tomorrow in UTC. A date read
    // in one zone next to a time read in another would put 10:37 pm on the
    // wrong day.
    vi.stubEnv('TZ', 'America/Los_Angeles')

    expect(formatLongDateTimeAU(REPLY_AT)).toBe('23 September 2026, 10:37 pm')
  })

  it('takes a Date as well as the string the API sends', () => {
    vi.stubEnv('TZ', 'Australia/Sydney')

    expect(formatLongDateTimeAU(new Date(REPLY_AT))).toBe('24 September 2026, 3:37 pm')
  })

  it('says nothing rather than "Invalid Date" for a value it cannot read', () => {
    expect(formatLongDateTimeAU('not a date')).toBe('')
  })
})

/**
 * The ticket page's header pills since the second redesign round (October
 * 2026): "Updated 29 Sept 2026, 8:18 pm". The month is short there, and the
 * zone rule is the conversation's.
 */
describe('formatDateTimeAU', () => {
  it('shows the short date and the time of day', () => {
    vi.stubEnv('TZ', 'Australia/Sydney')

    expect(formatDateTimeAU(REPLY_AT)).toBe('24 Sept 2026, 3:37 pm')
  })

  it('moves the date with the reader’s zone, not only the hour', () => {
    vi.stubEnv('TZ', 'America/Los_Angeles')

    expect(formatDateTimeAU(REPLY_AT)).toBe('23 Sept 2026, 10:37 pm')
  })

  it('says nothing rather than "Invalid Date" for a value it cannot read', () => {
    expect(formatDateTimeAU('not a date')).toBe('')
  })
})

/**
 * The zone itself. A signed-in profile's timezone wins over the computer's,
 * the way every other page of the platform reads times since 12 October 2026;
 * the computer's is only the fallback for a profile that names none.
 */
describe('the zone the ticket pages read times in', () => {
  it('is the Profile timezone, not the computer’s', () => {
    vi.stubEnv('TZ', 'America/Sao_Paulo')
    registerProfileTimeZone(() => 'Asia/Kolkata')

    // 05:37 UTC is 11:07 am in Kolkata; the computer would say 2:37 am.
    expect(formatLongDateTimeAU(REPLY_AT)).toBe('24 September 2026, 11:07 am')
    expect(formatDateTimeAU(REPLY_AT)).toBe('24 Sept 2026, 11:07 am')
  })

  it('moves the date with the Profile timezone too', () => {
    // Still the 23rd on the computer in Los Angeles, already the 24th for a
    // profile set to Sydney.
    vi.stubEnv('TZ', 'America/Los_Angeles')
    registerProfileTimeZone(() => 'Australia/Sydney')

    expect(formatDateAU(REPLY_AT)).toBe('24 Sept 2026')
  })

  it('falls back to the computer’s zone for a profile that names none, or none that exists', () => {
    vi.stubEnv('TZ', 'America/Sao_Paulo')

    for (const zone of [undefined, null, '', 'Mars/Olympus_Mons']) {
      registerProfileTimeZone(() => zone)
      expect(formatLongDateTimeAU(REPLY_AT), String(zone)).toBe('24 September 2026, 2:37 am')
    }
  })
})

