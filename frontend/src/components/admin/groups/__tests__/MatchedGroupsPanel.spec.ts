import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import MatchedGroupsPanel from '@/components/admin/groups/MatchedGroupsPanel.vue'

const activeGroup = {
  membershipId: 100,
  groupId: 1,
  groupName: 'BTF1',
  countryName: 'Australia',
  studentCount: 2,
  students: [
    { name: 'Ada Lovelace', hasLoggedIn: true, interests: ['Genomics'] },
    { name: 'Grace Hopper', hasLoggedIn: false, interests: [] }
  ],
  mentor: { mentorId: 20, name: 'Marie Curie', isActive: true, countryName: 'Australia', institution: 'USYD' }
}

const inactiveGroup = {
  membershipId: 101,
  groupId: 2,
  groupName: 'BTF2',
  countryName: 'Singapore',
  studentCount: 0,
  students: [],
  mentor: { mentorId: 21, name: 'Nikola Tesla', isActive: false, countryName: 'Singapore', institution: null }
}

const mentorPool = [
  { mentorId: 20, name: 'Marie Curie', countryName: 'Australia', institution: 'USYD', interests: [], maxGroupCount: 4, currentAssignedCount: 1, remainingCapacity: 3 },
  { mentorId: 22, name: 'Ada King', countryName: 'Australia', institution: 'UNSW', interests: [], maxGroupCount: 2, currentAssignedCount: 2, remainingCapacity: 0 },
  { mentorId: 23, name: 'Rosalind Franklin', countryName: 'Australia', institution: 'ANU', interests: [], maxGroupCount: 3, currentAssignedCount: 1, remainingCapacity: 2 }
]

const fetchMockFor = (
  groups: unknown[],
  opts: { replaceStatus?: number; replaceBody?: unknown; failGroupsRefetch?: boolean } = {}
) => {
  let matchedGroupsGets = 0
  return vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const method = (init?.method || 'GET').toUpperCase()
    const u = String(url)

    if (u.includes('/services/csrf/')) {
      return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'csrf-test' }), { status: 200 }))
    }
    if (method === 'POST' && u.includes('/mentor-match/unassign/')) {
      return Promise.resolve(
        new Response(JSON.stringify({ msg: 'ok', data: { unassignedCount: 1 } }), { status: 200 })
      )
    }
    if (method === 'POST' && u.includes('/mentor-match/replace/')) {
      return Promise.resolve(
        new Response(JSON.stringify(opts.replaceBody ?? { msg: 'ok', data: { replaced: 1 } }), {
          status: opts.replaceStatus ?? 200
        })
      )
    }
    if (method === 'POST' && u.includes('/mentor-match/confirm/')) {
      return Promise.resolve(
        new Response(JSON.stringify({ msg: 'ok', data: { confirmedCount: 1 } }), { status: 200 })
      )
    }
    if (method === 'GET' && u.includes('/mentor-match/replace-suggestions/')) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            msg: 'ok',
            data: {
              groupId: 2,
              groupName: 'BTF2',
              suggestions: [
                { mentorUserId: 23, name: 'Rosalind Franklin', institution: 'ANU', remainingCapacity: 2, atCapacity: false, score: 90, reason: 'Great fit' }
              ]
            }
          }),
          { status: 200 }
        )
      )
    }
    if (method === 'GET' && u.includes('/mentor-match/matched-groups/')) {
      matchedGroupsGets += 1
      // First GET is the initial load; a later one is a post-action refresh.
      if (opts.failGroupsRefetch && matchedGroupsGets > 1) {
        return Promise.resolve(new Response(JSON.stringify({ msg: 'Server error', data: null }), { status: 500 }))
      }
      return Promise.resolve(new Response(JSON.stringify({ msg: 'ok', data: groups }), { status: 200 }))
    }
    if (method === 'GET' && u.includes('/mentor-match/mentors/')) {
      return Promise.resolve(new Response(JSON.stringify({ msg: 'ok', data: mentorPool }), { status: 200 }))
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
  })
}

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

