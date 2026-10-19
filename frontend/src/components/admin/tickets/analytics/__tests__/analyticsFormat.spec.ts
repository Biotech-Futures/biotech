import { describe, expect, it } from 'vitest'

import { ApiError } from '@/utils/apiError'
import {
  channelLabel,
  describeWindow,
  dimensionLabel,
  duration,
  namedDay,
  niceScale,
  segmentLabel,
  windowProblem
} from '../analyticsFormat'

describe('duration', () => {
  it('carries a rounded-up remainder into the hour instead of printing 60m', () => {
    // U4 AN-24. React split the seconds into hours first and rounded the
    // leftover minutes, so anything from 59.5 minutes past the hour printed
    // "60m": 3,599 s read "60m", 7,199 s read "1h 60m" and 172,799 s read
    // "47h 60m". These are the three values that were checked against a
    // verbatim copy of the React function.
    expect(duration(3599)).toBe('1h')
    expect(duration(7199)).toBe('2h')
    expect(duration(172799)).toBe('2d')
  })

  it('keeps the coarse shape: minutes, then hours and minutes, then days', () => {
    expect(duration(null)).toBe('—')
    expect(duration(0)).toBe('0m')
    expect(duration(1800)).toBe('30m')
    expect(duration(3600)).toBe('1h')
    expect(duration(5400)).toBe('1h 30m')
    // The last minute before the switch to days still reads in hours.
    expect(duration(172740)).toBe('47h 59m')
    expect(duration(259200)).toBe('3d')
  })
})

describe('dimensionLabel', () => {
  it('derives the words from the key rather than looking them up', () => {
    expect(
      ['region', 'userType', 'category', 'assignee', 'programStage', 'first_response'].map(
        dimensionLabel
      )
    ).toEqual(['Region', 'User type', 'Category', 'Assignee', 'Program stage', 'First response'])
  })

  it('reads a run of capitals as one word, the known limit its comment admits', () => {
    expect(dimensionLabel('SLABreach')).toBe('Slabreach')
  })
})

describe('segmentLabel', () => {
  const roster = [
    { id: 3, name: 'Sam Reid', assignable: true },
    { id: 4, name: 'Sam Reid', assignable: false },
    { id: 11, name: 'Sana Reid', assignable: true }
  ]

  it('says "Not recorded" for an empty bucket on every dimension but category', () => {
    expect(
      ['region', 'userType', 'status', 'assignee', 'channel', 'priority'].map((dimension) =>
        segmentLabel(dimension, '', roster)
      )
    ).toEqual(Array(6).fill('Not recorded'))
  })

  it('names an empty category the way the Demand chart names it', () => {
    // U4 AN-27: React printed the same empty bucket as "Not categorised" in
    // "By category" and "Not recorded" in "Broken down by category".
    expect(segmentLabel('category', '', roster)).toBe('Not categorised')
    expect(segmentLabel('category', 'help_student_group', roster)).toBe(
      'Help with a student or group'
    )
  })

  it('puts words on the stored values of status, channel and priority', () => {
    expect(segmentLabel('status', 'pending_user', roster)).toBe('Pending user')
    expect(segmentLabel('channel', 'ai_screening', roster)).toBe('Raised by screening')
    expect(segmentLabel('priority', 'low', roster)).toBe('Low')
    // An unknown stored value is printed as it is, not hidden.
    expect(segmentLabel('status', 'archived', roster)).toBe('archived')
    expect(channelLabel('fax')).toBe('fax')
  })

  it('names owners, falls back to the id, and tells two same-named people apart', () => {
    expect(segmentLabel('assignee', '11', roster)).toBe('Sana Reid')
    expect(segmentLabel('assignee', '77', roster)).toBe('#77')
    expect(segmentLabel('assignee', '3', roster)).toBe('Sam Reid #3')
    expect(segmentLabel('assignee', '4', roster)).toBe('Sam Reid #4')
  })

  it('prints region and user type as stored', () => {
    expect(segmentLabel('region', 'Australia', roster)).toBe('Australia')
    expect(segmentLabel('userType', 'mentor', roster)).toBe('mentor')
  })
})

describe('the window echo', () => {
  // "Sept" is what this machine's ICU prints for en-AU, the same dependency
  // the React test carried.
  it('names both ends, inclusive, in UTC', () => {
    expect(describeWindow('2026-08-26', '2026-09-03')).toBe(
      'Covering 26 Aug 2026 to 3 Sept 2026 inclusive, in UTC.'
    )
  })

  it('has a sentence for each open end', () => {
    expect(describeWindow('2026-08-26', '')).toBe('Covering 26 Aug 2026 onwards, in UTC.')
    expect(describeWindow('', '2026-09-03')).toBe(
      'Covering everything up to and including 3 Sept 2026, in UTC.'
    )
  })

  it('keeps a year under 100 as that year, not 1900 and something', () => {
    // A native date input reports "0002-09-01" while somebody is part way
    // through typing 2026. Date.UTC reads years 0 to 99 as 1900 plus the year.
    expect(namedDay('0002-09-01')).toBe('1 Sept 2')
    expect(namedDay('0020-09-01')).toBe('1 Sept 20')
  })

  it('echoes something it cannot read exactly as it was given', () => {
    expect(namedDay('soon')).toBe('soon')
  })
})

describe('windowProblem', () => {
  const envelope = (error: string, code: string) => ({ error, code, request_id: 'req-1' })

  it("repeats the server's sentence for a 400 the window caused", () => {
    expect(
      windowProblem(new ApiError(envelope('from must be earlier than to.', 'invalid'), 400))
    ).toBe('from must be earlier than to.')
  })

  it('says nothing for a 500, a 400 without the envelope, or something that is not an ApiError', () => {
    expect(
      windowProblem(new ApiError(envelope('Internal server error', 'internal_server_error'), 500))
    ).toBeUndefined()
    // apiError.ts fills `error` with a fallback sentence of ours when the
    // body had none, and gives such a body the code http_400. That sentence
    // is not the server explaining the window.
    expect(
      windowProblem(
        new ApiError(envelope('Something went wrong at our end. Please try again in a moment.', 'http_400'), 400)
      )
    ).toBeUndefined()
    expect(windowProblem(new Error('from must be earlier than to.'))).toBeUndefined()
  })

  it('leaves a refusal to the page, even though its envelope carries a readable sentence', () => {
    // The same endpoint answers a reader without support access with this
    // 403. Its code is one ticketRefusalReason passes through, so only the
    // 400 check keeps it from being shown as a problem with the dates.
    expect(
      windowProblem(
        new ApiError(envelope('You do not have support privileges.', 'permission_denied'), 403)
      )
    ).toBeUndefined()
  })
})

describe('niceScale', () => {
  it('steps in whole round numbers up to a top at or above the largest value', () => {
    expect(niceScale(4)).toEqual({ top: 4, ticks: [0, 1, 2, 3, 4] })
    expect(niceScale(7)).toEqual({ top: 8, ticks: [0, 2, 4, 6, 8] })
    expect(niceScale(1)).toEqual({ top: 1, ticks: [0, 1] })
    expect(niceScale(7200)).toEqual({ top: 8000, ticks: [0, 2000, 4000, 6000, 8000] })
  })

  it('has a scale for all-zero data rather than dividing by nothing', () => {
    expect(niceScale(0)).toEqual({ top: 1, ticks: [0] })
  })
})
