import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AssigneeOption, RegionOption, TicketFilters } from '@/utils/ticketAgentSchema'
import FilterBar from '../FilterBar.vue'

/** Ported from adminweb's FilterBar.test.tsx, plus the dropdown contents and
 *  the Clear button, which React left untested. */

const REGIONS: RegionOption[] = [
  { value: 'Australia', label: 'Australia' },
  { value: '__unknown__', label: 'Unknown' }
]

const PEOPLE: AssigneeOption[] = [
  { id: 1, name: 'Sam Reid', assignable: true },
  // Kept out of the assign dropdown but deliberately present here: their
  // tickets did not move when the account was switched off, and filtering by
  // them is the only way to find that work in bulk.
  { id: 3, name: 'Gone Agent', assignable: false }
]

let wrapper: VueWrapper | null = null

function show(filters: TicketFilters = {}) {
  wrapper = mount(FilterBar, { props: { filters, regions: REGIONS, assignees: PEOPLE } })
  return wrapper
}

/** Every filter change the bar raised, oldest first. */
function changes() {
  return (wrapper!.emitted('change') ?? []).map(([next]) => next)
}

function options(label: string) {
  return wrapper!
    .get(`select[aria-label="${label}"]`)
    .findAll('option')
    .map((o) => [o.attributes('value'), o.text()])
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('FilterBar search box', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('does not raise a filter change on every keystroke', async () => {
    // The queue request is a COUNT plus a page of rows. Typing an eight-letter
    // ticket number used to issue eight of them.
    show()
    const box = wrapper!.get('input[aria-label="Search tickets"]')

    for (const value of ['S', 'SU', 'SUP', 'SUP-']) {
      await box.setValue(value)
    }

    expect(changes()).toEqual([])
  })

  it('raises exactly one change once the typing settles', async () => {
    show()
    const box = wrapper!.get('input[aria-label="Search tickets"]')

    for (const value of ['S', 'SU', 'SUP', 'SUP-']) {
      await box.setValue(value)
    }
    vi.advanceTimersByTime(400)

    expect(changes()).toEqual([{ search: 'SUP-' }])
  })

  it('waits the whole 300ms after the last key', async () => {
    show()
    const box = wrapper!.get('input[aria-label="Search tickets"]')

    await box.setValue('mia')
    vi.advanceTimersByTime(299)
    expect(changes()).toEqual([])

    vi.advanceTimersByTime(1)
    expect(changes()).toEqual([{ search: 'mia' }])
  })

  it('shows what was typed straight away, and keeps it while another filter changes', async () => {
    // The debounce is on what leaves the component, not on the box itself. A
    // laggy-feeling input is how a delay like this gets reported as a bug.
    // And the box follows the applied search only: React's comment on its
    // dependency list, "depending on `filters` as well would re-fire on every
    // other filter change and undo their edits", is the failure this pins.
    show()
    const box = wrapper!.get<HTMLInputElement>('input[aria-label="Search tickets"]')

    await box.setValue('mia')
    expect(box.element.value).toBe('mia')

    await wrapper!.setProps({ filters: { status: 'open' } })

    expect(box.element.value).toBe('mia')
  })

  it('empties the box when the parent clears the filters', async () => {
    // Clear filters sets the filters to {} from the outside; nothing else
    // would reset the local draft, and a stale word left in the box reads as
    // a filter that is still applied.
    show({ search: 'mia' })
    const box = wrapper!.get<HTMLInputElement>('input[aria-label="Search tickets"]')
    expect(box.element.value).toBe('mia')

    await wrapper!.setProps({ filters: {} })

    expect(box.element.value).toBe('')
    vi.advanceTimersByTime(400)
    // Emptying the box from outside is not the agent searching for nothing.
    expect(changes()).toEqual([])
  })

  it('keeps a filter picked while the typing was settling', async () => {
    // The settled search is spread over the filters as they are when it
    // settles, not as they were when typing began.
    show()
    await wrapper!.get('input[aria-label="Search tickets"]').setValue('mia')
    await wrapper!.setProps({ filters: { status: 'open' } })

    vi.advanceTimersByTime(400)

    expect(changes()).toEqual([{ status: 'open', search: 'mia' }])
  })
})

