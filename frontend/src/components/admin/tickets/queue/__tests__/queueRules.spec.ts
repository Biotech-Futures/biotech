import { describe, expect, it } from 'vitest'

import { clampPageSize, pageItems, servedPageCount, ticketIdFromQuery } from '../queueRules'

describe('ticketIdFromQuery', () => {
  // Guarded rather than coerced: Number("abc") is NaN, and a panel opened on
  // NaN sits on "Loading..." forever. React's route did the same check on a
  // value its router had already parsed; a Vue query value is a string.
  it.each([
    ['1', 1],
    ['128', 128],
    ['9007199254740991', 9007199254740991]
  ])('reads %j as ticket %d', (value, id) => {
    expect(ticketIdFromQuery(value)).toBe(id)
  })

  it.each([
    ['abc'],
    ['0'],
    ['-3'],
    ['+3'],
    ['1.5'],
    ['1.0'],
    ['012'],
    ['1e3'],
    [' 12'],
    ['12 '],
    [''],
    ['9007199254740993'],
    [undefined],
    [null],
    [12],
    [['4', '5']]
  ])('ignores %j', (value) => {
    expect(ticketIdFromQuery(value)).toBeNull()
  })
})

describe('clampPageSize', () => {
  it.each([
    [25, 25],
    [7.9, 7],
    [0, 1],
    [-4, 1],
    [100, 100],
    [101, 100],
    [500, 100],
    [Number.NaN, 25],
    [Number.POSITIVE_INFINITY, 25]
  ])('holds %d at %d', (typed, held) => {
    expect(clampPageSize(typed)).toBe(held)
  })
})

describe('servedPageCount', () => {
  it('divides by the size the server served, not the size asked for', () => {
    expect(servedPageCount(1, 200, { total: 450, limit: 100, hasMore: true })).toBe(5)
  })

  it('falls back to the asked size before any answer', () => {
    expect(servedPageCount(3, 10, null)).toBe(3)
  })

  it('keeps a page past this one while the server says there is more', () => {
    expect(servedPageCount(2, 10, { total: 5, limit: 10, hasMore: true })).toBe(3)
  })

  it('never says zero pages', () => {
    expect(servedPageCount(1, 10, { total: 0, limit: 10, hasMore: false })).toBe(1)
  })
})

describe('pageItems', () => {
  // The same window as adminweb's pagination-nav: seven buttons at most,
  // first and last pinned, a lone hidden page shown rather than hidden.
  it.each([
    [1, 1, [1]],
    [3, 7, [1, 2, 3, 4, 5, 6, 7]],
    [1, 20, [1, 2, 3, 4, 'ellipsis', 20]],
    [5, 20, [1, 'ellipsis', 4, 5, 6, 'ellipsis', 20]],
    [4, 20, [1, 2, 3, 4, 5, 'ellipsis', 20]],
    [20, 20, [1, 'ellipsis', 17, 18, 19, 20]],
    [17, 20, [1, 'ellipsis', 16, 17, 18, 19, 20]]
  ])('page %d of %d reads %j', (current, total, items) => {
    expect(pageItems(current, total)).toEqual(items)
  })
})
