import { describe, expect, it } from 'vitest'

import { defaultSystemLogFilters, systemLogQuery } from '@/composables/admin/useAdminSystemLogs'

const SYDNEY = 'Australia/Sydney'

describe('systemLogQuery', () => {
  it('sends a date range across the 4 October daylight-saving change with each end on its own offset', () => {
    const query = systemLogQuery({ ...defaultSystemLogFilters(), fromDate: '2026-10-01', toDate: '2026-10-15' }, '', SYDNEY)

    // 1 October starts on AEST (+10:00); 15 October ends on AEDT (+11:00).
    expect(query.from).toBe('2026-10-01T00:00:00.000+10:00')
    expect(query.to).toBe('2026-10-15T23:59:59.999+11:00')
    expect(new Date(query.from!).toISOString()).toBe('2026-09-30T14:00:00.000Z')
    expect(new Date(query.to!).toISOString()).toBe('2026-10-15T12:59:59.999Z')
  })

  it('reads the picked days in the zone it is given', () => {
    const query = systemLogQuery({ ...defaultSystemLogFilters(), fromDate: '2026-10-15', toDate: '2026-10-15' }, '', 'UTC')

    expect(query.from).toBe('2026-10-15T00:00:00.000+00:00')
    expect(query.to).toBe('2026-10-15T23:59:59.999+00:00')
  })

  it('maps every filter to its API name, trimmed', () => {
    const query = systemLogQuery(
      {
        fromDate: '',
        toDate: '',
        level: 'WARNING',
        source: ' apps.services ',
        user: ' amy@example.com ',
        requestId: ' abc123 '
      },
      '  smtp refused ',
      SYDNEY
    )

    expect(query).toEqual({
      from: undefined,
      to: undefined,
      level: 'WARNING',
      source: 'apps.services',
      user: 'amy@example.com',
      q: 'smtp refused',
      request_id: 'abc123'
    })
  })

  it('leaves out every empty filter', () => {
    const query = systemLogQuery(defaultSystemLogFilters(), '   ', SYDNEY)

    expect(Object.values(query).every((value) => value === undefined)).toBe(true)
  })
})
