import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import GroupDetailModal from '@/components/admin/groups/GroupDetailModal.vue'

const groupFixture = () => ({
  id: 1,
  name: 'BTF1',
  members: [
    { id: '10', name: 'Ada Lovelace', email: 'ada@example.com', role: 'student', membershipId: 100 },
    { id: '11', name: 'Grace Hopper', email: 'grace@example.com', role: 'student', membershipId: 101 }
  ],
  mentor: { id: '20', name: 'Marie Curie', email: 'marie@example.com', role: 'mentor', membershipId: 200 },
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z'
})

const textMessage = {
  id: 'm1',
  group_id: '1',
  sender: { id: '10', name: 'Ada Lovelace', email: 'ada@example.com', role: 'student' },
  message_type: 'text',
  text: 'Hey team, how is everyone?',
  attachments: [],
  gif: null,
  sent_at: '2026-01-05T00:00:00Z',
  edited_at: null
}

const gifMessage = {
  id: 'm2',
  group_id: '1',
  sender: { id: '20', name: 'Marie Curie', email: 'marie@example.com', role: 'mentor' },
  message_type: 'gif',
  text: '',
  attachments: [],
  gif: { gif_url: 'https://example.com/g.gif', preview_url: 'https://example.com/p.gif', title: 'nice' },
  sent_at: '2026-01-06T00:00:00Z',
  edited_at: null
}

const ungroupedStudent = (id: number, firstName: string, lastName: string) => ({
  id,
  firstName,
  lastName,
  email: `${firstName.toLowerCase()}@example.com`,
  role: 'student',
  groupId: null,
  groupName: null
})

const fetchMockFor = (opts: {
  page1?: unknown[]
  page2?: unknown[]
  total?: number
  /** When set, every DELETE responds 409 with this message instead of succeeding. */
  deleteError?: string
  /** Ungrouped students returned by GET /user/ for the add-students picker. */
  ungrouped?: unknown[]
} = {}) => {
  // Message deletes are tracked so a later GET reflects them, mirroring the
  // real backend (the component re-fetches the page after a removal).
  const deletedMessageIds = new Set<string>()
  const rawTotal = opts.total ?? (opts.page1?.length ?? 0)

  return vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const method = (init?.method || 'GET').toUpperCase()
    const u = String(url)

    if (u.includes('/services/csrf/')) {
      return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'csrf-test' }), { status: 200 }))
    }
    if (method === 'DELETE' && opts.deleteError) {
      return Promise.resolve(
        new Response(JSON.stringify({ error: opts.deleteError, code: 'conflict' }), { status: 409 })
      )
    }
    if (method === 'DELETE' && u.includes('/members/')) {
      return Promise.resolve(
        new Response(JSON.stringify({ msg: 'Member removed successfully', data: null }), { status: 200 })
      )
    }
    if (method === 'DELETE' && u.includes('/messages/')) {
      const id = u.match(/\/messages\/([^/]+)\//)?.[1]
      if (id) deletedMessageIds.add(id)
      return Promise.resolve(
        new Response(JSON.stringify({ msg: 'Message removed successfully', data: null }), { status: 200 })
      )
    }
    if (method === 'GET' && u.includes('/messages/')) {
      const page = u.includes('page=2') ? 2 : 1
      const raw = (page === 2 ? (opts.page2 ?? []) : (opts.page1 ?? [])) as { id: string }[]
      const items = raw.filter((m) => !deletedMessageIds.has(m.id))
      const total = rawTotal - deletedMessageIds.size
      return Promise.resolve(
        new Response(
          JSON.stringify({
            msg: 'ok',
            data: { items, total, page, limit: 50, has_more: page === 1 && total > 50 }
          }),
          { status: 200 }
        )
      )
    }
    if (method === 'GET' && u.includes('/user/')) {
      const items = opts.ungrouped ?? []
      return Promise.resolve(
        new Response(
          JSON.stringify({
            msg: 'ok',
            data: { items, total: items.length, page: 1, limit: 100, hasMore: false }
          }),
          { status: 200 }
        )
      )
    }
    if (method === 'POST' && u.includes('/match/confirm/')) {
      const body = JSON.parse(String(init?.body ?? '{}'))
      return Promise.resolve(
        new Response(
          JSON.stringify({
            msg: 'Assignments confirmed successfully',
            data: { assigned_count: body.assignments?.length ?? 0 }
          }),
          { status: 200 }
        )
      )
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
  })
}

