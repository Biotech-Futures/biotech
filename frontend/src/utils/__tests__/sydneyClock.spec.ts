import { describe, expect, it } from 'vitest'
import { sydneyClockOn } from '@/utils/date'

describe('sydneyClockOn', () => {
  it('is daylight saving from the first Sunday in October to the first in April', () => {
    expect(sydneyClockOn('2026-10-24')).toEqual({ name: 'AEDT', daylight: true, offset: 'UTC+11' })
    expect(sydneyClockOn('2026-10-04')).toEqual({ name: 'AEDT', daylight: true, offset: 'UTC+11' })
    expect(sydneyClockOn('2026-10-03')).toEqual({ name: 'AEST', daylight: false, offset: 'UTC+10' })
    expect(sydneyClockOn('2026-07-24')).toEqual({ name: 'AEST', daylight: false, offset: 'UTC+10' })
  })
})
