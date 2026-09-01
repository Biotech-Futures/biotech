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

const fetchMockFor = (opts: {
  page1?: unknown[]
  page2?: unknown[]
  total?: number
} = {}) =>
  vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const method = (init?.method || 'GET').toUpperCase()
    const u = String(url)

    if (u.includes('/services/csrf/')) {
      return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'csrf-test' }), { status: 200 }))
    }
    if (method === 'DELETE' && u.includes('/members/')) {
      return Promise.resolve(
        new Response(JSON.stringify({ msg: 'Member removed successfully', data: null }), { status: 200 })
      )
    }
    if (method === 'DELETE' && u.includes('/messages/')) {
      return Promise.resolve(
        new Response(JSON.stringify({ msg: 'Message removed successfully', data: null }), { status: 200 })
      )
    }
    if (method === 'GET' && u.includes('/messages/')) {
      const page = u.includes('page=2') ? 2 : 1
      const items = page === 2 ? (opts.page2 ?? []) : (opts.page1 ?? [])
      const total = opts.total ?? items.length
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
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
  })

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
  it('renders the mentor, members, and messages once opened', async () => {
    const fetchMock = fetchMockFor({ page1: [textMessage, gifMessage], total: 2 })
    await mountModal(fetchMock)

    const text = dialog()!.textContent!
    expect(text).toContain('Marie Curie')
    expect(text).toContain('Ada Lovelace')
    expect(text).toContain('Grace Hopper')
    expect(text).toContain('Hey team, how is everyone?')
    expect(text).toContain('[GIF]')
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

  it('removes a message after confirmation and decrements the total', async () => {
    const fetchMock = fetchMockFor({ page1: [textMessage], total: 1 })
    await mountModal(fetchMock)

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

  it('requests the next page of messages when the pager is used', async () => {
    const fetchMock = fetchMockFor({ page1: [textMessage], page2: [gifMessage], total: 60 })
    await mountModal(fetchMock)

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
