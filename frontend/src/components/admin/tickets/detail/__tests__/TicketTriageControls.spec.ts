import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AppSelect from '@/components/AppSelect.vue'
import type { AssigneeOption, TicketDetail } from '@/utils/ticketAgentSchema'

import {
  ACTIVE,
  OWNER,
  api,
  deferred,
  offeredChoices,
  openPanel,
  pending,
  pickChoice,
  refusal,
  resetPanelTests,
  serverError,
  shownChoice,
  ticketGone,
  ticketWith,
  triageField,
  type Panel
} from './ticketDetailFixtures'

// The four triage controls, driven through the real panel. Ported from the
// "assignee control", "when a change is refused" and "category control"
// blocks of adminweb/src/components/tickets/TicketDetailPanel.test.tsx.
//
// The React selects were Radix listboxes opened with ArrowDown. These were
// native <select>s until the 2026-10-22 client meeting asked for the
// platform's own dropdown (C-29), and are AppSelects now: "what the control
// shows" is the words in its box and "what it offers" is its list, opened. A
// row that cannot be picked is aria-disabled, and a press on it does nothing.
vi.mock('@/utils/ticketAgentAPI', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/utils/ticketAgentAPI')>()),
  fetchTicketDetail: vi.fn(),
  fetchAssignees: vi.fn(),
  fetchTicketHistory: vi.fn(),
  updateTicket: vi.fn(),
  sendTicketMessage: vi.fn(),
  downloadTicketAttachment: vi.fn()
}))

beforeEach(resetPanelTests)
afterEach(resetPanelTests)

const ownedByGoneAgent = () => ticketWith({ assignee: { id: OWNER.id, name: OWNER.name } })

const ASSIGNEE = 'Change assignee'

