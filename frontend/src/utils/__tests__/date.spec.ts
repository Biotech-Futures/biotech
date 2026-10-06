import { afterEach, describe, expect, it, vi } from 'vitest'
import { formatLongDateTimeAU } from '@/utils/date'

/**
 * The stamp on every line of a ticket conversation.
 *
 * Client item C-06: a date on its own could not tell a student whether the
 * reply under their message came five minutes or eight hours later. The stamp
 * now carries the time as well, read in the zone the reader's browser is set
 * to.
 *
 * The zone is pinned per test through TZ rather than left to the machine, so
 * the expected strings can be written out in full. Node picks a change to TZ
 * up on the spot; the suite passes started under TZ=UTC, which is what CI runs
 * in, and that is the check that the pin is really doing the work.
 */

// What the backend sends: an instant in UTC. 05:37 UTC on 24 September is
// 3:37 pm in Sydney (AEST, daylight saving starts on 4 October).
const REPLY_AT = '2026-09-24T05:37:00Z'

afterEach(() => {
  vi.unstubAllEnvs()
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
