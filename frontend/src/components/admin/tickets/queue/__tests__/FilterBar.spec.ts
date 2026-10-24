import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AssigneeOption, RegionOption, TicketFilters } from '@/utils/ticketAgentSchema'
import FilterBar from '../FilterBar.vue'
import { restingFilters } from '../queueFilters'

/** Ported from adminweb's FilterBar.test.tsx, plus the lists' contents and
 *  the Clear button, which React left untested. Since the 2026-10-22 client
 *  meeting each list takes several values (C-27) and the queue rests on
 *  every status but Resolved (C-28). */

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
  wrapper = mount(FilterBar, {
    props: { filters, regions: REGIONS, assignees: PEOPLE },
    attachTo: document.body
  })
  return wrapper
}

/** Every filter change the bar raised, oldest first. */
function changes() {
  return (wrapper!.emitted('change') ?? []).map(([next]) => next)
}

const box = (label: string) => wrapper!.get(`button[aria-label="${label}"]`)
const boxText = (label: string) => box(label).text()

async function openList(label: string) {
  if (box(label).attributes('aria-expanded') !== 'true') await box(label).trigger('click')
  return wrapper!.get(`[role="group"][aria-label="${label}"]`)
}

/** The list's choices, as [value, words, ticked]. */
async function choices(label: string) {
  const list = await openList(label)
  return list.findAll('label').map((option) => {
    const check = option.get<HTMLInputElement>('input[type="checkbox"]')
    return [check.element.value, option.text(), check.element.checked]
  })
}

async function tick(label: string, value: string, ticked = true) {
  const list = await openList(label)
  await list.get(`input[value="${value}"]`).setValue(ticked)
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
    const search = wrapper!.get('input[aria-label="Search tickets"]')

    for (const value of ['S', 'SU', 'SUP', 'SUP-']) {
      await search.setValue(value)
    }

    expect(changes()).toEqual([])
  })

  it('raises exactly one change once the typing settles', async () => {
    show()
    const search = wrapper!.get('input[aria-label="Search tickets"]')

    for (const value of ['S', 'SU', 'SUP', 'SUP-']) {
      await search.setValue(value)
    }
    vi.advanceTimersByTime(400)

    expect(changes()).toEqual([{ search: 'SUP-' }])
  })

  it('waits the whole 300ms after the last key', async () => {
    show()
    const search = wrapper!.get('input[aria-label="Search tickets"]')

    await search.setValue('mia')
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
    const search = wrapper!.get<HTMLInputElement>('input[aria-label="Search tickets"]')

    await search.setValue('mia')
    expect(search.element.value).toBe('mia')

    await wrapper!.setProps({ filters: { status: ['open'] } })

    expect(search.element.value).toBe('mia')
  })

  it('empties the box when the parent clears the filters', async () => {
    // Clear filters puts the resting view in from the outside, with no search
    // in it; nothing else would reset the local draft, and a stale word left
    // in the box reads as a filter that is still applied.
    show({ search: 'mia' })
    const search = wrapper!.get<HTMLInputElement>('input[aria-label="Search tickets"]')
    expect(search.element.value).toBe('mia')

    await wrapper!.setProps({ filters: restingFilters() })

    expect(search.element.value).toBe('')
    vi.advanceTimersByTime(400)
    // Emptying the box from outside is not the agent searching for nothing.
    expect(changes()).toEqual([])
  })

  it('keeps a filter picked while the typing was settling', async () => {
    // The settled search is spread over the filters as they are when it
    // settles, not as they were when typing began.
    show()
    await wrapper!.get('input[aria-label="Search tickets"]').setValue('mia')
    await wrapper!.setProps({ filters: { status: ['open'] } })

    vi.advanceTimersByTime(400)

    expect(changes()).toEqual([{ status: ['open'], search: 'mia' }])
  })
})