describe('assignee control', () => {
  it('still names the current owner after they stop being assignable', async () => {
    // The bug: the fallback row asked "are they missing from `assignees`",
    // and the endpoint deliberately keeps past owners in that list so the
    // filter dropdown can find their tickets. So the row never rendered, no
    // option matched the current value, and a ticket with an owner showed as
    // "Unassigned".
    const panel = await openPanel(ownedByGoneAgent())

    expect(shownChoice(panel, ASSIGNEE)).toContain('Gone Agent')
    expect(shownChoice(panel, ASSIGNEE)).not.toBe('Unassigned')
  })

  it('does not offer an unassignable person as a new owner', async () => {
    const panel = await openPanel(ownedByGoneAgent())

    const offered = await offeredChoices(panel, ASSIGNEE)
    expect(offered).toContain('Sam Reid')
    expect(offered).toContain('Gone Agent (no longer on the queue)')
    // ⚠️ The two lines above cannot fail alone. Dropping the assignable
    // filter keeps the current-owner row AND adds a plain "Gone Agent" below
    // it, so both still pass. This is the absence the test is named after.
    expect(offered).not.toContain('Gone Agent')
  })

  it('does not call a revoked agent inactive, which is a different thing', async () => {
    // Two things drop the owner off the assignable list: a deactivated
    // account, and queue access revoked on the support agents page. The
    // second leaves the account active, so "(inactive)" sent admins to switch
    // on an account that was never switched off.
    const panel = await openPanel(ownedByGoneAgent())

    expect(shownChoice(panel, ASSIGNEE)).toBe('Gone Agent (no longer on the queue)')
    expect(shownChoice(panel, ASSIGNEE)).not.toMatch(/inactive/i)
  })

  it('shows Unassigned when there really is no owner', async () => {
    const panel = await openPanel(ticketWith({ assignee: null }))

    expect(shownChoice(panel, ASSIGNEE)).toBe('Unassigned')
  })

  // P9-1. Every combination of "what state is the roster in" against "where
  // does the owner stand on it", generated rather than hand-picked, because a
  // hand-picked list of examples is the failure shape that has caught this
  // control before. The claim is a statement about a person, so it is earned
  // in one column only: a roster actually came back and the person is not
  // assignable on it.
  const ROSTERS: Record<string, (listed: AssigneeOption[]) => Promise<AssigneeOption[]>> = {
    'came back': (listed) => Promise.resolve(listed),
    'request failed': async () => {
      throw await serverError(500, {
        error: 'Internal server error',
        code: 'internal_server_error',
        request_id: 'r1'
      })
    },
    'still loading': () => pending()
  }

  const OWNER_STANDS: Record<string, AssigneeOption[]> = {
    'assignable on it': [ACTIVE, { id: 3, name: 'Gone Agent', assignable: true }],
    'listed but revoked': [ACTIVE, { id: 3, name: 'Gone Agent', assignable: false }],
    'not listed at all': [ACTIVE]
  }

  for (const [rosterName, roster] of Object.entries(ROSTERS)) {
    for (const [standName, listed] of Object.entries(OWNER_STANDS)) {
      const earned = rosterName === 'came back' && standName !== 'assignable on it'
      const expected = earned ? 'Gone Agent (no longer on the queue)' : 'Gone Agent'

      it(`roster ${rosterName}, owner ${standName}: the control reads "${expected}"`, async () => {
        const panel = await openPanel(ownedByGoneAgent(), { roster: roster(listed) })

        expect(shownChoice(panel, ASSIGNEE)).toBe(expected)
      })
    }
  }

  it('says why the dropdown is short when the roster is not there', async () => {
    // Two rows and no explanation reads as the whole platform, and makes
    // "Unassigned" look like a considered choice rather than the only one
    // left.
    const panel = await openPanel(ownedByGoneAgent(), {
      roster: Promise.reject(await ticketGone())
    })

    expect(await offeredChoices(panel, ASSIGNEE)).toEqual([
      'Unassigned',
      'Gone Agent',
      'Nobody else to pick here'
    ])
    // Its second, quieter line says why.
    expect(document.querySelector('[role="option"][aria-disabled="true"] .app-select__detail')?.textContent).toBe(
      'The assignee list has not loaded.'
    )
  })

  it('keys on the roster being available, not on the list being long', async () => {
    // P9-1, the constraint the fix exists to hold. "Is the list short" and
    // "do we have a roster" are different questions, and only the second is
    // a reason to stop making a statement about a person. A roster that came
    // back empty is still a roster: the owner is not on it.
    const panel = await openPanel(ownedByGoneAgent(), { roster: [] })

    expect(shownChoice(panel, ASSIGNEE)).toBe('Gone Agent (no longer on the queue)')
    expect(await offeredChoices(panel, ASSIGNEE)).not.toContain('Nobody else to pick here')
  })

  it('leaves the roster-down explanation inert, not a choosable option', async () => {
    // Its value went through Number() to NaN in React, which JSON.stringify
    // writes as null: the same body the Unassigned row sends. Measured there
    // with `disabled` removed: clicking the sentence un-assigned ticket #128.
    const panel = await openPanel(ownedByGoneAgent(), { roster: pending() })
    await offeredChoices(panel, ASSIGNEE)

    const row = Array.from(document.querySelectorAll('[role="option"]')).find((option) =>
      option.textContent?.includes('Nobody else to pick here')
    )
    expect(row?.getAttribute('aria-disabled')).toBe('true')

    row!.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, button: 0 }))
    await flushPromises()
    expect(api.updateTicket).not.toHaveBeenCalled()
  })

  it('refuses the explanation row even when something selects it anyway', async () => {
    // The second guard, independent of `disabled`: a value that is neither
    // the sentinel nor a person's id is never turned into a patch.
    const panel = await openPanel(ownedByGoneAgent(), { roster: pending() })
    const control = panel.wrapper
      .findAllComponents(AppSelect)
      .find((select) => select.vm.$attrs['aria-label'] === ASSIGNEE)!

    control.vm.$emit('change', '__unavailable')
    await flushPromises()

    expect(api.updateTicket).not.toHaveBeenCalled()
    expect(shownChoice(panel, ASSIGNEE)).toBe('Gone Agent')
  })

  it('says nothing of the sort while the roster is in hand', async () => {
    // The other direction, so the row above cannot pass by always rendering.
    const panel = await openPanel(ownedByGoneAgent())

    expect(await offeredChoices(panel, ASSIGNEE)).toEqual([
      'Unassigned',
      'Gone Agent (no longer on the queue)',
      'Sam Reid'
    ])
  })

  it('hands the ticket back to the pool as a real null', async () => {
    // The sentinel travels as JSON null, which is what the backend reads as
    // "back to the pool". Had no test in React (K-13).
    api.updateTicket.mockResolvedValue(ticketWith({ assignee: null }))
    const panel = await openPanel(ticketWith({ assignee: { id: 1, name: 'Sam Reid' } }))

    await pickChoice(panel, ASSIGNEE, 'Unassigned')

    expect(api.updateTicket).toHaveBeenCalledWith(7, { assignee: null })
  })

  it('sends a new owner as a number, and nothing else', async () => {
    api.updateTicket.mockResolvedValue(ticketWith({ assignee: { id: 1, name: 'Sam Reid' } }))
    const panel = await openPanel(ticketWith({ assignee: null }))

    await pickChoice(panel, ASSIGNEE, 'Sam Reid')

    expect(api.updateTicket).toHaveBeenCalledWith(7, { assignee: 1 })
    expect(shownChoice(panel, ASSIGNEE)).toBe('Sam Reid')
  })
})

