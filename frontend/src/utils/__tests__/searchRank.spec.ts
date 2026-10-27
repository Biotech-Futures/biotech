import { describe, expect, it } from 'vitest'
import { rankBySearch, searchForm } from '@/utils/searchRank'

const names = (list: string[], query: string) => rankBySearch(list, query, (name) => [name])

describe('searchForm', () => {
  it('reads a group however it is typed', () => {
    for (const typed of ['BTF07', 'btf7', 'BTF 7', 'BTF  07', 'btf-07', 'BTF_7', ' BTF7 ']) {
      expect(searchForm(typed)).toBe('btf7')
    }
  })

  it('keeps words apart and numbers whole', () => {
    expect(searchForm('  Ada   Lovelace ')).toBe('ada lovelace')
    expect(searchForm('Room 101')).toBe('room101')
    expect(searchForm('0.5')).toBe('0.5')
    expect(searchForm('2026 / 100')).toBe('2026 / 100')
    expect(searchForm('05/10/26 09:05')).toBe('5/10/26 9:5')
  })
})

describe('rankBySearch', () => {
  it('puts the group asked for first, then the closest, wherever they started', () => {
    // Newest first, as Finalist Submissions lists them.
    const newest = ['BTF111', 'BTF21', 'BTF10', 'BTF100', 'BTF01', 'BTF13']
    expect(names(newest, 'btf1')).toEqual(['BTF01', 'BTF10', 'BTF13', 'BTF111', 'BTF100'])
    expect(names(newest, 'BTF 1')).toEqual(names(newest, 'btf1'))
  })

  it('finds a group by its number alone, its own first', () => {
    expect(names(['BTF17', 'BTF70', 'BTF07', 'BTF27'], '7')).toEqual(['BTF07', 'BTF70', 'BTF17', 'BTF27'])
  })

  it('ranks words as it does groups', () => {
    const people = ['Joanna Smith', 'Ann Lee', 'Annabelle Ng', 'Leanne Annan', 'Anna Ito']
    expect(names(people, 'ann')).toEqual(['Ann Lee', 'Anna Ito', 'Annabelle Ng', 'Leanne Annan', 'Joanna Smith'])
  })

  it('leaves out what does not match, and leaves everything for no query', () => {
    expect(names(['BTF01', 'BTF02'], 'zzz')).toEqual([])
    const all = ['BTF02', 'BTF01']
    expect(rankBySearch(all, '   ', (name) => [name])).toBe(all)
  })

  it("scores a row by its best matching text", () => {
    const rows = [
      { group: 'BTF07', mentor: 'Joanna Smith' },
      { group: 'BTF10', mentor: 'Ann Lee' }
    ]
    const ranked = rankBySearch(rows, 'ann', (row) => [row.group, row.mentor])
    expect(ranked.map((row) => row.group)).toEqual(['BTF10', 'BTF07'])
  })
})