describe('FilterBar lists', () => {
  it('keeps agents who can no longer be assigned in the assignee filter', async () => {
    // The mirror image of BulkAssignBar: this list must NOT filter on
    // `assignable`. Dropping them here would make every ticket still in their
    // name invisible in bulk: not unassigned, so no counter shows it, and no
    // value to filter by.
    show()

    expect(await choices('Filter by assignee')).toEqual([
      ['__unassigned__', 'Unassigned', false],
      ['1', 'Sam Reid', false],
      ['3', 'Gone Agent', false]
    ])
  })

  it('ticks several of one kind (C-27)', async () => {
    show({ status: ['open'] })

    await tick('Filter by status', 'pending_user')

    expect(changes()).toEqual([{ status: ['open', 'pending_user'] }])
  })

  it('sends what is ticked in the list’s own order, whatever order it was ticked in', async () => {
    show({ priority: ['low'] })

    await tick('Filter by priority', 'high')

    expect(changes()).toEqual([{ priority: ['high', 'low'] }])
  })

  it('unticking the last one leaves no filter of that kind', async () => {
    show({ status: ['open'] })

    await tick('Filter by status', 'open', false)

    expect(changes()).toEqual([{ status: [] }])
  })

  it('carries Overdue beside the statuses as the sentinel the server reads with the card rule', async () => {
    show({ status: ['open'], priority: ['high'] })

    await tick('Filter by status', '__overdue__')

    expect(changes()).toEqual([{ status: ['open', '__overdue__'], priority: ['high'] }])
  })

  it('carries the Unknown region bucket as a sentinel, not an empty value', async () => {
    // An empty query parameter reads as "no filter" everywhere else on the
    // platform, so the bucket needs a value of its own.
    show()

    await tick('Filter by region', '__unknown__')

    expect(changes()).toEqual([{ region: ['__unknown__'] }])
  })

  it('keeps every other filter when one list changes', async () => {
    // The page replaces the whole filter state with what the bar sends, so a
    // bar that sent only the key it changed would silently clear the search
    // and the region the agent had already narrowed to.
    show({ region: ['Australia'], search: 'mia' })

    await tick('Filter by status', 'open')

    expect(changes()).toEqual([{ region: ['Australia'], search: 'mia', status: ['open'] }])
  })

  it('offers the four statuses, Overdue and three priorities in triage words', async () => {
    show()

    expect((await choices('Filter by status')).map(([value, words]) => [value, words])).toEqual([
      ['open', 'Open'],
      ['in_progress', 'In progress'],
      ['pending_user', 'Pending user'],
      ['resolved', 'Resolved'],
      // Last, and as a sentinel: it is the badge beside the status, not a
      // status a ticket can be set to.
      ['__overdue__', 'Overdue']
    ])
    expect((await choices('Filter by priority')).map(([value, words]) => [value, words])).toEqual([
      ['high', 'High'],
      ['normal', 'Normal'],
      ['low', 'Low']
    ])
  })

  it('offers every category a ticket can carry, screening’s included, last', async () => {
    // A bucket support cannot filter for is a bucket they cannot work
    // through, and message screening files its own tickets here.
    show()

    expect((await choices('Filter by category')).map(([value, words]) => [value, words])).toEqual([
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

  it('shows the filters already applied, on the box and as ticks', async () => {
    show({ priority: ['high'], assignee: ['3'] })

    expect(boxText('Filter by priority')).toBe('High')
    expect(boxText('Filter by assignee')).toBe('Gone Agent')
    expect(await choices('Filter by assignee')).toEqual([
      ['__unassigned__', 'Unassigned', false],
      ['1', 'Sam Reid', false],
      ['3', 'Gone Agent', true]
    ])
  })

  it('reads the queue’s resting view as Not Resolved (C-28)', () => {
    show(restingFilters())

    expect(boxText('Filter by status')).toBe('Not Resolved')
    expect(boxText('Filter by priority')).toBe('Any priority')
  })
})

describe('Clear filters', () => {
  const clearButton = () => wrapper!.findAll('button').find((b) => b.text() === 'Clear filters')

  it('is not offered on the view the queue opens on', () => {
    show(restingFilters())

    expect(clearButton()).toBeUndefined()
  })

  it('is offered once anything else is chosen, Resolved ticked or every status cleared included', () => {
    for (const filters of [
      { status: ['open', 'in_progress', 'pending_user', 'resolved'] },
      { status: [] },
      { ...restingFilters(), priority: ['high'] },
      { ...restingFilters(), search: 'mia' }
    ]) {
      show(filters)
      expect(clearButton(), JSON.stringify(filters)).toBeDefined()
      wrapper!.unmount()
      wrapper = null
    }
  })

  it('goes back to every status but Resolved, and nothing else', async () => {
    show({ status: ['resolved'], region: ['Australia'], search: 'mia' })

    await clearButton()!.trigger('click')

    expect(changes()).toEqual([{ status: ['open', 'in_progress', 'pending_user'] }])
  })
})