// FormSheet renders via <Teleport to="body">, so its content lives outside
// the mounted wrapper's own element tree. Query/interact through
// document.body, mirroring AdminGroupsPage.spec.ts's dialog helpers.
const dialog = () => document.body.querySelector('[role="dialog"]') as HTMLElement | null

// The removal confirmations use the app's ConfirmDialog, which teleports its own
// role="dialog" into <body> with the .admin-modal--confirm class.
const confirmDialog = () => document.body.querySelector('.admin-modal--confirm') as HTMLElement | null

const clickButton = (root: HTMLElement, label: string) => {
  const button = Array.from(root.querySelectorAll('button')).find((b) => b.textContent?.trim() === label)
  if (!button) throw new Error(`button "${label}" not found`)
  button.dispatchEvent(new Event('click', { bubbles: true }))
}

// Messages live behind a "View Messages" button now, not on the initial view.
const openMessages = async () => {
  clickButton(dialog()!, 'View Messages')
  await flushPromises()
}

let wrapper: VueWrapper | null = null

const mountModal = async (fetchMock: ReturnType<typeof vi.fn>, group = groupFixture()) => {
  vi.stubGlobal('fetch', fetchMock)
  wrapper = mount(GroupDetailModal, {
    attachTo: document.body,
    props: { modelValue: false, group: null }
  })
  // The message watcher fires on open (false -> true), not on initial props,
  // so flip modelValue after mount to mirror how AdminGroupsPage opens it.
  await wrapper.setProps({ modelValue: true, group })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

describe('GroupDetailModal', () => {
  it('shows mentor and members on open, and messages only after clicking through', async () => {
    const fetchMock = fetchMockFor({ page1: [textMessage, gifMessage], total: 2 })
    await mountModal(fetchMock)

    const infoText = dialog()!.textContent!
    expect(infoText).toContain('Marie Curie')
    expect(infoText).toContain('Ada Lovelace')
    expect(infoText).toContain('Grace Hopper')
    expect(infoText).not.toContain('Hey team, how is everyone?')

    await openMessages()
    const msgText = dialog()!.textContent!
    expect(msgText).toContain('Hey team, how is everyone?')
    expect(msgText).toContain('[GIF]')

    // "Back" returns to the group-information view.
    clickButton(dialog()!, 'Back to group information')
    await flushPromises()
    expect(dialog()!.textContent).toContain('Marie Curie')
    expect(dialog()!.textContent).not.toContain('Hey team, how is everyone?')
  })

  it('does not fetch messages until the Messages view is opened', async () => {
    const fetchMock = fetchMockFor({ page1: [textMessage], total: 1 })
    await mountModal(fetchMock)

    const messageGets = () =>
      fetchMock.mock.calls.filter(
        ([u, i]) => String(u).includes('/messages/') && (i as RequestInit | undefined)?.method === 'GET'
      )
    expect(messageGets()).toHaveLength(0)

    await openMessages()
    expect(messageGets().length).toBeGreaterThanOrEqual(1)
  })

  it('renders no timestamp instead of "Invalid Date" for a malformed sent_at', async () => {
    const fetchMock = fetchMockFor({ page1: [{ ...textMessage, sent_at: 'not-a-date' }], total: 1 })
    await mountModal(fetchMock)
    await openMessages()

    expect(dialog()!.textContent).toContain('Hey team, how is everyone?')
    expect(dialog()!.textContent).not.toContain('Invalid Date')
  })

  it('removes a member after confirmation and emits changed', async () => {
    const fetchMock = fetchMockFor({ page1: [], total: 0 })
    await mountModal(fetchMock)

    const removeButtons = Array.from(dialog()!.querySelectorAll('button')).filter(
      (b) => b.textContent?.trim() === 'Remove'
    )
    expect(removeButtons.length).toBe(2)
    removeButtons[0].dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()

    // The click stages the removal; confirm it in the app's ConfirmDialog.
    expect(confirmDialog()!.textContent).toContain('Remove Ada Lovelace from BTF1?')
    clickButton(confirmDialog()!, 'Remove')
    await flushPromises()

    const call = fetchMock.mock.calls.find(
      ([u, i]) => String(u).includes('/group/1/members/10/') && (i as RequestInit | undefined)?.method === 'DELETE'
    )
    expect(call).toBeDefined()
    expect(dialog()!.textContent).not.toContain('Ada Lovelace')
    expect(wrapper!.emitted('changed')).toBeTruthy()
  })

  it('does not remove the member when the confirmation is declined', async () => {
    const fetchMock = fetchMockFor({ page1: [], total: 0 })
    await mountModal(fetchMock)

    clickButton(dialog()!, 'Remove')
    await flushPromises()

    clickButton(confirmDialog()!, 'Cancel')
    await flushPromises()

    const called = fetchMock.mock.calls.some(
      ([u, i]) => String(u).includes('/members/') && (i as RequestInit | undefined)?.method === 'DELETE'
    )
    expect(called).toBe(false)
    expect(dialog()!.textContent).toContain('Ada Lovelace')
  })

  it('shows a member-removal failure inline in the dialog, not via window.alert', async () => {
    const alertSpy = vi.fn()
    vi.stubGlobal('alert', alertSpy)
    const fetchMock = fetchMockFor({ page1: [], total: 0, deleteError: 'Group must keep at least one student.' })
    await mountModal(fetchMock)

    clickButton(dialog()!, 'Remove')
    await flushPromises()
    clickButton(confirmDialog()!, 'Remove')
    await flushPromises()

    // Error surfaces inside the confirm dialog, which stays open.
    expect(confirmDialog()!.textContent).toContain('Group must keep at least one student.')
    expect(alertSpy).not.toHaveBeenCalled()
    // The member is still listed and nothing was emitted to the parent.
    expect(dialog()!.textContent).toContain('Ada Lovelace')
    expect(wrapper!.emitted('changed')).toBeFalsy()
  })

  it('adds ungrouped students to the group and emits changed', async () => {
    const fetchMock = fetchMockFor({
      ungrouped: [ungroupedStudent(30, 'Rosalind', 'Franklin'), ungroupedStudent(31, 'Alan', 'Turing')]
    })
    await mountModal(fetchMock)

    clickButton(dialog()!, 'Add students')
    await flushPromises()

    // Picker only asks for ungrouped students.
    const userCall = fetchMock.mock.calls.find(([u]) => String(u).includes('/user/'))
    expect(String(userCall![0])).toContain('inGroup=no')
    expect(String(userCall![0])).toContain('role=student')
    expect(dialog()!.textContent).toContain('3 seats left')

    const rosalind = Array.from(dialog()!.querySelectorAll('label')).find((l) =>
      l.textContent?.includes('Rosalind Franklin')
    )!
    const checkbox = rosalind.querySelector('input[type="checkbox"]') as HTMLInputElement
    checkbox.checked = true
    checkbox.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    clickButton(dialog()!, 'Add (1)')
    await flushPromises()

    const confirmCall = fetchMock.mock.calls.find(
      ([u, i]) => String(u).includes('/match/confirm/') && (i as RequestInit | undefined)?.method === 'POST'
    )
    expect(confirmCall).toBeDefined()
    expect(JSON.parse(String((confirmCall![1] as RequestInit).body))).toEqual({
      assignments: [{ studentId: 30, groupId: 1 }]
    })

    // Back on the info view with the new member listed.
    expect(dialog()!.textContent).toContain('Members (3)')
    expect(dialog()!.textContent).toContain('Rosalind Franklin')
    expect(wrapper!.emitted('changed')).toBeTruthy()
  })

  it('disables Add students when the group is full', async () => {
    const fetchMock = fetchMockFor()
    const full = groupFixture()
    full.members = Array.from({ length: 5 }, (_, i) => ({
      id: String(40 + i),
      name: `Student ${i}`,
      email: `s${i}@example.com`,
      role: 'student',
      membershipId: 300 + i
    }))
    await mountModal(fetchMock, full)

    const addButton = Array.from(dialog()!.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Add students'
    ) as HTMLButtonElement
    expect(addButton.disabled).toBe(true)
  })

  it('blocks adding more students than there are free seats', async () => {
    const fetchMock = fetchMockFor({
      ungrouped: [ungroupedStudent(30, 'Rosalind', 'Franklin'), ungroupedStudent(31, 'Alan', 'Turing')]
    })
    const almostFull = groupFixture()
    almostFull.members = Array.from({ length: 4 }, (_, i) => ({
      id: String(40 + i),
      name: `Student ${i}`,
      email: `s${i}@example.com`,
      role: 'student',
      membershipId: 300 + i
    }))
    await mountModal(fetchMock, almostFull)

    clickButton(dialog()!, 'Add students')
    await flushPromises()

    for (const box of Array.from(dialog()!.querySelectorAll('input[type="checkbox"]')) as HTMLInputElement[]) {
      box.checked = true
      box.dispatchEvent(new Event('change', { bubbles: true }))
    }
    await flushPromises()

    expect(dialog()!.textContent).toContain('Only 1 seat left')
    const addButton = Array.from(dialog()!.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Add (2)'
    ) as HTMLButtonElement
    expect(addButton.disabled).toBe(true)
  })

  it('does not count a mentor listed in members toward the seat limit', async () => {
    const fetchMock = fetchMockFor()
    const group = groupFixture()
    group.members = [
      ...Array.from({ length: 4 }, (_, i) => ({
        id: String(40 + i),
        name: `Student ${i}`,
        email: `s${i}@example.com`,
        role: 'student',
        membershipId: 300 + i
      })),
      { id: '20', name: 'Marie Curie', email: 'marie@example.com', role: 'mentor', membershipId: 200 }
    ]
    await mountModal(fetchMock, group)

    clickButton(dialog()!, 'Add students')
    await flushPromises()
    expect(dialog()!.textContent).toContain('1 seat left.')
  })

  it('Back and Cancel return to the member list without adding anyone', async () => {
    const fetchMock = fetchMockFor({ ungrouped: [ungroupedStudent(30, 'Rosalind', 'Franklin')] })
    await mountModal(fetchMock)

    clickButton(dialog()!, 'Add students')
    await flushPromises()
    clickButton(dialog()!, 'Back to group information')
    await flushPromises()
    expect(dialog()!.textContent).toContain('Members (2)')

    clickButton(dialog()!, 'Add students')
    await flushPromises()
    clickButton(dialog()!, 'Cancel')
    await flushPromises()
    expect(dialog()!.textContent).toContain('Members (2)')

    const posted = fetchMock.mock.calls.some(([u]) => String(u).includes('/match/confirm/'))
    expect(posted).toBe(false)
    expect(wrapper!.emitted('changed')).toBeFalsy()
  })

  it('disables Add students once an add fills the group', async () => {
    const fetchMock = fetchMockFor({ ungrouped: [ungroupedStudent(30, 'Rosalind', 'Franklin')] })
    const group = groupFixture()
    group.members = Array.from({ length: 4 }, (_, i) => ({
      id: String(40 + i),
      name: `Student ${i}`,
      email: `s${i}@example.com`,
      role: 'student',
      membershipId: 300 + i
    }))
    await mountModal(fetchMock, group)

    clickButton(dialog()!, 'Add students')
    await flushPromises()
    const box = dialog()!.querySelector('input[type="checkbox"]') as HTMLInputElement
    box.checked = true
    box.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()
    clickButton(dialog()!, 'Add (1)')
    await flushPromises()

    expect(dialog()!.textContent).toContain('Members (5)')
    const addButton = Array.from(dialog()!.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Add students'
    ) as HTMLButtonElement
    expect(addButton.disabled).toBe(true)
  })

  it('a just-added student can be removed again straight away', async () => {
    const fetchMock = fetchMockFor({ ungrouped: [ungroupedStudent(30, 'Rosalind', 'Franklin')] })
    await mountModal(fetchMock)

    clickButton(dialog()!, 'Add students')
    await flushPromises()
    const box = dialog()!.querySelector('input[type="checkbox"]') as HTMLInputElement
    box.checked = true
    box.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()
    clickButton(dialog()!, 'Add (1)')
    await flushPromises()

    // Rosalind is the third member row.
    const removeButtons = Array.from(dialog()!.querySelectorAll('button')).filter(
      (b) => b.textContent?.trim() === 'Remove'
    )
    expect(removeButtons).toHaveLength(3)
    removeButtons[2].dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()
    expect(confirmDialog()!.textContent).toContain('Remove Rosalind Franklin from BTF1?')
    clickButton(confirmDialog()!, 'Remove')
    await flushPromises()

    const call = fetchMock.mock.calls.find(
      ([u, i]) => String(u).includes('/group/1/members/30/') && (i as RequestInit | undefined)?.method === 'DELETE'
    )
    expect(call).toBeDefined()
    expect(dialog()!.textContent).not.toContain('Rosalind Franklin')
  })

  it('reopens on the member list rather than the picker', async () => {
    const fetchMock = fetchMockFor()
    await mountModal(fetchMock)

    clickButton(dialog()!, 'Add students')
    await flushPromises()
    await wrapper!.setProps({ modelValue: false })
    await wrapper!.setProps({ modelValue: true })
    await flushPromises()

    expect(dialog()!.textContent).toContain('Members (2)')
    expect(dialog()!.querySelector('input[type="search"]')).toBeNull()
  })

  it('removes a message after confirmation and decrements the total', async () => {
    const fetchMock = fetchMockFor({ page1: [textMessage], total: 1 })
    await mountModal(fetchMock)
    await openMessages()

    expect(dialog()!.textContent).toContain('Messages (1)')

    const removeMessageButton = dialog()!.querySelector('[aria-label="Remove message"]') as HTMLButtonElement | null
    expect(removeMessageButton).toBeTruthy()
    removeMessageButton!.dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()

    clickButton(confirmDialog()!, 'Remove')
    await flushPromises()

    const call = fetchMock.mock.calls.find(
      ([u, i]) =>
        String(u).includes('/group/1/messages/m1/') && (i as RequestInit | undefined)?.method === 'DELETE'
    )
    expect(call).toBeDefined()
    expect(dialog()!.textContent).not.toContain('Hey team, how is everyone?')
    expect(dialog()!.textContent).toContain('Messages (0)')
  })

  it('re-fetches after a message removal so the pager reflects the new total', async () => {
    const page1 = Array.from({ length: 50 }, (_, i) => ({ ...textMessage, id: `p1-${i}`, text: `msg ${i}` }))
    const fetchMock = fetchMockFor({ page1, page2: [{ ...textMessage, id: 'p2-0' }], total: 51 })
    await mountModal(fetchMock)
    await openMessages()

    const nextButton = () =>
      Array.from(dialog()!.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'Next') as
        | HTMLButtonElement
        | undefined
    expect(nextButton()!.disabled).toBe(false)

    // Remove one message from page 1 -> total drops to 50 -> a single page.
    ;(dialog()!.querySelector('[aria-label="Remove message"]') as HTMLButtonElement).dispatchEvent(
      new Event('click', { bubbles: true })
    )
    await flushPromises()
    clickButton(confirmDialog()!, 'Remove')
    await flushPromises()

    const getCalls = fetchMock.mock.calls.filter(
      ([u, i]) => String(u).includes('/messages/') && (i as RequestInit | undefined)?.method !== 'DELETE'
    )
    expect(getCalls.length).toBeGreaterThanOrEqual(2) // initial load + re-fetch after removal
    expect(nextButton()).toBeUndefined() // pager gone: 50 fits on one page
  })

  it('shows a message-removal failure inline in the dialog, not via window.alert', async () => {
    const alertSpy = vi.fn()
    vi.stubGlobal('alert', alertSpy)
    const fetchMock = fetchMockFor({ page1: [textMessage], total: 1, deleteError: 'Message already removed.' })
    await mountModal(fetchMock)
    await openMessages()

    const removeMessageButton = dialog()!.querySelector('[aria-label="Remove message"]') as HTMLButtonElement | null
    removeMessageButton!.dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()
    clickButton(confirmDialog()!, 'Remove')
    await flushPromises()

    expect(confirmDialog()!.textContent).toContain('Message already removed.')
    expect(alertSpy).not.toHaveBeenCalled()
    // Message stays and the count is unchanged.
    expect(dialog()!.textContent).toContain('Hey team, how is everyone?')
    expect(dialog()!.textContent).toContain('Messages (1)')
  })

  it('requests the next page of messages when the pager is used', async () => {
    const fetchMock = fetchMockFor({ page1: [textMessage], page2: [gifMessage], total: 60 })
    await mountModal(fetchMock)
    await openMessages()

    const nextButton = Array.from(dialog()!.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Next'
    ) as HTMLButtonElement | undefined
    expect(nextButton).toBeDefined()
    expect(nextButton!.disabled).toBe(false)

    nextButton!.dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()

    const page2Call = fetchMock.mock.calls.find(
      ([u, i]) =>
        String(u).includes('/messages/') &&
        String(u).includes('page=2') &&
        (i as RequestInit | undefined)?.method === 'GET'
    )
    expect(page2Call).toBeDefined()
    expect(dialog()!.textContent).toContain('[GIF]')
  })
})