describe('status, priority and category', () => {
  it('sends the status alone, never with an assignee', async () => {
    // The backend refuses a request carrying both, because each drives a
    // different transition.
    api.updateTicket.mockResolvedValue(ticketWith({ status: 'resolved' }))
    const panel = await openPanel(ticketWith({ status: 'in_progress' }))

    await pickChoice(panel, 'Change status', 'Resolved')

    expect(api.updateTicket).toHaveBeenCalledTimes(1)
    expect(api.updateTicket.mock.calls[0]).toEqual([7, { status: 'resolved' }])
    expect(Object.keys(api.updateTicket.mock.calls[0][1])).toEqual(['status'])
  })

  it('offers the four statuses and the three priorities in triage words', async () => {
    const panel = await openPanel(ticketWith())

    expect(await offeredChoices(panel, 'Change status')).toEqual([
      'Open',
      'In progress',
      'Pending user',
      'Resolved'
    ])
    expect(await offeredChoices(panel, 'Change priority')).toEqual(['High', 'Normal', 'Low'])
  })

  it('sends the priority alone', async () => {
    api.updateTicket.mockResolvedValue(ticketWith({ priority: 'high' }))
    const panel = await openPanel(ticketWith({ priority: 'normal' }))

    await pickChoice(panel, 'Change priority', 'High')

    expect(api.updateTicket.mock.calls[0]).toEqual([7, { priority: 'high' }])
  })

  it("shows the ticket's current category as a control, not as read-only text", async () => {
    // Two of the client's eight are near-synonyms, so mis-filing is routine
    // and the p52 category breakdown depends on someone being able to fix it.
    const panel = await openPanel(ticketWith({ category: 'help_mentor' }))

    expect(shownChoice(panel, 'Change category')).toBe('Help with a mentor')
  })

  it('offers the screening category too, so a mis-screened ticket has a way out', async () => {
    const panel = await openPanel(ticketWith({ category: 'flagged_content' }))

    expect(shownChoice(panel, 'Change category')).toBe('Flagged content')
    expect(await offeredChoices(panel, 'Change category')).toHaveLength(9)
  })

  it('sends the new category as a patch, and nothing else', async () => {
    // Re-filing must never look like either of the transitions: it writes no
    // timeline message and does not move the requester's clock.
    api.updateTicket.mockResolvedValue(ticketWith({ category: 'technical_issue' }))
    const panel = await openPanel(ticketWith({ category: 'account_access' }))

    await pickChoice(panel, 'Change category', 'Technical issue')

    expect(api.updateTicket).toHaveBeenCalledTimes(1)
    expect(api.updateTicket.mock.calls[0]).toEqual([7, { category: 'technical_issue' }])
    expect(Object.keys(api.updateTicket.mock.calls[0][1])).toEqual(['category'])
  })

  it('names a category it has no option for instead of showing a blank', async () => {
    const panel = await openPanel(ticketWith({ category: '' }))

    expect(shownChoice(panel, 'Change category')).toBe('Not categorised')
  })

  it('says it is saving while a change is on its way, and stops when it lands', async () => {
    const answer = deferred<TicketDetail>()
    api.updateTicket.mockReturnValue(answer.promise)
    const panel = await openPanel(ticketWith())

    await pickChoice(panel, 'Change priority', 'High')
    expect(panel.page.get('.triage__saving').text()).toBe('Saving…')
    expect(panel.page.get('.triage__saving').attributes('role')).toBe('status')

    answer.resolve(ticketWith({ priority: 'high' }))
    await flushPromises()
    expect(panel.page.get('.triage__saving').text()).toBe('')
  })
})

