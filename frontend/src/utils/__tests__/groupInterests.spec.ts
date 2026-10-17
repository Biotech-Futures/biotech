import { describe, expect, it } from 'vitest'

import { sharedInterests } from '@/utils/groupInterests'

describe('sharedInterests', () => {
  it('counts how many students have each area, the most shared first', () => {
    expect(
      sharedInterests([
        ['Biomedical Innovations', 'Water & Energy Tech'],
        ['biomedical innovations'],
        ['Space & Astrobiology', 'Biomedical Innovations'],
      ]),
    ).toEqual([
      { name: 'Biomedical Innovations', count: 3, students: [1, 2, 3] },
      { name: 'Space & Astrobiology', count: 1, students: [3] },
      { name: 'Water & Energy Tech', count: 1, students: [1] },
    ])
  })

  it('counts a student once per area and skips blanks and missing lists', () => {
    expect(sharedInterests([['Ecology', 'Ecology', ' '], null, undefined])).toEqual([
      { name: 'Ecology', count: 1, students: [1] },
    ])
  })
})
