import { describe, expect, it } from 'vitest'

import { RESTING_STATUSES, filterSummary, isRestingView, restingFilters, type FilterOption } from '../queueFilters'

const STATUSES: FilterOption[] = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'pending_user', label: 'Pending user' },
  { value: 'resolved', label: 'Resolved' },
  { value: '__overdue__', label: 'Overdue', extra: true }
]

describe('the queue’s resting view (C-28)', () => {
  it('is every status but Resolved', () => {
    expect(RESTING_STATUSES).toEqual(['open', 'in_progress', 'pending_user'])
    expect(restingFilters()).toEqual({ status: ['open', 'in_progress', 'pending_user'] })
  })

  it('hands out a new list each time, so one holder cannot move another', () => {
    const first = restingFilters()
    first.status!.push('resolved')

    expect(restingFilters().status).toEqual(['open', 'in_progress', 'pending_user'])
  })

  it('is recognised in any order, and nothing else is', () => {
    expect(isRestingView({ status: ['pending_user', 'open', 'in_progress'] })).toBe(true)
    expect(isRestingView({ status: ['pending_user', 'open', 'in_progress'], region: [] })).toBe(true)

    expect(isRestingView({})).toBe(false)
    expect(isRestingView({ status: [] })).toBe(false)
    expect(isRestingView({ status: ['open', 'in_progress'] })).toBe(false)
    expect(isRestingView({ status: ['open', 'in_progress', 'pending_user', 'resolved'] })).toBe(false)
    expect(isRestingView({ status: ['open', 'in_progress', 'resolved'] })).toBe(false)
    expect(isRestingView({ ...restingFilters(), search: 'mia' })).toBe(false)
    expect(isRestingView({ ...restingFilters(), assignee: ['__unassigned__'] })).toBe(false)
  })
})

describe('the words on a filter’s box', () => {
  it('reads nothing ticked, or every one of the kind, as Any', () => {
    expect(filterSummary([], STATUSES, 'Any status')).toBe('Any status')
    expect(filterSummary(['open', 'in_progress', 'pending_user', 'resolved'], STATUSES, 'Any status')).toBe('Any status')
    // Every status already takes in every ticket Overdue could add.
    expect(
      filterSummary(['open', 'in_progress', 'pending_user', 'resolved', '__overdue__'], STATUSES, 'Any status')
    ).toBe('Any status')
  })

  it('reads all but one of three or more as Not …, which is the resting view', () => {
    expect(filterSummary(['open', 'in_progress', 'pending_user'], STATUSES, 'Any status')).toBe(
      'Not Resolved'
    )
    expect(filterSummary(['in_progress', 'pending_user', 'resolved'], STATUSES, 'Any status')).toBe(
      'Not Open'
    )
  })

  it('does not say Not … of two, where it is just the other one', () => {
    const two: FilterOption[] = [
      { value: 'a', label: 'Alpha' },
      { value: 'b', label: 'Beta' }
    ]
    expect(filterSummary(['a'], two, 'Any')).toBe('Alpha')
  })

  it('lists anything else in the list’s order, whatever order it was ticked in', () => {
    expect(filterSummary(['pending_user', 'open'], STATUSES, 'Any status')).toBe('Open, Pending user')
    expect(filterSummary(['resolved'], STATUSES, 'Any status')).toBe('Resolved')
  })

  it('names Overdue after the statuses ticked beside it, and on its own', () => {
    expect(filterSummary(['__overdue__'], STATUSES, 'Any status')).toBe('Overdue')
    expect(filterSummary(['__overdue__', 'pending_user'], STATUSES, 'Any status')).toBe('Pending user, Overdue')
    expect(filterSummary(['open', 'in_progress', 'pending_user', '__overdue__'], STATUSES, 'Any status')).toBe(
      'Open, In progress, Pending user, Overdue'
    )
  })

  it('shows a value the list does not have yet as stored, rather than dropping it', () => {
    // Regions and people arrive from the server after the filters do.
    const people: FilterOption[] = [{ value: '__unassigned__', label: 'Unassigned' }]
    expect(filterSummary(['7'], people, 'Any assignee')).toBe('7')
    expect(filterSummary(['__unassigned__', '7'], people, 'Any assignee')).toBe('Unassigned, 7')
  })
})