describe('choosing with the keyboard', () => {
  // The native selects these replaced moved their value on the arrow keys of
  // a closed control on Windows and Linux and fired `change` at once, so this
  // component used to hold such a value back until Enter. AppSelect has no
  // such move: the arrow keys open its list and move a highlight through it,
  // and only Enter or a click picks. Sent one by one, In progress, Pending
  // user, Resolved would be two system lines on the requester's timeline and
  // a resolved email; on Assignee, the ticket in each person's name in turn.
  const key = (panel: Panel, name: string, which: string) =>
    panel.page.get(triageField(name)).trigger('keydown', { key: which })
  const highlighted = () => document.querySelector('[role="option"].is-active .app-select__label')?.textContent

  it('sends nothing while the arrow keys move through the statuses, then one PATCH on Enter', async () => {
    api.updateTicket.mockResolvedValue(ticketWith({ status: 'resolved' }))
    const panel = await openPanel(ticketWith({ status: 'in_progress' }))

    await key(panel, 'Change status', 'ArrowDown')
    await key(panel, 'Change status', 'ArrowDown')
    await key(panel, 'Change status', 'ArrowDown')
    await flushPromises()

    expect(highlighted()).toBe('Resolved')
    expect(api.updateTicket).not.toHaveBeenCalled()
    expect(shownChoice(panel, 'Change status')).toBe('In progress')

    await key(panel, 'Change status', 'Enter')
    await flushPromises()

    expect(api.updateTicket.mock.calls).toEqual([[7, { status: 'resolved' }]])
    expect(shownChoice(panel, 'Change status')).toBe('Resolved')
    expect(panel.page.get('.triage__saving').text()).toBe('')
  })

  it('moves through the people without picking any up, until Enter', async () => {
    api.updateTicket.mockResolvedValue(ticketWith({ assignee: { id: 1, name: 'Sam Reid' } }))
    const panel = await openPanel(ticketWith({ assignee: null }), {
      roster: [ACTIVE, { id: 2, name: 'Lee Park', assignable: true }]
    })

    await key(panel, ASSIGNEE, 'ArrowDown')
    await key(panel, ASSIGNEE, 'ArrowDown')
    await key(panel, ASSIGNEE, 'ArrowDown')
    await key(panel, ASSIGNEE, 'ArrowUp')
    expect(api.updateTicket).not.toHaveBeenCalled()

    await key(panel, ASSIGNEE, 'Enter')
    await flushPromises()

    expect(api.updateTicket.mock.calls).toEqual([[7, { assignee: 1 }]])
  })

  it('jumps to a typed first letter in the open list without sending it', async () => {
    const panel = await openPanel(ticketWith({ priority: 'normal' }))

    await key(panel, 'Change priority', 'ArrowDown')
    await key(panel, 'Change priority', 'h')
    await flushPromises()

    expect(highlighted()).toBe('High')
    expect(api.updateTicket).not.toHaveBeenCalled()
    expect(shownChoice(panel, 'Change priority')).toBe('Normal')
  })

  it('sends nothing when the agent leaves the control without choosing', async () => {
    const panel = await openPanel(ticketWith({ status: 'in_progress' }))
    await key(panel, 'Change status', 'ArrowDown')
    await key(panel, 'Change status', 'ArrowDown')

    await panel.page.get(triageField('Change status')).trigger('blur')
    await flushPromises()

    expect(api.updateTicket).not.toHaveBeenCalled()
    expect(shownChoice(panel, 'Change status')).toBe('In progress')
  })

  it('takes Esc to close its open list, and leaves the panel open until the next Esc', async () => {
    const panel = await openPanel(ticketWith({ status: 'in_progress' }))
    await key(panel, 'Change status', 'ArrowDown')
    expect(panel.page.get(triageField('Change status')).attributes('aria-expanded')).toBe('true')

    await key(panel, 'Change status', 'Escape')

    expect(panel.wrapper.emitted('close')).toBeUndefined()
    expect(panel.page.get(triageField('Change status')).attributes('aria-expanded')).toBe('false')
    expect(api.updateTicket).not.toHaveBeenCalled()

    await key(panel, 'Change status', 'Escape')

    expect(panel.wrapper.emitted('close')).toHaveLength(1)
  })

  it('sends a pick made with a click at once', async () => {
    api.updateTicket.mockResolvedValue(ticketWith({ status: 'resolved' }))
    const panel = await openPanel(ticketWith({ status: 'in_progress' }))

    await pickChoice(panel, 'Change status', 'Resolved')

    expect(api.updateTicket).toHaveBeenCalledWith(7, { status: 'resolved' })
  })

  it('opens on Enter and sends nothing', async () => {
    const panel = await openPanel(ticketWith())

    await key(panel, 'Change status', 'Enter')
    await flushPromises()

    expect(panel.page.get(triageField('Change status')).attributes('aria-expanded')).toBe('true')
    expect(api.updateTicket).not.toHaveBeenCalled()
  })

  it('sends nothing for a pick of what the ticket already has', async () => {
    const panel = await openPanel(ticketWith({ status: 'in_progress' }))

    await pickChoice(panel, 'Change status', 'In progress')

    expect(api.updateTicket).not.toHaveBeenCalled()
  })
})

