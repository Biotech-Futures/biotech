import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { appSelectLabels, openAppSelect, pickAppSelect } from '@/__tests__/appSelect'
import type { AssigneeOption } from '@/utils/ticketAgentSchema'
import BulkAssignBar from '../BulkAssignBar.vue'

/** Ported from adminweb's BulkAssignBar.test.tsx. The dropdown is the
 *  platform's AppSelect since the 2026-10-22 client meeting (C-29), so these
 *  open it to read what it offers and pick by the words on a choice. */

// The endpoint returns one list for two consumers. `assignable` marks the
// people the write path will actually accept; everybody else is here so the
// *filter* dropdown can still find their tickets.
const PEOPLE: AssigneeOption[] = [
  { id: 1, name: 'Sam Reid', assignable: true },
  { id: 2, name: 'Dana Okafor', assignable: true },
  { id: 3, name: 'Gone Agent', assignable: false }
]

let wrapper: VueWrapper | null = null

function open(props: Partial<InstanceType<typeof BulkAssignBar>['$props']> = {}) {
  wrapper = mount(BulkAssignBar, {
    props: {
      count: 3,
      assignees: PEOPLE,
      assigneesUnavailable: false,
      assigneesLoading: false,
      pending: false,
      ...props
    }
  })
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

const ASSIGN_TO = 'input[aria-label="Assign to"]'

/** What the dropdown offers, opened, as shown. */
function optionTexts() {
  return appSelectLabels(wrapper!, ASSIGN_TO)
}

function actionButton() {
  return wrapper!.get<HTMLButtonElement>('button.bulk-assign__go')
}

async function pick(label: string) {
  await pickAppSelect(wrapper!, ASSIGN_TO, label)
}

describe('BulkAssignBar', () => {
  it('offers only people the write path will accept', async () => {
    // The bug this pins: the detail panel filtered on `assignable` and this
    // dropdown did not. Picking the unfiltered name sent a batch the backend
    // refused with a 400, and nothing on screen said so.
    open()

    expect(await optionTexts()).toEqual(['Unassigned', 'Sam Reid', 'Dana Okafor'])
    expect(wrapper!.get(ASSIGN_TO).attributes('placeholder')).toBe('Assign to…')
  })

  it('does not let you assign before picking somebody', () => {
    open()

    expect(actionButton().text()).toBe('Assign')
    expect(actionButton().element.disabled).toBe(true)
  })

  it('hands the chosen id back as a number', async () => {
    open()

    await pick('Dana Okafor')
    await actionButton().trigger('click')

    // Not the string "2": the id goes straight into a JSON body the
    // serializer validates as a primary key.
    expect(wrapper!.emitted('assign')).toEqual([[2]])
  })

  it('says it is working and refuses a second click while it is', async () => {
    open({ pending: true })
    await pick('Dana Okafor')

    expect(actionButton().text()).toBe('Assigning…')
    expect(actionButton().element.disabled).toBe(true)
  })

  it('counts the batch in the shared bar, and names its clear button for what it clears', () => {
    open({ count: 1 })

    expect(wrapper!.get('[role="toolbar"]').attributes('aria-label')).toBe('Bulk actions')
    expect(wrapper!.get('.bulk-actions-bar__count').text()).toBe('1 ticket selected')
    expect(wrapper!.get('.bulk-actions-bar__clear').text()).toBe('Clear selection')
  })
})

describe('handing a batch back to the pool', () => {
  it('offers it under the name the filter bar already uses, above the people', async () => {
    // The endpoint has taken a null assignee since the serializer was written
    // and three backend tests pin it, but no control in the admin app could
    // ask for it. "Unassigned" is what the queue filter calls the same bucket.
    open()

    expect((await optionTexts())[0]).toBe('Unassigned')
  })

  it('sends null rather than a person', async () => {
    // Not 0 and not the sentinel string: the serializer reads null as "back
    // to the pool" and anything else as a primary key it will refuse.
    open()

    await pick('Unassigned')
    await actionButton().trigger('click')

    expect(wrapper!.emitted('assign')).toEqual([[null]])
  })

  it('calls the button what it is about to do', async () => {
    // A button reading "Assign" that takes the assignee away is the last
    // thing an agent sees before committing a batch of up to two hundred.
    open()

    await pick('Unassigned')

    expect(actionButton().text()).toBe('Unassign')
  })

  it('says it is handing back while it is', async () => {
    open({ pending: true })

    await pick('Unassigned')

    expect(actionButton().text()).toBe('Unassigning…')
  })
})

describe('when the assignee list could not be loaded', () => {
  const NOTE = 'Nobody to pick here'
  const WHY = 'The assignee list could not be loaded. Reload to try again.'

  it('says so instead of opening on a list that looks complete', async () => {
    // The endpoint failing leaves the list empty, and the pool line is
    // offered whatever happens, so without this the dropdown opens on one
    // plausible option and reads as a platform with nobody on it.
    open({ assignees: [], assigneesUnavailable: true })

    const choices = await openAppSelect(wrapper!, ASSIGN_TO)
    const note = choices.find((o) => o.querySelector('.app-select__label')?.textContent === NOTE)!
    expect(note.querySelector('.app-select__detail')?.textContent).toBe(WHY)
    expect(note.getAttribute('aria-disabled')).toBe('true')
  })

  it('still lets the batch go back to the pool', async () => {
    // Nothing about handing tickets back needs the list of people, so the one
    // action that still works has to stay reachable.
    open({ assignees: [], assigneesUnavailable: true })

    await pick('Unassigned')

    expect(actionButton().element.disabled).toBe(false)
  })

  it('says nothing while the list is fine', async () => {
    open()

    expect((await optionTexts()).join(' ')).not.toMatch(/Nobody to pick|Loading/i)
  })

  it('says the list is still coming rather than showing the pool alone', async () => {
    // React told the detail panel about a roster still loading (P9-1) but not
    // this dropdown, which opened on "Unassigned" alone and read as a
    // platform with nobody on it.
    open({ assignees: [], assigneesLoading: true })

    expect(await optionTexts()).toEqual(['Unassigned', 'Loading the assignee list…'])
  })
})

describe('a batch bigger than the server takes', () => {
  // serializers_admin.py refuses more than 200 ids in one batch. Written out
  // here rather than imported, so a change to the page's number has to be a
  // change to this test as well.
  const SERVER_BATCH_LIMIT = 200

  it('will not send it, and says why', async () => {
    open({ count: SERVER_BATCH_LIMIT + 1 })
    await pick('Sam Reid')

    expect(actionButton().element.disabled).toBe(true)
    expect(wrapper!.get('.bulk-assign__limit').text().replace(/\s+/g, ' ')).toBe(
      'One batch can hold at most 200 tickets, and 201 are selected. Deselect some to assign the rest.'
    )
    expect(actionButton().attributes('aria-describedby')).toBe(
      wrapper!.get('.bulk-assign__limit').attributes('id')
    )
  })

  it('sends a batch of exactly the limit', async () => {
    open({ count: SERVER_BATCH_LIMIT })
    await pick('Sam Reid')

    expect(actionButton().element.disabled).toBe(false)
    expect(wrapper!.find('.bulk-assign__limit').exists()).toBe(false)
  })
})
