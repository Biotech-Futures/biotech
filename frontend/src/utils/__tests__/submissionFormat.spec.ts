import { describe, expect, it } from 'vitest'
import {
  countWords,
  describeQuestionStep,
  describeTimeRemaining,
  formatFileSize,
  isDeadlineNear
} from '@/utils/submissionFormat'

// A fixed point to measure deadlines against, so these never depend on when
// they are run.
const NOW = new Date('2026-09-01T00:00:00Z').getTime()
const inHours = (h: number) => new Date(NOW + h * 3600_000).toISOString()

describe('countWords', () => {
  // Must agree with the server and the Qualtrics regex: a counter that
  // disagrees tells a student their answer fits, then the save is rejected.
  it('counts words separated by single spaces', () => {
    expect(countWords('one two three four five')).toBe(5)
  })

  it('ignores repeated spaces, tabs and newlines', () => {
    expect(countWords('  one \n\n two \t  three  ')).toBe(3)
  })

  it('treats empty and whitespace-only answers as zero', () => {
    expect(countWords('')).toBe(0)
    expect(countWords('   \n\t ')).toBe(0)
    expect(countWords(null)).toBe(0)
    expect(countWords(undefined)).toBe(0)
  })

  it('counts hyphenated and punctuated words as one each', () => {
    // Matches the server rather than being linguistically clever.
    expect(countWords('state-of-the-art solution, tested.')).toBe(3)
  })

  it('counts exactly at the limit as within it', () => {
    const exactly150 = Array.from({ length: 150 }, (_, i) => `w${i}`).join(' ')
    expect(countWords(exactly150)).toBe(150)
  })
})

describe('formatFileSize', () => {
  it('drops the decimal on whole megabytes so a limit reads "5 MB"', () => {
    expect(formatFileSize(5 * 1024 * 1024)).toBe('5 MB')
    expect(formatFileSize(50 * 1024 * 1024)).toBe('50 MB')
  })

  it('keeps one decimal for part megabytes', () => {
    expect(formatFileSize(6 * 1024 * 1024)).toBe('6 MB')
    expect(formatFileSize(1.5 * 1024 * 1024)).toBe('1.5 MB')
  })

  it('falls back to kilobytes and bytes', () => {
    expect(formatFileSize(2048)).toBe('2 KB')
    expect(formatFileSize(512)).toBe('512 bytes')
  })

  it('reports zero rather than calling it unknown', () => {
    // An empty file is a real thing that was uploaded; "unknown" is reserved
    // for a size the server did not record.
    expect(formatFileSize(0)).toBe('0 bytes')
    expect(formatFileSize(null)).toBe('unknown size')
    expect(formatFileSize(undefined)).toBe('unknown size')
  })
})

describe('describeTimeRemaining', () => {
  it('uses days while more than a day remains', () => {
    expect(describeTimeRemaining(inHours(72), NOW)).toBe('3 days left')
    expect(describeTimeRemaining(inHours(25), NOW)).toBe('1 day left')
  })

  it('switches to hours inside the last day', () => {
    expect(describeTimeRemaining(inHours(5), NOW)).toBe('5 hours left')
    expect(describeTimeRemaining(inHours(1), NOW)).toBe('1 hour left')
  })

  it('switches to minutes inside the last hour', () => {
    expect(describeTimeRemaining(new Date(NOW + 10 * 60_000).toISOString(), NOW)).toBe(
      '10 minutes left'
    )
  })

  it('says nothing at all once the moment has passed, rather than counting negative', () => {
    // Naming the grace period would publish a window the programme keeps quiet,
    // and a frozen phrase would keep saying "now" for up to a day.
    expect(describeTimeRemaining(inHours(-1), NOW)).toBe('')
    expect(describeTimeRemaining(inHours(-25), NOW)).toBe('')
  })

  it('says nothing when no deadline is configured', () => {
    expect(describeTimeRemaining(null, NOW)).toBe('')
    expect(describeTimeRemaining('not a date', NOW)).toBe('')
  })
})

describe('isDeadlineNear', () => {
  it('is true only inside the final day', () => {
    expect(isDeadlineNear(inHours(23), NOW)).toBe(true)
    expect(isDeadlineNear(inHours(25), NOW)).toBe(false)
  })

  it('is false once the deadline has passed, not "very near"', () => {
    expect(isDeadlineNear(inHours(-1), NOW)).toBe(false)
  })

  it('is false with no deadline set', () => {
    expect(isDeadlineNear(null, NOW)).toBe(false)
  })
})

describe('describeQuestionStep', () => {
  const keys = ['q1', 'q2', 'q3']

  it('counts only answers with content', () => {
    expect(describeQuestionStep({ q1: 'written', q2: '   ', q3: '' }, keys)).toBe(
      'Required · 1 of 3'
    )
  })

  it('counts every question when all are answered', () => {
    expect(describeQuestionStep({ q1: 'a', q2: 'b', q3: 'c' }, keys)).toBe('Required · 3 of 3')
  })

  it('does not claim progress it cannot know', () => {
    // Deliberately a count, not "Done": text in every box does not mean the
    // answers are finished.
    expect(describeQuestionStep({}, keys)).toBe('Required · 0 of 3')
  })

  it('still reports the requirement with no questions configured', () => {
    expect(describeQuestionStep({}, [])).toBe('Required')
  })
})