describe('MatchedGroupsPanel', () => {
  it('loads and renders matched groups with the inactive badge', async () => {
    const fetchMock = fetchMockFor([activeGroup, inactiveGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    expect(wrapper.text()).toContain('BTF1')
    expect(wrapper.text()).toContain('Marie Curie')
    // Capacity is looked up from the separately-fetched mentor pool (Marie
    // Curie is mentorId 20 there: currentAssignedCount 1, maxGroupCount 4).
    expect(wrapper.text()).toContain('1/4')
    expect(wrapper.text()).toContain('BTF2')
    expect(wrapper.text()).toContain('1 inactive')
    const replaceInactiveButton = wrapper.findAll('button').find((b) => b.text().includes('Replace Inactive Mentors'))
    expect(replaceInactiveButton).toBeDefined()
  })

  it('hides the "Replace Inactive Mentors" button when every mentor is active', async () => {
    const fetchMock = fetchMockFor([activeGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    expect(wrapper.text()).not.toContain('inactive')
    const replaceInactiveButton = wrapper.findAll('button').find((b) => b.text().includes('Replace Inactive Mentors'))
    expect(replaceInactiveButton).toBeUndefined()
  })

  it('expands a row to show its students', async () => {
    const fetchMock = fetchMockFor([activeGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    expect(wrapper.text()).not.toContain('Never signed in')

    await wrapper.find('tbody tr').trigger('click')

    expect(wrapper.text()).toContain('Ada Lovelace')
    expect(wrapper.text()).toContain('Grace Hopper')
    expect(wrapper.text()).toContain('Never signed in')
  })

  it('unassigns a mentor via the per-row replace control', async () => {
    const fetchMock = fetchMockFor([activeGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const replaceButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Replace Mentor')
    expect(replaceButton).toBeDefined()
    await replaceButton!.trigger('click')

    const select = wrapper.find('select')
    expect(select.exists()).toBe(true)
    await select.setValue('__unassign__')

    const confirmButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Confirm')
    await confirmButton!.trigger('click')
    await flushPromises()

    const call = fetchMock.mock.calls.find(
      ([u, i]) => String(u).includes('/mentor-match/unassign/') && (i as RequestInit | undefined)?.method === 'POST'
    ) as [string, RequestInit]
    expect(call).toBeDefined()
    expect(JSON.parse(String(call[1].body))).toEqual({ groupIds: [1] })
  })

  it('replaces a mentor via the per-row replace control', async () => {
    const fetchMock = fetchMockFor([activeGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const replaceButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Replace Mentor')
    await replaceButton!.trigger('click')

    const select = wrapper.find('select')
    await select.setValue('23')

    const confirmButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Confirm')
    await confirmButton!.trigger('click')
    await flushPromises()

    const call = fetchMock.mock.calls.find(
      ([u, i]) => String(u).includes('/mentor-match/replace/') && (i as RequestInit | undefined)?.method === 'POST'
    ) as [string, RequestInit]
    expect(call).toBeDefined()
    expect(JSON.parse(String(call[1].body))).toEqual({
      membershipId: 100,
      groupId: 1,
      newMentorUserId: 23
    })
  })

  it('reports a post-replace refresh failure as a stale list, not a failed replace', async () => {
    const fetchMock = fetchMockFor([activeGroup], { failGroupsRefetch: true })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    await wrapper.findAll('button').find((b) => b.text().trim() === 'Replace Mentor')!.trigger('click')
    await wrapper.find('select').setValue('23')
    await wrapper.findAll('button').find((b) => b.text().trim() === 'Confirm')!.trigger('click')
    await flushPromises()

    // The replace POST did go through...
    expect(
      fetchMock.mock.calls.some(
        ([u, i]) => String(u).includes('/mentor-match/replace/') && (i as RequestInit | undefined)?.method === 'POST'
      )
    ).toBe(true)
    // ...so the message must not blame the replace.
    expect(wrapper.text()).toContain('Mentor updated, but the list could not be refreshed')
    expect(wrapper.text()).not.toContain('Action failed')
  })

  it('sorts by clicking a column header', async () => {
    const fetchMock = fetchMockFor([activeGroup, inactiveGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    // Default sort is Group asc: BTF1 before BTF2.
    const namesBefore = wrapper.findAll('.matched-groups__name').map((n) => n.text())
    expect(namesBefore).toEqual(['BTF1', 'BTF2'])

    const groupHeader = wrapper.findAll('button').find((b) => b.text().trim() === 'Group')
    await groupHeader!.trigger('click')

    const namesAfter = wrapper.findAll('.matched-groups__name').map((n) => n.text())
    expect(namesAfter).toEqual(['BTF2', 'BTF1'])
  })

  it('shows the backend rejection when replacing with a mentor at capacity', async () => {
    const fetchMock = fetchMockFor([activeGroup], {
      replaceStatus: 400,
      replaceBody: { msg: 'Mentor is at capacity (2/2).', data: null }
    })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const replaceButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Replace Mentor')
    await replaceButton!.trigger('click')

    // Full mentors are hidden by default — reveal Ada King (mentorId 22, 2/2).
    await wrapper.find('input[type="checkbox"]').setValue(true)
    const select = wrapper.find('select')
    await select.setValue('22')

    const confirmButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Confirm')
    await confirmButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Mentor is at capacity (2/2).')
    // The inline form must stay open on failure so the admin can pick again,
    // not silently reset as if nothing happened.
    expect(wrapper.find('select').exists()).toBe(true)
  })

  it('replaces an inactive mentor via the bulk "Replace Inactive Mentors" dialog', async () => {
    const fetchMock = fetchMockFor([activeGroup, inactiveGroup])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(MatchedGroupsPanel)
    await flushPromises()

    const bulkButton = wrapper.findAll('button').find((b) => b.text().includes('Replace Inactive Mentors'))
    expect(bulkButton).toBeDefined()
    await bulkButton!.trigger('click')
    await flushPromises()

    const dialog = document.body.querySelector('[role="dialog"]') as HTMLElement
    expect(dialog).toBeTruthy()
    expect(dialog.textContent).toContain('BTF2')
    // The top scored (non-full) suggestion is pre-selected automatically.
    expect(dialog.textContent).toContain('Rosalind Franklin')

    const confirmButton = Array.from(dialog.querySelectorAll('button')).find(
      (b) => b.textContent?.trim().startsWith('Confirm')
    ) as HTMLButtonElement
    expect(confirmButton.disabled).toBe(false)
    confirmButton.dispatchEvent(new Event('click', { bubbles: true }))
    await flushPromises()

    const call = fetchMock.mock.calls.find(
      ([u, i]) => String(u).includes('/mentor-match/confirm/') && (i as RequestInit | undefined)?.method === 'POST'
    ) as [string, RequestInit]
    expect(call).toBeDefined()
    expect(JSON.parse(String(call[1].body))).toEqual({
      assignments: [{ groupId: 2, mentorUserId: 23 }]
    })
    expect(document.body.querySelector('[role="dialog"]')).toBeNull()
  })
})
