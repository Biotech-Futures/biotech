import { describe, expect, it } from 'vitest'
import { computeMutualInterests } from '@/utils/mutualInterests'

describe('computeMutualInterests', () => {
  it('returns an empty array for empty or null members', () => {
    expect(computeMutualInterests([])).toEqual([])
    expect(computeMutualInterests(null as unknown as [])).toEqual([])
    expect(computeMutualInterests(undefined as unknown as [])).toEqual([])
  })

  it('returns an empty array when members have no interests or non-overlapping interests', () => {
    const members = [
      { id: '1', interests: ['AI'] },
      { id: '2', interests: ['Biology'] },
      { id: '3', interests: ['Chemistry'] }
    ]
    expect(computeMutualInterests(members)).toEqual([])
  })

  it('ignores null, undefined or empty members in the list', () => {
    const members = [
      null,
      undefined,
      { interests: null },
      { interests: undefined },
      { interests: [] }
    ]
    expect(computeMutualInterests(members)).toEqual([])
  })

  it('computes shared interests with count >= 2 ordered by frequency descending', () => {
    const members = [
      { interests: ['AI', 'Bioinformatics', 'Genetics'] },
      { interests: ['AI', 'Bioinformatics', 'Robotics'] },
      { interests: ['AI', 'Climate Tech'] }
    ]
    const result = computeMutualInterests(members)
    expect(result).toEqual([
      { name: 'AI', count: 3 },
      { name: 'Bioinformatics', count: 2 }
    ])
  })

  it('deduplicates duplicate interests within a single member', () => {
    const members = [
      { interests: ['AI', 'AI', '  AI  '] },
      { interests: ['AI'] }
    ]
    const result = computeMutualInterests(members)
    expect(result).toEqual([{ name: 'AI', count: 2 }])
  })

  it('breaks ties using case-insensitive name ascending (matching backend name.lower())', () => {
    const members = [
      { interests: ['Genetics', 'ai', 'Bioinformatics'] },
      { interests: ['Genetics', 'ai', 'Bioinformatics'] }
    ]
    const result = computeMutualInterests(members)
    // All counts are 2.
    // 'ai'.toLowerCase() = 'ai'
    // 'Bioinformatics'.toLowerCase() = 'bioinformatics'
    // 'Genetics'.toLowerCase() = 'genetics'
    // Sorted order: ai, Bioinformatics, Genetics
    expect(result).toEqual([
      { name: 'ai', count: 2 },
      { name: 'Bioinformatics', count: 2 },
      { name: 'Genetics', count: 2 }
    ])
  })

  it('handles interests with leading and trailing whitespace', () => {
    const members = [
      { interests: ['  Bioinformatics  ', 'Genetics'] },
      { interests: ['Bioinformatics', '  Genetics  '] }
    ]
    const result = computeMutualInterests(members)
    expect(result).toEqual([
      { name: 'Bioinformatics', count: 2 },
      { name: 'Genetics', count: 2 }
    ])
  })
})