describe('when a change is refused', () => {
  const alertText = ({ page }: Panel) => page.get('[role="alert"]').text()

  it('says so, and puts the control back to what the server has', async () => {
    // All four controls are driven by the server's copy, so a rejected PATCH
    // leaves them on the old value; without the sentence the agent watches
    // the dropdown snap back and cannot tell that from having misclicked.
    api.updateTicket.mockRejectedValue(await ticketGone())
    const panel = await openPanel(ticketWith({ status: 'in_progress' }))

    await pickChoice(panel, 'Change status', 'Resolved')

    expect(alertText(panel)).toMatch(/^That change was not saved\./)
    expect(shownChoice(panel, 'Change status')).toBe('In progress')
  })

  it("passes on the server's reason instead of guessing at one", async () => {
    api.updateTicket.mockRejectedValue(await refusal('Send a status or an assignee, not both.'))
    const panel = await openPanel(ticketWith())

    await pickChoice(panel, 'Change status', 'Open')

    expect(alertText(panel)).toBe(
      'That change was not saved. Send a status or an assignee, not both.'
    )
  })

  it('keeps the whole sentence when the ticket has simply gone', async () => {
    // The 404 does not come through the exception handler: views_admin.py's
    // _not_found answers {"msg": "Ticket not found"}. Reading `msg` as a
    // reason replaced the one sentence that says what to do next with two
    // words that do not, on the failure this panel meets most often.
    api.updateTicket.mockRejectedValue(await ticketGone())
    const panel = await openPanel(ticketWith())

    await pickChoice(panel, 'Change priority', 'Low')

    expect(alertText(panel)).toBe(
      'That change was not saved. The ticket may have been deleted or changed by someone' +
        ' else. Close the panel and reopen it to see where it stands.'
    )
  })

  it("says why a new owner was refused, in the server's words (T03)", async () => {
    // The real body, not the React test's invented `Invalid pk "18" - object
    // does not exist.` (F1): both assignee fields override does_not_exist
    // with NOT_ASSIGNABLE, and the handler keeps the code. React answered
    // this sentence with "close the panel and reopen it", which is not what
    // is wrong.
    api.updateTicket.mockRejectedValue(
      await serverError(400, {
        error: 'Cannot assign to user "1". They need an active account with support queue access.',
        code: 'does_not_exist',
        request_id: '048bd2752e81',
        fields: {
          assignee: [
            'Cannot assign to user "1". They need an active account with support queue access.'
          ]
        }
      })
    )
    const panel = await openPanel(ticketWith({ assignee: null }))

    await pickChoice(panel, ASSIGNEE, 'Sam Reid')

    expect(alertText(panel)).toBe(
      'That change was not saved. Cannot assign to user "1". They need an active account' +
        ' with support queue access.'
    )
    expect(shownChoice(panel, ASSIGNEE)).toBe('Unassigned')
  })

  it("does not read DRF's own words out to the agent", async () => {
    // A rejected choice is DRF's default English, written for whoever wrote
    // the request. The standing sentence says what to do instead.
    api.updateTicket.mockRejectedValue(
      await serverError(400, {
        error: '"nope" is not a valid choice.',
        code: 'invalid_choice',
        request_id: '5d1e0b'
      })
    )
    const panel = await openPanel(ticketWith())

    await pickChoice(panel, 'Change status', 'Resolved')

    expect(alertText(panel)).not.toMatch(/valid choice/)
    expect(alertText(panel)).toMatch(/Close the panel and reopen it/)
  })

  it('stays quiet while everything is working', async () => {
    const panel = await openPanel(ticketWith())

    expect(panel.page.find('[role="alert"]').exists()).toBe(false)
  })

  it('clears the warning when the panel moves to another ticket', async () => {
    // Without this the red text follows the agent to the next ticket and
    // reads as a problem with the one they are now looking at.
    api.updateTicket.mockRejectedValue(await ticketGone())
    const panel = await openPanel(ticketWith())
    await pickChoice(panel, 'Change status', 'Resolved')
    expect(panel.page.find('[role="alert"]').exists()).toBe(true)

    api.fetchTicketDetail.mockResolvedValue(ticketWith({ id: 8, ticketNumber: 'SUP-2026-00008' }))
    await panel.wrapper.setProps({ ticketId: 8 })
    await flushPromises()

    expect(panel.page.get('h2').text()).toContain('SUP-2026-00008')
    expect(panel.page.find('[role="alert"]').exists()).toBe(false)
  })

  it('clears the warning when the next change goes through', async () => {
    api.updateTicket.mockRejectedValueOnce(await ticketGone())
    api.updateTicket.mockResolvedValueOnce(ticketWith({ priority: 'high' }))
    const panel = await openPanel(ticketWith())
    await pickChoice(panel, 'Change status', 'Resolved')

    await pickChoice(panel, 'Change priority', 'High')

    expect(panel.page.find('[role="alert"]').exists()).toBe(false)
  })
})