describe('FilterBar dropdowns', () => {
  it('keeps agents who can no longer be assigned in the assignee filter', () => {
    // The mirror image of BulkAssignBar: this list must NOT filter on
    // `assignable`. Dropping them here would make every ticket still in their
    // name invisible in bulk: not unassigned, so no counter shows it, and no
    // value to filter by.
    show()

    expect(options('Filter by assignee')).toEqual([
      ['', 'Any assignee'],
      ['__unassigned__', 'Unassigned'],
      ['1', 'Sam Reid'],
      ['3', 'Gone Agent']
    ])
  })

  it('carries Overdue as a status sentinel the server reads with the card rule', async () => {
    show({ priority: 'high' })

    await wrapper!.get('select[aria-label="Filter by status"]').setValue('__overdue__')

    expect(changes()).toEqual([{ priority: 'high', status: '__overdue__' }])
  })

  it('carries the Unknown region bucket as a sentinel, not an empty value', async () => {
    // An empty query parameter reads as "no filter" everywhere else on the
    // platform, so the bucket needs a value of its own.
    show()

    await wrapper!.get('select[aria-label="Filter by region"]').setValue('__unknown__')

    expect(changes()).toEqual([{ region: '__unknown__' }])
  })

  it('keeps every other filter when one dropdown changes', async () => {
    // The page replaces the whole filter state with what the bar sends, so a
    // bar that sent only the key it changed would silently clear the search
    // and the region the agent had already narrowed to. React had no test
    // for this; every case above starts from nothing or from one key.
    show({ region: 'Australia', search: 'mia' })

    await wrapper!.get('select[aria-label="Filter by status"]').setValue('open')

    expect(changes()).toEqual([{ region: 'Australia', search: 'mia', status: 'open' }])
  })

  it('turns the Any option back into no filter at all', async () => {
    // React carried "Any" as an "__any__" sentinel because its Select could
    // not hold an empty value; a native select can, so "Any" is "" itself.
    // What leaves the bar is the same as before: the key, emptied.
    show({ status: 'open' })

    await wrapper!.get('select[aria-label="Filter by status"]').setValue('')

    expect(changes()).toEqual([{ status: '' }])
  })

  it('offers the four statuses, Overdue and three priorities in triage words', () => {
    show()

    expect(options('Filter by status')).toEqual([
      ['', 'Any status'],
      ['open', 'Open'],
      ['in_progress', 'In progress'],
      ['pending_user', 'Pending user'],
      ['resolved', 'Resolved'],
      // Last, and as a sentinel: it is the badge beside the status, not a
      // status a ticket can be set to.
      ['__overdue__', 'Overdue']
    ])
    expect(options('Filter by priority')).toEqual([
      ['', 'Any priority'],
      ['high', 'High'],
      ['normal', 'Normal'],
      ['low', 'Low']
    ])
  })

  it('offers every category a ticket can carry, screening’s included, last', () => {
    // A bucket support cannot filter for is a bucket they cannot work
    // through, and message screening files its own tickets here.
    show()

    expect(options('Filter by category')).toEqual([
      ['', 'Any category'],
      ['account_access', 'Account and access'],
      ['registration', 'Registration'],
      ['help_student_group', 'Help with a student or group'],
      ['help_mentor', 'Help with a mentor'],
      ['technical_issue', 'Technical issue'],
      ['certificates_records', 'Certificates and records'],
      ['general_question', 'General Question'],
      ['other', 'Other'],
      ['flagged_content', 'Flagged content']
    ])
  })

  it('shows the filter already applied', () => {
    show({ priority: 'high', assignee: '3' })

    expect(
      (wrapper!.get('select[aria-label="Filter by priority"]').element as HTMLSelectElement).value
    ).toBe('high')
    expect(
      (wrapper!.get('select[aria-label="Filter by assignee"]').element as HTMLSelectElement).value
    ).toBe('3')
  })
})

describe('Clear filters', () => {
  const clearButton = () => wrapper!.findAll('button').find((b) => b.text() === 'Clear filters')

  it('is not offered while nothing is filtered', () => {
    show()

    expect(clearButton()).toBeUndefined()
  })

  it('is not offered for a dropdown set back to Any', () => {
    // "Any" leaves an empty string behind, which is no filter.
    show({ status: '' })

    expect(clearButton()).toBeUndefined()
  })

  it('clears everything at once', async () => {
    show({ status: 'open', search: 'mia' })

    await clearButton()!.trigger('click')

    expect(changes()).toEqual([{}])
  })
})
